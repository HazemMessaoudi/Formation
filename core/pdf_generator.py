"""
Générateur PDF – Lettre « إشعار بتكوين » / برنامج التكوين
=========================================================
Reproduction fidèle du modèle officiel.

Toutes les coordonnées (traits du cadre, colonnes du tableau, lignes de base
du texte) proviennent d'une extraction géométrique du PDF original.
Page : 595.32 × 830.64 pt — coordonnées ReportLab (origine en bas à gauche).

Les tailles de police sont calibrées pour que le rendu occupe exactement la
même largeur que le modèle d'origine :
  • KasserineAr  = Noto Sans Arabic + Liberation Sans  (≈ Arial)
  • Amiri Bold                                          (≈ Traditional Arabic Bold)
"""
import os
from datetime import datetime

from reportlab.pdfgen import canvas  # noqa: F401 — pg.canvas : point d'accroche des tests
from reportlab.lib import colors
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

import arabic_reshaper
from bidi.algorithm import get_display

from core import identite
from core import chemins


# ══════════════════════════════════════════════════════════════════════════════
#  GÉOMÉTRIE DU MODÈLE ORIGINAL
# ══════════════════════════════════════════════════════════════════════════════

PW, PH = 595.32, 830.64

RED   = colors.Color(1, 0, 0)
BLACK = colors.black

# ── Polices ──────────────────────────────────────────────────────────────────
# KasserineAr = Noto Sans Arabic (arabe) fusionné avec Liberation Sans (latin,
# métriques identiques à Arial) : une seule police couvre l'arabe, les chiffres,
# les parenthèses, la barre oblique et les lettres latines accentuées.
F_AR   = 'KasAr'         # ≈ Arial arabe
F_ARB  = 'KasArB'
F_DEC  = 'AmiriB'        # ≈ Traditional Arabic Bold
F_LAT  = 'KasAr'         # ≈ Arial / Calibri (latin)
F_LATB = 'KasArB'

# Police des titres décoratifs (« مذكــرة », « إلـــى ») et du bloc signature.
#   True  → Amiri gras (≈ Traditional Arabic), comme sur les modèles officiels
#   False → Arial gras : TOUT le document est alors composé en Arial
POLICE_DECORATIVE = False

# ── Tailles calibrées (largeur identique au modèle) ─────────────────────────
S_LAT    = 12.0          # Réf / Version / Date / Page      (min 12)
S_INST   = 12.0          # identification institution        (min 12)
S_MURA   = 12.0          # « مراسلة داخلية »                 (min 12)
S_TITRE  = 15.2          # « إلى » / « السيد مدير… »          (Trad. Arabic 18)
S_SUJET  = 14.0          # ligne « الموضوع »                 (Arial 16)
S_BODY   = 14.0          # corps                             (Arial 16)
S_WABAAD = 12.2          # « وبعد، »                          (Arial 14)
S_TAB    = 12.0          # tableau                           (min 12)
S_SIGN   = 15.2          # signature                         (Trad. Arabic 18)
S_MJ     = 9.5           # « الموجَّه إليهم » — titre et liste (volontairement petit)
S_PIED   = 8.0           # pied de page : coordonnées de l'École (petit, cf. modèle)

# ── Pied de page « coordonnées de l'École » ─────────────────────────────────
PIED_Y0   = 16.0                     # bas du cadre
PIED_H    = 46.0                     # hauteur du cadre
PIED_LEAD = 9.6                      # interligne des 4 lignes
PIED_X0, PIED_X1 = 55.6, 524.6       # mêmes marges que le corps (TXT_L / TXT_R)
PIED_LOGO_H     = 40.0               # v1.7.1 : emblème de l'École en tête du pied
PIED_LOGO_RATIO = 176 / 225          # largeur / hauteur de static/images/logo.jpg
PIED_LOGO_ECART = 8.0                # espace emblème → texte
PIED_EMB_W = 34.0                    # largeur de l'emblème (30 ans) à droite

# ── En-tête (cadre) ─────────────────────────────────────────────────────────
HD_X0, HD_X1 = 59.3, 547.5
HD_Y_T, HD_Y_B = PH - 14.2, PH - 103.3
HD_V1, HD_V2 = 230.8, 389.2          # séparateurs de colonnes
HD_VL        = 151.5                 # séparateur libellé | valeur
HD_Y_R1 = PH - 58.1                  # sous « Réf »
HD_Y_R2 = PH - 72.0                  # sous « Version »
HD_Y_R3 = PH - 85.9                  # sous « Date »

# Lignes de base de l'en-tête
B_REF   = 787.2
B_VER   = 761.6
B_DATE  = 747.7
B_PAGE  = 733.8
B_MURA  = 743.4
# Bloc « institution » : 7 lignes. L'interligne est très légèrement resserré
# par rapport au modèle (12.68) pour que le jambage de la dernière ligne
# « بالقصرين » reste à l'intérieur du cadre avec la police de substitution.
B_INST0    = 805.7
LEAD_INST  = 14.0

LOGO_X0, LOGO_X1 = 294.9, 324.9
LOGO_Y0, LOGO_Y1 = PH - 58.0, PH - 14.7

# ── Corps ────────────────────────────────────────────────────────────────────
TXT_L, TXT_R = 55.6, 524.6           # marges du bloc de texte
C_TITRE  = 276.8                     # centre des lignes de destinataire
B_ILA    = 676.2
B_SAYED  = 648.6
B_SUJET  = 603.8
B_WABAAD = 567.1
B_BODY1  = 539.5
B_BODY2  = 522.5   # (+1.5 pt / modèle : évite que les jambages touchent le tableau)

W_ILA = 81.2                         # largeur cible de « إلـــى » (kashida)

