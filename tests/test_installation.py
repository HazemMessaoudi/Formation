# -*- coding: utf-8 -*-
"""معالج التّنصيب — الحارس، الخطوات، أعداد الانطلاق.

منذ الإصدار 64 أُعيد تصميم المعالج ليصير سبع خطوات:
  1=nom_centre (قائمة)، 2=code_centre (END-3-XX-XX)، 3=ville_centre (قائمة)،
  4=المسؤول (رتبة قائمة + اسم نصّي)، 5=unite_garde (قائمة)،
  6=lieu_formation_defaut (قائمة)، 7=أعداد الانطلاق.
تُشير الاختبارات إلى الخطوات بأرقامها الجديدة أو عبر identite.NB_ETAPES.

ما يُختبر هنا ليس جمالية الصّفحات بل ثلاث ضمانات:

  1. لا تُستعمل المنظومة قبل أن تتعرّف على المركز (الحارس).
  2. لا تُمحى إجابة خطوة لمجرّد أنّها غير معروضة في خطوة أخرى.
  3. لا يُعاد إسناد عدد سبق أن خرج به مكتوب — ولو طلب المستعمل ذلك صراحة.
"""
import pytest

from core import identite


REPONSES = {
    'nom_centre':            'مركز التكوين الديواني ببنزرت',   # في CENTRES_FORMATION
    'nom_centre_ba':         'بمركز التكوين الديواني ببنزرت',
    'ville_centre':          'بنزرت',                          # في WILAYAS
    'entete_centre_1':       'المركز الجهوي للتّكوين الدّيواني',
    'entete_centre_2':       'بالشّمال',
    'titre_responsable':     'النقيب',                         # في GRADES_RESPONSABLE
    'nom_responsable':       'سمير التّرابلسي',
    'destination_dr':        'السّيّد المدير الجهوي للدّيوانة ببنزرت',
    'admin_regionale':       'الإدارة الجهويّة للدّيوانة ببنزرت',
    'unite_garde':           'الوحدة الثانية للحرس الديواني بجندوبة',  # في UNITES_GARDE
    'lieu_formation_defaut': 'مركز التكوين الجهوي ببنزرت',    # في SALLES_FORMATION
    '_code_part1':           '07',
    '_code_part2':           '01',
}


def _remplir(client, jusqua=identite.NB_ETAPES, premier_interne=1, premier_externe=1):
    """Déroule le معالج de la خطوة 1 à `jusqua` incluse."""
    for etape in identite.ETAPES_INSTALLATION:
        if etape['numero'] > jusqua:
            break
        if etape.get('type') == 'numeros':
            donnees = {'numero_depart_interne': str(premier_interne),
                       'numero_depart_externe': str(premier_externe)}
        elif etape.get('type') == 'code_centre':
            donnees = {'_code_part1': REPONSES['_code_part1'],
                       '_code_part2': REPONSES['_code_part2']}
        else:
            donnees = {c['cle']: REPONSES[c['cle']] for c in etape['champs']}
        donnees['_csrf'] = 'jeton-de-test'
        r = client.post(f"/installation/{etape['numero']}", data=donnees)
        assert r.status_code == 302, f"الخطوة {etape['numero']} لم تُقبل"
    return r


# ─── 1. الحارس ───────────────────────────────────────────────────────────────

def test_toute_page_renvoie_vers_le_معالج_avant_le_tنصيب(client_neuf):
    """Une منظومة non installée ne laisse passer aucune page métier."""
    for chemin in ('/', '/dashboard', '/lettre/nouvelle', '/parametres',
                   '/lettres', '/registre', '/mkowin', '/mawad', '/journal'):
        r = client_neuf.get(chemin)
        assert r.status_code in (301, 302), chemin
        assert '/installation' in r.headers['Location'], chemin


def test_l_api_repond_409_et_non_une_redirection(client_neuf):
    """Un appel JSON doit recevoir une erreur lisible, pas du HTML de redirection."""
    r = client_neuf.post('/api/users',
                         headers={'Content-Type': 'application/json',
                                  'X-CSRF-Token': 'jeton-de-test'},
                         data='{"username":"x","password":"secret123"}')
    assert r.status_code == 409
    assert 'تنصيب' in r.get_json()['erreur']


def test_le_معالج_lui_meme_reste_accessible(client_neuf):
    r = client_neuf.get('/installation', follow_redirects=True)
    assert r.status_code == 200
    assert 'تنصيب المنظومة' in r.get_data(as_text=True)


