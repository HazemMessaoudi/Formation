# -*- coding: utf-8 -*-
"""الدّورات متعدّدة الأيّام (V2) — règles et textes, sans Flask ni قاعدة.

Une دورة porte une date de début (`date_formation`) et, si elle dure plus
d'un jour, une date de fin (`date_fin`). Tant que `date_fin` est vide (ou ne
dépasse pas le début), la دورة est d'UN jour et TOUT se passe exactement
comme avant la V2 : aucun document, aucun écran ne change.

Règles retenues avec le centre :

  • au plus **6 jours** de formation (du lundi au samedi : la plus longue
    durée continue d'une دورة) ;
  • le **dimanche n'est pas un jour de formation** : il est sauté quand il
    tombe à l'intérieur de la période (seul un début fixé un dimanche, déjà
    confirmé par l'agent, reste compté) ;
  • la date de début appartient au mois du برنامج (règle inchangée) ; la fin
    peut déborder sur le mois suivant (دورة du 29 au 3).

Chaque jour a sa propre فترة (صباحا / مساءا), choisie dans برنامج الدورة ;
à défaut, c'est la فترة de la دورة qui s'applique.
"""

from datetime import date, timedelta

MAX_JOURS = 6

#: Les mois tels qu'ils s'écrivent dans les documents du centre.
MOIS = ('جانفي', 'فيفري', 'مارس', 'أفريل', 'ماي', 'جوان',
        'جويلية', 'أوت', 'سبتمبر', 'أكتوبر', 'نوفمبر', 'ديسمبر')
#: lundi = 0 … dimanche = 6 (convention de `date.weekday()`).
JOURS_SEMAINE = ('الاثنين', 'الثلاثاء', 'الأربعاء', 'الخميس', 'الجمعة', 'السبت', 'الأحد')

ORDINAUX = ('اليوم الأوّل', 'اليوم الثاني', 'اليوم الثالث',
            'اليوم الرابع', 'اليوم الخامس', 'اليوم السادس')


def lire(texte):
    """date ISO → `date`, ou None si la خانة est vide ou illisible."""
    try:
        return date.fromisoformat(str(texte or '').strip()[:10])
    except (ValueError, TypeError):
        return None


def jours_de_la_dorra(debut, fin=''):
    """Les jours de formation, en ISO, dans l'ordre.

    [] si le début est illisible ; [début] pour une دورة d'un jour (fin vide,
    illisible ou antérieure/égale au début). Les dimanches intérieurs sont
    sautés. Au-delà de MAX_JOURS, la liste est tronquée : la saisie qui
    dépasse est refusée ailleurs (`verifier_plage`), jamais devinée ici.
    """
    d0 = lire(debut)
    if not d0:
        return []
    d1 = lire(fin)
    if not d1 or d1 <= d0:
        return [d0.isoformat()]
    res, d = [d0.isoformat()], d0 + timedelta(days=1)
    # garde-fou : jamais plus de trois semaines parcourues
    while d <= d1 and d <= d0 + timedelta(days=21):
        if d.weekday() != 6:
            res.append(d.isoformat())
        d += timedelta(days=1)
    return res[:MAX_JOURS] if len(res) > MAX_JOURS else res


def nombre_de_jours(debut, fin=''):
    """Nombre de jours de formation, SANS troncature (pour le contrôle)."""
    d0, d1 = lire(debut), lire(fin)
    if not d0:
        return 0
    if not d1 or d1 <= d0:
        return 1
    n, d = 1, d0 + timedelta(days=1)
    while d <= d1:
        if d.weekday() != 6:
            n += 1
        d += timedelta(days=1)
    return n


def est_multi_jours(debut, fin=''):
    return nombre_de_jours(debut, fin) > 1


def normaliser_fin(debut, fin):
    """La date de fin telle qu'elle doit être enregistrée : '' pour une دورة
    d'un jour (fin vide ou égale au début), sinon l'ISO de la fin. Une fin
    illisible ou antérieure au début est gardée telle quelle : elle sera
    signalée au تأكيد (`verifier_plage`) au lieu d'être corrigée en silence ;
    d'ici là la دورة se lit comme une دورة d'un jour."""
    fin = str(fin or '').strip()
    if not fin:
        return ''
    d0, d1 = lire(debut), lire(fin)
    if d1 is None:
        return fin
    if d0 is not None and d1 == d0:
        return ''
    return d1.isoformat()


def derniere_date(f):
    """Dernier jour de formation d'une دورة (dict portant date_formation /
    date_fin) : la fin si elle existe, sinon le début."""
    jours = jours_de_la_dorra(f.get('date_formation'), f.get('date_fin'))
    return jours[-1] if jours else (f.get('date_formation') or '')


def libelle_jour(n):
    """1 → « اليوم الأوّل » … 6 → « اليوم السادس »."""
    try:
        return ORDINAUX[int(n) - 1]
    except (ValueError, TypeError, IndexError):
        return f'اليوم {n}'


def jour_semaine(iso):
    d = lire(iso)
    return JOURS_SEMAINE[d.weekday()] if d else ''


# ─── Contrôle de la saisie ───────────────────────────────────────────────────

