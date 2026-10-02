# -*- coding: utf-8 -*-
"""v1.7.1 — corrections demandées après l'essai de la v1.7 (données fictives).

1. زرّ رؤية كلمة المرور : le bouton retrouve son champ même quand un message
   de validation a été inséré ;
2. أرقام 1 2 3 (pas ١ ٢ ٣) dans l'interface ;
3. thème clair au premier lancement ;
4. الجنس / الفئة العمريّة obligatoires, colonne الجهة المرجعيّة retirée ;
5. مكان العمل : entête « مكان العمل الحالي » reconnu à l'import, fiches
   complétées depuis la قائمة المشاركين ;
6. بيان النشاط mémorisé et proposé, متدخّلون multiples choisis dans une liste ;
7. زرّ « طباعة شهائد المشاركين » dans chaque دورة منجزة.
"""
import io
import os
import re

from tests.conftest import BASE_DIR, js_programme

H = {'X-CSRF-Token': 'jeton-de-test'}
SF = {'sexe': 'ذكر', 'fiaa_omria': 'أقلّ من 40 سنة'}


def _lire(*chemin):
    return open(os.path.join(BASE_DIR, *chemin), encoding='utf-8').read()


# ═══ 1. زرّ رؤية كلمة المرور ═════════════════════════════════════════════════

def test_oeil_cherche_le_champ_dans_son_cadre():
    for gabarit in ('base.html', 'login.html'):
        src = _lire('templates', gabarit)
        corps = src[src.index('function toggleEye'):][:600]
        assert "btn.closest('.pwd-wrap')" in corps and "querySelector('input')" in corps


def test_message_de_validation_hors_du_cadre_mot_de_passe():
    ui = _lire('static', 'js', 'ui.js')
    assert "classList.contains('pwd-wrap')" in ui


def test_page_changement_mdp_a_trois_yeux(client):
    corps = client.get('/changer-mot-de-passe').data.decode('utf-8')
    assert corps.count('class="pwd-wrap"') == 3 and corps.count('toggleEye(this)') == 3


# ═══ 2. أرقام غربيّة ═════════════════════════════════════════════════════════

def test_aucun_chiffre_arabe_indien_dans_l_interface():
    motif = re.compile('[٠-٩۰-۹]')
    fautes = []
    for racine, _d, noms in os.walk(os.path.join(BASE_DIR, 'templates')):
        for n in noms:
            if n.endswith('.html'):
                for i, ligne in enumerate(open(os.path.join(racine, n), encoding='utf-8'), 1):
                    if motif.search(ligne):
                        fautes.append(f'{n}:{i}')
    assert fautes == []


def test_page_apropos_numerotee_1_a_6(client):
    corps = client.get('/tarif').data.decode('utf-8')
    nums = re.findall(r'<span class="ap-etape__num">([^<]+)</span>', corps)
    assert nums == ['1', '2', '3', '4', '5', '6']


# ═══ 3. Thème clair par défaut ══════════════════════════════════════════════

def test_theme_clair_par_defaut():
    ui = _lire('static', 'js', 'ui.js')
    assert 'THEME_DEFAUT = 0' in ui and 'prefers-color-scheme' not in ui
    login = _lire('templates', 'login.html')
    assert 'prefers-color-scheme' not in login


# ═══ 4. قائمة المشاركين ══════════════════════════════════════════════════════

def test_colonne_jiha_retiree_et_choix_obligatoires(client):
    corps = client.get('/lettre/nouvelle').data.decode('utf-8') + js_programme()
    assert 'الجهة المرجعيّة</th>' not in corps and 'p-jiha' not in corps
    assert 'class="p-sexe" title="الجنس (إجباري)" required' in corps
    assert 'class="p-fiaa" title="الفئة العمريّة (إجباري)" required' in corps
    assert 'يجب اختيار الجنس والفئة العمريّة لكلّ مشارك' in corps


def test_serveur_refuse_sans_sexe_ni_fiaa(client, db, programme):
    url = f"/lettre/{programme['lettre_id']}/formations/{programme['formation_id']}/participants"
    base = {'nom_prenom': 'مشارك وهمي', 'grade': 'عريف', 'identifiant_unique': '90000001'}
    r = client.post(url, headers=H, json={'participants': [base]})
    assert r.status_code == 400 and 'الجنس' in r.get_json()['erreur']
    r = client.post(url, headers=H, json={'participants': [{**base, **SF}]})
    assert r.status_code == 200


