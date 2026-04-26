"""
Schedule view-model assembly.

Turns Meeting + MeetingInvitation rows into the per-event dicts the schedule
template expects. The dict shape mirrors the data-* attributes on each
.sky-event__open / .sky-month__event-open / .sky-meeting__open / .sky-past__open
trigger so the same Detail panel can populate from any view.
"""

from __future__ import annotations

import datetime
import json
from dataclasses import dataclass

from django.utils import timezone

from portal.models import Meeting, MeetingInvitation


# Live: the schedule view anchors on real today. Pass an explicit `anchor`
# kwarg to assemble_for_user(...) when you need to render a fixed window
# (e.g. tests, demos, or a future "jump to date" UI).
WEEK_ANCHOR = None

DAY_NAMES = ['MON', 'TUE', 'WED', 'THU', 'FRI', 'SAT', 'SUN']
DAY_NAMES_LONG = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday',
                  'Saturday', 'Sunday']
MONTH_NAMES = ['January', 'February', 'March', 'April', 'May', 'June',
               'July', 'August', 'September', 'October', 'November', 'December']

PLATFORM_KEYS = {'slack', 'zoom', 'teams', 'meet', 'office'}


# ── per-event view-model ───────────────────────────────────────────────────

@dataclass
class EventVM:
    meet_id: int
    title: str
    date_long: str          # e.g. "Monday, 20 April 2026"
    time_range: str         # e.g. "10:00 – 11:00 · 1h"
    time_short: str         # e.g. "10:00"
    duration_short: str     # e.g. "1h"
    platform: str           # one of PLATFORM_KEYS
    type: str               # 'team' | 'personal' | 'standup'
    cadence: str            # '' or 'daily' / 'weekly' / etc.
    host: str               # team name (empty for personal without team)
    organizer: str
    organizer_role: str
    agenda: str
    my_status: str          # 'accepted' | 'pending' | 'declined'
    attendees_json: str     # JSON-encoded list of {name, role, status}
    attendees_count: int
    accepted_count: int
    avatars_preview: list   # first 3 attendees: [{initials}]
    avatars_more: int       # remaining count beyond preview, 0 if none
    is_past: bool           # meeting end is before now

    # template-friendly platform pill labels
    @property
    def platform_label(self) -> str:
        return {
            'slack': 'Slack', 'zoom': 'Zoom', 'teams': 'Teams',
            'meet': 'Meet', 'office': 'Office',
        }.get(self.platform, self.platform.title() if self.platform else '')

    @property
    def status_capitalised(self) -> str:
        return self.my_status.capitalize() if self.my_status else ''


