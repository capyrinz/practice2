import uuid

from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    ROLE_CLIENT = "client"
    ROLE_MASTER = "master"
    ROLE_ADMIN = "admin"
    ROLE_CHOICES = [
        (ROLE_CLIENT, "Клиент"),
        (ROLE_MASTER, "Мастер"),
        (ROLE_ADMIN, "Администратор"),
    ]

    role = models.CharField("Роль", max_length=20, choices=ROLE_CHOICES, default=ROLE_CLIENT)
    phone = models.CharField("Телефон", max_length=20, blank=True)

    class Meta:
        verbose_name = "Пользователь"
        verbose_name_plural = "Пользователи"

    def save(self, *args, **kwargs):
        if self.is_superuser:
            self.role = self.ROLE_ADMIN
        super().save(*args, **kwargs)

    @property
    def is_client(self):
        return self.role == self.ROLE_CLIENT

    @property
    def is_master(self):
        return self.role == self.ROLE_MASTER

    @property
    def is_admin(self):
        return self.role == self.ROLE_ADMIN

    @property
    def full_name(self):
        return self.get_full_name() or self.username

    def __str__(self):
        return f"{self.full_name} ({self.get_role_display()})"


class Service(models.Model):
    name = models.CharField("Название услуги", max_length=150)
    description = models.TextField("Описание", blank=True)
    price_from = models.DecimalField("Цена от, ₽", max_digits=10, decimal_places=2)
    duration_days = models.PositiveSmallIntegerField("Срок, дней", default=1)
    is_active = models.BooleanField("Активна", default=True)
    created_at = models.DateTimeField("Создана", auto_now_add=True)

    class Meta:
        verbose_name = "Услуга"
        verbose_name_plural = "Услуги"
        ordering = ["name"]

    def __str__(self):
        return self.name


class RepairRequest(models.Model):
    DEVICE_PHONE = "phone"
    DEVICE_LAPTOP = "laptop"
    DEVICE_TABLET = "tablet"
    DEVICE_TV = "tv"
    DEVICE_APPLIANCE = "appliance"
    DEVICE_OTHER = "other"
    DEVICE_CHOICES = [
        (DEVICE_PHONE, "Смартфон"),
        (DEVICE_LAPTOP, "Ноутбук"),
        (DEVICE_TABLET, "Планшет"),
        (DEVICE_TV, "Телевизор"),
        (DEVICE_APPLIANCE, "Бытовая техника"),
        (DEVICE_OTHER, "Другое"),
    ]

    STATUS_ACCEPTED = "accepted"
    STATUS_DIAGNOSTICS = "diagnostics"
    STATUS_IN_REPAIR = "in_repair"
    STATUS_READY = "ready"
    STATUS_ISSUED = "issued"
    STATUS_CHOICES = [
        (STATUS_ACCEPTED, "Принята"),
        (STATUS_DIAGNOSTICS, "В диагностике"),
        (STATUS_IN_REPAIR, "В ремонте"),
        (STATUS_READY, "Готова к выдаче"),
        (STATUS_ISSUED, "Выдана"),
    ]
    STATUS_CLASSES = {
        STATUS_ACCEPTED: "status-accepted",
        STATUS_DIAGNOSTICS: "status-diagnostics",
        STATUS_IN_REPAIR: "status-in-repair",
        STATUS_READY: "status-ready",
        STATUS_ISSUED: "status-issued",
    }

    client = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="requests", verbose_name="Клиент"
    )
    master = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assigned_requests",
        verbose_name="Мастер",
        limit_choices_to={"role": User.ROLE_MASTER},
    )
    service = models.ForeignKey(
        Service,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="requests",
        verbose_name="Услуга",
    )
    device_type = models.CharField("Тип устройства", max_length=20, choices=DEVICE_CHOICES)
    device_model = models.CharField("Модель / бренд", max_length=120, blank=True)
    description = models.TextField("Описание неисправности")
    photo = models.ImageField("Фото устройства", upload_to="requests/%Y/%m/", blank=True)
    status = models.CharField(
        "Статус", max_length=20, choices=STATUS_CHOICES, default=STATUS_ACCEPTED
    )
    estimated_cost = models.DecimalField(
        "Предварительная стоимость, ₽", max_digits=10, decimal_places=2, null=True, blank=True
    )
    work_cost = models.DecimalField(
        "Стоимость работ, ₽", max_digits=10, decimal_places=2, default=0
    )
    public_token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    created_at = models.DateTimeField("Создана", auto_now_add=True)
    updated_at = models.DateTimeField("Обновлена", auto_now=True)
    issued_at = models.DateTimeField("Выдана", null=True, blank=True)
    notified_at = models.DateTimeField("Уведомление отправлено", null=True, blank=True)

    class Meta:
        verbose_name = "Заявка"
        verbose_name_plural = "Заявки"
        ordering = ["-created_at"]

    @property
    def number(self):
        return f"З-{self.pk:06d}" if self.pk else "З-нов"

    @property
    def status_class(self):
        return self.STATUS_CLASSES.get(self.status, "status-accepted")

    @property
    def status_index(self):
        statuses = [value for value, _ in self.STATUS_CHOICES]
        return statuses.index(self.status) if self.status in statuses else 0

    @property
    def parts_cost(self):
        return sum((p.total for p in self.used_parts.all()), start=0)

    @property
    def total_cost(self):
        return self.work_cost + self.parts_cost

    def __str__(self):
        return f"{self.number} — {self.get_device_type_display()}"


