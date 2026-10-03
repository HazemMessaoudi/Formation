# -*- coding: utf-8 -*-
"""V3 — moteur de calcul du module « التّقارير » (lecture seule).

Ce module ne fait QUE lire la base : aucun برنامج, aucune دورة n'est modifié.
Il vit hors de core/db/ (la façade core.database garde sa liste de modules
figée) et produit un dictionnaire unique consommé par le تقرير كتابي
(PDF/Word), le تقرير البياني et les exports Excel.

Règles de comptage (identiques à core/db/rapports.py) :

• Une دورة appartient à l'année et au mois de SON برنامج (lettres.annee /
  lettres.mois) ; pour une « فترة محدّدة » on filtre sur date_formation.
• Seuls les برامج تكوين comptent (categorie 'programme' ou NULL).
• Nشاط منجز = دورة « مسجّلة نهائيًّا » (memo_formations.finalise_at) ; le
  critère 'toutes' compte aussi les autres, et `non_finalisees` permet à
  l'écran d'avertir l'utilisateur.
• مدّة التّكوين = core.jours.nombre_de_jours(date_formation, date_fin)
  (les dimanches ne comptent pas).
• المشاركون = participations (une ligne par دورة), clé unique pour les
  « مشاركون فعليّون ».
• الغيابات = présence explicitement notée 0 dans mustahaqqat_hodour ; un
  participant sans ligne de حضور est compté حاضر (comme get_hodour).
• Heures / montants : uniquement les المستحقّات achevées.
"""
from datetime import date
from importlib import import_module

from core.arabe import MOIS_AR
import_module('core.database')  # la façade doit être chargée (core.db._base s'y réfère)
from core.db._base import get_connection, _log
from core import classification as _cls
from core import validation as _validation
from core import jours as _jours
from core import bareme_mali as _bareme
from core.mustahaqqat import normaliser_grade

_PROGRAMME = "(l.categorie = 'programme' OR l.categorie IS NULL)"

# ─── Périodes ───────────────────────────────────────────────────────────────

TYPES_PERIODE = ('trimestre', 'semestre', 'annee', 'plage')
ORDINAUX_TRIMESTRE = {1: 'الأوّل', 2: 'الثّاني', 3: 'الثّالث', 4: 'الرّابع'}
ORDINAUX_SEMESTRE = {1: 'الأوّل', 2: 'الثّاني'}
NON_DEFINI = 'غير محدّد'

# Catégories de رتب — المشاركون (colonnes du modèle officiel)
P_OFFICIERS, P_SOUS_OFF, P_RAQIB, P_AUTRES = 'ضبّاط', 'ضبّاط صفّ', 'رقباء', 'آخرون'
CATEGORIES_PARTICIPANTS = (P_OFFICIERS, P_SOUS_OFF, P_RAQIB, P_AUTRES)
# Catégories de رتب — المكوّنون
F_SUPERIEURS, F_SUBALTERNES, F_SOUS_OFF, F_CIVILS = 'ضبّاط سامون', 'ضبّاط أعوان', 'ضبّاط صفّ', 'مدنيّين'
CATEGORIES_FORMATEURS = (F_SUPERIEURS, F_SUBALTERNES, F_SOUS_OFF, F_CIVILS)


def _fr(d):
    """ISO → jj/mm/aaaa (libellés)."""
    d = _jours.lire(d)
    return d.strftime('%d/%m/%Y') if d else ''


