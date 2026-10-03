# -*- coding: utf-8 -*-
"""المستحقّات المالية : barème رتبة → صنف, ورقة الحضور, الجدول المالي,
القيمة المالية d'une دورة.

Extrait de core/database.py (v1.4) — importer depuis core.database, qui
ré-exporte tout : les appelants existants restent inchangés."""

import json
from core import mustahaqqat as _mustahaqqat
from core import bareme_mali as _bareme_mali
from core import jours as _jours

from core.db._base import _log, get_connection
from core.db.referentiels import get_grades


# ══════════════════════════════════════════════════════════════════════════
#  المستحقّات المالية  (v1.0)
# ══════════════════════════════════════════════════════════════════════════
#
#  Chaîne complète :
#     دورة مسجَّلة نهائيًّا في المنظومة
#        └─► اختيار الدورة        (écran 1 : برامج تكوين غير منجزة)
#              └─► التأشير على الحضور   (écran 2 : حاضر / غائب)
#                    └─► تأكيد الصنف     (الصنف الأكثر حضورًا)
#                          └─► القيمة المالية والوثائق   (écran 3)
#
#  Une dorra n'entre ici qu'une fois `memo_formations.finalise_at` renseigné :
#  les مستحقّات se calculent sur un تكوين achevé, jamais sur un brouillon.


# ─── Barème رتبة → صنف ───────────────────────────────────────────────────────

def get_bareme_grades():
    """Le barème tel qu'il est en base : {رتبة : صنف}."""
    conn = get_connection()
    try:
        return {r['grade']: (r['classe'] or '')
                for r in conn.execute(
                    'SELECT grade, classe FROM mustahaqqat_grades').fetchall()}
    except Exception:
        _log.warning('get_bareme_grades : exception ignorée', exc_info=True)
        return _mustahaqqat.bareme_defaut()
    finally:
        conn.close()


def get_bareme_grades_detail():
    """Le barème trié comme la liste des رتب de la منظومة, pour الإعدادات."""
    bareme = get_bareme_grades()
    conn = get_connection()
    try:
        connus = [r['nom'] for r in conn.execute(
            'SELECT nom FROM grades ORDER BY id').fetchall()]
    finally:
        conn.close()
    ordonnes = [g for g in connus if g in bareme]
    ordonnes += sorted(g for g in bareme if g not in connus)
    return [{'grade': g,
             'classe': bareme.get(g, ''),
             'libelle_classe': _mustahaqqat.libelle_classe(bareme.get(g, ''))}
            for g in ordonnes]


def set_classe_grade(grade, classe):
    """Fixe (ou efface) le صنف d'une رتبة. Un صنف inconnu vaut « non classée »."""
    if classe not in _mustahaqqat.CLASSES:
        classe = ''
    conn = get_connection()
    try:
        conn.execute('INSERT INTO mustahaqqat_grades (grade, classe) VALUES (?, ?) '
                     'ON CONFLICT(grade) DO UPDATE SET classe=excluded.classe',
                     (str(grade).strip(), classe))
        conn.commit()
        return True
    except Exception as e:
        _log.exception(f"set_classe_grade error: {e}")
        return False
    finally:
        conn.close()


def reinitialiser_bareme():
    """Remet le barème officiel. Les رتب locales non classées le restent."""
    conn = get_connection()
    try:
        for libelle, classe in _mustahaqqat.bareme_defaut().items():
            conn.execute('INSERT INTO mustahaqqat_grades (grade, classe) VALUES (?, ?) '
                         'ON CONFLICT(grade) DO UPDATE SET classe=excluded.classe',
                         (libelle, classe))
        conn.commit()
        return True
    except Exception as e:
        _log.exception(f"reinitialiser_bareme error: {e}")
        return False
    finally:
        conn.close()


# ─── Les dorrat vues depuis les مستحقّات ─────────────────────────────────────

