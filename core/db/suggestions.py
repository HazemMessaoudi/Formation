# -*- coding: utf-8 -*-
"""v1.7.1 — Suggestions de saisie du برنامج الدورة.

Chaque بيان النشاط et chaque متدخّل confirmés dans un برنامج sont mémorisés
(table `programme_suggestions`) pour être proposés la fois suivante :
les plus utilisés d'abord, puis les plus récents.

Les متدخّلون d'une فقرة sont stockés dans la ligne du برنامج en un seul
texte séparé par « ، » (SEPARATEUR) : c'est ce texte que les documents PDF
et Word impriment, sans aucun changement de leur mise en page.
"""
from core.db._base import _log, get_connection

SEPARATEUR = '، '
LONGUEUR_MAX = 300
NATURES = ('activite', 'intervenant')


def decouper_intervenants(texte):
    """« أ، ب / ج » → ['أ', 'ب', 'ج'] (séparateurs acceptés : ، , / ; retour)."""
    import re
    morceaux = re.split(r'[،,;/\n]+', str(texte or ''))
    vus, res = set(), []
    for m in morceaux:
        m = ' '.join(m.split())
        if m and m not in vus:
            vus.add(m)
            res.append(m)
    return res


def _noter(conn, nature, texte):
    texte = ' '.join(str(texte or '').split())[:LONGUEUR_MAX]
    if not texte or nature not in NATURES:
        return
    conn.execute(
        "INSERT INTO programme_suggestions (nature, texte) VALUES (?, ?) "
        "ON CONFLICT(nature, texte) DO UPDATE SET usages = usages + 1, "
        "dernier_usage = CURRENT_TIMESTAMP", (nature, texte))


def memoriser_lignes(conn, lignes):
    """Mémorise les بيان النشاط / المتدخّلون de lignes de برنامج (connexion
    fournie, pas de commit : l'appelant décide)."""
    for r in lignes or []:
        if not isinstance(r, dict) or r.get('type', 'row') == 'date_header':
            continue
        _noter(conn, 'activite', r.get('activity'))
        for nom in decouper_intervenants(r.get('participants')):
            _noter(conn, 'intervenant', nom)


def memoriser_programme(lignes):
    """Version autonome (ouvre et valide sa propre connexion)."""
    conn = get_connection()
    try:
        memoriser_lignes(conn, lignes)
        conn.commit()
    except Exception:
        _log.exception('memoriser_programme')
    finally:
        conn.close()


def suggestions_programme(nature, limite=300):
    """Textes mémorisés d'une nature, les plus utilisés puis les plus récents."""
    if nature not in NATURES:
        return []
    conn = get_connection()
    try:
        return [r[0] for r in conn.execute(
            "SELECT texte FROM programme_suggestions WHERE nature=? "
            "ORDER BY usages DESC, dernier_usage DESC, texte LIMIT ?",
            (nature, int(limite)))]
    except Exception:
        _log.exception('suggestions_programme')
        return []
    finally:
        conn.close()
