# -*- coding: utf-8 -*-
"""مراقبة التّواريخ — الدّورة تقع في شهر برنامجها.

La règle du مركز est simple et ces tests ne défendent qu'elle : **دورة فيفري
في فيفري**. Une دورة datée de mars n'appartient pas au برنامج de février,
elle appartient à celui de mars.

Le second point, tout aussi important : le contrôle n'intervient qu'au
تأكيد. Un brouillon porte des dates provisoires et parfois vides ; les
refuser à la frappe ferait perdre le travail en cours. On ne refuse qu'au
moment où la مراسلة prend son عدد et devient irréversible.
"""

from core import periode


def dorra(titre='تحرير المحاضر', date_formation='2026-02-10'):
    return {'titre': titre, 'grade': 'مقدم', 'nom_formateur': 'البوهلالي زياد',
            'lieu_travail': '', 'date_formation': date_formation,
            'periode': '', 'lieu_formation': 'مركز التكوين الجهوي بالقصرين'}


# ─── القاعدة ─────────────────────────────────────────────────────────────────

def test_dorra_du_mois_du_programme_est_acceptee():
    assert periode.verifier_dates('فيفري', 2026, [dorra()]) == []


def test_dorra_au_premier_et_au_dernier_jour_du_mois():
    """Les bords du mois sont dans le mois : pas d'erreur d'un jour."""
    assert periode.verifier_dates('جانفي', 2026, [
        dorra(date_formation='2026-01-01'),
        dorra(date_formation='2026-01-31'),
    ]) == []


def test_dorra_dun_autre_mois_est_refusee():
    erreurs = periode.verifier_dates('فيفري', 2026,
                                     [dorra(date_formation='2026-03-03')])
    assert len(erreurs) == 1
    assert 'مارس' in erreurs[0]
    assert 'تحرير المحاضر' in erreurs[0]


def test_dorra_de_debut_janvier_suit_janvier_non_decembre():
    """Le cas qui a motivé la règle, dans les deux sens."""
    assert periode.verifier_dates('جانفي', 2026,
                                  [dorra(date_formation='2026-01-03')]) == []
    erreurs = periode.verifier_dates('ديسمبر', 2025,
                                     [dorra(date_formation='2026-01-03')])
    assert len(erreurs) == 1


def test_dorra_dune_autre_annee_est_refusee():
    erreurs = periode.verifier_dates('فيفري', 2026,
                                     [dorra(date_formation='2027-02-10')])
    assert len(erreurs) == 1
    assert '2027' in erreurs[0] and '2026' in erreurs[0]


def test_chaque_dorra_fautive_a_son_propre_message():
    """L'agent doit savoir laquelle corriger, pas seulement qu'il y a faute."""
    erreurs = periode.verifier_dates('فيفري', 2026, [
        dorra('الدّورة الأولى', '2026-02-10'),
        dorra('الدّورة الثّانية', '2026-03-10'),
        dorra('الدّورة الثّالثة', '2027-02-10'),
    ])
    assert len(erreurs) == 2
    assert any('الدّورة الثّانية' in e for e in erreurs)
    assert any('الدّورة الثّالثة' in e for e in erreurs)
    assert not any('الدّورة الأولى' in e for e in erreurs)


# ─── ما لا يُرفض ─────────────────────────────────────────────────────────────

def test_dorra_sans_date_nest_pas_un_motif_de_refus():
    """Une saisie incomplète se traite ailleurs : ici on ne juge que les dates écrites."""
    assert periode.verifier_dates('فيفري', 2026,
                                  [dorra(date_formation='')]) == []
    assert periode.verifier_dates('فيفري', 2026,
                                  [dorra(date_formation=None)]) == []


def test_programme_sans_mois_ne_compare_rien():
    assert periode.verifier_dates('', 2026, [dorra('د', '2026-03-03')]) == []
    assert periode.verifier_dates(None, None, [dorra('د', '2026-03-03')]) == []


def test_liste_vide_est_acceptee():
    assert periode.verifier_dates('فيفري', 2026, []) == []
    assert periode.verifier_dates('فيفري', 2026, None) == []