def bornes_periode(annee=None, type_periode='annee', n=None, debut=None, fin=None):
    """Décrit une période de تقرير.

    Rend {type, annee, n, mois:[...], debut, fin, libelle, libelle_court} ;
    `mois` (noms MOIS_AR) sert aux périodes calendaires, `debut`/`fin` (ISO)
    à la « فترة محدّدة ». Lève ValueError pour une période incohérente."""
    t = type_periode or 'annee'
    if t not in TYPES_PERIODE:
        raise ValueError('نوع فترة غير معروف')
    if t == 'plage':
        d0, d1 = _jours.lire(debut), _jours.lire(fin)
        if not d0 or not d1 or d1 < d0:
            raise ValueError('فترة غير صالحة')
        return {'type': t, 'annee': d0.year, 'n': None, 'mois': [],
                'debut': d0.isoformat(), 'fin': d1.isoformat(),
                'libelle': f'الفترة من {_fr(d0.isoformat())} إلى {_fr(d1.isoformat())}',
                'libelle_court': f'{_fr(d0.isoformat())} ← {_fr(d1.isoformat())}'}
    try:
        annee = int(annee)
    except (TypeError, ValueError):
        raise ValueError('سنة غير صالحة')
    if not 2000 <= annee <= 2100:
        raise ValueError('سنة غير صالحة')
    if t == 'trimestre':
        n = int(n or 0)
        if n not in ORDINAUX_TRIMESTRE:
            raise ValueError('ثلاثي غير صالح')
        mois = MOIS_AR[(n - 1) * 3: n * 3]
        lib = f'الثّلاثي {ORDINAUX_TRIMESTRE[n]} من سنة {annee}'
        court = f'ث{n} {annee}'
    elif t == 'semestre':
        n = int(n or 0)
        if n not in ORDINAUX_SEMESTRE:
            raise ValueError('سداسي غير صالح')
        mois = MOIS_AR[(n - 1) * 6: n * 6]
        lib = f'السّداسي {ORDINAUX_SEMESTRE[n]} من سنة {annee}'
        court = f'س{n} {annee}'
    else:
        n, mois = None, list(MOIS_AR)
        lib, court = f'سنة {annee}', str(annee)
    i0, i1 = MOIS_AR.index(mois[0]) + 1, MOIS_AR.index(mois[-1]) + 1
    fin_mois = date(annee + (i1 == 12), (i1 % 12) + 1, 1).toordinal() - 1
    return {'type': t, 'annee': annee, 'n': n, 'mois': list(mois),
            'debut': date(annee, i0, 1).isoformat(),
            'fin': date.fromordinal(fin_mois).isoformat(),
            'libelle': lib, 'libelle_court': court}


def meme_periode(periode, decalage):
    """La même période `decalage` années plus tôt (comparaisons)."""
    if periode['type'] == 'plage':
        def recul(iso):
            d = _jours.lire(iso)
            try:
                return d.replace(year=d.year - decalage).isoformat()
            except ValueError:            # 29 février
                return d.replace(year=d.year - decalage, day=28).isoformat()
        return bornes_periode(type_periode='plage', debut=recul(periode['debut']),
                              fin=recul(periode['fin']))
    return bornes_periode(periode['annee'] - decalage, periode['type'], periode['n'])


# ─── Classements des رتب ────────────────────────────────────────────────────

def _table_groupes(conn):
    try:
        brute = {r['grade']: r['groupe'] for r in
                 conn.execute('SELECT grade, groupe FROM mustahaqqat_groupes')}
    except Exception:
        _log.warning('rapports_moteur : mustahaqqat_groupes illisible', exc_info=True)
        brute = {}
    return _bareme.preparer_groupes(brute or _bareme.groupes_defaut())


def _est_raqib(cle):
    return cle.startswith('رقيب')


def _est_civil(cle):
    return cle in ('سيد', 'سيده', 'انسه')


def categorie_participant(grade, table):
    """ضبّاط (I/II/III), ضبّاط صفّ (IV), رقباء, آخرون."""
    g = _bareme.groupe_du_grade(grade, table)
    if g in ('I', 'II', 'III'):
        return P_OFFICIERS
    if g == 'IV':
        return P_SOUS_OFF
    return P_RAQIB if _est_raqib(normaliser_grade(grade)) else P_AUTRES


def categorie_formateur(grade, table):
    """ضبّاط سامون (I/II), ضبّاط أعوان (III), ضبّاط صفّ (IV + رقباء), مدنيّين."""
    g = _bareme.groupe_du_grade(grade, table)
    if g in ('I', 'II'):
        return F_SUPERIEURS
    if g == 'III':
        return F_SUBALTERNES
    if g == 'IV' or _est_raqib(normaliser_grade(grade)):
        return F_SOUS_OFF
    return F_CIVILS


