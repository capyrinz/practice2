"""Демонстрационные данные: python manage.py seed_demo."""

from datetime import timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.utils import timezone

from workshop.models import (
    RepairComment,
    RepairRequest,
    Service,
    SparePart,
    StatusHistory,
    UsedPart,
    User,
)

SERVICES = [
    ("Диагностика", "Проверка устройства и согласование сметы до начала работ.", 0, 1),
    ("Замена экрана смартфона", "Замена дисплейного модуля с проверкой сенсора.", 3500, 1),
    ("Замена аккумулятора", "Установка новой батареи с тестом ёмкости.", 1500, 1),
    ("Ремонт ноутбука", "Чистка от пыли, замена термопасты, диагностика платы.", 2500, 2),
    ("Восстановление после залития", "Промывка платы, ремонт цепей питания.", 4500, 3),
    ("Ремонт бытовой техники", "Диагностика и ремонт крупной бытовой техники на дому.", 2000, 2),
]

PARTS = [
    ("Экран iPhone 13", "SCR-IP13", 12, 3, 8900),
    ("Аккумулятор Samsung A52", "BAT-SA52", 18, 4, 2400),
    ("Термопаста Arctic MX-4", "THM-MX4", 5, 3, 450),
    ("SSD Kingston 512 ГБ", "SSD-K512", 3, 2, 5200),
    ("Клавиатура ноутбука Lenovo", "KBD-LNV", 1, 2, 3800),
    ("Разъём питания USB-C", "CON-USBC", 0, 3, 900),
    ("Кулер для ноутбука", "FAN-UNI", 6, 2, 1200),
    ("Термопрокладка 1 мм", "PAD-1MM", 2, 3, 300),
]

REQUESTS = [
    # (дней назад, статус, индекс клиента, индекс мастера, услуга, устройство, модель, описание, работы)
    (152, "issued", 0, 0, 1, "phone", "iPhone 12", "Разбит экран после падения, сенсор работает частично.", 3500),
    (146, "issued", 1, 1, 2, "phone", "Samsung A52", "Телефон быстро разряжается, battery health 71%.", 1500),
    (138, "issued", 2, 0, 3, "laptop", "Lenovo IdeaPad 5", "Шумит вентилятор, перегревается при работе.", 2500),
    (129, "issued", 0, 1, 4, "phone", "Xiaomi Redmi 10", "После попадания воды не включается.", 4500),
    (117, "issued", 1, 0, 0, "tv", "LG 43UM", "Нет изображения, звук присутствует.", 0),
    (104, "issued", 2, 1, 2, "phone", "iPhone 13", "Аккумулятор держит меньше половины дня.", 1500),
    (94, "issued", 0, 0, 4, "laptop", "ASUS Vivobook", "Залит чаем, клавиатура не работает.", 4500),
    (82, "issued", 1, 1, 1, "phone", "iPhone 13", "Трещина на экране, нижняя часть не реагирует.", 3500),
    (71, "issued", 2, 0, 5, "appliance", "Bosch Serie 4", "Стиральная машина не сливает воду.", 2000),
    (63, "issued", 0, 1, 2, "phone", "Samsung A52", "Вздулась батарея, корпус деформирован.", 1500),
    (55, "issued", 1, 0, 3, "laptop", "HP Pavilion", "Ноутбук выключается под нагрузкой.", 2500),
    (48, "issued", 2, 1, 1, "phone", "iPhone 13", "Экран полностью чёрный после падения.", 3500),
    (39, "issued", 0, 0, 4, "tablet", "iPad Air", "После воды не заряжается.", 4500),
    (31, "issued", 1, 1, 2, "phone", "Xiaomi Redmi 10", "Быстрый разряд, нагрев при зарядке.", 1500),
    (24, "issued", 2, 0, 1, "phone", "iPhone 12", "Разбита верхняя часть дисплея.", 3500),
    (18, "issued", 0, 1, 5, "appliance", "Samsung WD80", "Не отжимает бельё, ошибка E4.", 2000),
    (15, "issued", 1, 0, 3, "laptop", "Acer Aspire 5", "Перегрев и отключение вентилятора.", 2500),
    (9, "ready", 2, 1, 1, "phone", "iPhone 13", "Повреждён дисплей, требуется замена.", 3500),
    (8, "ready", 0, 0, 2, "phone", "Samsung A52", "Аккумулятор не держит заряд.", 1500),
    (6, "ready", 1, 1, 3, "laptop", "Lenovo IdeaPad 5", "Шум кулера, требуется чистка.", 2500),
    (5, "in_repair", 2, 0, 4, "phone", "Xiaomi Redmi 10", "Попала влага, нужна чистка платы.", 4500),
    (4, "in_repair", 0, 1, 1, "phone", "iPhone 12", "Разбит экран, заказан дисплей.", 3500),
    (3, "in_repair", 1, 0, 3, "laptop", "HP Pavilion", "Перегрев, заказана термопаста.", 2500),
    (3, "in_repair", 2, 1, 5, "appliance", "Bosch Serie 4", "Не сливает воду, проверяем насос.", 2000),
    (2, "diagnostics", 0, 0, 0, "tablet", "Samsung Tab A8", "Не включается после падения.", 0),
    (2, "diagnostics", 1, 1, 3, "laptop", "ASUS Vivobook", "Синий экран при запуске.", 0),
    (1, "diagnostics", 2, 0, 4, "phone", "iPhone 12", "После дождя не работает динамик.", 0),
    (1, "accepted", 0, None, 1, "phone", "iPhone 13", "Разбит экран, нужна консультация.", 0),
    (1, "accepted", 1, None, 2, "phone", "Samsung A52", "Быстро садится батарея.", 0),
    (0, "accepted", 2, None, 3, "laptop", "Lenovo IdeaPad 5", "Громко шумит вентилятор.", 0),
]

