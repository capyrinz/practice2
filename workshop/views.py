import json
import re
from datetime import datetime

from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count, F, Q
from django.http import FileResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from .decorators import role_required
from .forms import (
    AddPartForm,
    AssignForm,
    CommentForm,
    EmployeeEditForm,
    EmployeeForm,
    LoginForm,
    PartForm,
    RegisterForm,
    RequestForm,
    ServiceForm,
    StatusForm,
    WorkCostForm,
)
from .models import RepairRequest, Service, SparePart, StatusHistory, UsedPart, User
from .pdf import build_receipt_pdf
from .services import (
    StockError,
    add_comment,
    add_used_part,
    change_status,
    remove_used_part,
)

MONTHS = ["янв", "фев", "мар", "апр", "май", "июн", "июл", "авг", "сен", "окт", "ноя", "дек"]
ACTIVE_STATUSES = [
    RepairRequest.STATUS_ACCEPTED,
    RepairRequest.STATUS_DIAGNOSTICS,
    RepairRequest.STATUS_IN_REPAIR,
    RepairRequest.STATUS_READY,
]


# ---------------------------------------------------------------- публичная часть


def home(request):
    services = Service.objects.filter(is_active=True)
    query = request.GET.get("q", "").strip()
    if query:
        services = services.filter(Q(name__icontains=query) | Q(description__icontains=query))
    return render(
        request,
        "public/home.html",
        {
            "services": services,
            "query": query,
            "services_count": Service.objects.filter(is_active=True).count(),
        },
    )


def public_status(request, token):
    repair_request = get_object_or_404(RepairRequest, public_token=token)
    return render(
        request,
        "public/status.html",
        {
            "request": repair_request,
            "history": repair_request.history.select_related("changed_by")[:20],
        },
    )


def register(request):
    if request.user.is_authenticated:
        return redirect("dashboard")
    form = RegisterForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save(commit=False)
        user.role = User.ROLE_CLIENT
        user.email = form.cleaned_data["email"]
        user.save()
        login(request, user)
        messages.success(request, "Регистрация завершена. Добро пожаловать!")
        return redirect("client_requests")
    return render(request, "auth/register.html", {"form": form})


class AppLoginView(LoginView):
    template_name = "auth/login.html"
    authentication_form = LoginForm
    redirect_authenticated_user = True


@login_required
def dashboard(request):
    if request.user.is_admin or request.user.is_superuser:
        return redirect("admin_dashboard")
    if request.user.is_master:
        return redirect("master_requests")
    return redirect("client_requests")


# ---------------------------------------------------------------- клиент


def _can_view(user, repair_request):
    if user.is_superuser or user.is_admin:
        return True
    if user.is_master:
        return repair_request.master_id == user.pk
    return repair_request.client_id == user.pk


def _get_visible_request(user, pk):
    repair_request = get_object_or_404(
        RepairRequest.objects.select_related("client", "master", "service"), pk=pk
    )
    if not _can_view(user, repair_request):
        raise PermissionDenied("Это заявка другого клиента.")
    return repair_request


@role_required(User.ROLE_CLIENT)
def client_requests(request):
    status = request.GET.get("status", "")
    requests = RepairRequest.objects.filter(client=request.user).select_related(
        "master", "service"
    )
    if status:
        requests = requests.filter(status=status)
    counts = {
        row["status"]: row["total"]
        for row in RepairRequest.objects.filter(client=request.user)
        .values("status")
        .annotate(total=Count("id"))
    }
    return render(
        request,
        "client/requests.html",
        {
            "requests": requests,
            "status_filter": status,
            "statuses": RepairRequest.STATUS_CHOICES,
            "counts": counts,
            "total": sum(counts.values()),
        },
    )


@role_required(User.ROLE_CLIENT)
def client_request_create(request):
    form = RequestForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        repair_request = form.save(commit=False)
        repair_request.client = request.user
        repair_request.save()
        StatusHistory.objects.create(
            request=repair_request,
            status=RepairRequest.STATUS_ACCEPTED,
            changed_by=request.user,
            comment="Заявка создана клиентом",
        )
        messages.success(
            request, f"Заявка {repair_request.number} принята. Мы свяжемся с вами."
        )
        return redirect("request_detail", pk=repair_request.pk)
    return render(request, "client/request_form.html", {"form": form})


