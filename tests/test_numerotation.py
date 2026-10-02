# -*- coding: utf-8 -*-
"""Numérotation des مراسلات et مذكرات — le cœur réglementaire de l'application.

Règle métier : chaque document enregistré porte un numéro d'ordre UNIQUE tiré du
compteur de son type. La مذكرة ne doit JAMAIS réutiliser le numéro de la
مراسلة du programme.
"""


def test_verrouillage_attribue_une_reference(db, programme):
    ref, numero = db.verrouiller_lettre(programme['lettre_id'], 'interne')
    assert ref, "une référence doit être attribuée au verrouillage"
    assert numero > 0
    assert ref.endswith(f"{numero:04d}")


def test_verrouiller_deux_fois_ne_reincremente_pas(db, programme):
    ref1, num1 = db.verrouiller_lettre(programme['lettre_id'], 'interne')
    ref2, num2 = db.verrouiller_lettre(programme['lettre_id'], 'interne')
    assert (ref1, num1) == (ref2, num2), \
        "un programme déjà verrouillé conserve sa référence"


def test_memo_recoit_un_numero_DIFFERENT_de_la_lettre(db, programme):
    """Régression : les deux documents partageaient le même numéro."""
    ref_lettre, num_lettre = db.verrouiller_lettre(programme['lettre_id'], 'interne')

    db.save_memo_data(programme['formation_id'],
                      {'objet': 'دورة تكوينيّة', 'corps': 'النصّ', 'moujah': []},
                      confirmer=True)
    memo = db.get_memo_data(programme['lettre_id'], programme['formation_id'])

    assert memo['memo_ref'], "la مذكرة doit porter sa propre référence"
    assert memo['memo_ref'] != ref_lettre
    assert memo['memo_numero'] != num_lettre


def test_memo_conserve_son_numero_apres_reconfirmation(db, programme):
    db.verrouiller_lettre(programme['lettre_id'], 'interne')
    db.save_memo_data(programme['formation_id'],
                      {'objet': 'أ', 'corps': 'ب', 'moujah': []}, confirmer=True)
    premier = db.get_memo_data(programme['lettre_id'], programme['formation_id'])['memo_ref']

    db.save_memo_data(programme['formation_id'],
                      {'objet': 'ج', 'corps': 'د', 'moujah': []}, confirmer=True)
    second = db.get_memo_data(programme['lettre_id'], programme['formation_id'])['memo_ref']

    assert premier == second, "le numéro d'enregistrement ne doit jamais changer"


def test_enregistrement_sans_confirmation_n_attribue_pas_de_numero(db, programme):
    db.save_memo_data(programme['formation_id'],
                      {'objet': 'أ', 'corps': 'ب', 'moujah': []}, confirmer=False)
    memo = db.get_memo_data(programme['lettre_id'], programme['formation_id'])
    assert not memo['memo_ref'], \
        "un simple enregistrement ne consomme pas de numéro d'ordre"


def test_les_numeros_se_suivent_sans_doublon(db):
    """Aucun numéro attribué ne doit être servi deux fois."""
    vus = set()
    for _ in range(12):
        _, numero = db.get_next_ref('interne')
        assert numero not in vus, f"numéro {numero} attribué deux fois"
        vus.add(numero)


def test_compteurs_interne_et_externe_sont_independants(db):
    _, interne = db.get_next_ref('interne')
    _, externe = db.get_next_ref('externe')
    _, interne2 = db.get_next_ref('interne')
    assert interne2 == interne + 1, "le compteur interne progresse seul"
    assert externe == 1, "le compteur externe démarre indépendamment"


# ─── Étape 2 : مراسلة المدير الجهوي ──────────────────────────────────────────
#
# Régression : la lettre de l'étape 2 réutilisait le numéro de la مراسلة du
# programme. Déclarée خارجية, elle sortait donc avec un numéro de la série
# داخلية (END-…-0008 alors que la série externe en était à 0001).

