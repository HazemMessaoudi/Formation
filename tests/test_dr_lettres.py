# -*- coding: utf-8 -*-
"""مراسلات المديرين الجهويّين — واحدة لكلّ جهة، ولكلّ واحدة عددها.

Une دورة réunit des أعوان venus de plusieurs directions régionales : chacun
de leurs directeurs reçoit sa مراسلة, et chaque مراسلة est un document
officiel à part entière. La règle que ces tests défendent tient en une
phrase : **trois directeurs, trois أعداد, trois سطور au سجلّ** — jamais un
عدد partagé, jamais un عدد emprunté à l'autre série, jamais un عدد consommé
deux fois pour la même direction.

C'est la partie la plus sensible de la منظومة : une erreur ici ne casse pas
un écran, elle fausse des correspondances officielles déjà parties.
"""

import pytest


DESTINATIONS = (
    'الإدارة الجهويّة للدّيوانة ببنزرت',
    'الإدارة الجهويّة للدّيوانة بالمنستير',
    'الإدارة الجهويّة للدّيوانة بصفاقس',
)


@pytest.fixture()
def programme_confirme(db):
    """Un برنامج confirmé : sans confirmation, aucun عدد ne peut être tiré."""
    lettre_id = db.save_programme(
        'interne', 'فيفري', 2026,
        [{'titre': 'تحرير المحاضر', 'grade': 'مقدم',
          'nom_formateur': 'البوهلالي زياد', 'lieu_travail': '',
          'date_formation': '2026-02-10', 'periode': '',
          'lieu_formation': 'مركز التكوين الجهوي بالقصرين'}],
        'حازم مسعودي', 'النقيب')
    ref, numero = db.verrouiller_lettre(lettre_id, 'interne')
    return {'lettre_id': lettre_id, 'ref': ref, 'numero': numero}


def registre(db, **filtres):
    conn = db.get_connection()
    try:
        clause = ' AND '.join(f'{c}=?' for c in filtres) or '1=1'
        return [dict(r) for r in conn.execute(
            f'SELECT type, numero, source, source_id, statut, objet '
            f'FROM registre WHERE {clause} ORDER BY type, numero',
            tuple(filtres.values())).fetchall()]
    finally:
        conn.close()


# ─── لكلّ جهة عددها ──────────────────────────────────────────────────────────

def test_trois_directions_consomment_trois_numeros(db, programme_confirme):
    lid = programme_confirme['lettre_id']
    numeros = []
    for dest in DESTINATIONS:
        ref, numero, type_l, deja = db.attribuer_numero_dr(lid, 'externe', dest)
        assert deja is False
        assert type_l == 'externe'
        numeros.append(numero)

    assert numeros == [1, 2, 3]                 # suite, sans trou ni partage
    assert len(set(numeros)) == 3


def test_chaque_maraslat_a_sa_ligne_au_registre(db, programme_confirme):
    lid = programme_confirme['lettre_id']
    for dest in DESTINATIONS:
        db.attribuer_numero_dr(lid, 'externe', dest)

    lignes = registre(db, source='directeur')
    assert len(lignes) == 3
    assert sorted(l['numero'] for l in lignes) == [1, 2, 3]
    # Le سجلّ dit à quelle direction chaque عدد est parti.
    for dest in DESTINATIONS:
        assert any(dest in (l['objet'] or '') for l in lignes)


def test_la_liste_rend_les_maraslat_dans_lordre_des_numeros(db, programme_confirme):
    lid = programme_confirme['lettre_id']
    for dest in DESTINATIONS:
        db.attribuer_numero_dr(lid, 'externe', dest)

    liste = db.get_dr_lettres(lid)
    assert [d['destination'] for d in liste] == list(DESTINATIONS)
    assert [d['numero'] for d in liste] == [1, 2, 3]
    assert all(d['ref_complet'] for d in liste)


# ─── العدد يُسحب مرّة واحدة ────────────────────────────────────────────────────

def test_reimprimer_la_meme_direction_ne_consomme_rien(db, programme_confirme):
    """Réimprimer n'est pas réémettre : le عدد reste le même."""
    lid = programme_confirme['lettre_id']
    premier = db.attribuer_numero_dr(lid, 'externe', DESTINATIONS[0])
    assert premier[3] is False

    for _ in range(3):
        ref, numero, type_l, deja = db.attribuer_numero_dr(
            lid, 'externe', DESTINATIONS[0])
        assert deja is True
        assert (ref, numero) == (premier[0], premier[1])

    assert len(registre(db, source='directeur')) == 1


def test_le_type_dune_maraslat_deja_tiree_ne_change_plus(db, programme_confirme):
    """Un document parti sous un عدد خارجي ne devient pas داخلي après coup."""
    lid = programme_confirme['lettre_id']
    ref, numero, type_l, _ = db.attribuer_numero_dr(lid, 'externe', DESTINATIONS[0])
    r2, n2, t2, deja = db.attribuer_numero_dr(lid, 'interne', DESTINATIONS[0])
    assert deja is True
    assert (r2, n2, t2) == (ref, numero, 'externe')


# ─── السّلسلتان تبقيان مستقلّتين ───────────────────────────────────────────────

