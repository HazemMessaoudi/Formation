# -*- coding: utf-8 -*-
"""Socle commun des modules core/db/*.

La connexion et le chemin de la base restent définis dans la façade
core/database.py. Les modules les obtiennent ICI, au moment de l'appel : un
remplacement à chaud de core.database.DB_PATH ou core.database.get_connection
(tests, outils) s'applique donc à toutes les fonctions, où qu'elles vivent.
"""
import logging as _logging
import sys

# Même nom de journal qu'avant la scission : les traces restent regroupées.
_log = _logging.getLogger('formation.core.database')


def _facade():
    return sys.modules['core.database']


def get_connection():
    return _facade().get_connection()
