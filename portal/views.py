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
    Department,
    Employee,
    Meeting,
    MeetingInvitation,
    Message,
    MessageAttachment,
    MessageRecipient,
    Notification,
    NotificationRecipient,
    Skill,
    Team,
    TeamDependency,
    TeamManager,
    TeamType,
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


# ════════════════════════════════════════════════════════════════════
# === TEAMS ===
# ════════════════════════════════════════════════════════════════════
def _serialize_team(t):
    """
    Flatten one Team row into the dict shape the template loop and the
    JSON payload (for JS) both consume.

    Assumes the queryset has been prefetched so every relation accessed
    here is O(1) and triggers no extra queries.
    """
    skills = [a.skill.skillName for a in t.teamskillalloc_set.all()]
    managers = list(t.managers.all())
    manager_emp_ids = {m.emp_id for m in managers}
    manager_names = [str(m.emp.user) for m in managers]

    members = [
        {
            'name': str(e.user),
            'position': e.position or 'Engineer',
            'is_manager': e.empId in manager_emp_ids,
        }
        for e in t.employees.all()
    ]
    repos = [
        {
            'name': p.repoName,
            'url': p.repoUrl or '',
            'is_main': p.isMainProj,
        }
        for p in t.projects.all()
    ]
    upstream = [
        {
            'id': d.upstream.teamId,
            'name': d.upstream.teamName,
            'type': d.upstream.type.typeName if d.upstream.type else '',
            'dep_type': d.dependencyType or '',
        }
        for d in t.upstream_links.all()
    ]
    downstream = [
        {
            'id': d.downstream.teamId,
            'name': d.downstream.teamName,
            'type': d.downstream.type.typeName if d.downstream.type else '',
            'dep_type': d.dependencyType or '',
        }
        for d in t.downstream_links.all()
    ]

    return {
        'id': t.teamId,
        'team_name': t.teamName,
        'department_id': t.department_id,
        'department_name': t.department.departName,
        'type_id': t.type_id or 0,
        'type_name': t.type.typeName if t.type else '',
        'status': t.teamStatus,
        'manager_name': manager_names[0] if manager_names else 'Unassigned',
        'manager_names': manager_names,
        'description': t.descrip or '',
        'responsibilities': t.responsib or '',
        'focus': t.focusArea or '',
        'workstream': t.workstreamMf or '',
        'agile_practice': t.agilePractice or '',
        'concurrent_projs': t.concurrentProjs,
        'skills': skills,
        'skills_text': ' '.join(skills),
        'extra_skills_count': max(0, len(skills) - 3),
        'members': members,
        'member_count': len(members),
        'repos': repos,
        'repo_count': len(repos),
        'upstream': upstream,
        'downstream': downstream,
        'dep_count': len(upstream) + len(downstream),
        'jira_project': t.jiraProjName or '',
        'jira_link': t.jiraBoardLink or '',
        'standup_time': t.standupTime.strftime('%H:%M') if t.standupTime else '',
        'standup_link': t.standupLink or '',
        'comm_channel': t.commChann or '',
        'team_wiki': t.teamWiki or '',
        'created_at': t.createdAt.strftime('%d %b %Y') if t.createdAt else '',
        'updated_at': t.updatedAt.strftime('%d %b %Y') if t.updatedAt else '',
        'disbanded_at': t.disbandedAt.strftime('%d %b %Y') if t.disbandedAt else '',
    }


