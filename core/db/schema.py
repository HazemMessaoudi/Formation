# -*- coding: utf-8 -*-
"""Création et migration du schéma (init_db) — migrations additives
et idempotentes.

Extrait de core/database.py (v1.4) — importer depuis core.database, qui
ré-exporte tout : les appelants existants restent inchangés."""

import json
import os
from werkzeug.security import check_password_hash, generate_password_hash
from core import identite
from core import exercice as _exercice
from core import mustahaqqat as _mustahaqqat
from core import bareme_mali as _bareme_mali

from core.db._base import _facade, _log, get_connection
from core.db.registre import _creer_registre
from core.db.referentiels import GRADES_DEFAUT, _semer_jihat
from core.db.khalas import KHALAS_SETTINGS_DEFAUTS


# ══════════════════════════════════════════════════════════════════════════════
#  Création / mise à niveau du schéma — v1.7 : ÉTAPES NUMÉROTÉES
#
#  L'ancienne fonction unique (707 lignes) est découpée en étapes nommées,
#  exécutées dans le MÊME ordre, avec EXACTEMENT les mêmes instructions.
#  Chaque étape reste idempotente : elle s'exécute à chaque démarrage et ne
#  fait rien si son travail est déjà fait. Seules deux valeurs passent d'une
#  étape à l'autre, par `ctx` : installation_existante et existing_lt.
#
#  PRAGMA user_version enregistre la version du schéma atteinte : une future
#  migration saura d'où part la base (voir SCHEMA_VERSION).
# ══════════════════════════════════════════════════════════════════════════════

SCHEMA_VERSION = 21          # V3.1 (إشعارات المشرف العام)


def _etape_01_base_et_tables(conn, ctx):
    """Détection tnsib neuf / mise à niveau, puis tables de base."""
    # ── Tnsib jdid wella tarqiya ? ───────────────────────────────────────────
    # Il FAUT le savoir AVANT de créer la moindre table : une fois le script
    # de création passé, `config` existe toujours et la distinction est perdue.
    #   · config déjà présent  → on met à jour un tnsib existant : on y sème les
    #     valeurs historiques de القصرين pour que rien ne bouge.
    #   · config absent        → tnsib neuf : identité vierge, et l'assistant
    #     d'installation sera demandé au premier lancement.
    _installation_existante = bool(conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='config'"
    ).fetchone())

    conn.executescript('''
        CREATE TABLE IF NOT EXISTS mkowin (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            grade TEXT NOT NULL,
            nom TEXT NOT NULL,
            prenom TEXT,
            cin TEXT,
            cin_date TEXT,
            identifiant_unique TEXT,
            adresse TEXT,
            telephone_gsm TEXT,
            telephone_adm TEXT,
            diplome TEXT,
            degre TEXT,
            plan_fonctionnel TEXT,
            administration TEXT,
            ministere TEXT,
            lieu_travail TEXT,
            specialite TEXT,
            email TEXT,
            banque TEXT,
            agence TEXT,
            num_compte TEXT,
            notes TEXT,
            jiha_marjiiya TEXT,
            date_ajout TEXT DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS lieux (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nom TEXT UNIQUE NOT NULL
        );

        CREATE TABLE IF NOT EXISTS mawad (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            titre TEXT NOT NULL,
            type_formation TEXT DEFAULT 'أساسي',
            mahawer TEXT,
            objectifs TEXT,
            methodes_pedagogiques TEXT,
            moyens_pedagogiques TEXT,
            preparation_materielle TEXT,
            equipements TEXT,
            description TEXT,
            duree TEXT,
            niveau TEXT,
            mkow_id INTEGER REFERENCES mkowin(id),
            date_ajout TEXT DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS compteurs (
            type TEXT PRIMARY KEY,
            valeur INTEGER DEFAULT 0
        );
        INSERT OR IGNORE INTO compteurs (type, valeur) VALUES ('interne', 0);
        INSERT OR IGNORE INTO compteurs (type, valeur) VALUES ('externe', 0);

        CREATE TABLE IF NOT EXISTS grades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nom TEXT UNIQUE NOT NULL
        );

        -- الجهات المرجعيّة : الإدارات الجهويّة للدّيوانة، وحدات الحرس الدّيواني،
        -- وما يضيفه المركز. L'unicité porte sur le couple (type, nom) et non
        -- sur le seul nom : un même libellé peut légitimement exister dans
        -- deux familles différentes, et l'INSERT OR IGNORE du semis doit
        -- rester idempotent à chaque démarrage.
        CREATE TABLE IF NOT EXISTS jihat (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nom TEXT NOT NULL,
            type TEXT NOT NULL DEFAULT 'admin',
            UNIQUE(type, nom)
        );

        CREATE TABLE IF NOT EXISTS lettres (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            type TEXT NOT NULL,
            numero INTEGER NOT NULL,
            ref_complet TEXT NOT NULL,
            mois TEXT NOT NULL,
            annee INTEGER NOT NULL,
            date_creation TEXT DEFAULT CURRENT_TIMESTAMP,
            nom_responsable TEXT DEFAULT '',
            titre_responsable TEXT DEFAULT ''
        );

        CREATE TABLE IF NOT EXISTS formations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            lettre_id INTEGER NOT NULL REFERENCES lettres(id) ON DELETE CASCADE,
            ordre INTEGER NOT NULL,
            titre TEXT NOT NULL,
            grade TEXT,
            nom_formateur TEXT,
            lieu_travail TEXT,
            date_formation TEXT,
            periode TEXT,
            lieu_formation TEXT
        );

        CREATE TABLE IF NOT EXISTS config (
            cle TEXT PRIMARY KEY,
            valeur TEXT NOT NULL
        );
        -- Les valeurs d'identité ne sont plus semées ici : elles le sont par
        -- identite.seeder() plus bas, qui sait distinguer un tnsib neuf d'une
        -- mise à jour. Voir core/identite.py.

        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            date_ajout TEXT DEFAULT CURRENT_TIMESTAMP
        );
    ''')
    for g in GRADES_DEFAUT:
        conn.execute('INSERT OR IGNORE INTO grades (nom) VALUES (?)', (g,))
    ctx['installation_existante'] = _installation_existante


