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

  document.querySelectorAll('a[href*="#"]').forEach(anchor => {
    anchor.addEventListener('click', e => {
      const href = anchor.getAttribute('href') || '';
      const hashIndex = href.indexOf('#');
      if (hashIndex === -1) return;
      const id = href.slice(hashIndex);
      if (id === '#') return;
      const path = href.slice(0, hashIndex);
      // Interceptamos solo los enlaces que apuntan a esta misma página. Si el
      // enlace va a otra ruta (p. ej. /#beneficios desde /privacidad/), dejamos
      // que el navegador navegue y haga el salto al ancla.
      if (path && path !== window.location.pathname) return;
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
