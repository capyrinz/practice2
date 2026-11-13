# Ремонтная мастерская «Мастер+»

Учебный проект по практике: веб-приложение для приёма заявок на ремонт техники,
отслеживания статуса ремонта и учёта запчастей.

**Стек:** Python 3.12+, Django 6.1, SQLite, HTML/CSS/JavaScript (Bootstrap 5 и Chart.js
лежат локально), Pillow, ReportLab, qrcode.

## Что реализовано

- каталог услуг с ценами и поиском;
- регистрация/авторизация с ролями **клиент / мастер / администратор**;
- создание заявки с фото и серверной валидацией;
- личный кабинет клиента: история, фильтры, статус, смета, квитанция PDF;
- рабочее место мастера: назначенные заявки, смена статуса, комментарии,
  стоимость работ, списание/возврат запчастей;
- панель администратора: заявки, назначение мастеров, Kanban с drag-and-drop,
  услуги, склад, сотрудники, пользователи, статистика с графиками;
- PDF-квитанция/акт с QR-кодом на публичную страницу статуса;
- e-mail-уведомления клиенту при смене статуса (по умолчанию печатаются в консоль);
- 30 автоматических тестов.

## Быстрый запуск

Все команды выполняются **в корне проекта** — там, где лежит `manage.py`
(не внутри `workshop/`).

**Windows (PowerShell / cmd):**

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python manage.py migrate
python manage.py seed_demo
python manage.py runserver
```

**Linux / macOS / WSL:**

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py seed_demo
python manage.py runserver
```

> В WSL и большинстве Linux-дистрибутивов команды `python` нет — используйте
> `python3`. Внутри активированного `.venv` команда `python` уже работает.

Открыть <http://127.0.0.1:8000/>.

### Демо-доступ

| Роль | Логин | Пароль |
|---|---|---|
| Администратор | `admin` | `admin12345` |
| Мастер | `master` | `master12345` |
| Мастер | `master2` | `master12345` |
| Клиент | `client` | `client12345` |
| Клиент | `client2` | `client12345` |
| Клиент | `client3` | `client12345` |

Служебная панель Django (сброс паролей, «сырое» администрирование):
`/django-admin/` — тот же логин `admin`.

`seed_demo` идемпотентен: пользователи, услуги и запчасти создаются один раз,
демо-заявки — только если заявок ещё нет. Чтобы начать заново:

```bash
rm db.sqlite3
python manage.py migrate
python manage.py seed_demo
```

## Тесты

```bash
python manage.py test workshop
```

Покрыты: регистрация и хеширование пароля, роли и доступ к чужим заявкам,
валидация формы (короткое описание, фото > 5 МБ), создание заявки с фото,
смена статуса и e-mail, списание/возврат запчастей, запрет списания больше остатка,
Kanban, назначение мастера, CRUD услуг/запчастей/сотрудников, PDF и публичный статус.

## Настройки окружения

| Переменная | Назначение | По умолчанию |
|---|---|---|
| `DJANGO_SECRET_KEY` | секретный ключ | dev-ключ |
| `DJANGO_DEBUG` | `0` выключает debug | `1` |
| `DJANGO_ALLOWED_HOSTS` | хосты через запятую | localhost, 127.0.0.1 |
| `DJANGO_CSRF_TRUSTED_ORIGINS` | доверенные origin | пусто |
| `SITE_URL` | адрес сайта для QR и писем | `http://127.0.0.1:8000` |
| `EMAIL_HOST` | SMTP-сервер; без него письма в консоль | — |
| `EMAIL_PORT` | порт SMTP | `587` |
| `EMAIL_HOST_USER` / `EMAIL_HOST_PASSWORD` | доступ к SMTP | — |
| `EMAIL_USE_TLS` | `0` отключает TLS | `1` |
| `DEFAULT_FROM_EMAIL` | адрес отправителя | `noreply@masterplus.local` |

## Структура

```
config/                 настройки и корневые URL
workshop/
  models.py             User, Service, RepairRequest, StatusHistory,
                        RepairComment, SparePart, UsedPart
  views.py              публичные, клиентские, мастерские и админ-страницы
  forms.py              формы и валидация
  services.py           бизнес-логика: статусы, e-mail, склад
  pdf.py                PDF-квитанция с QR
  decorators.py         проверка ролей
  tests.py              30 тестов
  management/commands/seed_demo.py
  templates/            HTML-шаблоны
  static/               CSS, JS, Bootstrap, Chart.js
docs/
media/                  
```

