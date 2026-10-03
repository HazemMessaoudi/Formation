/* ═══ نظام إدارة التكوين — صفحة إعداد برنامج التكوين ═══
   Étapes 1 et 2 : saisie du برنامج, alertes, مسودّة, destinations.
   v1.7 : extrait tel quel de templates/nouvelle_lettre.html (aucun
   changement de comportement). Les données du serveur sont fournies
   par le petit script en ligne de la page (constantes *_INIT, PAGE).
   Les fichiers se chargent dans l'ordre 01 → 06. */


// ══ Modal : تحذير المغادرة ════════════════════════════════════════════════════
let _pendingNavUrl = null;
function _showLeaveModal(url) {
  _pendingNavUrl = url;
  document.getElementById('leaveWarningModal').style.display = 'flex';
}
async function _leaveModalSave() {
  document.getElementById('leaveWarningModal').style.display = 'none';
  // Enregistrement INDULGENT : on sauvegarde le travail en cours tel quel
  // (même incomplet) pour pouvoir le reprendre plus tard, sans exiger que tous
  // les champs soient remplis.
  const p = payload();
  const aContenu = (p.mois && p.mois.trim())
    || (p.formations && p.formations.some(f => f.titre && f.titre.trim()));
  if (aContenu) {
    try {
      const url = savedLettreId ? `/lettre/${savedLettreId}/mettre-a-jour` : '/lettre/enregistrer';
      const res = await fetch(url, {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(p)});
      const d = await res.json();
      if (d.succes) {
        if (d.lettre_id) savedLettreId = d.lettre_id;
        _dirty = false;
      }
    } catch(e) { /* on poursuit la navigation quoi qu'il arrive */ }
  }
  if (_pendingNavUrl) window.location.href = _pendingNavUrl;
}
function _leaveModalLeave() {
  document.getElementById('leaveWarningModal').style.display = 'none';
  _dirty = false;
  if (_pendingNavUrl) window.location.href = _pendingNavUrl;
}
function _leaveModalCancel() {
  document.getElementById('leaveWarningModal').style.display = 'none';
  _pendingNavUrl = null;
}

// ── Données initiales depuis le serveur ──────────────────────────────────────
// v1.4 : seules les fiches publiques des مكوّنين du programme modifié sont
// injectées ; l'autocomplétion interroge /api/mkowin/recherche.
// v1.6 — الجنس / الفئة العمريّة : pour الإحصائيات seulement, jamais imprimés.

let grades  = [...GRADES_INIT];
let lieux   = [...LIEUX_INIT];
let ligneCount = 0;
let savedLettreId = PAGE.lettreId;
const EDIT_MODE   = savedLettreId !== null;

