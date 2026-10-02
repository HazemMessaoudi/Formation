# -*- coding: utf-8 -*-
"""المستحقّات المالية — التأشير على الحضور وتحديد صنف الدورة (v1.0).

Ce que ces tests défendent, dans l'ordre où l'agent les rencontre :

  • le barème officiel أ1/أ2/ب/ج/د classe correctement chaque رتبة ;
  • une dorra n'apparaît dans « غير منجزة » qu'une fois enregistrée
    définitivement dans la منظومة ;
  • une ورقة حضور à moitié pointée est REFUSÉE — pas de صنف deviné ;
  • le صنف retenu est celui des **présents**, jamais celui de la liste
    d'origine ;
  • l'égalité entre deux أصناف est tranchée pour le plus élevé, et signalée ;
  • « رفض » ramène au pointage et efface le صنف déjà confirmé.
"""

import pytest

from core import mustahaqqat as m


JETON = {'X-CSRF-Token': 'jeton-de-test'}


# ─── Outillage ───────────────────────────────────────────────────────────────

def _dorra_enregistree(db, participants, titre='تحرير المحاضر', muqarrar=True):
    """Une dorra complète et **enregistrée définitivement** — le seul état
    dans lequel les مستحقّات acceptent de la voir.

    `muqarrar` : la دورة a déjà franchi l'écran «مقرّر الدورة» (v1.4d) ; sans
    lui, ni pointage ni صنف ni montant ne sont acceptés."""
    annee = db.annee_registre()
    lid = db.save_programme(
        'interne', 'فيفري', annee,
        [{'titre': titre, 'grade': 'مقدم', 'nom_formateur': 'زياد البوهلالي',
          'lieu_travail': '', 'date_formation': f'{annee}-02-10', 'periode': '',
          'lieu_formation': 'القصرين'}],
        'حازم مسعودي', 'النقيب')
    db.verrouiller_lettre(lid, 'interne')
    fid = db.get_lettre_detail(lid)['formations'][0]['id']
    db.save_participants(lid, fid, participants)
    db.save_memo_data(fid, {'objet': 'إعلام', 'corps': 'نصّ المذكّرة',
                            'moujah': [{'nom': 'الإدارة الجهوية'}]}, confirmer=True)
    ok, _info = db.finaliser_formation(fid)
    assert ok, 'la dorra de test doit être enregistrée définitivement'
    if muqarrar:
        db.save_muqarrar_dorra(fid, '2026/145', f'{annee}-02-20')   # v1.6.1 : après la دورة
    return lid, fid


def _p(nom, grade, uid):
    return {'nom_prenom': nom, 'grade': grade, 'identifiant_unique': uid,
            'lieu_travail': 'القصرين', 'jiha_marjiiya': ''}


# ─── Le barème رتبة → صنف ────────────────────────────────────────────────────

@pytest.mark.parametrize('grade, attendu', [
    ('العميد',        'أ1'),
    ('العقيد',        'أ1'),
    ('المقدم',        'أ1'),
    ('الرائد',        'أ1'),
    ('النقيب',        'أ1'),
    ('الملازم أول',   'أ1'),
    ('الملازم',       'أ2'),
    ('الوكيل أول',    'ب'),
    ('الوكيل',        'ب'),
    ('العريف أول',    'ب'),
    ('العريف',        'ج'),
    ('الرقيب أول',    'د'),
    ('الرقيب',        'د'),
])
def test_chaque_grade_recoit_son_صنف(grade, attendu):
    assert m.classe_du_grade(grade) == attendu


def test_les_libelles_officiels_sont_reconnus_tels_quels():
    """Le libellé officiel porte « للديوانة » et parfois les hamza pleines :
    la رتبة doit être reconnue quelle que soit la graphie."""
    assert m.classe_du_grade('عقيد للديوانة') == 'أ1'
    assert m.classe_du_grade('ملازم أول للديوانة صنف 2') == 'أ2'
    assert m.classe_du_grade('عريف أعلى للديوانة') == 'ب'
    assert m.classe_du_grade('رقيب أوّل للديوانة') == 'د'


