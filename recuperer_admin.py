# -*- coding: utf-8 -*-
"""Récupération du compte مشرف عام (console).

Lancé par recuperer_admin.bat : depuis les sources (python recuperer_admin.py)
ou, programme construit, sous la forme RecupererAdmin.exe (1.0 — le programme
lui-même n'a plus de console). Voir core/recuperation.py.
"""
import os
import sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

from core import chemins, recuperation  # noqa: E402

if __name__ == '__main__':
    # data/ à côté de l'exécutable (figé) ou du projet (sources)
    sys.exit(recuperation.executer_console(chemins.chemin_base()))
