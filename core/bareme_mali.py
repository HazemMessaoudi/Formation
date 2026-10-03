"""المستحقّات المالية — الجدول المالي: من صنف الدّورة ورتبة المكوّن إلى المبلغ.

Ce module ne connaît ni Flask ni la قاعدة : il reçoit des données et rend des
nombres. C'est ce qui permet de l'éprouver cas par cas — et c'est nécessaire,
car il décide d'argent.

────────────────────────────────────────────────────────────────────────────
Le barème officiel (د للساعة الواحدة)

                              │ صنف أ1 │ صنف أ2 │ صنف أ3 │ صنف ب.ج.د
  ────────────────────────────┼────────┼────────┼────────┼───────────
  I   لواء/عميد/عقيد/مقدم      │ 25.000 │ 21.500 │ 18.000 │  15.000
  II  رائد/نقيب                │ 20.000 │ 18.000 │ 15.000 │  11.000
  III ملازم أول/ملازم          │ 12.500 │ 11.500 │ 11.000 │   9.000
  IV  من وكيل أول إلى عريف      │  9.000 │  8.000 │  7.000 │   6.000

Deux entrées, deux tables distinctes :

  • la LIGNE vient de la رتبة du مكوّن (quatre groupes : I à IV) ;
  • la COLONNE vient du صنف de la دورة, lui-même déduit des présents.

Les أصناف ب، ج، د partagent une seule colonne : le texte officiel les paie
au même taux. أ3 existe dans le barème mais aucune رتبة ne s'y rattache
aujourd'hui ; la colonne reste en place, prête à servir, plutôt que d'être
retirée puis réintroduite à la première mise à jour du texte.

────────────────────────────────────────────────────────────────────────────
Les ساعات

Elles se lisent dans **برنامج الدّورة** — le tableau des فقرات, chacune avec
son « من / إلى ». La durée retenue est le MEDÉ : de la première heure de
début à la dernière heure de fin. Une استراحة non consignée reste donc dans
la durée, exactement comme le vit le مكوّن.

Puis vient la règle qui compte : **toute fraction d'heure entamée est due en
entier**. 3h01 se paient 4 heures. C'est un plafond vers le haut (ceil), et
il s'applique UNE SEULE FOIS, sur la durée totale de la دورة — jamais فقرة
par فقرة, ce qui gonflerait le total sans fondement.
"""

import math
import re
from decimal import Decimal, ROUND_HALF_UP

# ─── Les quatre groupes du barème ────────────────────────────────────────────

GROUPES = ('I', 'II', 'III', 'IV')

#: مكوّن dont la رتبة n'est rattachée à aucun groupe (مدنيّ, رتبة ajoutée par
#: le centre, رتبة hors du texte officiel). Il ne se paie pas tant que
#: l'agent ne lui a pas donné son groupe dans الإعدادات.
GROUPE_INCONNU = ''

LIBELLES_GROUPES = {
    'I':   'المجموعة I — لواء / عميد / عقيد / مقدم',
    'II':  'المجموعة II — رائد / نقيب',
    'III': 'المجموعة III — ملازم أول / ملازم',
    'IV':  'المجموعة IV — من وكيل أول إلى عريف',
    GROUPE_INCONNU: 'غير محدَّدة',
}

#: Libellé court, pour les tableaux serrés.
LIBELLES_GROUPES_COURTS = {
    'I': 'المجموعة I', 'II': 'المجموعة II',
    'III': 'المجموعة III', 'IV': 'المجموعة IV',
    GROUPE_INCONNU: 'غير محدَّدة',
}


# ─── Les colonnes du barème ──────────────────────────────────────────────────
#
# Le صنف de la دورة (أ1، أ2، ب، ج، د) ne désigne pas directement une colonne :
# ب، ج et د partagent la dernière. Cette indirection est la seule chose qui
# sépare le تصنيف du paiement ; elle est écrite ici, une fois.

COLONNE_BJD = 'ب.ج.د'
COLONNES = ('أ1', 'أ2', 'أ3', COLONNE_BJD)

LIBELLES_COLONNES = {
    'أ1': 'صنف أ1',
    'أ2': 'صنف أ2',
    'أ3': 'صنف أ3',
    COLONNE_BJD: 'صنف ب / ج / د',
}