def test_un_utilisateur_simple_ne_peut_pas_installer(client_neuf_simple):
    r = client_neuf_simple.get('/installation/1')
    assert r.status_code == 200
    texte = r.get_data(as_text=True)
    assert 'المشرف العام' in texte
    assert 'name="nom_centre"' not in texte      # aucun champ ne lui est offert


def test_apres_installation_le_معالج_ne_se_rouvre_pas(client):
    """`client` est installé : le معالج doit renvoyer vers la منظومة."""
    r = client.get('/installation/1')
    assert r.status_code == 302
    assert '/installation' not in r.headers['Location']


# ─── 2. الخطوات ──────────────────────────────────────────────────────────────

def test_une_etape_affiche_sa_question_et_ses_champs(client_neuf):
    r = client_neuf.get('/installation/4')   # المسؤول الممضي (الخطوة 4 منذ الإصدار 64)
    texte = r.get_data(as_text=True)
    assert r.status_code == 200
    assert 'name="titre_responsable"' in texte
    assert 'name="nom_responsable"' in texte
    assert 'name="nom_centre"' not in texte     # rien d'une autre étape


def test_un_champ_obligatoire_vide_bloque_l_etape(client_neuf, db):
    r = client_neuf.post('/installation/1',
                         data={'nom_centre': '   ', '_csrf': 'jeton-de-test'})
    assert r.status_code == 200                 # ré-affichage, pas de redirection
    assert 'وجوبيّة' in r.get_data(as_text=True)
    assert not db.get_config().get('nom_centre')


def test_un_champ_facultatif_vide_laisse_passer(client_neuf):
    r = client_neuf.post('/installation/5',   # وحدة الحرس (facultative) منذ الإصدار 64
                         data={'unite_garde': '', '_csrf': 'jeton-de-test'})
    assert r.status_code == 302
    assert r.headers['Location'].endswith('/installation/6')


def test_la_reponse_est_enregistree_immediatement(client_neuf, db):
    """Une coupure au milieu du معالج ne doit pas perdre ce qui a été saisi."""
    client_neuf.post('/installation/1',
                     data={'nom_centre': REPONSES['nom_centre'], '_csrf': 'jeton-de-test'})
    assert db.get_config()['nom_centre'] == REPONSES['nom_centre']
    # et la valeur revient pré-remplie si l'on repasse par l'étape
    r = client_neuf.get('/installation/1')
    assert REPONSES['nom_centre'] in r.get_data(as_text=True)


def test_une_etape_n_efface_pas_les_cles_qu_elle_n_affiche_pas(client_neuf, db):
    """Le principe qui gouverne aussi /parametres : on n'écrit que ce qu'on montre."""
    client_neuf.post('/installation/1',
                     data={'nom_centre': REPONSES['nom_centre'], '_csrf': 'jeton-de-test'})
    # الخطوة 2: رمز المركز (code_centre)
    client_neuf.post('/installation/2',
                     data={'_code_part1': REPONSES['_code_part1'],
                           '_code_part2': REPONSES['_code_part2'],
                           '_csrf': 'jeton-de-test'})
    # الخطوة 3: المدينة
    client_neuf.post('/installation/3',
                     data={'ville_centre': REPONSES['ville_centre'], '_csrf': 'jeton-de-test'})
    cfg = db.get_config()
    assert cfg['nom_centre'] == REPONSES['nom_centre']
    assert cfg['ref_prefix'] == f"END-3-{REPONSES['_code_part1']}-{REPONSES['_code_part2']}"
    assert cfg['ville_centre'] == REPONSES['ville_centre']


def test_une_etape_hors_domaine_revient_a_la_premiere(client_neuf):
    r = client_neuf.get('/installation/99')
    assert r.status_code == 302
    assert r.headers['Location'].endswith('/installation/1')


def test_la_derniere_etape_mene_au_resume(client_neuf):
    r = _remplir(client_neuf)
    assert '/installation/resume' in r.headers['Location']


# ─── 3. أعداد الانطلاق ───────────────────────────────────────────────────────

def test_le_premier_numero_saisi_est_bien_celui_qui_sera_servi(client_neuf, db):
    _remplir(client_neuf, premier_interne=147, premier_externe=58)
    assert db.prochain_numero_prevu('interne') == 147
    assert db.prochain_numero_prevu('externe') == 58
    # et c'est bien ce عدد-là que la منظومة sert réellement
    lettre_id = db.save_programme(
        'interne', 'أكتوبر', 2026,
        [{'titre': 'ت', 'grade': 'مقدم', 'nom_formateur': 'ف', 'lieu_travail': 'ل',
          'date_formation': '2026-10-21', 'periode': '', 'lieu_formation': 'ق'}], 'ن', 'ر')
    _ref, numero = db.verrouiller_lettre(lettre_id, 'interne')
    assert numero == 147
    assert db.prochain_numero_prevu('externe') == 58   # l'autre série n'a pas bougé


