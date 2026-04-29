"""Tests for the /profile/update/ endpoint.

Covers all three POST flavours:
  - Personal:  about_me + avatar
  - Security:  password change with current-password verification
  - JSON:      widget_sizes session persistence (Content-Type: application/json)
"""
import io
import json

from django.test import TestCase, Client
from django.urls import reverse

from portal.models import Action, User
from . import _helpers as f


def _png_bytes():
    """Tiny valid PNG so ImageField.validate accepts the upload."""
    # 1×1 transparent PNG.
    return bytes.fromhex(
        '89504e470d0a1a0a0000000d49484452'
        '0000000100000001080600000'
        '01f15c4890000000d49444154789c63000100000005000'
        '17a4e0c4f0000000049454e44ae426082'
    )


class ProfileUpdateAuthTests(TestCase):
    def test_anonymous_redirected_to_login(self):
        c = Client()
        r = c.post(reverse('profile_update'))
        self.assertEqual(r.status_code, 302)
        self.assertIn('/login/', r['Location'])

    def test_get_not_allowed(self):
        c = Client(); c.force_login(f.make_user('eve'))
        r = c.get(reverse('profile_update'))
        self.assertEqual(r.status_code, 405)


class ProfileUpdatePersonalTests(TestCase):
    def setUp(self):
        self.user = f.make_user('alice', first='Alice', last='Lee')
        self.client.force_login(self.user)

    def test_about_me_update_persists_and_audits(self):
        r = self.client.post(reverse('profile_update'), data={
            'form_type': 'personal',
            'about_me': 'I run things.',
        })
        self.assertEqual(r.status_code, 302)
        self.user.refresh_from_db()
        self.assertEqual(self.user.about_me, 'I run things.')
        # Audit row created.
        self.assertTrue(Action.objects.filter(
            user=self.user, action='update', entityType='Users',
            fieldChanged='about_me',
        ).exists())

    def test_about_me_too_long_rejected(self):
        long_text = 'x' * 1001
        r = self.client.post(reverse('profile_update'), data={
            'form_type': 'personal',
            'about_me': long_text,
        })
        self.assertEqual(r.status_code, 302)
        self.user.refresh_from_db()
        self.assertNotEqual(self.user.about_me, long_text)

    def test_dob_valid_update_persists_and_audits(self):
        import datetime
        valid_dob = datetime.date.today().replace(year=datetime.date.today().year - 30)
        r = self.client.post(reverse('profile_update'), data={
            'form_type': 'personal',
            'about_me': '',
            'dob': valid_dob.isoformat(),
        })
        self.assertEqual(r.status_code, 302)
        self.user.refresh_from_db()
        self.assertEqual(self.user.dob, valid_dob)
        self.assertTrue(Action.objects.filter(
            user=self.user, fieldChanged='dob',
        ).exists())

    def test_dob_under_18_rejected(self):
        import datetime
        too_young = datetime.date.today().replace(year=datetime.date.today().year - 16)
        r = self.client.post(reverse('profile_update'), data={
            'form_type': 'personal',
            'about_me': '',
            'dob': too_young.isoformat(),
        })
        self.assertEqual(r.status_code, 302)
        self.user.refresh_from_db()
        self.assertNotEqual(self.user.dob, too_young)

    def test_dob_in_future_rejected(self):
        import datetime
        future = datetime.date.today() + datetime.timedelta(days=365)
        r = self.client.post(reverse('profile_update'), data={
            'form_type': 'personal',
            'about_me': '',
            'dob': future.isoformat(),
        })
        self.assertEqual(r.status_code, 302)
        self.user.refresh_from_db()
        self.assertNotEqual(self.user.dob, future)

    def test_dob_empty_rejected(self):
        r = self.client.post(reverse('profile_update'), data={
            'form_type': 'personal',
            'about_me': '',
            'dob': '',
        })
        self.assertEqual(r.status_code, 302)
        self.user.refresh_from_db()
        self.assertIsNone(self.user.dob)

    def test_dob_invalid_format_rejected(self):
        r = self.client.post(reverse('profile_update'), data={
            'form_type': 'personal',
            'about_me': '',
            'dob': 'not-a-date',
        })
        self.assertEqual(r.status_code, 302)
        self.user.refresh_from_db()
        self.assertIsNone(self.user.dob)


class ProfileUpdateSecurityTests(TestCase):
    def setUp(self):
        self.user = f.make_user('alice', password='oldpassword123')
        self.client.force_login(self.user)

    def test_valid_password_change(self):
        r = self.client.post(reverse('profile_update'), data={
            'form_type': 'security',
            'current_password': 'oldpassword123',
            'new_password': 'newpassword456',
            'confirm_password': 'newpassword456',
        })
        self.assertEqual(r.status_code, 302)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password('newpassword456'))
        # Session stays valid (update_session_auth_hash) — confirm by
        # making another authenticated request.
        r2 = self.client.get(reverse('home'))
        self.assertEqual(r2.status_code, 200)
        # Audit logged.
        self.assertTrue(Action.objects.filter(
            user=self.user, fieldChanged='password',
        ).exists())

    def test_wrong_current_password_rejected(self):
        r = self.client.post(reverse('profile_update'), data={
            'form_type': 'security',
            'current_password': 'WRONG',
            'new_password': 'newpassword456',
            'confirm_password': 'newpassword456',
        })
        self.assertEqual(r.status_code, 302)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password('oldpassword123'))
        self.assertFalse(Action.objects.filter(
            user=self.user, fieldChanged='password',
        ).exists())

    def test_password_mismatch_rejected(self):
        r = self.client.post(reverse('profile_update'), data={
            'form_type': 'security',
            'current_password': 'oldpassword123',
            'new_password': 'newpassword456',
            'confirm_password': 'DIFFERENT',
        })
        self.assertEqual(r.status_code, 302)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password('oldpassword123'))

    def test_password_too_short_rejected(self):
        r = self.client.post(reverse('profile_update'), data={
            'form_type': 'security',
            'current_password': 'oldpassword123',
            'new_password': 'short',
            'confirm_password': 'short',
        })
        self.assertEqual(r.status_code, 302)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password('oldpassword123'))


class ProfileUpdateWidgetSizesTests(TestCase):
    def setUp(self):
        self.user = f.make_user('alice')
        self.client.force_login(self.user)

    def test_widget_sizes_persisted_to_session(self):
        r = self.client.post(
            reverse('profile_update'),
            data=json.dumps({'depAlerts': 'M', 'meetings': 'L'}),
            content_type='application/json',
        )
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertTrue(body['ok'])
        self.assertEqual(body['widget_sizes']['depAlerts'], 'M')
        self.assertEqual(body['widget_sizes']['meetings'], 'L')

    def test_widget_sizes_reject_unknown_keys_and_values(self):
        r = self.client.post(
            reverse('profile_update'),
            data=json.dumps({'evilKey': 'XL', 'depAlerts': 'M'}),
            content_type='application/json',
        )
        self.assertEqual(r.status_code, 200)
        body = r.json()
        # Unknown key dropped, valid one kept.
        self.assertNotIn('evilKey', body['widget_sizes'])
        self.assertEqual(body['widget_sizes']['depAlerts'], 'M')

    def test_invalid_json_rejected(self):
        r = self.client.post(
            reverse('profile_update'),
            data='not-json{{{',
            content_type='application/json',
        )
        self.assertEqual(r.status_code, 400)