def test_un_civil_nest_pas_classe():
    """السيد / السيدة ne figurent pas au barème : ils ne pèsent dans aucun
    صنف — et ne doivent surtout pas en inventer un."""
    assert m.classe_du_grade('السيد') == ''
    assert m.classe_du_grade('السيدة') == ''


def test_le_bareme_de_la_base_prime_sur_le_defaut(db):
    db.set_classe_grade('الملازم أول', 'أ2')
    assert m.classe_du_grade('الملازم أول', db.get_bareme_grades()) == 'أ2'
    db.reinitialiser_bareme()
    assert m.classe_du_grade('الملازم أول', db.get_bareme_grades()) == 'أ1'


def test_le_bareme_est_seme_au_premier_demarrage(db):
    bareme = db.get_bareme_grades()
    assert bareme['العميد'] == 'أ1'
    assert bareme['العريف'] == 'ج'
    # Les رتب civiles connues de la منظومة y figurent, sans صنف.
    assert bareme.get('السيد', None) == ''


# ─── الصنف الغالب ────────────────────────────────────────────────────────────

def test_le_صنف_est_celui_du_plus_grand_nombre():
    presents = [{'grade': 'العريف'}, {'grade': 'العريف'}, {'grade': 'العميد'}]
    classe, repart, ex_aequo = m.classe_dominante(presents)
    assert classe == 'ج'
    assert repart['ج'] == 2 and repart['أ1'] == 1
    assert ex_aequo == []


def test_une_egalite_retient_le_صنف_le_plus_eleve_et_le_signale():
    presents = [{'grade': 'العميد'}, {'grade': 'الرقيب'}]
    classe, _repart, ex_aequo = m.classe_dominante(presents)
    assert classe == 'أ1'
    assert ex_aequo == ['أ1', 'د']


def test_sans_aucun_grade_classable_il_ny_a_pas_de_صنف():
    classe, _r, _e = m.classe_dominante([{'grade': 'السيد'}, {'grade': 'السيدة'}])
    assert classe == ''


# ─── Le partage منجزة / غير منجزة ────────────────────────────────────────────

def test_une_dorra_non_enregistree_nentre_pas_dans_les_مستحقات(db, programme):
    """Tant que la dorra n'est pas enregistrée définitivement, les مستحقّات
    ne la connaissent pas : on ne paie pas sur un برنامج inachevé."""
    assert db.dorrat_mustahaqqat_ghayr_manjaza() == []
    assert db.get_dorra_mustahaqqat(programme['formation_id']) is None


def test_une_dorra_enregistree_apparait_en_ghayr_manjaza(db):
    _lid, fid = _dorra_enregistree(db, [_p('صالح المحمدي', 'المقدم', '80001')])
    liste = db.dorrat_mustahaqqat_ghayr_manjaza()
    assert [d['id'] for d in liste] == [fid]
    assert liste[0]['etat'] == 'attente'
    assert db.dorrat_mustahaqqat_manjaza() == []


# ─── ورقة الحضور ─────────────────────────────────────────────────────────────

def test_tout_participant_est_propose_present_avant_pointage(db):
    _lid, fid = _dorra_enregistree(db, [
        _p('صالح المحمدي', 'المقدم', '80001'),
        _p('محمد البكوش', 'العريف', '80002')])
    parts = db.get_hodour(fid)
    assert [p['present'] for p in parts] == [1, 1]
    assert [p['classe'] for p in parts] == ['أ1', 'ج']