_SQL_DORRA_MUSTAHAQQAT = '''
    SELECT f.id, f.lettre_id, f.ordre, f.titre, f.grade, f.nom_formateur,
           f.lieu_travail, f.date_formation, f.periode, f.lieu_formation,
           f.date_fin               AS date_fin,
           m.finalise_at            AS finalise_at,
           m.ref_complet            AS memo_ref,
           l.ref_complet            AS lettre_ref,
           l.mois                   AS lettre_mois,
           l.annee                  AS lettre_annee,
           mu.etat                  AS mu_etat,
           mu.classe                AS mu_classe,
           mu.classe_auto           AS mu_classe_auto,
           mu.nb_presents           AS mu_presents,
           mu.nb_absents            AS mu_absents,
           mu.hodour_at             AS mu_hodour_at,
           mu.classe_at             AS mu_classe_at,
           mu.acheve_at             AS mu_acheve_at,
           mu.groupe                AS mu_groupe,
           mu.heure_debut           AS mu_heure_debut,
           mu.heure_fin             AS mu_heure_fin,
           mu.minutes               AS mu_minutes,
           mu.heures                AS mu_heures,
           mu.taux                  AS mu_taux,
           mu.montant               AS mu_montant,
           mu.pret_at               AS mu_pret_at,
           mu.pret_par              AS mu_pret_par,
           (SELECT COUNT(*) FROM participants p
             WHERE p.formation_id = f.id) AS nb_participants
    FROM memo_formations m
    JOIN formations f ON f.id = m.formation_id
    JOIN lettres    l ON l.id = f.lettre_id
    LEFT JOIN mustahaqqat mu ON mu.formation_id = f.id
    WHERE m.finalise_at IS NOT NULL AND m.finalise_at != ''
'''


def _dorrat_mustahaqqat(achevees):
    """Dorrat enregistrées définitivement, selon que leurs مستحقّات sont
    achevées ou non. C'est exactement le partage « منجزة / غير منجزة »."""
    condition = ("AND mu.acheve_at IS NOT NULL AND mu.acheve_at != ''"
                 if achevees else
                 "AND (mu.acheve_at IS NULL OR mu.acheve_at = '')")
    conn = get_connection()
    try:
        rows = conn.execute(
            _SQL_DORRA_MUSTAHAQQAT + condition +
            ' ORDER BY f.date_formation DESC, f.id DESC').fetchall()
        return [_enrichir_dorra(dict(r)) for r in rows]
    finally:
        conn.close()


def _enrichir_dorra(d):
    """Ajoute l'état lisible d'une dorra pour l'affichage."""
    d['etat'] = d.get('mu_etat') or 'attente'
    d['classe'] = d.get('mu_classe') or ''
    d['libelle_classe'] = _mustahaqqat.libelle_classe(d['classe'])
    # Le montant arrêté, pour les listes. '' tant qu'il n'a pas été approuvé :
    # une dorra en cours n'a pas de montant, elle a une estimation — et une
    # estimation n'a pas sa place dans une colonne intitulée « المبلغ ».
    d['montant'] = d.get('mu_montant') or 0
    d['montant_texte'] = (_bareme_mali.formater_dinars(d['montant'])
                          if d['etat'] == 'acheve' and d['montant'] else '')
    d['heures'] = d.get('mu_heures') or 0
    d['etat_libelle'] = {
        'attente': 'لم تنطلق',
        'hodour':  'تأشير الحضور جارٍ',
        'classe':  'الصنف محدَّد',
        'acheve':  'منجزة',
    }.get(d['etat'], d['etat'])
    # v1.6 : « جاهز للمصادقة » — l'agent a tout préparé, l'مشرف arrête le montant.
    d['pret'] = bool(d.get('mu_pret_at')) and d['etat'] == 'classe'
    if d['pret']:
        d['etat_libelle'] = 'بانتظار مصادقة المشرف'
    # V2 — دورة متعدّدة الأيّام
    d['date_fin'] = d.get('date_fin') or ''
    d['multi'] = _jours.est_multi_jours(d.get('date_formation'), d['date_fin'])
    d['nb_jours'] = _jours.nombre_de_jours(d.get('date_formation'), d['date_fin'])
    d['derniere_date'] = _jours.derniere_date(d)
    d['dates_texte'] = _jours.plage_iso(d.get('date_formation'), d['date_fin'])
    return d


def dorrat_mustahaqqat_ghayr_manjaza():
    """Écran 1 : les dorrat enregistrées dont les مستحقّات restent à faire."""
    return _dorrat_mustahaqqat(achevees=False)


def dorrat_mustahaqqat_manjaza():
    """Les dorrat dont les مستحقّات sont achevées."""
    return _dorrat_mustahaqqat(achevees=True)


def get_dorra_mustahaqqat(formation_id):
    """Une dorra précise, vue depuis les مستحقّات. None si elle n'y a pas
    sa place (pas encore enregistrée définitivement dans la منظومة)."""
    conn = get_connection()
    try:
        row = conn.execute(_SQL_DORRA_MUSTAHAQQAT + ' AND f.id = ?',
                           (formation_id,)).fetchone()
        return _enrichir_dorra(dict(row)) if row else None
    finally:
        conn.close()


