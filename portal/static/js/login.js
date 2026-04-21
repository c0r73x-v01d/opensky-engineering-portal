/*
 * OpenSky auth screen — three-panel switcher (login / register / forgot),
 * password reveal toggles, and a small password-strength meter.
 */
(function () {
  'use strict';

  function show(section) {
    document.querySelectorAll('.auth-view-section').forEach(el => {
      el.classList.toggle('active', el.id === 'view' + section);
    });
  }

  document.addEventListener('DOMContentLoaded', () => {
    /* Respect server-side hint about which panel to show (e.g. after a
     * failed registration so the user sees their own form and errors). */
    if (window.__OPENSKY_ACTIVE_AUTH_VIEW__) {
      show(window.__OPENSKY_ACTIVE_AUTH_VIEW__);
    }

    /* Panel switching */
    document.querySelectorAll('[data-goto]').forEach(btn => {
      btn.addEventListener('click', () => {
        const target = btn.dataset.goto;
        show(target.charAt(0).toUpperCase() + target.slice(1));
      });
    });

    /* Password reveal toggles */
    document.querySelectorAll('[data-toggle-pw]').forEach(btn => {
      btn.addEventListener('click', () => {
        const input = document.getElementById(btn.dataset.togglePw);
        if (!input) return;
        input.type = input.type === 'password' ? 'text' : 'password';
      });
    });

    /* Password strength meter */
    const regPw = document.getElementById('regPw');
    const strengthHost = document.getElementById('regStrength');
    if (regPw && strengthHost) {
      strengthHost.className = 'auth-strength';
      strengthHost.innerHTML =
        '<div class="auth-strength__bars">' +
          '<div class="auth-strength__bar"></div>'.repeat(4) +
        '</div>' +
        '<div class="auth-strength__label">&nbsp;</div>';
      const bars = strengthHost.querySelectorAll('.auth-strength__bar');
      const label = strengthHost.querySelector('.auth-strength__label');
      regPw.addEventListener('input', () => {
        const pw = regPw.value;
        let score = 0;
        if (pw.length >= 8) score++;
        if (/[A-Z]/.test(pw)) score++;
        if (/[0-9]/.test(pw)) score++;
        if (/[^A-Za-z0-9]/.test(pw)) score++;
        const tiers = [
          ['', 'var(--sky-grey10)'],
          ['Weak',   'var(--sky-negative)'],
          ['Fair',   'var(--sky-attention)'],
          ['Good',   'var(--sky-primary)'],
          ['Strong', 'var(--sky-positive)'],
        ];
        const [text, colour] = tiers[score];
        bars.forEach((b, i) => b.style.background = i < score ? colour : 'var(--sky-grey10)');
        label.textContent = text || '\u00A0';
        label.style.color = colour;
      });
    }

    /* Admin/User toggle is cosmetic — form always posts to the same endpoint. */
    document.querySelectorAll('.sky-toggle__btn').forEach(btn => {
      btn.addEventListener('click', () => {
        document.querySelectorAll('.sky-toggle__btn').forEach(b =>
          b.classList.remove('sky-toggle__btn--active'));
        btn.classList.add('sky-toggle__btn--active');
      });
    });
  });
})();
