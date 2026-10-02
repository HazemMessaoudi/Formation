/* ══════════════════════════════════════════════════════════════════════════
   ui.js — Couche d'interface commune à toutes les pages
   • Protection CSRF automatique (fetch + formulaires)
   • Système de modales personnalisées (alerte / confirmation) en RTL arabe
   Chargé depuis base.html : aucune page n'a besoin de redéfinir ces fonctions.
   ══════════════════════════════════════════════════════════════════════════ */
(function () {
  'use strict';

  /* ── 0. Préférences d'affichage (v1.5) ─────────────────────────────────
     • Thème : le choix explicite (localStorage « app_theme ») prime ; à
       défaut, v1.7.1 : toujours le thème CLAIR 0 (demande de l'utilisateur),
       même si Windows est en mode sombre.
     • Police de l'interface : « amiri » (défaut historique) ou « cairo ».
     Chaque accès au stockage est protégé : un navigateur qui le refuse
     retombe simplement sur les valeurs par défaut. */
  function lire(cle) {
    try { return localStorage.getItem(cle); } catch (e) { return null; }
  }
  const THEME_DEFAUT = 0;   // v1.7.1 : clair au premier lancement
  window.APP_PREFS = {
    themeChoisi: function () {
      const t = lire('app_theme');
      return t !== null && t !== '' && !isNaN(+t) && +t >= 0 && +t <= 5;
    },
    theme: function () {
      return this.themeChoisi() ? +lire('app_theme') : THEME_DEFAUT;
    },
    // v1.6.1 : « القاهرة » est la police de départ. Seul un choix EXPLICITE
    // (clic dans «المظهر») est mémorisé, sous une nouvelle clé : l'ancienne
    // clé « app_police » était réécrite à chaque ouverture de page et ne
    // traduisait donc pas un vrai choix de l'utilisateur.
    police: function () { return lire('app_police_choix') === 'amiri' ? 'amiri' : 'cairo'; },
    setPolice: function (p, memoriser) {
      p = (p === 'amiri') ? 'amiri' : 'cairo';
      if (memoriser !== false) {
        try { localStorage.setItem('app_police_choix', p); } catch (e) { /* sans effet */ }
      }
      if (document.body) document.body.dataset.police = p;
      document.querySelectorAll('[data-police-choix]').forEach(function (b) {
        b.classList.toggle('actif', b.getAttribute('data-police-choix') === p);
      });
    },
    appliquer: function () {
      const b = document.body;
      if (!b) return;
      b.dataset.theme = this.theme();
      b.dataset.police = this.police();
    }
  };
  /* ── 0 bis. Notifications « toast » (v1.5) ─────────────────────────────
     Les messages flash du serveur sont rendus dans #toastZone par base.html ;
     showToast() permet d'en afficher depuis le JavaScript. Les succès
     disparaissent seuls (5 s, suspendu au survol) ; les erreurs et
     avertissements restent jusqu'à fermeture : ils doivent être lus. */
  const ICONES_TOAST = { success: '✔', error: '✖', warning: '⚠', info: 'ℹ' };

  function zoneToasts() {
    let z = document.getElementById('toastZone');
    if (!z) {
      z = document.createElement('div');
      z.id = 'toastZone';
      z.className = 'toast-zone';
      z.setAttribute('role', 'status');
      z.setAttribute('aria-live', 'polite');
      document.body.appendChild(z);
    }
    return z;
  }

  function fermerToast(t) {
    if (!t || t.dataset.ferme) return;
    t.dataset.ferme = '1';
    t.classList.add('toast-sortie');
    setTimeout(function () { if (t.parentNode) t.parentNode.removeChild(t); }, 260);
  }

  function armerToast(t) {
    if (t.dataset.arme) return;
    t.dataset.arme = '1';
    const x = t.querySelector('.toast-x');
    if (x) x.addEventListener('click', function () { fermerToast(t); });
    const duree = +(t.getAttribute('data-duree') || 0);
    if (duree > 0) {
      let reste = duree, debut = Date.now(), minuteur = null;
      const lancer = function () {
        debut = Date.now();
        minuteur = setTimeout(function () { fermerToast(t); }, reste);
      };
      t.addEventListener('mouseenter', function () {
        clearTimeout(minuteur); reste -= (Date.now() - debut);
      });
      t.addEventListener('mouseleave', lancer);
      lancer();
    }
  }

  /* v1.7 — échappement HTML unique : toute donnée saisie (titre, nom, lieu…)
     insérée via innerHTML passe par esc(), pour qu'un « < », un « & » ou un
     guillemet s'affiche tel quel au lieu de casser la page. */
  window.esc = function (valeur) {
    return String(valeur === null || valeur === undefined ? '' : valeur)
      .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
  };

  window.showToast = function (message, type, duree) {
    // Sans type : succès (compatibilité avec les anciens appels showToast(msg)).
    type = (type === undefined || type === null || type === '') ? 'success'
         : (ICONES_TOAST[type] ? type : 'info');
    // Depuis le JavaScript, une erreur reste 8 s (elle suit une action que
    // l'utilisateur vient de faire) ; les messages du serveur, eux, restent.
    if (duree === undefined) duree = (type === 'success' || type === 'info') ? 5000 : 8000;
    const t = document.createElement('div');
    t.className = 'toast toast-' + type;
    t.setAttribute('data-duree', String(duree));
    const i = document.createElement('span');
    i.className = 'toast-ico'; i.textContent = ICONES_TOAST[type];
    const m = document.createElement('span');
    m.className = 'toast-msg'; m.textContent = String(message == null ? '' : message);
    const x = document.createElement('button');
    x.type = 'button'; x.className = 'toast-x'; x.title = 'إغلاق'; x.textContent = '×';
    t.appendChild(i); t.appendChild(m); t.appendChild(x);
    zoneToasts().appendChild(t);
    armerToast(t);
    return t;
  };

  /* ── 0 ter. État vide d'une recherche (A7) ─────────────────────────────
     Appelé par les filtres des listes : quand aucune ligne ne correspond,
     un message illustré remplace le tableau vide (qui est masqué). */
  window.majEtatVide = function (table, visibles, requete) {
    if (!table) return;
    const bloc = table.closest('.card') || table;
    let msg = bloc.nextElementSibling;
    if (!msg || !msg.classList.contains('empty-msg--recherche')) {
      msg = document.createElement('div');
      msg.className = 'empty-msg empty-msg--recherche';
      bloc.parentNode.insertBefore(msg, bloc.nextSibling);
    }
    const vide = !!requete && visibles === 0;
    msg.style.display = vide ? '' : 'none';
    bloc.style.display = vide ? 'none' : '';
    if (vide) {
      msg.textContent = '';
      const t = document.createElement('strong');
      t.textContent = 'لا توجد نتائج مطابقة';
      const d = document.createElement('span');
      d.textContent = 'لم يُعثر على أيّ عنصر يطابق «' + requete + '». جرّب كلمة أخرى أو امسح خانة البحث.';
      msg.appendChild(t); msg.appendChild(d);
    }
  };

  function armerToastsServeur() {
    // La zone doit être un enfant direct de <body> : dans <main>, elle hérite
    // d'un contexte d'empilement et passe sous la barre de navigation.
    const z = document.getElementById('toastZone');
    if (z && z.parentNode !== document.body) document.body.appendChild(z);
    document.querySelectorAll('#toastZone .toast').forEach(armerToast);
  }

  /* ── 1. Jeton CSRF ───────────────────────────────────────────────────── */

  function jeton() {
    const m = document.querySelector('meta[name="csrf-token"]');
    return m ? m.getAttribute('content') : '';
  }
  window.CSRF_TOKEN = jeton();

  // Toute requête fetch modifiante vers notre propre serveur reçoit le jeton
  // sans que la page appelante ait à s'en occuper.
  const _fetchOrigine = window.fetch;
  window.fetch = function (entree, options) {
    options = options || {};
    const methode = (options.method || 'GET').toUpperCase();
    const url = (typeof entree === 'string') ? entree
              : (entree && entree.url) ? entree.url : '';
    const memeOrigine = !/^[a-z]+:\/\//i.test(url) || url.indexOf(location.origin) === 0;
    if (memeOrigine && ['POST', 'PUT', 'PATCH', 'DELETE'].indexOf(methode) !== -1) {
      const entetes = new Headers(options.headers || {});
      if (!entetes.has('X-CSRF-Token')) entetes.set('X-CSRF-Token', window.CSRF_TOKEN);
      options.headers = entetes;
    }
    return _fetchOrigine.call(this, entree, options);
  };

  // Les formulaires POST reçoivent un champ caché s'ils n'en ont pas déjà un.
  function equiperFormulaires() {
    document.querySelectorAll('form').forEach(function (f) {
      const m = (f.getAttribute('method') || 'get').toLowerCase();
      if (m !== 'post') return;
      if (f.querySelector('input[name="_csrf"]')) return;
      const i = document.createElement('input');
      i.type = 'hidden'; i.name = '_csrf'; i.value = window.CSRF_TOKEN;
      f.appendChild(i);
    });
  }

  /* ── 2. Modales personnalisées ───────────────────────────────────────── */

  const MARQUAGE = `
<div id="uiAlertModal" class="ui-modal" style="display:none;">
  <div class="ui-modal-box">
    <div id="uiAlertText" class="ui-modal-text"></div>
    <div class="ui-modal-actions">
      <button type="button" id="uiAlertOk" class="ui-btn ui-btn-primary">حسناً</button>
    </div>
  </div>
</div>
<div id="uiConfirmModal" class="ui-modal" style="display:none;">
  <div class="ui-modal-box">
    <div id="uiConfirmText" class="ui-modal-text"></div>
    <div class="ui-modal-actions">
      <button type="button" id="uiConfirmOk" class="ui-btn ui-btn-ok">✔ نعم، تأكيد</button>
      <button type="button" id="uiConfirmCancel" class="ui-btn ui-btn-cancel">✖ إلغاء</button>
    </div>
  </div>
</div>
<div id="uiPromptModal" class="ui-modal" style="display:none;">
  <div class="ui-modal-box">
    <div id="uiPromptText" class="ui-modal-text"></div>
    <textarea id="uiPromptInput" class="ui-modal-input" rows="3"></textarea>
    <div id="uiPromptErreur" class="ui-modal-erreur"></div>
    <div class="ui-modal-actions">
      <button type="button" id="uiPromptOk" class="ui-btn ui-btn-ok">✔ تأكيد</button>
      <button type="button" id="uiPromptCancel" class="ui-btn ui-btn-cancel">✖ إلغاء</button>
    </div>
  </div>
</div>`;

  const STYLE = `
.ui-modal{position:fixed;inset:0;background:rgba(0,0,0,.55);z-index:9999;
  display:flex;align-items:center;justify-content:center;}
.ui-modal-box{background:var(--card-bg,#fff);border-radius:14px;padding:2rem;
  max-width:470px;width:92%;box-shadow:0 12px 40px rgba(0,0,0,.35);
  direction:rtl;text-align:right;}
.ui-modal-text{font-size:1rem;margin-bottom:1.4rem;line-height:1.75;
  color:var(--text,#1e293b);}
.ui-modal-actions{display:flex;gap:.8rem;flex-wrap:wrap;}
.ui-btn{border:none;border-radius:8px;padding:.65rem 1.4rem;font-size:.98rem;
  cursor:pointer;font-family:inherit;font-weight:600;color:#fff;}
.ui-btn-primary{background:var(--primary,#1a3a6b);}
.ui-btn-ok{background:#22c55e;}
.ui-btn-cancel{background:#ef4444;}
.ui-btn:focus-visible{outline:3px solid #fbbf24;outline-offset:2px;}
.ui-modal-input{width:100%;box-sizing:border-box;font-family:inherit;font-size:1rem;
  padding:.6rem .75rem;border:1.5px solid var(--border,#cbd5e1);border-radius:8px;
  background:var(--input-bg,var(--card-bg,#fff));color:var(--text,#1e293b);
  resize:vertical;margin-bottom:.4rem;direction:rtl;}
.ui-modal-erreur{min-height:1.2rem;color:#dc2626;font-size:.88rem;margin-bottom:.8rem;}`;

  let rappelAlerte = null, rappelOui = null, rappelNon = null;
  let rappelSaisie = null, saisieMin = 0;

  function injecter() {
    if (document.getElementById('uiAlertModal')) return;
    const s = document.createElement('style');
    s.textContent = STYLE;
    document.head.appendChild(s);
    const d = document.createElement('div');
    d.innerHTML = MARQUAGE;
    while (d.firstChild) document.body.appendChild(d.firstChild);

    document.getElementById('uiAlertOk').addEventListener('click', function () {
      fermer('uiAlertModal');
      if (rappelAlerte) { const f = rappelAlerte; rappelAlerte = null; f(); }
    });
    document.getElementById('uiConfirmOk').addEventListener('click', function () {
      fermer('uiConfirmModal');
      if (rappelOui) { const f = rappelOui; rappelOui = null; f(); }
    });
    document.getElementById('uiConfirmCancel').addEventListener('click', function () {
      fermer('uiConfirmModal');
      if (rappelNon) { const f = rappelNon; rappelNon = null; f(); }
    });
    document.getElementById('uiPromptOk').addEventListener('click', function () {
      const v = document.getElementById('uiPromptInput').value.trim();
      if (v.length < saisieMin) {
        document.getElementById('uiPromptErreur').textContent =
          'يجب كتابة ' + saisieMin + ' أحرف على الأقلّ.';
        document.getElementById('uiPromptInput').focus();
        return;
      }
      fermer('uiPromptModal');
      if (rappelSaisie) { const f = rappelSaisie; rappelSaisie = null; f(v); }
    });
    document.getElementById('uiPromptCancel').addEventListener('click', function () {
      fermer('uiPromptModal'); rappelSaisie = null;
    });
    // Échap ferme la modale de confirmation (équivaut à « إلغاء »)
    document.addEventListener('keydown', function (e) {
      if (e.key !== 'Escape') return;
      const p = document.getElementById('uiPromptModal');
      if (p && p.style.display !== 'none') document.getElementById('uiPromptCancel').click();
      const c = document.getElementById('uiConfirmModal');
      if (c && c.style.display !== 'none') document.getElementById('uiConfirmCancel').click();
      const a = document.getElementById('uiAlertModal');
      if (a && a.style.display !== 'none') document.getElementById('uiAlertOk').click();
    });
  }

  function fermer(id) {
    const el = document.getElementById(id);
    if (el) el.style.display = 'none';
  }

  function texte(valeur) {
    // On échappe le contenu puis on rétablit les seuls sauts de ligne.
    const d = document.createElement('div');
    d.textContent = String(valeur == null ? '' : valeur);
    return d.innerHTML.replace(/\n/g, '<br>');
  }

  window.showAlertModal = function (message, apres) {
    injecter();
    document.getElementById('uiAlertText').innerHTML = texte(message);
    rappelAlerte = apres || null;
    document.getElementById('uiAlertModal').style.display = 'flex';
    setTimeout(function () { document.getElementById('uiAlertOk').focus(); }, 30);
  };

  window.showConfirmModal = function (message, siOui, siNon) {
    injecter();
    document.getElementById('uiConfirmText').innerHTML = texte(message);
    rappelOui = siOui || null;
    rappelNon = siNon || null;
    document.getElementById('uiConfirmModal').style.display = 'flex';
    setTimeout(function () { document.getElementById('uiConfirmOk').focus(); }, 30);
  };

  /* Saisie obligatoire (v1.6) : showPromptModal(message, {min, placeholder}, siOui(valeur)). */
  window.showPromptModal = function (message, opts, siOui) {
    injecter();
    opts = opts || {};
    saisieMin = +opts.min || 0;
    document.getElementById('uiPromptText').innerHTML = texte(message);
    const i = document.getElementById('uiPromptInput');
    i.value = ''; i.placeholder = opts.placeholder || '';
    document.getElementById('uiPromptErreur').textContent = '';
    rappelSaisie = siOui || null;
    document.getElementById('uiPromptModal').style.display = 'flex';
    setTimeout(function () { i.focus(); }, 30);
  };

  /* ── 2 bis. Confirmation déclarative (v1.5 — UX3) ──────────────────────
     <form data-confirm="…"> ou <a data-confirm="…"> : la fenêtre de
     confirmation de l'application remplace le confirm() natif du navigateur.
     Après « نعم », le formulaire est soumis (requestSubmit conserve le bouton
     et les validations HTML) ; le lien est suivi. */
  document.addEventListener('submit', function (e) {
    const f = e.target;
    if (!f || !f.hasAttribute || !f.hasAttribute('data-confirm')) return;
    if (f.dataset.confirmOk === '1') { delete f.dataset.confirmOk; return; }
    e.preventDefault();
    const bouton = e.submitter || null;
    window.showConfirmModal(f.getAttribute('data-confirm'), function () {
      f.dataset.confirmOk = '1';
      if (typeof f.requestSubmit !== 'function') f.submit();
      else if (bouton) f.requestSubmit(bouton); else f.requestSubmit();
    });
  }, true);
  document.addEventListener('click', function (e) {
    const a = e.target.closest ? e.target.closest('a[data-confirm]') : null;
    if (!a) return;
    e.preventDefault();
    window.showConfirmModal(a.getAttribute('data-confirm'), function () {
      if (a.target === '_blank') window.open(a.href, '_blank'); else location.href = a.href;
    });
  }, true);

  /* ── 2 ter. Veille d'inactivité (v1.5 — S3) ───────────────────────────
     body[data-inactivite] = délai en minutes (absent : fonction désactivée).
     L'activité (souris, clavier, défilement…) est partagée entre onglets via
     localStorage ; tant qu'il y a activité, un ping discret toutes les 4 min
     prolonge la session côté serveur. Une minute avant l'échéance, une
     fenêtre avertit avec un compte à rebours ; à l'échéance, déconnexion. */
  function demarrerVeille() {
    const b = document.body;
    const minutes = b ? +(b.getAttribute('data-inactivite') || 0) : 0;
    const sortie = b ? b.getAttribute('data-logout') : '';
    if (!minutes || !sortie) return;
    const DELAI = minutes * 60000, PREAVIS = 60000, PING = 4 * 60000;
    let locale = Date.now(), dernierPing = Date.now(), alerte = null, fini = false;

    function derniere() {
      let partagee = 0;
      try { partagee = +(localStorage.getItem('app_activite') || 0); } catch (e) {}
      return Math.max(locale, partagee);
    }
    let dernierEcrit = 0;
    function activite() {
      if (fini) return;
      locale = Date.now();
      if (locale - dernierEcrit > 3000) {
        dernierEcrit = locale;
        try { localStorage.setItem('app_activite', String(locale)); } catch (e) {}
      }
      if (alerte) fermerAlerte();
    }
    ['mousemove', 'mousedown', 'keydown', 'wheel', 'scroll', 'touchstart', 'input']
      .forEach(function (ev) { document.addEventListener(ev, activite, {passive: true, capture: true}); });
    activite();

    function fermerAlerte() {
      if (alerte && alerte.parentNode) alerte.parentNode.removeChild(alerte);
      alerte = null;
    }
    function montrerAlerte(reste) {
      if (!alerte) {
        alerte = document.createElement('div');
        alerte.className = 'veille-alerte';
        alerte.innerHTML = '<div class="veille-alerte__boite" role="alertdialog" aria-live="assertive">'
          + '<div class="veille-alerte__ico">⏳</div>'
          + '<div class="veille-alerte__titre">ستُغلق الجلسة قريبًا بسبب عدم النشاط</div>'
          + '<div class="veille-alerte__compte"></div>'
          + '<button type="button" class="ui-btn ui-btn-primary">مواصلة العمل</button></div>';
        alerte.querySelector('button').addEventListener('click', function () {
          activite(); pinger();
        });
        document.body.appendChild(alerte);
        alerte.querySelector('button').focus();
      }
      alerte.querySelector('.veille-alerte__compte').textContent = Math.max(0, Math.ceil(reste / 1000)) + ' ثانية';
    }
    function pinger() {
      dernierPing = Date.now();
      window.fetch('/api/ping', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: '{}'})
        .then(function (r) { if (r.status === 401) { fini = true; location.href = sortie; } })
        .catch(function () { /* hors ligne : on réessaiera */ });
    }
    setInterval(function () {
      if (fini) return;
      const maintenant = Date.now(), inactif = maintenant - derniere();
      if (inactif >= DELAI) {
        fini = true; location.href = sortie; return;
      }
      if (inactif >= DELAI - PREAVIS) { montrerAlerte(DELAI - inactif); return; }
      if (alerte) fermerAlerte();
      if (derniere() > dernierPing && maintenant - dernierPing >= PING) pinger();
    }, 1000);
  }

  /* ── 2 quater. Visionneuse PDF intégrée (v1.5 — A12 + P3) ─────────────
     Tout lien ou window.open(…, '_blank') vers une route de document PDF
     s'ouvre dans une fenêtre intégrée : indicateur de chargement pendant la
     génération, puis aperçu avec « طباعة » / « نافذة مستقلّة » / « تنزيل ».
     Si la route renvoie une page HTML (refus, message d'erreur), ses
     messages sont repris en notifications et la fenêtre se referme. */
  const MOTIF_PDF = /\/(pdf(\/[\w-]+)?|generer(-directeur-regional)?)\/?(\?.*)?$/i;
  function estUrlPdf(url) {
    try {
      const u = new URL(url, location.href);
      return u.origin === location.origin && MOTIF_PDF.test(u.pathname + u.search);
    } catch (e) { return false; }
  }
  let visionneuse = null;
  function fermerVisionneuse() {
    if (!visionneuse) return;
    visionneuse.remove();
    visionneuse = null;
    document.documentElement.classList.remove('pdfv-ouverte');
  }
  window.ouvrirPdf = function (url) {
    fermerVisionneuse();
    const v = document.createElement('div');
    v.className = 'pdfv';
    v.innerHTML = '<div class="pdfv__cadre" role="dialog" aria-label="معاينة الوثيقة">'
      + '<div class="pdfv__barre">'
      + '<span class="pdfv__titre">📄 معاينة الوثيقة</span>'
      + '<button type="button" class="pdfv__btn" data-act="imprimer" disabled>🖨 طباعة</button>'
      + '<a class="pdfv__btn" data-act="onglet" target="_blank" rel="noopener">↗ نافذة مستقلّة</a>'
      + '<a class="pdfv__btn" data-act="telecharger" download>⬇ تنزيل</a>'
      + '<button type="button" class="pdfv__btn pdfv__fermer" data-act="fermer" title="إغلاق (Esc)">✕</button>'
      + '</div>'
      + '<div class="pdfv__corps"><div class="pdfv__attente"><span class="pdfv__roue"></span>'
      + '<span>جاري إعداد الوثيقة…</span></div><iframe class="pdfv__iframe" title="الوثيقة"></iframe></div>'
      + '</div>';
    v.querySelector('[data-act="onglet"]').href = url;
    v.querySelector('[data-act="telecharger"]').href = url;
    const iframe = v.querySelector('iframe');
    const attente = v.querySelector('.pdfv__attente');
    v.addEventListener('click', function (e) {
      const act = e.target.closest('[data-act]');
      if (e.target === v || (act && act.getAttribute('data-act') === 'fermer')) { fermerVisionneuse(); return; }
      if (act && act.getAttribute('data-act') === 'imprimer') {
        try { iframe.contentWindow.focus(); iframe.contentWindow.print(); }
        catch (err) { window.open(url, '_blank'); }
      }
      if (act && act.getAttribute('data-act') === 'onglet') setTimeout(fermerVisionneuse, 50);
    });
    iframe.addEventListener('load', function () {
      let doc = null;
      try { doc = iframe.contentDocument; } catch (e) { doc = null; }
      // Le premier « load » est celui d'about:blank, avant la vraie réponse.
      if (!iframe.getAttribute('src')) return;
      try { if (doc && doc.location && doc.location.href === 'about:blank') return; } catch (e) {}
      const html = !!(doc && doc.contentType && doc.contentType.indexOf('html') !== -1 && doc.body);
      if (html && !doc.querySelector('#toastZone, .navbar, main, form, .error-msg, .card')
          && !(doc.body.textContent || '').trim()) {
        // Document vide : le navigateur n'affiche pas les PDF (lecteur
        // désactivé) et l'a téléchargé. On le dit, sans parler d'erreur.
        attente.innerHTML = '<span style="font-size:2rem">📥</span>'
          + '<span>لا يعرض هذا المتصفّح الوثائق داخل البرنامج.</span>'
          + '<span style="font-size:.9rem;opacity:.85">استعمل «نافذة مستقلّة» أو «تنزيل» في الأعلى.</span>';
        return;
      }
      if (html) {
        // Réponse HTML au lieu d'un PDF (refus, message) : on relaie ses messages.
        const msgs = Array.prototype.map.call(doc.querySelectorAll('#toastZone .toast'), function (t) {
          const m = t.querySelector('.toast-msg');
          return [t.classList.contains('toast-error') ? 'error' : (t.classList.contains('toast-success') ? 'success' : 'warning'),
                  m ? m.textContent.trim() : ''];
        }).filter(function (x) { return x[1]; });
        const erreur = doc.querySelector('.error-msg, .alert-error, .erreur-msg');
        fermerVisionneuse();
        if (msgs.length) msgs.forEach(function (x) { window.showToast(x[1], x[0]); });
        else window.showToast(erreur ? erreur.textContent.trim() : 'تعذّر إعداد الوثيقة.', 'error');
        return;
      }
      attente.style.display = 'none';
      iframe.style.visibility = 'visible';
      v.querySelector('[data-act="imprimer"]').disabled = false;
    });
    document.body.appendChild(v);
    document.documentElement.classList.add('pdfv-ouverte');
    visionneuse = v;
    iframe.src = url;
    v.querySelector('.pdfv__fermer').focus();
    return v;
  };
  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape' && visionneuse) fermerVisionneuse();
  });
  document.addEventListener('click', function (e) {
    if (e.defaultPrevented || e.button !== 0 || e.ctrlKey || e.metaKey || e.shiftKey) return;
    const a = e.target.closest ? e.target.closest('a[href]') : null;
    if (!a || a.hasAttribute('download') || a.hasAttribute('data-sans-apercu')) return;
    if (a.closest('.pdfv')) return;
    if (a.target === '_blank' && estUrlPdf(a.href)) { e.preventDefault(); window.ouvrirPdf(a.href); }
  });
  const _openOrigine = window.open;
  window.open = function (url, cible, options) {
    if ((cible === '_blank' || cible === undefined) && !options && url && estUrlPdf(String(url))) {
      window.ouvrirPdf(String(url));
      return null;
    }
    return _openOrigine.apply(window, arguments);
  };

  /* ── 2 quinquies. Tri des tableaux (v1.5 — A6) ─────────────────────────
     <table class="table-triable"> : un clic sur un en-tête trie les lignes
     (nombres, dates AAAA-MM-JJ ou JJ/MM/AAAA, sinon ordre alphabétique
     arabe). Un second clic inverse l'ordre. Les en-têtes contenant une case
     à cocher, ou marqués data-tri="non", ne trient pas. Avec
     data-renumeroter, les numéros d'ordre (.num-cell) sont recalculés. */
  function cleTri(texte) {
    const t = (texte || '').replace(/\s+/g, ' ').trim();
    if (!t || t === '—' || t === '-') return {vide: true};
    let m = t.match(/^(\d{4})-(\d{2})-(\d{2})/);
    if (m) return {n: +(m[1] + m[2] + m[3])};
    m = t.match(/^(\d{1,2})\/(\d{1,2})\/(\d{4})/);
    if (m) return {n: +(m[3] + ('0' + m[2]).slice(-2) + ('0' + m[1]).slice(-2))};
    const num = t.replace(/[\s,]/g, '').replace(/[٠-٩]/g, function (c) { return '٠١٢٣٤٥٦٧٨٩'.indexOf(c); });
    if (/^-?\d+(\.\d+)?$/.test(num)) return {n: parseFloat(num)};
    return {s: t};
  }
  const collateur = (window.Intl && Intl.Collator) ? new Intl.Collator('ar', {numeric: true, sensitivity: 'base'}) : null;
  function comparer(a, b) {
    if (a.vide || b.vide) return a.vide && b.vide ? 0 : (a.vide ? 1 : -1);   // vides toujours en bas
    if (a.n !== undefined && b.n !== undefined) return a.n - b.n;
    const x = a.s !== undefined ? a.s : String(a.n), y = b.s !== undefined ? b.s : String(b.n);
    return collateur ? collateur.compare(x, y) : x.localeCompare(y, 'ar');
  }
  function renumeroter(tbody) {
    let n = 0;
    Array.prototype.forEach.call(tbody.rows, function (tr) {
      if (tr.style.display === 'none') return;
      n++;
      const c = tr.querySelector('.num-cell');
      if (c) c.textContent = c.textContent.trim().length === 2 && /^\d\d$/.test(c.textContent.trim()) ? ('0' + n).slice(-2) : n;
    });
  }
  function equiperTri(table) {
    if (table.dataset.triArme) return;
    table.dataset.triArme = '1';
    const tete = table.tHead && table.tHead.rows[table.tHead.rows.length - 1];
    const corps = table.tBodies[0];
    if (!tete || !corps) return;
    Array.prototype.forEach.call(tete.cells, function (th, idx) {
      if (th.getAttribute('data-tri') === 'non' || th.querySelector('input') || th.colSpan > 1) return;
      th.classList.add('th-triable');
      th.setAttribute('tabindex', '0');
      th.setAttribute('aria-sort', 'none');
      th.title = 'اضغط للترتيب';
      const trier = function () {
        const sens = th.getAttribute('aria-sort') === 'ascending' ? -1 : 1;
        Array.prototype.forEach.call(tete.cells, function (h) { if (h !== th && h.classList.contains('th-triable')) h.setAttribute('aria-sort', 'none'); });
        th.setAttribute('aria-sort', sens === 1 ? 'ascending' : 'descending');
        const lignes = Array.prototype.slice.call(corps.rows).filter(function (r) { return r.cells.length > idx; });
        const autres = Array.prototype.slice.call(corps.rows).filter(function (r) { return r.cells.length <= idx; });
        lignes.map(function (r, i) { return {r: r, k: cleTri(r.cells[idx].textContent), i: i}; })
          .sort(function (a, b) { return comparer(a.k, b.k) * sens || a.i - b.i; })
          .forEach(function (o) { corps.appendChild(o.r); });
        autres.forEach(function (r) { corps.appendChild(r); });
        // Seuls les numéros d'ORDRE sont recalculés (data-renumeroter) : dans le
        // سجلّ, la première colonne est le numéro officiel et ne bouge jamais.
        if (table.hasAttribute('data-renumeroter')) renumeroter(corps);
      };
      th.addEventListener('click', trier);
      th.addEventListener('keydown', function (e) { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); trier(); } });
    });
  }

  /* ── 2 sexies. Vérification immédiate des champs (v1.5 — A8) ───────────
     • Contraintes HTML (required, minlength, pattern, type=email) : message
       arabe sous le champ dès qu'on le quitte, puis mise à jour en direct.
     • data-verif="telephone|email|chiffres" : simple AVERTISSEMENT (orange),
       qui n'empêche jamais l'enregistrement.
     • data-verif="cin|rib" (v1.6) : contrôle STRICT — une خانة remplie doit
       compter exactement 8 / 20 chiffres (chiffres arabes et séparateurs
       tolérés), sinon ERREUR rouge et enregistrement bloqué. Vide = accepté. */
  const VERIFS = {
    cin:       [/^\d{8}$/, 'رقم بطاقة التعريف الوطنية يجب أن يتكوّن من 8 أرقام بالضبط'],
    telephone: [/^(\+?216)?\d{8}$/, 'رقم الهاتف يتكوّن عادة من 8 أرقام (مع +216 اختياريًّا)'],
    rib:       [/^\d{20}$/, 'رقم الحساب البنكي أو البريدي يجب أن يتكوّن من 20 رقمًا بالضبط'],
    email:     [/^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/, 'صيغة البريد الإلكتروني غير صحيحة'],
    chiffres:  [/^\d+$/, 'يُنتظر أن تحتوي هذه الخانة على أرقام فقط']
  };
  const STRICTS = { cin: 1, rib: 1 };
  function chiffresOccidentaux(t) {
    return (t || '').replace(/[\u0660-\u0669]/g, function (c) { return String(c.charCodeAt(0) - 0x0660); })
                    .replace(/[\u06F0-\u06F9]/g, function (c) { return String(c.charCodeAt(0) - 0x06F0); });
  }
  function compact(t) { return chiffresOccidentaux(t).replace(/[\s.\-\/_]/g, ''); }
  // Message de la règle stricte, ou '' si la خانة est vide ou conforme ; la
  // validité native du champ est alignée (setCustomValidity) pour que le
  // navigateur refuse lui-même la soumission.
  function syncStrict(el) {
    const k = el.getAttribute('data-verif');
    if (!STRICTS[k] || typeof el.setCustomValidity !== 'function') return '';
    const v = compact(el.value);
    const msg = v && !VERIFS[k][0].test(v) ? VERIFS[k][1] : '';
    el.setCustomValidity(msg);
    return msg;
  }
  // Première خانة cin/rib non conforme dans `racine`, ou null (utilisé aussi
  // par les écrans qui enregistrent en fetch, comme وثائق الخلاص).
  window.champIdentiteInvalide = function (racine) {
    const champs = (racine || document).querySelectorAll('[data-verif="cin"], [data-verif="rib"]');
    for (let i = 0; i < champs.length; i++) {
      const el = champs[i];
      if (el.disabled) continue;
      const msg = syncStrict(el);
      if (msg) { el.dataset.touche = '1'; verifierChamp(el); return { champ: el, message: msg }; }
    }
    return null;
  };
  function messageNatif(el) {
    const v = el.validity;
    if (v.valid) return '';
    if (v.customError) return el.validationMessage;
    if (v.valueMissing) return 'هذه الخانة إجباريّة';
    if (v.tooShort) return 'يجب ألّا يقلّ الطول عن ' + el.minLength + ' رموز';
    if (v.typeMismatch && el.type === 'email') return VERIFS.email[1];
    if (v.patternMismatch) return el.getAttribute('data-msg') || 'الصيغة غير صحيحة';
    if (v.rangeUnderflow || v.rangeOverflow) return 'القيمة خارج المجال المسموح به';
    return el.validationMessage || 'قيمة غير صحيحة';
  }
  // Dans une ligne flex (plusieurs champs côte à côte), le message va SOUS la
  // ligne, préfixé du nom du champ, pour ne pas écraser ses voisins.
  function enLigne(el) {
    const p = el.parentNode;
    try {
      const cs = getComputedStyle(p);
      return cs.display.indexOf('flex') !== -1 && cs.flexDirection.indexOf('row') === 0
             && p.querySelectorAll('input, select, textarea').length > 1;
    } catch (e) { return false; }
  }
  function libelle(el) {
    if (el.getAttribute('data-libelle')) return el.getAttribute('data-libelle');
    if (el.placeholder) return el.placeholder;
    if (el.tagName === 'SELECT' && el.options.length) return el.options[0].text.replace(/[—\-]/g, '').trim();
    return '';
  }
  function bulle(el) {
    const ligne = enLigne(el);
    // v1.7.1 : un champ mot de passe vit dans .pwd-wrap avec son bouton œil ;
    // le message se place APRÈS ce cadre, jamais entre le champ et l'œil.
    const cadreMdp = !ligne && el.parentNode.classList && el.parentNode.classList.contains('pwd-wrap');
    const conteneur = ligne ? el.parentNode.parentNode : (cadreMdp ? el.parentNode.parentNode : el.parentNode);
    const apres = ligne ? el.parentNode : (cadreMdp ? el.parentNode : el);
    const cle = el.name || el.id || '';
    let b = conteneur.querySelector(':scope > .verif-msg[data-pour="' + cle + '"]');
    if (!b) {
      b = document.createElement('div');
      b.className = 'verif-msg';
      b.setAttribute('data-pour', cle);
      if (ligne) b.setAttribute('data-prefixe', libelle(el));
      let ref = apres;         // à la suite des messages déjà posés : ordre des champs
      while (ligne && ref.nextElementSibling && ref.nextElementSibling.classList.contains('verif-msg')) ref = ref.nextElementSibling;
      ref.insertAdjacentElement('afterend', b);
    }
    return b;
  }
  function verifierChamp(el) {
    if (el.disabled || el.readOnly || el.type === 'hidden') return;
    const val = (el.value || '').trim();
    let niveau = '', msg = '';
    syncStrict(el);
    if (typeof el.checkValidity === 'function' && !el.validity.valid) { niveau = 'erreur'; msg = messageNatif(el); }
    else if (val && el.getAttribute('data-verif')) {
      const r = VERIFS[el.getAttribute('data-verif')];
      const brut = el.getAttribute('data-verif') === 'email' ? val : val.replace(/[\s.\-\/]/g, '');
      if (r && !r[0].test(brut)) { niveau = 'avert'; msg = r[1]; }
    }
    el.classList.toggle('champ-invalide', niveau === 'erreur');
    el.classList.toggle('champ-avert', niveau === 'avert');
    el.classList.toggle('champ-valide', !niveau && !!val && (el.required || !!el.getAttribute('data-verif')));
    if (msg || el.dataset.bulle) {
      el.dataset.bulle = '1';
      const b = bulle(el);
      const pre = b.getAttribute('data-prefixe');
      b.textContent = msg && pre ? pre + ' : ' + msg : msg;
      b.className = 'verif-msg' + (niveau ? ' verif-msg--' + niveau : '');
      b.style.display = msg ? '' : 'none';
    }
  }
  function concerne(el) {
    if (!el || !el.matches) return false;
    if (!el.matches('input, select, textarea')) return false;
    if (el.closest('[data-sans-verif]')) return false;
    return el.required || el.hasAttribute('minlength') || el.hasAttribute('pattern')
        || el.type === 'email' || el.hasAttribute('data-verif');
  }
  document.addEventListener('focusout', function (e) {
    const el = e.target;
    if (!concerne(el)) return;
    // Chiffres arabes-indiens convertis dès qu'on quitte une خانة cin/rib.
    if (STRICTS[el.getAttribute('data-verif')] && /[\u0660-\u0669\u06F0-\u06F9]/.test(el.value)) {
      el.value = chiffresOccidentaux(el.value);
    }
    el.dataset.touche = '1';
    // Si le champ perd le focus parce qu'on appuie sur un bouton, la bulle
    // d'erreur insérée maintenant décalerait la page entre mousedown et mouseup
    // et le clic serait perdu : on l'affiche seulement après le relâchement.
    if (sourisEnfoncee) {
      document.addEventListener('mouseup', function () {
        setTimeout(function () { verifierChamp(el); }, 0);
      }, { once: true, capture: true });
    } else {
      verifierChamp(el);
    }
  }, true);
  let sourisEnfoncee = false;
  document.addEventListener('mousedown', function () { sourisEnfoncee = true; }, true);
  document.addEventListener('mouseup', function () { sourisEnfoncee = false; }, true);
  document.addEventListener('input', function (e) {
    const el = e.target;
    if (concerne(el) && el.dataset.touche) verifierChamp(el);
  }, true);
  // À la soumission : les champs invalides sont signalés et le premier reçoit le focus.
  document.addEventListener('invalid', function (e) {
    const el = e.target;
    if (!concerne(el)) return;
    e.preventDefault();
    el.dataset.touche = '1';
    verifierChamp(el);
    const f = el.form;
    if (f && !f.dataset.focusInvalide) {
      f.dataset.focusInvalide = '1';
      el.focus();
      el.scrollIntoView({block: 'center', behavior: 'smooth'});
      setTimeout(function () { delete f.dataset.focusInvalide; }, 300);
    }
  }, true);
  // Une fiche ouverte avec un ancien numéro non conforme, jamais touchée :
  // le contrôle est refait au moment de soumettre, et la soumission bloquée.
  document.addEventListener('submit', function (e) {
    const f = e.target;
    if (!f || !f.querySelector || f.hasAttribute('novalidate')) return;
    const pb = window.champIdentiteInvalide(f);
    if (!pb) return;
    e.preventDefault();
    e.stopImmediatePropagation();
    pb.champ.focus();
    pb.champ.scrollIntoView({block: 'center', behavior: 'smooth'});
  }, true);

  /* ── 2 septies. Mémoire des filtres (v1.5 — UX1) ───────────────────────
     Un champ portant data-memoriser="clé" retrouve sa valeur au retour sur
     la page (sessionStorage : propre à l'onglet, oublié à sa fermeture),
     puis déclenche input/change pour réappliquer le filtre. */
  function restaurerFiltres() {
    document.querySelectorAll('[data-memoriser]').forEach(function (el) {
      const cle = 'filtre:' + location.pathname + ':' + el.getAttribute('data-memoriser');
      let v = null;
      try { v = sessionStorage.getItem(cle); } catch (e) {}
      if (v !== null && v !== el.value) {
        if (el.tagName === 'SELECT' && !Array.prototype.some.call(el.options, function (o) { return o.value === v; })) v = null;
        if (v !== null) {
          el.value = v;
          el.dispatchEvent(new Event('change', {bubbles: true}));
          el.dispatchEvent(new Event('input', {bubbles: true}));
        }
      }
      const sauver = function () { try { sessionStorage.setItem(cle, el.value); } catch (e) {} };
      el.addEventListener('input', sauver);
      el.addEventListener('change', sauver);
    });
  }

  /* ── 2 octies. Infobulles des graphiques (v1.5 — D1/D2) ────────────────
     Tout élément [data-infobulle] affiche son texte au survol et au focus
     clavier (les colonnes des graphiques sont focalisables). */
  let bulleInfo = null;
  function montrerInfo(el, x, y) {
    if (!bulleInfo) {
      bulleInfo = document.createElement('div');
      bulleInfo.className = 'infobulle';
      bulleInfo.setAttribute('role', 'tooltip');
      document.body.appendChild(bulleInfo);
    }
    bulleInfo.textContent = el.getAttribute('data-infobulle');
    bulleInfo.style.display = 'block';
    const l = bulleInfo.offsetWidth, h = bulleInfo.offsetHeight;
    bulleInfo.style.left = Math.max(6, Math.min(window.innerWidth - l - 6, x - l / 2)) + 'px';
    bulleInfo.style.top = Math.max(6, y - h - 12) + 'px';
  }
  function cacherInfo() { if (bulleInfo) bulleInfo.style.display = 'none'; }
  document.addEventListener('mousemove', function (e) {
    const el = e.target.closest ? e.target.closest('[data-infobulle]') : null;
    if (el) montrerInfo(el, e.clientX, e.clientY); else cacherInfo();
  });
  document.addEventListener('focusin', function (e) {
    const el = e.target.closest ? e.target.closest('[data-infobulle]') : null;
    if (!el) return;
    const r = el.getBoundingClientRect();
    montrerInfo(el, r.left + r.width / 2, r.top + r.height / 3);
  });
  document.addEventListener('focusout', cacherInfo);

  /* ── 2 nonies. Recherche unifiée (v1.5 — D4) ───────────────────────────
     Saisie → /api/recherche (après 220 ms de pause) → résultats groupés.
     ↑/↓ pour parcourir, Entrée pour ouvrir, Échap pour fermer ; Ctrl+K ou
     « / » (hors d'un champ) place le curseur dans la recherche. */
  function demarrerRecherche() {
    const boite = document.getElementById('rechGlobale');
    if (!boite) return;
    const champ = document.getElementById('rechGlobaleInput');
    const res = document.getElementById('rechGlobaleRes');
    let minuteur = null, requeteEnCours = 0, actif = -1;

    function liens() { return Array.prototype.slice.call(res.querySelectorAll('a.rech-globale__item')); }
    function fermer() { res.hidden = true; champ.setAttribute('aria-expanded', 'false'); actif = -1; }
    function ouvrir() { res.hidden = false; champ.setAttribute('aria-expanded', 'true'); }
    function marquer(i) {
      const l = liens();
      l.forEach(function (a, k) { a.classList.toggle('actif', k === i); a.setAttribute('aria-selected', k === i ? 'true' : 'false'); });
      actif = i;
      if (l[i]) l[i].scrollIntoView({block: 'nearest'});
    }
    function afficher(donnees) {
      res.textContent = '';
      if (!donnees.groupes.length) {
        const v = document.createElement('div');
        v.className = 'rech-globale__vide';
        v.textContent = 'لا توجد نتائج لـ «' + donnees.q + '»';
        res.appendChild(v);
      }
      donnees.groupes.forEach(function (g) {
        const t = document.createElement('div');
        t.className = 'rech-globale__groupe';
        t.textContent = g.icone + ' ' + g.groupe;
        res.appendChild(t);
        g.resultats.forEach(function (x) {
          const a = document.createElement('a');
          a.className = 'rech-globale__item';
          a.href = x.url;
          a.setAttribute('role', 'option');
          const s1 = document.createElement('strong'); s1.textContent = x.titre;
          const s2 = document.createElement('small'); s2.textContent = x.sous_titre || '';
          a.appendChild(s1); a.appendChild(s2);
          res.appendChild(a);
        });
      });
      ouvrir();
      actif = -1;
    }
    function chercher() {
      const q = champ.value.trim();
      if (q.length < 2) { fermer(); return; }
      const n = ++requeteEnCours;
      window.fetch('/api/recherche?q=' + encodeURIComponent(q))
        .then(function (r) { return r.ok ? r.json() : null; })
        .then(function (d) { if (d && n === requeteEnCours && champ.value.trim() === q) afficher(d); })
        .catch(function () { /* hors ligne : silence */ });
    }
    champ.addEventListener('input', function () { clearTimeout(minuteur); minuteur = setTimeout(chercher, 220); });
    champ.addEventListener('focus', function () { if (res.childNodes.length && champ.value.trim().length >= 2) ouvrir(); });
    champ.addEventListener('keydown', function (e) {
      const l = liens();
      if (e.key === 'ArrowDown') { e.preventDefault(); if (res.hidden) chercher(); else marquer(Math.min(l.length - 1, actif + 1)); }
      else if (e.key === 'ArrowUp') { e.preventDefault(); marquer(Math.max(0, actif - 1)); }
      else if (e.key === 'Enter') {
        const cible = l[actif >= 0 ? actif : 0];
        if (cible && !res.hidden) { e.preventDefault(); location.href = cible.href; }
      }
      else if (e.key === 'Escape') { fermer(); champ.blur(); }
    });
    document.addEventListener('click', function (e) { if (!boite.contains(e.target)) fermer(); });
    document.addEventListener('keydown', function (e) {
      const dansChamp = e.target.closest && e.target.closest('input, textarea, select, [contenteditable]');
      if ((e.key === 'k' || e.key === 'K') && (e.ctrlKey || e.metaKey)) { e.preventDefault(); champ.focus(); champ.select(); }
      else if (e.key === '/' && !dansChamp) { e.preventDefault(); champ.focus(); }
    });
  }

  /* ── 3. Démarrage ────────────────────────────────────────────────────── */

  function demarrer() {
    injecter(); equiperFormulaires(); armerToastsServeur(); demarrerVeille();
    document.querySelectorAll('table.table-triable').forEach(equiperTri);
    restaurerFiltres();
    demarrerRecherche();
  }
  window.equiperTri = equiperTri;
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', demarrer);
  } else {
    demarrer();
  }
})();
