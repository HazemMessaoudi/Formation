# -*- coding: utf-8 -*-
"""لوحة القيادة (v1.5 — D2) et التقرير السنوي (v1.5 — D1).

Règles de comptage — les mêmes partout, pour qu'un chiffre de la لوحة
القيادة et le même chiffre du تقرير ne divergent jamais :

• Une دورة appartient à l'année et au mois de SON برنامج (lettres.annee /
  lettres.mois) — la date de la دورة tombe toujours dans ce mois (règle
  d'invariance du programme).
• Seuls les برامج تكوين comptent (categorie 'programme' ou NULL), jamais les
  مراسلات حرّة.
• Heures et montants : uniquement les المستحقّات ACHEVÉES (montant arrêté et
  approuvé) — une estimation ne figure jamais dans un rapport.
"""
from datetime import date, timedelta

from core.arabe import MOIS_AR
from core.db._base import get_connection, _log
from core import etats as _etats
from core import validation as _validation

_PROGRAMME = "(l.categorie = 'programme' OR l.categorie IS NULL)"


def _un(conn, sql, *args):
    try:
        v = conn.execute(sql, args).fetchone()[0]
        return v or 0
    except Exception:
        _log.warning('rapports._un : exception ignorée', exc_info=True)
        return 0


# ─── D2 : لوحة القيادة ──────────────────────────────────────────────────────

def donnees_tableau_de_bord(aujourdhui=None, horizon_jours=30):
    """Ce qui demande l'attention MAINTENANT, et l'activité de l'année."""
    j = aujourdhui or date.today()
    fin = j + timedelta(days=horizon_jours)
    conn = get_connection()
    try:
        # Programmes inachevés, avec leur plus ancienne دورة non enregistrée.
        inacheves = [dict(r) for r in conn.execute(f'''
            SELECT l.id, l.mois, l.annee, l.verrouille,
                   COUNT(f.id) AS nb_formations,
                   GROUP_CONCAT(f.titre, ' | ') AS titres,
                   SUM(CASE WHEN mf.finalise_at IS NOT NULL AND mf.finalise_at != ''
                            THEN 1 ELSE 0 END) AS nb_finalisees,
                   MIN(CASE WHEN mf.finalise_at IS NULL OR mf.finalise_at = ''
                            THEN NULLIF(f.date_formation, '') END) AS date_ouverte
            FROM lettres l
            LEFT JOIN formations f ON f.lettre_id = l.id
            LEFT JOIN memo_formations mf ON mf.formation_id = f.id
            WHERE {_PROGRAMME}
            GROUP BY l.id
            HAVING (COUNT(f.id) = 0) OR (nb_finalisees < COUNT(f.id))
        ''').fetchall()]
        en_retard = [p for p in inacheves if _etats.programme_en_retard(p, j)]
        brouillons = sum(1 for p in inacheves if not p['verrouille'])

        a_venir = [dict(r) for r in conn.execute(f'''
            SELECT f.id, f.lettre_id, f.titre, f.date_formation, f.periode, f.grade,
                   f.nom_formateur, f.lieu_formation,
                   (SELECT COUNT(*) FROM participants p
                     WHERE p.formation_id = f.id AND p.lettre_id = f.lettre_id) AS nb_participants,
                   l.verrouille
            FROM formations f JOIN lettres l ON l.id = f.lettre_id
            WHERE {_PROGRAMME} AND f.date_formation >= ? AND f.date_formation <= ?
              AND length(f.date_formation) = 10
            ORDER BY f.date_formation, f.id
            LIMIT 12
        ''', (j.isoformat(), fin.isoformat())).fetchall()]
        for d in a_venir:
            d['dans_jours'] = (date.fromisoformat(d['date_formation']) - j).days

        attente_mustahaqqat = _un(conn, '''
            SELECT COUNT(*) FROM memo_formations m
            LEFT JOIN mustahaqqat mu ON mu.formation_id = m.formation_id
            WHERE m.finalise_at IS NOT NULL AND m.finalise_at != ''
              AND COALESCE(mu.etat, '') != 'acheve' ''')
        numeros_reserves = _un(conn, '''
            SELECT COUNT(*) FROM registre WHERE statut = 'provisoire' AND annee = ?''', j.year)

        par_mois = _par_mois(conn, j.year)
    finally:
        conn.close()
    # v1.6 — دورات signalées « جاهز للمصادقة » : l'alerte du مشرف عام.
    from core.db.mustahaqqat import dorrat_pretes_validation
    try:
        pret_validation = [{'id': d['id'], 'titre': d.get('titre', ''),
                            'date_formation': d.get('date_formation', ''),
                            'pret_par': d.get('mu_pret_par') or '',
                            'pret_at': d.get('mu_pret_at') or ''}
                           for d in dorrat_pretes_validation()]
    except Exception:
        _log.warning('tableau de bord : pret_validation ignoré', exc_info=True)
        pret_validation = []
    return {
        'aujourdhui': j.isoformat(),
        'pret_validation': pret_validation,
        'annee': j.year,
        'en_retard': en_retard,
        'brouillons': brouillons,
        'a_venir': a_venir,
        'horizon_jours': horizon_jours,
        'attente_mustahaqqat': attente_mustahaqqat,
        'numeros_reserves': numeros_reserves,
        'par_mois': par_mois,
        'dorrat_annee': sum(m['dorrat'] for m in par_mois),
        'participants_annee': sum(m['participants'] for m in par_mois),
    }


