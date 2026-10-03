# -*- coding: utf-8 -*-
"""مقرّر الدورة (v1.4d) — « لا يمكن إسناد مستحقّات مالية بدون وجود مقرّر ».

  • Chaque دورة a SON مقرّر (عدد + تاريخ), demandé dès qu'on la choisit.
  • Sans lui : ni ورقة الحضور, ni الصنف, ni القيمة — côté écran ET serveur.
  • Il n'est plus un réglage global : إعدادات وثائق الخلاص ne le portent plus,
    et la valeur d'exemple semée par les versions précédentes disparaît.
  • نسبة الأداءات se règle désormais dans الجدول المالي.
"""
from tests.test_mustahaqqat import _dorra_enregistree, _p

JETON = {'X-CSRF-Token': 'jeton-de-test'}


def _dorra_sans_muqarrar(db):
    return _dorra_enregistree(db, [_p('خالد', 'العريف', '1')], muqarrar=False)


# ─── la porte ────────────────────────────────────────────────────────────────

def test_choisir_une_دورة_mene_d_abord_au_مقرر(client, db):
    _lid, fid = _dorra_sans_muqarrar(db)
    r = client.get(f'/mustahaqqat/dorra/{fid}/hodour')
    assert r.status_code == 302
    assert r.headers['Location'].endswith(f'/mustahaqqat/dorra/{fid}/muqarrar')
    page = client.get(f'/mustahaqqat/dorra/{fid}/muqarrar').get_data(as_text=True)
    assert 'name="muqarrar_numero"' in page and 'name="muqarrar_date"' in page
    assert 'لا يمكن إسناد مستحقّات مالية دون مقرّر' in page


def test_le_serveur_refuse_pointage_صنف_et_montant_sans_مقرر(client, db):
    _lid, fid = _dorra_sans_muqarrar(db)
    for url, corps in ((f'/mustahaqqat/dorra/{fid}/hodour', {'presences': {}}),
                       (f'/mustahaqqat/dorra/{fid}/classe', {'classe': 'ج'}),
                       (f'/mustahaqqat/dorra/{fid}/qima', {})):
        r = client.post(url, json=corps, headers=JETON)
        assert r.status_code == 400, url
        assert 'مقرّر' in r.get_json()['erreur'], url
    assert client.get(f'/mustahaqqat/dorra/{fid}/qima').status_code == 302


def test_le_مقرر_est_obligatoire_et_date_valide(client, db):
    _lid, fid = _dorra_sans_muqarrar(db)
    r = client.post(f'/mustahaqqat/dorra/{fid}/muqarrar',
                    data={'_csrf': 'jeton-de-test', 'muqarrar_numero': '',
                          'muqarrar_date': 'pas une date'})
    assert r.status_code == 200
    texte = r.get_data(as_text=True)
    assert 'عدد المقرّر وجوبيّ' in texte and 'تاريخ المقرّر وجوبيّ' in texte
    assert db.muqarrar_manquant(fid)


def test_une_fois_saisi_on_passe_a_la_feuille_de_presence(client, db):
    _lid, fid = _dorra_sans_muqarrar(db)
    r = client.post(f'/mustahaqqat/dorra/{fid}/muqarrar',
                    data={'_csrf': 'jeton-de-test', 'muqarrar_numero': '2026/77',
                          'muqarrar_date': f'{db.annee_registre()}-02-13'})
    assert r.status_code == 302
    assert r.headers['Location'].endswith(f'/mustahaqqat/dorra/{fid}/hodour')
    assert db.get_muqarrar_dorra(fid) == ('2026/77', f'{db.annee_registre()}-02-13')
    assert client.get(f'/mustahaqqat/dorra/{fid}/hodour').status_code == 200


def test_chaque_دورة_garde_son_propre_مقرر(db):
    _l1, f1 = _dorra_enregistree(db, [_p('خالد', 'العريف', '1')], titre='أ', muqarrar=False)
    _l2, f2 = _dorra_enregistree(db, [_p('سامي', 'العريف', '2')], titre='ب', muqarrar=False)
    db.save_muqarrar_dorra(f1, '11', '2026-01-01')
    db.save_muqarrar_dorra(f2, '22', '2026-02-02')
    assert db.get_muqarrar_dorra(f1) == ('11', '2026-01-01')
    assert db.get_muqarrar_dorra(f2) == ('22', '2026-02-02')