def test_jiha_suit_la_fiche_sans_colonne(client, db, programme):
    """La جهة n'est plus saisie mais reste transmise (البطاقة / إحصائيات)."""
    url = f"/lettre/{programme['lettre_id']}/formations/{programme['formation_id']}/participants"
    client.post(url, headers=H, json={'participants': [
        {'nom_prenom': 'مشارك وهمي', 'grade': 'عريف', 'identifiant_unique': '90000001',
         'jiha_marjiiya': 'جهة وهمية', **SF}]})
    assert client.get(url).get_json()['participants'][0]['jiha_marjiiya'] == 'جهة وهمية'


# ═══ 5. مكان العمل ══════════════════════════════════════════════════════════

def _classeur(entetes, lignes, titre=True):
    from openpyxl import Workbook
    wb = Workbook()
    ws = wb.active
    if titre:
        ws.append([])
        ws.append(['', '', 'قائمة وهمية'])
        ws.append([])
    ws.append(entetes)
    for l in lignes:
        ws.append(l)
    flux = io.BytesIO()
    wb.save(flux)
    return flux.getvalue()


def test_import_reconnait_mekan_el_amal_el_hali():
    from core import importation as imp
    octets = _classeur(
        ['الإمضاء', 'عدد الكنشات', 'مكان العمل الحالي', 'الرتبة', 'الإسم و اللقب', 'المعرف الوحيد', 'ع/ر'],
        [['', 1, 'مكتب وهمي أ', 'عميد للديوانة', 'شخص وهمي', 90000011, 1],
         ['', 1, 'مكتب وهمي ب', 'رقيب للديوانة', 'شخص وهمي ثان', 90000012, 2]])
    plan = imp.analyser(octets, [])
    assert 'lieu_travail' in plan['colonnes_reconnues']
    assert [f['lieu_travail'] for _n, f in plan['a_ajouter']] == ['مكتب وهمي أ', 'مكتب وهمي ب']


def test_import_prefixe_et_genre():
    from core import importation as imp
    assert imp.champ_de_libelle('مكان العمل (المصلحة)') == 'lieu_travail'
    assert imp.champ_de_libelle('مقر العمل الأصلي') == 'lieu_travail'
    assert imp.champ_de_libelle('عدد الكنشات') is None
    octets = _classeur(['المعرّف الوحيد', 'الاسم واللقب', 'الجنس', 'الفئة العمرية'],
                       [['90000021', 'شخص وهمي', 'أنثى', 'أقل من 40 سنة'],
                        ['90000022', 'شخص وهمي ثان', 'ذكر', '40 سنة فما فوق'],
                        ['90000023', 'شخص وهمي ثالث', '؟', 'غير معروف']], titre=False)
    plan = imp.analyser(octets, [])
    fiches = [f for _n, f in plan['a_ajouter']]
    assert (fiches[0]['sexe'], fiches[0]['fiaa_omria']) == ('أنثى', 'أقلّ من 40 سنة')
    assert (fiches[1]['sexe'], fiches[1]['fiaa_omria']) == ('ذكر', '40 سنة وأكثر')
    assert 'sexe' not in fiches[2] and 'fiaa_omria' not in fiches[2]


def test_import_complete_le_lieu_des_fiches_existantes(db):
    """Cas réel : fiches importées sans مكان العمل, fichier ré-importé en
    « استكمال » → le مكان العمل est rempli, rien d'autre n'est écrasé."""
    from core import importation as imp
    db.add_mkow({'grade': 'عميد للديوانة', 'nom': 'شخص وهمي', 'identifiant_unique': '90000011'})
    octets = _classeur(['مكان العمل الحالي', 'الرتبة', 'الإسم و اللقب', 'المعرف الوحيد'],
                       [['مكتب وهمي أ', 'رتبة أخرى', 'شخص وهمي', 90000011]])
    plan = imp.analyser(octets, db.get_mkowin(), completer_existantes=True)
    assert plan['a_completer'] and plan['a_completer'][0][2] == {'lieu_travail': 'مكتب وهمي أ'}


