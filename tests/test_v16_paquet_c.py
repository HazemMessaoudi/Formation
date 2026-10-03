import json
# -*- coding: utf-8 -*-
"""v1.6 — الحزمة ج : الجنس + الفئة العمريّة (مكوّنون ومشاركون).

Ces deux خانات servent AUX إحصائيات SEULEMENT, affichées sur demande ; elles
ne doivent jamais toucher la forme ni l'ordre des وثائق.

Données de test FICTIVES uniquement."""
import re

import pytest

from core import validation as val

JETON = {'X-CSRF-Token': 'jeton-de-test'}
H, F = 'ذكر', 'أنثى'
JEUNE, AGE = 'أقلّ من 40 سنة', '40 سنة وأكثر'
MSG_SEXE = val.CHOIX['sexe'][1]
MSG_FIAA = val.CHOIX['fiaa_omria'][1]


def _q(db, sql, args=()):
    conn = db.get_connection()
    try:
        return [dict(r) for r in conn.execute(sql, args).fetchall()]
    finally:
        conn.close()


# ─── 1. Le validateur ────────────────────────────────────────────────────────

def test_listes_fermees():
    assert val.SEXES == (H, F)
    assert val.FIAAT == (JEUNE, AGE)


@pytest.mark.parametrize('champ, valeur, ok', [
    ('sexe', '', True), ('sexe', None, True), ('sexe', '  ', True),
    ('sexe', H, True), ('sexe', F, True), ('sexe', f' {F} ', True),
    ('sexe', 'M', False), ('sexe', 'ذكور', False), ('sexe', 0, False),
    ('fiaa_omria', '', True), ('fiaa_omria', JEUNE, True), ('fiaa_omria', AGE, True),
    ('fiaa_omria', '35', False), ('fiaa_omria', 'أقل من 40 سنة', False),
])
def test_erreur_choix(champ, valeur, ok):
    assert (val.erreur_choix(champ, valeur) is None) is ok


def test_verifier_choix_nettoie_et_ignore_l_absent():
    d = {'sexe': f' {H} ', 'fiaa_omria': None}
    assert val.verifier_choix(d) == [] and d == {'sexe': H, 'fiaa_omria': ''}
    d = {'nom': 'x'}
    assert val.verifier_choix(d) == [] and d == {'nom': 'x'}
    d = {'sexe': 'X', 'fiaa_omria': 'Y'}
    assert val.verifier_choix(d) == [MSG_SEXE, MSG_FIAA]


# ─── 2. Schéma ───────────────────────────────────────────────────────────────

def test_colonnes_presentes(db):
    for table in ('mkowin', 'participants'):
        cols = {r['name'] for r in _q(db, f'PRAGMA table_info({table})')}
        assert {'sexe', 'fiaa_omria'} <= cols, table


def test_migration_idempotente(db):
    db.init_db()
    db.init_db()
    cols = [r['name'] for r in _q(db, 'PRAGMA table_info(participants)')]
    assert cols.count('fiaa_omria') == 1


# ─── 3. Fiche مكوّن ──────────────────────────────────────────────────────────

def _form(**k):
    return {'_csrf': 'jeton-de-test', 'grade': 'مقدم', 'nom': 'تجربة',
            'prenom': 'وهمي', **k}


def test_formulaire_ajout_propose_les_deux_listes(client):
    html = client.get('/mkowin/ajouter').get_data(as_text=True)
    for v in (H, F, JEUNE, AGE):
        assert f'<option value="{v}"' in html
    assert 'name="sexe"' in html and 'name="fiaa_omria"' in html


def test_ajout_avec_valeurs(client, db):
    r = client.post('/mkowin/ajouter', data=_form(sexe=F, fiaa_omria=AGE))
    assert r.status_code == 302
    m = _q(db, "SELECT sexe, fiaa_omria FROM mkowin WHERE nom='تجربة'")[0]
    assert m == {'sexe': F, 'fiaa_omria': AGE}


def test_ajout_sans_valeurs_permis(client, db):
    r = client.post('/mkowin/ajouter', data=_form(sexe='', fiaa_omria=''))
    assert r.status_code == 302
    m = _q(db, "SELECT sexe, fiaa_omria FROM mkowin WHERE nom='تجربة'")[0]
    assert (m['sexe'] or '') == '' and (m['fiaa_omria'] or '') == ''


@pytest.mark.parametrize('champ, valeur, msg', [
    ('sexe', 'M', MSG_SEXE), ('fiaa_omria', '33 سنة', MSG_FIAA)])
