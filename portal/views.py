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

from .forms import RegisterForm
from .models import Action, MeetingInvitation
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


@login_required
def messages_view(request):
    return _coming_soon(request, 'messages', 'Messages')


@login_required
def reports(request):
    return _coming_soon(request, 'reports', 'Reports')
