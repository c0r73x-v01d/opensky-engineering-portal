"""
OpenSky Engineering Portal views.
"""
import json

from django.contrib import messages as dj_messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from .forms import MeetingForm, RegisterForm
from .models import Action, Employee, Meeting, MeetingInvitation, TeamManager
from .services.schedule import assemble_for_user


# ════════════════════════════════════════════════════════════════════
# === AUTH ===
# ════════════════════════════════════════════════════════════════════
def register_view(request):
    if request.user.is_authenticated:
        return redirect('home')

    form = RegisterForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        with transaction.atomic():
            user = form.save()
            Employee.objects.create(user=user, teamId=None, position='Engineer')
            Action.objects.create(
                user=user, action='create', entityType='Users',
                entityId=user.pk, actionDescr='Self-registered.',
            )
        login(request, user)
        dj_messages.success(request, 'Welcome to OpenSky.')
        return redirect('home')
    return render(request, 'login.html', {
        'form': form,
        'register_form': form,
        'active_auth_view': 'Register',
    })


# ════════════════════════════════════════════════════════════════════
# === PAGES ===
# ════════════════════════════════════════════════════════════════════
@login_required
def home(request):
    return _coming_soon(request, 'home', 'Home')


def _coming_soon(request, active_page, title):
    return render(request, 'coming_soon.html', {
        'active_page': active_page,
        'page_title': title,
    })


@login_required
def schedule(request):
    import datetime as _dt
    anchor = None
    raw_anchor = request.GET.get('anchor')
    if raw_anchor:
        try:
            anchor = _dt.date.fromisoformat(raw_anchor)
        except ValueError:
            anchor = None

    ctx = assemble_for_user(request.user, anchor=anchor)
    ctx['active_page'] = 'schedule'
    ctx['anchor_iso'] = (anchor or _dt.date.today()).isoformat()

    # Options for the Schedule Meeting modal.
    user = request.user
    managed_teams = list(
        TeamManager.objects.filter(emp__user=user).select_related('teamId').values_list('teamId__teamId', 'teamId__teamName')
    )
    managed_team_ids = [tid for tid, _ in managed_teams]
    team_members_by_team = {}
    if managed_team_ids:
        for emp in Employee.objects.filter(teamId__in=managed_team_ids).select_related('user'):
            team_members_by_team.setdefault(emp.teamId_id, []).append({
                'user_id': emp.user_id,
                'name': f'{emp.user.first_name} {emp.user.last_name}'.strip() or emp.user.username,
            })
    ctx['managed_teams'] = [{'id': tid, 'name': name} for tid, name in managed_teams]
    ctx['team_members_by_team_json'] = json.dumps(team_members_by_team)
    ctx['user_is_employee'] = Employee.objects.filter(user=user).exists()
    return render(request, 'schedule.html', ctx)


# ════════════════════════════════════════════════════════════════════
# === SCHEDULE — RSVP ===
# ════════════════════════════════════════════════════════════════════
@login_required
@require_POST
def meeting_rsvp(request, meet_id):
    try:
        body = json.loads(request.body or b'{}')
    except json.JSONDecodeError:
        return JsonResponse({'ok': False, 'error': 'Invalid JSON.'}, status=400)

    new_status = (body.get('status') or '').strip().lower()
    if new_status not in ('accepted', 'declined'):
        return JsonResponse({'ok': False, 'error': 'Status must be accepted or declined.'}, status=400)

    try:
        invitation = MeetingInvitation.objects.select_related('meet').get(
            user=request.user, meet_id=meet_id,
        )
    except MeetingInvitation.DoesNotExist:
        return JsonResponse({'ok': False, 'error': 'No invitation for this meeting.'}, status=403)

    old_status = invitation.status
    if old_status == new_status:
        return JsonResponse({'ok': True, 'status': new_status, 'changed': False})

    with transaction.atomic():
        invitation.status = new_status
        invitation.save(update_fields=['status'])
        Action.objects.create(
            user=request.user,
            action='update',
            entityType='MeetingInvitation',
            entityId=invitation.invitationId,
            fieldChanged='status',
            oldValue=old_status,
            newValue=new_status,
            actionDescr=f'RSVP {old_status} → {new_status} for meeting {meet_id}.',
        )

    return JsonResponse({'ok': True, 'status': new_status, 'changed': True})


