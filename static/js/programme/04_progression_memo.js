/* ═══ نظام إدارة التكوين — صفحة إعداد برنامج التكوين ═══
   Progression دورة par دورة et étape 6 (مذكّرة, تسجيل نهائي).
   v1.7 : extrait tel quel de templates/nouvelle_lettre.html (aucun
   changement de comportement). Les données du serveur sont fournies
   par le petit script en ligne de la page (constantes *_INIT, PAGE).
   Les fichiers se chargent dans l'ordre 01 → 06. */

// ══ Chaque دورة se traite séparément ═════════════════════════════════════════
// Le programme n'est plus qu'un contenant : à partir de l'étape 3, l'agent
// choisit UNE dorra et ne voit que ses étapes. Annuler l'une ne touche pas
// les autres, et en enregistrer une n'empêche pas d'annuler les autres.

let _dorraActive = null;
let _FORMATIONS  = [];

const _ORDRE_ETAPES = [
  ['participants', '3'], ['bataqa', '4'], ['programme', '5'], ['memo', '6'],
];

function _resumeAvancement(etat) {
  if (!etat) return '—';
  if (etat.finalise) return '<span class="badge badge-blue">مسجَّلة نهائيًّا</span>';
  const faites = _ORDRE_ETAPES.filter(([cle]) => etat[cle]).map(([, n]) => n);
  if (!faites.length) return '<span class="badge badge-gray">لم تبدأ</span>';
  return `<span class="badge badge-green">الخطوات ${faites.join('، ')} ✓</span>`;
}