@login_required
def teams(request):
    teams_qs = (
        Team.objects
        .select_related('department', 'type')
        .prefetch_related(
            'employees__user',
            'managers__emp__user',
            'teamskillalloc_set__skill',
            'projects',
            'upstream_links__upstream__type',
            'downstream_links__downstream__type',
        )
        .order_by('teamName')
    )
    teams_data = [_serialize_team(t) for t in teams_qs]

    departments = [
        {'id': d.departmentId, 'name': d.departName}
        for d in Department.objects.order_by('departName')
    ]
    team_types = [
        {'id': tt.typeId, 'name': tt.typeName}
        for tt in TeamType.objects.order_by('typeName')
    ]

    return render(request, 'teams.html', {
        'active_page': 'teams',
        'teams': teams_data,
        'total_teams': len(teams_data),
        'active_teams': sum(1 for t in teams_data if t['status'] == 'active'),
        'total_engineers': Employee.objects.filter(teamId__isnull=False).count(),
        'total_skills': Skill.objects.count(),
        'departments': departments,
        'team_types': team_types,
    })


@login_required
def organisation(request):
    type_colours = {
        "Platform": "#0010f5",
        "Product": "#6626a1",
        "Infrastructure": "#f15a22",
        "Data": "#0a7cff",
        "Security": "#007e13",
        "Engineering": "#0010f5",
        "Design": "#6626a1",
        "Operations": "#f15a22",
    }

    teams_qs = (
        Team.objects
        .select_related("department", "type")
        .prefetch_related("employees__user", "managers__emp__user", "projects")
        .order_by("department__departName", "teamName")
    )

    all_teams = []

    for team in teams_qs:
        manager = team.managers.first()
        main_project = team.projects.filter(isMainProj=True).first()
        projects = list(team.projects.all())
        type_name = team.type.typeName if team.type else "Unassigned"

        members = []
        for emp in team.employees.all():
            full_name = f"{emp.user.first_name} {emp.user.last_name}".strip()
            members.append({
                "name": full_name or emp.user.username,
                "username": emp.user.username,
                "email": emp.user.email,
                "position": emp.position or "Engineer",
                "initials": "".join(part[0] for part in full_name.split()[:2]).upper()
                            or emp.user.username[:2].upper(),
            })

        all_teams.append({
            "team_id": team.teamId,
            "name": team.teamName,
            "department_id": team.department.departmentId,
            "department_name": team.department.departName,
            "type_name": type_name,
            "type_colour": type_colours.get(type_name, "#0010f5"),
            "description": team.descrip or "No team description available.",
            "responsibilities": team.responsib or "Responsibilities not yet recorded.",
            "focus_area": team.focusArea or "Not specified",
            "status": team.teamStatus,
            "status_display": team.teamStatus.replace("_", " ").title(),
            "manager_name": str(manager.emp.user) if manager else "No manager assigned",
            "manager_email": manager.emp.user.email if manager else "",
            "member_count": team.employees.count(),
            "members": members,
            "agile_practice": team.agilePractice or "Not specified",
            "contact_channel": team.commChann or "Not specified",
            "team_wiki": team.teamWiki or "",
            "standup_link": team.standupLink or "",
            "jira_board": team.jiraBoardLink or "",
            "repo_count": len(projects),
            "main_repo": main_project.repoName if main_project else "",
            "repositories": [
                {
                    "name": project.repoName,
                    "url": project.repoUrl or "",
                    "is_main": project.isMainProj,
                }
                for project in projects
            ],
        })

    dependencies = []
    for dep in TeamDependency.objects.select_related("upstream", "downstream").all():
        dependencies.append({
            "from": dep.upstream.teamId,
            "to": dep.downstream.teamId,
            "from_name": dep.upstream.teamName,
            "to_name": dep.downstream.teamName,
            "type": dep.dependencyType or "dependency",
        })

    for team in all_teams:
        team["depends_on"] = [dep for dep in dependencies if dep["from"] == team["team_id"]]
        team["depended_on_by"] = [dep for dep in dependencies if dep["to"] == team["team_id"]]

    departments = []
    for dept in Department.objects.all().order_by("departName"):
        dept_teams = [team for team in all_teams if team["department_id"] == dept.departmentId]
        leader_obj = getattr(dept, "leader", None)

        leader = None
        if leader_obj:
            user = leader_obj.emp.user
            full_name = f"{user.first_name} {user.last_name}".strip()
            leader = {
                "full_name": full_name or user.username,
                "email": user.email,
                "position": leader_obj.emp.position or "Department Leader",
                "initials": "".join(part[0] for part in full_name.split()[:2]).upper()
                            or user.username[:2].upper(),
            }

        departments.append({
            "department_id": dept.departmentId,
            "name": dept.departName,
            "specialization": dept.specialization or "No specialisation recorded",
            "leader": leader,
            "teams": dept_teams,
            "engineer_count": sum(team["member_count"] for team in dept_teams),
        })

    team_types = []
    for team_type in TeamType.objects.all().order_by("typeName"):
        type_teams = [team for team in all_teams if team["type_name"] == team_type.typeName]
        team_types.append({
            "name": team_type.typeName,
            "color": type_colours.get(team_type.typeName, "#0010f5"),
            "teams": type_teams,
        })

    stats = {
        "departments": Department.objects.count(),
        "teams": Team.objects.count(),
        "engineers": Employee.objects.count(),
        "dependencies": TeamDependency.objects.count(),
    }

    return render(request, "organisation.html", {
        "active_page": "organisation",
        "stats": stats,
        "departments": departments,
        "team_types": team_types,
        "teams_json": all_teams,
        "deps_json": dependencies,
    })