def test_les_deux_series_ne_sempruntent_jamais_un_numero(db, programme_confirme):
    """Le عدد du برنامج est داخلي ; celui de la مراسلة خارجية n'en découle pas."""
    lid = programme_confirme['lettre_id']
    assert programme_confirme['numero'] == 1            # داخلية n° 1

    _, n_externe, _, _ = db.attribuer_numero_dr(lid, 'externe', DESTINATIONS[0])
    assert n_externe == 1                               # خارجية repart à 1

    _, n_interne, _, _ = db.attribuer_numero_dr(lid, 'interne', DESTINATIONS[1])
    assert n_interne == 2                               # داخلية suit son cours

    types = {(l['type'], l['numero']) for l in registre(db)}
    assert ('interne', 1) in types and ('interne', 2) in types
    assert ('externe', 1) in types


def test_deux_programmes_partagent_la_suite_des_numeros(db, programme_confirme):
    """Le compteur appartient au مركز, pas au برنامج."""
    lid1 = programme_confirme['lettre_id']
    db.attribuer_numero_dr(lid1, 'externe', DESTINATIONS[0])

    lid2 = db.save_programme('interne', 'مارس', 2026, [], 'حازم مسعودي', 'النقيب')
    db.verrouiller_lettre(lid2, 'interne')
    _, numero, _, _ = db.attribuer_numero_dr(lid2, 'externe', DESTINATIONS[0])
    assert numero == 2          # même direction, autre برنامج : autre عدد


# ─── ما قبل التّأكيد ─────────────────────────────────────────────────────────

def test_aucun_numero_avant_la_confirmation_du_programme(db):
    lettre_id = db.save_programme('interne', 'فيفري', 2026, [],
                                  'حازم مسعودي', 'النقيب')
    assert db.attribuer_numero_dr(lettre_id, 'externe', DESTINATIONS[0]) == \
        (None, None, None, False)
    assert db.get_dr_lettres(lettre_id) == []
    assert registre(db, source='directeur') == []


def test_programme_inexistant_ne_consomme_rien(db):
    assert db.attribuer_numero_dr(9999, 'externe', DESTINATIONS[0]) == \
        (None, None, None, False)
    assert registre(db) == []


# ─── الفسخ ───────────────────────────────────────────────────────────────────

def test_le_fsakh_rend_tous_les_numeros_des_directeurs(db, programme_confirme):
    lid = programme_confirme['lettre_id']
    for dest in DESTINATIONS:
        db.attribuer_numero_dr(lid, 'externe', dest)

    assert db.delete_programme_inacheve(lid) is True

    conn = db.get_connection()
    try:
        assert conn.execute('SELECT COUNT(*) c FROM dr_lettres').fetchone()['c'] == 0
        liberes = {(r['type'], r['numero']) for r in conn.execute(
            'SELECT type, numero FROM numeros_liberes')}
    finally:
        conn.close()
    assert {('externe', 1), ('externe', 2), ('externe', 3)} <= liberes
    assert ('interne', 1) in liberes             # celui du برنامج aussi


def test_un_numero_libere_est_resservi_avant_un_neuf(db, programme_confirme):
    """Un عدد rendu par un فسخ ne laisse pas de trou dans la suite."""
    lid = programme_confirme['lettre_id']
    db.attribuer_numero_dr(lid, 'externe', DESTINATIONS[0])
    db.delete_programme_inacheve(lid)

    lid2 = db.save_programme('interne', 'مارس', 2026, [], 'حازم مسعودي', 'النقيب')
    db.verrouiller_lettre(lid2, 'interne')
    _, numero, _, _ = db.attribuer_numero_dr(lid2, 'externe', DESTINATIONS[0])
    assert numero == 1


# ─── الصّفحة ─────────────────────────────────────────────────────────────────

def test_la_page_de_detail_montre_ce_qui_est_parti(db, client, programme_confirme):
    lid = programme_confirme['lettre_id']
    for dest in DESTINATIONS[:2]:
        db.attribuer_numero_dr(lid, 'externe', dest)

    rep = client.get(f'/lettres/{lid}')
    assert rep.status_code == 200
    corps = rep.data.decode('utf-8')
    for dest in DESTINATIONS[:2]:
        assert dest in corps
    assert 'END-3-01-02' in corps
    assert 'ما رُسِّم إلى حدّ الآن' in corps


def test_la_page_propose_les_jihat_comme_destinations(db, client, programme_confirme):
    db.add_jiha('الإدارة الجهويّة للدّيوانة ببنزرت')
    rep = client.get(f'/lettres/{programme_confirme["lettre_id"]}')
    corps = rep.data.decode('utf-8')
    assert 'dl_dest_dr' in corps
    assert 'الإدارة الجهويّة للدّيوانة ببنزرت' in corps


# ─── قاعدة قديمة ─────────────────────────────────────────────────────────────

def test_une_base_ancienne_est_reprise_sans_perte(db, programme_confirme):
    """Une base d'avant `dr_lettres` porte sa مراسلة dans les colonnes dr_*.

    La reprise doit la verser dans la nouvelle table — et une seule fois,
    quel que soit le nombre de démarrages de la منظومة.
    """
    lid = programme_confirme['lettre_id']
    conn = db.get_connection()
    try:
        conn.execute('DELETE FROM dr_lettres')
        conn.execute(
            "UPDATE lettres SET dr_type='externe', dr_numero=7, "
            "dr_ref_complet='END-3-01-02-26-0007', dr_destination=? WHERE id=?",
            (DESTINATIONS[0], lid))
        conn.commit()
    finally:
        conn.close()

    db.init_db()
    db.init_db()                                  # idempotence

    liste = db.get_dr_lettres(lid)
    assert len(liste) == 1
    assert liste[0]['numero'] == 7
    assert liste[0]['destination'] == DESTINATIONS[0]
    assert len(registre(db, source='directeur')) == 1
