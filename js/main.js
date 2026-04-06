(function () {

  // ── Reveal (legacy no-op) ───────────────────────────
  var reveals = document.querySelectorAll('.reveal');
  if (reveals.length && 'IntersectionObserver' in window) {
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (e) {
        if (e.isIntersecting) { e.target.classList.add('in-view'); io.unobserve(e.target); }
      });
    }, { threshold: 0.1 });
    reveals.forEach(function (el) { io.observe(el); });
  }

  // ── Modal ───────────────────────────────────────────
  function openModal(id) {
    var modal = document.getElementById(id);
    if (!modal) return;
    modal.removeAttribute('hidden');
    modal.setAttribute('aria-hidden', 'false');
    document.body.style.overflow = 'hidden';
    var panel = modal.querySelector('.modal__panel');
    if (panel) setTimeout(function () { panel.focus(); }, 50);
  }

  function closeModal(id) {
    var modal = document.getElementById(id);
    if (!modal) return;
    modal.setAttribute('hidden', '');
    modal.setAttribute('aria-hidden', 'true');
    document.body.style.overflow = '';
  }

  // Close on backdrop or ✕ click
  document.addEventListener('click', function (e) {
    if (e.target.classList.contains('modal')) closeModal(e.target.id);
    if (e.target.classList.contains('modal__close')) closeModal(e.target.closest('.modal').id);
  });

  // Close on ESC
  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape') {
      document.querySelectorAll('.modal:not([hidden])').forEach(function (m) { closeModal(m.id); });
    }
  });

  // Formspree AJAX submit
  document.addEventListener('submit', function (e) {
    var form = e.target;
    if (!form.classList.contains('modal__form')) return;
    e.preventDefault();

    var btn    = form.querySelector('.modal__submit');
    var panel  = form.closest('.modal__panel');
    var success = panel.querySelector('.modal__success');
    var error   = panel.querySelector('.modal__error');

    btn.disabled = true;
    btn.textContent = 'Sending…';
    if (error) error.hidden = true;

    fetch(form.action, {
      method: 'POST',
      body: new FormData(form),
      headers: { 'Accept': 'application/json' }
    })
    .then(function (res) {
      if (res.ok) {
        form.hidden = true;
        if (success) success.hidden = false;
      } else {
        throw new Error('error');
      }
    })
    .catch(function () {
      btn.disabled = false;
      btn.textContent = btn.dataset.label;
      if (error) error.hidden = false;
    });
  });

  window.openModal  = openModal;
  window.closeModal = closeModal;

})();
