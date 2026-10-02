# -*- coding: utf-8 -*-
"""ملفّ الدورة كاملًا — les cinq pièces d'une دورة en Word (.docx), réunies
dans une archive ZIP (v1.7).

  1. المذكّرة
  2. برنامج الدورة
  3. القائمة الإسمية للمشاركين
  4. البطاقة البيداغوجية
  5. بطاقة الحضور

Les données viennent de `core/dossier_dorra.py`, exactement celles des PDF.
La mise en page reprend celle des PDF (et donc des modèles officiels) :
mêmes textes, mêmes polices (Arial ; Traditional Arabic pour le titre et la
signature de la مذكّرة), mêmes tailles, mêmes couleurs d'en-tête, mêmes
bordures doubles. Le Word est MODIFIABLE : c'est son intérêt — le PDF reste
la pièce de référence.

Une pièce non encore confirmée n'entre pas dans l'archive ; un fichier
« ملاحظة.txt » dit ce qui manque.
"""

import io
import os
import zipfile
from datetime import datetime

from core import identite
from core import jours as _jours
from core import docx_ecrivain as dx
from core.docx_ecrivain import paragraphe as P, run as R, cellule as C, ligne as L

MOIS = ['جانفي', 'فيفري', 'مارس', 'أفريل', 'ماي', 'جوان', 'جويلية', 'أوت',
        'سبتمبر', 'أكتوبر', 'نوفمبر', 'ديسمبر']
JOURS = ['الإثنين', 'الثلاثاء', 'الأربعاء', 'الخميس', 'الجمعة', 'السبت', 'الأحد']

BLEU_ENTETE = '5B9BD5'
BLEU_COLONNES = 'B4C6E7'
BLEU_DATE = 'D9E2F3'
GRIS_BATAQA = 'D5D5D5'

K_LISTE = 1.0732        # pt par pixel des captures (قائمة / بطاقة حضور)
K_PROG = 1.078          # pt par pixel (برنامج الدورة)


def _px(px, k):
    return dx.pt_cm(px * k)


def _chemin_image(base_dir, nom):
    return os.path.join(base_dir, 'static', 'images', nom)


def _logo_douane(base_dir):
    """Emblème de la ديوانة : la variante « document » si elle est livrée."""
    for nom in ('logo_douane_doc.png', 'logo_douane.png'):
        chemin = _chemin_image(base_dir, nom)
        if os.path.exists(chemin):
            return chemin
    return ''


def _date_arabe(date_iso, ville='', mois='', annee=''):
    try:
        d = datetime.strptime(date_iso or '', '%Y-%m-%d')
        txt = f'{d.day} {MOIS[d.month - 1]} {d.year}'
    except (TypeError, ValueError):
        txt = f'{mois or ""} {annee or ""}'.strip()
    if not txt:
        return ''
    return f'{ville} في {txt}'.strip() if ville else txt


def _date_titre(data, ville=''):
    """Ligne de date des listes ; V2 : « … في الفترة من 14 إلى 16 أكتوبر 2026 »
    pour une دورة متعدّدة الأيّام (même texte que le PDF)."""
    debut, fin = data.get('date_formation'), data.get('date_fin')
    if _jours.est_multi_jours(debut, fin):
        txt = f'في الفترة {_jours.plage_longue(debut, fin)}'
        return f'{ville} {txt}'.strip() if ville else txt
    return _date_arabe(debut, ville, data.get('mois'), data.get('annee'))


def _sans_tatweel(t):
    return ' '.join(str(t or '').replace('ـ', '').split())


# ─── Blocs communs ───────────────────────────────────────────────────────────

def _bloc_institution(lignes_nat, lignes_centre, largeur_cm):
    """Paragraphes du bloc d'identification (gras 12) : lignes étirées sur la
    largeur du bloc, « وزارة المالية » centrée, ligne courte du centre centrée."""
    # Lignes centrées dans un bloc de largeur fixe : même silhouette que les
    # lignes étirées du PDF, sans dépendre de l'étirement (kashida) propre à
    # chaque traitement de texte.
    paras = []
    for l in list(lignes_nat) + list(lignes_centre):
        l = _sans_tatweel(l)
        if l:
            paras.append(P(l, align='centre', taille=12, gras=True, ligne_pt=14.1))
    return paras


