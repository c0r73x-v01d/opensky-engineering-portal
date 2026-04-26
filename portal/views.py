"""
OpenSky Engineering Portal views.
"""
import json

from django.contrib import messages as dj_messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from .forms import MeetingForm, RegisterForm
from .models import (
    Action,
    Employee,
    Meeting,
    MeetingInvitation,
    Message,
    MessageRecipient,
    Notification,
    NotificationRecipient,
    Team,
    TeamManager,
    User,
)
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
    ctx = assemble_for_user(request.user)
    ctx['active_page'] = 'schedule'

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


# ════════════════════════════════════════════════════════════════════
# === MESSAGES ===
# ════════════════════════════════════════════════════════════════════
def _messages_redirect(folder='inbox'):
    return redirect(f"{reverse('messages')}?folder={folder}")


def _prepare_messages_for_template(messages, starred_ids):
    prepared = []

    for msg in messages:
        recipient_link = msg.recipients.select_related('user').first()

        msg.id = msg.messageId
        msg.sender = msg.user
        msg.recipient = recipient_link.user if recipient_link else None
        msg.sent_at = msg.sentAt
        msg.created_at = msg.createdAt
        msg.is_read = recipient_link.isRead if recipient_link else True
        msg.starred = str(msg.messageId) in starred_ids

        prepared.append(msg)

    return prepared


@login_required
def messages_view(request):
    current_folder = request.GET.get('folder', 'inbox')
    starred_ids = set(request.session.get('starred_messages', []))

    inbox_qs = Message.objects.filter(
        recipients__user=request.user,
        status='sent',
        recipients__recipMsgDeleted=False,
    ).select_related('user').prefetch_related('recipients__user').order_by('-sentAt', '-createdAt')

    sent_qs = Message.objects.filter(
        user=request.user,
        status='sent',
        senderMsgDeleted=False,
    ).select_related('user').prefetch_related('recipients__user').order_by('-sentAt', '-createdAt')

    draft_qs = Message.objects.filter(
        user=request.user,
        status='draft',
        senderMsgDeleted=False,
    ).select_related('user').prefetch_related('recipients__user').order_by('-createdAt')

    if current_folder == 'sent':
        selected_qs = sent_qs
    elif current_folder == 'drafts':
        selected_qs = draft_qs
    else:
        current_folder = 'inbox'
        selected_qs = inbox_qs

    messages = _prepare_messages_for_template(selected_qs, starred_ids)

    context = {
        'active_page': 'messages',
        'messages': messages,
        'current_folder': current_folder,
        'inbox_count': inbox_qs.count(),
        'sent_count': sent_qs.count(),
        'draft_count': draft_qs.count(),
        'unread_count': inbox_qs.filter(recipients__isRead=False).count(),
        'employees': User.objects.exclude(pk=request.user.pk).order_by('first_name', 'last_name', 'username'),
    }

    return render(request, 'messages.html', context)


@login_required
@require_POST
def message_send(request):
    recipient_id = request.POST.get('to')
    subject = request.POST.get('subject', '').strip()
    body = request.POST.get('body', '').strip()
    action = request.POST.get('action', 'send')

    if not recipient_id:
        dj_messages.error(request, 'Please choose a recipient.')
        return _messages_redirect('inbox')

    recipient = get_object_or_404(User, pk=recipient_id)

    with transaction.atomic():
        msg = Message.objects.create(
            user=request.user,
            subject=subject,
            body=body,
            status='draft' if action == 'draft' else 'sent',
            sentAt=None if action == 'draft' else timezone.now(),
        )

        MessageRecipient.objects.create(
            message=msg,
            user=recipient,
        )

        Action.objects.create(
            user=request.user,
            action='create',
            entityType='Message',
            entityId=msg.messageId,
            actionDescr='Saved draft message.' if action == 'draft' else 'Sent message.',
        )

    if action == 'draft':
        dj_messages.success(request, 'Draft saved.')
        return _messages_redirect('drafts')

    dj_messages.success(request, 'Message sent.')
    return _messages_redirect('sent')


@login_required
@require_POST
def message_star(request, message_id):
    starred_ids = set(request.session.get('starred_messages', []))
    message_id_str = str(message_id)

    if message_id_str in starred_ids:
        starred_ids.remove(message_id_str)
    else:
        starred_ids.add(message_id_str)

    request.session['starred_messages'] = list(starred_ids)
    request.session.modified = True

    folder = request.GET.get('folder', 'inbox')
    return _messages_redirect(folder)


@login_required
@require_POST
def message_send_draft(request, message_id):
    msg = get_object_or_404(
        Message,
        messageId=message_id,
        user=request.user,
        status='draft',
    )

    with transaction.atomic():
        msg.status = 'sent'
        msg.sentAt = timezone.now()
        msg.save(update_fields=['status', 'sentAt'])

        Action.objects.create(
            user=request.user,
            action='update',
            entityType='Message',
            entityId=msg.messageId,
            fieldChanged='status',
            oldValue='draft',
            newValue='sent',
            actionDescr='Sent draft message.',
        )

    dj_messages.success(request, 'Draft sent.')
    return _messages_redirect('sent')


@login_required
@require_POST
def message_mark_read(request, message_id):
    MessageRecipient.objects.filter(
        message_id=message_id,
        user=request.user,
    ).update(isRead=True)

    return JsonResponse({'ok': True})

@login_required
def reports(request):
    return _coming_soon(request, 'reports', 'Reports')
