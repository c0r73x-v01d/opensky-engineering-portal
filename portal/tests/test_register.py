"""Tests for the self-registration flow, including DOB validation."""

import datetime

from django.test import TestCase, Client
from django.urls import reverse

from portal.models import Action, Employee, User


def _valid_dob(years_ago=30):
    """Return a DOB that is exactly `years_ago` years before today."""
    today = datetime.date.today()
    try:
        return today.replace(year=today.year - years_ago)
    except ValueError:
        return today.replace(month=2, day=28, year=today.year - years_ago)


class RegisterFormTests(TestCase):
    def _post(self, **overrides):
        data = {
            'first_name': 'Alice',
            'last_name': 'Lee',
            'username': 'alice',
            'email': 'alice@example.com',
            'dob': _valid_dob(30).isoformat(),
            'password1': 'StrongPass#2026',
            'password2': 'StrongPass#2026',
        }
        data.update(overrides)
        return Client().post(reverse('register'), data=data)

    def test_valid_registration_creates_user_and_employee(self):
        r = self._post()
        self.assertEqual(r.status_code, 302)
        user = User.objects.get(username='alice')
        self.assertEqual(user.dob, _valid_dob(30))
        self.assertTrue(Employee.objects.filter(user=user).exists())
        # Audit log written by register_view.
        self.assertTrue(Action.objects.filter(
            user=user, entityType='Users', action='create',
        ).exists())

    def test_dob_under_18_rejected(self):
        r = self._post(dob=_valid_dob(16).isoformat())
        # Form rerenders, no user created.
        self.assertEqual(r.status_code, 200)
        self.assertFalse(User.objects.filter(username='alice').exists())

    def test_dob_in_future_rejected(self):
        future = (datetime.date.today() + datetime.timedelta(days=365)).isoformat()
        r = self._post(dob=future)
        self.assertEqual(r.status_code, 200)
        self.assertFalse(User.objects.filter(username='alice').exists())

    def test_dob_missing_rejected(self):
        r = self._post(dob='')
        self.assertEqual(r.status_code, 200)
        self.assertFalse(User.objects.filter(username='alice').exists())

    def test_dob_invalid_format_rejected(self):
        r = self._post(dob='not-a-date')
        self.assertEqual(r.status_code, 200)
        self.assertFalse(User.objects.filter(username='alice').exists())

    def test_register_page_shows_dob_input(self):
        r = Client().get(reverse('register'))
        self.assertEqual(r.status_code, 200)
        body = r.content.decode()
        self.assertIn('id="regDob"', body)
        self.assertIn('name="dob"', body)
        self.assertIn('type="date"', body)
