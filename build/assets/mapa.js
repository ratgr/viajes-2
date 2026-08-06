/* mapa.js — cromo del mapa sobre el markup del itinerario:
   mapa base Leaflet + barra lateral (casillas por fila, maestro e
   interruptor de colapso por día, chips de día exclusivos).
   Las capas (marcadores/rutas) se conectarán aquí en la siguiente fase. */
(function () {
  'use strict';

  // ---------- mapa base (tiles Positron, como el mapa viejo) ----------
  var map = null;
  if (window.L && document.getElementById('map')) {
    map = L.map('map', { zoomControl: true }).setView([35.0, 135.6], 6);
    L.tileLayer('https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png', {
      maxZoom: 20, subdomains: 'abcd', attribution: '© OpenStreetMap © CARTO'
    }).addTo(map);
  }

  // ---------- barra lateral ----------
  var days = Array.prototype.slice.call(document.querySelectorAll('section.day'));

  days.forEach(function (day) {
    var head = day.querySelector('.day-head');
    var rows = Array.prototype.slice.call(
      day.querySelectorAll(':scope > ul.steps > li:not(.hidden-summary)'));

    // casilla por fila (prender/apagar su capa cuando existan capas)
    rows.forEach(function (li) {
      var ck = document.createElement('input');
      ck.type = 'checkbox';
      ck.className = 'ck';
      li.insertBefore(ck, li.firstChild);
    });

    // cabecera: maestro + caret
    var master = document.createElement('input');
    master.type = 'checkbox';
    master.className = 'ck ck-day';
    var caret = document.createElement('span');
    caret.className = 'caret';
    caret.textContent = '▶';
    head.insertBefore(caret, head.firstChild);
    head.insertBefore(master, head.firstChild);

    head.addEventListener('click', function (e) {
      if (e.target === master) return;
      day.classList.toggle('open');
    });
    master.addEventListener('change', function () {
      rows.forEach(function (li) { li.querySelector('.ck').checked = master.checked; });
      if (master.checked) day.classList.add('open');
    });
    // maestro tri-estado según las filas
    day.addEventListener('change', function (e) {
      if (e.target === master || !e.target.classList.contains('ck')) return;
      var on = rows.filter(function (li) { return li.querySelector('.ck').checked; }).length;
      master.checked = on === rows.length && on > 0;
      master.indeterminate = on > 0 && on < rows.length;
    });
  });

  // chip de día = día EXCLUSIVO: abre ese, colapsa los demás
  document.querySelectorAll('.day-nav a[href^="#d"]').forEach(function (a) {
    a.addEventListener('click', function () {
      var id = a.getAttribute('href').slice(1);
      days.forEach(function (d) { d.classList.toggle('open', d.id === id); });
    });
  });

  // arranque: primer día abierto
  if (days.length) days[0].classList.add('open');
})();
