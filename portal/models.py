"""
OpenSky Engineering Portal — data models.

Mirrors the schema in db_creator.sql at column, constraint, and table-name level.
Every SQL CHECK is represented by a CheckConstraint in Meta.constraints.
Every SQL UNIQUE (including composite) is represented by a UniqueConstraint.
Application-layer invariants (≥5 engineers per team, ≥3 teams per department,
≥2 managers per team, manager-belongs-to-team) are enforced via clean().
"""
from django.contrib.auth.models import AbstractUser
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q


# ────────────────────────────────────────────────────────────────────
#  Users
# ────────────────────────────────────────────────────────────────────
class User(AbstractUser):
    """
    Authenticated identity. Maps 1:1 to the SQL `Users` table. Django's
    password hashing (PBKDF2 by default) is used rather than bcrypt; the
    column still stores an opaque hash string.
    """
    userId = models.AutoField(primary_key=True, db_column='userId')
    username = models.CharField(max_length=50, unique=True, db_column='username')
    password = models.CharField(max_length=255, db_column='password')
    email = models.EmailField(max_length=100, unique=True, db_column='email')
    first_name = models.CharField(max_length=50, db_column='fName')
    last_name = models.CharField(max_length=50, db_column='lName')
    dob = models.DateField(null=True, blank=True, db_column='dob')
    about_me = models.TextField(null=True, blank=True, db_column='aboutMe')

    REQUIRED_FIELDS = ['email', 'first_name', 'last_name']

    class Meta:
        db_table = 'Users'

    def __str__(self):
        return f'{self.first_name} {self.last_name}'.strip() or self.username

    # Template-facing aliases — the existing templates reference these names.
    @property
    def f_name(self):
        return self.first_name

    @property
    def l_name(self):
        return self.last_name


# ────────────────────────────────────────────────────────────────────
#  Department
# ────────────────────────────────────────────────────────────────────
class Department(models.Model):
    departmentId = models.AutoField(primary_key=True, db_column='departmentId')
    departName = models.CharField(max_length=100, unique=True, db_column='departName')
    specialization = models.CharField(max_length=100, null=True, blank=True,
                                      db_column='specialization')

    class Meta:
        db_table = 'Department'

    def __str__(self):
        return self.departName

    def clean(self):
        # Brief requires ≥3 teams per department; enforced post-hoc when teams
        # are present so an empty, freshly-created department can still be saved.
        if self.pk and self.team_set.count() > 0 and self.team_set.count() < 3:
            raise ValidationError('Each department must comprise at least 3 teams.')


# ────────────────────────────────────────────────────────────────────
#  TeamType
# ────────────────────────────────────────────────────────────────────
class TeamType(models.Model):
    typeId = models.AutoField(primary_key=True, db_column='typeId')
    typeName = models.CharField(max_length=50, db_column='typeName')

    class Meta:
        db_table = 'TeamType'

    def __str__(self):
        return self.typeName


# ────────────────────────────────────────────────────────────────────
#  Skill
# ────────────────────────────────────────────────────────────────────
class Skill(models.Model):
    skillId = models.AutoField(primary_key=True, db_column='skillId')
    skillName = models.CharField(max_length=50, unique=True, db_column='skillName')

    class Meta:
        db_table = 'Skill'

    def __str__(self):
        return self.skillName


