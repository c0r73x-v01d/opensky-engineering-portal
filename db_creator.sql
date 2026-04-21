-- OpenSky Engineering

PRAGMA foreign_keys = ON;

DROP TABLE IF EXISTS Notification_Recipient;
DROP TABLE IF EXISTS Notification;
DROP TABLE IF EXISTS Message_Recipient;
DROP TABLE IF EXISTS Message;
DROP TABLE IF EXISTS Action;
DROP TABLE IF EXISTS HealthVote;
DROP TABLE IF EXISTS HealthSession;
DROP TABLE IF EXISTS HealthCard;
DROP TABLE IF EXISTS MeetingInvitation;
DROP TABLE IF EXISTS Meeting;
DROP TABLE IF EXISTS Team_Skill_Alloc;
DROP TABLE IF EXISTS Project;
DROP TABLE IF EXISTS Team_Dependency;
DROP TABLE IF EXISTS TeamManager;
DROP TABLE IF EXISTS DepartmentLeader;
DROP TABLE IF EXISTS Employee;
DROP TABLE IF EXISTS Team;
DROP TABLE IF EXISTS TeamType;
DROP TABLE IF EXISTS Skill;
DROP TABLE IF EXISTS Department;
DROP TABLE IF EXISTS Users;

-- ============================================
--  Users
-- ============================================
CREATE TABLE Users (
    userId      INTEGER      PRIMARY KEY AUTOINCREMENT,
    username    VARCHAR(50)  NOT NULL UNIQUE,
    password    VARCHAR(255) NOT NULL, -- will store bcrypt hash
    email       VARCHAR(100) NOT NULL UNIQUE,
    fName       VARCHAR(50)  NOT NULL,
    lName       VARCHAR(50)  NOT NULL,
    dob         DATE,
    aboutMe     TEXT
);

-- ============================================
--  Department
--
--  The brief requires at least 3 teams
--  per department and at least 2 departments overall.
--  Each department should also have exactly one leader.
--  These minimums cannot be expressed in SQL and are
--  enforced at the application layer.
--
--  Department (1..1) --comprises--> (3..*) Team
--  is enforced at application layer
-- ============================================
CREATE TABLE Department (
    departmentId   INTEGER      PRIMARY KEY AUTOINCREMENT,
    departName     VARCHAR(100) NOT NULL UNIQUE,
    specialization VARCHAR(100)
);

-- ============================================
--  TeamType
-- ============================================
CREATE TABLE TeamType (
    typeId   INTEGER     PRIMARY KEY AUTOINCREMENT,
    typeName VARCHAR(50) NOT NULL
);

-- ============================================
--  Skill
-- ============================================
CREATE TABLE Skill (
    skillId   INTEGER     PRIMARY KEY AUTOINCREMENT,
    skillName VARCHAR(50) NOT NULL UNIQUE
);

-- ============================================
--  Team
--
--  The brief requires at least 5 engineers per team,
--  and the health check model requires at least 2
--  team leaders. These minimums cannot be expressed
--  in SQL and are enforced at the application layer.
--
--  Team (1..1) --comprises--> (5..*) Employee
--  is enforced at application layer
--  Team (1..1) --managed by-- (2..*) TeamManager
--  is enforced at application layer
-- ============================================
CREATE TABLE Team (
    teamId        INTEGER      PRIMARY KEY AUTOINCREMENT,
    departmentId  INT          NOT NULL,
    typeId        INT,
    teamName      VARCHAR(100) NOT NULL,
    descrip       TEXT,
    responsib     TEXT,
    focusArea     VARCHAR(100),
    standupTime   TIME,
    standupLink   VARCHAR(255),
    concurrentProjs INT,
    workstreamMf  VARCHAR(100),
    jiraProjName  VARCHAR(100),
    jiraBoardLink VARCHAR(255),
    commChann     VARCHAR(100),
    teamWiki      VARCHAR(255),
    agilePractice VARCHAR(50),
    teamStatus    VARCHAR(20)  NOT NULL,
    createdAt     TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updatedAt     TIMESTAMP             DEFAULT CURRENT_TIMESTAMP,
    disbandedAt   TIMESTAMP,

    FOREIGN KEY (departmentId) REFERENCES Department(departmentId),
    FOREIGN KEY (typeId)       REFERENCES TeamType(typeId),
    UNIQUE (departmentId, teamName)
);

