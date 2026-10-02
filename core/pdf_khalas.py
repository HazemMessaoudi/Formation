# -*- coding: utf-8 -*-
"""وثائق الخلاص — génération PDF des quatre documents officiels.

Principe : « modèle officiel → injection des données ». On NE redessine pas :
on reproduit la structure des modèles fournis (champs, ordre, tableaux, totaux,
cadres, en-têtes, logos, signatures, orientation) et on n'y injecte que les
valeurs variables assemblées par core/khalas.py.

Quatre documents :
  1. مذكرة (بيان حساب فردي)         — portrait
  2. بطاقة إرشادات حول المكون        — portrait
  3. جدول بيان حساب                  — paysage
  4. إعلام بإنجاز يوم دراسي          — portrait

On réutilise l'outillage arabe/ReportLab de pdf_generator (reshape+bidi,
polices, mesures) pour rester cohérent avec le reste des PDF de la منظومة.
"""

import logging as _logging
_log = _logging.getLogger('formation.' + __name__)

import os

from reportlab.pdfgen import canvas
from reportlab.lib import colors

from core.pdf_generator import ar, _register_fonts, F_AR, F_ARB, _w

BLACK = colors.black
GRIS  = colors.Color(.45, .45, .45)

A4W, A4H = 595.32, 841.92     # portrait
MARGE = 48.0


# ─── Aides de tracé ───────────────────────────────────────────────────────────

def _right(c, x, y, s, font=F_AR, size=11, color=BLACK):
    c.setFont(font, size); c.setFillColor(color); c.drawRightString(x, y, ar(s))

def _left(c, x, y, s, font=F_AR, size=11, color=BLACK):
    c.setFont(font, size); c.setFillColor(color); c.drawString(x, y, ar(s))

def _center(c, x, y, s, font=F_AR, size=11, color=BLACK):
    c.setFont(font, size); c.setFillColor(color); c.drawCentredString(x, y, ar(s))

def _box(c, x0, y0, x1, y1, w=0.8, color=BLACK):
    c.setStrokeColor(color); c.setLineWidth(w); c.rect(x0, y0, x1 - x0, y1 - y0, stroke=1, fill=0)

def _line(c, x0, y0, x1, y1, w=0.8, color=BLACK):
    c.setStrokeColor(color); c.setLineWidth(w); c.line(x0, y0, x1, y1)

def _logo(c, path, x, y, w, h):
    try:
        if path and os.path.exists(path):
            c.drawImage(path, x, y, w, h, preserveAspectRatio=True, mask='auto')
    except Exception:
        _log.warning('_logo : exception ignorée', exc_info=True)
        pass

def _wrap_lines(c, text, font, size, maxw):
    """Découpe un texte arabe (ordre logique) en lignes visuelles ≤ maxw."""
    mots = str(text or '').split()
    lignes, cur = [], []
    for m in mots:
        essai = cur + [m]
        if not cur or _w(c, ar(' '.join(essai)), font, size) <= maxw:
            cur = essai
        else:
            lignes.append(' '.join(cur)); cur = [m]
    if cur:
        lignes.append(' '.join(cur))
    return lignes or ['']

def _logos_paths(base_dir):
    d = os.path.join(base_dir, 'static', 'images')
    # Version nettoyée du logo Douane (le trait parasite en haut a été retiré) ;
    # repli sur l'original si le fichier nettoyé n'est pas présent.
    douane = os.path.join(d, 'logo_douane_doc.png')
    if not os.path.exists(douane):
        douane = os.path.join(d, 'logo_douane.png')
    return (os.path.join(d, 'logo.jpg'), douane,
            os.path.join(d, 'embleme_30.png'))


# ═══════════════════════════════════════════════════════════════════════════
#  DOCUMENT 1 — مذكرة (بيان حساب فردي)                              portrait
# ═══════════════════════════════════════════════════════════════════════════