#: صنف الدّورة → colonne du barème.
COLONNE_DE_CLASSE = {
    'أ1': 'أ1',
    'أ2': 'أ2',
    'أ3': 'أ3',
    'ب':  COLONNE_BJD,
    'ج':  COLONNE_BJD,
    'د':  COLONNE_BJD,
}


def colonne_de_classe(classe):
    """Colonne du barème qui paie ce صنف de دورة. '' si le صنف est inconnu."""
    return COLONNE_DE_CLASSE.get((classe or '').strip(), '')


# ─── رتبة du مكوّن → groupe ──────────────────────────────────────────────────
#
# Semé au premier démarrage puis modifiable depuis الإعدادات : « في حالة وجود
# رتبة خارج الجدول يمكن القيام بالتحيينات اللازمة يدويا ».
#
# الرقيب أول et الرقيب ne figurent PAS dans le texte (le groupe IV s'arrête à
# عريف) : ils restent sans groupe, visibles comme tels dans الإعدادات, plutôt
# que rattachés d'office à un taux que le texte ne leur donne pas.

GRADES_PAR_GROUPE = {
    'I': (
        'اللواء', 'العميد', 'العقيد', 'المقدم',
    ),
    'II': (
        # v1.7 : « الملازم أعلى » retiré (رتبة inexistante — décision du 26/09/2026)
        'الرائد', 'النقيب',
    ),
    'III': (
        'الملازم أول', 'الملازم أول صنف 1', 'الملازم أول صنف 2', 'الملازم',
    ),
    'IV': (
        'الوكيل أول', 'الوكيل', 'العريف الأعلى', 'العريف أعلى',
        'العريف أول', 'العريف',
    ),
}


# ─── Normalisation d'une رتبة ────────────────────────────────────────────────
#
# Même règle que dans `core.mustahaqqat` : deux libellés qui désignent la même
# رتبة doivent donner la même clé. On la réécrit ici plutôt que de l'importer
# pour que ce module reste autonome et éprouvable seul.

_DIACRITIQUES = re.compile(r'[ؐ-ًؚ-ٰۖ-ۭـ]')
_NON_MOT = re.compile(r'[^\w\s]', re.UNICODE)
_MOTS_VIDES = ('للديوانه', 'الديوانه', 'ديوانه', 'للديوانة', 'الديوانة')


def normaliser_grade(grade):
    """Réduit une رتبة à une forme comparable."""
    texte = str(grade or '').strip()
    if not texte:
        return ''
    texte = _DIACRITIQUES.sub('', texte)
    texte = (texte.replace('أ', 'ا').replace('إ', 'ا').replace('آ', 'ا')
                  .replace('ى', 'ي').replace('ة', 'ه')
                  .replace('ؤ', 'و').replace('ئ', 'ي'))
    texte = _NON_MOT.sub(' ', texte)
    mots = []
    for mot in texte.split():
        if mot in _MOTS_VIDES:
            continue
        if mot.startswith('ال') and len(mot) > 3:
            mot = mot[2:]
        mots.append(mot)
    # « صنف أ2 » (graphie des قوائم) = « صنف 2 »
    return re.sub(r'صنف ا(\d)', r'صنف \1', ' '.join(mots))


#: Correspondance normalisée {clé رتبة : groupe}, construite une fois.
GROUPES_DEFAUT = {}
LIBELLES_GRADES = {}
for _groupe in GROUPES:
    for _libelle in GRADES_PAR_GROUPE[_groupe]:
        _cle = normaliser_grade(_libelle)
        GROUPES_DEFAUT.setdefault(_cle, _groupe)
        LIBELLES_GRADES.setdefault(_cle, _libelle)


def groupes_defaut():
    """Copie du rattachement par défaut : {رتبة (libellé) : groupe}."""
    return {LIBELLES_GRADES[c]: g for c, g in GROUPES_DEFAUT.items()}