function afficherSelecteurDorrat() {
  const tbody = document.getElementById('dorraPickerBody');
  if (!tbody) return;
  document.getElementById('dorraPicker').style.display = '';
  tbody.innerHTML = _FORMATIONS.map((f, i) => {
    const etat = _ETATS[String(f.id)] || {};
    const actif = _dorraActive === f.id;
    return `
    <tr style="${actif ? 'background:var(--bg);font-weight:600;' : ''}">
      <td class="num-cell">${String(i + 1).padStart(2, '0')}</td>
      <td>${esc(f.titre || '—')}</td>
      <td><span dir="ltr">${f.date_formation ? datesDorra(f) : '—'}${f.periode ? ' (' + esc(f.periode) + ')' : ''}</span>${
        (_datePassee(f.date_formation) && !etat.finalise)
          ? ' <span class="tag-passee" title="تاريخ هذه الدورة قد مضى">⏳ مضى تاريخها</span>' : ''}</td>
      <td>${esc(f.nom_formateur || '—')}</td>
      <td>${_resumeAvancement(etat)}</td>
      <td class="actions-td" style="white-space:nowrap;">
        <button type="button" class="btn" style="padding:.3rem .8rem;font-size:.84rem;
                background:${actif ? '#0f766e' : 'var(--primary)'};color:#fff;"
                onclick="choisirDorra(${f.id})">${actif ? '✓ مختارة' : '▶ اشتغل عليها'}</button>
        ${etat.finalise ? '' : `
        <button type="button" class="btn" style="padding:.3rem .8rem;font-size:.84rem;
                background:#dc2626;color:#fff;"
                onclick="fsakhDorra(${f.id}, '${(f.titre || '').replace(/'/g, "\\'")}')">🗑 فسخ</button>`}
      </td>
    </tr>`;
  }).join('');
}

// v1.6.1 — تاريخ الدورة في الماضي : avertissement léger, jamais bloquant.
function _aujourdhuiISO() {
  const d = new Date(), z = n => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${z(d.getMonth() + 1)}-${z(d.getDate())}`;
}
function _datePassee(iso) {
  return /^\d{4}-\d{2}-\d{2}/.test(iso || '') && iso.slice(0, 10) < _aujourdhuiISO();
}
let _avisPasseeMasques = {};
function _masquerAvisPassee() {
  if (_dorraActive) _avisPasseeMasques[_dorraActive] = true;
  const el = document.getElementById('dorraPasseeAvis');
  if (el) el.style.display = 'none';
}
function _afficherAvisPassee(fid) {
  const el = document.getElementById('dorraPasseeAvis');
  if (!el) return;
  const f = _FORMATIONS.find(x => x.id === fid);
  const etat = _ETATS[String(fid)] || {};
  const montrer = f && _datePassee(f.date_formation) && !etat.finalise && !_avisPasseeMasques[fid];
  el.style.display = montrer ? '' : 'none';
  if (montrer) {
    el.querySelector('.avis-passee__txt').textContent =
      `ⓘ تاريخ الدورة «${f.titre || '—'}» (\u2066${f.date_formation.slice(0, 10)}\u2069) قد مضى. `
      + 'يمكنك مواصلة التعمير عاديًّا — تثبّت فقط من صحّة التاريخ.';
  }
}

function choisirDorra(fid) {
  _dorraActive = fid;
  _afficherAvisPassee(fid);
  ['fcard_', 'bcard_', 'progcard_', 'memocard_'].forEach(prefixe => {
    _FORMATIONS.forEach(f => {
      const carte = document.getElementById(`${prefixe}${f.id}`);
      if (carte) carte.style.display = (f.id === fid) ? '' : 'none';
    });
  });
  afficherSelecteurDorrat();
  document.getElementById('step3Section').scrollIntoView({behavior: 'smooth', block: 'start'});
}

function fsakhDorra(fid, titre) {
  showConfirmModal(
    `هل أنت متأكّد من فسخ الدورة «${titre}» نهائيًّا؟\n\n`
    + 'سيتمّ حذف معطياتها وحدها (المشاركون، البطاقة، البرنامج، المذكّرة) '
    + 'ويعود رقم مذكّرتها المحجوز إلى الرّصيد. بقيّة دورات البرنامج لا تتأثّر. '
    + 'ولا يمكن التراجع عن هذه العمليّة.',
    async () => {
      try {
        const res = await fetch(`/lettre/${savedLettreId}/formations/${fid}/annuler`,
                                { method: 'POST' });
        const d = await res.json();
        if (d.succes) {
          showToast('✅ تمّ فسخ الدورة');
          if (_dorraActive === fid) _dorraActive = null;
          await chargerFormations();
          if (_FORMATIONS.length) choisirDorra(_FORMATIONS[0].id);
        } else {
          showAlertModal(d.erreur || 'تعذّر فسخ الدورة.');
        }
      } catch (e) { showAlertModal('خطأ في الاتصال: ' + e.message); }
    });
}

// ══ Progression étape par étape, dorra par dorra ═════════════════════════════
// Une دورة se remplit dans l'ordre : 3 → 4 → 5 → 6. L'interface ne décide rien,
// elle reflète l'état que le serveur renvoie (/formations/etats) ; les gardes
// réelles sont côté serveur.

let _ETATS = {};

const _VERROUS = [
  // [id de la carte, étape concernée, libellé de l'étape qui manque]
  ['bcard_',     'bataqa',    'قائمة المشاركين (الخطوة 3)'],
  ['progcard_',  'programme', 'البطاقة البيداغوجية (الخطوة 4)'],
  ['memocard_',  'memo',      'برنامج الدورة (الخطوة 5)'],
];

function _poserVerrou(carte, verrouille, motif, fait) {
  if (!carte) return;
  carte.style.opacity = verrouille ? '.55' : '';
  carte.querySelectorAll('button').forEach(b => {
    if (verrouille) {
      if (!b.disabled) { b.dataset.verrouille = '1'; b.disabled = true; }
    } else if (b.dataset.verrouille === '1') {
      // On ne réactive que ce que le verrou avait éteint : un bouton désactivé
      // pour une autre raison (تكوين مسجّل, par ex.) doit le rester.
      delete b.dataset.verrouille;
      b.disabled = false;
    }
  });
  let badge = carte.querySelector('.etape-badge');
  if (!badge) {
    badge = document.createElement('div');
    badge.className = 'etape-badge';
    badge.style.cssText = 'margin-top:.5rem;font-size:.85rem;font-weight:600;';
    carte.firstElementChild.after(badge);
  }
  if (verrouille) {
    badge.style.color = '#b45309';
    badge.textContent = `🔒 يجب أوّلا استكمال ${motif}`;
  } else if (fait) {
    badge.style.color = '#15803d';
    badge.textContent = '✓ مستكملة';
  } else {
    badge.style.color = 'var(--text-muted)';
    badge.textContent = '▸ في انتظار الاستكمال';
  }
}

async function rafraichirEtats() {
  if (!savedLettreId) return;
  try {
    const res = await fetch(`/lettre/${savedLettreId}/formations/etats`);
    if (!res.ok) return;
    _ETATS = (await res.json()).etats || {};
  } catch (e) { console.error('rafraichirEtats:', e); return; }

  afficherSelecteurDorrat();
  if (_dorraActive) _afficherAvisPassee(_dorraActive);
  Object.entries(_ETATS).forEach(([fid, etat]) => {
    // Étape 3 : toujours ouverte, mais on affiche son état.
    _poserVerrou(document.getElementById(`fcard_${fid}`), false, '', etat.participants);
    _VERROUS.forEach(([prefixe, etape, motif]) => {
      const ouverte = (etat.ouvertes || []).includes(etape);
      _poserVerrou(document.getElementById(`${prefixe}${fid}`),
                   !ouverte, motif, etat[etape]);
    });
  });
  // La carte de مصادقة suit l'état : visible dès que toutes les دورات sont
  // enregistrées, verrouillée en « مُصادَق » une fois scellée.
  majBoutonMoussadaqa();
}

// ══ الخطوة 6 : تسجيل التكوين + مذكّرة تكوين داخليّة ═══════════════════════════

const MEMO_TYPES = ['للإعلام', 'للتعهد'];

function afficherMemoListe(formations) {
  const container = document.getElementById('memoList');
  if (!container) return;
  if (!formations.length) {
    container.innerHTML = '<p style="color:var(--text-muted)">لا توجد دورات.</p>';
    return;
  }
  container.innerHTML = formations.map(f => `
    <div class="card" style="margin-bottom:1rem; border:1px solid var(--border);" id="memocard_${f.id}">
      <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:.5rem;">
        <div style="font-weight:700; font-size:1rem;">${esc(f.titre || '—')}</div>
        <div style="color:var(--text-muted); font-size:.88rem;">
          ${datesDorra(f)} — ${esc(f.lieu_formation || '')}
        </div>
        <div style="display:flex; gap:.6rem; flex-wrap:wrap;">
          <button type="button" class="btn" id="btnEnreg_${f.id}"
                  style="background:#7c3aed;color:#fff;"
                  onclick="enregistrerFormation(${f.id})">🗂️ تسجيل التكوين</button>
          <button type="button" class="btn" id="btnMemo_${f.id}" style="display:none; background:#0369a1;color:#fff;"
                  onclick="ouvrirMemo(${f.id})">📝 إنشاء مذكّرة تكوين داخليّة</button>
        </div>
      </div>
      <div id="memopanel_${f.id}" style="display:none; margin-top:1rem;">
        <div class="form-group" style="margin-bottom:.9rem;">
          <label style="font-weight:600;">الموضوع</label>
          <input type="text" id="memoObjet_${f.id}" style="width:100%;"
                 oninput="marquerContenuManuel(${f.id})">
        </div>
        <div class="form-group" style="margin-bottom:.9rem;">
          <label style="font-weight:600;">المصاحيب (ثابتة)</label>
          <div id="memoMsahib_${f.id}"
               style="background:#f8fafc;border:1px solid var(--border);border-radius:6px;
                      padding:.6rem .8rem;font-size:.88rem;color:var(--text-muted);"></div>
        </div>
        <div class="form-group" style="margin-bottom:.9rem;">
          <label style="font-weight:600;">نصّ المذكّرة</label>
          <textarea id="memoCorps_${f.id}" rows="11"
                    oninput="marquerContenuManuel(${f.id})"
                    style="width:100%; line-height:1.9; font-size:.92rem;"></textarea>
          <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:.4rem;">
            <small style="color:var(--text-light);font-size:.82rem;">
              النصّ مُعمَّر تلقائيّاً من بيانات الدّورة — يمكنك تنقيحه قبل الطّباعة. كلّ سطر = فقرة.
            </small>
            <button type="button" class="btn" style="font-size:.8rem;padding:.25rem .7rem;"
                    onclick="regenererMemo(${f.id})" title="إعادة توليد النصّ من المعطيات الحالية">
              🔄 إعادة التوليد التلقائي
            </button>
          </div>
        </div>
        <div class="form-group" style="margin-bottom:.9rem;">
          <label style="font-weight:600;">الموجَّه إليهم</label>
          <div id="memoMoujah_${f.id}"></div>
          <button type="button" class="btn" style="margin-top:.5rem;background:#0369a1;color:#fff;font-size:.85rem;"
                  onclick="ajouterMoujah(${f.id})">＋ إضافة موجَّه إليه</button>
        </div>
        <div style="display:flex; gap:.8rem; flex-wrap:wrap; align-items:center; margin-top:1rem;">
          <button type="button" class="btn" style="background:#7c3aed;color:#fff;"
                  onclick="confirmerMemo(${f.id})">✅ تأكيد المذكّرة</button>
          <button type="button" class="btn btn-generate" id="btnPdfMemo_${f.id}"
                  style="display:none; background:#059669; color:#fff;"
                  onclick="genererPDFMemo(${f.id})">📄 طباعة المذكّرة (PDF)</button>
          <button type="button" class="btn" id="btnHodour_${f.id}"
                  style="display:none; background:#0f766e; color:#fff;"
                  title="وثيقة مستقلّة لا تُحتسب ضمن ترقيم الملفّ (ليست 4/4)"
                  onclick="genererPDFHodour(${f.id})">🖊️ بطاقة حضور</button>
          <button type="button" class="btn" id="btnDossier_${f.id}"
                  style="display:none; background:#374151; color:#fff;"
                  title="الوثائق الخمس بصيغة Word قابلة للتعديل، في ملفّ مضغوط واحد"
                  onclick="telechargerDossier(${f.id})">📦 ملفّ الدورة (Word)</button>
          <button type="button" class="btn" id="btnFinaliser_${f.id}"
                  style="display:none; background:#b91c1c; color:#fff;"
                  onclick="finaliserFormation(${f.id})">🔒 تسجيل الدورة في المنظومة</button>
        </div>
        <div id="memostatus_${f.id}" style="font-size:.85rem; color:var(--text-muted); margin-top:.4rem;"></div>
      </div>
    </div>
  `).join('');
}

// Suivi des retouches manuelles du contenu de la مذكرة (par dorra)
const _memoManuel = {};
function marquerContenuManuel(fid) { _memoManuel[fid] = true; }

// Restaure l'état des boutons de l'étape 6 (تكوين مسجّل / مذكّرة مؤكّدة / مسجّلة نهائيا)
async function chargerEtatMemo(fid) {
  if (!savedLettreId) return;
  try {
    const res = await fetch(`/lettre/${savedLettreId}/formations/${fid}/memo/data`);
    if (!res.ok) return;
    const d = await res.json();
    if (d.enregistre) {
      const b = document.getElementById(`btnEnreg_${fid}`);
      if (b) { b.textContent = '✓ تكوين مسجّل'; b.disabled = true; b.style.opacity = '.6'; }
      const bm = document.getElementById(`btnMemo_${fid}`);
      if (bm) bm.style.display = '';
    }
    if (d.confirmed) {
      const st = document.getElementById(`memostatus_${fid}`);
      if (st) st.textContent = `✓ تم التأكيد بتاريخ ${d.confirmed_at || ''}`;
    }
    if (d.finalise) marquerDorraFinalisee(fid, d.finalise_at);
  } catch(e) { /* silencieux */ }
}

// Verrouille toute l'interface de la dorra après « تسجيل نهائي »
function marquerDorraFinalisee(fid, quand) {
  const badge = `<span style="display:inline-flex;align-items:center;gap:.35rem;
      background:#dcfce7;color:#166534;border:1px solid #86efac;
      border-radius:20px;padding:.2rem .75rem;font-size:.82rem;font-weight:700;vertical-align:middle;">
      🔒 مسجَّلة في المنظومة ✓</span>`;

  const st = document.getElementById(`memostatus_${fid}`);
  if (st) st.innerHTML = `🔒 <strong>الدورة مسجَّلة نهائيًّا</strong> بتاريخ ${esc(quand || '')} — لم يعد بالإمكان تعديلها.`;

  ['btnFinaliser','btnEnreg'].forEach(p => {
    const b = document.getElementById(`${p}_${fid}`); if (b) b.style.display = 'none';
  });

  // Désactiver memo panel
  const memoPanel = document.getElementById(`memopanel_${fid}`);
  if (memoPanel) memoPanel.querySelectorAll('input,textarea,select,button').forEach(el => {
    if (el.id && el.id.startsWith('btnPdfMemo')) return;
    el.disabled = true; el.style.opacity = '.55';
  });

  // Désactiver participants panel + show badge
  const ppanel = document.getElementById(`ppanel_${fid}`);
  if (ppanel) {
    ppanel.querySelectorAll('input,textarea,select,button').forEach(el => {
      if (el.id && el.id.startsWith('btnPdfPart')) return;
      el.disabled = true; el.style.opacity = '.55';
    });
    const ps = document.getElementById(`pstatus_${fid}`);
    if (ps) ps.innerHTML += ' ' + badge;
  }

  // Désactiver bataqa panel + show badge
  const bpanel = document.getElementById(`bpanel_${fid}`);
  if (bpanel) {
    bpanel.querySelectorAll('input,textarea,select,button').forEach(el => {
      if (el.id && el.id.startsWith('btnPdfBataqa')) return;
      el.disabled = true; el.style.opacity = '.55';
    });
    const bs = document.getElementById(`bstatus_${fid}`);
    if (bs) bs.innerHTML += ' ' + badge;
  }

  // Désactiver programme panel + show badge
  const progpanel = document.getElementById(`progpanel_${fid}`);
  if (progpanel) {
    progpanel.querySelectorAll('input,textarea,select,button').forEach(el => {
      if (el.id && el.id.startsWith('btnPdfProg')) return;
      el.disabled = true; el.style.opacity = '.55';
    });
    const progs = document.getElementById(`progstatus_${fid}`);
    if (progs) progs.innerHTML += ' ' + badge;
  }

  // Memo card header badge
  const memoCard = document.getElementById(`memocard_${fid}`);
  if (memoCard) {
    const titleEl = memoCard.querySelector('div[style*="font-weight:700"]');
    if (titleEl && !titleEl.querySelector('.finalise-badge')) {
      const b = document.createElement('span');
      b.className = 'finalise-badge';
      b.innerHTML = ' ' + badge;
      titleEl.appendChild(b);
    }
    // v1.6 : « التراجع للتحيين » — réservé à المشرف العام, motif obligatoire
    if (EST_ADMIN && titleEl && !document.getElementById(`btnDeverr_${fid}`)) {
      const u = document.createElement('button');
      u.type = 'button'; u.id = `btnDeverr_${fid}`;
      u.className = 'btn btn-deverrouiller';
      u.style.marginInlineStart = '.5rem';
      u.textContent = '🔓 التراجع للتحيين';
      u.addEventListener('click', ev => { ev.stopPropagation(); deverrouillerFormation(fid); });
      titleEl.appendChild(u);
    }
  }
}

function deverrouillerFormation(fid) {
  if (!savedLettreId) return;
  showPromptModal('سبب التراجع للتحيين (إجباري — يُسجَّل في سجلّ العمليّات) :',
    { min: 5, placeholder: 'مثال : إصلاح خطإ في قائمة المشاركين' }, async motif => {
      try {
        const r = await fetch(`/lettre/${savedLettreId}/formations/${fid}/deverrouiller`, {
          method: 'POST', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ motif })
        });
        const d = await r.json().catch(() => ({}));
        if (!r.ok || !d.succes) { showAlertModal(d.erreur || 'تعذّر التراجع للتحيين'); return; }
        location.reload();
      } catch (e) { showAlertModal('تعذّر الاتّصال بالخادم'); }
    });
}

