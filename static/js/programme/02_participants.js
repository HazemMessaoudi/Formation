/* ═══ نظام إدارة التكوين — صفحة إعداد برنامج التكوين ═══
   Étape 3 : chargement des دورات et قائمة المشاركين.
   v1.7 : extrait tel quel de templates/nouvelle_lettre.html (aucun
   changement de comportement). Les données du serveur sont fournies
   par le petit script en ligne de la page (constantes *_INIT, PAGE).
   Les fichiers se chargent dans l'ordre 01 → 06. */

// ── Step 3 : chargement des formations + panneau participants ─────────────────

async function chargerFormations() {
  if (!savedLettreId) return;
  try {
    const res = await fetch(`/lettre/${savedLettreId}/formations`);
    const d = await res.json();
    if (d.formations) {
      _FORMATIONS = d.formations;
      afficherFormationsListe(d.formations);
      afficherBataqaListe(d.formations);
      afficherProgrammeListe(d.formations);
      await rafraichirEtats();
      if (_dorraActive && !d.formations.some(f => f.id === _dorraActive)) _dorraActive = null;
      if (!_dorraActive && d.formations.length) _dorraActive = d.formations[0].id;
      if (_dorraActive) choisirDorra(_dorraActive); else afficherSelecteurDorrat();
    }
  } catch(e) { console.error('chargerFormations:', e); }
}

function afficherFormationsListe(formations) {
  const container = document.getElementById('formationsList');
  if (!formations.length) {
    container.innerHTML = '<p style="color:var(--text-muted)">لا توجد دورات في هذا البرنامج.</p>';
    return;
  }
  container.innerHTML = formations.map((f, i) => `
    <div class="card" style="margin-bottom:.8rem; border:1px solid var(--border);" id="fcard_${f.id}">
      <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:.5rem;">
        <div style="font-weight:700; font-size:1rem;">${esc(f.titre || '—')}</div>
        <div style="color:var(--text-muted); font-size:.88rem;">
          ${datesDorra(f)} ${f.periode ? '(' + esc(f.periode) + ')' : ''} — ${esc(f.lieu_formation || '')}
        </div>
        <button type="button" class="btn" style="padding:.4rem .9rem; font-size:.88rem; background:var(--primary); color:#fff;"
                onclick="toggleParticipantsPanel(${f.id})">
          👥 إدخال المشاركين
        </button>
      </div>
      <!-- Sous-panneau participants -->
      <div id="ppanel_${f.id}" style="display:none; margin-top:1rem;">
        <div class="table-wrapper" style="margin-bottom:.7rem;">
          <table style="width:100%; border-collapse:collapse; font-size:.88rem;" id="ptable_${f.id}">
            <thead>
              <tr style="background:var(--bg);">
                <th style="padding:.4rem .5rem; border:1px solid var(--border); width:38px">ع/ر</th>
                <th style="padding:.4rem .5rem; border:1px solid var(--border);">الاسم واللقب</th>
                <th style="padding:.4rem .5rem; border:1px solid var(--border); width:110px">الرتبة</th>
                <th style="padding:.4rem .5rem; border:1px solid var(--border); width:130px">المعرف الوحيد</th>
                <th style="padding:.4rem .5rem; border:1px solid var(--border);">مكان العمل</th>
                <th style="padding:.4rem .5rem; border:1px solid var(--border); width:100px">الجنس <span class="req-etoile">*</span></th>
                <th style="padding:.4rem .5rem; border:1px solid var(--border); width:150px">الفئة العمريّة <span class="req-etoile">*</span></th>
                <th style="padding:.4rem .5rem; border:1px solid var(--border); width:36px"></th>
              </tr>
            </thead>
            <tbody id="ptbody_${f.id}"></tbody>
          </table>
        </div>
        <div style="display:flex; gap:.8rem; flex-wrap:wrap; align-items:center;">
          <button type="button" class="btn btn-add" onclick="ajouterParticipant(${f.id})">➕ إضافة مشارك</button>
          <button type="button" class="btn" style="background:#22c55e;color:#fff;"
                  onclick="validerParticipants(${f.id})">✅ تأكيد القائمة</button>
          <button type="button" class="btn btn-generate" id="btnPdfPart_${f.id}" style="display:none;"
                  onclick="genererPDFParticipants(${f.id})">📄 قائمة المشاركين (PDF)</button>
        </div>
        <div id="pstatus_${f.id}" style="font-size:.85rem; color:var(--text-muted); margin-top:.4rem;"></div>
      </div>
    </div>
  `).join('');

  // Mémoriser le nom du formateur par formation (pour blocage participant)
  formations.forEach(f => {
    _FORM_FORMATCEURS[f.id] = (f.nom_formateur || '').trim().toLowerCase();
  });

  // Ajouter une ligne vide par défaut dans chaque panneau
  formations.forEach(f => {
    ajouterParticipant(f.id);
    // Check if already has participants
    chargerParticipantsExistants(f.id);
  });
}