# ── Tableau ──────────────────────────────────────────────────────────────────
TB_X     = [59.7, 128.5, 206.6, 305.8, 398.0, 486.0, 541.8]
TB_Y_TOP = PH - 313.0
TB_HDR_H = 56.2
TB_ROW_H = 62.4
TB_PAD   = 3.0
TB_LEAD  = 13.0                      # interligne dans les cellules (≥ S_TAB)
TB_LEAD_H = 14.0                     # interligne des en-têtes
TB_MIN_Y   = 72.0                    # limite basse du tableau sur une page
TB_CONT_TOP = PH - 128.0             # haut du tableau sur les pages suivantes

# ── Signature ────────────────────────────────────────────────────────────────
C_SIGN  = 181.4
B_SIGN1 = 174.3
B_SIGN2 = 146.7
STAMP_X0, STAMP_X1 = 144.9, 225.0
STAMP_Y0, STAMP_Y1 = PH - 772.5, PH - 693.0


_fonts_ok = False

# Police effectivement retenue — renseignée par _register_fonts(), utile pour
# vérifier sur le poste de travail quelle police compose réellement les PDF.
POLICE_ACTIVE = {'nom': '?', 'regular': '', 'bold': '', 'arial': False}

# Arial d'abord : le dossier « fonts/ » de l'application, puis les polices
# système Windows, puis les msttcorefonts sous Linux.
# NOTE : Liberation Sans est volontairement exclu — il a bien les métriques
# d'Arial mais NE contient PAS l'arabe ; la substitution intégrée est meilleure.
def _arial_candidates(fd):
    return [
        os.path.join(fd, 'Arial.ttf'),
        os.path.join(fd, 'arial.ttf'),
        r'C:\Windows\Fonts\arial.ttf',
        r'C:\Windows\Fonts\Arial.ttf',
        os.path.expandvars(r'%LOCALAPPDATA%\Microsoft\Windows\Fonts\arial.ttf'),
        '/usr/share/fonts/truetype/msttcorefonts/Arial.ttf',
        '/Library/Fonts/Arial.ttf',
        '/System/Library/Fonts/Supplemental/Arial.ttf',
    ]


def _arial_bold_candidates(fd):
    return [
        os.path.join(fd, 'Arial-Bold.ttf'),
        os.path.join(fd, 'arialbd.ttf'),
        r'C:\Windows\Fonts\arialbd.ttf',
        r'C:\Windows\Fonts\ArialBD.ttf',
        os.path.expandvars(r'%LOCALAPPDATA%\Microsoft\Windows\Fonts\arialbd.ttf'),
        '/usr/share/fonts/truetype/msttcorefonts/Arial_Bold.ttf',
        '/Library/Fonts/Arial Bold.ttf',
        '/System/Library/Fonts/Supplemental/Arial Bold.ttf',
    ]


def _find_font(candidates):
    for p in candidates:
        try:
            if p and os.path.exists(p):
                return p
        except Exception:
            continue
    return None


def _has_arabic(path):
    """Vrai si la police couvre l'arabe (teste le caractère ب U+0628)."""
    try:
        from fontTools.ttLib import TTFont as _FTFont
        f = _FTFont(path)
        return 0x0628 in f.getBestCmap()
    except Exception:
        # fontTools indisponible : un vrai Arial système couvre l'arabe
        return True


def _register_fonts(base_dir):
    global _fonts_ok
    if _fonts_ok:
        return
    fd = os.path.join(base_dir, 'fonts')

    arial_reg  = _find_font(_arial_candidates(fd))
    arial_bold = _find_font(_arial_bold_candidates(fd))

    if arial_reg and _has_arabic(arial_reg):
        # Arial véritable (cas normal sous Windows) — arabe + latin + chiffres
        reg, bold = arial_reg, (arial_bold or arial_reg)
        POLICE_ACTIVE.update(nom='Arial', regular=reg, bold=bold, arial=True)
    else:
        # Substitution intégrée : métriques d'Arial + arabe Noto
        reg  = os.path.join(fd, 'KasserineAr-Regular.ttf')
        bold = os.path.join(fd, 'KasserineAr-Bold.ttf')
        POLICE_ACTIVE.update(nom='KasserineAr (substitut Arial)',
                             regular=reg, bold=bold, arial=False)

    pdfmetrics.registerFont(TTFont(F_AR,  reg))
    pdfmetrics.registerFont(TTFont(F_ARB, bold))

    # Police décorative des titres (« مذكــرة ») et du bloc signature.
    # Mettre POLICE_DECORATIVE = False pour composer TOUT le document en Arial.
    if POLICE_DECORATIVE:
        pdfmetrics.registerFont(TTFont(F_DEC, os.path.join(fd, 'Amiri-Bold.ttf')))
    else:
        pdfmetrics.registerFont(TTFont(F_DEC, bold))

    _fonts_ok = True


# ══════════════════════════════════════════════════════════════════════════════
#  HELPERS TEXTE ARABE
# ══════════════════════════════════════════════════════════════════════════════

def ar(text):
    """Texte arabe logique → chaîne en ordre visuel LTR pour ReportLab."""
    if text is None or text == '':
        return ''
    return get_display(arabic_reshaper.reshape(str(text)))


def _w(c, txt, font, size):
    return c.stringWidth(txt, font, size)


def _kashida(c, prefix, suffix, target_w, font, size):
    """Construit « prefix ـــ suffix » allongé pour approcher `target_w`."""
    best, best_d = prefix + suffix, 1e9
    for n in range(0, 60):
        s = prefix + ('ـ' * n) + suffix
        d = abs(_w(c, ar(s), font, size) - target_w)
        if d < best_d:
            best, best_d = s, d
    return best


def _wrap_log(c, text, font, size, maxw, maxw_first=None):
    """Découpe un texte arabe en lignes tenant dans `maxw`, en conservant
    l'ordre LOGIQUE — à passer à `_justify_rtl`, qui reshape lui-même.
    `maxw_first` permet un retrait de première ligne."""
    text = str(text or '').strip()
    if not text:
        return ['']
    lines, cur = [], []
    for word in text.split():
        limite = maxw if lines else (maxw_first if maxw_first is not None else maxw)
        trial = cur + [word]
        if not cur or _w(c, ar(' '.join(trial)), font, size) <= limite:
            cur = trial
        else:
            lines.append(' '.join(cur))
            cur = [word]
    if cur:
        lines.append(' '.join(cur))
    return lines


