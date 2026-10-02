# -*- coding: utf-8 -*-
"""Contrôle strict des numéros d'identité (v1.6 — حزمة ب).

  • رقم بطاقة التعريف الوطنية (cin)     : exactement 8 chiffres ;
  • الحساب البنكي أو البريدي (num_compte) : exactement 20 chiffres.

Les deux خانات restent FACULTATIVES : une خانة vide est acceptée. Mais une
خانة remplie doit avoir la bonne longueur, sinon l'enregistrement est refusé
avec un message arabe. Avant le contrôle, la saisie est normalisée : chiffres
arabes-indiens (٠١٢…) convertis, espaces, points, tirets et barres retirés —
« 07 010 0001234567890 12 » est donc un RIB valide, stocké sans séparateurs.
"""
import re

_CHIFFRES_AR = str.maketrans('٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹', '01234567890123456789')
_SEPARATEURS = re.compile(r'[\s.\-/_]+')

#: champ → (longueur exigée, libellé arabe)
LONGUEURS = {
    'cin':        (8,  'رقم بطاقة التعريف الوطنية'),
    'num_compte': (20, 'رقم الحساب البنكي أو البريدي'),
}


def normaliser(valeur):
    """Forme compacte d'une saisie : chiffres occidentaux, sans séparateurs."""
    if valeur is None:
        return ''
    t = str(valeur).translate(_CHIFFRES_AR)
    return _SEPARATEURS.sub('', t).strip().strip('"\'«»')


def message(champ):
    n, lib = LONGUEURS[champ]
    return f'{lib} يجب أن يتكوّن من {n} أرقام بالضبط' if n <= 10 else \
           f'{lib} يجب أن يتكوّن من {n} رقمًا بالضبط'


def erreur_champ(champ, valeur):
    """Message d'erreur arabe, ou None si la valeur est vide ou conforme."""
    v = normaliser(valeur)
    if not v:
        return None
    n = LONGUEURS[champ][0]
    if not v.isdigit() or len(v) != n:
        return message(champ)
    return None


def verifier_identite(data):
    """Normalise EN PLACE cin / num_compte présents dans `data` et rend la
    liste des erreurs (vide si tout est conforme). Seules les clés présentes
    sont touchées : une خانة non soumise n'est ni contrôlée ni écrite."""
    erreurs = []
    for champ in LONGUEURS:
        if champ not in data:
            continue
        err = erreur_champ(champ, data[champ])
        if err:
            erreurs.append(err)
        else:
            data[champ] = normaliser(data[champ])
    return erreurs


# ─── v1.6 — حزمة ج : الجنس et الفئة العمريّة ─────────────────────────────────
#
# Deux listes FERMÉES, utilisées seulement par les إحصائيات (aucun document
# ne les imprime). Vide = « غير محدّد » : toujours accepté. Toute autre valeur
# est refusée — une faute de frappe fausserait les comptes sans bruit.

SEXES = ('ذكر', 'أنثى')
FIAAT = ('أقلّ من 40 سنة', '40 سنة وأكثر')

#: champ → (valeurs admises, message arabe)
CHOIX = {
    'sexe':       (SEXES, 'قيمة الجنس غير صالحة : ذكر أو أنثى فقط'),
    'fiaa_omria': (FIAAT, 'قيمة الفئة العمريّة غير صالحة : «أقلّ من 40 سنة» أو «40 سنة وأكثر» فقط'),
}


def erreur_choix(champ, valeur):
    """Message arabe si `valeur` (non vide) n'est pas dans la liste fermée."""
    v = (valeur or '').strip() if isinstance(valeur, str) else ('' if valeur is None else str(valeur).strip())
    if not v:
        return None
    return None if v in CHOIX[champ][0] else CHOIX[champ][1]


def verifier_choix(data):
    """Nettoie EN PLACE sexe / fiaa_omria présents dans `data` (espaces
    retirés) et rend la liste des erreurs. Clés absentes : non touchées."""
    erreurs = []
    for champ in CHOIX:
        if champ not in data:
            continue
        err = erreur_choix(champ, data[champ])
        if err:
            erreurs.append(err)
        else:
            data[champ] = (data[champ] or '').strip() if isinstance(data[champ], str) else ''
    return erreurs
