# -*- coding: utf-8 -*-
"""Référentiels : configuration, رتب, أماكن التكوين, الجهات المرجعيّة.

Extrait de core/database.py (v1.4) — importer depuis core.database, qui
ré-exporte tout : les appelants existants restent inchangés."""

from core import regions

from core.db._base import _log, get_connection
from core.db.registre import _attribuer_numero


GRADES_DEFAUT = [
    # Officiers (ضبّاط) : de اللواء à ملازم (v1.7 : اللواء ajouté)
    'اللواء', 'العميد', 'العقيد', 'المقدم', 'الرائد', 'النقيب',
    'الملازم أول', 'الملازم',
    # Sous-officiers (ضبّاط صف) : de وكيل أول à عريف (v1.7 : العريف الأعلى ajouté)
    'الوكيل أول', 'الوكيل', 'الرقيب أول', 'الرقيب',
    'العريف الأعلى', 'العريف أول', 'العريف',
    # Civils
    'السيدة', 'السيد',
]


def get_config():
    conn = get_connection()
    rows = conn.execute('SELECT cle, valeur FROM config').fetchall()
    conn.close()
    return {r['cle']: r['valeur'] for r in rows}

def get_grades():
    conn = get_connection()
    rows = conn.execute('SELECT nom FROM grades ORDER BY id').fetchall()
    conn.close()
    return [r['nom'] for r in rows]

def add_grade(nom):
    conn = get_connection()
    try:
        conn.execute('INSERT OR IGNORE INTO grades (nom) VALUES (?)', (nom,))
        conn.commit()
        return True
    except Exception:
        _log.warning('add_grade : exception ignorée', exc_info=True)
        return False
    finally:
        conn.close()

def get_next_ref(type_lettre):
    conn = get_connection()
    try:
        ref, numero = _attribuer_numero(conn, type_lettre, 'programme', None, '')
        conn.commit()
        return ref, numero
    finally:
        conn.close()


# ─── Lieux ───────────────────────────────────────────────────────────────────

def get_lieux():
    conn = get_connection()
    rows = conn.execute('SELECT nom FROM lieux ORDER BY id').fetchall()
    conn.close()
    return [r['nom'] for r in rows]

def add_lieu(nom):
    conn = get_connection()
    try:
        conn.execute('INSERT OR IGNORE INTO lieux (nom) VALUES (?)', (nom,))
        conn.commit()
        return True
    except Exception:
        _log.warning('add_lieu : exception ignorée', exc_info=True)
        return False
    finally:
        conn.close()

def delete_lieu(nom):
    conn = get_connection()
    try:
        conn.execute('DELETE FROM lieux WHERE nom = ?', (nom,))
        conn.commit()
        return True
    except Exception:
        _log.warning('delete_lieu : exception ignorée', exc_info=True)
        return False
    finally:
        conn.close()


# ─── الجهات المرجعيّة ─────────────────────────────────────────────────────────
#
# Une جهة est l'administration de rattachement d'un مكوّن ou d'un مشارك :
# إدارة جهويّة للدّيوانة, وحدة للحرس الدّيواني, ou toute autre جهة que le centre
# ajoute lui-même. Les libellés proposés viennent de core/regions.py ; ils sont
# copiés dans la قاعدة pour que chaque centre puisse les corriger, en retirer
# ou en ajouter sans toucher au code.