# ════════════════════════════════════════════════════════════════════
# === MESSAGES ===
# ════════════════════════════════════════════════════════════════════
def _messages_redirect(folder='inbox'):
    return redirect(f"{reverse('messages')}?folder={folder}")


def _prepare_messages_for_template(messages, starred_ids):
    prepared = []

    for msg in messages:
        recipient_links = list(msg.recipients.select_related('user').all())
        recipient_link = recipient_links[0] if recipient_links else None
        attachments = list(msg.attachments.all())

        msg.id = msg.messageId
        msg.sender = msg.user
        msg.recipient = recipient_link.user if recipient_link else None
        msg.recipients_list = [r.user for r in recipient_links]
        msg.recipients_display = ', '.join([r.user.username for r in recipient_links])
        msg.sent_at = msg.sentAt
        msg.created_at = msg.createdAt
        msg.is_read = recipient_link.isRead if recipient_link else True
        msg.starred = str(msg.messageId) in starred_ids
        msg.attachments_list = attachments
        msg.attachments_display = ', '.join([
            a.file.name.split('/')[-1] for a in attachments
        ])

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
    ).select_related('user').prefetch_related(
        'recipients__user',
        'attachments',
    ).order_by('-sentAt', '-createdAt')

    sent_qs = Message.objects.filter(
        user=request.user,
        status='sent',
        senderMsgDeleted=False,
    ).select_related('user').prefetch_related(
        'recipients__user',
        'attachments',
    ).order_by('-sentAt', '-createdAt')

    draft_qs = Message.objects.filter(
        user=request.user,
        status='draft',
        senderMsgDeleted=False,
    ).select_related('user').prefetch_related(
        'recipients__user',
        'attachments',
    ).order_by('-createdAt')

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
        'employees': User.objects.all().order_by('first_name', 'last_name', 'username'),
    }

    return render(request, 'messages.html', context)


