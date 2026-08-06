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

  // ---------- divisor arrastrable (persistente) ----------
  var panel = document.querySelector('.panel');
  var splitter = document.getElementById('splitter');
  if (panel && splitter) {
    var saved = localStorage.getItem('mapa-panel-w');
    if (saved) panel.style.width = saved + 'px';
    var dragging = false;
    splitter.addEventListener('pointerdown', function (e) {
      dragging = true;
      splitter.classList.add('dragging');
      splitter.setPointerCapture(e.pointerId);
      e.preventDefault();
    });
    splitter.addEventListener('pointermove', function (e) {
      if (!dragging) return;
      var w = Math.max(260, Math.min(e.clientX, window.innerWidth * 0.7));
      panel.style.width = w + 'px';
      if (map) map.invalidateSize();
    });
    splitter.addEventListener('pointerup', function () {
      dragging = false;
      splitter.classList.remove('dragging');
      localStorage.setItem('mapa-panel-w', parseInt(panel.style.width || '380', 10));
    });
    splitter.addEventListener('dblclick', function () {
      panel.style.width = '380px';
      localStorage.removeItem('mapa-panel-w');
      if (map) map.invalidateSize();
    });
  }

  // ---------- selección de fila + tarjeta como popup EN el mapa ----------
  var GEO = { locations: {}, transits: {} };
  try {
    GEO = JSON.parse(document.getElementById('geo').textContent);
  } catch (e) { /* sin geometría: los links caen al dialog */ }
  var store = document.getElementById('modal-store').content;
  var selRow = null;
  var tempLayer = null;   // geometría resaltada de la selección (transit)

  function modalHtml(key) {
    var src = store.getElementById('m-' + key);
    return src ? src.outerHTML : '';
  }
  function selectRow(li) {
    if (selRow) selRow.classList.remove('sel');
    selRow = li;
    if (li) li.classList.add('sel');
  }
  function clearTemp() {
    if (tempLayer && map) { map.removeLayer(tempLayer); tempLayer = null; }
  }
  function showOnMap(key, fallbackTitle) {
    if (!map) return false;
    var content = modalHtml(key) ||
      '<div class="modal"><h3>' + (fallbackTitle || key) + '</h3></div>';
    var loc = GEO.locations[key];
    var tr = GEO.transits[key];
    clearTemp();
    if (loc) {
      map.flyTo(loc, Math.max(map.getZoom(), 15), { duration: .5 });
      L.popup({ maxWidth: 320 }).setLatLng(loc).setContent(content).openOn(map);
      return true;
    }
    if (tr && tr.coords.length) {
      tempLayer = L.polyline(tr.coords, {
        color: tr.color, weight: tr.mode === 'walk' ? 3 : 5, opacity: .9,
        dashArray: tr.mode === 'walk' ? '4 7' : null
      }).addTo(map);
      map.flyToBounds(tempLayer.getBounds().pad(.25), { duration: .5 });
      var mid = tr.coords[Math.floor(tr.coords.length / 2)];
      L.popup({ maxWidth: 320 }).setLatLng(mid).setContent(content).openOn(map);
      return true;
    }
    return false;
  }
  function rowOf(el) {
    var li = el.closest('li');
    while (li && !(li.parentElement && li.parentElement.classList.contains('steps'))) {
      li = li.parentElement ? li.parentElement.closest('li') : null;
    }
    return li;
  }

  // links a modal: si la clave tiene geometría, la tarjeta va al popup del
  // mapa (captura, para ganarle al dialog de itinerario.js); si no, dialog
  document.addEventListener('click', function (e) {
    var link = e.target.closest('.modal-link');
    if (!link || !e.target.closest('.panel')) return;
    var href = link.getAttribute('href') || '';
    if (href.indexOf('#m-') !== 0) return;
    var key = href.slice(3);
    if (showOnMap(key, link.textContent)) {
      e.preventDefault();
      e.stopPropagation();
      selectRow(rowOf(link));
    }
  }, true);

  // click en la fila (fuera de casillas/links): seleccionar y mostrar su clave
  document.querySelector('.panel').addEventListener('click', function (e) {
    if (e.target.closest('input') || e.target.closest('.modal-link') ||
        e.target.closest('.day-head') || e.target.closest('.day-nav')) return;
    var li = rowOf(e.target);
    if (!li) return;
    selectRow(li);
    var key = li.dataset.location || li.dataset.transit;
    if (key) {
      var title = li.querySelector('.title');
      showOnMap(key, title ? title.textContent : key);
    }
  });
})();