# ────────────────────────────────────────────────────────────────────
#  Team
# ────────────────────────────────────────────────────────────────────
class Team(models.Model):
    teamId = models.AutoField(primary_key=True, db_column='teamId')
    department = models.ForeignKey(Department, on_delete=models.PROTECT,
                                   db_column='departmentId')
    type = models.ForeignKey(TeamType, on_delete=models.SET_NULL,
                             null=True, blank=True, db_column='typeId')
    teamName = models.CharField(max_length=100, db_column='teamName')
    descrip = models.TextField(null=True, blank=True, db_column='descrip')
    responsib = models.TextField(null=True, blank=True, db_column='responsib')
    focusArea = models.CharField(max_length=100, null=True, blank=True, db_column='focusArea')
    standupTime = models.TimeField(null=True, blank=True, db_column='standupTime')
    standupLink = models.CharField(max_length=255, null=True, blank=True, db_column='standupLink')
    concurrentProjs = models.IntegerField(null=True, blank=True, db_column='concurrentProjs')
    workstreamMf = models.CharField(max_length=100, null=True, blank=True, db_column='workstreamMf')
    jiraProjName = models.CharField(max_length=100, null=True, blank=True, db_column='jiraProjName')
    jiraBoardLink = models.CharField(max_length=255, null=True, blank=True, db_column='jiraBoardLink')
    commChann = models.CharField(max_length=100, null=True, blank=True, db_column='commChann')
    teamWiki = models.CharField(max_length=255, null=True, blank=True, db_column='teamWiki')
    agilePractice = models.CharField(max_length=50, null=True, blank=True, db_column='agilePractice')
    teamStatus = models.CharField(max_length=20, db_column='teamStatus')
    createdAt = models.DateTimeField(auto_now_add=True, db_column='createdAt')
    updatedAt = models.DateTimeField(auto_now=True, db_column='updatedAt')
    disbandedAt = models.DateTimeField(null=True, blank=True, db_column='disbandedAt')

    class Meta:
        db_table = 'Team'
        constraints = [
            models.UniqueConstraint(
                fields=['department', 'teamName'],
                name='team_unique_dept_name',
            ),
        ]

    def __str__(self):
        return self.teamName

    def clean(self):
        # Brief: ≥5 engineers per team; health check model: ≥2 team leaders.
        if self.pk:
            emp_count = Employee.objects.filter(teamId=self.teamId).count()
            if 0 < emp_count < 5:
                raise ValidationError('Each team must comprise at least 5 engineers.')
            mgr_count = TeamManager.objects.filter(teamId=self.teamId).count()
            if 0 < mgr_count < 2:
                raise ValidationError('Each team must be managed by at least 2 team leaders.')


# ────────────────────────────────────────────────────────────────────
#  Employee
# ────────────────────────────────────────────────────────────────────
class Employee(models.Model):
    empId = models.AutoField(primary_key=True, db_column='empId')
    user = models.OneToOneField(User, on_delete=models.CASCADE,
                                db_column='userId', related_name='employee')
    teamId = models.ForeignKey(Team, on_delete=models.SET_NULL,
                               null=True, blank=True, db_column='teamId',
                               related_name='employees')
    position = models.CharField(max_length=50, null=True, blank=True,
                                db_column='position')

    class Meta:
        db_table = 'Employee'
        constraints = [
            models.UniqueConstraint(
                fields=['empId', 'teamId'],
                name='employee_unique_emp_team',
            ),
        ]

    def __str__(self):
        return f'{self.user} ({self.position or "engineer"})'


# ────────────────────────────────────────────────────────────────────
#  TeamManager
# ────────────────────────────────────────────────────────────────────
class TeamManager(models.Model):
    # empId is the PK in the schema. In Django the OneToOne serves both
    # as PK (via primary_key=True) and as the FK to Employee.
    emp = models.OneToOneField(Employee, on_delete=models.CASCADE,
                               primary_key=True, db_column='empId',
                               related_name='manager_role')
    teamId = models.ForeignKey(Team, on_delete=models.CASCADE,
                               db_column='teamId', related_name='managers')

    class Meta:
        db_table = 'TeamManager'

    def __str__(self):
        return f'Manager {self.emp} → {self.teamId}'

    def clean(self):
        # Composite FK (empId, teamId) → Employee(empId, teamId) must match.
        if self.emp_id and self.teamId_id and self.emp.teamId_id != self.teamId_id:
            raise ValidationError(
                'A team manager must be a member of the team they manage.'
            )


