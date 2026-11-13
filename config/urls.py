from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.auth.views import LogoutView
from django.urls import path

from workshop import views

urlpatterns = [
    path("django-admin/", admin.site.urls),
    path("", views.home, name="home"),
    path("status/<uuid:token>/", views.public_status, name="public_status"),
    # авторизация
    path("register/", views.register, name="register"),
    path("login/", views.AppLoginView.as_view(), name="login"),
    path("logout/", LogoutView.as_view(), name="logout"),
    path("dashboard/", views.dashboard, name="dashboard"),
    # клиент
    path("client/requests/", views.client_requests, name="client_requests"),
    path("client/requests/new/", views.client_request_create, name="client_request_create"),
    # общие страницы заявки
    path("requests/<int:pk>/", views.request_detail, name="request_detail"),
    path("requests/<int:pk>/receipt.pdf", views.receipt_pdf, name="receipt_pdf"),
    path("requests/<int:pk>/status/", views.change_status_view, name="change_status"),
    path("requests/<int:pk>/work-cost/", views.set_work_cost, name="set_work_cost"),
    path("requests/<int:pk>/comment/", views.add_comment_view, name="comment_create"),
    path("requests/<int:pk>/parts/add/", views.add_part_view, name="add_part"),
    path(
        "requests/<int:pk>/parts/<int:used_id>/remove/",
        views.remove_part_view,
        name="remove_part",
    ),
    # мастер
    path("master/", views.master_requests, name="master_requests"),
    # администратор
    path("manage/", views.admin_dashboard, name="admin_dashboard"),
    path("manage/requests/", views.admin_requests, name="admin_requests"),
    path("manage/kanban/", views.admin_kanban, name="admin_kanban"),
    path("manage/kanban/<int:pk>/move/", views.kanban_move, name="kanban_move"),
    path("manage/requests/<int:pk>/assign/", views.admin_assign, name="admin_assign"),
    path(
        "manage/requests/<int:pk>/delete/",
        views.admin_request_delete,
        name="admin_request_delete",
    ),
    path("manage/services/", views.admin_services, name="admin_services"),
    path("manage/services/new/", views.service_form, name="service_create"),
    path("manage/services/<int:pk>/edit/", views.service_form, name="service_edit"),
    path("manage/services/<int:pk>/toggle/", views.service_toggle, name="service_toggle"),
    path("manage/parts/", views.admin_parts, name="admin_parts"),
    path("manage/parts/new/", views.part_form, name="part_create"),
    path("manage/parts/<int:pk>/edit/", views.part_form, name="part_edit"),
    path("manage/parts/<int:pk>/toggle/", views.part_toggle, name="part_toggle"),
    path("manage/employees/", views.admin_employees, name="admin_employees"),
    path("manage/employees/new/", views.employee_form, name="employee_create"),
    path("manage/employees/<int:pk>/edit/", views.employee_form, name="employee_edit"),
    path("manage/employees/<int:pk>/toggle/", views.employee_toggle, name="employee_toggle"),
    path("manage/users/", views.admin_users, name="admin_users"),
    path("manage/users/<int:pk>/toggle/", views.user_toggle, name="user_toggle"),
    path("manage/stats/", views.admin_stats, name="admin_stats"),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

admin.site.site_header = "Ремонтная мастерская «Мастер+»"
admin.site.site_title = "Мастер+"
admin.site.index_title = "Служебное администрирование"
