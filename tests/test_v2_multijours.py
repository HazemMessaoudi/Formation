# -*- coding: utf-8 -*-
"""V2 — الدّورات متعدّدة الأيّام : règles, schéma, برنامج jour par jour,
ورقة الحضور par jour, صنف pondéré, heures, documents PDF / Word.

Données FICTIVES uniquement (noms et معرّفات inventés)."""
import io
import re
import zipfile

import pytest

from core import jours as J

CSRF = {'X-CSRF-Token': 'jeton-de-test'}


# ═══ 1. Règles pures (core/jours.py) ═════════════════════════════════════════

def test_un_jour_sans_fin():
    assert J.jours_de_la_dorra('2026-10-12') == ['2026-10-12']
    assert J.jours_de_la_dorra('2026-10-12', '2026-10-12') == ['2026-10-12']
    assert not J.est_multi_jours('2026-10-12', '')
    assert J.normaliser_fin('2026-10-12', '2026-10-12') == ''
    assert J.normaliser_fin('2026-10-12', '') == ''


def test_trois_jours_et_dimanche_saute():
    assert J.jours_de_la_dorra('2026-10-12', '2026-10-14') == \
        ['2026-10-12', '2026-10-13', '2026-10-14']
    # jeudi 15 → mardi 20 : le dimanche 18 n'est pas un jour de formation
    js = J.jours_de_la_dorra('2026-10-15', '2026-10-20')
    assert '2026-10-18' not in js and len(js) == 5
    assert J.nombre_de_jours('2026-10-15', '2026-10-20') == 5


def test_maximum_six_jours():
    assert J.verifier_plage('د', '2026-10-12', '2026-10-17') == []      # lundi → samedi
    err = J.verifier_plage('د', '2026-10-12', '2026-10-20')
    assert err and 'الحدّ الأقصى 6' in err[0]
    assert len(J.jours_de_la_dorra('2026-10-12', '2026-10-24')) == 6    # tronqué


def test_fin_avant_debut_refusee_et_gardee():
    assert J.normaliser_fin('2026-10-14', '2026-10-12') == '2026-10-12'
    assert 'يسبق' in J.verifier_plage('د', '2026-10-14', '2026-10-12')[0]
    assert J.jours_de_la_dorra('2026-10-14', '2026-10-12') == ['2026-10-14']


def test_textes_de_periode():
    assert J.plage_longue('2026-10-12', '2026-10-14') == 'من 12 إلى 14 أكتوبر 2026'
    assert J.plage_longue('2026-10-12', '2026-10-14', 'يوم') == \
        'من يوم 12 إلى يوم 14 أكتوبر 2026'
    assert J.plage_longue('2026-10-29', '2026-11-03') == 'من 29 أكتوبر إلى 3 نوفمبر 2026'
    assert J.plage_longue('2026-12-30', '2027-01-02') == \
        'من 30 ديسمبر 2026 إلى 2 جانفي 2027'
    assert J.plage_longue('2026-10-12') == '12 أكتوبر 2026'
    assert J.plage_slash('2026-10-12', '2026-10-14') == 'من 2026/10/12 إلى 2026/10/14'
    assert J.plage_iso('2026-10-12', '2026-10-14') == '2026-10-12 → 2026-10-14'
    assert J.libelle_jour(1) == 'اليوم الأوّل' and J.libelle_jour(6) == 'اليوم السادس'


def test_segmentation_des_lignes():
    rows = [{'type': 'date_header', 'jour': 1, 'date': '2026-10-12', 'periode': 'صباحا'},
            {'type': 'row', 'activity': 'أ'},
            {'type': 'date_header', 'jour': 2, 'date': '2026-10-13', 'periode': 'مساءا'},
            {'type': 'row', 'activity': 'ب'}, {'type': 'row', 'activity': 'ج'}]
    seg = J.segmenter_lignes(rows)
    assert [len(s) for _, s in seg] == [1, 2] and seg[1][0]['periode'] == 'مساءا'
    assert J.est_programme_multi(rows)
    # ancienne ligne d'en-tête sans date : ignorée, un seul jour
    assert not J.est_programme_multi([{'type': 'date_header'}, {'type': 'row'}])
    assert len(J.segmenter_lignes([{'type': 'date_header'}, {'type': 'row'}])) == 1