def verifier_plage(titre, debut, fin):
    """Messages qui s'opposent à une période « من … إلى … » ([] si elle est
    juste). Une fin vide est toujours juste : دورة d'un jour."""
    fin = str(fin or '').strip()
    if not fin:
        return []
    nom = f'«{titre}»' if titre else 'الدّورة'
    d0, d1 = lire(debut), lire(fin)
    if d1 is None:
        return [f'{nom}: تاريخ نهاية الدّورة غير مقروء ({fin}).']
    if d0 is None:
        return [f'{nom}: يجب إدخال تاريخ بداية الدّورة قبل تاريخ نهايتها.']
    if d1 < d0:
        return [f'{nom}: تاريخ نهاية الدّورة ({d1.isoformat()}) يسبق تاريخ '
                f'بدايتها ({d0.isoformat()}).']
    n = nombre_de_jours(debut, fin)
    if n > MAX_JOURS:
        return [f'{nom}: مدّة الدّورة {n} أيّام، والحدّ الأقصى {MAX_JOURS} أيّام '
                f'متواصلة (من الاثنين إلى السبت).']
    return []


# ─── Textes des documents ────────────────────────────────────────────────────

def _jma(d):
    return d.day, MOIS[d.month - 1], d.year


def plage_longue(debut, fin='', prefixe=''):
    """Période en toutes lettres, la plus courte possible :

        un jour          → « 14 أكتوبر 2026 »
        même mois        → « من 14 إلى 16 أكتوبر 2026 »
        mois différents  → « من 29 أكتوبر إلى 3 نوفمبر 2026 »
        années diff.     → « من 29 ديسمبر 2026 إلى 2 جانفي 2027 »

    `prefixe` (« يوم ») précède chaque quantième : « من يوم 14 إلى يوم 16 … ».
    """
    jours = jours_de_la_dorra(debut, fin)
    if not jours:
        return str(debut or '')
    p = f'{prefixe} ' if prefixe else ''
    a = lire(jours[0])
    if len(jours) == 1:
        j, m, y = _jma(a)
        return f'{p}{j} {m} {y}'
    b = lire(jours[-1])
    (ja, ma, ya), (jb, mb, yb) = _jma(a), _jma(b)
    if ya != yb:
        return f'من {p}{ja} {ma} {ya} إلى {p}{jb} {mb} {yb}'
    if ma != mb:
        return f'من {p}{ja} {ma} إلى {p}{jb} {mb} {yb}'
    return f'من {p}{ja} إلى {p}{jb} {mb} {yb}'


def plage_iso(debut, fin='', sep=' → '):
    """« 2026-10-14 » ou « 2026-10-14 → 2026-10-16 » (écrans, listes)."""
    jours = jours_de_la_dorra(debut, fin)
    if len(jours) <= 1:
        return str(debut or '')
    return f'{jours[0]}{sep}{jours[-1]}'


def plage_slash(debut, fin=''):
    """« 2026/10/14 » ou « من 2026/10/14 إلى 2026/10/16 » (البطاقة البيداغوجية)."""
    jours = jours_de_la_dorra(debut, fin)
    if not jours:
        return str(debut or '')
    fmt = lambda iso: lire(iso).strftime('%Y/%m/%d')
    if len(jours) == 1:
        return fmt(jours[0])
    return f'من {fmt(jours[0])} إلى {fmt(jours[-1])}'


def jours_detail(debut, fin='', periode_defaut='', periodes=None):
    """Les jours d'une دورة, prêts pour l'écran et les documents :
    [{jour, date, libelle, semaine, periode}]. `periodes` : {jour : فترة}
    choisies dans برنامج الدورة ; à défaut, la فترة de la دورة."""
    periodes = periodes or {}
    res = []
    for n, iso in enumerate(jours_de_la_dorra(debut, fin), start=1):
        res.append({
            'jour': n,
            'date': iso,
            'libelle': libelle_jour(n),
            'semaine': jour_semaine(iso),
            'periode': (periodes.get(n) if periodes.get(n) is not None
                        else (periode_defaut or '')).strip(),
        })
    return res


# ─── Programme : découpage des lignes par jour ───────────────────────────────

def segmenter_lignes(rows):
    """Découpe les lignes d'un برنامج en jours.

    Un برنامج متعدّد الأيّام est enregistré comme une seule liste où chaque
    jour commence par une ligne `{'type': 'date_header', 'jour', 'date',
    'periode'}`. Rend [(entête | None, [lignes 'row'])] ; un برنامج d'un
    jour (sans entête) rend [(None, lignes)]. Les anciennes lignes
    « date_header » sans date (versions antérieures) sont ignorées.
    """
    segments, courant, entete = [], [], None
    vu_entete = False
    for r in rows or []:
        if not isinstance(r, dict):
            continue
        t = r.get('type') or 'row'
        if t == 'date_header':
            if not r.get('date'):
                continue                    # ancienne ligne d'en-tête : ignorée
            if vu_entete or courant:
                segments.append((entete, courant))
            entete, courant, vu_entete = r, [], True
            continue
        if t == 'row':
            courant.append(r)
    if vu_entete or courant or not segments:
        segments.append((entete, courant))
    return segments


def est_programme_multi(rows):
    """Vrai si le برنامج enregistré est découpé en jours (entêtes datées)."""
    return any(isinstance(r, dict) and (r.get('type') == 'date_header')
               and r.get('date') for r in rows or [])