def _doc_mudhakkira(c, d, base_dir):
    W, H = A4W, A4H
    xg, xd = MARGE, W - MARGE           # gauche, droite

    # ── En-tête : 3 colonnes encadrées ──
    y_top = H - MARGE
    h_ent = 84
    y_bot = y_top - h_ent
    c1 = xg + 150     # séparateur gauche | centre
    c2 = xd - 150     # séparateur centre | droite
    _box(c, xg, y_bot, xd, y_top)
    _line(c, c1, y_bot, c1, y_top)
    _line(c, c2, y_bot, c2, y_top)

    # Colonne droite : institution
    inst = ['الجمهورية التونسية', 'وزارة المالية', 'المدرسة الوطنية للديوانة',
            'عدد : ................']
    yy = y_top - 16
    for i, l in enumerate(inst):
        _center(c, (c2 + xd) / 2, yy, l, F_ARB if i == 3 else F_AR, 9.5)
        yy -= 15
    # Colonne centre : objet
    obj = ['بيان حساب بعنوان تدريس مواد الدورة التكوينية',
           f'حول {d["titre"]}', f'{d["nom_centre_ba"]}']
    yy = y_top - 24
    for l in obj:
        for ln in _wrap_lines(c, l, F_AR, 9.5, (c2 - c1) - 12):
            _center(c, (c1 + c2) / 2, yy, ln, F_AR, 9.5); yy -= 13
    # Colonne gauche : صنف
    _center(c, (xg + c1) / 2, y_top - 34, d['titre'], F_ARB, 9)
    _center(c, (xg + c1) / 2, y_top - 50, f'صنف {d["classe"]}', F_ARB, 11)  # صنف الدورة

    # ── مذكرة عدد ──
    y = y_bot - 26
    _center(c, W / 2, y, f'مذكرة عدد : {d["numero_mudhakkira"] or "…"}', F_ARB, 12)

    # ── Champs identité (label droite : valeur) ──
    y -= 30
    lab_x = xd                     # labels alignés à droite
    val_x = xd - 200               # valeurs alignées à droite de leur colonne
    champs = [
        ('* بطاقة التعريف الوطنية', d['cin']),
        ('* المعرف الوحيد', d['identifiant_unique']),
        ('* اللقب و الأسم', d['formateur_nom']),
        ('* الخطة الوظيفية أو الرتبة', d['formateur_grade']),
        ('* الصنف', d['grade_categorie']),
        ('فترة أو دورة التكوين', f'الدورة التكوينية حول {d["titre"]} صنف {d["classe"]}'),
        ('عدد وتاريخ الأمر المتعلق بالتأجير', d['ordre_tajir']),
        ('* عدد و تاريخ مقرر التعيين',
         f'مقرر وزيرة المالية عدد {d["muqarrar_numero"]} بتاريخ {d["muqarrar_date"]}'),
        ('* الهوية البنكية أو البريدية', f'"{d["num_compte"]}"'),
    ]
    for lab, val in champs:
        _right(c, lab_x, y, lab, F_ARB, 10.5)
        _right(c, lab_x - 132, y, ':', F_AR, 10.5)
        for ln in _wrap_lines(c, val, F_AR, 10.5, val_x - xg):
            _right(c, val_x, y, ln, F_AR, 10.5); y -= 15
        y -= 3

    # ── Tableau des travaux ──
    y -= 8
    cols = [xg, xg + 90, xg + 175, xg + 250, xg + 355, xd]   # 5 colonnes
    hh, rh = 40, 46
    yt, yb = y, y - hh
    _box(c, xg, yb - rh, xd, yt)
    for x in cols[1:-1]:
        _line(c, x, yb - rh, x, yt)
    _line(c, xg, yb, xd, yb)          # sépare en-tête / ligne
    entetes = ['المبلغ الجملي\n(بالدينار)', 'سعر الساعة الواحدة\n(بالدينار)',
               'عدد الساعات', 'تاريخ الإنجاز', 'طبيعة الأشغال المنجزة']
    centres = [(cols[0] + cols[1]) / 2, (cols[1] + cols[2]) / 2, (cols[2] + cols[3]) / 2,
               (cols[3] + cols[4]) / 2, (cols[4] + cols[5]) / 2]
    for cx, txt in zip(centres, entetes):
        parts = txt.split('\n')
        yy = (yt + yb) / 2 + (len(parts) - 1) * 6 - 2
        for p in parts:
            _center(c, cx, yy, p, F_ARB, 8.6); yy -= 12
    # Ligne de données
    valeurs = [d['brut_texte'], d['taux_texte'], str(d['heures']), d['date_longue']]
    for k, (cx, v) in enumerate(zip(centres[:4], valeurs)):
        if k == 3 and d.get('multi'):
            # V2 : période d'une دورة متعدّدة الأيّام, sur deux lignes au besoin
            lns = _wrap_lines(c, v, F_AR, 10, cols[4] - cols[3] - 6)
            for i, ln in enumerate(lns):
                _center(c, cx, yb - rh / 2 - 3 + (len(lns) - 1) * 6 - i * 12, ln, F_AR, 10)
            continue
        _center(c, cx, yb - rh / 2 - 3, v, F_AR, 10)
    for i, ln in enumerate(_wrap_lines(c, f'تدريس مواد الدورة التكوينية حول {d["titre"]} صنف {d["classe"]}',
                                        F_AR, 8.8, cols[5] - cols[4] - 8)):
        _center(c, centres[4], yb - rh / 2 + 6 - i * 11, ln, F_AR, 8.8)

    # ── Récapitulatif montants ──
    y = yb - rh - 30
    for lab, val in [('المبلغ الخــام', d['brut_texte']),
                     (f'الأداءات ({int(d["taux_adaat"])}%)', d['adaat_texte']),
                     ('المبلغ الصافي', d['net_texte'])]:
        _right(c, 372, y, f'{lab} :', F_ARB, 11)
        _right(c, 258, y, val, F_ARB, 11)
        _right(c, 205, y, 'دينارا', F_AR, 10)
        y -= 24

    # ── Attestations ──
    y -= 14
    # Droite : le المنتفع (المكوّن) atteste, puis la DATE — celle du مقرّر, car la
    # مذكرة se fait APRÈS sa signature — et « إمضاء المنتفع » dessous, sous le
    # rang et le nom, avec un espace pour signer.
    _right(c, xd, y, 'إطلع عليه وتثبت من صحته :', F_AR, 10.5)
    _right(c, xd, y - 22, f'{d["formateur_grade"]} {d["formateur_nom"]}', F_ARB, 10.5)
    _right(c, xd, y - 46, f'{d["ville"]} في {d["muqarrar_date"]}', F_AR, 10)
    _right(c, xd - 30, y - 68, 'إمضاء المنتفع', F_ARB, 10.5)

    # Gauche : accord + montant en lettres.
    _left(c, xg, y, 'أوقف هذا الحساب بمبلغ قدره :', F_AR, 10.5)
    _left(c, xg, y - 22, d['montant_lettres'], F_ARB, 10.5)

    # ── Signature directeur ──
    ys = y - 120
    _center(c, W / 2, ys, 'الإمضـــــاء', F_ARB, 12)
    _center(c, W / 2, ys - 18, d['directeur_titre'], F_ARB, 11)
    _center(c, W / 2, ys - 36, f'{d["directeur_grade"]} {d["directeur_nom"]}', F_ARB, 12)