def test_fiche_completee_depuis_la_liste_des_participants(client, db, programme):
    db.add_mkow({'grade': 'عريف', 'nom': 'شخص', 'prenom': 'وهمي', 'identifiant_unique': '90000031'})
    db.add_mkow({'grade': 'عريف', 'nom': 'شخص', 'prenom': 'آخر', 'identifiant_unique': '90000032',
                 'sexe': 'أنثى', 'lieu_travail': 'مكتب قديم'})
    url = f"/lettre/{programme['lettre_id']}/formations/{programme['formation_id']}/participants"
    r = client.post(url, headers=H, json={'participants': [
        {'nom_prenom': 'شخص وهمي', 'grade': 'عريف', 'identifiant_unique': '90000031',
         'lieu_travail': 'مكتب وهمي', **SF},
        {'nom_prenom': 'شخص آخر', 'grade': 'عريف', 'identifiant_unique': '90000032',
         'lieu_travail': 'مكتب جديد', 'sexe': 'ذكر', 'fiaa_omria': '40 سنة وأكثر'}]})
    assert r.status_code == 200
    f1 = next(m for m in db.get_mkowin() if m['identifiant_unique'] == '90000031')
    f2 = next(m for m in db.get_mkowin() if m['identifiant_unique'] == '90000032')
    assert (f1['sexe'], f1['fiaa_omria'], f1['lieu_travail']) == ('ذكر', 'أقلّ من 40 سنة', 'مكتب وهمي')
    # jamais d'écrasement : الجنس et مكان العمل déjà connus restent
    assert (f2['sexe'], f2['fiaa_omria'], f2['lieu_travail']) == ('أنثى', '40 سنة وأكثر', 'مكتب قديم')


def test_autocompletion_remplit_le_lieu():
    js = js_programme()
    assert "const l = row.querySelector('.p-lieu');   if (l)  l.value  = lieu;" in js
    assert "row.querySelector('.f-lieu-travail').value = lieu;" in js


# ═══ 6. بيان النشاط / المتدخّلون ════════════════════════════════════════════

def _lignes(*paires):
    return [{'type': 'row', 'activity': a, 'participants': p, 'time_debut': '08:30',
             'time_fin': '10:00', 'time': 'من 08:30 إلى 10:00'} for a, p in paires]


def test_programme_memorise_activites_et_intervenants(db, programme):
    fid = programme['formation_id']
    db.save_programme_data(fid, {'reference': '', 'moment': 'صباحا', 'rows': _lignes(
        ('عرض نظري', 'المقدم متدخّل أوّل، النقيب متدخّل ثان'),
        ('تمارين تطبيقية', 'المقدم متدخّل أوّل'))})
    db.save_programme_data(fid, {'reference': '', 'moment': 'صباحا', 'rows': _lignes(
        ('تمارين تطبيقية', 'المقدم متدخّل أوّل'))})
    assert db.suggestions_programme('activite')[0] == 'تمارين تطبيقية'
    assert set(db.suggestions_programme('activite')) == {'عرض نظري', 'تمارين تطبيقية'}
    assert db.suggestions_programme('intervenant') == ['المقدم متدخّل أوّل', 'النقيب متدخّل ثان']
    assert db.suggestions_programme('autre') == []


def test_decouper_intervenants():
    from core.db.suggestions import decouper_intervenants
    assert decouper_intervenants('أ، ب ,ج / د\nأ') == ['أ', 'ب', 'ج', 'د']
    assert decouper_intervenants('') == []


def test_api_suggestions(client, db, programme):
    db.add_mkow({'grade': 'المقدم', 'nom': 'شخص', 'prenom': 'وهمي', 'identifiant_unique': '90000041'})
    db.save_programme_data(programme['formation_id'], {'rows': _lignes(('نشاط وهمي', 'متدخّل حرّ'))})
    d = client.get('/api/programme/suggestions').get_json()
    assert d['activites'] == ['نشاط وهمي']
    assert d['intervenants'][0] == 'متدخّل حرّ' and 'المقدم شخص وهمي' in d['intervenants']


