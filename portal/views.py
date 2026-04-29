"""
OpenSky Engineering Portal views.
"""
import datetime
import functools
import json

from django.contrib import messages as dj_messages
from django.contrib.auth import login, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView
from django.db import transaction
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from .context_processors import _max_dob_today
from .forms import MeetingForm, RegisterForm
from .models import (
    Action,
    Department,
    DepartmentLeader,
    Employee,
    Meeting,
    MeetingInvitation,
    Message,
    MessageAttachment,
    MessageRecipient,
    Notification,
    NotificationRecipient,
    Project,
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
class SkyLoginView(LoginView):
    """
    Login view that supports two flows from the same form:
    a regular user login (default) and an explicit "Admin Login" flow
    activated by the toggle in login.html, which sends `is_admin_login=true`
    as a hidden field.

    When admin login is requested:
      - the authenticated user must have is_staff=True, otherwise the
        login is rejected (form-level error, no session created);
      - after a successful auth the user is redirected to /admin/
        instead of the default LOGIN_REDIRECT_URL.

    Regular logins keep the standard Django behaviour: redirect to ?next=
    if present, otherwise LOGIN_REDIRECT_URL ('/').
    """
    template_name = 'login.html'
    redirect_authenticated_user = True

    def _is_admin_request(self):
        return (self.request.POST.get('is_admin_login') or '').strip().lower() == 'true'

    def form_valid(self, form):
        # form.get_user() is the authenticated User instance — auth has
        # already happened by this point, but no session has been created
        # yet, so refusing now leaves the user logged out.
        if self._is_admin_request() and not form.get_user().is_staff:
            form.add_error(None, 'This account does not have admin privileges.')
            return self.form_invalid(form)
        return super().form_valid(form)

    def get_success_url(self):
        if self._is_admin_request():
            return '/admin/'
        return super().get_success_url()


def team_member_required(active_page=''):
    """
    Gate a view behind 'user has been assigned to a team'.

    Self-registered users start out with an Employee row whose teamId is
    NULL — they're authenticated but not yet placed in an engineering
    team. Org-wide pages (Teams, Organisation, Reports) shouldn't expose
    sensitive structural data to people in that state. This decorator
    short-circuits to a friendly empty-state page rendered server-side
    (no redirect, so the user stays on the URL they tried).

    Staff (is_staff=True) always pass — admins legitimately need access
    even though they typically don't have an Employee row themselves.

    Use as @team_member_required('teams') — active_page is forwarded to
    the empty-state template so the navbar still highlights the section
    the user tried to reach.
    """
    def _decorator(view_func):
        @functools.wraps(view_func)
        @login_required
        def _wrapped(request, *args, **kwargs):
            user = request.user
            if user.is_staff:
                return view_func(request, *args, **kwargs)
            emp = Employee.objects.filter(user=user).first()
            if emp and emp.teamId_id is not None:
                return view_func(request, *args, **kwargs)
            return render(request, 'no_team.html', {
                'active_page': active_page,
            })
        return _wrapped
    return _decorator


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
        'dob_max_date': _max_dob_today(),
    })


# ════════════════════════════════════════════════════════════════════
# === PAGES ===
# ════════════════════════════════════════════════════════════════════
# ════════════════════════════════════════════════════════════════════
# === HOME ===
# ════════════════════════════════════════════════════════════════════
#
# The home dashboard pulls data from many slices (the user's team, recent
# meetings, messages, audit actions, dependencies). The serialisers below
# flatten every domain object into the camelCase->snake_case shape the
# template expects, so the template stays free of attribute gymnastics.
#
# Avatar palette: each user gets a stable bg/fg pair derived from their
# username, so the same person renders the same colour anywhere on the
# dashboard (member stack, message rows, manager card).
# ════════════════════════════════════════════════════════════════════

# Eight-stop palette indexed by username hash. Matches the design tokens.
_AVATAR_PALETTE = [
    ('rgba(0, 15, 245, .08)', '#0010f5'),    # primary
    ('rgba(0, 126, 19, .08)', '#007e13'),    # positive
    ('rgba(102, 38, 161, .08)', '#6626a1'),  # entertainment
    ('rgba(241, 90, 34, .08)', '#f15a22'),   # attention
    ('rgba(0, 174, 191, .08)', '#00aebf'),   # cyan
    ('rgba(214, 0, 122, .08)', '#d6007a'),   # magenta
    ('rgba(244, 154, 0, .08)', '#f49a00'),   # amber
    ('rgba(0, 96, 134, .08)', '#006086'),    # deep blue
]