# ═══ 2. Schéma et migration ═════════════════════════════════════════════════

def test_schema_v2(db):
    conn = db.get_connection()
    try:
        cols = {c['name'] for c in conn.execute('PRAGMA table_info(formations)')}
        tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    finally:
        conn.close()
    assert 'date_fin' in cols
    assert {'programme_jours', 'mustahaqqat_hodour_jours'} <= tables
    assert db.version_schema() >= 19   # V3 : 20


def test_migration_d_une_base_1_7_2(db):
    """Une base sans date_fin ni tables V2 est complétée sans rien perdre."""
    conn = db.get_connection()
    try:
        conn.execute("INSERT INTO lettres (type, numero, ref_complet, mois, annee) "
                     "VALUES ('interne', 0, '', 'أكتوبر', 2026)")
        lid = conn.execute('SELECT MAX(id) FROM lettres').fetchone()[0]
        conn.execute("INSERT INTO formations (lettre_id, ordre, titre, date_formation) "
                     "VALUES (?, 1, 'دورة قديمة', '2026-10-05')", (lid,))
        conn.execute('DROP TABLE programme_jours')
        conn.execute('DROP TABLE mustahaqqat_hodour_jours')
        conn.execute('ALTER TABLE formations DROP COLUMN date_fin')
        conn.execute('PRAGMA user_version = 18')
        conn.commit()
    finally:
        conn.close()
    db.init_db()
    f = db.get_lettre_detail(lid)['formations'][0]
    assert f['titre'] == 'دورة قديمة' and (f['date_fin'] or '') == ''
    assert db.version_schema() >= 19   # V3 : 20


# ═══ 3. Saisie du برنامج (من … إلى …) ═══════════════════════════════════════

def _formation(debut, fin='', periode='صباحا', lieu='قاعة المحاضرات', titre='التصرّف في المخاطر',
               formateur='الورتاني سامي'):
    return {'titre': titre, 'grade': 'الرائد', 'nom_formateur': formateur,
            'lieu_travail': '', 'date_formation': debut, 'date_fin': fin,
            'periode': periode, 'lieu_formation': lieu}


def _post(client, url, payload):
    return client.post(url, json=payload, headers=CSRF)


def test_enregistrement_date_fin(client, db):
    r = _post(client, '/lettre/enregistrer', {
        'type': 'interne', 'mois': 'أكتوبر', 'annee': 2026,
        'formations': [_formation('2026-10-12', '2026-10-14'),
                       _formation('2026-10-21', '2026-10-21', lieu='قاعة أخرى')]})
    lid = r.get_json()['lettre_id']
    fs = db.get_lettre_detail(lid)['formations']
    assert fs[0]['date_fin'] == '2026-10-14'
    assert fs[1]['date_fin'] == ''                   # même jour = دورة d'un jour


def test_confirmation_refuse_plus_de_six_jours(client, db):
    annee = db.annee_registre()
    lid = db.save_programme('interne', 'أكتوبر', annee,
                            [_formation(f'{annee}-10-12', f'{annee}-10-20')], 'م', 'ن')
    r = _post(client, f'/lettre/{lid}/valider', {'type': 'interne'})
    assert r.status_code == 400 and 'الحدّ الأقصى 6' in r.get_json()['erreur']


def test_meme_salle_un_jour_interieur_refusee(client, db):
    _post(client, '/lettre/enregistrer', {
        'type': 'interne', 'mois': 'أكتوبر', 'annee': 2026,
        'formations': [_formation('2026-10-12', '2026-10-14')]})
    # une autre دورة le 13, même salle, même فترة : refus
    r = _post(client, '/lettre/enregistrer', {
        'type': 'interne', 'mois': 'أكتوبر', 'annee': 2026,
        'formations': [_formation('2026-10-13', titre='دورة أخرى', formateur='التليلي كريم')]})
    assert r.status_code == 400 and '2026-10-13' in r.get_json()['erreur']
    # l'après-midi, la salle est libre
    r = _post(client, '/lettre/enregistrer', {
        'type': 'interne', 'mois': 'أكتوبر', 'annee': 2026,
        'formations': [_formation('2026-10-13', periode='مساءا', titre='دورة أخرى',
                                  formateur='التليلي كريم')]})
    assert r.status_code == 200