# ────────────────────────────────────────────────────────────────────
#  DepartmentLeader
# ────────────────────────────────────────────────────────────────────
class DepartmentLeader(models.Model):
    emp = models.OneToOneField(Employee, on_delete=models.CASCADE,
                               primary_key=True, db_column='empId',
                               related_name='leader_role')
    department = models.OneToOneField(Department, on_delete=models.CASCADE,
                                      db_column='departmentId',
                                      related_name='leader')

    class Meta:
        db_table = 'DepartmentLeader'

    def __str__(self):
        return f'Leader of {self.department}: {self.emp}'


# ────────────────────────────────────────────────────────────────────
#  Team_Skill_Alloc
# ────────────────────────────────────────────────────────────────────
class TeamSkillAlloc(models.Model):
    skill = models.ForeignKey(Skill, on_delete=models.CASCADE, db_column='skillId')
    team = models.ForeignKey(Team, on_delete=models.CASCADE, db_column='teamId')

    class Meta:
        db_table = 'Team_Skill_Alloc'
        constraints = [
            models.UniqueConstraint(
                fields=['skill', 'team'],
                name='team_skill_unique',
            ),
        ]

    def __str__(self):
        return f'{self.team} ↔ {self.skill}'


# ────────────────────────────────────────────────────────────────────
#  Project
# ────────────────────────────────────────────────────────────────────
class Project(models.Model):
    repoId = models.AutoField(primary_key=True, db_column='repoId')
    team = models.ForeignKey(Team, on_delete=models.CASCADE,
                             db_column='teamId', related_name='projects')
    repoName = models.CharField(max_length=100, db_column='repoName')
    repoUrl = models.CharField(max_length=255, null=True, blank=True, db_column='repoUrl')
    isMainProj = models.BooleanField(default=False, db_column='isMainProj')

    class Meta:
        db_table = 'Project'

    def __str__(self):
        return self.repoName


# ────────────────────────────────────────────────────────────────────
#  Team_Dependency
# ────────────────────────────────────────────────────────────────────
class TeamDependency(models.Model):
    upstream = models.ForeignKey(Team, on_delete=models.CASCADE,
                                 db_column='upstr_teamId',
                                 related_name='downstream_links')
    downstream = models.ForeignKey(Team, on_delete=models.CASCADE,
                                   db_column='downstr_teamId',
                                   related_name='upstream_links')
    dependencyType = models.CharField(max_length=50, null=True, blank=True,
                                      db_column='dependencyType')

    class Meta:
        db_table = 'Team_Dependency'
        constraints = [
            models.UniqueConstraint(
                fields=['upstream', 'downstream'],
                name='team_dep_unique_pair',
            ),
            models.CheckConstraint(
                check=~Q(upstream=models.F('downstream')),
                name='team_dep_no_self_loop',
            ),
        ]

    def __str__(self):
        return f'{self.upstream} → {self.downstream}'


# ────────────────────────────────────────────────────────────────────
#  HealthCard
# ────────────────────────────────────────────────────────────────────
class HealthCard(models.Model):
    cardId = models.AutoField(primary_key=True, db_column='cardId')
    cardName = models.CharField(max_length=100, unique=True, db_column='cardName')
    awesomeDesc = models.TextField(db_column='awesomeDesc')
    crappyDesc = models.TextField(db_column='crappyDesc')

    class Meta:
        db_table = 'HealthCard'

    def __str__(self):
        return self.cardName


# ────────────────────────────────────────────────────────────────────
#  HealthSession
# ────────────────────────────────────────────────────────────────────
class HealthSession(models.Model):
    sessionId = models.AutoField(primary_key=True, db_column='sessionId')
    sessionName = models.CharField(max_length=100, db_column='sessionName')
    sessionDate = models.DateField(db_column='sessionDate')
    createdAt = models.DateTimeField(auto_now_add=True, db_column='createdAt')

    class Meta:
        db_table = 'HealthSession'

    def __str__(self):
        return self.sessionName