# ═══════════════════════════════════════════════════════════════════════════
#  DOCUMENT 2 — بطاقة إرشادات حول المكون                            portrait
# ═══════════════════════════════════════════════════════════════════════════

def _doc_bitaqa(c, d, base_dir):
    W, H = A4W, A4H
    xg, xd = MARGE, W - MARGE
    annee = (d['date_iso'] or '')[:4] or ''

    # En-tête institution (droite)
    y = H - MARGE
    for l in ['الجمهورية التونسية', 'وزارة المالية', 'المدرسة الوطنية للديوانة']:
        _right(c, xd, y, l, F_AR, 9.5); y -= 13

    # Titre
    y -= 6
    _center(c, W / 2, y, 'بطاقة إرشادات حول المكون', F_ARB, 14); y -= 18
    _center(c, W / 2, y, '(خاصة بوحدة الإشراف الإداري و المالية)', F_ARB, 11); y -= 16
    _center(c, W / 2, y, f'الدورات التكوينية لسنة {annee}', F_ARB, 11); y -= 20

    # Tableau 3 colonnes (dorra / durée / matière)
    ht = 54
    yt, yb = y, y - ht
    t1 = xg + (xd - xg) / 3
    t2 = xg + 2 * (xd - xg) / 3
    _box(c, xg, yb, xd, yt)
    _line(c, t1, yb, t1, yt); _line(c, t2, yb, t2, yt)
    _line(c, xg, yt - 18, xd, yt - 18)
    _center(c, (t2 + xd) / 2, yt - 13, 'الدورة التكوينية', F_ARB, 9.5)
    _center(c, (t1 + t2) / 2, yt - 13, 'مدة الدورة التكوينية', F_ARB, 9.5)
    _center(c, (xg + t1) / 2, yt - 13, 'المادة المدرسة', F_ARB, 9.5)
    # Contenu
    coche_m = '☒' if d['type_takwin'] == 'mustamir' else '☐'
    coche_t = '☒' if d['type_takwin'] == 'tahili' else '☐'
    _right(c, xd - 10, yt - 34, f'{coche_m} تكوين مستمر', F_AR, 9.5)
    _right(c, xd - 10, yt - 48, f'{coche_t} تكوين تأهيلي', F_AR, 9.5)
    _center(c, (t1 + t2) / 2, yb + 22, f'{d["heures"]} ساعات', F_ARB, 10)
    for i, ln in enumerate(_wrap_lines(c, f'{d["titre"]} صنف {d["classe"]}', F_AR, 9, t1 - xg - 8)):
        _center(c, (xg + t1) / 2, yb + 26 - i * 12, ln, F_AR, 9)

    # Grand cadre formulaire
    y = yb - 6
    lignes = [
        ('إسم و لقب المكون', d['formateur_nom'], None, None),
        ('رقم بطاقة التعريف الوطنية', d['cin'], 'الصادرة بتاريخ', d['cin_date']),
        ('رقم المعرف الوحيد', d['identifiant_unique'], None, None),
        ('العنوان الشخصي', d['adresse'], None, None),
        ('الهاتف الجوال', d['telephone_gsm'], 'الهاتف الإداري', d['telephone_adm']),
        ('الشهادة العلمية', d['diplome'], None, None),
        ('الرتبة', d['formateur_grade'], None, None),
        # الدرجة = صنف رتبة المكوّن (وكيل → ب)، لا صنف الدورة ولا خانة الفيش.
        ('الدرجة', d['grade_categorie'], None, None),
        ('الخطة الوظيفية', d['plan_fonctionnel'], None, None),
        ('الإدارة', d['administration'], None, None),
        ('وزارة الإشراف', d['ministere'], None, None),
        ('البريد الإلكتروني', d['email'], None, None),
        ('البنك', d['banque'], 'الفرع', d['agence']),
        ('رقم الحساب البنكي / البريدي', f'"{d["num_compte"]}"', None, None),
    ]
    rh = 22
    cadre_h = rh * len(lignes) + 72        # +72 : espace bas pour date + signature
    yb2 = y - cadre_h
    _box(c, xg, yb2, xd, y, 1.0)
    lab_x = xd - 8
    mid = xg + (xd - xg) * 0.42
    yy = y - 16
    for lab, val, lab2, val2 in lignes:
        _right(c, lab_x, yy, lab, F_ARB, 9.6)
        _right(c, mid, yy, ':', F_AR, 9.6)
        if lab2:
            # Champ secondaire (الهاتف الإداري / الفرع) tiré vers la DROITE pour
            # laisser de la place à la valeur ; valeur secondaire élargie à gauche.
            _right(c, mid - 10, yy, str(val or ''), F_AR, 9.4)
            _right(c, xg + 150, yy, f'{lab2} :', F_ARB, 9.0)
            _right(c, xg + 78, yy, str(val2 or ''), F_AR, 9.0)
        else:
            for i, ln in enumerate(_wrap_lines(c, val, F_AR, 9.6, mid - xg - 12)):
                _center(c, (xg + mid) / 2, yy - i * 11, ln, F_AR, 9.6)
        _line(c, xg + 6, yy - 6, xd - 6, yy - 6, 0.4, GRIS)
        yy -= rh
    _center(c, W / 2, yb2 + 12, 'الرجاء ملء المعرف بالمصنف المكون من عشرين (20) رقما', F_AR, 8, GRIS)
    # Date à GAUCHE, au-dessus de « إمضاء المكون », avec un espace pour signer.
    _left(c, xg + 12, yb2 + 54, f'{d["ville"]} في {d.get("date_signature") or d["date_longue"]}', F_AR, 9)
    _left(c, xg + 12, yb2 + 36, 'إمضاء المكون', F_ARB, 9.6)

    # Section unité de formation
    y = yb2 - 16
    _right(c, xd, y, 'خاص بوحدة التكوين', F_ARB, 9.5, GRIS); y -= 6
    hbox = 90
    _box(c, xg, y - hbox, xd, y)
    _right(c, xd - 12, y - 20, 'عدد الساعات المبرمجة :', F_ARB, 9.6)
    _center(c, xd - 150, y - 20, str(d['heures_prog']), F_AR, 10)
    _right(c, xd - 12, y - 40, 'عدد الساعات المنجزة :', F_ARB, 9.6)
    _center(c, xd - 150, y - 40, str(d['heures_real']), F_AR, 10)
    _left(c, xg + 12, y - 20, 'الملاحظـــات', F_ARB, 9.6)
    for i, ln in enumerate(_wrap_lines(c, d['notes'], F_AR, 9, (W / 2) - xg - 20)):
        _left(c, xg + 12, y - 38 - i * 12, ln, F_AR, 9)
    _left(c, xg + 40, y - hbox + 8, 'وحدة التكوين', F_AR, 9)


