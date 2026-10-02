# -*- coding: utf-8 -*-
"""v1.7 — Paquet B : dossier de données unique, aucun PDF laissé sur le
disque, sauvegardes quotidiennes / étagées / externes, versions figées."""

import glob
import os
import sys
import tempfile
from datetime import datetime, timedelta

import pytest

from core import chemins

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
H = {'X-CSRF-Token': 'jeton-de-test'}


# ═══ 5. Dossier de données unique ═══════════════════════════════════════════

def test_les_tests_ecrivent_hors_du_vrai_data():
    assert os.environ.get('FK_DATA_DIR')
    assert os.path.abspath(chemins.dossier_donnees()) != os.path.join(BASE, 'data')


def test_executable_fige_donnees_a_cote_de_lexe(monkeypatch, tmp_path):
    exe_dir = tmp_path / 'FormationKasserine'
    interne = exe_dir / '_internal'
    interne.mkdir(parents=True)
    monkeypatch.delenv('FK_DATA_DIR', raising=False)
    monkeypatch.setattr(sys, 'frozen', True, raising=False)
    monkeypatch.setattr(sys, 'executable', str(exe_dir / 'FormationKasserine.exe'))
    monkeypatch.setattr(sys, '_MEIPASS', str(interne), raising=False)
    assert chemins.dossier_ressources() == str(interne)
    assert chemins.dossier_donnees() == str(exe_dir / 'data')
    assert chemins.chemin_base() == str(exe_dir / 'data' / 'formation.db')
    assert chemins.sous_dossier('logs') == str(exe_dir / 'data' / 'logs')


def test_migration_depuis_internal(monkeypatch, tmp_path):
    exe_dir = tmp_path / 'FK'
    ancien = exe_dir / '_internal' / 'data'
    (ancien / 'logs').mkdir(parents=True)
    (ancien / 'pdfs').mkdir()
    (ancien / 'secret_key').write_text('cle-ancienne')
    (ancien / 'logs' / 'application.log').write_text('trace')
    (ancien / 'pdfs' / 'lettre_x.pdf').write_bytes(b'%PDF')
    monkeypatch.delenv('FK_DATA_DIR', raising=False)
    monkeypatch.setattr(sys, 'frozen', True, raising=False)
    monkeypatch.setattr(sys, 'executable', str(exe_dir / 'FK.exe'))
    monkeypatch.setattr(sys, '_MEIPASS', str(exe_dir / '_internal'), raising=False)
    deplaces = chemins.migrer_ancien_emplacement()
    assert 'secret_key' in deplaces and 'logs/application.log' in deplaces
    assert (exe_dir / 'data' / 'secret_key').read_text() == 'cle-ancienne'
    assert (exe_dir / 'data' / 'logs' / 'application.log').read_text() == 'trace'
    assert not (ancien / 'pdfs').exists()
    assert chemins.migrer_ancien_emplacement() == []        # idempotent


def test_migration_sans_effet_en_mode_python():
    assert chemins.migrer_ancien_emplacement() == []


def test_journal_et_cle_dans_le_dossier_de_donnees():
    import app  # noqa: F401 — configure les journaux
    d = chemins.dossier_donnees()
    assert os.path.exists(os.path.join(d, 'secret_key'))
    assert os.path.isdir(os.path.join(d, 'logs'))


# ═══ 6. Aucun PDF ne reste sur le disque ════════════════════════════════════

def _pdfs_restants():
    return glob.glob(os.path.join(chemins.dossier_pdf_transitoire(), '*.pdf'))


def test_pdf_de_mourasla_envoye_puis_supprime(client, db, programme):
    for f in _pdfs_restants():
        os.remove(f)
    db.verrouiller_lettre(programme['lettre_id'], 'interne')
    r = client.get(f"/lettre/{programme['lettre_id']}/generer")
    assert r.status_code == 200 and r.data[:4] == b'%PDF'
    assert _pdfs_restants() == []


