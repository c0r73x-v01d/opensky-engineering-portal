"""
Context processors. Populate the navbar notification bell, user dropdown
data, and profile-modal context for every authenticated response.
"""
from .models import Employee, Notification, NotificationRecipient, TeamManager


def nav_context(request):
    if not getattr(request, 'user', None) or not request.user.is_authenticated:
        return {
            'notifications': [],
            'unread_notif_count': 0,
            'profile_modal_ctx': None,
        }

    recipient_rows = (
        NotificationRecipient.objects
        .filter(user=request.user)
        .select_related('notif')
        .order_by('-notif__createdAt')[:8]
    )
    notifications = [
        {
            'message': row.notif.message,
            'time': row.notif.time,
            'is_read': row.isRead,
        }
        for row in recipient_rows
    ]
    unread = NotificationRecipient.objects.filter(
        user=request.user, isRead=False,
    ).count()

    # Profile modal data — needs to be available on every page so the
    # avatar dropdown's "View Profile" button works site-wide.
    profile_ctx = _profile_modal_context(request.user)

    return {
        'notifications': notifications,
        'unread_notif_count': unread,
        'profile_modal_ctx': profile_ctx,
    }


def _profile_modal_context(user):
    """Build the data the shared profile modal needs.

    Mirrors the home view's user/team serialisation but lighter — only the
    fields the modal actually displays.
    """
    emp = (
        Employee.objects
        .select_related('teamId__department', 'teamId__type')
        .filter(user=user)
        .first()
    )
    team = emp.teamId if emp else None
    department = team.department if team else None

    # Status colour map mirrors home view.
    status_colour = {
        'active': '#007e13',
        'restructuring': '#f15a22',
        'disbanded': '#9aa0a6',
    }
    status_label = {
        'active': 'Active',
        'restructuring': 'Restructuring',
        'disbanded': 'Disbanded',
    }

    manager_dict = None
    if team:
        mgr = team.managers.select_related('emp__user').first()
        if mgr:
            manager_dict = {
                'f_name':       mgr.emp.user.first_name,
                'l_name':       mgr.emp.user.last_name,
                'email':        mgr.emp.user.email,
                'position':     mgr.emp.position or 'Engineering Manager',
                'avatar_bg':    'rgba(0, 15, 245, .08)',
                'avatar_color': '#0010f5',
                'avatar_url':   mgr.emp.user.avatar.url if mgr.emp.user.avatar else '',
            }

    return {
        'about_me':          user.about_me or '',
        'date_of_birth':     user.dob,
        'avatar_url':        user.avatar.url if user.avatar else '',
        'position':          emp.position if emp else '',
        'team': {
            'team_name':      team.teamName,
            'descrip':        team.descrip or '',
            'focus':          team.focusArea or 'Not specified',
            'agile_practice': team.agilePractice or 'Not specified',
        } if team else None,
        'department': {
            'depart_name': department.departName,
        } if department else None,
        'team_type_name':    team.type.typeName if team and team.type else '',
        'team_status_label': status_label.get(team.teamStatus, '') if team else '',
        'team_status_color': status_colour.get(team.teamStatus, '#9aa0a6') if team else '#9aa0a6',
        'manager':           manager_dict,
    }
