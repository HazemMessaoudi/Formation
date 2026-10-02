# -*- coding: utf-8 -*-
"""المستحقّات المالية — الشاشة التلخيصية وإقرار المبلغ (v1.1).

Ce que ces tests défendent, dans l'ordre où l'agent les rencontre :

  • les ساعات se lisent dans **برنامج الدّورة**, au MEDÉ, arrondies vers le
    haut — le montant en découle sans qu'aucun chiffre ne soit saisi ;
  • un calcul qui ne tient pas NOMME ce qui manque et refuse de s'arrêter :
    pas de « 0.000 د » affiché comme s'il était un montant ;
  • le تأكيد fige le chiffrage en base — un جدول مالي révisé l'an prochain
    ne réécrit pas ce qui a été approuvé cette année ;
  • rouvrir un montant approuvé reste du ressort du مشرف عام.
"""

import pytest

from core import bareme_mali as bm


JETON = {'X-CSRF-Token': 'jeton-de-test'}


# ─── Outillage ───────────────────────────────────────────────────────────────

def _p(nom, grade, uid):
    return {'nom_prenom': nom, 'grade': grade, 'identifiant_unique': uid,
            'lieu_travail': 'القصرين', 'jiha_marjiiya': ''}


def _dorra(db, participants, grade_formateur='المقدم', plages=(('08:30', '12:30'),),
           muqarrar=True):
    """Une dorra enregistrée définitivement, برنامج compris.

    Le برنامج est ce qui porte les ساعات : sans lui rien ne se chiffre, et
    c'est précisément l'un des cas qu'on veut pouvoir éprouver.
    """
    annee = db.annee_registre()
    lid = db.save_programme(
        'interne', 'فيفري', annee,
        [{'titre': 'تحرير المحاضر', 'grade': grade_formateur,
          'nom_formateur': 'زياد البوهلالي', 'lieu_travail': '',
          'date_formation': f'{annee}-02-10', 'periode': 'صباحا',
          'lieu_formation': 'القصرين'}],
        'حازم مسعودي', 'النقيب')
    db.verrouiller_lettre(lid, 'interne')
    fid = db.get_lettre_detail(lid)['formations'][0]['id']
    db.save_participants(lid, fid, participants)
    if plages is not None:
        db.save_programme_data(fid, {
            'reference': 'ref', 'moment': 'صباحا',
            'rows': [{'type': 'row', 'participants': 'الجميع',
                      'activity': 'نشاط', 'time_debut': d, 'time_fin': f}
                     for d, f in plages]})
    db.save_memo_data(fid, {'objet': 'إعلام', 'corps': 'نصّ',
                            'moujah': [{'nom': 'الإدارة الجهوية'}]}, confirmer=True)
    ok, _ = db.finaliser_formation(fid)
    assert ok
    if muqarrar:                         # l'écran «مقرّر الدورة» franchi (v1.4d)
        db.save_muqarrar_dorra(fid, '2026/145', f'{annee}-02-20')   # v1.6.1 : après la دورة
    return fid


def _jusquau_classement(db, fid, classe=None):
    """Amène la dorra à l'état « الصنف محدَّد » — l'entrée de l'écran 3."""
    participants = db.get_hodour(fid)
    db.save_hodour(fid, {p['id']: True for p in participants})
    if classe is None:
        classe = db.calculer_classe(fid)[0]
    ok, _ = db.confirmer_classe(fid, classe)
    assert ok, 'le صنف doit être confirmé avant la شاشة التلخيصية'
    return classe


# ═══ Le calcul, de bout en bout ══════════════════════════════════════════════

def test_le_montant_se_deduit_sans_aucune_saisie(db):
    """المقدم (مجموعة I) × صنف أ1 = 25 د ; 08:30→12:30 = 4 ساعات."""
    fid = _dorra(db, [_p('أ', 'المقدم', '1'), _p('ب', 'العقيد', '2')])
    _jusquau_classement(db, fid, 'أ1')

    c = db.calculer_mustahaqqat(fid)
    assert c['chiffrable'], c['motifs']
    assert (c['debut'], c['fin']) == ('08:30', '12:30')
    assert c['heures'] == 4
    assert c['groupe'] == 'I'
    assert c['taux'] == 25.0
    assert c['montant'] == 100.0


