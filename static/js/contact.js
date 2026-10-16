// CONTACT — modal de contacto del footer con envío por `fetch`.
document.addEventListener('DOMContentLoaded', () => {
  const form = document.querySelector('[data-contact-form]');
  if (!form) return;

  const modal = form.closest('.modal');
  const intro = form.closest('.modal-body').querySelector('[data-contact-intro]');
  const success = form.closest('.modal-body').querySelector('[data-contact-success]');
  const done = form.closest('.modal-body').querySelector('[data-contact-done]');
  const feedback = form.querySelector('[data-contact-feedback]');
  const submit = form.querySelector('[type="submit"]');

  function clearErrors() {
    form.querySelectorAll('[data-contact-error]').forEach((el) => {
      el.textContent = '';
    });
    if (feedback) {
      feedback.textContent = '';
      feedback.classList.add('d-none');
    }
  }

  function showFeedback(message) {
    if (!feedback) return;
    feedback.textContent = message;
    feedback.classList.remove('d-none');
  }

  form.addEventListener('submit', async (event) => {
    event.preventDefault();
    clearErrors();

    const original = submit.innerHTML;
    submit.disabled = true;
    submit.innerHTML = '<span class="spinner-border spinner-border-sm me-1" role="status" aria-hidden="true"></span> Enviando…';

    try {
      const response = await fetch(form.action, {
        method: 'POST',
        headers: { 'X-Requested-With': 'XMLHttpRequest' },
        body: new FormData(form),
      });
      const data = await response.json().catch(() => ({}));

      if (response.ok && data.ok) {
        form.classList.add('d-none');
        if (intro) intro.classList.add('d-none');
        if (done) done.classList.remove('d-none');
        if (success) success.classList.remove('d-none');
        return;
      }

      if (data.errors) {
        Object.entries(data.errors).forEach(([field, messages]) => {
          const target = form.querySelector(`[data-contact-error="${field}"]`);
          if (target) {
            target.textContent = messages.join(' ');
          } else {
            showFeedback(messages.join(' '));
          }
        });
        return;
      }

      showFeedback(data.message || 'No pudimos enviar tu mensaje. Inténtalo de nuevo.');
    } catch (error) {
      showFeedback('Revisa tu conexión e inténtalo de nuevo.');
    } finally {
      submit.disabled = false;
      submit.innerHTML = original;
    }
  });

  if (modal) {
    modal.addEventListener('hidden.bs.modal', () => {
      form.reset();
      clearErrors();
      form.classList.remove('d-none');
      if (intro) intro.classList.remove('d-none');
      if (success) success.classList.add('d-none');
      if (done) done.classList.add('d-none');
    });
  }
});
