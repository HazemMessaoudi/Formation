# -*- coding: utf-8 -*-
"""Emplacements des fichiers — source unique (v1.7).

Deux dossiers distincts, qu'il ne faut jamais confondre :

* **les ressources** (gabarits, CSS/JS, polices, logos) : ce qui est LIVRÉ
  avec le programme. Une fois figé par PyInstaller, elles vivent dans le
  dossier d'extraction (`_internal/` en mode onedir, `sys._MEIPASS`).

* **les données** (base, sauvegardes, journaux, clé de session) : ce qui
  APPARTIENT AU CENTRE. Elles vivent TOUJOURS dans `data/` à côté de
  l'exécutable (ou du dossier du projet en mode Python), pour qu'une mise à
  jour — qui remplace `_internal/` — ne les touche jamais.

Avant la v1.7, la base suivait la seconde règle mais les journaux, la clé
et les PDF suivaient la première : ils atterrissaient dans `_internal/data`
et disparaissaient à chaque mise à jour. `migrer_ancien_emplacement()`
rapatrie ce qui peut l'être.

`FK_DATA_DIR` (variable d'environnement) redirige les données — utilisé par
les tests pour ne jamais écrire dans le vrai `data/` du projet.
"""

import glob
import logging as _logging
import os
import shutil
import sys
import tempfile

_log = _logging.getLogger('formation.' + __name__)

_RACINE_PROJET = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def est_fige():
    return bool(getattr(sys, 'frozen', False))


def dossier_application():
    """Dossier de l'exécutable (figé) ou du projet (Python)."""
    if est_fige():
        return os.path.dirname(os.path.abspath(sys.executable))
    return _RACINE_PROJET


def dossier_ressources():
    """Dossier des gabarits, statiques et polices livrés."""
    if est_fige():
        return getattr(sys, '_MEIPASS', dossier_application())
    return _RACINE_PROJET


def dossier_donnees():
    """`data/` du centre — créé au besoin."""
    d = os.environ.get('FK_DATA_DIR') or os.path.join(dossier_application(), 'data')
    os.makedirs(d, exist_ok=True)
    return d


def sous_dossier(nom):
    d = os.path.join(dossier_donnees(), nom)
    os.makedirs(d, exist_ok=True)
    return d


def chemin_base():
    return os.path.join(dossier_donnees(), 'formation.db')


# ─── PDF transitoires ────────────────────────────────────────────────────────
#
# ReportLab compose dans un fichier ; ce fichier ne vit que le temps d'une
# requête : il est relu en mémoire puis supprimé (routes : envoyer_pdf).
# Il est rangé sous data/tmp — jamais dans le %TEMP% de Windows — et le
# dossier est vidé à chaque démarrage (reliquats d'un arrêt brutal).

def dossier_pdf_transitoire():
    return sous_dossier('tmp')


def chemin_pdf_transitoire(prefixe):
    fd, chemin = tempfile.mkstemp(suffix='.pdf', prefix=f'{prefixe}_',
                                  dir=dossier_pdf_transitoire())
    os.close(fd)
    return chemin


def lire_et_supprimer(chemin):
    """Contenu binaire du fichier, puis suppression (silencieuse)."""
    with open(chemin, 'rb') as fh:
        data = fh.read()
    supprimer(chemin)
    return data


def supprimer(chemin):
    try:
        if chemin and os.path.isfile(chemin):
            os.remove(chemin)
    except OSError:
        _log.warning('suppression impossible : %s', chemin, exc_info=True)


def purger_fichiers_transitoires():
    """Démarrage : vide data/tmp, l'ancien data/pdfs (copies de مراسلات
    accumulées avant la v1.7) et les وثائق الخلاص laissées dans %TEMP% par
    les versions précédentes (elles portent CIN et RIB). Renvoie le nombre
    de fichiers supprimés."""
    n = 0
    cibles = glob.glob(os.path.join(dossier_pdf_transitoire(), '*.pdf'))
    cibles += glob.glob(os.path.join(dossier_donnees(), 'pdfs', '*.pdf'))
    cibles += glob.glob(os.path.join(tempfile.gettempdir(), 'khalas_*.pdf'))
    for f in cibles:
        try:
            os.remove(f)
            n += 1
        except OSError:
            _log.warning('purge impossible : %s', f, exc_info=True)
    return n


def migrer_ancien_emplacement():
    """Exécutable figé : rapatrie dans data/ ce que les versions antérieures
    rangeaient par erreur dans `_internal/data` (journaux, clé de session),
    et supprime leurs copies de PDF. Sans effet en mode Python. Renvoie la
    liste des éléments déplacés."""
    if not est_fige():
        return []
    ancien = os.path.join(dossier_ressources(), 'data')
    nouveau = dossier_donnees()
    if os.path.normcase(os.path.abspath(ancien)) == os.path.normcase(os.path.abspath(nouveau)):
        return []
    if not os.path.isdir(ancien):
        return []
    deplaces = []
    cle = os.path.join(ancien, 'secret_key')
    if os.path.isfile(cle) and not os.path.exists(os.path.join(nouveau, 'secret_key')):
        shutil.move(cle, os.path.join(nouveau, 'secret_key'))
        deplaces.append('secret_key')
    logs = os.path.join(ancien, 'logs')
    if os.path.isdir(logs):
        dest = sous_dossier('logs')
        for f in os.listdir(logs):
            src = os.path.join(logs, f)
            if not os.path.isfile(src) or f.startswith('.'):
                continue
            cible = os.path.join(dest, f if not os.path.exists(os.path.join(dest, f))
                                 else 'ancien_' + f)
            shutil.move(src, cible)
            deplaces.append('logs/' + f)
    shutil.rmtree(os.path.join(ancien, 'pdfs'), ignore_errors=True)
    return deplaces