@login_required
def request_detail(request, pk):
    repair_request = _get_visible_request(request.user, pk)
    can_manage = request.user.is_admin or request.user.is_superuser or (
        request.user.is_master and repair_request.master_id == request.user.pk
    )
    context = {
        "request": repair_request,
        "history": repair_request.history.select_related("changed_by"),
        "comments": repair_request.comments.select_related("author"),
        "used_parts": repair_request.used_parts.select_related("part"),
        "can_manage": can_manage,
        "is_admin": request.user.is_admin or request.user.is_superuser,
        "status_form": StatusForm(initial={"status": repair_request.status}),
        "comment_form": CommentForm(),
        "work_cost_form": WorkCostForm(initial={"work_cost": repair_request.work_cost}),
        "add_part_form": AddPartForm(),
    }
    return render(request, "client/request_detail.html", context)


@login_required
def receipt_pdf(request, pk):
    repair_request = _get_visible_request(request.user, pk)
    content = build_receipt_pdf(repair_request)
    response = FileResponse(
        iter([content]),
        content_type="application/pdf",
        as_attachment=True,
        filename=f"kvitantsiya_{repair_request.number}.pdf",
    )
    return response


# ---------------------------------------------------------------- мастер


@role_required(User.ROLE_MASTER)
def master_requests(request):
    status = request.GET.get("status", "")
    requests = RepairRequest.objects.filter(master=request.user).select_related(
        "client", "service"
    )
    if status:
        requests = requests.filter(status=status)
    counts = {
        row["status"]: row["total"]
        for row in RepairRequest.objects.filter(master=request.user)
        .values("status")
        .annotate(total=Count("id"))
    }
    return render(
        request,
        "master/requests.html",
        {
            "requests": requests,
            "status_filter": status,
            "statuses": RepairRequest.STATUS_CHOICES,
            "counts": counts,
            "total": sum(counts.values()),
        },
    )


def _manageable_request(user, pk):
    repair_request = get_object_or_404(RepairRequest, pk=pk)
    if user.is_admin or user.is_superuser:
        return repair_request
    if repair_request.master_id != user.pk:
        raise PermissionDenied("Заявка назначена другому мастеру.")
    return repair_request


@role_required(User.ROLE_MASTER, User.ROLE_ADMIN)
@require_POST
def change_status_view(request, pk):
    repair_request = _manageable_request(request.user, pk)
    form = StatusForm(request.POST)
    if form.is_valid():
        changed = change_status(
            repair_request,
            form.cleaned_data["status"],
            request.user,
            form.cleaned_data["comment"],
        )
        messages.success(
            request,
            "Статус обновлён." if changed else "Статус не изменился.",
        )
    else:
        messages.error(request, "Не удалось изменить статус: проверьте форму.")
    return redirect("request_detail", pk=pk)


@role_required(User.ROLE_MASTER, User.ROLE_ADMIN)
@require_POST
def set_work_cost(request, pk):
    repair_request = _manageable_request(request.user, pk)
    form = WorkCostForm(request.POST)
    if form.is_valid():
        repair_request.work_cost = form.cleaned_data["work_cost"]
        repair_request.save(update_fields=["work_cost", "updated_at"])
        messages.success(request, "Стоимость работ сохранена.")
    else:
        messages.error(request, "Укажите корректную стоимость работ.")
    return redirect("request_detail", pk=pk)


@role_required(User.ROLE_MASTER, User.ROLE_ADMIN)
@require_POST
def add_part_view(request, pk):
    repair_request = _manageable_request(request.user, pk)
    form = AddPartForm(request.POST)
    if form.is_valid():
        try:
            add_used_part(repair_request, form.cleaned_data["part"].pk, form.cleaned_data["quantity"])
        except (StockError, SparePart.DoesNotExist) as error:
            messages.error(request, str(error))
        else:
            messages.success(request, "Запчасть списана со склада и добавлена в заявку.")
    else:
        messages.error(request, "Проверьте выбранную запчасть и количество.")
    return redirect("request_detail", pk=pk)


@role_required(User.ROLE_MASTER, User.ROLE_ADMIN)
@require_POST
def remove_part_view(request, pk, used_id):
    repair_request = _manageable_request(request.user, pk)
    used_part = get_object_or_404(UsedPart, pk=used_id, request=repair_request)
    remove_used_part(used_part)
    messages.success(request, "Запчасть возвращена на склад.")
    return redirect("request_detail", pk=pk)


