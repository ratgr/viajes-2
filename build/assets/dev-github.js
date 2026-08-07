/* dev-github.js — edición EN LÍNEA sin servidor: el cajón dev habla con la
   GitHub contents API usando los spans precalculados del build (GEO.edit).
   Misma semántica de empalme de texto que dev_server (comentarios intactos);
   los spans se corren por el delta de líneas tras cada commit. PAT
   fine-grained (contents RW del repo) pegado una vez → localStorage. */
(function () {
  'use strict';
  var ED = null;
  try {
    ED = (JSON.parse(document.getElementById('geo').textContent) || {}).edit || null;
  } catch (e) { /* página sin GEO */ }
  var TK = 'gh-pat';
  var st = { text: null, sha: null, steps: null, ents: null, touched: false };

  function hdrs(json) {
    var h = { Accept: 'application/vnd.github+json' };
    var t = localStorage.getItem(TK);
    if (t) h.Authorization = 'Bearer ' + t;
    if (json) h['Content-Type'] = 'application/json';
    return h;
  }
  function gh(p, opt) {
    opt = opt || {};
    opt.headers = hdrs(!!opt.body);
    return fetch('https://api.github.com' + p, opt).then(function (r) {
      return r.json().then(function (j) {
        if (!r.ok) throw new Error(j && j.message || ('HTTP ' + r.status));
        return j;
      });
    });
  }
  function deB64(b) {
    var bin = atob(b.replace(/\n/g, ''));
    var a = new Uint8Array(bin.length);
    for (var i = 0; i < bin.length; i++) a[i] = bin.charCodeAt(i);
    return new TextDecoder().decode(a);
  }
  function enB64(s) {
    var a = new TextEncoder().encode(s);
    var bin = '';
    for (var i = 0; i < a.length; i += 8192) {
      bin += String.fromCharCode.apply(null, a.subarray(i, i + 8192));
    }
    return btoa(bin);
  }
  function ensure() {
    if (st.text !== null) return Promise.resolve();
    return gh('/repos/' + ED.repo + '/contents/' + ED.path + '?ref=' + ED.branch)
      .then(function (d) {
        if (d.sha !== ED.sha && !st.touched) {
          throw new Error('el sitio va detrás del último commit — espera el deploy (~90 s) y recarga');
        }
        st.text = deB64(d.content);
        st.sha = d.sha;
        st.steps = JSON.parse(JSON.stringify(ED.steps));
        st.ents = JSON.parse(JSON.stringify(ED.entities));
      });
  }
  function lines() { return st.text.split(/(?<=\n)/); }
  // ports EXACTOS de dev_server._dedent_line / raw_step / _reindent
  function dedentLine(ln, col) {
    if (!ln.trim()) return ln.endsWith('\n') ? '\n' : ln;
    return ln.slice(0, col).trim() === '' ? ln.slice(col) : ln.replace(/^\s+/, '');
  }
  function sliceStep(sp) {
    var ls = lines().slice(sp[0], sp[1]);
    return ls.map(function (ln, i) {
      if (i === 0) {
        return ln.slice(0, sp[2] + 2).trim() === '-' ? ln.slice(sp[2] + 2) : ln.replace(/^\s+/, '');
      }
      return dedentLine(ln, sp[2] + 2);
    }).join('');
  }
  function reindentStep(raw, col) {
    var pad = new Array(col + 3).join(' ');
    return raw.split(/(?<=\n)/).map(function (ln, i) {
      var body = ln.replace(/\n$/, '');
      if (i === 0) return new Array(col + 1).join(' ') + '- ' + body + '\n';
      return body.trim() ? pad + body + '\n' : '\n';
    }).join('');
  }
  function shift(from, delta) {
    [st.steps, st.ents].forEach(function (m) {
      Object.keys(m).forEach(function (k) {
        var sp = m[k];
        var a = sp.length === 4 ? 1 : 0;   // entidades: [kind, a, b, col]
        if (sp[a] >= from) { sp[a] += delta; sp[a + 1] += delta; }
        else if (sp[a + 1] > from) { sp[a + 1] += delta; }
      });
    });
  }
  function commit(a, b, block, msg) {
    var ls = lines();
    var nuevo = ls.slice(0, a).join('') + block + ls.slice(b).join('');
    return gh('/repos/' + ED.repo + '/contents/' + ED.path, {
      method: 'PUT',
      body: JSON.stringify({ message: msg, branch: ED.branch,
                             content: enB64(nuevo), sha: st.sha })
    }).then(function (d) {
      st.text = nuevo;
      st.sha = d.content.sha;
      st.touched = true;
      shift(b, block.split('\n').length - 1 - (b - a));
      return d;
    });
  }
  function stepId(q) { return 'd' + q.day + '-r' + ('0' + q.step).slice(-2) + (q.sub || ''); }
  function spanOf(q) {
    var sp = st.steps[stepId(q)];
    if (!sp) throw new Error('fila sin span (¿ids renumerados? espera el deploy)');
    return sp;
  }
  function waitAction() {
    var t0 = Date.now();
    return new Promise(function (res, rej) {
      (function poll() {
        fetch('https://api.github.com/repos/' + ED.repo + '/actions/runs?per_page=1')
          .then(function (r) { return r.json(); })
          .then(function (d) {
            var run = (d.workflow_runs || [])[0];
            if (run && run.status === 'completed' && new Date(run.created_at) > new Date(t0 - 300000)) {
              return res({ ok: true, build: 'publicado (' + run.conclusion + ')' });
            }
            if (Date.now() - t0 > 360000) return res({ ok: true, build: 'sigue corriendo — recarga en un rato' });
            setTimeout(poll, 12000);
          })
          .catch(rej);
      })();
    });
  }

  window.DevGH = {
    available: function () { return !!(ED && ED.steps); },
    hasToken: function () { return !!localStorage.getItem(TK); },
    promptToken: function () {
      // diálogo con INSTRUCCIONES completas: cualquiera puede seguirlo
      return new Promise(function (res, rej) {
        var d = document.createElement('div');
        d.className = 'gh-login';
        d.innerHTML =
          '<h3>🛠 Editar en línea</h3>' +
          '<p>Necesitas un token de GitHub (una sola vez):</p>' +
          '<ol>' +
          '<li><a href="https://github.com/settings/personal-access-tokens/new" target="_blank" rel="noopener">Abrir GitHub → nuevo token ↗</a></li>' +
          '<li><b>Repository access</b>: <i>Only select repositories</i> → <b>' + ED.repo + '</b></li>' +
          '<li><b>Permissions</b> → <b>Contents</b>, <b>Pages</b> y <b>Pull requests</b>: <i>Read and write</i> (lo demás en No access)</li>' +
          '<li><b>Generate token</b> y cópialo (empieza con <code>github_pat_</code>)</li>' +
          '</ol>' +
          '<input type="password" placeholder="github_pat_…" spellcheck="false">' +
          '<div class="gh-login-btns"><button type="button" class="gh-ok">Entrar</button>' +
          '<button type="button" class="gh-no">Cancelar</button><span class="gh-msg"></span></div>' +
          '<p class="gh-note">El token se guarda solo en ESTE navegador. Para editar también necesitas ser colaborador del repo.</p>';
        document.body.appendChild(d);
        var inp = d.querySelector('input');
        var msg = d.querySelector('.gh-msg');
        inp.focus();
        function go() {
          var t = inp.value.trim();
          if (!t) { msg.textContent = 'pega el token'; return; }
          msg.textContent = 'validando…';
          localStorage.setItem(TK, t);
          gh('/user').then(function (u) {
            d.remove();
            res(u.login);
          }).catch(function (e) {
            localStorage.removeItem(TK);
            msg.textContent = '✗ ' + (e.message || 'token inválido');
          });
        }
        d.querySelector('.gh-ok').addEventListener('click', go);
        inp.addEventListener('keydown', function (e) { if (e.key === 'Enter') go(); });
        d.querySelector('.gh-no').addEventListener('click', function () {
          d.remove();
          rej(new Error('cancelado'));
        });
      });
    },
    api: function (path, body) {
      var p = path.split('?')[0];
      var q = body || {};
      if (path.indexOf('?') >= 0) {
        new URLSearchParams(path.split('?')[1]).forEach(function (v, k) { q[k] = v; });
      }
      var who = ' (web)';
      return ensure().then(function () {
        if (p === '/api/step' && body === undefined) {
          return { ok: true, yaml: sliceStep(spanOf(q)) };
        }
        if (p === '/api/step') {
          var sp = spanOf(q);
          return commit(sp[0], sp[1], reindentStep(q.yaml.replace(/\n?$/, '\n'), sp[2]),
                        'dev: paso ' + stepId(q) + who).then(function () { return { ok: true }; });
        }
        if (p === '/api/entity' && body === undefined) {
          var e = st.ents[q.key];
          if (!e) throw new Error("'" + q.key + "' no está en los catálogos");
          return { ok: true, kind: e[0],
                   yaml: lines().slice(e[1], e[2]).map(function (ln) { return dedentLine(ln, e[3]); }).join('') };
        }
        if (p === '/api/entity') {
          var e2 = st.ents[q.key];
          var pad = e2 ? new Array(e2[3] + 1).join(' ') : '  ';
          var block = q.yaml.replace(/\n?$/, '\n').split(/(?<=\n)/).map(function (ln) {
            return ln.trim() ? pad + ln.replace(/\n$/, '') + '\n' : '\n';
          }).join('');
          if (e2) {
            return commit(e2[1], e2[2], block, 'dev: ' + q.kind + '.' + q.key + who)
              .then(function () { return { ok: true }; });
          }
          // clave NUEVA: al final del catálogo = tras el último span de ese kind
          var last = null;
          Object.keys(st.ents).forEach(function (k) {
            var s2 = st.ents[k];
            if (s2[0] === q.kind && (!last || s2[2] > last[2])) last = s2;
          });
          if (!last) throw new Error('catálogo ' + q.kind + ' vacío');
          return commit(last[2], last[2], block, 'dev: nueva ' + q.kind + '.' + q.key + who)
            .then(function () {
              st.ents[q.key] = [q.kind, last[2], last[2] + block.split('\n').length - 1, last[3]];
              return { ok: true };
            });
        }
        if (p === '/api/step-insert') {
          var si = spanOf(q);
          var at = q.where === 'before' ? si[0] : si[1];
          var nb = new Array(si[2] + 1).join(' ') + '- title: (nuevo paso)\n';
          return commit(at, at, nb, 'dev: inserta paso en d' + q.day + who).then(function () {
            // mismo contrato que el server: número (1-based) del paso nuevo
            return { ok: true, step: q.where === 'before' ? +q.step : +q.step + 1 };
          });
        }
        if (p === '/api/step-move') {
          var a1 = spanOf(q);
          var q2 = { day: q.day, step: +q.step + (+q.dir), sub: q.sub };
          var b1 = spanOf(q2);
          var L = lines();
          var lo = Math.min(a1[0], b1[0]);
          var hi = Math.max(a1[1], b1[1]);
          var blkA = L.slice(a1[0], a1[1]).join('');
          var blkB = L.slice(b1[0], b1[1]).join('');
          var merged = a1[0] < b1[0] ? blkB + blkA : blkA + blkB;
          return commit(lo, hi, merged, 'dev: mueve paso en d' + q.day + who)
            .then(function () { return { ok: true, step: q2.step }; });
        }
        if (p === '/api/rebuild') {
          return waitAction();
        }
        throw new Error('endpoint sin soporte en modo GitHub: ' + p);
      }).then(function (r) { return r; }, function (e) { return { ok: false, error: String(e.message || e) }; });
    }
  };
})();
