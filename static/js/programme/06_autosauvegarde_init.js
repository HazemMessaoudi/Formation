/* ═══ نظام إدارة التكوين — صفحة إعداد برنامج التكوين ═══
   Autosauvegarde, reprise, initialisation de la page.
   v1.7 : extrait tel quel de templates/nouvelle_lettre.html (aucun
   changement de comportement). Les données du serveur sont fournies
   par le petit script en ligne de la page (constantes *_INIT, PAGE).
   Les fichiers se chargent dans l'ordre 01 → 06. */

// ══ Autosauvegarde — reprise du travail + protection coupure de courant ══════
const DRAFT_KEY = 'brouillon_lettre_' + (PAGE.lettreId || 'nouveau');
let _dirty = false;
let _locked = false;   // passé à true dans lockUI()

function _snapshot() {
  try {
    return JSON.stringify({
      t: Date.now(),
      type:  document.querySelector('input[name="type"]:checked')?.value || 'interne',
      mois:  document.getElementById('mois').value,
      annee: document.getElementById('annee').value,
      formations: collecterFormations()
    });
  } catch(e) { return null; }
}
const DRAFTS_REGISTRY_KEY = 'drafts_registry';

function _updateDraftsRegistry() {
  if (!savedLettreId) return;
  try {
    const reg = JSON.parse(localStorage.getItem(DRAFTS_REGISTRY_KEY) || '[]');
    const idx = reg.findIndex(e => e.lettreId === savedLettreId);
    const p = payload();
    const entry = {
      lettreId: savedLettreId,
      titre: (p.formations && p.formations[0] && p.formations[0].titre) || '',
      mois: p.mois || '',
      annee: p.annee || '',
      savedAt: new Date().toISOString()
    };
    if (idx >= 0) reg[idx] = entry; else reg.unshift(entry);
    localStorage.setItem(DRAFTS_REGISTRY_KEY, JSON.stringify(reg.slice(0, 20)));
  } catch(e) {}
}

function _removeDraftsRegistry() {
  if (!savedLettreId) return;
  try {
    const reg = JSON.parse(localStorage.getItem(DRAFTS_REGISTRY_KEY) || '[]');
    localStorage.setItem(DRAFTS_REGISTRY_KEY,
      JSON.stringify(reg.filter(e => e.lettreId !== savedLettreId)));
  } catch(e) {}
}

function autosave() {
  if (_locked) return;
  const s = _snapshot(); if (!s) return;
  try { localStorage.setItem(DRAFT_KEY, s); } catch(e) {}
  _updateDraftsRegistry();
}
function marquerDirty() { _dirty = true; autosave(); }
function draftSaved() {
  _dirty = false;
  try { localStorage.removeItem(DRAFT_KEY); } catch(e) {}
  _removeDraftsRegistry();
}

// Sauvegarde automatique périodique (toutes les 5 s) → survit à une coupure
setInterval(autosave, 5000);

// Sauvegarde SERVEUR périodique : dès qu'une dorra a un titre, le programme est
// persisté côté serveur (brouillon verrouille=0) → il apparaît dans « استكمال
// برنامج تكوين » même si l'utilisateur quitte sans confirmer.
let _serverSaving = false;
function _aDuContenu(p) {
  return (p.mois && p.mois.trim())
      || (p.formations && p.formations.some(f => f.titre && f.titre.trim()));
}
async function serveurAutosave() {
  if (_locked || _serverSaving || !_dirty) return;
  const p = payload();
  if (!_aDuContenu(p)) return;   // rien d'utile à reprendre
  _serverSaving = true;
  try {
    const body = JSON.stringify(Object.assign({lettre_id: savedLettreId || null}, p));
    const res = await fetch('/lettre/autosave', {
      method:'POST', headers:{'Content-Type':'application/json'}, body});
    const d = await res.json();
    if (d && d.succes && d.lettre_id) savedLettreId = d.lettre_id;
  } catch(e) { /* silencieux */ }
  finally { _serverSaving = false; }
}
setInterval(serveurAutosave, 3000);

// Sauvegarde ULTIME au moment de quitter (fermeture, rafraîchissement, lien) :
// sendBeacon envoie le brouillon de façon fiable même pendant le déchargement.
function _beaconSave() {
  if (_locked) return;
  const p = payload();
  if (!_aDuContenu(p)) return;
  try {
    // sendBeacon ne peut pas poser d'en-tête : le jeton CSRF voyage dans le corps.
    const body = new Blob(
      [JSON.stringify(Object.assign(
        {lettre_id: savedLettreId || null, _csrf: window.CSRF_TOKEN || ''}, p))],
      {type: 'application/json'});
    navigator.sendBeacon('/lettre/autosave', body);
  } catch(e) { /* silencieux */ }
}
// … et à chaque modification du formulaire
['input','change'].forEach(ev => document.addEventListener(ev, e => {
  if (!_locked && e.target.closest && e.target.closest('#formLettre')) marquerDirty();
}));
// Avertissement natif du navigateur + sauvegarde fiable avant de quitter
window.addEventListener('beforeunload', e => {
  if (_dirty && !_locked) {
    _beaconSave();                       // enregistre le brouillon côté serveur
    e.preventDefault(); e.returnValue = ''; return '';
  }
});
// Filet de sécurité supplémentaire (onglet caché / bascule d'app sur mobile)
document.addEventListener('visibilitychange', () => {
  if (document.visibilityState === 'hidden' && _dirty && !_locked) _beaconSave();
});

