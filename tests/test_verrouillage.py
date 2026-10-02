# -*- coding: utf-8 -*-
"""Verrouillage définitif d'une dorra (« تسجيل الدورة في المنظومة ») et
détermination des programmes à reprendre."""


def _confirmer_memo(db, formation_id):
    return db.save_memo_data(formation_id,
                             {'objet': 'أ', 'corps': 'ب', 'moujah': []},
                             confirmer=True)


def test_finalisation_exige_une_memo_confirmee(db, programme):
    ok, message = db.finaliser_formation(programme['formation_id'])
    assert ok is False
    assert 'المذكّرة' in message


def test_finalisation_puis_verrou_effectif(db, programme):
    _confirmer_memo(db, programme['formation_id'])
    ok, quand = db.finaliser_formation(programme['formation_id'])
    assert ok is True and quand

    assert db.formation_est_finalisee(programme['formation_id']) is True
    # Toute modification ultérieure est refusée
    assert db.save_memo_data(programme['formation_id'],
                             {'objet': 'تعديل', 'corps': 'ممنوع', 'moujah': []}) is False


def test_double_finalisation_refusee(db, programme):
    _confirmer_memo(db, programme['formation_id'])
    db.finaliser_formation(programme['formation_id'])
    ok, message = db.finaliser_formation(programme['formation_id'])
    assert ok is False
    assert 'من قبل' in message


def test_programme_inacheve_tant_que_la_dorra_n_est_pas_finalisee(db, programme):
    ids = [p['id'] for p in db.get_programmes_inacheves()]
    assert programme['lettre_id'] in ids, "un brouillon doit être proposé à la reprise"

    # Après confirmation du programme (verrouille=1) il reste à reprendre
    db.verrouiller_lettre(programme['lettre_id'], 'interne')
    ids = [p['id'] for p in db.get_programmes_inacheves()]
    assert programme['lettre_id'] in ids, \
        "un programme confirmé mais non enregistré reste à reprendre"

    assert db.programme_est_complet(programme['lettre_id']) is False


def test_programme_disparait_une_fois_toutes_les_dorrat_enregistrees(db, programme):
    db.verrouiller_lettre(programme['lettre_id'], 'interne')
    _confirmer_memo(db, programme['formation_id'])
    db.finaliser_formation(programme['formation_id'])

    assert db.programme_est_complet(programme['lettre_id']) is True
    ids = [p['id'] for p in db.get_programmes_inacheves()]
    assert programme['lettre_id'] not in ids, \
        "un programme achevé ne doit plus figurer dans « استكمال »"


def test_mise_a_jour_refusee_sur_programme_verrouille(db, programme):
    db.verrouiller_lettre(programme['lettre_id'], 'interne')
    resultat = db.update_programme(programme['lettre_id'], 'interne', 'نوفمبر', 2026, [])
    assert resultat is False, "un programme verrouillé n'est plus modifiable"
