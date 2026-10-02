"""المستحقّات المالية — تصنيف الرتب إلى أصناف، وتحديد صنف الدّورة.

Le barème des مستحقّات ne connaît pas les رتب une à une : il connaît des
**أصناف**. Ce module est l'unique endroit où la correspondance
« رتبة → صنف » est écrite, et l'unique endroit où se décide le صنف d'une
dorra. Tout le reste de la منظومة (routes, gabarits, PDF) s'y réfère.

La table officielle (الأمر المتعلّق بضبط النّظام الأساسي الخاصّ بأعوان الدّيوانة) :

    ┌────────────────────────┬─────────┬───────────────┐
    │ الرتبة                 │ الصنف   │ الصنف الفرعي  │
    ├────────────────────────┼─────────┼───────────────┤
    │ لواء للديوانة          │ أ       │ أ1            │
    │ عميد للديوانة          │ أ       │ أ1            │
    │ عقيد للديوانة          │ أ       │ أ1            │
    │ مقدم للديوانة          │ أ       │ أ1            │
    │ رائد للديوانة          │ أ       │ أ1            │
    │ نقيب للديوانة          │ أ       │ أ1            │
    │ ملازم أول صنف 1        │ أ       │ أ1            │
    │ ملازم أول صنف 2        │ أ       │ أ2            │
    │ ملازم للديوانة         │ أ       │ أ2            │
    ├────────────────────────┼─────────┼───────────────┤
    │ وكيل أول للديوانة      │ ب       │ —             │
    │ وكيل للديوانة          │ ب       │ —             │
    │ عريف أعلى للديوانة     │ ب       │ —             │
    │ عريف للديوانة          │ ج       │ —             │
    ├────────────────────────┼─────────┼───────────────┤
    │ رقيب أول للديوانة      │ د       │ —             │
    │ رقيب للديوانة          │ د       │ —             │
    └────────────────────────┴─────────┴───────────────┘

Les cinq valeurs retenues par la منظومة sont donc : أ1، أ2، ب، ج، د.
"""

import re

# ─── Les cinq أصناف, du plus élevé au plus bas ───────────────────────────────
#
# L'ordre compte : il tranche les égalités quand deux أصناف comptent autant de
# présents. On retient alors le plus élevé — un صنف plus bas ne peut pas
# emporter une dorra où il ne domine pas réellement.

CLASSES = ('أ1', 'أ2', 'ب', 'ج', 'د')

#: صنف attribué à un participant dont la رتبة n'est pas dans le barème
#: (مدنيّون : السيد / السيدة، ou une رتبة ajoutée par le centre).
CLASSE_INCONNUE = ''

LIBELLES_CLASSES = {
    'أ1': 'الصنف أ1',
    'أ2': 'الصنف أ2',
    'ب':  'الصنف ب',
    'ج':  'الصنف ج',
    'د':  'الصنف د',
    CLASSE_INCONNUE: 'غير مصنّف',
}


# ─── Normalisation d'une رتبة ────────────────────────────────────────────────

_DIACRITIQUES = re.compile(r'[ؐ-ًؚ-ٰٟۖ-ۭـ]')
_NON_MOT = re.compile(r'[^\w\s]', re.UNICODE)

#: Mots qui ne distinguent pas une رتبة d'une autre et qu'on écarte avant
#: comparaison : « العريف للديوانة » et « عريف » sont la même رتبة.
_MOTS_VIDES = ('للديوانه', 'الديوانه', 'ديوانه', 'للديوانة', 'الديوانة')


def normaliser_grade(grade):
    """Réduit une رتبة à une forme comparable.

    Enlève les diacritiques, l'article, la ponctuation et la mention
    « للديوانة », unifie les hamza et les formes finales. Deux libellés qui
    désignent la même رتبة donnent la même chaîne.
    """
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


def _cle(libelle):
    return normaliser_grade(libelle)


# ─── Barème par défaut : رتبة → صنف ──────────────────────────────────────────
#
# Il est semé en base au premier démarrage puis devient modifiable depuis
# الإعدادات : un centre n'a pas à patcher le code pour une رتبة qu'il ajoute.

GRADES_PAR_CLASSE = {
    'أ1': (
        'اللواء', 'العميد', 'العقيد', 'المقدم', 'الرائد', 'النقيب',
        'الملازم أول صنف 1', 'الملازم أول',
    ),
    'أ2': (
        'الملازم أول صنف 2', 'الملازم',
    ),
    'ب': (
        'الوكيل أول', 'الوكيل', 'العريف الأعلى', 'العريف أعلى', 'العريف أول',
    ),
    'ج': (
        'العريف',
    ),
    'د': (
        'الرقيب أول', 'الرقيب',
    ),
}

