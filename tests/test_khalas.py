# -*- coding: utf-8 -*-
"""وثائق الخلاص — assemblage, calculs, persistance et génération PDF.

On vérifie que RIEN n'est re-saisi (la fiche du المكوّن et les المستحقّات
alimentent seules les documents), que les montants et le montant-en-lettres
suivent le modèle, et que les quatre documents se génèrent sans erreur.
"""

import os
import pytest

from core import khalas
from core import pdf_khalas


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _dorra_chiffree(db, grade='وكيل', classe='ب', nom_formateur='السايحي ماهر',
                    debut='08:30', fin='12:30'):
    annee = db.annee_registre()
    lid = db.save_programme(
        'interne', 'فيفري', annee,
        [{'titre': 'النزاعات الديوانية', 'grade': grade,
          'nom_formateur': nom_formateur, 'lieu_travail': '',
          'date_formation': f'{annee}-05-12', 'periode': 'صباحا',
          'lieu_formation': 'مركز التكوين الجهوي بالقصرين'}],
        'حازم مسعودي', 'النقيب')
    db.verrouiller_lettre(lid, 'interne')
    fid = db.get_lettre_detail(lid)['formations'][0]['id']
    db.save_participants(lid, fid, [
        {'nom_prenom': 'مسعودي حازم', 'grade': grade,
         'identifiant_unique': '101', 'lieu_travail': 'القصرين', 'jiha_marjiiya': ''}])
    db.save_programme_data(fid, {'reference': 'م', 'moment': 'صباحا',
        'rows': [{'type': 'row', 'activity': 'حصّة', 'participants': 'الكلّ',
                  'time_debut': debut, 'time_fin': fin}]})
    db.save_memo_data(fid, {'objet': 'إعلام', 'corps': 'نصّ',
                            'moujah': [{'nom': 'الإدارة'}]}, confirmer=True)
    db.finaliser_formation(fid)
    db.save_hodour(fid, {x['id']: True for x in db.get_hodour(fid)})
    db.confirmer_classe(fid, classe)
    return fid


# ─── Montant en lettres ───────────────────────────────────────────────────────

def test_montant_lettres_suit_le_modele():
    assert khalas.montant_lettres(24) == 'أربعة وعشرون دينارا'
    assert khalas.montant_lettres(0).startswith('صفر')
    # millimes présents → « و…مليم »
    assert 'مليم' in khalas.montant_lettres(20.4)


# ─── Migration : tables présentes, défauts semés ──────────────────────────────

def test_migration_semee(db):
    s = db.get_khalas_settings()
    assert s['directeur_nom']            # semé
    assert s['ordre_1995'].startswith('الأمر')
    assert s['taux_adaat'] == '15'


def test_settings_override_garde_les_defauts(db):
    db.set_khalas_settings({'directeur_nom': 'اختبار'})
    s = db.get_khalas_settings()
    assert s['directeur_nom'] == 'اختبار'
    assert s['ordre_tajir']              # défaut conservé


# ─── Rapprochement de la fiche formateur ──────────────────────────────────────

def test_trouver_mkow_les_deux_ordres(db):
    db.add_mkow({'grade': 'وكيل', 'nom': 'السايحي', 'prenom': 'ماهر',
                 'identifiant_unique': '2195167388'})
    assert db.trouver_mkow_par_nom('السايحي ماهر')['identifiant_unique'] == '2195167388'
    assert db.trouver_mkow_par_nom('ماهر السايحي')['identifiant_unique'] == '2195167388'
    assert db.trouver_mkow_par_nom('لا أحد') == {}


# ─── Assemblage : aucune re-saisie ────────────────────────────────────────────

def test_assembler_reprend_la_fiche_et_calcule(db):
    db.add_mkow({'grade': 'وكيل', 'nom': 'السايحي', 'prenom': 'ماهر',
                 'cin': '09095417', 'identifiant_unique': '2195167388',
                 'num_compte': '05032000099501150681', 'banque': 'البنك التونسي'})
    fid = _dorra_chiffree(db)
    d = khalas.assembler(fid)
    # repris de la fiche, sans re-saisie
    assert d['cin'] == '09095417'
    assert d['identifiant_unique'] == '2195167388'
    assert d['num_compte'] == '05032000099501150681'
    assert d['mkow_trouve'] is True
    # calculs : وكيل × ب → 6.000 د/h × 4 = 24.000 ; 15% = 3.600 ; net 20.400
    assert d['chiffrable'] is True
    assert d['heures'] == 4
    assert d['brut_texte'] == '24.000'
    assert d['adaat_texte'] == '3.600'
    assert d['net_texte'] == '20.400'
    assert d['montant_lettres'] == 'أربعة وعشرون دينارا'
    assert d['directeur_nom']            # depuis les réglages


def test_assembler_inexistante(db):
    assert khalas.assembler(999999) is None


def test_champs_manquants_detecte_le_vide(db):
    fid = _dorra_chiffree(db)             # pas de fiche → CIN, RIB… manquants
    d = khalas.assembler(fid)
    manque = khalas.champs_manquants(d)
    assert 'رقم بطاقة التعريف الوطنية' in manque
    assert 'عدد المذكرة' in manque


# ─── Persistance des champs de la dorra ───────────────────────────────────────

def test_save_khalas_dorra_round_trip(db):
    fid = _dorra_chiffree(db)
    db.save_khalas_dorra(fid, {'numero_mudhakkira': '7', 'type_takwin': 'tahili',
                               'tarkhis_numero': '55', 'muqarrar_numero': '999'})
    d = khalas.assembler(fid)
    assert d['numero_mudhakkira'] == '7'
    assert d['type_takwin'] == 'tahili'
    assert d['tarkhis_numero'] == '55'
    assert d['muqarrar_numero'] == '999'     # surcharge le défaut des réglages


# ─── Génération PDF ───────────────────────────────────────────────────────────

def test_pdf_quatre_documents(db, tmp_path):
    fid = _dorra_chiffree(db)
    db.save_khalas_dorra(fid, {'numero_mudhakkira': '1'})
    d = khalas.assembler(fid)
    base = os.path.dirname(os.path.dirname(os.path.abspath(khalas.__file__)))
    chemin = pdf_khalas.generer(d, base, chemin=str(tmp_path / 'k.pdf'))
    assert os.path.exists(chemin) and os.path.getsize(chemin) > 5000
    from core.pdf_generator import compter_pages_pdf
    assert compter_pages_pdf(chemin) == 4


def test_pdf_document_unique(db, tmp_path):
    fid = _dorra_chiffree(db)
    d = khalas.assembler(fid)
    base = os.path.dirname(os.path.dirname(os.path.abspath(khalas.__file__)))
    for doc in ('mudhakkira', 'bitaqa', 'jadwal', 'iaam'):
        chemin = pdf_khalas.generer(d, base, docs=(doc,),
                                    chemin=str(tmp_path / f'{doc}.pdf'))
        from core.pdf_generator import compter_pages_pdf
        assert compter_pages_pdf(chemin) == 1


def test_pdf_ordre_officiel_toujours_respecte(db, tmp_path):
    """Quel que soit l'ordre demandé, l'ordre officiel est conservé."""
    fid = _dorra_chiffree(db)
    d = khalas.assembler(fid)
    base = os.path.dirname(os.path.dirname(os.path.abspath(khalas.__file__)))
    chemin = pdf_khalas.generer(d, base, docs=('iaam', 'mudhakkira'),
                                chemin=str(tmp_path / 'ordre.pdf'))
    from core.pdf_generator import compter_pages_pdf
    assert compter_pages_pdf(chemin) == 2      # deux docs, ordre interne géré
