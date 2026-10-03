# -*- coding: utf-8 -*-
"""Exports Excel (v1.5 — D3, S1).

Un classeur .xlsx plutôt qu'un CSV : Excel sous Windows (réglages régionaux
français ou arabes) ouvre un CSV avec le mauvais séparateur ou le mauvais
encodage, et l'arabe devient illisible. Le .xlsx n'a aucun de ces problèmes.

Chaque export : feuille de droite à gauche, en-tête en gras sur fond de la
couleur du programme, première ligne figée, filtre automatique, largeurs de
colonnes adaptées au contenu.

L'export des أسماء reprend EN TÊTE les عناوين que l'import reconnaît
(core/importation.COLONNES) : un fichier exporté, corrigé dans Excel, se
réimporte tel quel.
"""
from datetime import datetime
from io import BytesIO

MIME_XLSX = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'

def _cellule(v):
    if v is None:
        return ''
    return v if isinstance(v, (int, float)) else str(v)


def _remplir(ws, entetes, lignes, sous_titre=None):
    """Remplit une feuille : sous-titre éventuel, en-tête stylé, lignes,
    largeurs, ligne d'en-tête figée, filtre automatique."""
    from openpyxl.styles import Alignment, Font, PatternFill, Border, Side
    from openpyxl.utils import get_column_letter

    ws.sheet_view.rightToLeft = True
    debut = 1
    if sous_titre:
        ws.append([sous_titre])
        ws.cell(row=1, column=1).font = Font(bold=True, size=13, color='1E3A5F')
        ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=max(1, len(entetes)))
        ws.row_dimensions[1].height = 24
        debut = 2

    ws.append(list(entetes))
    fond = PatternFill('solid', fgColor='1E3A5F')
    fin = Side(style='thin', color='C8D0DC')
    for c in ws[debut]:
        c.font = Font(bold=True, color='FFFFFF', size=11)
        c.fill = fond
        c.alignment = Alignment(horizontal='center', vertical='center', wrap_text=True)
    ws.row_dimensions[debut].height = 24

    largeurs = [len(str(e)) + 4 for e in entetes]
    for ligne in lignes:
        ws.append([_cellule(v) for v in ligne])
        for i, v in enumerate(ligne):
            if i < len(largeurs):
                largeurs[i] = max(largeurs[i], min(60, len(str(v if v is not None else '')) + 2))
    for row in ws.iter_rows(min_row=debut + 1, max_row=ws.max_row):
        for c in row:
            # Une valeur saisie commençant par « = » reste du TEXTE : jamais une
            # formule exécutée à l'ouverture du fichier (injection de formule).
            if c.data_type == 'f':
                c.data_type = 's'
            c.border = Border(bottom=fin)
            c.alignment = Alignment(vertical='top', wrap_text=True)
    for i, w in enumerate(largeurs, start=1):
        ws.column_dimensions[get_column_letter(i)].width = max(10, w)

    ws.freeze_panes = ws.cell(row=debut + 1, column=1)
    if entetes:
        ws.auto_filter.ref = f'A{debut}:{get_column_letter(len(entetes))}{max(debut, ws.max_row)}'


def classeur(titre_feuille, entetes, lignes, sous_titre=None):
    """Construit un .xlsx d'une feuille en mémoire ; rend un BytesIO."""
    from openpyxl import Workbook
    wb = Workbook()
    ws = wb.active
    ws.title = (titre_feuille or 'Feuille')[:31]
    _remplir(ws, entetes, lignes, sous_titre)
    flux = BytesIO()
    wb.save(flux)
    flux.seek(0)
    return flux


def horodatage():
    return datetime.now().strftime('%Y%m%d_%H%M')


# ─── الأسماء ─────────────────────────────────────────────────────────────────

#: (champ, en-tête). Les 12 premières colonnes portent EXACTEMENT un libellé
#: reconnu par l'import ; les suivantes sont informatives (l'import les ignore).
COLONNES_MKOWIN = (
    ('identifiant_unique', 'المعرّف الوحيد'),
    ('grade', 'الرتبة'),
    ('nom', 'الاسم'),
    ('prenom', 'اللقب'),
    ('lieu_travail', 'مكان العمل'),
    ('jiha_marjiiya', 'الجهة المرجعية'),
    ('administration', 'الإدارة'),
    ('telephone_gsm', 'الهاتف'),
    ('email', 'البريد الإلكتروني'),
    ('cin', 'بطاقة التعريف'),
    ('specialite', 'الاختصاص'),
    ('diplome', 'الشهادة'),
    # ── informatives ──
    ('cin_date', 'تاريخ إصدار بطاقة التعريف'),
    ('telephone_adm', 'الهاتف الإداري'),
    ('adresse', 'العنوان الشخصي'),
    ('degre', 'الرتبة المهنية'),
    ('plan_fonctionnel', 'الخطة الوظيفية'),
    ('ministere', 'وزارة الإشراف'),
    ('banque', 'البنك'),
    ('agence', 'الفرع'),
    ('num_compte', 'رقم الحساب'),
    ('notes', 'ملاحظات'),
)


def export_mkowin(mkowin):
    lignes = [[m.get(ch) or '' for ch, _ in COLONNES_MKOWIN] for m in mkowin]
    return classeur('الأسماء', [t for _, t in COLONNES_MKOWIN], lignes)


# ─── سجلّ المراسلات ─────────────────────────────────────────────────────────

