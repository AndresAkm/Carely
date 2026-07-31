// THEME SYSTEM — persists accent color in localStorage
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
    '--clr-bg': '#FBFDFF',
    '--clr-bg-2': '#F0F5FC',
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
    '--clr-bg': '#FFFBFD',
    '--clr-bg-2': '#FAF0F5',
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
    '--clr-bg': '#FFFDF6',
    '--clr-bg-2': '#FAF5E9',
  },
};

const themeKeyByColor = {};
Object.keys(themes).forEach(k => { themeKeyByColor[themes[k]['--accent']] = k; });

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
  root.style.setProperty('--clr-bg', theme['--clr-bg']);
  root.style.setProperty('--clr-bg-2', theme['--clr-bg-2']);
  try {
    localStorage.setItem(THEME_STORAGE_KEY, name);
  } catch (_) {}
  document.querySelectorAll('.theme-btn').forEach(btn => {
    btn.classList.toggle('active', btn.dataset.theme === name);
  });
  syncHeroTabsToTheme(name);
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

// HERO TABS — indicator + sync con el theme picker
function moveHeroIndicator(tab) {
  const indicator = document.getElementById('tabsIndicator');
  if (!indicator || !tab) return;
  const track = tab.parentElement;
  const trackRect = track.getBoundingClientRect();
  const tabRect = tab.getBoundingClientRect();
  indicator.style.width = tabRect.width + 'px';
  indicator.style.transform = `translateX(${tabRect.left - trackRect.left - 5}px)`;
}

function activateHeroTab(tab) {
  if (!tab) return;
  document.querySelectorAll('.hero__tab').forEach(t => t.classList.remove('active'));
  tab.classList.add('active');
  document.documentElement.style.setProperty('--accent', tab.dataset.color);
  const heroAccent = document.getElementById('heroAccent');
  if (heroAccent) heroAccent.textContent = tab.dataset.label;
  moveHeroIndicator(tab);
}

function syncHeroTabsToTheme(name) {
  const tab = document.querySelector(`.hero__tab[data-theme="${name}"]`);
  if (tab) activateHeroTab(tab);
}

// THEME PICKER — floating UI injected on all pages
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

  // Theme system
  buildThemePicker();
  loadTheme();

  // Hero Tabs — click wiring
  const tabs = document.querySelectorAll('.hero__tab');

  tabs.forEach(tab => {
    tab.addEventListener('click', () => {
      activateHeroTab(tab);
      const themeKey = tab.dataset.theme || themeKeyByColor[tab.dataset.color];
      if (themeKey) {
        applyTheme(themeKey);
      }
    });
  });

  // Posiciona el indicador en la tab activa inicial
  (function initHeroIndicator() {
    const activeTab = document.querySelector('.hero__tab.active');
    if (activeTab) moveHeroIndicator(activeTab);
  })();

  window.addEventListener('resize', () => {
    const activeTab = document.querySelector('.hero__tab.active');
    if (activeTab) moveHeroIndicator(activeTab);
  });

  // Hero Parallax / Mouse Tilt
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

  // Scroll Reveal — IntersectionObserver
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

  // Hero entrance animation
  const heroRevealEls = document.querySelectorAll('.hero .anim-reveal');
  heroRevealEls.forEach(el => {
    const delay = el.dataset.delay || 0;
    setTimeout(() => {
      el.classList.add('revealed');
    }, 150 + Number(delay) * 140);
  });

});