# ─── ورقة الحضور ─────────────────────────────────────────────────────────────

def get_hodour(formation_id):
    """Les مشاركون d'une dorra avec leur état de présence.

    Un participant jamais pointé est présenté **حاضر** : c'est le cas courant,
    et l'agent ne coche alors que les absents. Rien n'est enregistré tant
    qu'il n'a pas validé — la valeur affichée n'est qu'une proposition.
    """
    conn = get_connection()
    try:
        rows = conn.execute('''
            SELECT p.id, p.ordre, p.nom_prenom, p.grade,
                   p.identifiant_unique, p.lieu_travail, p.jiha_marjiiya,
                   h.present AS present
            FROM participants p
            LEFT JOIN mustahaqqat_hodour h
                   ON h.participant_id = p.id AND h.formation_id = p.formation_id
            WHERE p.formation_id = ?
            ORDER BY p.ordre
        ''', (formation_id,)).fetchall()
    finally:
        conn.close()

    bareme = _mustahaqqat.preparer_bareme(get_bareme_grades())
    # V2 — دورة متعدّدة الأيّام : un حاضر/غائب par jour (proposé حاضر tant
    # que rien n'est enregistré, comme pour une دورة d'un jour).
    jours = get_jours_dorra(formation_id)
    par_jour = {}
    if len(jours) > 1:
        conn = get_connection()
        try:
            for r in conn.execute('SELECT participant_id, jour, present FROM '
                                  'mustahaqqat_hodour_jours WHERE formation_id=?',
                                  (formation_id,)).fetchall():
                par_jour.setdefault(r['participant_id'], {})[r['jour']] = int(r['present'])
        finally:
            conn.close()
    participants = []
    for r in rows:
        p = dict(r)
        p['present'] = 1 if (p['present'] is None) else int(p['present'])
        p['classe'] = _mustahaqqat.classe_du_grade(p.get('grade'), bareme)
        p['libelle_classe'] = _mustahaqqat.libelle_classe(p['classe'])
        if len(jours) > 1:
            connus = par_jour.get(p['id'], {})
            p['jours'] = {j['jour']: connus.get(j['jour'], 1) for j in jours}
            p['nb_jours_presents'] = sum(p['jours'].values())
            p['present'] = 1 if p['nb_jours_presents'] else 0
            p['absences'] = [j['jour'] for j in jours if not p['jours'][j['jour']]]
        participants.append(p)
    return participants


def get_jours_dorra(formation_id):
    """V2 — Les jours d'une دورة : [{jour, date, libelle, semaine, periode}].
    La فترة de chaque jour est celle choisie dans برنامج الدورة ; à défaut,
    celle de la دورة. Une دورة d'un jour rend un seul jour."""
    conn = get_connection()
    try:
        f = conn.execute('SELECT date_formation, date_fin, periode FROM formations '
                         'WHERE id=?', (formation_id,)).fetchone()
        if not f:
            return []
        periodes = {r['jour']: (r['periode'] or '') for r in conn.execute(
            'SELECT jour, periode FROM programme_jours WHERE formation_id=?',
            (formation_id,)).fetchall()}
        if not periodes:
            prog = conn.execute('SELECT rows_json FROM programme_formations '
                                'WHERE formation_id=?', (formation_id,)).fetchone()
            try:
                for r in json.loads((prog['rows_json'] if prog else None) or '[]'):
                    if isinstance(r, dict) and r.get('type') == 'date_header' and r.get('date'):
                        periodes[int(r.get('jour') or 0)] = r.get('periode') or ''
            except (TypeError, ValueError):
                pass
    finally:
        conn.close()
    return _jours.jours_detail(f['date_formation'], f['date_fin'] or '',
                               (f['periode'] or '').strip(), periodes)


def _presences_ponderees(participants):
    """Liste des présences qui fondent le صنف : un participant compte UNE fois
    par jour de présence (دورة متعدّدة الأيّام), ou une fois s'il est présent
    (دورة d'un jour)."""
    liste = []
    for p in participants:
        if 'jours' in p:
            liste.extend([p] * sum(1 for v in p['jours'].values() if v))
        elif p['present']:
            liste.append(p)
    return liste


