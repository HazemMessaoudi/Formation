# -*- coding: utf-8 -*-
"""قواعد البرمجة: اليوم، الفترة، المكان، والمشاركون.

Trois règles, de force différente :

  1. **يوم الأحد** — simple avertissement. Une دورة peut exceptionnellement
     tomber un dimanche ; l'agent doit seulement le décider en connaissance
     de cause (confirmer ou corriger).

  2. **Même تاريخ + même فترة + même مكان** — REFUS. Une salle n'accueille pas
     deux دورات à la fois : ce n'est pas un choix, c'est une impossibilité.

  3. **Même تاريخ + même فترة, lieux différents** — le programme est permis,
     mais un même مشارك ne peut pas être inscrit aux deux : REFUS au moment
     où la قائمة المشاركين est enregistrée. Il en va de même d'un مشارك qui
     serait, au même moment, المكوّن de l'autre دورة.

Une فترة vide (« — ») signifie la journée entière : elle recouvre le matin
comme l'après-midi.

Ce module ne connaît ni Flask ni la قاعدة : il reçoit des données, rend des
messages prêts à afficher.
"""

from datetime import date

from core.importation import _normaliser

PERIODES_DEMI_JOURNEE = ('صباحا', 'مساءا')

JOURS_AR = ('الإثنين', 'الثلاثاء', 'الأربعاء', 'الخميس', 'الجمعة', 'السبت', 'الأحد')


def _date(texte):
    try:
        return date.fromisoformat(str(texte or '').strip()[:10])
    except (ValueError, TypeError):
        return None


def jour_de_semaine(texte):
    """Nom arabe du jour, ou '' si la date est illisible."""
    d = _date(texte)
    return JOURS_AR[d.weekday()] if d else ''


def est_dimanche(texte):
    d = _date(texte)
    return bool(d and d.weekday() == 6)


def _periode(p):
    p = (p or '').strip()
    return p if p in PERIODES_DEMI_JOURNEE else ''     # '' = journée entière


def periodes_se_chevauchent(p1, p2):
    a, b = _periode(p1), _periode(p2)
    return not a or not b or a == b


def libelle_periode(p):
    return _periode(p) or 'كامل اليوم'


def meme_lieu(l1, l2):
    a, b = _normaliser(l1), _normaliser(l2)
    return bool(a) and a == b


def _titre(f, i=None):
    t = (f.get('titre') or '').strip()
    if t:
        return f'«{t}»'
    return f'الدّورة {i}' if i else 'دورة بدون عنوان'


# ─── Règle 2 : une salle, une دورة à la fois ─────────────────────────────────

def conflits_de_lieu(formations, existantes=()):
    """Rend la liste des معاذير « même تاريخ + même فترة + même مكان ».

    formations : les دورات du برنامج en cours (liste de dicts) ;
    existantes : les دورات déjà enregistrées ailleurs, aux mêmes dates
                 (dicts portant aussi `ref_complet`), programme en cours exclu.
    """
    erreurs = []
    fs = list(formations or [])

    def conflit(a, b):
        """Premier jour commun (ISO) où a et b occupent la même salle à la
        même فترة, ou '' — V2 : une دورة متعدّدة الأيّام occupe CHACUN de
        ses jours."""
        if not ((a.get('date_formation') or '').strip()
                and periodes_se_chevauchent(a.get('periode'), b.get('periode'))
                and meme_lieu(a.get('lieu_formation'), b.get('lieu_formation'))):
            return ''
        communs = sorted(set(jours_occupes(a)) & set(jours_occupes(b)))
        return communs[0] if communs else ''

    for i, a in enumerate(fs, start=1):
        for j in range(i, len(fs)):
            b = fs[j]
            jour = conflit(a, b)
            if jour:
                erreurs.append(
                    f'{_titre(a, i)} و{_titre(b, j + 1)} في هذا البرنامج: '
                    f'نفس التّاريخ ({jour}) ونفس الفترة '
                    f'({libelle_periode(a.get("periode"))}) ونفس المكان '
                    f'«{a.get("lieu_formation", "").strip()}».')
        for b in existantes or ():
            jour = conflit(a, b)
            if jour:
                ref = (b.get('ref_complet') or '').strip()
                ou = f'في البرنامج {ref}' if ref else 'في برنامج آخر'
                erreurs.append(
                    f'{_titre(a, i)} تتزامن مع {_titre(b)} {ou}: '
                    f'نفس التّاريخ ({jour}) ونفس الفترة '
                    f'({libelle_periode(a.get("periode"))}) ونفس المكان '
                    f'«{a.get("lieu_formation", "").strip()}».')
    return erreurs


def jours_occupes(f):
    """V2 — Les jours (ISO) qu'occupe une دورة : son seul jour, ou chacun des
    jours d'une دورة متعدّدة الأيّام."""
    from core import jours as _jours
    return _jours.jours_de_la_dorra(f.get('date_formation'), f.get('date_fin'))


# ─── Règle 3 : un مشارك n'est pas à deux endroits ───────────────────────────

def _meme_personne(a, b):
    ua = (a.get('identifiant_unique') or '').strip()
    ub = (b.get('identifiant_unique') or '').strip()
    if ua and ub:
        return ua == ub
    na, nb = _normaliser(a.get('nom_prenom') or ''), _normaliser(b.get('nom_prenom') or '')
    return bool(na) and na == nb


def conflits_de_participants(participants, formation, simultanees):
    """Rend les معاذير pour une قائمة المشاركين.

    formation   : la دورة dont on enregistre la قائمة (date, فترة) ;
    simultanees : les autres دورات du même jour dont la فترة recouvre celle-ci,
                  chacune avec `participants` (liste) et `nom_formateur`.
    """
    erreurs = []
    per = libelle_periode(formation.get('periode'))
    for p in participants or []:
        nom = (p.get('nom_prenom') or '').strip()
        if not nom:
            continue
        for autre in simultanees or ():
            # V2 : jour commun (دورة متعدّدة الأيّام), sinon la date de la دورة
            d = (autre.get('date_commune') or formation.get('date_formation') or '')[:10]
            per = libelle_periode(autre['periode_commune']) if autre.get('periode_commune') \
                is not None else libelle_periode(formation.get('periode'))
            lieu = (autre.get('lieu_formation') or '').strip()
            ou = f' بـ«{lieu}»' if lieu else ''
            ref = (autre.get('ref_complet') or '').strip()
            ref = f' (البرنامج {ref})' if ref else ''
            if any(_meme_personne(p, q) for q in autre.get('participants') or ()):
                erreurs.append(
                    f'المشارك «{nom}» مسجَّل في دورة {_titre(autre)}{ou}{ref} '
                    f'في نفس التّاريخ ({d}) ونفس الفترة ({per}).')
            elif _normaliser(autre.get('nom_formateur') or '') == _normaliser(nom):
                erreurs.append(
                    f'المشارك «{nom}» هو مكوّن دورة {_titre(autre)}{ou}{ref} '
                    f'في نفس التّاريخ ({d}) ونفس الفترة ({per}).')
    return erreurs


def dimanches(formations):
    """Les دورات tombant un dimanche : pour l'avertissement avant تأكيد."""
    return [f for f in formations or [] if est_dimanche(f.get('date_formation'))]