def _par_mois(conn, annee):
    """12 lignes (جانفي → ديسمبر) : دورات, مسجّلة نهائيًّا, مشاركون, ساعات, مبلغ."""
    lignes = {m: {'mois': m, 'rang': i + 1, 'dorrat': 0, 'finalisees': 0, 'participants': 0,
                  'heures': 0, 'montant': 0.0}
              for i, m in enumerate(MOIS_AR)}
    for r in conn.execute(f'''
        SELECT l.mois,
               COUNT(f.id) AS dorrat,
               SUM(CASE WHEN mf.finalise_at IS NOT NULL AND mf.finalise_at != '' THEN 1 ELSE 0 END) AS finalisees,
               SUM((SELECT COUNT(*) FROM participants p
                     WHERE p.formation_id = f.id AND p.lettre_id = f.lettre_id)) AS participants,
               SUM(CASE WHEN mu.etat = 'acheve' THEN mu.heures ELSE 0 END) AS heures,
               SUM(CASE WHEN mu.etat = 'acheve' THEN mu.montant ELSE 0 END) AS montant
        FROM lettres l
        JOIN formations f ON f.lettre_id = l.id
        LEFT JOIN memo_formations mf ON mf.formation_id = f.id
        LEFT JOIN mustahaqqat mu ON mu.formation_id = f.id
        WHERE {_PROGRAMME} AND l.annee = ?
        GROUP BY l.mois
    ''', (annee,)).fetchall():
        if r['mois'] in lignes:
            lignes[r['mois']].update(dorrat=r['dorrat'] or 0, finalisees=r['finalisees'] or 0,
                                     participants=r['participants'] or 0,
                                     heures=r['heures'] or 0, montant=float(r['montant'] or 0))
    return [lignes[m] for m in MOIS_AR]


# ─── D1 : التقرير السنوي ────────────────────────────────────────────────────

def annees_rapport():
    """Années ayant au moins un برنامج, la plus récente d'abord ; l'année en
    cours figure toujours (un rapport vide reste consultable)."""
    conn = get_connection()
    try:
        ans = {r[0] for r in conn.execute(
            f'SELECT DISTINCT l.annee FROM lettres l WHERE {_PROGRAMME} AND l.annee IS NOT NULL'
        ).fetchall() if r[0]}
    finally:
        conn.close()
    ans.add(date.today().year)
    return sorted((int(a) for a in ans), reverse=True)


