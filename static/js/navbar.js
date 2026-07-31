// NAVBAR — scroll shadow, mobile toggle and smooth anchors
document.addEventListener('DOMContentLoaded', () => {
  const nav = document.querySelector('.c-nav, .carely-navbar');
  if (nav) {
    const onScroll = () => {
      nav.classList.toggle('c-nav--scrolled', window.scrollY > 40);
    };
    window.addEventListener('scroll', onScroll, { passive: true });
    onScroll();
  }

  document.querySelectorAll('a[href^="#"]').forEach(anchor => {
    anchor.addEventListener('click', e => {
      const id = anchor.getAttribute('href');
      if (id === '#') return;
      const target = document.querySelector(id);
      if (target) {
        e.preventDefault();
        target.scrollIntoView({ behavior: 'smooth', block: 'start' });
        const toggle = document.getElementById('navToggle');
        if (toggle) toggle.checked = false;
      }
    });
  });
});