def test_ajout_refuse_valeur_hors_liste(client, db, champ, valeur, msg):
    r = client.post('/mkowin/ajouter', data=_form(**{champ: valeur}))
    assert r.status_code == 200 and msg in r.get_data(as_text=True)
    assert _q(db, "SELECT id FROM mkowin WHERE nom='تجربة'") == []


def _mkow(db, **k):
    db.add_mkow({'grade': 'مقدم', 'nom': 'تجربة', 'prenom': 'وهمي', **k})
    return _q(db, "SELECT id FROM mkowin WHERE nom='تجربة'")[0]['id']


def test_modification_et_fiche(client, db):
    mid = _mkow(db)
    r = client.post(f'/mkowin/{mid}/modifier', data=_form(sexe=H, fiaa_omria=JEUNE))
    assert r.status_code == 302
    m = _q(db, 'SELECT sexe, fiaa_omria FROM mkowin WHERE id=?', (mid,))[0]
    assert m == {'sexe': H, 'fiaa_omria': JEUNE}
    fiche = client.get(f'/mkowin/{mid}').get_data(as_text=True)
    assert 'الجنس' in fiche and H in fiche and JEUNE in fiche
    # Le formulaire de modification présélectionne les valeurs.
    html = client.get(f'/mkowin/{mid}/modifier').get_data(as_text=True)
    assert re.search(rf'<option value="{H}"\s+selected', html)
    assert re.search(rf'<option value="{JEUNE}"\s+selected', html)


def test_modification_refuse_et_garde_l_ancien(client, db):
    mid = _mkow(db, sexe=F, fiaa_omria=AGE)
    r = client.post(f'/mkowin/{mid}/modifier', data=_form(sexe='ZZ', fiaa_omria=AGE))
    assert r.status_code == 200 and MSG_SEXE in r.get_data(as_text=True)
    m = _q(db, 'SELECT sexe FROM mkowin WHERE id=?', (mid,))[0]
    assert m['sexe'] == F


def test_formulaire_sans_les_champs_ne_les_efface_pas(client, db):
    """Ce qui n'est pas soumis n'est pas écrit."""
    mid = _mkow(db, sexe=F, fiaa_omria=AGE)
    r = client.post(f'/mkowin/{mid}/modifier', data=_form(adresse='نهج وهمي'))
    assert r.status_code == 302
    m = _q(db, 'SELECT sexe, fiaa_omria FROM mkowin WHERE id=?', (mid,))[0]
    assert m == {'sexe': F, 'fiaa_omria': AGE}


def test_liste_json_publique_porte_les_champs(db):
    from core.db.mkowin import CHAMPS_MKOW_PUBLICS
    assert 'sexe' in CHAMPS_MKOW_PUBLICS and 'fiaa_omria' in CHAMPS_MKOW_PUBLICS


# ─── 4. Participants ─────────────────────────────────────────────────────────

def _url(p):
    return f"/lettre/{p['lettre_id']}/formations/{p['formation_id']}/participants"


def _part(nom, uid, **k):
    return {'nom_prenom': nom, 'grade': 'ملازم', 'identifiant_unique': uid,
            'lieu_travail': 'مكتب وهمي', 'jiha_marjiiya': '', **k}


def test_api_enregistre_et_relit(client, db, programme):
    r = client.post(_url(programme), headers=JETON, json={'participants': [
        _part('مشارك أوّل', '9000001', sexe=H, fiaa_omria=JEUNE),
        _part('مشاركة ثانية', '9000002', sexe=F, fiaa_omria=AGE)]})
    assert r.status_code == 200, r.get_json()
    parts = client.get(_url(programme)).get_json()['participants']
    assert [(p['sexe'], p['fiaa_omria']) for p in parts] == [(H, JEUNE), (F, AGE)]


def test_api_sexe_et_fiaa_obligatoires(client, db, programme):
    # v1.7.1 : الجنس et الفئة العمريّة sont obligatoires pour chaque participant
    r = client.post(_url(programme), headers=JETON, json={'participants': [
        _part('مشارك ثالث', '9000003', fiaa_omria=JEUNE)]})
    assert r.status_code == 400 and 'يجب اختيار الجنس' in r.get_json()['erreur']
    r = client.post(_url(programme), headers=JETON, json={'participants': [
        _part('مشارك ثالث', '9000003', sexe=H)]})
    assert r.status_code == 400 and 'يجب اختيار الفئة العمريّة' in r.get_json()['erreur']
    assert _q(db, 'SELECT id FROM participants') == []


@pytest.mark.parametrize('k, msg', [
    ({'sexe': 'رجل'}, MSG_SEXE), ({'fiaa_omria': 'شباب'}, MSG_FIAA),
    ({'sexe': 1}, MSG_SEXE)])
