"""Tests for the meeting_create endpoint."""

import datetime

from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone

from portal.models import Action, Meeting, MeetingInvitation
from . import _helpers as f


def _future_date(days=2):
    return (timezone.now() + datetime.timedelta(days=days)).date().isoformat()


class MeetingCreateTests(TestCase):
    def setUp(self):
        self.dept = f.make_department()
        self.team = f.make_team(self.dept)
        self.bob = f.make_user('bob')
        self.alice = f.make_user('alice')
        f.make_manager(self.bob, self.team)
        f.make_employee(self.alice, self.team)

    def _post(self, c, **overrides):
        data = {
            'meeting_type': 'team',
            'host_team': self.team.teamId,
            'title': 'Sprint Planning',
            'date': _future_date(),
            'time': '10:00',
            'duration': '1h',
            'platform': 'teams',
            'recurring': 'one-time',
            'agenda': '',
            'attendee_ids': '',
        }
        data.update(overrides)
        return c.post(reverse('meeting_create'), data=data)

    def test_login_required(self):
        c = Client()
        r = self._post(c)
        self.assertEqual(r.status_code, 302)

    def test_team_meeting_happy_path(self):
        c = Client(); c.force_login(self.bob)
        before = Meeting.objects.count()
        r = self._post(c)
        self.assertEqual(r.status_code, 200, r.content)
        body = r.json()
        self.assertTrue(body['ok'])
        self.assertEqual(Meeting.objects.count(), before + 1)
        m = Meeting.objects.latest('meetId')
        self.assertEqual(m.meetingType, 'team')
        self.assertEqual(m.platform, 'teams')
        self.assertEqual(m.teamId_id, self.team.teamId)
        # Creator is invited and accepted; team members are invited.
        self.assertTrue(MeetingInvitation.objects.filter(meet=m, user=self.bob, status='accepted').exists())
        self.assertTrue(MeetingInvitation.objects.filter(meet=m, user=self.alice).exists())

    def test_team_meeting_writes_audit(self):
        c = Client(); c.force_login(self.bob)
        before = Action.objects.filter(entityType='Meeting').count()
        self._post(c, title='Audit me')
        self.assertEqual(Action.objects.filter(entityType='Meeting').count(), before + 1)
        a = Action.objects.filter(entityType='Meeting').latest('actionId')
        self.assertEqual(a.action, 'create')
        self.assertEqual(a.user, self.bob)

    def test_personal_meeting_happy_path(self):
        c = Client(); c.force_login(self.alice)
        r = self._post(c, meeting_type='personal', host_team='', title='1:1')
        self.assertEqual(r.status_code, 200, r.content)
        m = Meeting.objects.latest('meetId')
        self.assertEqual(m.meetingType, 'personal')
        self.assertIsNone(m.teamId_id)
        self.assertIsNotNone(m.emp_id)

    def test_team_meeting_requires_host_team(self):
        c = Client(); c.force_login(self.bob)
        r = self._post(c, host_team='')
        self.assertEqual(r.status_code, 400)
        errs = r.json()['errors']
        self.assertIn('host_team', errs)

    def test_403_non_manager_cannot_create_team_meeting(self):
        c = Client(); c.force_login(self.alice)
        r = self._post(c)
        self.assertEqual(r.status_code, 403)

    def test_rejects_past_start(self):
        c = Client(); c.force_login(self.bob)
        past = (timezone.now() - datetime.timedelta(days=1)).date().isoformat()
        r = self._post(c, date=past)
        self.assertEqual(r.status_code, 400)
        self.assertIn('date', r.json()['errors'])

    def test_405_for_get(self):
        c = Client(); c.force_login(self.bob)
        r = c.get(reverse('meeting_create'))
        self.assertEqual(r.status_code, 405)
