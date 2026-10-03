# -*- coding: utf-8 -*-
"""v1.5 — الحزمة أ : en-tête réduite (N1), toasts (A11), états (A13/P2),
titres (A16), police locale (A14), impression (UX4), mode sombre (A3)."""
import os
import re
from datetime import date

from tests.conftest import _client_flask, BASE_DIR

import core.etats as etats


def _css():
    return open(os.path.join(BASE_DIR, 'static', 'css', 'app.css'), encoding='utf-8').read()


def _js():
    return open(os.path.join(BASE_DIR, 'static', 'js', 'ui.js'), encoding='utf-8').read()


# ─── N1 : changement obligatoire du mot de passe ─────────────────────────────

def _client_mdp_force(db, monkeypatch):
    db.update_config('installation_faite', '1')
    c = _client_flask(db, monkeypatch, 'admin')
    db.update_user_password('admin', 'secret123')
    conn = db.get_connection()
    conn.execute("UPDATE users SET doit_changer_mdp=1 WHERE username='admin'")
    conn.commit(); conn.close()
    with c.session_transaction() as s:
        s['doit_changer_mdp'] = True
    return c


def test_n1_entete_reduite_pendant_changement_force(db, monkeypatch):
    c = _client_mdp_force(db, monkeypatch)
    html = c.get('/changer-mot-de-passe').get_data(as_text=True)
    assert 'navbar--restreinte' in html
    assert 'nav-logo' in html and 'نظام إدارة التكوين الديواني' in html
    for absent in ('class="nav-bottom"', 'class="nav-menu"', 'id="themeSwitcher"',
                   'class="nav-user-block"', 'العودة إلى الشاشة الرئيسية', 'لوحة القيادة'):
        assert absent not in html, absent
    # le formulaire, lui, est bien là et sans bouton « إلغاء »
    assert 'name="nouveau"' in html and 'تغيير إجباري' in html
    assert 'btn btn-cancel' not in html


def test_n1_toute_autre_page_renvoie_vers_le_changement(db, monkeypatch):
    c = _client_mdp_force(db, monkeypatch)
    r = c.get('/dashboard')
    assert r.status_code == 302 and '/changer-mot-de-passe' in r.headers['Location']


def test_n1_apres_changement_la_navigation_revient(db, monkeypatch):
    c = _client_mdp_force(db, monkeypatch)
    r = c.post('/changer-mot-de-passe', data={
        'actuel': 'secret123', 'nouveau': 'nouveau456', 'confirmation': 'nouveau456',
        '_csrf': 'jeton-de-test'})
    assert r.status_code in (302, 303)
    html = c.get('/dashboard').get_data(as_text=True)
    assert 'navbar--restreinte' not in html
    assert 'class="nav-bottom"' in html and 'id="themeSwitcher"' in html


def test_n1_changement_volontaire_garde_la_navigation(client):
    html = client.get('/changer-mot-de-passe').get_data(as_text=True)
    assert 'navbar--restreinte' not in html and 'nav-menu' in html
    assert 'btn btn-cancel' in html


# ─── A11 : toasts ───────────────────────────────────────────────────────────

def test_a11_flash_rendu_en_toast(client):
    with client.session_transaction() as s:
        s['_flashes'] = [('success', 'تمّ الحفظ'), ('error', 'خطأ ما'), ('bizarre', 'x')]
    html = client.get('/dashboard').get_data(as_text=True)
    assert 'id="toastZone"' in html
    assert re.search(r'class="toast toast-success" data-duree="5000"', html)
    assert re.search(r'class="toast toast-error" data-duree="0"', html)   # reste affiché
    assert 'class="toast toast-info"' in html                               # catégorie inconnue
    assert 'تمّ الحفظ' in html and 'خطأ ما' in html


def test_a11_toast_echappe_le_html(client):
    with client.session_transaction() as s:
        s['_flashes'] = [('error', '<script>alert(1)</script>')]
    html = client.get('/dashboard').get_data(as_text=True)
    assert '<script>alert(1)</script>' not in html
    assert '&lt;script&gt;' in html