def test_dorrat_meme_jour_voit_les_jours_interieurs(db):
    db.save_programme('interne', 'أكتوبر', 2026, [_formation('2026-10-12', '2026-10-14')], 'م', 'ن')
    assert [d['titre'] for d in db.dorrat_meme_jour('2026-10-13')] == ['التصرّف في المخاطر']
    assert db.dorrat_meme_jour('2026-10-15') == []


# ═══ 4. Une دورة de trois jours, de bout en bout ═════════════════════════════

PARTS = [
    {'nom_prenom': 'مشارك وهمي أوّل', 'grade': 'النقيب', 'identifiant_unique': '90100001',
     'lieu_travail': 'مكتب وهمي', 'sexe': 'ذكر', 'fiaa_omria': ''},
    {'nom_prenom': 'مشاركة وهمية ثانية', 'grade': 'العريف', 'identifiant_unique': '90100002',
     'lieu_travail': 'مكتب وهمي', 'sexe': 'أنثى', 'fiaa_omria': ''},
    {'nom_prenom': 'مشارك وهمي ثالث', 'grade': 'العريف', 'identifiant_unique': '90100003',
     'lieu_travail': 'فرقة وهمية', 'sexe': 'ذكر', 'fiaa_omria': ''},
]


def _lignes(debut='08:30', milieu='10:00', fin='12:15'):
    return [{'type': 'row', 'time_debut': debut, 'time_fin': milieu,
             'activity': 'تقديم الدورة', 'participants': 'الرائد الورتاني سامي'},
            {'type': 'row', 'time_debut': milieu, 'time_fin': fin,
             'activity': 'ورشة تطبيقية', 'participants': 'الرائد الورتاني سامي، النقيب القاسمي هالة'}]


def _dorra3(db, client=None, jusqu_a='programme'):
    annee = db.annee_registre()
    lid = db.save_programme('interne', 'أكتوبر', annee,
                            [_formation(f'{annee}-10-12', f'{annee}-10-14')], 'م', 'ن')
    db.verrouiller_lettre(lid, 'interne')
    fid = db.get_lettre_detail(lid)['formations'][0]['id']
    db.save_participants(lid, fid, PARTS)
    db.save_bataqa_data(fid, {'mustahdafun': 'ضبّاط وضبّاط صف', 'mahawer': 'محور',
                              'objectifs': 'هدف'})
    if jusqu_a == 'bataqa':
        return lid, fid
    for n, per in ((1, 'صباحا'), (2, 'مساءا'), (3, 'صباحا')):
        rows = _lignes() if per == 'صباحا' else _lignes('13:30', '15:00', '16:45')
        rows = [dict(r, time=f"من {r['time_debut']} إلى {r['time_fin']}") for r in rows]
        ok, info = db.save_programme_jour(fid, n, per, rows)
        assert ok, info
    return lid, fid


