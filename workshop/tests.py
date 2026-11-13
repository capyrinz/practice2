import io
import shutil
import tempfile

from django.core import mail
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from PIL import Image

from .models import RepairRequest, Service, SparePart, StatusHistory, UsedPart, User
from .services import add_used_part


def png_file(name="photo.png", color="red"):
    buffer = io.BytesIO()
    Image.new("RGB", (8, 8), color).save(buffer, "PNG")
    return SimpleUploadedFile(name, buffer.getvalue(), content_type="image/png")


TEST_MAILERS = {
    "default": {"BACKEND": "django.core.mail.backends.locmem.EmailBackend"}
}


@override_settings(MAILERS=TEST_MAILERS)
class WorkshopTests(TestCase):
    @classmethod
    def setUpClass(cls):
        cls._media_dir = tempfile.mkdtemp()
        cls._media_override = override_settings(MEDIA_ROOT=cls._media_dir)
        cls._media_override.enable()
        super().setUpClass()

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        cls._media_override.disable()
        shutil.rmtree(cls._media_dir, ignore_errors=True)

    @classmethod
    def setUpTestData(cls):
        cls.client_user = User.objects.create_user(
            username="client", password="testpass123", role=User.ROLE_CLIENT,
            email="client@example.com", phone="+7 900 000-00-01",
        )
        cls.other_client = User.objects.create_user(
            username="client2", password="testpass123", role=User.ROLE_CLIENT,
            email="client2@example.com",
        )
        cls.master = User.objects.create_user(
            username="master", password="testpass123", role=User.ROLE_MASTER,
            email="master@example.com",
        )
        cls.other_master = User.objects.create_user(
            username="master2", password="testpass123", role=User.ROLE_MASTER,
        )
        cls.admin = User.objects.create_user(
            username="admin", password="testpass123", role=User.ROLE_ADMIN,
            is_staff=True,
        )
        cls.service = Service.objects.create(
            name="Замена экрана", price_from=3000, duration_days=1
        )
        cls.inactive_service = Service.objects.create(
            name="Скрытая услуга", price_from=100, is_active=False
        )
        cls.part = SparePart.objects.create(
            name="Экран", sku="SCR-1", quantity=5, min_quantity=1, price=1000
        )
        cls.request = RepairRequest.objects.create(
            client=cls.client_user,
            master=cls.master,
            service=cls.service,
            device_type=RepairRequest.DEVICE_PHONE,
            device_model="Test Phone",
            description="Не включается после падения",
        )
        StatusHistory.objects.create(
            request=cls.request, status=RepairRequest.STATUS_ACCEPTED, changed_by=cls.client_user
        )

    def login_client(self):
        self.client.login(username="client", password="testpass123")

    def login_master(self):
        self.client.login(username="master", password="testpass123")

    def login_admin(self):
        self.client.login(username="admin", password="testpass123")

    # ------------------------------------------------ публичная часть и каталог

    def test_catalog_shows_only_active_services(self):
        response = self.client.get(reverse("home"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Замена экрана")
        self.assertNotContains(response, "Скрытая услуга")

    def test_anonymous_redirected_to_login(self):
        response = self.client.get(reverse("client_requests"))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("login"), response["Location"])

    def test_public_status_has_no_personal_data(self):
        response = self.client.get(
            reverse("public_status", args=[self.request.public_token])
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.request.number)
        self.assertNotContains(response, "client@example.com")
        self.assertNotContains(response, "+7 900")

    def test_public_status_unknown_token_404(self):
        response = self.client.get(
            reverse("public_status", args=["00000000-0000-0000-0000-000000000000"])
        )
        self.assertEqual(response.status_code, 404)

    # ------------------------------------------------ регистрация и авторизация

    def test_registration_creates_client_and_hashes_password(self):
        response = self.client.post(
            reverse("register"),
            {
                "username": "newclient",
                "first_name": "Новый",
                "last_name": "Клиент",
                "email": "new@example.com",
                "phone": "+7 900 111-22-33",
                "password1": "verysecret123",
                "password2": "verysecret123",
            },
        )
        self.assertEqual(response.status_code, 302)
        user = User.objects.get(username="newclient")
        self.assertEqual(user.role, User.ROLE_CLIENT)
        self.assertTrue(user.check_password("verysecret123"))
        self.assertNotEqual(user.password, "verysecret123")

    def test_duplicate_email_rejected(self):
        response = self.client.post(
            reverse("register"),
            {
                "username": "newclient2",
                "email": "client@example.com",
                "password1": "verysecret123",
                "password2": "verysecret123",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "уже зарегистрирован")
        self.assertFalse(User.objects.filter(username="newclient2").exists())

    def test_role_access_isolation(self):
        self.login_client()
        self.assertEqual(self.client.get(reverse("master_requests")).status_code, 403)
        self.assertEqual(self.client.get(reverse("admin_dashboard")).status_code, 403)

        self.client.logout()
        self.login_master()
        self.assertEqual(self.client.get(reverse("client_requests")).status_code, 403)
        self.assertEqual(self.client.get(reverse("admin_stats")).status_code, 403)

    # ------------------------------------------------ клиентские заявки

    def test_client_cannot_view_foreign_request(self):
        self.login_client()
        foreign = RepairRequest.objects.create(
            client=self.other_client,
            device_type=RepairRequest.DEVICE_LAPTOP,
            description="Чужая заявка, смотреть нельзя",
        )
        response = self.client.get(reverse("request_detail", args=[foreign.pk]))
        self.assertEqual(response.status_code, 403)

    def test_client_creates_request_with_photo(self):
        self.login_client()
        response = self.client.post(
            reverse("client_request_create"),
            {
                "device_type": RepairRequest.DEVICE_LAPTOP,
                "device_model": "Lenovo",
                "description": "Ноутбук не включается после пролития воды",
                "service": self.service.pk,
                "photo": png_file(),
            },
        )
        self.assertEqual(response.status_code, 302)
        created = RepairRequest.objects.order_by("-pk").first()
        self.assertEqual(created.client, self.client_user)
        self.assertEqual(created.status, RepairRequest.STATUS_ACCEPTED)
        self.assertEqual(created.history.count(), 1)
        self.assertTrue(created.photo)

    def test_short_description_rejected(self):
        self.login_client()
        response = self.client.post(
            reverse("client_request_create"),
            {"device_type": RepairRequest.DEVICE_PHONE, "description": "мало"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "минимум 10 символов")
        self.assertEqual(RepairRequest.objects.filter(client=self.client_user).count(), 1)

    def test_oversized_photo_rejected(self):
        self.login_client()
        big = SimpleUploadedFile(
            "big.png",
            png_file().read() + b"0" * (5 * 1024 * 1024),
            content_type="image/png",
        )
        response = self.client.post(
            reverse("client_request_create"),
            {
                "device_type": RepairRequest.DEVICE_PHONE,
                "description": "Не включается после падения",
                "photo": big,
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Файл больше 5 МБ")

    # ------------------------------------------------ кабинет мастера

    def test_master_sees_only_assigned_requests(self):
        self.login_master()
        response = self.client.get(reverse("master_requests"))
        self.assertContains(response, self.request.number)

        self.client.logout()
        self.login_admin()
        foreign = RepairRequest.objects.create(
            client=self.client_user,
            master=self.other_master,
            device_type=RepairRequest.DEVICE_TV,
            description="Заявка другого мастера",
        )
        self.client.logout()
        self.login_master()
        self.assertEqual(
            self.client.get(reverse("request_detail", args=[foreign.pk])).status_code, 403
        )

    def test_master_changes_status_and_client_gets_email(self):
        self.login_master()
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(
                reverse("change_status", args=[self.request.pk]),
                {"status": RepairRequest.STATUS_READY, "comment": "Ремонт завершён"},
            )
        self.assertEqual(response.status_code, 302)
        self.request.refresh_from_db()
        self.assertEqual(self.request.status, RepairRequest.STATUS_READY)
        self.assertEqual(self.request.history.count(), 2)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn(self.request.number, mail.outbox[0].subject)

    def test_add_used_part_decreases_stock(self):
        self.login_master()
        response = self.client.post(
            reverse("add_part", args=[self.request.pk]),
            {"part": self.part.pk, "quantity": 2},
        )
        self.assertEqual(response.status_code, 302)
        self.part.refresh_from_db()
        self.assertEqual(self.part.quantity, 3)
        self.assertEqual(self.request.used_parts.count(), 1)
        self.assertEqual(self.request.total_cost, 2000)

    def test_cannot_use_more_parts_than_in_stock(self):
        self.login_master()
        response = self.client.post(
            reverse("add_part", args=[self.request.pk]),
            {"part": self.part.pk, "quantity": 99},
        )
        self.assertEqual(response.status_code, 302)
        self.part.refresh_from_db()
        self.assertEqual(self.part.quantity, 5)
        self.assertEqual(self.request.used_parts.count(), 0)

    def test_remove_used_part_returns_stock(self):
        used = add_used_part(self.request, self.part.pk, 2)
        self.login_master()
        response = self.client.post(
            reverse("remove_part", args=[self.request.pk, used.pk])
        )
        self.assertEqual(response.status_code, 302)
        self.part.refresh_from_db()
        self.assertEqual(self.part.quantity, 5)
        self.assertEqual(self.request.used_parts.count(), 0)

    def test_master_sets_work_cost(self):
        self.login_master()
        self.client.post(
            reverse("set_work_cost", args=[self.request.pk]), {"work_cost": "1500.50"}
        )
        self.request.refresh_from_db()
        self.assertEqual(str(self.request.work_cost), "1500.50")

    def test_master_adds_comment(self):
        self.login_master()
        self.client.post(
            reverse("comment_create", args=[self.request.pk]), {"text": "Проверено"}
        )
        self.assertEqual(self.request.comments.count(), 1)

    # ------------------------------------------------ администратор

    def test_admin_can_search_request_by_number(self):
        self.login_admin()
        response = self.client.get(reverse("admin_requests"), {"q": self.request.number})
        self.assertContains(response, self.request.number)

    def test_admin_assigns_master(self):
        self.login_admin()
        response = self.client.post(
            reverse("admin_assign", args=[self.request.pk]),
            {"master": self.other_master.pk, "estimated_cost": "4500"},
        )
        self.assertEqual(response.status_code, 302)
        self.request.refresh_from_db()
        self.assertEqual(self.request.master, self.other_master)
        self.assertEqual(str(self.request.estimated_cost), "4500.00")
        self.assertTrue(
            self.request.history.filter(comment__contains="Назначен мастер").exists()
        )

    def test_kanban_move_changes_status(self):
        self.login_admin()
        response = self.client.post(
            reverse("kanban_move", args=[self.request.pk]),
            data='{"status": "in_repair"}',
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["ok"])
        self.request.refresh_from_db()
        self.assertEqual(self.request.status, RepairRequest.STATUS_IN_REPAIR)

    def test_kanban_rejects_unknown_status_and_non_admin(self):
        self.login_admin()
        response = self.client.post(
            reverse("kanban_move", args=[self.request.pk]),
            data='{"status": "hacked"}',
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)
        self.client.logout()
        self.login_master()
        response = self.client.post(
            reverse("kanban_move", args=[self.request.pk]),
            data='{"status": "issued"}',
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 403)

    def test_admin_creates_employee_with_hashed_password(self):
        self.login_admin()
        response = self.client.post(
            reverse("employee_create"),
            {
                "username": "newmaster",
                "first_name": "Пётр",
                "last_name": "Новый",
                "email": "newmaster@example.com",
                "phone": "+7 900 555-44-33",
                "role": User.ROLE_MASTER,
                "password1": "strongpass123",
                "password2": "strongpass123",
            },
        )
        self.assertEqual(response.status_code, 302)
        employee = User.objects.get(username="newmaster")
        self.assertEqual(employee.role, User.ROLE_MASTER)
        self.assertTrue(employee.check_password("strongpass123"))

    def test_admin_creates_service_and_part(self):
        self.login_admin()
        response = self.client.post(
            reverse("service_create"),
            {"name": "Новая услуга", "price_from": "999", "duration_days": "2", "is_active": "on"},
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Service.objects.filter(name="Новая услуга").exists())

        response = self.client.post(
            reverse("part_create"),
            {
                "name": "Новая запчасть",
                "sku": "NEW-1",
                "quantity": "4",
                "min_quantity": "1",
                "price": "500",
                "is_active": "on",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(SparePart.objects.filter(sku="NEW-1").exists())

    def test_deleting_request_returns_parts_to_stock(self):
        used = add_used_part(self.request, self.part.pk, 3)
        self.login_admin()
        response = self.client.post(reverse("admin_request_delete", args=[self.request.pk]))
        self.assertEqual(response.status_code, 302)
        self.part.refresh_from_db()
        self.assertEqual(self.part.quantity, 5)
        self.assertFalse(RepairRequest.objects.filter(pk=self.request.pk).exists())

    def test_admin_pages_accessible(self):
        self.login_admin()
        for name in [
            "admin_dashboard", "admin_requests", "admin_kanban", "admin_services",
            "admin_parts", "admin_employees", "admin_users", "admin_stats",
        ]:
            with self.subTest(name=name):
                self.assertEqual(self.client.get(reverse(name)).status_code, 200)

    def test_admin_cannot_block_self(self):
        self.login_admin()
        self.client.post(reverse("user_toggle", args=[self.admin.pk]))
        self.admin.refresh_from_db()
        self.assertTrue(self.admin.is_active)

    # ------------------------------------------------ PDF и документы

    def test_receipt_pdf_available_to_owner_and_admin(self):
        self.login_client()
        response = self.client.get(reverse("receipt_pdf", args=[self.request.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/pdf")
        content = b"".join(response.streaming_content)
        self.assertTrue(content.startswith(b"%PDF"))

        self.client.logout()
        self.login_admin()
        response = self.client.get(reverse("receipt_pdf", args=[self.request.pk]))
        self.assertEqual(response.status_code, 200)

    def test_receipt_pdf_denied_to_foreign_client(self):
        self.client.login(username="client2", password="testpass123")
        response = self.client.get(reverse("receipt_pdf", args=[self.request.pk]))
        self.assertEqual(response.status_code, 403)

    def test_anonymous_cannot_download_receipt(self):
        response = self.client.get(reverse("receipt_pdf", args=[self.request.pk]))
        self.assertEqual(response.status_code, 302)
