# -*- coding: utf-8 -*-
"""Règles linguistiques arabes : accord du nombre (تمييز العدد), hiérarchie
militaire et rattachement des services."""
import pytest

from core import arabe


@pytest.mark.parametrize('nombre, attendu', [
    (1,  'مشارك واحد'),
    (2,  'مشاركين اثنين'),
    (3,  'ثلاثة مشاركين'),
    (10, 'عشرة مشاركين'),
    (11, 'أحد عشر مشاركا'),
    (14, 'أربعة عشر مشاركا'),
    (99, 'تسعة وتسعون مشاركا'),
])
def test_accord_du_nombre_de_participants(nombre, attendu):
    assert arabe.expression_participants(nombre) == attendu


def test_zero_participant_reste_generique():
    assert arabe.expression_participants(0) == 'المشاركين'


def test_tri_par_grade_respecte_la_hierarchie():
    participants = [
        {'grade': 'رقيب',    'nom': 'ج'},
        {'grade': 'عميد',    'nom': 'أ'},
        {'grade': 'ملازم',   'nom': 'ب'},
        {'grade': 'السيد',   'nom': 'د'},
    ]
    ordre = [p['nom'] for p in arabe.trier_par_grade(participants)]
    assert ordre == ['أ', 'ب', 'ج', 'د']


def test_phrase_des_grades_selon_les_presents():
    assert arabe.phrase_grades(['عميد', 'نقيب']) == 'ضبّاط'
    assert arabe.phrase_grades(['رقيب', 'عريف']) == 'ضبّاط صف'
    assert arabe.phrase_grades(['عميد', 'رقيب']) == 'ضبّاط وضبّاط صف'


def test_les_bureaux_sont_ramenes_a_leur_direction_regionale():
    r = arabe.rattachement_services(
        ['المكتب الحدودي للديوانة بقلعة سنان', 'المكتب الجهوي للديوانة بالكاف'],
        admin_regionale='الإدارة الجهوية للديوانة بالقصرين',
        unite_garde='وحدة الحرس الديواني')
    assert r['mot'] == 'المكاتب'
    assert r['entites'] == ['الإدارة الجهوية للديوانة بالقصرين'], \
        "les bureaux ne sont pas détaillés un par un"


def test_heure_en_toutes_lettres():
    assert arabe.heure_en_lettres('08:30') == 'الثّامنة والنّصف صباحا'
    assert arabe.heure_en_lettres('14:00') == 'الثّانية بعد الزّوال'


def test_date_longue_arabe():
    assert arabe.date_longue('2026-10-21') == '21 أكتوبر 2026'


def test_mustahdafun_derive_des_participants_reels():
    parts = [
        {'grade': 'عميد',  'lieu_travail': 'المكتب الحدودي للديوانة بقلعة سنان'},
        {'grade': 'رقيب',  'lieu_travail': 'المكتب الجهوي للديوانة بالكاف'},
    ]
    r = arabe.derive_mustahdafun(
        parts,
        admin_regionale='الإدارة الجهوية للديوانة بالقصرين',
        unite_garde='وحدة الحرس الديواني')
    assert r == 'ضبّاط وضبّاط صف من الإدارة الجهوية للديوانة بالقصرين'


def test_mustahdafun_sans_participant_reste_vide():
    assert arabe.derive_mustahdafun([]) == ''