async function enregistrerFormation(fid) {
  if (!savedLettreId) return;
  try {
    const res = await fetch(`/lettre/${savedLettreId}/formations/${fid}/memo/data`, {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({ confirmer: false })
    });
    const d = await res.json();
    if (d.succes) {
      showToast('✅ تمّ تسجيل التكوين');
      rafraichirEtats();
      document.getElementById(`btnMemo_${fid}`).style.display = '';
      const b = document.getElementById(`btnEnreg_${fid}`);
      if (b) { b.textContent = '✓ تكوين مسجّل'; b.disabled = true; b.style.opacity = '.6'; }
    } else {
      showToast(d.erreur || 'خطأ في التّسجيل', 'error');
    }
  } catch(e) { showToast('خطأ: '+e.message, 'error'); }
}

async function ouvrirMemo(fid) {
  const panel = document.getElementById(`memopanel_${fid}`);
  if (!panel) return;
  if (panel.style.display !== 'none') { panel.style.display = 'none'; return; }
  panel.style.display = '';
  try {
    const res = await fetch(`/lettre/${savedLettreId}/formations/${fid}/memo/data`);
    const d = await res.json();
    if (d.erreur) { showToast(d.erreur, 'error'); panel.style.display = 'none'; return; }

    document.getElementById(`memoObjet_${fid}`).value = d.objet || '';
    document.getElementById(`memoCorps_${fid}`).value = d.corps || '';
    _memoManuel[fid] = !!d.contenu_manuel;
    document.getElementById(`memoMsahib_${fid}`).innerHTML =
      (d.msahib || []).map(m => `• ${m}`).join('<br>');

    const box = document.getElementById(`memoMoujah_${fid}`);
    box.innerHTML = '';
    (d.moujah || []).forEach(m => ajouterMoujah(fid, m));
    if (!box.children.length) ajouterMoujah(fid);

    if (d.confirmed) {
      document.getElementById(`btnPdfMemo_${fid}`).style.display = '';
      document.getElementById(`btnHodour_${fid}`).style.display = '';
      { const bd = document.getElementById(`btnDossier_${fid}`); if (bd) bd.style.display = ''; }
      document.getElementById(`btnFinaliser_${fid}`).style.display = '';
      const st = document.getElementById(`memostatus_${fid}`);
      if (st) st.textContent = `✓ تم التأكيد بتاريخ ${d.confirmed_at || ''}`;
    }
    if (d.finalise) marquerDorraFinalisee(fid, d.finalise_at);
  } catch(e) { showToast('خطأ: '+e.message, 'error'); }
}

