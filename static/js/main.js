/* ═══════════════════════════════════════════════════════
   THEME SYSTEM — persists accent color in localStorage
   ═══════════════════════════════════════════════════════ */
const THEME_STORAGE_KEY = 'carely_theme';

const themes = {
  azul: {
    label: 'Azul',
    icon: 'bi bi-droplet',
    '--accent': '#5B8DEF',
    '--accent-soft': '#DCEEFF',
    '--clr-primary': '#E8609B',
    '--clr-primary-soft': '#F8D7E6',
    '--clr-secondary': '#5B8DEF',
    '--clr-secondary-soft': '#DCEEFF',
    '--color-button-hover': '#4A7BE0',
  },
  rosa: {
    label: 'Rosa',
    icon: 'bi bi-heart',
    '--accent': '#E8609B',
    '--accent-soft': '#F8D7E6',
    '--clr-primary': '#5B8DEF',
    '--clr-primary-soft': '#DCEEFF',
    '--clr-secondary': '#E8609B',
    '--clr-secondary-soft': '#F8D7E6',
    '--color-button-hover': '#D4538A',
  },
  amber: {
    label: 'Ámbar',
    icon: 'bi bi-sun',
    '--accent': '#F0B429',
    '--accent-soft': '#FEF3CD',
    '--clr-primary': '#E8609B',
    '--clr-primary-soft': '#F8D7E6',
    '--clr-secondary': '#5B8DEF',
    '--clr-secondary-soft': '#DCEEFF',
    '--color-button-hover': '#D4A020',
  },
};

function applyTheme(name) {
  const theme = themes[name];
  if (!theme) return;
  const root = document.documentElement;
  root.style.setProperty('--accent', theme['--accent']);
  root.style.setProperty('--accent-soft', theme['--accent-soft']);
  root.style.setProperty('--clr-primary', theme['--clr-primary']);
  root.style.setProperty('--clr-primary-soft', theme['--clr-primary-soft']);
  root.style.setProperty('--clr-secondary', theme['--clr-secondary']);
  root.style.setProperty('--clr-secondary-soft', theme['--clr-secondary-soft']);
  root.style.setProperty('--color-button-hover', theme['--color-button-hover']);
  try {
    localStorage.setItem(THEME_STORAGE_KEY, name);
  } catch (_) {}
  document.querySelectorAll('.theme-btn').forEach(btn => {
    btn.classList.toggle('active', btn.dataset.theme === name);
  });
}

function loadTheme() {
  let name;
  try {
    name = localStorage.getItem(THEME_STORAGE_KEY);
  } catch (_) {}
  if (name && themes[name]) {
    applyTheme(name);
  }
}

/* ═══════════════════════════════════════════════════════
   THEME PICKER — floating UI injected on all pages
   ═══════════════════════════════════════════════════════ */
function buildThemePicker() {
  const container = document.createElement('div');
  container.className = 'theme-picker';
  container.setAttribute('aria-label', 'Selector de color');

  const toggle = document.createElement('button');
  toggle.className = 'theme-picker__toggle';
  toggle.setAttribute('aria-label', 'Cambiar color');
  toggle.innerHTML = '<i class="bi bi-palette"></i>';

  const menu = document.createElement('div');
  menu.className = 'theme-picker__menu';

  Object.keys(themes).forEach(key => {
    const btn = document.createElement('button');
    btn.className = 'theme-btn';
    btn.dataset.theme = key;
    btn.setAttribute('aria-label', themes[key].label);
    btn.innerHTML = `<i class="${themes[key].icon}"></i>`;
    btn.addEventListener('click', e => {
      e.stopPropagation();
      applyTheme(key);
      toggle.classList.remove('is-open');
    });
    menu.appendChild(btn);
  });

  toggle.addEventListener('click', e => {
    e.stopPropagation();
    toggle.classList.toggle('is-open');
  });

  document.addEventListener('click', () => {
    toggle.classList.remove('is-open');
  });

  container.appendChild(toggle);
  container.appendChild(menu);
  document.body.appendChild(container);
}

