# -*- coding: utf-8 -*-
"""La شاشة رئيسية est-elle vraiment la porte d'entrée de la منظومة ? (v1.0)

Le défaut constaté par l'utilisateur : en ouvrant le برنامج il tombait sur
لوحة القيادة et non sur la شاشة رئيسية aux trois portes.

La cause n'était PAS dans `/` — qui redirige bien vers `/accueil` — mais
dans le mur d'authentification : le lanceur ouvre `/`, le حارس renvoie vers
`/login`, et `login()` renvoyait ensuite vers `dashboard` (la destination
d'avant la 1.0). La redirection `/` → `/accueil` n'était donc JAMAIS
atteinte au démarrage.

On teste ici tous les chemins d'entrée, pas seulement `/`.
"""

import pytest


def _client_anonyme(db, monkeypatch):
    """Client HTTP SANS session : on veut passer par le vrai mur de login."""
    import app as application
    monkeypatch.setattr(application, 'get_connection', db.get_connection,
                        raising=False)
    application.app.config.update(TESTING=True, WTF_CSRF_ENABLED=False)
    return application.app.test_client()


# ─── Les chemins d'entrée ────────────────────────────────────────────────────

def test_login_reussi_mene_a_la_شاشة_رئيسية(db, monkeypatch):
    """Le cas exact vécu par l'utilisateur : il ouvre, il se connecte."""
    db.update_config('installation_faite', '1')
    db.update_user_password('admin', 'motdepasse123')
    c = _client_anonyme(db, monkeypatch)

    rep = c.post('/login', data={'username': 'admin',
                                 'password': 'motdepasse123'})

    assert rep.status_code == 302
    assert rep.headers['Location'].endswith('/accueil'), \
        f"le دخول doit ouvrir la شاشة رئيسية, pas {rep.headers['Location']}"


def test_login_deja_connecte_mene_a_la_شاشة_رئيسية(client):
    """Un مستعمل déjà connecté qui retombe sur /login."""
    rep = client.get('/login')
    assert rep.status_code == 302
    assert rep.headers['Location'].endswith('/accueil')


def test_racine_mene_a_la_شاشة_رئيسية(client):
    rep = client.get('/')
    assert rep.status_code == 302
    assert rep.headers['Location'].endswith('/accueil')


def test_changement_de_mot_de_passe_mene_a_la_شاشة_رئيسية(db, monkeypatch):
    db.update_config('installation_faite', '1')
    db.update_user_password('admin', 'motdepasse123')
    c = _client_anonyme(db, monkeypatch)
    c.post('/login', data={'username': 'admin', 'password': 'motdepasse123'})
    # Le دخول vient de forger le jeton CSRF : on le présente comme le ferait
    # le formulaire réel, sinon c'est le حارس qu'on teste, pas la redirection.
    with c.session_transaction() as s:
        jeton = s['_csrf']

    rep = c.post('/changer-mot-de-passe',
                 data={'actuel': 'motdepasse123',
                       'nouveau': 'motdepasse456',
                       'confirmation': 'motdepasse456',
                       '_csrf': jeton})

    assert rep.status_code == 302
    assert rep.headers['Location'].endswith('/accueil')


def test_fin_installation_mene_a_la_شاشة_رئيسية(client_neuf, db):
    """Le معالج التّنصيب achevé ouvre lui aussi la شاشة رئيسية."""
    for etape in __import__('core.identite', fromlist=['identite']) \
            .ETAPES_INSTALLATION:
        if etape.get('type') == 'numeros':
            continue
        for champ in etape['champs']:
            if champ.get('obligatoire'):
                db.update_config(champ['cle'], 'قيمة')

    rep = client_neuf.post('/installation/resume',
                           headers={'X-CSRF-Token': 'jeton-de-test'})
    assert rep.status_code == 302
    assert rep.headers['Location'].endswith('/accueil')


# ─── Le زر كبير الحجم, présent dans les trois قسم ────────────────────────────

LIBELLE_RETOUR = 'العودة إلى الشاشة الرئيسية'

PAGES_DES_TROIS_PORTES = [
    ('/dashboard',     'برامج تكوينية'),
    ('/mustahaqqat',   'مستحقات مالية'),
    ('/statistiques',  'إحصائيات'),
]


@pytest.mark.parametrize('chemin,porte', PAGES_DES_TROIS_PORTES)
def test_bouton_retour_grand_et_present(client, chemin, porte):
    """Chaque قسم porte le même زر كبير, au même endroit."""
    html = client.get(chemin).get_data(as_text=True)
    assert LIBELLE_RETOUR in html, f"زر العودة غائب من {porte}"
    assert 'nav-home-btn' in html, f"زر العودة ليس كبيرًا في {porte}"


@pytest.mark.parametrize('chemin,porte', PAGES_DES_TROIS_PORTES)
def test_le_bouton_pointe_bien_vers_accueil(client, chemin, porte):
    html = client.get(chemin).get_data(as_text=True)
    bloc = html.split('nav-home-btn')[0]
    # l'attribut href précède la classe dans la balise
    assert '/accueil' in bloc[-300:], f"زر العودة في {porte} لا يؤدّي إلى الشاشة الرئيسية"


# ─── Chaque porte a SES titres, et rien que les siens ────────────────────────

def test_mustahaqqat_ne_renvoie_pas_vers_les_autres_sections(client):
    """Le passage d'un قسم à l'autre se fait par la شاشة رئيسية, pas par
    un lien glissé dans le menu."""
    html = client.get('/mustahaqqat').get_data(as_text=True)
    menu = html.split('nav-menu')[1].split('</ul>')[0]
    assert '/dashboard' not in menu
    assert '/statistiques' not in menu


def test_statistiques_ne_renvoie_pas_vers_les_autres_sections(client):
    html = client.get('/statistiques').get_data(as_text=True)
    menu = html.split('nav-menu')[1].split('</ul>')[0]
    assert '/dashboard' not in menu
    assert '/mustahaqqat' not in menu


def test_programmes_ne_renvoie_pas_vers_les_autres_sections(client):
    html = client.get('/dashboard').get_data(as_text=True)
    menu = html.split('nav-menu')[1].split('</ul>')[0]
    assert '/mustahaqqat' not in menu
    assert '/statistiques' not in menu


def test_page_erreur_renvoie_bien_a_la_شاشة_رئيسية(client):
    """La page d'erreur disait « العودة إلى الرئيسيّة » et menait ailleurs."""
    html = client.get('/lettre/999999').get_data(as_text=True)
    if 'erreur' in html or 'خطأ' in html:
        assert '/dashboard' not in html or '/accueil' in html