// v1.7.1 : après une modification de la قائمة المشاركين, le texte de la
// مذكّرة ouverte et non retouchée est rechargé (il est régénéré côté serveur).
async function rafraichirMemoApresParticipants(fid, manuel) {
  if (manuel || _memoManuel[fid]) {
    showToast('ℹ️ نصّ المذكّرة معدَّل يدويًّا فلم يُحيَّن آليًّا: استعمل «إعادة التوليد التلقائي» لتحيينه حسب القائمة الجديدة.', 'warning');
    return;
  }
  const panel = document.getElementById(`memopanel_${fid}`);
  const corps = document.getElementById(`memoCorps_${fid}`);
  if (!panel || !corps || panel.style.display === 'none') return;
  try {
    const res = await fetch(`/lettre/${savedLettreId}/formations/${fid}/memo/data`);
    const d = await res.json();
    if (d.erreur) return;
    document.getElementById(`memoObjet_${fid}`).value = d.objet || '';
    corps.value = d.corps || '';
  } catch (e) { console.error('rafraichirMemoApresParticipants:', e); }
}

// Réinjecte le texte auto-généré à partir des données actuelles
async function regenererMemo(fid) {
  if (!savedLettreId) return;
  try {
    const res = await fetch(`/lettre/${savedLettreId}/formations/${fid}/memo/data?auto=1`);
    const d = await res.json();
    if (d.erreur) { showToast(d.erreur, 'error'); return; }
    document.getElementById(`memoObjet_${fid}`).value = d.objet || '';
    document.getElementById(`memoCorps_${fid}`).value = d.corps || '';
    _memoManuel[fid] = false;
    showToast('تمّت إعادة توليد النصّ من المعطيات الحاليّة ✓');
  } catch(e) { showToast('خطأ: '+e.message, 'error'); }
}

