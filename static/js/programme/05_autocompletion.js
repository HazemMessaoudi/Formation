/* ═══ نظام إدارة التكوين — صفحة إعداد برنامج التكوين ═══
   Moteur d'autocomplétion (المكوّن + المشاركون).
   v1.7 : extrait tel quel de templates/nouvelle_lettre.html (aucun
   changement de comportement). Les données du serveur sont fournies
   par le petit script en ligne de la page (constantes *_INIT, PAGE).
   Les fichiers se chargent dans l'ordre 01 → 06. */

// ── Autocomplete : « portail » ───────────────────────────────────────────────
/* La liste est en position:fixed. Tant qu'elle reste à l'intérieur de
   .main-content, le moindre transform/filter/perspective sur un ancêtre en fait
   le bloc conteneur et la décale (régression v1.3). On la rattache donc
   directement à <body> dès sa première ouverture : plus aucun style d'ancêtre
   ne peut influer sur sa position. Le lien champ ↔ liste est conservé des deux
   côtés (inp._acList / list._acOwner). */
function _acListe(inp) {
  if (!inp) return null;
  if (!inp._acList) {
    const wrap = inp.closest('.ac-wrap');
    const list = wrap && wrap.querySelector('.ac-list');
    if (!list) return null;
    inp._acList = list;
    list._acOwner = inp;
  }
  if (inp._acList.parentElement !== document.body) document.body.appendChild(inp._acList);
  return inp._acList;
}
function _acChamp(el) {
  const list = el && el.closest('.ac-list');
  return list ? list._acOwner : null;
}
function _acMasquerTout(sauf) {
  document.querySelectorAll('body > .ac-list').forEach(l => {
    if (l === sauf) return;
    // Ligne supprimée entre-temps : la liste orpheline est retirée du DOM.
    if (!l._acOwner || !l._acOwner.isConnected) { l.remove(); return; }
    l.style.display = 'none';
  });
}
function _acRepositionner() {
  document.querySelectorAll('body > .ac-list').forEach(l => {
    if (l.style.display !== 'none' && l._acOwner && l._acOwner.isConnected) _acPosition(l._acOwner, l);
  });
}
window.addEventListener('scroll', _acRepositionner, true);
window.addEventListener('resize', _acRepositionner);

// ── Positionnement de la liste ─────────────────────────────────────────────────
function _acPosition(inp, list) {
  /* Position fixe calculée depuis le viewport — échappe à tout overflow parent */
  const rect = inp.getBoundingClientRect();
  const spaceBelow = window.innerHeight - rect.bottom;
  const listH = 220; // max-height CSS

  list.style.width = rect.width + 'px';
  list.style.left  = rect.left + 'px';
  list.style.right = 'auto';

  if (spaceBelow < listH + 8 && rect.top > listH + 8) {
    /* Pas assez de place en bas → ouvre vers le haut */
    list.style.top    = 'auto';
    list.style.bottom = (window.innerHeight - rect.top + 2) + 'px';
  } else {
    /* Ouvre vers le bas (comportement normal) */
    list.style.top    = (rect.bottom + 2) + 'px';
    list.style.bottom = 'auto';
  }
}

// ── Moteur unique d'autocomplétion (المكوّن + المشاركون) ───────────────────────
/* Une seule fonction construit la liste ; seule l'ACTION au choix diffère
   (_choixFormateur / _choixParticipant). Les fiches trouvées restent attachées
   à la liste (list._acData) : on ne recopie plus nom/رتبة/… dans des chaînes
   onmousedown="pickAc('…')" — un nom contenant une apostrophe cassait la
   sélection, et le texte affiché n'était pas échappé. */
const _AC_MAX = 40;

function _acEsc(s) {
  return String(s ?? '').replace(/[&<>"']/g,
    c => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[c]));
}

function _acNomComplet(m) {
  return ((m.nom || '') + (m.prenom ? ' ' + m.prenom : '')).trim();
}

/* Fiches déjà reçues du serveur, par nom complet : sert à la correspondance
   exacte « nom tapé → رتبة / مكان العمل » pendant la frappe. */
const _acCache = new Map();
MKOWIN_INIT.forEach(m => _acCache.set(_acNomComplet(m), m));

/* Source des propositions : le serveur filtre (nom complet, رتبة ou مكان العمل)
   avec la même règle qu'auparavant côté navigateur. */
async function _acRechercher(q) {
  const r = await fetch(`/api/mkowin/recherche?q=${encodeURIComponent(q)}&limite=${_AC_MAX}`,
                        {headers: {'Accept': 'application/json'}});
  if (!r.ok) throw new Error('HTTP ' + r.status);
  const liste = await r.json();
  liste.forEach(m => _acCache.set(_acNomComplet(m), m));
  return liste;
}

/* Nom tapé à la main identique à une fiche connue → رتبة / مكان العمل remplis
   (comme l'ancien écouteur 'input', mais aussi quand la réponse arrive après). */
function _acSyncExact(inp) {
  if (!inp.classList.contains('f-nom')) return;
  const m = _acCache.get(inp.value.trim());
  const row = inp.closest('tr');
  if (m && row) {
    row.querySelector('.f-grade').value = m.grade || '';
    row.querySelector('.f-lieu-travail').value = m.lieu_travail || '';
  }
}

