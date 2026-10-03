# -*- coding: utf-8 -*-
"""الانتقال إلى الجدول المالي — قاعدة v1.0 قائمة لا تفقد شيئا.

Hazem a déjà installé la v1.0 : sa قاعدة porte des dorrat pointées, des
أصناف confirmés, et un جدول أصناف qu'il a peut-être corrigé lui-même. Le
جدول المالي ajoute deux tables et sept colonnes. Rien de tout cela ne doit
coûter une ligne, ni écraser une correction.

Ces tests ramènent la قاعدة à la forme d'AVANT — on démonte précisément ce
que la migration bâtit — puis relancent `init_db()` comme le ferait le
premier démarrage chez lui.
"""

import pytest

from core import bareme_mali as bm


def base_avant_le_jadwal_mali(db):
    """Défait la migration : ni tables du جدول المالي, ni colonnes de chiffrage.

    SQLite ne sait pas retirer une colonne sur toutes les versions en
    service : on reconstruit `mustahaqqat` à sa forme v1.0 exacte, contenu
    compris. C'est aussi ce qui rend le test crédible — la table de départ
    n'est pas vide.
    """
    conn = db.get_connection()
    try:
        conn.execute('DROP TABLE IF EXISTS mustahaqqat_bareme_mali')
        conn.execute('DROP TABLE IF EXISTS mustahaqqat_groupes')
        conn.execute('''
            CREATE TABLE mustahaqqat_v10 (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                formation_id INTEGER UNIQUE REFERENCES formations(id) ON DELETE CASCADE,
                lettre_id    INTEGER,
                classe       TEXT    DEFAULT '',
                classe_auto  TEXT    DEFAULT '',
                nb_presents  INTEGER DEFAULT 0,
                nb_absents   INTEGER DEFAULT 0,
                etat         TEXT    DEFAULT 'hodour',
                hodour_at    TEXT    DEFAULT NULL,
                classe_at    TEXT    DEFAULT NULL,
                acheve_at    TEXT    DEFAULT NULL
            )''')
        conn.execute('''
            INSERT INTO mustahaqqat_v10
                (id, formation_id, lettre_id, classe, classe_auto,
                 nb_presents, nb_absents, etat, hodour_at, classe_at, acheve_at)
            SELECT id, formation_id, lettre_id, classe, classe_auto,
                   nb_presents, nb_absents, etat, hodour_at, classe_at, acheve_at
              FROM mustahaqqat''')
        conn.execute('DROP TABLE mustahaqqat')
        conn.execute('ALTER TABLE mustahaqqat_v10 RENAME TO mustahaqqat')
        conn.commit()
    finally:
        conn.close()


def _dorra_pointee(db):
    """Une dorra de la v1.0 : pointée, classée, mais pas encore chiffrée."""
    annee = db.annee_registre()
    lid = db.save_programme(
        'interne', 'فيفري', annee,
        [{'titre': 'تحرير المحاضر', 'grade': 'المقدم',
          'nom_formateur': 'زياد البوهلالي', 'lieu_travail': '',
          'date_formation': f'{annee}-02-10', 'periode': 'صباحا',
          'lieu_formation': 'القصرين'}],
        'حازم مسعودي', 'النقيب')
    db.verrouiller_lettre(lid, 'interne')
    fid = db.get_lettre_detail(lid)['formations'][0]['id']
    db.save_participants(lid, fid, [
        {'nom_prenom': 'مسعودي حازم', 'grade': 'المقدم',
         'identifiant_unique': '101', 'lieu_travail': 'القصرين',
         'jiha_marjiiya': ''}])
    db.save_programme_data(fid, {'reference': 'م', 'moment': 'صباحا',
                                 'rows': [{'type': 'row', 'activity': 'حصّة',
                                           'participants': 'الكلّ',
                                           'time_debut': '08:30',
                                           'time_fin': '12:30'}]})
    db.save_memo_data(fid, {'objet': 'إعلام', 'corps': 'نصّ',
                            'moujah': [{'nom': 'الإدارة'}]}, confirmer=True)
    ok, _ = db.finaliser_formation(fid)
    assert ok
    db.save_hodour(fid, {p['id']: True for p in db.get_hodour(fid)})
    db.confirmer_classe(fid, 'أ1')
    return fid


# ═══ La migration ne coûte rien ══════════════════════════════════════════════

def test_le_pointage_et_le_sanf_survivent_a_la_migration(db):
    fid = _dorra_pointee(db)
    avant = db.get_dorra_mustahaqqat(fid)

    base_avant_le_jadwal_mali(db)
    db.init_db()                       # le premier démarrage chez Hazem

    apres = db.get_dorra_mustahaqqat(fid)
    assert apres['mu_classe'] == avant['mu_classe'] == 'أ1'
    assert apres['mu_presents'] == avant['mu_presents']
    assert apres['mu_classe_at'] == avant['mu_classe_at']
    assert apres['etat'] == 'classe'


def test_une_dorra_de_la_v10_devient_chiffrable_sans_ressaisie(db):
    """Tout ce dont le chiffrage a besoin était déjà là : le برنامج portait
    ses heures, la رتبة était dans la dorra. Rien à re-saisir."""
    fid = _dorra_pointee(db)
    base_avant_le_jadwal_mali(db)
    db.init_db()

    c = db.calculer_mustahaqqat(fid)
    assert c['chiffrable'], c['motifs']
    assert c['heures'] == 4 and c['taux'] == 25.0 and c['montant'] == 100.0


def test_les_deux_tables_du_jadwal_sont_semees(db):
    base_avant_le_jadwal_mali(db)
    db.init_db()

    assert db.get_bareme_mali()[('I', 'أ1')] == 25.0
    rattachements = {r['grade']: r['groupe'] for r in db.get_groupes_grades_detail()}
    assert rattachements['المقدم'] == 'I'
    assert rattachements['الرقيب'] == ''


def test_relancer_deux_fois_ne_change_rien(db):
    """Le démarrage se répète à chaque ouverture du برنامج."""
    fid = _dorra_pointee(db)
    base_avant_le_jadwal_mali(db)
    db.init_db()
    premier = db.calculer_mustahaqqat(fid)

    db.init_db()
    db.init_db()
    assert db.calculer_mustahaqqat(fid) == premier
    assert db.get_bareme_mali()[('I', 'أ1')] == 25.0


def test_une_correction_du_centre_nest_pas_ecrasee_au_demarrage(db):
    """Hazem corrige un taux ; rouvrir le برنامج ne doit pas le lui reprendre."""
    db.set_taux_bareme_mali('I', 'أ1', 33.0)
    db.set_groupe_grade('الرقيب', 'IV')

    db.init_db()

    assert db.get_bareme_mali()[('I', 'أ1')] == 33.0
    assert {r['grade']: r['groupe']
            for r in db.get_groupes_grades_detail()}['الرقيب'] == 'IV'


def test_le_jadwal_des_asnaf_de_la_v10_nest_pas_touche(db):
    """Les deux jadwal sont distincts : semer l'un ne réécrit pas l'autre."""
    db.set_classe_grade('الرقيب', 'ب')       # correction du centre, côté أصناف
    base_avant_le_jadwal_mali(db)
    db.init_db()

    assert db.get_bareme_grades()['الرقيب'] == 'ب'