def _wrap(c, text, font, size, maxw):
    """Découpe un texte arabe logique en lignes visuelles tenant dans `maxw`."""
    return [ar(l) for l in _wrap_log(c, text, font, size, maxw)]


def _seg_rtl(c, segments, x_right, y):
    """
    Dessine une suite de segments arabes donnés dans l'ordre LOGIQUE
    (du premier au dernier mot de la phrase), alignée à droite sur `x_right`.

    En ordre visuel LTR la FIN de la phrase arabe se place à GAUCHE :
    les segments sont donc dessinés à rebours en partant de la gauche.

    segments : [(texte_logique, police, taille, couleur), …]
    """
    prep   = [(ar(t), f, s, col) for t, f, s, col in segments]
    widths = [_w(c, t, f, s) for t, f, s, _ in prep]
    x = x_right - sum(widths)
    for (txt, font, size, col), wdt in zip(reversed(prep), reversed(widths)):
        c.setFont(font, size)
        c.setFillColor(col)
        c.drawString(x, y, txt)
        x += wdt


def _justify_rtl(c, text, font, size, x_left, x_right, y, color=BLACK):
    """Ligne arabe justifiée entre `x_left` et `x_right`.
    Si l'écart inter-mots dépasse 2.5× l'espace normal, on préfère
    l'alignement à droite pour éviter les espaces disgracieux."""
    parts = [p for p in ar(text).split(' ') if p]
    c.setFont(font, size)
    c.setFillColor(color)
    if len(parts) < 2:
        c.drawRightString(x_right, y, ar(text))
        return
    natural     = sum(_w(c, p, font, size) for p in parts)
    normal_space = _w(c, ' ', font, size)
    gap = (x_right - x_left - natural) / (len(parts) - 1)
    # Trop d'espace entre les mots → aligner à droite simplement
    if gap < 0 or gap > normal_space * 2.5:
        c.drawRightString(x_right, y, ar(text))
        return
    x = x_left
    for p in parts:
        c.drawString(x, y, p)
        x += _w(c, p, font, size) + gap


def _cell(c, lines, x_center, y_top, y_bot, font, size, color=BLACK, leading=TB_LEAD):
    """Lignes visuelles centrées horizontalement et verticalement dans la cellule."""
    n = len(lines)
    mid = (y_top + y_bot) / 2
    y = mid - 0.10 * size + (n - 1) * leading / 2
    c.setFont(font, size)
    c.setFillColor(color)
    for ln in lines:
        c.drawCentredString(x_center, y, ln)
        y -= leading


def compter_pages_pdf(chemin):
    """Nombre de pages d'un PDF produit par ReportLab, sans dépendance externe.

    On lit le `/Count` du nœud `/Type /Pages`; à défaut on compte les objets
    `/Type /Page`. Renvoie 0 si le fichier est illisible — un décompte faux vaut
    mieux qu'un plantage au moment d'imprimer un document officiel."""
    import re as _re
    try:
        with open(chemin, 'rb') as fh:
            data = fh.read()
    except OSError:
        return 0
    counts = [int(m) for m in _re.findall(rb'/Type\s*/Pages[^>]*?/Count\s+(\d+)', data)]
    counts += [int(m) for m in _re.findall(rb'/Count\s+(\d+)[^>]*?/Type\s*/Pages', data)]
    if counts:
        return max(counts)
    return len(_re.findall(rb'/Type\s*/Page[^s]', data))


def _draw_entete(c, lettre_data, base_dir, nom_centre=None, avec_centre=True):
    """Dessine le bloc d'en-tête officiel (cadre, référence, logo, institution)."""
    c.setStrokeColor(BLACK)
    c.setLineWidth(0.5)

    # Cadre + colonnes
    c.rect(HD_X0, HD_Y_B, HD_X1 - HD_X0, HD_Y_T - HD_Y_B, stroke=1, fill=0)
    c.line(HD_V1, HD_Y_B, HD_V1, HD_Y_T)
    c.line(HD_V2, HD_Y_B, HD_V2, HD_Y_T)
    # Colonne gauche : 4 rangées
    for yy in (HD_Y_R1, HD_Y_R2, HD_Y_R3):
        c.line(HD_X0, yy, HD_V1, yy)
    c.line(HD_VL, HD_Y_B, HD_VL, HD_Y_R1)
    # Colonne centrale : trait sous le logo
    c.line(HD_V1, HD_Y_R1, HD_V2, HD_Y_R1)

    # ── Référence (numéro de série en rouge) ───────────────────────────
    ref_full = str(lettre_data['ref'])
    if '-' in ref_full:
        ref_base, ref_num = ref_full.rsplit('-', 1)
        ref_base += '-'
    else:
        ref_base, ref_num = '', ref_full

    txt_b = f'Réf : {ref_base}'
    wb = _w(c, txt_b, F_LAT, S_LAT)
    wn = _w(c, ref_num, F_LAT, S_LAT)
    xs = (HD_X0 + HD_V1) / 2 - (wb + wn) / 2
    c.setFont(F_LAT, S_LAT)
    c.setFillColor(BLACK)
    c.drawString(xs, B_REF, txt_b)
    c.setFillColor(BLACK)
    c.drawString(xs + wb, B_REF, ref_num)

    # ── Version / Date / Page ──────────────────────────────────────────
    c.setFillColor(BLACK)
    c.setFont(F_LAT, S_LAT)
    cx_lbl = (HD_X0 + HD_VL) / 2
    cx_val = (HD_VL + HD_V1) / 2
    c.drawCentredString(cx_lbl, B_VER,  'Version')
    c.drawCentredString(cx_val, B_VER,  '01')
    c.drawCentredString(cx_lbl, B_DATE, 'Date')
    c.drawCentredString(cx_val, B_DATE, '23/09/2024')
    c.drawCentredString(cx_lbl, B_PAGE, 'Page')
    # Nombre de feuillets du dossier (مذكّرة + برنامج + قائمة + بطاقة), compté
    # sur les PDF réellement produits — une pièce peut tenir sur plusieurs pages.
    _pages = lettre_data.get('pages')
    if _pages:
        c.drawCentredString(cx_val, B_PAGE, f'{int(_pages)}/{int(_pages)}')

    # ── Logo ───────────────────────────────────────────────────────────
    logo_path = os.path.join(base_dir, 'static', 'images', 'logo.jpg')
    if os.path.exists(logo_path):
        c.drawImage(logo_path, LOGO_X0, LOGO_Y0,
                    width=LOGO_X1 - LOGO_X0, height=LOGO_Y1 - LOGO_Y0,
                    preserveAspectRatio=True, anchor='c', mask='auto')

    # ── Type de correspondance ─────────────────────────────────────────
    type_label = ('مراسلة داخلية' if lettre_data.get('type') == 'interne'
                  else 'مراسلة خارجية')
    c.setFont(F_ARB, S_MURA)
    c.setFillColor(BLACK)
    c.drawCentredString((HD_V1 + HD_V2) / 2, B_MURA, ar(type_label))

    # ── Identification de l'institution ────────────────────────────────
    institution = list(identite.ENTETE_NATIONAL)
    # La مذكرة émane de l'École nationale : pas de ligne « centre régional »
    y0 = B_INST0
    if avec_centre:
        institution.append(nom_centre or identite.CENTRE_NEUTRE)
    else:
        y0 -= LEAD_INST / 2          # recentre le bloc de 5 lignes dans le cadre
    cx_inst = (HD_V2 + HD_X1) / 2
    c.setFont(F_AR, S_INST)
    c.setFillColor(BLACK)
    for k, line in enumerate(institution):
        c.drawCentredString(cx_inst, y0 - k * LEAD_INST, ar(line))


