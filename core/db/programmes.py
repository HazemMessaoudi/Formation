# -*- coding: utf-8 -*-
"""برامج التكوين et دورات : مراسلات, مراسلة المدير الجهوي, مراجعة,
مراسلات حرّة, étapes, المشاركون, البطاقة البيداغوجية, البرنامج, المذكّرة.

Extrait de core/database.py (v1.4) — importer depuis core.database, qui
ré-exporte tout : les appelants existants restent inchangés."""

import json
import re
from core import exercice as _exercice
from core import jours as _jours
from core import classification as _classif

from core.db._base import _log, get_connection
from core.db.registre import _attribuer_numero, _liberer_numero, confirmer_numeros_programme, liberer_numeros_programme


def _date_fin_de(f):
    """V2 — date de fin enregistrée d'une دورة : '' pour une دورة d'un jour
    (voir core.jours.normaliser_fin)."""
    return _jours.normaliser_fin(f.get('date_formation', ''), f.get('date_fin', ''))


def _classif_de(f, anciennes=None):
    """V3 — (mode, niveau, cooperation, hors_plan) normalisés, dans l'ordre
    des colonnes (voir core.classification)."""
    c = _classif.normaliser(f, anciennes)
    return tuple(c[k] for k in _classif.CHAMPS)


def annuler_dorra(formation_id):
    """فسخ دورة واحدة — les autres dorrat du même programme ne sont pas touchées.

    Chaque dorra vit sa propre vie à partir de l'étape 3 : en annuler une ne doit
    jamais empêcher les autres d'aller jusqu'à leur تسجيل, ni l'inverse. Le
    numéro de sa مذكّرة, s'il est encore provisoire, revient au pool.

    Refusé dès que CETTE dorra est enregistrée définitivement (`finalise_at`).
    Renvoie (ok, message)."""
    conn = get_connection()
    try:
        row = conn.execute(
            'SELECT lettre_id, titre FROM formations WHERE id=?', (formation_id,)).fetchone()
        if not row:
            return False, 'الدورة غير موجودة'
        m = conn.execute(
            'SELECT finalise_at FROM memo_formations WHERE formation_id=?',
            (formation_id,)).fetchone()
        if m and m['finalise_at']:
            return False, 'الدورة مسجَّلة نهائيًّا في المنظومة ولا يمكن فسخها'

        for r in conn.execute(
                "SELECT annee, type, numero FROM registre "
                "WHERE source='memo' AND source_id=? AND statut='provisoire'",
                (formation_id,)).fetchall():
            _liberer_numero(conn, r['type'], r['numero'], f'فسخ دورة #{formation_id}',
                            annee=r['annee'])

        conn.execute('DELETE FROM programme_formations WHERE formation_id=?', (formation_id,))
        conn.execute('DELETE FROM programme_jours      WHERE formation_id=?', (formation_id,))
        conn.execute('DELETE FROM bataqa_formations    WHERE formation_id=?', (formation_id,))
        conn.execute('DELETE FROM memo_formations      WHERE formation_id=?', (formation_id,))
        conn.execute('DELETE FROM participants         WHERE formation_id=?', (formation_id,))
        conn.execute('DELETE FROM formation_etapes     WHERE formation_id=?', (formation_id,))
        conn.execute('DELETE FROM formations           WHERE id=?', (formation_id,))
        conn.commit()

        # Si c'était la dernière dorra non enregistrée, le programme est achevé :
        # ses numéros deviennent définitifs.
        lid = row['lettre_id']
        reste = conn.execute(
            'SELECT COUNT(*) FROM formations f '
            'LEFT JOIN memo_formations m ON m.formation_id = f.id '
            'WHERE f.lettre_id=? AND (m.finalise_at IS NULL OR m.finalise_at = "")',
            (lid,)).fetchone()[0]
        total = conn.execute('SELECT COUNT(*) FROM formations WHERE lettre_id=?',
                             (lid,)).fetchone()[0]
        if total and reste == 0:
            confirmer_numeros_programme(conn, lid)
            conn.commit()
        return True, row['titre'] or ''
    except Exception as e:
        _log.exception(f"annuler_dorra error: {e}")
        return False, str(e)
    finally:
        conn.close()


def delete_programme_inacheve(lettre_id):
    """فسخ برنامج تكوين : supprime définitivement le programme et tout son
    contenu lié (formations, participants, étapes, programme/bataqa/mémo), et
    REND AU POOL les numéros encore provisoires qu'il avait consommés — celui de
    sa مراسلة, celui de sa مراسلة المدير الجهوي et ceux de ses مذكّرات.

    Le فسخ reste possible tant qu'AUCUNE dorra n'a été enregistrée
    définitivement dans la منظومة (`finalise_at`). Dès qu'une seule l'est, le
    programme a produit un acte irréversible et le فسخ est refusé.

    Renvoie True, ou False si le programme n'existe pas / n'est plus fsakhable."""
    conn = get_connection()
    try:
        row = conn.execute('SELECT verrouille FROM lettres WHERE id=?',
                            (lettre_id,)).fetchone()
        if not row:
            return False
        fids = [r['id'] for r in conn.execute(
            'SELECT id FROM formations WHERE lettre_id=?', (lettre_id,)).fetchall()]
        # Une seule dorra enregistrée définitivement suffit à bloquer le فسخ.
        for fid in fids:
            m = conn.execute(
                'SELECT finalise_at FROM memo_formations WHERE formation_id=?',
                (fid,)).fetchone()
            if m and m['finalise_at']:
                return False
        liberer_numeros_programme(conn, lettre_id)
        for fid in fids:
            conn.execute('DELETE FROM programme_formations WHERE formation_id=?', (fid,))
            conn.execute('DELETE FROM programme_jours      WHERE formation_id=?', (fid,))
            conn.execute('DELETE FROM bataqa_formations   WHERE formation_id=?', (fid,))
            conn.execute('DELETE FROM memo_formations      WHERE formation_id=?', (fid,))
        conn.execute('DELETE FROM participants     WHERE lettre_id=?', (lettre_id,))
        conn.execute('DELETE FROM formation_etapes WHERE lettre_id=?', (lettre_id,))
        conn.execute('DELETE FROM formations       WHERE lettre_id=?', (lettre_id,))
        # Les مراسلات المديرين الجهويّين disparaissent avec le برنامج ; leurs
        # أعداد sont déjà revenus au pool par liberer_numeros_programme.
        conn.execute('DELETE FROM dr_lettres       WHERE lettre_id=?', (lettre_id,))
        conn.execute('DELETE FROM lettres          WHERE id=?',        (lettre_id,))
        conn.commit()
        return True
    except Exception as e:
        _log.exception(f"delete_programme_inacheve error: {e}")
        return False
    finally:
        conn.close()


# ─── Lettres list ─────────────────────────────────────────────────────────────

def get_lettres_list():
    """All letters (both categories) with formation count."""
    conn = get_connection()
    rows = conn.execute('''
        SELECT l.*, COUNT(f.id) as nb_formations
        FROM lettres l
        LEFT JOIN formations f ON f.lettre_id = l.id
        GROUP BY l.id
        ORDER BY l.id DESC
    ''').fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_lettre_detail(lettre_id):
    conn = get_connection()
    lettre = conn.execute('SELECT * FROM lettres WHERE id = ?', (lettre_id,)).fetchone()
    formations = conn.execute('SELECT * FROM formations WHERE lettre_id = ? ORDER BY ordre', (lettre_id,)).fetchall()
    conn.close()
    if not lettre:
        return None
    return {'lettre': dict(lettre), 'formations': [dict(f) for f in formations]}

def save_programme(type_lettre, mois, annee, formations, nom_resp, titre_resp):
    """Save a programme WITHOUT incrementing the counter (no ref yet). Returns lettre_id."""
    conn = get_connection()
    cur = conn.execute('''
        INSERT INTO lettres (type, numero, ref_complet, mois, annee, nom_responsable, titre_responsable)
        VALUES (?, 0, '', ?, ?, ?, ?)
    ''', (type_lettre, mois, annee, nom_resp, titre_resp))
    lettre_id = cur.lastrowid
    from datetime import datetime as _dt
    maintenant = _dt.now().strftime('%Y-%m-%d %H:%M:%S')
    for i, f in enumerate(formations, 1):
        conn.execute('''
            INSERT INTO formations (lettre_id, ordre, titre, grade, nom_formateur,
                                    lieu_travail, date_formation, periode, lieu_formation,
                                    date_creation, date_fin,
                                    mode_formation, niveau_formation, cooperation, hors_plan)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (lettre_id, i, f.get('titre',''), f.get('grade',''), f.get('nom_formateur',''),
              f.get('lieu_travail',''), f.get('date_formation',''), f.get('periode',''),
              f.get('lieu_formation',''), maintenant, _date_fin_de(f), *_classif_de(f)))
    conn.commit()
    conn.close()
    return lettre_id

def update_programme(lettre_id, type_lettre, mois, annee, formations):
    """Update an already saved programme (type included). Refuses if locked."""
    conn = get_connection()
    row = conn.execute('SELECT verrouille FROM lettres WHERE id=?', (lettre_id,)).fetchone()
    if row and row['verrouille']:
        conn.close()
        return False  # locked — no modification allowed
    conn.execute('UPDATE lettres SET type=?, mois=?, annee=? WHERE id=?',
                 (type_lettre, mois, annee, lettre_id))
    # L'autosauvegarde réécrit les dorrat toutes les 3 s : la date de création
    # doit survivre à ces réécritures, sinon elle se remettrait sans cesse à
    # « maintenant ». On la conserve par rang.
    from datetime import datetime as _dt
    maintenant = _dt.now().strftime('%Y-%m-%d %H:%M:%S')
    _lignes = [dict(r) for r in conn.execute(
        'SELECT ordre, date_creation, mode_formation, niveau_formation, cooperation, hors_plan '
        'FROM formations WHERE lettre_id=?', (lettre_id,)).fetchall()]
    anciennes = {r['ordre']: r['date_creation'] for r in _lignes}
    # V3 — تصنيف : une clé absente du payload garde la valeur enregistrée.
    anciens_classif = {r['ordre']: r for r in _lignes}
    conn.execute('DELETE FROM formations WHERE lettre_id=?', (lettre_id,))
    for i, f in enumerate(formations, 1):
        conn.execute('''
            INSERT INTO formations (lettre_id, ordre, titre, grade, nom_formateur,
                                    lieu_travail, date_formation, periode, lieu_formation,
                                    date_creation, date_fin,
                                    mode_formation, niveau_formation, cooperation, hors_plan)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (lettre_id, i, f.get('titre',''), f.get('grade',''), f.get('nom_formateur',''),
              f.get('lieu_travail',''), f.get('date_formation',''), f.get('periode',''),
              f.get('lieu_formation',''), anciennes.get(i) or maintenant, _date_fin_de(f),
              *_classif_de(f, anciens_classif.get(i))))
    conn.commit()
    conn.close()
    return True

def finaliser_lettre(lettre_id, type_lettre):
    """Assign a ref number to a saved programme (legacy — prefer verrouiller_lettre)."""
    conn = get_connection()
    try:
        ref, numero = _attribuer_numero(conn, type_lettre, 'programme', lettre_id, '')
        conn.execute('UPDATE lettres SET ref_complet=?, numero=?, annee_sejel=? WHERE id=?',
                     (ref, numero, _exercice.annee_active(conn), lettre_id))
        conn.commit()
        return ref, numero
    finally:
        conn.close()


def annee_admise(annee_document, annee_sejel, est_libre=False):
    """v1.7 — Un document peut-il prendre son عدد dans le سجلّ ouvert ?

    • مراسلة حرّة : seulement si elle est de l'année du سجلّ.
    • برنامج تكوين : l'année du سجلّ, OU l'année suivante — le برنامج de
      جانفي s'envoie en ديسمبر et prend son عدد dans le سجلّ de ديسمبر
      (le عدد suit la date d'émission, non le mois annoncé).
    Un برنامج d'une année ÉCOULÉE n'est jamais admis."""
    try:
        a, s = int(annee_document), int(annee_sejel)
    except (TypeError, ValueError):
        return False
    if est_libre:
        return a == s
    return a in (s, s + 1)