# ────────────────────────────────────────────────────────────────────
#  HealthVote
# ────────────────────────────────────────────────────────────────────
class HealthVote(models.Model):
    RATING_CHOICES = [('green', 'Green'), ('amber', 'Amber'), ('red', 'Red')]
    TREND_CHOICES = [('up', 'Up'), ('stable', 'Stable'), ('down', 'Down')]

    emp = models.ForeignKey(Employee, on_delete=models.CASCADE, db_column='empId')
    session = models.ForeignKey(HealthSession, on_delete=models.CASCADE, db_column='sessionId')
    card = models.ForeignKey(HealthCard, on_delete=models.CASCADE, db_column='cardId')
    teamId = models.ForeignKey(Team, on_delete=models.CASCADE, db_column='teamId')
    rating = models.CharField(max_length=10, choices=RATING_CHOICES, db_column='rating')
    trend = models.CharField(max_length=10, choices=TREND_CHOICES, db_column='trend')
    votedAt = models.DateTimeField(auto_now_add=True, db_column='votedAt')

    class Meta:
        db_table = 'HealthVote'
        constraints = [
            models.UniqueConstraint(
                fields=['emp', 'session', 'card'],
                name='health_vote_unique',
            ),
            models.CheckConstraint(
                check=Q(rating__in=['green', 'amber', 'red']),
                name='health_vote_rating_valid',
            ),
            models.CheckConstraint(
                check=Q(trend__in=['up', 'stable', 'down']),
                name='health_vote_trend_valid',
            ),
        ]


# ────────────────────────────────────────────────────────────────────
#  Meeting
# ────────────────────────────────────────────────────────────────────
class Meeting(models.Model):
    TYPE_CHOICES = [
        ('personal', 'Personal'),
        ('team', 'Team'),
        ('standup', 'Standup'),
    ]
    STATUS_CHOICES = [
        ('scheduled', 'Scheduled'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ]

    meetId = models.AutoField(primary_key=True, db_column='meetId')
    teamId = models.ForeignKey(Team, on_delete=models.CASCADE,
                               null=True, blank=True,
                               db_column='teamId', related_name='meetings')
    emp = models.ForeignKey(Employee, on_delete=models.SET_NULL,
                            null=True, blank=True, db_column='empId',
                            related_name='personal_meetings')
    teamEmp = models.ForeignKey(TeamManager, on_delete=models.SET_NULL,
                                null=True, blank=True, db_column='teamEmpId',
                                related_name='team_meetings')
    meetingType = models.CharField(max_length=20, choices=TYPE_CHOICES, db_column='meetingType')
    startedAt = models.DateTimeField(db_column='startedAt')
    endedAt = models.DateTimeField(null=True, blank=True, db_column='endedAt')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES,
                              default='scheduled', db_column='status')
    platform = models.CharField(max_length=50, null=True, blank=True, db_column='platform')
    message = models.TextField(null=True, blank=True, db_column='message')

    class Meta:
        db_table = 'Meeting'
        constraints = [
            models.CheckConstraint(
                check=Q(status__in=['scheduled', 'in_progress', 'completed', 'cancelled']),
                name='meeting_status_valid',
            ),
            models.CheckConstraint(
                check=Q(endedAt__isnull=True) | Q(endedAt__gt=models.F('startedAt')),
                name='meeting_end_after_start',
            ),
            models.CheckConstraint(
                check=Q(meetingType__in=['personal', 'team', 'standup']),
                name='meeting_type_valid',
            ),
            models.CheckConstraint(
                check=(
                    (Q(meetingType='personal') & Q(emp__isnull=False) & Q(teamEmp__isnull=True))
                    | (Q(meetingType__in=['team', 'standup']) & Q(teamEmp__isnull=False) & Q(emp__isnull=True))
                ),
                name='meeting_type_host_xor',
            ),
        ]

    def __str__(self):
        return f'{self.get_meetingType_display()} meeting @ {self.startedAt:%Y-%m-%d %H:%M}'

    def clean(self):
        if self.meetingType == 'personal':
            if not self.emp_id or self.teamEmp_id:
                raise ValidationError(
                    'A personal meeting must have an employee host and no team host.'
                )
        elif self.meetingType in ('team', 'standup'):
            if not self.teamEmp_id or self.emp_id:
                raise ValidationError(
                    'A team or standup meeting must have a team-manager host and no individual host.'
                )
        if self.endedAt and self.startedAt and self.endedAt <= self.startedAt:
            raise ValidationError('Meeting end time must be after start time.')

    @property
    def organiser_user(self):
        """The human User who organises this meeting, regardless of type."""
        if self.meetingType == 'personal' and self.emp:
            return self.emp.user
        if self.teamEmp:
            return self.teamEmp.emp.user
        return None


