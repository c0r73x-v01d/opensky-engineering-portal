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

from .forms import RegisterForm
from .models import Action, MeetingInvitation, Message, MessageRecipient, User
from .services.schedule import assemble_for_user


# ════════════════════════════════════════════════════════════════════
# === AUTH ===
# ════════════════════════════════════════════════════════════════════
def register_view(request):
    if request.user.is_authenticated:
        return redirect('home')

    form = RegisterForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        user = form.save()
        login(request, user)
        Action.objects.create(
            user=user, action='create', entityType='Users',
            entityId=user.pk, actionDescr='Self-registered.',
        )
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
    return redirect('schedule')


def _coming_soon(request, active_page, title):
    return render(request, 'coming_soon.html', {
        'active_page': active_page,
        'page_title': title,
    })


@login_required
def schedule(request):
    ctx = assemble_for_user(request.user)
    ctx['active_page'] = 'schedule'
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


def _prepare_messages_for_template(messages, current_user, starred_ids):
    """
    The database model uses coursework field names:
    messageId, user, sentAt, createdAt, recipients.

    The template expects easier names:
    id, sender, recipient, sent_at, created_at, is_read, starred.
    This helper safely adds those display attributes without changing the database.
    """
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

    messages = _prepare_messages_for_template(selected_qs, request.user, starred_ids)

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
def message_mark_read(request, message_id):
    MessageRecipient.objects.filter(
        message_id=message_id,
        user=request.user,
    ).update(isRead=True)

    return JsonResponse({'ok': True})


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
def reports(request):
    return _coming_soon(request, 'reports', 'Reports')