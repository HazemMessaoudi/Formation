# -*- coding: utf-8 -*-
"""بطاقة الحضور — pièce autonome, hors numérotation du dossier.

Hazem l'a demandée « شبيهة بالتي في الصورة » (colonne الإمضاء vide), et
surtout : **elle ne doit jamais être comptée** parmi les feuillets numérotés
4/4 ou 5/5. Ces tests défendent les deux points : le PDF se produit avec les
participants, et le route répond hors de la chaîne de numérotation."""

import os


JETON = {'X-CSRF-Token': 'jeton-de-test'}


def _programme_avec_participants(db):
    annee = db.annee_registre()
    lid = db.save_programme(
        'interne', 'فيفري', annee,
        [{'titre': 'إجراءات التبليغ', 'grade': 'مقدم', 'nom_formateur': 'زياد البوهلالي',
          'lieu_travail': '', 'date_formation': f'{annee}-02-10', 'periode': '',
          'lieu_formation': 'القصرين'}],
        'حازم مسعودي', 'النقيب')
    db.verrouiller_lettre(lid, 'interne')
    fid = db.get_lettre_detail(lid)['formations'][0]['id']
    db.save_participants(lid, fid, [
        {'nom_prenom': 'صالح المحمدي', 'grade': 'مقدم', 'identifiant_unique': '80001',
         'lieu_travail': 'القصرين', 'jiha_marjiiya': ''},
        {'nom_prenom': 'محمد البكوش', 'grade': 'عريف', 'identifiant_unique': '80002',
         'lieu_travail': 'القصرين', 'jiha_marjiiya': ''}])
    return lid, fid


def test_bataqa_hodour_se_produit(db):
    from core.pdf_generator import generer_pdf_bataqa_hodour
    lid, fid = _programme_avec_participants(db)
    parts = db.get_participants(lid, fid)
    chemin = generer_pdf_bataqa_hodour({
        'titre': 'إجراءات التبليغ', 'date_formation': '2026-09-23',
        'nom_centre': 'مركز التكوين الديواني بالقصرين', 'ville_centre': 'القصرين',
        'nom_formateur': 'زياد البوهلالي', 'titre_responsable': 'النقيب',
        'nom_responsable': 'حازم مسعودي', 'participants': parts,
    }, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    assert os.path.exists(chemin)
    assert 'hodour_' in os.path.basename(chemin)
    assert open(chemin, 'rb').read(4) == b'%PDF'


def test_route_hodour_repond(client, db):
    lid, fid = _programme_avec_participants(db)
    r = client.get(f'/lettre/{lid}/formations/{fid}/hodour/pdf')
    assert r.status_code == 200
    assert r.mimetype == 'application/pdf'
    assert r.data[:4] == b'%PDF'


def test_hodour_ne_compte_pas_dans_la_numerotation(client, db):
    """Le cœur de la demande : la بطاقة حضور reste HORS du comptage 4/4.

    On vérifie que le nombre de feuillets du dossier (مذكّرة) est identique
    que la بطاقة حضور ait été produite ou non — elle n'entre jamais dedans."""
    lid, fid = _programme_avec_participants(db)
    # La بطاقة حضور n'est rattachée à aucun compteur de pages : le générateur
    # de مذكّرة compte مذكّرة + برنامج + قائمة + بطاقة بيداغوجية, jamais hodour.
    # v1.7 : le comptage vit dans core/dossier_dorra.pages_du_dossier.
    import inspect
    from core import dossier_dorra
    seg = inspect.getsource(dossier_dorra.pages_du_dossier)
    assert 'hodour' not in seg
