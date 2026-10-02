# -*- coding: utf-8 -*-
"""v1.6 — الحزمة أ : توزيع الأدوار والقفل بعد التسجيل النهائي.

Données de test fictives uniquement."""
import pytest

from core import etats
from tests.conftest import _client_flask
from tests.test_mustahaqqat_qima import _dorra, _p, _jusquau_classement

JETON = {'X-CSRF-Token': 'jeton-de-test'}
REFUS = 'هذه العمليّة من مشمولات المشرف العام'


@pytest.fixture()
def agent(db, monkeypatch):
    db.update_config('installation_faite', '1')
    return _client_flask(db, monkeypatch, 'user')


def _lettre_de(db, fid):
    c = db.get_connection()
    try:
        return c.execute('SELECT lettre_id FROM formations WHERE id=?', (fid,)).fetchone()[0]
    finally:
        c.close()


def _journal(db, action):
    c = db.get_connection()
    try:
        return [dict(r) for r in c.execute('SELECT * FROM journal WHERE action=?', (action,))]
    finally:
        c.close()


# ─── التراجع للتحيين ────────────────────────────────────────────────────────

def test_deverrouiller_reserve_au_mushrif(db, client, agent):
    fid = _dorra(db, [_p('أ', 'المقدم', '1')])
    lid = _lettre_de(db, fid)
    url = f'/lettre/{lid}/formations/{fid}/deverrouiller'
    assert db.formation_est_finalisee(fid)

    r = agent.post(url, json={'motif': 'تصحيح خطأ في التاريخ'}, headers=JETON)
    assert r.status_code == 403 and r.get_json()['erreur'] == REFUS
    assert db.formation_est_finalisee(fid)

    r = client.post(url, json={'motif': 'خطأ'}, headers=JETON)          # < 5 أحرف
    assert r.status_code == 400 and 'إجباري' in r.get_json()['erreur']
    r = client.post(url, json={}, headers=JETON)
    assert r.status_code == 400
    assert db.formation_est_finalisee(fid)

    r = client.post(url, json={'motif': 'تصحيح خطأ في التاريخ'}, headers=JETON)
    assert r.status_code == 200 and r.get_json()['succes']
    assert not db.formation_est_finalisee(fid)
    j = _journal(db, 'التراجع للتحيين')
    assert len(j) == 1 and j[0]['utilisateur'] == 'admin'
    assert 'تصحيح خطأ في التاريخ' in j[0]['details']

    # déjà déverrouillée → refus propre
    assert client.post(url, json={'motif': 'مرّة ثانية'}, headers=JETON).status_code == 400


def test_deverrouiller_lettre_etrangere(db, client):
    fid = _dorra(db, [_p('أ', 'المقدم', '1')])
    lid = _lettre_de(db, fid)
    r = client.post(f'/lettre/{lid + 999}/formations/{fid}/deverrouiller',
                    json={'motif': 'تصحيح خطأ'}, headers=JETON)
    assert r.status_code == 404 and db.formation_est_finalisee(fid)


def test_deverrouiller_refuse_si_mustahaqqat_achevees(db, client):
    fid = _dorra(db, [_p('أ', 'المقدم', '1')])
    _jusquau_classement(db, fid, 'أ1')
    assert db.confirmer_mustahaqqat(fid)[0]
    ok, msg = db.deverrouiller_formation(fid)
    assert not ok and 'أعد فتح المستحقّات' in msg
    assert db.formation_est_finalisee(fid)


def test_bouton_deverrouiller_admin_seulement(db, client, agent):
    assert 'const EST_ADMIN = true' in client.get('/lettre/nouvelle').get_data(as_text=True)
    assert 'const EST_ADMIN = false' in agent.get('/lettre/nouvelle').get_data(as_text=True)


# ─── جاهز للمصادقة / التأكيد النهائي ───────────────────────────────────────