def test_reprise_des_programmes_existants(db, programme):
    """Une base d'avant la v1.7.1 : ses برامج alimentent les suggestions."""
    import json
    conn = db.get_connection()
    try:
        conn.execute('DELETE FROM programme_suggestions')
        conn.execute("DELETE FROM config WHERE cle='v171_suggestions_reprises'")
        conn.execute('INSERT INTO programme_formations (formation_id, rows_json) VALUES (?, ?)',
                     (programme['formation_id'], json.dumps(_lignes(('نشاط قديم', 'متدخّل قديم')),
                                                           ensure_ascii=False)))
        conn.commit()
    finally:
        conn.close()
    db.init_db()
    assert db.suggestions_programme('activite') == ['نشاط قديم']
    assert db.suggestions_programme('intervenant') == ['متدخّل قديم']


def test_page_programme_suggestions_et_pastilles():
    js = js_programme()
    assert 'list="dl_activites"' in js and 'list="dl_intervenants"' in js
    assert 'class="prow-interv"' in js and '_intervAjouter' in js and '_intervRetirer' in js
    assert "/api/programme/suggestions" in js
    # le texte enregistré reste celui du champ .prow-participants (imprimé tel quel)
    assert '<input type="hidden" class="prow-participants"' in js
    assert "const INTERV_SEP = '، ';" in js


# ═══ 7. شهائد المشاركين ═════════════════════════════════════════════════════

def test_bouton_shahadat_dans_les_dorrat_manjaza(client, db):
    from tests.test_v17_paquet_d import _dorra
    lid, fid = _dorra(db)
    conn = db.get_connection()
    try:
        conn.execute("UPDATE mustahaqqat SET acheve_at='2026-02-20 10:00:00', etat='acheve' "
                     "WHERE formation_id=?", (fid,))
        conn.commit()
    finally:
        conn.close()
    corps = client.get('/mustahaqqat/dorrat/manjaza').data.decode('utf-8')
    assert f'/lettre/{lid}/formations/{fid}/shahadat/pdf' in corps
    assert '🎓 طباعة شهائد المشاركين (2)' in corps
    r = client.get(f'/lettre/{lid}/formations/{fid}/shahadat/pdf')
    assert r.status_code == 200 and r.data[:4] == b'%PDF'


def test_bouton_shahadat_dans_la_page_qima():
    src = _lire('templates', 'mustahaqqat', 'qima.html')
    assert "url_for('generer_shahadat_pdf', lettre_id=dorra.lettre_id, formation_id=dorra.id)" in src
    assert '🎓 طباعة شهائد المشاركين' in src


def test_intervenants_un_par_ligne_dans_word_et_pdf(db, monkeypatch):
    import zipfile
    from tests.test_v17_paquet_d import _dorra
    from core import dossier_dorra as dd, dossier_word as dw
    import core.pdf_generator as pg
    lid, fid = _dorra(db)
    db.save_programme_data(fid, {'reference': 'م', 'moment': 'صباحا', 'rows': _lignes(
        ('نشاط وهمي', 'المقدم متدخّل أوّل، النقيب متدخّل ثان'))})
    octets = dw.word_programme(dd.donnees_programme(lid, fid), BASE_DIR)
    xml = zipfile.ZipFile(io.BytesIO(octets)).read('word/document.xml').decode('utf-8')
    assert '>المقدم متدخّل أوّل<' in xml and '>النقيب متدخّل ثان<' in xml
    vus = []
    orig = pg._wrap_log
    monkeypatch.setattr(pg, '_wrap_log', lambda c, t, *a, **k: (vus.append(t), orig(c, t, *a, **k))[1])
    chemin = pg.generer_pdf_programme(dd.donnees_programme(lid, fid), BASE_DIR)
    os.remove(chemin)
    assert 'المقدم متدخّل أوّل' in vus and 'النقيب متدخّل ثان' in vus


def test_formulaire_import_porte_les_options(client):
    corps = client.get('/mkowin/importer').data.decode('utf-8')
    for nom in ('completer', 'essai', 'sans_identifiant'):
        assert f'name="{nom}"' in corps
    assert re.search(r'name="completer" value="1"\s*checked', corps)   # proposé par défaut
    assert re.search(r'name="essai" value="1" checked', corps)


