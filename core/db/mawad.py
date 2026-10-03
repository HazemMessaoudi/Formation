# -*- coding: utf-8 -*-
"""المواد التكوينية : lecture et CRUD.

Extrait de core/database.py (v1.4) — importer depuis core.database, qui
ré-exporte tout : les appelants existants restent inchangés."""


from core.db._base import _log, get_connection
from core.db.mkowin import _CHAMPS_MADDA, _completer


def delete_madda(madda_id):
    conn = get_connection()
    try:
        conn.execute('DELETE FROM mawad WHERE id = ?', (madda_id,))
        conn.commit()
        return True
    except Exception:
        _log.warning('delete_madda : exception ignorée', exc_info=True)
        return False
    finally:
        conn.close()


def dorrat_liees_mawad():
    """{id مادّة: nombre de دورات portant ce عنوان} (espaces normalisés)."""
    conn = get_connection()
    try:
        compte = {}
        for r in conn.execute('SELECT titre FROM formations').fetchall():
            t = ' '.join(str(r[0] or '').split())
            if t:
                compte[t] = compte.get(t, 0) + 1
        res = {}
        for m in conn.execute('SELECT id, titre FROM mawad').fetchall():
            nb = compte.get(' '.join(str(m['titre'] or '').split()), 0)
            if nb:
                res[m['id']] = nb
        return res
    except Exception:
        _log.warning('dorrat_liees_mawad : exception ignorée', exc_info=True)
        return {}
    finally:
        conn.close()


def nb_dorrat_liees_madda(madda_id):
    return dorrat_liees_mawad().get(madda_id, 0)


def delete_mawad_lot(ids):
    """Suppression groupée d'une sélection de matières de formation."""
    ids = [int(i) for i in (ids or []) if str(i).strip().isdigit()]
    if not ids:
        return 0
    conn = get_connection()
    try:
        marks = ','.join('?' * len(ids))
        cur = conn.execute(f'DELETE FROM mawad WHERE id IN ({marks})', ids)
        conn.commit()
        return cur.rowcount
    except Exception:
        _log.warning('delete_mawad_lot : exception ignorée', exc_info=True)
        return 0
    finally:
        conn.close()


# ─── Mawad (Training Materials) ──────────────────────────────────────────────

def get_mawad():
    conn = get_connection()
    rows = conn.execute('''
        SELECT m.*, mk.nom as mkow_nom, mk.grade as mkow_grade
        FROM mawad m LEFT JOIN mkowin mk ON m.mkow_id = mk.id
        ORDER BY m.titre
    ''').fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_madda(madda_id):
    conn = get_connection()
    row = conn.execute('''
        SELECT m.*, mk.nom as mkow_nom, mk.grade as mkow_grade
        FROM mawad m LEFT JOIN mkowin mk ON m.mkow_id = mk.id
        WHERE m.id = ?
    ''', (madda_id,)).fetchone()
    conn.close()
    return dict(row) if row else None

def get_madda_by_titre(titre):
    """Retrouve la matière (fiche pédagogique) correspondant à un titre de formation."""
    if not titre:
        return None
    conn = get_connection()
    row = conn.execute('SELECT * FROM mawad WHERE titre = ? ORDER BY id DESC LIMIT 1',
                       (titre.strip(),)).fetchone()
    conn.close()
    return dict(row) if row else None

def add_madda(data):
    data = _completer(data, _CHAMPS_MADDA)
    conn = get_connection()
    try:
        conn.execute('''
            INSERT INTO mawad (titre, type_formation, mahawer, objectifs,
                               methodes_pedagogiques, moyens_pedagogiques,
                               preparation_materielle, equipements,
                               mustahdafun, lieu_formation_defaut)
            VALUES (:titre, :type_formation, :mahawer, :objectifs,
                    :methodes_pedagogiques, :moyens_pedagogiques,
                    :preparation_materielle, :equipements,
                    :mustahdafun, :lieu_formation_defaut)
        ''', data)
        conn.commit()
        return True
    except Exception as e:
        _log.exception(f"add_madda error: {e}")
        return False
    finally:
        conn.close()

def update_madda(madda_id, data):
    data = _completer(data, _CHAMPS_MADDA)
    conn = get_connection()
    try:
        conn.execute('''
            UPDATE mawad SET titre=:titre, type_formation=:type_formation,
            mahawer=:mahawer, objectifs=:objectifs,
            methodes_pedagogiques=:methodes_pedagogiques,
            moyens_pedagogiques=:moyens_pedagogiques,
            preparation_materielle=:preparation_materielle,
            equipements=:equipements,
            mustahdafun=:mustahdafun,
            lieu_formation_defaut=:lieu_formation_defaut
            WHERE id=:id
        ''', {**data, 'id': madda_id})
        conn.commit()
        return True
    except Exception as e:
        _log.exception(f"update_madda error: {e}")
        return False
    finally:
        conn.close()
