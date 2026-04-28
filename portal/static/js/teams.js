/*
 * OpenSky — Teams page client logic.
 *
 * Reads the full teams payload from the <script id="teams-data"> JSON block
 * embedded in teams.html, then handles:
 *   - text search (TM-02, TM-03)
 *   - department / status / type filters + clear (TM-04 to TM-08)
 *   - grid <-> list view toggle (TM-09)
 *   - slide-in detail panel with full team info (TM-10, TM-11, TM-12)
 *   - Email Team / Schedule Meeting redirects (TM-13, TM-14)
 */
(function () {
  'use strict';

  // ── Read JSON payload emitted by {{ teams|json_script:"teams-data" }} ──
  var dataEl = document.getElementById('teams-data');
  var TEAMS = dataEl ? JSON.parse(dataEl.textContent) : [];
  var teamsById = Object.create(null);
  TEAMS.forEach(function (t) { teamsById[t.id] = t; });

  var currentView = 'grid';

  // ────────────────────────────────────────────────────────────────
  //  HTML escaping - every string from the JSON gets run through this
  //  before being injected into the panel via innerHTML.
  // ────────────────────────────────────────────────────────────────
  function esc(s) {
    if (s === null || s === undefined) return '';
    return String(s)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }

  // ────────────────────────────────────────────────────────────────
  //  Filtering (TM-02 to TM-08)
  // ────────────────────────────────────────────────────────────────
  function buildSearchHaystack(team) {
    return [
      team.team_name,
      team.department_name,
      team.manager_names.join(' '),
      team.skills_text,
      team.focus,
      team.jira_project,
    ].join(' ').toLowerCase();
  }

  function applyFilters() {
    var q = document.getElementById('team-search').value.trim().toLowerCase();
    var deptVal = document.getElementById('filter-dept').value;
    var statusVal = document.getElementById('filter-status').value;
    var typeVal = document.getElementById('filter-type').value;

    var visibleCount = 0;

    TEAMS.forEach(function (team) {
      var matchesSearch = !q || buildSearchHaystack(team).indexOf(q) !== -1;
      var matchesDept = deptVal === 'all' || String(team.department_id) === deptVal;
      var matchesStatus = statusVal === 'all' || team.status === statusVal;
      var matchesType = typeVal === 'all' || String(team.type_id) === typeVal;
      var visible = matchesSearch && matchesDept && matchesStatus && matchesType;

      // Both the grid card and the list row carry data-team-id; toggle both.
      var nodes = document.querySelectorAll(
        '.team-item[data-team-id="' + team.id + '"]'
      );
      for (var i = 0; i < nodes.length; i++) {
        nodes[i].style.display = visible ? '' : 'none';
      }
      if (visible) visibleCount++;
    });

    document.getElementById('result-count').textContent =
      'Showing ' + visibleCount + ' of ' + TEAMS.length + ' teams';
    document.getElementById('no-results').style.display =
      visibleCount === 0 ? 'block' : 'none';
  }

  function setupSearch() {
    var input = document.getElementById('team-search');
    if (input) input.addEventListener('input', applyFilters);
  }

  function setupFilterPanel() {
    var toggle = document.getElementById('toggle-filters');
    var panel = document.getElementById('filter-panel');
    if (toggle && panel) {
      toggle.addEventListener('click', function () {
        panel.classList.toggle('filter-panel--open');
      });
    }
    ['filter-dept', 'filter-status', 'filter-type'].forEach(function (id) {
      var sel = document.getElementById(id);
      if (sel) sel.addEventListener('change', applyFilters);
    });
    var clearBtn = document.getElementById('filter-clear');
    if (clearBtn) {
      clearBtn.addEventListener('click', function () {
        document.getElementById('team-search').value = '';
        document.getElementById('filter-dept').value = 'all';
        document.getElementById('filter-status').value = 'all';
        document.getElementById('filter-type').value = 'all';
        applyFilters();
      });
    }
  }

  // ────────────────────────────────────────────────────────────────
  //  View toggle (TM-09)
  // ────────────────────────────────────────────────────────────────
  function setupViewToggle() {
    var container = document.getElementById('teams-container');
    var btns = document.querySelectorAll('.view-toggle-btn');
    btns.forEach(function (btn) {
      btn.addEventListener('click', function () {
        var view = btn.getAttribute('data-view');
        if (!view || view === currentView) return;
        currentView = view;
        container.className = view === 'list' ? 'teams-list' : 'teams-grid';
        btns.forEach(function (other) {
          other.classList.toggle(
            'view-toggle-btn--active', other === btn
          );
        });
      });
    });
  }

  // ────────────────────────────────────────────────────────────────
  //  Detail panel renderers — markup style mirrors the Organisation
  //  page so the two slide-panels feel like one consistent surface.
  // ────────────────────────────────────────────────────────────────
  function statusModifier(status) {
    if (status === 'active') return 'positive';
    if (status === 'restructuring') return 'attention';
    return 'grey';
  }

  function renderActionsRow(team) {
    var mod = statusModifier(team.status);
    return (
      '<div class="tm-detail__actions">' +
        '<span class="tm-detail-status tm-detail-status--' + mod + '">● ' +
          esc(team.status_display || team.status) +
        '</span>' +
        '<button id="action-email" class="sky-btn sky-btn--primary" type="button">' +
          '<span class="sky-icon" data-icon="Mail" data-size="14"></span> Email Team' +
        '</button>' +
        '<button id="action-schedule" class="sky-btn sky-btn--primary" type="button">' +
          '<span class="sky-icon" data-icon="Calendar" data-size="14"></span> Schedule Meeting' +
        '</button>' +
      '</div>'
    );
  }

  function renderInfoPill(label, value) {
    return (
      '<div class="tm-info-pill">' +
        '<div class="tm-info-pill__label">' + esc(label) + '</div>' +
        '<div class="tm-info-pill__value">' + esc(value || 'Not specified') + '</div>' +
      '</div>'
    );
  }

  function renderMissionSection(team) {
    return (
      '<div class="tm-detail__section">' +
        '<h3 class="tm-detail__section-title">Mission &amp; Responsibilities</h3>' +
        renderInfoPill('Purpose', team.description || 'No team description recorded.') +
        renderInfoPill('Responsibilities', team.responsibilities || 'Responsibilities not yet recorded.') +
      '</div>'
    );
  }

  function renderTeamInfoSection(team) {
    return (
      '<div class="tm-detail__section">' +
        '<h3 class="tm-detail__section-title">Team Information</h3>' +
        '<div class="tm-detail__grid">' +
          renderInfoPill('Manager', team.manager_name) +
          renderInfoPill('Status', team.status_display || team.status) +
          renderInfoPill('Agile Practice', team.agile_practice) +
          renderInfoPill('Contact Channel', team.comm_channel) +
          renderInfoPill('Focus Area', team.focus) +
          renderInfoPill('Workstream', team.workstream) +
        '</div>' +
      '</div>'
    );
  }

  function renderSkillsSection(team) {
    if (!team.skills.length) {
      return (
        '<div class="tm-detail__section">' +
          '<h3 class="tm-detail__section-title">Skills</h3>' +
          '<p class="tm-empty">No skills tagged.</p>' +
        '</div>'
      );
    }
    return (
      '<div class="tm-detail__section">' +
        '<h3 class="tm-detail__section-title">Skills</h3>' +
        '<div style="display: flex; flex-wrap: wrap; gap: var(--sky-sp1);">' +
          team.skills.map(function (s) {
            return '<span class="skill-pill">' + esc(s) + '</span>';
          }).join('') +
        '</div>' +
      '</div>'
    );
  }

  function renderMembersSection(team) {
    if (!team.members.length) {
      return (
        '<div class="tm-detail__section">' +
          '<h3 class="tm-detail__section-title">Team Members</h3>' +
          '<p class="tm-empty">No members assigned.</p>' +
        '</div>'
      );
    }
    return (
      '<div class="tm-detail__section">' +
        '<h3 class="tm-detail__section-title">Team Members (' + team.member_count + ')</h3>' +
        team.members.map(function (m) {
          var avatarMod = m.is_manager ? ' tm-member-avatar--manager' : '';
          var managerTag = m.is_manager
            ? ' <span class="skill-pill skill-pill--manager">Manager</span>' : '';
          var avatarInner = m.avatar_url
            ? '<img src="' + esc(m.avatar_url) + '" alt="" />'
            : esc(m.initials || '?');
          return (
            '<div class="tm-member-row">' +
              '<div class="tm-member-avatar' + avatarMod + '">' + avatarInner + '</div>' +
              '<div style="flex: 1;">' +
                '<span class="tm-member-name">' + esc(m.name) + '</span>' +
                '<span class="tm-member-pos">' + esc(m.position) + '</span>' +
                managerTag +
                (m.email ? '<div class="tm-member-email">' + esc(m.email) + '</div>' : '') +
              '</div>' +
            '</div>'
          );
        }).join('') +
      '</div>'
    );
  }

  function renderReposSection(team) {
    if (!team.repos.length) {
      return (
        '<div class="tm-detail__section">' +
          '<h3 class="tm-detail__section-title">Code Repositories</h3>' +
          '<p class="tm-empty">No repositories recorded.</p>' +
        '</div>'
      );
    }
    return (
      '<div class="tm-detail__section">' +
        '<h3 class="tm-detail__section-title">Code Repositories (' + team.repo_count + ')</h3>' +
        team.repos.map(function (r) {
          var label = r.url
            ? '<a href="' + esc(r.url) + '" target="_blank" rel="noopener">' + esc(r.url) + '</a>'
            : esc(r.name);
          var mainBadge = r.is_main ? '<span class="tm-repo-main">Main</span>' : '';
          return (
            '<div class="tm-repo-row">' +
              '<span class="tm-repo-url">' + label + '</span>' +
              mainBadge +
            '</div>'
          );
        }).join('') +
      '</div>'
    );
  }

  function renderDependenciesSection(team) {
    var hasAny = team.upstream.length || team.downstream.length;
    if (!hasAny) {
      return (
        '<div class="tm-detail__section">' +
          '<h3 class="tm-detail__section-title">Dependencies</h3>' +
          '<p class="tm-empty">No dependencies recorded.</p>' +
        '</div>'
      );
    }
    var rows = '';
    rows += team.upstream.map(function (d) {
      return (
        '<div class="tm-dep-row tm-dep-row--up">' +
          '<span class="tm-dep-arrow--up">→</span>' +
          '<span class="tm-dep-name">Depends on ' + esc(d.name) + '</span>' +
          (d.dep_type ? '<span class="tm-dep-meta">' + esc(d.dep_type) + '</span>' : '') +
        '</div>'
      );
    }).join('');
    rows += team.downstream.map(function (d) {
      return (
        '<div class="tm-dep-row tm-dep-row--down">' +
          '<span class="tm-dep-arrow--down">←</span>' +
          '<span class="tm-dep-name">' + esc(d.name) + ' depends on this team</span>' +
          (d.dep_type ? '<span class="tm-dep-meta">' + esc(d.dep_type) + '</span>' : '') +
        '</div>'
      );
    }).join('');
    return (
      '<div class="tm-detail__section">' +
        '<h3 class="tm-detail__section-title">Dependencies</h3>' +
        rows +
      '</div>'
    );
  }

  function renderQuickLinksSection(team) {
    var rows = [];
    if (team.standup_link) {
      rows.push(
        '<div class="tm-ql-row">' +
          '<span class="tm-ql-label">Standup</span>' +
          '<span class="tm-ql-value"><a href="' + esc(team.standup_link) +
            '" target="_blank" rel="noopener">' + esc(team.standup_link) + '</a>' +
            (team.standup_time ? ' (' + esc(team.standup_time) + ')' : '') +
          '</span>' +
        '</div>'
      );
    }
    if (team.jira_link) {
      rows.push(
        '<div class="tm-ql-row">' +
          '<span class="tm-ql-label">Jira</span>' +
          '<span class="tm-ql-value"><a href="' + esc(team.jira_link) +
            '" target="_blank" rel="noopener">' +
            esc(team.jira_project || team.jira_link) + '</a></span>' +
        '</div>'
      );
    }
    if (team.team_wiki) {
      rows.push(
        '<div class="tm-ql-row">' +
          '<span class="tm-ql-label">Wiki</span>' +
          '<span class="tm-ql-value"><a href="' + esc(team.team_wiki) +
            '" target="_blank" rel="noopener">' + esc(team.team_wiki) + '</a></span>' +
        '</div>'
      );
    }
    if (!rows.length) return '';
    return (
      '<div class="tm-detail__section">' +
        '<h3 class="tm-detail__section-title">Quick Links</h3>' +
        rows.join('') +
      '</div>'
    );
  }

  function renderDatesSection(team) {
    return (
      '<div class="tm-detail__section">' +
        '<h3 class="tm-detail__section-title">Dates</h3>' +
        '<div class="tm-detail__grid">' +
          renderInfoPill('Created', team.created_at || '—') +
          renderInfoPill('Updated', team.updated_at || '—') +
          (team.disbanded_at ? renderInfoPill('Disbanded', team.disbanded_at) : '') +
        '</div>' +
      '</div>'
    );
  }

  function renderPanelBody(team) {
    return (
      renderActionsRow(team) +
      renderMissionSection(team) +
      renderTeamInfoSection(team) +
      renderSkillsSection(team) +
      renderMembersSection(team) +
      renderReposSection(team) +
      renderDependenciesSection(team) +
      renderQuickLinksSection(team) +
      renderDatesSection(team)
    );
  }

  function openPanel(teamId) {
    var team = teamsById[teamId];
    if (!team) return;

    document.getElementById('panel-team-name').textContent = team.team_name;
    document.getElementById('panel-subtitle').textContent =
      team.department_name + ' • ' + team.member_count + ' engineer' +
      (team.member_count === 1 ? '' : 's');

    var typeBadge = document.getElementById('panel-type-badge');
    typeBadge.innerHTML = team.type_name
      ? '<span class="tm-type-badge">' + esc(team.type_name) + '</span>'
      : '';

    var body = document.getElementById('panel-body');
    body.innerHTML = renderPanelBody(team);

    // Re-hydrate any [data-icon] spans inside the freshly injected markup
    // via the SKY_ICONS registry (loaded by base.html).
    if (typeof SKY_ICONS !== 'undefined') {
      body.querySelectorAll('.sky-icon[data-icon]').forEach(function (el) {
        var name = el.dataset.icon;
        var size = parseInt(el.dataset.size, 10) || 18;
        if (SKY_ICONS[name]) el.innerHTML = SKY_ICONS[name](size);
      });
    }

    // Wire action buttons (TM-13, TM-14).
    var emailBtn = document.getElementById('action-email');
    var scheduleBtn = document.getElementById('action-schedule');
    if (emailBtn) {
      emailBtn.addEventListener('click', function () {
        window.location.href = '/messages/';
      });
    }
    if (scheduleBtn) {
      scheduleBtn.addEventListener('click', function () {
        window.location.href = '/schedule/';
      });
    }

    document.getElementById('detail-panel').classList.add('sky-slide-panel--open');
  }

  function closePanel() {
    document.getElementById('detail-panel').classList.remove('sky-slide-panel--open');
  }

  function setupDetailPanel() {
    document.querySelectorAll('.team-item').forEach(function (el) {
      el.addEventListener('click', function () {
        var id = parseInt(el.getAttribute('data-team-id'), 10);
        if (!isNaN(id)) openPanel(id);
      });
    });
    var closeBtn = document.getElementById('panel-close-btn');
    if (closeBtn) closeBtn.addEventListener('click', closePanel);
    var backdrop = document.getElementById('panel-overlay-bg');
    if (backdrop) backdrop.addEventListener('click', closePanel);
    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape') closePanel();
    });
  }

  // ────────────────────────────────────────────────────────────────
  //  Boot
  // ────────────────────────────────────────────────────────────────
  document.addEventListener('DOMContentLoaded', function () {
    setupSearch();
    setupFilterPanel();
    setupViewToggle();
    setupDetailPanel();
  });
})();