def preparer_groupes(table=None):
    """Normalise une fois pour toutes les clés d'une table venue de la قاعدة."""
    prepare = dict(GROUPES_DEFAUT)
    for libelle, groupe in (table or {}).items():
        cle = normaliser_grade(libelle)
        if not cle:
            continue
        # Une رتبة explicitement laissée sans groupe ne doit pas retomber sur
        # le défaut : le centre l'a voulue ainsi.
        prepare[cle] = groupe if groupe in GROUPES else GROUPE_INCONNU
    return prepare


def _est_prepare(table):
    if not table:
        return False
    return all(normaliser_grade(k) == k for k in table)


def groupe_du_grade(grade, table=None):
    """Groupe du barème auquel appartient cette رتبة de مكوّن.

    Rend `GROUPE_INCONNU` pour une رتبة hors du texte : la دورة ne se chiffre
    pas tant que l'agent ne l'a pas rattachée dans الإعدادات.
    """
    cle = normaliser_grade(grade)
    if not cle:
        return GROUPE_INCONNU
    prete = table if _est_prepare(table) else preparer_groupes(table)
    valeur = prete.get(cle, GROUPE_INCONNU)
    return valeur if valeur in GROUPES else GROUPE_INCONNU


def libelle_groupe(groupe, court=False):
    table = LIBELLES_GROUPES_COURTS if court else LIBELLES_GROUPES
    return table.get(groupe, table[GROUPE_INCONNU])


# ─── Le barème officiel, en dinars par heure ─────────────────────────────────

TAUX_DEFAUT = {
    ('I',   'أ1'): 25.000, ('I',   'أ2'): 21.500,
    ('I',   'أ3'): 18.000, ('I',   COLONNE_BJD): 15.000,

    ('II',  'أ1'): 20.000, ('II',  'أ2'): 18.000,
    ('II',  'أ3'): 15.000, ('II',  COLONNE_BJD): 11.000,

    ('III', 'أ1'): 12.500, ('III', 'أ2'): 11.500,
    ('III', 'أ3'): 11.000, ('III', COLONNE_BJD):  9.000,

    ('IV',  'أ1'):  9.000, ('IV',  'أ2'):  8.000,
    ('IV',  'أ3'):  7.000, ('IV',  COLONNE_BJD):  6.000,
}


def bareme_defaut():
    """Copie du barème officiel : {(groupe, colonne) : taux}."""
    return dict(TAUX_DEFAUT)


def taux_horaire(groupe, classe, bareme=None):
    """Prix de l'heure pour ce (groupe de مكوّن, صنف de دورة).

    Rend `None` — et non zéro — quand le couple ne donne pas de taux : une
    رتبة sans groupe, un صنف non déterminé, ou une case laissée vide dans
    الإعدادات (la colonne أ3 l'est par défaut). Zéro serait un montant ;
    `None` dit qu'il n'y a pas de montant à dire.
    """
    if groupe not in GROUPES:
        return None
    colonne = colonne_de_classe(classe)
    if not colonne:
        return None
    table = bareme if bareme is not None else TAUX_DEFAUT
    valeur = table.get((groupe, colonne))
    if valeur is None:
        return None
    try:
        valeur = float(valeur)
    except (TypeError, ValueError):
        return None
    return valeur if valeur > 0 else None


# ─── Les ساعات, lues dans برنامج الدّورة ─────────────────────────────────────

_HEURE = re.compile(r'^\s*(\d{1,2})\s*[:.]\s*(\d{1,2})\s*$')


def lire_heure(texte):
    """Rend une heure en minutes depuis minuit, ou None si elle est illisible.

    Accepte « 08:30 » comme « 8.30 » : les deux graphies circulent dans les
    برامج saisis à la main.
    """
    m = _HEURE.match(str(texte or ''))
    if not m:
        return None
    heures, minutes = int(m.group(1)), int(m.group(2))
    if not (0 <= heures <= 23 and 0 <= minutes <= 59):
        return None
    return heures * 60 + minutes


def formater_heure(minutes):
    """Minutes depuis minuit → « 08:30 ». '' si la valeur n'a pas de sens."""
    if minutes is None:
        return ''
    try:
        minutes = int(minutes)
    except (TypeError, ValueError):
        return ''
    if minutes < 0:
        return ''
    return f'{minutes // 60:02d}:{minutes % 60:02d}'


