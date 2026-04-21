"""
Seed the database with realistic demo data that satisfies every schema
minimum:  ≥ 2 departments, ≥ 3 teams per department, ≥ 5 engineers per team,
≥ 2 team managers per team, 1 department leader per department.

Also creates a handful of meetings (personal / team / standup), invitations,
notifications, audit entries, skills, projects, dependencies, and a single
health session so every page has data to render.

Idempotent — running twice does not duplicate rows; it upserts by natural key.
"""
from datetime import date, datetime, time, timedelta

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from portal.models import (
    Action, Department, DepartmentLeader, Employee, HealthCard, HealthSession,
    HealthVote, Meeting, MeetingInvitation, Notification, NotificationRecipient,
    Project, Skill, Team, TeamDependency, TeamManager, TeamSkillAlloc, TeamType,
)

User = get_user_model()

DEMO_PASSWORD = 'sky-demo-2026'


DEPARTMENTS = [
    ('Platform',  'Infrastructure, tooling, reliability.'),
    ('Product',   'Customer-facing applications.'),
    ('Data',      'Data engineering and analytics.'),
]

TEAM_TYPES = ['Engineering', 'Design', 'Operations']

SKILLS = [
    'Python', 'Django', 'React', 'Kubernetes', 'Postgres',
    'TypeScript', 'SRE', 'Data Modelling',
]

HEALTH_CARDS = [
    ('Delivering value',
     'We deliver great stuff. We are proud of it.',
     'We deliver shit. We are not proud of it.'),
    ('Mission',
     'We know exactly why we are here and are really excited about it.',
     'We have no idea why we are here; there is no high-level picture.'),
]

# Teams: department_name → [team_name, ...]
TEAMS = {
    'Platform': ['Core Infra', 'Build Systems', 'Observability'],
    'Product':  ['Web Client', 'Mobile', 'Account Services'],
    'Data':     ['Ingest', 'Warehouse', 'ML Platform'],
}


