# -*- coding: utf-8 -*-
"""Les trois pièces « Word » : القائمة الإسمية, بطاقة الحضور, برنامج الدورة.

v1.7 : extrait tel quel de core/pdf_generator.py, qui reste la façade
(`from core.pdf_generator import generer_…` fonctionne comme avant) et
garde les outils communs (polices, arabe, en-têtes, tableaux)."""

from core import chemins
from core import identite
from core import jours as _jours
from datetime import datetime
from reportlab.pdfgen import canvas

from core.pdf_generator import (  # noqa: E402 — outils communs
    A4_H, A4_W, BLACK, BLEU_COLONNES, BLEU_DATE, BLEU_ENTETE, F_AR, F_ARB, JOURS_AR_W,
    MOIS_AR_W, SW_CORPS, SW_ENTETE, SW_LIBELLE, SW_NUM, SW_PIED, SW_PROG, SW_SOUS,
    TRAIT_BLANC, TRAIT_EPAIS, TRAIT_FIN, TRAIT_SIMPLE, _ListeWord, _Releve, _arh,
    _bloc_institution, _date_arabe, _double_h, _double_v, _groupes_fusion,
    _lignes_titre, _logo_ecole, _paginer, _register_fonts, _simple_h, _wrap_h,
)


def _date_titre(pdf_data, ville):
    """Ligne de date des listes : « القصرين في 14 أكتوبر 2026 » ; V2 — pour une
    دورة متعدّدة الأيّام : « القصرين في الفترة من 14 إلى 16 أكتوبر 2026 »."""
    debut, fin = pdf_data.get('date_formation', ''), pdf_data.get('date_fin', '')
    if _jours.est_multi_jours(debut, fin):
        txt = f'في الفترة {_jours.plage_longue(debut, fin)}'
        return f'{ville} {txt}'.strip() if ville else txt
    return _date_arabe(debut, ville, pdf_data.get('mois', ''),
                       pdf_data.get('annee', datetime.now().year))


# ══════════════════════════════════════════════════════════════════════════════
#  GÉNÉRATEUR LISTE DES PARTICIPANTS (قائمة المشاركين)
# ══════════════════════════════════════════════════════════════════════════════

