# -*- coding: utf-8 -*-
"""Non-régression de l'audit v1.4e : chaque test rejoue un défaut réellement
reproduit pendant l'audit et vérifie qu'il ne revient pas."""
import pytest

from tests.conftest import _client_flask

JETON = {'X-CSRF-Token': 'jeton-de-test'}


# ─── Aides ───────────────────────────────────────────────────────────────────

def _q(db, sql, *a):
    c = db.get_connection()
    try:
        return [dict(r) for r in c.execute(sql, a).fetchall()]
    finally:
        c.close()


def _ouvrir_annee(db, annee):
    from core import exercice as ex
    c = db.get_connection()
    ex.definir_annee(c, annee)
    for t in ('interne', 'externe'):
        c.execute('INSERT OR IGNORE INTO compteurs VALUES (?,?,0)', (annee, t))
    c.commit()
    c.close()


def _agent(db, monkeypatch):
    db.update_config('installation_faite', '1')
    return _client_flask(db, monkeypatch, 'user')


def _dorra_finalisee(db, grades=('العريف', 'العريف', 'الرقيب'), trainer_grade='مقدم',
                     rows=None, participants=None):
    lid = db.save_programme('interne', 'أكتوبر', 2026, [{
        'titre': 'تحرير المحاضر', 'grade': trainer_grade, 'nom_formateur': 'البوهلالي زياد',
        'lieu_travail': 'x', 'date_formation': '2026-10-21', 'periode': '',
        'lieu_formation': 'قاعة 1'}], 'n', 't')
    db.verrouiller_lettre(lid, 'interne')
    fid = db.get_lettre_detail(lid)['formations'][0]['id']
    db.save_participants(lid, fid, participants or [
        {'nom_prenom': f'p{i}', 'grade': g, 'identifiant_unique': str(1000 + i)}
        for i, g in enumerate(grades)])
    db.save_bataqa_data(fid, {})
    db.save_programme_data(fid, {'rows': rows or [
        {'type': 'row', 'time_debut': '08:30', 'time_fin': '11:45',
         'activity': 'a', 'participants': 'b'}]})
    db.save_memo_data(fid, {'objet': 'm', 'corps': 'c', 'moujah': [{'nom': 'x'}]},
                      confirmer=True)
    assert db.finaliser_formation(fid)[0]
    db.save_muqarrar_dorra(fid, '12', '2026-10-01')
    return lid, fid


# ─── C1 : compteurs par année ────────────────────────────────────────────────

def test_redemarrage_ne_reporte_pas_le_compteur_de_lannee_passee(db):
    for i in range(3):
        lid = db.save_lettre_libre('interne', 'أكتوبر', 2026, 'd', f'o{i}', 'c', 'n', 't')
        db.verrouiller_lettre(lid, 'interne')
    _ouvrir_annee(db, 2027)
    db.init_db()
    assert db.prochain_numero_prevu('interne') == 1


# ─── C2 : un عدد libéré retourne dans SA série ───────────────────────────────

def test_fsakh_dune_dorra_de_2026_ne_touche_pas_2027(db):
    lid = db.save_programme('interne', 'ديسمبر', 2026, [
        {'titre': 'A', 'date_formation': '2026-12-20', 'lieu_formation': 'q1'},
        {'titre': 'B', 'date_formation': '2026-12-21', 'lieu_formation': 'q1'}], 'n', 't')
    db.verrouiller_lettre(lid, 'interne')
    f1 = db.get_lettre_detail(lid)['formations'][0]['id']
    db.save_memo_data(f1, {'objet': 'm', 'corps': 'c', 'moujah': [{'nom': 'x'}]},
                      confirmer=True)
    _ouvrir_annee(db, 2027)
    for o in 'AB':
        l2 = db.save_lettre_libre('interne', 'جانفي', 2027, 'd', o, 'c', 'n', 't')
        db.verrouiller_lettre(l2, 'interne')
    db.annuler_dorra(f1)
    pool = _q(db, 'SELECT annee FROM numeros_liberes')
    assert all(p['annee'] == 2026 for p in pool)
    assert [r['numero'] for r in _q(db, 'SELECT numero FROM registre WHERE annee=2027 '
                                        'ORDER BY numero')] == [1, 2]
    assert db.prochain_numero_prevu('interne') == 3


def test_lancien_index_unique_type_numero_est_supprime(db):
    db.init_db()
    noms = {r['name'] for r in _q(db, "SELECT name FROM sqlite_master WHERE type='index'")}
    assert 'idx_registre_type_numero' not in noms


# ─── C4 : confirmation d'une مراسلة d'une autre année ─────────────────────────

