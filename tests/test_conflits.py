# -*- coding: utf-8 -*-
"""قواعد البرمجة : يوم الأحد، المكان، المشاركون (v1.4d).

  6. يوم أحد → تنبيه (le choix reste à l'agent).
  7. نفس التّاريخ + نفس الفترة + نفس المكان → رفض.
  8. نفس التّاريخ + نفس الفترة، مكان مختلف → رفض لمشارك مسجَّل في الدّورتين.
"""
import json

import pytest

from core import conflits as C

JETON = {'X-CSRF-Token': 'jeton-de-test'}


def dorra(titre, date, periode='صباحا', lieu='قاعة أ', formateur='مكوّن', **kw):
    d = {'titre': titre, 'grade': 'نقيب', 'nom_formateur': formateur,
         'lieu_travail': 'مكتب', 'date_formation': date, 'periode': periode,
         'lieu_formation': lieu}
    d.update(kw)
    return d


# ─── unité ───────────────────────────────────────────────────────────────────

def test_le_dimanche_est_reconnu():
    assert C.est_dimanche('2026-01-04')            # 4 janvier 2026 : dimanche
    assert not C.est_dimanche('2026-01-05')
    assert C.jour_de_semaine('2026-01-04') == 'الأحد'
    assert not C.est_dimanche('')


@pytest.mark.parametrize('a,b,attendu', [
    ('صباحا', 'صباحا', True), ('صباحا', 'مساءا', False),
    ('', 'مساءا', True),       ('مساءا', '', True),    # vide = journée entière
])
def test_chevauchement_des_periodes(a, b, attendu):
    assert C.periodes_se_chevauchent(a, b) is attendu


def test_meme_salle_meme_creneau_refuse():
    e = C.conflits_de_lieu([dorra('أ', '2026-01-06'), dorra('ب', '2026-01-06')])
    assert len(e) == 1 and 'نفس المكان' in e[0]


def test_meme_salle_creneaux_differents_permis():
    assert C.conflits_de_lieu([dorra('أ', '2026-01-06', 'صباحا'),
                               dorra('ب', '2026-01-06', 'مساءا')]) == []


def test_journee_entiere_recouvre_la_demi_journee():
    assert C.conflits_de_lieu([dorra('أ', '2026-01-06', ''),
                               dorra('ب', '2026-01-06', 'مساءا')])


def test_lieux_differents_permis_au_niveau_du_programme():
    assert C.conflits_de_lieu([dorra('أ', '2026-01-06', lieu='قاعة أ'),
                               dorra('ب', '2026-01-06', lieu='قاعة ب')]) == []


def test_le_lieu_se_compare_sans_حركات():
    assert C.conflits_de_lieu([dorra('أ', '2026-01-06', lieu='مركز التّكوين'),
                               dorra('ب', '2026-01-06', lieu='مركز التكوين')])


def test_participant_dans_deux_lieux_au_meme_moment():
    f = dorra('أ', '2026-01-06', lieu='قاعة أ')
    autre = dorra('ب', '2026-01-06', lieu='قاعة ب', ref_complet='END-1',
                  participants=[{'nom_prenom': 'سامي العلوي', 'identifiant_unique': ''}])
    e = C.conflits_de_participants([{'nom_prenom': 'سامي العلوي'}], f, [autre])
    assert e and 'سامي العلوي' in e[0] and 'قاعة ب' in e[0]


def test_l_identifiant_unique_prime_sur_le_nom():
    f = dorra('أ', '2026-01-06')
    autre = dorra('ب', '2026-01-06', lieu='قاعة ب',
                  participants=[{'nom_prenom': 'اسم آخر', 'identifiant_unique': '77001'}])
    assert C.conflits_de_participants(
        [{'nom_prenom': 'سامي', 'identifiant_unique': '77001'}], f, [autre])
    # deux homonymes aux معرّفات différents ne sont pas la même personne
    autre['participants'] = [{'nom_prenom': 'سامي', 'identifiant_unique': '11111'}]
    assert not C.conflits_de_participants(
        [{'nom_prenom': 'سامي', 'identifiant_unique': '22222'}], f, [autre])


def test_un_participant_ne_peut_etre_l_مكوّن_de_l_autre_دورة():
    f = dorra('أ', '2026-01-06')
    autre = dorra('ب', '2026-01-06', lieu='قاعة ب', formateur='منى بن عمر', participants=[])
    e = C.conflits_de_participants([{'nom_prenom': 'منى بن عمر'}], f, [autre])
    assert e and 'مكوّن' in e[0]


# ─── routes ──────────────────────────────────────────────────────────────────

def _post(client, url, payload):
    return client.post(url, headers={**JETON, 'Content-Type': 'application/json'},
                       data=json.dumps(payload))


