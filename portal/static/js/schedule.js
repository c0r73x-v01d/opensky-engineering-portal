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

    function openPanel(trigger) {
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
    setupAttendeeRemoval();
    setupPanels();
  });
})();