document.addEventListener('DOMContentLoaded', () => {

  /* ── Bootstrap Toasts ── */
  document.querySelectorAll('.toast').forEach(el => {
    new bootstrap.Toast(el, { autohide: true, delay: 4000 }).show();
  });

  /* ── Theme system ── */
  loadTheme();
  buildThemePicker();

  /* ── Navbar scroll shadow ── */
  const nav = document.querySelector('.c-nav, .carely-navbar');
  if (nav) {
    const onScroll = () => {
      nav.classList.toggle('c-nav--scrolled', window.scrollY > 40);
    };
    window.addEventListener('scroll', onScroll, { passive: true });
    onScroll();
  }

  /* ── Smooth anchor links ── */
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

  /* ── Hero Tabs — Interactive Color Change ── */
  const tabs = document.querySelectorAll('.hero__tab');
  const indicator = document.getElementById('tabsIndicator');
  const heroAccent = document.getElementById('heroAccent');
  const root = document.documentElement;

  function moveIndicator(tab) {
    if (!indicator || !tab) return;
    const track = tab.parentElement;
    const trackRect = track.getBoundingClientRect();
    const tabRect = tab.getBoundingClientRect();
    indicator.style.width = tabRect.width + 'px';
    indicator.style.transform = `translateX(${tabRect.left - trackRect.left - 5}px)`;
  }

  const themeKeyByColor = {};
  Object.keys(themes).forEach(k => { themeKeyByColor[themes[k]['--accent']] = k; });

  function activateTab(tab) {
    tabs.forEach(t => t.classList.remove('active'));
    tab.classList.add('active');
    const color = tab.dataset.color;
    const label = tab.dataset.label;
    root.style.setProperty('--accent', color);
    if (heroAccent) heroAccent.textContent = label;
    moveIndicator(tab);
    const themeKey = tab.dataset.theme || themeKeyByColor[color];
    if (themeKey) {
      applyTheme(themeKey);
    }
  }

  tabs.forEach(tab => {
    tab.addEventListener('click', () => activateTab(tab));
  });

  (function syncHeroTabs() {
    let savedTheme;
    try { savedTheme = localStorage.getItem(THEME_STORAGE_KEY); } catch (_) {}
    const match = savedTheme && tabs.length && Array.from(tabs).find(t => t.dataset.theme === savedTheme);
    if (match) {
      activateTab(match);
    } else {
      const activeTab = document.querySelector('.hero__tab.active');
      if (activeTab) moveIndicator(activeTab);
    }
  })();

  window.addEventListener('resize', () => {
    const activeTab = document.querySelector('.hero__tab.active');
    if (activeTab) moveIndicator(activeTab);
  });

  /* ── Hero Parallax / Mouse Tilt ── */
  const showcase = document.getElementById('heroShowcase');

  if (showcase) {
    const heroSection = document.getElementById('hero');
    if (heroSection) {
      heroSection.addEventListener('mousemove', e => {
        const rect = heroSection.getBoundingClientRect();
        const x = (e.clientX - rect.left) / rect.width - 0.5;
        const y = (e.clientY - rect.top) / rect.height - 0.5;
        const tiltX = y * -8;
        const tiltY = x * 8;
        const moveX = x * -12;
        const moveY = y * -12;
        showcase.style.transform =
          `perspective(800px) rotateX(${tiltX}deg) rotateY(${tiltY}deg) translate(${moveX}px, ${moveY}px)`;
      });

      heroSection.addEventListener('mouseleave', () => {
        showcase.style.transform = 'perspective(800px) rotateX(0) rotateY(0) translate(0, 0)';
        showcase.style.transition = 'transform .5s cubic-bezier(.4,0,.2,1)';
        setTimeout(() => { showcase.style.transition = 'transform .15s ease-out'; }, 500);
      });
    }
  }

  /* ── Scroll Reveal — IntersectionObserver ── */
  const revealElements = document.querySelectorAll('.anim-reveal, .anim-scroll');

  const revealObserver = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
      if (entry.isIntersecting) {
        const delay = entry.target.dataset.delay || 0;
        setTimeout(() => {
          entry.target.classList.add('revealed');
        }, Number(delay) * 120);
        revealObserver.unobserve(entry.target);
      }
    });
  }, {
    threshold: 0.12,
    rootMargin: '0px 0px -30px 0px'
  });

  revealElements.forEach(el => revealObserver.observe(el));

  /* ── Hero entrance animation ── */
  const heroRevealEls = document.querySelectorAll('.hero .anim-reveal');
  heroRevealEls.forEach(el => {
    const delay = el.dataset.delay || 0;
    setTimeout(() => {
      el.classList.add('revealed');
    }, 150 + Number(delay) * 140);
  });

});
