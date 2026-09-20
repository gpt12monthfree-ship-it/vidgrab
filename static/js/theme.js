/* ═══════════════════════════════════════════
   Theme Engine — Animated Circular Wipe Transition
   ═══════════════════════════════════════════ */

(function () {
  const KEY = 'vg-theme';
  const root = document.documentElement;

  function applyIcon(theme) {
    document.querySelectorAll('[data-theme-toggle] i').forEach(i => {
      i.className = theme === 'dark' ? 'fa-solid fa-sun' : 'fa-solid fa-moon';
    });
  }

  // Initial paint (no animation on load)
  const initial = localStorage.getItem(KEY) || 'dark';
  root.setAttribute('data-theme', initial);
  applyIcon(initial);

  function switchTheme(x, y) {
    const current = root.getAttribute('data-theme');
    const next = current === 'dark' ? 'light' : 'dark';

    // Fallback for browsers without View Transitions API
    if (!document.startViewTransition) {
      root.setAttribute('data-theme', next);
      localStorage.setItem(KEY, next);
      applyIcon(next);
      return;
    }

    root.style.setProperty('--tx-x', x + 'px');
    root.style.setProperty('--tx-y', y + 'px');

    const transition = document.startViewTransition(() => {
      root.setAttribute('data-theme', next);
      localStorage.setItem(KEY, next);
      applyIcon(next);
    });

    transition.ready.then(() => {
      const endRadius = Math.hypot(
        Math.max(x, innerWidth - x),
        Math.max(y, innerHeight - y)
      );
      document.documentElement.animate(
        {
          clipPath: [
            `circle(0px at ${x}px ${y}px)`,
            `circle(${endRadius}px at ${x}px ${y}px)`
          ]
        },
        {
          duration: 650,
          easing: 'cubic-bezier(.22,1,.36,1)',
          pseudoElement: '::view-transition-new(root)'
        }
      );
    });
  }

  document.addEventListener('click', e => {
    const btn = e.target.closest('[data-theme-toggle]');
    if (!btn) return;
    const rect = btn.getBoundingClientRect();
    switchTheme(rect.left + rect.width / 2, rect.top + rect.height / 2);

    // Icon spin feedback
    btn.classList.add('spin-once');
    setTimeout(() => btn.classList.remove('spin-once'), 500);
  });
})();


/* ---------- Toast system (unchanged) ---------- */
window.toast = function (message, type = 'info', ms = 3800) {
  const stack = document.getElementById('toasts');
  if (!stack) return;

  const icons = {
    success: 'fa-circle-check',
    error: 'fa-circle-exclamation',
    info: 'fa-circle-info',
    warn: 'fa-triangle-exclamation'
  };

  const el = document.createElement('div');
  el.className = `toast toast-${type}`;
  el.innerHTML = `<i class="fa-solid ${icons[type] || icons.info}"></i><p>${message}</p>
                  <button class="toast-x" aria-label="Dismiss">&times;</button>`;
  stack.appendChild(el);

  const kill = () => {
    el.classList.add('out');
    setTimeout(() => el.remove(), 260);
  };
  el.querySelector('.toast-x').onclick = kill;
  setTimeout(kill, ms);
};