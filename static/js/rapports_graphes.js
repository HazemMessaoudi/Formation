/* V3 — Phase 5 : graphiques du تقرير بياني (SVG dessiné à la main, hors ligne).
 *
 * Utilisé par la page « التّقارير » ET recopié tel quel dans l'export HTML
 * interactif : aucune dépendance, aucun appel réseau.
 *
 * Chaque graphique est décrit par les données de core/rapports_graphiques.py :
 *   { id, titre, forme: 'barres_v' | 'barres_h' | 'pile', unite, libelles[],
 *     valeurs[], max, couleurs[], accent }
 * Règles : une seule mesure par graphique, valeur écrite sur chaque barre,
 * ordre RTL (le premier élément à droite), infobulle au survol, tableau
 * équivalent sous le graphique (l'identité n'est jamais portée par la seule
 * couleur).
 * Le SVG est en direction RTL : « text-anchor: start » aligne donc le texte
 * sur son bord DROIT (libellés et valeurs des barres horizontales).
 */
(function () {
  'use strict';
  const NS = 'http://www.w3.org/2000/svg';

  function el(nom, attrs, parent) {
    const e = document.createElementNS(NS, nom);
    Object.keys(attrs || {}).forEach(function (k) { e.setAttribute(k, attrs[k]); });
    if (parent) parent.appendChild(e);
    return e;
  }
  function fmt(v, unite) {
    const r = Math.round(v * 100) / 100;
    const s = (r === Math.round(r)) ? String(Math.round(r)) : String(r);
    return unite === '%' ? s + '%' : s;
  }
  function texte(parent, x, y, s, attrs) {
    const t = el('text', Object.assign({ x: x, y: y }, attrs || {}), parent);
    t.textContent = s;
    return t;
  }
  // Découpe un libellé en deux lignes au plus (≈ n caractères par ligne).
  function lignes(s, n) {
    const mots = String(s).split(/\s+/);
    const out = [''];
    mots.forEach(function (m) {
      const cur = out[out.length - 1];
      if (cur && (cur + ' ' + m).length > n) out.push(m); else out[out.length - 1] = cur ? cur + ' ' + m : m;
    });
    if (out.length > 2) { out[1] = out.slice(1).join(' ').slice(0, n - 1) + '…'; out.length = 2; }
    return out;
  }

  /* ── infobulle partagée ── */
  let tip = null;
  function montrer(e, html) {
    if (!tip) { tip = document.createElement('div'); tip.className = 'rg-tip'; document.body.appendChild(tip); }
    tip.innerHTML = html;
    tip.style.display = 'block';
    const x = Math.min(e.clientX + 14, window.innerWidth - tip.offsetWidth - 8);
    tip.style.left = Math.max(8, x) + 'px';
    tip.style.top = (e.clientY - tip.offsetHeight - 12) + 'px';
  }
  function cacher() { if (tip) tip.style.display = 'none'; }
  function survol(cible, marque, html) {
    cible.addEventListener('mousemove', function (e) { marque.classList.add('rg-actif'); montrer(e, html); });
    cible.addEventListener('mouseleave', function () { marque.classList.remove('rg-actif'); cacher(); });
  }
  function esc(s) { return String(s).replace(/[&<>"]/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]; }); }

  /* ── barres verticales (séries temporelles, années) ── */
  function barresV(svg, g) {
    const W = 480, H = 250, bas = H - 42, haut = 22;
    svg.setAttribute('viewBox', '0 0 ' + W + ' ' + H);
    const n = g.valeurs.length, vmax = g.max || Math.max.apply(null, g.valeurs) || 1;
    const pas = (W - 16) / n, lb = Math.min(pas * 0.56, 46);
    el('line', { x1: 8, x2: W - 8, y1: bas, y2: bas, class: 'rg-axe' }, svg);
    g.valeurs.forEach(function (v, i) {
      const xc = W - 8 - pas * (i + 0.5);
      const hb = (bas - haut) * (v / vmax);
      const accent = (g.accent === null || g.accent === undefined || g.accent === i);
      const barre = el('path', { d: chemin(xc - lb / 2, bas - hb, lb, hb), class: 'rg-barre' + (accent ? '' : ' rg-barre--pale') }, svg);
      texte(svg, xc, bas - hb - 6, fmt(v, g.unite), { class: 'rg-val', 'text-anchor': 'middle' });
      lignes(g.libelles[i], Math.max(6, Math.floor(pas / 7))).forEach(function (l, k) {
        texte(svg, xc, bas + 16 + k * 13, l, { class: 'rg-lib', 'text-anchor': 'middle' });
      });
      const zone = el('rect', { x: xc - pas / 2, y: haut - 10, width: pas, height: bas - haut + 40, class: 'rg-zone' }, svg);
      survol(zone, barre, '<b>' + esc(g.libelles[i]) + '</b><br>' + esc(g.titre) + ': ' + fmt(v, g.unite));
    });
  }
  // Barre à coins arrondis EN HAUT seulement (ancrée à la ligne de base).
  function chemin(x, y, w, h) {
    if (h <= 0) return 'M0 0';
    const r = Math.min(4, h, w / 2);
    return 'M' + x + ' ' + (y + h) + 'V' + (y + r) + 'Q' + x + ' ' + y + ' ' + (x + r) + ' ' + y +
           'H' + (x + w - r) + 'Q' + (x + w) + ' ' + y + ' ' + (x + w) + ' ' + (y + r) + 'V' + (y + h) + 'Z';
  }
  function cheminH(xDroite, y, w, h) {       // ancrée à droite, arrondie à gauche
    if (w <= 0) return 'M0 0';
    const r = Math.min(4, w, h / 2), x = xDroite - w;
    return 'M' + xDroite + ' ' + y + 'H' + (x + r) + 'Q' + x + ' ' + y + ' ' + x + ' ' + (y + r) +
           'V' + (y + h - r) + 'Q' + x + ' ' + (y + h) + ' ' + (x + r) + ' ' + (y + h) + 'H' + xDroite + 'Z';
  }

  /* ── barres horizontales (catégories) ── */
  function barresH(svg, g) {
    const n = g.valeurs.length, ligne = 34, W = 480, H = Math.max(80, n * ligne + 12);
    svg.setAttribute('viewBox', '0 0 ' + W + ' ' + H);
    const vmax = g.max || Math.max.apply(null, g.valeurs) || 1;
    const larLib = 190, xb = W - larLib - 6, zone = xb - 58, eb = 16;
    el('line', { x1: xb, x2: xb, y1: 4, y2: H - 6, class: 'rg-axe' }, svg);
    g.valeurs.forEach(function (v, i) {
      const yc = 6 + ligne * (i + 0.5);
      const ls = lignes(g.libelles[i], 30);
      ls.forEach(function (l, k) {
        texte(svg, W - 4, yc + 4 + (ls.length > 1 ? (k === 0 ? -7 : 7) : 0), l, { class: 'rg-lib', 'text-anchor': 'start' });
      });
      const w = zone * (v / vmax);
      const barre = el('path', { d: cheminH(xb, yc - eb / 2, w, eb), class: 'rg-barre' }, svg);
      texte(svg, xb - w - 6, yc + 4, fmt(v, g.unite), { class: 'rg-val', 'text-anchor': 'start' });
      const z = el('rect', { x: 0, y: yc - ligne / 2, width: W, height: ligne, class: 'rg-zone' }, svg);
      survol(z, barre, '<b>' + esc(g.libelles[i]) + '</b><br>' + esc(g.titre) + ': ' + fmt(v, g.unite));
    });
  }

  /* ── barre empilée à 100 % (répartitions : genre, فئة عمرية) ── */
  function pile(svg, g, legende) {
    const W = 480, H = 70, y = 14, h = 30;
    svg.setAttribute('viewBox', '0 0 ' + W + ' ' + H);
    const total = g.valeurs.reduce(function (a, b) { return a + b; }, 0) || 1;
    let x = W - 4;
    const coul = g.couleurs || [];
    g.valeurs.forEach(function (v, i) {
      const w = (W - 8) * v / total;
      if (w <= 0) return;
      const seg = el('rect', { x: x - w + (i ? 2 : 0), y: y, width: Math.max(0, w - (i ? 2 : 0)), height: h, rx: 3, fill: coul[i] || 'var(--rg-serie)', class: 'rg-seg' }, svg);
      const p = Math.round(1000 * v / total) / 10;
      if (w > 44) texte(svg, x - w / 2, y + h / 2 + 5, p + '%', { class: 'rg-val rg-val--inv', 'text-anchor': 'middle' });
      survol(seg, seg, '<b>' + esc(g.libelles[i]) + '</b><br>' + fmt(v, '') + ' (' + p + '%)');
      x -= w;
    });
    if (legende) {
      legende.innerHTML = g.libelles.map(function (l, i) {
        return '<span class="rg-leg"><i style="background:' + (coul[i] || 'var(--rg-serie)') + '"></i>' + esc(l) +
               ' <b>' + fmt(g.valeurs[i], '') + '</b></span>';
      }).join('');
    }
  }

  /* ── barres groupées : même mesure, deux années (légende + valeurs) ── */
  function barresG(svg, g, legende) {
    const W = 900, H = 250, bas = H - 30, haut = 22;   // large : textes à taille lisible
    svg.setAttribute('viewBox', '0 0 ' + W + ' ' + H);
    const n = g.libelles.length, ns = g.series.length;
    const toutes = [].concat.apply([], g.series.map(function (s) { return s.valeurs; }));
    const vmax = Math.max.apply(null, toutes) || 1;
    const pas = (W - 16) / n, lb = Math.min((pas - 6) / ns, 16);
    el('line', { x1: 8, x2: W - 8, y1: bas, y2: bas, class: 'rg-axe' }, svg);
    g.libelles.forEach(function (lib, i) {
      const xc = W - 8 - pas * (i + 0.5);
      const infos = [];
      g.series.forEach(function (s, k) {
        const v = s.valeurs[i] || 0;
        const x = xc + (ns / 2 - k - 1) * (lb + 2) + 1;      // série 1 à droite
        const hb = (bas - haut) * (v / vmax);
        const b = el('path', { d: chemin(x, bas - hb, lb, hb), class: s.classe || 'rg-barre' }, svg);
        if (v) texte(svg, x + lb / 2, bas - hb - 4, fmt(v, ''), { class: 'rg-val rg-val--petit', 'text-anchor': 'middle' });
        infos.push(esc(s.nom) + ': ' + fmt(v, ''));
        b.dataset.i = i;
      });
      texte(svg, xc, bas + 16, lib, { class: 'rg-lib rg-lib--petit', 'text-anchor': 'middle' });
      const zone = el('rect', { x: xc - pas / 2, y: haut - 10, width: pas, height: bas - haut + 30, class: 'rg-zone' }, svg);
      survol(zone, zone, '<b>' + esc(lib) + '</b><br>' + infos.join('<br>'));
    });
    if (legende) {
      legende.innerHTML = g.series.map(function (s) {
        return '<span class="rg-leg"><i class="' + (s.classe.indexOf('pale') >= 0 ? 'rg-puce--pale' : 'rg-puce') + '"></i>' + esc(s.nom) + '</span>';
      }).join('');
    }
  }

  function tableau(g) {
    if (g.series) {
      const t = g.libelles.map(function (l, i) {
        return '<tr><td>' + esc(l) + '</td>' + g.series.map(function (s) { return '<td>' + fmt(s.valeurs[i] || 0, '') + '</td>'; }).join('') + '</tr>';
      }).join('');
      return '<details class="rg-details"><summary>📋 الجدول</summary><table class="rg-table"><thead><tr><th>البيان</th>' +
             g.series.map(function (s) { return '<th>' + esc(s.nom) + '</th>'; }).join('') + '</tr></thead><tbody>' + t + '</tbody></table></details>';
    }
    const lignesT = g.libelles.map(function (l, i) {
      return '<tr><td>' + esc(l) + '</td><td>' + fmt(g.valeurs[i], g.unite) + '</td></tr>';
    }).join('');
    return '<details class="rg-details"><summary>📋 الجدول</summary><table class="rg-table"><thead><tr><th>البيان</th><th>' +
           esc(g.titre) + '</th></tr></thead><tbody>' + lignesT + '</tbody></table></details>';
  }

  function dessiner(carte, g) {
    carte.innerHTML = '<h3 class="rg-titre">' + esc(g.titre) + '</h3>';
    const toutes = g.series ? [].concat.apply([], g.series.map(function (s) { return s.valeurs; })) : g.valeurs;
    const vide = !toutes.length || toutes.every(function (v) { return !v; });
    if (vide) {
      carte.insertAdjacentHTML('beforeend', '<p class="rg-vide">لا توجد معطيات لهذه الفترة</p>');
      return;
    }
    const svg = el('svg', { role: 'img', 'aria-label': g.titre, class: 'rg-svg rg-svg--' + g.forme });
    carte.appendChild(svg);
    if (g.forme === 'barres_v') barresV(svg, g);
    else if (g.forme === 'barres_h') barresH(svg, g);
    else if (g.forme === 'barres_g') {
      const leg = document.createElement('div');
      leg.className = 'rg-legende';
      barresG(svg, g, leg);
      carte.appendChild(leg);
    } else {
      const leg = document.createElement('div');
      leg.className = 'rg-legende';
      pile(svg, g, leg);
      carte.appendChild(leg);
    }
    carte.insertAdjacentHTML('beforeend', tableau(g));
  }

  window.RapportsGraphes = {
    dessinerTout: function (racine, donnees) {
      donnees.sections.forEach(function (s) {
        s.graphes.forEach(function (g) {
          const carte = racine.querySelector('[data-graphe="' + g.id + '"]');
          if (carte) dessiner(carte, g);
        });
      });
    }
  };
})();
