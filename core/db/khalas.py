# -*- coding: utf-8 -*-
"""وثائق الخلاص : المراجع الإدارية et données propres à chaque دورة.

Extrait de core/database.py (v1.4) — importer depuis core.database, qui
ré-exporte tout : les appelants existants restent inchangés."""


from core.db._base import _log, get_connection


# ═══ وثائق الخلاص — القيم الافتراضية للمراجع الإدارية ═════════════════════════
# Semées au premier démarrage, révisables depuis « إعدادات وثائق الخلاص ».
# Tirées des modèles officiels fournis ; l'agent les corrige une fois pour toutes.
KHALAS_SETTINGS_DEFAUTS = {
    'ordre_tajir':      'الأمر عدد 2650 لسنة 2008 المؤرّخ في 21 جويلية 2008',
    'ordre_1995':       'الأمر عدد 83 لسنة 1995 المؤرّخ في 16 جانفي 1995',
    'directeur_grade':  'العميد',
    'directeur_nom':    'جوهر حسيون',
    'directeur_titre':  'مدير إدارة التكوين الجهوي والمختص',
    'ministere_ichraf': 'وزارة المالية',
    'taux_adaat':       '15',      # édité depuis «الجدول المالي»
}

#: Le مقرّر n'est PLUS un réglage : chaque دورة a le sien, saisi à l'entrée
#: du قسم المستحقّات (v1.4d). Ces clés, héritées des versions précédentes,
#: sont retirées de la base et ignorées si elles y restent.
KHALAS_SETTINGS_RETIRES = ('muqarrar_numero', 'muqarrar_date')


# ═══════════════════════════════════════════════════════════════════════════
#  وثائق الخلاص (v1.2) — accès aux réglages et aux données par دورة
# ═══════════════════════════════════════════════════════════════════════════

def get_khalas_settings():
    """Les المراجع الإدارية, valeurs stockées par-dessus les défauts semés."""
    d = dict(KHALAS_SETTINGS_DEFAUTS)
    conn = get_connection()
    try:
        for r in conn.execute('SELECT cle, valeur FROM khalas_settings').fetchall():
            if r['cle'] in KHALAS_SETTINGS_RETIRES:
                continue
            if r['valeur'] is not None and str(r['valeur']).strip() != '':
                d[r['cle']] = r['valeur']
    except Exception:
        _log.warning('get_khalas_settings : exception ignorée', exc_info=True)
        pass
    finally:
        conn.close()
    return d


def set_khalas_settings(valeurs):
    """Écrit (ou met à jour) les réglages fournis. Les clés inconnues sont
    acceptées : le module peut en ajouter sans migration."""
    conn = get_connection()
    try:
        for cle, valeur in (valeurs or {}).items():
            conn.execute(
                'INSERT INTO khalas_settings (cle, valeur) VALUES (?, ?) '
                'ON CONFLICT(cle) DO UPDATE SET valeur = excluded.valeur',
                (str(cle), '' if valeur is None else str(valeur)))
        conn.commit()
    finally:
        conn.close()


def get_khalas_dorra(formation_id):
    """Champs propres à une دورة pour ses وثائق الخلاص ; {} si rien n'est saisi."""
    conn = get_connection()
    try:
        row = conn.execute('SELECT * FROM khalas_dorra WHERE formation_id = ?',
                           (formation_id,)).fetchone()
        return dict(row) if row else {}
    finally:
        conn.close()


def save_khalas_dorra(formation_id, data):
    """Enregistre (upsert) les champs propres à la دورة. Seules les colonnes
    connues sont écrites — le reste du dict est ignoré sans erreur."""
    colonnes = ('numero_mudhakkira', 'muqarrar_numero', 'muqarrar_date',
                'tarkhis_numero', 'tarkhis_date', 'type_takwin',
                'heures_programmees', 'heures_realisees', 'notes')
    from datetime import datetime as _dt
    vals = {c: ('' if data.get(c) is None else str(data.get(c, ''))) for c in colonnes}
    maj = _dt.now().strftime('%Y-%m-%d %H:%M:%S')
    conn = get_connection()
    try:
        cols = ', '.join(colonnes)
        ph = ', '.join('?' for _ in colonnes)
        upd = ', '.join(f'{c}=excluded.{c}' for c in colonnes)
        conn.execute(
            f'INSERT INTO khalas_dorra (formation_id, {cols}, maj) '
            f'VALUES (?, {ph}, ?) '
            f'ON CONFLICT(formation_id) DO UPDATE SET {upd}, maj=excluded.maj',
            (formation_id, *[vals[c] for c in colonnes], maj))
        conn.commit()
    finally:
        conn.close()


def get_muqarrar_dorra(formation_id):
    """(عدد المقرّر, تاريخه ISO) propres à la دورة ; ('', '') si non saisis."""
    d = get_khalas_dorra(formation_id)
    return (d.get('muqarrar_numero') or '').strip(), (d.get('muqarrar_date') or '').strip()


def muqarrar_manquant(formation_id):
    """Vrai tant que la دورة n'a pas son مقرّر : aucune مستحقّات sans lui."""
    numero, date_m = get_muqarrar_dorra(formation_id)
    return not (numero and date_m)


def save_muqarrar_dorra(formation_id, numero, date_iso):
    """N'écrit QUE le مقرّر : les autres champs de la دورة restent intacts."""
    from datetime import datetime as _dt
    maj = _dt.now().strftime('%Y-%m-%d %H:%M:%S')
    conn = get_connection()
    try:
        conn.execute(
            'INSERT INTO khalas_dorra (formation_id, muqarrar_numero, muqarrar_date, maj) '
            'VALUES (?, ?, ?, ?) ON CONFLICT(formation_id) DO UPDATE SET '
            'muqarrar_numero=excluded.muqarrar_numero, '
            'muqarrar_date=excluded.muqarrar_date, maj=excluded.maj',
            (formation_id, (numero or '').strip(), (date_iso or '').strip(), maj))
        conn.commit()
    finally:
        conn.close()


def _norm_grade(g):
    import re as _re
    g = ' '.join(str(g or '').replace('ـ', '').split())
    g = _re.sub(r'^ال', '', g)
    return g.replace('الديوانة', 'ديوانة').replace('للديوانة', 'ديوانة')


def candidats_mkow_par_nom(nom):
    """Toutes les fiches mkowin dont le nom correspond (tolérant aux espaces
    et à l'ordre nom/prénom)."""
    cible = ' '.join(str(nom or '').split())
    if not cible:
        return []
    conn = get_connection()
    try:
        rows = conn.execute('SELECT * FROM mkowin').fetchall()
    finally:
        conn.close()
    res = []
    for r in rows:
        d = dict(r)
        n = ' '.join(str(d.get('nom') or '').split())
        p = ' '.join(str(d.get('prenom') or '').split())
        formes = {n, f'{n} {p}'.strip(), f'{p} {n}'.strip()}
        if cible in {f for f in formes if f}:
            res.append(d)
    return res


def trouver_mkow_par_nom(nom, grade=None):
    """Retrouve LA fiche d'un المكوّن à partir de son nom (celui saisi dans la
    dorra). En cas d'homonymes, on départage par la رتبة ; si l'ambiguïté
    persiste, on renvoie {} — jamais la fiche d'une autre personne."""
    cands = candidats_mkow_par_nom(nom)
    if len(cands) > 1 and grade:
        g = _norm_grade(grade)
        cands = [c for c in cands if _norm_grade(c.get('grade')) == g]
    return cands[0] if len(cands) == 1 else {}
