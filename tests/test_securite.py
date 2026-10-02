# -*- coding: utf-8 -*-
"""Authentification, protection CSRF et cloisonnement des rôles."""
import json


def test_pages_protegees_redirigent_vers_login(db):
    import app as application
    application.app.config.update(TESTING=True)
    with application.app.test_client() as anonyme:
        for chemin in ('/dashboard', '/lettre/nouvelle', '/mkowin', '/journal'):
            r = anonyme.get(chemin)
            assert r.status_code in (301, 302), f"{chemin} doit exiger une session"
            assert '/login' in r.headers.get('Location', '')


def test_post_sans_jeton_csrf_est_rejete(client, programme):
    r = client.post(f"/lettre/{programme['lettre_id']}/annuler",
                    headers={'Content-Type': 'application/json'}, data='{}')
    assert r.status_code == 400, "une requête sans jeton CSRF doit être refusée"


def test_post_avec_jeton_csrf_est_accepte(client, programme):
    r = client.post(f"/lettre/{programme['lettre_id']}/annuler",
                    headers={'Content-Type': 'application/json',
                             'X-CSRF-Token': 'jeton-de-test'},
                    data='{}')
    assert r.status_code == 200
    assert json.loads(r.data)['succes'] is True


def test_jeton_csrf_errone_est_rejete(client, programme):
    r = client.post(f"/lettre/{programme['lettre_id']}/annuler",
                    headers={'Content-Type': 'application/json',
                             'X-CSRF-Token': 'mauvais-jeton'},
                    data='{}')
    assert r.status_code == 400


def test_gestion_des_utilisateurs_reservee_a_l_admin(db, monkeypatch):
    """Un simple مستعمل ne peut pas créer ni supprimer de comptes."""
    from tests.conftest import _client_flask
    db.update_config('installation_faite', '1')   # sinon le حارس répond avant le contrôle de rôle
    c = _client_flask(db, monkeypatch, 'user')    # compte réel, session valide
    with c:
        r = c.post('/api/users',
                   headers={'Content-Type': 'application/json',
                            'X-CSRF-Token': 'jeton-de-test'},
                   data=json.dumps({'username': 'x', 'password': 'secret123'}))
        assert r.status_code == 403

        r = c.get('/journal')
        assert r.status_code == 403


def test_roles_et_journal(db):
    db.add_user('agent', 'motdepasse', role='user')
    assert db.get_user_role('agent') == 'user'
    db.set_user_role('agent', 'admin')
    assert db.get_user_role('agent') == 'admin'

    db.journaliser('agent', 'تأكيد وإغلاق برنامج تكوين', 'مراسلة #1', 'END-3-01-02-26-0001')
    entrees = db.get_journal()
    assert entrees and entrees[0]['utilisateur'] == 'agent'
    assert entrees[0]['action'] == 'تأكيد وإغلاق برنامج تكوين'


def test_mot_de_passe_par_defaut_impose_un_changement(db):
    """Le compte admin livré avec « admin/admin » est marqué à changer."""
    assert db.user_doit_changer_mdp('admin') is True
    db.update_user_password('admin', 'nouveau-mot-de-passe')
    assert db.user_doit_changer_mdp('admin') is False
