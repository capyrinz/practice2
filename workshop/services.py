from django.conf import settings
from django.core.mail import send_mail
from django.db import transaction
from django.utils import timezone

from .models import RepairComment, RepairRequest, SparePart, StatusHistory, UsedPart


class StockError(Exception):
    """Недостаточно запчастей на складе."""


def change_status(repair_request, new_status, user, comment=""):
    """Единая точка смены статуса: история, дата выдачи и e-mail клиенту."""
    valid = dict(RepairRequest.STATUS_CHOICES)
    if new_status not in valid:
        raise ValueError("Неизвестный статус")
    if repair_request.status == new_status and not comment:
        return False

    repair_request.status = new_status
    if new_status == RepairRequest.STATUS_ISSUED:
        if not repair_request.issued_at:
            repair_request.issued_at = timezone.now()
    else:
        repair_request.issued_at = None
    repair_request.save(update_fields=["status", "issued_at", "updated_at"])
    StatusHistory.objects.create(
        request=repair_request,
        status=new_status,
        changed_by=user,
        comment=comment,
    )
    transaction.on_commit(lambda: notify_status_change(repair_request, new_status))
    return True


def add_comment(repair_request, user, text):
    text = (text or "").strip()
    if not text:
        return None
    return RepairComment.objects.create(request=repair_request, author=user, text=text)


def notify_status_change(repair_request, status):
    client = repair_request.client
    if not client.email:
        return
    subject = f"Заявка {repair_request.number}: {dict(RepairRequest.STATUS_CHOICES)[status]}"
    body = (
        f"Здравствуйте, {client.full_name}!\n\n"
        f"Статус вашей заявки {repair_request.number} изменён: "
        f"{dict(RepairRequest.STATUS_CHOICES)[status]}.\n"
        f"Проверить заявку: {settings.SITE_URL}/status/{repair_request.public_token}/\n\n"
        "Ремонтная мастерская «Мастер+»"
    )
    try:
        send_mail(subject, body, settings.DEFAULT_FROM_EMAIL, [client.email], fail_silently=True)
        RepairRequest.objects.filter(pk=repair_request.pk).update(notified_at=timezone.now())
    except Exception:  # почтовый сервер недоступен — заявка не должна падать
        pass


@transaction.atomic
def add_used_part(repair_request, part_id, quantity):
    if quantity < 1:
        raise StockError("Количество должно быть не меньше 1.")
    part = SparePart.objects.select_for_update().get(pk=part_id)
    if not part.is_active:
        raise StockError("Запчасть снята с учёта.")
    if part.quantity < quantity:
        raise StockError(
            f"На складе только {part.quantity} шт. «{part.name}». Уменьшите количество."
        )
    part.quantity -= quantity
    part.save(update_fields=["quantity"])
    return UsedPart.objects.create(
        request=repair_request, part=part, quantity=quantity, price=part.price
    )


@transaction.atomic
def remove_used_part(used_part):
    part = SparePart.objects.select_for_update().get(pk=used_part.part_id)
    part.quantity += used_part.quantity
    part.save(update_fields=["quantity"])
    used_part.delete()