def calculer_classe(formation_id, presences=None):
    """صنف الدّورة d'après les présents.

    `presences` : {participant_id : bool}. Absent → on lit ce qui est en base.
    Renvoie (classe, repartition, ex_aequo, nb_presents, nb_absents).
    """
    participants = get_hodour(formation_id)
    if presences is not None:
        for p in participants:
            if p['id'] in presences:
                v = presences[p['id']]
                if 'jours' in p and isinstance(v, dict):
                    p['jours'] = {n: (1 if v.get(n) else 0) for n in p['jours']}
                    p['present'] = 1 if any(p['jours'].values()) else 0
                else:
                    p['present'] = 1 if v else 0
    presents = [p for p in participants if p['present']]
    bareme = get_bareme_grades()
    # V2 : دورة متعدّدة الأيّام — le صنف le plus présent SUR TOUTE LA DURÉE :
    # chaque jour de présence d'un مشارك compte (pondération par les jours).
    classe, repart, ex_aequo = _mustahaqqat.classe_dominante(
        _presences_ponderees(participants), bareme)
    return classe, repart, ex_aequo, len(presents), len(participants) - len(presents)


def save_hodour(formation_id, presences):
    """Enregistre ورقة الحضور puis calcule le صنف proposé.

    `presences` : {participant_id : bool}. TOUS les participants doivent y
    figurer — une feuille de présence à moitié pointée ne fonde aucun صنف, et
    la منظومة refuse plutôt que de deviner.

    Renvoie (True, données) ou (False, message).
    """
    from datetime import datetime
    dorra = get_dorra_mustahaqqat(formation_id)
    if not dorra:
        return False, 'الدورة غير مسجَّلة نهائيًّا في المنظومة'
    if dorra['etat'] == 'acheve':
        return False, 'مستحقّات هذه الدورة منجزة ولا يمكن تعديلها'

    participants = get_hodour(formation_id)
    if not participants:
        return False, 'لا يوجد مشاركون في هذه الدورة'
    attendus = {p['id'] for p in participants}
    fournis = {int(k) for k in (presences or {})}
    if attendus - fournis:
        return False, 'يجب التأشير على كلّ المشاركين: حاضر أو غائب'
    if fournis - attendus:
        return False, 'قائمة الحضور تحتوي على مشارك لا ينتمي إلى هذه الدورة'

    # V2 — دورة متعدّدة الأيّام : un حاضر/غائب par مشارك ET par jour.
    jours = [j['jour'] for j in get_jours_dorra(formation_id)]
    multi = len(jours) > 1
    if multi:
        norm = {}
        for pid, v in presences.items():
            if not isinstance(v, dict):
                return False, 'يجب التأشير على حضور كلّ مشارك في كلّ يوم من أيّام الدورة'
            try:
                vj = {int(k): bool(x) for k, x in v.items()}
            except (TypeError, ValueError):
                return False, 'قائمة الحضور غير صحيحة'
            if set(jours) - set(vj):
                return False, 'يجب التأشير على حضور كلّ مشارك في كلّ يوم من أيّام الدورة'
            if set(vj) - set(jours):
                return False, 'قائمة الحضور تحتوي على يوم لا ينتمي إلى هذه الدورة'
            norm[int(pid)] = vj
        presences = norm

    classe, repart, ex_aequo, nb_p, nb_a = calculer_classe(formation_id, presences)
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    conn = get_connection()
    try:
        for pid in attendus:
            v = presences[pid]
            present = any(v.values()) if multi else bool(v)
            conn.execute(
                'INSERT INTO mustahaqqat_hodour (formation_id, participant_id, present) '
                'VALUES (?, ?, ?) '
                'ON CONFLICT(formation_id, participant_id) '
                'DO UPDATE SET present=excluded.present',
                (formation_id, pid, 1 if present else 0))
            if multi:
                for n, pj in v.items():
                    conn.execute(
                        'INSERT INTO mustahaqqat_hodour_jours (formation_id, participant_id, '
                        'jour, present) VALUES (?, ?, ?, ?) '
                        'ON CONFLICT(formation_id, participant_id, jour) '
                        'DO UPDATE SET present=excluded.present',
                        (formation_id, pid, n, 1 if pj else 0))
        conn.execute('''
            INSERT INTO mustahaqqat (formation_id, lettre_id, classe_auto,
                                     nb_presents, nb_absents, etat, hodour_at)
            VALUES (?, ?, ?, ?, ?, 'hodour', ?)
            ON CONFLICT(formation_id) DO UPDATE SET
                classe_auto = excluded.classe_auto,
                nb_presents = excluded.nb_presents,
                nb_absents  = excluded.nb_absents,
                hodour_at   = excluded.hodour_at,
                -- v1.4e : un nouveau pointage ANNULE le صنف déjà approuvé —
                -- il reposait sur l'ancienne feuille et doit être revalidé.
                classe      = CASE WHEN mustahaqqat.etat='acheve'
                                   THEN mustahaqqat.classe ELSE '' END,
                classe_at   = CASE WHEN mustahaqqat.etat='acheve'
                                   THEN mustahaqqat.classe_at ELSE NULL END,
                etat        = CASE WHEN mustahaqqat.etat='acheve'
                                   THEN mustahaqqat.etat ELSE 'hodour' END,
                -- v1.6 : « جاهز للمصادقة » tombe avec le صنف qu'il portait.
                pret_at     = CASE WHEN mustahaqqat.etat='acheve'
                                   THEN mustahaqqat.pret_at ELSE NULL END,
                pret_par    = CASE WHEN mustahaqqat.etat='acheve'
                                   THEN mustahaqqat.pret_par ELSE '' END
        ''', (formation_id, dorra['lettre_id'], classe, nb_p, nb_a, now))
        conn.commit()
    except Exception as e:
        _log.exception(f"save_hodour error: {e}")
        return False, 'خطأ في حفظ ورقة الحضور'
    finally:
        conn.close()

    resultat = {
        'classe':         classe,
        'libelle_classe': _mustahaqqat.libelle_classe(classe),
        'repartition':    repart,
        'ex_aequo':       ex_aequo,
        'nb_presents':    nb_p,
        'nb_absents':     nb_a,
    }
    if multi:
        resultat['nb_jours'] = len(jours)
        resultat['presences_jours'] = sum(1 for v in presences.values()
                                          for x in v.values() if x)
        resultat['par_jour'] = [{'jour': n, 'presents': sum(1 for v in presences.values()
                                                            if v.get(n))} for n in jours]
    return True, resultat