function gradesOptions(selected='') {
  return grades.map(g => `<option value="${g}" ${g===selected?'selected':''}>${g}</option>`).join('');
}
// v1.5 : une valeur enregistrée qui n'est plus dans la liste (مادة supprimée,
// مكان retiré, برنامج copié) reste sélectionnée et signalée — sinon le
// formulaire l'afficherait vide et la prochaine sauvegarde l'effacerait.
function _escOpt(v) {
  return String(v == null ? '' : v).replace(/&/g,'&amp;').replace(/"/g,'&quot;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
}
function _optionsChoix(liste, selected, vide) {
  const sel = String(selected == null ? '' : selected).trim();
  return `<option value="">${vide}</option>` + liste.map(v =>
    `<option value="${_escOpt(v)}"${v === sel ? ' selected' : ''}>${_escOpt(v)}</option>`).join('');
}
function _optionHorsListe(selected, liste) {
  return (selected && !liste.includes(selected))
    ? `<option value="${_escOpt(selected)}" selected>${_escOpt(selected)} ⚠ (غير موجود في القائمة)</option>` : '';
}
function mawadOptions(selected='') {
  return _optionHorsListe(selected, MAWAD_INIT.map(m => m.titre)) +
         MAWAD_INIT.map(m => `<option value="${_escOpt(m.titre)}" data-id="${m.id}" ${m.titre===selected?'selected':''}>${_escOpt(m.titre)}</option>`).join('') +
         `<option value="__new__">➕ تكوين جديد...</option>`;
}
function lieuxOptions(selected='') {
  return _optionHorsListe(selected, lieux) +
         lieux.map(l => `<option value="${_escOpt(l)}" ${l===selected?'selected':''}>${_escOpt(l)}</option>`).join('');
}

// V3 — تصنيف الدّورة (إحصائيّات وتقارير فقط : aucun effet sur le برنامج).
// Noms de boutons radio propres à chaque ligne (mode_N, niveau_N).
const CLS_MODES   = ['حضوري', 'عن بعد'];
const CLS_NIVEAUX = ['جهوي', 'مركزي', 'مختص'];
function celluleClassification(data, n) {
  const mode   = CLS_MODES.includes(data.mode_formation) ? data.mode_formation : CLS_MODES[0];
  const niveau = CLS_NIVEAUX.includes(data.niveau_formation) ? data.niveau_formation : CLS_NIVEAUX[0];
  const coop   = (data.cooperation === 'وطني' || data.cooperation === 'دولي') ? data.cooperation : '';
  const hors   = String(data.hors_plan || '') === '1' || data.hors_plan === true;
  const radios = (cls, nom, liste, choisi) => liste.map(v =>
    `<label class="cls-pill"><input type="radio" class="${cls}" name="${nom}_${n}" value="${_escOpt(v)}" ${v===choisi?'checked':''}><span>${esc(v)}</span></label>`
  ).join('');
  return `
    <div class="cls-grp" title="نمط التكوين">${radios('f-mode', 'mode', CLS_MODES, mode)}</div>
    <div class="cls-grp" title="مستوى التكوين">${radios('f-niveau', 'niveau', CLS_NIVEAUX, niveau)}</div>
    <div class="cls-grp cls-opt">
      <label class="cls-chk"><input type="checkbox" class="f-coop" ${coop?'checked':''}
             onchange="this.closest('.cls-opt').querySelector('.f-coop-type').disabled = !this.checked"> تعاون</label>
      <select class="f-coop-type" ${coop?'':'disabled'} title="نوع التعاون">
        <option value="وطني" ${coop!=='دولي'?'selected':''}>وطني</option>
        <option value="دولي" ${coop==='دولي'?'selected':''}>دولي</option>
      </select>
    </div>
    <div class="cls-grp cls-opt">
      <label class="cls-chk"><input type="checkbox" class="f-hors-plan" ${hors?'checked':''}> خارج المخطّط</label>
    </div>`;
}
function classificationDe(tr) {
  const coop = tr.querySelector('.f-coop')?.checked;
  return {
    mode_formation:   tr.querySelector('.f-mode:checked')?.value || CLS_MODES[0],
    niveau_formation: tr.querySelector('.f-niveau:checked')?.value || CLS_NIVEAUX[0],
    cooperation:      coop ? (tr.querySelector('.f-coop-type')?.value || 'وطني') : '',
    hors_plan:        tr.querySelector('.f-hors-plan')?.checked ? 1 : 0,
  };
}

function ajouterLigne(data={}) {
  ligneCount++;
  const tbody = document.getElementById('tbody');
  const tr = document.createElement('tr');
  tr.id = `ligne_${ligneCount}`;

  tr.innerHTML = `
    <td class="num-cell">${String(ligneCount).padStart(2,'0')}</td>
    <td>
      <select class="f-titre">
        <option value="">— اختر التكوين —</option>
        ${mawadOptions(data.titre||'')}
      </select>
    </td>
    <td><input type="text" class="f-grade" placeholder="الرتبة" value="${esc(data.grade||'')}" readonly style="background:#f8f9fa;cursor:default;"></td>
    <td style="position:relative;">
      <div class="ac-wrap" style="position:relative;">
        <input type="text" class="f-nom" placeholder="اكتب للبحث..." autocomplete="off"
               value="${esc((data.nom_formateur||''))}"
               data-grade="${esc((() => { const m = MKOWIN_INIT.find(x=>(x.nom+(x.prenom?' '+x.prenom:'')).trim()===(data.nom_formateur||'')); return m?m.grade||'':''; })())}"
               data-lieu="${esc((() => { const m = MKOWIN_INIT.find(x=>(x.nom+(x.prenom?' '+x.prenom:'')).trim()===(data.nom_formateur||'')); return m?m.lieu_travail||'':''; })())}"
               oninput="showAcList(this)" onfocus="showAcList(this)" onblur="hideAcList(this,300)">
        <div class="ac-list" style="display:none;"></div>
      </div>
    </td>
    <td><input type="text" class="f-lieu-travail" placeholder="مكان العمل" value="${esc(data.lieu_travail||'')}" readonly style="background:#f8f9fa;cursor:default;"></td>
    <td class="td-dates">
      <div class="dates-plage">
        <label class="dp-l"><span>من</span>
          <input type="date" class="f-date" value="${esc(data.date_formation||'')}" style="min-width:130px;" onchange="validateDateInMonth(this)"></label>
        <label class="dp-l"><span>إلى</span>
          <input type="date" class="f-date-fin" value="${esc(data.date_fin||'')}" style="min-width:130px;"
                 title="اتركه فارغا إذا كانت الدورة ليوم واحد" onchange="validerDateFin(this)"></label>
        <small class="dp-info"></small>
      </div>
    </td>
    <td>
      <select class="f-periode" onchange="verifierDateDoublon(this.closest('tr').querySelector('.f-date'))">
        <option value="">—</option>
        <option value="صباحا" ${data.periode==='صباحا'?'selected':''}>صباحا</option>
        <option value="مساءا" ${data.periode==='مساءا'?'selected':''}>مساءا</option>
      </select>
    </td>
    <td>
      <select class="f-lieu-formation" onchange="verifierDateDoublon(this.closest('tr').querySelector('.f-date'))">
        <option value="">— اختر —</option>
        ${lieuxOptions(data.lieu_formation||'')}
      </select>
    </td>
    <td class="td-classif">${celluleClassification(data, ligneCount)}</td>
    <td><button type="button" class="btn-del" onclick="supprimerLigne('ligne_${ligneCount}')">🗑</button></td>
  `;
  tbody.appendChild(tr);
  updateEmptyMsg();
  updateDateLimits();
  majInfoPlage(tr);

  tr.querySelector('.f-titre').addEventListener('change', function() {
    if (this.value === '__new__') {
      this.value = '';
      window.location.href = PAGE.urlAjouterMadda;
    }
  });

  // Autocomplete: fill grade+lieu when a name is typed/selected
  tr.querySelector('.f-nom').addEventListener('input', function() {
    const row = this.closest('tr');
    const val = this.value.trim();
    const m = _acCache.get(val);
    if (m) {
      row.querySelector('.f-grade').value = m.grade || '';
      row.querySelector('.f-lieu-travail').value = m.lieu_travail || '';
    } else {
      row.querySelector('.f-grade').value = '';
      row.querySelector('.f-lieu-travail').value = '';
    }
  });
}

function supprimerLigne(id) {
  document.getElementById(id)?.remove();
  reNumeroter(); updateEmptyMsg();
}
function reNumeroter() {
  document.querySelectorAll('#tbody tr').forEach((tr, i) => {
    const nc = tr.querySelector('.num-cell');
    if (nc) nc.textContent = String(i+1).padStart(2,'0');
  });
}
function updateEmptyMsg() {
  const empty = document.getElementById('tbody').children.length === 0;
  document.getElementById('emptyMsg').style.display = empty ? '' : 'none';
}

function collecterFormations() {
  return Array.from(document.querySelectorAll('#tbody tr')).map(tr => ({
    titre:          tr.querySelector('.f-titre')?.value?.trim() || '',
    grade:          (tr.querySelector('.f-grade')?.value || '').trim(),
    nom_formateur:  tr.querySelector('.f-nom')?.value?.trim() || '',
    lieu_travail:   tr.querySelector('.f-lieu-travail')?.value?.trim() || '',
    date_formation: tr.querySelector('.f-date')?.value?.trim() || '',
    date_fin:       tr.querySelector('.f-date-fin')?.value?.trim() || '',
    periode:        tr.querySelector('.f-periode')?.value || '',
    lieu_formation: tr.querySelector('.f-lieu-formation')?.value?.trim() || '',
    ...classificationDe(tr),
  }));
}
function payload() {
  return {
    type:       document.querySelector('input[name="type"]:checked')?.value || 'interne',
    mois:       document.getElementById('mois').value,
    annee:      parseInt(document.getElementById('annee').value),
    formations: collecterFormations()
  };
}

const MOIS_NUM = {
  'جانفي':1,'فيفري':2,'مارس':3,'أفريل':4,'ماي':5,'جوان':6,
  'جويلية':7,'أوت':8,'سبتمبر':9,'أكتوبر':10,'نوفمبر':11,'ديسمبر':12
};

function updateDateLimits() {
  const mois  = document.getElementById('mois').value;
  const annee = parseInt(document.getElementById('annee').value);
  if (!mois || !annee) return;
  const m = MOIS_NUM[mois];
  if (!m) return;
  const first = `${annee}-${String(m).padStart(2,'0')}-01`;
  const lastDate = new Date(annee, m, 0);
  const last = `${annee}-${String(m).padStart(2,'0')}-${String(lastDate.getDate()).padStart(2,'0')}`;
  document.querySelectorAll('.f-date').forEach(inp => {
    inp.min = first; inp.max = last;
    if (inp.value && (inp.value < first || inp.value > last)) inp.value = '';
    majInfoPlage(inp.closest('tr'));
  });
}

// ── V2 : دورة متعدّدة الأيّام (من … إلى …) ─────────────────────────────────
// Même règle que le serveur (core/jours.py) : au plus 6 jours de formation,
// le dimanche intérieur n'est pas compté ; la fin peut déborder sur le mois
// suivant, le début reste dans le mois du برنامج.
const MAX_JOURS_DORRA = 6;
function _isoLocal(d) {
  return `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')}`;
}
function joursDorra(debut, fin) {
  if (!debut) return [];
  const [y, m, j] = debut.split('-').map(Number);
  const d0 = new Date(y, m - 1, j);
  if (isNaN(d0)) return [];
  if (!fin || fin <= debut) return [debut];
  const res = [debut];
  const d = new Date(d0);
  for (let k = 0; k < 21; k++) {
    d.setDate(d.getDate() + 1);
    const iso = _isoLocal(d);
    if (iso > fin) break;
    if (d.getDay() !== 0) res.push(iso);
  }
  return res;
}
function datesDorra(f) {
  const js = joursDorra(f.date_formation || '', f.date_fin || '');
  if (js.length <= 1) return esc(f.date_formation || '');
  // Isolé en RTL : lisible même dans une cellule dir="ltr".
  return `<bdi dir="rtl">من <bdi dir="ltr">${esc(js[0])}</bdi> إلى <bdi dir="ltr">${esc(js[js.length-1])}</bdi>`
       + ` <span class="badge-jours">${js.length} أيّام</span></bdi>`;
}
function majInfoPlage(tr) {
  if (!tr) return;
  const info = tr.querySelector('.dp-info');
  const d = tr.querySelector('.f-date'), f = tr.querySelector('.f-date-fin');
  if (!info || !d || !f) return;
  f.min = d.value || '';
  if (d.value) {
    const [y, m, j] = d.value.split('-').map(Number);
    f.max = _isoLocal(new Date(y, m - 1, j + 13));
  }
  const n = joursDorra(d.value, f.value).length;
  info.textContent = n > 1 ? `دورة متعدّدة الأيّام: ${n} أيّام (الأحد لا يُحتسب)` : '';
}
function validerDateFin(inp) {
  const tr = inp.closest('tr');
  const d = tr.querySelector('.f-date');
  if (inp.value && !d.value) {
    showToast('أدخل تاريخ بداية الدورة أوّلا', 'error'); inp.value = ''; majInfoPlage(tr); return;
  }
  if (inp.value && inp.value < d.value) {
    showToast('تاريخ نهاية الدورة يسبق تاريخ بدايتها', 'error'); inp.value = ''; majInfoPlage(tr); return;
  }
  if (inp.value === d.value) inp.value = '';          // même jour = دورة d'un jour
  const n = joursDorra(d.value, inp.value).length;
  const brut = inp.value ? Math.round((new Date(inp.value) - new Date(d.value)) / 864e5) : 0;
  let ouvres = 1;
  if (inp.value) {
    const [y, m, j] = d.value.split('-').map(Number);
    for (let k = 1; k <= brut; k++) if (new Date(y, m - 1, j + k).getDay() !== 0) ouvres++;
  }
  if (ouvres > MAX_JOURS_DORRA) {
    showToast(`مدّة الدورة ${ouvres} أيّام، والحدّ الأقصى ${MAX_JOURS_DORRA} أيّام متواصلة (من الاثنين إلى السبت)`, 'error');
    inp.value = ''; majInfoPlage(tr); return;
  }
  majInfoPlage(tr);
  if (n > 1) verifierDateDoublon(d);
}

function validateDateInMonth(inp) {
  if (!inp.value) return;
  if ((inp.min && inp.value < inp.min) || (inp.max && inp.value > inp.max)) {
    const mois = document.getElementById('mois').value;
    showToast(`التاريخ يجب أن يكون ضمن شهر ${mois}`, 'error');
    inp.value = '';
    return;
  }
  // يوم الأحد : l'agent confirme ou corrige, mais il le sait.
  if (estDimanche(inp.value)) {
    const d = inp.value;
    showConfirmModal(
      `تاريخ الدّورة ${d} يوافق يوم أحد.\n\nهل تؤكّد هذا التّاريخ، أم تريد تحيينه؟`,
      () => { inp.dataset.dimancheOk = d; verifierDateDoublon(inp); },
      () => { inp.value = ''; inp.focus(); });
    return;
  }
  majInfoPlage(inp.closest('tr'));
  verifierDateDoublon(inp);
}

function estDimanche(iso) {
  if (!iso) return false;
  const [y, m, j] = iso.split('-').map(Number);
  return new Date(y, m - 1, j).getDay() === 0;     // date locale, pas UTC
}

// Une فترة vide = la journée entière : elle recouvre matin et après-midi.
function periodesSeChevauchent(a, b) {
  return !a || !b || a === b;
}

function normLieu(s) {
  return (s || '').replace(/[\u064B-\u0652\u0670]/g, '').replace(/\s+/g, ' ').trim();
}

// ── تنبيه عند برمجة دورتين في نفس اليوم ─────────────────────────────────────
// Purement informatif : l'agent peut vouloir deux دورات le même jour, mais il
// doit le décider en connaissance de cause.
async function verifierDateDoublon(inp) {
  if (!inp) return;
  const d = inp.value;
  if (!d) return;
  const tr        = inp.closest('tr');
  const formateur = (tr?.querySelector('.f-nom')?.value || '').trim();
  const periode   = (tr?.querySelector('.f-periode')?.value || '').trim();
  const lieu      = (tr?.querySelector('.f-lieu-formation')?.value || '').trim();

  // Un même jour ne suffit pas à alarmer : ce qui compte, c'est le même
  // formateur (il ne peut pas être à deux endroits) ou le même créneau.
  const conflits = [];
  document.querySelectorAll('#tbody tr').forEach(autre => {
    if (autre === tr) return;
    const ad = autre.querySelector('.f-date')?.value || '';
    if (ad !== d) return;
    conflits.push({
      titre:     autre.querySelector('.f-titre')?.value || '',
      formateur: (autre.querySelector('.f-nom')?.value || '').trim(),
      periode:   (autre.querySelector('.f-periode')?.value || '').trim(),
      lieu:      (autre.querySelector('.f-lieu-formation')?.value || '').trim(),
      ref:       'في هذا البرنامج نفسه',
    });
  });
  try {
    const q = savedLettreId ? `&lettre_id=${savedLettreId}` : '';
    const res = await fetch(`/api/dorrat/meme-jour?date=${encodeURIComponent(d)}${q}`);
    if (res.ok) (await res.json()).dorrat.forEach(x => conflits.push({
      titre: x.titre, formateur: (x.nom_formateur || '').trim(),
      periode: (x.periode || '').trim(), lieu: (x.lieu_formation || '').trim(), ref: x.ref,
    }));
  } catch (e) { console.error('verifierDateDoublon:', e); }

  if (!conflits.length) return;

  // ── REFUS : même تاريخ + même فترة + même مكان. Ce n'est pas un choix :
  // une salle n'accueille pas deux دورات à la fois. Le serveur refuse aussi.
  const salle = lieu && conflits.find(c =>
    c.lieu && normLieu(c.lieu) === normLieu(lieu) && periodesSeChevauchent(c.periode, periode));
  if (salle) {
    showToast(`مرفوض: «${salle.titre || 'دورة أخرى'}» مبرمجة في نفس المكان «${lieu}» `
            + `بتاريخ ${d} في نفس الفترة (${periode || salle.periode || 'كامل اليوم'})`
            + (salle.ref ? ` — ${salle.ref}` : '') + '. غيّر التّاريخ أو الفترة أو المكان.', 'error');
    inp.value = '';
    inp.focus();
    return;
  }

  const memeFormateur = formateur
    && conflits.filter(c => c.formateur && c.formateur === formateur);
  const memePeriode = periode
    && conflits.filter(c => c.periode && c.periode === periode);

  let msg = `يوجد ${conflits.length} تكوين(ات) مبرمج(ة) بتاريخ ${d}:\n`;
  conflits.forEach(c => {
    const marques = [];
    if (formateur && c.formateur === formateur) marques.push('نفس المكوّن');
    if (periode   && c.periode   === periode)   marques.push('نفس الفترة');
    msg += `• ${c.titre || '(بدون عنوان)'}`
         + (c.formateur ? ` — ${c.formateur}` : '')
         + (c.periode ? ` (${c.periode})` : '')
         + (c.ref ? ` — ${c.ref}` : '')
         + (marques.length ? `  ⚠ ${marques.join(' و')}` : '') + '\n';
  });
  if (memeFormateur && memeFormateur.length) {
    msg += `\n⚠ المكوّن «${formateur}» مبرمج فعلا في نفس اليوم.\n`;
  }
  if (memePeriode && memePeriode.length) {
    msg += `⚠ نفس الفترة (${periode}) محجوزة في نفس اليوم.\n`;
  }
  msg += '\nهل تريد الإبقاء على هذه البرمجة؟';
  showConfirmModal(msg, null, () => { inp.value = ''; inp.focus(); });
}

function validate() {
  const p = payload();
  if (!p.mois) { showToast('يرجى اختيار الشهر', 'error'); return false; }
  if (p.formations.length === 0) { showToast('يرجى إضافة دورة واحدة على الأقل', 'error'); return false; }
  for (let i = 0; i < p.formations.length; i++) {
    const f = p.formations[i]; const n = i + 1;
    if (!f.titre)          { showToast(`الدورة ${n}: يرجى اختيار عنوان التكوين`, 'error');   return false; }
    if (!f.nom_formateur)  { showToast(`الدورة ${n}: يرجى اختيار المكوِّن`, 'error');         return false; }
    if (!f.date_formation) { showToast(`الدورة ${n}: يرجى إدخال تاريخ التكوين`, 'error');    return false; }
    if (f.date_fin && f.date_fin < f.date_formation) { showToast(`الدورة ${n}: تاريخ النهاية يسبق تاريخ البداية`, 'error'); return false; }
    if (!f.lieu_formation) { showToast(`الدورة ${n}: يرجى اختيار المكان`, 'error');           return false; }
  }
  return p;
}

// ── حفظ المسودة ──────────────────────────────────────────────────────────────
async function sauvegarder() {
  const p = validate(); if (!p) return;
  const btn = document.getElementById('btnSauvegarder');
  btn.disabled = true; btn.textContent = '⏳ جاري الحفظ...';
  try {
    const url = savedLettreId ? `/lettre/${savedLettreId}/mettre-a-jour` : '/lettre/enregistrer';
    const res = await fetch(url, {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(p)});
    const d = await res.json();
    if (d.succes) {
      if (d.lettre_id) savedLettreId = d.lettre_id;
      draftSaved();
      showToast('تم حفظ المسودة بنجاح ✓');
      document.getElementById('btnConfirmer').style.display = 'inline-flex';
    } else {
      showToast(d.erreur || 'خطأ في التسجيل', 'error');
    }
  } catch(e) { showToast('خطأ: '+e.message,'error'); }
  finally { btn.disabled=false; btn.innerHTML='💾 حفظ المسودة'; }
}

// ── Modal ─────────────────────────────────────────────────────────────────────
function ouvrirModal() {
  if (!savedLettreId) { showToast('يرجى حفظ المسودة أولاً', 'error'); return; }
  const p = payload();
  document.getElementById('recap-type').textContent = p.type === 'interne' ? 'داخلية' : 'خارجية';
  document.getElementById('recap-mois').textContent = `${p.mois} ${p.annee}`;
  document.getElementById('recap-nb').textContent   = `${p.formations.length} دورات تكوينية`;
  const dim = p.formations.filter(f => estDimanche(f.date_formation));
  const bandeau = document.getElementById('recap-dimanche');
  if (dim.length) {
    bandeau.innerHTML = '⚠️ <strong>تنبيه — يوم أحد:</strong><br>'
      + dim.map(f => `• ${f.titre || 'دورة'} — ${f.date_formation}`).join('<br>')
      + '<br>يمكنك التّأكيد أو الرّجوع لتحيين التّاريخ.';
    bandeau.style.display = 'block';
  } else {
    bandeau.style.display = 'none';
  }
  document.getElementById('modalConfirm').style.display = 'flex';
}

function fermerModal() {
  document.getElementById('modalConfirm').style.display = 'none';
}

async function confirmer() {
  fermerModal();
  const p = validate(); if (!p) return;
  try {
    // Save latest changes first
    const saveUrl = savedLettreId ? `/lettre/${savedLettreId}/mettre-a-jour` : '/lettre/enregistrer';
    const saveRes = await fetch(saveUrl, {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(p)});
    const saved = await saveRes.json();
    if (!saved.succes) { showToast(saved.erreur || 'خطأ في الحفظ', 'error'); return; }
    if (saved.lettre_id) savedLettreId = saved.lettre_id;

    // Lock the letter
    const valRes = await fetch(`/lettre/${savedLettreId}/valider`, {
      method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({type: p.type})
    });
    const val = await valRes.json();
    if (val.succes) {
      showToast('✅ تم تأكيد البرنامج وإغلاقه بنجاح');
      lockUI(val.ref);
    } else {
      showToast(val.erreur || 'خطأ في التأكيد', 'error');
    }
  } catch(e) { showToast('خطأ: '+e.message,'error'); }
}

function lockUI(ref) {
  // Le programme est confirmé : plus de brouillon à protéger
  _locked = true;
  draftSaved();
  // Disable all interactive elements
  document.querySelectorAll('#formLettre input, #formLettre select').forEach(el => {
    el.disabled = true;
  });
  document.querySelectorAll('#tbody .btn-del').forEach(btn => btn.style.display = 'none');
  document.querySelector('.card-title-flex .btn-add')?.setAttribute('disabled','true');
  document.querySelector('.card-title-flex .btn-add')?.setAttribute('style','display:none');
  // Hide actions bar
  document.getElementById('actionsBar').style.display = 'none';
  // Show PDF bar
  const pdfBar = document.getElementById('pdfBar');
  pdfBar.style.display = 'flex';
  if (ref) document.getElementById('refBadge').textContent = ref;
  // Badge on step 1 (معلومات المراسلة)
  const step1Badge = document.createElement('span');
  step1Badge.style.cssText = 'display:inline-flex;align-items:center;gap:.3rem;background:#dbeafe;'
    + 'color:#1e40af;border:1px solid #93c5fd;border-radius:20px;padding:.15rem .7rem;'
    + 'font-size:.8rem;font-weight:700;margin-right:.6rem;vertical-align:middle;';
  step1Badge.textContent = '🔒 مسجَّلة في المنظومة ✓';
  const step1Title = document.querySelector('#formLettre .card .card-title');
  if (step1Title && !step1Title.querySelector('.step1-lock-badge')) {
    step1Badge.className = 'step1-lock-badge';
    step1Title.appendChild(step1Badge);
  }
  // Show Step 2 + Step 3 + Step 4 (Step 5 appears only after bataqa confirmed)
  document.getElementById('step2Section').style.display = '';
  document.getElementById('step3Section').style.display = '';
  document.getElementById('step4Section').style.display = '';
  document.getElementById('step5Section').style.display = '';
  document.getElementById('step6Section').style.display = '';
  initStep2();
  chargerFormations();
}

function genererPDF() {
  if (!savedLettreId) { showToast('يجب تأكيد البرنامج أولاً','error'); return; }
  window.open(`/lettre/${savedLettreId}/generer`, '_blank');
  showToast('تم فتح المراسلة (PDF) ✓');
}

// ── Step 2 : destinations multiples ──────────────────────────────────────────
let _destCount = 0;
let _step2Inited = false;


function initStep2() {
  if (_step2Inited) return;
  _step2Inited = true;
  ajouterJiha('admin');
  chargerDR();
}

// ما رُسِّم فعلا : la source de vérité, c'est le سجلّ. On l'affiche à part des
// lignes de saisie pour que « retirer » veuille dire « فسخ », pas « effacer ».
async function chargerDR() {
  if (!savedLettreId) return;
  let liste = [];
  try {
    const d = await (await fetch(`/lettre/${savedLettreId}/dr`)).json();
    liste = d.dr_lettres || [];
  } catch (e) { return; }
  const wrap = document.getElementById('drIssuedWrap');
  const box  = document.getElementById('drIssued');
  if (!wrap || !box) return;
  if (!liste.length) { wrap.style.display = 'none'; box.innerHTML = ''; return; }
  wrap.style.display = '';
  box.innerHTML = liste.map(d => `
    <div style="display:flex;align-items:center;gap:.6rem;flex-wrap:wrap;
                background:var(--bg);border:1px solid var(--border);border-radius:7px;
                padding:.4rem .7rem;">
      <span style="flex:1;min-width:150px;font-size:.88rem;">${esc((d.destination || '—'))}</span>
      <span dir="ltr" style="font-weight:700;font-size:.85rem;">${esc(d.ref_complet)}</span>
      <span class="badge ${d.type === 'externe' ? 'badge-green' : 'badge-blue'}"
            style="font-size:.78rem;">${d.type === 'externe' ? 'خارجية' : 'داخلية'}</span>
      <button type="button" class="btn" title="فسخ وإرجاع العدد"
              style="background:#ef4444;color:#fff;padding:.25rem .6rem;font-size:.8rem;"
              onclick="fsakhDR(${d.id}, '${esc((d.destination || '').replace(/'/g, ' '))}')">🗑 فسخ</button>
    </div>`).join('');
}

function fsakhDR(drId, dest) {
  showConfirmModal(
    `فسخ مراسلة المدير الجهوي الموجَّهة إلى «${dest || '—'}»؟\n\n`
    + 'يعود عددها إلى الرصيد فيأخذه أوّل طالب بعده.',
    async () => {
      try {
        const res = await fetch(`/lettre/${savedLettreId}/dr/${drId}/annuler`,
                                { method: 'POST' });
        const d = await res.json();
        if (d.succes) { showToast('✅ تمّ فسخ المراسلة وإرجاع عددها'); chargerDR(); }
        else { showAlertModal(d.erreur || 'تعذّر الفسخ.'); }
      } catch (e) { showAlertModal('خطأ: ' + e.message); }
    }
  );
}

function _optionsFor(cat) {
  const list = cat === 'garde' ? JIHAT_GARDE : JIHAT_ADMIN;
  return (list || []).map(nm =>
    `<option value="${String(nm).replace(/"/g, '&quot;')}">${esc(nm)}</option>`).join('');
}

function ajouterJiha(cat) {
  _destCount++;
  const n = _destCount;
  const container = document.getElementById(cat === 'garde' ? 'gardeContainer' : 'adminContainer');
  const ph = cat === 'garde' ? 'اسم وحدة الحرس...' : 'اسم الإدارة الجهوية...';
  const div = document.createElement('div');
  div.id = `dest_row_${n}`;
  div.style.cssText = 'display:flex; gap:.5rem; align-items:center; flex-wrap:wrap;';
  div.innerHTML = `
    <select id="dest_sel_${n}" onchange="onDestSel(${n})"
            style="flex:1; min-width:200px; padding:.42rem .6rem; border-radius:7px;
                   border:1.5px solid var(--border); background:var(--card-bg);
                   color:var(--text); font-size:.88rem; text-align:right; direction:rtl; cursor:pointer;">
      <option value="">— اختر —</option>
      ${_optionsFor(cat)}
      <option value="__manuel__">✏️ كتابة يدوية…</option>
    </select>
    <input type="text" id="dest_inp_${n}" placeholder="${ph}"
           style="display:none; flex:1; min-width:180px; padding:.42rem .75rem; border-radius:7px;
                  border:1.5px solid var(--border); background:var(--card-bg);
                  color:var(--text); font-size:.88rem; text-align:right; direction:rtl;">
    <select id="dest_type_${n}" title="نوع المراسلة"
            style="padding:.42rem .55rem; border-radius:7px; border:1.5px solid var(--border);
                   background:var(--card-bg); color:var(--text); font-size:.85rem;
                   text-align:right; direction:rtl; cursor:pointer;">
      <option value="interne">مراسلة داخلية</option>
      <option value="externe" selected>مراسلة خارجية</option>
    </select>
    <button type="button" class="btn" style="background:#f59e0b;color:#fff;white-space:nowrap;padding:.4rem .85rem;font-size:.85rem;"
            onclick="genererPDFDirecteur(${n})">📄 إنشاء المراسلة</button>
    <button type="button" class="btn-del" title="حذف" onclick="document.getElementById('dest_row_${n}').remove()">🗑</button>
  `;
  container.appendChild(div);
}

function onDestSel(n) {
  const sel = document.getElementById(`dest_sel_${n}`);
  const inp = document.getElementById(`dest_inp_${n}`);
  if (!sel || !inp) return;
  if (sel.value === '__manuel__') { inp.style.display = ''; inp.focus(); }
  else { inp.style.display = 'none'; }
}

function resolveDest(n) {
  const sel = document.getElementById(`dest_sel_${n}`);
  if (sel && sel.value === '__manuel__') {
    return (document.getElementById(`dest_inp_${n}`)?.value || '').trim();
  }
  return (sel?.value || '').trim();
}

async function genererPDFDirecteur(n) {
  if (!savedLettreId) { showToast('يجب تأكيد البرنامج أولاً','error'); return; }
  const dest = resolveDest(n);
  if (!dest) { showToast('يرجى اختيار الجهة أو كتابتها','error'); return; }
  const typeMr = document.getElementById(`dest_type_${n}`)?.value || 'interne';
  // On tire d'abord le عدد par l'API (geste tracé, réversible par فسخ), puis on
  // ouvre le PDF — qui réutilise ce même عدد sans en consommer un autre.
  try {
    const res = await fetch(`/lettre/${savedLettreId}/dr/attribuer`, {
      method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({ destination: dest, type_mr: typeMr })
    });
    const d = await res.json();
    if (!d.succes) { showToast(d.erreur || 'تعذّر ترقيم المراسلة', 'error'); return; }
    window.open(`/lettre/${savedLettreId}/generer-directeur-regional`
                + `?destination=${encodeURIComponent(dest)}`
                + `&type_mr=${encodeURIComponent(typeMr)}`, '_blank');
    showToast(d.deja ? 'إعادة طبع بنفس العدد ✓' : `تمّ سحب العدد ${d.ref} ✓`);
    // La ligne de saisie a fait son office : on la remet à zéro, et la مراسلة
    // apparaît désormais dans « ما رُسِّم » où elle peut être fsakhée proprement.
    const sel = document.getElementById(`dest_sel_${n}`);
    if (sel) sel.value = '';
    const inp = document.getElementById(`dest_inp_${n}`);
    if (inp) { inp.value = ''; inp.style.display = 'none'; }
    chargerDR();
  } catch (e) { showToast('خطأ: ' + e.message, 'error'); }
}