def verrouiller_lettre(lettre_id, type_lettre):
    """Assign ref using the correct type counter and permanently lock the letter.
    If already locked, returns existing ref without re-incrementing.

    v1.4e : la connexion est TOUJOURS refermée et la transaction annulée en
    cas d'erreur — une exception laissait la base verrouillée (« database is
    locked ») pour toutes les opérations suivantes."""
    if type_lettre not in ('interne', 'externe'):
        return None, None
    conn = get_connection()
    try:
        row = conn.execute(
            'SELECT verrouille, ref_complet, numero, categorie, mois, annee, objet '
            'FROM lettres WHERE id=?', (lettre_id,)
        ).fetchone()
        if not row:
            return None, None
        if row['verrouille']:
            return row['ref_complet'], row['numero']
        # Dernière garde (les routes l'annoncent avec un message clair).
        # v1.7 : le عدد vient du سجلّ OUVERT le jour de l'émission. Un برنامج
        # de l'année suivante (برنامج جانفي أُرسل في ديسمبر) y est admis ; une
        # مراسلة حرّة, elle, reste de l'année de son سجلّ.
        try:
            if row['annee'] and not annee_admise(
                    int(row['annee']), _exercice.annee_active(conn),
                    (row['categorie'] or 'programme') == 'libre'):
                _log.warning('verrouiller_lettre #%s : année %s ≠ سجلّ %s', lettre_id,
                             row['annee'], _exercice.annee_active(conn))
                return None, None
        except (TypeError, ValueError):
            return None, None

        # Numéro attribué atomiquement pour ce type de مراسلة, et inscrit au registre
        est_libre = (row['categorie'] or 'programme') == 'libre'
        _objet = (row['objet'] or '') if est_libre else \
                 f"برنامج التكوين لشهر {row['mois'] or ''} {row['annee'] or ''}".strip()
        ref, numero = _attribuer_numero(conn, type_lettre,
                                        'libre' if est_libre else 'programme',
                                        lettre_id, _objet,
                                        'definitif' if est_libre else 'provisoire')

        conn.execute(
            'UPDATE lettres SET ref_complet=?, numero=?, type=?, verrouille=1, '
            '                   annee_sejel=? WHERE id=?',
            (ref, numero, type_lettre, _exercice.annee_active(conn), lettre_id)
        )
        # ── تجميد هويّة الوثيقة ───────────────────────────────────────────
        # Le عدد et l'identité naissent dans la MÊME transaction. Une مراسلة
        # partie porte le nom du مركز et de son responsable tels qu'ils étaient
        # ce jour-là ; changer de responsable en mars ne doit pas réécrire la
        # مراسلة de janvier.
        try:
            from core import gel as _gel
            _cfg = {r['cle']: r['valeur']
                    for r in conn.execute('SELECT cle, valeur FROM config').fetchall()}
            _gel.figer(conn, lettre_id, _cfg)
        except Exception as e:                                # pragma: no cover
            _log.exception(f'gel de l\'identité #{lettre_id}: {e}')
        conn.commit()
        return ref, numero
    except Exception:
        conn.rollback()
        _log.exception('verrouiller_lettre #%s', lettre_id)
        raise
    finally:
        conn.close()


# ─── Étape 2 : مراسلة المدير الجهوي ──────────────────────────────────────────

def get_dr_lettres(lettre_id):
    """Les مراسلات المديرين الجهويّين déjà tirées pour ce برنامج, en ordre d'عدد.

    Rend une liste de dicts : `destination`, `type`, `numero`, `ref_complet`,
    `confirmed_at`. Vide tant qu'aucune n'a été tirée."""
    conn = get_connection()
    try:
        return [dict(r) for r in conn.execute(
            'SELECT id, destination, type, numero, ref_complet, confirmed_at '
            'FROM dr_lettres WHERE lettre_id=? ORDER BY numero',
            (lettre_id,)).fetchall()]
    finally:
        conn.close()


def attribuer_numero_dr(lettre_id, type_lettre, destination=''):
    """Numéro d'enregistrement d'UNE مراسلة مدير جهويّ (الخطوة 2).

    Une دورة réunit souvent des أعوان venus de plusieurs directions
    régionales, et chacun de leurs directeurs reçoit sa propre مراسلة. Ces
    مراسلات sont des correspondances officielles distinctes : **chacune tire
    son عدد de sa série**. Trois directeurs, ce sont trois أعداد et trois
    سطور au سجلّ — jamais un seul عدد partagé.

    La destination est donc la clé : deux مراسلات du même برنامج vers deux
    directions différentes sont deux documents ; deux تحرير vers la MÊME
    direction sont un seul document réimprimé, et le second ne consomme aucun
    عدد. C'est cette distinction qui protège le compteur.

    Si l'agent la déclare خارجية, le عدد vient de la suite des مراسلات
    خارجية — jamais de celle des داخلية.

    Retour : (ref, numero, type, deja_attribue). (None, None, None, False) si
    la مراسلة du برنامج n'existe pas ou n'est pas encore confirmée."""
    from datetime import datetime as _dt
    if type_lettre not in ('interne', 'externe'):
        type_lettre = 'externe'          # défaut métier de l'étape 2
    destination = (destination or '').strip()
    conn = get_connection()
    try:
        row = conn.execute(
            'SELECT verrouille, mois, annee, scelle_at FROM lettres WHERE id=?',
            (lettre_id,)).fetchone()
        if not row:
            return None, None, None, False
        # Destination normalisée : « …بالقصرين » et « …بالقصرين. » sont la
        # même direction — un point final ne doit pas coûter un عدد.
        destination = ' '.join(destination.split()).rstrip(' .،')

        # Cette direction a-t-elle déjà la sienne ? Alors on rend le عدد tel
        # quel : réimprimer ne renumérote pas et ne consomme rien.
        deja = conn.execute(
            'SELECT type, numero, ref_complet FROM dr_lettres '
            'WHERE lettre_id=? AND destination=?',
            (lettre_id, destination)).fetchone()
        if deja:
            return deja['ref_complet'], deja['numero'], deja['type'], True

        # Pas de عدد tant que le برنامج lui-même n'est pas confirmé.
        if not row['verrouille']:
            return None, None, None, False
        # Programme scellé (مصادقة نهائيّة) : plus aucun nouveau عدد — sinon le
        # سجلّ recevrait une ligne que la مصادقة n'a jamais vue.
        if row['scelle_at']:
            return None, None, None, False

        objet = (f"مراسلة المدير الجهوي — برنامج التكوين لشهر "
                 f"{row['mois'] or ''} {row['annee'] or ''}"
                 + (f" — {destination}" if destination else '')).strip()
        ref, numero = _attribuer_numero(conn, type_lettre, 'directeur', lettre_id,
                                        objet, 'provisoire')
        horodatage = _dt.now().strftime('%Y-%m-%d %H:%M:%S')
        conn.execute(
            'INSERT INTO dr_lettres (lettre_id, destination, type, numero, '
            '                        ref_complet, confirmed_at, annee) '
            'VALUES (?,?,?,?,?,?,?)',
            (lettre_id, destination, type_lettre, numero, ref, horodatage,
             _exercice.annee_active(conn)))
        # Les colonnes `lettres.dr_*` gardent la PREMIÈRE مراسلة tirée : une
        # base relue par une version antérieure y retrouve un état cohérent.
        conn.execute(
            'UPDATE lettres SET dr_type=?, dr_numero=?, dr_ref_complet=?, '
            '                   dr_destination=?, dr_confirmed_at=?, dr_annee_sejel=? '
            'WHERE id=? AND COALESCE(dr_numero,0)=0',
            (type_lettre, numero, ref, destination, horodatage,
             _exercice.annee_active(conn), lettre_id))
        conn.commit()
        return ref, numero, type_lettre, False
    finally:
        conn.close()


def annuler_dr_lettre(dr_id):
    """فسخ مراسلة مدير جهوي واحدة — son عدد revient au pool.

    Correctif du défaut trouvé à l'usage : à l'étape 2, tirer une مراسلة مدير
    جهوي consomme un عدد ; la retirer ne le rendait pas. Effacer la ligne à
    l'écran laissait le عدد inscrit au سجلّ pour une مراسلة qui n'existait
    plus. Ici le عدد est réellement libéré et resservira au prochain tirage de
    sa série.

    Le عدد ne se libère que tant qu'il est 'provisoire'. Dès que le برنامج est
    entièrement enregistré (toutes ses دورات finalisées), il devient
    'definitif' : la مراسلة est un acte parti et ne se fsakhe plus.

    Renvoie (ok, ref) en cas de succès, (False, message) sinon."""
    conn = get_connection()
    try:
        d = conn.execute(
            'SELECT lettre_id, destination, type, numero, ref_complet, annee '
            'FROM dr_lettres WHERE id=?', (dr_id,)).fetchone()
        if not d:
            return False, 'المراسلة غير موجودة'
        annee = d['annee'] if d['annee'] is not None else _exercice.annee_active(conn)
        reg = conn.execute(
            "SELECT statut FROM registre WHERE annee=? AND type=? AND numero=? "
            "AND source='directeur' AND source_id=?",
            (annee, d['type'], d['numero'], d['lettre_id'])).fetchone()
        if reg and reg['statut'] == 'definitif':
            return False, ('المراسلة أصبحت نهائيّة بعد تسجيل كامل البرنامج، '
                           'ولا يمكن فسخها.')
        _liberer_numero(conn, d['type'], d['numero'],
                        f'فسخ مراسلة مدير جهوي #{dr_id}', annee=annee)
        conn.execute('DELETE FROM dr_lettres WHERE id=?', (dr_id,))
        # Nettoyage du fallback lettres.dr_* s'il pointait sur CETTE مراسلة —
        # sinon une base relue par une version antérieure ressusciterait le عدد.
        conn.execute(
            "UPDATE lettres SET dr_type='', dr_numero=0, dr_ref_complet='', "
            "dr_destination='', dr_confirmed_at=NULL "
            'WHERE id=? AND dr_numero=?', (d['lettre_id'], d['numero']))
        conn.commit()
        return True, d['ref_complet']
    except Exception as e:
        _log.exception(f'annuler_dr_lettre error: {e}')
        return False, str(e)
    finally:
        conn.close()


# ─── مراجعة نهائيّة : الدورة، ثمّ البرنامج كامل ──────────────────────────────

def revue_dorra(formation_id):
    """مراجعة نهائيّة لدورة واحدة, avant « تسجيل الدورة في المنظومة ».

    Rassemble, pour que l'agent confirme en connaissance de cause :
      • les documents produits (مشاركون / بطاقة / برنامج / مذكّرة) et lesquels
        sont prêts ;
      • le عدد de la مذكّرة — l'unique عدد qu'une دورة consomme ;
      • si le نصّ de la مذكّرة a été retouché à la main ;
      • ce qui manque encore, le cas échéant.

    Renvoie None si la دورة n'existe pas."""
    conn = get_connection()
    try:
        f = conn.execute(
            'SELECT id, lettre_id, titre, date_formation, date_fin, lieu_formation, '
            '       nom_formateur FROM formations WHERE id=?',
            (formation_id,)).fetchone()
        if not f:
            return None
        nb = conn.execute('SELECT COUNT(*) FROM participants WHERE formation_id=?',
                          (formation_id,)).fetchone()[0]

        def _conf(table):
            try:
                r = conn.execute(
                    f'SELECT confirmed_at FROM {table} WHERE formation_id=?',
                    (formation_id,)).fetchone()
                return bool(r and r['confirmed_at'])
            except Exception:
                _log.warning('_conf : exception ignorée', exc_info=True)
                return False

        bataqa    = _conf('bataqa_formations')
        programme = _conf('programme_formations')
        m = conn.execute(
            'SELECT confirmed_at, finalise_at, contenu_manuel '
            'FROM memo_formations WHERE formation_id=?', (formation_id,)).fetchone()
        memo_ok  = bool(m and m['confirmed_at'])
        finalise = bool(m and m['finalise_at'])
        # عدد de la مذكّرة : le registre fait foi.
        memo_reg = conn.execute(
            "SELECT numero, ref_complet, statut FROM registre "
            "WHERE source='memo' AND source_id=?", (formation_id,)).fetchone()

        documents = [
            {'cle': 'participants', 'label': 'قائمة المشاركين', 'ok': nb > 0,
             'detail': f'{nb} مشارك'},
            {'cle': 'bataqa', 'label': 'البطاقة البيداغوجية', 'ok': bataqa, 'detail': ''},
            {'cle': 'programme', 'label': 'برنامج الدورة', 'ok': programme,
             # V2 : nombre de jours d'une دورة متعدّدة الأيّام
             'detail': (f"{_jours.nombre_de_jours(f['date_formation'], f['date_fin'])} أيّام"
                        if _jours.est_multi_jours(f['date_formation'], f['date_fin']) else '')},
            {'cle': 'memo', 'label': 'المذكّرة الداخليّة', 'ok': memo_ok,
             'detail': (memo_reg['ref_complet'] if memo_reg else '')},
        ]
        manquant = [d['label'] for d in documents if not d['ok']]
        return {
            'formation_id':   formation_id,
            'lettre_id':      f['lettre_id'],
            'titre':          f['titre'] or '',
            'date_formation': f['date_formation'] or '',
            'date_fin':       f['date_fin'] or '',
            'lieu_formation': f['lieu_formation'] or '',
            'nom_formateur':  f['nom_formateur'] or '',
            'nb_participants': nb,
            'documents':      documents,
            'memo_numero':    (memo_reg['numero'] if memo_reg else None),
            'memo_ref':       (memo_reg['ref_complet'] if memo_reg else ''),
            'memo_manuel':    bool(m and m['contenu_manuel']),
            'finalise':       finalise,
            'complet':        not manquant,
            'manquant':       manquant,
        }
    finally:
        conn.close()