// « تسجيل الدورة في المنظومة » — verrou définitif, précédé d'une مراجعة نهائيّة
// de tout ce que la دورة a produit : documents, عدد de la مذكّرة, retouches.
async function finaliserFormation(fid) {
  if (!savedLettreId) return;
  let r;
  try {
    r = await (await fetch(`/lettre/${savedLettreId}/formations/${fid}/revue`)).json();
  } catch (e) { showToast('تعذّر تحميل المراجعة: ' + e.message, 'error'); return; }

  if (r.manquant && r.manquant.length) {
    showAlertModal('لا يمكن تسجيل الدورة قبل استكمال:\n— ' + r.manquant.join('\n— '));
    return;
  }

  const L = [];
  L.push(`📋 المراجعة النهائيّة للدورة «${r.titre || '—'}»`);
  L.push('');
  L.push('الوثائق المستخرَجة:');
  r.documents.forEach(d => {
    L.push(`  ${d.ok ? '✓' : '✗'} ${d.label}${d.detail ? ' — ' + d.detail : ''}`);
  });
  L.push('');
  if (r.memo_ref) L.push(`عدد المذكّرة الداخليّة: ${r.memo_ref}`);
  L.push(`ما تمّ تحيينه في المذكّرة: ${r.memo_manuel ? 'نُقِّح النصّ يدويّا' : 'النصّ التلقائي'}`);
  L.push('');
  L.push('⚠️ بعد التأكيد تُسجَّل الدورة نهائيّا ولا يمكن تعديلها '
         + '(تبقى من مشمولات المشرف العام فقط).');
  L.push('هل تريد المتابعة؟');

  showConfirmModal(L.join('\n'), async () => {
    try {
      const res = await fetch(`/lettre/${savedLettreId}/formations/${fid}/finaliser`, {
        method: 'POST', headers: {'Content-Type': 'application/json'}, body: '{}'
      });
      const d = await res.json();
      if (d.succes) {
        showToast('🔒 تمّ تسجيل الدورة نهائيًّا في المنظومة');
        marquerDorraFinalisee(fid, d.finalise_at);
        majBoutonMoussadaqa();
      } else {
        showToast(d.erreur || 'تعذّر التسجيل النهائي', 'error');
      }
    } catch(e) { showToast('خطأ: '+e.message, 'error'); }
  });
}

