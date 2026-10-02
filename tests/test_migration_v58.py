# -*- coding: utf-8 -*-
"""الانتقال إلى النّسخة 58 — قاعدة قائمة لا تفقد شيئا.

Hazem a une قاعدة en service, avec des مراسلات déjà parties sur papier. La
version 58 change la forme de plusieurs tables : السّنة entre dans les
أعداد, les مراسلات المديرين الجهويّين quittent les colonnes `dr_*` pour
leur propre table, et l'هويّة se gèle. Aucun de ces changements ne doit
coûter une ligne.

Ces tests construisent une قاعدة **à l'ancienne forme** — on démonte
volontairement ce que la v58 a bâti — puis relancent `init_db()` comme le
ferait le premier démarrage chez lui, et vérifient ce qui compte :

* aucun عدد ne disparaît et aucun ne se dédouble ;
* les مراسلات المديرين الجهويّين se retrouvent, avec leur عدد ;
* la série reprend **après** le dernier عدد servi, jamais dessus ;
* relancer deux fois ne change rien de plus.
"""

from datetime import datetime

import pytest


def base_ancienne(db):
    """Ramène la قاعدة à la forme d'avant la v58.

    On défait précisément ce que les migrations bâtissent : les colonnes
    `annee`, la table `dr_lettres`, le gel. Ce que voit ensuite `init_db()`
    est ce que verra la قاعدة de Hazem au premier démarrage.
    """
    conn = db.get_connection()
    try:
        # 1. Le سجلّ d'avant : pas de سنة, unicité sur (نوع, عدد).
        conn.execute('''
            CREATE TABLE registre_ancien (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                type TEXT NOT NULL, numero INTEGER NOT NULL,
                ref_complet TEXT NOT NULL, source TEXT NOT NULL DEFAULT '',
                source_id INTEGER, objet TEXT DEFAULT '',
                date_attribution TEXT DEFAULT CURRENT_TIMESTAMP,
                statut TEXT DEFAULT 'definitif')
        ''')
        conn.execute(
            'INSERT INTO registre_ancien (id, type, numero, ref_complet, source, '
            'source_id, objet, date_attribution, statut) '
            'SELECT id, type, numero, ref_complet, source, source_id, objet, '
            '       date_attribution, statut FROM registre')
        conn.execute('DROP TABLE registre')
        conn.execute('ALTER TABLE registre_ancien RENAME TO registre')
        conn.execute('CREATE UNIQUE INDEX idx_registre_type_numero '
                     'ON registre(type, numero)')

        # 2. Les compteurs et le pool d'avant : une seule série, sans سنة.
        for table, colonnes, pk in (
                ('compteurs', 'type TEXT PRIMARY KEY, valeur INTEGER DEFAULT 0',
                 'type, valeur'),
                ('numeros_liberes',
                 'type TEXT NOT NULL, numero INTEGER NOT NULL, '
                 'libere_at TEXT, origine TEXT DEFAULT \'\', '
                 'PRIMARY KEY (type, numero)',
                 'type, numero, libere_at, origine')):
            conn.execute(f'CREATE TABLE {table}_ancien ({colonnes})')
            conn.execute(f'INSERT INTO {table}_ancien ({pk}) '
                         f'SELECT {pk} FROM {table}')
            conn.execute(f'DROP TABLE {table}')
            conn.execute(f'ALTER TABLE {table}_ancien RENAME TO {table}')

        # 3. La مراسلة du directeur vivait dans les colonnes de la مراسلة.
        for d in conn.execute('SELECT * FROM dr_lettres ORDER BY numero').fetchall():
            conn.execute(
                'UPDATE lettres SET dr_type=?, dr_numero=?, dr_ref_complet=?, '
                'dr_destination=?, dr_confirmed_at=? '
                'WHERE id=? AND COALESCE(dr_numero,0)=0',
                (d['type'], d['numero'], d['ref_complet'], d['destination'],
                 d['confirmed_at'], d['lettre_id']))
        conn.execute('DROP TABLE dr_lettres')

        # 4. Ni gel, ni سنة sur la مذكّرة.
        conn.execute('DROP TABLE IF EXISTS documents_geles')
        conn.execute("DELETE FROM config WHERE cle='annee_exercice'")

        conn.execute('DROP INDEX IF EXISTS idx_lettres_annee_type_numero')
        conn.execute('CREATE UNIQUE INDEX IF NOT EXISTS idx_lettres_type_numero '
                     'ON lettres(type, numero) WHERE numero > 0')
        conn.commit()
    finally:
        conn.close()


@pytest.fixture()
def base_en_service(db):
    """Une قاعدة telle qu'elle est chez lui : des مراسلات déjà parties."""
    annee = datetime.now().year
    faits = {'annee': annee, 'programmes': [], 'dr': []}

    for mois, jour in (('جانفي', '01-12'), ('فيفري', '02-10')):
        lettre_id = db.save_programme(
            'interne', mois, annee,
            [{'titre': f'دورة {mois}', 'grade': 'مقدم',
              'nom_formateur': 'زياد البوهلالي', 'lieu_travail': '',
              'date_formation': f'{annee}-{jour}', 'periode': '',
              'lieu_formation': 'مركز التكوين الجهوي بالقصرين'}],
            'حازم مسعودي', 'النقيب')
        ref, numero = db.verrouiller_lettre(lettre_id, 'interne')
        faits['programmes'].append({'id': lettre_id, 'ref': ref, 'numero': numero})

    # Une مراسلة حرة خارجية et deux مراسلات مديرين جهويّين.
    libre_id = db.save_lettre_libre('externe', 'فيفري', annee,
                                    'السيّد المدير العامّ', 'موضوع', 'نصّ',
                                    'حازم مسعودي', 'النقيب')
    faits['libre'] = db.verrouiller_lettre(libre_id, 'externe')

    for dest in ('الإدارة الجهويّة للدّيوانة ببنزرت',
                 'الإدارة الجهويّة للدّيوانة بالمنستير'):
        ref, numero, type_l, _ = db.attribuer_numero_dr(
            faits['programmes'][0]['id'], 'externe', dest)
        faits['dr'].append({'destination': dest, 'ref': ref, 'numero': numero})

    faits['registre_avant'] = {
        (r['type'], r['numero'], r['ref_complet'])
        for r in db.get_registre(None, annee)}
    base_ancienne(db)
    return faits