def _draw_pied_ecole(c, data, base_dir):
    """Pied de page officiel : coordonnées de l'École nationale de la Douane,
    encadrées, avec l'emblème à droite (conforme au modèle).

    Les valeurs proviennent des Réglages (clés ecole_email / ecole_tel /
    ecole_fax / ecole_web / ecole_adresse)."""
    email   = (data.get('ecole_email')   or 'end.dfrs@douane.gov.tn').strip()
    tel     = (data.get('ecole_tel')     or '72205722').strip()
    fax     = (data.get('ecole_fax')     or '72205636').strip()
    web     = (data.get('ecole_web')     or
               'www.douane.gov.tn/structures-de-formation').strip()
    adresse = (data.get('ecole_adresse') or
               'المدرسة الوطنيّة للدّيوانة – فندق الجديد – نابل – 8012').strip()

    # Les 4 lignes. Arial couvre l'arabe, le latin et les chiffres : une seule
    # police suffit, l'algorithme bidi place correctement les parties latines.
    lignes = [ar(t) for t in (
        f'البريد الإلكتروني : {email}',
        f'الهاتف : {tel} – الفاكس : {fax}',
        web,
        adresse,
    ) if t.strip()]

    # Aucun encadrement : sur le modèle officiel le bloc est simplement posé
    # en bas de page, l'emblème « 30 ans » à SA GAUCHE.
    c.setFont(F_AR, S_PIED)
    y_top   = PIED_Y0 + PIED_H

    # v1.7.1 : l'emblème de l'École ouvre la ligne (à DROITE, début de ligne
    # en arabe) ; le bloc de texte est décalé d'autant vers la gauche.
    x_right = PIED_X1
    logo = os.path.join(base_dir, 'static', 'images', 'logo.jpg')
    if os.path.exists(logo):
        h_logo = PIED_LOGO_H
        w_logo = h_logo * PIED_LOGO_RATIO
        y_logo = y_top - PIED_LEAD * len(lignes) / 2 - h_logo / 2 + S_PIED * 0.35
        c.drawImage(logo, PIED_X1 - w_logo, y_logo, width=w_logo, height=h_logo,
                    preserveAspectRatio=True, mask='auto')
        x_right = PIED_X1 - w_logo - PIED_LOGO_ECART

    y = y_top - PIED_LEAD
    c.setFillColor(BLACK)
    for txt in lignes:
        c.drawRightString(x_right, y, txt)
        y -= PIED_LEAD

    # (L'emblème « 30 ans » a été retiré du pied de page à la demande du centre.)


def _chemin_cachet(base_dir):
    """v1.7 — Le ختم n'est apposé que si le مشرف عام l'a activé
    (الإعدادات ← الأمان والصيانة ; désactivé par défaut). L'image est cherchée
    d'abord dans data/cachet.png (préservée par les mises à jour), puis dans
    static/images/cachet.png (emplacement historique)."""
    try:
        from core.database import get_config
        if str(get_config().get('cachet_actif', '0')).strip() != '1':
            return None
    except Exception:
        return None
    for chemin in (os.path.join(chemins.dossier_donnees(), 'cachet.png'),
                   os.path.join(base_dir, 'static', 'images', 'cachet.png')):
        if os.path.exists(chemin):
            return chemin
    return None


# ══════════════════════════════════════════════════════════════════════════════
#  v1.6 — PIÈCES « WORD » : قائمة المشاركين · بطاقة حضور · برنامج الدورة
# ══════════════════════════════════════════════════════════════════════════════
#
# Ces trois pièces sont, à l'origine, des documents Word au format A4. Leur mise
# en page est relevée au pixel sur les captures officielles (≈ 0,93 px par pt) :
# chaque cote ci-dessous est donnée en PIXELS de la capture, puis convertie en
# points par `_Releve`. Rien n'est « à l'œil » : on retrouve la cote d'origine
# dans le code, et on peut la revérifier sur l'image.
#
# Style Word reproduit :
#   • tout le texte est en Arial GRAS, sauf le corps des listes (Arial normal) ;
#   • tableau à bordure DOUBLE (cadre, séparateurs verticaux, bas de l'en-tête),
#     traits horizontaux SIMPLES entre les lignes du corps ;
#   • bloc institution aligné à droite et « étiré » (توسيع بالمدّ) sur la largeur
#     de sa plus longue ligne, « وزارة المالية » centrée.

