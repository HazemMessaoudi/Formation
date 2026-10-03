# -*- coding: utf-8 -*-
"""v1.7 — Paquet E : qualité technique (code mort, index, isolation des
tests, points d'entrée JSON couverts, échappement HTML)."""

import os
import re
import subprocess
import sys

import pytest

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
H = {'X-CSRF-Token': 'jeton-de-test'}


# ═══ 12. Code mort ══════════════════════════════════════════════════════════

def test_aucun_import_ni_variable_morts():
    """pyflakes : plus aucun avertissement, hors façade core/database.py dont
    les ré-exportations sont voulues (compatibilité des appelants)."""
    pytest.importorskip('pyflakes')
    fichiers = [os.path.join(BASE, 'app.py'), os.path.join(BASE, 'lancer_app.py'),
                os.path.join(BASE, 'recuperer_admin.py')]
    for d in ('core', 'routes'):
        for racine, _dirs, noms in os.walk(os.path.join(BASE, d)):
            fichiers += [os.path.join(racine, n) for n in noms
                         if n.endswith('.py') and n != 'database.py']
    r = subprocess.run([sys.executable, '-m', 'pyflakes'] + fichiers,
                       capture_output=True, text=True)
    assert r.stdout.strip() == '', r.stdout


# ═══ 12. Index ══════════════════════════════════════════════════════════════

def test_index_des_jointures(db):
    conn = db.get_connection()
    try:
        noms = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='index'")}
        plan = ' '.join(str(tuple(r)) for r in conn.execute(
            'EXPLAIN QUERY PLAN SELECT * FROM participants WHERE formation_id=1'))
    finally:
        conn.close()
    assert {'idx_formations_lettre', 'idx_participants_formation',
            'idx_participants_lettre_formation'} <= noms
    assert 'idx_participants' in plan


# ═══ 12. Isolation des tests ════════════════════════════════════════════════

def test_les_tests_ne_touchent_pas_au_data_du_projet(client, db, programme):
    avant = set()
    for racine, _d, noms in os.walk(os.path.join(BASE, 'data')):
        avant |= {os.path.join(racine, n) for n in noms}
    db.verrouiller_lettre(programme['lettre_id'], 'interne')
    client.get(f"/lettre/{programme['lettre_id']}/generer")
    apres = set()
    for racine, _d, noms in os.walk(os.path.join(BASE, 'data')):
        apres |= {os.path.join(racine, n) for n in noms}
    assert apres == avant


# ═══ 12. Points d'entrée JSON (routes/api.py) ═══════════════════════════════

def test_api_grades(client, db):
    assert 'النقيب' in client.get('/api/grades').get_json()
    assert client.post('/api/grades', headers=H, json={'nom': ''}).status_code == 400
    assert client.post('/api/grades', headers=H, json={'nom': 'رتبة تجريبية'}).get_json()['succes']
    assert 'رتبة تجريبية' in db.get_grades()
    assert client.post('/api/grades/supprimer', headers=H, json={'nom': ''}).status_code == 400
    assert client.post('/api/grades/supprimer', headers=H,
                       json={'nom': 'رتبة تجريبية'}).get_json()['succes']
    assert 'رتبة تجريبية' not in db.get_grades()


def test_api_lieux(client, db):
    assert client.post('/api/lieux', headers=H, json={'nom': ''}).status_code == 400
    assert client.post('/api/lieux', headers=H, json={'nom': 'قاعة تجريبية'}).get_json()['succes']
    assert 'قاعة تجريبية' in client.get('/api/lieux').get_json()
    client.post('/api/lieux/supprimer', headers=H, json={'nom': 'قاعة تجريبية'})
    assert 'قاعة تجريبية' not in client.get('/api/lieux').get_json()


def test_api_utilisateurs_liste_sans_mot_de_passe(client, db):
    comptes = client.get('/api/users').get_json()
    assert comptes and all('password_hash' not in c for c in comptes)