function _acAfficher(inp, list, matches, q) {
  const nouveau = `<div class="ac-item ac-new" onmousedown="goNewMkow()">➕ إضافة شخص جديد...</div>`;
  list._acData = matches;
  if (!matches.length && q) {
    list.innerHTML = nouveau;
  } else {
    list.innerHTML = matches.map((m, i) =>
      `<div class="ac-item" data-i="${i}" onmousedown="_acChoisir(event, this)">
        <span class="ac-name">${_acEsc(_acNomComplet(m))}</span>
        <span class="ac-grade">${_acEsc(m.grade||'')} — ${_acEsc(m.lieu_travail||'')}</span>
      </div>`).join('') + nouveau;
  }
  list.style.display = 'block';
  _acPosition(inp, list);
}

async function _acOuvrir(inp, surChoix) {
  const list = _acListe(inp);
  if (!list) return;
  _acMasquerTout(list);
  list._acChoix = surChoix;
  const q = inp.value.trim().toLowerCase();
  const jeton = (list._acJeton || 0) + 1;     // seule la dernière requête compte
  list._acJeton = jeton;
  let matches;
  try {
    matches = await _acRechercher(q);
  } catch (e) {
    console.error('autocomplétion :', e);
    matches = [];
  }
  if (list._acJeton !== jeton) return;        // réponse périmée (frappe rapide)
  _acSyncExact(inp);
  if (document.activeElement !== inp) return; // champ quitté entre-temps
  _acAfficher(inp, list, matches, q);
}

function _acChoisir(e, el) {
  e.preventDefault();
  const list = el.closest('.ac-list');
  const inp  = _acChamp(el);
  const m    = list && list._acData ? list._acData[+el.dataset.i] : null;
  if (!inp || !m) return;
  list.style.display = 'none';
  list._acChoix(inp, m);
}

function showAcList(inp)     { _acOuvrir(inp, _choixFormateur); }
function showAcListPart(inp) { _acOuvrir(inp, _choixParticipant); }

function hideAcList(inp, delay) {
  setTimeout(() => {
    const list = inp._acList || inp.closest('.ac-wrap')?.querySelector('.ac-list');
    if (list) list.style.display = 'none';
  }, delay);
}

function goNewMkow() {
  window.location.href = PAGE.urlAjouterMkow;
}

// ── Action au choix : المكوّن ──────────────────────────────────────────────────
function _choixFormateur(inp, m) {
  const grade = m.grade || '', lieu = m.lieu_travail || '';
  inp.value = _acNomComplet(m);
  inp.dataset.grade = grade;
  inp.dataset.lieu = lieu;
  const row = inp.closest('tr');
  if (row) {
    row.querySelector('.f-grade').value = grade;
    row.querySelector('.f-lieu-travail').value = lieu;
  }
}

// ── Action au choix : المشاركون ────────────────────────────────────────────────
function _choixParticipant(inp, m) {
  const name  = _acNomComplet(m);
  const grade = m.grade || '', lieu = m.lieu_travail || '';
  const iduq  = m.identifiant_unique || '', jiha = m.jiha_marjiiya || '';

  // Bloquer l'ajout du formateur comme participant
  const tbody = inp.closest('tbody');
  if (tbody) {
    const fid = tbody.id.replace('ptbody_', '');
    const formateur = _FORM_FORMATCEURS[fid] || '';
    if (formateur && name.trim().toLowerCase() === formateur) {
      showToast('⚠️ المكوِّن لا يمكن أن يكون مشاركاً في نفس الدورة', 'error');
      inp.value = '';
      return;
    }

    // Vérification doublon identifiant_unique (hors ligne courante)
    if (iduq) {
      const currentRow = inp.closest('tr');
      const alreadyIn = Array.from(tbody.querySelectorAll('tr'))
        .filter(tr => tr !== currentRow)
        .some(tr => (tr.querySelector('.p-id')?.value?.trim() || '') === iduq);
      if (alreadyIn) {
        showToast(`⚠️ هذا المشارك موجود مسبقاً في القائمة (المعرف: ${iduq})`, 'error');
        inp.value = '';
        return;
      }
    }
  }

  inp.value = name;
  const row = inp.closest('tr');
  if (row) {
    const g = row.querySelector('.p-grade');  if (g)  g.value  = grade;
    const i = row.querySelector('.p-id');     if (i)  i.value  = iduq;
    const l = row.querySelector('.p-lieu');   if (l)  l.value  = lieu;
    // La جهة portée par la fiche du مكوّن suit la personne : c'est la raison
    // d'être de la colonne. Une fiche sans جهة n'écrase rien de saisi à la main.
    // v1.7.1 : plus de colonne visible ; la جهة de la fiche suit la ligne.
    row.dataset.jiha = jiha || '';
    // v1.6 — même règle pour الجنس / الفئة العمريّة : la fiche remplit, une
    // fiche vide n'efface pas un choix fait à la main.
    const sx = row.querySelector('.p-sexe');
    if (sx && m.sexe && SEXES_INIT.includes(m.sexe)) { sx.value = m.sexe; sx.classList.remove('champ-manquant'); }
    const fa = row.querySelector('.p-fiaa');
    if (fa && m.fiaa_omria && FIAAT_INIT.includes(m.fiaa_omria)) { fa.value = m.fiaa_omria; fa.classList.remove('champ-manquant'); }
  }
}

