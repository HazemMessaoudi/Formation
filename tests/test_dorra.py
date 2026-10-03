# -*- coding: utf-8 -*-
"""Règles de saisie des dorrat : progression étape par étape, برنامج الدورة,
doublons de date."""


def _prealables(db, programme):
    """Étapes 3 et 4 achevées — sans elles, l'étape 5 est verrouillée."""
    db.save_participants(programme['lettre_id'], programme['formation_id'],
                         [{'nom_prenom': 'الوكيل أول خالد', 'grade': 'الوكيل أول',
                           'identifiant_unique': '123', 'lieu_travail': 'القصرين'}])
    db.save_bataqa_data(programme['formation_id'], {'mahawer': 'المحاور'})


def test_programme_refuse_sans_ligne_complete(client, db, programme):
    _prealables(db, programme)
    lid, fid = programme['lettre_id'], programme['formation_id']
    r = client.post(f'/lettre/{lid}/formations/{fid}/programme/data',
                    json={'rows': [{'type': 'row', 'time_debut': '08:00',
                                    'time_fin': '10:00',
                                    'activity': '', 'participants': ''}]},
                    headers={'X-CSRF-Token': 'jeton-de-test'})
    assert r.status_code == 400
    assert 'كامل' in r.get_json()['erreur']


def test_programme_accepte_une_ligne_complete(client, db, programme):
    _prealables(db, programme)
    lid, fid = programme['lettre_id'], programme['formation_id']
    r = client.post(f'/lettre/{lid}/formations/{fid}/programme/data',
                    json={'rows': [{'type': 'row', 'time_debut': '08:30',
                                    'time_fin': '12:00',
                                    'activity': 'تحرير المحاضر',
                                    'participants': 'المقدم البوهلالي زياد'}]},
                    headers={'X-CSRF-Token': 'jeton-de-test'})
    assert r.status_code == 200 and r.get_json().get('succes')


def test_programme_refuse_une_plage_de_moins_de_15_min(client, db, programme):
    """Garde serveur : une fقرة de moins de 15 min est refusée (document officiel)."""
    _prealables(db, programme)
    lid, fid = programme['lettre_id'], programme['formation_id']
    r = client.post(f'/lettre/{lid}/formations/{fid}/programme/data',
                    json={'rows': [{'type': 'row', 'time_debut': '08:30',
                                    'time_fin': '08:40',   # 10 min < 15
                                    'activity': 'تحرير المحاضر',
                                    'participants': 'المقدم البوهلالي زياد'}]},
                    headers={'X-CSRF-Token': 'jeton-de-test'})
    assert r.status_code == 400
    assert '15' in r.get_json()['erreur']


def test_programme_accepte_une_plage_de_15_min_exactement(client, db, programme):
    """La borne est inclusive : 15 min pile passe."""
    _prealables(db, programme)
    lid, fid = programme['lettre_id'], programme['formation_id']
    r = client.post(f'/lettre/{lid}/formations/{fid}/programme/data',
                    json={'rows': [{'type': 'row', 'time_debut': '08:30',
                                    'time_fin': '08:45',   # 15 min exactement
                                    'activity': 'تحرير المحاضر',
                                    'participants': 'المقدم البوهلالي زياد'}]},
                    headers={'X-CSRF-Token': 'jeton-de-test'})
    assert r.status_code == 200 and r.get_json().get('succes')


def test_programme_ecarte_les_lignes_partielles(client, db, programme):
    _prealables(db, programme)
    lid, fid = programme['lettre_id'], programme['formation_id']
    client.post(f'/lettre/{lid}/formations/{fid}/programme/data',
                json={'rows': [
                    {'type': 'row', 'time_debut': '08:30', 'time_fin': '10:00',
                     'activity': 'أ', 'participants': 'ب'},
                    {'type': 'row', 'time_debut': '10:00', 'time_fin': '12:00',
                     'activity': '',  'participants': ''},
                ]},
                headers={'X-CSRF-Token': 'jeton-de-test'})
    prog = db.get_programme_data(lid, fid)
    assert len(prog['rows']) == 1, "la ligne à moitié remplie ne doit pas être enregistrée"


