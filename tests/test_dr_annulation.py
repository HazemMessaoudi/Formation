# -*- coding: utf-8 -*-
"""فسخ مراسلة المدير الجهوي — العدد يعود إلى الرصيد.

Le défaut trouvé à l'usage : à l'étape 2, Hazem a tiré deux مراسلات مديرين
جهويّين (deux أعداد), puis en a retiré une avant la confirmation finale. La
مراسلة a disparu de l'écran — mais son عدد est resté inscrit au سجلّ, pour une
مراسلة qui n'existait plus. Un عدد mort dans le registre, c'est un trou dans la
série et une مراسلة fantôme.

Ce que ces tests défendent : retirer une مراسلة مدير جهوي **rend son عدد** ; le
prochain tirage le reprend ; et un عدد devenu نهائي (البرنامج entièrement
enregistré) ne se fsakhe plus."""

from datetime import datetime

import pytest


def _programme_confirme(db, mois='فيفري'):
    """Un برنامج confirmé (verrouille=1), prêt à tirer des مراسلات مديرين."""
    annee = db.annee_registre()
    lettre_id = db.save_programme(
        'interne', mois, annee,
        [{'titre': f'دورة {mois}', 'grade': 'مقدم', 'nom_formateur': 'زياد البوهلالي',
          'lieu_travail': '', 'date_formation': f'{annee}-02-10', 'periode': '',
          'lieu_formation': 'مركز التكوين الجهوي بالقصرين'}],
        'حازم مسعودي', 'النقيب')
    db.verrouiller_lettre(lettre_id, 'interne')
    return lettre_id


# ─── العدد يعود إلى الرصيد ───────────────────────────────────────────────────

def test_fsakh_maraslat_dir_rend_son_adad(db):
    lid = _programme_confirme(db)
    ref, num, typ, deja = db.attribuer_numero_dr(lid, 'externe', 'الإدارة الجهوية ببنزرت')
    assert num and not deja
    # Le عدد est bien au سجلّ externe.
    assert num in {e['numero'] for e in db.get_registre('externe', db.annee_registre())}

    dr = db.get_dr_lettres(lid)[0]
    ok, rendu = db.annuler_dr_lettre(dr['id'])
    assert ok
    # Il a quitté le سجلّ …
    assert num not in {e['numero'] for e in db.get_registre('externe', db.annee_registre())}
    # … et il attend en tête du rرصيد : le prochain tirage le reprend.
    assert db.prochain_numero_prevu('externe') == num


def test_le_scenario_exact_du_defaut(db):
    """Deux مراسلات, on en retire une : l'autre garde son عدد, le retiré revient."""
    lid = _programme_confirme(db)
    r1, n1, _, _ = db.attribuer_numero_dr(lid, 'externe', 'الإدارة الجهوية ببنزرت')
    r2, n2, _, _ = db.attribuer_numero_dr(lid, 'externe', 'الإدارة الجهوية بالمنستير')
    assert n2 == n1 + 1

    liste = db.get_dr_lettres(lid)
    a_retirer = next(d for d in liste if d['numero'] == n1)
    ok, _ = db.annuler_dr_lettre(a_retirer['id'])
    assert ok

    restantes = db.get_dr_lettres(lid)
    # La seconde مراسلة est intacte, avec SON عدد.
    assert [d['numero'] for d in restantes] == [n2]
    # Le عدد retiré n'est plus au سجلّ …
    externes = {e['numero'] for e in db.get_registre('externe', db.annee_registre())}
    assert n1 not in externes and n2 in externes
    # … et il est rendu : il resservira avant tout عدد neuf.
    assert db.prochain_numero_prevu('externe') == n1


def test_fsakh_puis_nouveau_tirage_reprend_le_meme_adad(db):
    lid = _programme_confirme(db)
    _, n1, _, _ = db.attribuer_numero_dr(lid, 'externe', 'بنزرت')
    dr = db.get_dr_lettres(lid)[0]
    db.annuler_dr_lettre(dr['id'])
    # Une nouvelle جهة reprend le عدد rendu — pas de trou.
    _, n2, _, _ = db.attribuer_numero_dr(lid, 'externe', 'صفاقس')
    assert n2 == n1


def test_les_deux_series_ne_se_melent_pas_au_fsakh(db):
    """Fsakher une externe ne touche pas la série interne."""
    lid = _programme_confirme(db)
    interne_prochain = db.prochain_numero_prevu('interne')
    _, n, _, _ = db.attribuer_numero_dr(lid, 'externe', 'بنزرت')
    dr = db.get_dr_lettres(lid)[0]
    db.annuler_dr_lettre(dr['id'])
    assert db.prochain_numero_prevu('interne') == interne_prochain


# ─── ما لا يُفسخ ─────────────────────────────────────────────────────────────

def test_un_adad_definitif_ne_se_fsakhe_plus(db):
    """Une fois le برنامج entièrement enregistré, le عدد est un acte parti."""
    lid = _programme_confirme(db)
    db.attribuer_numero_dr(lid, 'externe', 'بنزرت')
    dr = db.get_dr_lettres(lid)[0]
    # On rend définitifs les أعداد du برنامج (ce que fait le تسجيل complet).
    conn = db.get_connection()
    try:
        db.confirmer_numeros_programme(conn, lid)
        conn.commit()
    finally:
        conn.close()
    ok, msg = db.annuler_dr_lettre(dr['id'])
    assert not ok
    assert 'نهائيّة' in msg
    # La مراسلة et son عدد sont toujours là.
    assert db.get_dr_lettres(lid)


def test_fsakh_dune_maraslat_inexistante(db):
    ok, msg = db.annuler_dr_lettre(99999)
    assert not ok


# ─── الترقيم يبقى سليما ──────────────────────────────────────────────────────

def test_pas_de_trou_apres_fsakh_de_la_derniere(db):
    """Retirer la dernière مراسلة ne laisse pas de lacune dans la série."""
    lid = _programme_confirme(db)
    db.attribuer_numero_dr(lid, 'externe', 'بنزرت')
    _, n2, _, _ = db.attribuer_numero_dr(lid, 'externe', 'المنستير')
    dr2 = next(d for d in db.get_dr_lettres(lid) if d['numero'] == n2)
    db.annuler_dr_lettre(dr2['id'])
    assert db.registre_lacunes('externe', db.annee_registre()) == []