def test_agent_signale_pret_puis_mushrif_confirme(db, client, agent):
    fid = _dorra(db, [_p('أ', 'المقدم', '1')])
    _jusquau_classement(db, fid, 'أ1')

    # l'agent ne peut pas arrêter les مستحقّات …
    r = agent.post(f'/mustahaqqat/dorra/{fid}/qima', headers=JETON)
    assert r.status_code == 403 and r.get_json()['erreur'] == REFUS
    assert db.get_dorra_mustahaqqat(fid)['etat'] != 'acheve'

    # … il voit « جاهز للمصادقة », pas « التأكيد النهائي »
    html = agent.get(f'/mustahaqqat/dorra/{fid}/qima').get_data(as_text=True)
    assert 'id="btnPret"' in html and 'id="btnConfirmer"' not in html
    assert 'rouvrirMustahaqqat' not in html

    # … et le signale
    r = agent.post(f'/mustahaqqat/dorra/{fid}/pret', headers=JETON)
    assert r.status_code == 200 and r.get_json()['succes']
    d = db.get_dorra_mustahaqqat(fid)
    assert d['mu_pret_at'] and d['pret'] and d['mu_pret_par'] == 'agent'
    assert len(_journal(db, 'دورة جاهزة للمصادقة')) == 1
    assert 'بانتظار مصادقة المشرف' in agent.get(f'/mustahaqqat/dorra/{fid}/qima').get_data(as_text=True)
    # idempotent
    assert agent.post(f'/mustahaqqat/dorra/{fid}/pret', headers=JETON).get_json()['pret_at'] == d['mu_pret_at']

    # liste « غير منجزة » : pastille 📨
    assert 'جاهزة للمصادقة' in agent.get('/mustahaqqat/dorrat/ghayr-manjaza').get_data(as_text=True)

    # لوحة القيادة : le مشرف est averti, pas l'agent
    assert [x['id'] for x in db.donnees_tableau_de_bord()['pret_validation']] == [fid]
    assert 'دورات جاهزة للمصادقة النهائيّة' in client.get('/dashboard').get_data(as_text=True)
    assert 'دورات جاهزة للمصادقة النهائيّة' not in agent.get('/dashboard').get_data(as_text=True)

    # le مشرف voit « التأكيد النهائي » et arrête
    html = client.get(f'/mustahaqqat/dorra/{fid}/qima').get_data(as_text=True)
    assert 'id="btnConfirmer"' in html
    r = client.post(f'/mustahaqqat/dorra/{fid}/qima', headers=JETON)
    assert r.status_code == 200 and r.get_json()['succes']
    assert db.get_dorra_mustahaqqat(fid)['etat'] == 'acheve'
    assert db.donnees_tableau_de_bord()['pret_validation'] == []

    # liste « منجزة » : 🔒
    assert 'badge-verrou' in client.get('/mustahaqqat/dorrat/manjaza').get_data(as_text=True)

    # rouvrir : مشرف seulement
    r = agent.post(f'/mustahaqqat/dorra/{fid}/rouvrir', headers=JETON)
    assert r.status_code == 403
    assert db.get_dorra_mustahaqqat(fid)['etat'] == 'acheve'
    assert 'rouvrirMustahaqqat' not in agent.get(f'/mustahaqqat/dorra/{fid}/qima').get_data(as_text=True)
    assert 'rouvrirMustahaqqat' in client.get(f'/mustahaqqat/dorra/{fid}/qima').get_data(as_text=True)
    assert client.post(f'/mustahaqqat/dorra/{fid}/rouvrir', headers=JETON).status_code == 200
    assert db.get_dorra_mustahaqqat(fid)['etat'] != 'acheve'


def test_pret_refuse_avant_classement(db, agent):
    fid = _dorra(db, [_p('أ', 'المقدم', '1')])
    r = agent.post(f'/mustahaqqat/dorra/{fid}/pret', headers=JETON)
    assert r.status_code == 400
    assert not db.get_dorra_mustahaqqat(fid).get('mu_pret_at')


@pytest.mark.parametrize('action', ['hodour', 'classe', 'reprendre', 'rouvrir', 'deverrouiller'])
def test_pret_retombe_quand_la_dorra_change(db, action):
    """Toute modification en amont annule le signalement : le مشرف ne doit
    pas valider sur la foi d'un état périmé."""
    fid = _dorra(db, [_p('أ', 'المقدم', '1'), _p('ب', 'المقدم', '2')])
    _jusquau_classement(db, fid, 'أ1')
    if action == 'rouvrir':
        assert db.confirmer_mustahaqqat(fid)[0]
        db.rouvrir_mustahaqqat(fid)
        _jusquau_classement(db, fid, 'أ1')
    assert db.marquer_pret_validation(fid, 'agent')[0]
    assert db.get_dorra_mustahaqqat(fid)['mu_pret_at']

    if action == 'hodour':
        ps = db.get_hodour(fid)
        db.save_hodour(fid, {ps[0]['id']: True, ps[1]['id']: False})
    elif action == 'classe':
        auto = db.get_dorra_mustahaqqat(fid)['mu_classe_auto']
        assert db.confirmer_classe(fid, auto)[0]
    elif action == 'reprendre':
        db.reprendre_hodour(fid)
    elif action == 'rouvrir':
        assert db.confirmer_mustahaqqat(fid)[0]
        db.rouvrir_mustahaqqat(fid)
    elif action == 'deverrouiller':
        assert db.deverrouiller_formation(fid)[0]
    assert not (db.get_dorra_mustahaqqat(fid) or {}).get('mu_pret_at')
    conn = db.get_connection()
    row = conn.execute('SELECT pret_at, pret_par FROM mustahaqqat WHERE formation_id=?',
                       (fid,)).fetchone()
    conn.close()
    assert row is None or (row['pret_at'] is None and not row['pret_par'])
    assert db.dorrat_pretes_validation() == []


