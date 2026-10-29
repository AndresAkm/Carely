(function () {
  function setButtonLoading(button, text) {
    if (!button || button.dataset.carelyLoading === 'true') return;
    button.dataset.carelyLoading = 'true';
    button.dataset.carelyOriginalHtml = button.innerHTML;
    button.dataset.carelyOriginalWidth = button.style.width;
    button.dataset.carelyOriginalDisabled = button.disabled ? 'true' : 'false';
    button.style.width = button.offsetWidth + 'px';
    button.disabled = true;
    button.classList.add('is-loading');
    button.setAttribute('aria-busy', 'true');
    button.innerHTML =
      '<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span>';
  }

  function resetButtonLoading(button) {
    if (!button || button.dataset.carelyLoading !== 'true') return;
    button.innerHTML = button.dataset.carelyOriginalHtml || '';
    button.style.width = button.dataset.carelyOriginalWidth || '';
    button.disabled = button.dataset.carelyOriginalDisabled === 'true';
    button.classList.remove('is-loading');
    button.removeAttribute('aria-busy');
    delete button.dataset.carelyLoading;
    delete button.dataset.carelyOriginalHtml;
    delete button.dataset.carelyOriginalWidth;
    delete button.dataset.carelyOriginalDisabled;
  }

  function setOverlayLoading(element, text) {
    if (!element || element.dataset.carelyOverlay === 'true') return;
    element.dataset.carelyOverlay = 'true';
    element.classList.add('loading-container');
    element.setAttribute('aria-busy', 'true');
    let overlay = element.querySelector('.loading-overlay');
    if (!overlay) {
      overlay = document.createElement('div');
      overlay.className = 'loading-overlay';
      overlay.innerHTML =
        '<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span>';
      element.appendChild(overlay);
    }
  }

  function resetOverlayLoading(element) {
    if (!element || element.dataset.carelyOverlay !== 'true') return;
    element.classList.remove('loading-container');
    element.removeAttribute('aria-busy');
    const overlay = element.querySelector('.loading-overlay');
    if (overlay) overlay.remove();
    delete element.dataset.carelyOverlay;
  }

  function initImageSkeletons() {
    const observer = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        entry.target.classList.toggle('is-visible', entry.isIntersecting);
      });
    });

    document.querySelectorAll('img[data-loading-image]').forEach(function (image) {
      const parent = image.parentElement;
      if (!parent) return;
      parent.classList.add('image-skeleton');
      if (parent.querySelector('.image-skeleton__placeholder')) return;
      const placeholder = document.createElement('span');
      placeholder.className = 'image-skeleton__placeholder';
      placeholder.setAttribute('aria-hidden', 'true');
      parent.insertBefore(placeholder, image);
      observer.observe(parent);

      function finish() {
        parent.classList.add('is-loaded');
        placeholder.remove();
        observer.unobserve(parent);
      }

      if (image.complete && image.naturalWidth > 0) {
        finish();
        return;
      }
      image.addEventListener('load', finish, { once: true });
      image.addEventListener('error', finish, { once: true });
    });
  }

  document.addEventListener('submit', function (event) {
    const form = event.target.closest('form[data-loading]');
    if (!form) return;
    const text = form.getAttribute('data-loading-text') || 'Procesando…';
    form.querySelectorAll('button[type="submit"]:not([hidden])').forEach(function (button) {
      setButtonLoading(button, text);
    });
  });

  window.CarelyLoading = {
    button: setButtonLoading,
    resetButton: resetButtonLoading,
    overlay: setOverlayLoading,
    resetOverlay: resetOverlayLoading,
    initImageSkeletons: initImageSkeletons,
  };

  document.addEventListener('DOMContentLoaded', initImageSkeletons);
})();
