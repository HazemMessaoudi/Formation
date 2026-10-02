# -*- coding: utf-8 -*-
"""États affichables des دورات et des برامج (v1.5 — A13, P2).

Une seule source de vérité pour les pastilles d'état et le repérage des
dossiers EN RETARD : une دورة dont la date est passée mais qui n'a pas été
enregistrée définitivement (finalise_at vide), ou un برنامج inachevé dont la
dernière دورة est déjà passée.

Chaque état est un dict {code, label, icone} ; `code` sert de suffixe à la
classe CSS `.etat-pastille--<code>` (scelle, cours, acheve, brouillon,
retard, annule).
"""
from datetime import date
import re

_ISO = re.compile(r'^(\d{4})-(\d{2})-(\d{2})$')


def _jour(valeur):
    """'YYYY-MM-DD' → date ; toute autre forme (vide, texte libre) → None.
    Une date illisible ne doit JAMAIS faire passer un dossier pour en retard."""
    m = _ISO.match((valeur or '').strip())
    if not m:
        return None
    try:
        return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    except ValueError:
        return None


def _etat(code, label, icone):
    return {'code': code, 'label': label, 'icone': icone}


def est_en_retard(date_formation, finalise, aujourdhui=None):
    """Vrai si la دورة est passée (strictement avant aujourd'hui) sans avoir
    été enregistrée définitivement. Le jour même n'est pas un retard."""
    if finalise:
        return False
    j = _jour(date_formation)
    return bool(j and j < (aujourdhui or date.today()))


def etat_dorra(d, aujourdhui=None):
    """État principal d'une دورة de l'écran « الإطلاع على البرامج »."""
    if d.get('finalise_at'):
        return _etat('acheve', 'مسجّلة نهائيًّا — مقفلة', '🔒')
    if est_en_retard(d.get('date_formation'), False, aujourdhui):
        return _etat('retard', 'متأخّرة — لم تُسجَّل نهائيًّا', '⚠️')
    return _etat('cours', 'في طور الإنجاز', '⏳')


def etat_finances(d):
    """État des المستحقّات d'une دورة déjà enregistrée ; None sinon (une دورة
    non finalisée n'entre pas encore dans les المستحقّات)."""
    if not d.get('finalise_at'):
        return None
    if (d.get('mu_etat') or '') == 'acheve':
        return _etat('acheve', 'المستحقّات منجزة', '💰')
    return _etat('brouillon', 'المستحقّات غير منجزة', '💰')


def etats_programme(pr, aujourdhui=None):
    """Pastilles d'un برنامج inachevé (écran « إستكمال برنامج تكوين »)."""
    out = []
    if not pr.get('verrouille'):
        out.append(_etat('brouillon', 'مسودّة غير مؤكَّدة', '📝'))
    else:
        n, total = int(pr.get('nb_finalisees') or 0), int(pr.get('nb_formations') or 0)
        out.append(_etat('scelle', 'مؤكَّد', '🔒'))
        out.append(_etat('cours', f'{n}/{total} دورة مسجّلة', '⏳'))
    if programme_en_retard(pr, aujourdhui):
        out.append(_etat('retard', 'متأخّر — دورة فات تاريخها دون تسجيل', '⚠️'))
    return out


def programme_en_retard(pr, aujourdhui=None):
    """Un برنامج inachevé est en retard dès que l'une de ses دورات NON encore
    enregistrées est passée (`date_ouverte` = la plus ancienne d'entre elles)."""
    return est_en_retard(pr.get('date_ouverte'), False, aujourdhui)
