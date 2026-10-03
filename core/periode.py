# -*- coding: utf-8 -*-
"""مراقبة التّواريخ: الدّورة تقع في شهر برنامجها وسنته.

Un برنامج التكوين est mensuel : il porte un شهر et une سنة, et il les
annonce dans son objet même — « برنامج التكوين لشهر فيفري 2026 ». Une دورة
datée du 3 mars n'appartient donc pas à ce برنامج, elle appartient à celui
de mars. La règle est celle qu'a fixée le مركز : **دورة فيفري في فيفري**.

Le contrôle a lieu au moment du تأكيد, jamais pendant la saisie. Un
brouillon à demi rempli porte des dates provisoires et parfois vides ; les
refuser à la frappe ferait perdre le travail en cours. Mais dès que la
مراسلة prend son عدد, elle devient un acte officiel : à cet instant la date
doit être juste, car après elle ne se corrige plus.

Ce module ne connaît ni Flask ni la قاعدة : il reçoit des données et rend
des messages. C'est ce qui permet de l'éprouver cas par cas.
"""

from datetime import date

from core.arabe import MOIS_AR
from core import jours as _jours


def numero_de_mois(mois):
    """Rend le rang du شهر (1-12), ou None si le nom n'est pas reconnu.

    Le nom est comparé tel quel : les noms de mois de la منظومة viennent
    d'une liste fermée, on ne cherche pas à rattraper une graphie inconnue.
    """
    if not mois:
        return None
    nom = str(mois).strip()
    for rang, connu in enumerate(MOIS_AR, start=1):
        if nom == connu:
            return rang
    return None


def _lire_date(texte):
    """Rend une date ISO, ou None si la خانة est vide ou illisible."""
    if not texte:
        return None
    try:
        return date.fromisoformat(str(texte).strip()[:10])
    except (ValueError, TypeError):
        return None


def verifier_dates(mois, annee, formations):
    """Rend la liste des معاذير qui empêchent de confirmer ce برنامج.

    Liste vide : rien ne s'oppose au تأكيد. Chaque message nomme la دورة et
    dit ce qui cloche, de sorte que l'agent sache quoi corriger sans avoir à
    chercher.

    Une دورة sans date n'est pas un motif de refus ici : c'est une saisie
    incomplète, que les contrôles de complétude traitent ailleurs. Ce module
    ne juge que les dates effectivement écrites.
    """
    erreurs = []
    rang = numero_de_mois(mois)
    try:
        an = int(annee)
    except (TypeError, ValueError):
        an = None

    if rang is None or an is None:
        # Sans شهر ni سنة le برنامج n'a pas d'identité : rien à comparer.
        return erreurs

    for i, f in enumerate(formations or [], start=1):
        titre = (f.get('titre') or '').strip() or f'الدّورة {i}'
        brut = (f.get('date_formation') or '').strip()
        if not brut:
            continue
        d = _lire_date(brut)
        if d is None:
            erreurs.append(f'«{titre}»: التّاريخ غير مقروء ({brut}).')
            continue
        if d.year != an:
            erreurs.append(
                f'«{titre}»: التّاريخ في سنة {d.year} والبرنامج لسنة {an}. '
                f'دورة {MOIS_AR[d.month - 1]} {d.year} تتبع برنامج تلك السّنة.')
        elif d.month != rang:
            erreurs.append(
                f'«{titre}»: التّاريخ في شهر {MOIS_AR[d.month - 1]} '
                f'والبرنامج لشهر {mois}. دورة {MOIS_AR[d.month - 1]} '
                f'تتبع برنامج {MOIS_AR[d.month - 1]}.')
        # V2 : دورة متعدّدة الأيّام — la fin suit le début, 6 jours au plus.
        # Seul le DÉBUT est lié au mois du برنامج (دورة du 29 au 3 : برنامج
        # du mois où elle commence).
        erreurs.extend(_jours.verifier_plage(titre, brut, f.get('date_fin')))
    return erreurs
