"""
Context processors. Populate the navbar notification bell and user dropdown
data for every authenticated response.
"""
from .models import Notification, NotificationRecipient


def nav_context(request):
    if not getattr(request, 'user', None) or not request.user.is_authenticated:
        return {
            'notifications': [],
            'unread_notif_count': 0,
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
    return {
        'notifications': notifications,
        'unread_notif_count': unread,
    }
