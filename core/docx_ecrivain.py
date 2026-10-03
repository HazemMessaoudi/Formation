# -*- coding: utf-8 -*-
"""Écriture de documents Word (.docx) arabes — SANS dépendance (v1.7).

Un .docx est une archive ZIP de fichiers XML (Office Open XML). Ce module
en produit le strict nécessaire, à la main, comme `core/bataqa_import.py`
les lit déjà : aucune bibliothèque à installer sur les postes hors ligne.

Tout est pensé pour l'arabe :
  • section et paragraphes en droite-à-gauche (`w:bidi`) ;
  • tableaux en ordre visuel RTL (`w:bidiVisual`) : la PREMIÈRE colonne
    donnée est la plus à DROITE ;
  • tailles et graisses appliquées aussi aux écritures complexes
    (`w:szCs`, `w:bCs`) — sans cela Word ignore la taille du texte arabe ;
  • police Arial (celle des modèles officiels) pour toutes les écritures.

Unités : centimètres à l'entrée ; convertis en twips (1/20 pt) et en EMU.
"""

import io
import os
import zipfile
from xml.sax.saxutils import escape

TWIPS_CM = 566.929          # 1 cm = 566,929 twips
EMU_CM = 360000             # 1 cm = 360 000 EMU
A4 = (21.0, 29.7)

_NS = ('xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" '
       'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" '
       'xmlns:wp="http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing" '
       'xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" '
       'xmlns:pic="http://schemas.openxmlformats.org/drawingml/2006/picture"')


def tw(cm):
    return int(round(cm * TWIPS_CM))


def pt_cm(pt):
    return pt / 72.0 * 2.54


def _x(texte):
    return escape(str(texte if texte is not None else ''))


# ─── Runs et paragraphes ─────────────────────────────────────────────────────

def run(texte, taille=12, gras=False, souligne=False, police='Arial', ltr=False,
        couleur=None):
    """Un fragment de texte uniformément formaté (XML <w:r>)."""
    t = _x(texte)
    rpr = [f'<w:rFonts w:ascii="{police}" w:hAnsi="{police}" w:cs="{police}" '
           f'w:eastAsia="{police}"/>']
    if gras:
        rpr.append('<w:b/><w:bCs/>')
    if souligne:
        rpr.append('<w:u w:val="single"/>')
    if couleur:
        rpr.append(f'<w:color w:val="{couleur}"/>')
    demi = int(round(taille * 2))
    rpr.append(f'<w:sz w:val="{demi}"/><w:szCs w:val="{demi}"/>')
    if not ltr:
        rpr.append('<w:rtl/>')
    rpr.append('<w:lang w:val="fr-FR" w:bidi="ar-TN"/>')
    return (f'<w:r><w:rPr>{"".join(rpr)}</w:rPr>'
            f'<w:t xml:space="preserve">{t}</w:t></w:r>')


# Alignements LOGIQUES (start / end) : dans un paragraphe RTL, « left » et
# « right » sont interprétés différemment par Word et par LibreOffice ;
# start / end ne sont ambigus pour personne.
_JC_RTL = {'droite': 'start', 'gauche': 'end', 'centre': 'center',
           'justifie': 'both', 'distribue': 'distribute'}
_JC_LTR = {'droite': 'end', 'gauche': 'start', 'centre': 'center',
           'justifie': 'both', 'distribue': 'distribute'}