@login_required
@require_POST
def message_send(request):
    recipient_ids = request.POST.getlist('to')
    subject = request.POST.get('subject', '').strip()
    body = request.POST.get('body', '').strip()
    action = request.POST.get('action', 'send')
    attachment = request.FILES.get('attachment')

    if not recipient_ids:
        dj_messages.error(request, 'Please choose at least one recipient.')
        return _messages_redirect('inbox')

    recipients = User.objects.filter(pk__in=recipient_ids)

    if not recipients.exists():
        dj_messages.error(request, 'Selected recipients were not found.')
        return _messages_redirect('inbox')

    with transaction.atomic():
        msg = Message.objects.create(
            user=request.user,
            subject=subject,
            body=body,
            status='draft' if action == 'draft' else 'sent',
            sentAt=None if action == 'draft' else timezone.now(),
        )

        for recipient in recipients:
            MessageRecipient.objects.get_or_create(
                message=msg,
                user=recipient,
            )

        if attachment:
            MessageAttachment.objects.create(
                message=msg,
                file=attachment,
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
    teams = (
        Team.objects
        .select_related('department')
        .prefetch_related('managers__emp__user')
        .order_by('teamName')
    )
    departments = Department.objects.order_by('departName')

    dept_id = request.GET.get('department')
    if dept_id:
        teams = teams.filter(department_id=dept_id)

    unmanaged_active = teams.filter(managers__isnull=True).distinct()

    total_teams = teams.count()
    teams_without_managers = unmanaged_active.count()

    context = {
        'active_page': 'reports',
        'teams': teams,
        'departments': departments,
        'selected_department': dept_id,
        'total_teams': total_teams,
        'teams_without_managers': teams_without_managers,
        'unmanaged_active': unmanaged_active,
        'active_teams': total_teams,
        'total_employees': 0,
        'avg_team_size': 0,
        'total_repos': 0,
        'dept_stats': [],
        'status_breakdown': [],
        'type_stats': [],
        'recent_activity': [],
        'audit_log': [],
        'audit_types': [],
        'audit_counts': [],
    }

    return render(request, 'reports.html', context)


@login_required
def export_pdf(request):
    from django.http import HttpResponse
    try:
        from reportlab.pdfgen import canvas
    except ModuleNotFoundError:
        return HttpResponse(
            "PDF export is unavailable because 'reportlab' is not installed. "
            "Please install the project requirements and try again.",
            status=503,
            content_type='text/plain',
        )

    teams = (
        Team.objects
        .select_related('department')
        .prefetch_related('managers__emp__user')
        .order_by('teamName')
    )
    total_teams = teams.count()
    unmanaged = teams.filter(managers__isnull=True).distinct().count()

    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = 'attachment; filename="reports.pdf"'

    p = canvas.Canvas(response)
    p.setFont("Helvetica-Bold", 16)
    p.drawString(100, 800, "OpenSky Reports")

    p.setFont("Helvetica", 12)
    p.drawString(100, 760, f"Total Teams: {total_teams}")
    p.drawString(100, 740, f"Unmanaged Teams: {unmanaged}")

    y = 700
    p.drawString(100, y, "Teams List:")
    y -= 20

    for team in teams:
        team_name = team.teamName
        dept_name = team.department.departName if team.department else ""

        managers = list(team.managers.all())
        manager_name = str(managers[0].emp.user) if managers else "No Manager"

        if y < 80:
            p.showPage()
            p.setFont("Helvetica", 12)
            y = 800

        p.drawString(120, y, f"{team_name} - {dept_name} - {manager_name}")
        y -= 20

    p.showPage()
    p.save()
    return response


@login_required
def export_excel(request):
    from django.http import HttpResponse
    try:
        from openpyxl import Workbook
    except ModuleNotFoundError:
        return HttpResponse(
            "Excel export is unavailable because 'openpyxl' is not installed. "
            "Please install the project requirements and try again.",
            status=503,
            content_type='text/plain',
        )

    teams = (
        Team.objects
        .select_related('department')
        .prefetch_related('managers__emp__user')
        .order_by('teamName')
    )

    wb = Workbook()
    ws = wb.active
    ws.title = "Reports"

    ws.append(["Team Name", "Department", "Manager"])

    for team in teams:
        team_name = team.teamName
        dept_name = team.department.departName if team.department else ""

        managers = list(team.managers.all())
        manager_name = str(managers[0].emp.user) if managers else "Unassigned"

        ws.append([team_name, dept_name, manager_name])

    response = HttpResponse(
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    response["Content-Disposition"] = 'attachment; filename="reports.xlsx"'

    wb.save(response)
    return response