# ════════════════════════════════════════════════════════════════════
# === SCHEDULE — CREATE ===
# ════════════════════════════════════════════════════════════════════
@login_required
@require_POST
def meeting_create(request):
    form = MeetingForm(request.POST)
    if not form.is_valid():
        return JsonResponse({'ok': False, 'errors': form.errors}, status=400)

    cd = form.cleaned_data
    mtype = cd['meeting_type']
    user = request.user

    # Resolve who hosts the meeting based on the type and the user's role.
    emp_host = None
    team_mgr_host = None
    team = cd.get('host_team')

    if mtype == 'personal':
        try:
            emp_host = Employee.objects.get(user=user)
        except Employee.DoesNotExist:
            return JsonResponse(
                {'ok': False, 'errors': {'meeting_type': ['You must be an employee to create personal meetings.']}},
                status=403,
            )
    else:
        # team or standup — current user must manage the chosen team
        try:
            team_mgr_host = TeamManager.objects.get(emp__user=user, teamId=team)
        except TeamManager.DoesNotExist:
            return JsonResponse(
                {'ok': False, 'errors': {'host_team': ['You can only create team meetings for teams you manage.']}},
                status=403,
            )

    title = cd['title']
    agenda = (cd.get('agenda') or '').strip()
    message_lines = [title]
    if cd.get('recurring') and cd['recurring'] != 'one-time':
        message_lines.append(f'Recurring: {cd["recurring"]}')
    if agenda:
        message_lines.append('')
        message_lines.append(agenda)
    message = '\n'.join(message_lines)

    with transaction.atomic():
        meeting = Meeting.objects.create(
            teamId=team if mtype != 'personal' else None,
            emp=emp_host,
            teamEmp=team_mgr_host,
            meetingType=mtype,
            startedAt=cd['start'],
            endedAt=cd['end'],
            platform=cd['platform'],
            message=message,
            status='scheduled',
        )

        # Build the attendee list — explicit IDs from the form, plus the
        # creator (always invited and accepted), plus the host team's
        # employees for team meetings.
        attendee_user_ids = set(cd.get('attendee_ids') or [])
        attendee_user_ids.add(user.userId)
        if mtype != 'personal' and team is not None:
            for e in Employee.objects.filter(teamId=team).select_related('user'):
                attendee_user_ids.add(e.user_id)

        invitations = []
        for uid in attendee_user_ids:
            invitations.append(MeetingInvitation(
                user_id=uid,
                meet=meeting,
                status='accepted' if uid == user.userId else 'pending',
            ))
        if invitations:
            MeetingInvitation.objects.bulk_create(invitations, ignore_conflicts=True)

        Action.objects.create(
            user=user,
            action='create',
            entityType='Meeting',
            entityId=meeting.meetId,
            actionDescr=f'Created {mtype} meeting "{title}" at {cd["start"]:%Y-%m-%d %H:%M}.',
        )

    return JsonResponse({
        'ok': True,
        'meeting': {
            'meet_id': meeting.meetId,
            'type': meeting.meetingType,
            'title': title,
            'platform': meeting.platform,
            'start': meeting.startedAt.isoformat(),
            'end': meeting.endedAt.isoformat() if meeting.endedAt else None,
        },
    })


@login_required
def teams(request):
    return _coming_soon(request, 'teams', 'Teams')


@login_required
def organisation(request):
    return _coming_soon(request, 'organisation', 'Organisation')


@login_required
def messages_view(request):
    return _coming_soon(request, 'messages', 'Messages')


@login_required
def reports(request):
    return _coming_soon(request, 'reports', 'Reports')