def paragraphe(contenu='', align='droite', taille=12, gras=False, avant=0, apres=0,
               interligne=None, fond=None, bordure_bas=False, retrait_debut=0,
               retrait_fin=0, garder_suivant=False, saut_avant=False, ltr=False,
               ligne_pt=None):
    """Paragraphe RTL. `contenu` : texte simple, ou liste de runs déjà formés.
    `avant`/`apres` en points ; `interligne` : multiple (1.0, 1.15, 1.5…)."""
    if isinstance(contenu, (list, tuple)):
        runs = ''.join(contenu)
    else:
        runs = run(contenu, taille, gras, ltr=ltr) if str(contenu) != '' else ''
    ppr = []
    if garder_suivant:
        ppr.append('<w:keepNext/>')
    if saut_avant:
        ppr.append('<w:pageBreakBefore/>')
    if bordure_bas:
        ppr.append('<w:pBdr><w:bottom w:val="single" w:sz="6" w:space="1" w:color="000000"/></w:pBdr>')
    if fond:
        ppr.append(f'<w:shd w:val="clear" w:color="auto" w:fill="{fond}"/>')
    if not ltr:
        ppr.append('<w:bidi/>')
    esp = f'<w:spacing w:before="{int(avant * 20)}" w:after="{int(apres * 20)}"'
    if ligne_pt:
        # interligne EXACT (en points), comme le pas des lignes des PDF :
        # le rendu ne dépend plus de la hauteur propre à chaque police.
        esp += f' w:line="{int(round(ligne_pt * 20))}" w:lineRule="exact"'
    elif interligne:
        esp += f' w:line="{int(round(240 * interligne))}" w:lineRule="auto"'
    ppr.append(esp + '/>')
    if retrait_debut or retrait_fin:
        ppr.append(f'<w:ind w:start="{tw(retrait_debut)}" w:end="{tw(retrait_fin)}"/>')
    jc = (_JC_LTR if ltr else _JC_RTL).get(align, align)
    ppr.append(f'<w:jc w:val="{jc}"/>')
    # taille de la marque de paragraphe (hauteur d'une ligne vide)
    demi = int(round(taille * 2))
    rtl = '' if ltr else '<w:rtl/>'
    ppr.append(f'<w:rPr><w:sz w:val="{demi}"/><w:szCs w:val="{demi}"/>{rtl}</w:rPr>')
    return f'<w:p><w:pPr>{"".join(ppr)}</w:pPr>{runs}</w:p>'


def saut_de_page():
    return '<w:p><w:r><w:br w:type="page"/></w:r></w:p>'


# ─── Tableaux ────────────────────────────────────────────────────────────────

def _bord(val, sz=4):
    if val in (None, 'aucun', 'nil'):
        return 'w:val="nil"'
    return f'w:val="{val}" w:sz="{sz}" w:space="0" w:color="000000"'


def cellule(contenu, largeur_cm, fond=None, valign='center', fusion_v=None,
            colonnes=1, bords=None, marges_cm=None):
    """Une cellule. `contenu` : liste de paragraphes XML (ou un seul).
    `fusion_v` : 'debut' / 'suite' (fusion verticale) ; `colonnes` : gridSpan.
    `bords` : dict {'haut','bas','debut','fin': (val, sz)} propre à la cellule."""
    if isinstance(contenu, str):
        contenu = [contenu]
    contenu = [c for c in contenu if c] or [paragraphe('')]
    if contenu[-1].startswith('<w:tbl>'):
        # Une cellule DOIT se terminer par un paragraphe (sinon Word la
        # déclare corrompue et LibreOffice perd les bordures).
        contenu.append(paragraphe('', taille=2))
    tcpr = [f'<w:tcW w:w="{tw(largeur_cm)}" w:type="dxa"/>']
    if colonnes > 1:
        tcpr.append(f'<w:gridSpan w:val="{colonnes}"/>')
    if fusion_v == 'debut':
        tcpr.append('<w:vMerge w:val="restart"/>')
    elif fusion_v == 'suite':
        tcpr.append('<w:vMerge/>')
    if bords:
        b = ''.join(f'<w:{({"haut": "top", "bas": "bottom", "debut": "start", "fin": "end"})[k]} '
                    f'{_bord(*v) if isinstance(v, tuple) else _bord(v)}/>'
                    for k, v in bords.items())
        tcpr.append(f'<w:tcBorders>{b}</w:tcBorders>')
    if fond:
        tcpr.append(f'<w:shd w:val="clear" w:color="auto" w:fill="{fond}"/>')
    if marges_cm is not None:
        m = tw(marges_cm)
        tcpr.append(f'<w:tcMar><w:top w:w="{m}" w:type="dxa"/><w:bottom w:w="{m}" w:type="dxa"/>'
                    f'</w:tcMar>')
    tcpr.append(f'<w:vAlign w:val="{valign}"/>')
    return f'<w:tc><w:tcPr>{"".join(tcpr)}</w:tcPr>{"".join(contenu)}</w:tc>'