def _etape_02_colonnes_referentiel(conn, ctx):
    """Colonnes ajoutées aux مكوّنون / موادّ et tables manquantes."""
    # Migration : add new mkowin columns if they don't exist yet
    _mkowin_new_cols = [
        ('cin', 'TEXT'),
        ('cin_date', 'TEXT'),
        ('identifiant_unique', 'TEXT'),
        ('adresse', 'TEXT'),
        ('telephone_gsm', 'TEXT'),
        ('telephone_adm', 'TEXT'),
        ('diplome', 'TEXT'),
        ('degre', 'TEXT'),
        ('plan_fonctionnel', 'TEXT'),
        ('administration', 'TEXT'),
        ('ministere', 'TEXT'),
        ('banque', 'TEXT'),
        ('agence', 'TEXT'),
        ('num_compte', 'TEXT'),
        ('jiha_marjiiya', 'TEXT'),
    ]
    existing_mk = {r[1] for r in conn.execute("PRAGMA table_info(mkowin)").fetchall()}
    for col, typedef in _mkowin_new_cols:
        if col not in existing_mk:
            conn.execute(f'ALTER TABLE mkowin ADD COLUMN {col} {typedef}')

    # Migration : add new mawad columns if they don't exist yet
    _mawad_new_cols = [
        ('type_formation', "TEXT DEFAULT 'أساسي'"),
        ('mahawer', 'TEXT'),
        ('objectifs', 'TEXT'),
        ('methodes_pedagogiques', 'TEXT'),
        ('moyens_pedagogiques', 'TEXT'),
        ('preparation_materielle', 'TEXT'),
        ('equipements', 'TEXT'),
        ('mustahdafun', 'TEXT'),
        ('lieu_formation_defaut', 'TEXT'),
    ]
    existing_mw = {r[1] for r in conn.execute("PRAGMA table_info(mawad)").fetchall()}
    for col, typedef in _mawad_new_cols:
        if col not in existing_mw:
            conn.execute(f'ALTER TABLE mawad ADD COLUMN {col} {typedef}')

    # Migration: add missing tables (lieux, lettres, formations, config, grades)
    conn.executescript('''
        CREATE TABLE IF NOT EXISTS lieux (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nom TEXT UNIQUE NOT NULL
        );
        CREATE TABLE IF NOT EXISTS lettres (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            type TEXT NOT NULL,
            numero INTEGER NOT NULL,
            ref_complet TEXT NOT NULL,
            mois TEXT NOT NULL,
            annee INTEGER NOT NULL,
            date_creation TEXT DEFAULT CURRENT_TIMESTAMP,
            nom_responsable TEXT DEFAULT '',
            titre_responsable TEXT DEFAULT ''
        );
        CREATE TABLE IF NOT EXISTS formations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            lettre_id INTEGER NOT NULL REFERENCES lettres(id) ON DELETE CASCADE,
            ordre INTEGER NOT NULL,
            titre TEXT NOT NULL,
            grade TEXT,
            nom_formateur TEXT,
            lieu_travail TEXT,
            date_formation TEXT,
            periode TEXT,
            lieu_formation TEXT
        );
        CREATE TABLE IF NOT EXISTS config (
            cle TEXT PRIMARY KEY,
            valeur TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS compteurs (
            type TEXT PRIMARY KEY,
            valeur INTEGER DEFAULT 0
        );
        INSERT OR IGNORE INTO compteurs (type, valeur) VALUES ('interne', 0);
        INSERT OR IGNORE INTO compteurs (type, valeur) VALUES ('externe', 0);
    ''')


def _etape_03_identite_et_jihat(conn, ctx):
    """Identité du centre, جهات مرجعيّة, nettoyage de la قاعة historique."""
    _installation_existante = ctx['installation_existante']
    # ── Identité du centre ───────────────────────────────────────────────────
    # Source unique : core/identite.py. Sur un tnsib existant on sème les
    # valeurs historiques de القصرين (comportement inchangé) ; sur un tnsib
    # neuf on sème du vide et installation_faite reste à '0'.
    identite.seeder(conn, _installation_existante)

    # ── الجهات المرجعيّة ─────────────────────────────────────────────────────
    # Semé APRÈS identite.seeder : les deux جهات propres au centre
    # (`admin_regionale`, `unite_garde`) viennent du معالج التّنصيب, donc de
    # `config`. Sur un tnsib neuf elles sont encore vides — le semis sera
    # complété à la validation du معالج (voir semer_jihat).
    try:
        _semer_jihat(conn)
    except Exception as e:
        _log.exception(f"jihat: {e}")

    # ── Nettoyage unique de la قاعة par défaut historique ────────────────────
    # « قاعة التكوين المركزية » n'est plus semée : on retire l'ancienne entrée
    # une seule fois, et seulement si aucune formation ne l'utilise.
    try:
        deja = conn.execute("SELECT valeur FROM config WHERE cle='lieu_defaut_nettoye'").fetchone()
        if not deja:
            utilisee = conn.execute(
                "SELECT 1 FROM formations WHERE lieu_formation = 'قاعة التكوين المركزية' LIMIT 1"
            ).fetchone()
            if not utilisee:
                conn.execute("DELETE FROM lieux WHERE nom = 'قاعة التكوين المركزية'")
            conn.execute("INSERT OR REPLACE INTO config (cle, valeur) VALUES ('lieu_defaut_nettoye', '1')")
    except Exception as e:
        _log.exception(f"nettoyage lieu: {e}")