def test_a11_api_js_presente():
    js = _js()
    assert 'window.showToast' in js and 'armerToastsServeur' in js
    assert 'm.textContent' in js           # jamais innerHTML pour le message


# ─── A13 / P2 : états ───────────────────────────────────────────────────────

J = date(2026, 10, 15)


def test_etat_dorra():
    assert etats.etat_dorra({'finalise_at': '2026-10-01', 'date_formation': '2026-09-01'}, J)['code'] == 'acheve'
    assert etats.etat_dorra({'date_formation': '2026-10-14'}, J)['code'] == 'retard'
    assert etats.etat_dorra({'date_formation': '2026-10-15'}, J)['code'] == 'cours'   # le jour même
    assert etats.etat_dorra({'date_formation': '2026-10-16'}, J)['code'] == 'cours'
    # date absente ou illisible : jamais « en retard »
    for d in ('', None, '15/10/2026', '2026-13-40', 'بعد العيد'):
        assert etats.etat_dorra({'date_formation': d}, J)['code'] == 'cours', d


def test_etat_finances():
    assert etats.etat_finances({'date_formation': 'x'}) is None
    assert etats.etat_finances({'finalise_at': 'x', 'mu_etat': 'acheve'})['code'] == 'acheve'
    assert etats.etat_finances({'finalise_at': 'x', 'mu_etat': 'hodour'})['code'] == 'brouillon'
    assert etats.etat_finances({'finalise_at': 'x'})['code'] == 'brouillon'


def test_etats_programme():
    br = etats.etats_programme({'verrouille': 0, 'date_ouverte': '2026-10-20'}, J)
    assert [e['code'] for e in br] == ['brouillon']
    ok = etats.etats_programme({'verrouille': 1, 'nb_finalisees': 1, 'nb_formations': 3,
                                'date_ouverte': '2026-10-01'}, J)
    assert [e['code'] for e in ok] == ['scelle', 'cours', 'retard']
    assert ok[1]['label'].startswith('1/3')


def test_p2_programme_en_retard_affiche(client, db):
    lid = db.save_programme('interne', 'جانفي', 2020, [{
        'titre': 'دورة قديمة', 'grade': 'مقدم', 'nom_formateur': 'س ع',
        'lieu_travail': 'x', 'date_formation': '2020-01-10', 'periode': '',
        'lieu_formation': 'قاعة'}], 'n', 't')
    html = client.get('/formations-en-cours').get_data(as_text=True)
    assert 'bandeau-retard' in html and 'عدد البرامج المتأخّرة: 1' in html
    assert f'id="prog-row-{lid}"' in html and 'data-retard="1"' in html
    assert 'etat-pastille--retard' in html and 'etat-pastille--brouillon' in html


def test_p2_programme_futur_pas_en_retard(client, db):
    db.save_programme('interne', 'جانفي', 2099, [{
        'titre': 'دورة مقبلة', 'grade': 'مقدم', 'nom_formateur': 'س ع',
        'lieu_travail': 'x', 'date_formation': '2099-01-10', 'periode': '',
        'lieu_formation': 'قاعة'}], 'n', 't')
    html = client.get('/formations-en-cours').get_data(as_text=True)
    assert 'bandeau-retard' not in html and 'data-retard' not in html


def test_date_ouverte_ignore_les_dorrat_finalisees(db):
    from tests.test_audit_v14e import _dorra_finalisee
    lid, fid = _dorra_finalisee(db)
    # la seule دورة est finalisée : le programme n'est plus « inachevé »
    assert all(p['id'] != lid for p in db.get_programmes_inacheves())


def test_a13_pastilles_liste_programmes(client, db):
    from tests.test_audit_v14e import _dorra_finalisee
    _dorra_finalisee(db)
    html = client.get('/programmes').get_data(as_text=True)
    assert 'etat-pastille--acheve' in html and 'مسجّلة نهائيًّا' in html
    assert 'المستحقّات غير منجزة' in html


# ─── A16 : titres ───────────────────────────────────────────────────────────

def _titre(html):
    return re.search(r'<title>(.*?)</title>', html, re.S).group(1).strip()


