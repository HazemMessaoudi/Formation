# -*- coding: utf-8 -*-
"""Recherche unifiée (v1.5 — D4) : أسماء، مواد التكوين، دورات، مراسلات.

La comparaison se fait sur une forme normalisée (sans حركات ni تطويل, hamzas
et ى/ة unifiées, minuscules) ; TOUS les mots de la requête doivent figurer
dans la fiche (ET logique), dans n'importe quel ordre. Rien n'est écrit en
base : la recherche ne fait que lire.
"""
import re
import unicodedata

from core.db._base import get_connection

_DIACRITIQUES = re.compile(r'[ً-ْٰـ]')
LIMITE_PAR_GROUPE = 6


def normaliser(texte):
    t = unicodedata.normalize('NFKC', str(texte or ''))
    t = _DIACRITIQUES.sub('', t)
    t = (t.replace('أ', 'ا').replace('إ', 'ا').replace('آ', 'ا').replace('ٱ', 'ا')
          .replace('ى', 'ي').replace('ة', 'ه').replace('ؤ', 'و').replace('ئ', 'ي'))
    return re.sub(r'\s+', ' ', t).strip().lower()


def _correspond(mots, *champs):
    cible = normaliser(' '.join(str(c or '') for c in champs))
    return all(m in cible for m in mots)


def rechercher(q, limite=LIMITE_PAR_GROUPE):
    """Rend [{groupe, icone, resultats:[{titre, sous_titre, cible:(endpoint, args)}]}]."""
    mots = [m for m in normaliser(q).split(' ') if m]
    if not mots or len(''.join(mots)) < 2:
        return []
    conn = get_connection()
    try:
        groupes = []

        res = []
        for r in conn.execute('SELECT id, grade, nom, prenom, identifiant_unique, cin, lieu_travail, '
                              'administration FROM mkowin ORDER BY nom, prenom'):
            if _correspond(mots, r['nom'], r['prenom'], r['grade'], r['identifiant_unique'],
                           r['cin'], r['lieu_travail'], r['administration']):
                res.append({'titre': f"{r['nom'] or ''} {r['prenom'] or ''}".strip(),
                            'sous_titre': ' · '.join(x for x in (r['grade'], r['lieu_travail'],
                                                                 r['identifiant_unique']) if x),
                            'cible': ('fiche_mkow', {'mkow_id': r['id']})})
                if len(res) >= limite:
                    break
        groupes.append({'groupe': 'الأسماء', 'icone': '👤', 'resultats': res})

        res = []
        for r in conn.execute('SELECT id, titre, type_formation FROM mawad ORDER BY titre'):
            if _correspond(mots, r['titre'], r['type_formation']):
                res.append({'titre': r['titre'], 'sous_titre': r['type_formation'] or '',
                            'cible': ('fiche_madda', {'madda_id': r['id']})})
                if len(res) >= limite:
                    break
        groupes.append({'groupe': 'مواد التكوين', 'icone': '📚', 'resultats': res})

        res = []
        for r in conn.execute('''
                SELECT f.id, f.lettre_id, f.titre, f.grade, f.nom_formateur, f.date_formation,
                       f.lieu_formation, l.ref_complet, l.mois, l.annee, l.verrouille
                FROM formations f JOIN lettres l ON l.id = f.lettre_id
                WHERE (l.categorie = 'programme' OR l.categorie IS NULL)
                ORDER BY f.date_formation DESC, f.id DESC'''):
            if _correspond(mots, r['titre'], r['nom_formateur'], r['grade'], r['date_formation'],
                           r['lieu_formation'], r['ref_complet'], r['mois'], r['annee']):
                cible = (('detail_lettre', {'lettre_id': r['lettre_id']}) if r['verrouille']
                         else ('nouvelle_lettre', {'modifier': r['lettre_id']}))
                res.append({'titre': r['titre'] or '—',
                            'sous_titre': ' · '.join(x for x in (
                                r['date_formation'], f"{r['grade'] or ''} {r['nom_formateur'] or ''}".strip(),
                                r['ref_complet'] or 'مسودّة') if x),
                            'cible': cible})
                if len(res) >= limite:
                    break
        groupes.append({'groupe': 'الدورات', 'icone': '📋', 'resultats': res})

        res = []
        for r in conn.execute('''SELECT type, numero, ref_complet, objet, source, source_id, annee
                                 FROM registre ORDER BY annee DESC, numero DESC'''):
            if _correspond(mots, r['ref_complet'], r['objet'], r['numero']):
                cible = (('detail_lettre', {'lettre_id': r['source_id']})
                         if r['source'] in ('programme', 'libre', 'directeur') and r['source_id']
                         else ('registre_lettres', {'type_lettre': r['type'], 'annee': r['annee']}))
                res.append({'titre': r['ref_complet'],
                            'sous_titre': ('داخلية' if r['type'] == 'interne' else 'خارجية')
                                          + (' · ' + r['objet'] if r['objet'] else ''),
                            'cible': cible})
                if len(res) >= limite:
                    break
        groupes.append({'groupe': 'المراسلات', 'icone': '✉️', 'resultats': res})
    finally:
        conn.close()
    return [g for g in groupes if g['resultats']]
