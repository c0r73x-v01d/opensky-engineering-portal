"""
OpenSky views.
"""
from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import render
from django.urls import reverse
from django.views.decorators.csrf import csrf_exempt
from reportlab.pdfgen import canvas
from openpyxl import Workbook

# ════════════════════════════════════════════════════════════════════
# Main page views
# ════════════════════════════════════════════════════════════════════
def home(request):
    # TODO: load user's widgets / profile / activity from DB
    return render(request, 'home.html', {'active_page': 'home'})


def teams(request):
    # TODO: load teams list and teams_json for client-side filtering
    return render(request, 'teams.html', {'active_page': 'teams'})


def schedule(request):
    # TODO: load meetings, users, teams, and stats (today/week/upcoming/pending counts)
    return render(request, 'schedule.html', {'active_page': 'schedule'})


def messages_view(request):
    # TODO: load inbox / sent / drafts / starred messages + folder counts
    return render(request, 'messages.html', {'active_page': 'messages'})


def organisation(request):
    # TODO: load departments + teams hierarchy
    return render(request, 'organisation.html', {'active_page': 'organisation'})


def reports(request):
    from .models import Team, Department
    from django.db.models import Q

    teams = Team.objects.select_related('department').all()
    departments = Department.objects.all()

    dept_id = request.GET.get('department')
    if dept_id:
        teams = teams.filter(department_id=dept_id)

    unmanaged_active = teams.filter(
        Q(manager__isnull=True) | Q(manager__exact="")
    )

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

def export_pdf(request):
        from .models import Team
        from django.db.models import Q

        teams = Team.objects.all()
        total_teams = teams.count()
        unmanaged = teams.filter(Q(manager__isnull=True) | Q(manager="")).count()

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
            manager = team.manager if team.manager else "No Manager"
            p.drawString(120, y, f"{team.name} - {team.department.name} - {manager}")
            y -= 20

        p.showPage()
        p.save()

        return response


def export_excel(request):
    from .models import Team

    teams = Team.objects.select_related('department').all()

    wb = Workbook()
    ws = wb.active
    ws.title = "Reports"

    ws.append(["Team Name", "Department", "Manager"])

    for team in teams:
        ws.append([
            team.name,
            team.department.name,
            team.manager if team.manager else "Unassigned"
        ])

    response = HttpResponse(
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    response["Content-Disposition"] = 'attachment; filename="reports.xlsx"'

    wb.save(response)
    return response

# ════════════════════════════════════════════════════════════════════
# Auth views
# ════════════════════════════════════════════════════════════════════
@csrf_exempt
def login_view(request):
    # TODO: authenticate user on POST, handle errors, redirect on success
    if request.method == 'POST':
        return HttpResponseRedirect(reverse('home'))
    return render(request, 'login.html', {})


def logout_view(request):
    # TODO: clear session on real auth
    return HttpResponseRedirect(reverse('login'))


# ════════════════════════════════════════════════════════════════════
# Action endpoint stubs
# ════════════════════════════════════════════════════════════════════
@csrf_exempt
def stub_action(request):
    return HttpResponse(
        f'<p style="font-family: system-ui; padding: 40px;">'
        f'Stub endpoint: <code>{request.path}</code> (method: {request.method}). '
        f'Preview mode — nothing happens.</p>'
    )