def generer_pdf_participants(pdf_data: dict, base_dir: str) -> str:
    """قائمة المشاركين — document Word officiel, relevé au pixel (A4).

    Colonnes (de gauche à droite) : مكان العمل | المعرّف الوحيد | الرّتبة |
    الإسم واللقب | ع/ر. Des مكان العمل identiques et consécutifs sont fusionnés
    dans une seule cellule, comme sur le modèle."""
    _register_fonts(base_dir)
    output_path = chemins.chemin_pdf_transitoire('participants')
    c = canvas.Canvas(output_path, pagesize=(A4_W, A4_H))

    titre        = pdf_data.get('titre', '')
    nom_centre   = pdf_data.get('nom_centre') or identite.CENTRE_NEUTRE
    participants = pdf_data.get('participants', []) or []
    date_ar = _date_titre(pdf_data, (pdf_data.get('ville_centre') or '').strip())

    R = _Releve(1.0732, -5.2, 0.5)
    L = _ListeWord(
        c, base_dir, R,
        titre='قائمة المشاركين', taille_titre=18.0,
        sous_titres=[f'الدورة تكوينيّة حول " {titre} "',
                     f'تحت إشراف {nom_centre}', date_ar],
        cx_titre=R.x(270.0), cx_sous=[R.x(269.5), R.x(277.5), R.x(279.5)],
        y_titre_px=257.5, y_sous_px=[283.7, 307.7, 331.7],
        libelle='فندق الجديد في :', x_libelle=R.x(170),
        cols_px=[21, 224, 310, 387, 496, 523],
        entetes=['مكان العمل', 'المعرّف الوحيد', 'الرّتبة', 'الإسم واللقب', 'ع/ر'],
        y_table_px=363, inst_droite_px=512, inst_haut_px=20,
        logo_px=(234, 137, 62, 80),
        lignes_nat=identite.ENTETE_NATIONAL, lignes_centre=[nom_centre],
        bas_page=50.0)

    lignes = []
    for idx, p in enumerate(participants or [{}], 1):
        lignes.append({
            'lieu': str(p.get('lieu_travail', '') or '').strip(),
            'cells': [None,
                      L.decouper(1, p.get('identifiant_unique', '')),
                      L.decouper(2, p.get('grade', '')),
                      L.decouper(3, p.get('nom_prenom', '')),
                      [f'{idx:02d}'] if participants else []],
        })

    def hauteur(ln):
        n = max([1] + [len(x) for x in ln['cells'][1:4]])
        return L.pas + (n - 1) * L.lead

    def hauteurs_page(ids):
        """Hauteurs des lignes d'une page, cellules fusionnées comprises."""
        hs = [hauteur(lignes[i]) for i in ids]
        for a, b in _groupes_fusion([lignes[i]['lieu'] for i in ids]):
            n = max(1, len(L.decouper(0, lignes[ids[a]]['lieu'], reduire=(a == b))))
            besoin = L.pas + (n - 1) * L.lead
            manque = besoin - sum(hs[a:b + 1])
            if manque > 0:
                hs[b] += manque
        return hs

    dispo = L.haut_table() - R.d(23) - L.bas_page
    pages = _paginer(hauteurs_page(list(range(len(lignes)))), dispo, dispo)

    for n_page, ids in enumerate(pages):
        if n_page:
            c.showPage()
        y_table = L.en_tete_page()
        y = L.en_tete_tableau(y_table, BLEU_ENTETE)
        hs = hauteurs_page(ids)
        x0, x1 = L.vx[0], L.vx[-1] + R.d(4)
        tops = []
        for i, h in zip(ids, hs):
            tops.append(y)
            ln = lignes[i]
            for col in (1, 2, 3):
                if ln['cells'][col]:
                    L.texte_cellule(col, ln['cells'][col], y, y - h, F_AR, SW_CORPS)
            if ln['cells'][4]:
                L.texte_cellule(4, ln['cells'][4], y, y - h, F_ARB, SW_NUM)
            y -= h
        bas = y
        # Séparateurs : simples entre les lignes ; la colonne مكان العمل n'en a
        # pas à l'intérieur d'un groupe fusionné.
        groupes = _groupes_fusion([lignes[i]['lieu'] for i in ids])
        fin_groupe = {b for a, b in groupes}
        for k, (i, h) in enumerate(zip(ids, hs)):
            y_bas = tops[k] - h
            _simple_h(c, L.col(0)[1], x1, y_bas)
            if k in fin_groupe:
                _simple_h(c, x0, L.col(0)[1], y_bas)
        for a, b in groupes:
            texte = lignes[ids[a]]['lieu']
            if texte:
                # cellule fusionnée : le texte passe à la ligne, comme sur le
                # modèle ; cellule simple : il se réduit d'abord (≥ 12 pt)
                L.texte_cellule(0, L.decouper(0, texte, reduire=(a == b)),
                                tops[a], tops[b] - hs[b],
                                F_AR, SW_CORPS, centre=True)
        L.cadre(y_table, bas - TRAIT_SIMPLE)

    c.save()
    return output_path


# ══════════════════════════════════════════════════════════════════════════════
#  بطاقة حضور — pièce autonome (hors numérotation du dossier)
# ══════════════════════════════════════════════════════════════════════════════