def _sexe(v):
    v = str(v or '').strip()
    return v if v in _validation.SEXES else NON_DEFINI


def _fiaa(v):
    v = str(v or '').strip()
    return v if v in _validation.FIAAT else NON_DEFINI


def _nom_norm(nom):
    return ' '.join(str(nom or '').split())


def _index_mkowin(conn):
    """{forme du nom : [fiches]} — « nom », « nom prénom », « prénom nom »."""
    index = {}
    try:
        rows = conn.execute('SELECT nom, prenom, grade, sexe, fiaa_omria FROM mkowin').fetchall()
    except Exception:
        _log.warning('rapports_moteur : mkowin illisible', exc_info=True)
        rows = []
    for r in rows:
        d = dict(r)
        n, p = _nom_norm(d.get('nom')), _nom_norm(d.get('prenom'))
        for forme in {n, f'{n} {p}'.strip(), f'{p} {n}'.strip()}:
            if forme:
                index.setdefault(forme, []).append(d)
    return index


def _fiche_mkow(index, nom, grade):
    cands = index.get(_nom_norm(nom), [])
    if len(cands) > 1 and grade:
        g = normaliser_grade(grade)
        cands = [c for c in cands if normaliser_grade(c.get('grade')) == g]
    return cands[0] if len(cands) == 1 else {}


def _sexe_formateur(fiche, grade):
    sx = _sexe(fiche.get('sexe'))
    if sx != NON_DEFINI:
        return sx
    cle = normaliser_grade(grade)
    if cle in ('سيده', 'انسه'):
        return 'أنثى'
    if cle == 'سيد':
        return 'ذكر'
    return NON_DEFINI


def _decouper(texte):
    from core.db.suggestions import decouper_intervenants
    return decouper_intervenants(texte)


# ─── Outils numériques ──────────────────────────────────────────────────────

def _pct(a, b, dec=2):
    return round(100.0 * a / b, dec) if b else 0.0


def _moy(a, b, dec=2):
    return round(a / b, dec) if b else 0.0


def evolution(actuel, precedent, dec=1):
    """Variation en % (None si la référence est nulle)."""
    if not precedent:
        return None
    return round(100.0 * (actuel - precedent) / precedent, dec)


def _compteur(cles):
    return {k: 0 for k in cles}


# ─── Extraction ─────────────────────────────────────────────────────────────

def _filtre(periode):
    if periode['type'] == 'plage':
        return ('f.date_formation >= ? AND f.date_formation <= ? AND length(f.date_formation) = 10',
                [periode['debut'], periode['fin']])
    marques = ','.join('?' * len(periode['mois']))
    return f'l.annee = ? AND l.mois IN ({marques})', [periode['annee']] + list(periode['mois'])


def _dorrat(conn, periode):
    clause, args = _filtre(periode)
    return [dict(r) for r in conn.execute(f'''
        SELECT f.id, f.lettre_id, f.titre, f.grade, f.nom_formateur, f.date_formation,
               f.date_fin, f.lieu_formation, f.mode_formation, f.niveau_formation,
               f.cooperation, f.hors_plan, l.mois, l.annee,
               COALESCE(mf.finalise_at, '') AS finalise_at,
               COALESCE(mu.etat, '') AS etat_mu,
               CASE WHEN mu.etat = 'acheve' THEN COALESCE(mu.heures, 0) ELSE 0 END AS heures,
               CASE WHEN mu.etat = 'acheve' THEN COALESCE(mu.montant, 0) ELSE 0 END AS montant
        FROM formations f JOIN lettres l ON l.id = f.lettre_id
        LEFT JOIN memo_formations mf ON mf.formation_id = f.id
        LEFT JOIN mustahaqqat mu ON mu.formation_id = f.id
        WHERE {_PROGRAMME} AND {clause}
        ORDER BY f.date_formation, f.id
    ''', args).fetchall()]