def _semer_jihat(conn):
    """Plante les جهات proposées. Idempotent : ne réécrit ni n'écrase rien.

    `INSERT OR IGNORE` — le même choix que pour `grades` et `lieux` — garantit
    qu'une جهة renommée ou supprimée par le centre ne réapparaît pas à chaque
    démarrage… sauf si elle a été supprimée sans être renommée, auquel cas elle
    revient. C'est assumé : le semis ne connaît pas l'intention de l'utilisateur,
    et une liste de suggestions qui se reconstitue est moins grave qu'une جهة
    du centre qui disparaît.
    """
    cfg = {r['cle']: r['valeur'] for r in conn.execute('SELECT cle, valeur FROM config')}
    for nom, type_jiha in regions.jihat_a_semer(cfg):
        conn.execute('INSERT OR IGNORE INTO jihat (nom, type) VALUES (?, ?)',
                     (nom, type_jiha))
    # بذر قاعة التّكوين الافتراضيّة في جدول lieux من الإعداد الأوّلي
    lieu_defaut = (cfg.get('lieu_formation_defaut') or '').strip()
    if lieu_defaut:
        conn.execute('INSERT OR IGNORE INTO lieux (nom) VALUES (?)', (lieu_defaut,))


def semer_jihat():
    """Rejoue le semis — appelé à la fin du معالج التّنصيب, une fois connues
    l'إدارة جهويّة et la وحدة حرس propres au centre."""
    conn = get_connection()
    try:
        _semer_jihat(conn)
        conn.commit()
        return True
    except Exception as e:
        _log.exception(f"semer_jihat: {e}")
        return False
    finally:
        conn.close()


def get_jihat(type_jiha=None):
    """Les جهات, triées par famille puis par ordre d'ajout.

    Sans argument : toutes. Avec un type : cette famille seulement.
    """
    conn = get_connection()
    if type_jiha:
        rows = conn.execute(
            'SELECT id, nom, type FROM jihat WHERE type = ? ORDER BY id', (type_jiha,)
        ).fetchall()
    else:
        rows = conn.execute('''
            SELECT id, nom, type FROM jihat
            ORDER BY CASE type WHEN 'admin' THEN 0 WHEN 'garde' THEN 1 ELSE 2 END, id
        ''').fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_jihat_groupees():
    """Les جهات rangées par famille, dans l'ordre d'affichage attendu.

    Renvoie une liste de dicts {type, libelle, jihat} — les familles vides
    comprises, pour que la page de gestion montre où ajouter.
    """
    toutes = get_jihat()
    return [{'type': t,
             'libelle': regions.LIBELLES_TYPES[t],
             'jihat': [j for j in toutes if j['type'] == t]}
            for t in regions.TYPES]


def noms_jihat():
    """Tous les libellés, pour alimenter une liste déroulante."""
    return [j['nom'] for j in get_jihat()]


def add_jiha(nom, type_jiha=regions.TYPE_ADMIN):
    """Ajoute une جهة. Renvoie False si le libellé est vide ou déjà présent."""
    nom = (nom or '').strip()
    if not nom:
        return False
    if type_jiha not in regions.TYPES:
        type_jiha = regions.TYPE_AUTRE
    conn = get_connection()
    try:
        cur = conn.execute('INSERT OR IGNORE INTO jihat (nom, type) VALUES (?, ?)',
                           (nom, type_jiha))
        conn.commit()
        return cur.rowcount > 0
    except Exception as e:
        _log.exception(f"add_jiha error: {e}")
        return False
    finally:
        conn.close()


def delete_jiha(jiha_id):
    """Retire une جهة de la liste.

    Les مكوّنون et المشاركون qui la portaient gardent leur valeur : elle est
    stockée en toutes lettres, pas par référence. Retirer une جهة de la liste
    ne réécrit donc aucune donnée déjà saisie — c'est voulu.
    """
    conn = get_connection()
    try:
        conn.execute('DELETE FROM jihat WHERE id = ?', (jiha_id,))
        conn.commit()
        return True
    except Exception as e:
        _log.exception(f"delete_jiha error: {e}")
        return False
    finally:
        conn.close()


# ─── Config ───────────────────────────────────────────────────────────────────

def update_config(cle, valeur):
    conn = get_connection()
    try:
        conn.execute('INSERT OR REPLACE INTO config (cle, valeur) VALUES (?, ?)', (cle, valeur))
        conn.commit()
        return True
    except Exception:
        _log.warning('update_config : exception ignorée', exc_info=True)
        return False
    finally:
        conn.close()