def ligne(cellules, entete=False, hauteur_cm=None, insecable=True, exacte=False):
    trpr = []
    if insecable:
        trpr.append('<w:cantSplit/>')
    if entete:
        trpr.append('<w:tblHeader/>')
    if hauteur_cm:
        regle = 'exact' if exacte else 'atLeast'
        trpr.append(f'<w:trHeight w:val="{tw(hauteur_cm)}" w:hRule="{regle}"/>')
    return f'<w:tr><w:trPr>{"".join(trpr)}</w:trPr>{"".join(cellules)}</w:tr>'


def tableau(largeurs_cm, lignes, bordure_ext=('double', 4), bordure_h=('single', 4),
            bordure_v=('double', 4), centre=True, marge_cellule_cm=0.12):
    """Tableau RTL : `largeurs_cm[0]` est la colonne la plus à DROITE."""
    total = sum(largeurs_cm)
    grille = ''.join(f'<w:gridCol w:w="{tw(l)}"/>' for l in largeurs_cm)
    ext = _bord(*bordure_ext) if bordure_ext else _bord(None)
    bh = _bord(*bordure_h) if bordure_h else _bord(None)
    bv = _bord(*bordure_v) if bordure_v else _bord(None)
    m = tw(marge_cellule_cm)
    jc = '<w:jc w:val="center"/>' if centre else ''
    tblpr = (f'<w:tblPr><w:bidiVisual/><w:tblW w:w="{tw(total)}" w:type="dxa"/>'
             f'{jc}'
             f'<w:tblBorders><w:top {ext}/><w:start {ext}/><w:bottom {ext}/><w:end {ext}/>'
             f'<w:insideH {bh}/><w:insideV {bv}/></w:tblBorders>'
             f'<w:tblLayout w:type="fixed"/>'
             f'<w:tblCellMar><w:start w:w="{m}" w:type="dxa"/><w:end w:w="{m}" w:type="dxa"/>'
             f'</w:tblCellMar><w:tblLook w:val="0000"/></w:tblPr>')
    return f'<w:tbl>{tblpr}<w:tblGrid>{grille}</w:tblGrid>{"".join(lignes)}</w:tbl>'


# ─── Document ────────────────────────────────────────────────────────────────

