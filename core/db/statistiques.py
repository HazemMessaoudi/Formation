# -*- coding: utf-8 -*-
"""لوحة القيادة و الإحصائيات.

Extrait de core/database.py (v1.4) — importer depuis core.database, qui
ré-exporte tout : les appelants existants restent inchangés."""

from core import mustahaqqat as _mustahaqqat
from core import bareme_mali as _bareme_mali
from core import validation as _validation

from core.db._base import _log, get_connection
from core.db.mustahaqqat import get_bareme_grades


# ─── Stats ────────────────────────────────────────────────────────────────────

def get_stats():
    conn = get_connection()
    stats = {}
    stats['lettres_total'] = conn.execute('SELECT COUNT(*) FROM lettres').fetchone()[0]
    stats['lettres_interne'] = conn.execute("SELECT COUNT(*) FROM lettres WHERE type='interne'").fetchone()[0]
    stats['lettres_externe'] = conn.execute("SELECT COUNT(*) FROM lettres WHERE type='externe'").fetchone()[0]
    stats['formations_total'] = conn.execute('SELECT COUNT(*) FROM formations').fetchone()[0]
    stats['mkowin_total'] = conn.execute('SELECT COUNT(*) FROM mkowin').fetchone()[0]
    stats['mawad_total'] = conn.execute('SELECT COUNT(*) FROM mawad').fetchone()[0]
    conn.close()
    return stats


# ─── لوحة القيادة و الإحصائيات ───────────────────────────────────────────────

def get_stats_mustahaqqat():
    """Chiffres de l'écran d'accueil des مستحقّات."""
    conn = get_connection()
    try:
        def un(sql, *args):
            try:
                return conn.execute(sql, args).fetchone()[0] or 0
            except Exception:
                _log.warning('un : exception ignorée', exc_info=True)
                return 0

        enregistrees = un("SELECT COUNT(*) FROM memo_formations "
                          "WHERE finalise_at IS NOT NULL AND finalise_at != ''")
        achevees = un('''SELECT COUNT(*) FROM mustahaqqat
                         WHERE acheve_at IS NOT NULL AND acheve_at != '' ''')
        en_cours = un("SELECT COUNT(*) FROM mustahaqqat WHERE etat IN ('hodour','classe')")
        stats = {
            'dorrat_enregistrees': enregistrees,
            'dorrat_manjaza':      achevees,
            'dorrat_ghayr':        max(enregistrees - achevees, 0),
            'dorrat_en_cours':     en_cours,
            'presents':            un('SELECT SUM(nb_presents) FROM mustahaqqat'),
            'absents':             un('SELECT SUM(nb_absents) FROM mustahaqqat'),
            'formateurs': un('''SELECT COUNT(DISTINCT TRIM(f.nom_formateur))
                                FROM formations f
                                JOIN memo_formations m ON m.formation_id = f.id
                                WHERE m.finalise_at IS NOT NULL AND m.finalise_at != ''
                                  AND TRIM(COALESCE(f.nom_formateur,'')) != '' '''),
        }
        stats['par_classe'] = {c: 0 for c in _mustahaqqat.CLASSES}
        for r in conn.execute("SELECT classe, COUNT(*) n FROM mustahaqqat "
                              "WHERE classe != '' GROUP BY classe").fetchall():
            if r['classe'] in stats['par_classe']:
                stats['par_classe'][r['classe']] = r['n']

        # Les montants ne se comptent que sur les dorrat ACHEVÉES : ailleurs
        # ils ne sont qu'une estimation, et une estimation affichée en tête de
        # لوحة القيادة devient vite un chiffre qu'on cite.
        stats['heures_payees'] = un(
            "SELECT SUM(heures) FROM mustahaqqat WHERE etat='acheve'")
        stats['montant_total'] = un(
            "SELECT SUM(montant) FROM mustahaqqat WHERE etat='acheve'")
        stats['montant_texte'] = _bareme_mali.formater_dinars(
            stats['montant_total']) if stats['montant_total'] else '0.000'
        return stats
    finally:
        conn.close()