def test_dr_ne_reprend_pas_le_numero_du_programme(db, programme):
    ref_prog, num_prog = db.verrouiller_lettre(programme['lettre_id'], 'interne')
    ref_dr, num_dr, type_dr, deja = db.attribuer_numero_dr(
        programme['lettre_id'], 'externe', 'السيد المدير الجهوي للديوانة بالقصرين')

    # Le couple (type, numéro) doit différer : la référence imprimée, elle, ne
    # porte pas le type — deux séries indépendantes peuvent donc afficher le
    # même texte (c'est l'entête مراسلة داخلية/خارجية qui les distingue).
    assert ref_dr, "la مراسلة المدير الجهوي doit recevoir une référence"
    assert type_dr == 'externe'
    assert (type_dr, num_dr) != ('interne', num_prog), \
        "elle ne doit jamais emprunter le numéro de la مراسلة du programme"
    assert deja is False


def test_dr_externe_tire_son_numero_de_la_serie_externe(db, programme):
    """Le scénario exact rapporté : série interne à 7, série externe vide."""
    for _ in range(7):
        db.get_next_ref('interne')                               # الداخلية → 7
    db.verrouiller_lettre(programme['lettre_id'], 'interne')     # الداخلية → 8

    _, num_dr, type_dr, _ = db.attribuer_numero_dr(programme['lettre_id'], 'externe')
    assert type_dr == 'externe'
    assert num_dr == 1, "le numéro vient de la série externe, pas de la série interne"


def test_dr_conserve_son_numero_a_la_reimpression(db, programme):
    db.verrouiller_lettre(programme['lettre_id'], 'interne')
    premier   = db.attribuer_numero_dr(programme['lettre_id'], 'externe')
    second    = db.attribuer_numero_dr(programme['lettre_id'], 'externe')
    troisieme = db.attribuer_numero_dr(programme['lettre_id'], 'interne')  # type ignoré

    assert premier[:3] == second[:3] == troisieme[:3], \
        "réimprimer ne consomme aucun numéro et ne change pas le type"
    assert second[3] is True and troisieme[3] is True


def test_dr_refuse_un_programme_non_confirme(db, programme):
    ref, num, typ, deja = db.attribuer_numero_dr(programme['lettre_id'], 'externe')
    assert ref is None, "aucun numéro tant que le programme n'est pas confirmé"


# ─── Registre unique des numéros ─────────────────────────────────────────────

def test_registre_inscrit_toutes_les_sources(db, programme):
    db.verrouiller_lettre(programme['lettre_id'], 'interne')
    db.attribuer_numero_dr(programme['lettre_id'], 'externe')
    db.save_memo_data(programme['formation_id'],
                      {'objet': 'دورة', 'corps': 'النصّ', 'moujah': []}, confirmer=True)
    libre_id = db.save_lettre_libre('externe', 'أكتوبر', 2026, 'السيد أمين المال',
                                    'دعوة', 'النصّ', 'حازم مسعودي', 'النقيب')
    db.verrouiller_lettre(libre_id, 'externe')

    sources_int = {e['source'] for e in db.get_registre('interne')}
    sources_ext = {e['source'] for e in db.get_registre('externe')}
    assert {'programme', 'memo'} <= sources_int
    assert {'directeur', 'libre'} <= sources_ext, \
        "المراسلات الحرة et مراسلة المدير الجهوي figurent au registre externe"


def test_registre_sans_lacune_ni_doublon(db, programme):
    db.verrouiller_lettre(programme['lettre_id'], 'interne')
    db.save_memo_data(programme['formation_id'],
                      {'objet': 'أ', 'corps': 'ب', 'moujah': []}, confirmer=True)
    for _ in range(4):
        db.get_next_ref('interne')

    numeros = [e['numero'] for e in db.get_registre('interne')]
    assert len(numeros) == len(set(numeros)), "aucun numéro en double"
    assert db.registre_lacunes('interne') == [], "aucun trou dans la série"


