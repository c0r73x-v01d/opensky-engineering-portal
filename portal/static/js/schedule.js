(function () {
  'use strict';

  var RANGE_LABELS = {
    weekly: '16 Feb – 22 Feb',
    monthly: 'February 2026',
    upcoming: 'Next 30 days'
  };

  document.addEventListener('DOMContentLoaded', function () {
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
  });
})();
