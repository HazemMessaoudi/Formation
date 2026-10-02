# -*- coding: utf-8 -*-
"""Registre unique des numéros d'enregistrement (attribution, libération,
lacunes) et numéro de départ des séries.

Extrait de core/database.py (v1.4) — importer depuis core.database, qui
ré-exporte tout : les appelants existants restent inchangés."""

import sqlite3
from core import exercice as _exercice

from core.db._base import get_connection


def _prochain_numero(conn, type_lettre, annee=None):
    """Prochain numéro à servir dans la série demandée.

    Priorité au **rivet des numéros libérés** : un programme fsakhé rend ses
    numéros au pool (`numeros_liberes`) et le plus petit d'entre eux est resservi
    avant d'entamer un numéro neuf. La série reste ainsi sans trou. À défaut, le
    compteur avance d'un cran.

    ⚠ Seuls les numéros explicitement libérés par un فسخ reviennent au pool. Les
    trous hérités d'anciennes bases ne sont JAMAIS re-servis : un numéro qui a pu
    partir sur papier ne doit pas resservir.

    Tout se joue dans la سنة demandée — celle du سجلّ ouvert par défaut. Un
    عدد libéré en 2026 ne peut pas resservir en 2027 : ce sont deux registres."""
    if annee is None:
        annee = _exercice.annee_active(conn)
    conn.execute('INSERT OR IGNORE INTO compteurs (annee, type, valeur) VALUES (?,?,0)',
                 (annee, type_lettre))
    row = conn.execute(
        'SELECT numero FROM numeros_liberes WHERE annee=? AND type=? '
        'ORDER BY numero ASC LIMIT 1', (annee, type_lettre)).fetchone()
    if row:
        conn.execute('DELETE FROM numeros_liberes WHERE annee=? AND type=? AND numero=?',
                     (annee, type_lettre, row[0]))
        return row[0]
    numero = None
    try:
        cur = conn.execute(
            'UPDATE compteurs SET valeur = valeur + 1 '
            'WHERE annee = ? AND type = ? RETURNING valeur',
            (annee, type_lettre))
        r = cur.fetchone()
        if r:
            numero = r[0]
    except sqlite3.OperationalError:
        numero = None
    if numero is None:
        conn.execute('BEGIN IMMEDIATE') if not conn.in_transaction else None
        conn.execute('UPDATE compteurs SET valeur = valeur + 1 '
                     'WHERE annee = ? AND type = ?', (annee, type_lettre))
        numero = conn.execute('SELECT valeur FROM compteurs WHERE annee = ? AND type = ?',
                              (annee, type_lettre)).fetchone()[0]
    return numero


def _attribuer_numero(conn, type_lettre, source='', source_id=None, objet='',
                      statut='definitif'):
    """Incrémente ATOMIQUEMENT le compteur du type demandé et renvoie
    (ref_complet, numero). La lecture se fait via RETURNING lorsque SQLite le
    supporte (≥ 3.35), sinon dans une transaction IMMEDIATE — dans les deux cas
    deux appels simultanés ne peuvent pas obtenir le même numéro.

    Chaque numéro attribué est AUSSITÔT inscrit au `registre` (un enregistrement
    par numéro consommé, quelle qu'en soit la source : برنامج تكوين, مراسلة حرة,
    مراسلة المدير الجهوي, مذكّرة). C'est le registre — et non les compteurs — qui
    fait foi : sa contrainte UNIQUE(type, numero) rend structurellement
    impossible qu'un même numéro serve deux fois dans la même série, et qu'une
    série emprunte un numéro à l'autre.

    `statut` vaut 'provisoire' tant que le document peut encore disparaître par
    un فسخ (programme, مراسلة المدير الجهوي, مذكّرة non enregistrée), et
    'definitif' dès que plus rien ne peut l'annuler. Seuls les numéros
    'provisoire' sont libérables.

    `conn` est réutilisée par l'appelant : le commit reste de sa responsabilité.
    """
    from datetime import datetime as _dt
    if type_lettre not in ('interne', 'externe'):
        raise ValueError(f"type de مراسلة inconnu : {type_lettre!r}")
    annee = _exercice.annee_active(conn)
    numero = _prochain_numero(conn, type_lettre, annee)
    cfg = {r['cle']: r['valeur']
           for r in conn.execute('SELECT cle, valeur FROM config').fetchall()}
    prefix = cfg.get('ref_prefix', 'END-3-01-02')
    # Les deux chiffres du مرجع sont ceux de la سنة du سجلّ, non ceux de
    # l'horloge : une مراسلة inscrite au سجلّ de 2026 porte «-26-», même
    # signée le 2 janvier suivant.
    annee_short = str(annee)[-2:]
    ref = f"{prefix}-{annee_short}-{numero:04d}"
    # Inscription au registre unique (même transaction que l'incrément).
    conn.execute(
        'INSERT INTO registre (annee, type, numero, ref_complet, source, source_id, '
        '                      objet, date_attribution, statut) '
        'VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)',
        (annee, type_lettre, numero, ref, source or '', source_id, objet or '',
         _dt.now().strftime('%Y-%m-%d %H:%M:%S'), statut))
    return ref, numero


