# -*- coding: utf-8 -*-
"""Les مراسلات : إشعار بالبرنامج (generer_pdf), مراسلة المدير الجهوي, مراسلة حرّة.

v1.7 : extrait tel quel de core/pdf_generator.py, qui reste la façade
(`from core.pdf_generator import generer_…` fonctionne comme avant) et
garde les outils communs (polices, arabe, en-têtes, tableaux)."""

from core import chemins
from core import identite
from datetime import datetime
from reportlab.pdfgen import canvas

from core.pdf_generator import (  # noqa: E402 — outils communs
    BLACK, B_BODY1, B_ILA, B_SAYED, B_SIGN1, B_SIGN2, B_SUJET, B_WABAAD, C_SIGN,
    C_TITRE, F_AR, F_ARB, F_DEC, F_LATB, PH, PW, STAMP_X0, STAMP_X1, STAMP_Y0, STAMP_Y1,
    S_BODY, S_MJ, S_SIGN, S_SUJET, S_TAB, S_TITRE, S_WABAAD, TB_CONT_TOP, TB_HDR_H,
    TB_LEAD, TB_LEAD_H, TB_MIN_Y, TB_PAD, TB_ROW_H, TB_X, TXT_L, TXT_R, W_ILA, _cell,
    _chemin_cachet, _draw_entete, _kashida, _register_fonts, _seg_rtl, _w, _wrap, ar,
)


# ══════════════════════════════════════════════════════════════════════════════
#  GÉNÉRATEUR
# ══════════════════════════════════════════════════════════════════════════════


def _date_cellule(f):
    """Case « تاريخ التكوين » : la date ISO ; V2 — pour une دورة متعدّدة
    الأيّام, trois lignes courtes « 2026-10-12 » / « إلى » / « 2026-10-14 »
    (la colonne est étroite)."""
    from core import jours as _jours
    debut, fin = f.get('date_formation') or '', f.get('date_fin') or ''
    js = _jours.jours_de_la_dorra(debut, fin)
    if len(js) > 1:
        return [js[0], 'إلى', js[-1]]
    return debut