def test_le_serveur_refuse_la_meme_salle_dans_un_programme(client):
    r = _post(client, '/lettre/enregistrer', {
        'type': 'interne', 'mois': 'جانفي', 'annee': 2026,
        'formations': [dorra('أ', '2026-01-06'), dorra('ب', '2026-01-06')]})
    assert r.status_code == 400
    assert 'نفس المكان' in r.get_json()['erreur']


def test_le_serveur_refuse_la_salle_prise_par_un_autre_programme(client, db):
    db.save_programme('interne', 'جانفي', 2026, [dorra('قديمة', '2026-01-06')], 'ن', 'ر')
    r = _post(client, '/lettre/enregistrer', {
        'type': 'externe', 'mois': 'جانفي', 'annee': 2026,
        'formations': [dorra('جديدة', '2026-01-06')]})
    assert r.status_code == 400
    assert 'قديمة' in r.get_json()['erreur']


def test_la_mise_a_jour_ne_se_bloque_pas_elle_meme(client, db):
    """Réenregistrer son propre برنامج ne doit pas se compter comme conflit."""
    lid = db.save_programme('interne', 'جانفي', 2026, [dorra('أ', '2026-01-06')], 'ن', 'ر')
    r = _post(client, f'/lettre/{lid}/mettre-a-jour', {
        'type': 'interne', 'mois': 'جانفي', 'annee': 2026,
        'formations': [dorra('أ', '2026-01-06')]})
    assert r.status_code == 200, r.get_json()


def test_la_validation_refuse_un_brouillon_autosauve_en_conflit(client, db):
    """L'autosauvegarde est indulgente ; le تأكيد, lui, ne l'est pas."""
    db.save_programme('interne', 'جانفي', 2026, [dorra('قديمة', '2026-01-06')], 'ن', 'ر')
    lid = db.save_programme('interne', 'جانفي', 2026, [dorra('جديدة', '2026-01-06')], 'ن', 'ر')
    r = _post(client, f'/lettre/{lid}/valider', {'type': 'interne'})
    assert r.status_code == 400
    assert not db.get_lettre_detail(lid)['lettre'].get('verrouille')


def _formation_id(db, lettre_id):
    return db.get_lettre_detail(lettre_id)['formations'][0]['id']


def test_un_participant_ne_suit_pas_deux_دورات_simultanees(client, db):
    l1 = db.save_programme('interne', 'جانفي', 2026,
                           [dorra('أ', '2026-01-06', lieu='قاعة أ')], 'ن', 'ر')
    l2 = db.save_programme('interne', 'جانفي', 2026,
                           [dorra('ب', '2026-01-06', lieu='قاعة ب', formateur='آخر')], 'ن', 'ر')
    f1, f2 = _formation_id(db, l1), _formation_id(db, l2)
    sami = {'nom_prenom': 'سامي العلوي', 'grade': 'عريف', 'identifiant_unique': '77001', 'sexe': 'ذكر', 'fiaa_omria': 'أقلّ من 40 سنة'}
    assert _post(client, f'/lettre/{l1}/formations/{f1}/participants',
                 {'participants': [sami]}).status_code == 200
    r = _post(client, f'/lettre/{l2}/formations/{f2}/participants', {'participants': [sami]})
    assert r.status_code == 400
    assert 'سامي العلوي' in r.get_json()['erreur']
    assert db.get_participants(l2, f2) == []                    # rien d'enregistré


def test_creneaux_differents_le_meme_participant_est_permis(client, db):
    l1 = db.save_programme('interne', 'جانفي', 2026,
                           [dorra('أ', '2026-01-06', 'صباحا', lieu='قاعة أ')], 'ن', 'ر')
    l2 = db.save_programme('interne', 'جانفي', 2026,
                           [dorra('ب', '2026-01-06', 'مساءا', lieu='قاعة ب', formateur='آخر')],
                           'ن', 'ر')
    f1, f2 = _formation_id(db, l1), _formation_id(db, l2)
    sami = {'nom_prenom': 'سامي العلوي', 'grade': 'عريف', 'identifiant_unique': '77001', 'sexe': 'ذكر', 'fiaa_omria': 'أقلّ من 40 سنة'}
    assert _post(client, f'/lettre/{l1}/formations/{f1}/participants',
                 {'participants': [sami]}).status_code == 200
    assert _post(client, f'/lettre/{l2}/formations/{f2}/participants',
                 {'participants': [sami]}).status_code == 200


def test_la_saisie_signale_le_dimanche(client):
    from tests.conftest import js_programme
    html = client.get('/lettre/nouvelle').get_data(as_text=True) + js_programme()
    assert 'estDimanche' in html and 'يوافق يوم أحد' in html
    assert 'recap-dimanche' in html
