# -*- coding: utf-8 -*-
"""Le جدول المالي : des heures, un taux, un montant (v1.1).

Ce module décide d'argent. On l'éprouve donc cas par cas, et d'abord sur la
règle que l'utilisateur a posée lui-même : **toute fraction d'heure entamée
est due en entier**. Les exemples qu'il a validés en conversation sont repris
ici tels quels — ils sont le cahier des charges.
"""

import pytest

from core import bareme_mali as bm


# ═══ L'arrondi : « ما إن تتجاوز الساعة ولو بدقيقة يحسب البرنامج الساعة الموالية »

@pytest.mark.parametrize('minutes,attendu', [
    (0,    0),      # rien
    (1,    1),      # une minute est une heure due
    (59,   1),
    (60,   1),      # une heure pile reste une heure
    (61,   2),      # une minute de plus : deux heures
    (180,  3),      # 3h00 pile
    (181,  4),      # 3h01  → مثال المستعمل
    (210,  4),      # 3h30  → مثال المستعمل
    (240,  4),      # 4h00 pile
    (241,  5),      # 4h01  → مثال المستعمل
    (300,  5),      # 5h00 pile
    (301,  6),      # 5h01  → مثال المستعمل
    (165,  3),      # 2h45  → مثال المستعمل
])
def test_toute_fraction_dheure_est_due_en_entier(minutes, attendu):
    assert bm.arrondir_heures(minutes) == attendu


def test_une_duree_negative_ou_absurde_ne_paie_rien():
    assert bm.arrondir_heures(-10) == 0
    assert bm.arrondir_heures(None) == 0


# ═══ Les exemples de l'utilisateur, de bout en bout ══════════════════════════

def _prog(*plages):
    return [{'type': 'row', 'time_debut': d, 'time_fin': f} for d, f in plages]


@pytest.mark.parametrize('debut,fin,heures', [
    ('08:30', '12:30', 4),   # 4h pile
    ('08:30', '12:00', 4),   # 3h30 → 4
    ('08:30', '11:31', 4),   # 3h01 → 4
    ('08:30', '11:30', 3),   # 3h pile
    ('09:00', '14:00', 5),   # 5h pile
    ('09:00', '13:01', 5),   # 4h01 → 5
    ('08:00', '10:45', 3),   # 2h45 → 3
    ('08:00', '09:01', 2),   # 1h01 → 2
    ('08:30', '09:30', 1),   # 1h pile
])
def test_les_exemples_valides_par_lutilisateur(debut, fin, heures):
    d = bm.heures_du_programme(_prog((debut, fin)))
    assert d['heures'] == heures
    assert d['debut'] == debut and d['fin'] == fin


# ═══ Les ساعات se lisent dans برنامج الدّورة, au MEDÉ ════════════════════════

def test_le_mede_va_du_premier_debut_a_la_derniere_fin():
    """Plusieurs فقرات : c'est l'amplitude qui compte, pas leur somme."""
    d = bm.heures_du_programme(_prog(('08:30', '10:00'),
                                     ('10:15', '12:30')))
    assert (d['debut'], d['fin']) == ('08:30', '12:30')
    assert d['minutes'] == 240          # 08:30 → 12:30
    assert d['heures'] == 4


def test_une_pause_non_consignee_reste_dans_la_duree():
    """La décision de l'utilisateur : المدى, pas المجموع.

    Une heure de creux entre deux فقرات est vécue par le مكوّن : elle est
    payée. La somme des فقرات donnerait 3 heures, le مدى en donne 4.
    """
    rows = _prog(('08:30', '10:00'), ('11:00', '12:00'))
    d = bm.heures_du_programme(rows)
    assert d['minutes'] == 210          # 08:30 → 12:00
    assert d['heures'] == 4             # et non 3 (somme = 2h30)


def test_les_forcat_sont_lues_dans_le_desordre():
    """Rien ne garantit que les فقرات soient triées dans le JSON."""
    d = bm.heures_du_programme(_prog(('10:15', '12:30'),
                                     ('08:30', '10:00')))
    assert (d['debut'], d['fin']) == ('08:30', '12:30')


def test_un_entete_de_date_nest_pas_une_forat():
    rows = [{'type': 'date_header', 'time_debut': '00:00', 'time_fin': '23:59'},
            {'type': 'row', 'time_debut': '09:00', 'time_fin': '12:00'}]
    assert bm.heures_du_programme(rows)['heures'] == 3


def test_une_forat_a_moitie_saisie_est_ecartee():
    """Un début sans fin ne porte aucune durée — il ne doit pas la fausser."""
    rows = _prog(('08:30', '11:30')) + [{'type': 'row', 'time_debut': '14:00',
                                         'time_fin': ''}]
    assert bm.heures_du_programme(rows)['fin'] == '11:30'


