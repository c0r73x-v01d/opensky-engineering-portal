"""
Server-side tests for the Teams page view.

Each test maps to a CWK1 test plan ID (TM-01 through TM-14)
"""

import json
import re

from django.test import TestCase, Client
from django.urls import reverse

from portal.models import (
    Department, Employee, Project, Team, TeamDependency, TeamType, User,
)
from . import _helpers as f


def _user_with_team(team, username='alice', position='Engineer'):
    """Create a user, attach an Employee row to the given team"""
    user = f.make_user(username, first=username.title(), last='User')
    Employee.objects.create(user=user, teamId=team, position=position)
    return user


class TeamsViewTests(TestCase):
    """End-to-end server-side coverage of the Teams page"""

    @classmethod
    def setUpTestData(cls):
        # Departments
        cls.dept_platform = Department.objects.create(departName='Platform')
        cls.dept_data = Department.objects.create(departName='Data')

        # Team types
        cls.type_platform = TeamType.objects.create(typeName='Platform')
        cls.type_security = TeamType.objects.create(typeName='Security')

        # Teams: one active platform, one restructuring data, one disbanded
        cls.team_phoenix = Team.objects.create(
            teamName='Phoenix Platform', department=cls.dept_platform,
            type=cls.type_platform, teamStatus='active',
            descrip='Owns the Sky core platform.',
            responsib='Reliability and developer experience.',
            focusArea='Internal platform', agilePractice='Scrum',
            jiraProjName='PHX', jiraBoardLink='https://jira.local/phx',
            commChann='#phoenix', teamWiki='https://wiki.local/phoenix',
        )
        cls.team_streaming = Team.objects.create(
            teamName='Streaming Engine', department=cls.dept_data,
            type=cls.type_platform, teamStatus='restructuring',
            descrip='Real-time pipelines.',
        )
        cls.team_legacy = Team.objects.create(
            teamName='Legacy Edge', department=cls.dept_platform,
            type=cls.type_security, teamStatus='disbanded',
        )

        # An assigned user that the @team_member_required decorator accepts
        cls.user = _user_with_team(cls.team_phoenix, 'alice')

        # A single Project for Phoenix so TM-10 has a repo to render
        Project.objects.create(
            team=cls.team_phoenix, repoName='phoenix-core',
            repoUrl='https://git.local/phoenix-core', isMainProj=True,
        )

        # A single dependency: Phoenix depends on Streaming
        TeamDependency.objects.create(
            upstream=cls.team_streaming, downstream=cls.team_phoenix,
            dependencyType='data',
        )

    def setUp(self):
        self.client = Client()
        self.client.force_login(self.user)
        response = self.client.get(reverse('teams'))
        self.assertEqual(response.status_code, 200,
                         'Teams page should render for an authenticated team member.')
        self.body = response.content.decode()

    def _teams_json_payload(self):
        """Pull the JSON blob from the <script id="teams-data"> tag."""
        match = re.search(
            r'<script[^>]*id="teams-data"[^>]*>(.*?)</script>',
            self.body, flags=re.DOTALL,
        )
        self.assertIsNotNone(match, 'teams-data JSON block missing from page.')
        return json.loads(match.group(1))

    # ──────────────────────────────────────────────────────────────────
    # TM-01  View All Teams
    # ──────────────────────────────────────────────────────────────────
    def test_tm01_view_all_teams(self):
        # All three seeded teams render their names
        for team_name in ('Phoenix Platform', 'Streaming Engine', 'Legacy Edge'):
            self.assertIn(team_name, self.body,
                          f'{team_name} not rendered on the Teams page.')
        # Stats bar headings present
        for label in ('Total Teams', 'Active', 'Engineers', 'Skills'):
            self.assertIn(label, self.body, f'Stat label "{label}" missing.')

    # ──────────────────────────────────────────────────────────────────
    # TM-02  Search Teams (positive)
    # ──────────────────────────────────────────────────────────────────
    def test_tm02_search_input_and_haystack_present(self):
        # The search input the JS binds t
        self.assertIn('id="team-search"', self.body)
        # The serialiser builds a haystack the JS searches against
        payload = self._teams_json_payload()
        phoenix = next(t for t in payload if t['team_name'] == 'Phoenix Platform')
        self.assertIn('Phoenix Platform', phoenix['team_name'])
        # Search payload spans department, manager, skills text and Jira project
        self.assertEqual(phoenix['department_name'], 'Platform')

    # ──────────────────────────────────────────────────────────────────
    # TM-03  Search Teams (no-results state)
    # ──────────────────────────────────────────────────────────────────
    def test_tm03_no_results_empty_state_in_dom(self):
        self.assertIn('id="no-results"', self.body)
        self.assertIn('No teams found', self.body)

    # ──────────────────────────────────────────────────────────────────
    # TM-04  Filter by Department
    # ──────────────────────────────────────────────────────────────────
    def test_tm04_department_filter_options(self):
        self.assertIn('id="filter-dept"', self.body)
        # Each seeded department appears as an <option>
        self.assertIn('>Platform</option>', self.body)
        self.assertIn('>Data</option>', self.body)

    # ──────────────────────────────────────────────────────────────────
    # TM-05  Filter by Status
    # ──────────────────────────────────────────────────────────────────
    def test_tm05_status_filter_has_three_options(self):
        self.assertIn('id="filter-status"', self.body)
        for status_label in ('Active', 'Restructuring', 'Disbanded'):
            self.assertIn(f'>{status_label}</option>', self.body)
        # Cards expose data-status so the JS can filter against it.
        self.assertIn('data-status="active"', self.body)
        self.assertIn('data-status="restructuring"', self.body)
        self.assertIn('data-status="disbanded"', self.body)

    # ──────────────────────────────────────────────────────────────────
    # TM-06  Filter by Team Type
    # ──────────────────────────────────────────────────────────────────
    def test_tm06_type_filter_options(self):
        self.assertIn('id="filter-type"', self.body)
        self.assertIn('>Platform</option>', self.body)
        self.assertIn('>Security</option>', self.body)

    # ──────────────────────────────────────────────────────────────────
    # TM-07  Combined Filters + Search
    # ──────────────────────────────────────────────────────────────────
    def test_tm07_search_and_filters_coexist(self):
        # All four controls present in the same toolbar.
        self.assertIn('id="team-search"', self.body)
        self.assertIn('id="filter-dept"', self.body)
        self.assertIn('id="filter-status"', self.body)
        self.assertIn('id="filter-type"', self.body)
        # Each card exposes data-attributes the JS needs for AND-filtering
        for attr in ('data-team-id', 'data-dept', 'data-status', 'data-type'):
            self.assertIn(attr, self.body)

    # ──────────────────────────────────────────────────────────────────
    # TM-08  Clear Filters
    # ──────────────────────────────────────────────────────────────────
    def test_tm08_clear_button_present(self):
        self.assertIn('id="filter-clear"', self.body)

    # ──────────────────────────────────────────────────────────────────
    # TM-09  Toggle Grid / List View
    # ──────────────────────────────────────────────────────────────────
    def test_tm09_view_toggle_buttons(self):
        # Both toggles in the same group.
        self.assertIn('class="view-toggle-group"', self.body)
        self.assertIn('data-view="grid"', self.body)
        self.assertIn('data-view="list"', self.body)
        # Container starts in grid mode.
        self.assertIn('id="teams-container" class="teams-grid"', self.body)

    # ──────────────────────────────────────────────────────────────────
    # TM-10  View Team Detail Panel
    # ──────────────────────────────────────────────────────────────────
    def test_tm10_detail_panel_payload_complete(self):
        payload = self._teams_json_payload()
        phoenix = next(t for t in payload if t['team_name'] == 'Phoenix Platform')
        # Every field the slide-panel renders must be present and populated
        self.assertEqual(phoenix['description'], 'Owns the Sky core platform.')
        self.assertEqual(phoenix['responsibilities'],
                         'Reliability and developer experience.')
        self.assertEqual(phoenix['focus'], 'Internal platform')
        self.assertEqual(phoenix['agile_practice'], 'Scrum')
        self.assertEqual(phoenix['jira_project'], 'PHX')
        self.assertEqual(phoenix['comm_channel'], '#phoenix')
        # Members, repos and dependencies are arrays the JS iterates
        self.assertGreaterEqual(len(phoenix['members']), 1)
        self.assertEqual(len(phoenix['repos']), 1)
        self.assertEqual(phoenix['repos'][0]['name'], 'phoenix-core')
        # Slide-panel container itself is in the DOM
        self.assertIn('id="detail-panel"', self.body)
        self.assertIn('class="sky-slide-panel"', self.body)

    # ──────────────────────────────────────────────────────────────────
    # TM-11  Close Team Detail
    # ──────────────────────────────────────────────────────────────────
    def test_tm11_close_controls_present(self):
        self.assertIn('id="panel-close-btn"', self.body)
        self.assertIn('id="panel-overlay-bg"', self.body)

    # ──────────────────────────────────────────────────────────────────
    # TM-12  View Dependencies
    # ──────────────────────────────────────────────────────────────────
    def test_tm12_dependencies_serialised(self):
        payload = self._teams_json_payload()
        phoenix = next(t for t in payload if t['team_name'] == 'Phoenix Platform')
        streaming = next(t for t in payload if t['team_name'] == 'Streaming Engine')

        # Phoenix → upstream contains Streaming (Phoenix depends on it)
        upstream_names = [u['name'] for u in phoenix['upstream']]
        self.assertIn('Streaming Engine', upstream_names)

        # Streaming → downstream contains Phoenix (Phoenix depends on Streaming)
        downstream_names = [d['name'] for d in streaming['downstream']]
        self.assertIn('Phoenix Platform', downstream_names)

        # Dep count surfaced for the card footer
        self.assertGreaterEqual(phoenix['dep_count'], 1)

    # ──────────────────────────────────────────────────────────────────
    # TM-13  Email Team action
    # ──────────────────────────────────────────────────────────────────
    def test_tm13_email_team_action_wired(self):
        # The Email Team button is built client-side by teams.js using the
        # team id from the page payload. Within the scope of the Teams
        # slice, the assertion is twofold:
        #   1. every team has a numeric id the JS can append to the URL;
        #   2. the /messages/ endpoint exists and is reachable, so the
        #      hard-coded redirect target won't 404.
        # What the messages slice does with the ?compose=team&team_id=N
        # query is owned by another team member and not asserted here
        payload = self._teams_json_payload()
        phoenix = next(t for t in payload if t['team_name'] == 'Phoenix Platform')
        self.assertIsInstance(phoenix['id'], int)

        r = self.client.get(reverse('messages'))
        self.assertEqual(r.status_code, 200)

    # ──────────────────────────────────────────────────────────────────
    # TM-14  Schedule Meeting action
    # ──────────────────────────────────────────────────────────────────
    def test_tm14_schedule_meeting_action_wired(self):
        # As with TM-13, the Schedule Meeting button is rendered by JS
        # which builds /schedule/?compose=team&team_id=N. The schedule
        # view accepts that query and returns 200; the prefill JSON
        # payload only renders for manager users, but for the routing
        # smoke check it's enough to confirm the endpoint accepts the
        # parameters and returns the schedule page successfully.
        payload = self._teams_json_payload()
        phoenix = next(t for t in payload if t['team_name'] == 'Phoenix Platform')

        r = self.client.get(
            reverse('schedule') + f'?compose=team&team_id={phoenix["id"]}'
        )
        self.assertEqual(r.status_code, 200)
        self.assertIn('Schedule', r.content.decode())