def test_a16_suffixe_ajoute_une_seule_fois(client, db):
    t = _titre(client.get('/mkowin').get_data(as_text=True))
    assert t == 'قائمة الأسماء – نظام إدارة التكوين'
    t = _titre(client.get('/dashboard').get_data(as_text=True))
    assert t.count('نظام إدارة التكوين') == 1


def test_a16_titre_fiche_porte_le_nom_complet(client, db):
    db.add_mkow({'grade': 'نقيب', 'nom': 'منى', 'prenom': 'بن عمر'})
    mid = db.get_mkowin()[0]['id']
    t = _titre(client.get(f'/mkowin/{mid}').get_data(as_text=True))
    assert 'منى بن عمر' in t and t.endswith('نظام إدارة التكوين')
    t = _titre(client.get(f'/mkowin/{mid}/modifier').get_data(as_text=True))
    assert 'منى بن عمر' in t


# ─── A14 : police locale ────────────────────────────────────────────────────

def test_a14_police_cairo_servie_localement(client):
    css = _css()
    for f in re.findall(r"url\('\.\./fonts/(cairo-[^']+)'\)", css):
        assert os.path.isfile(os.path.join(BASE_DIR, 'static', 'fonts', f)), f
        r = client.get('/static/fonts/' + f)
        assert r.status_code == 200 and len(r.data) > 5000
        r.close()
    assert 'http' not in ''.join(re.findall(r'@font-face\s*{[^}]*}', css))
    assert os.path.isfile(os.path.join(BASE_DIR, 'static', 'fonts', 'Cairo-OFL.txt'))
    html = client.get('/dashboard').get_data(as_text=True)
    assert 'data-police-choix="cairo"' in html and 'data-police-choix="amiri"' in html


# ─── A3 / UX4 / A7 ──────────────────────────────────────────────────────────

def test_a3_mode_sombre_systeme():
    # v1.7.1 : le thème de départ est le clair (0), plus celui du système
    js = _js()
    assert 'prefers-color-scheme: dark' not in js and 'themeChoisi' in js
    assert 'THEME_DEFAUT = 0' in js


def test_a3_login_et_accueil_suivent_le_systeme(db, monkeypatch):
    login = open(os.path.join(BASE_DIR, 'templates', 'login.html'), encoding='utf-8').read()
    assert 'prefers-color-scheme: dark' not in login and 'return 0;' in login
    accueil = open(os.path.join(BASE_DIR, 'templates', 'accueil.html'), encoding='utf-8').read()
    assert 'APP_PREFS.appliquer()' in accueil


def test_ux4_feuille_impression():
    css = _css()
    assert '@media print' in css
    bloc = css[css.index('UX4'):]
    for sel in ('.navbar', '.footer', '.toast-zone', '.btn'):
        assert sel in bloc
    assert '.print-entete' in css


def test_a7_etat_vide_recherche_branche(client, db):
    db.add_mkow({'grade': 'نقيب', 'nom': 'منى', 'prenom': 'بن عمر'})
    html = client.get('/mkowin').get_data(as_text=True)
    assert 'majEtatVide(' in html
    assert 'window.majEtatVide' in _js()


# ─── Compléments : icône, toasts sur l'accueil, implémentation unique ───────

def test_favicon_servi_sans_connexion(db, monkeypatch):
    import app as application
    application.app.config.update(TESTING=True)
    r = application.app.test_client().get('/favicon.ico')
    assert r.status_code == 200 and r.mimetype == 'image/png' and r.data[:4] == b'\x89PNG'


def test_accueil_affiche_les_messages(client):
    with client.session_transaction() as s:
        s['_flashes'] = [('success', 'تمّ تغيير كلمة المرور بنجاح')]
    html = client.get('/accueil').get_data(as_text=True)
    assert 'id="toastZone"' in html and 'تمّ تغيير كلمة المرور بنجاح' in html


def test_une_seule_implementation_showtoast():
    for nom in ('nouvelle_lettre.html', 'nouvelle_lettre_libre.html'):
        s = open(os.path.join(BASE_DIR, 'templates', nom), encoding='utf-8').read()
        assert 'function showToast' not in s and 'id="toast"' not in s
    assert 'bottom: 1.8rem' not in _css()[:_css().index('v1.5')]
