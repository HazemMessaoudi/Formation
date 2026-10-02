# -*- coding: utf-8 -*-
"""Phase 1 (v1.4) : aucune exception n'est plus avalée en silence.

Le comportement reste identique (mêmes valeurs de repli), mais l'échec est
désormais tracé dans le journal « formation.* » → data/logs/application.log."""
import logging
import os
import re

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RE_EXCEPT = re.compile(r'^\s*except[^:]*:\s*$')


def _fichiers():
    for dossier in ('core', 'routes'):
        for nom in sorted(os.listdir(os.path.join(BASE, dossier))):
            if nom.endswith('.py'):
                yield os.path.join(BASE, dossier, nom)


def test_aucun_print_dans_un_except():
    """Un print() sur un poste sans console est invisible : interdit dans un except."""
    fautes = []
    for chemin in _fichiers():
        lignes = open(chemin, encoding='utf-8').read().split('\n')
        for i, ln in enumerate(lignes[:-1]):
            if RE_EXCEPT.match(ln) and lignes[i + 1].strip().startswith('print('):
                fautes.append(f'{os.path.basename(chemin)}:{i + 2}')
    assert fautes == []


def test_echec_base_trace_mais_repli_identique(db, monkeypatch, caplog):
    """get_journal() renvoie toujours [] en cas d'échec… et l'échec est tracé."""
    class ConnCassee:
        def execute(self, *a, **k):
            raise RuntimeError('base illisible (test)')
        def close(self):
            pass
    monkeypatch.setattr(db, 'get_connection', lambda: ConnCassee())
    with caplog.at_level(logging.WARNING, logger='formation'):
        assert db.get_journal() == []
    assert any('get_journal' in r.getMessage() and r.exc_info for r in caplog.records)


def test_erreur_ecriture_tracee_avec_trace(db, monkeypatch, caplog):
    """Les anciens print(f'... error: {e}') deviennent des log.exception (trace incluse)."""
    class ConnCassee:
        def execute(self, *a, **k):
            raise RuntimeError('écriture impossible (test)')
        def commit(self):
            pass
        def rollback(self):
            pass
        def close(self):
            pass
    monkeypatch.setattr(db, 'get_connection', lambda: ConnCassee())
    with caplog.at_level(logging.ERROR, logger='formation'):
        db.update_madda(1, {'titre': 'x'})
    assert any(r.levelno == logging.ERROR and r.exc_info for r in caplog.records)


def test_journal_branche_sur_le_fichier():
    """app.py attache le fichier application.log au logger « formation »."""
    import app  # noqa: F401  — la configuration se fait à l'import
    handlers = logging.getLogger('formation').handlers
    assert any(getattr(h, 'baseFilename', '').endswith('application.log') for h in handlers)
