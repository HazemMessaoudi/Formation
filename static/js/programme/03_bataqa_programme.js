/* ═══ نظام إدارة التكوين — صفحة إعداد برنامج التكوين ═══
   Étapes 4 et 5 : البطاقة البيداغوجية et برنامج الدّورة.
   v1.7 : extrait tel quel de templates/nouvelle_lettre.html (aucun
   changement de comportement). Les données du serveur sont fournies
   par le petit script en ligne de la page (constantes *_INIT, PAGE).
   Les fichiers se chargent dans l'ordre 01 → 06. */

// ── Step 4 : البطاقة البيداغوجية ──────────────────────────────────────────────

function afficherBataqaListe(formations) {
  const container = document.getElementById('bataqaList');
  if (!container) return;
  if (!formations.length) {
    container.innerHTML = '<p style="color:var(--text-muted)">لا توجد دورات.</p>';
    return;
  }
  container.innerHTML = formations.map(f => `
    <div class="card" style="margin-bottom:1rem; border:1px solid var(--border);" id="bcard_${f.id}">
      <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:.5rem;">
        <div style="font-weight:700; font-size:1rem;">${esc(f.titre || '—')}</div>
        <div style="color:var(--text-muted); font-size:.88rem;">
          ${datesDorra(f)} ${f.periode ? '('+esc(f.periode)+')' : ''} — ${esc(f.lieu_formation || '')}
        </div>
        <button type="button" class="btn" style="padding:.4rem .9rem; font-size:.88rem; background:#7c3aed; color:#fff;"
                onclick="toggleBataqaPanel(${f.id})">
          🗂️ البطاقة البيداغوجية
        </button>
      </div>
      <div id="bpanel_${f.id}" style="display:none; margin-top:1rem;">
        <!-- Info fixe -->
        <div style="display:grid; grid-template-columns:repeat(auto-fit,minmax(200px,1fr)); gap:.6rem; margin-bottom:1rem;
                    background:var(--bg); border-radius:8px; padding:.7rem 1rem; font-size:.9rem;">
          <div><span style="color:var(--text-muted)">عنوان الدورة:</span>
               <strong id="binfo_titre_${f.id}">${esc(f.titre||'—')}</strong></div>
          <div><span style="color:var(--text-muted)">نوع التكوين:</span>
               <strong id="binfo_type_${f.id}">—</strong></div>
          <div><span style="color:var(--text-muted)">تاريخ الدورة:</span>
               <strong>${f.date_formation ? datesDorra(f) : '—'}</strong></div>
          <div><span style="color:var(--text-muted)">عدد المشاركين:</span>
               <strong id="binfo_nb_${f.id}">—</strong></div>
          <div><span style="color:var(--text-muted)">مكان التكوين:</span>
               <strong id="binfo_lieu_${f.id}">—</strong></div>
        </div>
        <!-- Champs éditables -->
        <div style="display:grid; gap:.7rem;">
          ${_bataqa_field(f.id,'mustahdafun','المستهدفون بالتكوين',2)}
          ${_bataqa_field(f.id,'services','المصالح المعنية بالمشاركة',3)}
          ${_bataqa_field(f.id,'mahawer','محاور الدورة',4)}
          ${_bataqa_field(f.id,'objectifs','أهداف الدورة',4)}
          <div style="display:grid; grid-template-columns:1fr 1fr; gap:.7rem;">
            ${_bataqa_field(f.id,'methodes_pedagogiques','الطرق البيداغوجية',3)}
            ${_bataqa_field(f.id,'moyens_pedagogiques','المعينات البيداغوجية',3)}
          </div>
          <div style="display:grid; grid-template-columns:1fr 1fr; gap:.7rem;">
            ${_bataqa_field(f.id,'preparation_materielle','الإعداد المادي',3)}
            ${_bataqa_field(f.id,'equipements','التجهيزات والمعدات',3)}
          </div>
        </div>
        <!-- Actions -->
        <div style="display:flex; gap:.8rem; flex-wrap:wrap; align-items:center; margin-top:1rem;">
          <button type="button" class="btn" style="background:#7c3aed;color:#fff;"
                  onclick="confirmerBataqa(${f.id})">✅ تأكيد البطاقة البيداغوجية</button>
          <button type="button" class="btn btn-generate" id="btnPdfBataqa_${f.id}" style="display:none; background:#059669; color:#fff;"
                  onclick="genererPDFBataqa(${f.id})">📄 طباعة البطاقة (PDF)</button>
        </div>
        <div id="bstatus_${f.id}" style="font-size:.85rem; color:var(--text-muted); margin-top:.4rem;"></div>
      </div>
    </div>
  `).join('');

  // Load data for each formation
  formations.forEach(f => chargerBataqa(f.id));
}

function _bataqa_field(fid, key, label, rows) {
  return `<div>
    <label style="display:block; font-size:.85rem; color:var(--text-muted); margin-bottom:.2rem;">${label}</label>
    <textarea id="bf_${fid}_${key}" rows="${rows}" class="bf-auto" oninput="_ajusterHauteur(this)"
              style="width:100%;border:1px solid var(--border);border-radius:6px;padding:.5rem .7rem;
                     font-family:inherit;font-size:.9rem;resize:vertical;background:var(--card-bg);
                     color:var(--text);direction:rtl;overflow-y:hidden;"></textarea>
  </div>`;
}

// v1.6.1 : la zone s'agrandit avec son contenu (jamais plus petite que `rows`).
function _ajusterHauteur(el) {
  if (!el || !el.offsetParent) return;          // panneau fermé : rien à mesurer
  el.style.height = 'auto';
  el.style.height = (el.scrollHeight + 2) + 'px';
}
function _ajusterBataqa(fid) {
  document.querySelectorAll(`#bpanel_${fid} textarea.bf-auto`).forEach(_ajusterHauteur);
}

let _bpanelOpen = {};
function toggleBataqaPanel(fid) {
  const panel = document.getElementById(`bpanel_${fid}`);
  if (!panel) return;
  _bpanelOpen[fid] = !_bpanelOpen[fid];
  panel.style.display = _bpanelOpen[fid] ? '' : 'none';
  // Rechargement à CHAQUE ouverture : le nombre de participants et les
  // المصالح ont pu changer depuis le premier affichage de la page.
  if (_bpanelOpen[fid]) chargerBataqa(fid);
}