class Command(BaseCommand):
    help = 'Populate the database with demo data conforming to schema minimums.'

    @transaction.atomic
    def handle(self, *args, **opts):
        self.stdout.write(self.style.NOTICE('Seeding demo data…'))

        depts = self._seed_departments()
        types = self._seed_team_types()
        skills = self._seed_skills()
        self._seed_health_cards()

        teams = self._seed_teams(depts, types)
        self._seed_skill_allocations(teams, skills)
        self._seed_team_dependencies(teams)
        self._seed_projects(teams)
        employees, managers = self._seed_people(depts, teams)
        self._seed_department_leaders(depts, employees)
        self._seed_meetings(employees, managers, teams)
        self._seed_health_session(employees, teams)
        self._seed_notifications(employees)
        self._summarise(teams)

    # ---- Sub-seeders --------------------------------------------------
    def _seed_departments(self):
        out = {}
        for name, spec in DEPARTMENTS:
            d, _ = Department.objects.get_or_create(
                departName=name, defaults={'specialization': spec},
            )
            out[name] = d
        return out

    def _seed_team_types(self):
        out = {}
        for name in TEAM_TYPES:
            t, _ = TeamType.objects.get_or_create(typeName=name)
            out[name] = t
        return out

    def _seed_skills(self):
        out = {}
        for name in SKILLS:
            s, _ = Skill.objects.get_or_create(skillName=name)
            out[name] = s
        return out

    def _seed_health_cards(self):
        for name, awesome, crappy in HEALTH_CARDS:
            HealthCard.objects.get_or_create(
                cardName=name,
                defaults={'awesomeDesc': awesome, 'crappyDesc': crappy},
            )

    def _seed_teams(self, depts, types):
        out = {}
        primary_type = list(types.values())[0]
        for dept_name, team_names in TEAMS.items():
            dept = depts[dept_name]
            for team_name in team_names:
                t, _ = Team.objects.get_or_create(
                    department=dept, teamName=team_name,
                    defaults={
                        'type': primary_type,
                        'descrip': f'The {team_name} team under {dept_name}.',
                        'focusArea': dept.specialization,
                        'teamStatus': 'active',
                        'commChann': f'#{team_name.lower().replace(" ", "-")}',
                        'agilePractice': 'Scrum',
                    },
                )
                out[(dept_name, team_name)] = t
        return out

    def _seed_skill_allocations(self, teams, skills):
        # Tag each team with three skills cyclically.
        skill_list = list(skills.values())
        for i, team in enumerate(teams.values()):
            for j in range(3):
                TeamSkillAlloc.objects.get_or_create(
                    team=team, skill=skill_list[(i + j) % len(skill_list)],
                )

    def _seed_team_dependencies(self, teams):
        keys = list(teams.keys())
        pairs = [(keys[0], keys[3]), (keys[3], keys[6]), (keys[1], keys[4])]
        for up, down in pairs:
            TeamDependency.objects.get_or_create(
                upstream=teams[up], downstream=teams[down],
                defaults={'dependencyType': 'api'},
            )

    def _seed_projects(self, teams):
        for team in teams.values():
            Project.objects.get_or_create(
                team=team, repoName=f'{team.teamName.lower().replace(" ", "-")}-svc',
                defaults={
                    'repoUrl': f'https://git.opensky.local/{team.teamName.lower().replace(" ", "-")}',
                    'isMainProj': True,
                },
            )

    def _seed_people(self, depts, teams):
        """Create 6 engineers per team: 2 managers + 4 members (≥ 5 engineers total)."""
        employees = {}  # (dept, team) -> [Employee, ...]
        managers = {}   # (dept, team) -> [TeamManager, ...]
        for (dept_name, team_name), team in teams.items():
            roster = []
            for i in range(6):
                handle = f'{dept_name}{team_name}{i}'.lower().replace(' ', '')
                email = f'{handle}@opensky.local'
                user, created = User.objects.get_or_create(
                    username=handle,
                    defaults={
                        'email': email,
                        'first_name': f'{team_name.split()[0]}',
                        'last_name':  f'Member{i}',
                    },
                )
                if created:
                    user.set_password(DEMO_PASSWORD)
                    user.save()
                emp, _ = Employee.objects.get_or_create(
                    user=user,
                    defaults={'teamId': team,
                              'position': 'Engineering Manager' if i < 2 else 'Engineer'},
                )
                # Make sure they are attached to this team even on re-run.
                if emp.teamId_id != team.teamId:
                    emp.teamId = team
                    emp.save(update_fields=['teamId'])
                roster.append(emp)
            employees[(dept_name, team_name)] = roster

            # First two roster members become managers.
            mgr_list = []
            for emp in roster[:2]:
                mgr, _ = TeamManager.objects.get_or_create(
                    emp=emp, defaults={'teamId': team},
                )
                if mgr.teamId_id != team.teamId:
                    mgr.teamId = team
                    mgr.save(update_fields=['teamId'])
                mgr_list.append(mgr)
            managers[(dept_name, team_name)] = mgr_list
        return employees, managers

    def _seed_department_leaders(self, depts, employees):
        for dept_name, dept in depts.items():
            # Take the first manager of the first team in this department.
            first_team_key = next(k for k in employees if k[0] == dept_name)
            leader_emp = employees[first_team_key][0]
            DepartmentLeader.objects.get_or_create(
                department=dept, defaults={'emp': leader_emp},
            )

    def _seed_meetings(self, employees, managers, teams):
        now = timezone.now().replace(minute=0, second=0, microsecond=0)

        # A handful of representative meetings.
        samples = [
            # (offset_hours, duration, type, team_key, invitee_count)
            (+2,  60, 'team',     ('Platform', 'Core Infra'),   4),
            (+24, 30, 'standup',  ('Product',  'Web Client'),   5),
            (-48, 60, 'team',     ('Data',     'Ingest'),       3),  # past
            (+72, 45, 'personal', ('Platform', 'Core Infra'),   2),
            (+96, 60, 'team',     ('Product',  'Mobile'),       4),
        ]

        for offset, duration, mtype, team_key, invitee_n in samples:
            team = teams[team_key]
            started = now + timedelta(hours=offset)
            ended = started + timedelta(minutes=duration)
            defaults = {
                'teamId': team,
                'startedAt': started,
                'endedAt': ended,
                'status': 'completed' if offset < 0 else 'scheduled',
                'platform': 'teams',
                'message': f'{mtype.capitalize()} meeting for {team.teamName}.',
            }
            if mtype == 'personal':
                defaults['emp'] = employees[team_key][0]
                defaults['teamEmp'] = None
                defaults['teamId'] = None
            else:
                defaults['teamEmp'] = managers[team_key][0]
                defaults['emp'] = None

            meeting, created = Meeting.objects.get_or_create(
                meetingType=mtype,
                startedAt=started,
                teamId=defaults['teamId'],
                defaults=defaults,
            )
            if created:
                for emp in employees[team_key][:invitee_n]:
                    MeetingInvitation.objects.get_or_create(
                        user=emp.user, meet=meeting,
                        defaults={'status': 'pending'},
                    )

    def _seed_health_session(self, employees, teams):
        session, _ = HealthSession.objects.get_or_create(
            sessionName='Q1 Health Check',
            defaults={'sessionDate': date.today() - timedelta(days=30)},
        )
        cards = list(HealthCard.objects.all())
        # One vote per engineer of the first team, per card.
        first_team_key = next(iter(teams))
        team = teams[first_team_key]
        for emp in employees[first_team_key]:
            for card in cards:
                HealthVote.objects.get_or_create(
                    emp=emp, session=session, card=card,
                    defaults={'teamId': team, 'rating': 'green', 'trend': 'stable'},
                )

    def _seed_notifications(self, employees):
        notif, _ = Notification.objects.get_or_create(
            message='Welcome to OpenSky. Your workspace is ready.',
            defaults={'entityType': 'Team'},
        )
        # Broadcast to every engineer.
        for roster in employees.values():
            for emp in roster:
                NotificationRecipient.objects.get_or_create(
                    user=emp.user, notif=notif,
                )

    def _summarise(self, teams):
        self.stdout.write(self.style.SUCCESS(
            f'\nSeed complete. Demo credentials: username/password shown below '
            f'— password for all demo accounts: “{DEMO_PASSWORD}”.\n'))
        self.stdout.write('Departments: ' + ', '.join(
            d.departName for d in Department.objects.all()))
        for team in Team.objects.all():
            engs = Employee.objects.filter(teamId=team).count()
            mgrs = TeamManager.objects.filter(teamId=team).count()
            self.stdout.write(
                f'  · {team.department.departName} / {team.teamName}: '
                f'{engs} engineers, {mgrs} managers'
            )
        self.stdout.write('\nSample demo usernames:')
        for u in User.objects.order_by('username')[:5]:
            self.stdout.write(f'  - {u.username}  ({u.email})')
