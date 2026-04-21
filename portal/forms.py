"""
OpenSky forms.
"""
from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.core.exceptions import ValidationError

from .models import User


class RegisterForm(UserCreationForm):
    first_name = forms.CharField(max_length=50, required=True)
    last_name = forms.CharField(max_length=50, required=True)
    email = forms.EmailField(max_length=100, required=True)

    class Meta:
        model = User
        fields = ('first_name', 'last_name', 'username', 'email',
                  'password1', 'password2')

    def __init__(self, *args, **kwargs):
        data = kwargs.get('data')
        if data is not None:
            data = data.copy()
            if data.get('password'):
                data['password1'] = data['password']
            if data.get('password_confirm'):
                data['password2'] = data['password_confirm']
            kwargs['data'] = data
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.setdefault('class', 'sky-field__input')

    def clean_email(self):
        email = self.cleaned_data['email']
        if User.objects.filter(email__iexact=email).exists():
            raise ValidationError('An account with this email already exists.')
        return email
