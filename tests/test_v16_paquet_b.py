# -*- coding: utf-8 -*-
"""v1.6 — الحزمة ب : ب.ت.و = 8 أرقام بالضبط، الحساب = 20 رقمًا بالضبط.

Données de test FICTIVES uniquement (aucun CIN ni RIB réel)."""
import pytest

from core import validation as val
from core import importation as imp
from tests.test_khalas import _dorra_chiffree
from tests.test_importation import classeur, ENTETE

JETON = {'X-CSRF-Token': 'jeton-de-test'}
CIN_OK = '01234567'
RIB_OK = '00000000000000000001'
MSG_CIN = 'رقم بطاقة التعريف الوطنية يجب أن يتكوّن من 8 أرقام بالضبط'
MSG_RIB = 'رقم الحساب البنكي أو البريدي يجب أن يتكوّن من 20 رقمًا بالضبط'


def _q(db, sql, args=()):
    conn = db.get_connection()
    try:
        return [dict(r) for r in conn.execute(sql, args).fetchall()]
    finally:
        conn.close()


# ─── 1. Le validateur ────────────────────────────────────────────────────────

@pytest.mark.parametrize('brut, net', [
    ('01234567', '01234567'),
    ('٠١٢٣٤٥٦٧', '01234567'),
    (' 0123 4567 ', '01234567'),
    ('0000 0000-0000.0000/00_01', RIB_OK),
    (None, ''),
])
def test_normaliser(brut, net):
    assert val.normaliser(brut) == net


@pytest.mark.parametrize('champ, valeur, ok', [
    ('cin', '', True), ('cin', '   ', True),
    ('cin', CIN_OK, True), ('cin', '٠١٢٣٤٥٦٧', True),
    ('cin', '1234567', False), ('cin', '123456789', False), ('cin', '1234567A', False),
    ('num_compte', '', True), ('num_compte', RIB_OK, True),
    ('num_compte', '00 000 0000000000000 01', True),
    ('num_compte', '0' * 19, False), ('num_compte', '0' * 21, False),
    ('num_compte', 'RIB-00000000000000001', False),
])
def test_erreur_champ(champ, valeur, ok):
    assert (val.erreur_champ(champ, valeur) is None) is ok


def test_messages_arabes():
    assert val.message('cin') == MSG_CIN
    assert val.message('num_compte') == MSG_RIB


def test_verifier_identite_normalise_en_place_et_ignore_l_absent():
    d = {'cin': '٠١٢٣ ٤٥٦٧', 'num_compte': '00 000 0000000000000 01'}
    assert val.verifier_identite(d) == []
    assert d == {'cin': CIN_OK, 'num_compte': RIB_OK}
    d = {'nom': 'x'}
    assert val.verifier_identite(d) == [] and d == {'nom': 'x'}
    d = {'cin': '123', 'num_compte': '1'}
    assert val.verifier_identite(d) == [MSG_CIN, MSG_RIB]
    assert d['cin'] == '123'          # la saisie fautive n'est pas altérée


# ─── 2. إضافة مكوّن ──────────────────────────────────────────────────────────

def _form(**k):
    return {'_csrf': 'jeton-de-test', 'grade': 'مقدم', 'nom': 'تجربة',
            'prenom': 'وهمي', **k}


def test_ajout_refuse_cin_court(client, db):
    r = client.post('/mkowin/ajouter', data=_form(cin='1234567'))
    html = r.get_data(as_text=True)
    assert r.status_code == 200 and MSG_CIN in html
    ligne = next(l for l in html.splitlines() if 'VALEURS_RENVOYEES =' in l)
    assert '1234567' in ligne                              # saisie conservée
    assert _q(db, "SELECT id FROM mkowin WHERE nom='تجربة'") == []


def test_ajout_refuse_rib_19(client, db):
    r = client.post('/mkowin/ajouter', data=_form(num_compte='0' * 19))
    assert MSG_RIB in r.get_data(as_text=True)
    assert _q(db, "SELECT id FROM mkowin WHERE nom='تجربة'") == []


def test_ajout_accepte_et_stocke_normalise(client, db):
    r = client.post('/mkowin/ajouter',
                    data=_form(cin='٠١٢٣٤٥٦٧', num_compte='00 000 0000000000000 01'))
    assert r.status_code == 302
    row = _q(db, "SELECT cin, num_compte FROM mkowin WHERE nom='تجربة'")
    assert row == [{'cin': CIN_OK, 'num_compte': RIB_OK}]


def test_ajout_accepte_champs_vides(client, db):
    r = client.post('/mkowin/ajouter', data=_form(cin='', num_compte=''))
    assert r.status_code == 302
    assert len(_q(db, "SELECT id FROM mkowin WHERE nom='تجربة'")) == 1


# ─── 3. تحيين مكوّن ──────────────────────────────────────────────────────────

def _mkow(db):
    db.add_mkow({'grade': 'مقدم', 'nom': 'تجربة', 'prenom': 'وهمي',
                 'cin': '11111111', 'num_compte': '1' * 20})
    return _q(db, "SELECT id FROM mkowin WHERE nom='تجربة'")[0]['id']


