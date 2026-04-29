(function () {
  'use strict';

  var RANGE_LABELS = {
    weekly: '16 Feb – 22 Feb',
    monthly: 'February 2026',
    upcoming: 'Next 30 days'
  };

  function setupViewToggle() {
    var schedule = document.querySelector('.sky-schedule');
    var toolbar = document.querySelector('.sky-schedule__toolbar');
    if (!schedule || !toolbar) return;

    var pills = toolbar.querySelectorAll('[data-view-pill]');
    var rangeLabel = toolbar.querySelector('[data-role="range-label"]');

    pills.forEach(function (pill) {
      pill.addEventListener('click', function () {
        var view = pill.getAttribute('data-view-pill');
        if (!view) return;

        pills.forEach(function (other) {
          var isActive = other === pill;
          other.classList.toggle('is-active', isActive);
          other.setAttribute('aria-selected', isActive ? 'true' : 'false');
        });

        toolbar.setAttribute('data-view', view);
        schedule.setAttribute('data-view', view);

        if (rangeLabel && RANGE_LABELS[view]) {
          rangeLabel.textContent = RANGE_LABELS[view];
        }
      });
    });
  }

  function setupNavigator() {
    var toolbar = document.querySelector('.sky-schedule__toolbar');
    if (!toolbar) return;

    function shift(direction) {
      var view = toolbar.getAttribute('data-view') || 'weekly';
      var anchorStr = toolbar.getAttribute('data-anchor');
      var anchor = anchorStr ? new Date(anchorStr + 'T12:00:00') : new Date();
      if (direction === 0) {
        anchor = new Date();
      } else {
        var step = view === 'monthly' ? 0 : (view === 'upcoming' ? 21 : 7);
        if (view === 'monthly') {
          anchor.setMonth(anchor.getMonth() + direction);
        } else {
          anchor.setDate(anchor.getDate() + direction * step);
        }
      }
      var iso = anchor.getFullYear() + '-' +
        String(anchor.getMonth() + 1).padStart(2, '0') + '-' +
        String(anchor.getDate()).padStart(2, '0');
      var url = new URL(window.location.href);
      url.searchParams.set('anchor', iso);
      window.location.href = url.toString();
    }

    toolbar.querySelectorAll('[data-nav]').forEach(function (btn) {
      btn.addEventListener('click', function () {
        var nav = btn.getAttribute('data-nav');
        if (nav === 'prev') shift(-1);
        else if (nav === 'next') shift(+1);
        else if (nav === 'today') shift(0);
      });
    });
  }

  function setupModals() {
    var openTriggers = document.querySelectorAll('[data-modal-open]');
    if (!openTriggers.length) return;

    function openModal(modal) {
      // Move modal to <body> so no ancestor's containing block can scope its position:fixed
      if (modal.parentNode !== document.body) {
        document.body.appendChild(modal);
      }
      modal.hidden = false;
      document.body.style.overflow = 'hidden';
      var firstInput = modal.querySelector('input, textarea, select, button');
      if (firstInput) firstInput.focus();
    }

    function closeModal(modal) {
      modal.hidden = true;
      document.body.style.overflow = '';
    }

    function closeAllOpenModals() {
      document.querySelectorAll('.sky-modal').forEach(function (m) {
        if (!m.hidden) closeModal(m);
      });
    }

    openTriggers.forEach(function (trigger) {
      trigger.addEventListener('click', function () {
        var name = trigger.getAttribute('data-modal-open');
        var modal = document.querySelector('[data-modal="' + name + '"]');
        if (modal) openModal(modal);
      });
    });

    document.querySelectorAll('[data-modal-close]').forEach(function (btn) {
      btn.addEventListener('click', function () {
        var modal = btn.closest('.sky-modal');
        if (modal) closeModal(modal);
      });
    });

    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape') closeAllOpenModals();
    });
  }

  function setupSegmented() {
    document.querySelectorAll('[role="radiogroup"]').forEach(function (group) {
      var options = group.querySelectorAll('[role="radio"]');
      options.forEach(function (opt) {
        opt.addEventListener('click', function () {
          options.forEach(function (other) {
            var isActive = other === opt;
            other.classList.toggle('is-active', isActive);
            other.setAttribute('aria-checked', isActive ? 'true' : 'false');
          });
        });
      });
    });
  }

  function setupMeetingTypeToggle() {
    var form = document.querySelector('.sky-meeting-form');
    if (!form) return;
    var guests = form.querySelector('#mf-guests');
    var typeInput = form.querySelector('input[name="meeting_type"]');

    function applyType(type) {
      form.setAttribute('data-meeting-type', type);
      if (typeInput) typeInput.value = type;
      if (guests) {
        var key = type === 'personal' ? 'personalPlaceholder' : 'teamPlaceholder';
        if (guests.dataset[key]) guests.placeholder = guests.dataset[key];
      }
    }

    form.querySelectorAll('[data-meeting-type]').forEach(function (btn) {
      btn.addEventListener('click', function () {
        applyType(btn.getAttribute('data-meeting-type'));
      });
    });
  }

  function setupScheduleMeetingForm() {
    var form = document.querySelector('.sky-meeting-form');
    if (!form) return;

    var hostSelect = form.querySelector('#mf-host');
    var platformInput = form.querySelector('input[name="platform"]');
    var attendeeIdsInput = form.querySelector('input[name="attendee_ids"]');
    var teamSet = form.querySelector('[data-attendee-set="team"]');
    var personalSet = form.querySelector('[data-attendee-set="personal"]');

    var teamMembersByTeam = {};
    try { teamMembersByTeam = JSON.parse(form.dataset.teamMembers || '{}'); }
    catch (e) { teamMembersByTeam = {}; }

    // Render team-attendee chips for the chosen team.
    function renderTeamMembers() {
      if (!teamSet || !hostSelect) return;
      var members = teamMembersByTeam[hostSelect.value] || [];
      teamSet.innerHTML = '';
      members.forEach(function (m) {
        var li = document.createElement('li');
        li.className = 'sky-attendee';
        li.setAttribute('data-tone', 'team');
        li.setAttribute('data-user-id', String(m.user_id));
        li.innerHTML =
          '<span class="sky-attendee__dot"></span>' +
          '<span class="sky-attendee__name"></span>' +
          '<button type="button" class="sky-attendee__remove" aria-label="Remove">' +
            '<span class="sky-icon" data-icon="X" data-size="11"></span>' +
          '</button>';
        li.querySelector('.sky-attendee__name').textContent = m.name;
        li.querySelector('.sky-attendee__remove').addEventListener('click', function () {
          li.remove();
        });
        teamSet.appendChild(li);
      });
    }

    if (hostSelect) {
      renderTeamMembers();
      hostSelect.addEventListener('change', renderTeamMembers);
    }

    // ── Guest search dropdown ─────────────────────────────────────
    var guestsInput = form.querySelector('#mf-guests');
    var resultsList = form.querySelector('[data-slot="search-results"]');

    function activeAttendeeSet() {
      var type = form.getAttribute('data-meeting-type') || 'team';
      return form.querySelector('[data-attendee-set="' + type + '"]');
    }

    function existingIds() {
      var ids = {};
      form.querySelectorAll('.sky-attendee[data-user-id]').forEach(function (li) {
        ids[li.getAttribute('data-user-id')] = true;
      });
      return ids;
    }

    function buildChip(userId, name, tone) {
      var li = document.createElement('li');
      li.className = 'sky-attendee';
      li.setAttribute('data-tone', tone || 'team');
      li.setAttribute('data-user-id', String(userId));
      li.innerHTML =
        '<span class="sky-attendee__dot"></span>' +
        '<span class="sky-attendee__name"></span>' +
        '<button type="button" class="sky-attendee__remove" aria-label="Remove">' +
          '<span class="sky-icon" data-icon="X" data-size="11"></span>' +
        '</button>';
      li.querySelector('.sky-attendee__name').textContent = name;
      li.querySelector('.sky-attendee__remove').addEventListener('click', function () {
        li.remove();
      });
      return li;
    }

    function hideResults() {
      if (!resultsList) return;
      resultsList.innerHTML = '';
      resultsList.hidden = true;
    }

    function renderResults(items) {
      if (!resultsList) return;
      resultsList.innerHTML = '';
      if (!items.length) {
        var empty = document.createElement('li');
        empty.className = 'sky-attendee-search__empty';
        empty.textContent = 'No matches.';
        resultsList.appendChild(empty);
        resultsList.hidden = false;
        return;
      }
      var seen = existingIds();
      items.forEach(function (u) {
        if (seen[String(u.id)]) return;
        var li = document.createElement('li');
        li.className = 'sky-attendee-search__item';
        li.setAttribute('data-user-id', String(u.id));
        var nm = document.createElement('span');
        nm.className = 'sky-attendee-search__name';
        nm.textContent = u.name;
        var em = document.createElement('span');
        em.className = 'sky-attendee-search__email';
        em.textContent = u.email + (u.position ? ' · ' + u.position : '');
        li.appendChild(nm);
        li.appendChild(em);
        li.addEventListener('mousedown', function (ev) {
          ev.preventDefault();
          var set = activeAttendeeSet();
          if (!set) return;
          var type = form.getAttribute('data-meeting-type') || 'team';
          set.appendChild(buildChip(u.id, u.name, type === 'personal' ? 'blue' : 'team'));
          if (guestsInput) guestsInput.value = '';
          hideResults();
        });
        resultsList.appendChild(li);
      });
      resultsList.hidden = false;
    }

    var searchTimer = null;
    if (guestsInput) {
      guestsInput.addEventListener('input', function () {
        var q = guestsInput.value.trim();
        if (searchTimer) clearTimeout(searchTimer);
        if (q.length < 2) { hideResults(); return; }
        searchTimer = setTimeout(function () {
          fetch('/schedule/users/search/?q=' + encodeURIComponent(q), {
            credentials: 'same-origin',
            headers: { 'X-Requested-With': 'XMLHttpRequest' },
          })
          .then(function (r) { return r.ok ? r.json() : { results: [] }; })
          .then(function (body) { renderResults(body.results || []); })
          .catch(function () { hideResults(); });
        }, 220);
      });
      guestsInput.addEventListener('blur', function () {
        setTimeout(hideResults, 120);  // give mousedown time to fire
      });
    }

    // Sync the platform pill into the hidden input on click.
    form.querySelectorAll('.sky-platform[data-platform]').forEach(function (btn) {
      btn.addEventListener('click', function () {
        if (platformInput) platformInput.value = btn.getAttribute('data-platform');
      });
    });

    function collectAttendeeIds() {
      var type = form.getAttribute('data-meeting-type');
      var set = type === 'personal' ? personalSet : teamSet;
      if (!set) return [];
      var ids = [];
      set.querySelectorAll('[data-user-id]').forEach(function (li) {
        ids.push(li.getAttribute('data-user-id'));
      });
      return ids;
    }

    form.addEventListener('submit', function (e) {
      e.preventDefault();
      if (attendeeIdsInput) attendeeIdsInput.value = collectAttendeeIds().join(',');

      var data = new FormData(form);
      var token = (typeof getCsrfToken === 'function') ? getCsrfToken() : '';
      var submitBtn = form.querySelector('button[type="submit"]');
      if (submitBtn) submitBtn.disabled = true;

      fetch(form.action, {
        method: 'POST',
        credentials: 'same-origin',
        headers: { 'X-CSRFToken': token, 'X-Requested-With': 'XMLHttpRequest' },
        body: data,
      })
      .then(function (r) { return r.json().then(function (j) { return { ok: r.ok, body: j }; }); })
      .then(function (res) {
        if (submitBtn) submitBtn.disabled = false;
        if (!res.ok || !res.body || !res.body.ok) {
          var msg = 'Could not create meeting.';
          if (res.body && res.body.errors) {
            var first = Object.keys(res.body.errors)[0];
            var detail = res.body.errors[first];
            if (Array.isArray(detail)) detail = detail[0];
            if (typeof detail === 'object' && detail.message) detail = detail.message;
            msg = first + ': ' + detail;
          }
          if (typeof showToast === 'function') showToast(msg, 'error');
          return;
        }
        if (typeof showToast === 'function') showToast('Meeting scheduled.', 'success');
        window.location.reload();
      })
      .catch(function () {
        if (submitBtn) submitBtn.disabled = false;
        if (typeof showToast === 'function') showToast('Network error — try again.', 'error');
      });
    });
  }

  function setupAttendeeRemoval() {
    document.querySelectorAll('.sky-attendee__remove').forEach(function (btn) {
      btn.addEventListener('click', function () {
        var chip = btn.closest('.sky-attendee');
        if (chip) chip.remove();
      });
    });
  }

  function setupPanels() {
    var panel = document.querySelector('[data-panel="meeting"]');
    if (!panel) return;

    var PLATFORM_LABEL = { slack: 'Slack', zoom: 'Zoom', teams: 'Microsoft Teams', meet: 'Google Meet', office: 'Office' };
    var PLATFORM_ICON  = { slack: 'Hash', zoom: 'Video', teams: 'Video', meet: 'Video', office: 'Building' };

    function $(slot, root) { return (root || panel).querySelector('[data-slot="' + slot + '"]'); }

    function initials(name) {
      if (!name) return '';
      return name.split(/\s+/).filter(Boolean).slice(0, 2).map(function (w) { return w[0]; }).join('').toUpperCase();
    }

    function makeIcon(name, size) {
      var span = document.createElement('span');
      span.className = 'sky-icon';
      span.setAttribute('data-icon', name);
      span.setAttribute('data-size', String(size || 14));
      if (typeof SKY_ICONS !== 'undefined' && SKY_ICONS[name]) {
        span.innerHTML = SKY_ICONS[name](size || 14);
      }
      return span;
    }

    function buildTags(platform, type, cadence) {
      var frag = document.createDocumentFragment();

      var pill = document.createElement('span');
      pill.className = 'sky-pill sky-pill--platform';
      pill.setAttribute('data-platform', platform);
      var dot = document.createElement('span'); dot.className = 'sky-pill__dot';
      pill.appendChild(dot);
      pill.appendChild(document.createTextNode(PLATFORM_LABEL[platform] || platform));
      frag.appendChild(pill);

      if (type) {
        var typePill = document.createElement('span');
        typePill.className = 'sky-pill sky-pill--' + (type === 'personal' ? 'personal' : 'team');
        typePill.textContent = type === 'personal' ? 'PERSONAL' : 'TEAM';
        frag.appendChild(typePill);
      }

      if (cadence) {
        var cad = document.createElement('span');
        cad.className = 'sky-pill sky-pill--cadence';
        cad.appendChild(makeIcon('Repeat', 11));
        cad.appendChild(document.createTextNode(cadence));
        frag.appendChild(cad);
      }

      return frag;
    }

    function buildAttendee(name, role, status) {
      var li = document.createElement('li');
      li.className = 'sky-person';

      var avatar = document.createElement('span');
      avatar.className = 'sky-person__avatar';
      avatar.textContent = initials(name);
      li.appendChild(avatar);

      var info = document.createElement('div');
      info.className = 'sky-person__info';
      var nm = document.createElement('span');
      nm.className = 'sky-person__name';
      nm.textContent = name;
      info.appendChild(nm);
      if (role) {
        var rl = document.createElement('span');
        rl.className = 'sky-person__role';
        rl.textContent = role;
        info.appendChild(rl);
      }
      li.appendChild(info);

      if (status) {
        var st = document.createElement('span');
        st.className = 'sky-person__status sky-person__status--' + status;
        st.textContent = status[0].toUpperCase() + status.slice(1);
        li.appendChild(st);
      }
      return li;
    }

    function buildFoot(myStatus) {
      var foot = document.createDocumentFragment();
      function btn(variant, label, icon) {
        var b = document.createElement('button');
        b.type = 'button';
        b.className = 'sky-btn ' + variant + ' sky-panel__foot-btn';
        if (icon) b.appendChild(makeIcon(icon, 14));
        b.appendChild(document.createTextNode(label));
        return b;
      }
      if (myStatus === 'pending') {
        foot.appendChild(btn('sky-panel__accept', 'Accept', 'Check'));
        foot.appendChild(btn('sky-panel__decline-outline', 'Decline', 'XCircle'));
      } else if (myStatus === 'declined') {
        foot.appendChild(btn('sky-panel__accept-full', 'Accept', 'Check'));
      } else {
        foot.appendChild(btn('sky-panel__decline', 'Decline', 'XCircle'));
      }
      return foot;
    }

    function populate(trigger) {
      var d = trigger.dataset;

      $('title').textContent = d.title || '';
      $('date').textContent = d.date || '';
      $('time').textContent = d.time || '';

      var tags = $('tags');
      tags.innerHTML = '';
      tags.appendChild(buildTags(d.platform, d.type, d.cadence));

      var pTone = $('platform-tone');
      pTone.setAttribute('data-tone', d.platform || '');
      var pIcon = $('platform-icon');
      var iconName = PLATFORM_ICON[d.platform] || 'Video';
      pIcon.setAttribute('data-icon', iconName);
      if (typeof SKY_ICONS !== 'undefined' && SKY_ICONS[iconName]) {
        pIcon.innerHTML = SKY_ICONS[iconName](14);
      }
      $('platform-name').textContent = PLATFORM_LABEL[d.platform] || d.platform || '';

      if (d.host) {
        $('host-row').style.display = '';
        $('host').textContent = d.host;
      } else {
        $('host-row').style.display = 'none';
      }

      if (d.organizer) {
        $('organizer-section').style.display = '';
        $('organizer-initials').textContent = initials(d.organizer);
        $('organizer-name').textContent = d.organizer;
        $('organizer-role').textContent = d.organizerRole || '';
      } else {
        $('organizer-section').style.display = 'none';
      }

      if (d.agenda) {
        $('agenda-section').style.display = '';
        $('agenda').textContent = d.agenda;
      } else {
        $('agenda-section').style.display = 'none';
      }

      var attendees = [];
      try { attendees = d.attendees ? JSON.parse(d.attendees) : []; } catch (e) { attendees = []; }
      $('attendees-label').textContent = 'ATTENDEES (' + attendees.length + ')';
      var ul = $('attendees');
      ul.innerHTML = '';
      attendees.forEach(function (a) {
        ul.appendChild(buildAttendee(a.name, a.role, a.status));
      });

      var foot = $('foot');
      foot.innerHTML = '';
      if (d.isPast === '1' || d.isPast === 'true') {
        foot.style.display = 'none';
      } else {
        foot.style.display = '';
        foot.appendChild(buildFoot(d.myStatus || 'accepted'));
      }
    }

    var current = { meetId: null, status: 'accepted' };

    function openPanel(trigger) {
      populate(trigger);
      current.meetId = trigger.getAttribute('data-meet-id');
      current.status = trigger.getAttribute('data-my-status') || 'accepted';
      if (panel.parentNode !== document.body) {
        document.body.appendChild(panel);
      }
      panel.hidden = false;
      document.body.style.overflow = 'hidden';
    }

    function closePanel() {
      panel.hidden = true;
      document.body.style.overflow = '';
    }

    function refreshFootForStatus(newStatus) {
      var foot = $('foot');
      foot.innerHTML = '';
      foot.appendChild(buildFoot(newStatus));
    }

    function refreshSelfAttendeeRow(newStatus) {
      var ul = $('attendees');
      var rows = ul.querySelectorAll('.sky-person');
      for (var i = 0; i < rows.length; i++) {
        var nameEl = rows[i].querySelector('.sky-person__name');
        if (nameEl && /\(You\)/.test(nameEl.textContent)) {
          var stEl = rows[i].querySelector('.sky-person__status');
          if (stEl) {
            stEl.className = 'sky-person__status sky-person__status--' + newStatus;
            stEl.textContent = newStatus.charAt(0).toUpperCase() + newStatus.slice(1);
          }
          break;
        }
      }
    }

    function refreshCardsForMeeting(meetId, newStatus) {
      var label = newStatus.charAt(0).toUpperCase() + newStatus.slice(1);

      document.querySelectorAll('[data-meet-id="' + meetId + '"]').forEach(function (btn) {
        btn.setAttribute('data-my-status', newStatus);
      });

      document.querySelectorAll('.sky-event > [data-meet-id="' + meetId + '"]').forEach(function (trigger) {
        var card = trigger.closest('.sky-event');
        if (!card) return;
        var pill = card.querySelector('.sky-event__status');
        if (pill) {
          pill.className = 'sky-event__status sky-event__status--' + newStatus;
          pill.textContent = label;
        }
      });

      document.querySelectorAll('.sky-meeting > [data-meet-id="' + meetId + '"]').forEach(function (trigger) {
        var card = trigger.closest('.sky-meeting');
        if (!card) return;
        var pill = card.querySelector('.sky-meeting__status');
        if (pill) {
          pill.className = 'sky-meeting__status sky-meeting__status--' + newStatus;
          pill.textContent = label;
        }
      });
    }

    function postRsvp(meetId, status, btn) {
      if (!meetId) return;
      btn.disabled = true;
      var url = '/schedule/meeting/' + encodeURIComponent(meetId) + '/rsvp/';
      var token = (typeof getCsrfToken === 'function') ? getCsrfToken() : '';
      fetch(url, {
        method: 'POST',
        credentials: 'same-origin',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': token,
          'X-Requested-With': 'XMLHttpRequest',
        },
        body: JSON.stringify({ status: status }),
      })
      .then(function (r) { return r.json().then(function (j) { return { ok: r.ok, body: j }; }); })
      .then(function (res) {
        btn.disabled = false;
        if (!res.ok || !res.body || !res.body.ok) {
          if (typeof showToast === 'function') {
            showToast((res.body && res.body.error) || 'Could not update RSVP.', 'error');
          }
          return;
        }
        current.status = res.body.status;
        refreshFootForStatus(current.status);
        refreshSelfAttendeeRow(current.status);
        refreshCardsForMeeting(current.meetId, current.status);
        if (typeof showToast === 'function') {
          showToast(current.status === 'accepted' ? 'Marked as attending.' : 'Marked as declined.', 'success');
        }
      })
      .catch(function () {
        btn.disabled = false;
        if (typeof showToast === 'function') showToast('Network error — try again.', 'error');
      });
    }

    panel.addEventListener('click', function (e) {
      var btn = e.target.closest('.sky-panel__accept, .sky-panel__accept-full, .sky-panel__decline, .sky-panel__decline-outline');
      if (!btn) return;
      var status = btn.classList.contains('sky-panel__decline') || btn.classList.contains('sky-panel__decline-outline')
        ? 'declined' : 'accepted';
      postRsvp(current.meetId, status, btn);
    });

    document.addEventListener('click', function (e) {
      var trigger = e.target.closest('[data-detail-open]');
      if (!trigger) return;
      e.stopPropagation();
      e.preventDefault();
      openPanel(trigger);
    });

    panel.querySelectorAll('[data-panel-close]').forEach(function (btn) {
      btn.addEventListener('click', closePanel);
    });

    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape' && !panel.hidden) closePanel();
    });
  }

  document.addEventListener('DOMContentLoaded', function () {
    setupViewToggle();
    setupNavigator();
    setupModals();
    setupSegmented();
    setupMeetingTypeToggle();
    setupAttendeeRemoval();
    setupScheduleMeetingForm();
    setupPanels();
  });
})();