def confirmer_classe(formation_id, classe):
    """L'agent a approuvé le صنف proposé : il devient celui de la dorra."""
    from datetime import datetime
    if classe not in _mustahaqqat.CLASSES:
        return False, 'صنف غير معروف'
    dorra = get_dorra_mustahaqqat(formation_id)
    if not dorra:
        return False, 'الدورة غير مسجَّلة نهائيًّا في المنظومة'
    if dorra['etat'] == 'acheve':
        return False, 'مستحقّات هذه الدورة منجزة ولا يمكن تعديلها'
    if not dorra.get('mu_hodour_at'):
        return False, 'يجب التأشير على ورقة الحضور أوّلا'
    # v1.4e : le صنف approuvé est CELUI QUE LE POINTAGE A DONNÉ, et aucun
    # autre. La requête pouvait porter un صنف plus élevé (أ1 au lieu de ج) et
    # gonfler le montant — l'écran n'en propose jamais d'autre.
    if classe != (dorra.get('mu_classe_auto') or ''):
        return False, ('الصنف المُرسَل لا يطابق الصنف المحتسب من ورقة الحضور '
                       f"({dorra.get('mu_classe_auto') or '—'}).")
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    conn = get_connection()
    try:
        conn.execute("UPDATE mustahaqqat SET classe=?, classe_at=?, etat='classe', "
                     "pret_at=NULL, pret_par='' "
                     'WHERE formation_id=?', (classe, now, formation_id))
        conn.commit()
        return True, now
    except Exception as e:
        _log.exception(f"confirmer_classe error: {e}")
        return False, 'خطأ في الحفظ'
    finally:
        conn.close()


def reprendre_hodour(formation_id):
    """« رفض » sur l'écran de confirmation : on revient au pointage.
    Le صنف déjà confirmé est retiré — il ne vaut plus rien tant que la
    feuille de présence n'est pas revalidée."""
    conn = get_connection()
    try:
        conn.execute("UPDATE mustahaqqat SET classe='', classe_at=NULL, etat='hodour', "
                     "pret_at=NULL, pret_par='' "
                     "WHERE formation_id=? AND etat!='acheve'", (formation_id,))
        conn.commit()
        return True
    except Exception:
        _log.warning('reprendre_hodour : exception ignorée', exc_info=True)
        return False
    finally:
        conn.close()


