# -*- coding: utf-8 -*-
"""المذكّرة الداخليّة.

v1.7 : extrait tel quel de core/pdf_generator.py, qui reste la façade
(`from core.pdf_generator import generer_…` fonctionne comme avant) et
garde les outils communs (polices, arabe, en-têtes, tableaux)."""

from core import chemins
from reportlab.pdfgen import canvas

from core.pdf_generator import (  # noqa: E402 — outils communs
    BLACK, C_TITRE, F_AR, F_ARB, F_DEC, PH, PIED_H, PIED_Y0, PW, S_BODY, S_MJ, S_MURA,
    S_SIGN, S_SUJET, S_TITRE, TXT_L, TXT_R, _draw_entete, _draw_pied_ecole,
    _justify_rtl, _kashida, _register_fonts, _seg_rtl, _w, _wrap_log, ar,
)


# ══════════════════════════════════════════════════════════════════════════════
#  ÉTAPE 6 — مذكرة تكوين داخلية  (Memo)
# ══════════════════════════════════════════════════════════════════════════════

def generer_pdf_memo(pdf_data: dict, base_dir: str) -> str:
    """مذكرة تكوين داخلية — signée par le Directeur général de l'École."""
    _register_fonts(base_dir)
    output_path = chemins.chemin_pdf_transitoire('memo')
    c = canvas.Canvas(output_path, pagesize=(PW, PH))

    objet       = (pdf_data.get('objet') or '').strip()
    corps       = pdf_data.get('corps') or ''
    msahib_list = [str(x).strip() for x in (pdf_data.get('msahib') or []) if str(x).strip()]
    moujah_list = pdf_data.get('moujah') or []
    titre_dg    = (pdf_data.get('titre_directeur_general') or 'العميد').strip()
    nom_dg      = (pdf_data.get('nom_directeur_general') or '').strip()

    # ── Géométrie propre à la مذكرة ──────────────────────────────────────────
    B_FONDOUK   = PH - 118.0        # « فندق الجديد في: »
    X_FONDOUK   = 196.0
    B_MEMO      = PH - 140.0        # titre « مذكــرة »
    B_OBJ_MEMO  = PH - 180.0        # ligne « الموضوع »
    C_SIGN_MEMO = 245.0             # centre du bloc signature
    W_LBL       = 78.0              # largeur cible des libellés (kashida)
    # « الموجَّه إليهم » doit rester au-dessus du pied de page de l'École
    MJ_BOTTOM   = PIED_Y0 + PIED_H + 12.0

    def _entete():
        """En-tête + pied de page : appelé au début de CHAQUE page."""
        _draw_entete(c, pdf_data, base_dir, avec_centre=False)
        c.setFont(F_AR, S_MURA)
        c.setFillColor(BLACK)
        c.drawRightString(X_FONDOUK, B_FONDOUK, ar('فندق الجديد في:'))
        _draw_pied_ecole(c, pdf_data, base_dir)

    _entete()

    # ── 1. TITRE « مذكــرة » ─────────────────────────────────────────────────
    c.setFont(F_DEC, S_TITRE)
    c.setFillColor(BLACK)
    c.drawCentredString(C_TITRE, B_MEMO,
                        ar(_kashida(c, 'مذك', 'رة', 72.0, F_DEC, S_TITRE)))

    # ── 2. الموضوع ───────────────────────────────────────────────────────────
    y = B_OBJ_MEMO
    lbl_objet = _kashida(c, 'الموضـ', 'وع:', W_LBL, F_ARB, S_SUJET)
    if objet:
        _seg_rtl(c, [
            (lbl_objet,   F_ARB, S_SUJET, BLACK),
            (' ' + objet, F_AR,  S_SUJET, BLACK),
        ], TXT_R, y)
        w_lbl = _w(c, ar(lbl_objet), F_ARB, S_SUJET)
        c.setStrokeColor(BLACK); c.setLineWidth(0.9)
        c.line(TXT_R - w_lbl, y - 2.6, TXT_R, y - 2.6)
        y -= S_SUJET * 1.45

    # ── 3. المصاحيب ──────────────────────────────────────────────────────────
    if msahib_list:
        lbl_ms = _kashida(c, 'المصاحيـ', 'ب:', W_LBL, F_ARB, S_SUJET)
        c.setFont(F_ARB, S_SUJET); c.setFillColor(BLACK)
        c.drawRightString(TXT_R, y, ar(lbl_ms))
        w_ms = _w(c, ar(lbl_ms), F_ARB, S_SUJET)
        c.setStrokeColor(BLACK); c.setLineWidth(0.9)
        c.line(TXT_R - w_ms, y - 2.6, TXT_R, y - 2.6)
        x_items = TXT_R - w_ms - 6
        c.setFont(F_AR, S_SUJET)
        c.drawRightString(x_items, y, ar(msahib_list[0]))
        for item in msahib_list[1:]:
            y -= S_SUJET * 1.45
            c.drawRightString(x_items, y, ar(item))
        y -= S_SUJET * 1.45

    # ── 4. CORPS (justifié, première ligne en retrait) ───────────────────────
    y_body = y - 16
    BODY_LEAD = S_BODY * 1.42
    INDENT    = 22.0

    for paragraph in corps.split('\n'):
        paragraph = paragraph.strip()
        if not paragraph:
            y_body -= BODY_LEAD * 0.5
            continue
        # Lignes en ordre LOGIQUE, 1re ligne en retrait à droite
        lignes = _wrap_log(c, paragraph, F_AR, S_BODY,
                           TXT_R - TXT_L, (TXT_R - INDENT) - TXT_L)
        for idx, line in enumerate(lignes):
            if y_body < 200:
                c.showPage(); _entete(); y_body = PH - 150
            x_right = (TXT_R - INDENT) if idx == 0 else TXT_R
            if idx == len(lignes) - 1:          # dernière ligne : pas de justification
                c.setFont(F_AR, S_BODY); c.setFillColor(BLACK)
                c.drawRightString(x_right, y_body, ar(line))
            else:
                _justify_rtl(c, line, F_AR, S_BODY, TXT_L, x_right, y_body)
            y_body -= BODY_LEAD
        y_body -= BODY_LEAD * 0.15

    # ── 5. SIGNATURE (Directeur général de l'École nationale) ────────────────
    visible = [((m.get('nom') or '').strip(), (m.get('type') or '').strip())
               for m in moujah_list if (m.get('nom') or '').strip()]
    LEAD_MJ = S_MJ * 1.50
    block_h = ((1 + len(visible)) * LEAD_MJ + 6) if visible else 0
    y_mj_top = MJ_BOTTOM + block_h

    b1 = y_body - 28
    if b1 - (S_SIGN * 1.55) < y_mj_top + 8:
        c.showPage(); _entete()
        b1 = PH - 175
        y_mj_top = MJ_BOTTOM + block_h
    b2 = b1 - S_SIGN * 1.55

    c.setFont(F_DEC, S_SIGN); c.setFillColor(BLACK)
    c.drawCentredString(C_SIGN_MEMO, b1, ar('المدير العام للمدرسة الوطنيّة للدّيوانة'))
    c.drawCentredString(C_SIGN_MEMO, b2, ar(f'{titre_dg} {nom_dg}'.strip()))

    # ── 6. الموجَّه إليهم — ancré en bas à droite ────────────────────────────
    if visible:
        y_mj = y_mj_top
        c.setFont(F_ARB, S_MJ); c.setFillColor(BLACK)
        c.drawRightString(TXT_R, y_mj, ar('الموجَّه إليهم:'))
        y_mj -= LEAD_MJ
        c.setFont(F_AR, S_MJ)
        for nom_mj, type_mj in visible:
            bullet_vis = ar('ـ')
            body_txt = ar(f'{nom_mj}، {type_mj}.' if type_mj else f'{nom_mj}.')
            bullet_w = _w(c, bullet_vis, F_AR, S_MJ)
            c.drawRightString(TXT_R, y_mj, bullet_vis)
            c.drawRightString(TXT_R - bullet_w - 3, y_mj, body_txt)
            y_mj -= LEAD_MJ

    c.save()
    return output_path