def test_generateurs_ecrivent_dans_data_tmp_et_non_data_pdfs():
    import core.pdf_generator as pg
    src = open(os.path.join(BASE, 'core', 'pdf_generator.py'), encoding='utf-8').read()
    assert "'data', 'pdfs'" not in src
    p = pg.generer_pdf_programme({'theme': 'ت', 'date_formation': '2026-10-21', 'rows': []}, BASE)
    assert os.path.dirname(p) == chemins.dossier_pdf_transitoire()
    os.remove(p)


def test_khalas_ne_passe_plus_par_le_temp_de_windows():
    src = open(os.path.join(BASE, 'core', 'pdf_khalas.py'), encoding='utf-8').read()
    assert 'tempfile.mkstemp' not in src and 'chemin_pdf_transitoire' in src


def test_purge_au_demarrage(tmp_path, monkeypatch):
    t = chemins.dossier_pdf_transitoire()
    open(os.path.join(t, 'reste.pdf'), 'wb').write(b'x')
    ancien = chemins.sous_dossier('pdfs')
    open(os.path.join(ancien, 'lettre_END.pdf'), 'wb').write(b'x')
    monkeypatch.setattr(tempfile, 'gettempdir', lambda: str(tmp_path))
    (tmp_path / 'khalas_abc.pdf').write_bytes(b'x')
    (tmp_path / 'autre.pdf').write_bytes(b'x')          # pas à nous : épargné
    assert chemins.purger_fichiers_transitoires() == 3
    assert (tmp_path / 'autre.pdf').exists()
    assert not os.listdir(t) or all(not f.endswith('.pdf') for f in os.listdir(t))


def test_lire_et_supprimer(tmp_path):
    f = tmp_path / 'a.pdf'
    f.write_bytes(b'%PDF-1')
    assert chemins.lire_et_supprimer(str(f)) == b'%PDF-1' and not f.exists()


# ═══ 7. Sauvegardes ═════════════════════════════════════════════════════════

def _nom(d):
    return f'/b/formation_{d:%Y%m%d_%H%M%S}.db'


def test_politique_etagee():
    from core.db.sauvegarde import a_conserver
    maintenant = datetime(2026, 9, 26, 22, 0, 0)
    fichiers = []
    for jours in range(0, 400):                     # une copie par jour sur 400 jours
        fichiers.append(_nom(maintenant - timedelta(days=jours, hours=1)))
    for k in range(8):                              # 8 démarrages aujourd'hui
        fichiers.append(_nom(maintenant - timedelta(minutes=10 * k)))
    garde = a_conserver(fichiers, maintenant)
    auj = [f for f in garde if '20260926_' in f]
    assert len(auj) == 5                            # 5 copies du jour
    jours = {f.split('_')[1] for f in garde}
    for j in range(7):                              # 7 derniers jours présents
        assert (maintenant - timedelta(days=j)).strftime('%Y%m%d') in jours
    mois = {f.split('_')[1][:6] for f in garde}
    assert len(mois) >= 12 and '202510' in mois
    assert not any(f.split('_')[1] < '20250901' for f in garde)   # > 12 mois : purgé
    assert len(garde) < 40


def test_politique_nom_illisible_garde():
    from core.db.sauvegarde import a_conserver
    assert '/b/formation_manuel.db' in a_conserver(['/b/formation_manuel.db'])


def test_backup_db_puis_purge(db):
    d = db.dossier_sauvegardes()
    vieux = os.path.join(d, 'formation_20200101_101010.db')
    open(vieux, 'wb').write(b'')
    chemin = db.backup_db()
    assert chemin and os.path.exists(chemin)
    assert not os.path.exists(vieux)             # hors fenêtre : purgé