async function chargerBataqa(fid) {
  if (!savedLettreId) return;
  try {
    const res = await fetch(`/lettre/${savedLettreId}/formations/${fid}/bataqa/data`);
    if (!res.ok) return;
    const d = await res.json();
    // Fill fixed info
    const setTxt = (id, v) => { const el=document.getElementById(id); if(el) el.textContent = v||'—'; };
    setTxt(`binfo_type_${fid}`,  d.type_formation);
    // Participant count: always show the actual number (0 included), never a dash
    const nbEl = document.getElementById(`binfo_nb_${fid}`);
    if (nbEl) nbEl.textContent = (d.nb_participants != null ? d.nb_participants : 0);
    setTxt(`binfo_lieu_${fid}`,  d.lieu_formation);
    // Fill editable fields
    const fields = ['mustahdafun','services','mahawer','objectifs',
                    'methodes_pedagogiques','moyens_pedagogiques',
                    'preparation_materielle','equipements'];
    fields.forEach(k => {
      const el = document.getElementById(`bf_${fid}_${k}`);
      if (el) { el.value = d[k] || ''; el.dataset.charge = el.value; }
    });
    _ajusterBataqa(fid);
    // If already confirmed, show PDF button and reveal Step 5
    if (d.confirmed) {
      document.getElementById(`btnPdfBataqa_${fid}`).style.display = '';
      const st = document.getElementById(`bstatus_${fid}`);
      if (st) st.textContent = `✓ تم التأكيد بتاريخ ${d.confirmed_at||''}`;
      document.getElementById('step5Section').style.display = '';
    }
  } catch(e) { console.error('chargerBataqa:', e); }
}

// v1.7.1 : après une modification de la قائمة المشاركين, l'البطاقة affichée
// suit : nombre de participants, et المستهدفون / المصالح المعنيّة tant que
// l'agent ne les a pas retouchés dans la page (valeur = valeur chargée).
async function rafraichirBataqaDerives(fid) {
  if (!savedLettreId) return;
  try {
    const res = await fetch(`/lettre/${savedLettreId}/formations/${fid}/bataqa/data`);
    if (!res.ok) return;
    const d = await res.json();
    const nbEl = document.getElementById(`binfo_nb_${fid}`);
    if (nbEl) nbEl.textContent = (d.nb_participants != null ? d.nb_participants : 0);
    ['mustahdafun', 'services'].forEach(k => {
      const el = document.getElementById(`bf_${fid}_${k}`);
      if (el && (el.dataset.charge === undefined || el.value === el.dataset.charge)) {
        el.value = d[k] || ''; el.dataset.charge = el.value;
      }
    });
    _ajusterBataqa(fid);
  } catch (e) { console.error('rafraichirBataqaDerives:', e); }
}

async function confirmerBataqa(fid) {
  if (!savedLettreId) { showToast('يجب تأكيد البرنامج أولاً','error'); return; }

  // Collect editable fields
  const fields = ['mustahdafun','services','mahawer','objectifs',
                  'methodes_pedagogiques','moyens_pedagogiques',
                  'preparation_materielle','equipements'];
  const data = {};
  fields.forEach(k => {
    const el = document.getElementById(`bf_${fid}_${k}`);
    data[k] = el ? el.value.trim() : '';
  });

  try {
    const res = await fetch(`/lettre/${savedLettreId}/formations/${fid}/bataqa/data`, {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(data)
    });
    const d = await res.json();
    if (d.succes) {
      showToast('✅ تم تأكيد البطاقة البيداغوجية بنجاح');
      document.getElementById(`btnPdfBataqa_${fid}`).style.display = '';
      const st = document.getElementById(`bstatus_${fid}`);
      if (st) st.textContent = `✓ تم التأكيد — ${d.nb_participants} مشارك(ين)`;
      document.getElementById('step5Section').style.display = '';
      rafraichirEtats();
    } else {
      showToast(d.erreur || 'خطأ في الحفظ', 'error');
    }
  } catch(e) { showToast('خطأ: '+e.message, 'error'); }
}

function genererPDFBataqa(fid) {
  if (!savedLettreId) return;
  window.open(`/lettre/${savedLettreId}/formations/${fid}/bataqa/pdf`, '_blank');
  showToast('تم فتح البطاقة البيداغوجية (PDF) ✓');
}

// ── Step 5 : برنامج الدّورة التّكوينيّة ──────────────────────────────────────

function _formatArabicDate(isoDate, moment) {
  if (!isoDate) return '';
  const JOURS = ['الأحد','الاثنين','الثلاثاء','الأربعاء','الخميس','الجمعة','السبت'];
  const MOIS  = ['جانفي','فيفري','مارس','أفريل','ماي','جوان',
                 'جويلية','أوت','سبتمبر','أكتوبر','نوفمبر','ديسمبر'];
  const d = new Date(isoDate + 'T12:00:00');
  return `يوم ${JOURS[d.getDay()]} ${d.getDate()} ${MOIS[d.getMonth()]} ${d.getFullYear()} (${moment||'صباحا'})`;
}