def test_date_illisible_est_signalee_sans_faire_tomber():
    erreurs = periode.verifier_dates('فيفري', 2026,
                                     [dorra(date_formation='10/02/2026')])
    assert len(erreurs) == 1
    assert 'غير مقروء' in erreurs[0]


def test_les_noms_de_mois_sont_ceux_de_la_manzouma():
    assert periode.numero_de_mois('جانفي') == 1
    assert periode.numero_de_mois('فيفري') == 2
    assert periode.numero_de_mois('ديسمبر') == 12
    assert periode.numero_de_mois('  مارس  ') == 3
    assert periode.numero_de_mois('شهر لا وجود له') is None
    assert periode.numero_de_mois('') is None


# ─── au تأكيد, et seulement là ───────────────────────────────────────────────

def _payload(mois='فيفري', annee=2026, date_formation='2026-02-10'):
    return {'type': 'interne', 'mois': mois, 'annee': annee,
            'formations': [dorra(date_formation=date_formation)]}


def _enregistrer(client, **kw):
    from core.database import add_mkow, candidats_mkow_par_nom
    if not candidats_mkow_par_nom('البوهلالي زياد'):
        add_mkow({'grade': 'مقدم', 'nom': 'البوهلالي', 'prenom': 'زياد'})
    rep = client.post('/lettre/enregistrer',
                      headers={'X-CSRF-Token': 'jeton-de-test'},
                      json=_payload(**kw))
    assert rep.status_code == 200
    return rep.get_json()['lettre_id']


def test_le_brouillon_accepte_une_date_hors_mois(db, client):
    """Refuser à la saisie ferait perdre le travail en cours : on n'y touche pas."""
    lettre_id = _enregistrer(client, date_formation='2026-03-03')
    detail = db.get_lettre_detail(lettre_id)
    assert detail['formations'][0]['date_formation'] == '2026-03-03'


def test_la_confirmation_refuse_une_date_hors_mois(db, client):
    lettre_id = _enregistrer(client, date_formation='2026-03-03')
    rep = client.post(f'/lettre/{lettre_id}/valider',
                      headers={'X-CSRF-Token': 'jeton-de-test'},
                      json={'type': 'interne'})
    assert rep.status_code == 400
    assert 'مارس' in rep.get_json()['erreur']


def test_un_refus_ne_consomme_aucun_numero(db, client):
    """Le point décisif : une confirmation refusée ne doit rien dépenser."""
    lettre_id = _enregistrer(client, date_formation='2026-03-03')
    client.post(f'/lettre/{lettre_id}/valider',
                headers={'X-CSRF-Token': 'jeton-de-test'},
                json={'type': 'interne'})

    conn = db.get_connection()
    try:
        assert conn.execute('SELECT COUNT(*) c FROM registre').fetchone()['c'] == 0
        row = conn.execute('SELECT numero, verrouille FROM lettres WHERE id=?',
                           (lettre_id,)).fetchone()
    finally:
        conn.close()
    assert row['numero'] == 0
    assert not row['verrouille']


def test_la_confirmation_accepte_une_date_du_bon_mois(db, client):
    lettre_id = _enregistrer(client, date_formation='2026-02-10')
    rep = client.post(f'/lettre/{lettre_id}/valider',
                      headers={'X-CSRF-Token': 'jeton-de-test'},
                      json={'type': 'interne'})
    assert rep.status_code == 200
    assert rep.get_json()['succes'] is True


def test_apres_correction_la_confirmation_passe(db, client):
    """Le refus n'est pas une impasse : on corrige et on confirme."""
    lettre_id = _enregistrer(client, date_formation='2026-03-03')
    assert client.post(f'/lettre/{lettre_id}/valider',
                       headers={'X-CSRF-Token': 'jeton-de-test'},
                       json={'type': 'interne'}).status_code == 400

    client.post(f'/lettre/{lettre_id}/mettre-a-jour',
                headers={'X-CSRF-Token': 'jeton-de-test'},
                json=_payload(date_formation='2026-02-20'))
    rep = client.post(f'/lettre/{lettre_id}/valider',
                      headers={'X-CSRF-Token': 'jeton-de-test'},
                      json={'type': 'interne'})
    assert rep.status_code == 200
    assert rep.get_json()['ref']
