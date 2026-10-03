# -*- coding: utf-8 -*-
"""L'ordre du premier démarrage : دخول ← تغيير كلمة المرور ← تنصيب.

Incident constaté en v1.4c : la منظومة neuve s'ouvrait DIRECTEMENT sur le
معالج التّنصيب. Cause : le paquet livré contenait `data/secret_key` ; un cookie
de session resté dans le navigateur (signé par la même clé lors d'essais
précédents) passait pour une connexion valide, avec le mot de passe réputé
déjà changé. Ces tests verrouillent les deux protections ajoutées.
"""
import os
import zipfile

import pytest


@pytest.fixture()
def app_neuve(db, monkeypatch):
    """Une منظومة neuve, jamais installée, compte admin au mot de passe initial."""
    import app as application
    monkeypatch.setattr(application, 'get_connection', db.get_connection, raising=False)
    application.app.config.update(TESTING=True)
    return application.app


def _cookie_d_une_autre_base(c):
    """Le cookie tel qu'il restait dans le navigateur : admin, mdp « changé »,
    mais émis pour une AUTRE base."""
    with c.session_transaction() as s:
        s['username'] = 'admin'
        s['role'] = 'admin'
        s['doit_changer_mdp'] = False
        s['_csrf'] = 'x'
        s['_instance'] = 'identite-d-une-autre-base'


def test_un_vieux_cookie_ne_mene_plus_au_معالج(app_neuve):
    c = app_neuve.test_client()
    _cookie_d_une_autre_base(c)
    for chemin in ('/', '/accueil', '/installation', '/installation/1'):
        r = c.get(chemin)
        assert r.status_code == 302, chemin
        assert r.headers['Location'].endswith('/login'), (
            f'{chemin} → {r.headers["Location"]} : le vieux cookie ouvre encore la منظومة')


def test_un_cookie_sans_identite_de_base_est_rejete(app_neuve):
    """Les cookies émis AVANT ce correctif ne portent pas d'identité du tout."""
    c = app_neuve.test_client()
    with c.session_transaction() as s:
        s['username'] = 'admin'
        s['role'] = 'admin'
        s['doit_changer_mdp'] = False
    r = c.get('/installation/1')
    assert r.headers['Location'].endswith('/login')


def test_la_session_d_un_compte_supprime_est_rejetee(db, app_neuve):
    c = app_neuve.test_client()
    with c.session_transaction() as s:
        s['username'] = 'fantome'
        s['role'] = 'admin'
        s['_instance'] = db.get_config()['instance_id']
    assert c.get('/accueil').headers['Location'].endswith('/login')


def test_l_ordre_complet_du_premier_demarrage(db, app_neuve):
    """دخول ← تغيير كلمة المرور ← تنصيب, sans raccourci possible."""
    c = app_neuve.test_client()

    # 0. rien d'ouvert sans connexion
    assert c.get('/installation/1').headers['Location'].endswith('/login')

    # 1. connexion avec le mot de passe initial → changement obligatoire
    r = c.post('/login', data={'username': 'admin', 'password': 'admin'})
    assert r.headers['Location'].endswith('/changer-mot-de-passe')

    # 2. le معالج reste fermé tant que le mot de passe n'est pas changé
    r = c.get('/installation/1')
    assert r.headers['Location'].endswith('/changer-mot-de-passe'), (
        'le معالج s\'ouvre avant le changement du mot de passe')

    # 3. changement → seulement alors le معالج
    with c.session_transaction() as s:
        jeton = s['_csrf']
    r = c.post('/changer-mot-de-passe', data={
        'actuel': 'admin', 'nouveau': 'motdepasse9', 'confirmation': 'motdepasse9',
        '_csrf': jeton})
    assert r.status_code == 302
    r = c.get('/accueil')
    assert r.headers['Location'].endswith('/installation')
    assert c.get('/installation/1').status_code == 200


def test_l_obligation_de_changer_se_relit_en_base(db, app_neuve):
    """Un cookie qui dit « déjà changé » ne lève pas l'obligation inscrite en base."""
    c = app_neuve.test_client()
    with c.session_transaction() as s:
        s['username'] = 'admin'
        s['role'] = 'admin'
        s['doit_changer_mdp'] = False                       # mensonge du cookie
        s['_instance'] = db.get_config()['instance_id']     # mais bonne base
    r = c.get('/installation/1')
    assert r.headers['Location'].endswith('/changer-mot-de-passe')


def test_chaque_base_a_sa_propre_identite(db):
    ident = db.get_config().get('instance_id', '')
    assert len(ident) == 32
    db.init_db()                                   # une mise à jour ne la change pas
    assert db.get_config()['instance_id'] == ident


def test_le_paquet_ne_livre_jamais_de_cle_de_session():
    """`data/secret_key` est propre à CHAQUE poste : il ne doit pas voyager.

    Le script de livraison l'exclut ; ce test vérifie qu'il est bien listé dans
    les exclusions, pour qu'une livraison future ne le réintroduise pas."""
    racine = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    with open(os.path.join(racine, '.livraison_exclure'), encoding='utf-8') as f:
        exclus = f.read()
    assert 'data/secret_key' in exclus
    assert 'data/*.db' in exclus