function afficherProgrammeListe(formations) {
  const container = document.getElementById('programmeList');
  if (!container) return;
  if (!formations.length) {
    container.innerHTML = '<p style="color:var(--text-muted)">لا توجد دورات.</p>';
    return;
  }
  container.innerHTML = formations.map(f => `
    <div class="card" style="margin-bottom:1rem; border:1px solid var(--border);" id="progcard_${f.id}">
      <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:.5rem;">
        <div style="font-weight:700; font-size:1rem;">${esc(f.titre || '—')}</div>
        <div style="color:var(--text-muted); font-size:.88rem;">
          ${datesDorra(f)} ${f.periode ? '('+esc(f.periode)+')' : ''} — ${esc(f.lieu_formation || '')}
        </div>
        <button type="button" class="btn" style="padding:.4rem .9rem; font-size:.88rem; background:#0369a1; color:#fff;"
                onclick="toggleProgrammePanel(${f.id})">
          📋 البرنامج
        </button>
      </div>
      <div id="progpanel_${f.id}" style="display:none; margin-top:1rem;">
      ${_estMulti(f) ? _panneauJours(f) : `
        <!-- Table -->
        <div style="overflow-x:auto;">
          <table style="width:100%; border-collapse:collapse; font-size:.9rem; direction:rtl;"
                 id="progtable_${f.id}">
            <thead>
              <tr style="background:#0369a1; color:#fff;">
                <th style="padding:.5rem .7rem; border:1px solid #ccc; text-align:center; width:24%;">التّوقيت</th>
                <th style="padding:.5rem .7rem; border:1px solid #ccc; text-align:center; width:40%;">بيان النشّاط</th>
                <th style="padding:.5rem .7rem; border:1px solid #ccc; text-align:center; width:24%;">المتدخّلون</th>
                <th style="padding:.5rem .7rem; border:1px solid #ccc; text-align:center; width:12%;"></th>
              </tr>
            </thead>
            <tbody id="progtbody_${f.id}" data-periode="${esc(f.periode || '')}"></tbody>
          </table>
        </div>
        <!-- Actions : إضافة صف (right) | spacer | تأكيد البرنامج (far left) -->
        <div style="display:flex; gap:.8rem; flex-wrap:wrap; align-items:center; margin-top:1rem; direction:rtl;">
          <button type="button" class="btn" style="background:#0369a1;color:#fff;font-size:.85rem;"
                  onclick="ajouterLigneProgramme(${f.id},'row')">➕ إضافة صف</button>
          <button type="button" class="btn btn-generate" id="btnPdfProg_${f.id}" style="display:none; background:#059669; color:#fff;"
                  onclick="genererPDFProgramme(${f.id})">📄 طباعة البرنامج (PDF)</button>
          <span style="flex:1;"></span>
          <button type="button" class="btn" style="background:#0369a1;color:#fff;"
                  onclick="confirmerProgramme(${f.id})">✅ تأكيد البرنامج</button>
        </div>
        <div id="progstatus_${f.id}" style="font-size:.85rem; color:var(--text-muted); margin-top:.4rem;"></div>
      `}
      </div>
    </div>
  `).join('');

  afficherMemoListe(formations);
  _chargerSuggestionsProgramme();
  formations.forEach(f => _estMulti(f) ? chargerProgrammeJours(f.id) : chargerProgramme(f.id));
}

let _ppanelOpen = {};
function toggleProgrammePanel(fid) {
  const panel = document.getElementById(`progpanel_${fid}`);
  if (!panel) return;
  _ppanelOpen[fid] = !_ppanelOpen[fid];
  panel.style.display = _ppanelOpen[fid] ? '' : 'none';
}

function _derniereLigneProgVide(fid) {
  const tbody = document.getElementById(`progtbody_${fid}`);
  if (!tbody || !tbody.lastElementChild) return false;
  const tr = tbody.lastElementChild;
  const v = sel => { const el = tr.querySelector(sel); return el ? el.value.trim() : ''; };
  return !(v('.prow-time-debut') && v('.prow-time-fin')
           && v('.prow-activity') && v('.prow-participants'));
}

function ajouterLigneProgramme(fid, type, _rechargement) {
  const tbody = document.getElementById(`progtbody_${fid}`);
  if (!tbody) return;
  // Même règle qu'aux participants : pas de nouveau صف tant que le précédent
  // n'est pas complet (التوقيت من/إلى + بيان النشاط + المتدخّلون).
  if (!_rechargement && _derniereLigneProgVide(fid)) {
    showToast('يرجى تعمير الصف الحالي بالكامل قبل إضافة صف جديد', 'error');
    const el = tbody.lastElementChild.querySelector('.prow-time-debut');
    if (el) el.focus();
    return;
  }
  _creerListeHeures();
  const tr = document.createElement('tr');
  tr.dataset.type = 'row';
  tr.innerHTML = `
    <td style="padding:.3rem .5rem; border:1px solid #ccc;">
      <div style="display:flex;align-items:center;gap:.25rem;justify-content:center;flex-wrap:wrap;">
        <span style="font-size:.82rem;color:var(--text-muted);">من</span>
        <input type="text" class="prow-time-debut prow-heure" list="dl_heures" inputmode="numeric"
               maxlength="5" placeholder="--:--" dir="ltr" autocomplete="off"
               title="اكتب التوقيت مباشرة (مثال: 0830 أو 8:30) أو اختره من القائمة"
               oninput="_prowOnTimeInput(this)" onchange="_prowOnTimeCommit(this)"
               style="border:1px solid var(--border);border-radius:5px;background:transparent;
                      font-family:inherit;font-size:.86rem;padding:.15rem .3rem;width:5.6em;
                      text-align:center;"/>
        <span style="font-size:.82rem;color:var(--text-muted);">إلى</span>
        <input type="text" class="prow-time-fin prow-heure" list="dl_heures" inputmode="numeric"
               maxlength="5" placeholder="--:--" dir="ltr" autocomplete="off"
               title="اكتب التوقيت مباشرة (مثال: 0830 أو 8:30) أو اختره من القائمة"
               oninput="_prowOnTimeInput(this)" onchange="_prowOnTimeCommit(this)"
               style="border:1px solid var(--border);border-radius:5px;background:transparent;
                      font-family:inherit;font-size:.86rem;padding:.15rem .3rem;width:5.6em;
                      text-align:center;"/>
      </div>
      <div class="prow-time-warn" style="display:none;color:#b91c1c;font-size:.75rem;
           text-align:center;margin-top:.2rem;">⚠ الفترة أقصر من 15 دقيقة</div>
    </td>
    <td style="padding:.3rem .5rem; border:1px solid #ccc;">
      <input type="text" class="prow-activity" list="dl_activites" dir="rtl" autocomplete="off"
             placeholder="بيان النشاط... (اكتب أو اختر من المقترحات)"
             title="تُحفظ كلّ عبارة مؤكَّدة وتُقترح لاحقًا"
             style="width:100%;border:1px solid var(--border);border-radius:5px;background:transparent;
                    font-family:inherit;font-size:.9rem;padding:.3rem .4rem;"/>
    </td>
    <td style="padding:.3rem .5rem; border:1px solid #ccc;">
      <div class="prow-interv">
        <div class="prow-chips"></div>
        <input type="text" class="prow-interv-saisie" list="dl_intervenants" dir="rtl" autocomplete="off"
               placeholder="➕ اختر متدخّلًا من القائمة"
               title="يمكن اختيار أكثر من متدخّل للفقرة الواحدة"
               onchange="_intervAjouter(this)"
               onkeydown="if(event.key==='Enter'){event.preventDefault();_intervAjouter(this);}"
               style="width:100%;border:1px solid var(--border);border-radius:5px;background:transparent;
                      font-family:inherit;font-size:.86rem;padding:.25rem .4rem;"/>
        <input type="hidden" class="prow-participants" value=""/>
      </div>
    </td>
    <td style="border:1px solid #ccc; text-align:center; padding:.2rem;">
      <button type="button" onclick="supprimerLigneProgramme(this)"
              style="background:none;border:none;cursor:pointer;color:#dc2626;font-size:1rem;">✕</button>
    </td>`;
  tbody.appendChild(tr);
  // تواصل التوقيت: يبدأ الصف الجديد آليًّا من نهاية الصف السابق (أو 08:00 للأوّل)
  _prowSyncContinuite(tbody);
}

