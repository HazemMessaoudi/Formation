# -*- coding: utf-8 -*-
"""طباعة السّجلّ السّنوي (v1.7) — le سجلّ des مراسلات d'une année, en PDF
officiel, pour l'archivage papier de fin d'année.

Même contenu que l'export Excel : الرقم | المرجع | نوع الوثيقة | الموضوع |
الحالة | تاريخ الترسيم. En-tête national sur la première page, en-tête des
colonnes répété sur chaque page, « الصفحة n/N » en pied. Sous le tableau :
les أعداد rendus au pool (فسخ) et les lacunes éventuelles, puis la clôture
signée pour un سجلّ d'une année écoulée.
"""

from datetime import datetime

from reportlab.lib import colors
from reportlab.pdfgen import canvas

from core import chemins, identite
from core import pdf_generator as pg

A4 = (595.28, 841.89)
BLEU_ENTETE = colors.HexColor('#5B9BD5')
GRIS = colors.HexColor('#F2F2F2')

# Colonnes, de DROITE à gauche : (titre, largeur pt)
COLONNES = (('الرقم', 42), ('المرجع', 118), ('نوع الوثيقة', 86), ('الموضوع', 190),
            ('الحالة', 46), ('تاريخ الترسيم', 63))
MARGE = 25.0
TAILLE = 9.5
LEAD = 12.0


def _lignes_objet(c, texte, largeur):
    return pg._wrap(c, str(texte or '').strip() or '—', pg.F_AR, TAILLE, largeur) or ['']


class _PDFNumerote(canvas.Canvas):
    """Canvas qui connaît le nombre total de pages (« الصفحة n/N »)."""

    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self._pages = []

    def showPage(self):
        self._pages.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        total = len(self._pages)
        for etat in self._pages:
            self.__dict__.update(etat)
            self.setFont(pg.F_AR, 8.5)
            self.setFillColor(colors.black)
            self.drawCentredString(A4[0] / 2, 18, pg.ar(f'الصفحة {self._pageNumber}/{total}'))
            super().showPage()
        super().save()


