# -*- coding: utf-8 -*-
"""Phase 5 (v1.4) : core/database.py est une façade sur core/db/<domaine>.py.

Garanties vérifiées :
- tout nom historique reste importable depuis core.database ;
- remplacer core.database.DB_PATH / get_connection (tests, outils) agit sur
  les fonctions de TOUS les sous-modules ;
- aucun sous-module n'importe la façade au chargement (pas de cycle)."""
import ast
import os

import pytest

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOSSIER_DB = os.path.join(BASE, 'core', 'db')
MODULES = sorted(f[:-3] for f in os.listdir(DOSSIER_DB)
                 if f.endswith('.py') and not f.startswith('__'))


def test_modules_attendus():
    assert set(MODULES) == {'_base', 'sauvegarde', 'registre', 'referentiels', 'mkowin',
                            'mawad', 'programmes', 'utilisateurs', 'mustahaqqat',
                            'statistiques', 'khalas', 'schema', 'rapports', 'suggestions'}


def test_facade_legere():
    n = open(os.path.join(BASE, 'core', 'database.py'), encoding='utf-8').read().count('\n')
    assert n < 150


@pytest.mark.parametrize('mod', MODULES)
def test_pas_d_import_de_la_facade_au_chargement(mod):
    arbre = ast.parse(open(os.path.join(DOSSIER_DB, mod + '.py'), encoding='utf-8').read())
    for n in arbre.body:
        if isinstance(n, ast.ImportFrom):
            assert n.module != 'core.database' and not (n.module == 'core' and any(
                a.name == 'database' for a in n.names)), mod
        if isinstance(n, ast.Import):
            assert all(a.name != 'core.database' for a in n.names), mod


def test_tous_les_noms_publics_reexportes():
    import importlib
    import core.database as facade
    for mod in MODULES:
        if mod == '_base':
            continue
        m = importlib.import_module(f'core.db.{mod}')
        arbre = ast.parse(open(os.path.join(DOSSIER_DB, mod + '.py'), encoding='utf-8').read())
        definis = {n.name for n in arbre.body if isinstance(n, (ast.FunctionDef, ast.ClassDef))}
        definis |= {t.id for n in arbre.body if isinstance(n, ast.Assign) for t in n.targets
                    if isinstance(t, ast.Name)}
        for nom in definis:
            assert getattr(facade, nom) is getattr(m, nom), f'{mod}.{nom}'


def test_db_path_remplace_agit_partout(db):
    """La fixture `db` remplace core.database.DB_PATH : chaque domaine doit
    écrire/lire dans CETTE base temporaire."""
    import sqlite3
    db.add_mkow({'nom': 'اختبار', 'prenom': 'الواجهة', 'grade': 'عريف'})     # mkowin
    db.add_lieu('قاعة الاختبار')                                           # referentiels
    db.journaliser('test', 'façade')                                      # utilisateurs
    c = sqlite3.connect(db.DB_PATH)
    assert c.execute("SELECT COUNT(*) FROM mkowin WHERE nom='اختبار'").fetchone()[0] == 1
    assert c.execute("SELECT COUNT(*) FROM lieux WHERE nom='قاعة الاختبار'").fetchone()[0] == 1
    assert c.execute("SELECT COUNT(*) FROM journal WHERE action='façade'").fetchone()[0] == 1
    c.close()
    assert db.backup_db() is not None                                     # sauvegarde
    assert os.path.dirname(db.backup_db()).startswith(os.path.dirname(db.DB_PATH))


def test_get_connection_remplace_agit_partout(db, monkeypatch):
    appels = []
    vrai = db.get_connection

    def espion():
        appels.append(1)
        return vrai()
    monkeypatch.setattr(db, 'get_connection', espion)
    db.get_mkowin(); db.get_lieux(); db.get_users(); db.get_bareme_grades()
    db.get_khalas_settings(); db.get_stats()
    assert len(appels) >= 6