def test_les_deux_series_ne_s_empruntent_pas(client_neuf, db):
    _remplir(client_neuf, premier_interne=10, premier_externe=200)
    assert db.prochain_numero_prevu('interne') == 10
    assert db.prochain_numero_prevu('externe') == 200


def _inscrire_une_lettre_au_registre(db, type_lettre='interne'):
    """Un عدد n'entre au سجلّ qu'au verrouillage, pas à l'enregistrement."""
    lettre_id = db.save_programme(
        type_lettre, 'أكتوبر', 2026,
        [{'titre': 'ت', 'grade': 'مقدم', 'nom_formateur': 'ف', 'lieu_travail': 'ل',
          'date_formation': '2026-10-21', 'periode': '', 'lieu_formation': 'ق'}], 'ن', 'ر')
    return db.verrouiller_lettre(lettre_id, type_lettre)


def test_un_numero_deja_inscrit_au_registre_ne_peut_pas_etre_repris(db):
    """Le plancher protège les مراسلات déjà sorties sur papier."""
    _inscrire_une_lettre_au_registre(db)
    plancher = db.plancher_numero('interne')
    assert plancher >= 2
    with pytest.raises(ValueError):
        db.definir_numero_depart('interne', plancher - 1)
    # au plancher même, c'est permis
    assert db.definir_numero_depart('interne', plancher) == plancher


def test_un_numero_de_depart_invalide_est_refuse(db):
    for mauvais in ('0', '-3', 'abc', ''):
        with pytest.raises(ValueError):
            db.definir_numero_depart('externe', mauvais)
    with pytest.raises(ValueError):
        db.definir_numero_depart('serie-inconnue', 1)


def test_l_etape_des_numeros_signale_l_erreur_sans_planter(client_neuf, db):
    _inscrire_une_lettre_au_registre(db)
    r = client_neuf.post(f'/installation/{identite.NB_ETAPES}',
                         data={'numero_depart_interne': '1',
                               'numero_depart_externe': '1',
                               '_csrf': 'jeton-de-test'})
    assert r.status_code == 200
    assert 'لا يمكن الانطلاق من العدد' in r.get_data(as_text=True)


def test_l_etape_des_numeros_propose_la_suite_du_compteur(client_neuf, db):
    db.definir_numero_depart('interne', 42)
    r = client_neuf.get(f'/installation/{identite.NB_ETAPES}')
    assert 'value="42"' in r.get_data(as_text=True)


# ─── 4. الملخّص والمصادقة ────────────────────────────────────────────────────

def test_le_resume_montre_toutes_les_reponses(client_neuf):
    _remplir(client_neuf)
    texte = client_neuf.get('/installation/resume').get_data(as_text=True)
    for cle in ('nom_centre', 'nom_responsable'):
        assert REPONSES[cle] in texte


def test_la_validation_ouvre_la_منظومة(client_neuf, db):
    _remplir(client_neuf)
    r = client_neuf.post('/installation/resume', data={'_csrf': 'jeton-de-test'})
    assert r.status_code == 302
    assert db.get_config()['installation_faite'] == '1'
    assert identite.installation_faite(db.get_config())
    # le حارس s'efface
    r = client_neuf.get('/')
    assert r.status_code == 200 or '/installation' not in r.headers.get('Location', '')


def test_on_ne_peut_pas_valider_un_tنصيب_incomplet(client_neuf, db):
    _remplir(client_neuf, jusqua=3)
    r = client_neuf.post('/installation/resume', data={'_csrf': 'jeton-de-test'})
    assert r.status_code == 302
    assert r.headers['Location'].endswith('/installation/1')
    assert not identite.installation_faite(db.get_config())


def test_l_identite_saisie_alimente_les_pdf(client_neuf, db):
    """Ce que le مستعمل a répondu doit ressortir tel quel dans les مراسلات."""
    _remplir(client_neuf)
    champs = identite.champs_pdf(db.get_config())
    assert champs['nom_centre'] == REPONSES['nom_centre']
    assert champs['nom_centre_ba'] == REPONSES['nom_centre_ba']
    titre, nom = identite.signataire(db.get_config())
    assert (titre, nom) == (REPONSES['titre_responsable'], REPONSES['nom_responsable'])