# ─── Registre unique des numéros d'enregistrement ────────────────────────────

#  Libellés arabes des sources possibles d'un numéro.
REGISTRE_SOURCES = {
    'programme': 'برنامج تكوين',
    'libre':     'مراسلة حرة',
    'directeur': 'مراسلة المدير الجهوي',
    'memo':      'مذكّرة داخلية',
}


def _liberer_numero(conn, type_lettre, numero, origine='', annee=None):
    """Rend un numéro au pool : la ligne quitte le registre et devient
    disponible pour la prochaine attribution de la même série.

    `annee` : le سجلّ d'où le عدد repart. Par défaut l'année ouverte — mais on
    la précise pour libérer un عدد d'un سجلّ antérieur (un برنامج ouvert en
    décembre et fsakhé en janvier libère dans le سجلّ de décembre, non dans le
    neuf)."""
    from datetime import datetime as _dt
    if not numero:
        return
    if annee is None:
        annee = _exercice.annee_active(conn)
    conn.execute('DELETE FROM registre WHERE annee=? AND type=? AND numero=?',
                 (annee, type_lettre, numero))
    conn.execute(
        'INSERT OR IGNORE INTO numeros_liberes (annee, type, numero, libere_at, origine) '
        'VALUES (?, ?, ?, ?, ?)',
        (annee, type_lettre, numero, _dt.now().strftime('%Y-%m-%d %H:%M:%S'),
         origine or ''))


def liberer_numeros_programme(conn, lettre_id):
    """فسخ برنامج تكوين : tous les numéros que ce programme avait consommés et
    qui sont encore 'provisoire' reviennent au pool — le numéro de sa مراسلة, le
    numéro de sa مراسلة المدير الجهوي et les numéros des مذكّرات non enregistrées.

    À l'inverse des مراسلات حرة, dont le numéro est définitif dès la
    confirmation et n'est jamais rendu.

    Renvoie la liste des (type, numero) libérés."""
    liberes = []
    fids = [r['id'] for r in conn.execute(
        'SELECT id FROM formations WHERE lettre_id=?', (lettre_id,)).fetchall()]
    cibles = [('programme', lettre_id), ('directeur', lettre_id)]
    cibles += [('memo', fid) for fid in fids]
    for source, sid in cibles:
        for r in conn.execute(
                "SELECT annee, type, numero FROM registre "
                "WHERE source=? AND source_id=? AND statut='provisoire'",
                (source, sid)).fetchall():
            # Le عدد repart dans le سجلّ où il a été pris — jamais dans l'année
            # ouverte : sinon on effacerait la ligne d'une AUTRE مراسلة portant
            # le même numéro dans le سجلّ neuf, et ce numéro servirait deux fois.
            _liberer_numero(conn, r['type'], r['numero'], f'فسخ برنامج #{lettre_id}',
                            annee=r['annee'])
            liberes.append((r['type'], r['numero']))
    return liberes


def confirmer_numeros_programme(conn, lettre_id):
    """Le programme est achevé : ses numéros deviennent définitifs et ne peuvent
    plus être libérés par un فسخ."""
    fids = [r['id'] for r in conn.execute(
        'SELECT id FROM formations WHERE lettre_id=?', (lettre_id,)).fetchall()]
    conn.execute("UPDATE registre SET statut='definitif' "
                 "WHERE source IN ('programme','directeur') AND source_id=?", (lettre_id,))
    for fid in fids:
        conn.execute("UPDATE registre SET statut='definitif' "
                     "WHERE source='memo' AND source_id=?", (fid,))