def test_une_forat_inversee_est_ecartee():
    rows = _prog(('09:00', '12:00'), ('15:00', '14:00'))
    assert bm.heures_du_programme(rows)['fin'] == '12:00'


def test_un_programme_muet_ne_paie_rien():
    for vide in ([], None, [{'type': 'row', 'time_debut': '', 'time_fin': ''}]):
        d = bm.heures_du_programme(vide)
        assert d['heures'] == 0 and d['debut'] == ''


def test_lheure_sécrit_avec_deux_points_ou_un_point():
    """« 8.30 » circule dans les برامج saisis à la main."""
    assert bm.lire_heure('08:30') == bm.lire_heure('8.30') == 510


def test_une_heure_impossible_est_illisible():
    for mauvais in ('25:00', '08:75', 'صباحا', '', None, '830'):
        assert bm.lire_heure(mauvais) is None


def test_larrondi_est_signale_quand_il_ajoute_quelque_chose():
    assert bm.heures_du_programme(_prog(('08:30', '11:31')))['arrondi'] is True
    assert bm.heures_du_programme(_prog(('08:30', '11:30')))['arrondi'] is False


# ═══ رتبة du مكوّن → groupe du barème ════════════════════════════════════════

@pytest.mark.parametrize('grade,groupe', [
    ('العميد', 'I'), ('العقيد', 'I'), ('المقدم', 'I'), ('اللواء', 'I'),
    ('الرائد', 'II'), ('النقيب', 'II'),
    ('الملازم أول', 'III'), ('الملازم', 'III'),
    ('الوكيل أول', 'IV'), ('الوكيل', 'IV'), ('العريف', 'IV'),
])
def test_chaque_rutba_du_texte_a_son_groupe(grade, groupe):
    assert bm.groupe_du_grade(grade) == groupe


def test_une_rutba_secrit_de_plusieurs_facons():
    """« العقيد للديوانة », « عقيد », « العقيد » : une seule رتبة."""
    for graphie in ('العقيد', 'عقيد', 'العقيد للديوانة', ' العقيد  '):
        assert bm.groupe_du_grade(graphie) == 'I'


def test_une_rutba_hors_du_texte_na_pas_de_groupe():
    """Le groupe IV s'arrête à عريف : رقيب n'y est pas, et les مدنيّون non plus.

    Mieux vaut le dire que de les payer à un taux que le texte ne leur donne
    pas — l'agent les rattachera lui-même dans الإعدادات.
    """
    for hors in ('الرقيب', 'الرقيب أول', 'السيد', 'السيدة', 'رتبة مخترعة', ''):
        assert bm.groupe_du_grade(hors) == bm.GROUPE_INCONNU


def test_le_centre_peut_rattacher_une_rutba_lui_meme():
    assert bm.groupe_du_grade('الرقيب', {'الرقيب': 'IV'}) == 'IV'


def test_un_groupe_efface_a_la_main_ne_retombe_pas_sur_le_defaut():
    """Un centre qui retire son groupe à une رتبة l'a voulu."""
    assert bm.groupe_du_grade('العقيد', {'العقيد': ''}) == bm.GROUPE_INCONNU


# ═══ صنف الدّورة → colonne du barème ═════════════════════════════════════════

def test_les_asnaf_b_j_d_partagent_une_colonne():
    """« الاصناف ب ج ود يتم احتساب خلاصها بنفس القيمة »."""
    assert (bm.colonne_de_classe('ب') == bm.colonne_de_classe('ج')
            == bm.colonne_de_classe('د') == bm.COLONNE_BJD)


def test_les_asnaf_a_ont_chacun_leur_colonne():
    assert bm.colonne_de_classe('أ1') == 'أ1'
    assert bm.colonne_de_classe('أ2') == 'أ2'
    assert bm.colonne_de_classe('أ3') == 'أ3'


def test_un_sanf_inconnu_na_pas_de_colonne():
    for inconnu in ('', None, 'ه', 'أ4'):
        assert bm.colonne_de_classe(inconnu) == ''


# ═══ Le taux ═════════════════════════════════════════════════════════════════

@pytest.mark.parametrize('groupe,classe,taux', [
    ('I',   'أ1', 25.0),  ('I',   'أ2', 21.5),  ('I',   'ب', 15.0),
    ('II',  'أ1', 20.0),  ('II',  'أ2', 18.0),  ('II',  'ج', 11.0),
    ('III', 'أ1', 12.5),  ('III', 'أ2', 11.5),  ('III', 'د',  9.0),
    ('IV',  'أ1',  9.0),  ('IV',  'أ2',  8.0),  ('IV',  'ب',  6.0),
])
def test_le_bareme_officiel_case_par_case(groupe, classe, taux):
    assert bm.taux_horaire(groupe, classe) == taux