def generer(entrees, type_lettre, annee, cfg, base_dir, liberes=(), lacunes=(),
            ouverte=True):
    pg._register_fonts(base_dir)
    chemin = chemins.chemin_pdf_transitoire('registre')
    c = _PDFNumerote(chemin, pagesize=A4)
    nom_serie = 'الداخليّة' if type_lettre == 'interne' else 'الخارجيّة'
    c.setTitle(f'سجلّ المراسلات {nom_serie} {annee}')
    w, h = A4
    x_droite = w - MARGE
    largeurs = [l for _, l in COLONNES]
    x_cols = [x_droite]
    for l in largeurs:
        x_cols.append(x_cols[-1] - l)
    nom_centre = identite.nom_centre(cfg)

    def entete_premiere_page():
        c.setFillColor(colors.black)
        c.setFont(pg.F_ARB, 11)
        y = h - 40
        for ligne in list(identite.ENTETE_NATIONAL) + [nom_centre]:
            c.drawCentredString(x_droite - 90, y, pg.ar(ligne))
            y -= 13.5
        c.setFont(pg.F_ARB, 18)
        c.drawCentredString(w / 2, h - 150, pg.ar(f'سجلّ المراسلات {nom_serie}'))
        c.setFont(pg.F_ARB, 14)
        c.drawCentredString(w / 2, h - 172, pg.ar(f'سنة {annee}'))
        c.setFont(pg.F_AR, 10)
        etat = 'مفتوح' if ouverte else 'مغلق'
        c.drawCentredString(w / 2, h - 190, pg.ar(
            f'عدد المراسلات المسجَّلة: {len(entrees)} — السّجلّ {etat} — '
            f'طُبع يوم {datetime.now():%d/%m/%Y}'))
        return h - 205

    def entete_colonnes(y):
        c.setFillColor(BLEU_ENTETE)
        c.rect(x_cols[-1], y - 18, x_droite - x_cols[-1], 18, stroke=0, fill=1)
        c.setFillColor(colors.black)
        c.setFont(pg.F_ARB, 10)
        for i, (t, _l) in enumerate(COLONNES):
            c.drawCentredString((x_cols[i] + x_cols[i + 1]) / 2, y - 12.8, pg.ar(t))
        c.setLineWidth(0.8)
        c.rect(x_cols[-1], y - 18, x_droite - x_cols[-1], 18, stroke=1, fill=0)
        return y - 18

    y = entete_colonnes(entete_premiere_page())
    for k, e in enumerate(entrees):
        objet = _lignes_objet(c, e.get('objet'), largeurs[3] - 8)
        hauteur = max(16, len(objet) * LEAD + 5)
        if y - hauteur < 40:
            c.showPage()
            y = entete_colonnes(h - 40)
        if k % 2:
            c.setFillColor(GRIS)
            c.rect(x_cols[-1], y - hauteur, x_droite - x_cols[-1], hauteur, stroke=0, fill=1)
        c.setFillColor(colors.black)
        base = y - 11.5
        valeurs = ['%04d' % int(e.get('numero') or 0), e.get('ref_complet') or '',
                   e.get('source_label') or '', None,
                   'محجوز' if e.get('statut') == 'provisoire' else 'نهائي',
                   (e.get('date_attribution') or '')[:10]]
        for i, v in enumerate(valeurs):
            cx = (x_cols[i] + x_cols[i + 1]) / 2
            if i == 3:
                yy = base
                c.setFont(pg.F_AR, TAILLE)
                for ln in objet:
                    c.drawRightString(x_cols[i] - 4, yy, ln)
                    yy -= LEAD
            elif i in (1, 5, 0):
                c.setFont(pg.F_AR, TAILLE)
                c.drawCentredString(cx, base, str(v))        # latin / chiffres
            else:
                c.setFont(pg.F_AR, TAILLE)
                c.drawCentredString(cx, base, pg.ar(v))
        c.setLineWidth(0.4)
        c.setStrokeColor(colors.HexColor('#999999'))
        c.line(x_cols[-1], y - hauteur, x_droite, y - hauteur)
        c.setStrokeColor(colors.black)
        for x in x_cols:
            c.line(x, y, x, y - hauteur)
        y -= hauteur
    if not entrees:
        c.setFont(pg.F_AR, 11)
        c.drawCentredString(w / 2, y - 24, pg.ar('لا توجد مراسلات مسجَّلة في هذا السّجلّ.'))
        y -= 30

    # Notes sous le tableau
    notes = []
    if liberes:
        notes.append('أعداد مُرجعة بالفسخ في انتظار إعادة الإسناد: '
                     + '، '.join('%04d' % n for n in liberes))
    if lacunes:
        notes.append('أعداد غير موجودة في السّجلّ: ' + '، '.join('%04d' % n for n in lacunes))
    y -= 20
    for n in notes:
        for ln in pg._wrap(c, n, pg.F_AR, 10, w - 2 * MARGE):
            if y < 60:
                c.showPage()
                y = h - 50
            c.setFont(pg.F_AR, 10)
            c.drawRightString(x_droite, y, ln)
            y -= 14
    # Clôture (سجلّ d'une année écoulée) : attestation et signature
    if not ouverte:
        if y < 150:
            c.showPage()
            y = h - 60
        c.setFont(pg.F_AR, 11)
        c.drawRightString(x_droite, y - 10, pg.ar(
            f'أُغلق هذا السّجلّ على العدد {max([int(e.get("numero") or 0) for e in entrees] or [0]):04d}.'))
        c.setFont(pg.F_ARB, 12)
        resp = f'{cfg.get("titre_responsable", "")} {cfg.get("nom_responsable", "")}'.strip()
        c.drawCentredString(150, y - 50, pg.ar(f'رئيس {nom_centre}'))
        if resp:
            c.drawCentredString(150, y - 68, pg.ar(resp))
    c.showPage()
    c.save()
    return chemin