def generer_pdf(lettre_data: dict, base_dir: str) -> str:
    _register_fonts(base_dir)

    output_path = chemins.chemin_pdf_transitoire('lettre')

    c = canvas.Canvas(output_path, pagesize=(PW, PH))

    mois       = lettre_data.get('mois', '')
    annee      = str(lettre_data.get('annee', datetime.now().year))
    mois_annee = f"{mois} {annee}".strip()
    nom_centre = lettre_data.get('nom_centre') or identite.CENTRE_NEUTRE

    _draw_entete(c, lettre_data, base_dir, nom_centre)

    # ══════════════════════════════════════════════════════════════════════
    #  2. DESTINATAIRE
    # ══════════════════════════════════════════════════════════════════════
    c.setFont(F_DEC, S_TITRE)
    c.setFillColor(BLACK)
    c.drawCentredString(C_TITRE, B_ILA,
                        ar(_kashida(c, 'إل', 'ى', W_ILA, F_DEC, S_TITRE)))
    c.drawCentredString(C_TITRE, B_SAYED,
                        ar('السيـــــد مدير إدارة التكوين الجهوي والمختص'))

    # ══════════════════════════════════════════════════════════════════════
    #  3. OBJET  —  « الموضوع: برنامج التكوين لشهر <MOIS ANNÉE> »
    # ══════════════════════════════════════════════════════════════════════
    _seg_rtl(c, [
        ('الموضـوع:',              F_ARB, S_SUJET, BLACK),
        (' برنامج التكوين لشهر ',  F_AR,  S_SUJET, BLACK),
        (mois_annee,               F_AR,  S_SUJET, BLACK),
    ], TXT_R, B_SUJET)

    # Soulignement du seul mot « الموضوع: »
    w_obj = _w(c, ar('الموضـوع:'), F_ARB, S_SUJET)
    c.setStrokeColor(BLACK)
    c.setLineWidth(0.9)
    c.line(TXT_R - w_obj, B_SUJET - 2.6, TXT_R, B_SUJET - 2.6)

    # ══════════════════════════════════════════════════════════════════════
    #  4. CORPS
    # ══════════════════════════════════════════════════════════════════════
    c.setFont(F_AR, S_WABAAD)
    c.setFillColor(BLACK)
    c.drawRightString(TXT_R, B_WABAAD, ar('وبعد،'))

    # Phrase complète — _wrap calcule les sauts de ligne naturellement
    body_full  = (
        f'أتشرف بأن أحيل على سيادتكم برنامج التكوين المزمع إنجازه بـ '
        f'{nom_centre} خلال شهر {mois_annee} طبقا للجدول أسفله:'
    )
    body_lines = _wrap(c, body_full, F_AR, S_BODY, TXT_R - TXT_L)
    BODY_LEAD  = S_BODY * 1.35          # interligne ≈ 1.35× la taille
    y_body     = B_BODY1
    c.setFont(F_AR, S_BODY)
    c.setFillColor(BLACK)
    for line in body_lines:
        c.drawRightString(TXT_R, y_body, line)
        y_body -= BODY_LEAD

    # Le tableau commence juste après le corps (marge de 10 pt)
    tb_y_top_dyn = y_body - 10.0

    # ══════════════════════════════════════════════════════════════════════
    #  5. TABLEAU DES FORMATIONS
    # ══════════════════════════════════════════════════════════════════════
    headers = ['المكان', 'تاريخ التكوين', 'مكان العمل',
               'المكون الرتبة الاسم واللقب', 'الدورة التكوينية', 'ع/ر']

    formations = lettre_data.get('formations', []) or []

    # Colonnes dans l'ordre visuel du modèle (gauche → droite)
    rows_src = []
    for i, f in enumerate(formations, 1):
        grade = (f.get('grade') or '').strip()
        nomf  = (f.get('nom_formateur') or '').strip()
        rows_src.append([
            ((f.get('lieu_formation') or ''),  F_AR,   None),
            (_date_cellule(f),                  F_AR,   (f.get('periode') or '').strip()),
            ((f.get('lieu_travail') or ''),    F_AR,   None),
            (f'{grade} {nomf}'.strip(),        F_AR,   None),
            ((f.get('titre') or ''),           F_ARB,  None),
            (f'{i:02d}',                       F_LATB, 'raw'),
        ])

    # Pré-calcul des lignes et hauteurs
    prepared = []
    for row in rows_src:
        cells, maxlines = [], 1
        for ci, (txt, font, extra) in enumerate(row):
            colw = TB_X[ci + 1] - TB_X[ci] - 2 * TB_PAD
            if extra == 'raw':
                lines = [str(txt)]
            elif isinstance(txt, list):
                # V2 : période d'une دورة متعدّدة الأيّام, une ligne par borne
                lines = [l for x in txt for l in _wrap(c, x, font, S_TAB, colw)]
                if extra:
                    lines = lines + [ar(f'({extra})')]
            else:
                lines = _wrap(c, txt, font, S_TAB, colw)
                if ci == 1 and extra:
                    lines = lines + [ar(f'({extra})')]
            cells.append((lines, font))
            maxlines = max(maxlines, len(lines))
        h = max(TB_ROW_H, maxlines * TB_LEAD + 2 * TB_PAD + 8)
        prepared.append((cells, h))

    c.setLineWidth(0.5)
    c.setStrokeColor(BLACK)

    def _entete_tableau(y_top):
        """Trace la ligne d'en-tête du tableau ; retourne son y inférieur."""
        y_bot = y_top - TB_HDR_H
        for ci in range(6):
            x0, x1 = TB_X[ci], TB_X[ci + 1]
            c.rect(x0, y_bot, x1 - x0, y_top - y_bot, stroke=1, fill=0)
            lg = _wrap(c, headers[ci], F_ARB, S_TAB, x1 - x0 - 2 * TB_PAD)
            _cell(c, lg, (x0 + x1) / 2, y_top, y_bot, F_ARB, S_TAB, BLACK, TB_LEAD_H)
        return y_bot

    y_t = _entete_tableau(tb_y_top_dyn)

    # Lignes de données (avec passage à la page suivante si nécessaire)
    for cells, h in prepared:
        if y_t - h < TB_MIN_Y:
            c.showPage()
            _draw_entete(c, lettre_data, base_dir, nom_centre)
            c.setLineWidth(0.5)
            c.setStrokeColor(BLACK)
            y_t = _entete_tableau(TB_CONT_TOP)

        y_b = y_t - h
        for ci, (lines, font) in enumerate(cells):
            x0, x1 = TB_X[ci], TB_X[ci + 1]
            c.rect(x0, y_b, x1 - x0, y_t - y_b, stroke=1, fill=0)
            _cell(c, lines, (x0 + x1) / 2, y_t, y_b, font, S_TAB, BLACK, TB_LEAD)
        y_t = y_b

    table_bottom = y_t

    # ══════════════════════════════════════════════════════════════════════
    #  6. SIGNATURE + CACHET
    # ══════════════════════════════════════════════════════════════════════
    b1 = B_SIGN1 if table_bottom > B_SIGN1 + 26 else table_bottom - 30
    if b1 < 150:                       # place insuffisante : nouvelle page
        c.showPage()
        _draw_entete(c, lettre_data, base_dir, nom_centre)
        b1 = PH - 165
    b2 = b1 - (B_SIGN1 - B_SIGN2)

    titre_resp = lettre_data.get('titre_responsable', '')
    nom_resp   = lettre_data.get('nom_responsable', '')

    c.setFont(F_DEC, S_SIGN)
    c.setFillColor(BLACK)
    c.drawCentredString(C_SIGN, b1, ar(f'رئيس {nom_centre}'))
    c.drawCentredString(C_SIGN, b2, ar(f'{titre_resp} {nom_resp}'.strip()))

    stamp_path = _chemin_cachet(base_dir)
    if stamp_path:
        sy = STAMP_Y0 - (B_SIGN2 - b2)
        c.drawImage(stamp_path, STAMP_X0, sy,
                    width=STAMP_X1 - STAMP_X0, height=STAMP_Y1 - STAMP_Y0,
                    preserveAspectRatio=True, anchor='c', mask='auto')

    c.save()
    return output_path


