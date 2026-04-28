/*
 * OpenSky Home Dashboard
 * Handles: widget drag/drop reordering and resize cycling.
 *
 * Notes:
 *   - Profile modal lives in base.html; its logic is in profile.js.
 *   - Widget sizes are persisted to the server session via a small
 *     POST to /profile/update/ with a JSON body.
 */
(function () {
  'use strict';

  document.addEventListener('DOMContentLoaded', function () {

    // ═══════════════════════════════════════════════════════════════
    // Widget drag & drop reordering + resize cycling
    // ═══════════════════════════════════════════════════════════════
    var grid = document.getElementById('widget-grid');
    var dragKey = null;

    function cleanupDrag() {
      dragKey = null;
      if (grid) {
        grid.querySelectorAll('.wg-inner').forEach(function (el) {
          el.classList.remove('is-dragging', 'is-over');
        });
      }
    }

    function persistWidgetSizes() {
      if (!grid) return;
      var sizes = {};
      grid.querySelectorAll('.wg[data-widget]').forEach(function (wg) {
        var key = wg.dataset.widget;
        var label = wg.querySelector('.resize-label');
        if (key && label) sizes[key] = label.textContent.trim();
      });
      // Persist via the profile_update endpoint, form_type=widget_sizes.
      // We POST as JSON to keep the view simple; CSRF is required.
      var csrfCookie = document.cookie.split(';')
        .find(function (c) { return c.trim().startsWith('csrftoken='); });
      var csrf = csrfCookie ? csrfCookie.split('=')[1] : '';
      // No CSRF cookie? fall back silently — server will reject and the
      // user simply won't have their widget preferences persisted.
      fetch('/profile/update/', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': csrf,
        },
        body: JSON.stringify(sizes),
      }).catch(function () { /* swallow — non-critical */ });
    }

    if (grid) {
      grid.addEventListener('dragstart', function (e) {
        var wg = e.target.closest('.wg[data-widget]');
        if (!wg) return;
        dragKey = wg.dataset.widget;
        e.dataTransfer.effectAllowed = 'move';
        requestAnimationFrame(function () {
          var inner = wg.querySelector('.wg-inner');
          if (inner) inner.classList.add('is-dragging');
        });
      });

      grid.addEventListener('dragover', function (e) {
        e.preventDefault();
        e.dataTransfer.dropEffect = 'move';
        var wg = e.target.closest('.wg[data-widget]');
        if (wg && wg.dataset.widget !== dragKey) {
          var inner = wg.querySelector('.wg-inner');
          if (inner) inner.classList.add('is-over');
        }
      });

      grid.addEventListener('dragleave', function (e) {
        var wg = e.target.closest('.wg[data-widget]');
        if (wg) {
          var inner = wg.querySelector('.wg-inner');
          if (inner) inner.classList.remove('is-over');
        }
      });

      grid.addEventListener('drop', function (e) {
        e.preventDefault();
        var targetWg = e.target.closest('.wg[data-widget]');
        if (!targetWg || !dragKey) return;
        var targetKey = targetWg.dataset.widget;
        if (dragKey === targetKey) return;

        var dragEl = grid.querySelector('.wg[data-widget="' + dragKey + '"]');
        if (!dragEl) return;

        var all = Array.prototype.slice.call(grid.querySelectorAll('.wg[data-widget]'));
        var fromIdx = all.indexOf(dragEl);
        var toIdx = all.indexOf(targetWg);
        if (fromIdx < toIdx) targetWg.after(dragEl);
        else                 targetWg.before(dragEl);

        cleanupDrag();
      });

      grid.addEventListener('dragend', cleanupDrag);

      // Widget resize cycling: S → M → L → S ...
      grid.addEventListener('click', function (e) {
        var btn = e.target.closest('.resize-btn');
        if (!btn) return;
        e.stopPropagation();

        var sizes = btn.dataset.sizes.split(',');
        var labelEl = btn.querySelector('.resize-label');
        var current = labelEl ? labelEl.textContent.trim() : sizes[0];
        var nextIdx = (sizes.indexOf(current) + 1) % sizes.length;
        var next = sizes[nextIdx];

        if (labelEl) labelEl.textContent = next;
        var wgEl = btn.closest('.wg[data-widget]');
        if (wgEl) {
          wgEl.classList.remove('wg--s', 'wg--m', 'wg--l');
          wgEl.classList.add('wg--' + next.toLowerCase());
        }
        persistWidgetSizes();
      });
    }
  });
})();