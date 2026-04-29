"""Tests for the meeting_delete endpoint."""

import datetime

from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone

from portal.models import Action, Meeting, MeetingInvitation
from . import _helpers as f


class MeetingDeleteTests(TestCase):
    def setUp(self):
        self.dept = f.make_department()
        self.team = f.make_team(self.dept)
        self.bob = f.make_user('bob')
        self.alice = f.make_user('alice')
        f.make_manager(self.bob, self.team)
        f.make_employee(self.alice, self.team)
        when = timezone.now() + datetime.timedelta(days=2)
        self.meeting = f.make_meeting(self.bob, self.team, when=when, title='Demo')
        f.invite(self.alice, self.meeting, status='pending')
        f.invite(self.bob, self.meeting, status='accepted')

    def test_login_required(self):
        c = Client()
        r = c.post(reverse('meeting_delete', args=[self.meeting.meetId]))
        self.assertEqual(r.status_code, 302)

    def test_organiser_deletes_meeting(self):
        c = Client(); c.force_login(self.bob)
        before_actions = Action.objects.filter(entityType='Meeting').count()
        r = c.post(reverse('meeting_delete', args=[self.meeting.meetId]))
        self.assertEqual(r.status_code, 200, r.content)
        self.assertTrue(r.json()['ok'])
        self.assertFalse(Meeting.objects.filter(meetId=self.meeting.meetId).exists())
        self.assertFalse(MeetingInvitation.objects.filter(meet_id=self.meeting.meetId).exists())
        self.assertEqual(
            Action.objects.filter(entityType='Meeting', action='delete').count(),
            before_actions + 1,
        )

    def test_non_organiser_forbidden(self):
        c = Client(); c.force_login(self.alice)
        r = c.post(reverse('meeting_delete', args=[self.meeting.meetId]))
        self.assertEqual(r.status_code, 403)
        self.assertTrue(Meeting.objects.filter(meetId=self.meeting.meetId).exists())

    def test_404_for_unknown_meeting(self):
        c = Client(); c.force_login(self.bob)
        r = c.post(reverse('meeting_delete', args=[999999]))
        self.assertEqual(r.status_code, 404)

    def test_405_for_get(self):
        c = Client(); c.force_login(self.bob)
        r = c.get(reverse('meeting_delete', args=[self.meeting.meetId]))
        self.assertEqual(r.status_code, 405)
