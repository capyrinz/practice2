from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import RepairComment, RepairRequest, Service, SparePart, StatusHistory, UsedPart, User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    fieldsets = BaseUserAdmin.fieldsets + (
        ("Мастерская", {"fields": ("role", "phone")}),
    )
    add_fieldsets = BaseUserAdmin.add_fieldsets + (
        ("Мастерская", {"fields": ("role", "phone", "email")}),
    )
    list_display = ("username", "full_name", "role", "email", "phone", "is_active")
    list_filter = ("role", "is_active")
    search_fields = ("username", "first_name", "last_name", "email", "phone")


@admin.register(Service)
class ServiceAdmin(admin.ModelAdmin):
    list_display = ("name", "price_from", "duration_days", "is_active")
    list_filter = ("is_active",)
    search_fields = ("name",)


@admin.register(SparePart)
class SparePartAdmin(admin.ModelAdmin):
    list_display = ("name", "sku", "quantity", "min_quantity", "price", "is_active")
    list_filter = ("is_active",)
    search_fields = ("name", "sku")


class UsedPartInline(admin.TabularInline):
    model = UsedPart
    extra = 0


class StatusHistoryInline(admin.TabularInline):
    model = StatusHistory
    extra = 0
    can_delete = False
    readonly_fields = ("status", "comment", "changed_by", "created_at")


@admin.register(RepairRequest)
class RepairRequestAdmin(admin.ModelAdmin):
    list_display = ("number", "client", "master", "device_type", "status", "created_at")
    list_filter = ("status", "device_type", "master")
    search_fields = ("client__username", "device_model", "description")
    inlines = [UsedPartInline, StatusHistoryInline]


@admin.register(RepairComment)
class RepairCommentAdmin(admin.ModelAdmin):
    list_display = ("request", "author", "created_at")
