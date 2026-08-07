/* cfg.js — configuración compartida de las páginas nuevas: ⚙️ con
   🔎 Texto (zoom por niveles, persistente) y 🔄 Actualizar (SW update). */
(function () {
  'use strict';
  var ZOOMS = [1, 1.12, 1.25, 1.4];
  function apply() {
    // en el mapa el zoom va al PANEL (zoomear el body descuadra los clicks
    // de Leaflet); en las demás páginas, al body completo
    var target = document.querySelector('.panel') || document.body;
    target.style.zoom = localStorage.getItem('cfg-zoom') || 1;
  }
  apply();
  var b = document.createElement('button');
  b.className = 'cfg-toggle';
  b.type = 'button';
  b.textContent = '⚙️';
  b.title = 'Configuración';
  var menu = document.createElement('div');
  menu.className = 'cfg-menu';
  menu.hidden = true;
  menu.innerHTML = '<button type="button" data-a="fs">🔎 Texto más grande</button>' +
                   '<button type="button" data-a="upd">🔄 Buscar actualización</button>';
  document.body.appendChild(b);
  document.body.appendChild(menu);
  b.addEventListener('click', function (e) {
    e.stopPropagation();
    menu.hidden = !menu.hidden;
  });
  // cerrar al tocar FUERA (y que ningún listener del mapa se trague el click)
  ['click', 'pointerdown'].forEach(function (ev) {
    menu.addEventListener(ev, function (e) { e.stopPropagation(); });
  });
  document.addEventListener('click', function (e) {
    if (!menu.hidden && e.target !== b && !menu.contains(e.target)) menu.hidden = true;
  });
  menu.addEventListener('click', function (e) {
    var a = e.target.dataset && e.target.dataset.a;
    if (a === 'fs') {
      var cur = +(localStorage.getItem('cfg-zoom') || 1);
      var i = (ZOOMS.indexOf(cur) + 1) % ZOOMS.length;
      localStorage.setItem('cfg-zoom', ZOOMS[i]);
      apply();
      e.target.textContent = '🔎 Texto (' + Math.round(ZOOMS[(ZOOMS.indexOf(cur) + 1) % ZOOMS.length] * 100) + '%)';
    }
    if (a === 'upd') {
      e.target.textContent = '⏳ Actualizando…';
      var j = ('serviceWorker' in navigator)
        ? navigator.serviceWorker.getRegistration().then(function (r) { return r && r.update(); })
        : Promise.resolve();
      j.catch(function () {}).then(function () { location.reload(); });
    }
  });
})();