def _participants(conn, ids):
    if not ids:
        return []
    res = []
    for i in range(0, len(ids), 500):        # limite de variables SQLite
        lot = ids[i:i + 500]
        marques = ','.join('?' * len(lot))
        res += [dict(r) for r in conn.execute(f'''
            SELECT p.id, p.formation_id, p.nom_prenom, p.grade, p.identifiant_unique,
                   p.jiha_marjiiya, p.sexe, p.fiaa_omria,
                   COALESCE(h.present, 1) AS present, (h.id IS NOT NULL) AS note
            FROM participants p
            JOIN formations f ON f.id = p.formation_id AND f.lettre_id = p.lettre_id
            LEFT JOIN mustahaqqat_hodour h
                   ON h.formation_id = p.formation_id AND h.participant_id = p.id
            WHERE p.formation_id IN ({marques}) AND TRIM(COALESCE(p.nom_prenom, '')) != ''
            ORDER BY p.formation_id, p.ordre, p.id
        ''', lot).fetchall()]
    return res


def cle_participant(p):
    return (str(p.get('identifiant_unique') or '').strip()
            or _nom_norm(p.get('nom_prenom')))


# ─── Calcul principal ───────────────────────────────────────────────────────

def _bloc_presence(liste):
    """Compte / taux de حضور et غياب pour une liste de participations."""
    total = len(liste)
    absents = sum(1 for p in liste if not p['present'])
    return {'total': total, 'presents': total - absents, 'absents': absents,
            'taux_presence': _pct(total - absents, total),
            'taux_absence': _pct(absents, total)}