def test_le_retour_ne_sort_pas_de_la_منظومة(client, db):
    """Le paramètre `suite` ne peut renvoyer que vers un écran interne."""
    _lid, fid = _dorra_sans_muqarrar(db)
    r = client.post(f'/mustahaqqat/dorra/{fid}/muqarrar',
                    data={'_csrf': 'jeton-de-test', 'muqarrar_numero': '1',
                          'muqarrar_date': f'{db.annee_registre()}-02-13', 'suite': 'https://ailleurs.example'})
    assert r.headers['Location'].endswith(f'/mustahaqqat/dorra/{fid}/hodour')


# ─── les وثائق الخلاص ────────────────────────────────────────────────────────

def test_les_وثائق_impriment_le_مقرر_de_la_دورة(db):
    from core import khalas
    _lid, fid = _dorra_sans_muqarrar(db)
    a = db.annee_registre()
    db.save_muqarrar_dorra(fid, '2026/77', f'{a}-02-13')
    d = khalas.assembler(fid)
    assert d['muqarrar_numero'] == '2026/77'
    assert d['muqarrar_date'] == f'13 فيفري {a}'          # en toutes lettres


def test_sans_مقرر_les_وثائق_le_signalent_au_lieu_d_inventer(db):
    from core import khalas
    _lid, fid = _dorra_sans_muqarrar(db)
    d = khalas.assembler(fid)
    assert d['muqarrar_numero'] == '' and d['muqarrar_date'] == ''
    assert 'عدد المقرّر' in khalas.champs_manquants(d)


def test_l_ecran_des_وثائق_ne_peut_ecraser_le_مقرر(client, db):
    _lid, fid = _dorra_enregistree(db, [_p('خالد', 'العريف', '1')])
    avant = db.get_muqarrar_dorra(fid)
    client.post(f'/mustahaqqat/dorra/{fid}/khalas/save', headers=JETON,
                json={'numero_mudhakkira': '9', 'muqarrar_numero': 'PIRATE',
                      'muqarrar_date': ''})
    assert db.get_muqarrar_dorra(fid) == avant
    assert db.get_khalas_dorra(fid)['numero_mudhakkira'] == '9'


# ─── ce qui a quitté إعدادات وثائق الخلاص ────────────────────────────────────

def test_le_مقرر_n_est_plus_un_reglage(client, db):
    html = client.get('/mustahaqqat/khalas/parametres').get_data(as_text=True)
    assert 'name="muqarrar_numero"' not in html
    assert 'name="muqarrar_date"' not in html
    assert 'name="taux_adaat"' not in html
    s = db.get_khalas_settings()
    assert 'muqarrar_numero' not in s and 'muqarrar_date' not in s


def test_la_valeur_d_exemple_des_anciennes_versions_est_effacee(db):
    """`10101856 / 20 أوت 2026` était semé par défaut : il ne doit plus
    pouvoir se retrouver imprimé sur une وثيقة réelle."""
    db.set_khalas_settings({'muqarrar_numero': '10101856', 'muqarrar_date': '20 أوت 2026'})
    db.init_db()                                     # mise à jour de la base
    conn = db.get_connection()
    reste = conn.execute("SELECT COUNT(*) FROM khalas_settings WHERE cle IN "
                         "('muqarrar_numero','muqarrar_date')").fetchone()[0]
    conn.close()
    assert reste == 0


def test_نسبة_الأداءات_se_regle_dans_الجدول_المالي(client, db):
    html = client.get('/mustahaqqat/bareme-mali').get_data(as_text=True)
    assert 'name="taux_adaat"' in html and 'نسبة الأداءات' in html
    r = client.post('/mustahaqqat/bareme-mali',
                    data={'_csrf': 'jeton-de-test', 'taux_adaat': '12.5'})
    assert r.status_code == 302
    assert db.get_khalas_settings()['taux_adaat'] == '12.5'


def test_une_نسبة_absurde_est_refusee(client, db):
    client.post('/mustahaqqat/bareme-mali', data={'_csrf': 'jeton-de-test', 'taux_adaat': '150'})
    assert db.get_khalas_settings()['taux_adaat'] == '15'