// ── v1.7.1 : suggestions (بيان النشاط) et متدخّلون multiples ─────────────────
// Les متدخّلون d'une فقرة sont des « pastilles » choisies dans une liste
// (fiches + متدخّلون déjà utilisés) ; leur texte, joint par « ، », est gardé
// dans le champ caché .prow-participants — c'est lui qui est enregistré et
// imprimé, exactement comme l'ancien texte libre.
const INTERV_SEP = '، ';
let _suggProgChargees = false;

function _remplirDatalist(id, valeurs) {
  let dl = document.getElementById(id);
  if (!dl) { dl = document.createElement('datalist'); dl.id = id; document.body.appendChild(dl); }
  dl.innerHTML = '';
  (valeurs || []).forEach(v => { const o = document.createElement('option'); o.value = v; dl.appendChild(o); });
}

async function _chargerSuggestionsProgramme(forcer) {
  if (_suggProgChargees && !forcer) return;
  _suggProgChargees = true;
  _remplirDatalist('dl_activites', []);
  _remplirDatalist('dl_intervenants', []);
  try {
    const r = await fetch('/api/programme/suggestions', {headers: {'Accept': 'application/json'}});
    if (!r.ok) return;
    const d = await r.json();
    _remplirDatalist('dl_activites', d.activites || []);
    _remplirDatalist('dl_intervenants', d.intervenants || []);
  } catch (e) { console.error('suggestions programme :', e); }
}

function _intervListe(tr) {
  const h = tr.querySelector('.prow-participants');
  return (h && h.value ? h.value.split(/[،,;\/\n]+/) : []).map(x => x.trim()).filter(Boolean);
}

function _intervRendre(tr) {
  const zone = tr.querySelector('.prow-chips');
  if (!zone) return;
  zone.innerHTML = _intervListe(tr).map((nom, i) =>
    `<span class="interv-chip">${esc(nom)}<button type="button" title="حذف"
       onclick="_intervRetirer(this, ${i})">×</button></span>`).join('');
}

function _intervEcrire(tr, liste) {
  const h = tr.querySelector('.prow-participants');
  if (h) h.value = liste.join(INTERV_SEP);
  _intervRendre(tr);
}

function _intervAjouter(inp) {
  const tr = inp.closest('tr');
  const nom = (inp.value || '').replace(/\s+/g, ' ').trim();
  inp.value = '';
  if (!tr || !nom) return;
  const liste = _intervListe(tr);
  if (liste.includes(nom)) { showToast('هذا المتدخّل مضاف مسبقًا لهذه الفقرة', 'warning'); return; }
  liste.push(nom);
  _intervEcrire(tr, liste);
}

function _intervRetirer(btn, i) {
  const tr = btn.closest('tr');
  const liste = _intervListe(tr);
  liste.splice(i, 1);
  _intervEcrire(tr, liste);
}

function supprimerLigneProgramme(btn) {
  const tbody = btn.closest('tbody');
  btn.closest('tr').remove();
  if (tbody) _prowSyncContinuite(tbody);
}

function _formaterPlage(debut, fin) {
  if (debut && fin) return `من ${debut} إلى ${fin}`;
  if (debut)        return `انطلاقا من ${debut}`;
  return '';
}

// Durée d'une plage « HH:MM » → « HH:MM » en minutes, ou null si incalculable.
function _dureeMinutes(debut, fin) {
  if (!debut || !fin) return null;
  const md = debut.split(':'), mf = fin.split(':');
  if (md.length < 2 || mf.length < 2) return null;
  const a = (+md[0]) * 60 + (+md[1]);
  const b = (+mf[0]) * 60 + (+mf[1]);
  if (isNaN(a) || isNaN(b)) return null;
  return b - a;
}

// Bornes de la journée de formation.
const PROG_H_MIN = '08:00';
const PROG_H_MAX = '17:00';
// Une دورة de la فترة المسائيّة commence à 13:30 : le برنامج part de là,
// et aucune فقرة ne peut commencer avant.
const PROG_H_APRES_MIDI = '13:30';

function _debutJournee(tbody) {
  return (tbody && tbody.dataset.periode === 'مساءا') ? PROG_H_APRES_MIDI : PROG_H_MIN;
}

// v1.6.1 — التوقيت : saisie directe au clavier OU choix dans la liste.
// La liste (datalist) propose les quarts d'heure 08:00 → 17:00 ; au clavier
// toute minute est acceptée et la saisie est normalisée en « HH:MM » :
// « 830 », « 0830 », « 8:30 », « 8h30 », « 8.30 », « ٨:٣٠ » → « 08:30 ».
function _creerListeHeures() {
  if (document.getElementById('dl_heures')) return;
  const dl = document.createElement('datalist');
  dl.id = 'dl_heures';
  for (let m = 8 * 60; m <= 17 * 60; m += 15) {
    const o = document.createElement('option');
    o.value = String(Math.floor(m / 60)).padStart(2, '0') + ':' + String(m % 60).padStart(2, '0');
    dl.appendChild(o);
  }
  document.body.appendChild(dl);
}

const RE_HEURE = /^([01]\d|2[0-3]):[0-5]\d$/;