-- ============================================
--  Employee
-- ============================================
CREATE TABLE Employee (
    empId    INTEGER     PRIMARY KEY AUTOINCREMENT,
    userId   INT         NOT NULL UNIQUE,
    teamId   INT,
    position VARCHAR(50),

    FOREIGN KEY (userId) REFERENCES Users(userId) ON DELETE CASCADE,
    FOREIGN KEY (teamId) REFERENCES Team(teamId),
    UNIQUE (empId, teamId)
);

-- ============================================
--  TeamManager
--
--  The composite FK (empId, teamId) ensures a manager belongs to
--  the team they manage. The health check model
--  requires at least 2 team leaders per team which is enforced
--  at the application layer.
-- ============================================
CREATE TABLE TeamManager (
    empId  INT PRIMARY KEY,
    teamId INT NOT NULL,

    FOREIGN KEY (empId)         REFERENCES Employee(empId),
    FOREIGN KEY (empId, teamId) REFERENCES Employee(empId, teamId)
);

-- ============================================
--  DepartmentLeader
-- ============================================
CREATE TABLE DepartmentLeader (
    empId        INT PRIMARY KEY,
    departmentId INT NOT NULL UNIQUE,

    FOREIGN KEY (empId)        REFERENCES Employee(empId),
    FOREIGN KEY (departmentId) REFERENCES Department(departmentId)
);

-- ============================================
--  Team_Skill_Alloc
-- ============================================
CREATE TABLE Team_Skill_Alloc (
    skillId INT NOT NULL,
    teamId  INT NOT NULL,

    PRIMARY KEY (skillId, teamId),
    FOREIGN KEY (skillId) REFERENCES Skill(skillId),
    FOREIGN KEY (teamId)  REFERENCES Team(teamId)
);

-- ============================================
--  Project
-- ============================================
CREATE TABLE Project (
    repoId     INTEGER      PRIMARY KEY AUTOINCREMENT,
    teamId     INT          NOT NULL,
    repoName   VARCHAR(100) NOT NULL,
    repoUrl    VARCHAR(255),
    isMainProj BOOLEAN      NOT NULL DEFAULT FALSE,

    FOREIGN KEY (teamId) REFERENCES Team(teamId)
);

-- ============================================
--  Team_Dependency
-- ============================================
CREATE TABLE Team_Dependency (
    upstr_teamId    INT         NOT NULL,
    downstr_teamId  INT         NOT NULL,
    dependencyType  VARCHAR(50),

    PRIMARY KEY (upstr_teamId, downstr_teamId),
    FOREIGN KEY (upstr_teamId)   REFERENCES Team(teamId),
    FOREIGN KEY (downstr_teamId) REFERENCES Team(teamId),
    CHECK (upstr_teamId != downstr_teamId)
);

-- ============================================
--  HealthCard
-- ============================================
CREATE TABLE HealthCard (
    cardId      INTEGER      PRIMARY KEY AUTOINCREMENT,
    cardName    VARCHAR(100) NOT NULL UNIQUE,
    awesomeDesc TEXT         NOT NULL,
    crappyDesc  TEXT         NOT NULL
);