def test_confirmation_hors_annee_refusee_sans_bloquer_la_base(db):
    a = db.save_lettre_libre('interne', 'جانفي', 2027, 'd', 'A', 'c', 'n', 't')
    assert db.verrouiller_lettre(a, 'interne') == (None, None)
    _ouvrir_annee(db, 2027)
    b = db.save_lettre_libre('interne', 'جانفي', 2027, 'd', 'B', 'c', 'n', 't')
    ref, num = db.verrouiller_lettre(b, 'interne')
    assert ref and num == 1


# ─── H5 : un agent ne change pas le mot de passe d'un autre ───────────────────

def test_agent_ne_peut_pas_changer_le_mdp_du_mushrif(db, monkeypatch):
    _client_flask(db, monkeypatch, 'admin')
    c = _agent(db, monkeypatch)
    r = c.post('/api/users/changer-mdp', headers=JETON,
               json={'username': 'admin', 'new_password': 'pwned1'})
    assert r.status_code in (302, 403)
    assert not db.check_credentials('admin', 'pwned1')


# ─── H6 / H7 : الصنف suit ورقة الحضور ─────────────────────────────────────────

def test_classe_forgee_refusee(db, monkeypatch):
    c = _agent(db, monkeypatch)
    _, fid = _dorra_finalisee(db)
    ids = [p['id'] for p in db.get_hodour(fid)]
    c.post(f'/mustahaqqat/dorra/{fid}/hodour', headers=JETON,
           json={'presences': {str(i): True for i in ids}})
    r = c.post(f'/mustahaqqat/dorra/{fid}/classe', headers=JETON, json={'classe': 'أ1'})
    assert r.status_code == 400
    assert _q(db, 'SELECT classe FROM mustahaqqat')[0]['classe'] in ('', None)


def test_nouveau_pointage_annule_la_classe_confirmee(db, monkeypatch):
    c = _agent(db, monkeypatch)
    _, fid = _dorra_finalisee(db, grades=('المقدم', 'المقدم', 'العريف', 'العريف', 'العريف'))
    ids = [p['id'] for p in db.get_hodour(fid)]
    pr = {str(ids[0]): False, str(ids[1]): False, **{str(i): True for i in ids[2:]}}
    c.post(f'/mustahaqqat/dorra/{fid}/hodour', headers=JETON, json={'presences': pr})
    auto = _q(db, 'SELECT classe_auto FROM mustahaqqat')[0]['classe_auto']
    assert c.post(f'/mustahaqqat/dorra/{fid}/classe', headers=JETON,
                  json={'classe': auto}).get_json()['succes']
    pr = {str(ids[0]): True, str(ids[1]): True, **{str(i): False for i in ids[2:]}}
    c.post(f'/mustahaqqat/dorra/{fid}/hodour', headers=JETON, json={'presences': pr})
    etat = _q(db, 'SELECT etat, classe FROM mustahaqqat')[0]
    assert etat['classe'] in ('', None) and etat['etat'] != 'classe'
    j = c.post(f'/mustahaqqat/dorra/{fid}/qima', headers=JETON).get_json() or {}
    assert not j.get('succes')


# ─── H8 : homonymes dans وثائق الخلاص ────────────────────────────────────────

def test_homonymes_departages_par_la_rutba(db, monkeypatch):
    c = _agent(db, monkeypatch)
    db.add_mkow({'grade': 'الرائد', 'nom': 'البوهلالي', 'prenom': 'زياد',
                 'cin': '11111111', 'num_compte': 'RIB-1'})
    db.add_mkow({'grade': 'المقدم', 'nom': 'البوهلالي', 'prenom': 'زياد',
                 'cin': '22222222', 'num_compte': 'RIB-2'})
    _, fid = _dorra_finalisee(db, trainer_grade='المقدم')
    from core import khalas
    assert khalas.assembler(fid)['cin'] == '22222222'
    c.post(f'/mustahaqqat/dorra/{fid}/khalas/save', headers=JETON, json={'num_compte': '99999999999999999999'})
    comptes = {r['cin']: r['num_compte'] for r in _q(db, 'SELECT cin, num_compte FROM mkowin')}
    assert comptes == {'11111111': 'RIB-1', '22222222': '99999999999999999999'}


def test_homonymes_indiscernables_rien_ecrit(db, monkeypatch):
    c = _agent(db, monkeypatch)
    for cin in ('11111111', '22222222'):
        db.add_mkow({'grade': 'المقدم', 'nom': 'البوهلالي', 'prenom': 'زياد',
                     'cin': cin, 'num_compte': 'RIB-' + cin})
    _, fid = _dorra_finalisee(db, trainer_grade='المقدم')
    j = c.post(f'/mustahaqqat/dorra/{fid}/khalas/save', headers=JETON,
               json={'num_compte': '99999999999999999999'}).get_json()
    assert j.get('avertissement')
    assert '99999999999999999999' not in {r['num_compte'] for r in _q(db, 'SELECT num_compte FROM mkowin')}
    assert len(_q(db, 'SELECT id FROM mkowin')) == 2