function _normaliserHeure(v) {
  v = String(v || '').trim()
        .replace(/[\u0660-\u0669]/g, d => String(d.charCodeAt(0) - 0x0660))
        .replace(/[\u06F0-\u06F9]/g, d => String(d.charCodeAt(0) - 0x06F0));
  if (!v) return '';
  let h, m;
  const sep = v.match(/^(\d{1,2})\s*[:hH.,;\-\s]\s*(\d{1,2})$/);
  if (sep) {
    h = sep[1];
    m = sep[2].length === 1 ? sep[2] + '0' : sep[2];     // « 8:3 » → 08:30
  } else if (/^\d{1,4}$/.test(v)) {
    if (v.length <= 2)      { h = v;             m = '00'; }  // « 9 » → 09:00
    else if (v.length === 3){ h = v.slice(0, 1); m = v.slice(1); }
    else                    { h = v.slice(0, 2); m = v.slice(2); }
  } else {
    return null;
  }
  const hh = +h, mm = +m;
  if (isNaN(hh) || isNaN(mm) || hh > 23 || mm > 59) return null;
  return String(hh).padStart(2, '0') + ':' + String(mm).padStart(2, '0');
}

// Pendant la frappe : on ne réagit qu'à une heure complète (sinon « 8: »
// déclencherait une fausse alerte « hors plage »).
function _prowOnTimeInput(el) {
  if (RE_HEURE.test(el.value.trim())) _prowOnTimeChange(el);
}

// À la sortie du champ (ou au choix dans la liste) : normalisation puis contrôle.
function _prowOnTimeCommit(el) {
  if (el.readOnly) return;
  const n = _normaliserHeure(el.value);
  if (n !== null) el.value = n;
  _prowOnTimeChange(el);
}

// À chaque frappe : on synchronise la continuité des صفوف puis on vérifie la ligne.
function _prowOnTimeChange(el) {
  const tr = el && el.closest('tr');
  const tbody = tr && tr.closest('tbody');
  if (tbody) _prowSyncContinuite(tbody);
  _prowVerifierDuree(el);
}

// Continuité des صفوف : chaque صف démarre exactement à la fin du صف précédent.
// Le début des lignes suivantes est donc verrouillé (lecture seule) et recopié
// automatiquement — impossible de saisir un début antérieur à la fin d'avant.
function _prowSyncContinuite(tbody) {
  if (!tbody) return;
  const rows = Array.from(tbody.querySelectorAll('tr'));
  let finPrec = '';
  rows.forEach((tr, i) => {
    const d = tr.querySelector('.prow-time-debut');
    const f = tr.querySelector('.prow-time-fin');
    if (!d || !f) return;
    if (i === 0) {
      d.readOnly = false;
      d.style.background = 'transparent';
      d.title = '';
      // أوّل صف: 08:00 صباحًا، أو 13:30 إن كانت الدّورة في الفترة المسائيّة
      const debutJour = _debutJournee(tbody);
      d.min = debutJour;
      f.min = debutJour;
      if (!d.value.trim() || (RE_HEURE.test(d.value.trim()) && d.value.trim() < debutJour)) d.value = debutJour;
    } else {
      d.readOnly = true;
      d.style.background = 'rgba(0,0,0,.06)';
      d.style.cursor = 'not-allowed';
      d.title = 'يبدأ آليًّا من نهاية الصف السابق';
      d.value = finPrec || '';
    }
    finPrec = f.value || '';
  });
}


// Avertissement immédiat à la saisie. Le توقيت est refusé dès la frappe si :
//   • une heure sort de la plage 08:00–17:00 ;
//   • la fin est antérieure ou égale au début ;
//   • la fقرة dure moins de 15 minutes.
// Retourne true si la ligne est valide (ou incomplète : rien à signaler).
function _prowVerifierDuree(el) {
  const tr = el.closest('tr');
  if (!tr) return true;
  const td = tr.querySelector('.prow-time-debut');
  const tf = tr.querySelector('.prow-time-fin');
  const warn = tr.querySelector('.prow-time-warn');
  const debut = td ? td.value.trim() : '';
  const fin   = tf ? tf.value.trim() : '';

  let invalide = false;
  let message  = '';

  // 0) Saisie au clavier illisible (« 25:00 », « 8h7x »…).
  if ((debut && !RE_HEURE.test(debut)) || (fin && !RE_HEURE.test(fin))) {
    invalide = true;
    message  = '⚠ صيغة التوقيت غير صحيحة (مثال: 08:30)';
  }

  // 1) Hors de la plage 08:00–17:00 (vérifié dès qu'une heure est saisie).
  const horsPlage = (h) => h && (h < PROG_H_MIN || h > PROG_H_MAX);
  if (!invalide && (horsPlage(debut) || horsPlage(fin))) {
    invalide = true;
    message  = '⚠ التوقيت يجب أن يكون بين 08:00 و17:00';
  }

  // 2) Ordre et durée (quand les deux heures sont présentes).
  if (!invalide && debut && fin) {
    const duree = _dureeMinutes(debut, fin);
    if (duree !== null && duree <= 0) {
      invalide = true;
      message  = '⚠ نهاية التوقيت يجب أن تكون بعد بدايته';
    } else if (duree !== null && duree < 15) {
      invalide = true;
      message  = '⚠ الفترة أقصر من 15 دقيقة';
    }
  }

  if (warn) {
    warn.textContent  = message;
    warn.style.display = invalide ? '' : 'none';
  }
  [td, tf].forEach(i => { if (i) i.style.borderColor = invalide ? '#b91c1c' : 'var(--border)'; });
  return !invalide;
}

function _collectProgrammeRows(fid) {
  const rows = [];
  document.querySelectorAll(`#progtbody_${fid} tr`).forEach(tr => {
    const p  = tr.querySelector('.prow-participants');
    const a  = tr.querySelector('.prow-activity');
    const td = tr.querySelector('.prow-time-debut');
    const tf = tr.querySelector('.prow-time-fin');
    const norm = el => { if (!el) return ''; const n = _normaliserHeure(el.value);
                         return n === null ? el.value.trim() : n; };
    const debut = norm(td);
    const fin   = norm(tf);
    rows.push({
      type: 'row',
      participants: p ? p.value.trim() : '',
      activity:     a ? a.value.trim() : '',
      time_debut:   debut,
      time_fin:     fin,
      time:         _formaterPlage(debut, fin)
    });
  });
  return rows;
}