def _format_duration(start: datetime.datetime, end: datetime.datetime | None) -> str:
    if not end:
        return ''
    delta = end - start
    minutes = int(delta.total_seconds() // 60)
    if minutes <= 0:
        return ''
    if minutes < 60:
        return f'{minutes}m'
    hours, mins = divmod(minutes, 60)
    if mins == 0:
        return f'{hours}h'
    return f'{hours}h {mins}m'


def _normalise_platform(raw: str | None) -> str:
    if not raw:
        return 'teams'
    key = raw.strip().lower()
    return key if key in PLATFORM_KEYS else 'teams'


_CADENCE_CYCLE = ('weekly', 'bi-weekly', 'monthly', 'quarterly')


def _cadence_for(meeting: Meeting) -> str:
    if meeting.meetingType == 'standup':
        return 'daily'
    if meeting.meetingType == 'personal':
        return ''
    return _CADENCE_CYCLE[meeting.meetId % len(_CADENCE_CYCLE)]


def _organizer_role(meeting: Meeting) -> str:
    if meeting.meetingType == 'personal' and meeting.emp:
        return meeting.emp.position or ''
    if meeting.teamEmp:
        return meeting.teamEmp.emp.position or 'Team Manager'
    return ''


def _host_name(meeting: Meeting) -> str:
    if meeting.teamId:
        return meeting.teamId.teamName
    return ''


def _initials(name: str) -> str:
    parts = [p for p in (name or '').split() if p]
    if not parts:
        return '?'
    if len(parts) == 1:
        return parts[0][:2].upper()
    return (parts[0][0] + parts[-1][0]).upper()


def _attendees_payload(meeting: Meeting, current_user_id: int):
    rows = list(meeting.invitations.select_related('user', 'user__employee').all())
    payload = []
    accepted = 0
    for inv in rows:
        u = inv.user
        full_name = f'{u.first_name} {u.last_name}'.strip() or u.username
        if u.userId == current_user_id:
            full_name = f'{full_name} (You)'
        role = ''
        emp = getattr(u, 'employee', None)
        if emp and emp.position:
            role = emp.position
        payload.append({
            'name': full_name,
            'role': role,
            'status': inv.status,
        })
        if inv.status == 'accepted':
            accepted += 1
    return payload, accepted


def _my_status(meeting: Meeting, current_user_id: int) -> str:
    inv = next(
        (i for i in meeting.invitations.all() if i.user_id == current_user_id),
        None,
    )
    return inv.status if inv else 'accepted'


def serialise_meeting(meeting: Meeting, current_user_id: int,
                      now: datetime.datetime | None = None) -> EventVM:
    start = timezone.localtime(meeting.startedAt)
    end = timezone.localtime(meeting.endedAt) if meeting.endedAt else None
    duration = _format_duration(start, end)

    # "Monday, 20 April 2026"
    date_long = f'{DAY_NAMES_LONG[start.weekday()]}, {start.day} {MONTH_NAMES[start.month - 1]} {start.year}'

    # "10:00 – 11:00 · 1h" (or "10:00 · 1h" if no end)
    if end:
        time_range = f'{start:%H:%M} – {end:%H:%M}'
        if duration:
            time_range += f' · {duration}'
    else:
        time_range = f'{start:%H:%M}'

    organiser_user = meeting.organiser_user
    organizer_full = ''
    if organiser_user:
        organizer_full = f'{organiser_user.first_name} {organiser_user.last_name}'.strip()

    attendees, accepted = _attendees_payload(meeting, current_user_id)

    avatars_preview = [
        {'initials': _initials(a['name'].replace(' (You)', ''))}
        for a in attendees[:3]
    ]
    avatars_more = max(0, len(attendees) - len(avatars_preview))

    now = now or timezone.now()
    is_past = (end and end < now) or (not end and start < now)

    return EventVM(
        meet_id=meeting.meetId,
        title=meeting.message.split('\n', 1)[0] if meeting.message else _fallback_title(meeting),
        date_long=date_long,
        time_range=time_range,
        time_short=f'{start:%H:%M}',
        duration_short=duration,
        platform=_normalise_platform(meeting.platform),
        type=meeting.meetingType,
        cadence=_cadence_for(meeting),
        host=_host_name(meeting),
        organizer=organizer_full,
        organizer_role=_organizer_role(meeting),
        agenda=(meeting.message or '').strip(),
        my_status=_my_status(meeting, current_user_id),
        attendees_json=json.dumps(attendees),
        attendees_count=len(attendees),
        accepted_count=accepted,
        avatars_preview=avatars_preview,
        avatars_more=avatars_more,
        is_past=bool(is_past),
    )


def _fallback_title(meeting: Meeting) -> str:
    if meeting.meetingType == 'standup' and meeting.teamId:
        return f'{meeting.teamId.teamName} Daily Standup'
    if meeting.meetingType == 'team' and meeting.teamId:
        return f'{meeting.teamId.teamName} Sync'
    if meeting.meetingType == 'personal':
        return 'Personal Meeting'
    return 'Meeting'


# ── window queries ─────────────────────────────────────────────────────────

def _user_meetings_between(user, start_date: datetime.date, end_date: datetime.date):
    """Meetings the user is invited to (or organising) in [start_date, end_date]."""
    start_dt = datetime.datetime.combine(start_date, datetime.time.min, tzinfo=timezone.get_current_timezone())
    end_dt = datetime.datetime.combine(end_date, datetime.time.max, tzinfo=timezone.get_current_timezone())

    invited_ids = MeetingInvitation.objects.filter(user=user).values_list('meet_id', flat=True)
    organising_ids = list(
        Meeting.objects.filter(emp__user=user).values_list('meetId', flat=True)
    ) + list(
        Meeting.objects.filter(teamEmp__emp__user=user).values_list('meetId', flat=True)
    )
    ids = set(invited_ids) | set(organising_ids)

    return (
        Meeting.objects
        .filter(meetId__in=ids, startedAt__gte=start_dt, startedAt__lte=end_dt)
        .select_related('teamId', 'emp', 'emp__user', 'teamEmp', 'teamEmp__emp', 'teamEmp__emp__user')
        .prefetch_related('invitations__user__employee')
        .order_by('startedAt')
    )


def _user_meetings_before(user, before_date: datetime.date, limit: int = 3):
    start_dt = datetime.datetime.combine(before_date, datetime.time.min, tzinfo=timezone.get_current_timezone())
    invited_ids = MeetingInvitation.objects.filter(user=user).values_list('meet_id', flat=True)
    return (
        Meeting.objects
        .filter(meetId__in=invited_ids, startedAt__lt=start_dt)
        .select_related('teamId', 'emp', 'emp__user', 'teamEmp', 'teamEmp__emp', 'teamEmp__emp__user')
        .prefetch_related('invitations__user__employee')
        .order_by('-startedAt')[:limit]
    )


# ── view-model assemblers ──────────────────────────────────────────────────

def assemble_for_user(user, anchor: datetime.date | None = None) -> dict:
    """
    Return the full schedule view-model for `user`.

    Keys returned (consumed by schedule.html):
        weekly_days          [{name, num, is_today, events}, ...] (7)
        monthly_days         [{num, is_today, is_other_month, events}, ...] (35)
        monthly_label        "April 2026"
        weekly_range_label   "20 Apr – 26 Apr"
        upcoming_groups      [{label, tag, count, events}, ...]
        recent_past          [event, ...]
        kpis                 {today, this_week, upcoming, pending}
    """
    anchor = anchor or WEEK_ANCHOR or timezone.localdate()

    # The demo "now" is pinned to the anchor at midday so meetings in the
    # anchor week behave as upcoming/current, not past.
    tz = timezone.get_current_timezone()
    now_demo = datetime.datetime.combine(anchor, datetime.time(12, 0), tzinfo=tz)

    week_start = anchor - datetime.timedelta(days=anchor.weekday())
    week_end = week_start + datetime.timedelta(days=6)
    today = anchor

    # Monthly grid: 5 weeks starting on the Monday of the first week of the
    # anchor's month.
    first_of_month = anchor.replace(day=1)
    grid_start = first_of_month - datetime.timedelta(days=first_of_month.weekday())
    grid_end = grid_start + datetime.timedelta(days=34)

    # Window for upcoming list: from anchor through the next 21 days.
    upcoming_end = anchor + datetime.timedelta(days=21)

    week_meetings = _user_meetings_between(user, week_start, week_end)
    month_meetings = _user_meetings_between(user, grid_start, grid_end)
    upcoming_meetings = _user_meetings_between(user, anchor, upcoming_end)
    past_meetings = _user_meetings_before(user, anchor, limit=3)

    # ── weekly_days ────────────────────────────────────────────────
    weekly_days = []
    for i in range(7):
        d = week_start + datetime.timedelta(days=i)
        events = [serialise_meeting(m, user.userId, now=now_demo) for m in week_meetings if timezone.localtime(m.startedAt).date() == d]
        weekly_days.append({
            'name': DAY_NAMES[i],
            'num': d.day,
            'is_today': d == today,
            'events': events,
        })

    # ── monthly_days ───────────────────────────────────────────────
    monthly_days = []
    for i in range(35):
        d = grid_start + datetime.timedelta(days=i)
        events = [serialise_meeting(m, user.userId, now=now_demo) for m in month_meetings if timezone.localtime(m.startedAt).date() == d]
        monthly_days.append({
            'num': d.day,
            'is_today': d == today,
            'is_other_month': d.month != anchor.month,
            'events_visible': events[:2],
            'events_extra': max(0, len(events) - 2),
            'events_count': len(events),
        })

    # ── upcoming_groups ────────────────────────────────────────────
    by_date = {}
    for m in upcoming_meetings:
        d = timezone.localtime(m.startedAt).date()
        by_date.setdefault(d, []).append(m)
    upcoming_groups = []
    for d in sorted(by_date):
        evs = [serialise_meeting(m, user.userId, now=now_demo) for m in by_date[d]]
        if d == today:
            label = 'Today'
            tag = 'Today'
        else:
            label = f'{DAY_NAMES_LONG[d.weekday()]}, {d.day} {MONTH_NAMES[d.month - 1]} {d.year}'
            tag = ''
        upcoming_groups.append({
            'label': label,
            'tag': tag,
            'count': len(evs),
            'events': evs,
        })

    # ── recent_past ────────────────────────────────────────────────
    recent_past = [serialise_meeting(m, user.userId, now=now_demo) for m in past_meetings]

    # ── kpis ───────────────────────────────────────────────────────
    today_count = sum(1 for d in weekly_days if d['is_today'] for _ in d['events'])
    this_week_count = sum(len(d['events']) for d in weekly_days)
    upcoming_count = sum(g['count'] for g in upcoming_groups)
    # "Pending" = invitations the user has not yet responded to inside the visible window
    visible_meet_ids = set()
    for d in weekly_days:
        for e in d['events']:
            visible_meet_ids.add(e.meet_id)
    for g in upcoming_groups:
        for e in g['events']:
            visible_meet_ids.add(e.meet_id)
    pending_count = MeetingInvitation.objects.filter(
        user=user, meet_id__in=visible_meet_ids, status='pending',
    ).count()

    # ── range labels ───────────────────────────────────────────────
    if week_start.month == week_end.month:
        weekly_range_label = f'{week_start.day} – {week_end.day} {MONTH_NAMES[week_start.month - 1][:3]}'
    else:
        weekly_range_label = (
            f'{week_start.day} {MONTH_NAMES[week_start.month - 1][:3]} – '
            f'{week_end.day} {MONTH_NAMES[week_end.month - 1][:3]}'
        )
    monthly_label = f'{MONTH_NAMES[anchor.month - 1]} {anchor.year}'

    return {
        'weekly_days': weekly_days,
        'monthly_days': monthly_days,
        'monthly_label': monthly_label,
        'weekly_range_label': weekly_range_label,
        'upcoming_groups': upcoming_groups,
        'recent_past': recent_past,
        'kpis': {
            'today': today_count,
            'this_week': this_week_count,
            'upcoming': upcoming_count,
            'pending': pending_count,
        },
    }