def plage_du_programme(rows):
    """Le MEDÉ du برنامج : (début, fin) en minutes depuis minuit.

    On retient la première heure de début et la dernière heure de fin, toutes
    فقرات confondues — c'est la durée que vit réellement le مكوّن, استراحات
    comprises.

    Les lignes d'en-tête de date, les فقرات à moitié saisies et les heures
    illisibles sont écartées sans bruit : elles ne portent pas de durée.
    Rend (None, None) quand aucune فقرة n'est exploitable.
    """
    debuts, fins = [], []
    for row in rows or []:
        if not isinstance(row, dict):
            continue
        if (row.get('type') or 'row') != 'row':
            continue
        d = lire_heure(row.get('time_debut'))
        f = lire_heure(row.get('time_fin'))
        # Une فقرة n'entre dans le calcul que complète et cohérente : sans
        # cela on prendrait un début sans fin pour une durée nulle.
        if d is None or f is None or f <= d:
            continue
        debuts.append(d)
        fins.append(f)
    if not debuts:
        return None, None
    return min(debuts), max(fins)


def arrondir_heures(minutes):
    """Toute fraction d'heure entamée est due en entier.

    3h00 → 3 ; 3h01 → 4 ; 3h30 → 4. Le plafond s'applique une seule fois,
    sur la durée totale.
    """
    if not minutes or minutes <= 0:
        return 0
    return int(math.ceil(minutes / 60.0))


def heures_du_programme(rows):
    """Durée payable d'une دورة, telle qu'elle se lit dans son برنامج.

    Rend un dict :
      • `debut`, `fin`   — « 08:30 », « 12:30 » (ou '' si le برنامج est muet)
      • `minutes`        — durée réelle du مدى
      • `heures`         — durée payable, arrondie vers le haut
      • `arrondi`        — True si l'arrondi a ajouté quelque chose (pour que
                           l'écran puisse le dire au lieu de le taire)
    """
    # V2 — برنامج متعدّد الأيّام : chaque jour est une séance. Ses heures se
    # lisent et s'arrondissent SÉPARÉMENT (heure entamée due, une fois par
    # jour), puis s'additionnent. `jours` porte le détail pour l'écran.
    from core import jours as _jours
    if _jours.est_programme_multi(rows):
        detail = []
        for ent, lignes in _jours.segmenter_lignes(rows):
            h = heures_du_programme(lignes)
            h.update({'jour': (ent or {}).get('jour'), 'date': (ent or {}).get('date', ''),
                      'periode': (ent or {}).get('periode', ''),
                      'libelle': _jours.libelle_jour((ent or {}).get('jour'))})
            detail.append(h)
        utiles = [h for h in detail if h['heures'] > 0]
        minutes = sum(h['minutes'] for h in utiles)
        heures = sum(h['heures'] for h in utiles)
        return {
            'debut':   utiles[0]['debut'] if utiles else '',
            'fin':     utiles[-1]['fin'] if utiles else '',
            'minutes': minutes,
            'heures':  heures,
            'arrondi': (heures * 60) != minutes,
            'jours':   detail,
        }
    debut, fin = plage_du_programme(rows)
    if debut is None:
        return {'debut': '', 'fin': '', 'minutes': 0,
                'heures': 0, 'arrondi': False}
    minutes = fin - debut
    heures = arrondir_heures(minutes)
    return {
        'debut':   formater_heure(debut),
        'fin':     formater_heure(fin),
        'minutes': minutes,
        'heures':  heures,
        'arrondi': (heures * 60) != minutes,
    }


def duree_en_texte(minutes):
    """« 3 ساعات و30 دقيقة » — la durée réelle, dite en clair.

    L'écran montre côte à côte la durée vécue et la durée payée ; sans cette
    phrase, l'agent verrait « 4 ساعات » sans savoir d'où elles viennent.
    """
    try:
        minutes = int(minutes or 0)
    except (TypeError, ValueError):
        return ''
    if minutes <= 0:
        return ''
    h, m = divmod(minutes, 60)
    if h and m:
        return f'{h} ساعات و{m} دقيقة' if h > 1 else f'ساعة و{m} دقيقة'
    if h:
        return f'{h} ساعات' if h > 1 else 'ساعة واحدة'
    return f'{m} دقيقة'