def test_une_feuille_a_moitie_pointee_est_refusee(db):
    """Le cœur de la règle : un صنف ne se déduit que d'une feuille COMPLÈTE.
    Mieux vaut refuser que deviner."""
    _lid, fid = _dorra_enregistree(db, [
        _p('صالح المحمدي', 'المقدم', '80001'),
        _p('محمد البكوش', 'العريف', '80002')])
    premier = db.get_hodour(fid)[0]['id']
    ok, message = db.save_hodour(fid, {premier: True})
    assert not ok
    assert 'كلّ المشاركين' in message


def test_un_intrus_dans_la_feuille_est_refuse(db):
    _lid, fid = _dorra_enregistree(db, [_p('صالح المحمدي', 'المقدم', '80001')])
    pid = db.get_hodour(fid)[0]['id']
    ok, message = db.save_hodour(fid, {pid: True, pid + 9999: False})
    assert not ok
    assert 'لا ينتمي' in message


def test_le_صنف_suit_les_presents_et_non_la_liste(db):
    """Trois عريف inscrits, deux absents : le صنف bascule sur le seul présent.
    C'est exactement ce que le pointage sert à corriger."""
    _lid, fid = _dorra_enregistree(db, [
        _p('أوّل', 'العريف', '1'),
        _p('ثان',  'العريف', '2'),
        _p('ثالث', 'العميد', '3')])
    parts = db.get_hodour(fid)
    presences = {p['id']: (p['grade'] == 'العميد') for p in parts}
    ok, res = db.save_hodour(fid, presences)
    assert ok
    assert res['classe'] == 'أ1'
    assert res['nb_presents'] == 1 and res['nb_absents'] == 2


def test_le_pointage_est_conserve(db):
    _lid, fid = _dorra_enregistree(db, [
        _p('أوّل', 'العريف', '1'), _p('ثان', 'العميد', '2')])
    parts = db.get_hodour(fid)
    absent = parts[0]['id']
    ok, _res = db.save_hodour(fid, {p['id']: (p['id'] != absent) for p in parts})
    assert ok
    releve = {p['id']: p['present'] for p in db.get_hodour(fid)}
    assert releve[absent] == 0
    assert db.get_dorra_mustahaqqat(fid)['etat'] == 'hodour'


# ─── تأكيد الصنف ─────────────────────────────────────────────────────────────

def test_on_ne_confirme_pas_un_صنف_sans_avoir_pointe(db):
    _lid, fid = _dorra_enregistree(db, [_p('صالح', 'المقدم', '1')])
    ok, message = db.confirmer_classe(fid, 'أ1')
    assert not ok
    assert 'ورقة الحضور' in message


def test_la_confirmation_fixe_le_صنف(db):
    _lid, fid = _dorra_enregistree(db, [_p('صالح', 'المقدم', '1')])
    parts = db.get_hodour(fid)
    db.save_hodour(fid, {p['id']: True for p in parts})
    ok, _quand = db.confirmer_classe(fid, 'أ1')
    assert ok
    dorra = db.get_dorra_mustahaqqat(fid)
    assert dorra['classe'] == 'أ1'
    assert dorra['etat'] == 'classe'


def test_un_صنف_inconnu_est_refuse(db):
    _lid, fid = _dorra_enregistree(db, [_p('صالح', 'المقدم', '1')])
    parts = db.get_hodour(fid)
    db.save_hodour(fid, {p['id']: True for p in parts})
    ok, message = db.confirmer_classe(fid, 'ه')
    assert not ok and 'غير معروف' in message


def test_le_refus_ramene_au_pointage_et_efface_le_صنف(db):
    """« رفض » sur l'écran de confirmation : le صنف ne vaut plus rien tant
    que la feuille n'a pas été revue."""
    _lid, fid = _dorra_enregistree(db, [_p('صالح', 'المقدم', '1')])
    parts = db.get_hodour(fid)
    db.save_hodour(fid, {p['id']: True for p in parts})
    db.confirmer_classe(fid, 'أ1')
    db.reprendre_hodour(fid)
    dorra = db.get_dorra_mustahaqqat(fid)
    assert dorra['classe'] == ''
    assert dorra['etat'] == 'hodour'


