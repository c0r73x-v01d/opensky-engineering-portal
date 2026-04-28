/*
 * OpenSky — Profile modal client logic.
 *
 * Loaded on every authenticated page from base.html. Handles:
 *   - Open / close the modal (triggered from the navbar avatar dropdown)
 *   - Tab switching (Personal / Security / My Team)
 *   - Password visibility toggle on the Security tab
 *   - Avatar file picker - clicking the camera button opens the hidden
 *     file input, and the form submits when the user picks a file
 *
 * The modal data is rendered server-side from the nav_context processor;
 * this script just handles UI state.
 */
(function () {
  'use strict';

  document.addEventListener('DOMContentLoaded', function () {
    var modal = document.getElementById('profile-modal');
    if (!modal) return;  // anonymous user, no modal in DOM

    // ── Open / close ─────────────────────────────────────────────
    var openBtn = document.getElementById('view-profile-btn');
    var closeBtn = document.getElementById('close-profile-btn');

    function openModal(e) {
      if (e) e.stopPropagation();
      modal.classList.add('sky-overlay--open');
    }
    function closeModal() {
      modal.classList.remove('sky-overlay--open');
    }

    if (openBtn) openBtn.addEventListener('click', openModal);
    if (closeBtn) closeBtn.addEventListener('click', closeModal);

    // Click on the backdrop (the .sky-overlay element itself, not its child) closes.
    modal.addEventListener('click', function (e) {
      if (e.target === modal) closeModal();
    });

    // Escape key closes.
    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape' && modal.classList.contains('sky-overlay--open')) {
        closeModal();
      }
    });

    // ── Tab switching ────────────────────────────────────────────
    var TAB_LABELS = { personal: 'Personal', security: 'Security', team: 'My Team' };
    var titleEl = document.getElementById('profile-panel-title');

    document.querySelectorAll('.profile-tab-btn').forEach(function (btn) {
      btn.addEventListener('click', function () {
        var tab = btn.dataset.tab;
        document.querySelectorAll('.profile-tab-btn').forEach(function (b) {
          b.classList.remove('is-active');
        });
        btn.classList.add('is-active');

        document.querySelectorAll('.profile-panel').forEach(function (p) {
          p.style.display = 'none';
        });
        var panel = document.getElementById('panel-' + tab);
        if (panel) panel.style.display = 'block';

        if (titleEl) titleEl.textContent = TAB_LABELS[tab] || tab;
      });
    });

    // ── Password visibility toggle ───────────────────────────────
    document.querySelectorAll('.toggle-pw-btn').forEach(function (btn) {
      btn.addEventListener('click', function (e) {
        e.preventDefault();
        e.stopPropagation();
        var wrap = btn.closest('.sky-field__wrap');
        var input = wrap ? wrap.querySelector('input[type="password"], input[type="text"]') : null;
        if (!input) return;
        var wasPassword = input.type === 'password';
        input.type = wasPassword ? 'text' : 'password';
        var iconEl = btn.querySelector('.sky-icon');
        if (iconEl && typeof SKY_ICONS !== 'undefined') {
          iconEl.dataset.icon = wasPassword ? 'EyeOff' : 'Eye';
          var iconName = iconEl.dataset.icon;
          var size = parseInt(iconEl.dataset.size, 10) || 16;
          if (SKY_ICONS[iconName]) iconEl.innerHTML = SKY_ICONS[iconName](size);
        }
      });
    });

    // ── Avatar upload trigger ────────────────────────────────────
    // Camera button → opens the hidden file input. Picking a file
    // submits the personal form so the upload reaches profile_update.
    var cameraBtn = document.getElementById('profile-avatar-trigger');
    var fileInput = document.getElementById('profile-avatar-file');
    var personalForm = document.getElementById('profile-personal-form');

    if (cameraBtn && fileInput) {
      cameraBtn.addEventListener('click', function (e) {
        e.preventDefault();
        fileInput.click();
      });
      fileInput.addEventListener('change', function () {
        if (fileInput.files && fileInput.files.length > 0 && personalForm) {
          personalForm.submit();
        }
      });
    }
  });
})();
