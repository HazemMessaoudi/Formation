# -*- coding: utf-8 -*-
"""Intégrité référentielle : suppressions en cascade, absence d'orphelins,
et protection des programmes déjà enregistrés."""


def _compter(db, table, **filtres):
    conn = db.get_connection()
    try:
        if filtres:
            cle, valeur = next(iter(filtres.items()))
            r = conn.execute(f'SELECT COUNT(*) c FROM {table} WHERE {cle}=?',
                             (valeur,)).fetchone()
        else:
            r = conn.execute(f'SELECT COUNT(*) c FROM {table}').fetchone()
        return r['c']
    finally:
        conn.close()


def test_les_cles_etrangeres_sont_actives(db):
    conn = db.get_connection()
    try:
        assert conn.execute('PRAGMA foreign_keys').fetchone()[0] == 1
    finally:
        conn.close()


def test_suppression_programme_ne_laisse_aucun_orphelin(db, programme):
    db.save_participants(programme['lettre_id'], programme['formation_id'],
                         [{'nom_prenom': 'الشابي وليد', 'grade': 'عميد',
                           'identifiant_unique': '12345',
                           'lieu_travail': 'المكتب الحدودي'}])
    db.save_memo_data(programme['formation_id'],
                      {'objet': 'أ', 'corps': 'ب', 'moujah': []}, confirmer=True)

    assert _compter(db, 'participants', lettre_id=programme['lettre_id']) == 1

    assert db.delete_programme_inacheve(programme['lettre_id']) is True

    assert _compter(db, 'lettres', id=programme['lettre_id']) == 0
    assert _compter(db, 'formations', lettre_id=programme['lettre_id']) == 0
    assert _compter(db, 'participants', lettre_id=programme['lettre_id']) == 0
    assert _compter(db, 'memo_formations', formation_id=programme['formation_id']) == 0

    conn = db.get_connection()
    try:
        assert list(conn.execute('PRAGMA foreign_key_check')) == []
    finally:
        conn.close()


def test_programme_enregistre_non_supprimable(db, programme):
    """Le verrou du فسخ n'est PAS la confirmation du programme (qui reste
    fsakhable) mais l'enregistrement définitif d'une dorra dans la منظومة."""
    db.verrouiller_lettre(programme['lettre_id'], 'interne')
    db.save_memo_data(programme['formation_id'],
                      {'objet': 'أ', 'corps': 'ب', 'moujah': []}, confirmer=True)
    db.finaliser_formation(programme['formation_id'])

    assert db.delete_programme_inacheve(programme['lettre_id']) is False, \
        "un programme dont une dorra est enregistrée ne doit pas pouvoir être fsakh"
    assert _compter(db, 'lettres', id=programme['lettre_id']) == 1


def test_suppression_personne_detache_ses_matieres(db):
    """mawad.mkow_id référence mkowin sans ON DELETE : la personne doit tout de
    même pouvoir être supprimée, la matière étant simplement détachée."""
    # Formulaire volontairement partiel : l'enregistrement doit l'accepter.
    assert db.add_mkow({'grade': 'مقدم', 'nom': 'البوهلالي', 'prenom': 'زياد'}) is True
    mkow_id = db.get_mkowin()[-1]['id']
    db.add_madda({'titre': 'تحرير المحاضر'})
    conn = db.get_connection()
    conn.execute('UPDATE mawad SET mkow_id=? WHERE titre=?',
                 (mkow_id, 'تحرير المحاضر'))
    conn.commit(); conn.close()

    assert db.delete_mkow(mkow_id) is True
    assert _compter(db, 'mkowin', id=mkow_id) == 0

    matieres = [m for m in db.get_mawad() if m['titre'] == 'تحرير المحاضر']
    assert matieres, "la matière de formation doit survivre"
    assert not matieres[0]['mkow_id'], "elle est simplement détachée"


def test_sauvegarde_cree_un_fichier(db):
    chemin = db.backup_db()
    import os
    assert chemin and os.path.exists(chemin)
    assert os.path.getsize(chemin) > 0