def _entete_word(doc, base_dir, libelle, lignes_nat, lignes_centre, largeur_page_cm,
                 largeur_bloc_cm=6.4, logo=(2.35, 3.03)):
    """En-tête des pièces « Word » : bloc institution à droite, libellé de
    lieu à gauche, logo de l'École centré dessous."""
    reste = largeur_page_cm - largeur_bloc_cm
    doc.ajouter(dx.tableau(
        [largeur_bloc_cm, reste],
        [L([C(_bloc_institution(lignes_nat, lignes_centre, largeur_bloc_cm),
              largeur_bloc_cm, valign='top'),
            C(P(libelle, align='gauche', taille=11, gras=True), reste, valign='top')],
           insecable=False)],
        bordure_ext=None, bordure_h=None, bordure_v=None, marge_cellule_cm=0))
    doc.ajouter(doc.image(_chemin_image(base_dir, 'logo.jpg'), logo[0], logo[1],
                          avant=10, apres=6))


def _titres(doc, titre, taille_titre, sous_titres):
    doc.ajouter(P(titre, align='centre', taille=taille_titre, gras=True, avant=4, apres=2,
                  ligne_pt=taille_titre * 1.4))
    for s in sous_titres:
        if s:
            doc.ajouter(P(s, align='centre', taille=16, gras=True, apres=0, ligne_pt=25.8))
    doc.ajouter(P('', taille=8))


def _cell_entete(texte, largeur, fond, taille=12):
    return C(P(texte, align='centre', taille=taille, gras=True, ligne_pt=taille * 1.25),
             largeur, fond=fond,
             bords={'bas': ('double', 4)})


# ─── 3. القائمة الإسمية للمشاركين ────────────────────────────────────────────

def word_participants(data, base_dir):
    doc = dx.DocumentWord(marges_cm=(0.9, 0.9, 1.3, 0.9), titre='قائمة المشاركين')
    nom_centre = data.get('nom_centre') or identite.CENTRE_NEUTRE
    _entete_word(doc, base_dir, 'فندق الجديد في :', identite.ENTETE_NATIONAL,
                 [nom_centre], 19.2)
    _titres(doc, 'قائمة المشاركين', 18, [
        f'الدورة تكوينيّة حول " {data.get("titre", "")} "',
        f'تحت إشراف {nom_centre}',
        _date_titre(data, (data.get('ville_centre') or '').strip())])
    # ordre RTL : ع/ر | الإسم واللقب | الرّتبة | المعرّف الوحيد | مكان العمل
    larg = [_px(p, K_LISTE) for p in (27, 109, 77, 86, 203)]
    lignes = [L([_cell_entete(t, w, BLEU_ENTETE) for t, w in zip(
        ('ع/ر', 'الإسم واللقب', 'الرّتبة', 'المعرّف الوحيد', 'مكان العمل'), larg)],
        entete=True)]
    parts = data.get('participants') or []
    lieux = [str(p.get('lieu_travail') or '').strip() for p in parts]
    for i, p in enumerate(parts):
        # مكان العمل : cellules identiques et consécutives fusionnées (modèle)
        if lieux[i] and i > 0 and lieux[i] == lieux[i - 1]:
            fusion = 'suite'
        elif lieux[i] and i + 1 < len(parts) and lieux[i + 1] == lieux[i]:
            fusion = 'debut'
        else:
            fusion = None
        lieu = C(P('' if fusion == 'suite' else lieux[i], align='centre', taille=14, ligne_pt=16.1),
                 larg[4], fusion_v=fusion)
        lignes.append(L([
            C(P(f'{i + 1:02d}', align='centre', taille=12, gras=True), larg[0]),
            C(P(p.get('nom_prenom', ''), align='centre', taille=14, ligne_pt=16.1), larg[1]),
            C(P(p.get('grade', ''), align='centre', taille=14, ligne_pt=16.1), larg[2]),
            C(P(p.get('identifiant_unique', ''), align='centre', taille=14, ligne_pt=16.1), larg[3]),
            lieu], hauteur_cm=_px(19.55, K_LISTE)))
    doc.ajouter(dx.tableau(larg, lignes))
    return doc.octets()


# ─── 5. بطاقة الحضور ─────────────────────────────────────────────────────────

