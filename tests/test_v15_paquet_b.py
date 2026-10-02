# -*- coding: utf-8 -*-
"""v1.5 — الحزمة ب : confirmations (UX3), déconnexion automatique (S3),
visionneuse PDF (A12/P3), tri (A6), vérifications (A8), suggestions (A10),
mémoire des filtres (UX1)."""
import glob
import os
import re
import time

import pytest

from tests.conftest import _client_flask, BASE_DIR
from core.securite import delai_inactivite, DELAIS_INACTIVITE, DELAI_INACTIVITE_DEFAUT

JETON = {'X-CSRF-Token': 'jeton-de-test'}


def _lire(*chemin):
    return open(os.path.join(BASE_DIR, *chemin), encoding='utf-8').read()


def _journal(db):
    c = db.get_connection()
    try:
        return [dict(r) for r in c.execute('SELECT * FROM journal ORDER BY id').fetchall()]
    finally:
        c.close()


# ─── UX3 : plus aucune boîte native ─────────────────────────────────────────

def test_ux3_aucun_confirm_ni_alert_natif():
    for p in glob.glob(os.path.join(BASE_DIR, 'templates', '**', '*.html'), recursive=True):
        s = open(p, encoding='utf-8').read()
        assert not re.search(r'(?<![\w.])confirm\(', s), p
        assert not re.search(r'(?<![\w.])alert\(', s), p
        assert not re.search(r'(?<![\w.])prompt\(', s), p


def test_ux3_formulaires_de_suppression_declaratifs(client, db):
    assert 'data-confirm="حذف «' in _lire('templates', 'jihat.html')
    db.add_mkow({'grade': 'نقيب', 'nom': 'منى', 'prenom': 'بن عمر'})
    mid = db.get_mkowin()[0]['id']
    html = client.get(f'/mkowin/{mid}').get_data(as_text=True)
    assert 'data-confirm="حذف «منى بن عمر» نهائيًّا؟' in html
    js = _lire('static', 'js', 'ui.js')
    assert "hasAttribute('data-confirm')" in js and 'requestSubmit' in js
    # la suppression elle-même est inchangée côté serveur
    r = client.post(f'/mkowin/{mid}/supprimer', data={'_csrf': 'jeton-de-test'})
    assert r.status_code == 302 and db.get_mkowin() == []


# ─── S3 : déconnexion automatique ───────────────────────────────────────────

@pytest.mark.parametrize('brut,attendu', [
    (None, DELAI_INACTIVITE_DEFAUT), ('', DELAI_INACTIVITE_DEFAUT), ('abc', DELAI_INACTIVITE_DEFAUT),
    ('0', 0), ('15', 15), ('30', 30), ('60', 60), ('120', 120), (' 60 ', 60),
    ('7', DELAI_INACTIVITE_DEFAUT), ('-1', DELAI_INACTIVITE_DEFAUT), ('999', DELAI_INACTIVITE_DEFAUT),
])
def test_s3_delai_borne(brut, attendu):
    cfg = {} if brut is None else {'delai_inactivite': brut}
    assert delai_inactivite(cfg) == attendu


def test_s3_session_inactive_expiree(client, db):
    db.update_config('delai_inactivite', '15')
    with client.session_transaction() as s:
        s['_vu'] = int(time.time()) - 16 * 60
    r = client.get('/dashboard')
    assert r.status_code == 302 and '/login?expire=1' in r.headers['Location']
    assert any(e['action'] == 'خروج تلقائي بسبب عدم النشاط' for e in _journal(db))
    # la session est bien détruite
    r = client.get('/dashboard')
    assert r.status_code == 302 and '/login' in r.headers['Location']


def test_s3_api_repond_401_json(client, db):
    db.update_config('delai_inactivite', '15')
    with client.session_transaction() as s:
        s['_vu'] = int(time.time()) - 3600
    r = client.post('/api/ping', headers=JETON, json={})
    assert r.status_code == 401 and r.get_json()['expire'] is True