@role_required(User.ROLE_MASTER, User.ROLE_ADMIN)
@require_POST
def add_comment_view(request, pk):
    repair_request = _manageable_request(request.user, pk)
    form = CommentForm(request.POST)
    if form.is_valid():
        add_comment(repair_request, request.user, form.cleaned_data["text"])
        messages.success(request, "Комментарий добавлен.")
    else:
        messages.error(request, "Комментарий не может быть пустым.")
    return redirect("request_detail", pk=pk)


# ---------------------------------------------------------------- администратор


@role_required(User.ROLE_ADMIN)
def admin_dashboard(request):
    requests = RepairRequest.objects.select_related("client", "master", "service")
    issued = list(
        requests.filter(status=RepairRequest.STATUS_ISSUED).prefetch_related("used_parts")
    )
    context = {
        "requests_total": requests.count(),
        "requests_active": requests.filter(status__in=ACTIVE_STATUSES).count(),
        "ready_count": requests.filter(status=RepairRequest.STATUS_READY).count(),
        "clients_count": User.objects.filter(role=User.ROLE_CLIENT).count(),
        "masters_count": User.objects.filter(role=User.ROLE_MASTER, is_active=True).count(),
        "revenue": sum((r.total_cost for r in issued), start=0),
        "latest": requests[:8],
        "low_stock": [p for p in SparePart.objects.filter(is_active=True) if p.is_low_stock][:6],
        "unassigned": requests.filter(master__isnull=True, status__in=ACTIVE_STATUSES).count(),
    }
    return render(request, "admin_panel/dashboard.html", context)


@role_required(User.ROLE_ADMIN)
def admin_requests(request):
    requests = RepairRequest.objects.select_related("client", "master", "service")
    status = request.GET.get("status", "")
    master_id = request.GET.get("master", "")
    query = request.GET.get("q", "").strip()
    if status:
        requests = requests.filter(status=status)
    if master_id:
        requests = requests.filter(master_id=master_id)
    if query:
        filters = (
            Q(device_model__icontains=query)
            | Q(description__icontains=query)
            | Q(client__username__icontains=query)
            | Q(client__last_name__icontains=query)
        )
        if query.isdigit():
            filters |= Q(pk=int(query))
        else:
            number_match = re.fullmatch(r"[зz]\s*-?\s*(\d+)", query.lower())
            if number_match:
                filters |= Q(pk=int(number_match.group(1)))
        requests = requests.filter(filters)
    paginator = Paginator(requests.distinct(), 20)
    page = paginator.get_page(request.GET.get("page"))
    return render(
        request,
        "admin_panel/requests.html",
        {
            "page": page,
            "requests": page.object_list,
            "statuses": RepairRequest.STATUS_CHOICES,
            "status_filter": status,
            "master_filter": master_id,
            "query": query,
            "masters": User.objects.filter(role=User.ROLE_MASTER),
        },
    )


@role_required(User.ROLE_ADMIN)
def admin_kanban(request):
    columns = []
    for status, label in RepairRequest.STATUS_CHOICES:
        columns.append(
            {
                "status": status,
                "label": label,
                "requests": RepairRequest.objects.filter(status=status).select_related(
                    "client", "master", "service"
                )[:60],
            }
        )
    return render(request, "admin_panel/kanban.html", {"columns": columns})


@role_required(User.ROLE_ADMIN)
@require_POST
def kanban_move(request, pk):
    repair_request = get_object_or_404(RepairRequest, pk=pk)
    try:
        payload = json.loads(request.body or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"ok": False, "error": "Некорректный JSON"}, status=400)
    new_status = payload.get("status")
    if new_status not in dict(RepairRequest.STATUS_CHOICES):
        return JsonResponse({"ok": False, "error": "Неизвестный статус"}, status=400)
    change_status(
        repair_request,
        new_status,
        request.user,
        "Статус изменён на Kanban-доске",
    )
    return JsonResponse(
        {
            "ok": True,
            "status": repair_request.status,
            "label": repair_request.get_status_display(),
            "number": repair_request.number,
        }
    )


@role_required(User.ROLE_ADMIN)
def admin_assign(request, pk):
    repair_request = get_object_or_404(RepairRequest, pk=pk)
    previous_master_id = repair_request.master_id
    form = AssignForm(request.POST or None, instance=repair_request)
    if request.method == "POST" and form.is_valid():
        form.save()
        if repair_request.master_id and repair_request.master_id != previous_master_id:
            StatusHistory.objects.create(
                request=repair_request,
                status=repair_request.status,
                changed_by=request.user,
                comment=f"Назначен мастер: {repair_request.master.full_name}",
            )
        messages.success(request, "Заявка обновлена.")
        return redirect("request_detail", pk=pk)
    return render(
        request,
        "admin_panel/assign.html",
        {"form": form, "request": repair_request},
    )