async function chargerProgramme(fid) {
  if (!savedLettreId) return;
  try {
    const res = await fetch(`/lettre/${savedLettreId}/formations/${fid}/programme/data`);
    const tbody = document.getElementById(`progtbody_${fid}`);
    if (!tbody) return;
    tbody.innerHTML = '';
    if (!res.ok) { ajouterLigneProgramme(fid, 'row', true); return; }
    const d = await res.json();
    const rows = (d.rows || []).filter(r => (r.type || 'row') !== 'date_header');
    if (rows.length === 0) {
      ajouterLigneProgramme(fid, 'row', true);
    } else {
      rows.forEach(row => {
        ajouterLigneProgramme(fid, 'row', true);
        const tr = tbody.lastElementChild;
        const p  = tr.querySelector('.prow-participants');
        const a  = tr.querySelector('.prow-activity');
        const td = tr.querySelector('.prow-time-debut');
        const tf = tr.querySelector('.prow-time-fin');
        if (p) { p.value = row.participants || ''; _intervRendre(tr); }
        if (a) a.value = row.activity     || '';
        // Anciennes lignes : التوقيت était un texte libre — on en réextrait les
        // deux heures quand c'est possible, sinon les sélecteurs restent vides.
        let debut = row.time_debut || '';
        let fin   = row.time_fin   || '';
        if (!debut && row.time) {
          const m = String(row.time).match(/(\d{1,2}:\d{2})\D+(\d{1,2}:\d{2})/);
          if (m) { debut = m[1].padStart(5, '0'); fin = m[2].padStart(5, '0'); }
        }
        if (td) td.value = debut;
        if (tf) tf.value = fin;
        if (td) _prowVerifierDuree(td);
      });
      _prowSyncContinuite(tbody);  // تطبيع تواصل التوقيت بعد التحميل
    }
    if (d.confirmed) {
      document.getElementById(`btnPdfProg_${fid}`).style.display = '';
      const st = document.getElementById(`progstatus_${fid}`);
      if (st) st.textContent = `✓ تم التأكيد بتاريخ ${d.confirmed_at || ''}`;
      document.getElementById('step6Section').style.display = '';
      chargerEtatMemo(fid);
    }
  } catch(e) {
    console.error('chargerProgramme:', e);
    const tbody = document.getElementById(`progtbody_${fid}`);
    if (tbody && tbody.children.length === 0) ajouterLigneProgramme(fid, 'row', true);
  }
}

async function confirmerProgramme(fid) {
  _verifierProgramme(fid, complets => _envoyerProgramme(fid, complets));
}

// Contrôles d'un برنامج (ou d'UN jour d'une دورة متعدّدة الأيّام : `cle` =
// « fid_jN ») avant l'envoi ; `suite(complets)` est appelée si tout est juste.
function _verifierProgramme(fid, suite) {
  if (!savedLettreId) { showToast('يجب تأكيد البرنامج أولاً','error'); return; }
  const rows = _collectProgrammeRows(fid);
  if (!rows.length) { showToast('يرجى إضافة صف واحد على الأقل','error'); return; }
  // Un صف كامل = التوقيت + بيان النشاط + المتدخّلون. Les lignes à moitié
  // remplies ne partent pas à l'impression : le برنامج est un document officiel.
  const complets = rows.filter(r => r.time && r.activity && r.participants);
  if (!complets.length) {
    showToast('يجب تعمير صف واحد كامل على الأقل: التوقيت (من/إلى) وبيان النشاط والمتدخّلون','error');
    return;
  }
  const illisible = complets.find(r => !RE_HEURE.test(r.time_debut) || !RE_HEURE.test(r.time_fin));
  if (illisible) {
    showToast(`صيغة التوقيت غير صحيحة «${illisible.time_debut} – ${illisible.time_fin}». `
              + 'اكتب التوقيت على شكل 08:30 أو اختره من القائمة.', 'error');
    return;
  }
  // Toutes les heures doivent tenir dans la journée : 08:00–17:00, ou
  // 13:30–17:00 pour une دورة de la فترة المسائيّة.
  const hMin = _debutJournee(document.getElementById(`progtbody_${fid}`));
  const horsPlage = complets.find(r =>
    (r.time_debut && (r.time_debut < hMin || r.time_debut > PROG_H_MAX)) ||
    (r.time_fin   && (r.time_fin   < hMin || r.time_fin   > PROG_H_MAX)));
  if (horsPlage) {
    showToast(`التوقيت يجب أن يكون بين ${hMin} و${PROG_H_MAX}`
            + (hMin === PROG_H_APRES_MIDI ? ' (دورة في الفترة المسائيّة)' : '')
            + '. يرجى مراجعة البرنامج.', 'error');
    return;
  }
  // La fin doit suivre le début.
  const inverse = complets.find(r => {
    const d = _dureeMinutes(r.time_debut, r.time_fin);
    return d !== null && d <= 0;
  });
  if (inverse) {
    showToast(`الصف «من ${inverse.time_debut} إلى ${inverse.time_fin}»: `
              + 'نهاية التوقيت يجب أن تكون بعد بدايته.', 'error');
    return;
  }
  // Chaque plage complète (من/إلى) doit durer 15 min au moins avant l'envoi.
  const courte = complets.find(r => {
    const d = _dureeMinutes(r.time_debut, r.time_fin);
    return d !== null && d < 15;
  });
  if (courte) {
    showToast(`الفترة «من ${courte.time_debut} إلى ${courte.time_fin}» أقصر من 15 دقيقة. `
              + 'لكلّ فقرة 15 دقيقة على الأقلّ.', 'error');
    return;
  }
  const partiels = rows.length - complets.length;
  if (partiels > 0) {
    showConfirmModal(
      `يوجد ${partiels} صف(وف) غير مكتمل(ة) سيتمّ حذفها قبل التأكيد. هل تواصل؟`,
      () => suite(complets));
    return;
  }
  suite(complets);
}

async function _envoyerProgramme(fid, complets) {
  try {
    const res = await fetch(`/lettre/${savedLettreId}/formations/${fid}/programme/data`, {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({ rows: complets })
    });
    const d = await res.json();
    if (d.succes) {
      showToast('✅ تم تأكيد البرنامج بنجاح');
      _chargerSuggestionsProgramme(true);   // v1.7.1 : nouvelles عبارات proposées
      rafraichirEtats();
      document.getElementById(`btnPdfProg_${fid}`).style.display = '';
      const st = document.getElementById(`progstatus_${fid}`);
      if (st) st.textContent = `✓ تم التأكيد — ${complets.length} صف(وف)`;
      document.getElementById('step6Section').style.display = '';
      chargerEtatMemo(fid);
    } else {
      showToast(d.erreur || 'خطأ في الحفظ', 'error');
    }
  } catch(e) { showToast('خطأ: '+e.message, 'error'); }
}