# ────────────────────────────────────────────────────────────────────
#  MeetingInvitation
# ────────────────────────────────────────────────────────────────────
class MeetingInvitation(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('accepted', 'Accepted'),
        ('declined', 'Declined'),
    ]

    invitationId = models.AutoField(primary_key=True, db_column='invitationId')
    user = models.ForeignKey(User, on_delete=models.CASCADE,
                             db_column='userId', related_name='invitations')
    meet = models.ForeignKey(Meeting, on_delete=models.CASCADE,
                             db_column='meetId', related_name='invitations')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES,
                              default='pending', db_column='status')

    class Meta:
        db_table = 'MeetingInvitation'
        constraints = [
            models.UniqueConstraint(
                fields=['user', 'meet'],
                name='meeting_invitation_unique',
            ),
            models.CheckConstraint(
                check=Q(status__in=['pending', 'accepted', 'declined']),
                name='meeting_invitation_status_valid',
            ),
        ]

    def __str__(self):
        return f'{self.user} → {self.meet} ({self.status})'


# ────────────────────────────────────────────────────────────────────
#  Action (polymorphic audit log)
# ────────────────────────────────────────────────────────────────────
class Action(models.Model):
    ACTION_CHOICES = [('create', 'Create'), ('update', 'Update'), ('delete', 'Delete')]
    ENTITY_TYPES = [
        'Users', 'Team', 'Employee', 'Department', 'Project', 'Meeting',
        'Message', 'MeetingInvitation', 'TeamManager', 'DepartmentLeader',
        'Team_Skill_Alloc', 'Team_Dependency', 'HealthCard', 'HealthSession',
        'HealthVote', 'Notification', 'Notification_Recipient',
    ]
    ENTITY_TYPE_CHOICES = [(v, v) for v in ENTITY_TYPES]

    actionId = models.AutoField(primary_key=True, db_column='actionId')
    user = models.ForeignKey(User, on_delete=models.CASCADE,
                             db_column='userId', related_name='actions')
    actionDescr = models.TextField(null=True, blank=True, db_column='actionDescr')
    action = models.CharField(max_length=20, choices=ACTION_CHOICES, db_column='action')
    entityId = models.IntegerField(null=True, blank=True, db_column='entityId')
    entityType = models.CharField(max_length=50, null=True, blank=True,
                                  choices=ENTITY_TYPE_CHOICES, db_column='entityType')
    fieldChanged = models.CharField(max_length=50, null=True, blank=True, db_column='fieldChanged')
    oldValue = models.TextField(null=True, blank=True, db_column='oldValue')
    newValue = models.TextField(null=True, blank=True, db_column='newValue')
    timestamp = models.DateTimeField(auto_now_add=True, db_column='timestamp')

    class Meta:
        db_table = 'Action'
        constraints = [
            models.CheckConstraint(
                check=Q(action__in=['create', 'update', 'delete']),
                name='action_action_valid',
            ),
            models.CheckConstraint(
                check=Q(entityType__in=[
                    'Users', 'Team', 'Employee', 'Department', 'Project', 'Meeting',
                    'Message', 'MeetingInvitation', 'TeamManager', 'DepartmentLeader',
                    'Team_Skill_Alloc', 'Team_Dependency', 'HealthCard', 'HealthSession',
                    'HealthVote', 'Notification', 'Notification_Recipient',
                ]) | Q(entityType__isnull=True),
                name='action_entity_type_valid',
            ),
        ]

    def __str__(self):
        return f'{self.action} {self.entityType}#{self.entityId} by {self.user}'