@role_required(User.ROLE_ADMIN)
@require_POST
def admin_request_delete(request, pk):
    repair_request = get_object_or_404(RepairRequest, pk=pk)
    number = repair_request.number
    with transaction.atomic():
        for used in repair_request.used_parts.select_related("part"):
            SparePart.objects.filter(pk=used.part_id).update(
                quantity=F("quantity") + used.quantity
            )
        if repair_request.photo:
            repair_request.photo.delete(save=False)
        repair_request.delete()
    messages.success(request, f"Заявка {number} удалена, запчасти возвращены на склад.")
    return redirect("admin_requests")


@role_required(User.ROLE_ADMIN)
def admin_services(request):
    services = Service.objects.annotate(requests_count=Count("requests"))
    return render(request, "admin_panel/services.html", {"services": services})


@role_required(User.ROLE_ADMIN)
def service_form(request, pk=None):
    service = get_object_or_404(Service, pk=pk) if pk else None
    form = ServiceForm(request.POST or None, instance=service)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Услуга сохранена.")
        return redirect("admin_services")
    return render(
        request,
        "admin_panel/service_form.html",
        {"form": form, "service": service},
    )


@role_required(User.ROLE_ADMIN)
@require_POST
def service_toggle(request, pk):
    service = get_object_or_404(Service, pk=pk)
    service.is_active = not service.is_active
    service.save(update_fields=["is_active"])
    messages.success(request, "Статус услуги изменён.")
    return redirect("admin_services")


@role_required(User.ROLE_ADMIN)
def admin_parts(request):
    parts = SparePart.objects.all()
    query = request.GET.get("q", "").strip()
    if query:
        parts = parts.filter(Q(name__icontains=query) | Q(sku__icontains=query))
    low_only = request.GET.get("low") == "1"
    parts = list(parts)
    if low_only:
        parts = [part for part in parts if part.is_low_stock]
    return render(
        request,
        "admin_panel/parts.html",
        {
            "parts": parts,
            "query": query,
            "low_only": low_only,
            "low_count": sum(1 for part in SparePart.objects.all() if part.is_low_stock),
            "stock_value": sum((part.quantity * part.price for part in parts), start=0),
        },
    )


@role_required(User.ROLE_ADMIN)
def part_form(request, pk=None):
    part = get_object_or_404(SparePart, pk=pk) if pk else None
    form = PartForm(request.POST or None, instance=part)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Запчасть сохранена.")
        return redirect("admin_parts")
    return render(
        request,
        "admin_panel/part_form.html",
        {"form": form, "part": part},
    )


@role_required(User.ROLE_ADMIN)
@require_POST
def part_toggle(request, pk):
    part = get_object_or_404(SparePart, pk=pk)
    part.is_active = not part.is_active
    part.save(update_fields=["is_active"])
    messages.success(request, "Статус запчасти изменён.")
    return redirect("admin_parts")


@role_required(User.ROLE_ADMIN)
def admin_employees(request):
    employees = User.objects.filter(role__in=[User.ROLE_MASTER, User.ROLE_ADMIN]).annotate(
        active_requests=Count(
            "assigned_requests", filter=Q(assigned_requests__status__in=ACTIVE_STATUSES)
        )
    )
    return render(request, "admin_panel/employees.html", {"employees": employees})


@role_required(User.ROLE_ADMIN)
def employee_form(request, pk=None):
    employee = get_object_or_404(User, pk=pk) if pk else None
    form_class = EmployeeEditForm if employee else EmployeeForm
    form = form_class(request.POST or None, instance=employee)
    if request.method == "POST" and form.is_valid():
        obj = form.save(commit=False)
        if not employee:
            obj.role = form.cleaned_data["role"]
        obj.save()
        messages.success(request, "Сотрудник сохранён.")
        return redirect("admin_employees")
    return render(
        request,
        "admin_panel/employee_form.html",
        {"form": form, "employee": employee},
    )


