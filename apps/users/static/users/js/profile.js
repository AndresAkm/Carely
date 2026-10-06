// Perfil — lateral fija, selector de color y pestañas activas
(function () {
  const DEFAULT_THEME = "azul";
  const MOBILE_BREAKPOINT = 992;

  function currentTheme() {
    try {
      return localStorage.getItem("carely_theme") || DEFAULT_THEME;
    } catch (_) {
      return DEFAULT_THEME;
    }
  }

  function markActiveTheme() {
    const active = currentTheme();
    document.querySelectorAll(".profile-swatch").forEach((btn) => {
      btn.classList.toggle("active", btn.dataset.theme === active);
    });
  }

  document.querySelectorAll(".profile-swatch").forEach((btn) => {
    btn.addEventListener("click", () => {
      if (typeof applyTheme === "function") {
        applyTheme(btn.dataset.theme);
      }
      markActiveTheme();
    });
  });

  markActiveTheme();

  const side = document.querySelector(".profile-side");

  // La lateral es `fixed` y el contenedor está centrado con `margin: 0 auto`,
  // así que su `left` depende del ancho real del viewport y del padding del
  // `.container`. Medirlo es más fiable que calcularlo en CSS, que se
  // desfasa con la barra de desplazamiento vertical.
  function alignSide() {
    if (!side) return;
    if (window.innerWidth < MOBILE_BREAKPOINT) {
      document.documentElement.style.removeProperty("--profile-side-left");
      return;
    }
    const container = document.querySelector(".profile-page .container");
    if (!container) return;
    const styles = getComputedStyle(container);
    const paddingLeft = parseFloat(styles.paddingLeft) || 0;
    const left = container.getBoundingClientRect().left + paddingLeft;
    document.documentElement.style.setProperty("--profile-side-left", `${left}px`);
  }

  const footer = document.querySelector(".c-footer");

  // Al ser `fixed` la lateral viaja hasta el final del documento y termina
  // sobre el footer. Se esconde cuando el footer le alcanza por abajo.
  function updateSideVisibility() {
    if (!side || !footer || window.innerWidth < MOBILE_BREAKPOINT) {
      if (side) side.classList.remove("is-hidden");
      return;
    }
    const overlaps = footer.getBoundingClientRect().top < side.getBoundingClientRect().bottom + 16;
    side.classList.toggle("is-hidden", overlaps);
  }

  const subnav = document.querySelector(".profile-subnav");
  const links = subnav
    ? Array.from(subnav.querySelectorAll('a[href^="#"]'))
    : [];
  const sections = links
    .map((link) => document.querySelector(link.getAttribute("href")))
    .filter(Boolean);

  if (!sections.length) return;

  // Margen de tolerancia en px. Al aterrizar una sección, la línea de lectura
  // cae justo en su borde superior y el redondeo a subpíxel puede dejarla un
  // pelo por encima o por debajo.
  const TOLERANCE = 2;

  // La línea de lectura tiene que coincidir con `scroll-margin-top`. Al pulsar
  // un enlace el navegador deja el inicio de la sección a esa distancia del
  // borde superior, así que si la línea queda más arriba la sección pulsada
  // todavía no la alcanza y se queda marcada la anterior.
  let readOffset = 0;
  let activeId = sections[0].id;

  function measureReadOffset() {
    const nav = document.querySelector(".c-nav");
    const navHeight = nav ? nav.getBoundingClientRect().height : 0;
    const margin = parseFloat(getComputedStyle(sections[0]).scrollMarginTop) || 0;
    readOffset = Math.max(navHeight + 24, margin);
  }

  // Desplaza la tira horizontal de móvil para que la opción activa quede a la
  // vista. El scroller es el nav, no la lista. Con `link.scrollIntoView` se
  // arrastraría también la página hacia arriba, porque la tira ya quedó fuera
  // del viewport al llegar a la sección.
  function centerInStrip(link) {
    if (subnav.scrollWidth <= subnav.clientWidth + 1) return;
    const linkRect = link.getBoundingClientRect();
    const stripRect = subnav.getBoundingClientRect();
    const offset = linkRect.left - stripRect.left;
    const target = subnav.scrollLeft + offset - (subnav.clientWidth - linkRect.width) / 2;
    const clamped = Math.max(
      0,
      Math.min(target, subnav.scrollWidth - subnav.clientWidth)
    );
    if (Math.abs(subnav.scrollLeft - clamped) < 1) return;
    subnav.scrollTo({ left: clamped, behavior: "smooth" });
  }

  function setActive(id) {
    activeId = id;
    links.forEach((link) => {
      const isActive = link.getAttribute("href") === "#" + id;
      link.classList.toggle("is-active", isActive);
      if (isActive) centerInStrip(link);
    });
  }

  // La activa es la sección que CONTIENE la línea de lectura, no la última que
  // quedó por encima. Al pulsar un enlace el navegador aterriza la sección
  // justo sobre la línea, así que con la comparación "por encima" la sección
  // pulsada nunca llega a ganar y el subnav marca siempre la anterior.
  function highlight() {
    const line = window.scrollY + readOffset;
    for (const section of sections) {
      const rect = section.getBoundingClientRect();
      const top = rect.top + window.scrollY;
      if (line >= top - TOLERANCE && line < top + rect.height) {
        setActive(section.id);
        return;
      }
    }
    // La línea cayó en un hueco entre secciones: se mantiene la anterior.
    setActive(activeId);
  }

  // `html { scroll-behavior: smooth }` convierte un clic en un.scroll de varios
  // cientos de ms. El scrollspy correría en cada frame intermedio y volvería a
  // marcar la sección por la que se está pasando, así que se congela hasta que
  // el scroll se calma.
  let settling = false;
  let settleTimer = null;

  function onNavClick(id) {
    settling = true;
    clearTimeout(settleTimer);
    setActive(id);
  }

  function scheduleSettle() {
    clearTimeout(settleTimer);
    settleTimer = setTimeout(() => {
      settling = false;
      highlight();
    }, 120);
  }

  links.forEach((link) => {
    link.addEventListener("click", () => onNavClick(link.getAttribute("href").slice(1)));
  });

  function sync() {
    alignSide();
    measureReadOffset();
    highlight();
    updateSideVisibility();
  }

  window.addEventListener(
    "scroll",
    () => {
      if (settling) scheduleSettle();
      else highlight();
      updateSideVisibility();
    },
    { passive: true }
  );
  window.addEventListener("resize", sync);
  window.addEventListener("load", sync);
  sync();
})();