function restaurerBrouillon(callback) {
  let raw; try { raw = localStorage.getItem(DRAFT_KEY); } catch(e) { callback(false); return; }
  if (!raw) { callback(false); return; }
  let d; try { d = JSON.parse(raw); } catch(e) { callback(false); return; }
  const fs = (d && d.formations) || [];
  const contenu = (d && d.mois) || fs.some(f => f.titre || f.nom_formateur || f.date_formation);
  if (!contenu) { callback(false); return; }
  const quand = d.t ? new Date(d.t).toLocaleString('fr-FR') : '';
  showConfirmModal(
    `💾 توجد مسودّة غير مؤكَّدة${quand ? ' (' + quand + ')' : ''}.\n\nهل تريد استرجاع العمل الذي لم يُحفظ؟`,
    () => {
      if (d.type)  { const r = document.querySelector(`input[name="type"][value="${d.type}"]`); if (r) r.checked = true; }
      if (d.mois)  document.getElementById('mois').value = d.mois;
      if (d.annee) document.getElementById('annee').value = d.annee;
      document.getElementById('tbody').innerHTML = ''; ligneCount = 0;
      fs.forEach(f => ajouterLigne(f));
      updateDateLimits(); updateEmptyMsg();
      showToast('تمّ استرجاع المسودّة ✓');
      callback(true);
    },
    () => {
      try { localStorage.removeItem(DRAFT_KEY); } catch(e) {}
      callback(false);
    }
  );
}

// ── استكمال برنامج تكوين (Change 3+9) ───────────────────────────────────────
async function afficherBrouillonsServeur() {
  const section = document.getElementById('draftsSection');
  if (!section) return;
  try {
    const res = await fetch('/api/drafts');
    if (!res.ok) return;
    const d = await res.json();
    const drafts = (d.drafts || []);
    if (!drafts.length) return;
    section.style.display = '';
    const list = document.getElementById('draftsList');
    list.innerHTML = drafts.map(dr => {
      const titres = dr.titres ? dr.titres.split(' | ').filter(Boolean) : [];
      const titrePrincipal = titres[0] || '—';
      const dateStr = dr.date_creation ? dr.date_creation.slice(0,10) : '';
      const moisAnnee = [dr.mois, dr.annee].filter(Boolean).join(' ');
      return `<div style="display:flex;align-items:center;gap:.8rem;flex-wrap:wrap;
                          padding:.6rem .8rem;background:var(--bg);border-radius:8px;
                          border:1px solid var(--border);">
        <div style="flex:1;min-width:140px;">
          <div style="font-weight:700;font-size:.95rem;">${esc(titrePrincipal)}</div>
          <div style="color:var(--text-muted);font-size:.82rem;">
            ${esc(moisAnnee)}${dateStr ? ' · ' + dateStr : ''}
            · ${dr.nb_formations} دورة
          </div>
        </div>
        <a href="/lettre/nouvelle?modifier=${dr.lettre_id}"
           class="btn" style="background:#f59e0b;color:#fff;text-decoration:none;
                              padding:.4rem .9rem;font-size:.88rem;white-space:nowrap;">
          ▶ استكمال
        </a>
      </div>`;
    }).join('');
  } catch(e) { /* silencieux */ }
}

// ── Init ──────────────────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  if (PAGE.etat === 'verrouille') {
  // Already locked
  if (FORMATIONS_EDIT.length) FORMATIONS_EDIT.forEach(f => ajouterLigne(f));
  else ajouterLigne();
  lockUI(PAGE.refVerrouille);
  } else if (PAGE.etat === 'brouillon') {
  // Draft in edit mode — show confirm button
  if (FORMATIONS_EDIT.length) FORMATIONS_EDIT.forEach(f => ajouterLigne(f));
  else ajouterLigne();
  document.getElementById('btnConfirmer').style.display = 'inline-flex';
  } else {
  // New page: check localStorage for an in-progress draft
  restaurerBrouillon(restored => {
    if (!restored) ajouterLigne();
  });
  }
});

// ── Change 1 : intercepter les clics sur les liens quand isDirty ─────────────
document.addEventListener('click', e => {
  if (_locked) return;
  if (!_dirty) return;
  const anchor = e.target.closest('a[href]');
  if (!anchor) return;
  const href = anchor.getAttribute('href');
  if (!href || href.startsWith('#') || href.startsWith('javascript')) return;
  // Allow same-page navigation
  try {
    const url = new URL(href, location.href);
    if (url.pathname === location.pathname && url.search === location.search) return;
  } catch(ex) {}
  e.preventDefault();
  _showLeaveModal(anchor.href || href);
});

// Avertissement natif du navigateur avant fermeture / rechargement de l'onglet
// (Change 1 : keepbeforeunload pour browser close/refresh)

// Re-open panels if user navigated back to a locked letter
// step sections already shown by lockUI above
