# -*- coding: utf-8 -*-
"""المذكّرة الدّاخليّة : المدير الجهوي ورئيس وحدة الحرس مرجعا النظر (v1.4d).

Ils sont ajoutés d'office à la قائمة الموجَّه إليهم, juste APRÈS
«السيّد مدير إدارة التّعليم والدّراسات», et restent déplaçables à la main
(la liste enregistrée par l'agent est rendue telle quelle)."""


def _dorra(db):
    lid = db.save_programme('interne', 'جانفي', 2026, [{
        'titre': 'الفوترة', 'grade': 'نقيب', 'nom_formateur': 'بلال هرماسي',
        'lieu_travail': 'مكتب', 'date_formation': '2026-01-06', 'periode': 'صباحا',
        'lieu_formation': 'قاعة أ'}], 'ن', 'ر')
    fid = db.get_lettre_detail(lid)['formations'][0]['id']
    return lid, fid


def test_les_deux_مراجع_النظر_suivent_التعليم_والدراسات(db):
    db.update_config('admin_regionale', 'الإدارة الجهويّة للدّيوانة بالقصرين')
    db.update_config('unite_garde', 'الوحدة الرّابعة للحرس الدّيواني بقفصة')
    lid, fid = _dorra(db)
    noms = [m['nom'] for m in db.get_memo_data(lid, fid)['moujah']]
    i = noms.index('السيّد مدير إدارة التّعليم والدّراسات')
    assert noms[i + 1] == 'السيّد المدير الجهوي للدّيوانة بالقصرين'
    assert noms[i + 2] == 'السيّد رئيس الوحدة الرّابعة للحرس الدّيواني بقفصة'
    assert noms[-1] == 'مصلحة المحفوظات والتوثيق'


def test_la_وجهة_reglee_prime(db):
    db.update_config('destination_dr', 'السيد المدير الجهوي للديوانة بسيدي بوزيد')
    lid, fid = _dorra(db)
    noms = [m['nom'] for m in db.get_memo_data(lid, fid)['moujah']]
    assert 'السيد المدير الجهوي للديوانة بسيدي بوزيد' in noms


def test_a_defaut_la_ville_du_centre(db):
    db.update_config('ville_centre', 'بنزرت')
    lid, fid = _dorra(db)
    noms = [m['nom'] for m in db.get_memo_data(lid, fid)['moujah']]
    assert 'السيّد المدير الجهوي للدّيوانة ببنزرت' in noms


def test_rien_de_regle_rien_d_ajoute(db):
    for c in ('destination_dr', 'admin_regionale', 'unite_garde', 'ville_centre'):
        db.update_config(c, '')
    lid, fid = _dorra(db)
    assert len(db.get_memo_data(lid, fid)['moujah']) == 4


def test_l_ordre_choisi_par_l_agent_est_respecte(db):
    """Une fois la liste enregistrée, ni ajout d'office ni réordonnancement."""
    import json
    db.update_config('unite_garde', 'الوحدة الرّابعة للحرس الدّيواني بقفصة')
    lid, fid = _dorra(db)
    choisi = [{'nom': 'السيّد رئيس الوحدة الرّابعة للحرس الدّيواني بقفصة', 'type': 'للتعهد'},
              {'nom': 'مصلحة المحفوظات والتوثيق', 'type': ''}]
    db.save_memo_data(fid, {'moujah': choisi, 'objet': 'x', 'corps': 'y'})
    assert [m['nom'] for m in db.get_memo_data(lid, fid)['moujah']] == [c['nom'] for c in choisi]