# ═══════════════════════════════════════════════════════════════════════════
#  DOCUMENT 3 — جدول بيان حساب                                      paysage
# ═══════════════════════════════════════════════════════════════════════════

def _doc_jadwal(c, d, base_dir):
    W, H = A4H, A4W                    # paysage
    xg, xd = 30, W - 30
    logo1, logo2, _ = _logos_paths(base_dir)
    _logo(c, logo1, xg, H - 88, 70, 70)
    _logo(c, logo2, xd - 78, H - 86, 66, 66)   # شعار الديوانة (بلا الخط الشارد)

    y = H - 40
    for i, ln in enumerate(_wrap_lines(
            c, f'جدول بيان حساب في مستحقات الدورة التكوينية حول {d["titre"]} صنف {d["classe"]} {d["nom_centre_ba"]}',
            F_ARB, 13, W - 220)):
        _center(c, W / 2, y - i * 18, ln, F_ARB, 13)
    y -= 44
    _center(c, W / 2, y, f'تبعا لمقرر وزيرة المالية عدد {d["muqarrar_numero"]} بتاريخ {d["muqarrar_date"]}', F_ARB, 11)

    # Tableau large (droite → gauche)
    y -= 34
    entetes = ['الإسم واللقب', 'الرتبة', 'المعرف الوحيد', 'رقم بطاقة\nالتعريف الوطنية',
               'الصنف', 'الهوية البنكية أو البريدية', 'عدد\nالساعات',
               'سعر الساعة\nالواحدة(بالدينار)', 'المبلغ الجملي\n(بالدينار)',
               'الأداءات\n(15 %)', 'المبلغ الصافي', 'المبلغ بالاحرف']
    # largeurs proportionnelles (somme = W - 2*30)
    poids = [1.6, 0.9, 1.3, 1.3, 0.7, 2.2, 0.8, 1.3, 1.2, 1.0, 1.1, 2.0]
    total_p = sum(poids)
    usable = (xd - xg)
    # colonnes de DROITE à GAUCHE
    bornes = [xd]
    for p in poids:
        bornes.append(bornes[-1] - p / total_p * usable)
    hh, rh = 40, 30
    yt = y
    yb_hdr = yt - hh
    yb_row = yb_hdr - rh
    yb_tot = yb_row - rh
    # En-tête + ligne de données : sur toute la largeur.
    _box(c, xg, yb_row, xd, yt, 0.9)
    for x in bornes[1:-1]:
        _line(c, x, yb_row, x, yt, 0.6)
    _line(c, xg, yb_hdr, xd, yb_hdr, 0.9)
    # Ligne المجموع : seulement les colonnes 6→11 (المجموع + les totaux). La
    # partie droite (الإسم..الهوية) n'a pas lieu d'être répétée → aucun cadre.
    _box(c, xg, yb_tot, bornes[6], yb_row, 0.9)
    for x in bornes[7:-1]:
        _line(c, x, yb_tot, x, yb_row, 0.6)
    # en-têtes
    for i, txt in enumerate(entetes):
        cx = (bornes[i] + bornes[i + 1]) / 2
        parts = txt.split('\n')
        yy = (yt + yb_hdr) / 2 + (len(parts) - 1) * 6 - 1
        for p in parts:
            _center(c, cx, yy, p, F_ARB, 7.6); yy -= 11
    # ligne de données
    vals = [d['formateur_nom'], d['formateur_grade'], d['identifiant_unique'], d['cin'],
            d['grade_categorie'], f'"{d["num_compte"]}"', str(d['heures']), d['taux_texte'],
            d['brut_texte'], d['adaat_texte'], d['net_texte'], d['montant_lettres']]
    for i, v in enumerate(vals):
        cx = (bornes[i] + bornes[i + 1]) / 2
        lignes = _wrap_lines(c, str(v), F_AR, 7.8, (bornes[i] - bornes[i + 1]) - 4)
        yy = (yb_hdr + yb_row) / 2 + (len(lignes) - 1) * 5 - 1
        for ln in lignes:
            _center(c, cx, yy, ln, F_AR, 7.8); yy -= 10
    # ligne المجموع
    _center(c, (bornes[6] + bornes[7]) / 2, (yb_row + yb_tot) / 2 - 2, 'المجموع', F_ARB, 8.5)
    for i, v in [(8, d['brut_texte']), (9, d['adaat_texte']), (10, d['net_texte']), (11, d['montant_lettres'])]:
        cx = (bornes[i] + bornes[i + 1]) / 2
        lignes = _wrap_lines(c, str(v), F_ARB, 7.8, (bornes[i] - bornes[i + 1]) - 4)
        yy = (yb_row + yb_tot) / 2 + (len(lignes) - 1) * 5 - 1
        for ln in lignes:
            _center(c, cx, yy, ln, F_ARB, 7.8); yy -= 10

    # Signature
    ys = yb_tot - 44
    _right(c, xg + 300, ys, d['directeur_titre'], F_ARB, 11)
    _right(c, xg + 300, ys - 18, f'{d["directeur_grade"]} {d["directeur_nom"]}', F_ARB, 12)