def word_hodour(data, base_dir):
    jours = [j for j in (data.get('jours') or []) if j.get('date')]
    if len(jours) > 1:
        return _word_hodour_multi(data, base_dir, jours)
    doc = dx.DocumentWord(marges_cm=(1.0, 1.9, 1.3, 1.9), titre='بطاقة حضور')
    nom_centre = data.get('nom_centre') or identite.CENTRE_NEUTRE
    ville = (data.get('ville_centre') or '').strip()
    _entete_word(doc, base_dir, f'{ville} في :' if ville else 'في :',
                 identite.ENTETE_NATIONAL, [nom_centre], 17.2)
    _titres(doc, 'بطاقة حضور', 20, [
        f'الدورة تكوينيّة حول " {data.get("titre", "")} "',
        f'تحت إشراف {nom_centre}',
        _date_arabe(data.get('date_formation'), ville, data.get('mois'), data.get('annee'))])
    larg = [_px(p, K_LISTE) for p in (27, 109, 77, 164)]
    lignes = [L([_cell_entete(t, w, BLEU_ENTETE) for t, w in zip(
        ('ع/ر', 'الإسم واللقب', 'الرّتبة', 'الإمضاء'), larg)], entete=True)]
    for i, p in enumerate(data.get('participants') or []):
        lignes.append(L([
            C(P(f'{i + 1:02d}', align='centre', taille=12, gras=True), larg[0]),
            C(P(p.get('nom_prenom', ''), align='centre', taille=14, ligne_pt=16.1), larg[1]),
            C(P(p.get('grade', ''), align='centre', taille=14, ligne_pt=16.1), larg[2]),
            C(P(''), larg[3])], hauteur_cm=_px(19.55, K_LISTE)))
    doc.ajouter(dx.tableau(larg, lignes))
    # Pied : المكوّن à droite ; رئيس المركز à gauche
    formateur = f'{(data.get("grade_formateur") or "").strip()} ' \
                f'{(data.get("nom_formateur") or "").strip()}'.strip()
    resp = f'{(data.get("titre_responsable") or "").strip()} ' \
           f'{(data.get("nom_responsable") or "").strip()}'.strip()
    w = sum(larg) / 2
    doc.ajouter(P('', taille=10), dx.tableau([w, w], [L([
        C([P('المكوّن', taille=12, gras=True), P(formateur, taille=12, gras=True)], w,
          valign='top'),
        C([P(f'رئيس {nom_centre}', align='centre', taille=12, gras=True),
           P(resp, align='centre', taille=12, gras=True)], w, valign='top')])],
        bordure_ext=None, bordure_h=None, bordure_v=None))
    return doc.octets()


