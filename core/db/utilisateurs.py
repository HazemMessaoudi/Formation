# -*- coding: utf-8 -*-
"""Utilisateurs, authentification et journal d'audit.

Extrait de core/database.py (v1.4) — importer depuis core.database, qui
ré-exporte tout : les appelants existants restent inchangés."""

from werkzeug.security import check_password_hash, generate_password_hash

from core.db._base import _log, get_connection


# ─── Users / Auth ─────────────────────────────────────────────────────────────

def get_users():
    conn = get_connection()
    rows = conn.execute(
        'SELECT id, username, date_ajout, role, doit_changer_mdp '
        'FROM users ORDER BY id').fetchall()
    conn.close()
    return [dict(r) for r in rows]

def add_user(username, password, role='user'):
    conn = get_connection()
    try:
        conn.execute('INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)',
                     (username.strip(), generate_password_hash(password),
                      'admin' if role == 'admin' else 'user'))
        conn.commit()
        return True
    except Exception:
        _log.warning('add_user : exception ignorée', exc_info=True)
        return False
    finally:
        conn.close()

def update_user_password(username, new_password):
    conn = get_connection()
    try:
        # Changer le mot de passe lève l'obligation de le changer
        conn.execute('UPDATE users SET password_hash=?, doit_changer_mdp=0 WHERE username=?',
                     (generate_password_hash(new_password), username))
        conn.commit()
        return True
    except Exception:
        _log.warning('update_user_password : exception ignorée', exc_info=True)
        return False
    finally:
        conn.close()


def get_user_role(username):
    """'admin' (مشرف عام) ou 'user' (مستعمل). 'user' par défaut."""
    conn = get_connection()
    try:
        r = conn.execute('SELECT role FROM users WHERE username=?', (username,)).fetchone()
        return (r['role'] if r and r['role'] else 'user')
    except Exception:
        _log.warning('get_user_role : exception ignorée', exc_info=True)
        return 'user'
    finally:
        conn.close()


def nb_admins(conn=None):
    """Nombre de comptes مشرف عام."""
    propre = conn is None
    conn = conn or get_connection()
    try:
        return conn.execute("SELECT COUNT(*) FROM users WHERE role='admin'").fetchone()[0]
    finally:
        if propre:
            conn.close()


def changer_role(username, role, demandeur):
    """v1.7 — Change le rôle d'un compte, sous trois gardes :
    • le compte doit exister ;
    • un مشرف ne change pas son propre rôle (il ne peut pas se destituer) ;
    • la منظومة garde toujours au moins un مشرف عام.
    Renvoie (ok, message)."""
    role = 'admin' if role == 'admin' else 'user'
    if username == demandeur:
        return False, 'لا يمكنك تغيير دور حسابك الحالي'
    conn = get_connection()
    try:
        r = conn.execute('SELECT role FROM users WHERE username=?', (username,)).fetchone()
        if not r:
            return False, 'المستخدم غير موجود'
        actuel = r['role'] or 'user'
        if actuel == role:
            return True, ''
        if actuel == 'admin' and nb_admins(conn) <= 1:
            return False, 'يجب الإبقاء على مشرف عام واحد على الأقلّ'
        conn.execute('UPDATE users SET role=? WHERE username=?', (role, username))
        conn.commit()
        return True, ''
    finally:
        conn.close()


def set_user_role(username, role):
    conn = get_connection()
    try:
        conn.execute('UPDATE users SET role=? WHERE username=?',
                     ('admin' if role == 'admin' else 'user', username))
        conn.commit()
        return True
    except Exception:
        _log.warning('set_user_role : exception ignorée', exc_info=True)
        return False
    finally:
        conn.close()


def user_doit_changer_mdp(username):
    conn = get_connection()
    try:
        r = conn.execute('SELECT doit_changer_mdp FROM users WHERE username=?',
                         (username,)).fetchone()
        return bool(r and r['doit_changer_mdp'])
    except Exception:
        _log.warning('user_doit_changer_mdp : exception ignorée', exc_info=True)
        return False
    finally:
        conn.close()


# ─── Journal d'audit ─────────────────────────────────────────────────────────

def journaliser(utilisateur, action, cible='', details=''):
    """Enregistre une action dans le journal d'audit. Ne lève jamais : la
    traçabilité ne doit pas faire échouer l'opération métier."""
    from datetime import datetime as _dt
    try:
        conn = get_connection()
        conn.execute(
            'INSERT INTO journal (horodatage, utilisateur, action, cible, details) '
            'VALUES (?,?,?,?,?)',
            (_dt.now().strftime('%Y-%m-%d %H:%M:%S'), utilisateur or '',
             action, str(cible or ''), str(details or '')[:500]))
        conn.commit()
        conn.close()
        return True
    except Exception:
        _log.warning('journaliser : exception ignorée', exc_info=True)
        return False