def test_toute_fraction_dheure_entamee_est_payee_en_entier(db):
    """08:30 → 12:00 = 3h30 vécues, 4 heures payées."""
    fid = _dorra(db, [_p('أ', 'المقدم', '1')], plages=(('08:30', '12:00'),))
    _jusquau_classement(db, fid, 'أ1')

    c = db.calculer_mustahaqqat(fid)
    assert c['minutes'] == 210 and c['heures'] == 4
    assert c['arrondi'] is True
    assert c['montant'] == 100.0


def test_la_duree_est_le_mede_pauses_comprises(db):
    """Décision de l'utilisateur : المدى, pas المجموع.

    Deux فقرات séparées d'une heure creuse : la somme donnerait 3 heures,
    le مدى en donne 4 — et c'est 4 qui se paie.
    """
    fid = _dorra(db, [_p('أ', 'المقدم', '1')],
                 plages=(('08:30', '10:00'), ('11:00', '12:00')))
    _jusquau_classement(db, fid, 'أ1')

    c = db.calculer_mustahaqqat(fid)
    assert (c['debut'], c['fin']) == ('08:30', '12:00')
    assert c['heures'] == 4


def test_les_asnaf_b_j_d_se_paient_au_meme_taux(db):
    """« الاصناف ب ج ود يتم احتساب خلاصها بنفس القيمة »."""
    montants = []
    for classe, grade in (('ب', 'الوكيل'), ('ج', 'العريف'), ('د', 'الرقيب أول')):
        fid = _dorra(db, [_p('أ', grade, f'u{classe}')], grade_formateur='المقدم')
        _jusquau_classement(db, fid, classe)
        montants.append(db.calculer_mustahaqqat(fid)['montant'])
    assert len(set(montants)) == 1, 'ب، ج، د doivent payer pareil'
    assert montants[0] == 4 * 15.0


def test_le_groupe_du_formateur_change_le_taux_pas_le_sanf(db):
    """Même dorra, même صنف : seul le grade du مكوّن fait varier le prix."""
    resultats = {}
    for grade, attendu in (('المقدم', 25.0), ('الرائد', 20.0),
                           ('الملازم', 12.5), ('الوكيل', 9.0)):
        fid = _dorra(db, [_p('أ', 'المقدم', f'u{grade}')], grade_formateur=grade)
        _jusquau_classement(db, fid, 'أ1')
        resultats[grade] = db.calculer_mustahaqqat(fid)['taux']
        assert resultats[grade] == attendu


# ═══ Ce qui empêche de chiffrer est dit, pas tu ══════════════════════════════

def test_un_barnamaj_sans_horaire_ne_donne_pas_un_montant_nul(db):
    """Un « 0.000 د » affiché serait un montant. Il faut nommer le manque."""
    fid = _dorra(db, [_p('أ', 'المقدم', '1')], plages=None)
    _jusquau_classement(db, fid, 'أ1')

    c = db.calculer_mustahaqqat(fid)
    assert not c['chiffrable']
    assert c['montant'] is None
    assert any('توقيت' in m for m in c['motifs'])


def test_une_rutba_hors_du_bareme_bloque_le_chiffrage(db):
    """الرقيب n'est pas dans le texte : on le dit au lieu de l'inventer."""
    fid = _dorra(db, [_p('أ', 'المقدم', '1')], grade_formateur='الرقيب')
    _jusquau_classement(db, fid, 'أ1')

    c = db.calculer_mustahaqqat(fid)
    assert not c['chiffrable']
    assert any('رتبة' in m for m in c['motifs'])


def test_une_case_videe_dans_les_reglages_bloque_le_chiffrage(db):
    fid = _dorra(db, [_p('أ', 'المقدم', '1')])
    _jusquau_classement(db, fid, 'أ1')
    db.set_taux_bareme_mali('I', 'أ1', 0)

    c = db.calculer_mustahaqqat(fid)
    assert not c['chiffrable'] and c['montant'] is None


