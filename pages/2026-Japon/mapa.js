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

  // INVARIANTE del maestro del día: todo prendido = ✔ · algo prendido = ▬
  // (tercer estado) · nada = vacío. Se recalcula tras CUALQUIER cambio,
  // venga de un click o de código (stepper de día, hash, restauración).
  function updateMaster(day) {
    var m = day.querySelector('.ck-day');
    if (!m) return;
    var cks = Array.prototype.slice.call(day.querySelectorAll('.ck:not(.ck-day)'));
    var on = cks.filter(function (c) { return c.checked; }).length;
    m.checked = on === cks.length && on > 0;
    m.indeterminate = on > 0 && on < cks.length;
  }

  days.forEach(function (day) {
    var head = day.querySelector('.day-head');
    var rows = Array.prototype.slice.call(
      day.querySelectorAll(':scope > ul.steps > li'));   // incluye los solo-mapa

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
      // abrir un día también lo ENCUADRA (toda su geometría, sin dibujarla)
      if (day.classList.toggle('open')) focusKeys(keysUnder(day));
    });
    // el maestro prende TODO el día, incluidos los sub-pasos de las opciones
    // (aunque estén ocultas/plegadas: su geometría también cuenta)
    master.addEventListener('change', function () {
      Array.prototype.forEach.call(day.querySelectorAll('.ck:not(.ck-day)'), function (ck) {
        ck.checked = master.checked;
      });
      master.indeterminate = false;
      if (master.checked) day.classList.add('open');
    });
    // tri-estado ante CUALQUIER cambio de casilla dentro del día
    day.addEventListener('change', function (e) {
      if (e.target === master || !e.target.classList.contains('ck')) return;
      updateMaster(day);
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
  // un LUGAR puede aparecer en varios días (las rutas son únicas): la tarjeta
  // lleva una pieza por día, colapsada a «día + una línea»; la del día
  // seleccionado (sección abierta) o la fila clickeada llega expandida
  function dayPieces(key, activeRowId) {
    var rows = document.querySelectorAll('.panel .steps > li[data-location="' + key + '"]');
    if (!rows.length) return '';
    var out = ['<div class="uses">'];
    rows.forEach(function (li) {
      var day = li.closest('section.day');
      var label = day ? (day.querySelector('h3').textContent.split('·')[0].trim()) : '';
      var time = li.querySelector('time');
      var title = li.querySelector('.title');
      var note = li.querySelector('.note');
      var open = (day && day.classList.contains('open')) || li.id === activeRowId;
      out.push('<details class="use"' + (open ? ' open' : '') + '>' +
        '<summary><b>' + label + '</b><span class="use-line">' +
        (time ? time.textContent + ' · ' : '') + (title ? title.textContent : '') +
        '</span></summary>' +
        (note ? '<div class="use-note">' + note.innerHTML + '</div>' : '') +
        '</details>');
    });
    out.push('</div>');
    return out.join('');
  }
  function selectRow(li) {
    if (selRow) selRow.classList.remove('sel');
    selRow = li;
    if (li) li.classList.add('sel');
  }
  // el DÓNDE ESTAMOS vive en el hash (#m-clave@fila · #@fila · #dN) para que
  // una recarga (p.ej. tras rebuild) vuelva al mismo punto; la visibilidad
  // de casillas NO se codifica (recarga = default)
  function updateHash(mKey, rowId) {
    var h = (mKey ? 'm-' + mKey : '') + (rowId ? '@' + rowId : '');
    if (h) history.replaceState(null, '', '#' + h);
  }
  function openDayOf(li) {
    var day = li.closest('section.day');
    if (day) days.forEach(function (d) { d.classList.toggle('open', d === day); });
  }
  function clearTemp() {
    if (tempLayer && map) { map.removeLayer(tempLayer); tempLayer = null; }
  }

  // halo de SELECCIÓN: resalta en el mapa la geometría de lo elegido en la
  // barra (línea gorda translúcida / disco brillante), debajo de las capas
  var haloLayer = null;
  function clearHalo() {
    if (haloLayer && map) { map.removeLayer(haloLayer); haloLayer = null; }
  }
  // FOCO genérico: cualquier nivel de la barra (fila, elección, grupo, día)
  // encuadra TODA la geometría contenida en su subárbol
  function keysUnder(el) {
    var keys = [];
    var own = el.dataset && (el.dataset.location || el.dataset.transit);
    if (own) keys.push(own);
    el.querySelectorAll('[data-location],[data-transit]').forEach(function (e2) {
      var k = e2.dataset.location || e2.dataset.transit;
      if (k && keys.indexOf(k) < 0) keys.push(k);
    });
    return keys;
  }
  function boundsForKeys(keys) {
    var bounds = null;
    keys.forEach(function (key) {
      var loc = GEO.locations[key];
      var tr = GEO.transits[key];
      var b = null;
      if (loc) b = L.latLngBounds([loc]);
      else if (tr && tr.coords.length) b = L.latLngBounds(tr.coords);
      if (b) bounds = bounds ? bounds.extend(b) : L.latLngBounds(b.getSouthWest(), b.getNorthEast());
    });
    return bounds;
  }
  function focusKeys(keys) {
    if (!map || !keys.length) return;
    var b = boundsForKeys(keys);
    if (b && b.isValid()) map.flyToBounds(b.pad(.2), { duration: .5 });
  }
  function haloFor(keys) {
    clearHalo();
    if (!map) return;
    var parts = [];
    keys.forEach(function (key) {
      var loc = GEO.locations[key];
      var tr = GEO.transits[key];
      if (loc) {
        parts.push(L.circleMarker(loc, {
          radius: 14, color: '#b23a2a', weight: 0, fillColor: '#b23a2a',
          fillOpacity: .3, interactive: false
        }));
      } else if (tr && tr.coords.length) {
        parts.push(L.polyline(tr.coords, {
          color: tr.color, weight: 13, opacity: .35,
          lineCap: 'round', lineJoin: 'round', interactive: false
        }));
      }
    });
    if (parts.length) {
      haloLayer = L.layerGroup(parts).addTo(map);
      parts.forEach(function (p) { if (p.bringToBack) p.bringToBack(); });
    }
  }

  // ---------- grupos de options: colapsables y seleccionables ----------
  // elegir un grupo (plan o tier) enciende TODA su geometría de un golpe
  var selGroupEl = null;
  function groupKeys(g) {
    var keys = [];
    g.querySelectorAll('[data-location],[data-transit]').forEach(function (el) {
      var k = el.dataset.location || el.dataset.transit;
      if (k && keys.indexOf(k) < 0) keys.push(k);
    });
    g.querySelectorAll('a.modal-link').forEach(function (a) {
      var h = a.getAttribute('href') || '';
      if (h.indexOf('#m-') === 0 && keys.indexOf(h.slice(3)) < 0) keys.push(h.slice(3));
    });
    return keys;
  }
  function showGroupGeometry(g) {
    if (!map) return;
    clearTemp();
    haloFor(groupKeys(g));
    var layers = [];
    groupKeys(g).forEach(function (key) {
      var loc = GEO.locations[key];
      var tr = GEO.transits[key];
      if (loc) {
        layers.push(L.circleMarker(loc, {
          radius: 7, color: '#fff', weight: 2, fillColor: '#b23a2a', fillOpacity: 1
        }).bindTooltip(key));
      } else if (tr && tr.coords.length) {
        layers.push(L.polyline(tr.coords, {
          color: tr.color, weight: tr.mode === 'walk' ? 3 : 5, opacity: .9,
          dashArray: tr.mode === 'walk' ? '4 7' : null
        }));
      }
    });
    if (!layers.length) return;
    tempLayer = L.layerGroup(layers).addTo(map);
    var bounds = null;
    layers.forEach(function (l) {
      var b = l.getBounds ? l.getBounds() : L.latLngBounds([l.getLatLng()]);
      bounds = bounds ? bounds.extend(b) : L.latLngBounds(b.getSouthWest(), b.getNorthEast());
    });
    map.flyToBounds(bounds.pad(.2), { duration: .5 });
  }
  function selectGroup(g) {
    if (selGroupEl) selGroupEl.classList.remove('sel-group');
    selGroupEl = g;
    g.classList.add('sel-group');
    showGroupGeometry(g);
  }
  // la FILA principal de una elección también se pliega: su caret colapsa
  // el conjunto de options completo
  document.querySelectorAll('.panel .steps > li').forEach(function (li) {
    var opts = li.querySelector(':scope > .body > ul.options');
    var title = li.querySelector('.title');
    if (!opts || !title) return;
    var caret = document.createElement('span');
    caret.className = 'group-caret row-caret';
    caret.textContent = '▼';
    title.insertBefore(caret, title.firstChild);
    caret.addEventListener('click', function (e) {
      e.stopPropagation();
      li.classList.toggle('opts-closed');
    });
  });

  // cada ul.options es un CONJUNTO DE ELECCIÓN: sus grupos llevan radio
  // (mutuamente excluyentes); elegir uno marca la opción y enciende su geometría
  document.querySelectorAll('.panel .options').forEach(function (set, si) {
    // ojo del conjunto: 👁 = fantasma de los no elegidos · 🙈 = solo el elegido
    // (vive en la FILA padre, no dentro de las opciones)
    var eye = document.createElement('button');
    eye.type = 'button';
    eye.className = 'eye-toggle';
    eye.textContent = '👁';
    eye.title = 'Los no elegidos: fantasma (👁) u ocultos (🙈)';
    set.classList.add('eye-ghost');
    var host = set.closest('li') || set;
    host.appendChild(eye);
    eye.addEventListener('click', function (e) {
      e.stopPropagation();
      var hide = set.classList.toggle('eye-hide');
      set.classList.toggle('eye-ghost', !hide);
      eye.textContent = hide ? '🙈' : '👁';
    });
    // sub-filas de planes: casilla propia, individualmente seleccionables
    set.querySelectorAll('.steps > li').forEach(function (li) {
      if (li.querySelector(':scope > .ck')) return;
      var ck = document.createElement('input');
      ck.type = 'checkbox';
      ck.className = 'ck';
      li.insertBefore(ck, li.firstChild);
    });
    set.querySelectorAll(':scope > li').forEach(function (g) {
      var label = g.querySelector(':scope > b');
      if (!label) return;
      var caret = document.createElement('span');
      caret.className = 'group-caret';
      caret.textContent = '▼';
      label.insertBefore(caret, label.firstChild);
      caret.addEventListener('click', function (e) {
        e.stopPropagation();          // colapsar NO elige
        g.classList.toggle('closed');
      });
      var isPlan = !!g.querySelector(':scope > ul.steps');
      if (isPlan) {
        // plan: la elección es el GRUPO (sus sub-pasos son su itinerario)
        var radio = document.createElement('input');
        radio.type = 'radio';
        radio.name = 'choice-' + si;
        radio.className = 'group-choice';
        label.insertBefore(radio, caret);
        label.addEventListener('click', function (e) {
          e.stopPropagation();
          radio.checked = true;
          selectGroup(g);
          closePanelIfNarrow();
        });
      } else {
        // elección anidada (tiers): la elección real es CADA opción de abajo —
        // el radio va en el nivel inferior, compartido por TODO el conjunto
        label.addEventListener('click', function (e) {
          e.stopPropagation();
          selectGroup(g);             // ver la geometría del tier completo
          closePanelIfNarrow();
        });
        g.querySelectorAll(':scope > .option').forEach(function (opt) {
          var r = document.createElement('input');
          r.type = 'radio';
          r.name = 'choice-' + si;
          r.className = 'option-choice';
          opt.insertBefore(r, opt.firstChild);
          r.addEventListener('change', function () {
            var a = opt.querySelector('a.modal-link');
            var key = a && (a.getAttribute('href') || '').slice(3);
            if (key) showOnMap(key, a.textContent);
          });
          // pliegue propio de la opción: colapsa sus sub-pasos (ida/lugar/regreso)
          var sub = opt.querySelector(':scope > ul.steps');
          if (sub) {
            var oc = document.createElement('span');
            oc.className = 'group-caret option-caret';
            oc.textContent = '▼';
            opt.insertBefore(oc, r.nextSibling);
            opt.classList.add('closed');   // plegada por defecto
            oc.addEventListener('click', function (e) {
              e.stopPropagation();
              opt.classList.toggle('closed');
            });
          }
        });
      }
    });
    // por defecto la PRIMERA opción del conjunto queda elegida (sin volar ahí)
    if (!set.querySelector('.group-choice:checked, .option-choice:checked')) {
      var first = set.querySelector('.group-choice, .option-choice');
      if (first) first.checked = true;
    }
  });
  // popup con la tarjeta COMPLETA (en teléfono es la única vista); si es alta
  // se colapsa tras «Ver más» y expandida scrollea con tope de 40% de pantalla
  function openCardPopup(latlng, content) {
    var pop = L.popup({ maxWidth: 320 })
      .setLatLng(latlng)
      .setContent('<div class="popup-card">' + content + '</div>')
      .openOn(map);
    // OJO: nada de pop.update() tras mutar el DOM — re-renderiza el contenido
    // desde el string original y borra la clase y el botón
    var root = pop.getElement ? pop.getElement() : null;
    var el = root && root.querySelector('.popup-card');
    var card = el && el.querySelector('.modal');
    if (card && card.scrollHeight > window.innerHeight * 0.4) {
      el.classList.add('collapsed');
      var btn = document.createElement('button');
      btn.className = 'see-more';
      btn.textContent = 'Ver más ↓';
      btn.addEventListener('click', function () {
        var collapsed = el.classList.toggle('collapsed');
        btn.textContent = collapsed ? 'Ver más ↓' : 'Ver menos ↑';
      });
      el.appendChild(btn);
    }
    return pop;
  }
  var lastShownKey = null;   // repetir click en lo YA elegido acerca el zoom
  function showOnMap(key, fallbackTitle, activeRowId, zoomOpt) {
    if (!map) return false;
    var content = modalHtml(key) ||
      '<div class="modal"><h3>' + (fallbackTitle || key) + '</h3></div>';
    var loc = GEO.locations[key];
    var tr = GEO.transits[key];
    var repeat = key === lastShownKey && !zoomOpt;
    lastShownKey = key;
    clearTemp();
    haloFor([key]);
    if (loc) {
      var z = repeat ? Math.min(19, map.getZoom() + 2)
                     : (zoomOpt || Math.max(map.getZoom(), 15));
      map.flyTo(loc, z, { duration: .5 });
      openCardPopup(loc, content + dayPieces(key, activeRowId));
      return true;
    }
    if (tr && tr.coords.length) {
      tempLayer = transitGroup(key, tr, tr.coords).addTo(map);
      if (repeat) {
        map.flyToBounds(tempLayer.getBounds().pad(.02), { duration: .5 });
      } else if (zoomOpt) {
        map.flyTo(tempLayer.getBounds().getCenter(), zoomOpt, { duration: .5 });
      } else {
        map.flyToBounds(tempLayer.getBounds().pad(.25), { duration: .5 });
      }
      openCardPopup(tr.coords[Math.floor(tr.coords.length / 2)], content);
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

  // ---------- capas vivas: la CASILLA manda ----------
  // solo las filas/sub-filas MARCADAS dibujan su geometría (el maestro del
  // día marca todo el día); abrir/plegar solo organiza la barra
  var liveLayers = {};    // clave → capa Leaflet
  var autoLayers = {};    // id de fila → conector automático (transit sin geometría)
  var seqLabels = {};     // clave de lugar → '1' / '2·5' (cronología del día)

  // rumbo de pantalla a→b en grados CSS (horario, 0° = este)
  function segAngle(a, b) {
    var dx = (b[1] - a[1]) * Math.cos(a[0] * Math.PI / 180);
    var dy = a[0] - b[0];   // pantalla: y crece hacia el sur
    return Math.atan2(dy, dx) * 180 / Math.PI;
  }
  // punto y rumbo a una fracción del largo total de la línea
  function pointAlong(coords, frac) {
    var d = [0], total = 0;
    for (var i = 1; i < coords.length; i++) {
      var dx = (coords[i][1] - coords[i - 1][1]) * Math.cos(coords[i][0] * Math.PI / 180);
      var dy = coords[i][0] - coords[i - 1][0];
      total += Math.sqrt(dx * dx + dy * dy);
      d.push(total);
    }
    if (!total) return null;
    var goal = total * frac;
    for (var j = 1; j < coords.length; j++) {
      if (d[j] >= goal) {
        var t = (goal - d[j - 1]) / (d[j] - d[j - 1] || 1);
        var a = coords[j - 1], b = coords[j];
        return { p: [a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t], ang: segAngle(a, b) };
      }
    }
    return null;
  }
  // flechas de dirección sobre la línea (¼, ½, ¾ del recorrido)
  function chevronMarkers(coords, color) {
    var out = [];
    [.25, .5, .75].forEach(function (f) {
      var pa = pointAlong(coords, f);
      if (!pa) return;
      out.push(L.marker(pa.p, {
        interactive: false, keyboard: false,
        icon: L.divIcon({
          className: 'chev', iconSize: [16, 16],
          html: '<span style="transform:rotate(' + Math.round(pa.ang) + 'deg);color:' + color + '">❯</span>'
        })
      }));
    });
    return out;
  }
  // línea de transporte: polilínea + flechas + (si las estaciones calzan con
  // los vértices, como en los rieles) un punto con nombre por estación
  function transitGroup(key, tr, coords) {
    var g = L.featureGroup();
    var line = L.polyline(coords, {
      color: tr.color, weight: tr.mode === 'walk' ? 3 : 5, opacity: .85,
      dashArray: tr.mode === 'walk' ? '4 7' : null
    });
    // línea de IMPACTO invisible y gorda: las punteadas casi no se atinan
    g.addLayer(L.polyline(coords, { weight: 16, opacity: 0.001, interactive: true }));
    g.addLayer(line);
    g._line = line;
    g._decos = chevronMarkers(coords, tr.color);
    g._dots = [];
    if (tr.stations && tr.stations.length === coords.length) {
      coords.forEach(function (c, i) {
        var dot = L.circleMarker(c, { radius: 3.5, color: tr.color, weight: 2, fillColor: '#fff', fillOpacity: 1 });
        if (tr.stations[i]) dot.bindTooltip(tr.stations[i], { direction: 'top', offset: [0, -4] });
        g._dots.push(dot);
      });
    }
    g._decos.concat(g._dots).forEach(function (d) { g.addLayer(d); });
    return g;
  }
  function locIcon(key, ghost) {
    var label = seqLabels[key] || '';
    var w = label.length > 2 ? 10 + label.length * 8 : 22;
    return L.divIcon({
      className: 'seq-badge' + (ghost ? ' ghost' : '') + (label ? '' : ' plain'),
      html: label, iconSize: label ? [w, 22] : [16, 16]
    });
  }
  function makeLayer(key) {
    var loc = GEO.locations[key];
    var tr = GEO.transits[key];
    var ly = null;
    if (loc) {
      ly = L.marker(loc, { icon: locIcon(key, false) });
    } else if (tr && tr.coords.length) {
      ly = transitGroup(key, tr, tr.coords);
    }
    if (ly) {
      // click en la geometría: SIEMPRE (re)abre su tarjeta — aun ya
      // seleccionada — y selecciona la fila correspondiente en la barra
      ly.on('click', function () {
        var content = modalHtml(key) || '<div class="modal"><h3>' + key + '</h3></div>';
        if (loc) content += dayPieces(key, null);
        openCardPopup(loc || tr.coords[Math.floor(tr.coords.length / 2)], content);
        // segundo click en lo ya elegido = acercar el zoom
        if (key === lastShownKey && map) {
          if (loc) map.flyTo(loc, Math.min(19, map.getZoom() + 2), { duration: .4 });
          else map.flyToBounds(L.latLngBounds(tr.coords).pad(.02), { duration: .4 });
        }
        lastShownKey = key;
        selectByKey(key);
      });
    }
    return ly;
  }
  // geometría → barra: seleccionar la fila del elemento clickeado en el mapa
  // (si la clave se repite, gana la de un día abierto)
  function selectByKey(key) {
    var idx = -1;
    for (var j = 0; j < stEls.length; j++) {
      if ((stEls[j].dataset.location || stEls[j].dataset.transit) !== key) continue;
      var day = stEls[j].closest('section.day');
      if (day && day.classList.contains('open')) { idx = j; break; }
      if (idx < 0) idx = j;
    }
    if (idx < 0) return;
    var li = rowOf(stEls[idx]) || stEls[idx];
    openDayOf(li);
    selectRow(li);
    li.scrollIntoView({ block: 'center' });
    stCur = idx;
    stMode = null;
    stRender();
  }
  // estado fantasma: elemento marcado dentro de una opción NO elegida —
  // con 👁 su geometría se dibuja atenuada; con 🙈 va en línea GORDA tenue
  // (sigue visible: distinta, no borrada)
  function ghostState(el) {
    var set = el.closest('.options');
    if (!set) return 'full';
    var chosen = set.querySelector('.option-choice:checked, .group-choice:checked');
    if (!chosen) return 'full';
    var container = el.closest('.option') || el.closest('.options > li');
    if (!container || container.contains(chosen)) return 'full';
    if (set.classList.contains('eye-hide')) return 'hidden';
    return set.classList.contains('eye-ghost') ? 'ghost' : 'full';
  }
  var ST_RANK = { full: 3, ghost: 2, hidden: 1 };
  function applyLayerState(key, st) {
    var ly = liveLayers[key];
    if (!ly) return;
    var lineOp = st === 'full' ? .85 : st === 'ghost' ? .25 : .12;
    var markOp = st === 'full' ? 1 : st === 'ghost' ? .25 : .12;
    if (ly._line) {                       // grupo de transporte
      var w = GEO.transits[key] && GEO.transits[key].mode === 'walk' ? 3 : 5;
      ly._line.setStyle({ opacity: lineOp, weight: st === 'hidden' ? w + 7 : w });
      ly._decos.forEach(function (d) { d.setOpacity(markOp); });
      ly._dots.forEach(function (d) { d.setStyle({ opacity: markOp, fillOpacity: markOp }); });
    } else if (ly.setIcon) {              // marcador de lugar (insignia numerada)
      ly.setIcon(locIcon(key, st !== 'full'));
    }
  }
  // ¿el2 está en la MISMA rama de opciones que el? Un paso dentro de una
  // opción NO es vecino de los pasos de OTRA opción del mismo conjunto: su
  // ruta automática debe brincar al siguiente paso real, no a la opción de
  // al lado. (el2 fuera de todo conjunto siempre es válido.)
  function sameBranch(el, el2) {
    var node = el2;
    for (var set = node.closest('.options'); set;
         set = set.parentElement && set.parentElement.closest('.options')) {
      if (!set.contains(el)) return false;                    // otra opción/conjunto
      if (chosenContainer(set, el) !== chosenContainer(set, node)) return false;
      node = set;
    }
    return true;
  }
  // punto de anclaje de una fila con geometría: lugar → su gps;
  // transporte → su último/primer vértice (según sea el previo o el siguiente)
  function anchorPoint(el, end) {
    var key = el.dataset.location || el.dataset.transit;
    var loc = GEO.locations[key];
    if (loc) return loc;
    var tr = GEO.transits[key];
    if (tr && tr.coords.length) return end ? tr.coords[tr.coords.length - 1] : tr.coords[0];
    return null;
  }
  function syncLayers() {
    if (!map) return;
    var want = {};      // clave → 'full' | 'ghost'
    var autos = {};     // id de conector → {a, b, st}
    var els = Array.prototype.slice.call(
      document.querySelectorAll('.panel [data-location], .panel [data-transit]'));
    var states = els.map(function (el) {
      var ck = el.querySelector(':scope > .ck');
      if (!ck || !ck.checked) return null;
      return ghostState(el);
    });
    els.forEach(function (el, i) {
      var st = states[i];
      if (!st) return;
      var key = el.dataset.location || el.dataset.transit;
      if (GEO.locations[key] || (GEO.transits[key] && GEO.transits[key].coords.length)) {
        if (!want[key] || ST_RANK[st] > ST_RANK[want[key]]) want[key] = st;
        return;
      }
      if (!el.dataset.transit) return;
      // transporte SIN geometría (referencia sin cumplir) = conector automático:
      // une el punto previo con el siguiente dentro del mismo día
      var day = el.closest('section.day');
      var a = null, b = null, j;
      for (j = i - 1; j >= 0 && !a; j--) {
        if (els[j].closest('section.day') !== day) break;
        if (!sameBranch(el, els[j])) continue;      // no anclar en OTRA opción
        a = anchorPoint(els[j], true);
      }
      for (j = i + 1; j < els.length && !b; j++) {
        if (els[j].closest('section.day') !== day) break;
        if (!sameBranch(el, els[j])) continue;
        b = anchorPoint(els[j], false);
      }
      if (a && b) autos['auto-' + i + '-' + key] = { a: a, b: b, st: st };
    });
    // cronología del día: numerar los LUGARES plenos en orden del documento
    seqLabels = {};
    days.forEach(function (day) {
      var n = 0;
      els.forEach(function (el, i) {
        if (states[i] !== 'full' || !el.dataset.location) return;
        if (el.closest('section.day') !== day) return;
        var key = el.dataset.location;
        if (!GEO.locations[key]) return;
        n += 1;
        seqLabels[key] = seqLabels[key] ? seqLabels[key] + '·' + n : String(n);
      });
    });
    Object.keys(liveLayers).forEach(function (k) {
      if (!want[k]) {
        map.removeLayer(liveLayers[k]);
        delete liveLayers[k];
      }
    });
    Object.keys(want).forEach(function (k) {
      if (!liveLayers[k]) {
        var ly = makeLayer(k);
        if (ly) {
          liveLayers[k] = ly;
          ly.addTo(map);
        }
      }
      applyLayerState(k, want[k]);
    });
    // conectores automáticos: punteado recto gris, una flecha al centro
    Object.keys(autoLayers).forEach(function (id) {
      if (!autos[id]) {
        map.removeLayer(autoLayers[id]);
        delete autoLayers[id];
      }
    });
    Object.keys(autos).forEach(function (id) {
      var sp = autos[id];
      if (!autoLayers[id]) {
        var g = L.featureGroup();
        var line = L.polyline([sp.a, sp.b], { color: '#8a8073', weight: 2.5, opacity: .7, dashArray: '2 8' });
        g.addLayer(line);
        g._line = line;
        g._decos = chevronMarkers([sp.a, sp.b], '#8a8073').slice(1, 2);   // solo la del centro
        g._decos.forEach(function (d) { g.addLayer(d); });
        autoLayers[id] = g.addTo(map);
      }
      var op = sp.st === 'full' ? .7 : sp.st === 'ghost' ? .2 : .1;
      autoLayers[id]._line.setStyle({ opacity: op, weight: sp.st === 'hidden' ? 9 : 2.5 });
      autoLayers[id]._decos.forEach(function (d) { d.setOpacity(sp.st === 'full' ? .8 : op); });
    });
  }
  function fitToLayers() {
    var bounds = null;
    Object.keys(liveLayers).forEach(function (k) {
      var l = liveLayers[k];
      var b = l.getBounds ? l.getBounds() : L.latLngBounds([l.getLatLng()]);
      bounds = bounds ? bounds.extend(b) : L.latLngBounds(b.getSouthWest(), b.getNorthEast());
    });
    if (bounds && bounds.isValid()) map.flyToBounds(bounds.pad(.15), { duration: .5 });
  }
  var syncT = null;
  function schedSync() {
    clearTimeout(syncT);
    syncT = setTimeout(syncLayers, 120);
  }
  document.querySelector('.panel').addEventListener('click', schedSync);
  document.querySelector('.panel').addEventListener('change', schedSync);
  // chips de día: tras el cambio exclusivo, sincronizar y encuadrar el día
  document.querySelectorAll('.day-nav a[href^="#d"]').forEach(function (a) {
    a.addEventListener('click', function () {
      clearHalo();
      var sec = document.getElementById((a.getAttribute('href') || '').slice(1));
      setTimeout(function () {
        syncLayers();
        if (sec) focusKeys(keysUnder(sec)); else fitToLayers();
      }, 60);
    });
  });
  setTimeout(function () { syncLayers(); fitToLayers(); }, 150);   // arranque

  // ---------- STEPPER: recorrido paso a paso (navegación principal en teléfono) ----------
  // ‹ / › recorren los pasos CONCRETOS (con lugar o transporte) siguiendo la
  // opción ELEGIDA de cada choice; cuando el siguiente paso entra a un choice
  // se muestran sus opciones para elegir a cuál saltar (anidados: columnas
  // plegables por grupo — se elige la opción de abajo, no el grupo); dentro
  // de una opción el «saltar a» sigue visible (plegable) y saltar a otra
  // opción arranca en su primer paso
  var stEls = Array.prototype.slice.call(
    document.querySelectorAll('.panel [data-location], .panel [data-transit]'));
  var stCur = stEls.length ? 0 : -1;
  var stMode = null;        // conjunto .options mostrando elección, o null
  var stJumpOpen = true;

  function chosenContainer(set, node) {
    var opt = node.closest('.option');
    if (opt && opt.closest('.options') === set) return opt;
    var li = node;
    while (li && li.parentElement !== set) li = li.parentElement;
    return li;
  }
  function onChosenPath(el) {
    var node = el;
    for (var set = node.closest('.options'); set;
         set = set.parentElement && set.parentElement.closest('.options')) {
      var chosen = set.querySelector('.option-choice:checked, .group-choice:checked');
      if (chosen) {
        var cont = chosenContainer(set, node);
        if (!cont || !cont.contains(chosen)) return false;
      }
      node = set;
    }
    return true;
  }
  function nextConcrete(i, dir) {
    for (var j = i + dir; j >= 0 && j < stEls.length; j += dir) {
      if (onChosenPath(stEls[j])) return j;
    }
    return -1;
  }
  function stTitle(el) {
    var t = el.querySelector('.title') || el.querySelector('a.modal-link');
    return (t ? t.textContent : (el.dataset.location || el.dataset.transit))
      .replace(/\s+/g, ' ').trim();
  }
  function optLabel(cont) {
    var a = cont.querySelector('a.modal-link');
    var b = cont.querySelector('b');
    var s = (a && a.textContent) || (b && b.textContent) || cont.textContent;
    // fuera el caret de plegado de la barra si vino dentro del <b>
    return s.replace(/\s+/g, ' ').replace(/^[▼▾▸▶ ]+/, '').trim().slice(0, 42);
  }

  var stBar = document.createElement('div');
  stBar.className = 'stepper';
  stBar.innerHTML =
    '<div class="st-row">' +
    '<button class="st-prev" type="button">‹</button>' +
    '<div class="st-center"></div>' +
    '<button class="st-next" type="button">›</button></div>' +
    '<div class="st-jump" hidden>' +
    '<button class="st-jump-toggle" type="button">saltar a ▾</button>' +
    '<div class="st-jump-body"></div></div>';
  document.getElementById('map').appendChild(stBar);
  // parar TODO lo de ratón: un click en la barra que burbujee hasta Leaflet
  // CIERRA el popup recién abierto por ese mismo click
  ['pointerdown', 'mousedown', 'mouseup', 'click', 'touchstart', 'dblclick', 'wheel'].forEach(function (ev) {
    stBar.addEventListener(ev, function (e) { e.stopPropagation(); });
  });

  // zoom esperado de un elemento: lugar = 16; línea = el que la encuadra
  function expectedZoomFor(el) {
    if (!el || !map) return map ? map.getZoom() : 14;
    var key = el.dataset.location || el.dataset.transit;
    if (GEO.locations[key]) return 16;
    var tr = GEO.transits[key];
    if (tr && tr.coords.length) {
      return Math.min(16, map.getBoundsZoom(L.latLngBounds(tr.coords).pad(.25)));
    }
    return map.getZoom();
  }
  function stGoTo(i) {
    // cruzar de día con el caminador — como sea que pase (‹ ›, día ‹ ›,
    // saltar a opción) — OCULTA el día anterior y ACTIVA el nuevo completo
    var prevDi = dayIndexOf(stEls[stCur]);
    var newDi = dayIndexOf(stEls[i]);
    if (newDi >= 0 && newDi !== prevDi) {
      if (prevDi >= 0) setDayChecked(days[prevDi], false);
      setDayChecked(days[newDi], true);
      syncLayers();
    }
    stCur = i;
    stMode = null;
    var el = stEls[i];
    var li = rowOf(el) || el;
    openDayOf(li);
    selectRow(li);
    li.scrollIntoView({ block: 'center' });
    var key = el.dataset.location || el.dataset.transit;
    // suavizar el zoom entre pasos (regla del usuario): promedio aritmético
    // de (2 × zoom nuevo + zoom actual + zoom esperado del paso siguiente) / 4
    var blend = null;
    if (map) {
      var nxI = nextConcrete(i, 1);
      var zNew = expectedZoomFor(el);
      var zNext = nxI >= 0 ? expectedZoomFor(stEls[nxI]) : zNew;
      blend = Math.round((2 * zNew + map.getZoom() + zNext) / 4 * 2) / 2;
    }
    if (!showOnMap(key, stTitle(el), li.id, blend)) {
      // sin geometría (conector automático): encuadrar sus puntos vecinos y
      // abrir su tarjeta ahí mismo (el popup SIEMPRE acompaña al paso)
      var pts = [], j, p;
      for (j = i - 1; j >= 0; j--) {
        if (!sameBranch(el, stEls[j])) continue;
        p = anchorPoint(stEls[j], true);
        if (p) { pts.push(p); break; }
      }
      for (j = i + 1; j < stEls.length; j++) {
        if (!sameBranch(el, stEls[j])) continue;
        p = anchorPoint(stEls[j], false);
        if (p) { pts.push(p); break; }
      }
      if (pts.length && map) {
        var c = L.latLngBounds(pts).getCenter();
        map.flyTo(c, blend || map.getZoom(), { duration: .5 });
        openCardPopup(c, modalHtml(key) ||
          '<div class="modal"><h3>' + stTitle(el) + '</h3></div>');
      }
    }
    stRender();
  }
  function enterOption(cont) {
    var r = cont.querySelector('.option-choice, .group-choice');
    if (r && !r.checked) { r.checked = true; syncLayers(); }
    for (var j = 0; j < stEls.length; j++) {
      if (cont.contains(stEls[j])) { stGoTo(j); return; }
    }
    stMode = null;
    stRender();
  }
  // botones de opciones de un conjunto: planes = un botón por li; tiers = las
  // opciones de abajo agrupadas en columnas plegables por grupo
  function renderChoices(set, box) {
    box.innerHTML = '';
    var curEl = stEls[stCur];
    [].slice.call(set.children).forEach(function (li) {
      if (li.tagName !== 'LI') return;
      var opts = [].slice.call(li.querySelectorAll('.option')).filter(function (o) {
        return o.closest('.options') === set;
      });
      function mkBtn(cont, label) {
        var b = document.createElement('button');
        b.type = 'button';
        b.className = 'st-opt';
        b.textContent = label;
        if (li.dataset.tier) b.dataset.tier = li.dataset.tier;   // color del tier
        if (curEl && cont.contains(curEl)) b.classList.add('on');
        var r = cont.querySelector('.option-choice, .group-choice');
        if (r && r.checked) b.classList.add('chosen');
        b.addEventListener('click', function () { enterOption(cont); });
        return b;
      }
      if (opts.length) {
        // columna por grupo con su etiqueta fija (solo el «saltar a» se pliega)
        var col = document.createElement('div');
        col.className = 'st-col';
        var head = li.querySelector('b');
        if (head) {
          var hs = document.createElement('span');
          hs.className = 'st-col-head';
          if (li.dataset.tier) hs.dataset.tier = li.dataset.tier;
          hs.textContent = head.textContent.replace(/\s+/g, ' ')
            .replace(/^[▼▾▸▶ ]+/, '').trim();
          col.appendChild(hs);
        }
        opts.forEach(function (o) { col.appendChild(mkBtn(o, optLabel(o))); });
        box.appendChild(col);
      } else {
        box.appendChild(mkBtn(li, optLabel(li)));
      }
    });
  }
  function stRender() {
    var el = stEls[stCur];
    var center = stBar.querySelector('.st-center');
    var nextB = stBar.querySelector('.st-next');
    var jump = stBar.querySelector('.st-jump');
    stBar.querySelector('.st-prev').disabled = nextConcrete(stCur, -1) < 0;
    if (stMode) {                       // eligiendo a qué opción entrar
      center.innerHTML = '';
      renderChoices(stMode, center);
      nextB.hidden = true;
    } else {
      center.innerHTML = '<span class="st-cur"></span>';
      center.querySelector('.st-cur').textContent = el ? stTitle(el) : '—';
      var nx = nextConcrete(stCur, 1);
      nextB.hidden = false;
      nextB.disabled = nx < 0;
    }
    // dentro de una opción: «saltar a» con TODAS las opciones del conjunto
    var set = el ? el.closest('.options') : null;
    if (set && !stMode) {
      jump.hidden = false;
      var body = jump.querySelector('.st-jump-body');
      body.hidden = !stJumpOpen;
      jump.querySelector('.st-jump-toggle').textContent = stJumpOpen ? 'saltar a ▾' : 'saltar a ▸';
      if (stJumpOpen) renderChoices(set, body); else body.innerHTML = '';
    } else {
      jump.hidden = true;
    }
    if (dayBar) dsRender();
  }
  stBar.querySelector('.st-prev').addEventListener('click', function () {
    var p = nextConcrete(stCur, -1);
    if (stMode) { stMode = null; stRender(); return; }   // cancelar elección
    if (p >= 0) stGoTo(p);
  });
  stBar.querySelector('.st-next').addEventListener('click', function () {
    var nx = nextConcrete(stCur, 1);
    if (nx < 0) return;
    var curSet = stEls[stCur] ? stEls[stCur].closest('.options') : null;
    var nxSet = stEls[nx].closest('.options');
    if (nxSet && nxSet !== curSet) { stMode = nxSet; stRender(); return; }
    stGoTo(nx);
  });
  stBar.querySelector('.st-jump-toggle').addEventListener('click', function () {
    stJumpOpen = !stJumpOpen;
    stRender();
  });
  // click en una fila de la barra → el stepper se posiciona ahí
  function stSyncTo(li) {
    for (var j = 0; j < stEls.length; j++) {
      if (stEls[j] === li || li.contains(stEls[j])) { stCur = j; stMode = null; stRender(); return; }
    }
  }

  // ---------- STEPPER DE DÍA (barra inferior) ----------
  // ‹ día / día › saltan al PRIMER paso concreto del día vecino: apagan y
  // pliegan el día actual, prenden y muestran el nuevo completo
  var dayBar = document.createElement('div');
  dayBar.className = 'day-stepper';
  dayBar.innerHTML =
    '<button class="ds-prev" type="button">‹ día</button>' +
    '<span class="ds-cur"></span>' +
    '<button class="ds-next" type="button">día ›</button>';
  document.getElementById('map').appendChild(dayBar);
  ['pointerdown', 'mousedown', 'mouseup', 'click', 'touchstart', 'dblclick', 'wheel'].forEach(function (ev) {
    dayBar.addEventListener(ev, function (e) { e.stopPropagation(); });
  });
  function dayIndexOf(el) {
    return el ? days.indexOf(el.closest('section.day')) : -1;
  }
  function setDayChecked(day, on) {
    Array.prototype.forEach.call(day.querySelectorAll('.ck:not(.ck-day)'), function (c) {
      c.checked = on;
    });
    updateMaster(day);
  }
  function firstConcreteOfDay(di) {
    for (var j = 0; j < stEls.length; j++) {
      if (stEls[j].closest('section.day') === days[di] && onChosenPath(stEls[j])) return j;
    }
    return -1;
  }
  function goDay(di) {
    if (di < 0 || di >= days.length) return;
    var cur = dayIndexOf(stEls[stCur]);
    if (cur >= 0 && cur !== di) setDayChecked(days[cur], false);   // ocultar el actual
    setDayChecked(days[di], true);                                 // mostrar el nuevo
    days.forEach(function (d, i2) { d.classList.toggle('open', i2 === di); });
    syncLayers();
    var j = firstConcreteOfDay(di);
    if (j >= 0) stGoTo(j); else stRender();
  }
  function dsRender() {
    var di = dayIndexOf(stEls[stCur]);
    var h3 = di >= 0 ? days[di].querySelector('h3') : null;
    dayBar.querySelector('.ds-cur').textContent =
      h3 ? h3.textContent.replace(/\s+/g, ' ').trim() : '—';
    dayBar.querySelector('.ds-prev').disabled = di <= 0;
    dayBar.querySelector('.ds-next').disabled = di < 0 || di >= days.length - 1;
  }
  dayBar.querySelector('.ds-prev').addEventListener('click', function () {
    goDay(dayIndexOf(stEls[stCur]) - 1);
  });
  dayBar.querySelector('.ds-next').addEventListener('click', function () {
    goDay(dayIndexOf(stEls[stCur]) + 1);
  });
  stRender();

  // teléfono: el panel es un sobrepuesto que abre el botón ☰; al elegir algo
  // se cierra solo para dejar ver el popup
  var narrow = window.matchMedia('(max-width: 820px)');
  var toggle = document.createElement('button');
  toggle.className = 'panel-toggle';
  toggle.type = 'button';
  toggle.textContent = '☰';
  toggle.title = 'Días';
  document.body.appendChild(toggle);
  toggle.addEventListener('click', function () {
    document.body.classList.toggle('panel-open');
  });
  function closePanelIfNarrow() {
    if (narrow.matches) document.body.classList.remove('panel-open');
  }

  // toggle ⏳: ver el tiempo LIBRE entre pasos (huecos calculados, data-free)
  var freeBtn = document.createElement('button');
  freeBtn.className = 'free-toggle';
  freeBtn.type = 'button';
  freeBtn.textContent = '⏳';
  freeBtn.title = 'Ver tiempo libre entre pasos';
  document.body.appendChild(freeBtn);
  if (localStorage.getItem('mapa-free') === '1') {
    document.body.classList.add('show-free');
    freeBtn.classList.add('on');
  }
  freeBtn.addEventListener('click', function () {
    var on = document.body.classList.toggle('show-free');
    localStorage.setItem('mapa-free', on ? '1' : '0');
    freeBtn.classList.toggle('on', on);
  });

  // links a modal: si la clave tiene geometría, la tarjeta va al popup del
  // mapa (captura, para ganarle al dialog de itinerario.js); si no, dialog
  document.addEventListener('click', function (e) {
    var link = e.target.closest('.modal-link');
    if (!link || !e.target.closest('.panel')) return;
    if (devMode) {                        // en modo dev la fila se EDITA
      var liDev = rowOf(link);
      if (liDev) {
        e.preventDefault();
        e.stopPropagation();
        selectRow(liDev);
        openDevEditor(liDev);
      }
      return;
    }
    var href = link.getAttribute('href') || '';
    if (href.indexOf('#m-') !== 0) return;
    var key = href.slice(3);
    var linkRow = rowOf(link);
    if (showOnMap(key, link.textContent, linkRow && linkRow.id)) {
      e.preventDefault();
      e.stopPropagation();
      selectRow(linkRow);
      updateHash(key, linkRow && linkRow.id);
      closePanelIfNarrow();
    }
  }, true);

  // click en la fila (fuera de casillas/links): seleccionar y mostrar su clave
  document.querySelector('.panel').addEventListener('click', function (e) {
    if (e.target.closest('input') || e.target.closest('.modal-link') ||
        e.target.closest('.day-head') || e.target.closest('.day-nav')) return;
    var li = rowOf(e.target);
    if (!li) return;
    selectRow(li);
    stSyncTo(li);
    if (devMode) { updateHash(null, li.id); openDevEditor(li); return; }
    var key = li.dataset.location || li.dataset.transit;
    if (key) {
      var title = li.querySelector('.title');
      if (showOnMap(key, title ? title.textContent : key, li.id)) {
        updateHash(key, li.id);
        closePanelIfNarrow();
      }
    } else {
      updateHash(null, li.id);
      var ks = keysUnder(li);          // fila-contenedor: enfocar TODO lo suyo
      if (ks.length) {
        haloFor(ks);
        focusKeys(ks);
      }
    }
  });

  // ---------- modo dev (solo localhost): click en fila = editar su paso YAML;
  // guardar hace POST al dev_server, que reescribe src/<viaje>/viaje.yaml y
  // reconstruye — la fila dN-rMM ES days[N-1].steps[M-1] (proyección 1:1)
  var TRIP = location.pathname.split('/').slice(-2, -1)[0] || '';
  var devMode = false;
  var drawer = null;
  if (location.hostname === 'localhost' || location.hostname === '127.0.0.1') {
    var devBtn = document.createElement('button');
    devBtn.className = 'dev-toggle';
    devBtn.type = 'button';
    devBtn.textContent = '🛠';
    devBtn.title = 'Modo dev: click en una fila = editar su YAML';
    document.body.appendChild(devBtn);
    devMode = localStorage.getItem('mapa-dev') === '1';
    devBtn.classList.toggle('on', devMode);
    devBtn.addEventListener('click', function () {
      devMode = !devMode;
      localStorage.setItem('mapa-dev', devMode ? '1' : '0');
      devBtn.classList.toggle('on', devMode);
      if (!devMode) closeDrawer();
    });
  }
  function closeDrawer() {
    stopGeomEdit();
    if (drawer) { drawer.remove(); drawer = null; }
  }

  // ---------- editor de GEOMETRÍA de un segmento (modo dev) ----------
  // arrastra los vértices · click en un punto medio inserta uno · click
  // derecho sobre un vértice lo borra · «Ajustar a calle» pega la línea a la
  // vialidad más cercana (OSRM público) — cada cambio reescribe la línea
  // coords: del YAML de la entidad en el cajón; Guardar referencia persiste
  var geomEd = null;   // {key, coords, group, ta, msg}
  function stopGeomEdit() {
    if (geomEd) {
      if (map) map.removeLayer(geomEd.group);
      geomEd = null;
    }
  }
  function geomToYaml() {
    if (!geomEd) return;
    var s = geomEd.coords.map(function (c) {
      return c[0].toFixed(6) + ',' + c[1].toFixed(6);
    }).join(' ');
    var ta = geomEd.ta;
    // OJO: el dump del server puede PLEGAR la escalar larga en varias líneas
    // (más indentadas): reemplazar el bloque completo, no solo la primera
    var re = /^([ \t]*)coords:[^\n]*(?:\n\1[ \t]+[^\n]*)*/m;
    if (re.test(ta.value)) {
      ta.value = ta.value.replace(re, '$1coords: ' + s);
    } else {
      ta.value = ta.value.replace(/\s*$/, '\n') + 'coords: ' + s + '\n';
    }
    GEO.transits[geomEd.key] = GEO.transits[geomEd.key] || { color: '#7a6f63', mode: 'walk' };
    GEO.transits[geomEd.key].coords = geomEd.coords;
  }
  function startGeomEdit(key, ta, msg) {
    stopGeomEdit();
    if (!map) return;
    var tr = GEO.transits[key];
    var coords = tr && tr.coords.length
      ? tr.coords.map(function (c) { return [c[0], c[1]]; })
      : (function () {
        // transit NUEVO sin geometría: sembrar la línea entre el último punto
        // del paso previo y el primero del siguiente (donde se referencia)
        for (var j = 0; j < stEls.length; j++) {
          if (stEls[j].dataset.transit !== key) continue;
          var pts = [], a, p;
          for (a = j - 1; a >= 0; a--) {
            if (!sameBranch(stEls[j], stEls[a])) continue;
            p = anchorPoint(stEls[a], true);
            if (p) { pts.push([p[0], p[1]]); break; }
          }
          for (a = j + 1; a < stEls.length; a++) {
            if (!sameBranch(stEls[j], stEls[a])) continue;
            p = anchorPoint(stEls[a], false);
            if (p) { pts.push([p[0], p[1]]); break; }
          }
          if (pts.length === 2) return pts;
          break;
        }
        var c = map.getCenter(), d = 0.002;
        return [[c.lat, c.lng - d], [c.lat, c.lng + d]];
      })();
    var group = L.featureGroup().addTo(map);
    geomEd = { key: key, coords: coords, group: group, ta: ta, msg: msg };
    function redraw() {
      group.clearLayers();
      var line = L.polyline(coords, { color: '#d4a017', weight: 4, opacity: .9, dashArray: '1 7' });
      group.addLayer(line);
      coords.forEach(function (c, i) {
        var h = L.marker(c, {
          draggable: true,
          icon: L.divIcon({ className: 'geo-pt', iconSize: [12, 12] })
        });
        h.on('drag', function (e) {
          var ll = e.target.getLatLng();
          coords[i] = [ll.lat, ll.lng];
          line.setLatLngs(coords);
        });
        h.on('dragend', function () { redraw(); geomToYaml(); });
        h.on('contextmenu', function () {
          if (coords.length > 2) { coords.splice(i, 1); redraw(); geomToYaml(); }
        });
        group.addLayer(h);
      });
      for (var i = 0; i + 1 < coords.length; i++) {
        (function (i) {
          var mid = [(coords[i][0] + coords[i + 1][0]) / 2, (coords[i][1] + coords[i + 1][1]) / 2];
          var m = L.marker(mid, { icon: L.divIcon({ className: 'geo-mid', iconSize: [10, 10] }) });
          m.on('click', function () {
            coords.splice(i + 1, 0, mid);
            redraw();
            geomToYaml();
          });
          group.addLayer(m);
        })(i);
      }
    }
    redraw();
    map.flyToBounds(L.latLngBounds(coords).pad(.3), { duration: .4 });
  }
  function snapGeomToRoads() {
    if (!geomEd) return;
    var msg = geomEd.msg;
    msg.textContent = 'ajustando a calles…';
    // punto por punto contra /nearest (el /match del OSRM público rechaza
    // trazas largas con TooBig); caminatas van al perfil PEATONAL de FOSSGIS
    // (incluye calles peatonales), lo demás al de auto
    var tr0 = GEO.transits[geomEd.key];
    var base = (!tr0 || tr0.mode === 'walk')
      ? 'https://routing.openstreetmap.de/routed-foot/nearest/v1/foot/'
      : 'https://router.project-osrm.org/nearest/v1/driving/';
    var reqs = geomEd.coords.map(function (c) {
      return fetch(base + c[1].toFixed(6) + ',' + c[0].toFixed(6))
        .then(function (r) { return r.json(); })
        .then(function (d) {
          var w = d.code === 'Ok' && d.waypoints && d.waypoints[0];
          return w && w.location ? [w.location[1], w.location[0]] : null;
        })
        .catch(function () { return null; });
    });
    Promise.all(reqs).then(function (snapped) {
      if (!geomEd) return;
      var moved = 0;
      snapped.forEach(function (p, i) {
        if (p) { geomEd.coords[i] = p; moved += 1; }
      });
      geomToYaml();                                        // persistir en GEO + textarea
      startGeomEdit(geomEd.key, geomEd.ta, geomEd.msg);    // redibujar con lo ajustado
      geomEd.msg.textContent = 'snap ✓ (' + moved + '/' + snapped.length + ' puntos)';
    });
  }
  function openDevEditor(li) {
    var m = /^d(\d+)-r(\d+)$/.exec(li.id || '');
    if (!m) return;   // sub-pasos de planes: sin id de fila (edítalos en el YAML)
    closeDrawer();
    // «todo» de la fila: identidad, claves, horario visible y conflicto
    var facts = ['fila ' + li.id + '  (days[' + (m[1] - 1) + '].steps[' + (m[2] - 1) + '])'];
    ['location', 'transit', 'mode'].forEach(function (k) {
      if (li.dataset[k]) facts.push(k + ': ' + li.dataset[k]);
    });
    var t = li.querySelector('time');
    if (t) facts.push('horario: ' + t.textContent.replace(/\s+/g, ' ').trim());
    var w = li.querySelector('.warn');
    if (w) facts.push('⚠️ ' + (w.getAttribute('title') || ''));
    drawer = document.createElement('div');
    drawer.className = 'dev-drawer';
    drawer.innerHTML = '<div class="dev-info"></div>' +
      '<textarea class="dev-step" spellcheck="false">cargando…</textarea>' +
      '<div class="dev-btns"><button class="dev-save" type="button">Guardar</button>' +
      '<button class="dev-rebuild" type="button">Rebuild</button>' +
      '<button class="dev-close" type="button">Cancelar</button><span class="dev-msg"></span></div>' +
      '<div class="dev-btns dev-step-ops">' +
      '<button class="dev-add-before" type="button" title="Insertar un paso nuevo ANTES de esta fila">+ antes</button>' +
      '<button class="dev-add-after" type="button" title="Insertar un paso nuevo DESPUÉS de esta fila">+ después</button>' +
      '<button class="dev-move-up" type="button" title="Subir esta fila un lugar">▲ subir</button>' +
      '<button class="dev-move-down" type="button" title="Bajar esta fila un lugar">▼ bajar</button></div>' +
      '<div class="dev-refs"></div>' +
      '<textarea class="dev-entity" spellcheck="false" hidden></textarea>' +
      '<div class="dev-btns dev-entity-btns" hidden>' +
      '<button class="dev-save-entity" type="button">Guardar referencia</button>' +
      '<button class="dev-geom" type="button" hidden ' +
      'title="Arrastra vértices · click en punto medio inserta · click derecho borra">Geometría</button>' +
      '<button class="dev-snap" type="button" hidden>Ajustar a calle</button>' +
      '<span class="dev-entity-name"></span></div>';
    drawer.querySelector('.dev-info').textContent = facts.join('\n');
    document.body.appendChild(drawer);
    var ta = drawer.querySelector('.dev-step');
    var msg = drawer.querySelector('.dev-msg');

    // lo REFERENCIADO por la fila (location/transit + @refs de los textos):
    // un botón por clave carga su YAML del catálogo para editarlo también
    var refKeys = [];
    if (li.dataset.location) refKeys.push(li.dataset.location);
    if (li.dataset.transit) refKeys.push(li.dataset.transit);
    li.querySelectorAll('.modal-link').forEach(function (a) {
      var h = a.getAttribute('href') || '';
      if (h.indexOf('#m-') === 0 && refKeys.indexOf(h.slice(3)) < 0) refKeys.push(h.slice(3));
    });
    var refsBox = drawer.querySelector('.dev-refs');
    var entTa = drawer.querySelector('.dev-entity');
    var entBtns = drawer.querySelector('.dev-entity-btns');
    var entName = drawer.querySelector('.dev-entity-name');
    var geomBtn = drawer.querySelector('.dev-geom');
    var snapBtn = drawer.querySelector('.dev-snap');
    var entCur = null;    // {kind, key} de la entidad cargada
    geomBtn.addEventListener('click', function () {
      if (geomEd) {
        stopGeomEdit();
        geomBtn.textContent = 'Geometría';
        snapBtn.hidden = true;
        msg.textContent = 'edición de geometría terminada';
        return;
      }
      if (!entCur) { msg.textContent = 'carga primero una referencia'; return; }
      try {
        startGeomEdit(entCur.key, entTa, msg);
      } catch (err) {
        msg.textContent = 'geometría error: ' + (err && err.message || err);
        return;
      }
      geomBtn.textContent = 'Terminar geometría';
      snapBtn.hidden = false;
    });
    snapBtn.addEventListener('click', snapGeomToRoads);
    refKeys.forEach(function (key) {
      var b = document.createElement('button');
      b.type = 'button';
      b.textContent = key;
      b.addEventListener('click', function () {
        msg.textContent = '';
        fetch('/api/entity?trip=' + encodeURIComponent(TRIP) + '&key=' + encodeURIComponent(key))
          .then(function (r) { return r.json(); })
          .then(function (d) {
            if (!d.ok) { msg.textContent = 'error: ' + d.error; return; }
            entCur = { kind: d.kind, key: key };
            entName.textContent = d.kind + ' · ' + key;
            entTa.value = d.yaml;
            entTa.hidden = false;
            entBtns.hidden = false;
            stopGeomEdit();
            geomBtn.hidden = d.kind !== 'transits';
            geomBtn.textContent = 'Geometría';
            snapBtn.hidden = true;
          })
          .catch(function (e) { msg.textContent = 'error: ' + e; });
      });
      refsBox.appendChild(b);
    });
    drawer.querySelector('.dev-save-entity').addEventListener('click', function () {
      if (!entCur) return;
      msg.textContent = 'guardando referencia…';
      fetch('/api/entity', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ trip: TRIP, kind: entCur.kind, key: entCur.key, yaml: entTa.value })
      }).then(function (r) { return r.json(); })
        .then(function (d) {
          msg.textContent = d.ok ? 'referencia guardada ✓ (pendiente rebuild)' : 'error: ' + d.error;
        })
        .catch(function (e) { msg.textContent = 'error: ' + e; });
    });
    fetch('/api/step?trip=' + encodeURIComponent(TRIP) + '&day=' + m[1] + '&step=' + m[2])
      .then(function (r) { return r.json(); })
      .then(function (d) { ta.value = d.ok ? d.yaml : 'error: ' + d.error; })
      .catch(function (e) { ta.value = 'error: ' + e; });
    drawer.querySelector('.dev-close').addEventListener('click', closeDrawer);
    // Guardar SOLO escribe el YAML (se pueden editar varias filas); Rebuild
    // reconstruye una vez y recarga — el hash #@fila nos regresa aquí mismo
    drawer.querySelector('.dev-save').addEventListener('click', function () {
      msg.textContent = 'guardando…';
      fetch('/api/step', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ trip: TRIP, day: +m[1], step: +m[2], yaml: ta.value })
      }).then(function (r) { return r.json(); })
        .then(function (d) {
          msg.textContent = d.ok ? 'guardado ✓ (pendiente rebuild)' : 'error: ' + d.error;
        })
        .catch(function (e) { msg.textContent = 'error: ' + e; });
    });
    drawer.querySelector('.dev-rebuild').addEventListener('click', function () {
      msg.textContent = 'rebuild…';
      fetch('/api/rebuild', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ trip: TRIP })
      }).then(function (r) { return r.json(); })
        .then(function (d) {
          if (d.ok) {
            msg.textContent = 'rebuild ok — recargando…';
            setTimeout(function () { location.reload(); }, 400);
          } else {
            msg.textContent = 'error: ' + d.error;
          }
        })
        .catch(function (e) { msg.textContent = 'error: ' + e; });
    });
    // insertar / mover pasos: el server reescribe days[].steps[] y al aceptar
    // se pregunta si recalcular (rebuild + recarga posicionada en el paso)
    function stepOp(path, body) {
      msg.textContent = '…';
      fetch(path, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(Object.assign({ trip: TRIP, day: +m[1], step: +m[2] }, body))
      }).then(function (r) { return r.json(); })
        .then(function (d) {
          if (!d.ok) { msg.textContent = 'error: ' + d.error; return; }
          var target = 'd' + m[1] + '-r' + String(d.step).padStart(2, '0');
          if (window.confirm('Guardado. ¿Recalcular (rebuild) ahora?')) {
            fetch('/api/rebuild', {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({ trip: TRIP })
            }).then(function (r) { return r.json(); })
              .then(function (d2) {
                if (!d2.ok) { msg.textContent = 'error: ' + d2.error; return; }
                location.hash = '#@' + target;
                location.reload();
              })
              .catch(function (e) { msg.textContent = 'error: ' + e; });
          } else {
            msg.textContent = 'guardado ✓ (pendiente rebuild — los ids de fila ya cambiaron)';
          }
        })
        .catch(function (e) { msg.textContent = 'error: ' + e; });
    }
    drawer.querySelector('.dev-add-before').addEventListener('click', function () {
      stepOp('/api/step-insert', { where: 'before' });
    });
    drawer.querySelector('.dev-add-after').addEventListener('click', function () {
      stepOp('/api/step-insert', { where: 'after' });
    });
    drawer.querySelector('.dev-move-up').addEventListener('click', function () {
      stepOp('/api/step-move', { dir: -1 });
    });
    drawer.querySelector('.dev-move-down').addEventListener('click', function () {
      stepOp('/api/step-move', { dir: 1 });
    });
  }

  // ---------- llegada: restaurar el DÓNDE ESTAMOS desde el hash ----------
  // #dN = día exclusivo · #@fila = fila seleccionada · #m-clave@fila = popup;
  // en modo dev la fila reabre su editor. itinerario.js pudo abrir su dialog
  // con el mismo hash: aquí manda el mapa, se cierra.
  (function restore() {
    var overlayEl = document.getElementById('overlay');
    var m = /^#(?:m-([^@]+))?(?:@(.+))?$/.exec(location.hash || '');
    var dm = /^#(d\d+)$/.exec(location.hash || '');
    if (dm) {
      // #dN: ese día completo seleccionado y el stepper en su primer paso
      var sec = document.getElementById(dm[1]);
      if (sec) goDay(days.indexOf(sec));
      return;
    }
    if (!m || (!m[1] && !m[2])) {
      // sin posición en el hash: día 1 completo seleccionado, stepper en su
      // primer paso concreto (sin volar: el encuadre inicial ya lo hace)
      if (days.length) {
        setDayChecked(days[0], true);
        days.forEach(function (d, i2) { d.classList.toggle('open', i2 === 0); });
        var j0 = firstConcreteOfDay(0);
        if (j0 >= 0) { stCur = j0; stRender(); }
        schedSync();
      }
      return;
    }
    if (overlayEl && overlayEl.open) overlayEl.close();
    var li = m[2] ? document.getElementById(m[2]) : null;
    if (li) {
      openDayOf(li);
      // el día de la fila del hash llega ACTIVO (visible en el mapa)
      var liDay = li.closest('section.day');
      if (liDay) setDayChecked(liDay, true);
      selectRow(li);
      stSyncTo(li);
      li.scrollIntoView({ block: 'center' });
      schedSync();
    }
    if (devMode && li) {
      openDevEditor(li);
    } else if (m[1]) {
      var title = li && li.querySelector('.title');
      showOnMap(m[1], title ? title.textContent : m[1], li && li.id);
    }
  })();
})();