let _FORM_FORMATCEURS = {};
let _panelOpen = {};

function toggleParticipantsPanel(fid) {
  const panel = document.getElementById(`ppanel_${fid}`);
  if (!panel) return;
  _panelOpen[fid] = !_panelOpen[fid];
  panel.style.display = _panelOpen[fid] ? '' : 'none';
}

let _partCount = {};
function _dernierePartieVide(fid) {
  const tbody = document.getElementById(`ptbody_${fid}`);
  if (!tbody || !tbody.lastElementChild) return false;
  const nom = tbody.lastElementChild.querySelector('.p-nom');
  return !(nom && nom.value.trim());
}

function ajouterParticipant(fid, data={}) {
  // Un tableau de participants ne se remplit pas par lignes vides : on n'en
  // ouvre une nouvelle qu'une fois la précédente nommée. (`data` non vide =
  // rechargement depuis la base, pas un clic de l'agent.)
  const _clic = !data || !Object.keys(data).length;
  if (_clic && _dernierePartieVide(fid)) {
    showToast('يرجى تعمير السطر الحالي قبل إضافة سطر جديد', 'error');
    const nom = document.querySelector(`#ptbody_${fid} tr:last-child .p-nom`);
    if (nom) nom.focus();
    return;
  }
  _partCount[fid] = (_partCount[fid] || 0) + 1;
  const n = _partCount[fid];
  const tbody = document.getElementById(`ptbody_${fid}`);
  if (!tbody) return;
  const tr = document.createElement('tr');
  tr.id = `prow_${fid}_${n}`;
  // v1.7.1 : الجهة المرجعيّة n'est plus une colonne ; elle suit la fiche de
  // la personne (données de l'البطاقة et des إحصائيات) sans être affichée.
  tr.dataset.jiha = data.jiha_marjiiya || '';
  tr.innerHTML = `
    <td style="padding:.3rem .4rem; border:1px solid var(--border); text-align:center;">${String(tbody.children.length + 1).padStart(2,'0')}</td>
    <td style="padding:.3rem .4rem; border:1px solid var(--border);">
      <div class="ac-wrap" style="position:relative;">
        <input type="text" class="p-nom" placeholder="الاسم واللقب" value="${esc(data.nom_prenom||'')}"
               autocomplete="off"
               style="width:100%; border:none; background:transparent; text-align:right; box-sizing:border-box;"
               oninput="showAcListPart(this)" onfocus="showAcListPart(this)" onblur="hideAcList(this,300)">
        <div class="ac-list" style="display:none;"></div>
      </div>
    </td>
    <td style="padding:.3rem .4rem; border:1px solid var(--border);">
      <input type="text" class="p-grade" placeholder="الرتبة" value="${esc(data.grade||'')}"
             style="width:100%; border:none; background:transparent; text-align:right;">
    </td>
    <td style="padding:.3rem .4rem; border:1px solid var(--border);">
      <input type="text" class="p-id" placeholder="المعرف الوحيد" value="${esc(data.identifiant_unique||'')}"
             style="width:100%; border:none; background:transparent; text-align:right;">
    </td>
    <td style="padding:.3rem .4rem; border:1px solid var(--border);">
      <input type="text" class="p-lieu" placeholder="مكان العمل" value="${esc(data.lieu_travail||'')}"
             style="width:100%; border:none; background:transparent; text-align:right;">
    </td>
    <td style="padding:.3rem .4rem; border:1px solid var(--border);">
      <select class="p-sexe" title="الجنس (إجباري)" required style="width:100%; border:none; background:transparent;">
        ${_optionsChoix(SEXES_INIT, data.sexe, '—')}
      </select>
    </td>
    <td style="padding:.3rem .4rem; border:1px solid var(--border);">
      <select class="p-fiaa" title="الفئة العمريّة (إجباري)" required style="width:100%; border:none; background:transparent;">
        ${_optionsChoix(FIAAT_INIT, data.fiaa_omria, '—')}
      </select>
    </td>
    <td style="padding:.3rem .4rem; border:1px solid var(--border); text-align:center;">
      <button type="button" class="btn-del" onclick="supprimerParticipant('prow_${fid}_${n}', ${fid})">🗑</button>
    </td>
  `;
  tbody.appendChild(tr);
  reNumeroterParticipants(fid);
}