// Affiche la carte de مصادقة dès que toutes les دورات sont enregistrées.
async function majBoutonMoussadaqa() {
  const carte = document.getElementById('carteMoussadaqa');
  if (!carte || !savedLettreId) return;
  try {
    const r = await (await fetch(`/lettre/${savedLettreId}/revue`)).json();
    if (r.scelle) {
      carte.style.display = '';
      const s = document.getElementById('moussadaqaScelle');
      if (s) { s.style.display = ''; s.textContent = '🔒 برنامج مُصادَق عليه نهائيّا ✓'; }
      const btn = carte.querySelector('button');
      if (btn) btn.style.display = 'none';
    } else {
      carte.style.display = (r.tout_finalise && r.dorrat.length) ? '' : 'none';
    }
  } catch (e) { /* silencieux : la carte reste simplement masquée */ }
}

// مراجعة نهائيّة لكامل البرنامج ثمّ الختم.
async function ouvrirMoussadaqa() {
  if (!savedLettreId) return;
  let r;
  try {
    r = await (await fetch(`/lettre/${savedLettreId}/revue`)).json();
  } catch (e) { showAlertModal('تعذّر تحميل المراجعة: ' + e.message); return; }

  const L = [];
  L.push(`📋 المراجعة النهائيّة للبرنامج ${r.ref || ''}`);
  L.push('');
  L.push(`الدورات: ${r.dorrat.length} — المسجَّلة نهائيّا: `
         + `${r.dorrat.filter(d => d.finalise).length}`);
  if (r.dr_lettres.length)
    L.push(`مراسلات المديرين الجهويّين: ${r.dr_lettres.length}`);
  L.push(`الأعداد المسحوبة من السّجلّ: ${r.registre.length}`);
  L.push('');

  if (!r.coherent) {
    L.push('⚠️ لا يمكن المصادقة — يجب إصلاح ما يلي أوّلا:');
    r.problemes.forEach(p => L.push('— ' + p));
    showAlertModal(L.join('\n'));
    return;
  }

  L.push('✅ كلّ المعطيات سليمة وكلّ عدد في مقابله وثيقة قائمة.');
  L.push('');
  L.push('بعد المصادقة يُختم البرنامج نهائيّا. هل تريد المتابعة؟');
  showConfirmModal(L.join('\n'), async () => {
    try {
      const res = await fetch(`/lettre/${savedLettreId}/sceller`, { method: 'POST' });
      const d = await res.json();
      if (d.succes) { showToast('🔒 تمّت المصادقة على البرنامج'); majBoutonMoussadaqa(); }
      else {
        showAlertModal('تعذّرت المصادقة:\n— ' + (d.problemes || ['خطأ']).join('\n— '));
      }
    } catch (e) { showAlertModal('خطأ: ' + e.message); }
  });
}