def test_sauvegarde_quotidienne_une_seule_fois(db, monkeypatch):
    from core.db import sauvegarde
    for f in glob.glob(os.path.join(db.dossier_sauvegardes(), '*.db')):
        os.remove(f)
    sauvegarde._dernier_controle['jour'] = None
    assert db.sauvegarde_quotidienne_si_necessaire()
    assert db.sauvegarde_quotidienne_si_necessaire() is None       # même jour
    sauvegarde._dernier_controle['jour'] = None
    assert db.sauvegarde_quotidienne_si_necessaire() is None       # copie du jour existe


def test_copie_externe(db, tmp_path):
    cle = tmp_path / 'USB'
    cle.mkdir()
    chemin = db.copier_vers_externe(str(cle))
    assert os.path.exists(chemin) and db.DOSSIER_EXTERNE in chemin
    import sqlite3
    assert sqlite3.connect(chemin).execute('PRAGMA integrity_check').fetchone()[0] == 'ok'
    cfg = db.get_config()
    assert cfg['destination_sauvegarde_externe'] == str(cle)
    etat = db.etat_sauvegarde_externe(cfg)
    assert etat['jours'] == 0 and not etat['rappel']


def test_copie_externe_refusee(db, tmp_path):
    with pytest.raises(ValueError):
        db.copier_vers_externe('')
    with pytest.raises(ValueError):
        db.copier_vers_externe(str(tmp_path / 'absent'))
    with pytest.raises(ValueError):                       # dossier du programme
        db.copier_vers_externe(os.path.dirname(db.DB_PATH))


def test_rappel_externe():
    from core.db.sauvegarde import etat_sauvegarde_externe
    assert etat_sauvegarde_externe({})['rappel']
    il_y_a = (datetime.now() - timedelta(days=9)).strftime('%Y-%m-%d %H:%M')
    e = etat_sauvegarde_externe({'derniere_sauvegarde_externe': il_y_a})
    assert e['rappel'] and e['jours'] == 9


def test_route_copie_externe(db, client, tmp_path):
    cle = tmp_path / 'K'
    cle.mkdir()
    r = client.post('/parametres/sauvegarde/externe',
                    data={'_csrf': 'jeton-de-test', 'chemin': str(cle)})
    assert r.status_code == 302
    assert glob.glob(str(cle / db.DOSSIER_EXTERNE / 'formation_*.db'))
    assert any(j['action'] == 'نسخة احتياطيّة خارجيّة' for j in db.get_journal(5))


def test_route_copie_externe_reservee_au_mushrif(db, monkeypatch, tmp_path):
    from tests.conftest import _client_flask
    db.update_config('installation_faite', '1')
    c = _client_flask(db, monkeypatch, 'user')
    r = c.post('/parametres/sauvegarde/externe', data={'_csrf': 'jeton-de-test',
                                                     'chemin': str(tmp_path)})
    assert r.status_code == 403


def test_rappel_au_tableau_de_bord(db, client, monkeypatch):
    corps = client.get('/dashboard').data.decode('utf-8')
    assert 'لم تُؤخذ أيّ نسخة احتياطيّة خارجيّة بعد' in corps
    from tests.conftest import _client_flask
    c = _client_flask(db, monkeypatch, 'user')
    assert 'نسخة احتياطيّة خارجيّة' not in c.get('/dashboard').data.decode('utf-8')


def test_carte_securite_affiche_la_copie_externe(db, client):
    corps = client.get('/parametres').data.decode('utf-8')
    assert 'نسخ الآن' in corps and 'آخر 5 نسخ من اليوم' in corps


# ═══ 11. Versions figées ════════════════════════════════════════════════════

def test_versions_figees_et_utilisees():
    lock = open(os.path.join(BASE, 'requirements-lock.txt'), encoding='utf-8').read()
    for paquet in ('Flask==', 'waitress==', 'reportlab==', 'python-bidi==',
                   'arabic-reshaper==', 'openpyxl==', 'xlrd==', 'pillow=='):
        assert paquet in lock
    for bat in ('construire_exe.bat', 'lancer.bat'):
        assert 'requirements-lock.txt' in open(os.path.join(BASE, bat), encoding='utf-8').read()
