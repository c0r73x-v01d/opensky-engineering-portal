"""Shared test helpers — small object factories for the schedule slice tests."""

from __future__ import annotations

import datetime

from django.utils import timezone

from portal.models import (
    Department, Employee, Meeting, MeetingInvitation, Team, TeamManager,
    User,
)


def make_user(username='alice', first='Alice', last='Lee', email=None, password='pw'):
    return User.objects.create_user(
        username=username,
        first_name=first,
        last_name=last,
        email=email or f'{username}@example.com',
        password=password,
    )


def make_department(name='Platform'):
    return Department.objects.create(departName=name)


def make_team(department=None, name='Core Infra', status='active'):
    return Team.objects.create(
        teamName=name,
        department=department or make_department(),
        teamStatus=status,
    )


def make_employee(user, team=None, position='Engineer'):
    return Employee.objects.create(user=user, teamId=team, position=position)


def make_manager(user, team):
    """Make `user` an Employee on `team` AND a TeamManager of `team`."""
    emp = Employee.objects.filter(user=user).first() or make_employee(user, team, 'Engineering Manager')
    if emp.teamId_id != team.teamId:
        emp.teamId = team
        emp.save(update_fields=['teamId'])
    TeamManager.objects.get_or_create(emp=emp, teamId=team)
    return emp


def make_meeting(host_user, team, when=None, duration_minutes=60,
                 platform='teams', mtype='team', title='Sync'):
    """`host_user` is a User; helper resolves the Employee/TeamManager."""
    when = when or (timezone.now() + datetime.timedelta(days=1))
    emp = Employee.objects.get(user=host_user)
    if mtype == 'personal':
        return Meeting.objects.create(
            teamId=None,
            emp=emp,
            teamEmp=None,
            meetingType=mtype,
            startedAt=when,
            endedAt=when + datetime.timedelta(minutes=duration_minutes),
            platform=platform,
            message=title,
            status='scheduled',
        )
    tm = TeamManager.objects.get(emp=emp, teamId=team)
    return Meeting.objects.create(
        teamId=team,
        emp=None,
        teamEmp=tm,
        meetingType=mtype,
        startedAt=when,
        endedAt=when + datetime.timedelta(minutes=duration_minutes),
        platform=platform,
        message=title,
        status='scheduled',
    )


def invite(user, meeting, status='pending'):
    return MeetingInvitation.objects.create(user=user, meet=meeting, status=status)
