# -*- coding: utf-8 -*-
"""Géométrie des graphiques en colonnes (v1.5 — D1, D2), rendus en SVG par
templates/_graphiques.html. Aucune bibliothèque : le poste peut être hors ligne.

Spécifications (skill dataviz) : une seule série → pas de légende (le titre la
nomme) ; colonnes ≤ 24 px, bout arrondi de 4 px, carrées à la ligne de base ;
graduations « rondes » ; chaque colonne non nulle est étiquetée (V3.0.1) ; zone de survol plus large que la colonne.
Sens de lecture arabe : le premier libellé (جانفي) est à DROITE.
"""
import math

LARGEUR, HAUTEUR = 640, 220
MARGE_HAUT, MARGE_BAS, MARGE_DROITE, MARGE_GAUCHE = 26, 30, 12, 44
COLONNE_MAX = 24
ARRONDI = 4


NB_GRADUATIONS = 4


def pas_rond(v, entier=False):
    """Plus petit pas « rond » (1, 2, 2.5, 5 × 10ⁿ) ≥ v. Pour des effectifs
    (entier=True), jamais de pas fractionnaire : 1 au minimum, et 2.5 n'est
    admis que s'il donne un entier (25, 250…)."""
    if v <= 0:
        return 1
    puissance = 10 ** math.floor(math.log10(v))
    for m in (1, 2, 2.5, 5, 10):
        p = m * puissance
        if p + 1e-12 >= v and (not entier or (p >= 1 and float(p).is_integer())):
            return int(p) if float(p).is_integer() else p
    return max(1, 10 * puissance)


def maximum_rond(v, entier=False):
    """Haut de l'axe : NB_GRADUATIONS pas ronds couvrant v (au moins 1 par pas
    pour des effectifs, pour qu'un graphique presque vide ne gonfle pas une
    unité en pleine hauteur)."""
    haut = NB_GRADUATIONS * pas_rond(max(v, 0) / NB_GRADUATIONS, entier)
    return int(haut) if float(haut).is_integer() else haut


def _chemin_colonne(x, y, l, h):
    """Colonne à bout supérieur arrondi, base carrée."""
    r = min(ARRONDI, l / 2, h)
    b = y + h
    return (f'M{x:.1f},{b:.1f} L{x:.1f},{y + r:.1f} Q{x:.1f},{y:.1f} {x + r:.1f},{y:.1f} '
            f'L{x + l - r:.1f},{y:.1f} Q{x + l:.1f},{y:.1f} {x + l:.1f},{y + r:.1f} '
            f'L{x + l:.1f},{b:.1f} Z')


def colonnes(libelles, valeurs, format_valeur=None, unite=''):
    """Rend {largeur, hauteur, colonnes[], graduations[], base_y, vide}."""
    fmt = format_valeur or (lambda v: f'{v:g}' if isinstance(v, float) else str(v))
    n = max(1, len(valeurs))
    entier = all(float(v or 0).is_integer() for v in valeurs) and format_valeur is None
    haut = maximum_rond(max([v or 0 for v in valeurs] + [0]), entier)
    zone_l = LARGEUR - MARGE_DROITE - MARGE_GAUCHE
    zone_h = HAUTEUR - MARGE_HAUT - MARGE_BAS
    bande = zone_l / n
    larg = min(COLONNE_MAX, bande * 0.62)
    base = MARGE_HAUT + zone_h
    vmax = max([v or 0 for v in valeurs] + [0])
    cols = []
    for i, (lib, v) in enumerate(zip(libelles, valeurs)):
        v = v or 0
        # droite → gauche : l'élément 0 occupe la bande la plus à droite
        x_bande = LARGEUR - MARGE_DROITE - (i + 1) * bande
        x = x_bande + (bande - larg) / 2
        h = (v / haut) * zone_h if haut else 0
        cols.append({
            'libelle': lib, 'valeur': v, 'texte': fmt(v),
            'x_bande': round(x_bande, 1), 'bande': round(bande, 1),
            'cx': round(x_bande + bande / 2, 1),
            'chemin': _chemin_colonne(x, base - h, larg, h) if h > 0 else '',
            'y_haut': round(base - h, 1),
            # V3.0.1 — chaque colonne non nulle porte sa valeur (plus seulement le maximum)
            'etiquette': v > 0,
            'infobulle': f'{lib}: {fmt(v)}{(" " + unite) if unite else ""}',
        })
    grads = []
    for k in range(NB_GRADUATIONS + 1):
        val = haut * k / NB_GRADUATIONS
        grads.append({'y': round(base - zone_h * k / NB_GRADUATIONS, 1),
                      'texte': fmt(int(val) if float(val).is_integer() else round(val, 1))})
    return {'largeur': LARGEUR, 'hauteur': HAUTEUR, 'colonnes': cols, 'graduations': grads,
            'base_y': base, 'x_gauche': MARGE_GAUCHE, 'x_droite': LARGEUR - MARGE_DROITE,
            'vide': vmax == 0}