def verifier_integrite_programme(lettre_id):
    """المراجعات اللازمة لضمان سلامة كلّ المعطيات وترقيم المراسلات.

    Passe le برنامج au crible avant sa مصادقة نهائيّة et renvoie la liste des
    problèmes trouvés (liste vide = tout est sain) :
      • une دورة à qui manque un document, ou qui n'est pas encore enregistrée ;
      • un عدد inscrit au سجلّ sans document vivant en face — l'orphelin que
        produisait l'ancien défaut de l'étape 2 ;
      • incohérence du عدد de la مراسلة principale."""
    conn = get_connection()
    try:
        l = conn.execute('SELECT id, verrouille, numero FROM lettres WHERE id=?',
                         (lettre_id,)).fetchone()
        if not l:
            return ['البرنامج غير موجود.']
        problemes = []
        if not l['verrouille']:
            problemes.append('البرنامج لم يُؤكَّد بعد (المراسلة الرئيسيّة بلا عدد).')

        formations = conn.execute(
            'SELECT id, titre FROM formations WHERE lettre_id=? ORDER BY ordre, id',
            (lettre_id,)).fetchall()
        if not formations:
            problemes.append('البرنامج بلا دورات.')

        def _conf(table, fid):
            try:
                r = conn.execute(
                    f'SELECT confirmed_at FROM {table} WHERE formation_id=?',
                    (fid,)).fetchone()
                return bool(r and r['confirmed_at'])
            except Exception:
                _log.warning('_conf : exception ignorée', exc_info=True)
                return False

        for f in formations:
            fid   = f['id']
            titre = f['titre'] or f'#{fid}'
            nb = conn.execute('SELECT COUNT(*) FROM participants WHERE formation_id=?',
                              (fid,)).fetchone()[0]
            m = conn.execute(
                'SELECT confirmed_at, finalise_at FROM memo_formations WHERE formation_id=?',
                (fid,)).fetchone()
            if nb == 0:
                problemes.append(f'الدورة «{titre}»: لا مشاركون.')
            if not _conf('bataqa_formations', fid):
                problemes.append(f'الدورة «{titre}»: البطاقة البيداغوجية غير مؤكَّدة.')
            if not _conf('programme_formations', fid):
                problemes.append(f'الدورة «{titre}»: برنامج الدورة غير مؤكَّد.')
            if not (m and m['confirmed_at']):
                problemes.append(f'الدورة «{titre}»: المذكّرة الداخليّة غير مؤكَّدة.')
            elif not m['finalise_at']:
                problemes.append(f'الدورة «{titre}»: لم تُسجَّل نهائيّا في المنظومة.')

        # ── ترقيم المراسلات : chaque عدد 'directeur' du سجلّ a-t-il encore sa
        # مراسلة en face ? Un عدد sans ligne dr_lettres est l'orphelin du défaut
        # corrigé — on le signale pour qu'il soit fsakhé et rendu au rرصيد.
        for r in conn.execute(
                "SELECT numero, ref_complet, type FROM registre "
                "WHERE source='directeur' AND source_id=?", (lettre_id,)).fetchall():
            vivante = conn.execute(
                'SELECT 1 FROM dr_lettres WHERE lettre_id=? AND type=? AND numero=?',
                (lettre_id, r['type'], r['numero'])).fetchone()
            if not vivante:
                problemes.append(
                    f'العدد {r["ref_complet"]} مُسجَّل لمراسلة مدير جهوي لم تعد موجودة — '
                    f'يجب فسخه ليعود إلى الرصيد.')
        return problemes
    finally:
        conn.close()


def revue_programme(lettre_id):
    """مراجعة نهائيّة للبرنامج كامل, avant sa مصادقة.

    Réunit tout ce que le برنامج a produit — sa مراسلة principale, ses دورات et
    l'état de chacune, ses مراسلات مديرين جهويّين, et TOUS les أعداد qu'il a
    consommés au سجلّ — puis y joint le verdict de سلامة
    (`verifier_integrite_programme`). Renvoie None si le برنامج n'existe pas."""
    conn = get_connection()
    try:
        l = conn.execute(
            'SELECT id, ref_complet, numero, type, mois, annee, verrouille, scelle_at '
            'FROM lettres WHERE id=?', (lettre_id,)).fetchone()
        if not l:
            return None
        formations = conn.execute(
            'SELECT id, titre, date_formation FROM formations '
            'WHERE lettre_id=? ORDER BY ordre, id', (lettre_id,)).fetchall()
        dorrat = []
        tout_finalise = bool(formations)
        for f in formations:
            m = conn.execute(
                'SELECT finalise_at, confirmed_at FROM memo_formations WHERE formation_id=?',
                (f['id'],)).fetchone()
            fin = bool(m and m['finalise_at'])
            if not fin:
                tout_finalise = False
            memo_reg = conn.execute(
                "SELECT ref_complet FROM registre WHERE source='memo' AND source_id=?",
                (f['id'],)).fetchone()
            dorrat.append({
                'formation_id':   f['id'],
                'titre':          f['titre'] or '',
                'date_formation': f['date_formation'] or '',
                'finalise':       fin,
                'memo_ref':       (memo_reg['ref_complet'] if memo_reg else ''),
            })
        dr = [dict(r) for r in conn.execute(
            'SELECT id, destination, type, numero, ref_complet FROM dr_lettres '
            'WHERE lettre_id=? ORDER BY numero', (lettre_id,)).fetchall()]
        registre = [dict(r) for r in conn.execute(
            "SELECT type, numero, ref_complet, source, statut FROM registre "
            "WHERE (source IN ('programme','directeur') AND source_id=?) "
            "   OR (source='memo' AND source_id IN "
            "       (SELECT id FROM formations WHERE lettre_id=?)) "
            "ORDER BY type, numero", (lettre_id, lettre_id)).fetchall()]
    finally:
        conn.close()

    problemes = verifier_integrite_programme(lettre_id)
    return {
        'lettre_id':     lettre_id,
        'ref':           l['ref_complet'] or '',
        'numero':        l['numero'],
        'type':          l['type'],
        'mois':          l['mois'] or '',
        'annee':         l['annee'],
        'verrouille':    bool(l['verrouille']),
        'scelle':        bool(l['scelle_at']),
        'scelle_at':     l['scelle_at'] or '',
        'dorrat':        dorrat,
        'dr_lettres':    dr,
        'registre':      registre,
        'tout_finalise': tout_finalise,
        'problemes':     problemes,
        'coherent':      not problemes,
    }


def sceller_programme(lettre_id):
    """المصادقة النهائيّة على البرنامج.

    Après que `verifier_integrite_programme` n'a plus rien à redire — chaque
    دورة enregistrée, chaque عدد du سجلّ en face d'un document vivant — le
    برنامج se scelle. La مصادقة atteste précisément qu'il n'y a aucun problème :
    on la refuse tant qu'il en reste un, en le nommant.

    Idempotente : un برنامج déjà scellé renvoie son horodatage sans rien
    changer. Renvoie (True, horodatage) ou (False, liste_problemes)."""
    problemes = verifier_integrite_programme(lettre_id)
    if problemes:
        return False, problemes
    from datetime import datetime as _dt
    conn = get_connection()
    try:
        row = conn.execute('SELECT scelle_at FROM lettres WHERE id=?',
                           (lettre_id,)).fetchone()
        if not row:
            return False, ['البرنامج غير موجود.']
        if row['scelle_at']:
            return True, row['scelle_at']
        now = _dt.now().strftime('%Y-%m-%d %H:%M:%S')
        conn.execute('UPDATE lettres SET scelle_at=? WHERE id=?', (now, lettre_id))
        # Sûreté : sceller rend définitifs tous les أعداد du برنامج (ils le sont
        # déjà si toutes les دورات sont enregistrées, mais on ne s'y fie pas).
        confirmer_numeros_programme(conn, lettre_id)
        conn.commit()
        return True, now
    except Exception as e:
        _log.warning('sceller_programme : exception ignorée', exc_info=True)
        return False, [str(e)]
    finally:
        conn.close()


def programme_est_scelle(lettre_id):
    """True si le برنامج a reçu sa مصادقة نهائيّة."""
    conn = get_connection()
    try:
        r = conn.execute('SELECT scelle_at FROM lettres WHERE id=?',
                         (lettre_id,)).fetchone()
        return bool(r and r['scelle_at'])
    finally:
        conn.close()


# ─── Lettres libres ──────────────────────────────────────────────────────────

def save_lettre_libre(type_lettre, mois, annee, destinataire, objet, corps,
                      nom_resp, titre_resp, msahib='', moujah_lahom=''):
    """Save a free letter WITHOUT incrementing the counter. Returns lettre_id."""
    conn = get_connection()
    cur = conn.execute('''
        INSERT INTO lettres (type, numero, ref_complet, mois, annee,
                             categorie, destinataire, objet, corps,
                             nom_responsable, titre_responsable,
                             msahib, moujah_lahom)
        VALUES (?, 0, '', ?, ?, 'libre', ?, ?, ?, ?, ?, ?, ?)
    ''', (type_lettre, mois, annee, destinataire, objet, corps,
          nom_resp, titre_resp, msahib or '', moujah_lahom or ''))
    lettre_id = cur.lastrowid
    conn.commit()
    conn.close()
    return lettre_id

def update_lettre_libre(lettre_id, type_lettre, mois, annee, destinataire, objet, corps,
                        msahib='', moujah_lahom=''):
    """Update an already saved free letter (type included). Refuses if locked."""
    conn = get_connection()
    row = conn.execute('SELECT verrouille FROM lettres WHERE id=?', (lettre_id,)).fetchone()
    if row and row['verrouille']:
        conn.close()
        return False  # locked — no modification allowed
    conn.execute('''
        UPDATE lettres SET type=?, mois=?, annee=?, destinataire=?, objet=?, corps=?,
                           msahib=?, moujah_lahom=?
        WHERE id=?
    ''', (type_lettre, mois, annee, destinataire, objet, corps,
          msahib or '', moujah_lahom or '', lettre_id))
    conn.commit()
    conn.close()
    return True

# ─── Progression étape par étape d'une dorra ─────────────────────────────────
#
# Une دورة se remplit dans l'ordre, et on ne passe à une étape qu'une fois la
# précédente achevée. L'étape 2 (مراسلة المدير الجهوي) est facultative et porte
# sur la مراسلة, pas sur la dorra : elle ne bloque rien.
#
#   3. قائمة المشاركين   → au moins UN participant
#   4. البطاقة البيداغوجية → enregistrée ou confirmée
#   5. برنامج الدورة      → au moins un صف كامل confirmé
#   6. المذكّرة الداخلية   → confirmée, puis تسجيل نهائي

ETAPES_DORRA = ('participants', 'bataqa', 'programme', 'memo')

#  Étape → étape qui doit être achevée avant d'y toucher.
PREALABLE_ETAPE = {
    'participants': None,
    'bataqa':       'participants',
    'programme':    'bataqa',
    'memo':         'programme',
}

LIBELLE_ETAPE = {
    'participants': 'قائمة المشاركين (الخطوة 3)',
    'bataqa':       'البطاقة البيداغوجية (الخطوة 4)',
    'programme':    'برنامج الدورة (الخطوة 5)',
    'memo':         'المذكّرة الداخلية (الخطوة 6)',
}