A4_W, A4_H = 595.28, 841.89

BLEU_ENTETE   = colors.HexColor('#5B9BD5')   # en-tête قائمة المشاركين / بطاقة حضور
BLEU_COLONNES = colors.HexColor('#B4C6E7')   # en-têtes de colonnes du برنامج
BLEU_DATE     = colors.HexColor('#D9E2F3')   # ligne de date du برنامج

# Traits — bordure double Word : trait plein (haut / gauche), blanc, trait fin.
TRAIT_EPAIS  = 1.5
TRAIT_BLANC  = 1.1
TRAIT_FIN    = 1.0
TRAIT_SIMPLE = 0.75       # séparateur entre deux lignes du corps

# Tailles Arial relevées sur les modèles (contrôlées sur les chiffres, dont la
# chasse Arial est connue : 2026 → 16 pt, identifiants → 14 pt, 01 → 12 pt).
SW_INST    = 12.0         # bloc institution                       (gras)
SW_LIBELLE = 11.0         # « فندق الجديد في : »                    (gras)
SW_SOUS    = 16.0         # sous-titres et ligne de date            (gras)
SW_ENTETE  = 12.0         # en-têtes de colonnes                    (gras)
SW_CORPS   = 14.0         # corps des listes                        (normal)
SW_NUM     = 12.0         # ع/ر                                      (gras)
SW_PIED    = 12.0         # pied de la بطاقة حضور                    (gras)
SW_PROG    = 11.0         # corps du tableau du برنامج (gras) — v1.7.1 : 9 → 11, plus lisible
SW_MIN     = 12.0         # plancher de réduction des titres trop longs

MOIS_AR_W  = ['جانفي', 'فيفري', 'مارس', 'أفريل', 'ماي', 'جوان',
              'جويلية', 'أوت', 'سبتمبر', 'أكتوبر', 'نوفمبر', 'ديسمبر']
JOURS_AR_W = ['الاثنين', 'الثلاثاء', 'الأربعاء', 'الخميس', 'الجمعة', 'السبت', 'الأحد']


# Façonnage arabe AVEC voyelles (شدّة…) : les modèles Word les affichent
# (« التّوقيت », « المتدخّلون », « الرّتبة »). `ar()` les supprime et reste
# réservé aux autres pièces, qui ne doivent pas bouger.
#
# ReportLab ne positionne pas les voyelles (pas d'OpenType) : il les dessine
# telles que la police les a tracées, avec une chasse nulle. Selon la police,
# le tracé est à DROITE de l'origine (Noto : la voyelle doit précéder sa lettre
# dans la chaîne visuelle — ordre donné par python-bidi) ou à GAUCHE (elle doit
# la suivre). On lit la convention dans la police active ; si elle est
# illisible, on retombe sur `ar()` (sans voyelles), comme avant.
_RESHAPER_HARAKAT = arabic_reshaper.ArabicReshaper(
    configuration={'delete_harakat': False})
_CONVENTION_HARAKAT = {}


def _convention_harakat():
    """'droite' | 'gauche' | None — tracé de la شدّة dans la police grasse active.

    Lu directement dans la police chargée par ReportLab (table glyf : xMin du
    glyphe), sans dépendance supplémentaire."""
    chemin = POLICE_ACTIVE.get('bold') or ''
    if chemin not in _CONVENTION_HARAKAT:
        conv = None
        try:
            import struct
            face = pdfmetrics.getFont(F_ARB).face
            gid = face.charToGlyph.get(0x0651)
            if gid and face.hmetrics[gid][0] == 0 and 'glyf' in face.table:
                pos = face.table['glyf']['offset'] + face.glyphPos[gid]
                if face.glyphPos[gid + 1] > face.glyphPos[gid]:      # glyphe non vide
                    n, xmin = struct.unpack('>hh', face._ttf_data[pos:pos + 4])
                    if n != 0:
                        conv = 'droite' if xmin >= 0 else 'gauche'
        except Exception:
            conv = None
        _CONVENTION_HARAKAT[chemin] = conv
    return _CONVENTION_HARAKAT[chemin]


def _voyelles_apres(visuel):
    """Place chaque suite de voyelles APRÈS la lettre qui la suit (police à
    voyelles tracées à gauche de l'origine)."""
    out, attente = [], []
    for ch in visuel:
        if ch in _HARAKAT:
            attente.append(ch)
        else:
            out.append(ch)
            out.extend(attente)
            attente = []
    return ''.join(out + attente)


def _arh(text):
    """Comme `ar()`, mais en conservant les voyelles (harakat)."""
    if text is None or text == '':
        return ''
    conv = _convention_harakat()
    if conv is None:
        return ar(text)
    visuel = get_display(_RESHAPER_HARAKAT.reshape(str(text)))
    return _voyelles_apres(visuel) if conv == 'gauche' else visuel


def _wrap_h(c, text, font, size, maxw):
    return [_arh(l) for l in _wrap_log(c, text, font, size, maxw)]


class _Releve:
    """Conversion des cotes relevées (pixels de la capture) en points A4.

    k      : points par pixel (hauteur A4 / hauteur de la page sur la capture)
    dx, dy : décalage du bord de page sur la capture (bord gauche / haut)."""

    def __init__(self, k, dx, dy):
        self.k, self.dx, self.dy = k, dx, dy

    def x(self, px):
        return (px - self.dx) * self.k

    def y(self, py):
        """Ordonnée ReportLab (origine en bas) d'une ligne de pixels."""
        return A4_H - (py - self.dy) * self.k

    def d(self, px):
        return px * self.k


# ── Allongement par tatwīl (مدّ) ────────────────────────────────────────────

_SANS_LIAISON = set('ءآأؤإاةدذرزوى')
_HARAKAT = {chr(c) for c in range(0x064B, 0x0653)} | {'ٰ'}


