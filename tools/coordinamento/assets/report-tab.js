// Interazioni del report a schede: schede, filtri e selezione del portafoglio (che filtra il dettaglio e il piano operativo),
// varianti 1a/1b del dettaglio nel tempo, apertura dei TSK di una sezione, isolamento delle dipendenze al passaggio,
// filtri del piano operativo. Nessun dato viene calcolato qui: i KPI filtrati sono il numero delle righe mostrate.
(function () {
  var $ = function (s, r) { return Array.prototype.slice.call((r || document).querySelectorAll(s)); };

  $('.tab').forEach(function (b) {
    b.addEventListener('click', function () {
      $('.tab').forEach(function (x) { x.classList.toggle('on', x === b); });
      $('.pane').forEach(function (p) { p.hidden = p.getAttribute('data-pane') !== b.getAttribute('data-tab'); });
    });
  });

  // ---- piano operativo: filtri per obiettivo e persona
  var fob = 'tutti', fown = 'tutti';
  function filtra() {
    var n = 0, p0 = 0, pronti = 0, attesa = 0;
    $('.grp').forEach(function (g) {
      var vis = 0;
      $('.tk', g).forEach(function (t) {
        var ok = (fob === 'tutti' || t.getAttribute('data-ob') === fob) && (fown === 'tutti' || t.getAttribute('data-own') === fown);
        t.hidden = !ok;
        if (ok) {
          vis++; n++;
          p0 += +t.getAttribute('data-p0'); pronti += +t.getAttribute('data-pronto'); attesa += +t.getAttribute('data-attesa');
        }
      });
      g.hidden = vis === 0;
    });
    // sezioni completate: nessun TSK da filtrare, seguono il filtro obiettivo e spariscono col filtro persona
    $('.grp-fatta').forEach(function (g) {
      g.hidden = (fob !== 'tutti' && g.getAttribute('data-ob') !== fob) || fown !== 'tutti';
    });
    var set = function (id, v) { var el = document.getElementById(id); if (el) el.textContent = v; };
    set('kpi-n', n); set('kpi-p0', p0); set('kpi-pronti', pronti); set('kpi-attesa', attesa);
    $('.nessuno').forEach(function (x) { x.hidden = n > 0; });
  }
  function filtroObiettivo(id) {
    fob = id;
    $('.chip[data-fob]').forEach(function (x) { x.classList.toggle('on', x.getAttribute('data-fob') === id); });
    filtra();
  }
  $('.chip[data-fob]').forEach(function (c) {
    c.addEventListener('click', function () { filtroObiettivo(c.getAttribute('data-fob')); });
  });
  $('.chip[data-fown]').forEach(function (c) {
    c.addEventListener('click', function () {
      fown = c.getAttribute('data-fown');
      $('.chip[data-fown]').forEach(function (x) { x.classList.toggle('on', x === c); });
      filtra();
    });
  });

  // ---- portafoglio: la selezione apre il dettaglio dell'obiettivo e filtra il piano operativo
  function seleziona(id, sincronizza) {
    $('.pf-row[data-ob]').forEach(function (r) { r.classList.toggle('sel', r.getAttribute('data-ob') === id); });
    $('.obdet').forEach(function (d) { d.hidden = d.getAttribute('data-obdet') !== id; });
    if (sincronizza) filtroObiettivo(id);
  }
  var visibile = $('.obdet').filter(function (d) { return !d.hidden; })[0];
  if (visibile) seleziona(visibile.getAttribute('data-obdet'), false);
  $('.pf-row[data-ob]').forEach(function (r) {
    r.addEventListener('click', function () { seleziona(r.getAttribute('data-ob'), true); });
  });
  $('.dep[data-sel]').forEach(function (b) {
    b.addEventListener('click', function () { seleziona(b.getAttribute('data-sel'), true); });
  });
  $('.chip[data-f]').forEach(function (c) {
    c.addEventListener('click', function () {
      var f = c.getAttribute('data-f');
      $('.chip[data-f]').forEach(function (x) { x.classList.toggle('on', x === c); });
      $('.pf-row[data-ob]').forEach(function (r) {
        var ok = f === 'tutti' || (f === 'interno' || f === 'esterno') && r.getAttribute('data-tipo') === f ||
          f === 'alto' && r.getAttribute('data-alto') === '1' || f === 'gg30' && r.getAttribute('data-gg30') === '1';
        r.hidden = !ok;
      });
    });
  });

  // ---- isolamento delle dipendenze al passaggio del mouse
  function isola(righe, attr) {
    righe.forEach(function (r) {
      r.addEventListener('mouseenter', function () {
        var k = r.getAttribute(attr), rel = (r.getAttribute('data-rel') || '').split(' ');
        righe.forEach(function (x) {
          var xk = x.getAttribute(attr), xrel = (x.getAttribute('data-rel') || '').split(' ');
          x.style.opacity = (xk === k || rel.indexOf(xk) >= 0 || xrel.indexOf(k) >= 0) ? 1 : 0.28;
        });
      });
      r.addEventListener('mouseleave', function () { righe.forEach(function (x) { x.style.opacity = 1; }); });
    });
  }
  isola($('.pf-row[data-ob]'), 'data-ob');
  $('.ga').forEach(function (g) { isola($('.ga-row[data-k]', g), 'data-k'); });

  // ---- dettaglio nel tempo: varianti, TSK, fuori sezione
  $('.card').forEach(function (card) {
    var hint = card.querySelector('.hint');
    $('.tg[data-var]', card).forEach(function (b) {
      b.addEventListener('click', function () {
        if (b.disabled) return;
        var v = b.getAttribute('data-var');
        $('.tg[data-var]', card).forEach(function (x) { x.classList.toggle('on', x === b); });
        $('.var', card).forEach(function (x) { x.hidden = !x.classList.contains('v-' + v); });
        if (hint) hint.textContent = hint.getAttribute('data-hint-' + v);
      });
    });
    $('.tg[data-tg]', card).forEach(function (b) {
      b.addEventListener('click', function () {
        b.classList.toggle('on');
        var ga = card.querySelector('.ga');
        if (!ga) return;
        if (b.getAttribute('data-tg') === 'tsk') ga.classList.toggle('all-tsk', b.classList.contains('on'));
        else ga.classList.toggle('no-fuori', !b.classList.contains('on'));
      });
    });
  });
  $('.ga-row.apre').forEach(function (r) {
    r.addEventListener('click', function () {
      var k = r.getAttribute('data-k'), aperta = !r.classList.contains('exp');
      r.classList.toggle('exp', aperta);
      $('.ga-row[data-of="' + k + '"]', r.parentNode).forEach(function (t) { t.classList.toggle('open', aperta); });
    });
  });

  // ---- collega gli ID dei TSK citati nei testi: clic = apre la riga nel dettaglio nel tempo, o nel piano operativo
  var RX = /\b[A-Z]+-TSK-\d+\b/g;
  $('.ga-d, .ids, .pa .b').forEach(function (el) {
    if (el.querySelector('.idl')) return;
    var h = el.innerHTML.replace(RX, function (id) { return '<span class="idl" data-id="' + id + '">' + id + '</span>'; });
    el.innerHTML = el.classList.contains('ga-d') ? '<span>' + h + '</span>' : h;
  });
  function mostra(r) {
    r.scrollIntoView({ block: 'center' });
    r.classList.remove('flash'); void r.offsetWidth; r.classList.add('flash');
  }
  document.addEventListener('click', function (ev) {
    var l = ev.target.closest && ev.target.closest('.idl');
    if (!l) return;
    ev.stopPropagation();
    var id = l.getAttribute('data-id');
    var det = $('.obdet').filter(function (d) { return !d.hidden; })[0];
    var r = det && det.querySelector('.ga-row[data-k="t-' + id + '"]');
    if (r && !det.querySelector('.v-a').hidden) {
      var of = r.getAttribute('data-of');
      if (of) { var p = det.querySelector('.ga-row[data-k="' + of + '"]'); if (p && !p.classList.contains('exp')) p.click(); }
      r.classList.add('open');
      var ga = r.closest('.ga'); if (ga && r.classList.contains('fuori')) ga.classList.remove('no-fuori');
      mostra(r); return;
    }
    var t = document.querySelector('.tk[data-tsk="' + id + '"]');
    if (t) {
      document.querySelector('.tab[data-tab="ops"]').click();
      filtroObiettivo(t.getAttribute('data-ob'));
      var own = document.querySelector('.chip[data-fown="tutti"]'); if (own && !own.classList.contains('on')) own.click();
      mostra(t);
    }
  }, true);
  $('.altri-bl').forEach(function (b) {
    b.addEventListener('click', function () {
      var card = b.closest('.card');
      $('.bl[data-extra]', card).forEach(function (r) { r.hidden = false; });
      b.parentNode.hidden = true;
    });
  });
})();
