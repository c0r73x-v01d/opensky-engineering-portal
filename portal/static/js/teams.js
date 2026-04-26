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
  //  Detail panel (TM-10, TM-11, TM-12)
  // ────────────────────────────────────────────────────────────────
  function renderMembersList(members) {
    if (!members.length) {
      return '<p class="panel-section__empty">No members assigned.</p>';
    }
    return '<ul class="panel-list">' + members.map(function (m) {
      return (
        '<li>' +
          '<span>' + esc(m.name) + ' <span style="color: var(--sky-grey40);">— ' + esc(m.position) + '</span></span>' +
          (m.is_manager ? '<span class="skill-pill skill-pill--manager">Manager</span>' : '') +
        '</li>'
      );
    }).join('') + '</ul>';
  }

  function renderReposList(repos) {
    if (!repos.length) {
      return '<p class="panel-section__empty">No repositories.</p>';
    }
    return '<ul class="panel-list">' + repos.map(function (r) {
      var name = r.url
        ? '<a href="' + esc(r.url) + '" target="_blank" rel="noopener">' + esc(r.name) + '</a>'
        : esc(r.name);
      return (
        '<li>' +
          '<span>' + name + (r.is_main ? ' <span class="type-badge">Main</span>' : '') + '</span>' +
        '</li>'
      );
    }).join('') + '</ul>';
  }

  function renderDepList(deps) {
    if (!deps.length) {
      return '<p class="panel-section__empty">None.</p>';
    }
    return '<ul class="panel-list">' + deps.map(function (d) {
      var typeBadge = d.type
        ? ' <span class="type-badge">' + esc(d.type) + '</span>' : '';
      var depType = d.dep_type
        ? '<span style="color: var(--sky-grey40); font-size: 11px;">' + esc(d.dep_type) + '</span>' : '';
      return (
        '<li>' +
          '<span>' + esc(d.name) + typeBadge + '</span>' +
          depType +
        '</li>'
      );
    }).join('') + '</ul>';
  }

  function renderQuickLinks(team) {
    var items = [];
    if (team.standup_link) {
      items.push(
        '<li><a href="' + esc(team.standup_link) + '" target="_blank" rel="noopener">Join standup' +
        (team.standup_time ? ' (' + esc(team.standup_time) + ')' : '') + '</a></li>'
      );
    }
    if (team.jira_link) {
      items.push(
        '<li><a href="' + esc(team.jira_link) + '" target="_blank" rel="noopener">Jira board' +
        (team.jira_project ? ' — ' + esc(team.jira_project) : '') + '</a></li>'
      );
    }
    if (team.comm_channel) {
      items.push('<li><span>Channel: ' + esc(team.comm_channel) + '</span></li>');
    }
    if (team.team_wiki) {
      items.push(
        '<li><a href="' + esc(team.team_wiki) + '" target="_blank" rel="noopener">Team wiki</a></li>'
      );
    }
    if (!items.length) {
      return '<p class="panel-section__empty">No quick links available.</p>';
    }
    return '<ul class="panel-list">' + items.join('') + '</ul>';
  }

  function renderDetails(team) {
    var concurrent = (team.concurrent_projs === null || team.concurrent_projs === undefined)
      ? '—' : esc(String(team.concurrent_projs));
    return (
      '<dl class="panel-meta">' +
        '<dt>Department</dt><dd>' + esc(team.department_name) + '</dd>' +
        (team.type_name ? '<dt>Type</dt><dd>' + esc(team.type_name) + '</dd>' : '') +
        (team.focus ? '<dt>Focus</dt><dd>' + esc(team.focus) + '</dd>' : '') +
        (team.workstream ? '<dt>Workstream</dt><dd>' + esc(team.workstream) + '</dd>' : '') +
        (team.agile_practice ? '<dt>Agile</dt><dd>' + esc(team.agile_practice) + '</dd>' : '') +
        '<dt>Concurrent</dt><dd>' + concurrent + '</dd>' +
      '</dl>'
    );
  }

  function renderDates(team) {
    return (
      '<dl class="panel-meta">' +
        '<dt>Created</dt><dd>' + esc(team.created_at) + '</dd>' +
        '<dt>Updated</dt><dd>' + esc(team.updated_at) + '</dd>' +
        (team.disbanded_at ? '<dt>Disbanded</dt><dd>' + esc(team.disbanded_at) + '</dd>' : '') +
      '</dl>'
    );
  }

  function renderPanelBody(team) {
    return (
      '<section class="panel-section">' +
        '<h3 class="panel-section__title">Mission</h3>' +
        (team.description
          ? '<p class="panel-section__text">' + esc(team.description) + '</p>'
          : '<p class="panel-section__empty">No description.</p>') +
      '</section>' +

      '<section class="panel-section">' +
        '<h3 class="panel-section__title">Responsibilities</h3>' +
        (team.responsibilities
          ? '<p class="panel-section__text">' + esc(team.responsibilities) + '</p>'
          : '<p class="panel-section__empty">No responsibilities recorded.</p>') +
      '</section>' +

      '<section class="panel-section">' +
        '<h3 class="panel-section__title">Team Details</h3>' +
        renderDetails(team) +
      '</section>' +

      '<section class="panel-section">' +
        '<h3 class="panel-section__title">Members (' + team.member_count + ')</h3>' +
        renderMembersList(team.members) +
      '</section>' +

      '<section class="panel-section">' +
        '<h3 class="panel-section__title">Skills</h3>' +
        (team.skills.length
          ? '<div class="team-card__skills">' + team.skills.map(function (s) {
              return '<span class="skill-pill">' + esc(s) + '</span>';
            }).join('') + '</div>'
          : '<p class="panel-section__empty">No skills tagged.</p>') +
      '</section>' +

      '<section class="panel-section">' +
        '<h3 class="panel-section__title">Repositories (' + team.repo_count + ')</h3>' +
        renderReposList(team.repos) +
      '</section>' +

      '<section class="panel-section">' +
        '<h3 class="panel-section__title">Dependencies</h3>' +
        '<p class="panel-deps__heading">Upstream (' + team.upstream.length + ')</p>' +
        renderDepList(team.upstream) +
        '<p class="panel-deps__heading">Downstream (' + team.downstream.length + ')</p>' +
        renderDepList(team.downstream) +
      '</section>' +

      '<section class="panel-section">' +
        '<h3 class="panel-section__title">Quick Links</h3>' +
        renderQuickLinks(team) +
      '</section>' +

      '<section class="panel-section">' +
        '<h3 class="panel-section__title">Dates</h3>' +
        renderDates(team) +
      '</section>' +

      '<div class="panel-actions">' +
        '<button id="action-email" class="sky-btn sky-btn--primary">Email Team</button>' +
        '<button id="action-schedule" class="sky-btn sky-btn--ghost">Schedule Meeting</button>' +
      '</div>'
    );
  }

  function openPanel(teamId) {
    var team = teamsById[teamId];
    if (!team) return;

    document.getElementById('panel-team-name').textContent = team.team_name;
    document.getElementById('panel-subtitle').textContent =
      team.department_name + ' · ' + team.manager_name;

    var body = document.getElementById('panel-body');
    body.innerHTML = renderPanelBody(team);

    // Re-render any newly added [data-icon] spans inside the panel via the
    // SKY_ICONS registry (loaded by base.html).
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