def test_s3_session_active_rafraichie(client, db):
    db.update_config('delai_inactivite', '15')
    ancien = int(time.time()) - 10 * 60
    with client.session_transaction() as s:
        s['_vu'] = ancien
    assert client.get('/dashboard').status_code == 200
    with client.session_transaction() as s:
        assert s['_vu'] >= int(time.time()) - 2
    r = client.post('/api/ping', headers=JETON, json={})
    assert r.status_code == 200 and r.get_json() == {'ok': True}


def test_s3_desactive_ne_expire_jamais(client, db):
    db.update_config('delai_inactivite', '0')
    with client.session_transaction() as s:
        s['_vu'] = int(time.time()) - 30 * 24 * 3600
    assert client.get('/dashboard').status_code == 200


def test_s3_session_sans_horodatage_non_expiree(client, db):
    db.update_config('delai_inactivite', '15')
    assert client.get('/dashboard').status_code == 200     # ancien cookie : pas de _vu


def test_s3_reglage_par_admin(client, db):
    html = client.get('/parametres').get_data(as_text=True)
    assert 'id="carteSecurite"' in html and 'value="30" selected' in html.replace('\n', ' ').replace('  ', ' ') \
        or re.search(r'value="30"\s+selected', html)
    r = client.post('/parametres/securite', data={'delai_inactivite': '60', '_csrf': 'jeton-de-test'})
    assert r.status_code == 302 and db.get_config()['delai_inactivite'] == '60'
    r = client.post('/parametres/securite', data={'delai_inactivite': '45', '_csrf': 'jeton-de-test'})
    assert db.get_config()['delai_inactivite'] == '60'          # valeur hors liste refusée
    r = client.post('/parametres/securite', data={'delai_inactivite': 'x', '_csrf': 'jeton-de-test'})
    assert db.get_config()['delai_inactivite'] == '60'
    assert any(e['action'] == 'تعديل مدّة الخروج التلقائي' for e in _journal(db))


def test_s3_reglage_refuse_a_un_agent(db, monkeypatch):
    db.update_config('installation_faite', '1')
    c = _client_flask(db, monkeypatch, 'user')
    r = c.post('/parametres/securite', data={'delai_inactivite': '0', '_csrf': 'jeton-de-test'})
    assert r.status_code == 403 and 'delai_inactivite' not in db.get_config()
    assert 'id="carteSecurite"' not in c.get('/parametres').get_data(as_text=True)


def test_s3_page_porte_le_delai(client, db):
    html = client.get('/dashboard').get_data(as_text=True)
    assert 'data-inactivite="30"' in html and 'inactivite=1' in html
    db.update_config('delai_inactivite', '0')
    html = client.get('/dashboard').get_data(as_text=True)
    assert 'data-inactivite' not in html
    db.update_config('delai_inactivite', '60')
    assert 'data-inactivite="60"' in client.get('/accueil').get_data(as_text=True)


def test_s3_logout_automatique_et_message(client, db):
    r = client.get('/logout?inactivite=1')
    assert r.status_code == 302 and 'expire=1' in r.headers['Location']
    assert _journal(db)[-1]['action'] == 'خروج تلقائي بسبب عدم النشاط'
    html = client.get('/login?expire=1').get_data(as_text=True)
    assert 'تمّ إغلاق الجلسة تلقائيًّا' in html
    assert 'تمّ إغلاق الجلسة' not in client.get('/login').get_data(as_text=True)


def test_s3_logout_normal_inchange(client, db):
    r = client.get('/logout')
    assert r.status_code == 302 and 'expire' not in r.headers['Location']
    assert _journal(db)[-1]['action'] == 'خروج من النظام'


def test_s3_connexion_pose_horodatage(db, monkeypatch):
    import app as application
    db.update_config('installation_faite', '1')
    db.update_user_password('admin', 'motdepasse1')
    c = application.app.test_client()
    with c.session_transaction() as s:
        s['_csrf'] = 'jeton-de-test'
    c.post('/login', data={'username': 'admin', 'password': 'motdepasse1', '_csrf': 'jeton-de-test'})
    with c.session_transaction() as s:
        assert abs(s.get('_vu', 0) - time.time()) < 5