def test_programme_jour_par_jour_par_http(client, db):
    lid, fid = _dorra3(db, jusqu_a='bataqa')
    url = f'/lettre/{lid}/formations/{fid}'
    # l'ancienne route (برنامج d'un jour) refuse une دورة متعدّدة الأيّام
    r = _post(client, f'{url}/programme/data', {'rows': _lignes()})
    assert r.status_code == 400 and 'يومًا بيوم' in r.get_json()['erreur']
    # le jour 2 ne passe pas avant le jour 1
    r = _post(client, f'{url}/programme/jour/2', {'periode': 'صباحا', 'rows': _lignes()})
    assert r.status_code == 400 and 'اليوم الأوّل' in r.get_json()['erreur']
    r = _post(client, f'{url}/programme/jour/1', {'periode': 'صباحا', 'rows': _lignes()})
    d = r.get_json()
    assert d['succes'] and not d['termine'] and d['suivant'] == 2
    assert not db.etat_dorra(fid)['programme']          # étape 5 pas encore achevée
    # jour 2 l'après-midi : 08:30 est refusé, 13:30 accepté
    r = _post(client, f'{url}/programme/jour/2', {'periode': 'مساءا', 'rows': _lignes()})
    assert r.status_code == 400 and '13:30' in r.get_json()['erreur']
    r = _post(client, f'{url}/programme/jour/2',
              {'periode': 'مساءا', 'rows': _lignes('13:30', '15:00', '16:45')})
    assert r.get_json()['suivant'] == 3
    r = _post(client, f'{url}/programme/jour/3', {'periode': 'صباحا', 'rows': _lignes()})
    d = r.get_json()
    assert d['termine'] and d['suivant'] is None and d['nb_jours'] == 3
    assert db.etat_dorra(fid)['programme']              # étape 5 achevée
    # lecture : trois jours, périodes propres à chaque jour
    j = client.get(f'{url}/programme/jours').get_json()
    assert j['confirmed'] and [x['periode'] for x in j['jours']] == ['صباحا', 'مساءا', 'صباحا']
    assert all(x['confirmed'] and len(x['rows']) == 2 for x in j['jours'])
    prog = db.get_programme_data(lid, fid)
    assert prog['multi'] and sum(1 for r in prog['rows'] if r['type'] == 'date_header') == 3
    # un jour déjà confirmé peut être retouché tant que la دورة n'est pas enregistrée
    r = _post(client, f'{url}/programme/jour/1', {'periode': 'صباحا',
                                                  'rows': _lignes('08:00', '10:00', '12:00')})
    assert r.get_json()['termine']
    prog = db.get_programme_data(lid, fid)
    assert prog['jours'][0]['rows'][0]['time_debut'] == '08:00'


def test_heures_jour_par_jour():
    from core import bareme_mali as bm
    rows = [{'type': 'date_header', 'jour': 1, 'date': '2026-10-12'},
            {'type': 'row', 'time_debut': '08:30', 'time_fin': '12:10'},      # 3h40 → 4
            {'type': 'date_header', 'jour': 2, 'date': '2026-10-13'},
            {'type': 'row', 'time_debut': '13:30', 'time_fin': '16:00'},      # 2h30 → 3
            {'type': 'date_header', 'jour': 3, 'date': '2026-10-14'},
            {'type': 'row', 'time_debut': '08:30', 'time_fin': '11:30'}]      # 3h00 → 3
    h = bm.heures_du_programme(rows)
    assert h['heures'] == 10 and h['minutes'] == 220 + 150 + 180
    assert [j['heures'] for j in h['jours']] == [4, 3, 3]
    assert h['debut'] == '08:30' and h['fin'] == '11:30'
    # un برنامج d'un jour : calcul inchangé, sans détail
    h1 = bm.heures_du_programme(rows[1:2])
    assert h1 == {'debut': '08:30', 'fin': '12:10', 'minutes': 220, 'heures': 4, 'arrondi': True}


def test_memo_et_bataqa_disent_la_periode(db):
    lid, fid = _dorra3(db)
    memo = db.get_memo_data(lid, fid)
    annee = db.annee_registre()
    assert f'وذلك من يوم 12 إلى يوم 14 أكتوبر {annee}' in memo['corps']
    assert 'طيلة الأيّام المشار إليها أعلاه' in memo['corps']
    # jours à heures d'ouverture différentes → le برنامج fait foi
    assert 'حسب التّوقيت المضبوط لكلّ يوم' in memo['corps']
    assert db.get_bataqa_data(lid, fid)['date_fin'] == f'{annee}-10-14'


def _finaliser(db, lid, fid):
    db.save_memo_data(fid, {'objet': 'دورة', 'corps': 'نصّ', 'moujah': []}, confirmer=True)
    db.finaliser_formation(fid)


