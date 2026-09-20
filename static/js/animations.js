/* ═══════════════════════════════════════════
   VidGrab Pro — Animation Engine
   Scroll reveals, counters, magnetic buttons, ripples
   ═══════════════════════════════════════════ */

/* ---------- 1. Scroll Reveal (Intersection Observer) ---------- */
(function scrollReveal() {
  const els = document.querySelectorAll('[data-reveal]');
  if (!els.length) return;

  const io = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
      if (entry.isIntersecting) {
        const delay = entry.target.dataset.delay || 0;
        setTimeout(() => entry.target.classList.add('is-visible'), delay);
        io.unobserve(entry.target);
      }
    });
  }, { threshold: 0.15, rootMargin: '0px 0px -60px 0px' });

  els.forEach(el => io.observe(el));
})();


/* ---------- 2. Stagger children automatically ---------- */
(function staggerGroups() {
  document.querySelectorAll('[data-stagger]').forEach(group => {
    [...group.children].forEach((child, i) => {
      child.setAttribute('data-reveal', '');
      child.setAttribute('data-delay', i * 90);
    });
  });
  // Re-run observer for newly tagged elements
  const els = document.querySelectorAll('[data-reveal]:not(.is-visible)');
  const io = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
      if (entry.isIntersecting) {
        const delay = entry.target.dataset.delay || 0;
        setTimeout(() => entry.target.classList.add('is-visible'), delay);
        io.unobserve(entry.target);
      }
    });
  }, { threshold: 0.1, rootMargin: '0px 0px -40px 0px' });
  els.forEach(el => io.observe(el));
})();


/* ---------- 3. Count-up numbers ---------- */
(function countUp() {
  const els = document.querySelectorAll('[data-count]');
  if (!els.length) return;

  const animate = (el) => {
    const target = parseInt(el.dataset.count, 10);
    const dur = 1200;
    const start = performance.now();

    function tick(now) {
      const p = Math.min((now - start) / dur, 1);
      const eased = 1 - Math.pow(1 - p, 3); // ease-out-cubic
      el.textContent = Math.floor(eased * target);
      if (p < 1) requestAnimationFrame(tick);
      else el.textContent = target;
    }
    requestAnimationFrame(tick);
  };

  const io = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
      if (entry.isIntersecting) {
        animate(entry.target);
        io.unobserve(entry.target);
      }
    });
  }, { threshold: 0.5 });

  els.forEach(el => io.observe(el));
})();


/* ---------- 4. Magnetic buttons ---------- */
(function magneticButtons() {
  const buttons = document.querySelectorAll('.btn-primary, .btn-success, .brand-mark, .avatar');

  buttons.forEach(btn => {
    btn.addEventListener('mousemove', (e) => {
      const rect = btn.getBoundingClientRect();
      const x = e.clientX - rect.left - rect.width / 2;
      const y = e.clientY - rect.top - rect.height / 2;
      btn.style.transform = `translate(${x * 0.18}px, ${y * 0.28}px)`;
    });
    btn.addEventListener('mouseleave', () => {
      btn.style.transform = '';
    });
  });
})();


/* ---------- 5. Ripple effect on click ---------- */
(function rippleEffect() {
  document.addEventListener('click', (e) => {
    const btn = e.target.closest('.btn, .chip-btn, .icon-btn, .q-card, .seg, .tag');
    if (!btn) return;

    const circle = document.createElement('span');
    const rect = btn.getBoundingClientRect();
    const size = Math.max(rect.width, rect.height);

    circle.className = 'ripple';
    circle.style.width = circle.style.height = size + 'px';
    circle.style.left = (e.clientX - rect.left - size / 2) + 'px';
    circle.style.top = (e.clientY - rect.top - size / 2) + 'px';

    btn.appendChild(circle);
    setTimeout(() => circle.remove(), 650);
  });
})();


/* ---------- 6. Tilt effect on cards ---------- */
(function tiltCards() {
  const cards = document.querySelectorAll('.feature, .stat, .result-thumb');

  cards.forEach(card => {
    card.addEventListener('mousemove', (e) => {
      const rect = card.getBoundingClientRect();
      const x = (e.clientX - rect.left) / rect.width - 0.5;
      const y = (e.clientY - rect.top) / rect.height - 0.5;
      card.style.transform = `perspective(700px) rotateY(${x * 6}deg) rotateX(${-y * 6}deg) translateY(-4px)`;
    });
    card.addEventListener('mouseleave', () => {
      card.style.transform = '';
    });
  });
})();


/* ---------- 7. Cursor glow (desktop only) ---------- */
(function cursorGlow() {
  if (matchMedia('(pointer: coarse)').matches) return; // skip on touch

  const glow = document.createElement('div');
  glow.className = 'cursor-glow';
  document.body.appendChild(glow);

  let mx = 0, my = 0, gx = 0, gy = 0;
  addEventListener('mousemove', e => { mx = e.clientX; my = e.clientY; });

  function loop() {
    gx += (mx - gx) * 0.12;
    gy += (my - gy) * 0.12;
    glow.style.transform = `translate(${gx}px, ${gy}px)`;
    requestAnimationFrame(loop);
  }
  loop();
})();


/* ---------- 8. Scroll progress bar ---------- */
(function scrollProgress() {
  const bar = document.createElement('div');
  bar.className = 'scroll-progress';
  document.body.appendChild(bar);

  addEventListener('scroll', () => {
    const h = document.documentElement;
    const pct = (h.scrollTop / (h.scrollHeight - h.clientHeight)) * 100;
    bar.style.width = pct + '%';
  });
})();


/* ---------- 9. Animated counter for hero badge dot pulse sync ---------- */
document.querySelectorAll('.badge-pill .dot').forEach((dot, i) => {
  dot.style.animationDelay = `${i * 0.3}s`;
});


/* ---------- 10. Smooth anchor scroll with offset ---------- */
document.querySelectorAll('a[href^="#"]').forEach(a => {
  a.addEventListener('click', e => {
    const id = a.getAttribute('href');
    if (id.length < 2) return;
    const target = document.querySelector(id);
    if (!target) return;
    e.preventDefault();
    const y = target.getBoundingClientRect().top + scrollY - 90;
    scrollTo({ top: y, behavior: 'smooth' });
  });
});