def test_dorrat_meme_jour_detecte_le_doublon(db, programme):
    memes = db.dorrat_meme_jour('2026-10-21')
    assert len(memes) == 1 and memes[0]['titre'] == 'تحرير المحاضر'
    assert db.dorrat_meme_jour('2026-10-21', exclure_lettre=programme['lettre_id']) == []
    assert db.dorrat_meme_jour('2026-10-22') == []
    assert db.dorrat_meme_jour('') == []


# ─── Progression étape par étape (une dorra à la fois) ───────────────────────
#
# Régression : une dorra SANS participants passait quand même au برنامج puis à
# la مذكّرة finale, parce que chaque étape ne vérifiait que sa voisine immédiate.

ROW_OK = {'type': 'row', 'time_debut': '08:30', 'time_fin': '10:00',
          'activity': 'تحرير المحاضر', 'participants': 'المقدم البوهلالي زياد'}
CSRF = {'X-CSRF-Token': 'jeton-de-test'}


def _ajouter_participant(db, programme):
    db.save_participants(programme['lettre_id'], programme['formation_id'],
                         [{'nom_prenom': 'الوكيل أول خالد', 'grade': 'الوكيل أول',
                           'identifiant_unique': '123', 'lieu_travail': 'القصرين'}])



def test_etat_initial_n_ouvre_que_l_etape_3(db, programme):
    etat = db.etat_dorra(programme['formation_id'])
    assert etat['ouvertes'] == ['participants']
    assert etat['prochaine'] == 'participants'


def test_participants_refuse_une_liste_vide(client, programme):
    lid, fid = programme['lettre_id'], programme['formation_id']
    r = client.post(f'/lettre/{lid}/formations/{fid}/participants',
                    json={'participants': [{'nom_prenom': '   '}]}, headers=CSRF)
    assert r.status_code == 400
    assert 'متكوّن' in r.get_json()['erreur']


def test_programme_refuse_sans_bataqa(client, db, programme):
    _ajouter_participant(db, programme)
    lid, fid = programme['lettre_id'], programme['formation_id']
    r = client.post(f'/lettre/{lid}/formations/{fid}/programme/data',
                    json={'rows': [ROW_OK]}, headers=CSRF)
    assert r.status_code == 400
    assert 'البطاقة البيداغوجية' in r.get_json()['erreur']


def test_memo_refuse_sans_programme(client, db, programme):
    _ajouter_participant(db, programme)
    lid, fid = programme['lettre_id'], programme['formation_id']
    r = client.post(f'/lettre/{lid}/formations/{fid}/memo/data',
                    json={'confirmer': False}, headers=CSRF)
    assert r.status_code == 400
    assert 'برنامج الدورة' in r.get_json()['erreur']


def test_chaine_complete_ouvre_les_etapes_une_a_une(db, programme):
    fid = programme['formation_id']
    _ajouter_participant(db, programme)
    assert db.etat_dorra(fid)['ouvertes'] == ['participants', 'bataqa']

    db.save_bataqa_data(fid, {'mahawer': 'المحاور'})
    assert db.etat_dorra(fid)['ouvertes'] == ['participants', 'bataqa', 'programme']

    db.save_programme_data(fid, {'rows': [ROW_OK]})
    assert db.etat_dorra(fid)['ouvertes'] == \
        ['participants', 'bataqa', 'programme', 'memo']


def test_plage_horaire_composee_pour_le_pdf(client, db, programme):
    fid = programme['formation_id']
    _ajouter_participant(db, programme)
    db.save_bataqa_data(fid, {'mahawer': 'المحاور'})
    client.post(f"/lettre/{programme['lettre_id']}/formations/{fid}/programme/data",
                json={'rows': [dict(ROW_OK, time='')]}, headers=CSRF)
    ligne = db.get_programme_data(programme['lettre_id'], fid)['rows'][0]
    assert ligne['time'] == 'من 08:30 إلى 10:00'
    assert ligne['time_debut'] == '08:30' and ligne['time_fin'] == '10:00'