def test_hodour_par_jour_et_classe_ponderee(db):
    lid, fid = _dorra3(db)
    _finaliser(db, lid, fid)
    hs = db.get_hodour(fid)
    assert all(set(p['jours']) == {1, 2, 3} for p in hs)
    par_nom = {p['nom_prenom']: p['id'] for p in hs}
    # incomplet : refus
    ok, msg = db.save_hodour(fid, {pid: {'1': True} for pid in par_nom.values()})
    assert not ok and 'كلّ يوم' in msg
    # النقيب (أ1) présent 3 jours ; les deux عريف (ج) présents 1 jour chacun :
    # par têtes ج l'emporterait (2 contre 1) ; par jours de présence أ1 (3 contre 2).
    pres = {par_nom['مشارك وهمي أوّل']: {'1': True, '2': True, '3': True},
            par_nom['مشاركة وهمية ثانية']: {'1': True, '2': False, '3': False},
            par_nom['مشارك وهمي ثالث']: {'1': False, '2': False, '3': True}}
    ok, res = db.save_hodour(fid, pres)
    assert ok, res
    assert res['classe'] == 'أ1' and res['presences_jours'] == 5 and res['nb_jours'] == 3
    assert res['repartition']['أ1'] == 3 and res['repartition']['ج'] == 2
    assert res['nb_presents'] == 3 and res['nb_absents'] == 0
    assert [x['presents'] for x in res['par_jour']] == [2, 1, 2]
    relu = {p['nom_prenom']: p for p in db.get_hodour(fid)}
    assert relu['مشاركة وهمية ثانية']['jours'] == {1: 1, 2: 0, 3: 0}
    assert relu['مشاركة وهمية ثانية']['absences'] == [2, 3]


def test_absent_tous_les_jours_sans_shahada(db):
    lid, fid = _dorra3(db)
    _finaliser(db, lid, fid)
    hs = db.get_hodour(fid)
    pres = {p['id']: {'1': p['grade'] == 'النقيب', '2': p['grade'] == 'النقيب',
                      '3': p['grade'] == 'النقيب'} for p in hs}
    ok, res = db.save_hodour(fid, pres)
    assert ok and res['nb_presents'] == 1 and res['nb_absents'] == 2
    from core import dossier_dorra
    donnees, presents = dossier_dorra.donnees_shahadat(lid, fid)
    assert [p['grade'] for p in presents] == ['النقيب']
    assert donnees['date_fin'].endswith('-10-14')


def test_mustahaqqat_somme_des_jours(client, db):
    lid, fid = _dorra3(db)
    _finaliser(db, lid, fid)
    hs = db.get_hodour(fid)
    db.save_hodour(fid, {p['id']: {'1': True, '2': True, '3': True} for p in hs})
    dorra = db.get_dorra_mustahaqqat(fid)
    assert dorra['multi'] and dorra['nb_jours'] == 3
    db.confirmer_classe(fid, dorra and db.get_dorra_mustahaqqat(fid)['mu_classe_auto'])
    c = db.calculer_mustahaqqat(fid)
    # 08:30→12:15 = 3h45 → 4 ; 13:30→16:45 = 3h15 → 4 ; 08:30→12:15 → 4
    assert c['heures'] == 12 and [j['heures'] for j in c['jours']] == [4, 4, 4]
    assert c['chiffrable'] and abs(c['montant'] - 12 * c['taux']) < 1e-6
    # l'écran القيمة المالية montre le détail
    db.save_muqarrar_dorra(fid, '77', f'{db.annee_registre()}-10-20')
    page = client.get(f'/mustahaqqat/dorra/{fid}/qima').data.decode('utf-8')
    assert 'اليوم الثاني' in page and 'تُحتسب ساعات كلّ يوم على حدة' in page


def test_muqarrar_apres_le_dernier_jour(client, db):
    lid, fid = _dorra3(db)
    _finaliser(db, lid, fid)
    annee = db.annee_registre()
    r = client.post(f'/mustahaqqat/dorra/{fid}/muqarrar',
                    data={'muqarrar_numero': '12', 'muqarrar_date': f'{annee}-10-13',
                          '_csrf': 'jeton-de-test'})
    corps = r.data.decode('utf-8')
    assert r.status_code == 200 and f'{annee}-10-14' in corps     # refusé : pendant la دورة
    r = client.post(f'/mustahaqqat/dorra/{fid}/muqarrar',
                    data={'muqarrar_numero': '12', 'muqarrar_date': f'{annee}-10-15',
                          '_csrf': 'jeton-de-test'})
    assert r.status_code == 302


