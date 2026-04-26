"""Smoke tests for the schedule page view."""

import datetime

from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone

from portal.models import MeetingInvitation
from . import _helpers as f


class ScheduleViewTests(TestCase):
    def setUp(self):
        self.dept = f.make_department()
        self.team = f.make_team(self.dept)
        self.alice = f.make_user('alice')
        self.bob = f.make_user('bob')
        f.make_employee(self.alice, self.team)
        f.make_manager(self.bob, self.team)

        # Anchor the test meeting on real today so the schedule's live window
        # always picks it up regardless of when the suite runs.
        anchor_dt = datetime.datetime.combine(timezone.localdate(), datetime.time(10, 0),
                                              tzinfo=timezone.get_current_timezone())
        self.meeting = f.make_meeting(self.bob, self.team, when=anchor_dt, title='Anchor sync')
        f.invite(self.alice, self.meeting, status='pending')

    def test_login_required(self):
        c = Client()
        r = c.get(reverse('schedule'))
        self.assertEqual(r.status_code, 302)
        self.assertIn('/login/', r['Location'])

    def test_renders_logged_in(self):
        c = Client(); c.force_login(self.alice)
        r = c.get(reverse('schedule'))
        self.assertEqual(r.status_code, 200)
        body = r.content.decode()
        self.assertIn('Anchor sync', body)
        self.assertIn('data-meet-id="' + str(self.meeting.meetId) + '"', body)

    def test_kpi_pending_counts_user_invitations(self):
        c = Client(); c.force_login(self.alice)
        r = c.get(reverse('schedule'))
        self.assertEqual(r.context['kpis']['pending'], 1)

    def test_other_users_meetings_not_shown(self):
        # Carol has no invitations; her schedule shouldn't show alice's meeting.
        carol = f.make_user('carol')
        f.make_employee(carol, self.team)
        c = Client(); c.force_login(carol)
        r = c.get(reverse('schedule'))
        body = r.content.decode()
        self.assertNotIn('data-meet-id="' + str(self.meeting.meetId) + '"', body)
        self.assertEqual(r.context['kpis']['this_week'], 0)