# ─── Les écrans ──────────────────────────────────────────────────────────────

def test_la_page_daccueil_ouvre_sur_les_trois_portes(client):
    r = client.get('/', follow_redirects=True)
    assert r.status_code == 200
    page = r.get_data(as_text=True)
    for porte in ('برامج تكوينية', 'مستحقات مالية', 'إحصائيات'):
        assert porte in page


def test_la_lوحة_de_bord_des_programmes_reste_accessible(client):
    """La منظومة s'ouvre autrement, mais لوحة القيادة n'a pas bougé."""
    r = client.get('/dashboard')
    assert r.status_code == 200
    assert 'لوحة القيادة' in r.get_data(as_text=True)


def test_les_ecrans_des_مستحقات_repondent(client, db):
    _lid, fid = _dorra_enregistree(db, [_p('صالح', 'المقدم', '1')])
    for url in ('/mustahaqqat',
                '/mustahaqqat/mkowin',
                '/mustahaqqat/dorrat/ghayr-manjaza',
                '/mustahaqqat/dorrat/manjaza',
                '/mustahaqqat/bareme',
                f'/mustahaqqat/dorra/{fid}/hodour',
                '/statistiques'):
        r = client.get(url)
        assert r.status_code == 200, f'{url} → {r.status_code}'


def test_lecran_1_liste_la_dorra_a_traiter(client, db):
    _lid, fid = _dorra_enregistree(db, [_p('صالح', 'المقدم', '1')],
                                   titre='إجراءات التبليغ')
    page = client.get('/mustahaqqat/dorrat/ghayr-manjaza').get_data(as_text=True)
    assert 'إجراءات التبليغ' in page
    assert f'dorra-{fid}' in page


def test_la_route_du_pointage_renvoie_le_صنف_propose(client, db):
    _lid, fid = _dorra_enregistree(db, [
        _p('أوّل', 'العريف', '1'), _p('ثان', 'العريف', '2'),
        _p('ثالث', 'العميد', '3')])
    parts = db.get_hodour(fid)
    presences = {str(p['id']): True for p in parts}
    r = client.post(f'/mustahaqqat/dorra/{fid}/hodour',
                    json={'presences': presences}, headers=JETON)
    assert r.status_code == 200
    d = r.get_json()
    assert d['succes'] is True
    assert d['classe'] == 'ج'          # deux عريف contre un عميد
    assert d['nb_presents'] == 3 and d['nb_absents'] == 0


def test_la_route_du_pointage_refuse_une_feuille_incomplete(client, db):
    _lid, fid = _dorra_enregistree(db, [
        _p('أوّل', 'العريف', '1'), _p('ثان', 'العميد', '2')])
    pid = db.get_hodour(fid)[0]['id']
    r = client.post(f'/mustahaqqat/dorra/{fid}/hodour',
                    json={'presences': {str(pid): True}}, headers=JETON)
    assert r.status_code == 400
    assert 'كلّ المشاركين' in r.get_json()['erreur']


def test_la_route_de_confirmation_mene_a_lecran_suivant(client, db):
    _lid, fid = _dorra_enregistree(db, [_p('صالح', 'المقدم', '1')])
    parts = db.get_hodour(fid)
    client.post(f'/mustahaqqat/dorra/{fid}/hodour',
                json={'presences': {str(p['id']): True for p in parts}},
                headers=JETON)
    r = client.post(f'/mustahaqqat/dorra/{fid}/classe',
                    json={'classe': 'أ1'}, headers=JETON)
    assert r.status_code == 200
    suite = r.get_json()['suite']
    assert suite.endswith(f'/mustahaqqat/dorra/{fid}/qima')
    assert client.get(suite).status_code == 200


