from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm

from .models import RepairRequest, Service, SparePart, User


class StyledFormMixin:
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            widget = field.widget
            if isinstance(widget, forms.CheckboxInput):
                widget.attrs.setdefault("class", "form-check-input")
            elif isinstance(widget, forms.Select):
                widget.attrs.setdefault("class", "form-select")
            elif isinstance(widget, forms.FileInput):
                widget.attrs.setdefault("class", "form-control")
            else:
                widget.attrs.setdefault("class", "form-control")


class LoginForm(StyledFormMixin, AuthenticationForm):
    username = forms.CharField(label="Логин", widget=forms.TextInput(attrs={"autofocus": True}))
    password = forms.CharField(label="Пароль", widget=forms.PasswordInput)


class RegisterForm(StyledFormMixin, UserCreationForm):
    email = forms.EmailField(label="E-mail", required=True)
    phone = forms.CharField(label="Телефон", max_length=20, required=False)

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("username", "first_name", "last_name", "email", "phone")

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("Пользователь с таким e-mail уже зарегистрирован.")
        return email


class RequestForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = RepairRequest
        fields = ("service", "device_type", "device_model", "description", "photo")
        widgets = {
            "description": forms.Textarea(
                attrs={"rows": 5, "placeholder": "Опишите, что случилось с устройством"}
            ),
            "photo": forms.FileInput(
                attrs={"accept": "image/*", "data-preview": "#photoPreview"}
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["service"].queryset = Service.objects.filter(is_active=True)
        self.fields["service"].empty_label = "Не выбрана (уточним при диагностике)"

    def clean_description(self):
        description = self.cleaned_data["description"].strip()
        if len(description) < 10:
            raise forms.ValidationError("Опишите неисправность подробнее — минимум 10 символов.")
        return description

    def clean_photo(self):
        photo = self.cleaned_data.get("photo")
        if photo and photo.size > 5 * 1024 * 1024:
            raise forms.ValidationError("Файл больше 5 МБ. Загрузите фото меньшего размера.")
        return photo


class ServiceForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = Service
        fields = ("name", "description", "price_from", "duration_days", "is_active")
        widgets = {"description": forms.Textarea(attrs={"rows": 3})}

    def clean_price_from(self):
        price = self.cleaned_data["price_from"]
        if price < 0:
            raise forms.ValidationError("Цена не может быть отрицательной.")
        return price


class PartForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = SparePart
        fields = ("name", "sku", "quantity", "min_quantity", "price", "is_active")

    def clean_price(self):
        price = self.cleaned_data["price"]
        if price < 0:
            raise forms.ValidationError("Цена не может быть отрицательной.")
        return price


class EmployeeForm(StyledFormMixin, UserCreationForm):
    email = forms.EmailField(label="E-mail", required=True)
    phone = forms.CharField(label="Телефон", max_length=20, required=False)
    role = forms.ChoiceField(
        label="Роль",
        choices=[(User.ROLE_MASTER, "Мастер"), (User.ROLE_ADMIN, "Администратор")],
    )

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("username", "first_name", "last_name", "email", "phone", "role")

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("Пользователь с таким e-mail уже существует.")
        return email


class EmployeeEditForm(StyledFormMixin, forms.ModelForm):
    role = forms.ChoiceField(
        label="Роль",
        choices=[(User.ROLE_MASTER, "Мастер"), (User.ROLE_ADMIN, "Администратор")],
    )

    class Meta:
        model = User
        fields = ("first_name", "last_name", "email", "phone", "role", "is_active")
        widgets = {"is_active": forms.CheckboxInput()}

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if not email:
            return email
        qs = User.objects.filter(email__iexact=email).exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError("Пользователь с таким e-mail уже существует.")
        return email


class AssignForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = RepairRequest
        fields = ("master", "estimated_cost")
        widgets = {
            "estimated_cost": forms.NumberInput(attrs={"step": "0.01", "min": "0"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["master"].queryset = User.objects.filter(
            role=User.ROLE_MASTER, is_active=True
        )
        self.fields["master"].empty_label = "Не назначен"


class StatusForm(StyledFormMixin, forms.Form):
    status = forms.ChoiceField(label="Новый статус", choices=RepairRequest.STATUS_CHOICES)
    comment = forms.CharField(
        label="Комментарий",
        required=False,
        widget=forms.Textarea(attrs={"rows": 3, "placeholder": "Что сделано / что дальше"}),
    )


class WorkCostForm(StyledFormMixin, forms.Form):
    work_cost = forms.DecimalField(
        label="Стоимость работ, ₽", max_digits=10, decimal_places=2, min_value=0
    )


class AddPartForm(StyledFormMixin, forms.Form):
    part = forms.ModelChoiceField(label="Запчасть", queryset=SparePart.objects.none())
    quantity = forms.IntegerField(label="Количество", min_value=1, initial=1)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["part"].queryset = SparePart.objects.filter(
            is_active=True, quantity__gt=0
        ).order_by("name")
        self.fields["part"].empty_label = "Выберите запчасть"

    def clean(self):
        cleaned = super().clean()
        part, quantity = cleaned.get("part"), cleaned.get("quantity")
        if part and quantity and quantity > part.quantity:
            self.add_error(
                "quantity", f"На складе только {part.quantity} шт. «{part.name}»."
            )
        return cleaned


class CommentForm(StyledFormMixin, forms.Form):
    text = forms.CharField(
        label="Комментарий",
        widget=forms.Textarea(attrs={"rows": 3, "placeholder": "Сообщение клиенту"}),
    )


class RequestDeleteForm(forms.Form):
    confirm = forms.BooleanField(
        label="Подтверждаю удаление заявки и связанных данных",
        widget=forms.CheckboxInput(attrs={"class": "form-check-input"}),
    )