def etat_dorra(formation_id):
    """État d'avancement d'une dorra, étape par étape.

    Renvoie un dict :
      participants / bataqa / programme / memo : bool (étape achevée)
      nb_participants : int
      finalise        : bool (تسجيل نهائي)
      ouvertes        : liste des étapes que l'agent a le droit d'ouvrir
      prochaine       : première étape non achevée, ou None
    """
    conn = get_connection()
    try:
        nb = conn.execute(
            'SELECT COUNT(*) FROM participants WHERE formation_id=?',
            (formation_id,)).fetchone()[0]

        def _confirme(table):
            try:
                r = conn.execute(
                    f'SELECT confirmed_at FROM {table} WHERE formation_id=?',
                    (formation_id,)).fetchone()
                return bool(r and r['confirmed_at'])
            except Exception:
                _log.warning('_confirme : exception ignorée', exc_info=True)
                return False

        bataqa    = _confirme('bataqa_formations')
        programme = _confirme('programme_formations')
        memo      = _confirme('memo_formations')
        r = conn.execute(
            'SELECT finalise_at FROM memo_formations WHERE formation_id=?',
            (formation_id,)).fetchone()
        finalise = bool(r and r['finalise_at'])
    finally:
        conn.close()

    etat = {
        'formation_id':    formation_id,
        'nb_participants': nb,
        'participants':    nb > 0,
        'bataqa':          bataqa,
        'programme':       programme,
        'memo':            memo,
        'finalise':        finalise,
    }
    ouvertes, prochaine = [], None
    for e in ETAPES_DORRA:
        prealable = PREALABLE_ETAPE[e]
        if prealable is None or etat[prealable]:
            ouvertes.append(e)
            if prochaine is None and not etat[e]:
                prochaine = e
        else:
            break
    etat['ouvertes'] = ouvertes
    etat['prochaine'] = prochaine
    return etat


def etape_autorisee(formation_id, etape):
    """(autorisee, message). Garde serveur : refuse d'ouvrir une étape dont la
    précédente n'est pas achevée."""
    prealable = PREALABLE_ETAPE.get(etape)
    if prealable is None:
        return True, ''
    etat = etat_dorra(formation_id)
    if etat[prealable]:
        return True, ''
    return False, f'يجب أوّلا استكمال {LIBELLE_ETAPE[prealable]}'


def etats_dorrat(lettre_id):
    """État de toutes les dorrat d'un programme, indexé par formation_id."""
    conn = get_connection()
    try:
        fids = [r['id'] for r in conn.execute(
            'SELECT id FROM formations WHERE lettre_id=? ORDER BY ordre, id',
            (lettre_id,)).fetchall()]
    finally:
        conn.close()
    return {fid: etat_dorra(fid) for fid in fids}


def _candidates_autour(conn, dates, exclure_lettre=None):
    """V2 — دورات dont un jour peut tomber à l'une de ces dates : celles qui
    commencent à ces dates ET les دورات متعدّدة الأيّام commencées jusqu'à
    trois semaines plus tôt. Le tri fin se fait ensuite sur leurs jours."""
    from datetime import timedelta
    ds = sorted(d for d in (_jours.lire(x) for x in dates) if d)
    if not ds:
        return []
    bas = (ds[0] - timedelta(days=21)).isoformat()
    sql = ('SELECT f.id, f.titre, f.date_formation, f.date_fin, f.periode, f.lieu_formation, '
           '       f.nom_formateur, l.id AS lettre_id, l.ref_complet, l.mois, l.annee '
           'FROM formations f JOIN lettres l ON l.id = f.lettre_id '
           'WHERE (substr(f.date_formation, 1, 10) IN (%s)) '
           "   OR (COALESCE(f.date_fin, '') != '' AND substr(f.date_formation, 1, 10) >= ? "
           '       AND substr(f.date_formation, 1, 10) <= ?)'
           % ','.join('?' * len(ds)))
    params = [d.isoformat() for d in ds] + [bas, ds[-1].isoformat()]
    sql = f'SELECT * FROM ({sql})'
    if exclure_lettre:
        sql += ' WHERE lettre_id <> ?'
        params.append(exclure_lettre)
    voulus = {d.isoformat() for d in ds}
    res = []
    for r in conn.execute(sql + ' ORDER BY id', params).fetchall():
        r = dict(r)
        if set(_jours.jours_de_la_dorra(r['date_formation'], r['date_fin'])) & voulus:
            res.append(r)
    return res


def dorrat_meme_jour(date_formation, exclure_lettre=None):
    """Dorrat déjà enregistrées le même JOUR. Sert à alerter l'agent avant qu'il
    ne programme deux دورات à la même date — le centre n'en accueille
    normalement qu'une. On exclut le programme en cours de saisie.
    V2 : une دورة متعدّدة الأيّام compte pour chacun de ses jours."""
    date_formation = (date_formation or '').strip()
    if not date_formation:
        return []
    conn = get_connection()
    try:
        return _candidates_autour(conn, [date_formation], exclure_lettre)
    finally:
        conn.close()


def dorrat_aux_dates(dates, exclure_lettre=None):
    """Toutes les دورات enregistrées à l'une de ces dates, avec la référence
    de leur برنامج — pour la règle « une salle, une دورة à la fois ».
    V2 : y compris les دورات متعدّدة الأيّام dont UN jour tombe à ces dates."""
    dates = sorted({(d or '').strip()[:10] for d in dates or [] if (d or '').strip()})
    if not dates:
        return []
    conn = get_connection()
    try:
        return _candidates_autour(conn, dates, exclure_lettre)
    finally:
        conn.close()


def _occupation(conn, f):
    """V2 — {date ISO : فترة} des jours d'une دورة. Pour une دورة متعدّدة
    الأيّام, la فترة de chaque jour est celle choisie dans son برنامج ; à
    défaut, celle de la دورة."""
    periodes = {r['jour']: (r['periode'] or '') for r in conn.execute(
        'SELECT jour, periode FROM programme_jours WHERE formation_id=?',
        (f['id'],)).fetchall()}
    return {j['date']: j['periode'] for j in _jours.jours_detail(
        f.get('date_formation'), f.get('date_fin'), (f.get('periode') or '').strip(), periodes)}


def dorrat_simultanees(formation_id):
    """La دورة `formation_id` et les AUTRES دورات du même jour dont la فترة
    la recouvre, chacune avec sa قائمة المشاركين.

    V2 : pour une دورة متعدّدة الأيّام, « même jour » = n'importe lequel de
    ses jours (avec la فترة propre à chaque jour) ; le jour et la فترة en
    cause sont joints (`date_commune`, `periode_commune`) pour le message.

    Rend (formation, [autres]) ; (None, []) si la دورة n'existe pas."""
    from core.conflits import periodes_se_chevauchent
    conn = get_connection()
    try:
        f = conn.execute('SELECT id, lettre_id, titre, date_formation, date_fin, periode, '
                         'lieu_formation, nom_formateur FROM formations WHERE id=?',
                         (formation_id,)).fetchone()
        if not f or not (f['date_formation'] or '').strip():
            return (dict(f) if f else None), []
        f = dict(f)
        occ_f = _occupation(conn, f)
        autres = []
        for r in _candidates_autour(conn, list(occ_f)):
            if r['id'] == formation_id:
                continue
            occ_r = _occupation(conn, r)
            commun = None
            for d in sorted(set(occ_f) & set(occ_r)):
                if periodes_se_chevauchent(occ_f[d], occ_r[d]):
                    commun = d
                    break
            if commun is None:
                continue
            if len(occ_f) > 1 or len(occ_r) > 1:
                r['date_commune'] = commun
                r['periode_commune'] = occ_f[commun]
            r['participants'] = [dict(p) for p in conn.execute(
                'SELECT nom_prenom, identifiant_unique FROM participants '
                'WHERE formation_id=?', (r['id'],)).fetchall()]
            autres.append(r)
        return f, autres
    finally:
        conn.close()


def get_lettres_programmes():
    """Return only برامج التكوين (categorie='programme')."""
    conn = get_connection()
    rows = conn.execute('''
        SELECT l.*, COUNT(f.id) as nb_formations
        FROM lettres l
        LEFT JOIN formations f ON f.lettre_id = l.id
        WHERE l.categorie = 'programme' OR l.categorie IS NULL
        GROUP BY l.id
        ORDER BY l.id DESC
    ''').fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_dorrat_avec_memo():
    """Toutes les dorrat pour lesquelles une مذكرة داخلية a été CONFIRMÉE,
    enrichies de tout ce qu'il faut pour l'écran « الإطلاع على البرامج » :
    titre, dates, lieu, formateur, référence de la lettre, participants, et
    l'état (confirmé ou non) de chacune des pièces imprimables."""
    conn = get_connection()
    rows = conn.execute('''
        SELECT f.*, m.confirmed_at AS memo_confirmed_at,
               m.finalise_at AS finalise_at,
               m.ref_complet AS memo_ref,
               l.ref_complet AS lettre_ref, l.mois AS lettre_mois,
               l.annee AS lettre_annee, l.type AS lettre_type,
               mu.etat AS mu_etat
        FROM memo_formations m
        JOIN formations f ON f.id = m.formation_id
        JOIN lettres    l ON l.id = f.lettre_id
        LEFT JOIN mustahaqqat mu ON mu.formation_id = f.id
        WHERE m.confirmed_at IS NOT NULL AND m.confirmed_at != ''
        ORDER BY f.date_formation DESC, f.id DESC
    ''').fetchall()

    dorrat = []
    for r in rows:
        d   = dict(r)
        fid = d['id']
        lid = d['lettre_id']
        d['participants'] = [dict(p) for p in conn.execute(
            'SELECT nom_prenom, grade, identifiant_unique, lieu_travail '
            'FROM participants WHERE lettre_id=? AND formation_id=? ORDER BY ordre',
            (lid, fid)).fetchall()]
        d['nb_participants'] = len(d['participants'])
        for table, cle in (('bataqa_formations', 'bataqa'),
                           ('programme_formations', 'programme'),
                           ('memo_formations', 'memo')):
            try:
                row = conn.execute(
                    f'SELECT confirmed_at FROM {table} WHERE formation_id=?',
                    (fid,)).fetchone()
                d[cle + '_ok'] = bool(row and row['confirmed_at'])
            except Exception:
                _log.warning('get_dorrat_avec_memo : exception ignorée', exc_info=True)
                d[cle + '_ok'] = False
        dorrat.append(d)
    conn.close()
    return dorrat


def get_lettres_libres():
    """Return only مراسلات حرة (categorie='libre')."""
    conn = get_connection()
    rows = conn.execute('''
        SELECT l.*
        FROM lettres l
        WHERE l.categorie = 'libre'
        ORDER BY l.id DESC
    ''').fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ─── Participants ─────────────────────────────────────────────────────────────