def test_lecran_de_la_valeur_exige_un_صنف(client, db):
    """Sans صنف confirmé, l'écran 3 renvoie au pointage : il n'y a rien à
    calculer tant que la dorra n'est pas classée."""
    _lid, fid = _dorra_enregistree(db, [_p('صالح', 'المقدم', '1')])
    r = client.get(f'/mustahaqqat/dorra/{fid}/qima')
    assert r.status_code == 302
    assert f'/mustahaqqat/dorra/{fid}/hodour' in r.headers['Location']


def test_le_journal_garde_trace_du_pointage_et_du_classement(client, db):
    _lid, fid = _dorra_enregistree(db, [_p('صالح', 'المقدم', '1')])
    parts = db.get_hodour(fid)
    client.post(f'/mustahaqqat/dorra/{fid}/hodour',
                json={'presences': {str(p['id']): True for p in parts}},
                headers=JETON)
    client.post(f'/mustahaqqat/dorra/{fid}/classe',
                json={'classe': 'أ1'}, headers=JETON)
    actions = [e['action'] for e in db.get_journal(50)]
    assert 'التأشير على ورقة الحضور' in actions
    assert 'تصنيف دورة تكوينية' in actions


# ─── جدول الأصناف ────────────────────────────────────────────────────────────

def test_un_مستعمل_عادي_ne_modifie_pas_le_bareme(db, monkeypatch):
    from tests.conftest import _client_flask
    db.update_config('installation_faite', '1')
    c = _client_flask(db, monkeypatch, 'user')
    c.post('/mustahaqqat/bareme', data={'classe__العميد': 'د',
                                        '_csrf': 'jeton-de-test'})
    assert db.get_bareme_grades()['العميد'] == 'أ1'


def test_le_مشرف_peut_corriger_le_bareme(client, db):
    client.post('/mustahaqqat/bareme',
                data={'classe__العميد': 'أ2', '_csrf': 'jeton-de-test'})
    assert db.get_bareme_grades()['العميد'] == 'أ2'
    client.post('/mustahaqqat/bareme',
                data={'action': 'reinitialiser', '_csrf': 'jeton-de-test'})
    assert db.get_bareme_grades()['العميد'] == 'أ1'


# ─── الإحصائيات ──────────────────────────────────────────────────────────────

def test_les_statistiques_comptent_ce_quelles_annoncent(db):
    _dorra_enregistree(db, [
        _p('أوّل', 'العريف', '1'),
        _p('ثان',  'العميد', '2')], titre='دورة أولى')
    s = db.get_stats_avancees()
    assert s['dorrat'] == 1
    assert s['dorrat_finalisees'] == 1
    assert s['participations'] == 2
    assert s['par_classe']['ج'] == 1
    assert s['par_classe']['أ1'] == 1
    # Les mois sont rendus dans l'ordre du calendrier, pas par volume.
    assert [mois for mois, _n in s['par_mois']][:3] == ['جانفي', 'فيفري', 'مارس']


def test_la_lوحة_des_مستحقات_compte_les_dorrat(db):
    _dorra_enregistree(db, [_p('صالح', 'المقدم', '1')])
    s = db.get_stats_mustahaqqat()
    assert s['dorrat_enregistrees'] == 1
    assert s['dorrat_ghayr'] == 1
    assert s['dorrat_manjaza'] == 0


def test_la_liste_des_مكونين_recense_les_dorrat_enregistrees(db):
    _dorra_enregistree(db, [_p('صالح', 'المقدم', '1')], titre='أولى')
    _dorra_enregistree(db, [_p('محمد', 'العريف', '2')], titre='ثانية')
    formateurs = db.get_formateurs_mustahaqqat()
    assert len(formateurs) == 1
    assert formateurs[0]['nom_formateur'] == 'زياد البوهلالي'
    assert formateurs[0]['nb_dorrat'] == 2
    assert formateurs[0]['nb_restantes'] == 2