def test_registre_interdit_le_meme_numero_deux_fois(db):
    import sqlite3
    conn = db.get_connection()
    try:
        conn.execute("INSERT INTO registre (type, numero, ref_complet, source) "
                     "VALUES ('externe', 1, 'X-0001', 'libre')")
        conn.commit()
        try:
            conn.execute("INSERT INTO registre (type, numero, ref_complet, source) "
                         "VALUES ('externe', 1, 'X-0001', 'programme')")
            conn.commit()
            assert False, "le registre doit refuser un numéro déjà attribué"
        except sqlite3.IntegrityError:
            pass
    finally:
        conn.close()


# ─── Libération des numéros au فسخ ───────────────────────────────────────────
#
# Un برنامج fsakhé rend ses numéros : la مراسلة n'est jamais partie, donc le
# numéro n'a pas été consommé. À l'inverse d'une مراسلة حرة, dont le numéro est
# définitif dès la confirmation.

def test_fsakh_libere_les_deux_numeros(db, programme):
    ref_prog, num_prog = db.verrouiller_lettre(programme['lettre_id'], 'interne')
    _, num_dr, _, _ = db.attribuer_numero_dr(programme['lettre_id'], 'externe')

    assert db.delete_programme_inacheve(programme['lettre_id']) is True
    assert num_prog in {r['numero'] for r in db.get_numeros_liberes('interne')}
    assert num_dr   in {r['numero'] for r in db.get_numeros_liberes('externe')}
    assert num_prog not in {e['numero'] for e in db.get_registre('interne')}


def test_le_numero_libere_est_resservi_avant_un_neuf(db, programme):
    _, num_prog = db.verrouiller_lettre(programme['lettre_id'], 'interne')
    db.delete_programme_inacheve(programme['lettre_id'])

    _, suivant = db.get_next_ref('interne')
    assert suivant == num_prog, "le numéro rendu repart avant d'entamer un numéro neuf"
    assert db.get_numeros_liberes('interne') == []


def test_le_numero_d_une_lettre_libre_n_est_jamais_libere(db):
    libre_id = db.save_lettre_libre('externe', 'أكتوبر', 2026, 'السيد أمين المال',
                                    'دعوة', 'النصّ', 'حازم مسعودي', 'النقيب')
    _, num = db.verrouiller_lettre(libre_id, 'externe')
    entree = [e for e in db.get_registre('externe') if e['numero'] == num][0]
    assert entree['statut'] == 'definitif'


def test_fsakh_refuse_si_une_dorra_est_enregistree(db, programme):
    db.verrouiller_lettre(programme['lettre_id'], 'interne')
    db.save_memo_data(programme['formation_id'],
                      {'objet': 'أ', 'corps': 'ب', 'moujah': []}, confirmer=True)
    ok, _ = db.finaliser_formation(programme['formation_id'])
    assert ok

    assert db.delete_programme_inacheve(programme['lettre_id']) is False, \
        "un programme dont une dorra est enregistrée ne peut plus être fsakhé"


def test_fsakh_accepte_un_programme_confirme_non_enregistre(db, programme):
    """Régression : le système refusait TOUT programme verrouillé."""
    db.verrouiller_lettre(programme['lettre_id'], 'interne')
    db.save_memo_data(programme['formation_id'],
                      {'objet': 'أ', 'corps': 'ب', 'moujah': []}, confirmer=True)
    assert db.delete_programme_inacheve(programme['lettre_id']) is True


def test_enregistrement_rend_les_numeros_definitifs(db, programme):
    db.verrouiller_lettre(programme['lettre_id'], 'interne')
    db.attribuer_numero_dr(programme['lettre_id'], 'externe')
    db.save_memo_data(programme['formation_id'],
                      {'objet': 'أ', 'corps': 'ب', 'moujah': []}, confirmer=True)
    db.finaliser_formation(programme['formation_id'])

    statuts = {e['source']: e['statut']
               for e in db.get_registre('interne') + db.get_registre('externe')}
    assert statuts.get('programme') == 'definitif'
    assert statuts.get('directeur') == 'definitif'
    assert statuts.get('memo')      == 'definitif'