def generer_pdf_bataqa_hodour(pdf_data: dict, base_dir: str) -> str:
    """بطاقة حضور — document Word officiel, relevé au pixel (A4).

    Même en-tête que la قائمة المشاركين ; tableau à quatre colonnes dont la
    dernière (الإمضاء) reste vide pour la signature ; pied à deux blocs :
    المكوّن à droite, رئيس المركز à gauche. Hors comptage des feuillets."""
    # V2 — دورة متعدّدة الأيّام : une colonne de signature par jour.
    jours = [j for j in (pdf_data.get('jours') or []) if j.get('date')]
    if len(jours) > 1:
        return _generer_hodour_multi(pdf_data, base_dir, jours)
    _register_fonts(base_dir)
    output_path = chemins.chemin_pdf_transitoire('hodour')
    c = canvas.Canvas(output_path, pagesize=(A4_W, A4_H))

    titre        = pdf_data.get('titre', '')
    nom_centre   = pdf_data.get('nom_centre') or identite.CENTRE_NEUTRE
    participants = pdf_data.get('participants', []) or []
    nom_form     = (pdf_data.get('nom_formateur') or '').strip()
    grade_form   = (pdf_data.get('grade_formateur') or '').strip()
    titre_resp   = (pdf_data.get('titre_responsable') or '').strip()
    nom_resp     = (pdf_data.get('nom_responsable') or '').strip()
    ville        = (pdf_data.get('ville_centre') or '').strip()
    date_ar = _date_arabe(pdf_data.get('date_formation', ''), ville,
                          pdf_data.get('mois', ''),
                          pdf_data.get('annee', datetime.now().year))

    R = _Releve(1.0732, -5.2, 1.5)
    L = _ListeWord(
        c, base_dir, R,
        titre='بطاقة حضور', taille_titre=20.0,
        sous_titres=[f'الدورة تكوينيّة حول " {titre} "',
                     f'تحت إشراف {nom_centre}', date_ar],
        cx_titre=R.x(271.0), cx_sous=[R.x(273.0), R.x(273.0), R.x(280.5)],
        y_titre_px=207.5, y_sous_px=[233.7, 257.7, 281.7],
        libelle=f'{ville} في :' if ville else 'في :', x_libelle=R.x(163),
        cols_px=[81, 245, 322, 431, 458],
        entetes=['الإمضاء', 'الرّتبة', 'الإسم واللقب', 'ع/ر'],
        y_table_px=290, inst_droite_px=486, inst_haut_px=27,
        logo_px=(236, 85, 62, 80),
        lignes_nat=identite.ENTETE_NATIONAL, lignes_centre=[nom_centre],
        bas_page=50.0)

    lignes = []
    for idx, p in enumerate(participants or [{}], 1):
        lignes.append([[],
                       L.decouper(1, p.get('grade', '')),
                       L.decouper(2, p.get('nom_prenom', '')),
                       [f'{idx:02d}'] if participants else []])
    hs_all = [L.pas + (max([1] + [len(x) for x in ln[1:3]]) - 1) * L.lead
              for ln in lignes]

    PIED = R.d(50)          # du bas du tableau à la 2e ligne du pied, + marge
    dispo = L.haut_table() - R.d(23) - L.bas_page
    pages = _paginer(hs_all, dispo, dispo, reserve_fin=PIED)

    bas = 0.0
    for n_page, ids in enumerate(pages):
        if n_page:
            c.showPage()
        y_table = L.en_tete_page()
        y = L.en_tete_tableau(y_table, BLEU_ENTETE)
        x0, x1 = L.vx[0], L.vx[-1] + R.d(4)
        for i in ids:
            h = hs_all[i]
            ln = lignes[i]
            for col in (1, 2):
                if ln[col]:
                    L.texte_cellule(col, ln[col], y, y - h, F_AR, SW_CORPS)
            if ln[3]:
                L.texte_cellule(3, ln[3], y, y - h, F_ARB, SW_NUM)
            y -= h
            _simple_h(c, x0, x1, y)
        bas = y
        L.cadre(y_table, bas - TRAIT_SIMPLE)

    # Pied : المكوّن à droite ; رئيس المركز à gauche (deux lignes centrées).
    c.setFillColor(BLACK)
    c.setFont(F_ARB, SW_PIED)
    b1, b2 = bas - R.d(29.5), bas - R.d(46.5)
    c.drawCentredString(R.x(160.0), b1, _arh(f'رئيس {nom_centre}'))
    if titre_resp or nom_resp:
        c.drawCentredString(R.x(165.0), b2, _arh(f'{titre_resp} {nom_resp}'.strip()))
    c.drawRightString(R.x(459), b1, _arh('المكوّن'))
    formateur = f'{grade_form} {nom_form}'.strip()
    if formateur:
        c.drawRightString(R.x(459), b2, _arh(formateur))
    c.save()
    return output_path


# ── V2 : بطاقة حضور d'une دورة متعدّدة الأيّام ──────────────────────────────
#
# Même document que la بطاقة حضور d'un jour (bloc institution, logo, titres,
# en-têtes #5B9BD5, bordures doubles, pied المكوّن / رئيس المركز), avec UNE
# colonne de signature par jour et une colonne ملاحظات :
#   · 2 ou 3 jours  → A4 portrait, colonnes aux largeurs habituelles ;
#   · 4 à 6 jours   → A4 paysage, colonnes الرتبة / الاسم / ملاحظات réduites
#     pour loger jusqu'à six jours (du lundi au samedi).