def _word_hodour_multi(data, base_dir, jours):
    """V2 — بطاقة حضور d'une دورة متعدّدة الأيّام : une colonne de signature
    par jour + ملاحظات ; portrait jusqu'à 3 jours, paysage de 4 à 6."""
    paysage = len(jours) >= 4
    page = (29.7, 21.0) if paysage else dx.A4
    doc = dx.DocumentWord(marges_cm=(1.0, 1.4, 1.2, 1.4), page=page, titre='بطاقة حضور')
    nom_centre = data.get('nom_centre') or identite.CENTRE_NEUTRE
    ville = (data.get('ville_centre') or '').strip()
    larg_page = page[0] - 2.8
    _entete_word(doc, base_dir, f'{ville} في :' if ville else 'في :',
                 identite.ENTETE_NATIONAL, [nom_centre], larg_page,
                 logo=(1.8, 2.3) if paysage else (2.35, 3.03))
    _titres(doc, 'بطاقة حضور', 20, [
        f'الدورة تكوينيّة حول " {data.get("titre", "")} "',
        f'تحت إشراف {nom_centre}', _date_titre(data, ville)])
    if paysage:
        l_num, l_nom, l_grade, l_obs = 1.1, 5.3, 3.7, 3.1
        t_corps = 11
    else:
        l_num, l_nom, l_grade, l_obs = 1.0, 4.4, 3.3, 2.5
        t_corps = 13
    l_jour = (larg_page - l_num - l_nom - l_grade - l_obs) / len(jours)
    # ordre RTL : ع/ر | الإسم واللقب | الرّتبة | jours… | ملاحظات
    larg = [l_num, l_nom, l_grade] + [l_jour] * len(jours) + [l_obs]
    entetes = [_cell_entete('ع/ر', l_num, BLEU_ENTETE),
               _cell_entete('الإسم واللقب', l_nom, BLEU_ENTETE),
               _cell_entete('الرّتبة', l_grade, BLEU_ENTETE)]
    for j in jours:
        d = datetime.strptime(j['date'], '%Y-%m-%d')
        paras = [P(JOURS[d.weekday()], align='centre',
                   taille=10, gras=True),
                 P(f'{d.day:02d}/{d.month:02d}', align='centre', taille=10, gras=True, ltr=True)]
        if (j.get('periode') or '').strip():
            paras.append(P(f'({j["periode"].strip()})', align='centre', taille=9, gras=True))
        entetes.append(C(paras, l_jour, fond=BLEU_ENTETE, bords={'bas': ('double', 4)}))
    entetes.append(_cell_entete('ملاحظات', l_obs, BLEU_ENTETE))
    lignes = [L(entetes, entete=True)]
    for i, p in enumerate(data.get('participants') or []):
        lignes.append(L([
            C(P(f'{i + 1:02d}', align='centre', taille=12, gras=True), l_num),
            C(P(p.get('nom_prenom', ''), align='centre', taille=t_corps, ligne_pt=t_corps * 1.15), l_nom),
            C(P(p.get('grade', ''), align='centre', taille=t_corps - 1, ligne_pt=t_corps * 1.15), l_grade)]
            + [C(P(''), l_jour) for _ in jours] + [C(P(''), l_obs)],
            hauteur_cm=_px(19.55, K_LISTE)))
    doc.ajouter(dx.tableau(larg, lignes))
    formateur = f'{(data.get("grade_formateur") or "").strip()} ' \
                f'{(data.get("nom_formateur") or "").strip()}'.strip()
    resp = f'{(data.get("titre_responsable") or "").strip()} ' \
           f'{(data.get("nom_responsable") or "").strip()}'.strip()
    w = larg_page / 2
    doc.ajouter(P('', taille=10), dx.tableau([w, w], [L([
        C([P('المكوّن', taille=12, gras=True), P(formateur, taille=12, gras=True)], w,
          valign='top'),
        C([P(f'رئيس {nom_centre}', align='centre', taille=12, gras=True),
           P(resp, align='centre', taille=12, gras=True)], w, valign='top')])],
        bordure_ext=None, bordure_h=None, bordure_v=None))
    return doc.octets()


# ─── 2. برنامج الدورة ────────────────────────────────────────────────────────