def test_api_ajout_utilisateur_controles(client, db):
    assert client.post('/api/users', headers=H, json={'username': '', 'password': 'x'}
                       ).status_code == 400
    assert client.post('/api/users', headers=H, json={'username': 'u1', 'password': '123'}
                       ).status_code == 400
    assert client.post('/api/users', headers=H, json={'username': 'u1', 'password': '123456'}
                       ).get_json()['succes']
    assert client.post('/api/users', headers=H, json={'username': 'u1', 'password': '123456'}
                       ).status_code == 400                        # doublon
    assert db.get_user_role('u1') == 'user'


def test_api_changer_mdp_controles(client, db):
    db.add_user('u2', 'secret123')
    assert client.post('/api/users/changer-mdp', headers=H, json={}).status_code == 400
    assert client.post('/api/users/changer-mdp', headers=H,
                       json={'username': 'u2', 'new_password': '12'}).status_code == 400
    assert client.post('/api/users/changer-mdp', headers=H,
                       json={'username': 'fantome', 'new_password': '123456'}).status_code == 404
    assert client.post('/api/users/changer-mdp', headers=H,
                       json={'username': 'u2', 'new_password': 'neuf1234'}).get_json()['succes']
    assert db.check_credentials('u2', 'neuf1234') and db.user_doit_changer_mdp('u2')


def test_api_suppression_controles(client, db):
    assert client.post('/api/users/supprimer', headers=H, json={}).status_code == 400
    assert client.post('/api/users/supprimer', headers=H,
                       json={'username': 'admin'}).status_code == 400   # soi-même
    db.add_user('u3', 'secret123')
    assert client.post('/api/users/supprimer', headers=H, json={'username': 'u3'}).get_json()['succes']


def test_api_brouillons_et_meme_jour(client, db, programme):
    d = client.get('/api/drafts').get_json()['drafts']
    assert d and d[0]['nb_formations'] == 1
    r = client.get('/api/dorrat/meme-jour?date=2026-10-21').get_json()
    assert r['nombre'] == 1 and r['dorrat'][0]['titre'] == 'تحرير المحاضر'
    assert client.get(f"/api/dorrat/meme-jour?date=2026-10-21&lettre_id={programme['lettre_id']}"
                      ).get_json()['nombre'] == 0


def test_api_recherche_mkowin_champs_publics(client, db):
    db.add_mkow({'grade': 'المقدم', 'nom': 'زياد', 'prenom': 'تجريبي', 'cin': '12345678',
                 'num_compte': '12345678901234567890'})
    res = client.get('/api/mkowin/recherche?q=زياد').get_json()
    assert res and 'cin' not in res[0] and 'num_compte' not in res[0]


# ═══ 13. Échappement HTML ═══════════════════════════════════════════════════

def test_esc_defini_une_seule_fois():
    ui = open(os.path.join(BASE, 'static', 'js', 'ui.js'), encoding='utf-8').read()
    assert 'window.esc = function' in ui
    for c in ('&amp;', '&lt;', '&gt;', '&quot;', '&#39;'):
        assert c in ui


def test_donnees_saisies_echappees_dans_les_gabarits():
    """Aucune donnée saisie (titre, nom, lieu, رتبة…) n'est plus insérée
    brute dans un gabarit HTML construit en JavaScript."""
    from tests.conftest import js_programme
    src = open(os.path.join(BASE, 'templates', 'nouvelle_lettre.html'), encoding='utf-8').read() + js_programme()
    litteraux = [l for l in re.findall(r'`[^`]*`', src, re.S) if '<' in l]
    champ = re.compile(r"\b(?:f|data|d|m)\.(titre|nom_formateur|nom_prenom|lieu_formation|"
                       r"lieu_travail|grade|destination|jiha_marjiiya|identifiant_unique|periode)\b")
    fautes = []
    for l in litteraux:
        for expr in re.findall(r'\$\{((?:[^{}]|\{[^{}]*\})*)\}', l):
            if not champ.search(expr):
                continue
            # permis : échappé, simple comparaison, ou passé à un constructeur
            # d'<option> qui échappe lui-même (_escOpt)
            if re.search(r'(?i)esc\w*\(', expr) or '===' in expr or 'Options(' in expr:
                continue
            fautes.append(expr)
    assert fautes == []