-- ============================================
--  HealthSession
-- ============================================
CREATE TABLE HealthSession (
    sessionId   INTEGER      PRIMARY KEY AUTOINCREMENT,
    sessionName VARCHAR(100) NOT NULL,
    sessionDate DATE         NOT NULL,
    createdAt   TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- ============================================
--  HealthVote
--
--  UNIQUE (empId, sessionId, cardId) ensures
--  one vote per engineer per card per session.
--
--  teamId is stored explicitly (not derived from
--  Employee.teamId) to preserve historical accuracy
--  if an engineer transfers between teams.
-- ============================================
CREATE TABLE HealthVote (
    empId     INT         NOT NULL,
    sessionId INT         NOT NULL,
    cardId    INT         NOT NULL,
    teamId    INT         NOT NULL,
    rating    VARCHAR(10) NOT NULL,
    trend     VARCHAR(10) NOT NULL,
    votedAt   TIMESTAMP   NOT NULL DEFAULT CURRENT_TIMESTAMP,

    PRIMARY KEY (empId, sessionId, cardId),

    FOREIGN KEY (empId)     REFERENCES Employee(empId),
    FOREIGN KEY (teamId)    REFERENCES Team(teamId),
    FOREIGN KEY (sessionId) REFERENCES HealthSession(sessionId),
    FOREIGN KEY (cardId)    REFERENCES HealthCard(cardId),

    CHECK (rating IN ('green', 'amber', 'red')),
    CHECK (trend  IN ('up', 'stable', 'down'))
);

-- ============================================
--  Meeting
--
--  A scheduled event (personal, team, or standup).
--  Participants are tracked via MeetingInvitation.
--  A meeting should always have at least one invitee,
--  but this minimum cannot be expressed in SQL and
--  is enforced at the application layer.
--
--  Meeting (1..1) --includes--> (1..*) MeetingInvitation
--  is enforced at application layer
--
--  CHECK enforces exactly one FK is filled based
--  on meetingType.
-- ============================================
CREATE TABLE Meeting (
    meetId      INTEGER      PRIMARY KEY AUTOINCREMENT,
    teamId      INT,
    empId       INT,
    teamEmpId   INT,
    meetingType VARCHAR(20)  NOT NULL,
    startedAt   TIMESTAMP    NOT NULL,
    endedAt     TIMESTAMP,
    status      VARCHAR(20)  NOT NULL,
    platform    VARCHAR(50),
    message     TEXT,

    FOREIGN KEY (teamId)    REFERENCES Team(teamId),
    FOREIGN KEY (empId)     REFERENCES Employee(empId),
    FOREIGN KEY (teamEmpId) REFERENCES TeamManager(empId),

    CHECK (status IN ('scheduled', 'in_progress', 'completed', 'cancelled')),
    CHECK (endedAt IS NULL OR endedAt > startedAt),
    CHECK (meetingType IN ('personal', 'team', 'standup')),
    CHECK (
        (meetingType = 'personal'              AND empId IS NOT NULL AND teamEmpId IS NULL)
        OR
        (meetingType IN ('team', 'standup')     AND teamEmpId IS NOT NULL AND empId IS NULL)
    )
);

-- ============================================
--  MeetingInvitation (M:N junction)
--
--  Tracks which users are invited to which meetings
--  and their response status. Every meeting should
--  have at least one invitee which is enforced at the application layer.
-- ============================================
CREATE TABLE MeetingInvitation (
    invitationId INTEGER     PRIMARY KEY AUTOINCREMENT,
    userId       INT         NOT NULL,
    meetId       INT         NOT NULL,
    status       VARCHAR(20) NOT NULL,

    UNIQUE (userId, meetId),

    FOREIGN KEY (userId) REFERENCES Users(userId),
    FOREIGN KEY (meetId) REFERENCES Meeting(meetId),

    CHECK (status IN ('pending', 'accepted', 'declined'))
);

-- ============================================
--  Action (polymorphic association)
--
--  NOTE: entityId + entityType form a polymorphic
--  reference where entityId points to a row in the
--  table named by entityType (e.g. entityId = 5,
--  entityType = 'Team' -> Team where teamId = 5).
--
--  Referential integrity for entityId is NOT enforced
--  at the database level. This is intentional so that audit
--  logs survive the deletion of the referenced entity
--  (e.g. "user X deleted Team 5" must remain even after
--  Team 5 no longer exists).
--
--  But we gotta admit that polymorphic associations have its own drawbacks
--  (see GitLab docs: https://docs.gitlab.com/development/database/polymorphic_associations/):
--    - No FK enforcement = data integrity is application-only
--    - Wasted space on repeated entityType strings = redundant data
--    - Queries always need a two-column filter = additional complexity
--    - One table mixes data with different semantics
--  The alternative is a separate table per entity type,
--  BUT for a small-scale audit log this is acceptable ig.
-- ============================================
CREATE TABLE Action (
    actionId     INTEGER      PRIMARY KEY AUTOINCREMENT,
    userId       INT          NOT NULL,
    actionDescr  TEXT,
    action       VARCHAR(20)  NOT NULL,
    entityId     INT,
    entityType   VARCHAR(50),
    fieldChanged VARCHAR(50),
    oldValue     TEXT,
    newValue     TEXT,
    timestamp    TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (userId) REFERENCES Users(userId),

    CHECK (action IN ('create', 'update', 'delete')),
    CHECK (entityType IN ('Users', 'Team', 'Employee', 'Department', 'Project', 'Meeting', 'Message', 'MeetingInvitation', 'TeamManager', 'DepartmentLeader', 'Team_Skill_Alloc', 'Team_Dependency', 'HealthCard', 'HealthSession', 'HealthVote', 'Notification', 'Notification_Recipient'))
);

-- ============================================
--  Message
-- ============================================
CREATE TABLE Message (
    messageId        INTEGER      PRIMARY KEY AUTOINCREMENT,
    userId           INT          NOT NULL,
    subject          VARCHAR(200),
    body             TEXT,
    createdAt        TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    sentAt           TIMESTAMP,
    status           VARCHAR(20)  NOT NULL,
    senderMsgDeleted BOOLEAN      NOT NULL DEFAULT FALSE,

    FOREIGN KEY (userId) REFERENCES Users(userId),

    CHECK (status IN ('draft', 'sent', 'fail'))
);

-- ============================================
--  Message_Recipient
-- ============================================
CREATE TABLE Message_Recipient (
    userId          INT     NOT NULL,
    messageId       INT     NOT NULL,
    isRead          BOOLEAN NOT NULL DEFAULT FALSE,
    recipMsgDeleted BOOLEAN NOT NULL DEFAULT FALSE,

    PRIMARY KEY (userId, messageId),
    FOREIGN KEY (userId)    REFERENCES Users(userId),
    FOREIGN KEY (messageId) REFERENCES Message(messageId)
);

-- ============================================
--  Notification
--
--  A system-generated notification about an event
--  (e.g. a new meeting, health session, or team
--  change). The content is stored once here;
--  recipients are tracked in Notification_Recipient,
--  mirroring the Message / Message_Recipient pattern.
--  A notification may target one user or be broadcast
--  to many, but must always have at least one
--  recipient which is enforced at the application layer.
--
--  E.g. Notification (1..1) --is for--> (1..*) Notification_Recipient
--
--  Polymorphic reference (entityId + entityType)
--  mirrors the Action table pattern.
-- ============================================
CREATE TABLE Notification (
    notifId    INTEGER      PRIMARY KEY AUTOINCREMENT,
    entityId   INT,
    entityType VARCHAR(50),
    message    TEXT         NOT NULL,
    createdAt  TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CHECK (entityType IN (
        'Meeting', 'MeetingInvitation', 'Message',
        'Team', 'HealthSession'
    ))
);

-- ============================================
--  Notification_Recipient (M:N junction)
--
--  Resolves the many-to-many relationship between
--  notifications and users. Each row means a
--  specific user has received a specific notification.
--  isRead tracks whether the user has seen it.
-- ============================================
CREATE TABLE Notification_Recipient (
    userId  INT     NOT NULL,
    notifId INT     NOT NULL,
    isRead  BOOLEAN NOT NULL DEFAULT FALSE,

    PRIMARY KEY (userId, notifId),
    FOREIGN KEY (userId)  REFERENCES Users(userId),
    FOREIGN KEY (notifId) REFERENCES Notification(notifId)
);