def word_programme(data, base_dir):
    doc = dx.DocumentWord(marges_cm=(1.0, 1.5, 1.3, 1.5), titre='برنامج الدّورة التّكوينيّة')
    nom_centre = data.get('nom_centre') or identite.CENTRE_NEUTRE
    ville = (data.get('ville_centre') or '').strip()
    moment = (data.get('moment') or '').strip()
    date_long, date_ligne = data.get('date_formation', ''), ''
    try:
        d = datetime.strptime(data.get('date_formation') or '', '%Y-%m-%d')
        date_long = f'يوم {d.day} {MOIS[d.month - 1]} {d.year}' + (f' ({moment})' if moment else '')
        date_ligne = (f'{ville} يوم {JOURS[d.weekday()]} الموافق لـ '
                      f'{d.day} {MOIS[d.month - 1]} {d.year}').strip()
    except (TypeError, ValueError):
        pass
    lignes_centre = [l.strip() for l in (data.get('entete_centre_1', ''),
                                          data.get('entete_centre_2', ''))
                     if (l or '').strip()] or [nom_centre]
    _entete_word(doc, base_dir, 'فندق الجديد في:', identite.ENTETE_NATIONAL_ORNE,
                 lignes_centre, 18.0)
    jours = [j for j in (data.get('jours') or []) if j.get('date')]
    if len(jours) > 1:
        # V2 : période en titre ; chaque jour a sa ligne de date (et sa فترة)
        date_long = _jours.plage_longue(jours[0]['date'], jours[-1]['date'], 'يوم')
    _titres(doc, 'برنامج الدّورة التّكوينيّة', 20, [
        f'الدّورة التّكوينيّة حول " {data.get("theme", "")} "',
        (data.get('nom_centre_ba') or '').strip() or nom_centre,
        date_long])
    # ordre RTL : التّوقيت | بيان النشّاط | المتدخّلون
    larg = [_px(p, K_PROG) for p in (126, 169, 164)]

    def tableau(ligne_date, rows):
        lignes = [L([_cell_entete(t, w, BLEU_COLONNES) for t, w in zip(
            ('التّوقيت', 'بيان النشّاط', 'المتدخّلون'), larg)], entete=True,
            hauteur_cm=_px(24, K_PROG))]
        if ligne_date:
            lignes.append(L([C(P(ligne_date, align='centre', taille=16, gras=True), sum(larg),
                               fond=BLEU_DATE, colonnes=3, bords={'bas': ('double', 4)})],
                            hauteur_cm=_px(25, K_PROG)))
        for r in rows or []:
            if r.get('type', 'row') == 'date_header':
                continue
            lignes.append(L([
                C(P(r.get('time', ''), align='centre', taille=11, gras=True, interligne=1.5), larg[0]),
                C(P(r.get('activity', ''), align='centre', taille=11, gras=True, interligne=1.5),
                  larg[1]),
                # v1.7.1 : plusieurs متدخّلون (joints par « ، ») → un paragraphe chacun
                C([P(nom, align='centre', taille=11, gras=True, interligne=1.5)
                   for nom in (x.strip() for x in str(r.get('participants', '') or '').split('،'))
                   if nom] or [P('', align='centre', taille=11, gras=True, interligne=1.5)],
                  larg[2], valign='top')],
                hauteur_cm=_px(21, K_PROG)))
        return dx.tableau(larg, lignes)

    if len(jours) > 1:
        # V2 — un tableau par jour, l'un sous l'autre
        for k, j in enumerate(jours):
            d = datetime.strptime(j['date'], '%Y-%m-%d')
            ligne = (f"{_jours.libelle_jour(j['jour'])}: يوم {JOURS[d.weekday()]} الموافق لـ "
                     f'{d.day} {MOIS[d.month - 1]} {d.year}')
            if (j.get('periode') or '').strip():
                ligne += f" ({j['periode'].strip()})"
            if k:
                doc.ajouter(P('', taille=10))
            doc.ajouter(tableau(ligne, j.get('rows')))
    else:
        doc.ajouter(tableau(date_ligne, data.get('rows')))
    return doc.octets()


# ─── 4. البطاقة البيداغوجية ──────────────────────────────────────────────────

def _items(txt):
    if not txt:
        return []
    items = [l.strip(' -•\t') for l in str(txt).splitlines()]
    items = [l for l in items if l]
    if len(items) == 1:
        for sep in ('؛', ';', ' / ', '/'):
            if sep in items[0]:
                return [p.strip() for p in items[0].split(sep) if p.strip()]
    return items


def _puces(items):
    return [P(f'- {it}', taille=12, apres=0, ligne_pt=15.4) for it in items] or [P('')]