def _pos_kashida(mot):
    """Indice où glisser un tatwīl : avant la DERNIÈRE lettre du mot, si la
    lettre qui la précède se lie à la suivante (« الجمهوريـــة », « الغربـــي »)."""
    base = [i for i, ch in enumerate(mot) if ch not in _HARAKAT]
    if len(base) < 2:
        return None
    der, avant = base[-1], base[-2]
    a, b = mot[avant], mot[der]
    if not ('ب' <= a <= 'ي') or a in _SANS_LIAISON or a == 'ـ':
        return None
    if not ('ء' <= b <= 'ي') or b in 'ءـ':
        return None
    return der


def _etirer_mot(mot, n):
    p = _pos_kashida(mot)
    if p is None or n <= 0:
        return mot
    return mot[:p] + 'ـ' * n + mot[p:]


def _texte_kashida(c, texte, font, size, cible):
    """Allonge `texte` (ordre logique) par tatwīl, mot après mot, jusqu'à
    approcher `cible` sans la dépasser."""
    mots = texte.replace('ـ', '').split()
    elig = [i for i, m in enumerate(mots) if _pos_kashida(m) is not None]
    courant = ' '.join(mots)
    if not elig:
        return courant
    n = [0] * len(mots)
    bloques = set()
    k = 0
    while len(bloques) < len(elig) and k < 400:
        i = elig[k % len(elig)]
        k += 1
        if i in bloques:
            continue
        n[i] += 1
        essai = ' '.join(_etirer_mot(m, n[j]) for j, m in enumerate(mots))
        if _w(c, _arh(essai), font, size) > cible:
            n[i] -= 1
            bloques.add(i)
            continue
        courant = essai
    return courant


def _dessiner_mots(c, texte, font, size, x_gauche, x_droite, y):
    """Répartit l'espace restant entre les mots (justification Word)."""
    parts = [p for p in _arh(texte).split(' ') if p]
    c.setFont(font, size)
    if len(parts) < 2:
        c.drawRightString(x_droite, y, _arh(texte))
        return
    total = sum(_w(c, p, font, size) for p in parts)
    gap = (x_droite - x_gauche - total) / (len(parts) - 1)
    x = x_gauche
    for p in parts:
        c.drawString(x, y, p)
        x += _w(c, p, font, size) + gap


def _ligne_etiree(c, texte, font, size, x_droite, largeur, y):
    """Ligne « موزّعة » sur [x_droite − largeur, x_droite] : d'abord par l'espace
    entre les mots si l'écart est faible, sinon par tatwīl, le reliquat étant
    réparti entre les mots."""
    texte = ' '.join(str(texte).replace('ـ', '').split())
    c.setFont(font, size)
    nat = _w(c, _arh(texte), font, size)
    if nat >= largeur - 0.3:
        c.drawRightString(x_droite, y, _arh(texte))
        return
    mots = texte.split()
    esp = _w(c, ' ', font, size)
    if len(mots) < 2 or largeur - nat > (len(mots) - 1) * 1.5 * esp:
        texte = _texte_kashida(c, texte, font, size, largeur)
    _dessiner_mots(c, texte, font, size, x_droite - largeur, x_droite, y)


def _ligne_centree_etiree(c, texte, font, size, cx, largeur, y):
    texte = _texte_kashida(c, ' '.join(str(texte).replace('ـ', '').split()),
                           font, size, largeur)
    c.setFont(font, size)
    c.drawCentredString(cx, y, _arh(texte))


def _bloc_institution(c, lignes_nat, lignes_centre, x_droite, y0, interligne):
    """Bloc d'identification en haut à droite.

    Largeur du bloc = ligne nationale la plus longue (« إدارة التكوين الجهوي
    والمختص ») ; les autres lignes y sont étirées, « وزارة المالية » est centrée
    (≈ 56 % de la largeur, comme sur le modèle). Le nom du centre est découpé à
    cette même largeur. Renvoie l'ordonnée de la ligne suivante."""
    font, size = F_ARB, SW_INST
    c.setFillColor(BLACK)
    c.setFont(font, size)
    nat = [' '.join(str(l).replace('ـ', '').split()) for l in lignes_nat if str(l).strip()]
    ministere = [i for i, l in enumerate(nat) if l.startswith('وزارة')]
    autres = [_w(c, _arh(l), font, size) for i, l in enumerate(nat) if i not in ministere]
    larg = max(autres) if autres else 130.0
    centre = []
    for l in lignes_centre:
        l = ' '.join(str(l or '').replace('ـ', '').split())
        if l:
            centre += _wrap_log(c, l, font, size, larg)
    y = y0
    for i, l in enumerate(nat):
        if i in ministere:
            _ligne_centree_etiree(c, l, font, size, x_droite - larg / 2, larg * 0.56, y)
        else:
            _ligne_etiree(c, l, font, size, x_droite, larg, y)
        y -= interligne
    for l in centre:
        w = _w(c, _arh(l), font, size)
        if w < larg * 0.55:
            # v1.6.1 : une ligne courte (« بالقصرين ») est CENTRÉE sous le bloc,
            # comme « وزارة المالية », au lieu d'être collée à droite.
            c.setFont(font, size)
            c.drawCentredString(x_droite - larg / 2, y, _arh(l))
        else:
            _ligne_etiree(c, l, font, size, x_droite, larg, y)
        y -= interligne
    return y


def _lignes_titre(c, texte, font, size, largeur_max, plancher=SW_MIN):
    """(lignes visuelles, taille) : réduit jusqu'au plancher, puis découpe."""
    texte = ' '.join(str(texte or '').split())
    s = size
    while s > plancher and _w(c, _arh(texte), font, s) > largeur_max:
        s -= 0.5
    if _w(c, _arh(texte), font, s) <= largeur_max:
        return [_arh(texte)], s
    return _wrap_h(c, texte, font, s, largeur_max), s