def _etape_04_utilisateurs_et_lettres(conn, ctx):
    """Utilisateurs, compte admin initial, colonnes des مراسلات."""
    # Migration: add users table if not present
    existing_tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
    if 'users' not in existing_tables:
        conn.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                date_ajout TEXT DEFAULT CURRENT_TIMESTAMP
            )
        ''')
    # Insert default admin user if no users exist
    if conn.execute('SELECT COUNT(*) FROM users').fetchone()[0] == 0:
        conn.execute('INSERT INTO users (username, password_hash) VALUES (?, ?)',
                     ('admin', generate_password_hash('admin')))

    # Migration: add categorie + free-letter + verrouille + v12 columns to lettres if missing
    existing_lt = {r[1] for r in conn.execute("PRAGMA table_info(lettres)").fetchall()}
    _lettres_new_cols = [
        ('categorie',     "TEXT DEFAULT 'programme'"),
        ('destinataire',  'TEXT'),
        ('objet',         'TEXT'),
        ('corps',         'TEXT'),
        ('verrouille',    'INTEGER DEFAULT 0'),
        ('msahib',        'TEXT'),
        ('moujah_lahom',  'TEXT'),
        # ── مراسلة المدير الجهوي (الخطوة 2) ────────────────────────────────
        # C'est une مراسلة à part entière : elle porte SON PROPRE numéro, pris
        # dans SA PROPRE série (داخلية ou خارجية selon le choix de l'agent), et
        # jamais celui de la مراسلة du programme. Même principe que la مذكّرة
        # (corrigé en v51) ; ici la correction porte sur l'étape 2.
        ('dr_type',        "TEXT DEFAULT ''"),
        ('dr_numero',      'INTEGER DEFAULT 0'),
        ('dr_ref_complet', "TEXT DEFAULT ''"),
        ('dr_destination', "TEXT DEFAULT ''"),
        ('dr_confirmed_at', 'TEXT DEFAULT NULL'),
        # ── المصادقة النهائيّة على البرنامج (v59) ──────────────────────────
        # Horodatage du « تأكيد البرنامج نهائيّا » : le برنامج a passé la
        # مراجعة de سلامة المعطيات et de الترقيم, et se scelle. NULL tant
        # qu'il n'est pas scellé.
        ('scelle_at',      'TEXT DEFAULT NULL'),
        # ── v1.7 : سنة السّجلّ du عدد (≠ سنة البرنامج pour جانفي أُرسل في ديسمبر)
        # NULL = même année que le برنامج (toutes les مراسلات antérieures).
        ('annee_sejel',    'INTEGER DEFAULT NULL'),
        ('dr_annee_sejel', 'INTEGER DEFAULT NULL'),
    ]
    for col, typedef in _lettres_new_cols:
        if col not in existing_lt:
            conn.execute(f'ALTER TABLE lettres ADD COLUMN {col} {typedef}')
    ctx['existing_lt'] = existing_lt


def _etape_05_lettres_dr(conn, ctx):
    """مراسلات المديرين الجهويّين et date de création des دورات."""
    existing_lt = ctx['existing_lt']
    # ── مراسلات المديرين الجهويّين : une par direction régionale ─────────────
    #
    # Une دورة réunit volontiers des أعوان de plusieurs directions régionales.
    # Chacun de leurs directeurs reçoit alors SA مراسلة — et, comme toute
    # مراسلة رسميّة, elle porte SON عدد propre, tiré de sa série. Trois
    # directeurs, ce sont trois أعداد et trois سطور au سجلّ ; jamais un seul
    # عدد partagé entre plusieurs destinataires.
    #
    # Les colonnes `lettres.dr_*` ne portaient qu'une destination : elles
    # restent en place (une base ancienne doit pouvoir se relire) mais ne sont
    # plus la source de vérité. La reprise ci-dessous les verse dans la
    # nouvelle table, une fois, sans rien perdre.
    conn.execute('''
        CREATE TABLE IF NOT EXISTS dr_lettres (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            lettre_id    INTEGER NOT NULL,
            destination  TEXT NOT NULL,
            type         TEXT NOT NULL,
            numero       INTEGER NOT NULL,
            ref_complet  TEXT NOT NULL,
            confirmed_at TEXT DEFAULT '',
            FOREIGN KEY (lettre_id) REFERENCES lettres(id) ON DELETE CASCADE
        )
    ''')
    # Un عدد ne sert qu'une fois dans sa série ; une direction n'est adressée
    # qu'une fois par برنامج. Ces deux contraintes sont structurelles, non
    # laissées à la vigilance du code appelant.
    # L'unicité du عدد porte sur la سنة aussi : le عدد 1 de 2027 n'est pas
    # celui de 2026, et les deux doivent pouvoir coexister.
    if 'annee' not in {c['name'] for c in conn.execute('PRAGMA table_info(dr_lettres)')}:
        conn.execute('ALTER TABLE dr_lettres ADD COLUMN annee INTEGER')
        conn.execute('DROP INDEX IF EXISTS idx_dr_lettres_type_numero')
    conn.execute('''CREATE UNIQUE INDEX IF NOT EXISTS idx_dr_lettres_annee_type_numero
                    ON dr_lettres(annee, type, numero)''')
    conn.execute('''CREATE UNIQUE INDEX IF NOT EXISTS idx_dr_lettres_destination
                    ON dr_lettres(lettre_id, destination)''')
    conn.execute('''CREATE INDEX IF NOT EXISTS idx_dr_lettres_lettre
                    ON dr_lettres(lettre_id)''')
    if 'dr_numero' in existing_lt or 'dr_numero' in {
            c['name'] for c in conn.execute('PRAGMA table_info(lettres)')}:
        conn.execute('''
            INSERT OR IGNORE INTO dr_lettres
                   (lettre_id, destination, type, numero, ref_complet, confirmed_at, annee)
            SELECT l.id, COALESCE(l.dr_destination, ''), l.dr_type,
                   l.dr_numero, COALESCE(l.dr_ref_complet, ''),
                   COALESCE(l.dr_confirmed_at, ''),
                   COALESCE(l.annee, ?)
            FROM lettres l
            WHERE l.dr_numero > 0 AND l.dr_type IN ('interne', 'externe')
        ''', (_exercice.annee_active(conn),))

    # Migration : date de création de chaque dorra (date et heure du système au
    # moment où elle a été saisie). Les dorrat antérieures héritent de la date de
    # création de leur مراسلة.
    _f_cols = {c['name'] for c in conn.execute('PRAGMA table_info(formations)')}
    if 'date_creation' not in _f_cols:
        conn.execute("ALTER TABLE formations ADD COLUMN date_creation TEXT DEFAULT ''")
        conn.execute('''UPDATE formations SET date_creation = COALESCE(
                            (SELECT l.date_creation FROM lettres l WHERE l.id = formations.lettre_id),
                            '')
                        WHERE date_creation IS NULL OR date_creation = '' ''')


def _etape_06_participants_et_pieces(conn, ctx):
    """المشاركون, مراحل, pièces (برنامج / بطاقة / مذكّرة)."""
    # Migration: add participants table + formation_etapes table
    existing_tables2 = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
    if 'participants' not in existing_tables2:
        conn.execute('''
            CREATE TABLE participants (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                lettre_id INTEGER NOT NULL REFERENCES lettres(id) ON DELETE CASCADE,
                formation_id INTEGER NOT NULL REFERENCES formations(id) ON DELETE CASCADE,
                ordre INTEGER NOT NULL,
                nom_prenom TEXT NOT NULL DEFAULT '',
                grade TEXT DEFAULT '',
                identifiant_unique TEXT DEFAULT '',
                lieu_travail TEXT DEFAULT '',
                jiha_marjiiya TEXT DEFAULT ''
            )
        ''')
    # Migration : الجهة المرجعيّة du مشارك (bases antérieures à la v58).
    # Le CREATE ci-dessus ne s'exécute que si la table n'existe pas ; une base
    # déjà en service passe forcément par cet ALTER.
    _p_cols = {c['name'] for c in conn.execute('PRAGMA table_info(participants)')}
    if 'jiha_marjiiya' not in _p_cols:
        conn.execute("ALTER TABLE participants ADD COLUMN jiha_marjiiya TEXT DEFAULT ''")
    # Migration v1.6 (حزمة ج) : الجنس et الفئة العمريّة du مشارك — servent
    # UNIQUEMENT aux إحصائيات ; aucun document ne les imprime.
    for _col in ('sexe', 'fiaa_omria'):
        if _col not in _p_cols:
            conn.execute(f"ALTER TABLE participants ADD COLUMN {_col} TEXT DEFAULT ''")
    if 'formation_etapes' not in existing_tables2:
        conn.execute('''
            CREATE TABLE formation_etapes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                lettre_id INTEGER NOT NULL REFERENCES lettres(id) ON DELETE CASCADE,
                formation_id INTEGER,
                etape INTEGER NOT NULL,
                validee INTEGER DEFAULT 0,
                date_validation TEXT DEFAULT NULL,
                UNIQUE(lettre_id, formation_id, etape)
            )
        ''')
    if 'programme_formations' not in existing_tables2:
        conn.execute('''
            CREATE TABLE programme_formations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                formation_id INTEGER UNIQUE REFERENCES formations(id) ON DELETE CASCADE,
                reference TEXT DEFAULT '',
                moment TEXT DEFAULT '',
                rows_json TEXT DEFAULT '[]',
                confirmed_at TEXT DEFAULT NULL
            )
        ''')
    if 'bataqa_formations' not in existing_tables2:
        conn.execute('''
            CREATE TABLE bataqa_formations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                formation_id INTEGER UNIQUE REFERENCES formations(id) ON DELETE CASCADE,
                mustahdafun TEXT DEFAULT '',
                services TEXT DEFAULT '',
                mahawer TEXT DEFAULT '',
                objectifs TEXT DEFAULT '',
                methodes_pedagogiques TEXT DEFAULT '',
                moyens_pedagogiques TEXT DEFAULT '',
                preparation_materielle TEXT DEFAULT '',
                equipements TEXT DEFAULT '',
                confirmed_at TEXT DEFAULT NULL
            )
        ''')
    if 'memo_formations' not in existing_tables2:
        conn.execute('''
            CREATE TABLE memo_formations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                formation_id INTEGER UNIQUE REFERENCES formations(id) ON DELETE CASCADE,
                objet TEXT DEFAULT '',
                corps TEXT DEFAULT '',
                moujah_json TEXT DEFAULT '[]',
                heure_debut TEXT DEFAULT '',
                enregistre_at TEXT DEFAULT NULL,
                confirmed_at TEXT DEFAULT NULL
            )
        ''')

    # Migration : colonnes ajoutées à memo_formations
    #  • contenu_manuel : 1 si l'utilisateur a modifié le نص/الموضوع à la main
    #    (sinon le contenu est régénéré à partir des données courantes).
    #  • finalise_at    : horodatage du « تسجيل الدورة في المنظومة » (verrou final).
    _memo_cols = {c['name'] for c in conn.execute("PRAGMA table_info(memo_formations)")}
    if 'contenu_manuel' not in _memo_cols:
        conn.execute("ALTER TABLE memo_formations ADD COLUMN contenu_manuel INTEGER DEFAULT 0")
    if 'finalise_at' not in _memo_cols:
        conn.execute("ALTER TABLE memo_formations ADD COLUMN finalise_at TEXT DEFAULT NULL")
    # La مذكرة porte son PROPRE numéro d'enregistrement (interne), distinct de
    # celui de la مراسلة du programme.
    if 'numero' not in _memo_cols:
        conn.execute("ALTER TABLE memo_formations ADD COLUMN numero INTEGER DEFAULT 0")
    if 'ref_complet' not in _memo_cols:
        conn.execute("ALTER TABLE memo_formations ADD COLUMN ref_complet TEXT DEFAULT ''")
    # La سنة du سجلّ où la مذكّرة a pris son عدد : celle de sa مراسلة.
    if 'annee' not in _memo_cols:
        conn.execute("ALTER TABLE memo_formations ADD COLUMN annee INTEGER")
    conn.execute('''
        UPDATE memo_formations SET annee = (
            SELECT l.annee FROM formations f JOIN lettres l ON l.id = f.lettre_id
            WHERE f.id = memo_formations.formation_id)
        WHERE annee IS NULL''')


def _etape_07_unicite_et_registre(conn, ctx):
    """Unicité des أعداد et سجلّ unique."""
    # Unicité des numéros d'enregistrement attribués (les brouillons portent
    # numero=0 et restent donc hors de l'index partiel).
    #
    # L'unicité inclut la سنة : un سجلّ est annuel, et le عدد 1 de 2027 doit
    # pouvoir coexister avec celui de 2026. Les index d'avant cette version,
    # qui n'en tenaient pas compte, sont déposés — ils interdiraient
    # l'ouverture même du سجلّ suivant.
    conn.execute('DROP INDEX IF EXISTS idx_lettres_type_numero')
    conn.execute('DROP INDEX IF EXISTS idx_memo_numero')
    conn.execute('DROP INDEX IF EXISTS idx_lettres_dr_type_numero')
    # v1.7 : l'unicité porte sur la سنة du سجلّ où le عدد a été pris
    # (annee_sejel), à défaut sur celle du برنامج. Un برنامج جانفي 2027
    # numéroté 26-0001 en ديسمبر et le برنامج فيفري 2027 numéroté 27-0001
    # portent tous deux le عدد 1 sans être en conflit.
    conn.execute('DROP INDEX IF EXISTS idx_lettres_annee_type_numero')
    conn.execute('DROP INDEX IF EXISTS idx_lettres_dr_annee_numero')
    try:
        conn.execute('''CREATE UNIQUE INDEX IF NOT EXISTS idx_lettres_sejel_type_numero
                        ON lettres(COALESCE(annee_sejel, annee), type, numero)
                        WHERE numero > 0''')
    except Exception as e:
        _log.exception(f"index lettres(sejel,type,numero): {e}")
    # La مذكّرة est toujours داخلية ; son عدد est unique dans le سجلّ de
    # l'année de sa مراسلة.
    try:
        conn.execute('''CREATE UNIQUE INDEX IF NOT EXISTS idx_memo_annee_numero
                        ON memo_formations(annee, numero) WHERE numero > 0''')
    except Exception as e:
        _log.exception(f"index memo_formations(annee,numero): {e}")
    try:
        conn.execute('''CREATE UNIQUE INDEX IF NOT EXISTS idx_lettres_dr_sejel_numero
                        ON lettres(COALESCE(dr_annee_sejel, annee), dr_type, dr_numero)
                        WHERE dr_numero > 0''')
    except Exception as e:
        _log.exception(f"index lettres(dr_sejel,dr_type,dr_numero): {e}")

    # Registre unique de TOUS les numéros attribués + resynchronisation des
    # compteurs. Placé après les migrations de colonnes : il a besoin de dr_*.
    try:
        _creer_registre(conn)
    except Exception as e:
        _log.exception(f"registre: {e}")


def _etape_08_ouverture_annee(conn, ctx):
    """Ouverture automatique du سجلّ de l'année."""
    # ── Ouverture automatique du سجلّ de l'année civile ──────────────────────
    # Au 1er janvier la série repart : l'agent qui ouvre la منظومة le 2
    # janvier trouve son nouveau سجلّ prêt, sans rien demander à personne.
    # Les سنوات écoulées restent lisibles et imprimables ; on n'y écrit plus.
    try:
        _cfg_depart = {r['cle']: r['valeur'] for r in
                       conn.execute('SELECT cle, valeur FROM config').fetchall()}
        _bascule = _exercice.basculer_si_necessaire(conn, {
            'interne': _cfg_depart.get('numero_depart_interne') or 1,
            'externe': _cfg_depart.get('numero_depart_externe') or 1,
        })
        if _bascule:
            conn.commit()
            print(f'سجلّ جديد: {_bascule[0]} ← {_bascule[1]}')
    except Exception as e:
        _log.exception(f"bascule d'année: {e}")


def _etape_09_journal_roles_index(conn, ctx):
    """Journal d'audit, rôles, index, blocage de connexion."""
    # Journal d'audit : qui a fait quoi et quand
    conn.execute('''
        CREATE TABLE IF NOT EXISTS journal (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            horodatage TEXT NOT NULL,
            utilisateur TEXT NOT NULL DEFAULT '',
            action TEXT NOT NULL,
            cible TEXT DEFAULT '',
            details TEXT DEFAULT ''
        )
    ''')
    conn.execute('CREATE INDEX IF NOT EXISTS idx_journal_date ON journal(horodatage DESC)')

    # Rôles utilisateurs : 'admin' (مشرف عام) ou 'user' (مستعمل)
    _user_cols = {c['name'] for c in conn.execute("PRAGMA table_info(users)")}
    if 'role' not in _user_cols:
        conn.execute("ALTER TABLE users ADD COLUMN role TEXT DEFAULT 'user'")
        # Le compte historique « admin » devient مشرف عام
        conn.execute("UPDATE users SET role='admin' WHERE username='admin'")
    if 'doit_changer_mdp' not in _user_cols:
        conn.execute("ALTER TABLE users ADD COLUMN doit_changer_mdp INTEGER DEFAULT 0")
        # Si le mot de passe par défaut est encore en place, on force son
        # changement à la prochaine connexion.
        try:
            r = conn.execute("SELECT password_hash FROM users WHERE username='admin'").fetchone()
            if r and check_password_hash(r['password_hash'], 'admin'):
                conn.execute("UPDATE users SET doit_changer_mdp=1 WHERE username='admin'")
        except Exception:
            _log.warning('init_db : exception ignorée', exc_info=True)
            pass

    # v1.7 — index des clés de jointure les plus parcourues (sans effet sur
    # les données ; accélère les listes et statistiques après des années).
    for _nom, _def in (('idx_formations_lettre', 'formations(lettre_id)'),
                       ('idx_participants_formation', 'participants(formation_id)'),
                       ('idx_participants_lettre_formation', 'participants(lettre_id, formation_id)')):
        try:
            conn.execute(f'CREATE INDEX IF NOT EXISTS {_nom} ON {_def}')
        except Exception as e:
            _log.exception(f'index {_nom} : {e}')

    # v1.7 — blocage temporaire après des échecs de connexion répétés.
    _user_cols = {c['name'] for c in conn.execute("PRAGMA table_info(users)")}
    if 'echecs' not in _user_cols:
        conn.execute("ALTER TABLE users ADD COLUMN echecs INTEGER DEFAULT 0")
    if 'bloque_jusqua' not in _user_cols:
        conn.execute("ALTER TABLE users ADD COLUMN bloque_jusqua TEXT DEFAULT NULL")


def _etape_10_mustahaqqat(conn, ctx):
    """المستحقّات المالية (tables et barème des أصناف)."""
    # ── المستحقّات المالية (v1.0) ────────────────────────────────────────────
    #
    # Trois tables, aucune modification de l'existant : la partie التكوين
    # continue de fonctionner mot pour mot comme avant, et une base v61 qui
    # n'a jamais vu les مستحقّات s'ouvre ici sans perdre une ligne.
    conn.executescript('''
        -- Barème « رتبة → صنف ». Semé au premier démarrage avec la table
        -- officielle, puis modifiable : un centre qui ajoute une رتبة lui
        -- donne son صنف sans toucher au code.
        CREATE TABLE IF NOT EXISTS mustahaqqat_grades (
            grade  TEXT PRIMARY KEY,
            classe TEXT NOT NULL DEFAULT ''
        );

        -- Une ligne par dorra dont les مستحقّات sont ouvertes.
        -- etat : 'hodour'  → التأشير على الحضور en cours
        --        'classe'  → الصنف confirmé, reste la valeur financière
        --        'acheve'  → مستحقّات achevées (la dorra passe en « منجزة »)
        CREATE TABLE IF NOT EXISTS mustahaqqat (
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
        );

        -- ورقة الحضور : un حاضر/غائب par participant et par dorra.
        CREATE TABLE IF NOT EXISTS mustahaqqat_hodour (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            formation_id   INTEGER NOT NULL REFERENCES formations(id) ON DELETE CASCADE,
            participant_id INTEGER NOT NULL REFERENCES participants(id) ON DELETE CASCADE,
            present        INTEGER DEFAULT 1,
            UNIQUE(formation_id, participant_id)
        );

        CREATE INDEX IF NOT EXISTS idx_hodour_formation
            ON mustahaqqat_hodour(formation_id);
    ''')

    # Semis du barème officiel — une seule fois, sans jamais écraser un صنف
    # que le centre aurait corrigé lui-même.
    for _libelle, _classe in _mustahaqqat.bareme_defaut().items():
        conn.execute('INSERT OR IGNORE INTO mustahaqqat_grades (grade, classe) '
                     'VALUES (?, ?)', (_libelle, _classe))
    # Les رتب connues de la منظومة mais absentes du barème officiel
    # (المدنيّون : السيد / السيدة) sont inscrites sans صنف : elles apparaissent
    # dans l'écran des الإعدادات, et l'agent voit qu'elles ne sont pas classées.
    for _g in conn.execute('SELECT nom FROM grades').fetchall():
        conn.execute('INSERT OR IGNORE INTO mustahaqqat_grades (grade, classe) '
                     'VALUES (?, ?)', (_g['nom'], ''))

    # Migration : الجنس du مكوّن — nécessaire aux إحصائيات, déduit une fois de
    # la رتبة (السيدة → أنثى, السيد → ذكر) et corrigeable ensuite à la main.
    _mk_cols = {c['name'] for c in conn.execute('PRAGMA table_info(mkowin)')}
    if 'sexe' not in _mk_cols:
        conn.execute("ALTER TABLE mkowin ADD COLUMN sexe TEXT DEFAULT ''")
        conn.execute("UPDATE mkowin SET sexe='أنثى' WHERE TRIM(grade)='السيدة'")
        conn.execute("UPDATE mkowin SET sexe='ذكر'  WHERE TRIM(grade)='السيد'")
    # Migration v1.6 (حزمة ج) : الفئة العمريّة du مكوّن (liste fermée,
    # voir core.validation.FIAAT) — reprise dans la قائمة المشاركين par
    # l'auto-complétion, jamais imprimée.
    if 'fiaa_omria' not in _mk_cols:
        conn.execute("ALTER TABLE mkowin ADD COLUMN fiaa_omria TEXT DEFAULT ''")


def _etape_11_jadwal_mali(conn, ctx):
    """الجدول المالي (groupes, taux) et retrait des رتب ملغاة."""
    # ─── الجدول المالي (v1.1) ────────────────────────────────────────────────
    #
    # Le تصنيف dit à quel صنف appartient une دورة ; le جدول المالي dit combien
    # elle paie. Deux tables distinctes parce que ce sont deux décisions
    # distinctes : la première se déduit des présents, la seconde vient d'un
    # texte réglementaire qui change sans que le تصنيف change.
    conn.executescript('''
        -- رتبة المكوّن → مجموعة الجدول المالي (I, II, III, IV).
        CREATE TABLE IF NOT EXISTS mustahaqqat_groupes (
            grade  TEXT PRIMARY KEY,
            groupe TEXT NOT NULL DEFAULT ''
        );

        -- السعر للساعة الواحدة, à l'intersection (مجموعة, صنف).
        CREATE TABLE IF NOT EXISTS mustahaqqat_bareme_mali (
            groupe  TEXT NOT NULL,
            colonne TEXT NOT NULL,
            taux    REAL NOT NULL DEFAULT 0,
            PRIMARY KEY (groupe, colonne)
        );
    ''')

    # Semis du rattachement officiel — jamais par-dessus un choix du centre.
    for _libelle, _groupe in _bareme_mali.groupes_defaut().items():
        conn.execute('INSERT OR IGNORE INTO mustahaqqat_groupes (grade, groupe) '
                     'VALUES (?, ?)', (_libelle, _groupe))
    # Les رتب connues de la منظومة mais hors du texte (الرقيب, المدنيّون)
    # s'inscrivent sans مجموعة : elles apparaissent dans الإعدادات, et l'agent
    # voit qu'elles ne sont pas encore rattachées.
    for _g in conn.execute('SELECT nom FROM grades').fetchall():
        conn.execute('INSERT OR IGNORE INTO mustahaqqat_groupes (grade, groupe) '
                     'VALUES (?, ?)', (_g['nom'], ''))

    # v1.7 — « الملازم أعلى » et « وكيل أعلى » n'existent pas : retirées une
    # fois pour toutes des tables de référence (رتب، الأصناف، الجدول المالي).
    # Les fiches de personnes ne sont pas touchées. Exécuté une seule fois :
    # un centre qui les réintroduirait délibérément ne les reverrait pas
    # disparaître au démarrage suivant.
    _deja = conn.execute("SELECT valeur FROM config WHERE cle='v17_rutab_retirees'").fetchone()
    if not _deja:
        _retirees = {'ملازم اعلي', 'وكيل اعلي'}
        for _table, _col in (('grades', 'nom'), ('mustahaqqat_groupes', 'grade'),
                             ('mustahaqqat_grades', 'grade')):
            try:
                for _r in conn.execute(f'SELECT {_col} FROM {_table}').fetchall():
                    if _bareme_mali.normaliser_grade(_r[0]) in _retirees:
                        conn.execute(f'DELETE FROM {_table} WHERE {_col}=?', (_r[0],))
            except Exception as e:
                _log.exception(f'retrait des رتب ({_table}) : {e}')
        conn.execute("INSERT OR REPLACE INTO config (cle, valeur) VALUES ('v17_rutab_retirees', '1')")

    # Semis du barème officiel. La colonne أ3 y figure à son taux réglementaire
    # bien qu'aucune رتبة n'y mène aujourd'hui : « دعه فارغا قابلا للتحيين ».
    for (_gr, _col), _taux in _bareme_mali.bareme_defaut().items():
        conn.execute('INSERT OR IGNORE INTO mustahaqqat_bareme_mali '
                     '(groupe, colonne, taux) VALUES (?, ?, ?)',
                     (_gr, _col, _taux))

    # Le chiffrage d'une dorra, figé au moment du تأكيد. On le conserve au lieu
    # de le recalculer : un barème révisé l'an prochain ne doit pas réécrire
    # rétroactivement ce qui a été arrêté et payé cette année.
    _mu_cols = {c['name'] for c in conn.execute('PRAGMA table_info(mustahaqqat)')}
    for _col, _type in (('groupe',      "TEXT DEFAULT ''"),
                        ('heure_debut', "TEXT DEFAULT ''"),
                        ('heure_fin',   "TEXT DEFAULT ''"),
                        ('minutes',     'INTEGER DEFAULT 0'),
                        ('heures',      'INTEGER DEFAULT 0'),
                        ('taux',        'REAL DEFAULT 0'),
                        ('montant',     'REAL DEFAULT 0'),
                        # v1.6 : « جاهز للمصادقة » signalé par l'agent au مشرف
                        ('pret_at',     'TEXT DEFAULT NULL'),
                        ('pret_par',    "TEXT DEFAULT ''")):
        if _col not in _mu_cols:
            conn.execute(f'ALTER TABLE mustahaqqat ADD COLUMN {_col} {_type}')


def _etape_12_khalas(conn, ctx):
    """وثائق الخلاص."""
    # ── وثائق الخلاص (v1.2) ──────────────────────────────────────────────────
    # Deux tables : les المراجع الإدارية (valeurs par défaut révisables) et les
    # champs propres à chaque دورة (n° مذكرة, مقرر, ترخيص, نوع التكوين…). Tout le
    # reste est déjà dans la منظومة (dorra, مستحقّات, fiche المكوّن) et n'est
    # jamais re-saisi. Migration purement additive : rien de la 1.1 n'est touché.
    conn.executescript('''
        CREATE TABLE IF NOT EXISTS khalas_settings (
            cle    TEXT PRIMARY KEY,
            valeur TEXT NOT NULL DEFAULT ''
        );
        CREATE TABLE IF NOT EXISTS khalas_dorra (
            formation_id       INTEGER PRIMARY KEY
                               REFERENCES formations(id) ON DELETE CASCADE,
            numero_mudhakkira  TEXT DEFAULT '',
            muqarrar_numero    TEXT DEFAULT '',
            muqarrar_date      TEXT DEFAULT '',
            tarkhis_numero     TEXT DEFAULT '',
            tarkhis_date       TEXT DEFAULT '',
            type_takwin        TEXT DEFAULT 'mustamir',
            heures_programmees TEXT DEFAULT '',
            heures_realisees   TEXT DEFAULT '',
            notes              TEXT DEFAULT '',
            maj                TEXT DEFAULT ''
        );
    ''')
    for _cle, _val in KHALAS_SETTINGS_DEFAUTS.items():
        conn.execute('INSERT OR IGNORE INTO khalas_settings (cle, valeur) '
                     'VALUES (?, ?)', (_cle, _val))
    # v1.4d : le مقرّر est propre à chaque دورة — l'ancien réglage global
    # (qui portait une valeur d'exemple) ne doit plus pouvoir s'imprimer.
    conn.execute("DELETE FROM khalas_settings WHERE cle IN "
                 "('muqarrar_numero', 'muqarrar_date')")


def _etape_13_identite_base(conn, ctx):
    """Identité (instance_id) de cette base."""
    # ── Identité de CETTE base ───────────────────────────────────────────────
    # Tirée une seule fois, jamais modifiée. Une session n'est valable que pour
    # la base qui l'a ouverte : un cookie resté dans le navigateur depuis une
    # autre installation (ou une base remplacée) ne peut plus faire entrer
    # personne sans passer par l'écran de connexion.
    conn.execute("INSERT OR IGNORE INTO config (cle, valeur) VALUES ('instance_id', ?)",
                 (os.urandom(16).hex(),))


def _etape_14_suggestions_programme(conn, ctx):
    """v1.7.1 — Mémoire des بيان النشاط et des المتدخّلون déjà saisis dans les
    برامج الدورات, pour les proposer à la saisie. Reprise, une seule fois, de
    tout ce que contiennent déjà les programmes enregistrés."""
    conn.execute('''
        CREATE TABLE IF NOT EXISTS programme_suggestions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nature TEXT NOT NULL,              -- 'activite' | 'intervenant'
            texte  TEXT NOT NULL,
            usages INTEGER NOT NULL DEFAULT 1,
            dernier_usage TEXT DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(nature, texte)
        )''')
    fait = conn.execute("SELECT valeur FROM config WHERE cle='v171_suggestions_reprises'").fetchone()
    if fait:
        return
    from core.db.suggestions import memoriser_lignes
    for (rows_json,) in conn.execute(
            "SELECT rows_json FROM programme_formations WHERE rows_json IS NOT NULL").fetchall():
        try:
            lignes = json.loads(rows_json or '[]')
        except (TypeError, ValueError):
            continue
        memoriser_lignes(conn, lignes)
    conn.execute("INSERT OR REPLACE INTO config (cle, valeur) VALUES ('v171_suggestions_reprises', '1')")


def _etape_15_dorrat_multi_jours(conn, ctx):
    """V2 — الدّورات متعدّدة الأيّام.

    • formations.date_fin : dernier jour de la دورة ('' = دورة d'un jour, cas
      de TOUTES les دورات antérieures : rien ne change pour elles) ;
    • programme_jours : برنامج saisi jour par jour (فترة propre à chaque jour,
      confirmation jour après jour) ; à la confirmation du dernier jour, le
      برنامج complet est recomposé dans programme_formations ;
    • mustahaqqat_hodour_jours : ورقة الحضور jour par jour (un حاضر/غائب par
      مشارك et par jour) ; mustahaqqat_hodour garde la synthèse (حاضر au
      moins un jour) lue par les شهادات et les écrans existants."""
    _f_cols = {c['name'] for c in conn.execute('PRAGMA table_info(formations)')}
    if 'date_fin' not in _f_cols:
        conn.execute("ALTER TABLE formations ADD COLUMN date_fin TEXT DEFAULT ''")
    conn.executescript('''
        CREATE TABLE IF NOT EXISTS programme_jours (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            formation_id INTEGER NOT NULL REFERENCES formations(id) ON DELETE CASCADE,
            jour         INTEGER NOT NULL,
            date_jour    TEXT    NOT NULL DEFAULT '',
            periode      TEXT    DEFAULT '',
            rows_json    TEXT    DEFAULT '[]',
            confirmed_at TEXT    DEFAULT NULL,
            UNIQUE(formation_id, jour)
        );
        CREATE INDEX IF NOT EXISTS idx_programme_jours_formation
            ON programme_jours(formation_id);

        CREATE TABLE IF NOT EXISTS mustahaqqat_hodour_jours (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            formation_id   INTEGER NOT NULL REFERENCES formations(id) ON DELETE CASCADE,
            participant_id INTEGER NOT NULL REFERENCES participants(id) ON DELETE CASCADE,
            jour           INTEGER NOT NULL,
            present        INTEGER DEFAULT 1,
            UNIQUE(formation_id, participant_id, jour)
        );
        CREATE INDEX IF NOT EXISTS idx_hodour_jours_formation
            ON mustahaqqat_hodour_jours(formation_id);
    ''')
    _nettoyer_fantomes_dr(conn)


def _nettoyer_fantomes_dr(conn):
    """V2 (correctif) — Retire du سجلّ les lignes « fantômes » des مراسلات
    المديرين الجهويّين : la même مراسلة (même عدد, même مرجع, même برنامج)
    réinscrite par erreur sous une AUTRE سنة que celle de son مرجع (voir
    registre._creer_registre). La ligne authentique, sous la bonne سنة, est
    conservée ; aucun عدد réellement servi n'est touché, aucun compteur ne
    recule. Idempotent."""
    import re as _re
    lignes = [dict(r) for r in conn.execute(
        "SELECT id, annee, type, numero, ref_complet, source_id FROM registre "
        "WHERE source='directeur'").fetchall()]
    par_ref = {}
    for l in lignes:
        par_ref.setdefault((l['ref_complet'], l['source_id'], l['type'], l['numero']), []).append(l)
    supprimes = 0
    for (ref, _sid, _t, _n), groupe in par_ref.items():
        m = _re.search(r'-(\d{2})-\d+$', ref or '')
        if not m or len(groupe) < 2:
            continue
        aa = m.group(1)
        bons = [l for l in groupe if str(l['annee'])[-2:] == aa]
        if not bons:
            continue
        for l in groupe:
            if str(l['annee'])[-2:] != aa:
                conn.execute('DELETE FROM registre WHERE id=?', (l['id'],))
                supprimes += 1
    if supprimes:
        _log.warning('V2 : %s ligne(s) fantôme(s) retirée(s) du سجلّ (مراسلات المدير الجهوي)',
                     supprimes)
        ancien = conn.execute("SELECT valeur FROM config WHERE cle='v2_fantomes_dr_retires'").fetchone()
        total = supprimes + (int(ancien['valeur']) if ancien and str(ancien['valeur']).isdigit() else 0)
        conn.execute("INSERT OR REPLACE INTO config (cle, valeur) VALUES ('v2_fantomes_dr_retires', ?)",
                     (str(total),))


def _etape_16_classification_rapports(conn, ctx):
    """V3 — تصنيف الدّورات (إحصائيّات وتقارير فقط, AUCUN effet sur le
    déroulement du برنامج) :

    • formations.mode_formation   : 'حضوري' (défaut) | 'عن بعد' ;
    • formations.niveau_formation : 'جهوي' (défaut) | 'مركزي' | 'مختص' ;
    • formations.cooperation      : '' (défaut) | 'وطني' | 'دولي' ;
    • formations.hors_plan        : 0 (défaut) | 1 (خارج المخطّط) ;
    • parametres_annuels          : عدد الدّورات المبرمجة par سنة (نسبة الإنجاز).

    Les دورات antérieures prennent les valeurs par défaut : rien ne change
    pour elles. Idempotent."""
    _f_cols = {c['name'] for c in conn.execute('PRAGMA table_info(formations)')}
    for nom, ddl in (
        ('mode_formation',   "TEXT DEFAULT 'حضوري'"),
        ('niveau_formation', "TEXT DEFAULT 'جهوي'"),
        ('cooperation',      "TEXT DEFAULT ''"),
        ('hors_plan',        'INTEGER DEFAULT 0'),
    ):
        if nom not in _f_cols:
            conn.execute(f'ALTER TABLE formations ADD COLUMN {nom} {ddl}')
    conn.executescript('''
        CREATE TABLE IF NOT EXISTS parametres_annuels (
            annee                 INTEGER PRIMARY KEY,
            nb_dorrat_programmees INTEGER DEFAULT 0,
            date_maj              TEXT    DEFAULT ''
        );
    ''')


def _etape_17_notifications(conn, ctx):
    """V3.1 — إشعارات المشرف العام : `users.notif_vu` = dernière entrée du
    journal vue par le compte. Les comptes existants partent de l'entrée la
    plus récente (aucune avalanche d'historique à la mise à jour). Idempotent."""
    _u_cols = {c['name'] for c in conn.execute('PRAGMA table_info(users)')}
    if 'notif_vu' not in _u_cols:
        conn.execute('ALTER TABLE users ADD COLUMN notif_vu INTEGER')
        dernier = conn.execute('SELECT COALESCE(MAX(id), 0) FROM journal').fetchone()[0]
        conn.execute('UPDATE users SET notif_vu=?', (dernier,))


ETAPES = (
    _etape_01_base_et_tables,
    _etape_02_colonnes_referentiel,
    _etape_03_identite_et_jihat,
    _etape_04_utilisateurs_et_lettres,
    _etape_05_lettres_dr,
    _etape_06_participants_et_pieces,
    _etape_07_unicite_et_registre,
    _etape_08_ouverture_annee,
    _etape_09_journal_roles_index,
    _etape_10_mustahaqqat,
    _etape_11_jadwal_mali,
    _etape_12_khalas,
    _etape_13_identite_base,
    _etape_14_suggestions_programme,
    _etape_15_dorrat_multi_jours,
    _etape_16_classification_rapports,
    _etape_17_notifications,
)


def init_db():
    """Crée ou met à niveau la base : toutes les étapes, dans l'ordre."""
    os.makedirs(os.path.dirname(_facade().DB_PATH), exist_ok=True)
    conn = get_connection()

    try:
        ctx = {}
        for etape in ETAPES:
            etape(conn, ctx)
        conn.execute(f'PRAGMA user_version = {SCHEMA_VERSION}')
        conn.commit()
    finally:
        conn.close()


def version_schema():
    """Version du schéma enregistrée dans la base (0 = antérieure à la v1.7)."""
    conn = get_connection()
    try:
        return conn.execute('PRAGMA user_version').fetchone()[0]
    finally:
        conn.close()