def test_un_calcul_qui_ne_tient_pas_ne_sarrete_pas(db):
    """Mieux vaut renvoyer l'agent au manque que d'arrêter un montant faux."""
    fid = _dorra(db, [_p('أ', 'المقدم', '1')], plages=None)
    _jusquau_classement(db, fid, 'أ1')

    ok, message = db.confirmer_mustahaqqat(fid)
    assert not ok and 'توقيت' in message
    assert db.get_dorra_mustahaqqat(fid)['etat'] != 'acheve'


def test_le_sanf_doit_preceder_le_chiffrage(db):
    fid = _dorra(db, [_p('أ', 'المقدم', '1')])
    db.save_hodour(fid, {p['id']: True for p in db.get_hodour(fid)})
    ok, message = db.confirmer_mustahaqqat(fid)
    assert not ok and 'صنف' in message


# ═══ Le تأكيد fige le chiffrage ══════════════════════════════════════════════

def test_le_takid_arrete_le_montant_et_acheve_la_dorra(db):
    fid = _dorra(db, [_p('أ', 'المقدم', '1')])
    _jusquau_classement(db, fid, 'أ1')

    ok, info = db.confirmer_mustahaqqat(fid)
    assert ok and info['montant'] == 100.0

    dorra = db.get_dorra_mustahaqqat(fid)
    assert dorra['etat'] == 'acheve'
    assert dorra['mu_acheve_at']
    assert dorra['mu_heures'] == 4 and dorra['mu_taux'] == 25.0
    assert dorra['mu_heure_debut'] == '08:30' and dorra['mu_heure_fin'] == '12:30'


def test_une_dorra_arretee_passe_dans_les_manjaza(db):
    fid = _dorra(db, [_p('أ', 'المقدم', '1')])
    _jusquau_classement(db, fid, 'أ1')
    assert fid in [d['id'] for d in db.dorrat_mustahaqqat_ghayr_manjaza()]

    db.confirmer_mustahaqqat(fid)
    assert fid in [d['id'] for d in db.dorrat_mustahaqqat_manjaza()]
    assert fid not in [d['id'] for d in db.dorrat_mustahaqqat_ghayr_manjaza()]


def test_un_bareme_revise_ne_reecrit_pas_un_montant_deja_approuve(db):
    """C'est la raison d'être du figeage : ce qui a été arrêté est arrêté."""
    fid = _dorra(db, [_p('أ', 'المقدم', '1')])
    _jusquau_classement(db, fid, 'أ1')
    db.confirmer_mustahaqqat(fid)

    db.set_taux_bareme_mali('I', 'أ1', 40.0)      # le texte est révisé

    c = db.calculer_mustahaqqat(fid)
    assert c['fige'] is True
    assert c['taux'] == 25.0 and c['montant'] == 100.0


def test_on_ne_confirme_pas_deux_fois(db):
    fid = _dorra(db, [_p('أ', 'المقدم', '1')])
    _jusquau_classement(db, fid, 'أ1')
    assert db.confirmer_mustahaqqat(fid)[0]
    ok, message = db.confirmer_mustahaqqat(fid)
    assert not ok and 'منجزة' in message


def test_rouvrir_efface_le_chiffrage_fige(db):
    """Le montant figé ne vaut plus rien dès qu'on rouvre ce qui le fonde."""
    fid = _dorra(db, [_p('أ', 'المقدم', '1')])
    _jusquau_classement(db, fid, 'أ1')
    db.confirmer_mustahaqqat(fid)

    db.rouvrir_mustahaqqat(fid)
    dorra = db.get_dorra_mustahaqqat(fid)
    assert dorra['etat'] == 'classe'
    assert not dorra['mu_acheve_at'] and not dorra['mu_montant']
    assert db.calculer_mustahaqqat(fid)['fige'] is False


# ═══ Le جدول المالي, modifiable depuis الإعدادات ═════════════════════════════

def test_le_bareme_officiel_est_seme_au_premier_demarrage(db):
    grille = db.get_bareme_mali()
    assert grille[('I', 'أ1')] == 25.0
    assert grille[('IV', bm.COLONNE_BJD)] == 6.0


def test_la_colonne_a3_existe_et_reste_disponible(db):
    """« لا يوجد صنف أ3 ولكن دعه فارغا قابلا للتحيين »."""
    assert db.get_bareme_mali()[('I', 'أ3')] == 18.0
    assert 'أ3' in bm.COLONNES