#: Correspondance normalisée, construite une seule fois.
#: Les libellés les plus longs sont insérés en premier pour qu'une رتبة
#: composée (« الملازم أول ») ne soit jamais écrasée par sa racine.
BAREME_DEFAUT = {}
for _classe in CLASSES:
    for _libelle in GRADES_PAR_CLASSE[_classe]:
        BAREME_DEFAUT.setdefault(_cle(_libelle), _classe)

#: Libellé d'origine de chaque clé, pour peupler la table éditable.
LIBELLES_GRADES = {}
for _classe in CLASSES:
    for _libelle in GRADES_PAR_CLASSE[_classe]:
        LIBELLES_GRADES.setdefault(_cle(_libelle), _libelle)


def bareme_defaut():
    """Copie du barème par défaut : {رتبة (libellé) : صنف}."""
    return {LIBELLES_GRADES[cle]: classe for cle, classe in BAREME_DEFAUT.items()}


# ─── Classement d'un participant ─────────────────────────────────────────────

def preparer_bareme(bareme=None):
    """Normalise une fois pour toutes les clés d'un barème venu de la قاعدة.

    Sans cette étape, chaque participant relancerait la normalisation de
    TOUTES les رتب du barème — inutile, et lent dès que le centre en ajoute.
    """
    prepare = dict(BAREME_DEFAUT)
    for libelle, classe in (bareme or {}).items():
        cle = normaliser_grade(libelle)
        if not cle:
            continue
        if classe in CLASSES:
            prepare[cle] = classe
        else:
            # Une رتبة explicitement laissée sans صنف (مدنيّون) ne doit pas
            # retomber sur le barème par défaut : le centre l'a voulue ainsi.
            prepare[cle] = CLASSE_INCONNUE
    return prepare


def classe_du_grade(grade, bareme=None):
    """صنف d'une رتبة. `bareme` est un dict {رتبة : صنف} venu de la قاعدة —
    brut ou déjà passé par `preparer_bareme()` ; à défaut, le barème officiel
    s'applique.

    Une رتبة inconnue (مدني, رتبة ajoutée localement sans صنف) renvoie
    `CLASSE_INCONNUE` : elle ne pèse dans aucun صنف et ne fausse donc pas le
    calcul du صنف الدّورة.
    """
    cle = normaliser_grade(grade)
    if not cle:
        return CLASSE_INCONNUE
    table = bareme if _est_prepare(bareme) else preparer_bareme(bareme)
    valeur = table.get(cle, CLASSE_INCONNUE)
    return valeur if valeur in CLASSES else CLASSE_INCONNUE


def _est_prepare(bareme):
    """Un barème préparé a toutes ses clés déjà normalisées."""
    if not bareme:
        return False
    return all(normaliser_grade(k) == k for k in bareme)


# ─── صنف الدّورة ─────────────────────────────────────────────────────────────

def repartition(participants, bareme=None):
    """Compte les participants par صنف.

    `participants` : itérable de dict portant au moins `grade`. Seuls les
    présents doivent être transmis — l'absent ne compte pas dans le صنف.

    Renvoie {صنف : nombre} pour les cinq أصناف, plus la clé `CLASSE_INCONNUE`
    quand des رتب non classées figurent dans la liste.
    """
    table = preparer_bareme(bareme)
    compte = {c: 0 for c in CLASSES}
    for p in participants or []:
        grade = p.get('grade') if isinstance(p, dict) else p
        classe = classe_du_grade(grade, table)
        if classe in compte:
            compte[classe] += 1
        else:
            compte[CLASSE_INCONNUE] = compte.get(CLASSE_INCONNUE, 0) + 1
    return compte


def classe_dominante(participants, bareme=None):
    """صنف الدّورة = le صنف le plus représenté parmi les **présents**.

    Renvoie `(classe, repartition, ex_aequo)` :
      • `classe`      — le صنف retenu, ou `CLASSE_INCONNUE` si aucun présent
                        n'est classable ;
      • `repartition` — le détail du comptage, pour l'écran de confirmation ;
      • `ex_aequo`    — liste des أصناف à égalité quand il y en a plusieurs.
                        L'agent voit alors que la منظومة a tranché, et sur
                        quoi : le صنف le plus élevé l'emporte.
    """
    compte = repartition(participants, bareme)
    maximum = max((compte.get(c, 0) for c in CLASSES), default=0)
    if maximum <= 0:
        return CLASSE_INCONNUE, compte, []
    egaux = [c for c in CLASSES if compte.get(c, 0) == maximum]
    return egaux[0], compte, (egaux if len(egaux) > 1 else [])


def libelle_classe(classe):
    return LIBELLES_CLASSES.get(classe, LIBELLES_CLASSES[CLASSE_INCONNUE])