function genererPDFProgramme(fid) {
  if (!savedLettreId) return;
  window.open(`/lettre/${savedLettreId}/formations/${fid}/programme/pdf`, '_blank');
  showToast('تم فتح برنامج الدورة (PDF) ✓');
}





// ══ V2 : برنامج دورة متعدّدة الأيّام — saisie et confirmation jour par jour ══
// Chaque jour a sa فترة (صباحا / مساءا) et son tableau. Le jour N ne s'ouvre
// qu'une fois le jour N-1 confirmé ; la confirmation du dernier jour achève
// l'étape 5 (le serveur recompose alors le برنامج complet). Les contrôles des
// صفوف sont ceux du برنامج d'un jour (_verifierProgramme), jour par jour.

const _JOURS_PROG = {};      // fid → {jours:[…], confirmed}
const _JOUR_EDITION = {};    // fid → numéro du jour rouvert pour modification
const ORDINAUX_JOURS = ['اليوم الأوّل','اليوم الثاني','اليوم الثالث','اليوم الرابع','اليوم الخامس','اليوم السادس'];
const JOURS_SEM = ['الأحد','الاثنين','الثلاثاء','الأربعاء','الخميس','الجمعة','السبت'];

function _estMulti(f) { return joursDorra(f.date_formation || '', f.date_fin || '').length > 1; }
function _libJour(n) { return ORDINAUX_JOURS[n - 1] || `اليوم ${n}`; }
function _dateJourTxt(iso) {
  const [y, m, j] = iso.split('-').map(Number);
  const d = new Date(y, m - 1, j);
  return `${JOURS_SEM[d.getDay()]} ${String(j).padStart(2,'0')}/${String(m).padStart(2,'0')}/${y}`;
}

function _panneauJours(f) {
  return `
    <div class="jours-progress" id="jprog_${f.id}"></div>
    <div id="jourscont_${f.id}"><p style="color:var(--text-muted)">جارٍ التحميل…</p></div>
    <div style="display:flex; gap:.8rem; flex-wrap:wrap; align-items:center; margin-top:.4rem;">
      <button type="button" class="btn btn-generate" id="btnPdfProg_${f.id}" style="display:none; background:#059669; color:#fff;"
              onclick="genererPDFProgramme(${f.id})">📄 طباعة البرنامج (PDF)</button>
    </div>
    <div id="progstatus_${f.id}" style="font-size:.85rem; color:var(--text-muted); margin-top:.4rem;"></div>`;
}

async function chargerProgrammeJours(fid) {
  if (!savedLettreId) return;
  try {
    const res = await fetch(`/lettre/${savedLettreId}/formations/${fid}/programme/jours`);
    if (!res.ok) return;
    const d = await res.json();
    _JOURS_PROG[fid] = d;
    _rendreJours(fid);
    if (d.confirmed) {
      document.getElementById(`btnPdfProg_${fid}`).style.display = '';
      const st = document.getElementById(`progstatus_${fid}`);
      if (st) st.textContent = `✓ تم تأكيد برنامج كامل أيّام الدورة (${d.jours.length} أيّام) بتاريخ ${d.confirmed_at || ''}`;
      document.getElementById('step6Section').style.display = '';
      chargerEtatMemo(fid);
    }
  } catch (e) { console.error('chargerProgrammeJours:', e); }
}

function _jourActif(fid) {
  const d = _JOURS_PROG[fid];
  if (!d) return null;
  if (_JOUR_EDITION[fid]) return _JOUR_EDITION[fid];
  const j = d.jours.find(x => !x.confirmed);
  return j ? j.jour : null;
}

function _dorraVerrouillee(fid) {
  return !!(typeof _ETATS !== 'undefined' && _ETATS[fid] && _ETATS[fid].finalise);
}