# ═══════════════════════════════════════════════════════════════════════════
#  DOCUMENT 4 — إعلام بإنجاز يوم دراسي                              portrait
# ═══════════════════════════════════════════════════════════════════════════

def _doc_iaam(c, d, base_dir):
    W, H = A4W, A4H
    xg, xd = MARGE, W - MARGE
    logo1, logo2, _ = _logos_paths(base_dir)
    _logo(c, logo1, xg, H - 96, 74, 74)
    _logo(c, logo2, xd - 80, H - 94, 70, 70)   # شعار الديوانة (بلا الخط الشارد)

    y = H - 44
    for l in ['الجمهورية التونسية', 'وزارة المالية', 'المدرسة الوطنية للديوانة',
              d['nom_centre'], 'إعلام بإنجاز يوم دراسي(1)']:
        _center(c, W / 2, y, l, F_ARB, 13); y -= 20

    # Champs
    y -= 14
    champs = [
        ('المعرف الوحيد', d['identifiant_unique']),
        ('الاسم واللقب', d['formateur_nom']),
        ('الرتبة', d['formateur_grade']),
        ('الخطة الوظيفية', d['plan_fonctionnel']),
        ('مكان العمل', d['administration']),
    ]
    for lab, val in champs:
        _right(c, xd - 60, y, lab, F_ARB, 12)
        _right(c, xd - 175, y, ':', F_AR, 12)
        _center(c, xg + 160, y, str(val or ''), F_AR, 12)
        y -= 30

    # Corps
    y -= 6
    corps = (f'عملا بأحكام {d["ordre_tajir"] if False else d["ordre_1995"]} '
             'والمتعلق بممارسة أعوان الدولة و الجماعات المحلية والمؤسسات العمومية '
             'ذات الصبغة الإدارية والمنشآت العمومية بعنوان مهني لنشاط خاص بمقابل')
    for ln in _wrap_lines(c, corps, F_AR, 11, xd - xg):
        _right(c, xd, y, ln, F_AR, 11); y -= 18
    y -= 8
    _center(c, W / 2, y, 'أتشرف بإعلامكم بقيامي بنشاط تكويني ) تقديم يوم دراسي (1)', F_ARB, 11); y -= 24
    _center(c, W / 2, y,
            f'تبعا للترخيص السنوي عدد {d["tarkhis_numero"] or "……………"} '
            f'بتاريخ {d["tarkhis_date"] or "…../…../……"} (2)', F_AR, 10.5); y -= 26

    # Quatre lignes alignées : libellés à droite (même bord), valeurs en colonne.
    for lab, val in [('في الموضوع الآتي', f'{d["titre"]} صنف {d["classe"]}'),
                     ('وذلك في الفترة' if d.get('multi') else 'وذلك يوم', d['date_longue']),
                     ('المكان', d['nom_centre_ba']),
                     ('عدد الساعات', str(d['heures']))]:
        _right(c, xd, y, f'{lab} :', F_ARB, 11)
        _right(c, xd - 160, y, str(val), F_AR, 11)
        y -= 26
    y -= 14

    # Date + الإمضاء + nom : alignés à GAUCHE, ordonnés, avec espace pour signer.
    _left(c, xg, y, f'{d["ville"]} في : {d.get("date_signature") or d["date_longue"]}', F_AR, 10.5); y -= 24
    _left(c, xg + 20, y, 'الإمضـــاء', F_ARB, 12); y -= 34
    _left(c, xg, y, f'{d["formateur_grade"]} {d["formateur_nom"]}', F_ARB, 11)