function ajouterMoujah(fid, data={}) {
  const box = document.getElementById(`memoMoujah_${fid}`);
  if (!box) return;
  const row = document.createElement('div');
  row.className = 'moujah-row';
  row.style.cssText = 'display:flex; gap:.4rem; align-items:center; margin-bottom:.4rem;';
  const opts = ['', ...MEMO_TYPES].map(t =>
    `<option value="${esc(t)}" ${((data.type||'') === t) ? 'selected' : ''}>${esc(t || '— بدون —')}</option>`
  ).join('');
  row.innerHTML = `
    <span class="mj-num" style="flex:none;width:26px;text-align:center;font-weight:700;
          background:var(--primary);color:#fff;border-radius:6px;padding:.25rem 0;font-size:.8rem;">1</span>
    <input type="text" class="mj-nom" value="${(data.nom||'').replace(/"/g,'&quot;')}"
           placeholder="مثال: السيّد رئيس المكتب الجهوي للديوانة بالكاف"
           style="flex:1; min-width:0;">
    <select class="mj-type" style="width:120px; flex:none;">${opts}</select>
    <button type="button" class="btn" style="padding:.3rem .55rem;font-size:.8rem;flex:none;"
            onclick="deplacerMoujah(this,-1)" title="نقل إلى الأعلى">▲</button>
    <button type="button" class="btn" style="padding:.3rem .55rem;font-size:.8rem;flex:none;"
            onclick="deplacerMoujah(this,1)" title="نقل إلى الأسفل">▼</button>
    <button type="button" class="btn" style="padding:.3rem .55rem;font-size:.8rem;flex:none;background:#ef4444;color:#fff;"
            onclick="const b=this.closest('.moujah-row').parentElement; this.closest('.moujah-row').remove(); renumeroterMoujah(b);"
            title="حذف">🗑</button>
  `;
  box.appendChild(row);
  renumeroterMoujah(box);
}

