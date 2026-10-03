# -*- coding: utf-8 -*-
"""المراجعة النهائيّة — للدورة، ثمّ للبرنامج كامل، ثمّ المصادقة.

Hazem a demandé, à l'usage, deux garde-fous de plus :

* avant d'enregistrer une دورة, une **مراجعة** de ce qu'elle a produit — quels
  documents, sous quel عدد, ce qui manque ;
* quand toutes les دورات sont enregistrées, un **زر نهائي** qui n'accepte de
  sceller le برنامج qu'après avoir vérifié سلامة كلّ المعطيات وترقيم المراسلات.

Ces tests défendent : la مراجعة dit vrai ; la vérification attrape ce qui
cloche (document manquant, دورة non enregistrée, عدد orphelin) ; et la مصادقة
refuse tant qu'un seul problème demeure, mais scelle sans broncher quand tout
est sain."""

import pytest


def _programme_confirme(db, mois='فيفري'):
    annee = db.annee_registre()
    lid = db.save_programme(
        'interne', mois, annee,
        [{'titre': f'دورة {mois}', 'grade': 'مقدم', 'nom_formateur': 'زياد البوهلالي',
          'lieu_travail': '', 'date_formation': f'{annee}-02-10', 'periode': '',
          'lieu_formation': 'مركز التكوين الجهوي بالقصرين'}],
        'حازم مسعودي', 'النقيب')
    db.verrouiller_lettre(lid, 'interne')
    return lid


def _formation_id(db, lid):
    return db.get_lettre_detail(lid)['formations'][0]['id']


def _achever_dorra(db, lid, fid, finaliser=True):
    """Mène une دورة jusqu'au bout : مشاركون → بطاقة → برنامج → مذكّرة → تسجيل."""
    db.save_participants(lid, fid, [
        {'nom_prenom': 'سمير الوسلاتي', 'grade': 'عريف', 'identifiant_unique': '80012',
         'lieu_travail': 'بنزرت', 'jiha_marjiiya': ''}])
    db.save_bataqa_data(fid, {'mustahdafun': 'أعوان', 'objectifs': 'الإتقان'})
    db.save_programme_data(fid, {'reference': '', 'moment': 'صباحا', 'rows': [
        {'type': 'row', 'time': 'من 09:00 إلى 12:00', 'activity': 'المحاضر',
         'participants': 'الجميع'}]})
    db.save_memo_data(fid, {'objet': 'إعلام', 'corps': 'نصّ المذكّرة',
                            'moujah': [{'nom': 'السيّد المدير', 'type': ''}]},
                      confirmer=True)
    if finaliser:
        ok, _ = db.finaliser_formation(fid)
        assert ok


# ─── مراجعة الدورة ───────────────────────────────────────────────────────────

def test_revue_dorra_dit_ce_qui_est_pret(db):
    lid = _programme_confirme(db)
    fid = _formation_id(db, lid)
    db.save_participants(lid, fid, [
        {'nom_prenom': 'سمير الوسلاتي', 'grade': 'عريف', 'identifiant_unique': '80012',
         'lieu_travail': '', 'jiha_marjiiya': ''}])
    r = db.revue_dorra(fid)
    assert r['nb_participants'] == 1
    docs = {d['cle']: d['ok'] for d in r['documents']}
    assert docs['participants'] is True
    assert docs['bataqa'] is False       # pas encore
    assert r['complet'] is False
    assert 'البطاقة البيداغوجية' in r['manquant']


def test_revue_dorra_porte_le_adad_de_la_memo(db):
    lid = _programme_confirme(db)
    fid = _formation_id(db, lid)
    _achever_dorra(db, lid, fid, finaliser=False)
    r = db.revue_dorra(fid)
    assert r['complet'] is True
    assert r['manquant'] == []
    assert r['memo_ref']                 # la مذكّرة a tiré son عدد
    assert r['memo_numero']


def test_revue_dorra_inexistante(db):
    assert db.revue_dorra(99999) is None


# ─── مراجعة سلامة البرنامج ───────────────────────────────────────────────────

def test_integrite_signale_dorra_incomplete(db):
    lid = _programme_confirme(db)
    problemes = db.verifier_integrite_programme(lid)
    # Rien n'a été fait sur la دورة : plusieurs manques attendus.
    assert any('مشاركون' in p for p in problemes)
    assert any('لم تُسجَّل' in p or 'غير مؤكَّدة' in p for p in problemes)


def test_integrite_attrape_le_adad_orphelin(db):
    """Le cœur du correctif vu du côté vérification : un عدد 'directeur' au
    سجلّ sans مراسلة en face doit être signalé."""
    lid = _programme_confirme(db)
    _, num, _, _ = db.attribuer_numero_dr(lid, 'externe', 'بنزرت')
    # On simule l'ancien défaut : la ligne dr_lettres disparaît, le عدد reste.
    conn = db.get_connection()
    try:
        conn.execute('DELETE FROM dr_lettres WHERE lettre_id=?', (lid,))
        conn.commit()
    finally:
        conn.close()
    problemes = db.verifier_integrite_programme(lid)
    assert any('لم تعد موجودة' in p for p in problemes)


def test_integrite_propre_quand_tout_est_enregistre(db):
    lid = _programme_confirme(db)
    fid = _formation_id(db, lid)
    _achever_dorra(db, lid, fid, finaliser=True)
    assert db.verifier_integrite_programme(lid) == []


# ─── المصادقة النهائيّة ──────────────────────────────────────────────────────

def test_sceller_refuse_si_probleme(db):
    lid = _programme_confirme(db)
    ok, problemes = db.sceller_programme(lid)
    assert not ok
    assert isinstance(problemes, list) and problemes
    assert not db.programme_est_scelle(lid)


def test_sceller_reussit_quand_tout_est_sain(db):
    lid = _programme_confirme(db)
    fid = _formation_id(db, lid)
    _achever_dorra(db, lid, fid, finaliser=True)
    ok, quand = db.sceller_programme(lid)
    assert ok
    assert db.programme_est_scelle(lid)


def test_sceller_est_idempotent(db):
    lid = _programme_confirme(db)
    fid = _formation_id(db, lid)
    _achever_dorra(db, lid, fid, finaliser=True)
    ok1, q1 = db.sceller_programme(lid)
    ok2, q2 = db.sceller_programme(lid)
    assert ok1 and ok2
    assert q1 == q2          # même horodatage : rien n'a bougé


def test_revue_programme_reunit_tout(db):
    lid = _programme_confirme(db)
    fid = _formation_id(db, lid)
    db.attribuer_numero_dr(lid, 'externe', 'بنزرت')
    _achever_dorra(db, lid, fid, finaliser=True)
    r = db.revue_programme(lid)
    assert r['ref']
    assert r['tout_finalise'] is True
    assert len(r['dorrat']) == 1
    assert len(r['dr_lettres']) == 1
    assert r['coherent'] is True
    # Le سجلّ du برنامج : sa مراسلة (interne), sa مراسلة directeur (externe),
    # la مذكّرة (interne). Au moins trois lignes.
    assert len(r['registre']) >= 3


def test_revue_programme_inexistant(db):
    assert db.revue_programme(99999) is None