# ─── الجدول المالي : المجموعات والأسعار ──────────────────────────────────────

def get_groupes_grades():
    """{رتبة : مجموعة} tel qu'il est en base. Le défaut officiel si vide."""
    conn = get_connection()
    try:
        return {r['grade']: r['groupe'] for r in conn.execute(
            'SELECT grade, groupe FROM mustahaqqat_groupes').fetchall()}
    except Exception:
        _log.warning('get_groupes_grades : exception ignorée', exc_info=True)
        return _bareme_mali.groupes_defaut()
    finally:
        conn.close()


def get_groupes_grades_detail():
    """La table رتبة → مجموعة pour l'écran des الإعدادات, dans l'ordre des
    رتب de la منظومة (hiérarchique), les رتب ajoutées ensuite à la suite."""
    table = get_groupes_grades()
    ordre = get_grades()
    connus = set(ordre)
    rangs = ordre + sorted(g for g in table if g not in connus)
    detail = []
    for g in rangs:
        groupe = table.get(g, '')
        detail.append({
            'grade': g,
            'groupe': groupe,
            'libelle_groupe': _bareme_mali.libelle_groupe(groupe, court=True),
        })
    return detail


def set_groupe_grade(grade, groupe):
    """Rattache une رتبة à une مجموعة. `groupe` vide = رتبة non rattachée."""
    groupe = (groupe or '').strip()
    if groupe and groupe not in _bareme_mali.GROUPES:
        return False
    conn = get_connection()
    try:
        conn.execute('INSERT INTO mustahaqqat_groupes (grade, groupe) VALUES (?, ?) '
                     'ON CONFLICT(grade) DO UPDATE SET groupe=excluded.groupe',
                     (grade, groupe))
        conn.commit()
        return True
    except Exception as e:
        _log.exception(f'set_groupe_grade error: {e}')
        return False
    finally:
        conn.close()


def get_bareme_mali():
    """{(مجموعة, عمود) : سعر الساعة}. Le barème officiel si la table est vide."""
    conn = get_connection()
    try:
        rows = conn.execute(
            'SELECT groupe, colonne, taux FROM mustahaqqat_bareme_mali').fetchall()
    except Exception:
        _log.warning('get_bareme_mali : exception ignorée', exc_info=True)
        return _bareme_mali.bareme_defaut()
    finally:
        conn.close()
    if not rows:
        return _bareme_mali.bareme_defaut()
    return {(r['groupe'], r['colonne']): r['taux'] for r in rows}


def set_taux_bareme_mali(groupe, colonne, taux):
    """Corrige une case du جدول المالي. Un taux vide ou nul efface la case —
    le couple cesse alors d'être payable, ce qui est dit à l'écran plutôt
    que chiffré à zéro."""
    if groupe not in _bareme_mali.GROUPES or colonne not in _bareme_mali.COLONNES:
        return False
    try:
        valeur = float(str(taux).strip().replace(',', '.')) if str(taux).strip() else 0.0
    except (TypeError, ValueError):
        return False
    if valeur < 0:
        return False
    conn = get_connection()
    try:
        conn.execute('INSERT INTO mustahaqqat_bareme_mali (groupe, colonne, taux) '
                     'VALUES (?, ?, ?) ON CONFLICT(groupe, colonne) '
                     'DO UPDATE SET taux=excluded.taux', (groupe, colonne, valeur))
        conn.commit()
        return True
    except Exception as e:
        _log.exception(f'set_taux_bareme_mali error: {e}')
        return False
    finally:
        conn.close()


def reinitialiser_bareme_mali():
    """Rend au جدول المالي ses valeurs réglementaires, rattachements compris."""
    conn = get_connection()
    try:
        for (gr, col), taux in _bareme_mali.bareme_defaut().items():
            conn.execute('INSERT INTO mustahaqqat_bareme_mali (groupe, colonne, taux) '
                         'VALUES (?, ?, ?) ON CONFLICT(groupe, colonne) '
                         'DO UPDATE SET taux=excluded.taux', (gr, col, taux))
        for libelle, groupe in _bareme_mali.groupes_defaut().items():
            conn.execute('INSERT INTO mustahaqqat_groupes (grade, groupe) VALUES (?, ?) '
                         'ON CONFLICT(grade) DO UPDATE SET groupe=excluded.groupe',
                         (libelle, groupe))
        conn.commit()
        return True
    except Exception as e:
        _log.exception(f'reinitialiser_bareme_mali error: {e}')
        return False
    finally:
        conn.close()


