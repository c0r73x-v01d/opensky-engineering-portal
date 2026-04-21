from django.urls import path
from . import views

urlpatterns = [
    # Main pages
    path('',              views.home,          name='home'),
    path('teams/',        views.teams,         name='teams'),
    path('schedule/',     views.schedule,      name='schedule'),
    path('messages/',     views.messages_view, name='messages'),
    path('organisation/', views.organisation,  name='organisation'),
    path('reports/',      views.reports,       name='reports'),
    path('reports/pdf/', views.export_pdf, name='export_pdf'),
    path('reports/excel/', views.export_excel, name='export_excel'),

    # Auth (all three pages use login.html, JS switches views client-side)
    path('login/',            views.login_view,  name='login'),
    path('logout/',           views.logout_view, name='logout'),
    path('register/',         views.login_view,  name='register'),
    path('forgot-password/',  views.login_view,  name='forgot_password'),

    # POST-only action stubs — replace with real views when you write them
    path('profile/update/',   views.stub_action, name='profile_update'),
    path('messages/star/',    views.stub_action, name='message_star'),
    path('messages/send/',    views.stub_action, name='message_send'),
]