def test_import_reel_complete_les_fiches(client, db):
    db.add_mkow({'grade': 'عريف', 'nom': 'شخص وهمي', 'identifiant_unique': '90000051'})
    octets = _classeur(['مكان العمل الحالي', 'الرتبة', 'الإسم و اللقب', 'المعرف الوحيد'],
                       [['مكتب وهمي ج', 'عريف', 'شخص وهمي', 90000051]])
    r = client.post('/mkowin/importer', headers=H, content_type='multipart/form-data', data={
        'fichier': (io.BytesIO(octets), 'وهمي.xlsx'), 'completer': '1'})
    assert r.status_code == 200
    f = next(m for m in db.get_mkowin() if m['identifiant_unique'] == '90000051')
    assert f['lieu_travail'] == 'مكتب وهمي ج'


# ═══ Lot 2 (28/09 après-midi) ═══════════════════════════════════════════════

def test_programme_corps_du_tableau_en_11(monkeypatch):
    import core.pdf_generator as pg
    assert pg.SW_PROG == 11.0
    src = _lire('core', 'dossier_word.py')
    # V2 : le tableau est construit par une fonction (un tableau par jour)
    debut = src.index("for r in rows or []:")
    bloc = src[debut:src.index('return dx.tableau(larg, lignes)', debut)]
    assert 'taille=11' in bloc and 'taille=9' not in bloc


def test_hodour_et_qima_dans_l_ordre_des_rutab(client, db):
    from tests.test_v17_paquet_d import _dorra
    lid, fid = _dorra(db)       # saisis : الملازم, النقيب, الوكيل
    db.save_muqarrar_dorra(fid, '123', f'{db.annee_registre()}-02-20')
    corps = client.get(f'/mustahaqqat/dorra/{fid}/hodour').data.decode('utf-8')
    pos = [corps.index(n) for n in ('مشارك وهمي ثان', 'مشارك وهمي أوّل', 'مشارك غائب')]
    assert pos == sorted(pos)   # النقيب → الملازم → الوكيل


def test_statistiques_sans_la_jiha(client, db):
    corps = client.get('/statistiques').data.decode('utf-8')
    assert 'المشاركون حسب الجهة المرجعية' not in corps
    corps = client.get('/statistiques/rapport-annuel').data.decode('utf-8')
    assert 'المشاركون حسب الجهة المرجعيّة' not in corps


def test_pied_de_la_memo_avec_embleme(db, monkeypatch):
    import core.pdf_generator as pg
    dessins = []
    from reportlab.pdfgen import canvas
    orig = canvas.Canvas.drawImage
    monkeypatch.setattr(canvas.Canvas, 'drawImage',
                        lambda self, img, x, y, **k: (dessins.append((str(img), x, y, k)), orig(self, img, x, y, **k))[1])
    c = canvas.Canvas(io.BytesIO())
    textes = []
    orig_txt = canvas.Canvas.drawRightString
    monkeypatch.setattr(canvas.Canvas, 'drawRightString',
                        lambda self, x, y, t, *a, **k: (textes.append(x), orig_txt(self, x, y, t, *a, **k))[1])
    pg._draw_pied_ecole(c, {}, BASE_DIR)
    logo = [d for d in dessins if d[0].endswith('logo.jpg')]
    assert logo and abs(logo[0][1] + logo[0][3]['width'] - pg.PIED_X1) < 0.01   # à droite
    assert textes and max(textes) < pg.PIED_X1 - logo[0][3]['width']           # texte décalé


def test_word_memo_pied_avec_embleme(db):
    import zipfile
    from tests.test_v17_paquet_d import _dorra
    from core import dossier_dorra as dd, dossier_word as dw
    lid, fid = _dorra(db)
    octets = dw.word_memo(dd.donnees_memo(lid, fid, db.get_memo_data(lid, fid)), BASE_DIR)
    z = zipfile.ZipFile(io.BytesIO(octets))
    pied = z.read('word/footer1.xml').decode('utf-8')
    assert '<w:drawing>' in pied and 'end.dfrs@douane.gov.tn' in pied
    assert 'word/_rels/footer1.xml.rels' in z.namelist()