def _creer_registre(conn):
    """Crée le registre s'il n'existe pas, puis le remplit à partir des numéros
    DÉJÀ attribués (bases antérieures à cette version), et resynchronise enfin
    les compteurs sur le plus grand numéro réellement inscrit — de sorte qu'un
    numéro déjà utilisé ne puisse jamais être ré-attribué."""
    conn.execute('''
        CREATE TABLE IF NOT EXISTS registre (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            type TEXT NOT NULL,
            numero INTEGER NOT NULL,
            ref_complet TEXT NOT NULL,
            source TEXT NOT NULL DEFAULT '',
            source_id INTEGER,
            objet TEXT DEFAULT '',
            date_attribution TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    # (L'ancien index unique (type, numero), SANS l'année, n'est plus créé :
    # il était recréé à chaque démarrage et aurait interdit au عدد 1 de
    # l'année neuve de coexister avec celui de l'année écoulée. L'unicité
    # porte sur (annee, type, numero) — voir plus bas.)
    # Statut : 'provisoire' (libérable par un فسخ) ou 'definitif'.
    _reg_cols = {c['name'] for c in conn.execute('PRAGMA table_info(registre)')}
    if 'statut' not in _reg_cols:
        conn.execute("ALTER TABLE registre ADD COLUMN statut TEXT DEFAULT 'definitif'")
    # Pool des numéros rendus par un فسخ, resservis avant tout numéro neuf.
    conn.execute('''
        CREATE TABLE IF NOT EXISTS numeros_liberes (
            type TEXT NOT NULL,
            numero INTEGER NOT NULL,
            libere_at TEXT DEFAULT CURRENT_TIMESTAMP,
            origine TEXT DEFAULT '',
            PRIMARY KEY (type, numero)
        )
    ''')

    # ── السّنة المحاسبيّة ────────────────────────────────────────────────────
    #
    # Un سجلّ est annuel : au 1er janvier on en ouvre un neuf et la série
    # repart. Le عدد 1 de 2027 n'est pas le successeur du dernier عدد de
    # 2026 — ce sont deux registres. Sans la سنة, les deux séries se
    # mêleraient et un عدد de 2026 barrerait la route à son homonyme de 2027.
    #
    # La reprise stampe l'existant sur la سنة ouverte : une base antérieure
    # à cette version tenait un seul registre, qui devient celui de son année.
    _annee_courante = _exercice.annee_active(conn)
    if 'annee' not in {c['name'] for c in conn.execute('PRAGMA table_info(registre)')}:
        # La سنة est NOT NULL avec un défaut : une ligne sans année
        # échapperait à l'unicité (NULL n'étant égal à rien en SQL) et deux
        # مراسلات pourraient porter le même عدد. Ce n'est pas une garantie
        # qu'on laisse à la vigilance du code appelant — d'où la refonte de
        # la table plutôt qu'un simple ALTER.
        conn.execute('''
            CREATE TABLE registre_v2 (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                annee INTEGER NOT NULL
                      DEFAULT (CAST(strftime('%Y','now') AS INTEGER)),
                type TEXT NOT NULL,
                numero INTEGER NOT NULL,
                ref_complet TEXT NOT NULL,
                source TEXT NOT NULL DEFAULT '',
                source_id INTEGER,
                objet TEXT DEFAULT '',
                date_attribution TEXT DEFAULT CURRENT_TIMESTAMP,
                statut TEXT DEFAULT 'definitif'
            )
        ''')
        conn.execute(
            'INSERT INTO registre_v2 (id, annee, type, numero, ref_complet, source, '
            '                         source_id, objet, date_attribution, statut) '
            'SELECT id, ?, type, numero, ref_complet, source, source_id, objet, '
            '       date_attribution, COALESCE(statut, \'definitif\') FROM registre',
            (_annee_courante,))
        # L'unicité porte désormais sur (سنة, نوع, عدد) : l'ancien index
        # interdirait au عدد 1 de 2027 de coexister avec celui de 2026.
        conn.execute('DROP INDEX IF EXISTS idx_registre_type_numero')
        conn.execute('DROP TABLE registre')
        conn.execute('ALTER TABLE registre_v2 RENAME TO registre')
    conn.execute('''CREATE UNIQUE INDEX IF NOT EXISTS idx_registre_annee_type_numero
                    ON registre(annee, type, numero)''')
    # Les bases démarrées au moins deux fois avant la v1.4e portent encore
    # l'index sans année : on le retire.
    conn.execute('DROP INDEX IF EXISTS idx_registre_type_numero')

    if 'annee' not in {c['name'] for c in conn.execute('PRAGMA table_info(numeros_liberes)')}:
        # La clé primaire change : SQLite impose de refaire la table.
        conn.execute('''
            CREATE TABLE numeros_liberes_v2 (
                annee INTEGER NOT NULL,
                type TEXT NOT NULL,
                numero INTEGER NOT NULL,
                libere_at TEXT DEFAULT CURRENT_TIMESTAMP,
                origine TEXT DEFAULT '',
                PRIMARY KEY (annee, type, numero)
            )
        ''')
        conn.execute(
            'INSERT OR IGNORE INTO numeros_liberes_v2 '
            '(annee, type, numero, libere_at, origine) '
            'SELECT ?, type, numero, libere_at, origine FROM numeros_liberes',
            (_annee_courante,))
        conn.execute('DROP TABLE numeros_liberes')
        conn.execute('ALTER TABLE numeros_liberes_v2 RENAME TO numeros_liberes')

    if 'annee' not in {c['name'] for c in conn.execute('PRAGMA table_info(compteurs)')}:
        conn.execute('''
            CREATE TABLE compteurs_v2 (
                annee INTEGER NOT NULL,
                type TEXT NOT NULL,
                valeur INTEGER DEFAULT 0,
                PRIMARY KEY (annee, type)
            )
        ''')
        conn.execute(
            'INSERT OR IGNORE INTO compteurs_v2 (annee, type, valeur) '
            'SELECT ?, type, valeur FROM compteurs', (_annee_courante,))
        conn.execute('DROP TABLE compteurs')
        conn.execute('ALTER TABLE compteurs_v2 RENAME TO compteurs')
    for _serie in ('interne', 'externe'):
        conn.execute('INSERT OR IGNORE INTO compteurs (annee, type, valeur) '
                     'VALUES (?,?,0)', (_annee_courante, _serie))
    _exercice.definir_annee(conn, _annee_courante)

    # ── Reprise de l'existant (idempotente : INSERT OR IGNORE sur l'index) ──
    # 1. مراسلات (برامج + حرة) : le type et le numéro sont portés par la ligne.
    conn.execute('''
        INSERT OR IGNORE INTO registre (annee, type, numero, ref_complet, source,
                                        source_id, objet, date_attribution)
        SELECT COALESCE(l.annee_sejel, l.annee, ?), l.type, l.numero, l.ref_complet,
               CASE WHEN COALESCE(l.categorie,'programme')='libre'
                    THEN 'libre' ELSE 'programme' END,
               l.id,
               CASE WHEN COALESCE(l.categorie,'programme')='libre'
                    THEN COALESCE(l.objet,'')
                    ELSE 'برنامج التكوين لشهر ' || COALESCE(l.mois,'') || ' '
                         || COALESCE(l.annee,'') END,
               COALESCE(l.date_creation, '')
        FROM lettres l
        WHERE l.numero > 0
          -- v1.7 : un برنامج de l'année N+1 numéroté dans le سجلّ de l'année N
          -- (برنامج جانفي أُرسل في ديسمبر) est déjà inscrit sous l'année N.
          -- Sans cette garde, la reprise l'inscrirait une 2e fois sous N+1 et
          -- occuperait un عدد fantôme dans le سجلّ neuf.
          AND NOT EXISTS (SELECT 1 FROM registre r
                          WHERE r.source IN ('programme','libre')
                            AND r.source_id = l.id
                            AND r.type = l.type AND r.numero = l.numero)
    ''', (_annee_courante,))
    # 2. مراسلات المديرين الجهويّين : une ligne de سجلّ par direction adressée.
    #    Chaque مراسلة a consommé son propre عدد ; le سجلّ doit les porter tous,
    #    sans quoi un عدد servi resterait invisible et pourrait être re-servi.
    _tables = {r['name'] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'")}
    if 'dr_lettres' in _tables:
        conn.execute('''
            INSERT OR IGNORE INTO registre (annee, type, numero, ref_complet, source,
                                            source_id, objet, date_attribution)
            SELECT COALESCE(d.annee, ?), d.type, d.numero, d.ref_complet,
                   'directeur', d.lettre_id,
                   'مراسلة المدير الجهوي — ' || COALESCE(l.mois,'') || ' '
                   || COALESCE(l.annee,''),
                   COALESCE(d.confirmed_at, '')
            FROM dr_lettres d JOIN lettres l ON l.id = d.lettre_id
            WHERE d.numero > 0 AND d.type IN ('interne','externe')
        ''', (_annee_courante,))
    # Reprise des bases antérieures à `dr_lettres`, où la مراسلة unique vivait
    # dans les colonnes `lettres.dr_*`.
    _lt_cols = {c['name'] for c in conn.execute('PRAGMA table_info(lettres)')}
    if 'dr_numero' in _lt_cols:
        # V2 (correctif) : cette reprise n'écrivait pas la سنة ; la colonne
        # prenait alors l'année de l'HORLOGE (défaut de la table). Après chaque
        # changement d'année, la 1re مراسلة مدير جهوي de chaque برنامج des
        # années passées était réinscrite dans le سجلّ de l'année nouvelle
        # (عدد fantôme), et la resynchronisation faisait repartir la série
        # neuve au-delà de ces fantômes (1–20 sautés). On écrit désormais la
        # سنة du سجلّ d'origine, et on ne reprend jamais une مراسلة déjà inscrite.
        _dr_an = 'l.dr_annee_sejel' if 'dr_annee_sejel' in _lt_cols else 'NULL'
        conn.execute(f'''
            INSERT OR IGNORE INTO registre (annee, type, numero, ref_complet, source, source_id,
                                            objet, date_attribution)
            SELECT COALESCE({_dr_an}, l.annee_sejel, l.annee, ?), l.dr_type, l.dr_numero,
                   l.dr_ref_complet, 'directeur', l.id,
                   'مراسلة المدير الجهوي — ' || COALESCE(l.mois,'') || ' '
                   || COALESCE(l.annee,''),
                   COALESCE(l.dr_confirmed_at, '')
            FROM lettres l
            WHERE l.dr_numero > 0 AND l.dr_type IN ('interne','externe')
              AND NOT EXISTS (SELECT 1 FROM registre r
                              WHERE r.source = 'directeur' AND r.source_id = l.id
                                AND r.type = l.dr_type AND r.numero = l.dr_numero
                                AND r.ref_complet = l.dr_ref_complet)
        ''', (_annee_courante,))
    # 3. مذكّرات : toujours des مراسلات داخلية.
    _memo_cols = {c['name'] for c in conn.execute('PRAGMA table_info(memo_formations)')}
    if 'numero' in _memo_cols:
        conn.execute('''
            INSERT OR IGNORE INTO registre (annee, type, numero, ref_complet, source,
                                            source_id, objet, date_attribution)
            SELECT COALESCE(m.annee, l.annee, ?), 'interne', m.numero, m.ref_complet, 'memo',
                   m.formation_id, COALESCE(m.objet,''), COALESCE(m.confirmed_at, '')
            FROM memo_formations m
            LEFT JOIN formations f ON f.id = m.formation_id
            LEFT JOIN lettres    l ON l.id = f.lettre_id
            WHERE m.numero > 0
              AND NOT EXISTS (SELECT 1 FROM registre r
                              WHERE r.source = 'memo' AND r.source_id = m.formation_id
                                AND r.type = 'interne' AND r.numero = m.numero)
        ''', (_annee_courante,))

    # Toute ligne reprise sans سنة rejoint le سجلّ ouvert : une ligne sans
    # année échapperait à l'unicité (annee, type, numero), NULL n'étant égal
    # à rien en SQL — deux مراسلات pourraient alors porter le même عدد.
    conn.execute('UPDATE registre SET annee=? WHERE annee IS NULL', (_annee_courante,))
    conn.execute('UPDATE dr_lettres SET annee=? WHERE annee IS NULL', (_annee_courante,))

    # 4. Statut des lignes reprises : 'provisoire' tant qu'un فسخ reste possible.
    conn.execute('''
        UPDATE registre SET statut='provisoire'
        WHERE source IN ('programme','directeur') AND source_id IN (
            SELECT l.id FROM lettres l
            WHERE COALESCE(l.categorie,'programme') <> 'libre'
              AND (NOT EXISTS (SELECT 1 FROM formations f WHERE f.lettre_id = l.id)
                   OR EXISTS (SELECT 1 FROM formations f
                              LEFT JOIN memo_formations m ON m.formation_id = f.id
                              WHERE f.lettre_id = l.id
                                AND (m.finalise_at IS NULL OR m.finalise_at = '')))
        )
    ''')
    conn.execute('''
        UPDATE registre SET statut='provisoire'
        WHERE source='memo' AND source_id IN (
            SELECT m.formation_id FROM memo_formations m
            WHERE m.finalise_at IS NULL OR m.finalise_at = ''
        )
    ''')

    # ── Resynchronisation des compteurs — SÉRIE PAR SÉRIE, ANNÉE PAR ANNÉE ──
    # v1.4e : le maximum était pris sur TOUTES les années et appliqué à tous
    # les compteurs ; au 2e démarrage de janvier, la série neuve repartait du
    # dernier عدد de l'année écoulée (1, puis 6, laissant 1–5 en « lacune »).
    for _an, _t, _max in conn.execute(
            'SELECT annee, type, COALESCE(MAX(numero), 0) FROM registre '
            'GROUP BY annee, type').fetchall():
        conn.execute('INSERT OR IGNORE INTO compteurs (annee, type, valeur) VALUES (?,?,0)',
                     (_an, _t))
        conn.execute('UPDATE compteurs SET valeur=? WHERE annee=? AND type=? AND valeur < ?',
                     (_max, _an, _t, _max))


def annee_registre():
    """L'année dont le سجلّ est ouvert — celle où s'inscrivent les nouveaux أعداد."""
    conn = get_connection()
    try:
        return _exercice.annee_active(conn)
    finally:
        conn.close()


def annees_du_registre():
    """Toutes les سنوات qui ont un سجلّ, la plus récente d'abord."""
    conn = get_connection()
    try:
        return _exercice.annees_connues(conn)
    finally:
        conn.close()


def get_registre(type_lettre=None, annee=None):
    """Registre des numéros attribués, trié par numéro croissant.

    `type_lettre` : 'interne', 'externe' ou None (les deux).
    `annee` : le سجلّ à lire — celui qui est ouvert par défaut. Un سجلّ
    d'une année écoulée se lit et s'imprime ; il ne s'écrit plus."""
    conn = get_connection()
    try:
        if annee is None:
            annee = _exercice.annee_active(conn)
        if type_lettre in ('interne', 'externe'):
            rows = conn.execute(
                'SELECT * FROM registre WHERE annee=? AND type=? ORDER BY numero ASC',
                (annee, type_lettre)).fetchall()
        else:
            rows = conn.execute(
                'SELECT * FROM registre WHERE annee=? ORDER BY type ASC, numero ASC',
                (annee,)).fetchall()
    finally:
        conn.close()
    out = []
    for r in rows:
        d = dict(r)
        d['source_label'] = REGISTRE_SOURCES.get(d.get('source') or '', '—')
        out.append(d)
    return out


def get_numeros_liberes(type_lettre, annee=None):
    """Numéros rendus au pool par un فسخ, en attente d'être resservis."""
    conn = get_connection()
    try:
        if annee is None:
            annee = _exercice.annee_active(conn)
        rows = conn.execute(
            'SELECT * FROM numeros_liberes WHERE annee=? AND type=? ORDER BY numero ASC',
            (annee, type_lettre)).fetchall()
    finally:
        conn.close()
    return [dict(r) for r in rows]


def registre_lacunes(type_lettre, annee=None):
    """Numéros manquants dans une série — hors numéros rendus au pool par un
    فسخ, qui ne sont pas des trous mais des numéros en attente de réemploi."""
    nums = {r['numero'] for r in get_registre(type_lettre, annee)}
    if not nums:
        return []
    pool = {r['numero'] for r in get_numeros_liberes(type_lettre, annee)}
    return [n for n in range(1, max(nums) + 1) if n not in nums and n not in pool]


# ─── Numéro de départ des deux séries (v58 — diffusion multi-centres) ────────
#
# Un centre qui reçoit la منظومة tient déjà, le plus souvent, un سجلّ ورقي en
# cours. Il doit pouvoir dire « ma série داخلية reprend au 147 » sans que la
# منظومة reparte de 1 — et sans qu'elle puisse jamais redescendre sous un عدد
# déjà inscrit au registre.

def prochain_numero_prevu(type_lettre):
    """Le عدد que la منظومة servira à la prochaine attribution de cette série.

    C'est ce que verra la prochaine مراسلة : le plus petit عدد rendu au pool
    par un فسخ s'il en existe, sinon le compteur + 1."""
    if type_lettre not in ('interne', 'externe'):
        raise ValueError(f"type de مراسلة inconnu : {type_lettre!r}")
    conn = get_connection()
    try:
        annee = _exercice.annee_active(conn)
        row = conn.execute(
            'SELECT numero FROM numeros_liberes WHERE annee=? AND type=? '
            'ORDER BY numero ASC LIMIT 1', (annee, type_lettre)).fetchone()
        if row:
            return row[0]
        row = conn.execute('SELECT valeur FROM compteurs WHERE annee=? AND type=?',
                           (annee, type_lettre)).fetchone()
        return (row[0] if row else 0) + 1
    finally:
        conn.close()


def plancher_numero(type_lettre):
    """Le plus petit عدد qu'il reste permis de servir dans cette série.

    Un عدد déjà inscrit au registre a pu partir sur papier : il ne resservira
    jamais. Le plancher est donc MAX(registre) + 1 — dans le سجلّ ouvert :
    les أعداد de l'année écoulée appartiennent à un autre registre et ne
    bornent pas celui-ci."""
    if type_lettre not in ('interne', 'externe'):
        raise ValueError(f"type de مراسلة inconnu : {type_lettre!r}")
    conn = get_connection()
    try:
        annee = _exercice.annee_active(conn)
        _max = conn.execute(
            'SELECT COALESCE(MAX(numero), 0) FROM registre WHERE annee=? AND type=?',
            (annee, type_lettre)).fetchone()[0]
    finally:
        conn.close()
    return (_max or 0) + 1


def definir_numero_depart(type_lettre, premier_numero):
    """Fixe le PREMIER عدد que la منظومة attribuera dans la série demandée.

    `premier_numero` est le عدد tel que le centre l'écrirait sur son registre :
    on stocke donc `premier_numero - 1` dans le compteur, qui s'incrémente
    AVANT de servir.

    Refuse — par une ValueError — tout عدد inférieur au plancher, c'est-à-dire
    tout عدد déjà inscrit au registre. Cette règle n'est jamais contournable :
    c'est elle qui garantit qu'un عدد parti sur papier ne resservira pas.

    Renvoie le premier عدد effectivement retenu.
    """
    if type_lettre not in ('interne', 'externe'):
        raise ValueError(f"type de مراسلة inconnu : {type_lettre!r}")
    try:
        premier = int(str(premier_numero).strip())
    except (TypeError, ValueError):
        raise ValueError('العدد يجب أن يكون رقما صحيحا')
    if premier < 1:
        raise ValueError('العدد يجب أن يكون 1 على الأقلّ')
    plancher = plancher_numero(type_lettre)
    if premier < plancher:
        raise ValueError(
            f'لا يمكن الانطلاق من العدد {premier}: الأعداد إلى حدود '
            f'{plancher - 1} مسندة فعلا في السّجلّ ولا تُسند مرّتين')
    conn = get_connection()
    try:
        annee = _exercice.annee_active(conn)
        conn.execute('INSERT OR IGNORE INTO compteurs (annee, type, valeur) '
                     'VALUES (?, ?, 0)', (annee, type_lettre))
        conn.execute('UPDATE compteurs SET valeur=? WHERE annee=? AND type=?',
                     (premier - 1, annee, type_lettre))
        conn.commit()
    finally:
        conn.close()
    return premier