function _rendreJours(fid) {
  const d = _JOURS_PROG[fid];
  const cont = document.getElementById(`jourscont_${fid}`);
  const prog = document.getElementById(`jprog_${fid}`);
  if (!d || !cont) return;
  const actif = _jourActif(fid);
  const verrou = _dorraVerrouillee(fid);
  prog.innerHTML = d.jours.map(j => {
    const cls = (j.jour === actif) ? 'actif' : (j.confirmed ? 'fait' : '');
    return `<div class="jp-etape ${cls}">${j.confirmed && j.jour !== actif ? '✓ ' : ''}${esc(_libJour(j.jour))}<br>
            <span style="font-weight:400;font-size:.76rem;">${esc(_dateJourTxt(j.date))}</span></div>`;
  }).join('');
  cont.innerHTML = d.jours.map(j => {
    const cle = `${fid}_j${j.jour}`;
    const titre = `${esc(_libJour(j.jour))} — ${esc(_dateJourTxt(j.date))}`;
    if (j.jour === actif && !verrou) {
      const dernier = j.jour === d.jours.length;
      const txtBtn = dernier ? `✔ تأكيد ${_libJour(j.jour)} وإتمام برنامج الدورة`
                             : `✔ تأكيد ${_libJour(j.jour)} والانتقال إلى ${_libJour(j.jour + 1)}`;
      const per = (j.periode || '');
      const opt = (v, t) => `<label style="display:flex;gap:.25rem;align-items:center;">
          <input type="radio" name="per_${cle}" value="${v}" ${per === v ? 'checked' : ''}
                 onchange="_changerPeriodeJour('${cle}', this.value)"> ${t}</label>`;
      return `
        <div class="jour-carte actif" id="jcarte_${cle}">
          <div class="jour-tete"><span>✏️ ${titre}</span>
            ${_JOUR_EDITION[fid] ? `<button type="button" class="btn" style="padding:.2rem .7rem;font-size:.8rem;" onclick="_annulerEditionJour(${fid})">إلغاء التعديل</button>` : ''}</div>
          <div class="jour-corps">
            <div class="jour-periode"><strong>فترة هذا اليوم:</strong>
              ${opt('صباحا', '🌅 صباحا')} ${opt('مساءا', '🌇 مساءا')} ${opt('', '— كامل اليوم')}
            </div>
            <div style="overflow-x:auto;">
              <table style="width:100%; border-collapse:collapse; font-size:.9rem; direction:rtl;">
                <thead><tr style="background:#0369a1; color:#fff;">
                  <th style="padding:.5rem .7rem; border:1px solid #ccc; width:24%;">التّوقيت</th>
                  <th style="padding:.5rem .7rem; border:1px solid #ccc; width:40%;">بيان النشّاط</th>
                  <th style="padding:.5rem .7rem; border:1px solid #ccc; width:24%;">المتدخّلون</th>
                  <th style="padding:.5rem .7rem; border:1px solid #ccc; width:12%;"></th>
                </tr></thead>
                <tbody id="progtbody_${cle}" data-periode="${esc(per)}"></tbody>
              </table>
            </div>
            <div style="display:flex; gap:.8rem; flex-wrap:wrap; align-items:center; margin-top:.8rem;">
              <button type="button" class="btn" style="background:#0369a1;color:#fff;font-size:.85rem;"
                      onclick="ajouterLigneProgramme('${cle}','row')">➕ إضافة صف</button>
              <span style="flex:1;"></span>
              <button type="button" class="btn" id="btnJour_${cle}" style="background:#16a34a;color:#fff;"
                      onclick="confirmerJour(${fid}, ${j.jour})">${esc(txtBtn)}</button>
            </div>
          </div>
        </div>`;
    }
    if (j.confirmed) {
      const lignes = (j.rows || []).map(r => `<tr><td style="white-space:nowrap;text-align:center;">${esc(r.time || _formaterPlage(r.time_debut || '', r.time_fin || ''))}</td>
          <td>${esc(r.activity || '')}</td><td>${esc(r.participants || '')}</td></tr>`).join('');
      return `
        <div class="jour-carte fait" id="jcarte_${cle}">
          <div class="jour-tete"><span>✓ ${titre}${j.periode ? ' (' + esc(j.periode) + ')' : ''} — ${ (j.rows || []).length } فقرة</span>
            ${verrou ? '' : `<button type="button" class="btn" style="padding:.2rem .7rem;font-size:.8rem;" onclick="_editerJour(${fid}, ${j.jour})">✏️ تعديل</button>`}</div>
          <div class="jour-corps"><table class="jour-lecture" style="width:100%;border-collapse:collapse;">${lignes}</table></div>
        </div>`;
    }
    return `
      <div class="jour-carte attente" id="jcarte_${cle}">
        <div class="jour-tete"><span>⏳ ${titre}</span></div>
        <div class="jour-corps" style="color:var(--text-muted);font-size:.86rem;">يظهر بعد تأكيد ${esc(_libJour(j.jour - 1))}.</div>
      </div>`;
  }).join('');
  if (actif && !verrou) _remplirJour(fid, actif);
}

function _remplirJour(fid, n) {
  const d = _JOURS_PROG[fid];
  const j = d.jours.find(x => x.jour === n);
  const cle = `${fid}_j${n}`;
  const tbody = document.getElementById(`progtbody_${cle}`);
  if (!tbody) return;
  tbody.innerHTML = '';
  const rows = (j.rows || []).filter(r => (r.type || 'row') === 'row');
  if (!rows.length) { ajouterLigneProgramme(cle, 'row', true); return; }
  rows.forEach(row => {
    ajouterLigneProgramme(cle, 'row', true);
    const tr = tbody.lastElementChild;
    const p = tr.querySelector('.prow-participants');
    if (p) { p.value = row.participants || ''; _intervRendre(tr); }
    const a = tr.querySelector('.prow-activity'); if (a) a.value = row.activity || '';
    const td = tr.querySelector('.prow-time-debut'), tf = tr.querySelector('.prow-time-fin');
    if (td) td.value = row.time_debut || '';
    if (tf) tf.value = row.time_fin || '';
    if (td) _prowVerifierDuree(td);
  });
  _prowSyncContinuite(tbody);
}

function _changerPeriodeJour(cle, v) {
  const tbody = document.getElementById(`progtbody_${cle}`);
  if (!tbody) return;
  tbody.dataset.periode = v;
  // Le premier صف part de 08:00 le matin, de 13:30 l'après-midi.
  const d = tbody.querySelector('tr .prow-time-debut');
  if (d) {
    const debutJour = _debutJournee(tbody);
    if (v === 'مساءا' && d.value && d.value < debutJour) d.value = debutJour;
    if (v !== 'مساءا' && d.value === PROG_H_APRES_MIDI) d.value = PROG_H_MIN;
  }
  _prowSyncContinuite(tbody);
  tbody.querySelectorAll('.prow-time-debut').forEach(el => _prowVerifierDuree(el));
}

function _editerJour(fid, n) {
  _JOUR_EDITION[fid] = n;
  _rendreJours(fid);
}
function _annulerEditionJour(fid) {
  delete _JOUR_EDITION[fid];
  _rendreJours(fid);
}

function confirmerJour(fid, n) {
  const cle = `${fid}_j${n}`;
  const per = document.querySelector(`input[name="per_${cle}"]:checked`);
  _verifierProgramme(cle, complets => _envoyerJour(fid, n, per ? per.value : '', complets));
}

async function _envoyerJour(fid, n, periode, complets) {
  const btn = document.getElementById(`btnJour_${fid}_j${n}`);
  if (btn) btn.disabled = true;
  try {
    const res = await fetch(`/lettre/${savedLettreId}/formations/${fid}/programme/jour/${n}`, {
      method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({ periode: periode, rows: complets })
    });
    const d = await res.json();
    if (!res.ok || !d.succes) { showToast(d.erreur || 'خطأ في الحفظ', 'error'); return; }
    delete _JOUR_EDITION[fid];
    _chargerSuggestionsProgramme(true);
    if (d.termine) {
      showToast(`✅ تمّ تأكيد برنامج كامل أيّام الدورة (${d.nb_jours} أيّام)`);
      rafraichirEtats();
    } else {
      showToast(`✅ تمّ تأكيد ${_libJour(n)} — واصل تعمير ${_libJour(d.suivant)}`);
    }
    await chargerProgrammeJours(fid);
    const suiv = document.getElementById(`jcarte_${fid}_j${d.suivant}`);
    if (suiv && !d.termine) suiv.scrollIntoView({behavior: 'smooth', block: 'center'});
  } catch (e) { showToast('خطأ: ' + e.message, 'error'); }
  finally { if (btn) btn.disabled = false; }
}