def _generer_hodour_multi(pdf_data, base_dir, jours):
    _register_fonts(base_dir)
    output_path = chemins.chemin_pdf_transitoire('hodour')
    paysage = len(jours) >= 4
    W, H = (A4_H, A4_W) if paysage else (A4_W, A4_H)
    c = canvas.Canvas(output_path, pagesize=(W, H))

    titre        = pdf_data.get('titre', '')
    nom_centre   = pdf_data.get('nom_centre') or identite.CENTRE_NEUTRE
    participants = pdf_data.get('participants', []) or []
    nom_form     = (pdf_data.get('nom_formateur') or '').strip()
    grade_form   = (pdf_data.get('grade_formateur') or '').strip()
    titre_resp   = (pdf_data.get('titre_responsable') or '').strip()
    nom_resp     = (pdf_data.get('nom_responsable') or '').strip()
    ville        = (pdf_data.get('ville_centre') or '').strip()
    date_ar      = _date_titre(pdf_data, ville)

    # ── Géométrie (points, depuis le HAUT de la page) ───────────────────────
    k = 1.0732
    if paysage:
        G = dict(inst_x=W - 40, inst_y=30.0, inst_pas=13.2, lib_x=190.0, lib_y=31.0,
                 logo=(W / 2 - 26, 16.0, 52.0, 67.0), titre_y=104.0, titre_s=20.0,
                 sous_y=128.0, sous_pas=21.0, table_y=194.0,
                 x_g=40.0, x_d=W - 40)
        # الإمضاء par jour | ملاحظات | الرتبة | الإسم | ع/ر (largeurs, pt)
        l_num, l_nom, l_grade, l_obs = 30.0, 150.0, 105.0, 88.0
        taille_corps, taille_min = 12.0, 9.0
    else:
        G = dict(inst_x=(486 + 5.2) * k, inst_y=(35 - 1.5) * k, inst_pas=13.17 * k,
                 lib_x=(163 + 5.2) * k, lib_y=(36 - 1.5) * k,
                 logo=((236 + 5.2) * k, (85 - 1.5) * k, 62 * k, 80 * k),
                 titre_y=(207.5 - 1.5) * k, titre_s=20.0,
                 sous_y=(233.7 - 1.5) * k, sous_pas=24 * k, table_y=(290 - 1.5) * k,
                 x_g=42.0, x_d=A4_W - 42.0)
        l_num, l_nom, l_grade, l_obs = 29.0, 125.0, 95.0, 72.0
        taille_corps, taille_min = 14.0, 10.0
    Y = lambda t: H - t                                   # noqa: E731
    cx = (G['x_g'] + G['x_d']) / 2
    n = len(jours)
    l_jour = (G['x_d'] - G['x_g'] - l_num - l_nom - l_grade - l_obs) / n
    # Bords gauches des colonnes, de gauche à droite (ordre visuel RTL) :
    # ملاحظات, jour n … jour 1, الرتبة, الإسم واللقب, ع/ر
    largeurs = [l_obs] + [l_jour] * n + [l_grade, l_nom, l_num]
    vx = [G['x_g']]
    for w in largeurs:
        vx.append(vx[-1] + w)
    D = 4 * k                                             # épaisseur d'une double
    COL = lambda i: (vx[i] + D, vx[i + 1])                # noqa: E731
    i_obs, i_grade, i_nom, i_num = 0, n + 1, n + 2, n + 3
    i_jour = lambda j: n - j + 1                          # jour 1 → à droite  # noqa: E731

    pas = 19.55 * k
    lead = taille_corps * 1.15
    H_ENT = 44.0                                          # en-tête : 3 lignes

    def ajuster(texte, i, font=F_AR):
        """(lignes visuelles, taille) : réduit jusqu'au plancher, puis coupe."""
        a, b = COL(i)
        texte = str(texte or '').strip()
        if not texte:
            return [], taille_corps
        s = taille_corps
        while s > taille_min and c.stringWidth(_arh(texte), font, s) > b - a - 5:
            s -= 0.5
        if c.stringWidth(_arh(texte), font, s) <= b - a - 5:
            return [_arh(texte)], s
        return _wrap_h(c, texte, font, s, b - a - 5), s

    lignes = []
    for idx, p in enumerate(participants or [{}], 1):
        nom, s_nom = ajuster(p.get('nom_prenom', ''), i_nom)
        grade, s_gr = ajuster(p.get('grade', ''), i_grade)
        h = pas + (max(1, len(nom), len(grade)) - 1) * lead
        lignes.append({'nom': (nom, s_nom), 'grade': (grade, s_gr), 'h': h,
                       'num': f'{idx:02d}' if participants else ''})

    def en_tete_page():
        c.setFillColor(BLACK)
        c.setFont(F_ARB, SW_LIBELLE)
        c.drawRightString(G['lib_x'], Y(G['lib_y']), _arh(f'{ville} في :' if ville else 'في :'))
        _bloc_institution(c, identite.ENTETE_NATIONAL, [nom_centre],
                          G['inst_x'], Y(G['inst_y']), G['inst_pas'])
        lx, ly, lw, lh = G['logo']
        _logo_ecole(c, base_dir, lx, Y(ly), lw, lh)
        c.setFillColor(BLACK)
        c.setFont(F_ARB, G['titre_s'])
        c.drawCentredString(cx, Y(G['titre_y']), _arh('بطاقة حضور'))
        decal = 0.0
        for i, texte in enumerate((f'الدورة تكوينيّة حول " {titre} "',
                                   f'تحت إشراف {nom_centre}', date_ar)):
            ls, sz = _lignes_titre(c, texte, F_ARB, SW_SOUS, G['x_d'] - G['x_g'] - 20)
            c.setFont(F_ARB, sz)
            for m, ln in enumerate(ls):
                c.drawCentredString(cx, Y(G['sous_y'] + i * G['sous_pas']) - decal
                                    - m * G['sous_pas'], ln)
            decal += (len(ls) - 1) * G['sous_pas']
        return Y(G['table_y']) - decal

    def texte_centre(i, ls, y_haut, y_bas, font, size, lead_=None):
        a, b = COL(i)
        lead_ = lead_ or size * 1.15
        base = (y_haut + y_bas) / 2 - 0.30 * size + (len(ls) - 1) * lead_ / 2
        c.setFont(font, size)
        c.setFillColor(BLACK)
        for ln in ls:
            c.drawCentredString((a + b) / 2, base, ln)
            base -= lead_

    def en_tete_tableau(y_haut):
        x0, x1 = vx[0], vx[-1] + D
        y_bas = y_haut - H_ENT
        for i in range(len(largeurs)):
            a, b = COL(i)
            c.setFillColor(BLEU_ENTETE)
            c.rect(a, y_bas, b - a, y_haut - D - y_bas, stroke=0, fill=1)
        fixes = {i_num: 'ع/ر', i_nom: 'الإسم واللقب', i_grade: 'الرّتبة', i_obs: 'ملاحظات'}
        for i, t in fixes.items():
            a, b = COL(i)
            ls, sz = _lignes_titre(c, t, F_ARB, SW_ENTETE, b - a - 4, plancher=8)
            texte_centre(i, ls[:1], y_haut - D, y_bas, F_ARB, sz)
        for j in jours:
            dj = datetime.strptime(j['date'], '%Y-%m-%d')
            ls = [_arh(JOURS_AR_W[dj.weekday()]), f'{dj.day:02d}/{dj.month:02d}']
            per = (j.get('periode') or '').strip()
            if per:
                ls.append(_arh(f'({per})'))
            i = i_jour(j['jour'])
            a, b = COL(i)
            sz = SW_ENTETE if not paysage else 10.5
            while sz > 8 and max(c.stringWidth(x, F_ARB, sz) for x in ls) > b - a - 4:
                sz -= 0.5
            texte_centre(i, ls, y_haut - D, y_bas, F_ARB, sz, lead_=sz * 1.12)
        _double_h(c, x0, x1, y_haut)
        _double_h(c, x0, x1, y_bas)
        return y_bas - D

    PIED = 50 * k
    decal_titres = sum((len(_lignes_titre(c, t, F_ARB, SW_SOUS, G['x_d'] - G['x_g'] - 20)[0]) - 1)
                       * G['sous_pas'] for t in (f'الدورة تكوينيّة حول " {titre} "',
                                                 f'تحت إشراف {nom_centre}', date_ar))
    dispo = Y(G['table_y']) - decal_titres - H_ENT - D - 50.0
    pages = _paginer([ln['h'] for ln in lignes], dispo, dispo, reserve_fin=PIED)

    bas = 0.0
    for n_page, ids in enumerate(pages):
        if n_page:
            c.showPage()
        y_table = en_tete_page()
        y = en_tete_tableau(y_table)
        x0, x1 = vx[0], vx[-1] + D
        for i in ids:
            ln = lignes[i]
            h = ln['h']
            ls, sz = ln['nom']
            if ls:
                texte_centre(i_nom, ls, y, y - h, F_AR, sz)
            ls, sz = ln['grade']
            if ls:
                texte_centre(i_grade, ls, y, y - h, F_AR, sz)
            if ln['num']:
                texte_centre(i_num, [ln['num']], y, y - h, F_ARB, SW_NUM)
            y -= h
            _simple_h(c, x0, x1, y)
        bas = y
        for x in vx:
            _double_v(c, x, bas - TRAIT_SIMPLE, y_table)

    # Pied : المكوّن à droite ; رئيس المركز à gauche (deux lignes).
    c.setFillColor(BLACK)
    c.setFont(F_ARB, SW_PIED)
    b1, b2 = bas - 29.5 * k, bas - 46.5 * k
    xg = G['x_g'] + (G['x_d'] - G['x_g']) * 0.22
    c.drawCentredString(xg, b1, _arh(f'رئيس {nom_centre}'))
    if titre_resp or nom_resp:
        c.drawCentredString(xg, b2, _arh(f'{titre_resp} {nom_resp}'.strip()))
    c.drawRightString(G['x_d'] - 8, b1, _arh('المكوّن'))
    formateur = f'{grade_form} {nom_form}'.strip()
    if formateur:
        c.drawRightString(G['x_d'] - 8, b2, _arh(formateur))
    c.save()
    return output_path


