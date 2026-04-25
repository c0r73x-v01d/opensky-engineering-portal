(function () {
  'use strict';

  document.addEventListener('DOMContentLoaded', function () {
    var toolbar = document.querySelector('.sky-schedule__toolbar');
    if (!toolbar) return;

    var pills = toolbar.querySelectorAll('[data-view-pill]');

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
      });
    });
  });
})();