# ────────────────────────────────────────────────────────────────────
#  Message
# ────────────────────────────────────────────────────────────────────
class Message(models.Model):
    STATUS_CHOICES = [('draft', 'Draft'), ('sent', 'Sent'), ('fail', 'Fail')]

    messageId = models.AutoField(primary_key=True, db_column='messageId')
    user = models.ForeignKey(User, on_delete=models.CASCADE,
                             db_column='userId', related_name='sent_messages')
    subject = models.CharField(max_length=200, null=True, blank=True, db_column='subject')
    body = models.TextField(null=True, blank=True, db_column='body')
    createdAt = models.DateTimeField(auto_now_add=True, db_column='createdAt')
    sentAt = models.DateTimeField(null=True, blank=True, db_column='sentAt')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, db_column='status')
    senderMsgDeleted = models.BooleanField(default=False, db_column='senderMsgDeleted')

    class Meta:
        db_table = 'Message'
        constraints = [
            models.CheckConstraint(
                check=Q(status__in=['draft', 'sent', 'fail']),
                name='message_status_valid',
            ),
        ]

    def __str__(self):
        return self.subject or f'(message #{self.messageId})'


# ────────────────────────────────────────────────────────────────────
#  Message_Recipient
# ────────────────────────────────────────────────────────────────────
class MessageRecipient(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, db_column='userId')
    message = models.ForeignKey(Message, on_delete=models.CASCADE,
                                db_column='messageId', related_name='recipients')
    isRead = models.BooleanField(default=False, db_column='isRead')
    recipMsgDeleted = models.BooleanField(default=False, db_column='recipMsgDeleted')

    class Meta:
        db_table = 'Message_Recipient'
        constraints = [
            models.UniqueConstraint(
                fields=['user', 'message'],
                name='message_recipient_unique',
            ),
        ]


# ────────────────────────────────────────────────────────────────────
#  Notification (polymorphic)
# ────────────────────────────────────────────────────────────────────
class Notification(models.Model):
    ENTITY_TYPES = [
        'Meeting', 'MeetingInvitation', 'Message', 'Team', 'HealthSession',
    ]
    ENTITY_TYPE_CHOICES = [(v, v) for v in ENTITY_TYPES]

    notifId = models.AutoField(primary_key=True, db_column='notifId')
    entityId = models.IntegerField(null=True, blank=True, db_column='entityId')
    entityType = models.CharField(max_length=50, null=True, blank=True,
                                  choices=ENTITY_TYPE_CHOICES, db_column='entityType')
    message = models.TextField(db_column='message')
    createdAt = models.DateTimeField(auto_now_add=True, db_column='createdAt')

    class Meta:
        db_table = 'Notification'
        constraints = [
            models.CheckConstraint(
                check=Q(entityType__in=[
                    'Meeting', 'MeetingInvitation', 'Message',
                    'Team', 'HealthSession',
                ]) | Q(entityType__isnull=True),
                name='notification_entity_type_valid',
            ),
        ]

    def __str__(self):
        return self.message[:60]

    @property
    def time(self):
        """Humanised timestamp for the navbar dropdown."""
        return self.createdAt.strftime('%d %b, %H:%M')


# ────────────────────────────────────────────────────────────────────
#  Notification_Recipient
# ────────────────────────────────────────────────────────────────────
class NotificationRecipient(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE,
                             db_column='userId', related_name='notifications')
    notif = models.ForeignKey(Notification, on_delete=models.CASCADE,
                              db_column='notifId', related_name='recipients')
    isRead = models.BooleanField(default=False, db_column='isRead')

    class Meta:
        db_table = 'Notification_Recipient'
        constraints = [
            models.UniqueConstraint(
                fields=['user', 'notif'],
                name='notification_recipient_unique',
            ),
        ]