def test_b_j_et_d_se_paient_au_meme_taux():
    for groupe in bm.GROUPES:
        taux = {bm.taux_horaire(groupe, c) for c in ('ب', 'ج', 'د')}
        assert len(taux) == 1, f'{groupe} paie ب، ج، د différemment'


def test_un_couple_sans_taux_ne_rend_pas_zero_mais_rien():
    """Zéro serait un montant. `None` dit qu'il n'y a pas de montant."""
    assert bm.taux_horaire(bm.GROUPE_INCONNU, 'أ1') is None
    assert bm.taux_horaire('I', '') is None
    assert bm.taux_horaire('I', 'أ1', {('I', 'أ1'): 0}) is None


def test_le_bareme_de_la_base_prime_sur_le_defaut():
    assert bm.taux_horaire('I', 'أ1', {('I', 'أ1'): 30.0}) == 30.0


# ═══ Le montant ══════════════════════════════════════════════════════════════

def test_le_montant_est_le_produit_des_deux():
    assert bm.calculer_montant(4, 25.0) == 100.0
    assert bm.calculer_montant(3, 11.5) == 34.5


def test_sans_taux_ou_sans_heures_il_ny_a_pas_de_montant():
    assert bm.calculer_montant(4, None) is None
    assert bm.calculer_montant(0, 25.0) is None


def test_le_dinar_secrit_a_trois_decimales():
    assert bm.formater_dinars(75) == '75.000'
    assert bm.formater_dinars(11.5) == '11.500'
    assert bm.formater_dinars(None) == ''


# ═══ Le calcul complet — les cinq exemples validés par l'utilisateur ═════════

CAS = [
    # (من, إلى, صنف, رتبة المكوّن, ساعات, سعر, مبلغ)
    ('10:00', '13:00', 'أ1', 'العميد',     3, 25.0,  75.0),   # مثال 1
    ('08:30', '12:00', 'ب',  'الرائد',     4, 11.0,  44.0),   # مثال 2
    ('09:00', '14:01', 'أ2', 'النقيب',     6, 18.0, 108.0),   # مثال 3
    ('08:00', '10:45', 'ج',  'الملازم',    3,  9.0,  27.0),   # مثال 4
    ('09:00', '12:31', 'أ1', 'المقدم',     4, 25.0, 100.0),   # مثال 5-أ
    ('09:00', '12:31', 'أ1', 'الرائد',     4, 20.0,  80.0),   # مثال 5-ب
]


@pytest.mark.parametrize('debut,fin,classe,grade,heures,taux,montant', CAS)
def test_les_cas_valides_par_lutilisateur(debut, fin, classe, grade,
                                          heures, taux, montant):
    r = bm.chiffrer(_prog((debut, fin)), classe, grade)
    assert r['chiffrable'], r['motifs']
    assert r['heures'] == heures
    assert r['taux'] == taux
    assert r['montant'] == montant


def test_le_calcul_dit_ce_qui_lempeche_plutot_que_de_rendre_zero():
    """Un écran qui annonce « 0.000 د » ment. Il doit nommer ce qui manque."""
    r = bm.chiffrer([], 'أ1', 'العميد')          # برنامج muet
    assert not r['chiffrable'] and r['montant'] is None
    assert any('توقيت' in m for m in r['motifs'])

    r = bm.chiffrer(_prog(('09:00', '12:00')), '', 'العميد')   # صنف absent
    assert not r['chiffrable'] and any('صنف' in m for m in r['motifs'])

    r = bm.chiffrer(_prog(('09:00', '12:00')), 'أ1', 'الرقيب')  # رتبة hors texte
    assert not r['chiffrable'] and any('رتبة' in m for m in r['motifs'])


def test_la_colonne_a3_est_prete_mais_vide_par_defaut():
    """« لا يوجد صنف أ3 ولكن دعه فارغا قابلا للتحيين » — la colonne existe,
    aucune رتبة n'y mène, et son taux officiel reste disponible."""
    assert 'أ3' in bm.COLONNES
    assert bm.taux_horaire('I', 'أ3') == 18.0


def test_le_calcul_expose_la_duree_reelle_a_cote_de_la_duree_payee():
    """L'agent doit voir d'où viennent les heures qu'il paie."""
    r = bm.chiffrer(_prog(('08:30', '12:00')), 'أ1', 'العميد')
    assert r['minutes'] == 210
    assert r['duree_texte'] == '3 ساعات و30 دقيقة'
    assert r['heures'] == 4 and r['arrondi'] is True
