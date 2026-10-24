(function () {
  const current = document.currentScript;
  if (!current) return;

  const assets = {
    driverCss: current.dataset.driverCss,
    driverJs: current.dataset.driverJs,
    tourCss: current.dataset.tourCss,
    tourJs: current.dataset.tourJs,
  };

  function loadCss(href) {
    if (!href || document.querySelector(`link[href="${href}"]`)) return;
    const link = document.createElement('link');
    link.rel = 'stylesheet';
    link.href = href;
    document.head.appendChild(link);
  }

  function loadScript(src) {
    return new Promise(function (resolve, reject) {
      if (!src || document.querySelector(`script[src="${src}"]`)) {
        resolve();
        return;
      }
      const script = document.createElement('script');
      script.src = src;
      script.onload = resolve;
      script.onerror = reject;
      document.body.appendChild(script);
    });
  }

  document.addEventListener('DOMContentLoaded', function () {
    if (!document.querySelector('[data-tour]')) return;

    loadCss(assets.driverCss);
    loadCss(assets.tourCss);

    loadScript(assets.driverJs)
      .then(function () {
        return loadScript(assets.tourJs);
      })
      .catch(function () {});
  });
})();