# ══════════════════════════════════════════════════════════════════════════════
#  GÉNÉRATEUR LETTRE DIRECTEUR RÉGIONAL (étape 2 — optionnel)
# ══════════════════════════════════════════════════════════════════════════════

def _adresse_directeur(destination):
    """La مراسلة المدير الجهوي s'adresse au DIRECTEUR régional, pas à
    l'administration. « الإدارة الجهويّة للدّيوانة ب… » devient donc
    « السيّد المدير الجهوي للدّيوانة ب… ». Une destination écrite à la main
    (qui ne commence pas par « الإدارة الجهويّة ») est laissée telle quelle."""
    import re as _re
    d = (destination or '').strip()
    m = _re.match(r'^ال[إا]دارة\s+الجهوي[ّ]?ة(.*)$', d)
    if m:
        return ('السيّد المدير الجهوي' + m.group(1)).strip()
    return d


def generer_pdf_directeur_regional(lettre_data: dict, base_dir: str) -> str:
    """Lettre adressée au directeur régional — même format que la lettre principale
    mais avec un destinataire différent (السيد المدير الجهوي للديوانة)."""
    _register_fonts(base_dir)

    output_path = chemins.chemin_pdf_transitoire('dir_regional')

    data2 = dict(lettre_data)
    c = canvas.Canvas(output_path, pagesize=(PW, PH))

    mois       = data2.get('mois', '')
    annee      = str(data2.get('annee', datetime.now().year))
    mois_annee = f"{mois} {annee}".strip()
    nom_centre = data2.get('nom_centre') or identite.CENTRE_NEUTRE

    _draw_entete(c, data2, base_dir, nom_centre)

    c.setFont(F_DEC, S_TITRE)
    c.setFillColor(BLACK)
    c.drawCentredString(C_TITRE, B_ILA,
                        ar(_kashida(c, 'إل', 'ى', W_ILA, F_DEC, S_TITRE)))
    destination = (data2.get('destination')
                   or data2.get('destination_dr', '')).strip()
    destination = _adresse_directeur(destination)
    c.drawCentredString(C_TITRE, B_SAYED, ar(destination))

    _seg_rtl(c, [
        ('الموضـوع:',              F_ARB, S_SUJET, BLACK),
        (' برنامج التكوين لشهر ',  F_AR,  S_SUJET, BLACK),
        (mois_annee,               F_AR,  S_SUJET, BLACK),
    ], TXT_R, B_SUJET)
    w_obj = _w(c, ar('الموضـوع:'), F_ARB, S_SUJET)
    c.setStrokeColor(BLACK)
    c.setLineWidth(0.9)
    c.line(TXT_R - w_obj, B_SUJET - 2.6, TXT_R, B_SUJET - 2.6)

    c.setFont(F_AR, S_WABAAD)
    c.setFillColor(BLACK)
    c.drawRightString(TXT_R, B_WABAAD, ar('وبعد،'))

    body_full = (
        f'أتشرف بأن أحيل على سيادتكم برنامج التكوين المزمع إنجازه بـ '
        f'{nom_centre} خلال شهر {mois_annee} طبقا للجدول أسفله ونرجو من الجناب '
        f'توجيه نسخة منه الى كافة السادة رؤساء المكاتب والسيد آمر فصيل الحراسة '
        f'والتفتيشات الديوانية لتعمير أسماء المشاركين:'
    )
    body_lines = _wrap(c, body_full, F_AR, S_BODY, TXT_R - TXT_L)
    BODY_LEAD  = S_BODY * 1.35
    y_body     = B_BODY1
    c.setFont(F_AR, S_BODY)
    c.setFillColor(BLACK)
    for line in body_lines:
        c.drawRightString(TXT_R, y_body, line)
        y_body -= BODY_LEAD

    tb_y_top_dyn = y_body - 10.0

    # Tableau avec 5 colonnes (sans المكون et sans ملاحظات)
    HDR_REG  = ['الضباط وضباط الصف المزمع تشريكهم',
                'المكان', 'تاريخ التكوين',
                'الدورة التكوينية', 'ع/ر']
    TB_X_REG = [59.7, 248.8, 328.8, 398.8, 498.8, 541.8]

    formations = data2.get('formations', []) or []
    rows_src2 = []
    for i, f in enumerate(formations, 1):
        rows_src2.append([
            ('', F_AR, None),
            ((f.get('lieu_formation') or ''), F_AR, None),
            (_date_cellule(f), F_AR, (f.get('periode') or '').strip()),
            ((f.get('titre') or ''),    F_ARB, None),
            (f'{i:02d}',               F_LATB, 'raw'),
        ])

    prepared_reg = []
    for row in rows_src2:
        cells, maxlines = [], 1
        for ci, (txt, font, extra) in enumerate(row):
            colw = TB_X_REG[ci + 1] - TB_X_REG[ci] - 2 * TB_PAD
            if extra == 'raw':
                lines = [str(txt)]
            elif isinstance(txt, list):
                # V2 : période d'une دورة متعدّدة الأيّام, une ligne par borne
                lines = [l for x in txt for l in _wrap(c, x, font, S_TAB, colw)]
                if extra:
                    lines = lines + [ar(f'({extra})')]
            else:
                lines = _wrap(c, txt, font, S_TAB, colw)
                if ci == 3 and extra:
                    lines = lines + [ar(f'({extra})')]
            cells.append((lines, font))
            maxlines = max(maxlines, len(lines))
        h = max(TB_ROW_H, maxlines * TB_LEAD + 2 * TB_PAD + 8)
        prepared_reg.append((cells, h))

    c.setLineWidth(0.5)
    c.setStrokeColor(BLACK)

    def _entete_reg(y_top):
        y_bot = y_top - TB_HDR_H
        for ci in range(5):
            x0, x1 = TB_X_REG[ci], TB_X_REG[ci + 1]
            c.rect(x0, y_bot, x1 - x0, y_top - y_bot, stroke=1, fill=0)
            lg = _wrap(c, HDR_REG[ci], F_ARB, S_TAB, x1 - x0 - 2 * TB_PAD)
            _cell(c, lg, (x0 + x1) / 2, y_top, y_bot, F_ARB, S_TAB, BLACK, TB_LEAD_H)
        return y_bot

    y_t = _entete_reg(tb_y_top_dyn)

    for cells, h in prepared_reg:
        if y_t - h < TB_MIN_Y:
            c.showPage()
            _draw_entete(c, data2, base_dir, nom_centre)
            c.setLineWidth(0.5)
            c.setStrokeColor(BLACK)
            y_t = _entete_reg(TB_CONT_TOP)
        y_b = y_t - h
        for ci, (lines, font) in enumerate(cells):
            x0, x1 = TB_X_REG[ci], TB_X_REG[ci + 1]
            c.rect(x0, y_b, x1 - x0, y_t - y_b, stroke=1, fill=0)
            _cell(c, lines, (x0 + x1) / 2, y_t, y_b, font, S_TAB, BLACK, TB_LEAD)
        y_t = y_b



    b1 = y_t - 30
    if b1 < 150:
        c.showPage()
        _draw_entete(c, data2, base_dir, nom_centre)
        b1 = PH - 165
    b2 = b1 - (B_SIGN1 - B_SIGN2)
    titre_resp = data2.get('titre_responsable', '')
    nom_resp   = data2.get('nom_responsable', '')
    c.setFont(F_DEC, S_SIGN)
    c.setFillColor(BLACK)
    c.drawCentredString(C_SIGN, b1, ar(f'رئيس {nom_centre}'))
    c.drawCentredString(C_SIGN, b2, ar(f'{titre_resp} {nom_resp}'.strip()))
    stamp_path = _chemin_cachet(base_dir)
    if stamp_path:
        sy = STAMP_Y0 - (B_SIGN2 - b2)
        c.drawImage(stamp_path, STAMP_X0, sy,
                    width=STAMP_X1 - STAMP_X0, height=STAMP_Y1 - STAMP_Y0,
                    preserveAspectRatio=True, anchor='c', mask='auto')
    c.save()
    return output_path


