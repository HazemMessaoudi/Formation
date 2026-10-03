# -*- coding: utf-8 -*-
"""البطاقة البيداغوجية (tableau extensible).

v1.7 : extrait tel quel de core/pdf_generator.py, qui reste la façade
(`from core.pdf_generator import generer_…` fonctionne comme avant) et
garde les outils communs (polices, arabe, en-têtes, tableaux)."""

from core import chemins
from core import identite
from datetime import datetime
from reportlab.lib import colors
from reportlab.pdfgen import canvas
import os

from core.pdf_generator import (  # noqa: E402 — outils communs
    BLACK, F_AR, F_ARB, PH, PW, _cell, _register_fonts, _w, _wrap, ar,
)


# ══════════════════════════════════════════════════════════════════════════════
#  ÉTAPE 4 — البطاقة البيداغوجية  (Fiche pédagogique)
#  Géométrie relevée au pixel sur le modèle officiel (image 555 × 785 px).
# ══════════════════════════════════════════════════════════════════════════════

def generer_pdf_bataqa(pdf_data: dict, base_dir: str) -> str:
    """Fiche pédagogique — copie conforme du modèle officiel, remplie automatiquement."""
    _register_fonts(base_dir)

    output_path = chemins.chemin_pdf_transitoire('bataqa')

    c = canvas.Canvas(output_path, pagesize=(PW, PH))

    # ── Conversion pixel → point (origine ReportLab en bas à gauche) ────────────
    IMG_W, IMG_H = 555.0, 785.0
    SX, SY = PW / IMG_W, PH / IMG_H
    def X(px):  return px * SX
    def Y(py):  return PH - py * SY
    def WPX(px): return px * SX          # largeur px → pt
    def HPX(px): return px * SY          # hauteur px → pt

    # ── Palette ─────────────────────────────────────────────────────────────
    HDR_GRAY = colors.Color(213/255, 213/255, 213/255)   # cellules d'en-tête

    # ── Données ──────────────────────────────────────────────────────────────
    theme        = pdf_data.get('theme', '')
    mustahdafun  = pdf_data.get('mustahdafun', '')
    nb_part      = pdf_data.get('nb_participants', 0)
    services     = pdf_data.get('services', []) or []
    type_form    = pdf_data.get('type_formation', '')
    mahawer      = pdf_data.get('mahawer', '')
    objectifs    = pdf_data.get('objectifs', '')
    lieu_form    = pdf_data.get('lieu_formation', '')
    date_form    = pdf_data.get('date_formation', '')
    methodes     = pdf_data.get('methodes', '')
    moyens       = pdf_data.get('moyens', '')
    preparation  = pdf_data.get('preparation', '')
    equipements  = pdf_data.get('equipements', '') or 'لاشيئ'
    nom_centre   = pdf_data.get('nom_centre') or identite.CENTRE_NEUTRE

    # Date ISO → JJ/MM/AAAA
    date_disp = date_form
    try:
        _d = datetime.strptime(date_form, '%Y-%m-%d')
        date_disp = _d.strftime('%Y/%m/%d')
    except Exception:
        pass
    # V2 — دورة متعدّدة الأيّام : « من 2026/10/12 إلى 2026/10/14 »
    from core import jours as _jours
    if _jours.est_multi_jours(date_form, pdf_data.get('date_fin', '')):
        date_disp = _jours.plage_slash(date_form, pdf_data.get('date_fin', ''))

    def _split_items(txt):
        """Découpe un champ texte en items (par retour-ligne, puis ';' ou '/')."""
        if not txt:
            return []
        raw = [l.strip(' -•\t') for l in str(txt).splitlines()]
        items = [l for l in raw if l]
        if len(items) <= 1 and items:
            # une seule ligne : tenter de séparer sur / ou ؛ ou ;
            for sep in ('؛', ';', ' / ', '/'):
                if sep in items[0]:
                    items = [p.strip() for p in items[0].split(sep) if p.strip()]
                    break
        return items

    # ══════════════════════════════════════════════════════════════════════════
    #  Helpers de dessin
    # ══════════════════════════════════════════════════════════════════════════
    def _diamond(cx, cy, r):
        p = c.beginPath()
        p.moveTo(cx, cy + r); p.lineTo(cx + r, cy)
        p.lineTo(cx, cy - r); p.lineTo(cx - r, cy); p.close()
        c.setFillColor(BLACK)
        c.drawPath(p, fill=1, stroke=0)

    def _section_title(txt_logique, base_py, colon=False):
        """Titre de section « ◆ ... » aligné à droite sur le bord droit du tableau."""
        y = Yo(base_py)
        c.setFont(F_ARB, 12.0)
        c.setFillColor(BLACK)
        s = txt_logique + ('' if not colon else '')
        _diamond(X(508), y + 3.2, 2.4)
        c.drawRightString(X(500), y, ar(s))

    def _hdr_cell(x0, x1, y_top, y_bot, txt_logique, size=12.0):
        """Cellule d'en-tête grise avec titre centré (bold)."""
        c.setFillColor(HDR_GRAY)
        c.setStrokeColor(BLACK)
        c.setLineWidth(0.9)
        c.rect(x0, y_bot, x1 - x0, y_top - y_bot, stroke=1, fill=1)
        lines = _wrap(c, txt_logique, F_ARB, size, (x1 - x0) - 6)
        _cell(c, lines, (x0 + x1) / 2, y_top, y_bot, F_ARB, size, BLACK, leading=size + 2.2)

    def _cell_centered(x0, x1, y_top, y_bot, txt_logique, font=F_AR, size=12.0):
        c.setFillColor(colors.white)
        c.setStrokeColor(BLACK)
        c.setLineWidth(0.9)
        c.rect(x0, y_bot, x1 - x0, y_top - y_bot, stroke=1, fill=1)
        lines = _wrap(c, txt_logique, font, size, (x1 - x0) - 8)
        _cell(c, lines, (x0 + x1) / 2, y_top, y_bot, font, size, BLACK, leading=size + 3)

    def _cell_bullets(x0, x1, y_top, y_bot, items, size=12.0, fill=True):
        """Cellule blanche avec liste à puces « - » alignée à droite, en haut."""
        if fill:
            c.setFillColor(colors.white)
            c.setStrokeColor(BLACK)
            c.setLineWidth(0.9)
            c.rect(x0, y_bot, x1 - x0, y_top - y_bot, stroke=1, fill=1)
        c.setFont(F_AR, size)
        c.setFillColor(BLACK)
        pad_r = 5
        x_right = x1 - pad_r
        dash = '-'
        dash_w = _w(c, dash, F_AR, size)
        gap = 3
        avail = (x1 - x0) - pad_r - dash_w - gap - 4
        lead = size + 3.4
        y = y_top - size - 3
        for it in items:
            wrapped = _wrap(c, it, F_AR, size, avail)
            first = True
            for wl in wrapped:
                if first:
                    c.setFont(F_ARB, size)
                    c.drawRightString(x_right, y, ar('-'))
                    c.setFont(F_AR, size)
                    c.drawRightString(x_right - dash_w - gap, y, wl)
                    first = False
                else:
                    c.drawRightString(x_right - dash_w - gap, y, wl)
                y -= lead

    # ══════════════════════════════════════════════════════════════════════════
    #  EN-TÊTE : logos + institution + titres
    # ══════════════════════════════════════════════════════════════════════════
    # Logo gauche (école) — bord gauche aligné avec le bord gauche du tableau (X=44)
    logo_l = os.path.join(base_dir, 'static', 'images', 'logo.jpg')
    if os.path.exists(logo_l):
        c.drawImage(logo_l, X(44), Y(110), width=WPX(74), height=HPX(88),
                    preserveAspectRatio=True, anchor='c', mask='auto')
    # Logo droit (DOUANE) — clipPath pour masquer le trait noir en haut de l'image
    logo_r = os.path.join(base_dir, 'static', 'images', 'logo_douane.png')
    if os.path.exists(logo_r):
        c.saveState()
        _cp = c.beginPath()
        # On exclut les 5 premiers pixels (en haut de la boîte) qui portent le trait noir
        _cp.rect(X(447), Y(105), WPX(74), HPX(80))
        c.clipPath(_cp, stroke=0)
        c.drawImage(logo_r, X(447), Y(105), width=WPX(74), height=HPX(85),
                    preserveAspectRatio=True, anchor='c', mask='auto')
        c.restoreState()

    # Bloc institution (centré)
    inst = list(identite.ENTETE_NATIONAL[:4])
    c.setFont(F_ARB, 12.0)
    c.setFillColor(BLACK)
    inst_base = [37, 50, 63, 76]
    for t, py in zip(inst, inst_base):
        c.drawCentredString(X(277), Y(py), ar(t))

    # Titres
    c.setFont(F_ARB, 13.5)
    c.drawCentredString(X(277), Y(107), ar('بطاقة بيداغوجيّة'))
    c.setFont(F_ARB, 11.5)
    c.drawCentredString(X(277), Y(130), ar(f'دورة تكوينيّة في مجال " {theme} "'))
    c.drawCentredString(X(277), Y(145), ar(nom_centre))

    # ══════════════════════════════════════════════════════════════════════════
    #  v1.6.1 — tableau EXTENSIBLE
    #  Chaque ligne de données garde la hauteur du modèle officiel tant que son
    #  contenu y tient (rendu inchangé) ; sinon elle s'allonge et tout ce qui
    #  suit descend d'autant. Une section qui ne tient plus sur la page passe
    #  en entier sur la page suivante ; un contenu plus haut qu'une page entière
    #  est d'abord légèrement réduit (≥ 10 pt), puis la liste est coupée entre
    #  deux items et continue sur la page suivante sous un rappel de l'en-tête.
    # ══════════════════════════════════════════════════════════════════════════
    MARGE_BAS = 28.0              # bas utile de la page (pt)
    HAUT_SUITE = PH - 40.0        # haut d'une section reportée sur une page de suite
    TAILLE_MIN = 10.0             # réduction maximale avant de couper une liste
    etat = {'off': 0.0}           # décalage vertical cumulé (pt)

    def Yo(py):
        return Y(py) - etat['off']

    def _h_puces(x0, x1, items, size):
        """Hauteur utile d'une cellule à puces (même découpe que _cell_bullets)."""
        if not items:
            return 0.0
        dash_w = _w(c, '-', F_AR, size)
        avail = (x1 - x0) - 5 - dash_w - 3 - 4
        n = sum(len(_wrap(c, it, F_AR, size, avail)) for it in items)
        return 3 + size + (n - 1) * (size + 3.4) + 5

    def _h_centre(x0, x1, txt, font, size):
        """Hauteur utile d'une cellule centrée (même découpe que _cell_centered)."""
        n = len(_wrap(c, txt, font, size, (x1 - x0) - 8))
        return n * (size + 3) + 6

    def _section(titre, titre_py, top_py, hb_py, db_py, entetes, donnees, peut_sauter=True):
        """entetes : [(x0, x1, libellé)] ; donnees : [(genre, x0, x1, contenu, police)]
        avec genre 'puces' (liste) ou 'centre' (texte centré)."""
        modele = HPX(db_py - hb_py)

        def besoin(s):
            h = modele
            for genre, x0, x1, contenu, font in donnees:
                if genre == 'puces':
                    h = max(h, _h_puces(x0, x1, contenu, s))
                else:
                    h = max(h, _h_centre(x0, x1, contenu, font, s))
            return h

        def deborde(s):
            return Yo(db_py) - (besoin(s) - modele) < MARGE_BAS

        def entete():
            if titre:
                _section_title(titre, titre_py)
            for x0, x1, libelle in entetes:
                _hdr_cell(x0, x1, Yo(top_py), Yo(hb_py), libelle)

        def rangee(cellules, y_bas, s):
            for genre, x0, x1, contenu, font in cellules:
                if genre == 'puces':
                    _cell_bullets(x0, x1, Yo(hb_py), y_bas, contenu, size=s)
                else:
                    _cell_centered(x0, x1, Yo(hb_py), y_bas, contenu, font=font, size=s)

        def tient_page_neuve(s):
            ancre = titre_py if titre else top_py
            return HAUT_SUITE - (Y(ancre) - Y(db_py)) - (besoin(s) - modele) >= MARGE_BAS

        def sauter():
            c.showPage()
            etat['off'] = Y(titre_py if titre else top_py) - HAUT_SUITE

        # Ordre de préférence : (1) tel quel ici ; (2) tel quel en haut de la
        # page suivante ; (3) légèrement réduit (≥ 10 pt) ici, ou (4) en haut de
        # la page suivante ; (5) sinon la liste est coupée entre deux items.
        taille = 12.0
        if deborde(taille):
            if peut_sauter and tient_page_neuve(taille):
                sauter()
            else:
                s_ici = next((t / 2 for t in range(int(taille * 2) - 1, int(TAILLE_MIN * 2) - 1, -1)
                              if not deborde(t / 2)), None)
                s_neuve = next((t / 2 for t in range(int(taille * 2) - 1, int(TAILLE_MIN * 2) - 1, -1)
                                if tient_page_neuve(t / 2)), None) if peut_sauter else None
                if s_ici is not None:
                    taille = s_ici
                elif s_neuve is not None:
                    sauter()
                    taille = s_neuve
                elif peut_sauter and Yo(hb_py) - MARGE_BAS < 4 * 15.4:
                    sauter()          # trop peu de place ici pour entamer la liste

        if deborde(taille):
            # Plus haut qu'une page : la liste est coupée entre deux items et
            # continue sur la page suivante (même taille), sous un rappel de
            # l'en-tête du tableau.
            dispo = Yo(hb_py) - MARGE_BAS
            ici, suite = [], []
            for genre, x0, x1, contenu, font in donnees:
                if genre != 'puces':
                    ici.append((genre, x0, x1, contenu, font))
                    suite.append((genre, x0, x1, '', font))
                    continue
                k = len(contenu)
                while k > 1 and _h_puces(x0, x1, contenu[:k], taille) > dispo:
                    k -= 1
                ici.append((genre, x0, x1, contenu[:k], font))
                suite.append((genre, x0, x1, contenu[k:], font))
            entete()
            rangee(ici, MARGE_BAS, taille)
            c.showPage()
            etat['off'] = Y(top_py) - HAUT_SUITE
            _section(None, top_py, top_py, hb_py, db_py, entetes, suite, peut_sauter=False)
            return

        extra = besoin(taille) - modele
        entete()
        rangee(donnees, Yo(db_py) - extra, taille)
        etat['off'] += extra

    def _items(txt):
        return _split_items(txt) or ([txt] if txt else [])

    # ══════════════════════════════════════════════════════════════════════════
    #  SECTION 1 — تقديم الدورة التكوينيّة
    # ══════════════════════════════════════════════════════════════════════════
    xs1 = [X(44), X(106), X(231), X(281), X(433), X(510)]
    # En-têtes (gauche → droite) : نوع | المصالح | عدد | المستهدفون | موضوع
    _section('تقديم الدورة التكوينيّة', 172, 188, 214, 278, [
        (xs1[0], xs1[1], 'نوع التكوين'),
        (xs1[1], xs1[2], 'المصالح المعنية بالمشاركة'),
        (xs1[2], xs1[3], 'عدد المشاركين'),
        (xs1[3], xs1[4], 'المستهدفون بالتكوين'),
        (xs1[4], xs1[5], 'موضوع التكوين'),
    ], [
        ('centre', xs1[0], xs1[1], type_form, F_AR),
        ('puces', xs1[1], xs1[2], services, F_AR),
        ('centre', xs1[2], xs1[3], str(nb_part), F_ARB),
        ('puces', xs1[3], xs1[4], _items(mustahdafun), F_AR),
        ('centre', xs1[4], xs1[5], theme, F_AR),
    ], peut_sauter=False)

    # ══════════════════════════════════════════════════════════════════════════
    #  SECTION 2 — محاور الدورة | أهداف الدورة
    # ══════════════════════════════════════════════════════════════════════════
    xr, xm, xl = X(510), X(280), X(44)
    _section(None, 294, 294, 326, 392, [
        (xm, xr, 'محاور الدورة'),
        (xl, xm, 'أهداف الدورة'),
    ], [
        ('puces', xm, xr, _split_items(mahawer), F_AR),
        ('puces', xl, xm, _split_items(objectifs), F_AR),
    ])

    # ══════════════════════════════════════════════════════════════════════════
    #  SECTION 3 — الإطار المكاني والزماني
    # ══════════════════════════════════════════════════════════════════════════
    x3s = X(244)
    _section('الإطار المكاني والزماني للدورة التكوينية:', 416, 427, 455, 514, [
        (x3s, X(510), 'مكان التكوين'),
        (X(44), x3s, 'تاريخ الدورة التكوينية'),
    ], [
        ('centre', x3s, X(510), lieu_form, F_AR),
        ('centre', X(44), x3s, date_disp, F_ARB),
    ])

    # ══════════════════════════════════════════════════════════════════════════
    #  SECTION 4 — الطرق والمعينات البيداغوجية
    # ══════════════════════════════════════════════════════════════════════════
    x4s = X(282)
    _section('الطرق والمعينات البيداغوجية:', 539, 550, 576, 640, [
        (x4s, X(510), 'الطرق البيداغوجية'),
        (X(44), x4s, 'المعينات البيداغوجية'),
    ], [
        ('puces', x4s, X(510), _split_items(methodes), F_AR),
        ('puces', X(44), x4s, _split_items(moyens), F_AR),
    ])

    # ══════════════════════════════════════════════════════════════════════════
    #  SECTION 5 — الإعداد المادّي والتجهيزات
    # ══════════════════════════════════════════════════════════════════════════
    x5s = X(277)
    _section('الإعداد المادّي والتجهيزات والمعدّات الخصوصية:', 665, 677, 703, 728, [
        (x5s, X(510), 'الإعداد المادّي'),
        (X(44), x5s, 'التجهيزات والمعدّات الخصوصية'),
    ], [
        ('puces', x5s, X(510), _items(preparation), F_AR),
        ('centre', X(44), x5s, equipements, F_AR),
    ])

    c.save()
    return output_path