def rapport_annuel(annee):
    annee = int(annee)
    conn = get_connection()
    try:
        par_mois = _par_mois(conn, annee)
        t = {
            'programmes': _un(conn, f'SELECT COUNT(*) FROM lettres l WHERE {_PROGRAMME} AND l.annee=?', annee),
            'programmes_confirmes': _un(conn, f'SELECT COUNT(*) FROM lettres l WHERE {_PROGRAMME} '
                                              'AND l.annee=? AND l.verrouille=1', annee),
            'dorrat': sum(m['dorrat'] for m in par_mois),
            'finalisees': sum(m['finalisees'] for m in par_mois),
            'participations': sum(m['participants'] for m in par_mois),
            'heures': sum(m['heures'] for m in par_mois),
            'montant': round(sum(m['montant'] for m in par_mois), 3),
            'participants_uniques': _un(conn, f'''
                SELECT COUNT(*) FROM (SELECT DISTINCT COALESCE(NULLIF(TRIM(p.identifiant_unique), ''),
                                                                TRIM(p.nom_prenom))
                FROM participants p JOIN lettres l ON l.id = p.lettre_id
                WHERE {_PROGRAMME} AND l.annee = ? AND TRIM(COALESCE(p.nom_prenom, '')) != '')''', annee),
            'formateurs': _un(conn, f'''
                SELECT COUNT(DISTINCT TRIM(f.nom_formateur)) FROM formations f
                JOIN lettres l ON l.id = f.lettre_id
                WHERE {_PROGRAMME} AND l.annee = ? AND TRIM(COALESCE(f.nom_formateur, '')) != '' ''', annee),
            'dorrat_payees': _un(conn, f'''
                SELECT COUNT(*) FROM mustahaqqat mu JOIN formations f ON f.id = mu.formation_id
                JOIN lettres l ON l.id = f.lettre_id
                WHERE {_PROGRAMME} AND l.annee = ? AND mu.etat = 'acheve' ''', annee),
            'libres': _un(conn, "SELECT COUNT(*) FROM lettres WHERE categorie='libre' AND annee=?", annee),
            'registre_interne': _un(conn, "SELECT COUNT(*) FROM registre WHERE annee=? AND type='interne'", annee),
            'registre_externe': _un(conn, "SELECT COUNT(*) FROM registre WHERE annee=? AND type='externe'", annee),
        }
        t['moyenne_participants'] = round(t['participations'] / t['dorrat'], 1) if t['dorrat'] else 0

        par_formateur = [dict(r) for r in conn.execute(f'''
            SELECT TRIM(f.nom_formateur) AS nom, MAX(f.grade) AS grade,
                   COUNT(f.id) AS dorrat,
                   SUM(CASE WHEN mu.etat = 'acheve' THEN mu.heures ELSE 0 END) AS heures,
                   SUM(CASE WHEN mu.etat = 'acheve' THEN mu.montant ELSE 0 END) AS montant
            FROM formations f JOIN lettres l ON l.id = f.lettre_id
            LEFT JOIN mustahaqqat mu ON mu.formation_id = f.id
            WHERE {_PROGRAMME} AND l.annee = ? AND TRIM(COALESCE(f.nom_formateur, '')) != ''
            GROUP BY TRIM(f.nom_formateur)
            ORDER BY dorrat DESC, heures DESC, nom
        ''', (annee,)).fetchall()]
        par_madda = [dict(r) for r in conn.execute(f'''
            SELECT f.titre AS titre, COUNT(f.id) AS dorrat,
                   SUM((SELECT COUNT(*) FROM participants p
                         WHERE p.formation_id = f.id AND p.lettre_id = f.lettre_id)) AS participants
            FROM formations f JOIN lettres l ON l.id = f.lettre_id
            WHERE {_PROGRAMME} AND l.annee = ? AND TRIM(COALESCE(f.titre, '')) != ''
            GROUP BY f.titre ORDER BY dorrat DESC, participants DESC, titre
        ''', (annee,)).fetchall()]
        par_jiha = [dict(r) for r in conn.execute(f'''
            SELECT COALESCE(NULLIF(TRIM(p.jiha_marjiiya), ''), 'غير محدّدة') AS jiha, COUNT(*) AS participants
            FROM participants p JOIN lettres l ON l.id = p.lettre_id
            WHERE {_PROGRAMME} AND l.annee = ?
            GROUP BY 1 ORDER BY participants DESC, jiha
        ''', (annee,)).fetchall()]
        # v1.6.1 — المشاركون حسب الجنس : ذكر، أنثى، puis « غير محدّد » s'il y en a.
        compte = {r['sexe']: dict(r) for r in conn.execute(f'''
            SELECT COALESCE(NULLIF(TRIM(p.sexe), ''), 'غير محدّد') AS sexe,
                   COUNT(*) AS participations,
                   COUNT(DISTINCT COALESCE(NULLIF(TRIM(p.identifiant_unique), ''),
                                           TRIM(p.nom_prenom))) AS uniques
            FROM participants p JOIN lettres l ON l.id = p.lettre_id
            WHERE {_PROGRAMME} AND l.annee = ? AND TRIM(COALESCE(p.nom_prenom, '')) != ''
            GROUP BY 1
        ''', (annee,)).fetchall()}
        par_sexe = [compte.pop(sx, {'sexe': sx, 'participations': 0, 'uniques': 0})
                    for sx in _validation.SEXES]
        reste = [v for v in compte.values()]
        if reste:
            par_sexe.append({'sexe': 'غير محدّد',
                             'participations': sum(v['participations'] for v in reste),
                             'uniques': sum(v['uniques'] for v in reste)})
        total_p = sum(x['participations'] for x in par_sexe)
        for x in par_sexe:
            x['part'] = round(100 * x['participations'] / total_p, 1) if total_p else 0
    finally:
        conn.close()
    return {'annee': annee, 'totaux': t, 'par_mois': par_mois, 'par_formateur': par_formateur,
            'par_madda': par_madda, 'par_jiha': par_jiha, 'par_sexe': par_sexe}