def get_bareme_mali_grille():
    """Le جدول المالي en grille, prêt pour l'écran : une ligne par مجموعة."""
    bareme = get_bareme_mali()
    grille = []
    for groupe in _bareme_mali.GROUPES:
        cases = []
        for colonne in _bareme_mali.COLONNES:
            taux = bareme.get((groupe, colonne))
            cases.append({
                'colonne': colonne,
                'taux': taux if taux else '',
                'texte': _bareme_mali.formater_dinars(taux) if taux else '',
            })
        grille.append({
            'groupe':  groupe,
            'libelle': _bareme_mali.libelle_groupe(groupe),
            'cases':   cases,
        })
    return grille


# ─── القيمة المالية لدورة ────────────────────────────────────────────────────

def _rows_programme(formation_id):
    """Les فقرات du برنامج d'une dorra, d'où se lisent les ساعات."""
    conn = get_connection()
    try:
        row = conn.execute('SELECT rows_json FROM programme_formations '
                           'WHERE formation_id=?', (formation_id,)).fetchone()
    except Exception:
        _log.warning('_rows_programme : exception ignorée', exc_info=True)
        return []
    finally:
        conn.close()
    if not row:
        return []
    try:
        return json.loads(row['rows_json'] or '[]')
    except (ValueError, TypeError):
        return []


def calculer_mustahaqqat(formation_id):
    """المستحقّات المالية d'une dorra : ساعات, سعر, مبلغ — et ce qui manque.

    Tant que la dorra n'est pas achevée, tout se recalcule à chaque affichage :
    un barème corrigé ou un برنامج complété se voit aussitôt. Une fois achevée,
    on relit ce qui a été arrêté — c'est la valeur qui a été approuvée, et un
    barème révisé plus tard ne doit pas la réécrire.
    """
    dorra = get_dorra_mustahaqqat(formation_id)
    if not dorra:
        return None

    if dorra.get('mu_etat') == 'acheve':
        fige = {
            'debut':   dorra.get('mu_heure_debut') or '',
            'fin':     dorra.get('mu_heure_fin') or '',
            'minutes': dorra.get('mu_minutes') or 0,
            'heures':  dorra.get('mu_heures') or 0,
            'groupe':  dorra.get('mu_groupe') or '',
            'taux':    dorra.get('mu_taux') or None,
            'montant': dorra.get('mu_montant') or None,
        }
        fige.update({
            'duree_texte':     _bareme_mali.duree_en_texte(fige['minutes']),
            'arrondi':         (fige['heures'] * 60) != fige['minutes'],
            'libelle_groupe':  _bareme_mali.libelle_groupe(fige['groupe']),
            'colonne':         _bareme_mali.colonne_de_classe(dorra.get('mu_classe')),
            'taux_texte':      _bareme_mali.formater_dinars(fige['taux']),
            'montant_texte':   _bareme_mali.formater_dinars(fige['montant']),
            'chiffrable':      True,
            'motifs':          [],
            'fige':            True,
            # V2 : détail par jour (lecture seule, relu dans le برنامج figé)
            'jours':           _bareme_mali.heures_du_programme(
                _rows_programme(formation_id)).get('jours', []),
        })
        fige['libelle_colonne'] = _bareme_mali.LIBELLES_COLONNES.get(
            fige['colonne'], '')
        return fige

    chiffrage = _bareme_mali.chiffrer(
        _rows_programme(formation_id),
        dorra.get('mu_classe') or '',
        dorra.get('grade') or '',
        bareme=get_bareme_mali(),
        groupes=get_groupes_grades())
    chiffrage['fige'] = False
    return chiffrage