def get_journal(limite=200):
    conn = get_connection()
    try:
        rows = conn.execute(
            'SELECT * FROM journal ORDER BY id DESC LIMIT ?', (int(limite),)).fetchall()
        return [dict(r) for r in rows]
    except Exception:
        _log.warning('get_journal : exception ignorée', exc_info=True)
        return []
    finally:
        conn.close()

def delete_user(username):
    conn = get_connection()
    try:
        conn.execute('DELETE FROM users WHERE username=?', (username,))
        conn.commit()
        return True
    except Exception:
        _log.warning('delete_user : exception ignorée', exc_info=True)
        return False
    finally:
        conn.close()

def check_credentials(username, password):
    conn = get_connection()
    row = conn.execute('SELECT password_hash FROM users WHERE username=?', (username,)).fetchone()
    conn.close()
    if row and check_password_hash(row['password_hash'], password):
        return True
    return False


# ─── سجلّ التدقيق : recherche filtrée (v1.5 — S1) ───────────────────────────

def get_journal_filtre(utilisateur='', du='', au='', q='', limite=1000):
    """Entrées du journal, les plus récentes d'abord, filtrées par utilisateur,
    par période (bornes 'AAAA-MM-JJ' incluses) et par texte libre."""
    sql, args = 'SELECT * FROM journal WHERE 1=1', []
    if utilisateur:
        sql += ' AND utilisateur=?'; args.append(utilisateur)
    if du:
        sql += ' AND substr(horodatage, 1, 10) >= ?'; args.append(du[:10])
    if au:
        sql += ' AND substr(horodatage, 1, 10) <= ?'; args.append(au[:10])
    if q:
        sql += ' AND (action LIKE ? OR cible LIKE ? OR details LIKE ?)'
        motif = '%' + q.replace('%', '').replace('_', '') + '%'
        args += [motif, motif, motif]
    sql += ' ORDER BY id DESC LIMIT ?'
    args.append(max(1, min(int(limite or 1000), 20000)))
    conn = get_connection()
    try:
        return [dict(r) for r in conn.execute(sql, args).fetchall()]
    except Exception:
        _log.warning('get_journal_filtre : exception ignorée', exc_info=True)
        return []
    finally:
        conn.close()


def utilisateurs_du_journal():
    conn = get_connection()
    try:
        return [r[0] for r in conn.execute(
            "SELECT DISTINCT utilisateur FROM journal WHERE utilisateur != '' ORDER BY utilisateur").fetchall()]
    finally:
        conn.close()


# ─── v1.7 : blocage temporaire après des échecs répétés ─────────────────────

ECHECS_MAX = 5            # essais manqués consécutifs
BLOCAGE_MINUTES = 5       # durée du blocage
LONGUEUR_MIN_MDP = 6      # مستعمل
LONGUEUR_MIN_MDP_ADMIN = 8  # مشرف عام


def longueur_min_mdp(role):
    return LONGUEUR_MIN_MDP_ADMIN if role == 'admin' else LONGUEUR_MIN_MDP


def minutes_de_blocage(username, maintenant=None):
    """Minutes restantes de blocage (arrondies au-dessus), 0 si libre."""
    from datetime import datetime as _dt
    maintenant = maintenant or _dt.now()
    conn = get_connection()
    try:
        r = conn.execute('SELECT bloque_jusqua FROM users WHERE username=?',
                         (username,)).fetchone()
    finally:
        conn.close()
    if not r or not r['bloque_jusqua']:
        return 0
    try:
        fin = _dt.strptime(r['bloque_jusqua'], '%Y-%m-%d %H:%M:%S')
    except ValueError:
        return 0
    reste = (fin - maintenant).total_seconds()
    return 0 if reste <= 0 else int(-(-reste // 60))


def noter_echec(username, maintenant=None):
    """Compte un échec ; au 5e consécutif, bloque le compte 5 minutes.
    Renvoie True si le compte vient d'être bloqué. Sans effet pour un nom
    inconnu (rien à bloquer)."""
    from datetime import datetime as _dt, timedelta as _td
    maintenant = maintenant or _dt.now()
    conn = get_connection()
    try:
        r = conn.execute('SELECT echecs FROM users WHERE username=?', (username,)).fetchone()
        if not r:
            return False
        n = (r['echecs'] or 0) + 1
        if n >= ECHECS_MAX:
            fin = (maintenant + _td(minutes=BLOCAGE_MINUTES)).strftime('%Y-%m-%d %H:%M:%S')
            conn.execute('UPDATE users SET echecs=0, bloque_jusqua=? WHERE username=?',
                         (fin, username))
            conn.commit()
            return True
        conn.execute('UPDATE users SET echecs=? WHERE username=?', (n, username))
        conn.commit()
        return False
    finally:
        conn.close()


def remettre_a_zero_echecs(username):
    conn = get_connection()
    try:
        conn.execute('UPDATE users SET echecs=0, bloque_jusqua=NULL WHERE username=?',
                     (username,))
        conn.commit()
    finally:
        conn.close()