# ─── M9 : programme scellé → plus de nouveau عدد ─────────────────────────────

def test_programme_scelle_ne_tire_plus_de_numero_dr(db, monkeypatch):
    c = _agent(db, monkeypatch)
    lid, _ = _dorra_finalisee(db)
    assert db.sceller_programme(lid)[0]
    avant = len(_q(db, 'SELECT id FROM registre'))
    for dest in ('المدير الجهوي للديوانة بالقصرين', 'x'):
        c.get(f'/lettre/{lid}/generer-directeur-regional',
              query_string={'destination': dest, 'type_mr': 'interne'})
    r = c.post(f'/lettre/{lid}/dr/attribuer', headers=JETON,
               json={'destination': 'y', 'type_mr': 'interne'})
    assert r.status_code == 400
    assert len(_q(db, 'SELECT id FROM registre')) == avant
    assert db.verifier_integrite_programme(lid) == []


def test_point_final_ne_coute_pas_un_numero(db):
    lid, _ = _dorra_finalisee(db)
    a = db.attribuer_numero_dr(lid, 'interne', 'المدير الجهوي بالقصرين')
    b = db.attribuer_numero_dr(lid, 'interne', 'المدير الجهوي بالقصرين.')
    assert a[0] == b[0] and b[3] is True


# ─── M11 : وثائق الخلاص après المصادقة seulement ──────────────────────────────

def test_documents_de_khalas_refuses_avant_approbation(db, monkeypatch):
    c = _agent(db, monkeypatch)
    _, fid = _dorra_finalisee(db)
    for url in (f'/mustahaqqat/dorra/{fid}/khalas',
                f'/mustahaqqat/dorra/{fid}/khalas/pdf',
                f'/mustahaqqat/dorra/{fid}/khalas/pdf/all?dl=1'):
        r = c.get(url)
        assert r.status_code == 302 and r.mimetype != 'application/pdf'


# ─── E1 : مكوّن absent de قائمة الأسماء ───────────────────────────────────────

def test_confirmation_refusee_pour_un_mkow_inconnu(db, client):
    lid = db.save_programme('interne', 'أكتوبر', 2026, [{
        'titre': 't', 'grade': 'مقدم', 'nom_formateur': 'مجهول فلان',
        'date_formation': '2026-10-21', 'lieu_formation': 'q'}], 'n', 't')
    r = client.post(f'/lettre/{lid}/valider', headers=JETON, json={'type': 'interne'})
    assert r.status_code == 400 and 'مجهول فلان' in r.get_json()['erreur']
    db.add_mkow({'grade': 'مقدم', 'nom': 'مجهول', 'prenom': 'فلان'})
    r = client.post(f'/lettre/{lid}/valider', headers=JETON, json={'type': 'interne'})
    assert r.status_code == 200


# ─── Saisies invalides : 400, jamais 500 ─────────────────────────────────────

@pytest.mark.parametrize('url,corps', [
    ('/lettre/enregistrer', {'annee': 'abc', 'formations': []}),
    ('/lettre/libre/enregistrer', {'annee': 'x'}),
    ('/lettre/enregistrer', {'annee': 2026, 'formations': ['x']}),
    ('/lettre/{lid}/mettre-a-jour', {'annee': '2026x'}),
    ('/lettre/{lid}/valider', {'type': 'foo'}),
    ('/lettre/{lid}/formations/{fid}/participants', {'participants': ['x']}),
    ('/lettre/{lid}/formations/{fid}/participants', {'participants': 'x'}),
])
def test_saisie_invalide_donne_400(db, client, programme, url, corps):
    url = url.format(lid=programme['lettre_id'], fid=programme['formation_id'])
    assert client.post(url, headers=JETON, json=corps).status_code == 400


def test_annee_absente_prend_lannee_courante(db, client):
    r = client.post('/lettre/libre/enregistrer', headers=JETON, json={'annee': None})
    assert r.status_code == 200


# ─── Montant en toutes lettres ───────────────────────────────────────────────

@pytest.mark.parametrize('montant,texte', [
    (1, 'دينار واحد'), (2, 'ديناران'), (3, 'ثلاثة دنانير'), (10, 'عشرة دنانير'),
    (11, 'أحد عشر دينارا'), (24, 'أربعة وعشرون دينارا'), (100, 'مائة دينار'),
    (103, 'مائة وثلاثة دنانير'), (250, 'مائتان وخمسون دينارا'), (1000, 'ألف دينار'),
    (2000, 'ألفا دينار'), (3000, 'ثلاثة آلاف دينار'), (12000, 'اثنا عشر ألف دينار'),
    (1500, 'ألف وخمسمائة دينار'), (0.25, 'مائتان وخمسون مليما'),
    (45.002, 'خمسة وأربعون دينارا ومليمان'),
])
def test_montant_en_lettres(montant, texte):
    from core.khalas import montant_lettres
    assert montant_lettres(montant) == texte