# ─── A12 / P3 : visionneuse PDF ─────────────────────────────────────────────

def _motif_pdf():
    js = _lire('static', 'js', 'ui.js')
    m = re.search(r"const MOTIF_PDF = /(.+)/i;", js)
    return re.compile(m.group(1), re.I)


def test_a12_motif_couvre_toutes_les_routes_pdf():
    import app as application
    motif = _motif_pdf()
    for regle in application.app.url_map.iter_rules():
        chemin = re.sub(r'<[^>]+>', '7', regle.rule)
        doc = regle.endpoint in ('generer_lettre', 'generer_lettre_libre', 'generer_lettre_directeur_regional') \
            or regle.rule.endswith('/pdf') or '/pdf/' in regle.rule
        if doc and 'GET' in regle.methods:
            assert motif.search(chemin), regle.rule
        if not doc:
            assert not motif.search(chemin), regle.rule


def test_a12_visionneuse_et_interceptions():
    js = _lire('static', 'js', 'ui.js')
    for fragment in ('window.ouvrirPdf', "a.target === '_blank' && estUrlPdf", 'window.open = function',
                     "indexOf('html')", 'جاري إعداد الوثيقة'):
        assert fragment in js, fragment


# ─── A6 : tri ───────────────────────────────────────────────────────────────

def test_a6_tableaux_triables(client, db):
    db.add_mkow({'grade': 'نقيب', 'nom': 'منى', 'prenom': 'بن عمر'})
    html = client.get('/mkowin').get_data(as_text=True)
    assert 'table-triable" data-renumeroter' in html and '<th data-tri="non">إجراءات</th>' in html
    reg = _lire('templates', 'lettres', 'registre.html')
    assert 'table-triable' in reg and 'data-renumeroter' not in reg   # numéro officiel intouchable
    for p in ('mawad/liste.html', 'journal.html', 'lettres/liste_libres.html',
              'mustahaqqat/dorrat_manjaza.html', 'mustahaqqat/mkowin.html'):
        assert 'table-triable' in _lire('templates', *p.split('/')), p
    js = _lire('static', 'js', 'ui.js')
    assert "table.hasAttribute('data-renumeroter')" in js


# ─── A8 / A10 : fiches de personnes ─────────────────────────────────────────

def test_a8_verifications_souples(client, db):
    for url in ('/mkowin/ajouter',):
        html = client.get(url).get_data(as_text=True)
        for champ, v in (('cin', 'cin'), ('identifiant_unique', 'chiffres'), ('telephone_gsm', 'telephone'),
                         ('email', 'email'), ('num_compte', 'rib')):
            assert f'name="{champ}" data-verif="{v}"' in html
        # jamais de pattern bloquant ajouté
        assert 'pattern=' not in html


def test_a8_un_cin_atypique_est_refuse_depuis_v16(client, db):
    # v1.5 laissait passer un ب.ت.و atypique ; la v1.6 (حزمة ب) exige
    # 8 chiffres exactement — la خانة reste facultative (voir test_v16_paquet_b).
    r = client.post('/mkowin/ajouter', data={'grade': 'نقيب', 'nom': 'منى', 'prenom': 'بن عمر',
                                             'cin': '12 34', 'telephone_gsm': 'x', '_csrf': 'jeton-de-test'})
    assert r.status_code == 200
    assert 'يجب أن يتكوّن من 8 أرقام بالضبط' in r.get_data(as_text=True)
    assert db.get_mkowin() == []
    # le téléphone, lui, reste souple : seul l'avertissement client subsiste
    r = client.post('/mkowin/ajouter', data={'grade': 'نقيب', 'nom': 'منى', 'prenom': 'بن عمر',
                                             'cin': '1234 5678', 'telephone_gsm': 'x', '_csrf': 'jeton-de-test'})
    assert r.status_code == 302
    assert db.get_mkowin()[0]['cin'] == '12345678'