# Status presentation maps. Three-tone scheme matches Teams page.
_STATUS_COLOUR = {
    'active': '#007e13',
    'restructuring': '#f15a22',
    'disbanded': '#9aa0a6',
}
_STATUS_LABEL = {
    'active': 'Active',
    'restructuring': 'Restructuring',
    'disbanded': 'Disbanded',
}

# Type-name -> brand colour. Used for the team type badge in the hero card.
_TYPE_COLOUR = {
    'Platform': '#0010f5',
    'Product': '#6626a1',
    'Infrastructure': '#f15a22',
    'Data': '#0a7cff',
    'Security': '#007e13',
    'Engineering': '#0010f5',
    'Design': '#6626a1',
    'Operations': '#f15a22',
}

# Conferencing platform -> coloured side-bar in the meetings widget.
_PLATFORM_COLOUR = {
    'teams': '#6264a7',
    'zoom': '#2d8cff',
    'meet': '#34a853',
    'in-person': '#5f6368',
}

# Org-wide activity event presentation. Each event kind maps to (icon, colour).
_ORG_EVENT_PRESENTATION = {
    'team_status':     ('AlertTri', '#f15a22'),
    'team_created':    ('Plus',     '#007e13'),
    'team_disbanded':  ('Trash',    '#9aa0a6'),
    'employee_joined': ('User',     '#6626a1'),
    'manager_assigned':('Star',     '#0010f5'),
    'leader_assigned': ('Award',    '#0010f5'),
    'dept_created':    ('Building', '#007e13'),
}

_DEFAULT_WIDGET_SIZES = {
    'depAlerts': 'S',
    'meetings':  'M',
    'messages':  'L',
    'activity':  'M',
    'repos':     'S',
}


def _avatar_palette_for(username):
    """Stable per-user (bg, fg) tuple — same username always same colours."""
    idx = sum(ord(c) for c in (username or '?')) % len(_AVATAR_PALETTE)
    return _AVATAR_PALETTE[idx]


def _initials_for(first, last, fallback):
    f = (first or '').strip()
    l = (last or '').strip()
    if f and l:
        return (f[0] + l[0]).upper()
    if f:
        return f[:2].upper()
    return (fallback or '??')[:2].upper()


def _greeting(now=None):
    """'Good morning' / 'Good afternoon' / 'Good evening' by local time."""
    now = now or timezone.localtime()
    h = now.hour
    if h < 12:
        return 'Good morning'
    if h < 18:
        return 'Good afternoon'
    return 'Good evening'


def _serialize_user_for_home(user, position):
    """User context expected by home.html — flattens model + Employee.position."""
    bg, fg = _avatar_palette_for(user.username)
    return {
        'username':      user.username,
        'f_name':        user.first_name,
        'l_name':        user.last_name,
        'email':         user.email,
        'about_me':      user.about_me or '',
        'date_of_birth': user.dob,
        'position':      position or 'Engineer',
        'avatar_url':    user.avatar.url if user.avatar else '',
        'avatar_bg':     bg,
        'avatar_color':  fg,
        'initials':      _initials_for(user.first_name, user.last_name, user.username),
    }


def _serialize_member_for_home(emp, manager_emp_ids):
    """One row in the team-members avatar stack OR the My Team panel."""
    u = emp.user
    bg, fg = _avatar_palette_for(u.username)
    return {
        'f_name':       u.first_name,
        'l_name':       u.last_name,
        'email':        u.email,
        'position':     emp.position or 'Engineer',
        'is_manager':   emp.empId in manager_emp_ids,
        'avatar_bg':    bg,
        'avatar_color': fg,
        'avatar_url':   u.avatar.url if u.avatar else '',
    }


def _serialize_team_for_home(team):
    return {
        'team_name':        team.teamName,
        'descrip':          team.descrip or '',
        'focus':            team.focusArea or 'Not specified',
        'agile_practice':   team.agilePractice or 'Not specified',
        'concurrent_projs': team.concurrentProjs or 0,
    }