def _mawad_et_bataqa(db, client, lid, fid, participants):
    c = db.get_connection()
    c.execute("INSERT INTO mawad (titre, type_formation) VALUES ('تحرير المحاضر','تكوين مستمر')")
    c.commit(); c.close()
    url = f'/lettre/{lid}/formations/{fid}/participants'
    assert client.post(url, headers=H, json={'participants': participants}).status_code == 200
    b = client.get(f'/lettre/{lid}/formations/{fid}/bataqa/data').get_json()
    r = client.post(f'/lettre/{lid}/formations/{fid}/bataqa/data', headers=H, json=b)
    assert r.status_code == 200, r.get_json()
    return url


OFF = [{'nom_prenom': 'ضابط وهمي أ', 'grade': 'النقيب', 'identifiant_unique': '91', 'lieu_travail': 'مكتب وهمي', **SF},
       {'nom_prenom': 'ضابط وهمي ب', 'grade': 'الملازم', 'identifiant_unique': '92', 'lieu_travail': 'مكتب وهمي', **SF}]
SOUS = {'nom_prenom': 'عون وهمي ج', 'grade': 'العريف', 'identifiant_unique': '93', 'lieu_travail': 'فرقة وهمية', **SF}


def test_bataqa_suit_la_nouvelle_liste(client, db, programme):
    lid, fid = programme['lettre_id'], programme['formation_id']
    url = _mawad_et_bataqa(db, client, lid, fid, OFF)
    avant = client.get(f'/lettre/{lid}/formations/{fid}/bataqa/data').get_json()
    assert avant['mustahdafun'].startswith('ضبّاط ') and 'صف' not in avant['mustahdafun']
    r = client.post(url, headers=H, json={'participants': OFF + [SOUS]}).get_json()
    assert r['bataqa_actualisee'] == ['mustahdafun', 'services']
    apres = client.get(f'/lettre/{lid}/formations/{fid}/bataqa/data').get_json()
    assert 'ضبّاط وضبّاط صف' in apres['mustahdafun'] and 'فرقة وهمية' in apres['services']
    assert apres['nb_participants'] == 3


def test_bataqa_retouchee_a_la_main_n_est_pas_ecrasee(client, db, programme):
    lid, fid = programme['lettre_id'], programme['formation_id']
    url = _mawad_et_bataqa(db, client, lid, fid, OFF)
    b = client.get(f'/lettre/{lid}/formations/{fid}/bataqa/data').get_json()
    client.post(f'/lettre/{lid}/formations/{fid}/bataqa/data', headers=H,
                json={**b, 'mustahdafun': 'نصّ كتبه العون'})
    r = client.post(url, headers=H, json={'participants': OFF + [SOUS]}).get_json()
    assert r['bataqa_actualisee'] == ['services']
    apres = client.get(f'/lettre/{lid}/formations/{fid}/bataqa/data').get_json()
    assert apres['mustahdafun'] == 'نصّ كتبه العون'


def test_memo_non_retouchee_suit_la_liste(client, db, programme):
    lid, fid = programme['lettre_id'], programme['formation_id']
    url = _mawad_et_bataqa(db, client, lid, fid, OFF)
    db.save_programme_data(fid, {'rows': _lignes(('نشاط', 'متدخّل'))})
    m = client.get(f'/lettre/{lid}/formations/{fid}/memo/data').get_json()
    assert 'لفائدة ضبّاط الدّيوانة' in m['corps']
    client.post(f'/lettre/{lid}/formations/{fid}/memo/data', headers=H, json={**m, 'contenu_manuel': False})
    r = client.post(url, headers=H, json={'participants': OFF + [SOUS]}).get_json()
    assert r['memo_manuel'] is False
    m = client.get(f'/lettre/{lid}/formations/{fid}/memo/data').get_json()
    assert 'لفائدة ضبّاط وضبّاط صف الدّيوانة' in m['corps']


def test_page_rafraichit_bataqa_et_memo():
    js = js_programme()
    assert 'rafraichirBataqaDerives(fid);' in js and 'rafraichirMemoApresParticipants(fid, !!d.memo_manuel);' in js
