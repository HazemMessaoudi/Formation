# -*- coding: utf-8 -*-
"""شهادات المشاركة (v1.7) — une شهادة par مشارك حاضر, A4 paysage.

Aucun modèle officiel n'a été fourni : le gabarit reprend l'identité du
مركز (en-tête national, logo de l'École, nom du centre, signataire), avec un
double cadre sobre. Les présents sont ceux de ورقة الحضور (مستحقّات) : une
شهادة ne se délivre qu'une fois la présence enregistrée.

Le texte s'accorde au الجنس du مشارك quand il est connu (شارك / شاركت).
"""

import os
from datetime import datetime

from reportlab.lib import colors
from reportlab.pdfgen import canvas

from core import chemins, identite
from core import pdf_generator as pg

A4P = (841.89, 595.28)          # A4 paysage (pt)
BLEU = colors.HexColor('#1F3A68')
OR = colors.HexColor('#B08D3C')
NOIR = colors.black

MOIS = ['جانفي', 'فيفري', 'مارس', 'أفريل', 'ماي', 'جوان', 'جويلية', 'أوت',
        'سبتمبر', 'أكتوبر', 'نوفمبر', 'ديسمبر']


def date_longue(date_iso):
    try:
        d = datetime.strptime(date_iso or '', '%Y-%m-%d')
        return f'{d.day} {MOIS[d.month - 1]} {d.year}'
    except (TypeError, ValueError):
        return str(date_iso or '')


def _sans_tatweel(t):
    return ' '.join(str(t or '').replace('ـ', '').split())


def _feminin(sexe):
    return str(sexe or '').strip() in ('أنثى', 'انثى', 'F', 'f')


def _centre(c, texte, y, font, size, couleur=NOIR, largeur_max=640):
    """Ligne arabe centrée ; réduite si elle déborde (≥ 60 % de la taille)."""
    s = size
    while s > size * 0.6 and pg._w(c, pg._arh(texte), font, s) > largeur_max:
        s -= 0.5
    c.setFont(font, s)
    c.setFillColor(couleur)
    c.drawCentredString(A4P[0] / 2, y, pg._arh(texte))
    return s


def _cadre(c):
    w, h = A4P
    c.setStrokeColor(BLEU)
    c.setLineWidth(4)
    c.rect(22, 22, w - 44, h - 44, stroke=1, fill=0)
    c.setStrokeColor(OR)
    c.setLineWidth(1.2)
    c.rect(32, 32, w - 64, h - 64, stroke=1, fill=0)
    # coins
    for x, y in ((32, 32), (w - 32, 32), (32, h - 32), (w - 32, h - 32)):
        c.setFillColor(OR)
        c.circle(x, y, 3.2, stroke=0, fill=1)


def _page(c, base_dir, d, p, numero, total):
    w, h = A4P
    _cadre(c)
    # En-tête national (droite) et logo (centre)
    c.setFillColor(NOIR)
    c.setFont(pg.F_ARB, 11)
    y = h - 62
    for ligne in list(identite.ENTETE_NATIONAL) + [d['nom_centre']]:
        c.drawCentredString(w - 150, y, pg._arh(ligne))
        y -= 14
    logo = os.path.join(base_dir, 'static', 'images', 'logo.jpg')
    if os.path.exists(logo):
        c.drawImage(logo, w / 2 - 30, h - 132, width=60, height=78,
                    preserveAspectRatio=True, anchor='c', mask='auto')

    fem = _feminin(p.get('sexe'))
    _centre(c, 'شهادة مشاركة', h - 185, pg.F_DEC, 40, BLEU)
    c.setStrokeColor(OR)
    c.setLineWidth(1)
    c.line(w / 2 - 110, h - 198, w / 2 + 110, h - 198)

    _centre(c, f'يشهد رئيس {d["nom_centre"]} بأنّ', h - 232, pg.F_AR, 17)
    nom = f'{(p.get("grade") or "").strip()} {(p.get("nom_prenom") or "").strip()}'.strip()
    _centre(c, nom, h - 268, pg.F_ARB, 26, BLEU)
    y = h - 292
    if (p.get('identifiant_unique') or '').strip():
        _centre(c, f'المعرّف الوحيد: {p["identifiant_unique"].strip()}', y, pg.F_AR, 12.5)
    verbe = 'قد شاركت' if fem else 'قد شارك'
    _centre(c, f'{verbe} في الدورة التكوينيّة حول « {d["titre"]} »', h - 324, pg.F_AR, 17)
    lieu = _sans_tatweel(d.get('lieu_formation'))
    quand = f'يوم {date_longue(d.get("date_formation"))}'
    # V2 — دورة متعدّدة الأيّام : « من يوم 12 إلى يوم 14 أكتوبر 2026 »
    from core import jours as _jours
    date_sign = date_longue(d.get('date_formation'))
    if _jours.est_multi_jours(d.get('date_formation'), d.get('date_fin')):
        quand = _jours.plage_longue(d.get('date_formation'), d.get('date_fin'), 'يوم')
        date_sign = date_longue(_jours.derniere_date(d))
    if lieu:
        # « بمركز… », « بالقصرين » : la préposition s'attache au mot
        lieu = lieu if lieu.startswith('ب') and not lieu.startswith('بطاقة') else 'ب' + lieu
        ligne = f'المنظَّمة {lieu} {quand}'
    else:
        ligne = f'المنظَّمة {quand}'
    _centre(c, ligne, h - 352, pg.F_AR, 17)
    # V3.0.1 — lignes « بتأطير … » et « وقد سُلّمت … » retirées (demande du centre)

    # Date et signature (gauche)
    ville = (d.get('ville_centre') or '').strip()
    c.setFillColor(NOIR)
    c.setFont(pg.F_AR, 13)
    xs = 215
    c.drawCentredString(xs, 140, pg._arh(f'{ville} في {date_sign}' if ville else date_sign))
    c.setFont(pg.F_ARB, 14)
    c.drawCentredString(xs, 114, pg._arh(f'رئيس {d["nom_centre"]}'))
    resp = f'{(d.get("titre_responsable") or "").strip()} {(d.get("nom_responsable") or "").strip()}'.strip()
    if resp:
        c.drawCentredString(xs, 95, pg._arh(resp))
    cachet = pg._chemin_cachet(base_dir)
    if cachet:
        c.drawImage(cachet, xs - 45, 40, width=90, height=90,
                    preserveAspectRatio=True, anchor='c', mask='auto')

    # Référence discrète (droite, bas)
    c.setFont(pg.F_AR, 8)
    c.setFillColor(colors.HexColor('#555555'))
    c.drawRightString(w - 48, 44, pg._arh(f'شهادة {numero}/{total} — {d.get("date_formation") or ""}'))


def generer(donnees, participants, base_dir):
    """PDF des شهادات (une page par مشارك). Renvoie le chemin (transitoire)."""
    pg._register_fonts(base_dir)
    chemin = chemins.chemin_pdf_transitoire('shahadat')
    c = canvas.Canvas(chemin, pagesize=A4P)
    c.setTitle('شهادات المشاركة')
    total = len(participants)
    for i, p in enumerate(participants, 1):
        if i > 1:
            c.showPage()
        _page(c, base_dir, donnees, p, i, total)
    c.save()
    return chemin
