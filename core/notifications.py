# -*- coding: utf-8 -*-
"""V3.1 — إشعارات المشرف العام.

Toute opération d'un autre utilisateur (مستعمل ou autre مشرف عام) déjà
consignée au سجلّ التّدقيق (table `journal`) devient un إشعار pour chaque
مشرف عام, jusqu'à ce qu'il la marque « مقروءة ». Rien de nouveau n'est
journalisé : on lit le journal existant.

Seules les opérations qui CHANGENT quelque chose comptent : l'impression,
l'export, le téléchargement, les entrées / sorties et les copies de
sauvegarde ne sont pas des تحيينات (`EXCLUS`).

L'état de lecture est propre à chaque مشرف : `users.notif_vu` = identifiant
de la dernière entrée du journal qu'il a vue (étape 17 du schéma).
"""

import logging as _logging
from importlib import import_module

_log = _logging.getLogger('formation.' + __name__)

# Débuts d'action qui ne sont pas des تحيينات.
EXCLUS = (
    'طباعة', 'تصدير', 'تحميل', 'تنزيل', 'دخول', 'خروج', 'إيقاف مؤقّت للحساب',
    'إنشاء نسخة احتياطية', 'نسخة احتياطيّة خارجيّة', 'تغيير كلمة المرور',
    'استرجاع آليّ',
)
LIMITE_LISTE = 30


def _db():
    return import_module('core.database')


def _filtre_sql():
    """Clause SQL + paramètres : entrées d'AUTRES utilisateurs, hors EXCLUS."""
    clauses = ["utilisateur != ''", 'utilisateur != ?']
    clauses += ['action NOT LIKE ?'] * len(EXCLUS)
    return ' AND '.join(clauses), [e + '%' for e in EXCLUS]


def _vu(conn, username):
    """Dernière entrée vue par ce مشرف. Première consultation (NULL) : on part
    de l'entrée la plus récente — pas d'avalanche d'historique."""
    r = conn.execute('SELECT notif_vu FROM users WHERE username=?', (username,)).fetchone()
    if r is None:
        return None
    if r[0] is not None:
        return int(r[0])
    dernier = conn.execute('SELECT COALESCE(MAX(id), 0) FROM journal').fetchone()[0]
    conn.execute('UPDATE users SET notif_vu=? WHERE username=?', (dernier, username))
    conn.commit()
    return int(dernier)


def resume(username, limite=LIMITE_LISTE):
    """{'nb': int, 'liste': [dict], 'auteurs': [str]} des إشعارات non lus."""
    conn = _db().get_connection()
    try:
        vu = _vu(conn, username)
        if vu is None:
            return {'nb': 0, 'liste': [], 'auteurs': []}
        filtre, params = _filtre_sql()
        base = f'FROM journal WHERE id > ? AND {filtre}'
        args = [vu, username] + params
        nb = conn.execute(f'SELECT COUNT(*) {base}', args).fetchone()[0]
        liste = [dict(r) for r in conn.execute(
            f'SELECT id, horodatage, utilisateur, action, cible {base} ORDER BY id DESC LIMIT ?',
            args + [int(limite)])]
        auteurs = [r[0] for r in conn.execute(
            f'SELECT utilisateur {base} GROUP BY utilisateur ORDER BY MAX(id) DESC', args)]
        return {'nb': int(nb), 'liste': liste, 'auteurs': auteurs}
    finally:
        conn.close()


def marquer_lues(username):
    """Tout ce qui existe à cet instant devient « مقروء » pour ce مشرف."""
    conn = _db().get_connection()
    try:
        dernier = conn.execute('SELECT COALESCE(MAX(id), 0) FROM journal').fetchone()[0]
        conn.execute('UPDATE users SET notif_vu=? WHERE username=?', (dernier, username))
        conn.commit()
        return int(dernier)
    finally:
        conn.close()


def message_connexion(username):
    """Texte du toast affiché au مشرف à sa connexion ('' si rien de neuf)."""
    try:
        r = resume(username, limite=1)
    except Exception:
        _log.warning('message_connexion : exception ignorée', exc_info=True)
        return ''
    if not r['nb']:
        return ''
    auteurs = '، '.join(r['auteurs'][:3]) + (' وغيرهم' if len(r['auteurs']) > 3 else '')
    return f'🔔 تحيينات جديدة منذ آخر اطّلاع لك (العدد: {r["nb"]}) من طرف: {auteurs} — انظر الإشعارات.'