def calculer(periode, critere='finalisees', avec_details=True):
    """Toutes les données chiffrées d'une période (dict sérialisable)."""
    critere = critere if critere in ('finalisees', 'toutes') else 'finalisees'
    conn = get_connection()
    try:
        toutes = _dorrat(conn, periode)
        dorrat = [d for d in toutes if critere == 'toutes' or d['finalise_at']]
        ids = [d['id'] for d in dorrat]
        parts = _participants(conn, ids)
        table = _table_groupes(conn)
        index_mk = _index_mkowin(conn)
    finally:
        conn.close()

    # ── الأنشطة ──
    for d in dorrat:
        d['jours'] = _jours.nombre_de_jours(d['date_formation'], d['date_fin'])
        d['categorie'] = _cls.categorie_rapport(d)
        d['mode'] = d['mode_formation'] if d['mode_formation'] in _cls.MODES else _cls.MODE_DEFAUT
        d['niveau'] = (d['niveau_formation'] if d['niveau_formation'] in _cls.NIVEAUX
                       else _cls.NIVEAU_DEFAUT)
    categories = []
    for c in _cls.CATEGORIES_RAPPORT:
        sel = [d for d in dorrat if d['categorie'] == c]
        categories.append({'categorie': c, 'activites': len(sel),
                           'jours': sum(d['jours'] for d in sel)})
    nb_act = len(dorrat)
    nb_jours = sum(d['jours'] for d in dorrat)
    nb_plan = next(c['activites'] for c in categories if c['categorie'] == _cls.CATEGORIE_PLAN)

    from core.db.rapports import get_nb_programmees
    programmees = get_nb_programmees(periode['annee'])
    realisation = {'annee': periode['annee'], 'programmees': programmees,
                   'realisees_plan': nb_plan,
                   'taux': _pct(nb_plan, programmees, 1) if programmees else None}

    # ── المشاركون ──
    for p in parts:
        p['categorie'] = categorie_participant(p['grade'], table)
        p['sexe_n'] = _sexe(p['sexe'])
        p['fiaa_n'] = _fiaa(p['fiaa_omria'])
    nb_p = len(parts)
    par_cat = _compteur(CATEGORIES_PARTICIPANTS)
    for p in parts:
        par_cat[p['categorie']] += 1
    sexes = list(_validation.SEXES) + [NON_DEFINI]
    par_sexe = _compteur(sexes)
    for p in parts:
        par_sexe[p['sexe_n']] += 1
    fiaat = list(_validation.FIAAT) + [NON_DEFINI]
    par_fiaa = _compteur(fiaat)
    for p in parts:
        par_fiaa[p['fiaa_n']] += 1

    participants = {
        'total': nb_p,
        'uniques': len({cle_participant(p) for p in parts}),
        'par_categorie': par_cat,
        'par_sexe': par_sexe,
        'par_fiaa': par_fiaa,
        'moyenne': _moy(nb_p, nb_act),
        'moyenne_categorie': {k: _moy(v, nb_act) for k, v in par_cat.items()},
        'moyenne_sexe': {k: _moy(v, nb_act) for k, v in par_sexe.items()},
        'part_sexe': {k: _pct(v, nb_p) for k, v in par_sexe.items()},
        'part_categorie': {k: _pct(v, nb_p) for k, v in par_cat.items()},
    }

    # ── الحضور والغياب ──
    presence = {'global': _bloc_presence(parts),
                'par_categorie': {k: _bloc_presence([p for p in parts if p['categorie'] == k])
                                  for k in CATEGORIES_PARTICIPANTS},
                'par_sexe': {k: _bloc_presence([p for p in parts if p['sexe_n'] == k])
                             for k in sexes},
                'dorrat_sans_hodour': len({p['formation_id'] for p in parts}
                                          - {p['formation_id'] for p in parts if p['note']})}

    # ── المكوّنون ──
    formateurs = {}
    for d in dorrat:
        noms = _decouper(d['nom_formateur'])
        grades = _decouper(d['grade']) or ['']
        for i, nom in enumerate(noms):
            grade = grades[i] if i < len(grades) else grades[0]
            cle = _nom_norm(nom)
            if cle not in formateurs:
                fiche = _fiche_mkow(index_mk, nom, grade)
                grade_ref = grade or fiche.get('grade') or ''
                formateurs[cle] = {'nom': cle, 'grade': grade_ref,
                                   'categorie': categorie_formateur(grade_ref, table),
                                   'sexe': _sexe_formateur(fiche, grade_ref),
                                   'fiche': bool(fiche),
                                   'activites': 0, 'jours': 0, 'participants': 0,
                                   'heures': 0.0, 'montant': 0.0}
            f = formateurs[cle]
            f['activites'] += 1
            f['jours'] += d['jours']
            f['participants'] += sum(1 for p in parts if p['formation_id'] == d['id'])
            if len(noms) == 1:                  # montants non ventilables sinon
                f['heures'] += float(d['heures'] or 0)
                f['montant'] += float(d['montant'] or 0)
    liste_f = sorted(formateurs.values(), key=lambda x: (-x['activites'], -x['jours'], x['nom']))
    f_cat = _compteur(CATEGORIES_FORMATEURS)
    f_sexe = _compteur(sexes)
    for f in liste_f:
        f_cat[f['categorie']] += 1
        f_sexe[f['sexe']] += 1
        f['heures'] = round(f['heures'], 2)
        f['montant'] = round(f['montant'], 3)
    formateurs_res = {'total': len(liste_f), 'par_categorie': f_cat, 'par_sexe': f_sexe,
                      'sans_fiche': sum(1 for f in liste_f if not f['fiche'])}

    res = {
        'periode': periode,
        'critere': critere,
        'activites': {'total': nb_act, 'jours': nb_jours, 'categories': categories,
                      'heures': round(sum(float(d['heures'] or 0) for d in dorrat), 2),
                      'montant': round(sum(float(d['montant'] or 0) for d in dorrat), 3)},
        'non_finalisees': sum(1 for d in toutes if not d['finalise_at']),
        'total_dorrat_periode': len(toutes),
        'realisation': realisation,
        'participants': participants,
        'presence': presence,
        'formateurs': formateurs_res,
    }
    if avec_details:
        res.update(_details(periode, dorrat, parts, liste_f, sexes))
    return res


