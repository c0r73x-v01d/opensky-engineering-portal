"""
Admin registration for the OpenSky portal.
Every domain model is exposed so administrators can manage records directly.
"""
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import (
    Action, Department, DepartmentLeader, Employee, HealthCard, HealthSession,
    HealthVote, Meeting, MeetingInvitation, Message, MessageRecipient,
    Notification, NotificationRecipient, Project, Skill, Team, TeamDependency,
    TeamManager, TeamSkillAlloc, TeamType, User,
)


# ────────────────────────────────────────────────────────────────────
#  User
# ────────────────────────────────────────────────────────────────────
class EmployeeInline(admin.StackedInline):
    model = Employee
    can_delete = False
    extra = 0
    raw_id_fields = ('teamId',)


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    inlines = (EmployeeInline,)
    list_display = ('username', 'email', 'first_name', 'last_name', 'is_staff')
    search_fields = ('username', 'email', 'first_name', 'last_name')
    fieldsets = BaseUserAdmin.fieldsets + (
        ('OpenSky profile', {'fields': ('dob', 'about_me')}),
    )


# ────────────────────────────────────────────────────────────────────
#  Organisation
# ────────────────────────────────────────────────────────────────────
@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ('departName', 'specialization')
    search_fields = ('departName', 'specialization')


@admin.register(TeamType)
class TeamTypeAdmin(admin.ModelAdmin):
    list_display = ('typeId', 'typeName')
    search_fields = ('typeName',)


@admin.register(Skill)
class SkillAdmin(admin.ModelAdmin):
    list_display = ('skillId', 'skillName')
    search_fields = ('skillName',)


@admin.register(Team)
class TeamAdmin(admin.ModelAdmin):
    list_display = ('teamName', 'department', 'type', 'teamStatus', 'createdAt')
    list_filter = ('teamStatus', 'department', 'type')
    search_fields = ('teamName', 'descrip', 'focusArea')
    raw_id_fields = ('department', 'type')


@admin.register(Employee)
class EmployeeAdmin(admin.ModelAdmin):
    list_display = ('empId', 'user', 'teamId', 'position')
    list_filter = ('teamId',)
    search_fields = ('user__username', 'user__first_name', 'user__last_name', 'position')
    raw_id_fields = ('user', 'teamId')


@admin.register(TeamManager)
class TeamManagerAdmin(admin.ModelAdmin):
    list_display = ('emp', 'teamId')
    raw_id_fields = ('emp', 'teamId')


@admin.register(DepartmentLeader)
class DepartmentLeaderAdmin(admin.ModelAdmin):
    list_display = ('emp', 'department')
    raw_id_fields = ('emp', 'department')


@admin.register(TeamSkillAlloc)
class TeamSkillAllocAdmin(admin.ModelAdmin):
    list_display = ('team', 'skill')
    raw_id_fields = ('team', 'skill')


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ('repoName', 'team', 'isMainProj')
    list_filter = ('isMainProj',)
    search_fields = ('repoName', 'repoUrl')
    raw_id_fields = ('team',)


@admin.register(TeamDependency)
class TeamDependencyAdmin(admin.ModelAdmin):
    list_display = ('upstream', 'downstream', 'dependencyType')
    list_filter = ('dependencyType',)
    raw_id_fields = ('upstream', 'downstream')


# ────────────────────────────────────────────────────────────────────
#  Health check
# ────────────────────────────────────────────────────────────────────
@admin.register(HealthCard)
class HealthCardAdmin(admin.ModelAdmin):
    list_display = ('cardName',)
    search_fields = ('cardName',)


@admin.register(HealthSession)
class HealthSessionAdmin(admin.ModelAdmin):
    list_display = ('sessionName', 'sessionDate', 'createdAt')
    list_filter = ('sessionDate',)


@admin.register(HealthVote)
class HealthVoteAdmin(admin.ModelAdmin):
    list_display = ('emp', 'session', 'card', 'teamId', 'rating', 'trend', 'votedAt')
    list_filter = ('rating', 'trend', 'session')
    raw_id_fields = ('emp', 'session', 'card', 'teamId')


# ────────────────────────────────────────────────────────────────────
#  Schedule
# ────────────────────────────────────────────────────────────────────
class MeetingInvitationInline(admin.TabularInline):
    model = MeetingInvitation
    extra = 0
    raw_id_fields = ('user',)


@admin.register(Meeting)
class MeetingAdmin(admin.ModelAdmin):
    list_display = ('meetId', 'meetingType', 'startedAt', 'endedAt',
                    'status', 'platform', 'teamId')
    list_filter = ('meetingType', 'status', 'platform')
    search_fields = ('message',)
    raw_id_fields = ('teamId', 'emp', 'teamEmp')
    date_hierarchy = 'startedAt'
    inlines = [MeetingInvitationInline]


@admin.register(MeetingInvitation)
class MeetingInvitationAdmin(admin.ModelAdmin):
    list_display = ('invitationId', 'user', 'meet', 'status')
    list_filter = ('status',)
    raw_id_fields = ('user', 'meet')


# ────────────────────────────────────────────────────────────────────
#  Messaging
# ────────────────────────────────────────────────────────────────────
class MessageRecipientInline(admin.TabularInline):
    model = MessageRecipient
    extra = 0
    raw_id_fields = ('user',)


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ('messageId', 'user', 'subject', 'status', 'createdAt', 'sentAt')
    list_filter = ('status',)
    search_fields = ('subject', 'body')
    raw_id_fields = ('user',)
    inlines = [MessageRecipientInline]


@admin.register(MessageRecipient)
class MessageRecipientAdmin(admin.ModelAdmin):
    list_display = ('user', 'message', 'isRead', 'recipMsgDeleted')
    list_filter = ('isRead',)
    raw_id_fields = ('user', 'message')


# ────────────────────────────────────────────────────────────────────
#  Notifications + audit
# ────────────────────────────────────────────────────────────────────
class NotificationRecipientInline(admin.TabularInline):
    model = NotificationRecipient
    extra = 0
    raw_id_fields = ('user',)


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ('notifId', 'entityType', 'entityId', 'createdAt')
    list_filter = ('entityType',)
    search_fields = ('message',)
    inlines = [NotificationRecipientInline]


@admin.register(NotificationRecipient)
class NotificationRecipientAdmin(admin.ModelAdmin):
    list_display = ('user', 'notif', 'isRead')
    list_filter = ('isRead',)
    raw_id_fields = ('user', 'notif')


@admin.register(Action)
class ActionAdmin(admin.ModelAdmin):
    list_display = ('actionId', 'user', 'action', 'entityType', 'entityId', 'timestamp')
    list_filter = ('action', 'entityType')
    search_fields = ('actionDescr', 'fieldChanged')
    readonly_fields = ('timestamp',)