# ─── لا يضيع عدد ─────────────────────────────────────────────────────────────

def test_aucun_adad_ne_disparait(db, base_en_service):
    db.init_db()
    apres = {(r['type'], r['numero'], r['ref_complet'])
             for r in db.get_registre(None, base_en_service['annee'])}
    assert base_en_service['registre_avant'] <= apres


def test_aucun_adad_ne_se_dedouble(db, base_en_service):
    """Le risque propre à cette migration : une ligne reprise deux fois."""
    db.init_db()
    db.init_db()
    entrees = db.get_registre(None, base_en_service['annee'])
    cles = [(e['type'], e['numero']) for e in entrees]
    assert len(cles) == len(set(cles))


def test_les_maraslat_des_directeurs_se_retrouvent(db, base_en_service):
    db.init_db()
    liste = db.get_dr_lettres(base_en_service['programmes'][0]['id'])
    # L'ancienne forme ne portait qu'UNE مراسلة par برنامج : c'est elle qu'on
    # doit retrouver, avec son عدد intact.
    assert liste
    premiere = base_en_service['dr'][0]
    assert any(d['numero'] == premiere['numero']
               and d['destination'] == premiere['destination'] for d in liste)


def test_les_lignes_reprises_portent_toutes_une_annee(db, base_en_service):
    """Une ligne sans سنة échapperait à l'unicité : il n'en reste aucune."""
    db.init_db()
    conn = db.get_connection()
    try:
        for table in ('registre', 'dr_lettres'):
            manquantes = conn.execute(
                f'SELECT COUNT(*) c FROM {table} WHERE annee IS NULL').fetchone()['c']
            assert manquantes == 0, f'{table} porte des lignes sans سنة'
    finally:
        conn.close()


# ─── السّلسلة تُستأنف ولا تُعاد ────────────────────────────────────────────────

def test_la_serie_reprend_apres_le_dernier_adad(db, base_en_service):
    """Un عدد parti sur papier ne resservira pas : c'est la règle cardinale."""
    db.init_db()
    plus_haut = max(p['numero'] for p in base_en_service['programmes'])
    assert db.prochain_numero_prevu('interne') > plus_haut
    assert db.plancher_numero('interne') > plus_haut


def test_une_nouvelle_maraslat_ne_reprend_pas_un_adad_servi(db, base_en_service):
    db.init_db()
    annee = base_en_service['annee']
    deja = {e['numero'] for e in db.get_registre('interne', annee)}
    lettre_id = db.save_programme(
        'interne', 'مارس', annee,
        [{'titre': 'دورة مارس', 'grade': 'مقدم', 'nom_formateur': 'زياد البوهلالي',
          'lieu_travail': '', 'date_formation': f'{annee}-03-10', 'periode': '',
          'lieu_formation': 'القصرين'}], 'حازم مسعودي', 'النقيب')
    _, numero = db.verrouiller_lettre(lettre_id, 'interne')
    assert numero not in deja


def test_les_deux_series_restent_separees_apres_migration(db, base_en_service):
    db.init_db()
    annee = base_en_service['annee']
    internes = {e['numero'] for e in db.get_registre('interne', annee)}
    externes = {e['numero'] for e in db.get_registre('externe', annee)}
    assert internes and externes
    # Les deux séries numérotent chacune pour soi : se recouvrir est normal,
    # se mélanger ne l'est pas.
    for e in db.get_registre('interne', annee):
        assert e['type'] == 'interne'
    for e in db.get_registre('externe', annee):
        assert e['type'] == 'externe'


# ─── ما يبقى بعد الانتقال ────────────────────────────────────────────────────

def test_la_reference_survit_a_la_migration(db, base_en_service):
    db.add_mkow({'identifiant_unique': '77001', 'nom': 'زياد',
                 'prenom': 'البوهلالي', 'grade': 'عريف'})
    avant = len(db.get_mkowin()), len(db.noms_jihat())
    db.init_db()
    assert (len(db.get_mkowin()), len(db.noms_jihat())) == avant


def test_les_maraslat_gardent_leur_marjaa(db, base_en_service):
    db.init_db()
    for p in base_en_service['programmes']:
        detail = db.get_lettre_detail(p['id'])
        assert detail['lettre']['ref_complet'] == p['ref']
        assert detail['lettre']['numero'] == p['numero']


def test_la_page_du_registre_souvre_apres_migration(db, base_en_service, client):
    db.init_db()
    for url in ('/registre/interne', '/registre/externe'):
        rep = client.get(url)
        assert rep.status_code == 200
    rep = client.get(f'/lettres/{base_en_service["programmes"][0]["id"]}')
    assert rep.status_code == 200
