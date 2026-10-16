// Legal — índice pegajoso acotado a `.legal-layout`.
//
// `.page-wrapper { overflow: hidden }` (base.css) crea un contexto de
// scroll que rompe `position: sticky`, así que replicamos su comportamiento a
// mano: el índice fluye con el contenido, se fija arriba mientras se recorre la
// sección y se detiene en el borde inferior del layout. La posición se calcula
// contra `.legal-layout` (que es `position: relative`) y no contra el viewport,
// para que al subir no se desfase ni tape el hero.
(function () {
  "use strict";

  const MOBILE_BREAKPOINT = 992;
  const STICKY_OFFSET = 104;
  const WIDTH = "280px";

  const layout = document.querySelector(".legal-layout");
  const card = document.querySelector(".legal-toc__card");
  if (!layout || !card) return;

  function clear() {
    card.style.position = "";
    card.style.top = "";
    card.style.left = "";
    card.style.width = "";
    card.style.zIndex = "";
  }

  function update() {
    if (window.innerWidth < MOBILE_BREAKPOINT) {
      clear();
      return;
    }

    const rect = layout.getBoundingClientRect();
    const cardHeight = card.offsetHeight;

    if (rect.top > STICKY_OFFSET) {
      // El layout todavía no llega a la línea superior: posición natural.
      clear();
    } else if (rect.bottom - STICKY_OFFSET < cardHeight) {
      // El layout se agota: se ancla al fondo para no desbordarlo.
      card.style.position = "absolute";
      card.style.top = Math.max(0, rect.height - cardHeight) + "px";
      card.style.left = "0";
      card.style.width = WIDTH;
      card.style.zIndex = "900";
    } else {
      // Pegado a la parte de arriba mientras se recorre la sección.
      card.style.position = "fixed";
      card.style.top = STICKY_OFFSET + "px";
      card.style.left = rect.left + "px";
      card.style.width = WIDTH;
      card.style.zIndex = "900";
    }
  }

  window.addEventListener("scroll", update, { passive: true });
  window.addEventListener("resize", update);
  window.addEventListener("load", update);
  update();
})();