# ─── Chaque دورة est indépendante des autres ─────────────────────────────────
#
# Régression : un برنامج à deux دورات dont l'une était enregistrée ne pouvait
# plus être fsakhé du tout — l'autre دورة restait bloquée indéfiniment. Chaque
# دورة s'annule désormais séparément, depuis le tableau des dorrat.

DEUX_DORRAT = [
    {'titre': 'المحضر الإلكتروني', 'grade': 'وكيل للديوانة', 'nom_formateur': 'ساسي ماهر',
     'lieu_travail': 'المكتب الحدودي', 'date_formation': '2026-10-20', 'periode': 'صباحا',
     'lieu_formation': 'مركز التكوين الجهوي'},
    {'titre': 'الإعلاميّة والمكتبيّة', 'grade': 'وكيل للديوانة', 'nom_formateur': 'ساسي ماهر',
     'lieu_travail': 'المكتب الحدودي', 'date_formation': '2026-10-20', 'periode': 'صباحا',
     'lieu_formation': 'مركز التكوين الجهوي'},
]


def _programme_a_deux_dorrat(db):
    lid = db.save_programme('interne', 'أكتوبر', 2026, DEUX_DORRAT, 'حازم مسعودي', 'النقيب')
    db.verrouiller_lettre(lid, 'interne')
    fids = [f['id'] for f in db.get_lettre_detail(lid)['formations']]
    return lid, fids


def _mener_jusqu_a_l_enregistrement(db, lid, fid):
    db.save_participants(lid, fid, [{'nom_prenom': 'خالد', 'grade': 'الوكيل',
                                     'identifiant_unique': '9', 'lieu_travail': 'x'}])
    db.save_bataqa_data(fid, {'mahawer': 'م'})
    db.save_programme_data(fid, {'rows': [ROW_OK]})
    db.save_memo_data(fid, {'objet': 'أ', 'corps': 'ب', 'moujah': []}, confirmer=True)
    return db.finaliser_formation(fid)


def test_fsakh_d_une_dorra_epargne_les_autres(db):
    lid, (a, b) = _programme_a_deux_dorrat(db)
    _mener_jusqu_a_l_enregistrement(db, lid, a)

    ok, _ = db.annuler_dorra(b)
    assert ok, "la dorra non enregistrée doit rester annulable"
    restantes = [f['id'] for f in db.get_lettre_detail(lid)['formations']]
    assert restantes == [a], "seule la dorra visée disparaît"


def test_une_dorra_enregistree_n_est_plus_annulable(db):
    lid, (a, _b) = _programme_a_deux_dorrat(db)
    _mener_jusqu_a_l_enregistrement(db, lid, a)
    ok, msg = db.annuler_dorra(a)
    assert ok is False and 'مسجَّلة' in msg


def test_fsakh_d_une_dorra_libere_le_numero_de_sa_memo(db):
    lid, (a, b) = _programme_a_deux_dorrat(db)
    db.save_participants(lid, b, [{'nom_prenom': 'خالد', 'grade': 'الوكيل',
                                   'identifiant_unique': '9', 'lieu_travail': 'x'}])
    db.save_bataqa_data(b, {'mahawer': 'م'})
    db.save_programme_data(b, {'rows': [ROW_OK]})
    db.save_memo_data(b, {'objet': 'أ', 'corps': 'ب', 'moujah': []}, confirmer=True)
    num_memo = db.get_memo_data(lid, b)['memo_numero']

    db.annuler_dorra(b)
    assert num_memo in {r['numero'] for r in db.get_numeros_liberes('interne')}


def test_la_derniere_dorra_annulee_rend_les_numeros_definitifs(db):
    lid, (a, b) = _programme_a_deux_dorrat(db)
    _mener_jusqu_a_l_enregistrement(db, lid, a)
    db.annuler_dorra(b)
    statuts = {e['source']: e['statut'] for e in db.get_registre('interne')}
    assert statuts.get('programme') == 'definitif'