class StatusHistory(models.Model):
    request = models.ForeignKey(
        RepairRequest, on_delete=models.CASCADE, related_name="history", verbose_name="Заявка"
    )
    status = models.CharField("Статус", max_length=20, choices=RepairRequest.STATUS_CHOICES)
    comment = models.TextField("Комментарий", blank=True)
    changed_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, verbose_name="Изменил"
    )
    created_at = models.DateTimeField("Дата", auto_now_add=True)

    class Meta:
        verbose_name = "История статуса"
        verbose_name_plural = "История статусов"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.request.number}: {self.get_status_display()}"


class RepairComment(models.Model):
    request = models.ForeignKey(
        RepairRequest, on_delete=models.CASCADE, related_name="comments", verbose_name="Заявка"
    )
    author = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name="Автор")
    text = models.TextField("Комментарий")
    created_at = models.DateTimeField("Дата", auto_now_add=True)

    class Meta:
        verbose_name = "Комментарий"
        verbose_name_plural = "Комментарии"
        ordering = ["created_at"]

    def __str__(self):
        return f"Комментарий от {self.author}"


class SparePart(models.Model):
    name = models.CharField("Название", max_length=150)
    sku = models.CharField("Артикул", max_length=50, unique=True)
    quantity = models.PositiveIntegerField("Остаток", default=0)
    min_quantity = models.PositiveIntegerField("Минимальный остаток", default=1)
    price = models.DecimalField("Цена, ₽", max_digits=10, decimal_places=2)
    is_active = models.BooleanField("Активна", default=True)
    created_at = models.DateTimeField("Создана", auto_now_add=True)

    class Meta:
        verbose_name = "Запчасть"
        verbose_name_plural = "Запчасти"
        ordering = ["name"]

    @property
    def is_low_stock(self):
        return self.quantity <= self.min_quantity

    @property
    def stock_value(self):
        return self.quantity * self.price

    def __str__(self):
        return f"{self.name} ({self.sku})"


class UsedPart(models.Model):
    request = models.ForeignKey(
        RepairRequest, on_delete=models.CASCADE, related_name="used_parts", verbose_name="Заявка"
    )
    part = models.ForeignKey(
        SparePart, on_delete=models.PROTECT, related_name="usages", verbose_name="Запчасть"
    )
    quantity = models.PositiveIntegerField("Количество", default=1)
    price = models.DecimalField("Цена на момент установки, ₽", max_digits=10, decimal_places=2)
    created_at = models.DateTimeField("Дата", auto_now_add=True)

    class Meta:
        verbose_name = "Использованная запчасть"
        verbose_name_plural = "Использованные запчасти"

    @property
    def total(self):
        return self.price * self.quantity

    def __str__(self):
        return f"{self.part.name} × {self.quantity}"
