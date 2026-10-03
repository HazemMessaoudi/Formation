# -*- coding: utf-8 -*-
"""Phase 4 (v1.4) : l'autocomplétion interroge /api/mkowin/recherche au lieu de
recevoir toute la table مكوّنون dans la page."""
import json

import pytest


@pytest.fixture()
def personnes(db):
    db.add_mkow({'nom': 'الزواري', 'prenom': 'سامي', 'grade': 'مقدم',
                 'identifiant_unique': '111111', 'lieu_travail': 'إدارة القصرين',
                 'jiha_marjiiya': 'الإدارة الجهوية بالقصرين',
                 'cin': '09876543', 'num_compte': '07000123456789012345',
                 'adresse': 'نهج الحرية', 'email': 'x@exemple.tn'})
    db.add_mkow({'nom': 'الزين', 'prenom': 'مروان', 'grade': 'وكيل',
                 'identifiant_unique': '222222', 'lieu_travail': 'مكتب فريانة'})
    db.add_mkow({'nom': 'Ben Ali', 'prenom': '', 'grade': 'عريف',
                 'identifiant_unique': '333333', 'lieu_travail': 'Sbeitla'})
    for i in range(60):
        db.add_mkow({'nom': f'موظف{i:02d}', 'prenom': 'تجربة', 'grade': 'عريف',
                     'identifiant_unique': f'9{i:05d}', 'lieu_travail': 'مكتب'})
    return db


def _ancien_filtre(db, q, limite=40):
    """Réplique exacte de l'ancien filtre JavaScript (v1.3) sur get_mkowin()."""
    q = q.strip().lower()
    res = []
    for m in db.get_mkowin():
        full = ((m['nom'] or '') + (' ' + m['prenom'] if m.get('prenom') else '')).strip()
        if (not q or q in full.lower() or q in (m['grade'] or '').lower()
                or q in (m['lieu_travail'] or '').lower()):
            res.append(full)
    return res[:limite]


@pytest.mark.parametrize('q', ['', 'الز', 'سامي', 'وكيل', 'فريانة', 'ben', 'BEN ALI',
                               'sbeitla', 'موظف0', 'عريف', 'غير موجود', '  الزين  '])
def test_meme_resultats_que_l_ancien_filtre(personnes, q):
    obtenus = [personnes.nom_complet_mkow(m) for m in personnes.rechercher_mkowin(q)]
    assert obtenus == _ancien_filtre(personnes, q)


def test_limite(personnes):
    assert len(personnes.rechercher_mkowin('', 40)) == 40
    assert len(personnes.rechercher_mkowin('', 5)) == 5
    assert len(personnes.rechercher_mkowin('', 'abc')) == 40      # valeur invalide → défaut
    assert len(personnes.rechercher_mkowin('', 10_000)) <= 200    # plafonnée


def test_aucun_champ_sensible(personnes):
    m = personnes.rechercher_mkowin('سامي')[0]
    assert set(m) == set(personnes.CHAMPS_MKOW_PUBLICS)
    assert m['identifiant_unique'] == '111111'
    assert m['jiha_marjiiya'] == 'الإدارة الجهوية بالقصرين'


def test_api_recherche(client, personnes):
    rep = client.get('/api/mkowin/recherche?q=' + 'الزو')
    assert rep.status_code == 200
    data = rep.get_json()
    assert [personnes.nom_complet_mkow(m) for m in data] == ['الزواري سامي']
    brut = rep.get_data(as_text=True)
    for secret in ('09876543', '07000123456789012345', 'نهج الحرية', 'x@exemple.tn'):
        assert secret not in brut


def test_api_exige_connexion(db):
    import app as application
    application.app.config.update(TESTING=True)
    c = application.app.test_client()
    db.update_config('installation_faite', '1')
    rep = c.get('/api/mkowin/recherche?q=a')
    assert rep.status_code in (302, 401)


def test_page_nouvelle_lettre_sans_donnees_sensibles(client, personnes):
    """Avant v1.4, CIN / compte bancaire / adresse de TOUTES les personnes
    figuraient dans le code source de la page."""
    html = client.get('/lettre/nouvelle').get_data(as_text=True)
    for secret in ('09876543', '07000123456789012345', 'نهج الحرية', 'x@exemple.tn',
                   'موظف00'):
        assert secret not in html
    assert 'const MKOWIN_INIT  = [];' in html


def test_modification_injecte_seulement_les_formateurs_du_programme(client, personnes):
    lettre_id = personnes.save_programme(
        'interne', 'أكتوبر', 2026,
        [{'titre': 'تحرير المحاضر', 'grade': 'مقدم', 'nom_formateur': 'الزواري سامي',
          'lieu_travail': 'إدارة القصرين', 'date_formation': '2026-10-21',
          'periode': '', 'lieu_formation': 'مركز التكوين الجهوي بالقصرين'}],
        'حازم مسعودي', 'النقيب')
    rep = client.get(f'/lettre/nouvelle?modifier={lettre_id}')
    html = rep.get_data(as_text=True)
    ligne = [l for l in html.split('\n') if l.startswith('const MKOWIN_INIT')][0]
    injecte = json.loads(ligne.split('=', 1)[1].strip().rstrip(';'))
    assert [personnes.nom_complet_mkow(m) for m in injecte] == ['الزواري سامي']
    assert '09876543' not in html