def test_modification_refusee_ne_touche_pas_la_fiche(client, db):
    mid = _mkow(db)
    r = client.post(f'/mkowin/{mid}/modifier',
                    data=_form(cin='2222222', num_compte='2' * 21, specialite='جديد'))
    html = r.get_data(as_text=True)
    assert MSG_CIN in html and MSG_RIB in html
    assert 'value="2222222"' in html
    row = _q(db, 'SELECT cin, num_compte, specialite FROM mkowin WHERE id=?', (mid,))[0]
    assert row['cin'] == '11111111' and row['num_compte'] == '1' * 20
    assert (row['specialite'] or '') != 'جديد'


def test_modification_acceptee(client, db):
    mid = _mkow(db)
    r = client.post(f'/mkowin/{mid}/modifier', data=_form(cin='2222 2222', num_compte='٢' * 20))
    assert r.status_code == 302
    row = _q(db, 'SELECT cin, num_compte FROM mkowin WHERE id=?', (mid,))[0]
    assert row == {'cin': '22222222', 'num_compte': '2' * 20}


def test_modification_vider_est_permis(client, db):
    mid = _mkow(db)
    client.post(f'/mkowin/{mid}/modifier', data=_form(cin='', num_compte=''))
    row = _q(db, 'SELECT cin, num_compte FROM mkowin WHERE id=?', (mid,))[0]
    assert (row['cin'] or '') == '' and (row['num_compte'] or '') == ''


def test_formulaires_portent_le_controle_client(client, db):
    html = client.get('/mkowin/ajouter').get_data(as_text=True)
    assert 'data-verif="cin"' in html and 'data-verif="rib"' in html
    mid = _mkow(db)
    html = client.get(f'/mkowin/{mid}/modifier').get_data(as_text=True)
    assert 'data-verif="cin"' in html and 'data-verif="rib"' in html


# ─── 4. وثائق الخلاص ─────────────────────────────────────────────────────────

def test_khalas_refuse_sans_rien_ecrire(client, db):
    fid = _dorra_chiffree(db, nom_formateur='تجربة وهمي')
    avant_mk = _q(db, 'SELECT * FROM mkowin')
    avant_kh = db.get_khalas_dorra(fid)
    r = client.post(f'/mustahaqqat/dorra/{fid}/khalas/save', headers=JETON,
                    json={'numero_mudhakkira': '77', 'cin': '123', 'num_compte': RIB_OK})
    assert r.status_code == 400
    j = r.get_json()
    assert j['succes'] is False and MSG_CIN in j['erreur']
    assert _q(db, 'SELECT * FROM mkowin') == avant_mk
    assert db.get_khalas_dorra(fid) == avant_kh


def test_khalas_rib_faux(client, db):
    fid = _dorra_chiffree(db, nom_formateur='تجربة وهمي')
    r = client.post(f'/mustahaqqat/dorra/{fid}/khalas/save', headers=JETON,
                    json={'num_compte': '0' * 19})
    assert r.status_code == 400 and MSG_RIB in r.get_json()['erreur']


def test_khalas_accepte_et_normalise(client, db):
    fid = _dorra_chiffree(db, nom_formateur='تجربة وهمي')
    r = client.post(f'/mustahaqqat/dorra/{fid}/khalas/save', headers=JETON,
                    json={'numero_mudhakkira': '77', 'cin': '٠١٢٣٤٥٦٧',
                          'num_compte': '00 000 0000000000000 01'})
    assert r.status_code == 200 and r.get_json()['succes']
    row = _q(db, "SELECT cin, num_compte FROM mkowin WHERE nom='تجربة'")
    assert row == [{'cin': CIN_OK, 'num_compte': RIB_OK}]
    assert db.get_khalas_dorra(fid)['numero_mudhakkira'] == '77'


def test_assistant_khalas_porte_le_controle_client(client, db):
    fid = _dorra_chiffree(db, nom_formateur='تجربة وهمي')
    ok, info = db.confirmer_mustahaqqat(fid)
    assert ok, info
    html = client.get(f'/mustahaqqat/dorra/{fid}/khalas').get_data(as_text=True)
    assert 'data-verif="cin"' in html and 'data-verif="rib"' in html
    assert 'champIdentiteInvalide' in html


# ─── 5. استيراد إكسال ────────────────────────────────────────────────────────

def _plan(lignes):
    return imp.analyser(classeur([ENTETE + ['بطاقة التعريف']] + lignes), [])


def test_import_cin_numerique_retrouve_son_zero():
    plan = _plan([['9001', 'مقدم', 'تجربة', 'وهمي', 'x', 'y', 1234567]])
    assert plan['rejetes'] == []
    assert plan['a_ajouter'][0][1]['cin'] == CIN_OK


def test_import_cin_texte_normalise():
    plan = _plan([['9002', 'مقدم', 'تجربة', 'وهمي', 'x', 'y', '٠١٢٣ ٤٥٦٧']])
    assert plan['a_ajouter'][0][1]['cin'] == CIN_OK


def test_import_cin_invalide_rejete():
    plan = _plan([['9003', 'مقدم', 'تجربة', 'وهمي', 'x', 'y', '12345'],
                  ['9004', 'مقدم', 'ثان', 'وهمي', 'x', 'y', '123456789'],
                  ['9005', 'مقدم', 'ثالث', 'وهمي', 'x', 'y', '']])
    motifs = [r['motif'] for r in plan['rejetes']]
    assert motifs == ['رقم بطاقة التعريف يجب أن يتكوّن من 8 أرقام'] * 2
    assert [f['identifiant_unique'] for _, f in plan['a_ajouter']] == ['9005']
