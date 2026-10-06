// Legal — índice fijo y desvanecido, mismo patrón que la lateral del panel
// (`profile.js`). La tarjeta va `fixed` porque `.page-wrapper` es ancestro de
// scroll y el `sticky` no se pegaría al viewport.
(function () {
  "use strict";

  const MOBILE_BREAKPOINT = 992;

  const card = document.querySelector(".legal-toc__card");
  if (!card) return;

  const footer = document.querySelector(".c-footer");

  // La tarjeta es `fixed` y el contenedor está centrado con `margin: 0 auto`,
  // así que su `left` depende del ancho real del viewport y del padding del
  // `.container`. Medirlo es más fiable que calcularlo en CSS, que se desfasa
  // con la barra de desplazamiento vertical.
  function alignCard() {
    if (window.innerWidth < MOBILE_BREAKPOINT) {
      document.documentElement.style.removeProperty("--legal-toc-left");
      return;
    }
    const container = document.querySelector(".legal-page .container");
    if (!container) return;
    const styles = getComputedStyle(container);
    const paddingLeft = parseFloat(styles.paddingLeft) || 0;
    const left = container.getBoundingClientRect().left + paddingLeft;
    document.documentElement.style.setProperty("--legal-toc-left", `${left}px`);
  }

  // Al ser `fixed` la tarjeta viaja hasta el final del documento y termina
  // sobre el footer. Se esconde cuando el footer le alcanza por abajo.
  function updateVisibility() {
    if (!footer || window.innerWidth < MOBILE_BREAKPOINT) {
      card.classList.remove("is-hidden");
      return;
    }
    const cardBottom = card.getBoundingClientRect().bottom;
    const footerTop = footer.getBoundingClientRect().top;
    card.classList.toggle("is-hidden", footerTop < cardBottom + 16);
  }

  function sync() {
    alignCard();
    updateVisibility();
  }

  window.addEventListener("scroll", updateVisibility, { passive: true });
  window.addEventListener("resize", sync);
  window.addEventListener("load", sync);
  sync();
})();