def _format_time_ago(when, now):
    """'2m ago' / '3h ago' / '5d ago' / 'just now'."""
    if when is None:
        return ''
    delta = now - when
    secs = delta.total_seconds()
    if secs < 60:
        return 'just now'
    if secs < 3600:
        return f'{int(secs // 60)}m ago'
    if secs < 86400:
        return f'{int(secs // 3600)}h ago'
    return f'{int(secs // 86400)}d ago'


def _format_meeting_for_widget(meeting, now):
    """One meeting row: when, duration, conferencing platform, colour bar."""
    started = meeting.startedAt
    is_today = started.date() == now.date()
    duration_minutes = int((meeting.endedAt - started).total_seconds() // 60) if meeting.endedAt else 0
    duration = f'{duration_minutes}min' if duration_minutes else '—'
    platform = (meeting.platform or 'in-person').lower()
    return {
        'title':           (meeting.message or 'Untitled').splitlines()[0],
        'duration':        duration,
        'platform':        platform.title(),
        'platform_color':  _PLATFORM_COLOUR.get(platform, '#5f6368'),
        'time_display':    started.strftime('%H:%M'),
        'day_short':       started.strftime('%a'),
        'is_today':        is_today,
    }


def _build_org_activity(now, limit=20):
    """
    Synthesise an org-wide activity feed from current state of the
    organisation. Pulls seven event kinds and merges them into a single
    list sorted by timestamp descending, then trims to `limit`.

    This is a *snapshot* feed, not a true audit log: removals (e.g. a
    manager being replaced) are invisible because the schema doesn't
    soft-delete those rows. Future work: hook Django signals to write
    Action records on save/delete and read from there instead.
    """
    events = []

    # 1. Team status changes (only non-active teams, timestamped at updatedAt).
    for t in Team.objects.exclude(teamStatus='active').only(
        'teamId', 'teamName', 'teamStatus', 'updatedAt',
    ):
        label = _STATUS_LABEL.get(t.teamStatus, t.teamStatus)
        events.append({
            'kind':  'team_status',
            'when':  t.updatedAt,
            'text':  f'{t.teamName} is now {label}',
            'actor': 'Org',
        })

    # 2. New teams.
    for t in Team.objects.only('teamName', 'createdAt'):
        events.append({
            'kind':  'team_created',
            'when':  t.createdAt,
            'text':  f'New team created: {t.teamName}',
            'actor': 'Org',
        })

    # 3. Disbanded teams (when disbandedAt set).
    for t in Team.objects.exclude(disbandedAt__isnull=True).only(
        'teamName', 'disbandedAt',
    ):
        events.append({
            'kind':  'team_disbanded',
            'when':  t.disbandedAt,
            'text':  f'Team disbanded: {t.teamName}',
            'actor': 'Org',
        })

    # 4. New employees.
    for e in Employee.objects.select_related('user', 'teamId').only(
        'joinedAt', 'position', 'teamId__teamName',
        'user__first_name', 'user__last_name', 'user__username',
    ):
        full = f'{e.user.first_name} {e.user.last_name}'.strip() or e.user.username
        team_part = f' to {e.teamId.teamName}' if e.teamId else ''
        events.append({
            'kind':  'employee_joined',
            'when':  e.joinedAt,
            'text':  f'{full} joined as {e.position or "Engineer"}{team_part}',
            'actor': full,
        })

    # 5. Team manager assignments.
    for tm in TeamManager.objects.select_related('emp__user', 'teamId').only(
        'assignedAt', 'teamId__teamName',
        'emp__user__first_name', 'emp__user__last_name', 'emp__user__username',
    ):
        u = tm.emp.user
        full = f'{u.first_name} {u.last_name}'.strip() or u.username
        events.append({
            'kind':  'manager_assigned',
            'when':  tm.assignedAt,
            'text':  f'{full} assigned as manager of {tm.teamId.teamName}',
            'actor': full,
        })

    # 6. Department leader assignments.
    for dl in DepartmentLeader.objects.select_related('emp__user', 'department').only(
        'assignedAt', 'department__departName',
        'emp__user__first_name', 'emp__user__last_name', 'emp__user__username',
    ):
        u = dl.emp.user
        full = f'{u.first_name} {u.last_name}'.strip() or u.username
        events.append({
            'kind':  'leader_assigned',
            'when':  dl.assignedAt,
            'text':  f'{full} now leads {dl.department.departName}',
            'actor': full,
        })

    # 7. New departments.
    for d in Department.objects.only('departName', 'createdAt'):
        events.append({
            'kind':  'dept_created',
            'when':  d.createdAt,
            'text':  f'New department: {d.departName}',
            'actor': 'Org',
        })

    # Sort newest-first and trim. Drop events with no timestamp defensively.
    events = [e for e in events if e['when'] is not None]
    events.sort(key=lambda e: e['when'], reverse=True)

    out = []
    for ev in events[:limit]:
        icon, colour = _ORG_EVENT_PRESENTATION.get(
            ev['kind'], ('Activity', '#5f6368')
        )
        out.append({
            'text':      ev['text'],
            'actor':     ev['actor'],
            'time':      _format_time_ago(ev['when'], now),
            'icon_name': icon,
            'color':     colour,
        })
    return out


@login_required
def home(request):
    user = request.user
    now = timezone.localtime()

    # Resolve the user's Employee row + team. The Employee row may not
    # exist for self-registered users who haven't been assigned yet.
    emp = (
        Employee.objects
        .select_related('teamId__department', 'teamId__type')
        .filter(user=user)
        .first()
    )
    team = emp.teamId if emp else None
    department = team.department if team else None

    user_ctx = _serialize_user_for_home(user, emp.position if emp else None)

    # Team-related context — every block below assumes a team exists, so
    # we early-return a 'no team' rendering if the user has no Employee
    # row yet (typical for fresh self-registrations).
    if not team:
        return render(request, 'home.html', {
            'active_page':           'home',
            'greeting':              _greeting(now),
            'home_user':             user_ctx,
            'team':                  None,
            'department':            None,
            'team_member_count':     0,
            'team_members_visible':  [],
            'team_members_extra':    0,
            'team_type_name':        '',
            'team_type_color':       '#0010f5',
            'team_status_label':     '',
            'team_status_color':     '#9aa0a6',
            'manager':               None,
            'repo_count':            0,
            'dep_count':             0,
            'dep_alerts':            [],
            'upcoming_meetings':     [],
            'recent_messages':       [],
            'recent_activity':       _build_org_activity(now),
            'repos':                 [],
            'widget_sizes':          request.session.get('widget_sizes', _DEFAULT_WIDGET_SIZES),
        })

    # --- Members + manager ---
    managers = list(team.managers.select_related('emp__user').all())
    manager_emp_ids = {m.emp_id for m in managers}
    members_qs = list(team.employees.select_related('user').all())
    members = [_serialize_member_for_home(m, manager_emp_ids) for m in members_qs]

    # Show first 5 in the avatar stack on the hero card, with a +N pill
    # for the overflow.
    members_visible = members[:5]
    members_extra = max(0, len(members) - len(members_visible))

    manager_serialised = None
    if managers:
        m_emp = managers[0].emp
        bg, fg = _avatar_palette_for(m_emp.user.username)
        manager_serialised = {
            'f_name':       m_emp.user.first_name,
            'l_name':       m_emp.user.last_name,
            'email':        m_emp.user.email,
            'position':     m_emp.position or 'Engineering Manager',
            'avatar_bg':    bg,
            'avatar_color': fg,
            'avatar_url':   m_emp.user.avatar.url if m_emp.user.avatar else '',
        }

    # --- Repos for the team ---
    repos_qs = list(Project.objects.filter(team=team).order_by('-isMainProj', 'repoName'))
    repos_for_template = [
        {
            'repo_name':    p.repoName,
            'repo_url':     p.repoUrl or '',
            'is_main_proj': p.isMainProj,
        }
        for p in repos_qs
    ]

    # --- Dependency alerts: upstream teams whose status != 'active'.
    # Semantically: 'something the team depends on is unhealthy'.
    dep_links = list(
        TeamDependency.objects
        .filter(downstream=team)
        .select_related('upstream')
    )
    dep_count_total = TeamDependency.objects.filter(
        Q(upstream=team) | Q(downstream=team)
    ).count()
    dep_alerts = []
    for link in dep_links:
        if link.upstream.teamStatus and link.upstream.teamStatus != 'active':
            dep_alerts.append({
                'text':      f'{link.upstream.teamName} is {_STATUS_LABEL.get(link.upstream.teamStatus, link.upstream.teamStatus)}',
                'icon_name': 'AlertTri',
                'color':     _STATUS_COLOUR.get(link.upstream.teamStatus, '#f15a22'),
            })

    # --- Upcoming meetings invited to the user (max 5).
    upcoming_qs = (
        MeetingInvitation.objects
        .filter(user=user, meet__startedAt__gte=now,
                status__in=('pending', 'accepted'))
        .select_related('meet')
        .order_by('meet__startedAt')[:5]
    )
    upcoming_meetings = [_format_meeting_for_widget(inv.meet, now) for inv in upcoming_qs]

    # --- Recent messages (inbox only, unread first, then by date).
    msg_recip_qs = (
        MessageRecipient.objects
        .filter(user=user, recipMsgDeleted=False, message__status='sent')
        .select_related('message__user')
        .order_by('isRead', '-message__sentAt', '-message__createdAt')[:5]
    )
    recent_messages = []
    for mr in msg_recip_qs:
        m = mr.message
        sender = m.user
        bg, fg = _avatar_palette_for(sender.username)
        sender_full = f'{sender.first_name} {sender.last_name}'.strip() or sender.username
        recent_messages.append({
            'from_name':         sender_full,
            'from_initials':     _initials_for(sender.first_name, sender.last_name, sender.username),
            'from_avatar_bg':    bg,
            'from_avatar_color': fg,
            'from_avatar_url':   sender.avatar.url if sender.avatar else '',
            'time':              _format_time_ago(m.sentAt or m.createdAt, now),
            'subject':           m.subject or '(no subject)',
            'preview':           (m.body or '')[:120],
            'unread':            not mr.isRead,
        })

    # --- Org-wide activity feed: synthesised from current state of orga
    # objects (Department, Team, Employee, TeamManager, DepartmentLeader).
    # See `_build_org_activity` for the full event taxonomy.
    recent_activity = _build_org_activity(now)

    # --- Department/type badges ---
    type_name = team.type.typeName if team.type else ''
    return render(request, 'home.html', {
        'active_page':          'home',
        'greeting':             _greeting(now),
        'home_user':            user_ctx,
        'team':                 _serialize_team_for_home(team),
        'department':           {'depart_name': department.departName} if department else None,
        'team_member_count':    len(members),
        'team_members_visible': members_visible,
        'team_members_extra':   members_extra,
        'team_type_name':       type_name,
        'team_type_color':      _TYPE_COLOUR.get(type_name, '#0010f5'),
        'team_status_label':    _STATUS_LABEL.get(team.teamStatus, ''),
        'team_status_color':    _STATUS_COLOUR.get(team.teamStatus, '#9aa0a6'),
        'manager':              manager_serialised,
        'repo_count':           len(repos_for_template),
        'dep_count':            dep_count_total,
        'dep_alerts':           dep_alerts,
        'upcoming_meetings':    upcoming_meetings,
        'recent_messages':      recent_messages,
        'recent_activity':      recent_activity,
        'repos':                repos_for_template,
        'widget_sizes':         request.session.get('widget_sizes', _DEFAULT_WIDGET_SIZES),
    })


# ════════════════════════════════════════════════════════════════════
# === PROFILE ===
# ════════════════════════════════════════════════════════════════════
#
# Single endpoint for the profile modal — handles three forms posted to
# the same URL, distinguished by `form_type`:
#   - personal (default): about_me text + optional avatar upload
#   - security: password change with current_password verification
#   - widget_sizes (AJAX): persists per-session widget layout
# ════════════════════════════════════════════════════════════════════

_ABOUT_ME_MAX_LEN = 1000
_MIN_DOB_AGE_YEARS = 18


@login_required
@require_POST
def profile_update(request):
    user = request.user

    # Widget sizes — sent as JSON from home.js (drag/resize). Detected by
    # the Content-Type header before we look at request.POST so the JSON
    # body isn't accidentally treated as a form.
    if request.content_type == 'application/json':
        try:
            sizes = json.loads(request.body or b'{}')
        except json.JSONDecodeError:
            return JsonResponse({'ok': False, 'error': 'Invalid JSON.'}, status=400)
        cleaned = {}
        for k, v in sizes.items():
            if k in _DEFAULT_WIDGET_SIZES and v in ('S', 'M', 'L'):
                cleaned[k] = v
        request.session['widget_sizes'] = cleaned or _DEFAULT_WIDGET_SIZES
        request.session.modified = True
        return JsonResponse({'ok': True, 'widget_sizes': request.session['widget_sizes']})

    form_type = (request.POST.get('form_type') or 'personal').strip().lower()

    # ---- Security: change password ----
    if form_type == 'security':
        current = request.POST.get('current_password') or ''
        new_pw = request.POST.get('new_password') or ''
        confirm = request.POST.get('confirm_password') or ''

        if not user.check_password(current):
            dj_messages.error(request, 'Current password is incorrect.')
            return redirect('home')
        if len(new_pw) < 8:
            dj_messages.error(request, 'New password must be at least 8 characters.')
            return redirect('home')
        if new_pw != confirm:
            dj_messages.error(request, 'New password and confirmation do not match.')
            return redirect('home')

        with transaction.atomic():
            user.set_password(new_pw)
            user.save(update_fields=['password'])
            Action.objects.create(
                user=user,
                action='update',
                entityType='Users',
                entityId=user.pk,
                fieldChanged='password',
                actionDescr='Changed account password.',
            )
        # Critical: keep the session valid after the password changes.
        update_session_auth_hash(request, user)
        dj_messages.success(request, 'Password updated.')
        return redirect('home')

    # ---- Personal: about_me + optional avatar + DOB ----
    about_me = (request.POST.get('about_me') or '').strip()
    if len(about_me) > _ABOUT_ME_MAX_LEN:
        dj_messages.error(
            request,
            f'About Me cannot exceed {_ABOUT_ME_MAX_LEN} characters.',
        )
        return redirect('home')

    # DOB is required and must place the user at or above the minimum age.
    # We only run the validator if the field is actually present in the
    # POST — older HTML caches without the new input shouldn't wipe an
    # existing value. The field is required in the form, so an empty
    # string from a freshly-rendered modal is treated as a validation
    # failure rather than a clear-the-field action.
    new_dob = None
    dob_changed = False
    raw_dob = request.POST.get('dob')
    if raw_dob is not None:
        raw_dob = raw_dob.strip()
        if not raw_dob:
            dj_messages.error(request, 'Date of birth is required.')
            return redirect('home')
        try:
            new_dob = datetime.date.fromisoformat(raw_dob)
        except ValueError:
            dj_messages.error(request, 'Date of birth is not a valid date.')
            return redirect('home')

        today = timezone.localdate()
        if new_dob > today:
            dj_messages.error(request, 'Date of birth cannot be in the future.')
            return redirect('home')

        # Compute age accounting for whether the birthday has occurred yet
        # this year. (today.year - dob.year) over-counts before the birthday.
        age = today.year - new_dob.year - (
            (today.month, today.day) < (new_dob.month, new_dob.day)
        )
        if age < _MIN_DOB_AGE_YEARS:
            dj_messages.error(
                request,
                f'You must be at least {_MIN_DOB_AGE_YEARS} years old.',
            )
            return redirect('home')

        dob_changed = (user.dob != new_dob)

    avatar_file = request.FILES.get('avatar')
    changed_fields = []

    with transaction.atomic():
        if about_me != (user.about_me or ''):
            user.about_me = about_me
            changed_fields.append('about_me')

        if dob_changed:
            user.dob = new_dob
            changed_fields.append('dob')

        if avatar_file:
            # Pillow opens lazily on .save(); ImageField will reject non-images.
            user.avatar = avatar_file
            changed_fields.append('avatar')

        if changed_fields:
            user.save(update_fields=changed_fields)
            for field in changed_fields:
                Action.objects.create(
                    user=user,
                    action='update',
                    entityType='Users',
                    entityId=user.pk,
                    fieldChanged=field,
                    actionDescr=f'Updated profile field: {field}.',
                )

    if changed_fields:
        dj_messages.success(request, 'Profile saved.')
    return redirect('home')


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

    # Prefill the meeting modal when the user arrives via "Schedule Meeting"
    # from a team detail panel: ?compose=team&team_id=N.
    # If the user manages that team, the meeting modal opens in 'team' mode
    # with the host_team selector preset. Otherwise it opens in 'personal'
    # mode with the team's members preloaded as invitees.
    prefill = {'open': False}
    if (request.GET.get('compose') or '').strip().lower() == 'team':
        try:
            req_team_id = int(request.GET.get('team_id') or 0)
        except ValueError:
            req_team_id = 0
        if req_team_id:
            prefill['open'] = True
            prefill['team_id'] = req_team_id
            if req_team_id in managed_team_ids:
                prefill['mode'] = 'team'
            else:
                prefill['mode'] = 'personal'
                # Build the personal-invitees list excluding the current user.
                invitees = []
                personal_qs = (
                    Employee.objects
                    .filter(teamId_id=req_team_id)
                    .exclude(user=user)
                    .select_related('user')
                )
                for emp in personal_qs:
                    u = emp.user
                    invitees.append({
                        'user_id': u.pk,
                        'name': f'{u.first_name} {u.last_name}'.strip() or u.username,
                    })
                prefill['invitees'] = invitees
    ctx['meeting_prefill_json'] = json.dumps(prefill)
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

    members = []
    for e in t.employees.all():
        full_name = f'{e.user.first_name} {e.user.last_name}'.strip()
        display_name = full_name or e.user.username
        initials = ''.join(p[0] for p in full_name.split()[:2]).upper() \
            or e.user.username[:2].upper()
        members.append({
            'name': display_name,
            'position': e.position or 'Engineer',
            'is_manager': e.empId in manager_emp_ids,
            'initials': initials,
            'email': e.user.email or '',
            'username': e.user.username,
            'avatar_url': e.user.avatar.url if e.user.avatar else '',
        })
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
        'status_display': t.teamStatus.replace('_', ' ').title() if t.teamStatus else '',
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


@team_member_required('teams')
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


@team_member_required('organisation')
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

    # Prefill recipients for the compose modal — set when the user arrives
    # via "Email Team" from a team detail panel: ?compose=team&team_id=N.
    # The frontend opens the compose overlay automatically and pre-populates
    # the recipient chips. The current user is excluded — you don't email
    # yourself.
    prefill_recipients = []
    prefill_compose_open = False
    compose_mode = (request.GET.get('compose') or '').strip().lower()
    if compose_mode == 'team':
        try:
            team_id = int(request.GET.get('team_id') or 0)
        except ValueError:
            team_id = 0
        if team_id:
            members_qs = (
                Employee.objects
                .filter(teamId_id=team_id)
                .exclude(user=request.user)
                .select_related('user')
            )
            for emp in members_qs:
                u = emp.user
                full = f'{u.first_name} {u.last_name}'.strip()
                label = full or u.username
                # Compose dropdown labels follow the existing convention:
                # "First Last (username)" or just "username" if no real name.
                display = f'{label} ({u.username})' if full else u.username
                prefill_recipients.append({'id': u.pk, 'name': display})
            prefill_compose_open = True

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
        'prefill_recipients': prefill_recipients,
        'prefill_compose_open': prefill_compose_open,
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
@require_POST
def message_delete(request, message_id):
    folder = request.GET.get('folder', 'inbox')

    if folder == 'sent' or folder == 'drafts':
        msg = get_object_or_404(Message, messageId=message_id, user=request.user)
        msg.senderMsgDeleted = True
        msg.save(update_fields=['senderMsgDeleted'])

        Action.objects.create(
            user=request.user,
            action='delete',
            entityType='Message',
            entityId=msg.messageId,
            actionDescr=f'Deleted message from {folder}.',
        )

    else:
        recipient = get_object_or_404(
            MessageRecipient,
            message_id=message_id,
            user=request.user,
        )
        recipient.recipMsgDeleted = True
        recipient.save(update_fields=['recipMsgDeleted'])

        Action.objects.create(
            user=request.user,
            action='delete',
            entityType='Message',
            entityId=message_id,
            actionDescr='Deleted message from inbox.',
        )

    return _messages_redirect(folder)

@team_member_required('reports')
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


@team_member_required('reports')
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


@team_member_required('reports')
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