class DocumentWord:
    """Accumulateur de blocs XML ; `octets()` rend le .docx complet."""

    def __init__(self, marges_cm=(1.5, 1.6, 1.5, 1.6), page=A4, titre=''):
        self.blocs = []
        self.images = []            # (nom, octets)
        self.marges = marges_cm     # haut, droite(début), bas, gauche(fin)
        self.page = page
        self.titre = titre
        self.pied = None            # paragraphes XML du pied de page

    def ajouter(self, *xml):
        self.blocs.extend(x for x in xml if x)

    def image(self, chemin, largeur_cm, hauteur_cm, align='centre', apres=0, avant=0):
        """Paragraphe contenant une image (JPG/PNG), taille imposée."""
        xml = self.image_inline(chemin, largeur_cm, hauteur_cm)
        if not xml:
            return ''
        return paragraphe([xml], align=align, apres=apres, avant=avant, taille=6)

    def image_inline(self, chemin, largeur_cm, hauteur_cm):
        if not chemin or not os.path.exists(chemin):
            return ''
        ext = os.path.splitext(chemin)[1].lower().lstrip('.')
        ext = 'jpeg' if ext in ('jpg', 'jpeg') else 'png'
        n = len(self.images) + 1
        nom = f'image{n}.{ext}'
        with open(chemin, 'rb') as fh:
            self.images.append((nom, fh.read()))
        rid = f'rIdImg{n}'
        cx, cy = int(largeur_cm * EMU_CM), int(hauteur_cm * EMU_CM)
        return (
            f'<w:r><w:drawing><wp:inline distT="0" distB="0" distL="0" distR="0">'
            f'<wp:extent cx="{cx}" cy="{cy}"/><wp:docPr id="{n}" name="صورة {n}"/>'
            f'<a:graphic><a:graphicData uri="http://schemas.openxmlformats.org/drawingml/2006/picture">'
            f'<pic:pic><pic:nvPicPr><pic:cNvPr id="{n}" name="{nom}"/><pic:cNvPicPr/></pic:nvPicPr>'
            f'<pic:blipFill><a:blip r:embed="{rid}"/><a:stretch><a:fillRect/></a:stretch></pic:blipFill>'
            f'<pic:spPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="{cx}" cy="{cy}"/></a:xfrm>'
            f'<a:prstGeom prst="rect"><a:avLst/></a:prstGeom></pic:spPr></pic:pic>'
            f'</a:graphicData></a:graphic></wp:inline></w:drawing></w:r>')

    # ── assemblage ──────────────────────────────────────────────────────────
    def _document_xml(self):
        h, d, b, g = (tw(x) for x in self.marges)
        pw, ph = (tw(x) for x in self.page)
        pied_ref = ('<w:footerReference w:type="default" r:id="rIdPied"/>'
                    if self.pied else '')
        # V2 : page paysage (بطاقة حضور de 4 à 6 jours)
        orient = ' w:orient="landscape"' if pw > ph else ''
        sect = (f'<w:sectPr>{pied_ref}<w:pgSz w:w="{pw}" w:h="{ph}"{orient}/>'
                f'<w:pgMar w:top="{h}" w:right="{d}" w:bottom="{b}" w:left="{g}" '
                f'w:header="425" w:footer="425" w:gutter="0"/><w:bidi/></w:sectPr>')
        return (f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                f'<w:document {_NS}><w:body>{"".join(self.blocs)}{sect}</w:body></w:document>')

    def _styles_xml(self):
        return ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                f'<w:styles {_NS}><w:docDefaults><w:rPrDefault><w:rPr>'
                '<w:rFonts w:ascii="Arial" w:hAnsi="Arial" w:cs="Arial" w:eastAsia="Arial"/>'
                '<w:sz w:val="24"/><w:szCs w:val="24"/><w:lang w:val="fr-FR" w:bidi="ar-TN"/>'
                '</w:rPr></w:rPrDefault><w:pPrDefault><w:pPr><w:bidi/>'
                '<w:spacing w:before="0" w:after="0" w:line="240" w:lineRule="auto"/>'
                '</w:pPr></w:pPrDefault></w:docDefaults>'
                '<w:style w:type="paragraph" w:default="1" w:styleId="Normal"><w:name w:val="Normal"/>'
                '<w:pPr><w:bidi/></w:pPr><w:rPr><w:rtl/></w:rPr></w:style>'
                '<w:style w:type="table" w:default="1" w:styleId="TableNormal">'
                '<w:name w:val="Normal Table"/><w:tblPr><w:tblInd w:w="0" w:type="dxa"/>'
                '<w:tblCellMar><w:top w:w="0" w:type="dxa"/><w:left w:w="108" w:type="dxa"/>'
                '<w:bottom w:w="0" w:type="dxa"/><w:right w:w="108" w:type="dxa"/></w:tblCellMar>'
                '</w:tblPr></w:style></w:styles>')

    def octets(self):
        buf = io.BytesIO()
        ct_img = ''.join(sorted({f'<Default Extension="{n.rsplit(".", 1)[1]}" '
                                 f'ContentType="image/{n.rsplit(".", 1)[1]}"/>'
                                 for n, _ in self.images}))
        pied_ct = ('<Override PartName="/word/footer1.xml" ContentType="application/'
                   'vnd.openxmlformats-officedocument.wordprocessingml.footer+xml"/>'
                   if self.pied else '')
        content_types = (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
            '<Default Extension="xml" ContentType="application/xml"/>' + ct_img +
            '<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-'
            'officedocument.wordprocessingml.document.main+xml"/>'
            '<Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-'
            'officedocument.wordprocessingml.styles+xml"/>'
            '<Override PartName="/word/settings.xml" ContentType="application/vnd.openxmlformats-'
            'officedocument.wordprocessingml.settings+xml"/>' + pied_ct +
            '<Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-'
            'package.core-properties+xml"/></Types>')
        rels = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/'
                'relationships/officeDocument" Target="word/document.xml"/>'
                '<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/'
                'relationships/metadata/core-properties" Target="docProps/core.xml"/>'
                '</Relationships>')
        doc_rels = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                    '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                    '<Relationship Id="rIdStyles" Type="http://schemas.openxmlformats.org/officeDocument/'
                    '2006/relationships/styles" Target="styles.xml"/>'
                    '<Relationship Id="rIdSettings" Type="http://schemas.openxmlformats.org/officeDocument/'
                    '2006/relationships/settings" Target="settings.xml"/>')
        for i, (nom, _) in enumerate(self.images, 1):
            doc_rels += (f'<Relationship Id="rIdImg{i}" Type="http://schemas.openxmlformats.org/'
                         f'officeDocument/2006/relationships/image" Target="media/{nom}"/>')
        if self.pied:
            doc_rels += ('<Relationship Id="rIdPied" Type="http://schemas.openxmlformats.org/'
                         'officeDocument/2006/relationships/footer" Target="footer1.xml"/>')
        doc_rels += '</Relationships>'
        settings = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                    f'<w:settings {_NS}><w:defaultTabStop w:val="720"/>'
                    '<w:compat><w:compatSetting w:name="compatibilityMode" '
                    'w:uri="http://schemas.microsoft.com/office/word" w:val="15"/></w:compat>'
                    '</w:settings>')
        core = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                '<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/'
                'metadata/core-properties" xmlns:dc="http://purl.org/dc/elements/1.1/">'
                f'<dc:title>{_x(self.titre)}</dc:title><dc:creator>نظام إدارة التكوين الديواني'
                '</dc:creator></cp:coreProperties>')
        with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as z:
            z.writestr('[Content_Types].xml', content_types)
            z.writestr('_rels/.rels', rels)
            z.writestr('word/document.xml', self._document_xml())
            z.writestr('word/styles.xml', self._styles_xml())
            z.writestr('word/settings.xml', settings)
            z.writestr('word/_rels/document.xml.rels', doc_rels)
            z.writestr('docProps/core.xml', core)
            if self.pied:
                z.writestr('word/footer1.xml',
                           '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                           f'<w:ftr {_NS}>{"".join(self.pied)}</w:ftr>')
                # v1.7.1 : le pied peut porter une image (emblème de l'École) —
                # il lui faut ses propres relations vers les médias.
                if self.images:
                    z.writestr('word/_rels/footer1.xml.rels',
                               '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                               '<Relationships xmlns="http://schemas.openxmlformats.org/'
                               'package/2006/relationships">' + ''.join(
                                   f'<Relationship Id="rIdImg{i}" Type="http://schemas.'
                                   f'openxmlformats.org/officeDocument/2006/relationships/'
                                   f'image" Target="media/{nom}"/>'
                                   for i, (nom, _) in enumerate(self.images, 1))
                               + '</Relationships>')
            for nom, data in self.images:
                z.writestr(f'word/media/{nom}', data)
        return buf.getvalue()