def test_page_hodour_par_jour(client, db):
    lid, fid = _dorra3(db)
    _finaliser(db, lid, fid)
    db.save_muqarrar_dorra(fid, '77', f'{db.annee_registre()}-10-20')
    page = client.get(f'/mustahaqqat/dorra/{fid}/hodour').data.decode('utf-8')
    assert page.count('class="ck-jour"') == 9 and 'data-multi="1"' in page
    assert 'اليوم الثالث' in page and '3 أيّام' in page
    # l'envoi HTTP par jour
    hs = db.get_hodour(fid)
    r = client.post(f'/mustahaqqat/dorra/{fid}/hodour', headers=CSRF,
                    json={'presences': {str(p['id']): {'1': True, '2': True, '3': False}
                                        for p in hs}})
    d = r.get_json()
    assert d['succes'] and d['presences_jours'] == 6


# ═══ 5. Documents ═══════════════════════════════════════════════════════════

def _mediabox(pdf):
    m = re.search(rb'/MediaBox\s*\[\s*0\s+0\s+([\d.]+)\s+([\d.]+)', pdf)
    return float(m.group(1)), float(m.group(2))


def test_pdf_programme_et_bataqa_hodour(client, db):
    lid, fid = _dorra3(db)
    url = f'/lettre/{lid}/formations/{fid}'
    r = client.get(f'{url}/programme/pdf')
    assert r.status_code == 200 and r.data[:4] == b'%PDF'
    r = client.get(f'{url}/hodour/pdf')
    assert r.status_code == 200 and _mediabox(r.data)[0] < 600     # 3 jours : portrait


def test_bataqa_hodour_paysage_a_partir_de_4_jours(db, tmp_path):
    from core import pdf_generator as pg
    import os
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    jours = J.jours_detail('2026-10-12', '2026-10-17', 'صباحا')
    chemin = pg.generer_pdf_bataqa_hodour({
        'titre': 'دورة', 'date_formation': '2026-10-12', 'date_fin': '2026-10-17',
        'jours': jours, 'participants': PARTS, 'nom_formateur': 'س', 'grade_formateur': 'الرائد',
        'nom_centre': 'مركز وهمي', 'ville_centre': 'مدينة'}, base)
    with open(chemin, 'rb') as fh:
        pdf = fh.read()
    os.remove(chemin)
    largeur, hauteur = _mediabox(pdf)
    assert largeur > hauteur                                        # paysage
    # un seul jour : la بطاقة d'origine, portrait, inchangée
    chemin = pg.generer_pdf_bataqa_hodour({
        'titre': 'دورة', 'date_formation': '2026-10-12', 'participants': PARTS,
        'nom_centre': 'مركز وهمي', 'ville_centre': 'مدينة'}, base)
    with open(chemin, 'rb') as fh:
        pdf = fh.read()
    os.remove(chemin)
    assert _mediabox(pdf)[0] < 600


def test_dossier_word_multi_jours(client, db):
    lid, fid = _dorra3(db)
    _finaliser(db, lid, fid)
    r = client.get(f'/lettre/{lid}/formations/{fid}/dossier.zip')
    assert r.status_code == 200
    with zipfile.ZipFile(io.BytesIO(r.data)) as z:
        docs = {n: z.read(n) for n in z.namelist() if n.endswith('.docx')}
    def xml(octets):
        with zipfile.ZipFile(io.BytesIO(octets)) as z:
            return z.read('word/document.xml').decode('utf-8')
    prog = next(xml(o) for n, o in docs.items() if 'برنامج' in n)
    assert prog.count('<w:tbl>') >= 4          # en-tête + un tableau par jour
    for t in ('اليوم الأوّل', 'اليوم الثاني', 'اليوم الثالث', '(مساءا)'):
        assert t in prog
    hod = next(xml(o) for n, o in docs.items() if 'حضور' in n)
    assert 'ملاحظات' in hod and 'في الفترة من 12 إلى 14' in hod


def test_docx_paysage():
    from core import docx_ecrivain as dx
    doc = dx.DocumentWord(page=(29.7, 21.0))
    doc.ajouter(dx.paragraphe('نصّ'))
    with zipfile.ZipFile(io.BytesIO(doc.octets())) as z:
        assert 'w:orient="landscape"' in z.read('word/document.xml').decode('utf-8')
    doc = dx.DocumentWord()
    doc.ajouter(dx.paragraphe('نصّ'))
    with zipfile.ZipFile(io.BytesIO(doc.octets())) as z:
        assert 'orient' not in z.read('word/document.xml').decode('utf-8')


