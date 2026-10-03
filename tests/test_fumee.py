# -*- coding: utf-8 -*-
"""Test de fumée global (v1.4) : TOUTES les pages GET de l'application répondent
sans erreur serveur, sur une base peuplée (programme, participants, مكوّن, مادة).

Filet transversal pour les refactors : si une page quelconque casse (import
manquant, fonction renommée, gabarit invalide…), ce test le voit."""
import pytest

from core import pdf_khalas


@pytest.fixture()
def peuple(db, programme):
    mkow_id = db.add_mkow({'nom': 'البوهلالي زياد', 'grade': 'مقدم',
                           'identifiant_unique': '123456', 'cin': '01234567',
                           'lieu_travail': 'الإدارة الجهوية للديوانة بالقصرين'})
    madda_id = db.add_madda({'titre': 'تحرير المحاضر', 'type_formation': 'مستمر'})
    db.save_participants(programme['lettre_id'], programme['formation_id'], [
        {'nom_prenom': 'التونسي علي', 'grade': 'عريف', 'identifiant_unique': '654321',
         'lieu_travail': 'مكتب القصرين'},
    ])
    ids = dict(programme)
    ids['mkow_id'] = mkow_id if isinstance(mkow_id, int) else 1
    ids['madda_id'] = madda_id if isinstance(madda_id, int) else 1
    return ids


def _urls(app, ids):
    valeurs = {'lettre_id': ids['lettre_id'], 'formation_id': ids['formation_id'],
               'mkow_id': ids['mkow_id'], 'madda_id': ids['madda_id'],
               'numero': 1, 'type_lettre': 'interne'}
    for r in app.url_map.iter_rules():
        if 'GET' not in r.methods or r.rule.startswith('/static') or r.rule == '/logout':
            continue
        if 'doc' in r.arguments:
            for doc in list(pdf_khalas.ORDRE) + ['all']:
                yield r.rule.replace('<int:formation_id>', str(ids['formation_id'])).replace('<doc>', doc)
            continue
        url = r.rule
        for arg in r.arguments:
            url = url.replace(f'<int:{arg}>', str(valeurs[arg])).replace(f'<{arg}>', str(valeurs[arg]))
        yield url


def test_toutes_les_pages_repondent(client, peuple):
    import app as application
    erreurs = []
    urls = list(_urls(application.app, peuple))
    assert len(urls) > 60
    for url in urls:
        rep = client.get(url)
        if rep.status_code >= 500:
            erreurs.append(f'{url} → {rep.status_code}')
    assert erreurs == []


def test_pages_cles_rendues(client, peuple):
    """Les écrans principaux renvoient bien du HTML (200), pas une redirection d'erreur."""
    for url in ('/accueil', '/dashboard', '/mkowin', '/mawad', '/programmes',
                '/lettre/nouvelle', '/mustahaqqat', '/statistiques', '/parametres',
                f"/lettre/{peuple['lettre_id']}/formations/{peuple['formation_id']}/participants"):
        rep = client.get(url)
        assert rep.status_code == 200, f'{url} → {rep.status_code}'