# ══════════════════════════════════════════════════════════════════════════════
#  GÉNÉRATEUR LETTRE LIBRE
# ══════════════════════════════════════════════════════════════════════════════

def generer_pdf_libre(lettre_data: dict, base_dir: str) -> str:
    """Génère un PDF pour une lettre libre (corps rédigé manuellement)."""
    import json as _json

    _register_fonts(base_dir)

    output_path  = chemins.chemin_pdf_transitoire('lettre_libre')

    c = canvas.Canvas(output_path, pagesize=(PW, PH))

    nom_centre    = lettre_data.get('nom_centre') or identite.CENTRE_NEUTRE
    destinataire  = lettre_data.get('destinataire', '')
    objet         = lettre_data.get('objet', '')
    corps         = lettre_data.get('corps', '')

    # Parse مصاحب from JSON list or plain string
    msahib_raw = lettre_data.get('msahib', '') or ''
    msahib_list = []
    if msahib_raw:
        try:
            parsed = _json.loads(msahib_raw) if isinstance(msahib_raw, str) else msahib_raw
            if isinstance(parsed, list):
                msahib_list = [str(x).strip() for x in parsed if str(x).strip()]
            elif isinstance(parsed, str) and parsed.strip():
                msahib_list = [parsed.strip()]
        except Exception:
            if msahib_raw.strip():
                msahib_list = [msahib_raw.strip()]

    # Parse الموجَّه لهم from JSON string or list
    moujah_raw = lettre_data.get('moujah_lahom', '') or ''
    moujah_list = []
    if moujah_raw:
        try:
            moujah_list = _json.loads(moujah_raw) if isinstance(moujah_raw, str) else moujah_raw
            if not isinstance(moujah_list, list):
                moujah_list = []
        except Exception:
            moujah_list = []

    _draw_entete(c, lettre_data, base_dir, nom_centre)

    # ── 2. DESTINATAIRE ──────────────────────────────────────────────────────
    c.setFont(F_DEC, S_TITRE)
    c.setFillColor(BLACK)
    c.drawCentredString(C_TITRE, B_ILA,
                        ar(_kashida(c, 'إل', 'ى', W_ILA, F_DEC, S_TITRE)))

    if destinataire:
        dest_lines = _wrap(c, destinataire, F_DEC, S_TITRE, TXT_R - TXT_L)
        y_dest = B_SAYED
        for dl in dest_lines:
            c.drawCentredString(C_TITRE, y_dest, dl)
            y_dest -= S_TITRE * 1.35
    else:
        y_dest = B_SAYED - S_TITRE * 1.35

    # ── 3. OBJET ─────────────────────────────────────────────────────────────
    y_objet = min(y_dest - 18, B_SUJET)
    if objet:
        _seg_rtl(c, [
            ('الموضـوع:',  F_ARB, S_SUJET, BLACK),
            (' ' + objet,  F_AR,  S_SUJET, BLACK),
        ], TXT_R, y_objet)
        w_obj = _w(c, ar('الموضـوع:'), F_ARB, S_SUJET)
        c.setStrokeColor(BLACK)
        c.setLineWidth(0.9)
        c.line(TXT_R - w_obj, y_objet - 2.6, TXT_R, y_objet - 2.6)

    # ── 3b. مصاحيب (optional subtitle lines below objet) ─────────────────────
    y_after_objet = y_objet - S_SUJET * 1.45
    if msahib_list:
        # Label "مصاحيب:" une fois — gras + souligné, même style que الموضوع
        c.setFont(F_ARB, S_SUJET)
        c.setFillColor(BLACK)
        c.drawRightString(TXT_R, y_after_objet, ar('مصاحيب:'))
        w_msahib_lbl = _w(c, ar('مصاحيب:'), F_ARB, S_SUJET)
        c.setStrokeColor(BLACK)
        c.setLineWidth(0.9)
        c.line(TXT_R - w_msahib_lbl, y_after_objet - 2.6, TXT_R, y_after_objet - 2.6)
        # Bord droit de la colonne des éléments (juste à gauche du label)
        GAP_MS = 6
        x_ms_items = TXT_R - w_msahib_lbl - GAP_MS
        c.setFont(F_AR, S_SUJET)
        c.setFillColor(BLACK)
        # 1er élément sur la même ligne que le label
        c.drawRightString(x_ms_items, y_after_objet, ar(msahib_list[0]))
        # Éléments suivants : directement sous le 1er, même bord droit
        for ms_item in msahib_list[1:]:
            y_after_objet -= S_SUJET * 1.45
            c.drawRightString(x_ms_items, y_after_objet, ar(ms_item))
        y_after_objet -= S_SUJET * 1.45

    # ── 4. CORPS ──────────────────────────────────────────────────────────────
    y_body = y_after_objet - 14
    BODY_LEAD = S_BODY * 1.40

    c.setFont(F_AR, S_WABAAD)
    c.setFillColor(BLACK)
    c.drawRightString(TXT_R, y_body, ar('وبعد،'))
    y_body -= S_WABAAD * 1.8

    c.setFont(F_AR, S_BODY)
    c.setFillColor(BLACK)

    for paragraph in corps.split('\n'):
        paragraph = paragraph.strip()
        if not paragraph:
            y_body -= BODY_LEAD * 0.6
            continue
        para_lines = _wrap(c, paragraph, F_AR, S_BODY, TXT_R - TXT_L)
        for line in para_lines:
            if y_body < 160:
                c.showPage()
                _draw_entete(c, lettre_data, base_dir, nom_centre)
                y_body = PH - 145
                c.setFont(F_AR, S_BODY)
                c.setFillColor(BLACK)
            c.drawRightString(TXT_R, y_body, line)
            y_body -= BODY_LEAD

    # ── 5. SIGNATURE ──────────────────────────────────────────────────────────
    b1 = y_body - 40
    if b1 < 150:
        c.showPage()
        _draw_entete(c, lettre_data, base_dir, nom_centre)
        b1 = PH - 165
    b2 = b1 - (B_SIGN1 - B_SIGN2)

    titre_resp = lettre_data.get('titre_responsable', '')
    nom_resp   = lettre_data.get('nom_responsable', '')

    c.setFont(F_DEC, S_SIGN)
    c.setFillColor(BLACK)
    c.drawCentredString(C_SIGN, b1, ar(f'رئيس {nom_centre}'))
    c.drawCentredString(C_SIGN, b2, ar(f'{titre_resp} {nom_resp}'.strip()))

    stamp_path = _chemin_cachet(base_dir)
    if stamp_path:
        sy = STAMP_Y0 - (B_SIGN2 - b2)
        c.drawImage(stamp_path, STAMP_X0, sy,
                    width=STAMP_X1 - STAMP_X0, height=STAMP_Y1 - STAMP_Y0,
                    preserveAspectRatio=True, anchor='c', mask='auto')

    # ── 6. الموجَّه إليهم — ancré en bas à droite de la page ──────────────────
    if moujah_list:
        LEAD_MJ = S_MJ * 1.50
        MJ_RIGHT = TXT_R                     # bord droit du texte

        # Filtrer les entrées valides
        visible = [(e.get('nom', '').strip(), e.get('type', '').strip())
                   for e in moujah_list if (e.get('nom', '') or '').strip()]

        if visible:
            # Calculer la hauteur totale du bloc pour le placer depuis le bas
            n_lines = 1 + len(visible)           # titre + entrées
            block_h  = n_lines * LEAD_MJ + 6
            PAGE_BOT = 38                        # marge basse absolue
            y_mj     = PAGE_BOT + block_h        # haut du bloc

            # Titre
            c.setFont(F_ARB, S_MJ)
            c.setFillColor(BLACK)
            c.drawRightString(MJ_RIGHT, y_mj, ar('الموجَّه إليهم:'))
            y_mj -= LEAD_MJ

            # Lignes (kashida + nom + type)
            c.setFont(F_AR, S_MJ)
            for nom_mj, type_mj in visible:
                # Construction séparée du préfixe kashida et du texte
                # pour éviter la jonction de caractères par le reshaper
                bullet_vis = ar('ـ')
                if type_mj:
                    body_txt = ar(f'{nom_mj}، {type_mj}.')
                else:
                    body_txt = ar(f'{nom_mj}.')
                bullet_w = _w(c, bullet_vis, F_AR, S_MJ)
                GAP = 3
                c.drawRightString(MJ_RIGHT, y_mj, bullet_vis)
                c.drawRightString(MJ_RIGHT - bullet_w - GAP, y_mj, body_txt)
                y_mj -= LEAD_MJ

    c.save()
    return output_path