def word_bataqa(data, base_dir):
    doc = dx.DocumentWord(marges_cm=(0.9, 1.6, 1.0, 1.6), titre='بطاقة بيداغوجيّة')
    nom_centre = data.get('nom_centre') or identite.CENTRE_NEUTRE
    larg_page = 17.8
    # En-tête : emblème de la ديوانة à droite, logo de l'École à gauche
    w_logo, w_mid = 3.0, larg_page - 6.0
    doc.ajouter(dx.tableau([w_logo, w_mid, w_logo], [L([
        C(doc.image(_logo_douane(base_dir), 2.6, 2.8), w_logo),
        C([P(t, align='centre', taille=12, gras=True) for t in identite.ENTETE_NATIONAL[:4]],
          w_mid),
        C(doc.image(_chemin_image(base_dir, 'logo.jpg'), 2.6, 2.8), w_logo)],
        insecable=False)], bordure_ext=None, bordure_h=None, bordure_v=None))
    doc.ajouter(P('بطاقة بيداغوجيّة', align='centre', taille=13.5, gras=True, avant=4, apres=6))
    doc.ajouter(P(f'دورة تكوينيّة في مجال " {data.get("theme", "")} "', align='centre',
                  taille=11.5, gras=True))
    doc.ajouter(P(nom_centre, align='centre', taille=11.5, gras=True, apres=8))

    def section(titre, entetes, cellules, largeurs):
        if titre:
            doc.ajouter(P([R('•  ', 12, True), R(titre, 12, True)], taille=12, avant=6,
                          apres=4, garder_suivant=True))
        lignes = [L([C(P(t, align='centre', taille=12, gras=True, ligne_pt=14.2), w,
                       fond=GRIS_BATAQA)
                     for t, w in zip(entetes, largeurs)], entete=True),
                  L([C(c, w, valign='top') for c, w in zip(cellules, largeurs)],
                    hauteur_cm=2.2, insecable=False)]
        doc.ajouter(dx.tableau(largeurs, lignes, bordure_ext=('single', 6),
                               bordure_h=('single', 6), bordure_v=('single', 6)))

    date_disp = data.get('date_formation', '')
    try:
        date_disp = datetime.strptime(date_disp, '%Y-%m-%d').strftime('%Y/%m/%d')
    except (TypeError, ValueError):
        pass
    if _jours.est_multi_jours(data.get('date_formation'), data.get('date_fin')):
        date_disp = _jours.plage_slash(data.get('date_formation'), data.get('date_fin'))
    k = larg_page / 466.0         # 466 px = de X(44) à X(510) sur la capture
    # section 1 — ordre RTL : موضوع | المستهدفون | عدد | المصالح | نوع
    section('تقديم الدورة التكوينيّة',
            ['موضوع التكوين', 'المستهدفون بالتكوين', 'عدد المشاركين',
             'المصالح المعنية بالمشاركة', 'نوع التكوين'],
            [[P(data.get('theme', ''), align='centre', taille=12, ligne_pt=15)],
             _puces(_items(data.get('mustahdafun')) or ([data['mustahdafun']]
                                                         if data.get('mustahdafun') else [])),
             [P(str(data.get('nb_participants', 0)), align='centre', taille=12, gras=True)],
             _puces(data.get('services') or []),
             [P(data.get('type_formation', ''), align='centre', taille=12, ligne_pt=15)]],
            [k * 77, k * 152, k * 50, k * 125, k * 62])
    doc.ajouter(P('', taille=8))
    section(None, ['محاور الدورة', 'أهداف الدورة'],
            [_puces(_items(data.get('mahawer'))), _puces(_items(data.get('objectifs')))],
            [k * 230, k * 236])
    section('الإطار المكاني والزماني للدورة التكوينية:', ['مكان التكوين', 'تاريخ الدورة التكوينية'],
            [[P(data.get('lieu_formation', ''), align='centre', taille=12, ligne_pt=15)],
             [P(date_disp, align='centre', taille=12, gras=True,
                ltr=not date_disp.startswith('من '))]],
            [k * 266, k * 200])
    section('الطرق والمعينات البيداغوجية:', ['الطرق البيداغوجية', 'المعينات البيداغوجية'],
            [_puces(_items(data.get('methodes'))), _puces(_items(data.get('moyens')))],
            [k * 228, k * 238])
    section('الإعداد المادّي والتجهيزات والمعدّات الخصوصية:',
            ['الإعداد المادّي', 'التجهيزات والمعدّات الخصوصية'],
            [_puces(_items(data.get('preparation')) or ([data['preparation']]
                                                         if data.get('preparation') else [])),
             [P(data.get('equipements') or 'لاشيئ', align='centre', taille=12, ligne_pt=15)]],
            [k * 233, k * 233])
    return doc.octets()


# ─── 1. المذكّرة ─────────────────────────────────────────────────────────────