def _logo_ecole(c, base_dir, x, y_haut, largeur, hauteur):
    chemin = os.path.join(base_dir, 'static', 'images', 'logo.jpg')
    if os.path.exists(chemin):
        c.drawImage(chemin, x, y_haut - hauteur, width=largeur, height=hauteur,
                    preserveAspectRatio=True, anchor='c', mask='auto')


# ── Traits de tableau Word ──────────────────────────────────────────────────

def _double_h(c, x0, x1, y_haut):
    """Bordure double horizontale dont le bord supérieur est `y_haut`."""
    c.setStrokeColor(BLACK)
    c.setLineWidth(TRAIT_EPAIS)
    c.line(x0, y_haut - TRAIT_EPAIS / 2, x1, y_haut - TRAIT_EPAIS / 2)
    c.setLineWidth(TRAIT_FIN)
    yf = y_haut - TRAIT_EPAIS - TRAIT_BLANC - TRAIT_FIN / 2
    c.line(x0, yf, x1, yf)


def _double_v(c, x_gauche, y_bas, y_haut):
    """Bordure double verticale dont le bord gauche est `x_gauche`."""
    c.setStrokeColor(BLACK)
    c.setLineWidth(TRAIT_EPAIS)
    c.line(x_gauche + TRAIT_EPAIS / 2, y_bas, x_gauche + TRAIT_EPAIS / 2, y_haut)
    c.setLineWidth(TRAIT_FIN)
    xf = x_gauche + TRAIT_EPAIS + TRAIT_BLANC + TRAIT_FIN / 2
    c.line(xf, y_bas, xf, y_haut)


def _simple_h(c, x0, x1, y_bas):
    """Trait simple dont le bord SUPÉRIEUR est `y_bas` (bas d'une ligne)."""
    c.setStrokeColor(BLACK)
    c.setLineWidth(TRAIT_SIMPLE)
    c.line(x0, y_bas - TRAIT_SIMPLE / 2, x1, y_bas - TRAIT_SIMPLE / 2)


def _date_arabe(date_iso, ville, mois='', annee=''):
    """« القصرين في 24 جوان 2026 » (ville facultative)."""
    try:
        d = datetime.strptime(date_iso or '', '%Y-%m-%d')
        txt = f'{d.day} {MOIS_AR_W[d.month - 1]} {d.year}'
    except Exception:
        txt = f'{mois or ""} {annee or ""}'.strip()
    if not txt:
        return ''
    return f'{ville} في {txt}'.strip() if ville else txt


# ── Liste Word commune : قائمة المشاركين / بطاقة حضور ────────────────────────
#
# Les deux captures sont à la même échelle (pas des lignes identique : 19,64 px),
# page A4 de 784,5 px de haut → k = 1,0732 pt/px. Le bord gauche de la page est
# rogné de 5,2 px sur la capture (contrôle : le titre tombe au centre de page).

class _ListeWord:
    """Gabarit d'une liste Word (en-tête officiel + tableau à bordure double)."""

    def __init__(self, c, base_dir, R, *, titre, sous_titres, cx_titre, cx_sous,
                 taille_titre, libelle, x_libelle, cols_px, entetes, y_table_px,
                 inst_droite_px, inst_haut_px, logo_px, y_titre_px, y_sous_px,
                 lignes_nat, lignes_centre, bas_page):
        self.c, self.base_dir, self.R = c, base_dir, R
        self.titre, self.sous_titres = titre, sous_titres
        self.cx_titre, self.cx_sous = cx_titre, cx_sous
        self.taille_titre = taille_titre
        self.libelle, self.x_libelle = libelle, x_libelle
        self.vx = [R.x(p) for p in cols_px]          # bord gauche de chaque bordure
        self.entetes = entetes
        self.y_table_px = y_table_px
        self.inst_droite_px, self.inst_haut_px = inst_droite_px, inst_haut_px
        self.logo_px = logo_px
        self.y_titre_px, self.y_sous_px = y_titre_px, y_sous_px
        self.lignes_nat, self.lignes_centre = lignes_nat, lignes_centre
        self.bas_page = bas_page
        self.pas = R.d(19.55)                          # pas des lignes du corps
        self.lead = SW_CORPS * 1.15                    # interligne d'une cellule

    # colonnes : intérieur entre deux bordures doubles
    def col(self, i):
        return self.vx[i] + self.R.d(4), self.vx[i + 1]

    def en_tete_page(self):
        c, R = self.c, self.R
        c.setFillColor(BLACK)
        c.setFont(F_ARB, SW_LIBELLE)
        c.drawRightString(self.x_libelle, R.y(self.inst_haut_px + 9.0), _arh(self.libelle))
        _bloc_institution(c, self.lignes_nat, self.lignes_centre,
                          R.x(self.inst_droite_px), R.y(self.inst_haut_px + 8.0),
                          R.d(13.17))
        lx, ly, lw, lh = self.logo_px
        _logo_ecole(c, self.base_dir, R.x(lx), R.y(ly), R.d(lw), R.d(lh))
        c.setFillColor(BLACK)
        c.setFont(F_ARB, self.taille_titre)
        c.drawCentredString(self.cx_titre, R.y(self.y_titre_px), _arh(self.titre))
        decal = 0.0
        for (lignes, s), cx, ypx in zip(self.sous_lignes(), self.cx_sous, self.y_sous_px):
            c.setFont(F_ARB, s)
            y = R.y(ypx) - decal
            for i, ln in enumerate(lignes):
                c.drawCentredString(cx, y - i * R.d(24), ln)
            decal += (len(lignes) - 1) * R.d(24)
        return self.haut_table()

    def sous_lignes(self):
        """Sous-titres : 16 pt gras ; un titre trop long est réduit (≥ 12 pt),
        puis passe à la ligne en repoussant le tableau."""
        res = []
        for texte, cx in zip(self.sous_titres, self.cx_sous):
            marge = min(cx, A4_W - cx) - 24
            res.append(_lignes_titre(self.c, texte, F_ARB, SW_SOUS, 2 * marge))
        return res

    def haut_table(self):
        decal = sum((len(l) - 1) * self.R.d(24) for l, _ in self.sous_lignes())
        return self.R.y(self.y_table_px) - decal

    def en_tete_tableau(self, y_haut, fond):
        """Rangée d'en-tête : fond coloré, texte gras 12, bordures doubles."""
        c, R = self.c, self.R
        x0, x1 = self.vx[0], self.vx[-1] + R.d(4)
        y_bas_hdr = y_haut - R.d(19)                   # début du double inférieur
        for i in range(len(self.entetes)):
            a, b = self.col(i)
            c.setFillColor(fond)
            c.rect(a, y_bas_hdr, b - a, y_haut - R.d(4) - y_bas_hdr, stroke=0, fill=1)
        c.setFillColor(BLACK)
        for i, t in enumerate(self.entetes):
            a, b = self.col(i)
            lignes, s = _lignes_titre(c, t, F_ARB, SW_ENTETE, b - a - 4, plancher=8)
            c.setFont(F_ARB, s)
            c.drawCentredString((a + b) / 2, y_haut - R.d(14.6), lignes[0])
        _double_h(c, x0, x1, y_haut)
        _double_h(c, x0, x1, y_bas_hdr)
        return y_bas_hdr - R.d(4)                      # haut de la 1re ligne

    def cadre(self, y_haut, y_bas):
        for x in self.vx:
            _double_v(self.c, x, y_bas, y_haut)

    def texte_cellule(self, i, lignes, y_haut, y_bas, font, size, lead=None,
                      centre=False):
        """Lignes visuelles centrées horizontalement. Verticalement, la ligne de
        base de la DERNIÈRE ligne est à 4,6 px du bas de la rangée (Word : même
        ligne de base pour le 14 pt et le ع/ر en 12 pt) ; `centre=True` centre
        le bloc (cellule fusionnée)."""
        c, R = self.c, self.R
        a, b = self.col(i)
        lead = lead or self.lead
        size = getattr(lignes, 'taille', size)
        n = len(lignes)
        if centre:
            base = (y_haut + y_bas) / 2 - 0.30 * size + (n - 1) * lead / 2
        else:
            base = y_bas + R.d(4.6) + (n - 1) * lead
        c.setFont(font, size)
        c.setFillColor(BLACK)
        for ln in lignes:
            c.drawCentredString((a + b) / 2, base, ln)
            base -= lead

    def decouper(self, i, texte, font=None, size=SW_CORPS, reduire=True):
        """Lignes visuelles d'une cellule. Un texte un peu trop long est d'abord
        réduit (jusqu'à 12 pt) pour rester sur une ligne — « رقيب للديوانة » dans
        la colonne الرّتبة —, puis seulement découpé. La taille retenue est portée
        par la liste (`.taille`)."""
        a, b = self.col(i)
        font = font or F_AR
        texte = str(texte or '').strip()
        larg = b - a - 6
        if not texte:
            return _Lignes([], size)
        s = size
        while s >= (SW_MIN if reduire else size):
            if _w(self.c, _arh(texte), font, s) <= larg:
                return _Lignes([_arh(texte)], s)
            s -= 0.5
        return _Lignes(_wrap_h(self.c, texte, font, size, larg), size)