function supprimerParticipant(rowId, fid) {
  document.getElementById(rowId)?.remove();
  reNumeroterParticipants(fid);
}

function reNumeroterParticipants(fid) {
  const tbody = document.getElementById(`ptbody_${fid}`);
  if (!tbody) return;
  Array.from(tbody.children).forEach((tr, i) => {
    const td = tr.querySelector('td:first-child');
    if (td) td.textContent = String(i + 1).padStart(2, '0');
  });
}

function collecterParticipants(fid) {
  const tbody = document.getElementById(`ptbody_${fid}`);
  if (!tbody) return [];
  return Array.from(tbody.querySelectorAll('tr')).map(tr => ({
    nom_prenom:        tr.querySelector('.p-nom')?.value?.trim() || '',
    grade:             tr.querySelector('.p-grade')?.value?.trim() || '',
    identifiant_unique: tr.querySelector('.p-id')?.value?.trim() || '',
    lieu_travail:      tr.querySelector('.p-lieu')?.value?.trim() || '',
    jiha_marjiiya:     (tr.dataset.jiha || '').trim(),
    sexe:              tr.querySelector('.p-sexe')?.value || '',
    fiaa_omria:        tr.querySelector('.p-fiaa')?.value || '',
  })).filter(p => p.nom_prenom);
}

async function chargerParticipantsExistants(fid) {
  if (!savedLettreId) return;
  try {
    const res = await fetch(`/lettre/${savedLettreId}/formations/${fid}/participants`);
    const d = await res.json();
    if (d.participants && d.participants.length > 0) {
      // Clear default empty row and load saved data
      const tbody = document.getElementById(`ptbody_${fid}`);
      if (tbody) { tbody.innerHTML = ''; _partCount[fid] = 0; }
      d.participants.forEach(p => ajouterParticipant(fid, p));
      document.getElementById(`btnPdfPart_${fid}`).style.display = '';
      const st = document.getElementById(`pstatus_${fid}`);
      if (st) st.textContent = `✓ ${d.participants.length} مشارك(ين) محفوظ(ين)`;
    }
  } catch(e) { console.error('chargerParticipantsExistants:', e); }
}

