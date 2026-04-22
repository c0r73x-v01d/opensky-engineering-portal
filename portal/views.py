"""
OpenSky Engineering Portal views.
"""
from django.contrib import messages as dj_messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

from .forms import RegisterForm
from .models import Action


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
    return render(request, 'schedule.html', {'active_page': 'schedule'})


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