def test_un_taux_se_corrige_et_sapplique_aussitot(db):
    fid = _dorra(db, [_p('أ', 'المقدم', '1')])
    _jusquau_classement(db, fid, 'أ1')
    assert db.calculer_mustahaqqat(fid)['montant'] == 100.0

    db.set_taux_bareme_mali('I', 'أ1', 30.0)
    assert db.calculer_mustahaqqat(fid)['montant'] == 120.0


def test_un_taux_absurde_est_refuse(db):
    assert not db.set_taux_bareme_mali('I', 'أ1', -5)
    assert not db.set_taux_bareme_mali('I', 'أ1', 'مبلغ')
    assert not db.set_taux_bareme_mali('V', 'أ1', 10)
    assert db.get_bareme_mali()[('I', 'أ1')] == 25.0


def test_une_rutba_hors_texte_se_rattache_a_la_main(db):
    """« في حالة وجود رتبة خارج الجدول يمكن القيام بالتحيينات اللازمة يدويا »."""
    fid = _dorra(db, [_p('أ', 'المقدم', '1')], grade_formateur='الرقيب')
    _jusquau_classement(db, fid, 'أ1')
    assert not db.calculer_mustahaqqat(fid)['chiffrable']

    db.set_groupe_grade('الرقيب', 'IV')
    c = db.calculer_mustahaqqat(fid)
    assert c['chiffrable'] and c['groupe'] == 'IV' and c['taux'] == 9.0


def test_les_rutab_hors_texte_apparaissent_sans_groupe(db):
    """L'agent doit VOIR lesquelles ne sont pas rattachées."""
    detail = {r['grade']: r['groupe'] for r in db.get_groupes_grades_detail()}
    assert detail['المقدم'] == 'I'
    assert detail['الرقيب'] == ''
    assert detail['السيد'] == ''


def test_la_remise_a_zero_rend_les_valeurs_officielles(db):
    db.set_taux_bareme_mali('I', 'أ1', 99.0)
    db.set_groupe_grade('المقدم', 'IV')
    db.reinitialiser_bareme_mali()

    assert db.get_bareme_mali()[('I', 'أ1')] == 25.0
    assert {r['grade']: r['groupe']
            for r in db.get_groupes_grades_detail()}['المقدم'] == 'I'


# ═══ Les écrans ══════════════════════════════════════════════════════════════

def test_lecran_deroule_le_calcul_au_lieu_de_lannoncer(db, client):
    """L'agent doit voir d'où vient le montant qu'il approuve."""
    fid = _dorra(db, [_p('أ', 'المقدم', '1')], plages=(('08:30', '12:00'),))
    _jusquau_classement(db, fid, 'أ1')

    html = client.get(f'/mustahaqqat/dorra/{fid}/qima').get_data(as_text=True)
    assert '08:30' in html and '12:00' in html      # d'où viennent les heures
    assert '3 ساعات و30 دقيقة' in html              # la durée vécue
    assert '25.000' in html                          # le prix de l'heure
    assert '100.000' in html                         # le montant
    assert 'التأكيد النهائي' in html               # v1.6 : bouton du مشرف


def test_lecran_nomme_le_manque_et_retire_le_bouton(db, client):
    fid = _dorra(db, [_p('أ', 'المقدم', '1')], plages=None)
    _jusquau_classement(db, fid, 'أ1')

    html = client.get(f'/mustahaqqat/dorra/{fid}/qima').get_data(as_text=True)
    assert 'تعذّر احتساب المستحقّات' in html
    assert 'id="btnConfirmer"' not in html, 'rien ne doit pouvoir être approuvé'
    # La page ne doit pas non plus PORTER de quoi approuver : une phrase de
    # confirmation au montant vide traînait ici tant que le script était émis
    # sans condition.
    assert 'سيُثبَّت المبلغ' not in html
    assert 'confirmerMustahaqqat' not in html