# ══════════════════════════════════════════════════════════════════════════════
#  ÉTAPE 5 — برنامج الدّورة التّكوينيّة
# ══════════════════════════════════════════════════════════════════════════════

def generer_pdf_programme(pdf_data: dict, base_dir: str) -> str:
    """برنامج الدّورة التّكوينيّة — document Word officiel, relevé au pixel (A4).

    Tableau : التّوقيت | بيان النشّاط | المتدخّلون (de droite à gauche), en-tête
    des colonnes sur fond #B4C6E7, ligne de date pleine largeur sur #D9E2F3,
    corps en Arial gras 9 (المتدخّلون aligné en haut, les autres centrés).
    Un programme trop long continue sur une page nouvelle, l'en-tête des
    colonnes y étant répété."""
    _register_fonts(base_dir)
    output_path = chemins.chemin_pdf_transitoire('programme')
    c = canvas.Canvas(output_path, pagesize=(A4_W, A4_H))

    # Capture : page A4 de 781 px de haut, bord gauche à 2,5 px.
    R = _Releve(1.078, 2.5, 0.5)

    theme      = pdf_data.get('theme', '')
    date_form  = pdf_data.get('date_formation', '')
    moment     = (pdf_data.get('moment') or '').strip()
    rows       = pdf_data.get('rows', []) or []
    nom_centre = pdf_data.get('nom_centre') or identite.CENTRE_NEUTRE
    ville      = (pdf_data.get('ville_centre') or '').strip()

    date_long, date_ligne = date_form, ''
    try:
        d = datetime.strptime(date_form, '%Y-%m-%d')
        # Ligne de titre : sans jour de semaine ; la فترة n'apparaît entre
        # parenthèses que si elle a réellement été choisie.
        date_long = f"يوم {d.day} {MOIS_AR_W[d.month - 1]} {d.year}"
        if moment:
            date_long += f" ({moment})"
        # Ligne de date du tableau : ville + jour de semaine, sans moment
        date_ligne = (f"{ville} يوم {JOURS_AR_W[d.weekday()]} الموافق لـ "
                      f"{d.day} {MOIS_AR_W[d.month - 1]} {d.year}").strip()
    except Exception:
        pass
    # V2 — دورة متعدّدة الأيّام : la période en titre (sans فترة : chaque jour
    # a la sienne, écrite sur sa ligne de date).
    jours = [j for j in (pdf_data.get('jours') or []) if j.get('date')]
    if len(jours) > 1:
        date_long = _jours.plage_longue(jours[0]['date'], jours[-1]['date'], 'يوم')

    def ligne_de_jour(j):
        """« اليوم الأوّل: يوم الاثنين الموافق لـ 14 أكتوبر 2026 (صباحا) »."""
        dj = datetime.strptime(j['date'], '%Y-%m-%d')
        txt = (f"{_jours.libelle_jour(j['jour'])}: يوم {JOURS_AR_W[dj.weekday()]} "
               f"الموافق لـ {dj.day} {MOIS_AR_W[dj.month - 1]} {dj.year}")
        per = (j.get('periode') or '').strip()
        return txt + (f' ({per})' if per else '')

    # ── En-tête ─────────────────────────────────────────────────────────────
    lignes_centre = [l.strip() for l in (pdf_data.get('entete_centre_1', ''),
                                          pdf_data.get('entete_centre_2', ''))
                     if (l or '').strip()] or [nom_centre]
    c.setFillColor(BLACK)
    c.setFont(F_ARB, SW_LIBELLE)
    c.drawRightString(R.x(175), R.y(31.4), _arh('فندق الجديد في:'))
    _bloc_institution(c, identite.ENTETE_NATIONAL_ORNE, lignes_centre,
                      R.x(511), R.y(30.7), R.d(13.4))
    _logo_ecole(c, base_dir, R.x(243), R.y(118), R.d(62), R.d(80))

    c.setFillColor(BLACK)
    c.setFont(F_ARB, 20.0)
    c.drawCentredString(R.x(266), R.y(236.5), _arh('برنامج الدّورة التّكوينيّة'))
    # Nom du centre précédé de la préposition « بـ » — jamais dérivé ici : la
    # forme correcte (« ببنزرت », « بالقصرين ») est saisie par le centre.
    centre_disp = (pdf_data.get('nom_centre_ba') or '').strip() or nom_centre
    decal = 0.0
    for texte, cx, ypx in ((f'الدّورة التّكوينيّة حول " {theme} "', R.x(266), 262.7),
                           (centre_disp, R.x(266), 286.7),
                           (date_long, R.x(276), 310.7)):
        marge = min(cx, A4_W - cx) - 24
        lignes, s = _lignes_titre(c, texte, F_ARB, SW_SOUS, 2 * marge)
        c.setFont(F_ARB, s)
        for i, ln in enumerate(lignes):
            c.drawCentredString(cx, R.y(ypx) - decal - i * R.d(24), ln)
        decal += (len(lignes) - 1) * R.d(24)

    # ── Tableau ─────────────────────────────────────────────────────────────
    vx = [R.x(p) for p in (59, 223, 392, 514)]   # bord gauche des bordures
    X0, X1 = vx[0], vx[-1] + R.d(4)
    COLS = [(vx[i] + R.d(4), vx[i + 1]) for i in range(3)]
    # v1.7.1 : police du corps 9 → 11 pt ; interligne et hauteur minimale
    # suivent la même proportion (1,5 ligne comme dans le modèle Word).
    LEAD = R.d(18)                                # Word : interligne 1,5
    H_MIN = R.d(24)
    MARGE_BAS = 50.0
    HAUT_SUITE = A4_H - 56.7                      # haut du tableau, pages suivantes

    def cellule(i, lignes, y_haut, y_bas, font, size, haut=False):
        a, b = COLS[i]
        c.setFont(font, size)
        c.setFillColor(BLACK)
        n = len(lignes)
        if haut:
            base = y_haut - R.d(14)
        else:
            base = (y_haut + y_bas) / 2 - 0.30 * size + (n - 1) * LEAD / 2
        for ln in lignes:
            c.drawCentredString((a + b) / 2, base, ln)
            base -= LEAD

    def rangee_entete(y_haut):
        """En-tête des colonnes (fond #B4C6E7) ; renvoie le bas de sa bordure."""
        y_bas = y_haut - R.d(24)
        for a, b in COLS:
            c.setFillColor(BLEU_COLONNES)
            c.rect(a, y_bas, b - a, y_haut - R.d(4) - y_bas, stroke=0, fill=1)
        for i, t in enumerate(('المتدخّلون', 'بيان النشّاط', 'التّوقيت')):
            cellule(i, [_arh(t)], y_haut - R.d(4), y_bas, F_ARB, SW_ENTETE)
        _double_h(c, X0, X1, y_haut)
        _double_h(c, X0, X1, y_bas)
        return y_bas - R.d(4)

    def rangee_date(y_haut, texte=None):
        texte = date_ligne if texte is None else texte
        y_bas = y_haut - R.d(25)
        c.setFillColor(BLEU_DATE)
        c.rect(COLS[0][0], y_bas, COLS[2][1] - COLS[0][0], y_haut - y_bas,
               stroke=0, fill=1)
        lignes, s = _lignes_titre(c, texte, F_ARB, SW_SOUS,
                                  COLS[2][1] - COLS[0][0] - 8)
        c.setFont(F_ARB, s)
        c.setFillColor(BLACK)
        c.drawCentredString((COLS[0][0] + COLS[2][1]) / 2,
                            (y_haut + y_bas) / 2 - 0.30 * s, lignes[0])
        _double_h(c, X0, X1, y_bas)
        return y_bas - R.d(4)

    # Lignes du corps (les anciennes lignes « date_header » sont ignorées).
    def corps_de(lignes_src):
        corps = []
        for r in lignes_src:
            if r.get('type', 'row') == 'date_header':
                continue
            cells = []
            for i, cle in enumerate(('participants', 'activity', 'time')):
                a, b = COLS[i]
                t = str(r.get(cle, '') or '').strip()
                if cle == 'participants' and '،' in t:
                    # v1.7.1 : plusieurs متدخّلون (joints par « ، ») → un par ligne
                    lignes_c = []
                    for nom in (x.strip() for x in t.split('،')):
                        if nom:
                            lignes_c += _wrap_h(c, nom, F_ARB, SW_PROG, b - a - 6)
                    cells.append(lignes_c)
                    continue
                cells.append(_wrap_h(c, t, F_ARB, SW_PROG, b - a - 6) if t else [])
            n = max([1] + [len(x) for x in cells])
            corps.append((cells, max(H_MIN, n * LEAD + R.d(3))))
        return corps

    def verticales(y_bas, y_haut, saut=None):
        """Bordures verticales ; `saut` = (bas, haut) de la ligne de date, cellule
        fusionnée sur toute la largeur : seuls les bords extérieurs la longent."""
        for i, x in enumerate(vx):
            if saut and 0 < i < len(vx) - 1:
                _double_v(c, x, saut[1], y_haut)
                _double_v(c, x, y_bas, saut[0])
            else:
                _double_v(c, x, y_bas, y_haut)

    def tableau(y_haut_table, ligne_date, corps):
        """Un tableau complet (en-tête, ligne de date, فقرات), continué sur la
        page suivante s'il le faut. Rend le bas de sa bordure double."""
        y = rangee_entete(y_haut_table)
        saut = None
        if ligne_date:
            y_date = y
            y = rangee_date(y, ligne_date)
            # de la bordure double supérieure de la ligne de date à sa bordure basse
            saut = (y + R.d(4), y_date + R.d(4) - (TRAIT_EPAIS + TRAIT_BLANC + TRAIT_FIN))
        for k, (cells, h) in enumerate(corps):
            if y - h < MARGE_BAS:
                # Fin de page : le tableau continue sur la page suivante.
                verticales(y, y_haut_table, saut)
                saut = None
                c.showPage()
                y_haut_table = HAUT_SUITE
                y = rangee_entete(y_haut_table)
            cellule(0, cells[0], y, y - h, F_ARB, SW_PROG, haut=True)
            cellule(1, cells[1], y, y - h, F_ARB, SW_PROG)
            cellule(2, cells[2], y, y - h, F_ARB, SW_PROG)
            y -= h
            if k < len(corps) - 1:
                _simple_h(c, X0, X1, y)
        # Bas du tableau : bordure double, comme le haut.
        _double_h(c, X0, X1, y)
        y_fin = y - (TRAIT_EPAIS + TRAIT_BLANC + TRAIT_FIN)
        verticales(y_fin, y_haut_table, saut)
        return y_fin

    if len(jours) > 1:
        # V2 — دورة متعدّدة الأيّام : un tableau par jour, l'un sous l'autre ;
        # chacun commence par sa ligne de date (اليوم، التاريخ، الفترة). Un
        # tableau qui ne peut pas montrer au moins sa première فقرة sur la page
        # commence sur la page suivante.
        y0 = R.y(319) - decal
        for j in jours:
            corps = corps_de(j.get('rows') or [])
            premiere = corps[0][1] if corps else H_MIN
            besoin = R.d(28) + R.d(29) + premiere
            total = R.d(28) + R.d(29) + sum(h for _, h in corps) + R.d(4)
            # Un jour qui tient entier sur une page neuve n'est pas coupé.
            if y0 - besoin < MARGE_BAS or (y0 - total < MARGE_BAS
                                           and total <= HAUT_SUITE - MARGE_BAS):
                c.showPage()
                y0 = HAUT_SUITE
            y0 = tableau(y0, ligne_de_jour(j), corps) - R.d(16)
    else:
        tableau(R.y(319) - decal, date_ligne, corps_de(rows))
    c.save()
    return output_path