async function validerParticipants(fid) {
  if (!savedLettreId) { showToast('يجب تأكيد البرنامج أولاً','error'); return; }
  const parts = collecterParticipants(fid);
  if (!parts.length) { showToast('يرجى إدخال مشارك واحد على الأقل','error'); return; }

  // Vérification : données complètes. Un participant sans رتبة ou معرّف vient
  // d'un nom tapé à la main sans le choisir dans la liste — la classification
  // des مستحقّات en dépend, on ne confirme donc pas une liste incomplète.
  const incomplets = parts.filter(p => !(p.grade || '').trim() || !(p.identifiant_unique || '').trim());
  if (incomplets.length) {
    showToast(`⚠️ ${incomplets.length} مشارك(ين) ببيانات ناقصة (الرتبة/المعرف الوحيد). اختر الاسم من قائمة الاقتراحات ليُعمَّر آليًّا، أو أكمل الخانات الناقصة.`, 'error');
    return;
  }

  // v1.7.1 : الجنس et الفئة العمريّة sont obligatoires pour chaque participant
  // (statistiques et rapport annuel). Les cases manquantes sont signalées.
  const tbodyV = document.getElementById(`ptbody_${fid}`);
  let sansChoix = 0;
  if (tbodyV) Array.from(tbodyV.querySelectorAll('tr')).forEach(tr => {
    if (!(tr.querySelector('.p-nom')?.value || '').trim()) return;
    ['.p-sexe', '.p-fiaa'].forEach(sel => {
      const el = tr.querySelector(sel);
      const vide = el && !el.value;
      if (el) el.classList.toggle('champ-manquant', !!vide);
      if (vide) sansChoix++;
    });
  });
  if (sansChoix) {
    showToast('⚠️ يجب اختيار الجنس والفئة العمريّة لكلّ مشارك (الخانات المحدَّدة بالأحمر).', 'error');
    return;
  }

  // Vérification : le formateur ne peut pas être un participant
  const formateur = (_FORM_FORMATCEURS[fid] || '').trim().toLowerCase();
  if (formateur) {
    const conflict = parts.find(p => p.nom_prenom.trim().toLowerCase() === formateur);
    if (conflict) {
      showToast(`⚠️ "${conflict.nom_prenom}" هو المكوِّن ولا يمكن إضافته كمشارك في نفس الدورة`, 'error');
      return;
    }
  }

  // Vérification doublons identifiant_unique
  const seen = {};
  for (const p of parts) {
    const uid = (p.identifiant_unique || '').trim();
    if (uid) {
      if (seen[uid]) {
        showToast(`⚠️ المشارك بالمعرف الوحيد "${uid}" مضاف مرتين في القائمة`, 'error');
        return;
      }
      seen[uid] = true;
    }
  }

  try {
    const res = await fetch(`/lettre/${savedLettreId}/formations/${fid}/participants`, {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({participants: parts})
    });
    const d = await res.json();
    if (d.succes) {
      showToast(`✅ تم حفظ ${parts.length} مشارك(ين) بنجاح`);
      rafraichirEtats();
      document.getElementById(`btnPdfPart_${fid}`).style.display = '';
      const st = document.getElementById(`pstatus_${fid}`);
      if (st) st.textContent = `✓ ${parts.length} مشارك(ين) محفوظ(ين)`;
      // v1.7.1 : البطاقة et المذكّرة suivent la nouvelle liste
      rafraichirBataqaDerives(fid);
      rafraichirMemoApresParticipants(fid, !!d.memo_manuel);
      if ((d.bataqa_actualisee || []).length)
        showToast('🔄 حُيِّنت البطاقة البيداغوجيّة (المستهدفون / المصالح المعنيّة) حسب القائمة الجديدة', 'info');
    } else {
      showToast(d.erreur || 'خطأ في الحفظ', 'error');
    }
  } catch(e) { showToast('خطأ: ' + e.message, 'error'); }
}

function genererPDFParticipants(fid) {
  if (!savedLettreId) return;
  window.open(`/lettre/${savedLettreId}/formations/${fid}/participants/pdf`, '_blank');
  showToast('تم فتح قائمة المشاركين (PDF) ✓');
}

