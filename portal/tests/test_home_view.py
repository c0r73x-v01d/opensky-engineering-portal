"""Smoke tests for the home dashboard view."""

from django.test import TestCase, Client
from django.urls import reverse

from . import _helpers as f


class HomeViewTests(TestCase):
    def setUp(self):
        self.dept = f.make_department(name='Platform')
        self.team = f.make_team(self.dept, name='Core Infra')
        self.alice = f.make_user('alice', first='Alice', last='Lee')
        self.bob = f.make_user('bob', first='Bob', last='Marsh')
        f.make_employee(self.alice, self.team, position='Senior Engineer')
        f.make_manager(self.bob, self.team)

    def test_login_required(self):
        c = Client()
        r = c.get(reverse('home'))
        self.assertEqual(r.status_code, 302)
        self.assertIn('/login/', r['Location'])

    def test_renders_full_dashboard_for_team_member(self):
        c = Client(); c.force_login(self.alice)
        r = c.get(reverse('home'))
        self.assertEqual(r.status_code, 200)
        body = r.content.decode()
        # Hero shows greeting + team name
        self.assertIn('Alice', body)
        self.assertIn('Core Infra', body)
        self.assertIn('Platform', body)
        # Widget grid mounted
        self.assertIn('id="widget-grid"', body)
        # Profile modal mounted on every authenticated page
        self.assertIn('id="profile-modal"', body)
        self.assertIn('id="view-profile-btn"', body)

    def test_renders_no_team_state_for_new_user(self):
        """Self-registered users with no Employee row see a welcome stub."""
        loner = f.make_user('loner', first='Loner', last='Wolf')
        c = Client(); c.force_login(loner)
        r = c.get(reverse('home'))
        self.assertEqual(r.status_code, 200)
        body = r.content.decode()
        # No widget grid, just the welcome stub
        self.assertNotIn('id="widget-grid"', body)
        self.assertIn('Welcome, Loner', body)
        # Profile modal still mounted
        self.assertIn('id="profile-modal"', body)
