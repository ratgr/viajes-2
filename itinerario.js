(function () {
  'use strict';
  var overlay = document.getElementById('overlay');
  var body = document.getElementById('overlay-body');
  var store = document.getElementById('modal-store').content;
  var currentRow = '';   // fila desde la que se abrió el modal visible

  // el modal es compartible: el hash guarda tarjeta + fila (#m-clave@fila)
  function setHash(h) {
    history.replaceState(null, '', h ? '#' + h : location.pathname + location.search);
  }
  function openModal(id, rowId) {
    var src = store.getElementById(id);
    if (!src) return;
    body.innerHTML = src.outerHTML;
    if (rowId) currentRow = rowId;
    setHash(id + (currentRow ? '@' + currentRow : ''));
    if (!overlay.open) overlay.showModal();   // Escape y focus los maneja el <dialog>
  }
  overlay.addEventListener('close', function () {   // cubre ×, backdrop y Escape
    body.innerHTML = '';
    currentRow = '';
    setHash('');
  });

  document.addEventListener('click', function (e) {
    var link = e.target.closest('.modal-link');
    if (link) {
      var href = link.getAttribute('href') || '';
      if (href.indexOf('#m-') === 0) {
        e.preventDefault();
        var row = link.closest('li[id]');   // dentro del dialog no hay fila: conserva la actual
        openModal('m-' + href.slice(3), row ? row.id : '');
        return;
      }
    }
    if (e.target === overlay || e.target.closest('.overlay-close')) overlay.close();
  });

  // llegada con #m-clave[@fila]: scroll a la fila (con flash) y abrir la tarjeta
  function applyHash() {
    var m = /^#(m-[^@]+)(?:@(.+))?$/.exec(location.hash);
    if (!m) return;
    var row = m[2] ? document.getElementById(m[2]) : null;
    if (!row) {
      var firstLink = document.querySelector('.steps a[href="#' + m[1] + '"]');
      row = firstLink && firstLink.closest('li[id]');
    }
    if (row) {
      row.scrollIntoView({ block: 'center' });
      row.classList.add('flash');
      setTimeout(function () { row.classList.remove('flash'); }, 2000);
    }
    openModal(m[1], row ? row.id : '');
  }
  applyHash();
  window.addEventListener('hashchange', applyHash);   // también al navegar solo el hash

  // fotos rotas: ocultarlas (reemplaza los onerror inline del pipeline viejo)
  document.addEventListener('error', function (e) {
    if (e.target.tagName === 'IMG' && e.target.closest('.modal')) {
      e.target.style.display = 'none';
    }
  }, true);

  // barra de días: resaltar el día visible
  var nav = document.querySelector('.day-nav');
  if (nav && 'IntersectionObserver' in window) {
    var links = {};
    nav.querySelectorAll('a[href^="#d-"]').forEach(function (a) {
      links[a.getAttribute('href').slice(1)] = a;
    });
    var days = Array.prototype.slice.call(document.querySelectorAll('section.day'));
    var visible = {};
    var observer = new IntersectionObserver(function (entries) {
      entries.forEach(function (en) { visible[en.target.id] = en.isIntersecting; });
      var current = null;
      days.forEach(function (d) { if (!current && visible[d.id]) current = d.id; });
      if (!current) return;    // arriba del día 1: conservar el resaltado previo
      days.forEach(function (d) {
        if (links[d.id]) links[d.id].classList.toggle('on', d.id === current);
      });
      if (current && links[current].scrollIntoView) {
        links[current].scrollIntoView({ block: 'nearest', inline: 'nearest' });
      }
    }, { rootMargin: '-50px 0px -55% 0px' });
    days.forEach(function (d) { observer.observe(d); });
  }
})();
