"""
OpenSky forms.
"""
import datetime

from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.core.exceptions import ValidationError
from django.utils import timezone

from .models import Team, User


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


# ════════════════════════════════════════════════════════════════════
# === Schedule — MeetingForm ===
# ════════════════════════════════════════════════════════════════════

DURATION_CHOICES = [
    ('15m', '15m'),
    ('30m', '30m'),
    ('1h', '1h'),
    ('2h', '2h'),
    ('3h', '3h'),
]
DURATION_MINUTES = {
    '15m': 15, '30m': 30, '1h': 60, '2h': 120, '3h': 180,
}

PLATFORM_CHOICES = [
    ('teams', 'Teams'),
    ('zoom', 'Zoom'),
    ('slack', 'Slack'),
    ('meet', 'Meet'),
    ('office', 'Office'),
]

TYPE_CHOICES = [
    ('team', 'Team Meeting'),
    ('personal', 'Personal Meeting'),
]

RECURRING_CHOICES = [
    ('one-time', 'One-time'),
    ('daily', 'Daily'),
    ('weekly', 'Weekly'),
    ('bi-weekly', 'Bi-weekly'),
    ('monthly', 'Monthly'),
]


class MeetingForm(forms.Form):
    """
    Server-side validation for the Schedule Meeting modal. The view turns the
    cleaned data into a Meeting + MeetingInvitation rows, so this form does
    not subclass ModelForm — the host-team / employee resolution depends on
    the current user and lives in the view.
    """

    title = forms.CharField(max_length=120, required=True)
    meeting_type = forms.ChoiceField(choices=TYPE_CHOICES)
    host_team = forms.ModelChoiceField(queryset=Team.objects.all(), required=False)
    date = forms.DateField()
    time = forms.TimeField()
    duration = forms.ChoiceField(choices=DURATION_CHOICES)
    platform = forms.ChoiceField(choices=PLATFORM_CHOICES)
    recurring = forms.ChoiceField(choices=RECURRING_CHOICES, required=False)
    agenda = forms.CharField(required=False)
    attendee_ids = forms.CharField(required=False)  # comma-separated User IDs

    def clean_title(self):
        title = (self.cleaned_data.get('title') or '').strip()
        if not title:
            raise ValidationError('Meeting title is required.')
        return title

    def clean_attendee_ids(self):
        raw = (self.cleaned_data.get('attendee_ids') or '').strip()
        if not raw:
            return []
        try:
            ids = [int(s) for s in raw.split(',') if s.strip()]
        except ValueError:
            raise ValidationError('Invalid attendee list.')
        return ids

    def clean(self):
        cleaned = super().clean()
        meeting_type = cleaned.get('meeting_type')
        host_team = cleaned.get('host_team')

        if meeting_type == 'team' and not host_team:
            self.add_error('host_team', 'A team meeting needs a host team.')

        date = cleaned.get('date')
        time = cleaned.get('time')
        duration = cleaned.get('duration')
        if date and time and duration:
            naive_start = datetime.datetime.combine(date, time)
            tz = timezone.get_current_timezone()
            start = timezone.make_aware(naive_start, tz)
            end = start + datetime.timedelta(minutes=DURATION_MINUTES[duration])
            cleaned['start'] = start
            cleaned['end'] = end

        return cleaned