def test_filtre_dates_dorra():
    import app as application
    f = application._filtre_dates_dorra
    assert f({'date_formation': '2026-10-12', 'date_fin': ''}) == '2026-10-12'
    assert f({'date_formation': ''}) == '—'
    html = str(f({'date_formation': '2026-10-12', 'date_fin': '2026-10-14'}))
    assert 'من <bdi dir="ltr">2026-10-12</bdi> إلى <bdi dir="ltr">2026-10-14</bdi>' in html
    assert '3 أيّام' in html


def test_page_programme_contient_le_code_multi_jours():
    from tests.conftest import js_programme
    js = js_programme()
    for nom in ('function joursDorra', 'function chargerProgrammeJours', 'function confirmerJour',
                "class=\"f-date-fin\"", 'MAX_JOURS_DORRA = 6', '/programme/jour/'):
        assert nom in js, nom


def test_une_dorra_d_un_jour_reste_identique(client, db):
    """Aucune clé nouvelle ne change le parcours d'une دورة d'un jour."""
    from tests.test_v17_paquet_d import _dorra
    lid, fid = _dorra(db)
    prog = db.get_programme_data(lid, fid)
    assert not prog['multi'] and len(prog['jours']) == 1
    assert all(r['type'] == 'row' for r in prog['rows'])
    assert 'يوم' in db.get_memo_data(lid, fid)['corps']
    hs = db.get_hodour(fid)
    assert all('jours' not in p for p in hs)
    assert db.calculer_mustahaqqat(fid)['jours'] == []


# ═══ 6. Correctif découvert par la simulation 2025 → 2028 ═══════════════════

def test_pas_de_fantome_dr_apres_changement_d_annee(db):
    """La 1re مراسلة مدير جهوي d'un برنامج de l'année N n'est plus réinscrite
    dans le سجلّ de l'année N+1 au démarrage (la série N+1 repartait au-delà)."""
    from datetime import datetime
    from core import exercice as ex
    reel = datetime.now().year
    conn = db.get_connection()
    ex.definir_annee(conn, reel - 1)
    conn.commit()
    conn.close()
    lid = db.save_programme('interne', 'ديسمبر', reel - 1,
                            [_formation(f'{reel - 1}-12-10')], 'م', 'ن')
    db.verrouiller_lettre(lid, 'interne')
    ref, num, typ, deja = db.attribuer_numero_dr(lid, 'externe', 'إدارة جهويّة وهمية')
    assert ref and not deja
    conn = db.get_connection()
    ex.definir_annee(conn, reel)
    conn.commit()
    conn.close()
    db.init_db()
    db.init_db()
    conn = db.get_connection()
    try:
        lignes = conn.execute("SELECT annee FROM registre WHERE source='directeur'").fetchall()
        compteur = conn.execute("SELECT valeur FROM compteurs WHERE annee=? AND type='externe'",
                                (reel,)).fetchone()
    finally:
        conn.close()
    assert [r['annee'] for r in lignes] == [reel - 1]
    assert (compteur['valeur'] if compteur else 0) == 0      # la série neuve part de 1


def test_nettoyage_des_fantomes_existants(db):
    from datetime import datetime
    reel = datetime.now().year
    lid = db.save_programme('interne', 'أكتوبر', reel, [_formation(f'{reel}-10-12')], 'م', 'ن')
    db.verrouiller_lettre(lid, 'interne')
    ref, num, _, _ = db.attribuer_numero_dr(lid, 'externe', 'إدارة جهويّة وهمية')
    conn = db.get_connection()
    conn.execute("INSERT INTO registre (annee, type, numero, ref_complet, source, source_id) "
                 "VALUES (?, 'externe', ?, ?, 'directeur', ?)", (reel + 1, num, ref, lid))
    conn.commit()
    conn.close()
    db.init_db()
    conn = db.get_connection()
    try:
        ans = [r['annee'] for r in conn.execute(
            "SELECT annee FROM registre WHERE source='directeur'")]
    finally:
        conn.close()
    assert ans == [reel]