def get_formateurs_mustahaqqat():
    """« قائمة الأسماء » de la section مستحقّات : les مكوّنون qui ont
    effectivement animé une dorra enregistrée, avec leur volume d'activité."""
    conn = get_connection()
    try:
        rows = conn.execute('''
            SELECT TRIM(f.nom_formateur)  AS nom_formateur,
                   MAX(COALESCE(f.grade,''))        AS grade,
                   MAX(COALESCE(f.lieu_travail,'')) AS lieu_travail,
                   COUNT(*)                         AS nb_dorrat,
                   SUM(CASE WHEN mu.acheve_at IS NOT NULL AND mu.acheve_at != ''
                            THEN 1 ELSE 0 END)      AS nb_manjaza,
                   MAX(f.date_formation)            AS derniere_dorra
            FROM formations f
            JOIN memo_formations m ON m.formation_id = f.id
            LEFT JOIN mustahaqqat mu ON mu.formation_id = f.id
            WHERE m.finalise_at IS NOT NULL AND m.finalise_at != ''
              AND TRIM(COALESCE(f.nom_formateur,'')) != ''
            GROUP BY TRIM(f.nom_formateur)
            ORDER BY nb_dorrat DESC, nom_formateur
        ''').fetchall()
        formateurs = []
        for r in rows:
            d = dict(r)
            d['nb_restantes'] = max((d['nb_dorrat'] or 0) - (d['nb_manjaza'] or 0), 0)
            mk = conn.execute(
                'SELECT id, grade, sexe, jiha_marjiiya, lieu_travail '
                "FROM mkowin WHERE TRIM(nom || ' ' || COALESCE(prenom,'')) = ? "
                'LIMIT 1', (d['nom_formateur'],)).fetchone()
            d['mkow'] = dict(mk) if mk else None
            formateurs.append(d)
        return formateurs
    finally:
        conn.close()