# ─── Graphies des رتب ─────────────────────────────────────────────────────────

@pytest.mark.parametrize('grade,classe,groupe', [
    ('ملازم أول صنف أ2 للديوانة', 'أ2', 'III'),
    ('الملازم أول صنف 2', 'أ2', 'III'),
    ('ملازم أول صنف أ1', 'أ1', 'III'),
    ('ملازم أول', 'أ1', 'III'),
])
def test_graphies_du_grade_de_mulazim_awwal(grade, classe, groupe):
    from core import mustahaqqat, bareme_mali
    assert mustahaqqat.classe_du_grade(grade) == classe
    assert bareme_mali.groupe_du_grade(grade) == groupe


def test_tri_des_mkowin_par_rutba_quelle_que_soit_la_graphie(db):
    for g, n in (('عريف للديوانة', 'c'), ('النقيب', 'b'), ('عميد للديوانة', 'a'),
                 ('ملازم أول صنف أ2 للديوانة', 'd')):
        db.add_mkow({'grade': g, 'nom': n, 'prenom': 'x'})
    assert [m['nom'] for m in db.get_mkowin()] == ['a', 'b', 'd', 'c']


# ─── Documents : الإدارة الجهويّة, المذكّرة ────────────────────────────────────

def test_admin_regionale_jamais_vide_si_la_ville_est_connue():
    from core import identite
    assert identite.admin_regionale({'ville_centre': 'القصرين'}) == \
        'الإدارة الجهويّة للدّيوانة بالقصرين'
    assert identite.admin_regionale({'admin_regionale': 'X'}) == 'X'


def test_destinataires_suivent_les_jihat_des_participants(db):
    lid, fid = _dorra_finalisee(db, participants=[
        {'nom_prenom': 'a', 'grade': 'العريف', 'identifiant_unique': '1',
         'jiha_marjiiya': 'الإدارة الجهويّة للدّيوانة بسيدي بوزيد'},
        {'nom_prenom': 'b', 'grade': 'العريف', 'identifiant_unique': '2',
         'jiha_marjiiya': 'الوحدة الجهويّة للحرس الدّيواني بالقصرين'}])
    c = db.get_connection()
    c.execute('DELETE FROM memo_formations')
    c.commit()
    c.close()
    noms = [m['nom'] for m in db.get_memo_data(lid, fid)['moujah']]
    assert 'السيّد المدير الجهوي للدّيوانة بسيدي بوزيد' in noms
    assert 'السيّد رئيس الوحدة الجهويّة للحرس الدّيواني بالقصرين' in noms


def test_heure_de_la_memo_vient_du_programme(db):
    lid, fid = _dorra_finalisee(db, rows=[
        {'type': 'row', 'time_debut': '09:00', 'time_fin': '11:00', 'activity': 'a',
         'participants': 'b'}])
    c = db.get_connection()
    c.execute('DELETE FROM memo_formations')
    c.commit()
    c.close()
    assert db.get_memo_data(lid, fid)['heure_debut'] == '09:00'


# ─── سجلّ التّدقيق ─────────────────────────────────────────────────────────────

def test_ajout_dun_mkow_journalise(db, client):
    r = client.post('/mkowin/ajouter', data={'_csrf': 'jeton-de-test', 'grade': 'مقدم',
                                             'nom': 'تجربة', 'prenom': 'سجل'})
    assert r.status_code == 302
    actions = [j['action'] for j in _q(db, 'SELECT action FROM journal')]
    assert 'إضافة مكوّن' in actions


def test_numero_de_version():
    from core import identite
    # 1.0 : numérotation repartie de 1.0 à la mise en service (aucun code ne
    # compare les versions : affichage et ?v= contre le cache seulement).
    assert identite.VERSION_APP and identite.VERSION_APP in identite.VERSION_LABEL


def test_un_maktab_releve_de_sa_propre_direction_regionale():
    from core import arabe
    r = arabe.rattachement_services(
        [('مكتب الديوانة بسيدي بوزيد', 'الإدارة الجهويّة للدّيوانة بسيدي بوزيد'),
         ('مكتب الديوانة بفريانة', '')],
        admin_regionale='الإدارة الجهويّة للدّيوانة بالقصرين')
    assert r['entites'] == ['الإدارة الجهويّة للدّيوانة بسيدي بوزيد',
                            'الإدارة الجهويّة للدّيوانة بالقصرين']
