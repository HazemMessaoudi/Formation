# -*- coding: utf-8 -*-
"""V3.2 — دليل الاستعمال : contenu cohérent avec l'application, page, bouton « ؟ »."""
import re

from core import guide


def _endpoints():
    import app as application
    return {r.endpoint for r in application.app.url_map.iter_rules()}


def test_fiches_uniques_et_completes():
    ids = [f['id'] for f in guide.FICHES]
    assert len(ids) == len(set(ids))
    parties = {p for p, _n, _t in guide.PARTIES}
    for f in guide.FICHES:
        assert f['partie'] in parties, f['id']
        assert f['titre'] and f['but'] and f['etapes'], f['id']
        assert f['suivant'] is None or guide.fiche(f['suivant']), f['id']
    assert all(liste for _p, _n, _t, liste in guide.sommaire())


def test_liens_et_pages_existent():
    """Un endpoint renommé casse ce test, pas le دليل."""
    eps = _endpoints()
    for f in guide.FICHES:
        assert f['lien'] is None or f['lien'] in eps, (f['id'], f['lien'])
        for ep in f['pages']:
            assert ep in eps, (f['id'], ep)


def test_chaque_endpoint_n_a_qu_une_fiche():
    vus = {}
    for f in guide.FICHES:
        for ep in f['pages']:
            assert ep not in vus, (ep, vus.get(ep), f['id'])
            vus[ep] = f['id']
    assert guide.fiche_pour('mustahaqqat_qima') == 'qima'
    assert guide.fiche_pour('inconnu') == '' and guide.fiche_pour(None) == ''


def test_page_du_guide(client):
    html = client.get('/dalil').get_data(as_text=True)
    for f in guide.FICHES:
        assert f'id="{f["id"]}"' in html and f['titre'].replace('&', '&amp;') in html
    assert 'id="dlRech"' in html and 'window.print()' in html
    assert 'من مشمولات المشرف العام' in html
    assert 'href="/lettre/nouvelle"' in html                  # « اذهب إلى الصفحة »


def test_bouton_aide_ouvre_la_fiche_de_la_page(client):
    html = client.get('/lettre/nouvelle').get_data(as_text=True)
    assert 'class="aide-btn"' in html and 'href="/dalil#programme_nouveau"' in html
    html = client.get('/statistiques').get_data(as_text=True)
    assert 'href="/dalil#stats_centre"' in html
    html = client.get('/dalil').get_data(as_text=True)
    assert re.search(r'href="/dalil"\s+class="aide-btn"', html)   # pas de fiche : sommaire


def test_lien_depuis_l_accueil(client):
    html = client.get('/accueil').get_data(as_text=True)
    assert 'href="/dalil"' in html and 'دليل الاستعمال' in html


def test_guide_accessible_au_simple_utilisateur(db, monkeypatch):
    from tests.conftest import _client_flask
    db.update_config('installation_faite', '1')
    c = _client_flask(db, monkeypatch, 'user')
    assert c.get('/dalil').status_code == 200