def get_stats_avancees():
    """Tout ce que l'écran « إحصائيات » montre du centre."""
    conn = get_connection()
    try:
        def un(sql, *args):
            try:
                return conn.execute(sql, args).fetchone()[0] or 0
            except Exception:
                _log.warning('un : exception ignorée', exc_info=True)
                return 0

        def paires(sql, *args):
            try:
                return [(r[0] or 'غير محدّد', r[1] or 0)
                        for r in conn.execute(sql, args).fetchall()]
            except Exception:
                _log.warning('paires : exception ignorée', exc_info=True)
                return []

        s = {}
        s['programmes']       = un("SELECT COUNT(*) FROM lettres "
                                   "WHERE categorie='programme' OR categorie IS NULL")
        s['programmes_confirmes'] = un("SELECT COUNT(*) FROM lettres WHERE verrouille=1 "
                                       "AND (categorie='programme' OR categorie IS NULL)")
        s['dorrat']           = un('SELECT COUNT(*) FROM formations')
        s['dorrat_finalisees'] = un("SELECT COUNT(*) FROM memo_formations "
                                    "WHERE finalise_at IS NOT NULL AND finalise_at != ''")
        s['participations']   = un('SELECT COUNT(*) FROM participants')
        s['participants_uniques'] = un('''SELECT COUNT(*) FROM (
                                            SELECT DISTINCT TRIM(nom_prenom) FROM participants
                                            WHERE TRIM(COALESCE(nom_prenom,'')) != '')''')
        s['mkowin']           = un('SELECT COUNT(*) FROM mkowin')
        s['mawad']            = un('SELECT COUNT(*) FROM mawad')
        s['jihat']            = un('SELECT COUNT(*) FROM jihat')
        s['lettres_libres']   = un("SELECT COUNT(*) FROM lettres WHERE categorie='libre'")
        s['moyenne_participants'] = round(
            (s['participations'] / s['dorrat']), 1) if s['dorrat'] else 0

        # المشاركون حسب الصنف — calculé sur les رتب réelles des مشاركين.
        bareme = _mustahaqqat.preparer_bareme(get_bareme_grades())
        repart = {c: 0 for c in _mustahaqqat.CLASSES}
        non_classes = 0
        for r in conn.execute('SELECT grade, COUNT(*) n FROM participants '
                              'GROUP BY grade').fetchall():
            classe = _mustahaqqat.classe_du_grade(r['grade'], bareme)
            if classe in repart:
                repart[classe] += r['n']
            else:
                non_classes += r['n']
        s['par_classe'] = repart
        s['non_classes'] = non_classes

        # الجنس — connu pour les مكوّنون ; « غير محدّد » sinon, sans deviner.
        s['par_sexe'] = paires("SELECT CASE WHEN TRIM(COALESCE(sexe,''))='' "
                               "THEN 'غير محدّد' ELSE sexe END, COUNT(*) "
                               'FROM mkowin GROUP BY 1 ORDER BY 2 DESC')

        # v1.6 — الجنس / الفئة العمريّة (affichés seulement à la demande).
        # Ordre fixe : les deux options, puis « غير محدّد » s'il y en a.
        def repartition(table, col, options):
            compte = dict(paires(f"SELECT TRIM(COALESCE({col},'')), COUNT(*) "
                                 f'FROM {table} GROUP BY 1'))
            res = [(o, compte.pop(o, 0)) for o in options]
            reste = sum(compte.values())
            if reste:
                res.append(('غير محدّد', reste))
            return res
        s['par_sexe_participants'] = repartition('participants', 'sexe', _validation.SEXES)
        s['par_fiaa_participants'] = repartition('participants', 'fiaa_omria', _validation.FIAAT)
        s['par_sexe_mkowin'] = repartition('mkowin', 'sexe', _validation.SEXES)
        s['par_fiaa_mkowin'] = repartition('mkowin', 'fiaa_omria', _validation.FIAAT)

        s['par_grade'] = paires('''SELECT grade, COUNT(*) n FROM participants
                                   WHERE TRIM(COALESCE(grade,'')) != ''
                                   GROUP BY grade ORDER BY n DESC LIMIT 12''')
        s['par_jiha'] = paires('''SELECT jiha_marjiiya, COUNT(*) n FROM participants
                                  WHERE TRIM(COALESCE(jiha_marjiiya,'')) != ''
                                  GROUP BY jiha_marjiiya ORDER BY n DESC LIMIT 10''')
        s['par_lieu'] = paires('''SELECT lieu_formation, COUNT(*) n FROM formations
                                  WHERE TRIM(COALESCE(lieu_formation,'')) != ''
                                  GROUP BY lieu_formation ORDER BY n DESC LIMIT 10''')
        s['par_formateur'] = paires('''SELECT TRIM(nom_formateur), COUNT(*) n
                                       FROM formations
                                       WHERE TRIM(COALESCE(nom_formateur,'')) != ''
                                       GROUP BY TRIM(nom_formateur)
                                       ORDER BY n DESC LIMIT 10''')
        s['par_madda'] = paires('''SELECT titre, COUNT(*) n FROM formations
                                   WHERE TRIM(COALESCE(titre,'')) != ''
                                   GROUP BY titre ORDER BY n DESC LIMIT 10''')
        # Les mois sont rendus dans l'ordre du calendrier, pas par volume :
        # une courbe d'activité annuelle ne se lit pas triée par fréquence.
        _mois_ordre = ['جانفي', 'فيفري', 'مارس', 'أفريل', 'ماي', 'جوان',
                       'جويلية', 'أوت', 'سبتمبر', 'أكتوبر', 'نوفمبر', 'ديسمبر']
        _par_mois = dict(paires('''SELECT mois, COUNT(*) n FROM lettres
                                   WHERE (categorie='programme' OR categorie IS NULL)
                                   GROUP BY mois'''))
        s['par_mois'] = [(m, _par_mois.get(m, 0)) for m in _mois_ordre]
        for _m_autre, _n in _par_mois.items():
            if _m_autre not in _mois_ordre:
                s['par_mois'].append((_m_autre, _n))
        s['par_annee'] = paires('''SELECT annee, COUNT(f.id) n
                                   FROM lettres l LEFT JOIN formations f ON f.lettre_id=l.id
                                   WHERE (l.categorie='programme' OR l.categorie IS NULL)
                                   GROUP BY annee ORDER BY annee''')
        s['par_type_formation'] = paires('''SELECT type_formation, COUNT(*) n FROM mawad
                                            GROUP BY type_formation ORDER BY n DESC''')
        return s
    finally:
        conn.close()