# ═══════════════════════════════════════════════════════════════════════════
#  Assemblage
# ═══════════════════════════════════════════════════════════════════════════

DRAW = {
    'mudhakkira': (_doc_mudhakkira, False),
    'bitaqa':     (_doc_bitaqa,     False),
    'jadwal':     (_doc_jadwal,     True),      # paysage
    'iaam':       (_doc_iaam,       False),
}
ORDRE = ('mudhakkira', 'bitaqa', 'jadwal', 'iaam')
TITRES = {
    'mudhakkira': 'مذكرة',
    'bitaqa':     'بطاقة إرشادات حول المكون',
    'jadwal':     'جدول بيان حساب',
    'iaam':       'إعلام بإنجاز يوم دراسي',
}


def generer(data, base_dir, docs=ORDRE, chemin=None):
    """Génère un PDF contenant les documents demandés, dans l'ordre officiel.
    `docs` : sous-ensemble/ordre de ORDRE. Retourne le chemin du PDF."""
    _register_fonts(base_dir)
    if not chemin:
        from core import chemins
        chemin = chemins.chemin_pdf_transitoire('khalas')
    docs = [x for x in ORDRE if x in set(docs)]   # ordre officiel garanti
    c = canvas.Canvas(chemin, pagesize=(A4W, A4H))
    for nom in docs:
        fn, paysage = DRAW[nom]
        c.setPageSize((A4H, A4W) if paysage else (A4W, A4H))
        fn(c, data, base_dir)
        c.showPage()
    c.save()
    return chemin