def export_registre(entrees, type_lettre, annee):
    nom = 'الداخلية' if type_lettre == 'interne' else 'الخارجية'
    entetes = ('الرقم', 'المرجع', 'نوع الوثيقة', 'الموضوع', 'الحالة', 'تاريخ الترسيم')
    lignes = [[
        '%04d' % int(e.get('numero') or 0),
        e.get('ref_complet') or '',
        e.get('source_label') or '',
        e.get('objet') or '',
        'محجوز' if e.get('statut') == 'provisoire' else 'نهائي',
        (e.get('date_attribution') or '')[:10],
    ] for e in entrees]
    return classeur(f'سجل {annee}', entetes, lignes,
                    sous_titre=f'سجلّ المراسلات {nom} — سنة {annee}')


# ─── الدورات التكوينية ──────────────────────────────────────────────────────

def _plage(d):
    """V2 : « 2026-10-12 → 2026-10-14 » pour une دورة متعدّدة الأيّام."""
    from core import jours as _jours
    return _jours.plage_iso(d.get('date_formation') or '', d.get('date_fin') or '')


def export_dorrat(dorrat):
    entetes = ('عنوان الدورة', 'مرجع البرنامج', 'الشهر', 'السنة', 'تاريخ الدورة', 'الفترة',
               'مكان التكوين', 'رتبة المكوّن', 'المكوّن', 'مكان عمل المكوّن',
               'عدد المشاركين', 'حالة الدورة', 'المستحقّات')
    lignes = [[
        d.get('titre') or '', d.get('lettre_ref') or '', d.get('lettre_mois') or '',
        d.get('lettre_annee') or '', _plage(d), d.get('periode') or '',
        d.get('lieu_formation') or '', d.get('grade') or '', d.get('nom_formateur') or '',
        d.get('lieu_travail') or '', d.get('nb_participants') or 0,
        (d.get('etat') or {}).get('label', ''),
        (d.get('etat_fin') or {}).get('label', '') if d.get('etat_fin') else '—',
    ] for d in dorrat]
    return classeur('الدورات', entetes, lignes)


# ─── سجلّ التدقيق ───────────────────────────────────────────────────────────

def export_journal(entrees):
    entetes = ('التاريخ والساعة', 'المستعمل', 'العمليّة', 'العنصر', 'تفاصيل')
    lignes = [[e.get('horodatage') or '', e.get('utilisateur') or '', e.get('action') or '',
               e.get('cible') or '', e.get('details') or ''] for e in entrees]
    return classeur('سجل التدقيق', entetes, lignes)


# ─── التقرير السنوي (D1) ────────────────────────────────────────────────────

def export_rapport(r, centre=''):
    """Classeur de plusieurs feuilles : ملخّص، حسب الشهر، حسب المكوّن، حسب
    المادّة، حسب الجهة، حسب الجنس. Montants arrondis au millime (3 décimales)."""
    from openpyxl import Workbook
    a, t = r['annee'], r['totaux']
    wb = Workbook()
    ws = wb.active
    ws.title = 'ملخّص'
    _remplir(ws, ('البيان', 'القيمة'), [
        ('برامج التكوين', t['programmes']), ('منها مؤكَّدة', t['programmes_confirmes']),
        ('الدورات', t['dorrat']), ('الدورات المسجّلة نهائيًّا', t['finalisees']),
        ('المشاركات', t['participations']), ('المشاركون (دون تكرار)', t['participants_uniques']),
        ('معدّل المشاركين في الدورة', t['moyenne_participants']),
        ('المكوّنون', t['formateurs']), ('دورات أُنجزت مستحقّاتها', t['dorrat_payees']),
        ('ساعات التكوين المدفوعة', t['heures']), ('جملة المستحقّات (د)', round(t['montant'], 3)),
        ('المراسلات الحرّة', t['libres']),
        ('أعداد السجلّ الداخلي', t['registre_interne']), ('أعداد السجلّ الخارجي', t['registre_externe']),
    ], sous_titre=f'التقرير السنوي {a}' + (f' — {centre}' if centre else ''))
    ws2 = wb.create_sheet('حسب الشهر')
    _remplir(ws2, ('الشهر', 'الدورات', 'المسجّلة نهائيًّا', 'المشاركون', 'الساعات المدفوعة', 'المستحقّات (د)'),
             [(m['mois'], m['dorrat'], m['finalisees'], m['participants'], m['heures'], round(m['montant'], 3))
              for m in r['par_mois']]
             + [('المجموع', t['dorrat'], t['finalisees'], t['participations'], t['heures'], round(t['montant'], 3))])
    ws3 = wb.create_sheet('حسب المكوّن')
    _remplir(ws3, ('المكوّن', 'الرتبة', 'الدورات', 'الساعات المدفوعة', 'المستحقّات (د)'),
             [(f['nom'], f['grade'] or '', f['dorrat'], f['heures'] or 0, round(f['montant'] or 0, 3))
              for f in r['par_formateur']])
    ws4 = wb.create_sheet('حسب المادّة')
    _remplir(ws4, ('مادّة التكوين', 'الدورات', 'المشاركون'),
             [(m['titre'], m['dorrat'], m['participants'] or 0) for m in r['par_madda']])
    # v1.7.1 : feuille « حسب الجهة » retirée (statistique abandonnée)
    ws6 = wb.create_sheet('حسب الجنس')
    _remplir(ws6, ('الجنس', 'المشاركات', 'المشاركون (دون تكرار)', 'النسبة (%)'),
             [(x['sexe'], x['participations'], x['uniques'], x['part'])
              for x in r.get('par_sexe', [])])
    flux = BytesIO()
    wb.save(flux)
    flux.seek(0)
    return flux