def save_participants(lettre_id, formation_id, participants_list):
    """Save participants for a formation (replaces existing). Returns True on success."""
    conn = get_connection()
    try:
        conn.execute('DELETE FROM participants WHERE lettre_id=? AND formation_id=?',
                     (lettre_id, formation_id))
        for i, p in enumerate(participants_list, 1):
            conn.execute('''
                INSERT INTO participants (lettre_id, formation_id, ordre, nom_prenom, grade,
                                         identifiant_unique, lieu_travail, jiha_marjiiya,
                                         sexe, fiaa_omria)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (lettre_id, formation_id, i,
                  p.get('nom_prenom', '').strip(),
                  p.get('grade', '').strip(),
                  p.get('identifiant_unique', '').strip(),
                  p.get('lieu_travail', '').strip(),
                  p.get('jiha_marjiiya', '').strip(),
                  # v1.6 — statistiques seulement ; absents = غير محدّد
                  (p.get('sexe') or '').strip(),
                  (p.get('fiaa_omria') or '').strip()))
        conn.commit()
        return True
    except Exception as e:
        _log.exception(f"save_participants error: {e}")
        return False
    finally:
        conn.close()


def get_participants(lettre_id, formation_id):
    """Get participants list for a formation, ordered by ordre."""
    conn = get_connection()
    rows = conn.execute('''
        SELECT * FROM participants WHERE lettre_id=? AND formation_id=? ORDER BY ordre
    ''', (lettre_id, formation_id)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def save_lettre(type_lettre, ref, numero, mois, annee, formations, nom_resp, titre_resp):
    conn = get_connection()
    cur = conn.execute('''
        INSERT INTO lettres (type, numero, ref_complet, mois, annee, nom_responsable, titre_responsable)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (type_lettre, numero, ref, mois, annee, nom_resp, titre_resp))
    lettre_id = cur.lastrowid
    for i, f in enumerate(formations, 1):
        conn.execute('''
            INSERT INTO formations (lettre_id, ordre, titre, grade, nom_formateur,
                                    lieu_travail, date_formation, periode, lieu_formation,
                                    date_fin,
                                    mode_formation, niveau_formation, cooperation, hors_plan)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (lettre_id, i, f.get('titre',''), f.get('grade',''), f.get('nom_formateur',''),
              f.get('lieu_travail',''), f.get('date_formation',''), f.get('periode',''), f.get('lieu_formation',''),
              _date_fin_de(f), *_classif_de(f)))
    conn.commit()
    conn.close()
    return lettre_id


# ─── Étapes (Step Tracking) ───────────────────────────────────────────────────
# Steps 1–2 are letter-level (formation_id=NULL), steps 3–9 are per-formation.
# Total = 9 steps.

ETAPES_LABELS = {
    1: 'إشعار بتكوين',
    2: 'مراسلة المدير الجهوي',
    3: 'قائمة المشاركين',
    4: 'محضر الانطلاق',
    5: 'تقرير منتصف الدورة',
    6: 'قائمة الحضور',
    7: 'تقييم المشاركين',
    8: 'تقرير الختام',
    9: 'شهادات المشاركين',
}

def valider_etape(lettre_id, formation_id, etape):
    """Mark an etape as validated. formation_id=None for common steps 1-2.
    SQLite treats NULL != NULL in UNIQUE constraints, so we do a manual upsert."""
    from datetime import datetime
    now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    conn = get_connection()
    try:
        fid = formation_id if formation_id else None
        # Check if exists
        if fid is None:
            row = conn.execute(
                'SELECT id FROM formation_etapes WHERE lettre_id=? AND formation_id IS NULL AND etape=?',
                (lettre_id, etape)
            ).fetchone()
        else:
            row = conn.execute(
                'SELECT id FROM formation_etapes WHERE lettre_id=? AND formation_id=? AND etape=?',
                (lettre_id, fid, etape)
            ).fetchone()
        if row:
            conn.execute(
                'UPDATE formation_etapes SET validee=1, date_validation=? WHERE id=?',
                (now_str, row['id'])
            )
        else:
            conn.execute(
                'INSERT INTO formation_etapes (lettre_id, formation_id, etape, validee, date_validation) VALUES (?,?,?,1,?)',
                (lettre_id, fid, etape, now_str)
            )
        conn.commit()
        return True
    except Exception as e:
        _log.exception(f"valider_etape error: {e}")
        return False
    finally:
        conn.close()

def get_etapes_lettre(lettre_id):
    """Get all validated etapes for a letter (common steps 1-2, formation_id=NULL)."""
    conn = get_connection()
    rows = conn.execute('''
        SELECT etape, validee, date_validation FROM formation_etapes
        WHERE lettre_id=? AND formation_id IS NULL
    ''', (lettre_id,)).fetchall()
    conn.close()
    return {r['etape']: {'validee': r['validee'], 'date': r['date_validation']} for r in rows}

def get_etapes_formation(lettre_id, formation_id):
    """Get all validated etapes for a specific formation (steps 3-9)."""
    conn = get_connection()
    rows = conn.execute('''
        SELECT etape, validee, date_validation FROM formation_etapes
        WHERE lettre_id=? AND formation_id=?
    ''', (lettre_id, formation_id)).fetchall()
    conn.close()
    return {r['etape']: {'validee': r['validee'], 'date': r['date_validation']} for r in rows}

def get_formations_en_cours():
    """Return all locked letters with their formations that haven't completed all 9 steps.
    Steps 1-2 are letter-level, steps 3-9 are per-formation.
    Returns list of {lettre, formations: [{formation, etapes_validees, etapes_restantes}]}
    """
    conn = get_connection()
    # Only locked letters (they have a ref and are in execution)
    lettres = conn.execute('''
        SELECT l.*, COUNT(f.id) as nb_formations
        FROM lettres l
        LEFT JOIN formations f ON f.lettre_id = l.id
        WHERE l.verrouille=1 AND (l.categorie='programme' OR l.categorie IS NULL)
        GROUP BY l.id
        ORDER BY l.annee DESC, l.mois DESC, l.id DESC
    ''').fetchall()

    result = []
    for lettre in lettres:
        lid = lettre['id']
        # Check letter-level steps (1-2)
        lettre_etapes = {r['etape']: {'validee': r['validee'], 'date': r['date_validation']}
                         for r in conn.execute(
            'SELECT etape, validee, date_validation FROM formation_etapes WHERE lettre_id=? AND formation_id IS NULL',
            (lid,)
        ).fetchall()}
        lettre_steps_done = sum(1 for e in [1, 2] if lettre_etapes.get(e, {}).get('validee', 0) == 1)

        # Get formations with their per-formation step status
        formations = conn.execute(
            'SELECT * FROM formations WHERE lettre_id=? ORDER BY ordre', (lid,)
        ).fetchall()

        formations_data = []
        all_complete = (lettre_steps_done == 2)  # start optimistic
        for f in formations:
            fid = f['id']
            f_etapes = {r['etape']: {'validee': r['validee'], 'date': r['date_validation']}
                        for r in conn.execute(
                'SELECT etape, validee, date_validation FROM formation_etapes WHERE lettre_id=? AND formation_id=?',
                (lid, fid)
            ).fetchall()}
            f_steps_done = sum(1 for e in range(3, 10) if f_etapes.get(e, {}).get('validee', 0) == 1)
            f_complete = (f_steps_done == 7)  # steps 3-9
            if not f_complete:
                all_complete = False
            formations_data.append({
                'formation': dict(f),
                'etapes_lettre': lettre_etapes,
                'etapes_formation': f_etapes,
                'lettre_steps_done': lettre_steps_done,
                'f_steps_done': f_steps_done,
                'complete': f_complete,
            })

        # Skip letters where everything is complete
        if all_complete and len(formations_data) > 0:
            continue

        result.append({
            'lettre': dict(lettre),
            'lettre_etapes': lettre_etapes,
            'lettre_steps_done': lettre_steps_done,
            'formations': formations_data,
            'all_complete': all_complete,
        })

    conn.close()
    return result


def get_programmes_inacheves():
    """Programmes de formation NON encore achevés — à reprendre depuis la page
    « إستكمال برنامج تكوين ». Sont considérés inachevés :
      • les brouillons non confirmés (verrouille=0) ; ET
      • les programmes confirmés (verrouille=1) dont au moins une dorra n'a pas
        encore été enregistrée définitivement (finalise_at NULL).
    Un programme dont TOUTES les dorrat sont finalisées est achevé → exclu."""
    conn = get_connection()
    try:
        rows = conn.execute('''
            SELECT l.id, l.mois, l.annee, l.type, l.date_creation, l.verrouille,
                   COUNT(f.id) AS nb_formations,
                   GROUP_CONCAT(f.titre, ' | ') AS titres,
                   SUM(CASE WHEN mf.finalise_at IS NOT NULL AND mf.finalise_at != ''
                            THEN 1 ELSE 0 END) AS nb_finalisees,
                   MIN(CASE WHEN mf.finalise_at IS NULL OR mf.finalise_at = ''
                            THEN NULLIF(f.date_formation, '') END) AS date_ouverte
            FROM lettres l
            LEFT JOIN formations f ON f.lettre_id = l.id
            LEFT JOIN memo_formations mf ON mf.formation_id = f.id
            WHERE (l.categorie = 'programme' OR l.categorie IS NULL)
            GROUP BY l.id
            HAVING (COUNT(f.id) = 0) OR (nb_finalisees < COUNT(f.id))
            ORDER BY l.date_creation DESC, l.id DESC
        ''').fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def programme_est_complet(lettre_id):
    """True si le programme a au moins une dorra ET que TOUTES ses dorrat sont
    enregistrées définitivement (finalise_at renseigné)."""
    conn = get_connection()
    try:
        fids = [r['id'] for r in conn.execute(
            'SELECT id FROM formations WHERE lettre_id=?', (lettre_id,)).fetchall()]
        if not fids:
            return False
        for fid in fids:
            r = conn.execute(
                'SELECT finalise_at FROM memo_formations WHERE formation_id=?',
                (fid,)).fetchone()
            if not r or not r['finalise_at']:
                return False
        return True
    finally:
        conn.close()


# ─── Bataqa (البطاقة البيداغوجية) ─────────────────────────────────────────────

def _bataqa_derives(conn, lettre_id, formation_id):
    """(nombre, المستهدفون déduits, المصالح المعنيّة déduites) à partir des
    participants ACTUELLEMENT inscrits dans la dorra."""
    parts = [dict(p) for p in conn.execute(
        'SELECT grade, lieu_travail, jiha_marjiiya FROM participants '
        'WHERE lettre_id=? AND formation_id=? ORDER BY ordre',
        (lettre_id, formation_id)).fetchall()]
    seen = {}
    services_list = []
    for p in parts:
        lt = (p.get('lieu_travail') or '').strip()
        if lt and lt not in seen:
            seen[lt] = True
            services_list.append((lt, (p.get('jiha_marjiiya') or '').strip()))
    # Les مكاتب sont remplacés par leur direction régionale de rattachement et
    # les فرق par leur unité de la garde douanière : inutile de les détailler.
    from core import arabe as _arabe
    from core import identite as _identite
    _cfg_r = {r['cle']: r['valeur'] for r in conn.execute(
        "SELECT cle, valeur FROM config WHERE cle IN ('admin_regionale','unite_garde',"
        "'destination_dr','ville_centre')")}
    _admin_reg = _identite.admin_regionale(_cfg_r)
    _unite_grd = _cfg_r.get('unite_garde', '')
    services_list = _arabe.rattachement_services(
        services_list, _admin_reg, _unite_grd)['entites']
    # « المستهدفون بالتّكوين » déduit des participants réellement inscrits :
    # grades présents + جهات/مصالح de rattachement. '' s'il n'y a personne.
    mustahdafun = _arabe.derive_mustahdafun(
        parts, admin_regionale=_admin_reg, unite_garde=_unite_grd)
    return len(parts), mustahdafun, '\n'.join(services_list)


def bataqa_derives(lettre_id, formation_id):
    """Version autonome de `_bataqa_derives` (ouvre sa connexion)."""
    conn = get_connection()
    try:
        return _bataqa_derives(conn, lettre_id, formation_id)
    finally:
        conn.close()


def actualiser_bataqa_apres_participants(lettre_id, formation_id, anciens):
    """v1.7.1 — Après une modification de la قائمة المشاركين (dorra non encore
    enregistrée définitivement), les champs de l'البطاقة البيداغوجيّة qui
    avaient été ENREGISTRÉS TELS QUE PROPOSÉS (المستهدفون, المصالح المعنيّة)
    suivent les nouveaux participants. Un texte retouché à la main (différent
    de la proposition d'alors) n'est jamais touché.
    `anciens` : bataqa_derives() calculé AVANT l'enregistrement de la liste.
    Rend la liste des champs actualisés."""
    _nb, anc_m, anc_s = anciens
    conn = get_connection()
    try:
        row = conn.execute('SELECT mustahdafun, services FROM bataqa_formations '
                           'WHERE formation_id=?', (formation_id,)).fetchone()
        if not row:
            return []
        _n, nouv_m, nouv_s = _bataqa_derives(conn, lettre_id, formation_id)
        maj = {}
        norm = lambda t: ' '.join(str(t or '').split())
        if norm(row['mustahdafun']) == norm(anc_m) and norm(anc_m) != norm(nouv_m):
            maj['mustahdafun'] = nouv_m
        if norm(row['services']) == norm(anc_s) and norm(anc_s) != norm(nouv_s):
            maj['services'] = nouv_s
        if maj:
            conn.execute('UPDATE bataqa_formations SET '
                         + ', '.join(f'{c}=?' for c in maj) + ' WHERE formation_id=?',
                         (*maj.values(), formation_id))
            conn.commit()
        return sorted(maj)
    except Exception:
        _log.exception('actualiser_bataqa_apres_participants')
        return []
    finally:
        conn.close()


def get_bataqa_data(lettre_id, formation_id):
    """Return merged bataqa data: formation fixed fields + participants count/services
    + saved overrides (or madda defaults when not yet saved)."""
    conn = get_connection()

    # Formation row
    formation = conn.execute(
        'SELECT * FROM formations WHERE id=? AND lettre_id=?', (formation_id, lettre_id)
    ).fetchone()
    if not formation:
        conn.close()
        return None
    formation = dict(formation)

    # Participants : nombre + valeurs déduites (المستهدفون / المصالح المعنيّة)
    nb_participants, mustahdafun_derive, services_default = _bataqa_derives(
        conn, lettre_id, formation_id)

    # Saved bataqa overrides
    bataqa = conn.execute(
        'SELECT * FROM bataqa_formations WHERE formation_id=?', (formation_id,)
    ).fetchone()
    bataqa = dict(bataqa) if bataqa else {}

    # Madda defaults (lookup by titre)
    madda = None
    titre = formation.get('titre', '').strip()
    if titre:
        madda_row = conn.execute(
            'SELECT * FROM mawad WHERE titre=? ORDER BY id DESC LIMIT 1', (titre,)
        ).fetchone()
        if madda_row:
            madda = dict(madda_row)

    conn.close()

    def _f(key, madda_key=None):
        """Return saved override, else madda default, else empty."""
        if key in bataqa and bataqa[key] is not None and bataqa[key] != '':
            return bataqa[key]
        if madda_key and madda:
            return madda.get(madda_key) or ''
        return ''

    return {
        # Fixed (read-only in form)
        'titre':          formation.get('titre', ''),
        'type_formation': formation.get('type_formation') or (madda.get('type_formation') if madda else '') or '',
        'date_formation': formation.get('date_formation', ''),
        'date_fin':       formation.get('date_fin') or '',
        'lieu_formation': formation.get('lieu_formation') or (madda.get('lieu_formation_defaut') if madda else '') or '',
        'nb_participants': nb_participants,
        # Editable (from saved bataqa or madda defaults)
        # Priorité : اختيار محفوظ يدويّا ← مشتقّ من المشاركين ← افتراضي المادّة ← فارغ
        'mustahdafun':          (
            bataqa['mustahdafun'] if (bataqa.get('mustahdafun') not in (None, ''))
            else (mustahdafun_derive or _f('mustahdafun', 'mustahdafun'))
        ),
        'services':             bataqa.get('services') if (bataqa.get('services') not in (None, '')) else services_default,
        'mahawer':              _f('mahawer', 'mahawer'),
        'objectifs':            _f('objectifs', 'objectifs'),
        'methodes_pedagogiques':_f('methodes_pedagogiques', 'methodes_pedagogiques'),
        'moyens_pedagogiques':  _f('moyens_pedagogiques', 'moyens_pedagogiques'),
        'preparation_materielle':_f('preparation_materielle', 'preparation_materielle'),
        'equipements':          _f('equipements', 'equipements'),
        'confirmed': bool(bataqa.get('confirmed_at')),
        'confirmed_at': bataqa.get('confirmed_at', ''),
    }


def save_bataqa_data(formation_id, data):
    """Upsert bataqa overrides and mark as confirmed. Returns True on success."""
    from datetime import datetime
    conn = get_connection()
    try:
        existing = conn.execute(
            'SELECT id FROM bataqa_formations WHERE formation_id=?', (formation_id,)
        ).fetchone()
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        fields = ('mustahdafun', 'services', 'mahawer', 'objectifs',
                  'methodes_pedagogiques', 'moyens_pedagogiques',
                  'preparation_materielle', 'equipements')
        values = tuple(data.get(f, '') for f in fields)
        if existing:
            placeholders = ', '.join(f'{f}=?' for f in fields)
            conn.execute(
                f'UPDATE bataqa_formations SET {placeholders}, confirmed_at=? WHERE formation_id=?',
                values + (now, formation_id)
            )
        else:
            cols = ', '.join(fields)
            qmarks = ', '.join('?' for _ in fields)
            conn.execute(
                f'INSERT INTO bataqa_formations (formation_id, {cols}, confirmed_at) VALUES (?, {qmarks}, ?)',
                (formation_id,) + values + (now,)
            )
        conn.commit()
        return True
    except Exception as e:
        _log.exception(f"save_bataqa_data error: {e}")
        return False
    finally:
        conn.close()


# ── Programme (étape 5) ───────────────────────────────────────────────────────

def get_programme_data(lettre_id, formation_id):
    """Return programme data merged with formation fixed fields."""
    conn = get_connection()
    formation = conn.execute(
        'SELECT * FROM formations WHERE id=? AND lettre_id=?', (formation_id, lettre_id)
    ).fetchone()
    if not formation:
        conn.close()
        return None
    formation = dict(formation)
    prog = conn.execute(
        'SELECT * FROM programme_formations WHERE formation_id=?', (formation_id,)
    ).fetchone()
    prog = dict(prog) if prog else {}
    conn.close()
    rows = json.loads(prog.get('rows_json') or '[]')
    return {
        'titre':          formation.get('titre', ''),
        'date_formation': formation.get('date_formation', ''),
        'lieu_formation': formation.get('lieu_formation', ''),
        'reference':      prog.get('reference', ''),
        # La فترة affichée dans le برنامج est celle CHOISIE dans la dorra
        # (champ periode). Aucune valeur par défaut : vide si non renseignée.
        'moment':         (formation.get('periode') or '').strip(),
        'rows':           rows,
        'confirmed':      bool(prog.get('confirmed_at')),
        'confirmed_at':   prog.get('confirmed_at', ''),
        # V2 — دورة متعدّدة الأيّام : dernier jour et découpage par jour.
        'date_fin':       formation.get('date_fin') or '',
        'multi':          _jours.est_multi_jours(formation.get('date_formation'),
                                                 formation.get('date_fin')),
        'jours':          _jours_du_programme(formation, rows),
    }


def _jours_du_programme(formation, rows):
    """Les jours du برنامج enregistré : [{jour, date, libelle, semaine,
    periode, rows}]. Une دورة d'un jour rend un seul jour portant toutes les
    lignes (et la فترة de la دورة)."""
    debut, fin = formation.get('date_formation'), formation.get('date_fin')
    periode = (formation.get('periode') or '').strip()
    segments = _jours.segmenter_lignes(rows)
    if not _jours.est_multi_jours(debut, fin):
        lignes = [r for _, seg in segments for r in seg]
        detail = _jours.jours_detail(debut, '', periode) or [
            {'jour': 1, 'date': debut or '', 'libelle': _jours.libelle_jour(1),
             'semaine': '', 'periode': periode}]
        detail[0]['rows'] = lignes
        return detail
    par_jour = {}
    for ent, seg in segments:
        if ent:
            try:
                par_jour[int(ent.get('jour'))] = (ent, seg)
            except (TypeError, ValueError):
                continue
    periodes = {n: (e.get('periode') or '') for n, (e, _) in par_jour.items()}
    detail = _jours.jours_detail(debut, fin, periode, periodes)
    for j in detail:
        j['rows'] = par_jour.get(j['jour'], (None, []))[1]
    return detail


def save_programme_data(formation_id, data):
    """Upsert programme rows + metadata. Returns True on success."""
    from datetime import datetime
    conn = get_connection()
    try:
        existing = conn.execute(
            'SELECT id FROM programme_formations WHERE formation_id=?', (formation_id,)
        ).fetchone()
        now        = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        reference  = data.get('reference', '')
        moment     = (data.get('moment') or '').strip()
        rows_json  = json.dumps(data.get('rows', []), ensure_ascii=False)
        if existing:
            conn.execute(
                'UPDATE programme_formations SET reference=?, moment=?, rows_json=?, confirmed_at=? WHERE formation_id=?',
                (reference, moment, rows_json, now, formation_id)
            )
        else:
            conn.execute(
                'INSERT INTO programme_formations (formation_id, reference, moment, rows_json, confirmed_at) VALUES (?,?,?,?,?)',
                (formation_id, reference, moment, rows_json, now)
            )
        # v1.7.1 : بيان النشاط / المتدخّلون mémorisés pour les suggestions
        from core.db.suggestions import memoriser_lignes
        memoriser_lignes(conn, data.get('rows', []))
        conn.commit()
        return True
    except Exception as e:
        _log.exception(f"save_programme_data error: {e}")
        return False
    finally:
        conn.close()


# ── V2 : برنامج دورة متعدّدة الأيّام, saisi et confirmé jour par jour ───────
#
# Chaque jour a sa فترة et ses فقرات, enregistrés dans programme_jours. Le
# jour N ne se confirme qu'après le jour N-1. À la confirmation du DERNIER
# jour, le برنامج complet est recomposé dans programme_formations (une ligne
# « date_header » en tête de chaque jour) et reçoit sa date de confirmation :
# c'est alors seulement que l'étape 5 est achevée. Tout lecteur existant
# (heures des مستحقّات, suggestions, PDF, Word) lit donc la même table.

def _formation_multi(conn, formation_id):
    f = conn.execute('SELECT * FROM formations WHERE id=?', (formation_id,)).fetchone()
    return dict(f) if f else None


def get_programme_jours(lettre_id, formation_id):
    """Les jours du برنامج d'une دورة متعدّدة الأيّام, pour la saisie :
    {multi, jours:[{jour, date, libelle, semaine, periode, rows, confirmed,
    confirmed_at}], confirmed, confirmed_at}. None si la دورة n'existe pas."""
    conn = get_connection()
    try:
        f = conn.execute('SELECT * FROM formations WHERE id=? AND lettre_id=?',
                         (formation_id, lettre_id)).fetchone()
        if not f:
            return None
        f = dict(f)
        enreg = {r['jour']: dict(r) for r in conn.execute(
            'SELECT * FROM programme_jours WHERE formation_id=? ORDER BY jour',
            (formation_id,)).fetchall()}
        prog = conn.execute('SELECT rows_json, confirmed_at FROM programme_formations '
                            'WHERE formation_id=?', (formation_id,)).fetchone()
    finally:
        conn.close()
    try:
        rows_prog = json.loads(prog['rows_json'] or '[]') if prog else []
    except (TypeError, ValueError):
        rows_prog = []
    compose = {j['jour']: j for j in _jours_du_programme(f, rows_prog)} \
        if (prog and prog['confirmed_at']) else {}
    periode = (f.get('periode') or '').strip()
    jours = []
    for j in _jours.jours_detail(f.get('date_formation'), f.get('date_fin'), periode):
        e = enreg.get(j['jour'])
        if e:
            try:
                j['rows'] = json.loads(e.get('rows_json') or '[]')
            except (TypeError, ValueError):
                j['rows'] = []
            j['periode'] = (e.get('periode') or '').strip()
            j['confirmed_at'] = e.get('confirmed_at') or ''
        elif j['jour'] in compose:
            j['rows'] = compose[j['jour']].get('rows', [])
            j['periode'] = compose[j['jour']].get('periode', periode)
            j['confirmed_at'] = prog['confirmed_at']
        else:
            j['rows'] = []
            j['confirmed_at'] = ''
        j['confirmed'] = bool(j['confirmed_at'])
        jours.append(j)
    return {
        'titre':          f.get('titre', ''),
        'date_formation': f.get('date_formation', ''),
        'date_fin':       f.get('date_fin') or '',
        'lieu_formation': f.get('lieu_formation', ''),
        'moment':         periode,
        'multi':          len(jours) > 1,
        'jours':          jours,
        'confirmed':      bool(prog and prog['confirmed_at']),
        'confirmed_at':   (prog['confirmed_at'] if prog else '') or '',
    }


def composer_lignes_jours(jours):
    """[{jour, date, periode, rows}] → la liste unique enregistrée dans
    programme_formations : une ligne « date_header » avant chaque jour."""
    lignes = []
    for j in jours:
        lignes.append({'type': 'date_header', 'jour': j['jour'], 'date': j['date'],
                       'periode': (j.get('periode') or '').strip(),
                       'libelle': _jours.libelle_jour(j['jour'])})
        lignes.extend(r for r in (j.get('rows') or []) if (r.get('type') or 'row') == 'row')
    return lignes


def save_programme_jour(formation_id, jour, periode, rows):
    """Confirme le jour `jour` du برنامج d'une دورة متعدّدة الأيّام.

    Rend (True, {'jour', 'termine', 'suivant'}) ou (False, message). Les
    lignes arrivent déjà contrôlées par la route (même garde que le برنامج
    d'un jour)."""
    from datetime import datetime
    periode = (periode or '').strip()
    if periode not in ('', 'صباحا', 'مساءا'):
        return False, 'الفترة غير صالحة'
    conn = get_connection()
    try:
        f = _formation_multi(conn, formation_id)
        if not f:
            return False, 'الدورة غير موجودة'
        jours = _jours.jours_detail(f.get('date_formation'), f.get('date_fin'),
                                    (f.get('periode') or '').strip())
        if len(jours) < 2:
            return False, 'هذه الدورة ليوم واحد: يُؤكَّد برنامجها دفعة واحدة'
        try:
            jour = int(jour)
        except (TypeError, ValueError):
            return False, 'اليوم غير صالح'
        if not 1 <= jour <= len(jours):
            return False, 'اليوم غير صالح'
        confirmes = {r['jour'] for r in conn.execute(
            'SELECT jour FROM programme_jours WHERE formation_id=? AND '
            "confirmed_at IS NOT NULL AND confirmed_at != ''", (formation_id,)).fetchall()}
        manquants = [n for n in range(1, jour) if n not in confirmes]
        if manquants:
            return False, (f'يجب أوّلا تأكيد برنامج {_jours.libelle_jour(manquants[0])} '
                           'قبل المرور إلى اليوم الموالي.')
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        date_jour = jours[jour - 1]['date']
        conn.execute('''
            INSERT INTO programme_jours (formation_id, jour, date_jour, periode, rows_json, confirmed_at)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(formation_id, jour) DO UPDATE SET
                date_jour=excluded.date_jour, periode=excluded.periode,
                rows_json=excluded.rows_json, confirmed_at=excluded.confirmed_at
        ''', (formation_id, jour, date_jour, periode,
              json.dumps(rows, ensure_ascii=False), now))
        from core.db.suggestions import memoriser_lignes
        memoriser_lignes(conn, rows)
        confirmes.add(jour)
        termine = all(j['jour'] in confirmes for j in jours)
        if termine:
            enreg = {r['jour']: dict(r) for r in conn.execute(
                'SELECT jour, date_jour, periode, rows_json FROM programme_jours '
                'WHERE formation_id=?', (formation_id,)).fetchall()}
            complets = []
            for j in jours:
                e = enreg[j['jour']]
                complets.append({'jour': j['jour'], 'date': j['date'],
                                 'periode': e['periode'] or '',
                                 'rows': json.loads(e['rows_json'] or '[]')})
            rows_json = json.dumps(composer_lignes_jours(complets), ensure_ascii=False)
            existe = conn.execute('SELECT id FROM programme_formations WHERE formation_id=?',
                                  (formation_id,)).fetchone()
            if existe:
                conn.execute('UPDATE programme_formations SET moment=?, rows_json=?, '
                             'confirmed_at=? WHERE formation_id=?',
                             ((f.get('periode') or '').strip(), rows_json, now, formation_id))
            else:
                conn.execute('INSERT INTO programme_formations (formation_id, reference, moment, '
                             'rows_json, confirmed_at) VALUES (?, ?, ?, ?, ?)',
                             (formation_id, '', (f.get('periode') or '').strip(), rows_json, now))
        conn.commit()
        suivant = next((j['jour'] for j in jours if j['jour'] not in confirmes), None)
        return True, {'jour': jour, 'termine': termine, 'suivant': suivant,
                      'nb_jours': len(jours), 'confirmed_at': now}
    except Exception as e:
        _log.exception(f'save_programme_jour error: {e}')
        return False, 'خطأ في الحفظ'
    finally:
        conn.close()


def formation_est_multi_jours(formation_id):
    conn = get_connection()
    try:
        f = conn.execute('SELECT date_formation, date_fin FROM formations WHERE id=?',
                         (formation_id,)).fetchone()
    finally:
        conn.close()
    return bool(f) and _jours.est_multi_jours(f['date_formation'], f['date_fin'])


# ══════════════════════════════════════════════════════════════════════════════
#  مذكرة تكوين داخلية (étape 6)
# ══════════════════════════════════════════════════════════════════════════════

# Les مصاحيب sont toujours les mêmes (cf. modèle officiel)
MEMO_MSAHIB = [
    'نسخة من برنامج الدّورة التّكوينيّة.',
    'قائمة إسميّة في المشاركين.',
    'نسخة من بطاقة بيداغوجيّة.',
]

# Destinataires imposés — conservés dans cet ordre (les trois « للإعلام »
# viennent en tête de liste, مصلحة المحفوظات والتوثيق toujours en dernier).
MEMO_MOUJAH_TETE = [
    {'nom': 'السيّد مدير إدارة الإنتدابات والتّكوين',                  'type': 'للإعلام'},
    {'nom': 'السيّد مدير إدارة التّخطيط والبرمجة والتّعاون الخارجي', 'type': 'للإعلام'},
    {'nom': 'السيّد مدير إدارة التّعليم والدّراسات',                    'type': 'للإعلام'},
]
MEMO_MOUJAH_FIN = {'nom': 'مصلحة المحفوظات والتوثيق', 'type': ''}

MEMO_TYPES = ['للإعلام', 'للتعهد']


def _destinataire_de_jiha(jiha):
    """« الإدارة الجهويّة للدّيوانة بـX » → « السيّد المدير الجهوي للدّيوانة بـX » ;
    une unité / فرقة → « السيّد رئيس … » ; une إدارة → « السيّد مدير … »."""
    j = ' '.join(str(jiha or '').split())
    if not j:
        return ''
    corps = re.sub(r'^(?:ال)?إدارة\s+الجهوي[ّ]?ة\s*', '', j)
    if corps != j:
        return f'السيّد المدير الجهوي {corps}'.strip()
    if re.match(r'^(?:ال)?إدارة', j):
        return f'السيّد مدير {j}'
    return f'السيّد رئيس {j}'


def moujah_regionaux(cfg, jihat=None):
    """Les مراجع النظر qui libèrent les أعوان pour la دورة, « للتعهد ».

    Ils suivent les الجهات المرجعيّة des مشاركين réellement inscrits : une
    دورة qui réunit des أعوان de deux directions régionales s'adresse aux deux
    directeurs. Sans جهة connue, on retombe sur ceux réglés pour le centre."""
    from core import identite
    res, vus = [], set()
    for j in (jihat or []):
        nom = _destinataire_de_jiha(j)
        if nom and nom not in vus:
            vus.add(nom)
            res.append({'nom': nom, 'type': 'للتعهد'})
    if res:
        return res
    for nom in (identite.directeur_regional(cfg), identite.chef_unite_garde(cfg)):
        if nom:
            res.append({'nom': nom, 'type': 'للتعهد'})
    return res


def _memo_corps_defaut(annee, titre, rattach, date_long, lieu,
                       formateur, nb_participants, heure_lettres, grades_phrase,
                       plage=None, heure_variable=False):
    """Compose les trois paragraphes du modèle avec les variables de la dorra.

    `rattach` provient de arabe.rattachement_services() : les MKATEB sont
    remplacés par leur direction régionale et les FIRAQ par leur unité de la
    garde douanière — inutile de les détailler un par un.
    `grades_phrase` reflète les grades réellement inscrits (ضبّاط / ضبّاط صف /
    ضبّاط وضبّاط صف)."""
    lieu_txt = f' بـ{lieu}' if lieu else ''
    mot     = rattach.get('mot') or 'المصالح'
    phrase  = (rattach.get('phrase') or '').strip()
    raj = (f'بمختلف {mot} الرّاجعة بالنّظر إلى {phrase}'
           if phrase else f'بمختلف {mot}')
    from core import arabe as _arabe
    nb_txt = _arabe.expression_participants(nb_participants)
    p1 = (f'في إطار تنفيذ البرنامج السّنوي للتّكوين للإدارة العامّة للدّيوانة '
          f'بعنوان سنة {annee}، تقرّر تنفيذ دورة تكوينيّة ميدانيّة في مجال '
          f'" {titre} " لفائدة {grades_phrase} الدّيوانة المباشرين '
          f'{raj} وذلك ' + (plage or f'يوم {date_long}') + f'{lieu_txt}.')
    p2 = (f'سيشرف على تأمين فعاليّات الدّورة التّدريبيّة المرتقبة {formateur} '
          f'وذلك بمشاركة {nb_txt} عن هيئة {grades_phrase} الدّيوانة '
          f'المباشرين {raj}.')
    p3 = (f'وعليه، فالمطلوب من المشاركين المضمّنة أسماؤهم بالقائمة المصاحبة '
          f'الحضور إلى {lieu} مرتدين للزّي الرّسمي لمتابعة فعاليّات الدّورة '
          f'التّكوينيّة المرتقبة وذلك في التّاريخ المشار إليه أعلاه بداية من '
          f'السّاعة {heure_lettres}.')
    if plage:
        # V2 — دورة متعدّدة الأيّام : les jours, et l'heure si elle est la même
        # chaque jour ; sinon le برنامج المصاحب fait foi.
        suite = ('حسب التّوقيت المضبوط لكلّ يوم ببرنامج الدّورة المصاحب'
                 if heure_variable else f'بداية من السّاعة {heure_lettres}')
        p3 = (f'وعليه، فالمطلوب من المشاركين المضمّنة أسماؤهم بالقائمة المصاحبة '
              f'الحضور إلى {lieu} مرتدين للزّي الرّسمي لمتابعة فعاليّات الدّورة '
              f'التّكوينيّة المرتقبة وذلك طيلة الأيّام المشار إليها أعلاه {suite}.')
    return '\n'.join([p1, p2, p3])


def get_memo_data(lettre_id, formation_id, force_auto=False):
    """Données de la مذكرة : champs figés de la dorra + valeurs enregistrées,
    sinon gabarit généré automatiquement."""
    from core import arabe, identite

    conn = get_connection()
    formation = conn.execute(
        'SELECT * FROM formations WHERE id=? AND lettre_id=?', (formation_id, lettre_id)
    ).fetchone()
    if not formation:
        conn.close()
        return None
    formation = dict(formation)

    lettre = conn.execute('SELECT * FROM lettres WHERE id=?', (lettre_id,)).fetchone()
    lettre = dict(lettre) if lettre else {}

    parts = conn.execute(
        'SELECT lieu_travail, grade, jiha_marjiiya FROM participants '
        'WHERE lettre_id=? AND formation_id=? ORDER BY ordre',
        (lettre_id, formation_id)
    ).fetchall()
    nb_participants = len(parts)
    services, grades_parts, jihat = [], [], []
    _vus_lt = set()
    for p in parts:
        jm = (p['jiha_marjiiya'] or '').strip()
        if jm and jm not in jihat:
            jihat.append(jm)
        lt = (p['lieu_travail'] or '').strip()
        if lt and lt not in _vus_lt:
            _vus_lt.add(lt)
            services.append((lt, jm))
        gr = (p['grade'] or '').strip()
        if gr and gr not in grades_parts:
            grades_parts.append(gr)

    # Entités de rattachement (paramétrées dans les Réglages)
    _cfg = {r['cle']: r['valeur'] for r in conn.execute(
        "SELECT cle, valeur FROM config WHERE cle IN ('admin_regionale','unite_garde',"
        "'destination_dr','ville_centre')")}

    prog = conn.execute(
        'SELECT * FROM programme_formations WHERE formation_id=?', (formation_id,)
    ).fetchone()
    prog = dict(prog) if prog else {}

    memo = conn.execute(
        'SELECT * FROM memo_formations WHERE formation_id=?', (formation_id,)
    ).fetchone()
    memo = dict(memo) if memo else {}
    conn.close()

    titre      = (formation.get('titre') or '').strip()
    annee      = lettre.get('annee') or ''
    date_iso   = formation.get('date_formation') or ''
    date_long  = arabe.date_longue(date_iso)
    lieu       = (formation.get('lieu_formation') or '').strip()
    grade_f    = (formation.get('grade') or '').strip()
    nom_f      = (formation.get('nom_formateur') or '').strip()
    formateur  = f'{grade_f} {nom_f}'.strip()

    # Ouverture de la دورة : 08:30 le matin, 13:30 pour la فترة المسائيّة
    # (sauf saisie explicite).
    _ouverture    = '13:30' if (formation.get('periode') or '').strip() == 'مساءا' else '08:30'
    # L'heure du برنامج fait foi : première فقرة datée.
    try:
        _rows = json.loads(prog.get('rows_json') or '[]')
    except (ValueError, TypeError):
        _rows = []
    # V2 — دورة متعدّدة الأيّام : l'heure d'ouverture est celle du PREMIER
    # jour ; on note si les jours ne commencent pas tous à la même heure.
    _segments = _jours.segmenter_lignes(_rows) if _jours.est_programme_multi(_rows) else [(None, _rows)]
    _debuts_jours = []
    for _ent, _seg in _segments:
        _d = sorted(str(r.get('time_debut') or '').strip() for r in _seg
                    if isinstance(r, dict) and re.match(r'^\d{1,2}:\d{2}$',
                                                        str(r.get('time_debut') or '').strip()))
        if _d:
            _debuts_jours.append(_d[0].zfill(5))
    if _debuts_jours:
        _ouverture = _debuts_jours[0]
    _heure_variable = len(set(_debuts_jours)) > 1
    heure_txt     = (memo.get('heure_debut') or '').strip() or _ouverture
    heure_lettres = arabe.heure_en_lettres(heure_txt)
    nb_lettres    = arabe.nombre_en_lettres(nb_participants)

    # Les مكاتب → leur direction régionale ; les فرق → leur unité de garde
    rattach       = arabe.rattachement_services(
        services, identite.admin_regionale(_cfg), _cfg.get('unite_garde', ''))
    grades_phrase = arabe.phrase_grades(grades_parts)

    objet_defaut = f'دورة تكوينيّة حول {titre}.' if titre else ''
    # V2 : « من يوم 14 إلى يوم 16 أكتوبر 2026 » pour une دورة متعدّدة الأيّام
    _multi = _jours.est_multi_jours(date_iso, formation.get('date_fin'))
    _plage = _jours.plage_longue(date_iso, formation.get('date_fin'), 'يوم') if _multi else None
    if _multi:
        date_long = _jours.plage_longue(date_iso, formation.get('date_fin'))
    corps_defaut = _memo_corps_defaut(annee, titre, rattach, date_long,
                                      lieu, formateur, nb_participants,
                                      heure_lettres, grades_phrase,
                                      plage=_plage, heure_variable=_heure_variable)

    # Liste des destinataires : saisie manuelle, pré-remplie des entrées imposées
    try:
        moujah = json.loads(memo.get('moujah_json') or '[]')
        if not isinstance(moujah, list):
            moujah = []
    except Exception:
        _log.warning('get_memo_data : exception ignorée', exc_info=True)
        moujah = []
    if not moujah:
        # Ordre : les 3 directions « للإعلام », puis les deux مراجع النظر
        # régionaux — المدير الجهوي (pour les مكاتب) et رئيس وحدة الحرس (pour
        # les فرق) —, puis مصلحة المحفوظات والتوثيق. L'utilisateur peut
        # ensuite réordonner librement (boutons ▲ ▼) ou en retirer un.
        moujah = [dict(x) for x in MEMO_MOUJAH_TETE] \
            + moujah_regionaux(_cfg, jihat) + [dict(MEMO_MOUJAH_FIN)]

    return {
        # Figés
        'titre':           titre,
        'date_formation':  date_iso,
        'date_fin':        formation.get('date_fin') or '',
        'date_longue':     date_long,
        'lieu_formation':  lieu,
        'formateur':       formateur,
        'nb_participants': nb_participants,
        'nb_lettres':      nb_lettres,
        'annee':           annee,
        'services':        [s for s, _ in services],
        'rattachement':    rattach['entites'],
        'grades_phrase':   grades_phrase,
        'msahib':          list(MEMO_MSAHIB),
        'types_moujah':    list(MEMO_TYPES),
        # Modifiables — si le contenu n'a PAS été retouché à la main
        # (contenu_manuel = 0), on régénère toujours à partir des données
        # courantes : ainsi une réimpression après modification des
        # participants/grades reflète bien les mises à jour.
        'objet':  ((memo.get('objet') or '').strip() or objet_defaut)
                  if (memo.get('contenu_manuel') and not force_auto) else objet_defaut,
        'corps':  ((memo.get('corps') or '').strip() or corps_defaut)
                  if (memo.get('contenu_manuel') and not force_auto) else corps_defaut,
        'contenu_manuel': bool(memo.get('contenu_manuel')) and not force_auto,
        'heure_debut':  heure_txt,
        'heure_lettres': heure_lettres,
        'moujah':       moujah,
        # Référence PROPRE de la مذكرة (distincte de celle de la مراسلة)
        'memo_ref':     memo.get('ref_complet') or '',
        'memo_numero':  memo.get('numero') or '',
        # États
        'enregistre':   bool(memo.get('enregistre_at')),
        'confirmed':    bool(memo.get('confirmed_at')),
        'confirmed_at': memo.get('confirmed_at') or '',
        'finalise':     bool(memo.get('finalise_at')),
        'finalise_at':  memo.get('finalise_at') or '',
    }


def save_memo_data(formation_id, data, confirmer=True):
    """Upsert de la مذكرة. `confirmer=False` ne fait qu'enregistrer la dorra
    (bouton « تسجيل التكوين ») sans valider le contenu de la مذكرة."""
    from datetime import datetime
    conn = get_connection()
    try:
        # Une dorra verrouillée (تسجيل نهائي) ne peut plus être modifiée.
        lock = conn.execute(
            'SELECT finalise_at FROM memo_formations WHERE formation_id=?',
            (formation_id,)).fetchone()
        if lock and lock['finalise_at']:
            return False

        row = conn.execute(
            'SELECT id, enregistre_at, confirmed_at, numero, ref_complet '
            'FROM memo_formations WHERE formation_id=?',
            (formation_id,)
        ).fetchone()
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        objet       = (data.get('objet') or '').strip()
        corps       = (data.get('corps') or '').strip()
        heure       = (data.get('heure_debut') or '').strip()
        manuel      = 1 if data.get('contenu_manuel') else 0
        moujah      = data.get('moujah', [])
        moujah_json = json.dumps(
            [{'nom': (m.get('nom') or '').strip(), 'type': (m.get('type') or '').strip()}
             for m in moujah if (m.get('nom') or '').strip()],
            ensure_ascii=False)

        # ── Numéro d'enregistrement PROPRE à la مذكرة (compteur interne) ──────
        # Attribué une seule fois, à la première confirmation de la مذكرة, pour
        # qu'elle ne partage PAS le numéro de la مراسلة du programme.
        memo_ref = (row['ref_complet'] if row and row['ref_complet'] else '')
        memo_num = (row['numero'] if row and row['numero'] else 0)
        nouveau_numero = False
        if confirmer and not memo_ref:
            nouveau_numero = True
            memo_ref, memo_num = _attribuer_numero(
                conn, 'interne', 'memo', formation_id, objet or '', 'provisoire')

        if row:
            enregistre_at = row['enregistre_at'] or now
            confirmed_at  = now if confirmer else row['confirmed_at']
            conn.execute(
                'UPDATE memo_formations SET objet=?, corps=?, moujah_json=?, '
                'heure_debut=?, contenu_manuel=?, enregistre_at=?, confirmed_at=?, '
                'numero=?, ref_complet=?, '
                'annee=CASE WHEN ? THEN ? ELSE COALESCE(annee, ?) END '
                'WHERE formation_id=?',
                (objet, corps, moujah_json, heure, manuel,
                 enregistre_at, confirmed_at, memo_num, memo_ref,
                 # v1.7 : l'année de la مذكّرة est celle du سجلّ où son عدد
                 # vient d'être pris (brouillon de ديسمبر confirmé en جانفي).
                 1 if nouveau_numero else 0, _exercice.annee_active(conn),
                 _exercice.annee_active(conn), formation_id))
        else:
            conn.execute(
                'INSERT INTO memo_formations (formation_id, objet, corps, moujah_json, '
                'heure_debut, contenu_manuel, enregistre_at, confirmed_at, numero, '
                'ref_complet, annee) '
                'VALUES (?,?,?,?,?,?,?,?,?,?,?)',
                (formation_id, objet, corps, moujah_json, heure, manuel, now,
                 now if confirmer else None, memo_num, memo_ref,
                 _exercice.annee_active(conn)))
        conn.commit()
        return True
    except Exception as e:
        _log.exception(f"save_memo_data error: {e}")
        return False
    finally:
        conn.close()


def finaliser_formation(formation_id):
    """« تسجيل الدورة في المنظومة » : verrou définitif. Après cela la dorra ne
    peut plus être modifiée (réservé au superadmin ultérieurement)."""
    from datetime import datetime
    conn = get_connection()
    try:
        row = conn.execute(
            'SELECT id, confirmed_at, finalise_at FROM memo_formations WHERE formation_id=?',
            (formation_id,)).fetchone()
        if not row or not row['confirmed_at']:
            return False, 'يجب تأكيد المذكّرة الداخليّة أوّلا'
        if row['finalise_at']:
            return False, 'الدورة مسجَّلة نهائيًّا من قبل'
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        conn.execute('UPDATE memo_formations SET finalise_at=? WHERE formation_id=?',
                     (now, formation_id))
        # Le numéro de cette مذكّرة devient définitif ; et si toutes les dorrat du
        # programme sont désormais enregistrées, ceux du programme et de la
        # مراسلة المدير الجهوي le deviennent aussi — plus aucun فسخ possible.
        conn.execute("UPDATE registre SET statut='definitif' "
                     "WHERE source='memo' AND source_id=?", (formation_id,))
        lid = conn.execute('SELECT lettre_id FROM formations WHERE id=?',
                           (formation_id,)).fetchone()
        if lid:
            reste = conn.execute(
                'SELECT COUNT(*) FROM formations f '
                'LEFT JOIN memo_formations m ON m.formation_id = f.id '
                'WHERE f.lettre_id=? AND (m.finalise_at IS NULL OR m.finalise_at = "")',
                (lid[0],)).fetchone()[0]
            if reste == 0:
                confirmer_numeros_programme(conn, lid[0])
        conn.commit()
        return True, now
    except Exception as e:
        _log.warning('finaliser_formation : exception ignorée', exc_info=True)
        return False, str(e)
    finally:
        conn.close()


def formation_est_finalisee(formation_id):
    """True si la dorra a été enregistrée définitivement dans le système."""
    conn = get_connection()
    try:
        r = conn.execute(
            'SELECT finalise_at FROM memo_formations WHERE formation_id=?',
            (formation_id,)).fetchone()
        return bool(r and r['finalise_at'])
    finally:
        conn.close()


def deverrouiller_formation(formation_id):
    """« التراجع للتحيين » (v1.6, réservé au مشرف) : lève le verrou posé par
    `finaliser_formation` pour permettre une correction.

    - Refusé si les مستحقّات de la دورة sont achevées : il faut d'abord les
      rouvrir (le chiffrage payé ne doit pas diverger de la دورة corrigée).
    - Si le برنامج était scellé, sa مصادقة tombe aussi : elle attestait un
      état qui va changer ; on la redonnera après correction.
    - Les أعداد du سجلّ restent définitifs : ils ont été émis et ne reviennent
      jamais au pool.
    Renvoie (ok, message | {'lettre_id', 'titre', 'scelle_leve'})."""
    conn = get_connection()
    try:
        row = conn.execute(
            'SELECT f.lettre_id, f.titre, m.finalise_at FROM formations f '
            'LEFT JOIN memo_formations m ON m.formation_id = f.id WHERE f.id=?',
            (formation_id,)).fetchone()
        if not row:
            return False, 'الدورة غير موجودة'
        if not row['finalise_at']:
            return False, 'الدورة غير مسجَّلة نهائيًّا'
        mu = conn.execute('SELECT etat FROM mustahaqqat WHERE formation_id=?',
                          (formation_id,)).fetchone()
        if mu and mu['etat'] == 'acheve':
            return False, ('مستحقّات هذه الدورة مؤكَّدة نهائيًّا : '
                           'أعد فتح المستحقّات أوّلا ثمّ تراجع للتحيين')
        conn.execute('UPDATE memo_formations SET finalise_at=NULL WHERE formation_id=?',
                     (formation_id,))
        # Une مستحقّات en attente de validation n'a plus d'objet : la دورة va changer.
        conn.execute('UPDATE mustahaqqat SET pret_at=NULL, pret_par=\'\' '
                     'WHERE formation_id=?', (formation_id,))
        sc = conn.execute('SELECT scelle_at FROM lettres WHERE id=?',
                          (row['lettre_id'],)).fetchone()
        scelle_leve = bool(sc and sc['scelle_at'])
        if scelle_leve:
            conn.execute('UPDATE lettres SET scelle_at=NULL WHERE id=?', (row['lettre_id'],))
        conn.commit()
        return True, {'lettre_id': row['lettre_id'], 'titre': row['titre'] or '',
                      'scelle_leve': scelle_leve}
    except Exception as e:
        _log.warning('deverrouiller_formation : exception ignorée', exc_info=True)
        return False, str(e)
    finally:
        conn.close()


# ─── نسخ برنامج (v1.5 — P1) ──────────────────────────────────────────────────

def dupliquer_programme(lettre_id, mois, annee):
    """Crée un NOUVEAU برنامج (brouillon, non confirmé, sans numéro) à partir
    d'un برنامج existant, pour le mois et l'année choisis.

    Sont repris : le type (داخلية/خارجية), le signataire, et pour chaque دورة
    son عنوان, son مكوّن (رتبة, اسم, مكان عمل), sa فترة et son مكان.
    Ne sont PAS repris : les dates (elles doivent tomber dans le nouveau mois —
    l'agent les saisit), les مشاركون, les وثائق confirmées, les أعداد.
    Rend l'id du nouveau برنامج, ou None si la source est introuvable ou n'est
    pas un برنامج تكوين."""
    conn = get_connection()
    try:
        src = conn.execute(
            "SELECT * FROM lettres WHERE id=? AND (categorie='programme' OR categorie IS NULL)",
            (lettre_id,)).fetchone()
        if not src:
            return None
        formations = [dict(r) for r in conn.execute(
            'SELECT titre, grade, nom_formateur, lieu_travail, periode, lieu_formation '
            'FROM formations WHERE lettre_id=? ORDER BY ordre', (lettre_id,)).fetchall()]
    finally:
        conn.close()
    for f in formations:
        f['date_formation'] = ''
    return save_programme(src['type'] or 'interne', mois, int(annee), formations,
                          src['nom_responsable'] or '', src['titre_responsable'] or '')