/* Renumérote les lignes : l'ordre affiché = l'ordre imprimé sur la مذكرة */
function renumeroterMoujah(box) {
  if (!box) return;
  Array.from(box.querySelectorAll('.moujah-row')).forEach((r, i) => {
    const n = r.querySelector('.mj-num');
    if (n) n.textContent = i + 1;
  });
}

function deplacerMoujah(btn, dir) {
  const row = btn.closest('.moujah-row');
  const box = row.parentElement;
  if (dir < 0 && row.previousElementSibling) {
    box.insertBefore(row, row.previousElementSibling);
  } else if (dir > 0 && row.nextElementSibling) {
    box.insertBefore(row.nextElementSibling, row);
  }
  renumeroterMoujah(box);
}

function collecterMoujah(fid) {
  const box = document.getElementById(`memoMoujah_${fid}`);
  if (!box) return [];
  return Array.from(box.querySelectorAll('.moujah-row')).map(r => ({
    nom:  r.querySelector('.mj-nom')?.value?.trim() || '',
    type: r.querySelector('.mj-type')?.value || '',
  })).filter(m => m.nom);
}

async function confirmerMemo(fid) {
  if (!savedLettreId) return;
  const objet  = document.getElementById(`memoObjet_${fid}`).value.trim();
  const corps  = document.getElementById(`memoCorps_${fid}`).value.trim();
  const moujah = collecterMoujah(fid);
  if (!objet)  { showToast('يرجى إدخال موضوع المذكّرة', 'error'); return; }
  if (!corps)  { showToast('يرجى إدخال نصّ المذكّرة', 'error'); return; }
  if (!moujah.length) { showToast('يرجى إضافة موجَّه إليه واحد على الأقلّ', 'error'); return; }
  try {
    const res = await fetch(`/lettre/${savedLettreId}/formations/${fid}/memo/data`, {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({ confirmer: true, objet, corps, moujah,
                             contenu_manuel: !!_memoManuel[fid] })
    });
    const d = await res.json();
    if (d.succes) {
      showToast('✅ تمّ تأكيد المذكّرة بنجاح');
      document.getElementById(`btnPdfMemo_${fid}`).style.display = '';
      document.getElementById(`btnHodour_${fid}`).style.display = '';
      { const bd = document.getElementById(`btnDossier_${fid}`); if (bd) bd.style.display = ''; }
      document.getElementById(`btnFinaliser_${fid}`).style.display = '';
      const st = document.getElementById(`memostatus_${fid}`);
      if (st) st.textContent = `✓ تم التأكيد — ${moujah.length} موجَّه إليه`;
    } else {
      showToast(d.erreur || 'خطأ في الحفظ', 'error');
    }
  } catch(e) { showToast('خطأ: '+e.message, 'error'); }
}

function genererPDFMemo(fid) {
  if (!savedLettreId) return;
  window.open(`/lettre/${savedLettreId}/formations/${fid}/memo/pdf`, '_blank');
  showToast('تم فتح المذكّرة (PDF) ✓');
}

function genererPDFHodour(fid) {
  if (!savedLettreId) return;
  window.open(`/lettre/${savedLettreId}/formations/${fid}/hodour/pdf`, '_blank');
  showToast('تم فتح بطاقة الحضور (PDF) ✓');
}

// v1.7 — ملفّ الدورة كاملًا : téléchargement direct de l'archive (pas d'onglet)
function telechargerDossier(fid) {
  if (!savedLettreId) return;
  window.location.href = `/lettre/${savedLettreId}/formations/${fid}/dossier.zip`;
  showToast('جارٍ تحميل ملفّ الدورة (Word) ✓');
}

// showToast() : implémentation commune (static/js/ui.js, v1.5).

