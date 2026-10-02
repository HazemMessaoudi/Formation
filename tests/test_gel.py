# -*- coding: utf-8 -*-
"""تجميد هويّة الوثيقة — المراسلة المؤكّدة لا تُعاد كتابتها.

Une مراسلة qui a pris son عدد est partie. Elle porte le nom du مركز et de
son responsable tels qu'ils étaient ce jour-là. Si le مركز change de
responsable en mars, réimprimer la مراسلة de janvier doit rendre la مراسلة
de janvier.

C'est ce que ces tests défendent. Sans ce gel, corriger une faute de frappe
dans les إعدادات réécrirait rétroactivement toute la correspondance déjà
enregistrée — et la distribution à plusieurs مراكز rendrait le cas courant.
"""

import pytest

from core import gel, identite


@pytest.fixture()
def centre(db):
    """Une identité de مركز complète, telle que la laisse le معالج التّنصيب."""
    db.update_config('nom_responsable', 'حازم مسعودي')
    db.update_config('titre_responsable', 'النقيب')
    db.update_config('nom_centre', 'مركز التكوين الجهوي بالقصرين')
    return db


def confirmer(db, mois='فيفري', annee=2026):
    lettre_id = db.save_programme(
        'interne', mois, annee,
        [{'titre': 'تحرير المحاضر', 'grade': 'مقدم',
          'nom_formateur': 'البوهلالي زياد', 'lieu_travail': '',
          'date_formation': f'{annee}-02-10', 'periode': '',
          'lieu_formation': 'مركز التكوين الجهوي بالقصرين'}],
        'حازم مسعودي', 'النقيب')
    db.verrouiller_lettre(lettre_id, 'interne')
    return lettre_id


# ─── ما يُجمَّد ──────────────────────────────────────────────────────────────

def test_la_confirmation_fige_lidentite(centre):
    db = centre
    lettre_id = confirmer(db)
    conn = db.get_connection()
    try:
        fige = gel.lire(conn, lettre_id)
    finally:
        conn.close()
    assert fige['nom_responsable'] == 'حازم مسعودي'
    assert fige['titre_responsable'] == 'النقيب'


def test_changer_de_responsable_ne_reecrit_pas_une_maraslat_partie(centre):
    """Le cas qui justifie tout ce module."""
    db = centre
    lettre_id = confirmer(db)

    db.update_config('nom_responsable', 'شخص آخر')
    db.update_config('titre_responsable', 'الرائد')

    champs = gel.champs_pdf(db.get_config(), lettre_id)
    assert champs['nom_responsable'] == 'حازم مسعودي'
    assert champs['titre_responsable'] == 'النقيب'


def test_changer_le_nom_du_centre_ne_touche_pas_au_passe(centre):
    db = centre
    lettre_id = confirmer(db)
    ancien = gel.champs_pdf(db.get_config(), lettre_id)['nom_centre']

    db.update_config('nom_centre', 'مركز التكوين الجهوي بسوسة')
    assert gel.champs_pdf(db.get_config(), lettre_id)['nom_centre'] == ancien
    # …tandis que l'identité courante, elle, a bien changé.
    assert identite.champs_pdf(db.get_config())['nom_centre'] != ancien


def test_un_nouveau_programme_prend_la_nouvelle_identite(centre):
    """Le gel protège le passé, il ne fige pas l'avenir."""
    db = centre
    confirmer(db, mois='فيفري')
    db.update_config('nom_responsable', 'شخص آخر')
    suivant = confirmer(db, mois='مارس')
    assert gel.champs_pdf(db.get_config(), suivant)['nom_responsable'] == 'شخص آخر'


# ─── ما لا يُجمَّد ────────────────────────────────────────────────────────────

def test_un_brouillon_non_confirme_suit_les_reglages_du_jour(centre):
    db = centre
    lettre_id = db.save_programme('interne', 'فيفري', 2026, [],
                                  'حازم مسعودي', 'النقيب')
    db.update_config('nom_responsable', 'شخص آخر')
    assert gel.champs_pdf(db.get_config(), lettre_id)['nom_responsable'] == 'شخص آخر'


def test_sans_lettre_id_lidentite_est_celle_du_jour(centre):
    db = centre
    courants = identite.champs_pdf(db.get_config())
    assert gel.champs_pdf(db.get_config()) == courants
    assert gel.champs_pdf(db.get_config(), None) == courants


def test_une_base_sans_gel_ne_casse_rien(centre):
    """Une base d'avant cette version n'a aucun gel : on rend le jour même."""
    db = centre
    lettre_id = confirmer(db)
    conn = db.get_connection()
    try:
        conn.execute('DROP TABLE IF EXISTS documents_geles')
        conn.commit()
    finally:
        conn.close()
    champs = gel.champs_pdf(db.get_config(), lettre_id)
    assert champs['nom_responsable'] == 'حازم مسعودي'


def test_une_khana_ajoutee_apres_le_gel_prend_la_valeur_du_jour(centre):
    """Le gel complète l'identité courante ; il ne l'ampute pas.

    Une nouvelle version de la منظومة peut ajouter une خانة d'identité que
    les anciens gels ne portent pas : la وثيقة ne doit pas l'afficher vide.
    """
    db = centre
    lettre_id = confirmer(db)
    conn = db.get_connection()
    try:
        conn.execute("UPDATE documents_geles SET donnees=? WHERE lettre_id=?",
                     ('{"nom_responsable": "حازم مسعودي"}', lettre_id))
        conn.commit()
    finally:
        conn.close()
    champs = gel.champs_pdf(db.get_config(), lettre_id)
    assert champs['nom_responsable'] == 'حازم مسعودي'
    assert champs['nom_centre']                       # rempli, non vide
    assert set(champs) == set(identite.champs_pdf(db.get_config()))


def test_le_gel_ne_se_reecrit_pas(centre):
    """On ne regèle pas un document parti, même si la confirmation est rejouée."""
    db = centre
    lettre_id = confirmer(db)
    db.update_config('nom_responsable', 'شخص آخر')
    db.verrouiller_lettre(lettre_id, 'interne')       # déjà verrouillée
    assert gel.champs_pdf(db.get_config(), lettre_id)['nom_responsable'] == 'حازم مسعودي'


# ─── الوثائق ─────────────────────────────────────────────────────────────────

def test_la_maraslat_est_construite_avec_lidentite_gelee(centre, client, monkeypatch):
    """L'épreuve qui compte : ce que reçoit le générateur, pas ce que rend une fonction.

    On n'imprime pas réellement — la fonte n'est pas requise pour vérifier
    ce qui est mis dans la وثيقة — mais on intercepte les données au dernier
    instant, juste avant le tracé.
    """
    import routes.pdf as rpdf

    db = centre
    lettre_id = confirmer(db)
    db.update_config('nom_responsable', 'شخص آخر')
    db.update_config('nom_centre', 'مركز التكوين الجهوي بسوسة')

    recu = {}

    def _faux_pdf(donnees, base_dir):
        recu.update(donnees)
        chemin = '/tmp/gel_test.pdf'
        with open(chemin, 'wb') as f:
            f.write(b'%PDF-1.4\n')
        return chemin

    monkeypatch.setattr(rpdf, 'generer_pdf', _faux_pdf)
    rep = client.get(f'/lettre/{lettre_id}/generer')
    assert rep.status_code == 200

    assert recu['nom_responsable'] == 'حازم مسعودي'
    assert 'القصرين' in recu['nom_centre']
    assert 'سوسة' not in recu['nom_centre']
