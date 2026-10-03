# -*- coding: utf-8 -*-
"""Les routes de l'étape 2 et de la مصادقة, vues par le navigateur.

On refait ici, à travers le client HTTP, le geste qui a révélé le défaut :
tirer deux مراسلات مديرين جهويّين, en fsakher une, et vérifier que la منظومة
a bien rendu le عدد — pas seulement effacé une ligne à l'écran."""

import pytest

JETON = {'X-CSRF-Token': 'jeton-de-test'}


def _programme_confirme(client, db, mois='فيفري'):
    annee = db.annee_registre()
    if not db.candidats_mkow_par_nom('زياد البوهلالي'):
        db.add_mkow({'grade': 'مقدم', 'nom': 'البوهلالي', 'prenom': 'زياد'})
    charge = {'type': 'interne', 'mois': mois, 'annee': annee,
              'formations': [{'titre': f'دورة {mois}', 'grade': 'مقدم',
                              'nom_formateur': 'زياد البوهلالي', 'lieu_travail': '',
                              'date_formation': f'{annee}-02-10', 'periode': '',
                              'lieu_formation': 'القصرين'}]}
    lid = client.post('/lettre/enregistrer', headers=JETON,
                      json=charge).get_json()['lettre_id']
    client.post(f'/lettre/{lid}/valider', headers=JETON, json={'type': 'interne'})
    return lid


def test_attribuer_puis_fsakher_via_les_routes(client, db):
    lid = _programme_confirme(client, db)
    # Deux مراسلات externes.
    r1 = client.post(f'/lettre/{lid}/dr/attribuer', headers=JETON,
                     json={'destination': 'بنزرت', 'type_mr': 'externe'}).get_json()
    r2 = client.post(f'/lettre/{lid}/dr/attribuer', headers=JETON,
                     json={'destination': 'المنستير', 'type_mr': 'externe'}).get_json()
    assert r1['succes'] and r2['succes']
    assert r2['numero'] == r1['numero'] + 1

    liste = client.get(f'/lettre/{lid}/dr').get_json()['dr_lettres']
    assert len(liste) == 2
    cible = next(d for d in liste if d['numero'] == r1['numero'])

    rep = client.post(f'/lettre/{lid}/dr/{cible["id"]}/annuler', headers=JETON)
    assert rep.status_code == 200 and rep.get_json()['succes']

    # Une seule reste ; le عدد rendu resservira.
    reste = client.get(f'/lettre/{lid}/dr').get_json()['dr_lettres']
    assert [d['numero'] for d in reste] == [r2['numero']]
    assert db.prochain_numero_prevu('externe') == r1['numero']


def test_attribuer_refuse_sans_destination(client, db):
    lid = _programme_confirme(client, db)
    rep = client.post(f'/lettre/{lid}/dr/attribuer', headers=JETON,
                      json={'destination': '', 'type_mr': 'externe'})
    assert rep.status_code == 400


def test_reimpression_ne_consomme_pas_un_adad(client, db):
    lid = _programme_confirme(client, db)
    a = client.post(f'/lettre/{lid}/dr/attribuer', headers=JETON,
                    json={'destination': 'بنزرت', 'type_mr': 'externe'}).get_json()
    b = client.post(f'/lettre/{lid}/dr/attribuer', headers=JETON,
                    json={'destination': 'بنزرت', 'type_mr': 'externe'}).get_json()
    assert b['deja'] is True
    assert b['numero'] == a['numero']


def test_revue_programme_route(client, db):
    lid = _programme_confirme(client, db)
    r = client.get(f'/lettre/{lid}/revue').get_json()
    assert r['ref']
    assert r['coherent'] is False        # la دورة n'est pas achevée
    assert r['problemes']


def test_sceller_refuse_puis_expose_les_problemes(client, db):
    lid = _programme_confirme(client, db)
    rep = client.post(f'/lettre/{lid}/sceller', headers=JETON)
    assert rep.status_code == 400
    assert rep.get_json()['problemes']