def confirmer_mustahaqqat(formation_id):
    """L'agent approuve la شاشة التلخيصية : les مستحقّات sont arrêtées.

    Le chiffrage est figé en base à cet instant — ساعات, سعر et مبلغ — et la
    dorra passe en « منجزة ». Rien n'est enregistré si le calcul ne tient pas :
    mieux vaut renvoyer l'agent à ce qui manque que d'arrêter un montant faux.
    """
    from datetime import datetime
    dorra = get_dorra_mustahaqqat(formation_id)
    if not dorra:
        return False, 'الدورة غير مسجَّلة نهائيًّا في المنظومة'
    if dorra.get('mu_etat') == 'acheve':
        return False, 'مستحقّات هذه الدورة منجزة'
    if not dorra.get('mu_classe'):
        return False, 'يجب تحديد صنف الدورة أوّلا'
    # Le montant ne s'arrête que sur un صنف approuvé APRÈS le dernier pointage,
    # et identique à celui que ce pointage donne.
    if dorra.get('mu_etat') != 'classe' or \
            dorra.get('mu_classe') != (dorra.get('mu_classe_auto') or ''):
        return False, 'ورقة الحضور تغيّرت بعد تأكيد الصنف: أكّد الصنف من جديد.'

    c = calculer_mustahaqqat(formation_id)
    if not c or not c['chiffrable']:
        return False, (c['motifs'][0] if c and c['motifs']
                       else 'تعذّر احتساب المستحقّات')

    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    conn = get_connection()
    try:
        conn.execute("""UPDATE mustahaqqat
                           SET groupe=?, heure_debut=?, heure_fin=?, minutes=?,
                               heures=?, taux=?, montant=?,
                               etat='acheve', acheve_at=?
                         WHERE formation_id=?""",
                     (c['groupe'], c['debut'], c['fin'], c['minutes'],
                      c['heures'], c['taux'], c['montant'], now, formation_id))
        conn.commit()
        return True, {'acheve_at': now, 'montant': c['montant'],
                      'montant_texte': c['montant_texte'],
                      'heures': c['heures']}
    except Exception as e:
        _log.exception(f'confirmer_mustahaqqat error: {e}')
        return False, 'خطأ في الحفظ'
    finally:
        conn.close()


def rouvrir_mustahaqqat(formation_id):
    """Ramène une dorra achevée à l'étape du صنف — le chiffrage figé est
    effacé, car il ne vaut plus rien dès lors qu'on rouvre ce qui le fonde."""
    conn = get_connection()
    try:
        conn.execute("""UPDATE mustahaqqat
                           SET etat='classe', acheve_at=NULL, groupe='',
                               heure_debut='', heure_fin='', minutes=0,
                               heures=0, taux=0, montant=0,
                               pret_at=NULL, pret_par=''
                         WHERE formation_id=?""", (formation_id,))
        conn.commit()
        return True
    except Exception:
        _log.warning('rouvrir_mustahaqqat : exception ignorée', exc_info=True)
        return False
    finally:
        conn.close()


# ─── v1.6 : « جاهز للمصادقة » ────────────────────────────────────────────────

def _verifier_confirmable(dorra, c):
    """Les conditions de l'arrêt du montant, partagées par « جاهز للمصادقة »
    (l'agent) et « التأكيد النهائي » (المشرف). None si tout est prêt."""
    if not dorra:
        return 'الدورة غير مسجَّلة نهائيًّا في المنظومة'
    if dorra.get('mu_etat') == 'acheve':
        return 'مستحقّات هذه الدورة منجزة'
    if not dorra.get('mu_classe'):
        return 'يجب تحديد صنف الدورة أوّلا'
    if dorra.get('mu_etat') != 'classe' or \
            dorra.get('mu_classe') != (dorra.get('mu_classe_auto') or ''):
        return 'ورقة الحضور تغيّرت بعد تأكيد الصنف: أكّد الصنف من جديد.'
    if not c or not c['chiffrable']:
        return c['motifs'][0] if c and c['motifs'] else 'تعذّر احتساب المستحقّات'
    return None


def marquer_pret_validation(formation_id, utilisateur):
    """L'agent signale que la dorra est prête : l'مشرف العام en est averti
    sur لوحة القيادة. Renvoie (ok, pret_at | message)."""
    from datetime import datetime
    dorra = get_dorra_mustahaqqat(formation_id)
    motif = _verifier_confirmable(dorra, calculer_mustahaqqat(formation_id) if dorra else None)
    if motif:
        return False, motif
    if dorra.get('mu_pret_at'):
        return True, dorra['mu_pret_at']
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    conn = get_connection()
    try:
        conn.execute('UPDATE mustahaqqat SET pret_at=?, pret_par=? WHERE formation_id=?',
                     (now, utilisateur or '', formation_id))
        conn.commit()
        return True, now
    except Exception as e:
        _log.exception(f'marquer_pret_validation error: {e}')
        return False, 'خطأ في الحفظ'
    finally:
        conn.close()


def dorrat_pretes_validation():
    """Les dorrat signalées « جاهز للمصادقة » et pas encore arrêtées."""
    return [d for d in _dorrat_mustahaqqat(achevees=False) if d['pret']]