def test_a10_suggestions(db):
    for i, (adm, banque) in enumerate((('إدارة أ', 'بنك 1'), ('إدارة أ', 'بنك 2'), ('إدارة ب', 'بنك 2'),
                                       ('  إدارة أ  ', ''), ('', None))):
        db.add_mkow({'grade': 'نقيب', 'nom': f'ن{i}', 'prenom': 'ل', 'administration': adm, 'banque': banque})
    s = db.suggestions_mkowin()
    assert s['administration'] == ['إدارة أ', 'إدارة ب']        # la plus fréquente d'abord, espaces ignorés
    assert s['banque'] == ['بنك 2', 'بنك 1']
    assert set(s) == set(db.CHAMPS_SUGGERES)


def test_a10_datalists_rendues(client, db):
    db.add_jiha('الإدارة الجهويّة للدّيوانة بالكاف', 'direction') if hasattr(db, 'add_jiha') else None
    db.add_mkow({'grade': 'نقيب', 'nom': 'منى', 'prenom': 'بن عمر', 'banque': 'البنك الوطني'})
    mid = db.get_mkowin()[0]['id']
    for url in ('/mkowin/ajouter', f'/mkowin/{mid}/modifier'):
        html = client.get(url).get_data(as_text=True)
        assert 'name="banque" list="dl_mk_banque"' in html
        assert '<datalist id="dl_mk_banque">' in html and 'value="البنك الوطني"' in html
        assert '<datalist id="dl_mk_administration">' in html


def test_a10_valeur_hors_liste_acceptee(client, db):
    r = client.post('/mkowin/ajouter', data={'grade': 'نقيب', 'nom': 'س', 'prenom': 'ع',
                                             'administration': 'جهة جديدة تمامًا', '_csrf': 'jeton-de-test'})
    assert r.status_code == 302 and db.get_mkowin()[0]['administration'] == 'جهة جديدة تمامًا'


# ─── UX1 : mémoire des filtres ──────────────────────────────────────────────

def test_ux1_filtres_memorises(client, db):
    db.add_mkow({'grade': 'نقيب', 'nom': 'منى', 'prenom': 'بن عمر'})
    html = client.get('/mkowin').get_data(as_text=True)
    assert 'data-memoriser="colonne"' in html and 'data-memoriser="texte"' in html
    assert 'data-memoriser' in _lire('templates', 'mawad', 'liste.html')
    assert 'data-memoriser' in _lire('templates', 'journal.html')
    assert 'sessionStorage' in _lire('static', 'js', 'ui.js')


def test_a12_rappel_de_la_route_dr_ne_consomme_pas_de_numero(client, db):
    """La visionneuse peut rappeler l'URL (تنزيل / نافذة مستقلّة) : la مراسلة
    المدير الجهوي doit garder SON numéro, sans en tirer un second."""
    from tests.test_audit_v14e import _ouvrir_annee
    _ouvrir_annee(db, 2026)
    lid = db.save_programme('interne', 'أكتوبر', 2026, [{
        'titre': 'دورة', 'grade': 'مقدم', 'nom_formateur': 'س ع', 'lieu_travail': 'x',
        'date_formation': '2026-10-21', 'periode': '', 'lieu_formation': 'قاعة'}], 'n', 't')
    db.verrouiller_lettre(lid, 'interne')
    url = f'/lettre/{lid}/generer-directeur-regional?type_mr=externe'
    r1 = client.get(url); r2 = client.get(url); r3 = client.get(url)
    assert r1.status_code == r2.status_code == r3.status_code == 200
    assert r1.mimetype == 'application/pdf'
    c = db.get_connection()
    n = c.execute("SELECT COUNT(*) FROM dr_lettres WHERE lettre_id=?", (lid,)).fetchone()[0]
    c.close()
    assert n == 1