def test_api_refuse_valeur_hors_liste(client, db, programme, k, msg):
    valides = {'sexe': H, 'fiaa_omria': JEUNE, **k}
    r = client.post(_url(programme), headers=JETON, json={'participants': [
        _part('مشارك أوّل', '9000001', **valides)]})
    assert r.status_code == 400
    assert msg in r.get_json()['erreur'] and 'مشارك أوّل' in r.get_json()['erreur']
    assert _q(db, 'SELECT id FROM participants') == []


def test_save_participants_direct(db, programme):
    assert db.save_participants(programme['lettre_id'], programme['formation_id'],
                                [_part('س', '1', sexe=F), _part('ع', '2', sexe=None)])
    rows = _q(db, 'SELECT sexe, fiaa_omria FROM participants ORDER BY ordre')
    assert rows == [{'sexe': F, 'fiaa_omria': ''}, {'sexe': '', 'fiaa_omria': ''}]


def test_page_programme_expose_les_listes(client, db, programme):
    for url in ('/lettre/nouvelle', f"/lettre/nouvelle?modifier={programme['lettre_id']}"):
        r = client.get(url)
        assert r.status_code == 200, url
        from tests.conftest import js_programme
        html = r.get_data(as_text=True) + js_programme()
        assert 'SEXES_INIT' in html and 'FIAAT_INIT' in html
        assert 'p-sexe' in html and 'p-fiaa' in html
        m_s = re.search(r'const SEXES_INIT = (\[.*?\]);', html)
        m_f = re.search(r'const FIAAT_INIT = (\[.*?\]);', html)
        assert json.loads(m_s.group(1)) == ['ذكر', 'أنثى']
        assert json.loads(m_f.group(1)) == ['أقلّ من 40 سنة', '40 سنة وأكثر']


# ─── 5. إحصائيات ─────────────────────────────────────────────────────────────

def test_stats_repartition(db, programme):
    db.save_participants(programme['lettre_id'], programme['formation_id'], [
        _part('أ', '1', sexe=H, fiaa_omria=AGE), _part('ب', '2', sexe=H),
        _part('ج', '3', sexe=F, fiaa_omria=JEUNE), _part('د', '4')])
    _mkow(db, sexe=F, fiaa_omria=JEUNE)
    s = db.get_stats_avancees()
    assert s['par_sexe_participants'] == [(H, 2), (F, 1), ('غير محدّد', 1)]
    assert s['par_fiaa_participants'] == [(JEUNE, 1), (AGE, 1), ('غير محدّد', 2)]
    assert s['par_sexe_mkowin'][:2] == [(H, 0), (F, 1)]
    assert s['par_fiaa_mkowin'][:2] == [(JEUNE, 1), (AGE, 0)]


def test_stats_base_vide(db):
    s = db.get_stats_avancees()
    assert s['par_sexe_participants'] == [(H, 0), (F, 0)]
    assert s['par_fiaa_participants'] == [(JEUNE, 0), (AGE, 0)]


def test_page_stats_bloc_toujours_visible(client, db, programme):
    """v1.6.1 : الجنس / الفئة العمريّة toujours affichés (plus de bouton), et
    les deux tableaux « الأسماء المسجّلة حسب … » ont disparu."""
    db.save_participants(programme['lettre_id'], programme['formation_id'],
                         [_part('أ', '1', sexe=H, fiaa_omria=AGE)])
    html = client.get('/statistiques').get_data(as_text=True)
    assert 'id="btnSexeFiaa"' not in html
    assert 'id="blocSexeFiaa"' in html and '<div id="blocSexeFiaa" hidden>' not in html
    debut = html.index('id="blocSexeFiaa"')
    contenu = html[debut:html.index('لا تظهر في وثائق الدورة', debut)]
    for titre in ('المشاركون حسب الجنس', 'المشاركون حسب الفئة العمريّة'):
        assert titre in contenu
    assert 'الأسماء المسجّلة حسب الجنس' not in html
    assert 'الأسماء المسجّلة حسب الفئة العمريّة' not in html
    # Et rien dans le عرض تلقائي.
    viz = re.search(r'id="viz-data"[^>]*>(.*?)</script>', html, re.S)
    assert viz
    donnees = json.loads(viz.group(1))
    assert set(donnees) == {'mois', 'annee', 'classes', 'grades', 'types', 'formateurs'}
    brut = json.dumps(donnees, ensure_ascii=False)
    assert H not in brut and AGE not in brut


# ─── 6. Les وثائق ne bougent pas ─────────────────────────────────────────────

def test_pdf_participants_ignore_les_nouveaux_champs():
    import inspect
    from core import pdf_generator
    src = inspect.getsource(pdf_generator)
    assert 'fiaa_omria' not in src and "'sexe'" not in src and '"sexe"' not in src
