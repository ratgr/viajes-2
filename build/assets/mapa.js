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
  function showOnMap(key, fallbackTitle, activeRowId) {
    if (!map) return false;
    var content = modalHtml(key) ||
      '<div class="modal"><h3>' + (fallbackTitle || key) + '</h3></div>';
    var loc = GEO.locations[key];
    var tr = GEO.transits[key];
    clearTemp();
    if (loc) {
      map.flyTo(loc, Math.max(map.getZoom(), 15), { duration: .5 });
      openCardPopup(loc, content + dayPieces(key, activeRowId));
      return true;
    }
    if (tr && tr.coords.length) {
      tempLayer = L.polyline(tr.coords, {
        color: tr.color, weight: tr.mode === 'walk' ? 3 : 5, opacity: .9,
        dashArray: tr.mode === 'walk' ? '4 7' : null
      }).addTo(map);
      map.flyToBounds(tempLayer.getBounds().pad(.25), { duration: .5 });
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

  // ---------- capas vivas: el mapa muestra TODO lo visible en la barra ----------
  // cada fila/sub-fila con clave dibuja su geometría si está a la vista (día
  // abierto, opción desplegada, ojo…); la casilla la ANCLA aunque se oculte
  var liveLayers = {};    // clave → capa Leaflet

  function makeLayer(key) {
    var loc = GEO.locations[key];
    var tr = GEO.transits[key];
    var ly = null;
    if (loc) {
      ly = L.circleMarker(loc, { radius: 6, color: '#fff', weight: 2, fillColor: '#b23a2a', fillOpacity: 1 });
    } else if (tr && tr.coords.length) {
      ly = L.polyline(tr.coords, {
        color: tr.color, weight: tr.mode === 'walk' ? 3 : 5, opacity: .85,
        dashArray: tr.mode === 'walk' ? '4 7' : null
      });
    }
    if (ly) {
      ly.on('click', function () {
        var content = modalHtml(key) || '<div class="modal"><h3>' + key + '</h3></div>';
        if (loc) content += dayPieces(key, null);
        openCardPopup(loc || tr.coords[Math.floor(tr.coords.length / 2)], content);
      });
    }
    return ly;
  }
  function syncLayers() {
    if (!map) return;
    var want = {};
    document.querySelectorAll('.panel [data-location], .panel [data-transit]').forEach(function (el) {
      var key = el.dataset.location || el.dataset.transit;
      if (!key || want[key]) return;
      var ck = el.querySelector(':scope > .ck');
      if (el.offsetParent !== null || (ck && ck.checked)) want[key] = true;
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
      setTimeout(function () { syncLayers(); fitToLayers(); }, 60);
    });
  });
  setTimeout(function () { syncLayers(); fitToLayers(); }, 150);   // arranque

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
    if (drawer) { drawer.remove(); drawer = null; }
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
      '<div class="dev-refs"></div>' +
      '<textarea class="dev-entity" spellcheck="false" hidden></textarea>' +
      '<div class="dev-btns dev-entity-btns" hidden>' +
      '<button class="dev-save-entity" type="button">Guardar referencia</button>' +
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
    var entCur = null;    // {kind, key} de la entidad cargada
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
      var sec = document.getElementById(dm[1]);
      if (sec) days.forEach(function (d) { d.classList.toggle('open', d === sec); });
      return;
    }
    if (!m || (!m[1] && !m[2])) return;
    if (overlayEl && overlayEl.open) overlayEl.close();
    var li = m[2] ? document.getElementById(m[2]) : null;
    if (li) {
      openDayOf(li);
      selectRow(li);
      li.scrollIntoView({ block: 'center' });
    }
    if (devMode && li) {
      openDevEditor(li);
    } else if (m[1]) {
      var title = li && li.querySelector('.title');
      showOnMap(m[1], title ? title.textContent : m[1], li && li.id);
    }
  })();
})();