@role_required(User.ROLE_ADMIN)
@require_POST
def employee_toggle(request, pk):
    employee = get_object_or_404(User, pk=pk)
    if employee.pk == request.user.pk:
        messages.error(request, "Нельзя заблокировать собственную учётную запись.")
        return redirect("admin_employees")
    employee.is_active = not employee.is_active
    employee.save(update_fields=["is_active"])
    messages.success(request, "Доступ сотрудника изменён.")
    return redirect("admin_employees")


@role_required(User.ROLE_ADMIN)
def admin_users(request):
    role = request.GET.get("role", User.ROLE_CLIENT)
    users = User.objects.filter(role=role).annotate(requests_count=Count("requests"))
    return render(
        request,
        "admin_panel/users.html",
        {
            "users": users,
            "role": role,
            "roles": User.ROLE_CHOICES,
        },
    )


@role_required(User.ROLE_ADMIN)
@require_POST
def user_toggle(request, pk):
    user = get_object_or_404(User, pk=pk)
    if user.pk == request.user.pk:
        messages.error(request, "Нельзя заблокировать собственную учётную запись.")
        return redirect("admin_users")
    user.is_active = not user.is_active
    user.save(update_fields=["is_active"])
    messages.success(request, "Доступ пользователя изменён.")
    return redirect("admin_users")


def _shift_month(year, month, delta):
    index = year * 12 + (month - 1) + delta
    return index // 12, index % 12 + 1


@role_required(User.ROLE_ADMIN)
def admin_stats(request):
    today = timezone.localdate()
    start_year, start_month = _shift_month(today.year, today.month, -5)
    start = timezone.make_aware(
        datetime(start_year, start_month, 1), timezone.get_current_timezone()
    )

    requests = list(
        RepairRequest.objects.select_related("master")
        .prefetch_related("used_parts")
        .filter(created_at__gte=start)
    )
    issued_in_window = list(
        RepairRequest.objects.filter(
            status=RepairRequest.STATUS_ISSUED, issued_at__gte=start
        ).prefetch_related("used_parts")
    )
    labels, counts, revenue = [], [], []
    for offset in range(6):
        year, month = _shift_month(start_year, start_month, offset)
        labels.append(f"{MONTHS[month - 1]} {str(year)[2:]}")
        month_requests = [
            r
            for r in requests
            if timezone.localtime(r.created_at).year == year
            and timezone.localtime(r.created_at).month == month
        ]
        counts.append(len(month_requests))
        revenue.append(
            float(
                sum(
                    (
                        r.total_cost
                        for r in issued_in_window
                        if timezone.localtime(r.issued_at).year == year
                        and timezone.localtime(r.issued_at).month == month
                    ),
                    start=0,
                )
            )
        )

    device_counts = dict(
        RepairRequest.objects.values_list("device_type").annotate(total=Count("id"))
    )
    device_labels = [
        dict(RepairRequest.DEVICE_CHOICES).get(key, key) for key in device_counts.keys()
    ]
    service_counts = (
        RepairRequest.objects.filter(service__isnull=False)
        .values("service__name")
        .annotate(total=Count("id"))
        .order_by("-total")[:6]
    )
    master_load = list(
        User.objects.filter(role=User.ROLE_MASTER)
        .annotate(
            active=Count(
                "assigned_requests", filter=Q(assigned_requests__status__in=ACTIVE_STATUSES)
            ),
            done=Count(
                "assigned_requests", filter=Q(assigned_requests__status=RepairRequest.STATUS_ISSUED)
            ),
        )
        .order_by("-active", "first_name")
    )
    all_requests = RepairRequest.objects.all()
    issued_requests = list(
        all_requests.filter(status=RepairRequest.STATUS_ISSUED).prefetch_related("used_parts")
    )
    revenue_total = sum((r.total_cost for r in issued_requests), start=0)
    context = {
        "labels": labels,
        "counts": counts,
        "revenue": revenue,
        "device_labels": device_labels,
        "device_values": list(device_counts.values()),
        "service_labels": [row["service__name"] for row in service_counts],
        "service_values": [row["total"] for row in service_counts],
        "master_load": master_load,
        "max_load": max((m.active for m in master_load), default=1) or 1,
        "total_requests": all_requests.count(),
        "issued_count": len(issued_requests),
        "revenue_total": revenue_total,
        "avg_cost": (revenue_total / len(issued_requests)) if issued_requests else 0,
        "low_stock": [p for p in SparePart.objects.filter(is_active=True) if p.is_low_stock],
    }
    return render(request, "admin_panel/stats.html", context)
