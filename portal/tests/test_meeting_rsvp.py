"""Tests for the RSVP endpoint."""

import datetime
import json

from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone

from portal.models import Action, MeetingInvitation
from . import _helpers as f


class MeetingRsvpTests(TestCase):
    def setUp(self):
        self.dept = f.make_department()
        self.team = f.make_team(self.dept)
        self.alice = f.make_user('alice')
        self.bob = f.make_user('bob')
        f.make_employee(self.alice, self.team)
        f.make_manager(self.bob, self.team)
        self.meeting = f.make_meeting(self.bob, self.team)
        self.invite = f.invite(self.alice, self.meeting, status='pending')

    def _post(self, c, meet_id, payload):
        return c.post(
            reverse('meeting_rsvp', args=[meet_id]),
            data=json.dumps(payload),
            content_type='application/json',
        )

    def test_login_required(self):
        c = Client()
        r = self._post(c, self.meeting.meetId, {'status': 'accepted'})
        self.assertEqual(r.status_code, 302)

    def test_accept_flips_status_and_writes_action(self):
        c = Client(); c.force_login(self.alice)
        before = Action.objects.count()
        r = self._post(c, self.meeting.meetId, {'status': 'accepted'})
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertTrue(body['ok'])
        self.assertEqual(body['status'], 'accepted')
        self.assertTrue(body['changed'])
        self.invite.refresh_from_db()
        self.assertEqual(self.invite.status, 'accepted')
        self.assertEqual(Action.objects.count(), before + 1)
        a = Action.objects.latest('actionId')
        self.assertEqual(a.entityType, 'MeetingInvitation')
        self.assertEqual(a.fieldChanged, 'status')

    def test_idempotent_repost(self):
        self.invite.status = 'accepted'; self.invite.save()
        c = Client(); c.force_login(self.alice)
        r = self._post(c, self.meeting.meetId, {'status': 'accepted'})
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertTrue(body['ok'])
        self.assertFalse(body['changed'])

    def test_decline_flips_back(self):
        self.invite.status = 'accepted'; self.invite.save()
        c = Client(); c.force_login(self.alice)
        r = self._post(c, self.meeting.meetId, {'status': 'declined'})
        self.assertEqual(r.status_code, 200)
        self.invite.refresh_from_db()
        self.assertEqual(self.invite.status, 'declined')

    def test_403_when_no_invitation(self):
        carol = f.make_user('carol')
        c = Client(); c.force_login(carol)
        r = self._post(c, self.meeting.meetId, {'status': 'accepted'})
        self.assertEqual(r.status_code, 403)
        self.assertFalse(r.json()['ok'])

    def test_400_for_invalid_status(self):
        c = Client(); c.force_login(self.alice)
        r = self._post(c, self.meeting.meetId, {'status': 'maybe'})
        self.assertEqual(r.status_code, 400)

    def test_400_for_invalid_json(self):
        c = Client(); c.force_login(self.alice)
        r = c.post(reverse('meeting_rsvp', args=[self.meeting.meetId]),
                   data='not json', content_type='application/json')
        self.assertEqual(r.status_code, 400)

    def test_405_for_get(self):
        c = Client(); c.force_login(self.alice)
        r = c.get(reverse('meeting_rsvp', args=[self.meeting.meetId]))
        self.assertEqual(r.status_code, 405)
