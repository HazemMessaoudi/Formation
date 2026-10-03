# -*- coding: utf-8 -*-
"""Fixtures communes : chaque test reçoit une base SQLite neuve et isolée."""
import os
import sys
import tempfile

import pytest

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)

# v1.7 : les tests n'écrivent JAMAIS dans le vrai data/ du projet (clé de
# session, journaux, PDF transitoires) — tout va dans un dossier jetable.
os.environ.setdefault('FK_DATA_DIR', tempfile.mkdtemp(prefix='fk_data_'))
# V3.1 : la نسخة المرآة non plus ne sort jamais du dossier jetable.
os.environ.setdefault('FK_MIROIR_DIR', tempfile.mkdtemp(prefix='fk_miroir_'))


@pytest.fixture()
def db(monkeypatch):
    """Base temporaire initialisée avec le schéma courant."""
    import core.database as database
    dossier = tempfile.mkdtemp(prefix='fk_test_')
    chemin = os.path.join(dossier, 'formation.db')
    monkeypatch.setattr(database, 'DB_PATH', chemin)
    database.init_db()
    yield database
    for f in os.listdir(dossier):
        try:
            os.remove(os.path.join(dossier, f))
        except OSError:
            pass


def _client_flask(db, monkeypatch, role='admin'):
    """Client de test authentifié, sans rien présumer de l'état d'installation."""
    import app as application
    monkeypatch.setattr(application, 'get_connection', db.get_connection, raising=False)
    application.app.config.update(TESTING=True, WTF_CSRF_ENABLED=False)
    # La session doit décrire un état RÉEL : le compte existe dans cette base,
    # son mot de passe initial est déjà changé, et la session porte l'identité
    # de la base (app._valider_session rejette tout cookie qui ne la porte pas).
    nom = 'admin' if role == 'admin' else 'agent'
    conn = db.get_connection()
    try:
        if not conn.execute('SELECT 1 FROM users WHERE username=?', (nom,)).fetchone():
            from werkzeug.security import generate_password_hash
            conn.execute('INSERT INTO users (username, password_hash, role) VALUES (?,?,?)',
                         (nom, generate_password_hash('secret123'), role))
        conn.execute('UPDATE users SET doit_changer_mdp=0 WHERE username=?', (nom,))
        conn.commit()
    finally:
        conn.close()
    c = application.app.test_client()
    with c.session_transaction() as s:
        s['username'] = nom
        s['role'] = role
        s['doit_changer_mdp'] = False
        s['_csrf'] = 'jeton-de-test'
        s['_instance'] = db.get_config().get('instance_id', '')
    return c


@pytest.fixture()
def client(db, monkeypatch):
    """Client HTTP Flask authentifié en tant que مشرف عام, منظومة déjà installée.

    Une base de test est neuve, donc `installation_faite='0'` : sans ce
    réglage le حارس de app.py renverrait TOUTES les pages vers le معالج
    et aucun test métier ne testerait plus ce qu'il croit tester."""
    db.update_config('installation_faite', '1')
    yield _client_flask(db, monkeypatch, 'admin')


@pytest.fixture()
def client_neuf(db, monkeypatch):
    """Client مشرف عام sur une منظومة qui n'a PAS encore été installée."""
    return _client_flask(db, monkeypatch, 'admin')


@pytest.fixture()
def client_neuf_simple(db, monkeypatch):
    """Client مستعمل عادي sur une منظومة non installée."""
    return _client_flask(db, monkeypatch, 'user')


@pytest.fixture()
def programme(db):
    """Un programme (lettre) avec une dorra, prêt à être manipulé."""
    lettre_id = db.save_programme(
        'interne', 'أكتوبر', 2026,
        [{'titre': 'تحرير المحاضر', 'grade': 'مقدم', 'nom_formateur': 'البوهلالي زياد',
          'lieu_travail': 'الإدارة الجهوية للديوانة بالقصرين',
          'date_formation': '2026-10-21', 'periode': '',
          'lieu_formation': 'مركز التكوين الجهوي بالقصرين'}],
        'حازم مسعودي', 'النقيب')
    detail = db.get_lettre_detail(lettre_id)
    return {'lettre_id': lettre_id,
            'formation_id': detail['formations'][0]['id']}


def js_programme():
    """v1.7 — le code de la page إعداد برنامج التكوين vit dans
    static/js/programme/*.js (chargés dans l'ordre 01 → 06). Les tests qui
    inspectent ce code lisent le gabarit ET ces fichiers."""
    import glob
    return '\n'.join(open(f, encoding='utf-8').read() for f in sorted(
        glob.glob(os.path.join(BASE_DIR, 'static', 'js', 'programme', '*.js'))))