# ─── تاريخ إنشاء التكوين ─────────────────────────────────────────────────────

def test_chaque_dorra_porte_sa_date_de_creation(db, programme):
    f = db.get_lettre_detail(programme['lettre_id'])['formations'][0]
    assert f['date_creation'], "la dorra doit porter la date/heure du système"
    assert len(f['date_creation']) >= 16, "date ET heure, pas seulement la date"


def test_l_autosauvegarde_ne_remet_pas_la_date_de_creation_a_zero(db, programme):
    lid = programme['lettre_id']
    avant = db.get_lettre_detail(lid)['formations'][0]['date_creation']
    db.update_programme(lid, 'interne', 'أكتوبر', 2026, [
        {'titre': 'تحرير المحاضر', 'grade': 'مقدم', 'nom_formateur': 'البوهلالي زياد',
         'lieu_travail': '', 'date_formation': '2026-10-21', 'periode': '',
         'lieu_formation': 'مركز التكوين الجهوي بالقصرين'}])
    apres = db.get_lettre_detail(lid)['formations'][0]['date_creation']
    assert apres == avant, "la date de création survit aux réécritures de l'autosave"


def test_meme_jour_renvoie_le_formateur_pour_l_alerte(db):
    lid, _ = _programme_a_deux_dorrat(db)
    memes = db.dorrat_meme_jour('2026-10-20')
    assert len(memes) == 2
    assert all(m['nom_formateur'] == 'ساسي ماهر' for m in memes)
    assert all(m['periode'] == 'صباحا' for m in memes)


# ── v1.4d : la فترة المسائيّة commence à 13:30 ─────────────────────────────────

def _apres_midi(db, programme):
    conn = db.get_connection()
    conn.execute("UPDATE formations SET periode='مساءا' WHERE id=?",
                 (programme['formation_id'],))
    conn.commit()
    conn.close()


def _ligne(debut, fin):
    return {'rows': [{'type': 'row', 'time_debut': debut, 'time_fin': fin,
                      'activity': 'تحرير المحاضر', 'participants': 'المقدم زياد'}]}


def test_apres_midi_refuse_un_debut_avant_13h30(client, db, programme):
    _prealables(db, programme)
    _apres_midi(db, programme)
    lid, fid = programme['lettre_id'], programme['formation_id']
    r = client.post(f'/lettre/{lid}/formations/{fid}/programme/data',
                    json=_ligne('08:00', '12:00'), headers={'X-CSRF-Token': 'jeton-de-test'})
    assert r.status_code == 400
    assert '13:30' in r.get_json()['erreur']


def test_apres_midi_accepte_13h30(client, db, programme):
    _prealables(db, programme)
    _apres_midi(db, programme)
    lid, fid = programme['lettre_id'], programme['formation_id']
    r = client.post(f'/lettre/{lid}/formations/{fid}/programme/data',
                    json=_ligne('13:30', '16:30'), headers={'X-CSRF-Token': 'jeton-de-test'})
    assert r.status_code == 200, r.get_json()


def test_le_matin_reste_a_08h00(client, db, programme):
    _prealables(db, programme)
    lid, fid = programme['lettre_id'], programme['formation_id']
    r = client.post(f'/lettre/{lid}/formations/{fid}/programme/data',
                    json=_ligne('08:00', '12:00'), headers={'X-CSRF-Token': 'jeton-de-test'})
    assert r.status_code == 200


def test_l_editeur_part_de_13h30_l_apres_midi(client):
    from tests.conftest import js_programme
    html = client.get('/lettre/nouvelle').get_data(as_text=True) + js_programme()
    assert "PROG_H_APRES_MIDI = '13:30'" in html
    assert 'data-periode=' in html


def test_la_مذكرة_annonce_13h30_l_apres_midi(db, programme):
    _apres_midi(db, programme)
    m = db.get_memo_data(programme['lettre_id'], programme['formation_id'])
    assert m['heure_debut'] == '13:30'