# ─── Le montant ──────────────────────────────────────────────────────────────
#
# v1.7 — Tout calcul d'argent passe par Decimal : un float ne représente pas
# 0.1 exactement, et round() sur un float arrondit « au pair » ce qui est en
# réalité juste en dessous de la moitié (5.250 × 15 % donnait 0.787 au lieu
# de 0.788). Règle retenue : arrondi au millime, « نصف فما فوق ».

MILLIME = Decimal('0.001')


def dec(valeur):
    """Decimal exact d'un montant saisi ou stocké (float, int, str « 12,5 »)."""
    if isinstance(valeur, Decimal):
        return valeur
    if valeur is None or str(valeur).strip() == '':
        raise ValueError('montant vide')
    return Decimal(str(valeur).strip().replace(',', '.'))


def arrondir_millime(d):
    """Arrondi au millime, la moitié vers le haut (0.7875 → 0.788)."""
    return dec(d).quantize(MILLIME, rounding=ROUND_HALF_UP)


def calculer_montant(heures, taux):
    """المبلغ = عدد الساعات × سعر الساعة. None si l'un des deux manque."""
    if taux is None or not heures:
        return None
    try:
        # v1.7 : arithmétique décimale exacte, arrondi au millime.
        return float(arrondir_millime(dec(taux) * int(heures)))
    except (TypeError, ValueError, ArithmeticError):
        return None


def formater_dinars(montant):
    """« 75.000 » — le dinar s'écrit à trois décimales (millimes)."""
    if montant is None:
        return ''
    try:
        return f'{arrondir_millime(dec(montant)):.3f}'
    except (TypeError, ValueError, ArithmeticError):
        return ''


def chiffrer(rows, classe, grade_formateur, bareme=None, groupes=None):
    """Le calcul complet d'une دورة, d'un seul tenant.

    Réunit les trois lectures — les ساعات du برنامج, le groupe de la رتبة, le
    taux du barème — et dit le montant. Quand quelque chose manque, le dit
    aussi : `motifs` porte ce qui empêche de chiffrer, en clair, pour que
    l'écran l'affiche au lieu d'annoncer un zéro trompeur.
    """
    duree = heures_du_programme(rows)
    groupe = groupe_du_grade(grade_formateur, groupes)
    colonne = colonne_de_classe(classe)
    taux = taux_horaire(groupe, classe, bareme)
    montant = calculer_montant(duree['heures'], taux)

    motifs = []
    if duree['heures'] <= 0:
        motifs.append('برنامج الدورة لا يحمل توقيتًا صالحًا (من / إلى)، '
                      'فلا يمكن احتساب الساعات.')
    if not colonne:
        motifs.append('صنف الدورة غير محدَّد.')
    if groupe == GROUPE_INCONNU:
        # v1.7 : message explicite (الرقيب, المدنيّون… : hors texte).
        motifs.append(f'رتبة المكوّن «{grade_formateur or "—"}» خارج الجدول المالي: '
                      'لا يحدّد النصّ سعرًا لهذه الرتبة. يمكن للمشرف العام ربطها '
                      'بمجموعة من الإعدادات ← الجدول المالي إن اقتضى الأمر.')
    elif taux is None and colonne:
        motifs.append(f'الجدول المالي لا يحمل سعرًا للـ{libelle_groupe(groupe, True)} '
                      f'في {LIBELLES_COLONNES.get(colonne, colonne)}.')

    return {
        'debut':           duree['debut'],
        'fin':             duree['fin'],
        'minutes':         duree['minutes'],
        'duree_texte':     duree_en_texte(duree['minutes']),
        'heures':          duree['heures'],
        'arrondi':         duree['arrondi'],
        'groupe':          groupe,
        'libelle_groupe':  libelle_groupe(groupe),
        'colonne':         colonne,
        'libelle_colonne': LIBELLES_COLONNES.get(colonne, ''),
        'taux':            taux,
        'taux_texte':      formater_dinars(taux),
        'montant':         montant,
        'montant_texte':   formater_dinars(montant),
        'chiffrable':      not motifs,
        'motifs':          motifs,
        # V2 : détail jour par jour d'une دورة متعدّدة الأيّام ([] sinon)
        'jours':           duree.get('jours', []),
    }
