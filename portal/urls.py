from django.contrib.auth import views as auth_views
from django.urls import path

from . import views

urlpatterns = [
    # Main pages
    path('',              views.home,          name='home'),
    path('teams/',        views.teams,         name='teams'),
    path('schedule/',     views.schedule,      name='schedule'),
    path('schedule/meeting/new/', views.meeting_create, name='meeting_create'),
    path('schedule/meeting/<int:meet_id>/rsvp/', views.meeting_rsvp, name='meeting_rsvp'),
    path('messages/', views.messages_view, name='messages'),
    path('messages/send/', views.message_send, name='message_send'),
    path('messages/star/<int:message_id>/', views.message_star, name='message_star'),
    path('messages/send-draft/<int:message_id>/', views.message_send_draft, name='message_send_draft'),
    path('messages/read/<int:message_id>/', views.message_mark_read, name='message_mark_read'),
    path('organisation/', views.organisation,  name='organisation'),
    path('reports/',      views.reports,       name='reports'),
    path('reports/pdf/',  views.export_pdf,    name='export_pdf'),
    path('reports/excel/', views.export_excel, name='export_excel'),

    # Auth
    path('login/',           auth_views.LoginView.as_view(
                                 template_name='login.html',
                                 redirect_authenticated_user=True,
                             ), name='login'),
    path('logout/',          auth_views.LogoutView.as_view(
                                 next_page='/login/',
                             ), name='logout'),
    path('register/',        views.register_view, name='register'),
    path('forgot-password/', auth_views.PasswordResetView.as_view(
                                 template_name='login.html',
                                 success_url='/accounts/password_reset/done/',
                             ), name='forgot_password'),
]