def word_memo(data, base_dir):
    doc = dx.DocumentWord(marges_cm=(1.0, 1.6, 1.5, 1.6), titre='مذكّرة')
    # ── En-tête officiel : institution | logo + نوع المراسلة | Réf / Version / Date / Page
    w_inst, w_mid, w_ref = 6.6, 5.0, 6.2
    ref_full = str(data.get('ref') or '')
    pages = data.get('pages')
    sous = dx.tableau([2.9, 3.1], [
        L([C(P('Version', align='centre', taille=12, ltr=True), 2.9),
           C(P('01', align='centre', taille=12, ltr=True), 3.1)]),
        L([C(P('Date', align='centre', taille=12, ltr=True), 2.9),
           C(P('23/09/2024', align='centre', taille=12, ltr=True), 3.1)]),
        L([C(P('Page', align='centre', taille=12, ltr=True), 2.9),
           C(P(f'{int(pages)}/{int(pages)}' if pages else '', align='centre', taille=12,
               ltr=True), 3.1)]),
    ], bordure_ext=('single', 4), bordure_h=('single', 4), bordure_v=('single', 4),
        centre=False, marge_cellule_cm=0.05)
    type_label = 'مراسلة داخلية' if data.get('type') == 'interne' else 'مراسلة خارجية'
    doc.ajouter(dx.tableau([w_inst, w_mid, w_ref], [L([
        C([P(t, align='centre', taille=12) for t in identite.ENTETE_NATIONAL], w_inst,
          valign='center'),
        C([doc.image(_chemin_image(base_dir, 'logo.jpg'), 1.3, 1.65, apres=2),
           P(type_label, align='centre', taille=12, gras=True)], w_mid),
        C([P(f'Réf : {ref_full}', align='centre', taille=12, ltr=True, avant=4, apres=4), sous],
          w_ref, valign='top')], insecable=False)],
        bordure_ext=('single', 4), bordure_h=('single', 4), bordure_v=('single', 4)))
    doc.ajouter(P('فندق الجديد في:', align='gauche', taille=12, avant=4,
                  retrait_fin=3.6))
    doc.ajouter(P([R('مذكّــــرة', 18, True, police='Traditional Arabic')], align='centre',
                  taille=18, avant=2, apres=14))
    objet = (data.get('objet') or '').strip()
    if objet:
        doc.ajouter(P([R('الموضـــــوع:', 14, True, souligne=True), R(' ' + objet, 14)],
                      taille=14, apres=3))
    ms = [str(x).strip() for x in (data.get('msahib') or []) if str(x).strip()]
    if ms:
        doc.ajouter(P([R('المصاحيــب:', 14, True, souligne=True), R(' ' + ms[0], 14)],
                      taille=14, apres=0))
        for it in ms[1:]:
            doc.ajouter(P(it, taille=14, retrait_debut=2.45))
    doc.ajouter(P('', taille=10))
    for par in str(data.get('corps') or '').split('\n'):
        par = par.strip()
        if par:
            doc.ajouter('<w:p><w:pPr><w:bidi/><w:spacing w:before="0" w:after="60" '
                        'w:line="340" w:lineRule="auto"/><w:ind w:firstLine="440"/>'
                        '<w:jc w:val="both"/></w:pPr>' + R(par, 14) + '</w:p>')
        else:
            doc.ajouter(P('', taille=7))
    titre_dg = (data.get('titre_directeur_general') or 'العميد').strip()
    nom_dg = (data.get('nom_directeur_general') or '').strip()
    doc.ajouter(P('', taille=14), P('', taille=14))
    for t in ('المدير العام للمدرسة الوطنيّة للدّيوانة', f'{titre_dg} {nom_dg}'.strip()):
        doc.ajouter(P([R(t, 18, True, police='Traditional Arabic')], align='centre',
                      taille=18, retrait_debut=6.5))
    visible = [((m.get('nom') or '').strip(), (m.get('type') or '').strip())
               for m in (data.get('moujah') or []) if (m.get('nom') or '').strip()]
    if visible:
        doc.ajouter(P('', taille=14), P('', taille=14),
                    P([R('الموجَّه إليهم:', 9.5, True, souligne=True)], taille=9.5, apres=2))
        for nom, typ in visible:
            doc.ajouter(P(f'ـ {nom}، {typ}.' if typ else f'ـ {nom}.', taille=9.5))
    # Pied de page : coordonnées de l'École (comme la مذكّرة PDF)
    email = (data.get('ecole_email') or 'end.dfrs@douane.gov.tn').strip()
    tel = (data.get('ecole_tel') or '72205722').strip()
    fax = (data.get('ecole_fax') or '72205636').strip()
    web = (data.get('ecole_web') or 'www.douane.gov.tn/structures-de-formation').strip()
    adresse = (data.get('ecole_adresse') or
               'المدرسة الوطنيّة للدّيوانة – فندق الجديد – نابل – 8012').strip()
    lignes_pied = [P(t, taille=8) for t in (f'البريد الإلكتروني : {email}',
                                             f'الهاتف : {tel} – الفاكس : {fax}', web, adresse)]
    # v1.7.1 : emblème de l'École en début de ligne (à droite), texte décalé
    # vers la gauche — comme la مذكّرة PDF. Tableau sans bordure à 2 colonnes.
    logo = doc.image_inline(_chemin_image(base_dir, 'logo.jpg'), 1.1, 1.4)
    if logo:
        doc.pied = [dx.tableau([1.5, 15.0], [L([
            C([P([logo], align='centre', taille=6)], 1.5),
            C(lignes_pied, 15.0)])], bordure_ext=None, bordure_h=None, bordure_v=None,
            centre=False, marge_cellule_cm=0.05), P('', taille=2)]
    else:
        doc.pied = lignes_pied
    return doc.octets()


