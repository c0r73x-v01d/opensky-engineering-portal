"""Tests for the meeting_user_search endpoint (guests autocomplete)."""

from django.test import TestCase, Client
from django.urls import reverse

from . import _helpers as f


class MeetingUserSearchTests(TestCase):
    def setUp(self):
        self.dept = f.make_department()
        self.team = f.make_team(self.dept)
        self.alice = f.make_user('alice', first='Alice', last='Lee', email='alice@example.com')
        self.bob = f.make_user('bob', first='Bob', last='Stone', email='bob.stone@example.com')
        self.charlie = f.make_user('charlie', first='Charlie', last='Park', email='char@example.com')
        f.make_employee(self.alice, self.team, position='Engineer')
        f.make_employee(self.bob, self.team, position='Manager')
        f.make_employee(self.charlie, self.team, position='Engineer')

    def _get(self, c, q):
        return c.get(reverse('meeting_user_search'), {'q': q})

    def test_login_required(self):
        c = Client()
        r = self._get(c, 'bob')
        self.assertEqual(r.status_code, 302)

    def test_short_query_returns_empty(self):
        c = Client(); c.force_login(self.alice)
        r = self._get(c, 'a')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json(), {'results': []})

    def test_query_matches_first_name(self):
        c = Client(); c.force_login(self.alice)
        r = self._get(c, 'bob')
        self.assertEqual(r.status_code, 200)
        names = [u['name'] for u in r.json()['results']]
        self.assertIn('Bob Stone', names)

    def test_query_matches_email(self):
        c = Client(); c.force_login(self.alice)
        r = self._get(c, 'char@')
        names = [u['name'] for u in r.json()['results']]
        self.assertIn('Charlie Park', names)

    def test_excludes_requester(self):
        c = Client(); c.force_login(self.alice)
        r = self._get(c, 'alice')
        ids = [u['id'] for u in r.json()['results']]
        self.assertNotIn(self.alice.pk, ids)

    def test_response_shape(self):
        c = Client(); c.force_login(self.alice)
        r = self._get(c, 'bob')
        result = r.json()['results'][0]
        self.assertIn('id', result)
        self.assertIn('name', result)
        self.assertIn('email', result)
        self.assertIn('position', result)

    def test_results_capped_at_eight(self):
        # Add several more users matching 'demo'
        for i in range(12):
            f.make_user(f'demo{i}', first=f'Demo{i}', last='User',
                        email=f'demo{i}@example.com')
        c = Client(); c.force_login(self.alice)
        r = self._get(c, 'demo')
        self.assertLessEqual(len(r.json()['results']), 8)