def test_la_route_de_takid_arrete_le_montant(db, client):
    fid = _dorra(db, [_p('أ', 'المقدم', '1')])
    _jusquau_classement(db, fid, 'أ1')

    rep = client.post(f'/mustahaqqat/dorra/{fid}/qima', headers=JETON)
    assert rep.status_code == 200
    assert rep.get_json()['montant_texte'] == '100.000'
    assert db.get_dorra_mustahaqqat(fid)['etat'] == 'acheve'


def test_la_route_de_takid_refuse_un_calcul_incomplet(db, client):
    fid = _dorra(db, [_p('أ', 'المقدم', '1')], plages=None)
    _jusquau_classement(db, fid, 'أ1')

    rep = client.post(f'/mustahaqqat/dorra/{fid}/qima', headers=JETON)
    assert rep.status_code == 400
    assert 'erreur' in rep.get_json()


def test_rouvrir_est_reserve_au_mochrif(db, monkeypatch):
    """Défaire un montant approuvé n'est pas un geste ordinaire."""
    from tests.conftest import _client_flask
    db.update_config('installation_faite', '1')
    fid = _dorra(db, [_p('أ', 'المقدم', '1')])
    _jusquau_classement(db, fid, 'أ1')
    db.confirmer_mustahaqqat(fid)

    agent = _client_flask(db, monkeypatch, role='user')
    assert agent.post(f'/mustahaqqat/dorra/{fid}/rouvrir',
                      headers=JETON).status_code == 403
    assert db.get_dorra_mustahaqqat(fid)['etat'] == 'acheve'

    admin = _client_flask(db, monkeypatch, role='admin')
    assert admin.post(f'/mustahaqqat/dorra/{fid}/rouvrir',
                      headers=JETON).status_code == 200
    assert db.get_dorra_mustahaqqat(fid)['etat'] == 'classe'


def test_lecran_des_reglages_affiche_la_grille_et_les_rattachements(client):
    html = client.get('/mustahaqqat/bareme-mali').get_data(as_text=True)
    assert 'الجدول المالي' in html
    assert '25.000' in html or 'value="25.0"' in html
    assert 'صنف ب / ج / د' in html
    assert 'المجموعة IV' in html


def test_les_reglages_se_modifient_depuis_lecran(db, client):
    rep = client.post('/mustahaqqat/bareme-mali',
                      data={'taux__I__أ1': '30.000',
                            'groupe__الرقيب': 'IV'},
                      headers=JETON)
    assert rep.status_code == 302
    assert db.get_bareme_mali()[('I', 'أ1')] == 30.0
    assert {r['grade']: r['groupe']
            for r in db.get_groupes_grades_detail()}['الرقيب'] == 'IV'


def test_les_reglages_sont_reserves_au_mochrif(db, monkeypatch):
    from tests.conftest import _client_flask
    db.update_config('installation_faite', '1')
    agent = _client_flask(db, monkeypatch, role='user')
    agent.post('/mustahaqqat/bareme-mali',
               data={'taux__I__أ1': '99.000'}, headers=JETON)
    assert db.get_bareme_mali()[('I', 'أ1')] == 25.0


def test_le_montant_arrete_apparait_dans_la_liste_des_manjaza(db):
    """Une dorra en cours n'a pas de montant : elle a une estimation."""
    fid = _dorra(db, [_p('أ', 'المقدم', '1')])
    _jusquau_classement(db, fid, 'أ1')

    en_cours = [d for d in db.dorrat_mustahaqqat_ghayr_manjaza() if d['id'] == fid][0]
    assert en_cours['montant_texte'] == ''

    db.confirmer_mustahaqqat(fid)
    achevee = [d for d in db.dorrat_mustahaqqat_manjaza() if d['id'] == fid][0]
    assert achevee['montant_texte'] == '100.000'


def test_la_lawha_ne_totalise_que_ce_qui_est_arrete(db):
    fid = _dorra(db, [_p('أ', 'المقدم', '1')])
    _jusquau_classement(db, fid, 'أ1')
    assert db.get_stats_mustahaqqat()['montant_total'] == 0

    db.confirmer_mustahaqqat(fid)
    stats = db.get_stats_mustahaqqat()
    assert stats['montant_total'] == 100.0
    assert stats['heures_payees'] == 4
    assert stats['montant_texte'] == '100.000'