# ─── V3 : paramètres annuels (عدد الدّورات المبرمجة → نسبة الإنجاز) ─────────

def get_parametres_annuels():
    """[{annee, nb_dorrat_programmees, date_maj}] de la plus récente à la plus ancienne."""
    conn = get_connection()
    try:
        return [dict(r) for r in conn.execute(
            'SELECT annee, nb_dorrat_programmees, date_maj FROM parametres_annuels '
            'ORDER BY annee DESC')]
    finally:
        conn.close()


def get_nb_programmees(annee):
    """Nombre de دورات programmées pour l'année (0 si non renseigné)."""
    conn = get_connection()
    try:
        r = conn.execute('SELECT nb_dorrat_programmees FROM parametres_annuels WHERE annee=?',
                         (int(annee),)).fetchone()
        return int(r[0] or 0) if r else 0
    finally:
        conn.close()


def set_parametre_annuel(annee, nb):
    """Crée ou met à jour l'année. Renvoie False si les valeurs sont invalides."""
    try:
        annee, nb = int(annee), int(nb)
    except (TypeError, ValueError):
        return False
    if not (2000 <= annee <= 2100) or not (0 <= nb <= 9999):
        return False
    from datetime import datetime
    conn = get_connection()
    try:
        conn.execute(
            'INSERT INTO parametres_annuels (annee, nb_dorrat_programmees, date_maj) VALUES (?,?,?) '
            'ON CONFLICT(annee) DO UPDATE SET nb_dorrat_programmees=excluded.nb_dorrat_programmees, '
            'date_maj=excluded.date_maj',
            (annee, nb, datetime.now().strftime('%Y-%m-%d %H:%M')))
        conn.commit()
        return True
    finally:
        conn.close()


def supprimer_parametre_annuel(annee):
    try:
        annee = int(annee)
    except (TypeError, ValueError):
        return False
    conn = get_connection()
    try:
        n = conn.execute('DELETE FROM parametres_annuels WHERE annee=?', (annee,)).rowcount
        conn.commit()
        return n > 0
    finally:
        conn.close()
