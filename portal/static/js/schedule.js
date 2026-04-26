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

    function applyType(type) {
      form.setAttribute('data-meeting-type', type);
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
      foot.appendChild(buildFoot(d.myStatus || 'accepted'));
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
    setupModals();
    setupSegmented();
    setupMeetingTypeToggle();
    setupAttendeeRemoval();
    setupPanels();
  });
})();