class _Lignes(list):
    """Lignes d'une cellule, avec la taille de police retenue."""

    def __init__(self, lignes, taille):
        super().__init__(lignes)
        self.taille = taille


def _paginer(hauteurs, dispo_premiere, dispo_suivantes, reserve_fin=0.0):
    """Répartit des lignes de hauteurs données sur des pages.

    Renvoie une liste de listes d'indices. `reserve_fin` : place à garder sous
    la dernière ligne de la DERNIÈRE page (pied de la بطاقة حضور)."""
    pages, cur, dispo = [], [], dispo_premiere
    for i, h in enumerate(hauteurs):
        if cur and h > dispo:
            pages.append(cur)
            cur, dispo = [], dispo_suivantes
        cur.append(i)
        dispo -= h
    if cur or not pages:
        pages.append(cur)
    if reserve_fin and dispo < reserve_fin and pages[-1]:
        # Le pied ne tient pas : la dernière ligne passe sur une page nouvelle.
        der = pages[-1].pop()
        if not pages[-1]:
            pages.pop()
        pages.append([der])
    return pages


def _groupes_fusion(valeurs):
    """[(début, fin)] des suites de valeurs identiques non vides (fusion Word)."""
    groupes, i = [], 0
    while i < len(valeurs):
        j = i
        v = (valeurs[i] or '').strip()
        while v and j + 1 < len(valeurs) and (valeurs[j + 1] or '').strip() == v:
            j += 1
        groupes.append((i, j))
        i = j + 1
    return groupes


# ══════════════════════════════════════════════════════════════════════════════
#  v1.7 — Les générateurs vivent dans core/pdf/<document>.py ; ils sont
#  ré-exportés ici : `from core.pdf_generator import generer_pdf_memo` et
#  `pg.generer_pdf_memo(...)` fonctionnent exactement comme avant.
#  (Import placé en fin de module : les outils ci-dessus existent déjà.)
# ══════════════════════════════════════════════════════════════════════════════
from core.pdf.mourasalat import generer_pdf, _adresse_directeur, generer_pdf_directeur_regional, generer_pdf_libre  # noqa: E402,F401
from core.pdf.pieces_word import generer_pdf_participants, generer_pdf_bataqa_hodour, generer_pdf_programme  # noqa: E402,F401
from core.pdf.bataqa import generer_pdf_bataqa  # noqa: E402,F401
from core.pdf.memo import generer_pdf_memo  # noqa: E402,F401

# Noms ré-exportés (façade) — déclarés pour les outils d'analyse.
__all__ = [
    'canvas', 'generer_pdf', 'generer_pdf_directeur_regional', 'generer_pdf_libre',
    '_adresse_directeur', 'generer_pdf_participants', 'generer_pdf_bataqa_hodour',
    'generer_pdf_programme', 'generer_pdf_bataqa', 'generer_pdf_memo',
]