def _details(periode, dorrat, parts, liste_f, sexes):
    """Listes détaillées : par mois, دورة, مكوّن, مستوى, نمط, تعاون."""
    par_dorra_p = {}
    for p in parts:
        par_dorra_p.setdefault(p['formation_id'], []).append(p)

    lignes_dorrat = []
    for d in dorrat:
        pr = _bloc_presence(par_dorra_p.get(d['id'], []))
        lignes_dorrat.append({
            'id': d['id'], 'lettre_id': d['lettre_id'], 'titre': d['titre'] or '',
            'date_formation': d['date_formation'] or '', 'date_fin': d['date_fin'] or '',
            'jours': d['jours'], 'formateur': d['nom_formateur'] or '', 'grade': d['grade'] or '',
            'lieu': d['lieu_formation'] or '', 'mois': d['mois'], 'categorie': d['categorie'],
            'mode': d['mode'], 'niveau': d['niveau'], 'cooperation': d['cooperation'] or '',
            'finalisee': bool(d['finalise_at']), 'participants': pr['total'],
            'presents': pr['presents'], 'absents': pr['absents'],
            'taux_presence': pr['taux_presence'],
            'heures': round(float(d['heures'] or 0), 2)})

    if periode['type'] == 'plage':
        mois_ordre = []
        for d in dorrat:
            m = (d['annee'], d['mois'])
            if m not in mois_ordre:
                mois_ordre.append(m)
    else:
        mois_ordre = [(periode['annee'], m) for m in periode['mois']]
    par_mois = []
    for an, m in mois_ordre:
        sel = [x for x in lignes_dorrat
               if x['mois'] == m and (periode['type'] != 'plage'
                                      or any(d['id'] == x['id'] and d['annee'] == an for d in dorrat))]
        par_mois.append({'mois': m, 'annee': an, 'activites': len(sel),
                         'jours': sum(x['jours'] for x in sel),
                         'participants': sum(x['participants'] for x in sel),
                         'absents': sum(x['absents'] for x in sel)})

    def regrouper(cle, valeurs):
        out = []
        for v in valeurs:
            sel = [x for x in lignes_dorrat if x[cle] == v]
            out.append({'valeur': v, 'activites': len(sel),
                        'jours': sum(x['jours'] for x in sel),
                        'participants': sum(x['participants'] for x in sel)})
        return out

    return {
        'par_mois': par_mois,
        'par_dorra': lignes_dorrat,
        'par_formateur': liste_f,
        'par_niveau': regrouper('niveau', _cls.NIVEAUX),
        'par_mode': regrouper('mode', _cls.MODES),
        'par_cooperation': regrouper('cooperation', [c for c in _cls.COOPERATIONS if c]),
    }


# ─── Comparaisons ───────────────────────────────────────────────────────────

def resume(res):
    """Les indicateurs clés d'un résultat de calculer() (comparaisons, KPI)."""
    return {'libelle': res['periode']['libelle'], 'libelle_court': res['periode']['libelle_court'],
            'annee': res['periode']['annee'],
            'activites': res['activites']['total'], 'jours': res['activites']['jours'],
            'participants': res['participants']['total'],
            'uniques': res['participants']['uniques'],
            'moyenne': res['participants']['moyenne'],
            'absents': res['presence']['global']['absents'],
            'taux_presence': res['presence']['global']['taux_presence'],
            'formateurs': res['formateurs']['total'],
            'heures': res['activites']['heures'],
            'taux_realisation': res['realisation']['taux']}


def comparer(periode, n_annees=1, critere='finalisees'):
    """La période et la même période des `n_annees` années précédentes (1–5).

    Rend {courant, precedents:[résumés du plus récent au plus ancien],
    evolution_absences, evolution_activites, evolution_participants} — les
    évolutions sont calculées par rapport à l'année immédiatement antérieure."""
    n_annees = max(1, min(5, int(n_annees or 1)))
    courant = resume(calculer(periode, critere, avec_details=False))
    precedents = []
    for k in range(1, n_annees + 1):
        try:
            precedents.append(resume(calculer(meme_periode(periode, k), critere,
                                              avec_details=False)))
        except ValueError:
            break
    ref = precedents[0] if precedents else None
    return {'courant': courant, 'precedents': precedents,
            'evolution_absences': evolution(courant['absents'], ref['absents']) if ref else None,
            'evolution_activites': evolution(courant['activites'], ref['activites']) if ref else None,
            'evolution_participants': (evolution(courant['participants'], ref['participants'])
                                       if ref else None)}