# ─── L'archive ───────────────────────────────────────────────────────────────

PIECES = (
    ('memo', '1_المذكرة.docx', 'المذكّرة', 'المذكّرة غير مؤكّدة بعد'),
    ('programme', '2_برنامج_الدورة.docx', 'برنامج الدورة', 'برنامج الدورة غير مؤكّد بعد'),
    ('participants', '3_القائمة_الإسمية_للمشاركين.docx', 'القائمة الإسمية للمشاركين',
     'لم يُسجَّل أيّ مشارك بعد'),
    ('bataqa', '4_البطاقة_البيداغوجية.docx', 'البطاقة البيداغوجية',
     'البطاقة البيداغوجية غير مؤكّدة بعد'),
    ('hodour', '5_بطاقة_الحضور.docx', 'بطاقة الحضور', 'لم يُسجَّل أيّ مشارك بعد'),
)


def pieces_disponibles(lettre_id, formation_id, base_dir, etat=None):
    """{clé: (nom_fichier, octets) | (nom_fichier, None, motif)} pour les cinq pièces."""
    from core import dossier_dorra as dd
    from core.database import etat_dorra
    etat = etat or etat_dorra(formation_id)
    res = {}
    for cle, nom, _libelle, motif in PIECES:
        try:
            if cle == 'memo':
                donnees = dd.donnees_memo(lettre_id, formation_id)
                if donnees:
                    donnees['pages'] = dd.pages_du_dossier(lettre_id, formation_id,
                                                           donnees, base_dir)
                    res[cle] = (nom, word_memo(donnees, base_dir))
            elif cle == 'programme':
                donnees = dd.donnees_programme(lettre_id, formation_id)
                if donnees:
                    res[cle] = (nom, word_programme(donnees, base_dir))
            elif cle == 'participants' and etat.get('participants'):
                res[cle] = (nom, word_participants(
                    dd.donnees_participants(lettre_id, formation_id), base_dir))
            elif cle == 'bataqa' and etat.get('bataqa'):
                donnees = dd.donnees_bataqa(lettre_id, formation_id)
                if donnees:
                    res[cle] = (nom, word_bataqa(donnees, base_dir))
            elif cle == 'hodour' and etat.get('participants'):
                res[cle] = (nom, word_hodour(
                    dd.donnees_hodour(lettre_id, formation_id), base_dir))
        except Exception as e:  # une pièce en échec n'empêche pas les autres
            import logging
            logging.getLogger('formation.' + __name__).exception(f'pièce {cle} : {e}')
            res[cle] = (nom, None, f'تعذّر إعداد الوثيقة ({e.__class__.__name__})')
        if cle not in res:
            res[cle] = (nom, None, motif)
    return res


def archive_dorra(lettre_id, formation_id, base_dir, titre=''):
    """(octets du ZIP, liste des pièces absentes [(libellé, motif)]).
    Lève LookupError si aucune pièce n'est encore disponible."""
    pieces = pieces_disponibles(lettre_id, formation_id, base_dir)
    absentes = [(lib, pieces[cle][2]) for cle, _n, lib, _m in PIECES if pieces[cle][1] is None]
    if len(absentes) == len(PIECES):
        raise LookupError('لا توجد أيّ وثيقة جاهزة بعد لهذه الدورة')
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as z:
        for cle, _n, _lib, _m in PIECES:
            if pieces[cle][1] is not None:
                z.writestr(pieces[cle][0], pieces[cle][1])
        if absentes:
            texte = ['ملفّ الدورة: ' + (titre or ''), '',
                     'الوثائق التالية غير موجودة في هذا الملفّ لأنّها لم تكتمل بعد:', '']
            texte += [f'- {lib}: {motif}' for lib, motif in absentes]
            texte += ['', 'أعد تحميل الملفّ بعد استكمالها.']
            # BOM : le Bloc-notes de Windows lit l'arabe sans ambiguïté
            z.writestr('ملاحظة.txt', '﻿' + '\r\n'.join(texte))
    return buf.getvalue(), absentes
