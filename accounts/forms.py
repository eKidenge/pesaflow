from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import (
    AuthenticationForm,
    UserCreationForm,
    PasswordResetForm as DjangoPasswordResetForm,
    SetPasswordForm
)

User = get_user_model()


# ============================
# AUTH / LOGIN FORMS
# ============================

class UserLoginForm(AuthenticationForm):
    username = forms.CharField(
        label="Email or Username",
        widget=forms.TextInput(attrs={"class": "form-control"})
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={"class": "form-control"})
    )


# ============================
# REGISTRATION FORMS
# ============================

class UserRegistrationForm(UserCreationForm):
    email = forms.EmailField(required=True)
    phone = forms.CharField(required=False)
    country = forms.CharField(required=False)

    class Meta:
        model = User
        fields = (
            "email",
            "first_name",
            "last_name",
            "phone",
            "country",
            "password1",
            "password2",
        )

    def save(self, commit=True):
        user = super().save(commit=False)
        user.username = self.cleaned_data["email"]
        user.email = self.cleaned_data["email"]
        if commit:
            user.save()
        return user


class AdminRegistrationForm(UserRegistrationForm):
    def save(self, commit=True):
        user = super().save(commit=False)
        user.user_type = "system_admin"
        user.is_staff = True
        user.is_superuser = True
        if commit:
            user.save()
        return user


class BusinessRegistrationForm(UserRegistrationForm):
    business_name = forms.CharField(required=True)
    business_type = forms.CharField(required=False)

    def save(self, commit=True):
        user = super().save(commit=False)
        user.user_type = "business_owner"
        if commit:
            user.save()
        return user


class ClientRegistrationForm(UserRegistrationForm):
    id_number = forms.CharField(required=False)
    address = forms.CharField(required=False)

    def save(self, commit=True):
        user = super().save(commit=False)
        user.user_type = "client"
        if commit:
            user.save()
        return user


# ============================
# PASSWORD RESET FORMS
# ============================

class PasswordResetForm(DjangoPasswordResetForm):
    email = forms.EmailField(
        widget=forms.EmailInput(attrs={"class": "form-control"})
    )


class SetNewPasswordForm(SetPasswordForm):
    new_password1 = forms.CharField(
        widget=forms.PasswordInput(attrs={"class": "form-control"})
    )
    new_password2 = forms.CharField(
        widget=forms.PasswordInput(attrs={"class": "form-control"})
    )