COMMENTS = {
    18: "Дисплей заменён, проверяем калибровку и сенсор.",
    20: "Кулер почищен, температура в норме. Готовим к выдаче.",
    21: "Плата промыта, устройство включается. Идёт тестирование.",
    3: "Дисплей заказан у поставщика, ожидаем поставку 1–2 дня.",
}


class Command(BaseCommand):
    help = "Создаёт демонстрационных пользователей, услуги, запчасти и заявки."

    def handle(self, *args, **options):
        admin = self.create_user("admin", "admin12345", "Администратор", "Мастерской", "admin@masterplus.local", "+7 (495) 000-00-01", "admin", superuser=True)
        master1 = self.create_user("master", "master12345", "Иван", "Петров", "petrov@masterplus.local", "+7 (495) 000-00-02", "master")
        master2 = self.create_user("master2", "master12345", "Анна", "Сидорова", "sidorova@masterplus.local", "+7 (495) 000-00-03", "master")
        clients = [
            self.create_user("client", "client12345", "Сергей", "Смирнов", "smirnov@example.com", "+7 (916) 111-22-33", "client"),
            self.create_user("client2", "client12345", "Ольга", "Кузнецова", "kuznetsova@example.com", "+7 (916) 222-33-44", "client"),
            self.create_user("client3", "client12345", "Дмитрий", "Волков", "volkov@example.com", "+7 (916) 333-44-55", "client"),
        ]
        masters = [master1, master2]

        services = []
        for name, description, price, days in SERVICES:
            service, _ = Service.objects.get_or_create(
                name=name,
                defaults={
                    "description": description,
                    "price_from": Decimal(price),
                    "duration_days": days,
                },
            )
            services.append(service)

        parts = []
        for name, sku, quantity, minimum, price in PARTS:
            part, _ = SparePart.objects.get_or_create(
                sku=sku,
                defaults={
                    "name": name,
                    "quantity": quantity,
                    "min_quantity": minimum,
                    "price": Decimal(price),
                },
            )
            parts.append(part)

        if RepairRequest.objects.exists():
            self.stdout.write(self.style.WARNING("Заявки уже есть — демо-заявки не создавались."))
            self.print_credentials()
            return

        now = timezone.now()
        created_requests = []
        for index, row in enumerate(REQUESTS):
            days, status, client_index, master_index, service_index, device, model, description, work = row
            created = now - timedelta(days=days, hours=(index * 3) % 12, minutes=(index * 7) % 60)
            repair_request = RepairRequest.objects.create(
                client=clients[client_index],
                master=masters[master_index] if master_index is not None else None,
                service=services[service_index],
                device_type=device,
                device_model=model,
                description=description,
                status=status,
                estimated_cost=Decimal(work) + Decimal("1500"),
                work_cost=Decimal(work),
                issued_at=created + timedelta(days=2) if status == "issued" else None,
            )
            RepairRequest.objects.filter(pk=repair_request.pk).update(created_at=created)
            repair_request.refresh_from_db()
            created_requests.append(repair_request)

            # История: все этапы от «Принята» до текущего статуса.
            flow = ["accepted", "diagnostics", "in_repair", "ready", "issued"]
            current_index = flow.index(status)
            for step in range(current_index + 1):
                history = StatusHistory.objects.create(
                    request=repair_request,
                    status=flow[step],
                    changed_by=clients[client_index] if step == 0 else (repair_request.master or admin),
                    comment="Заявка создана клиентом" if step == 0 else "",
                )
                StatusHistory.objects.filter(pk=history.pk).update(
                    created_at=created + timedelta(days=step, hours=step * 2)
                )

            if status in ("ready", "issued") and index % 2 == 0:
                part = parts[index % 4]
                if part.quantity > 0:
                    UsedPart.objects.create(
                        request=repair_request,
                        part=part,
                        quantity=1,
                        price=part.price,
                    )
                    part.quantity -= 1
                    part.save(update_fields=["quantity"])
            if repair_request.master and index in COMMENTS:
                comment = RepairComment.objects.create(
                    request=repair_request,
                    author=repair_request.master,
                    text=COMMENTS[index],
                )
                RepairComment.objects.filter(pk=comment.pk).update(
                    created_at=now - timedelta(days=max(days - 1, 0))
                )

        self.stdout.write(self.style.SUCCESS(f"Создано заявок: {len(created_requests)}"))
        self.print_credentials()

    def create_user(self, username, password, first_name, last_name, email, phone, role, superuser=False):
        user, created = User.objects.get_or_create(
            username=username,
            defaults={
                "first_name": first_name,
                "last_name": last_name,
                "email": email,
                "phone": phone,
                "role": role,
                "is_staff": superuser,
                "is_superuser": superuser,
            },
        )
        if created:
            user.set_password(password)
            user.save()
        return user

    def print_credentials(self):
        self.stdout.write(
            "\nДемо-доступ:\n"
            "  admin / admin12345     — администратор (и суперпользователь /django-admin/)\n"
            "  master / master12345   — мастер Иван Петров\n"
            "  master2 / master12345  — мастер Анна Сидорова\n"
            "  client / client12345   — клиент Сергей Смирнов\n"
            "  client2 / client12345  — клиент Ольга Кузнецова\n"
            "  client3 / client12345  — клиент Дмитрий Волков\n"
        )