def test_agent_garde_hodour_et_classe(db, agent):
    """L'agent continue de saisir الحضور et le صنف."""
    fid = _dorra(db, [_p('أ', 'المقدم', '1')])
    pid = db.get_hodour(fid)[0]['id']
    r = agent.post(f'/mustahaqqat/dorra/{fid}/hodour', json={'presences': {str(pid): True}},
                   headers=JETON)
    assert r.status_code != 403
    r = agent.post(f'/mustahaqqat/dorra/{fid}/classe', json={'classe': 'أ1'}, headers=JETON)
    assert r.status_code != 403


# ─── حذف مكوّن / مادّة, توريد ───────────────────────────────────────────────

def test_suppressions_et_import_reserves(db, client, agent):
    db.add_mkow({'grade': 'المقدم', 'nom': 'زياد', 'prenom': 'البوهلالي'})
    db.add_madda({'titre': 'تحرير المحاضر'})
    mid = db.get_mkowin()[0]['id']
    did = db.get_mawad()[0]['id']
    form = {'_csrf': 'jeton-de-test'}

    for url, data in ((f'/mkowin/{mid}/supprimer', form),
                      ('/mkowin/supprimer-lot', {**form, 'ids': [str(mid)]}),
                      (f'/mawad/{did}/supprimer', form),
                      ('/mawad/supprimer-lot', {**form, 'ids': [str(did)]})):
        assert agent.post(url, data=data).status_code == 403, url
    assert db.get_mkow(mid) and db.get_madda(did)
    assert agent.get('/mkowin/importer').status_code == 403
    assert agent.get('/mkowin/importer/namouthaj').status_code == 403

    # interface : ni cases à cocher, ni فسخ, ni lien d'توريد pour l'agent
    for url in ('/mkowin', '/mawad'):
        html = agent.get(url).get_data(as_text=True)
        assert 'name="ids"' not in html and 'fsakhSelection()' not in html
        assert 'const DECALAGE_COL = 1' in html
        html = client.get(url).get_data(as_text=True)
        assert 'name="ids"' in html and 'const DECALAGE_COL = 0' in html
    assert 'توريد من ملفّ إكسال' not in agent.get('/dashboard').get_data(as_text=True)
    assert 'توريد من ملفّ إكسال' in client.get('/dashboard').get_data(as_text=True)
    assert '/supprimer' not in agent.get(f'/mkowin/{mid}').get_data(as_text=True)

    # le مشرف supprime, c'est journalisé
    assert client.post(f'/mkowin/{mid}/supprimer', data=form).status_code == 302
    assert client.post(f'/mawad/{did}/supprimer', data=form).status_code == 302
    assert not db.get_mkow(mid) and not db.get_madda(did)
    assert _journal(db, 'حذف مكوّن') and _journal(db, 'حذف مادّة تكوين')


def test_avertissement_dorrat_liees(db, client):
    _dorra(db, [_p('أ', 'المقدم', '1')])      # formateur زياد البوهلالي, مادّة تحرير المحاضر
    db.add_mkow({'grade': 'المقدم', 'nom': 'زياد', 'prenom': 'البوهلالي'})
    db.add_mkow({'grade': 'النقيب', 'nom': 'منى', 'prenom': 'بن عمر'})
    db.add_madda({'titre': '  تحرير   المحاضر '})
    db.add_madda({'titre': 'مادّة أخرى'})
    ids = {m['nom']: m['id'] for m in db.get_mkowin()}
    assert db.nb_dorrat_liees_mkow(ids['زياد']) == 1
    assert db.nb_dorrat_liees_mkow(ids['منى']) == 0
    mawad = {' '.join(m['titre'].split()): m['id'] for m in db.get_mawad()}
    assert db.nb_dorrat_liees_madda(mawad['تحرير المحاضر']) == 1
    assert db.nb_dorrat_liees_madda(mawad['مادّة أخرى']) == 0

    assert f'data-liees="1"' in client.get('/mkowin').get_data(as_text=True)
    assert 'data-liees="1"' in client.get('/mawad').get_data(as_text=True)

    client.post(f'/mkowin/{ids["زياد"]}/supprimer', data={'_csrf': 'jeton-de-test'})
    j = _journal(db, 'حذف مكوّن')
    assert j and 'مرتبط بـ 1 دورة' in j[0]['details']


# ─── Pastilles 🔒 et mot de passe ───────────────────────────────────────────

def test_etat_dorra_finalisee_porte_le_verrou():
    e = etats.etat_dorra({'finalise_at': '2026-02-10 10:00:00'})
    assert e['icone'] == '🔒' and 'مقفلة' in e['label'] and e['code'] == 'acheve'
    e2 = etats.etat_dorra({'finalise_at': None, 'date_formation': '2099-01-01'})
    assert e2['icone'] != '🔒'


def test_agent_change_son_mot_de_passe(db, agent):
    assert 'changer-mot-de-passe' in agent.get('/dashboard').get_data(as_text=True)
    r = agent.post('/changer-mot-de-passe', data={
        '_csrf': 'jeton-de-test', 'actuel': 'secret123',
        'nouveau': 'nouveau456', 'confirmation': 'nouveau456'})
    assert r.status_code == 302
    assert db.check_credentials('agent', 'nouveau456')
