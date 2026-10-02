# -*- coding: utf-8 -*-
"""Données des pièces d'une دورة — source UNIQUE pour le PDF et le Word (v1.7).

Jusqu'à la v1.6.1, chaque route PDF assemblait elle-même son dictionnaire.
Le ملفّ الدورة en Word (v1.7) doit dire EXACTEMENT la même chose que les
PDF : les deux lisent donc ici, et nulle part ailleurs, ce que porte chaque
pièce.

Chaque fonction rend le dict attendu par le générateur PDF correspondant,
ou None quand la pièce n'existe pas (encore).
"""

import logging as _logging

from core import gel
from core import arabe as _arabe
from core.database import (
    get_config, get_lettre_detail, get_participants, get_bataqa_data,
    get_programme_data, get_memo_data, get_jours_dorra,
)

_log = _logging.getLogger('formation.' + __name__)


def _formation(lettre_id, formation_id):
    detail = get_lettre_detail(lettre_id)
    if not detail:
        return None, None
    f = next((x for x in detail['formations'] if x['id'] == formation_id), None)
    return detail, f


def donnees_participants(lettre_id, formation_id, cfg=None):
    """القائمة الإسمية للمشاركين (ordre militaire, du grade le plus élevé)."""
    detail, formation = _formation(lettre_id, formation_id)
    if not formation:
        return None
    cfg = cfg if cfg is not None else get_config()
    ltr = detail['lettre']
    return {
        'titre':          formation.get('titre', ''),
        'date_formation': formation.get('date_formation', ''),
        'date_fin':       formation.get('date_fin') or '',     # V2
        'mois':           ltr['mois'],
        'annee':          ltr['annee'],
        'participants':   _arabe.trier_par_grade(get_participants(lettre_id, formation_id)),
        **gel.champs_pdf(cfg, lettre_id),
    }


def donnees_hodour(lettre_id, formation_id, cfg=None):
    """بطاقة الحضور : la liste + le المكوّن pour le pied."""
    detail, formation = _formation(lettre_id, formation_id)
    if not formation:
        return None
    cfg = cfg if cfg is not None else get_config()
    ltr = detail['lettre']
    return {
        'titre':           formation.get('titre', ''),
        'date_formation':  formation.get('date_formation', ''),
        'date_fin':        formation.get('date_fin') or '',    # V2
        # V2 : un jour = une colonne de signature (دورة متعدّدة الأيّام)
        'jours':           get_jours_dorra(formation_id),
        'nom_formateur':   formation.get('nom_formateur', ''),
        'grade_formateur': formation.get('grade', ''),
        'mois':            ltr['mois'],
        'annee':           ltr['annee'],
        'participants':    _arabe.trier_par_grade(get_participants(lettre_id, formation_id)),
        **gel.champs_pdf(cfg, lettre_id),
    }


def donnees_bataqa(lettre_id, formation_id, cfg=None):
    """البطاقة البيداغوجية (données enregistrées, surcharges comprises)."""
    bataqa = get_bataqa_data(lettre_id, formation_id)
    if not bataqa:
        return None
    cfg = cfg if cfg is not None else get_config()
    services = [s.strip() for s in (bataqa.get('services') or '').split('\n') if s.strip()]
    return {
        'theme':           bataqa.get('titre', ''),
        'mustahdafun':     bataqa.get('mustahdafun', ''),
        'nb_participants': bataqa.get('nb_participants', 0),
        'services':        services,
        'type_formation':  bataqa.get('type_formation', ''),
        'mahawer':         bataqa.get('mahawer', ''),
        'objectifs':       bataqa.get('objectifs', ''),
        'lieu_formation':  bataqa.get('lieu_formation', ''),
        'date_formation':  bataqa.get('date_formation', ''),
        'date_fin':        bataqa.get('date_fin', ''),        # V2
        'methodes':        bataqa.get('methodes_pedagogiques', ''),
        'moyens':          bataqa.get('moyens_pedagogiques', ''),
        'preparation':     bataqa.get('preparation_materielle', ''),
        'equipements':     bataqa.get('equipements', ''),
        **gel.champs_pdf(cfg, lettre_id),
    }


def donnees_programme(lettre_id, formation_id, cfg=None):
    """برنامج الدورة — seulement s'il est confirmé."""
    prog = get_programme_data(lettre_id, formation_id)
    if not prog or not prog.get('confirmed'):
        return None
    cfg = cfg if cfg is not None else get_config()
    return {
        'theme':          prog.get('titre', ''),
        'date_formation': prog.get('date_formation', ''),
        'lieu_formation': prog.get('lieu_formation', ''),
        'reference':      prog.get('reference', ''),
        # Pas de valeur par défaut : sans فترة choisie, rien entre parenthèses.
        'moment':         (prog.get('moment') or '').strip(),
        'rows':           prog.get('rows', []),
        # V2 : un tableau par jour (دورة متعدّدة الأيّام)
        'date_fin':       prog.get('date_fin', ''),
        'jours':          prog.get('jours', []) if prog.get('multi') else [],
        **gel.champs_pdf(cfg, lettre_id),
    }


def donnees_memo(lettre_id, formation_id, cfg=None):
    """المذكّرة — seulement si elle est confirmée. `pages` reste à None : la
    خانة Page se calcule sur les PDF réels (routes/pdf.py)."""
    memo = get_memo_data(lettre_id, formation_id)
    if not memo or not memo.get('confirmed'):
        return None
    detail = get_lettre_detail(lettre_id)
    ltr = detail['lettre'] if detail else {}
    cfg = cfg if cfg is not None else get_config()
    return {
        'type':      'interne',  # la مذكرة est toujours une مراسلة داخلية
        'ref':       memo.get('memo_ref') or ltr.get('ref_complet', ''),
        'numero':    memo.get('memo_numero') or ltr.get('numero', ''),
        'mois':      ltr.get('mois', ''),
        'annee':     ltr.get('annee', ''),
        'objet':     memo.get('objet', ''),
        'corps':     memo.get('corps', ''),
        'msahib':    memo.get('msahib', []),
        'moujah':    memo.get('moujah', []),
        'titre_directeur_general': cfg.get('titre_directeur_general', 'العميد'),
        'nom_directeur_general':   cfg.get('nom_directeur_general', ''),
        'ecole_email':   cfg.get('ecole_email', ''),
        'ecole_tel':     cfg.get('ecole_tel', ''),
        'ecole_fax':     cfg.get('ecole_fax', ''),
        'ecole_web':     cfg.get('ecole_web', ''),
        'ecole_adresse': cfg.get('ecole_adresse', ''),
        **gel.champs_pdf(cfg, lettre_id),
        'pages':     None,
    }


def pages_du_dossier(lettre_id, formation_id, memo_data, base_dir):
    """خانة Page de la مذكّرة : pages RÉELLES de la مذكّرة + برنامج الدورة +
    القائمة الإسمية + البطاقة البيداغوجية (convention « total/total »).
    Une pièce absente compte pour 0 ; la مذكّرة seule vaut au moins 1."""
    from core import chemins
    from core.pdf_generator import (generer_pdf_programme, generer_pdf_participants,
                                    generer_pdf_bataqa, generer_pdf_memo, compter_pages_pdf)

    def _pages(gen, donnees):
        chemin = gen(donnees, base_dir)
        try:
            return compter_pages_pdf(chemin)
        finally:
            chemins.supprimer(chemin)

    cfg = get_config()
    total = 0
    prog = donnees_programme(lettre_id, formation_id, cfg)
    if prog:
        try:
            total += _pages(generer_pdf_programme, prog)
        except Exception as e:
            _log.warning('comptage برنامج الدورة : %s', e)
    try:
        parts = donnees_participants(lettre_id, formation_id, cfg)
        if parts and parts['participants']:
            total += _pages(generer_pdf_participants, parts)
    except Exception as e:
        _log.warning('comptage القائمة الإسمية : %s', e)
    try:
        bataqa = donnees_bataqa(lettre_id, formation_id, cfg)
        if bataqa:
            total += _pages(generer_pdf_bataqa, bataqa)
    except Exception as e:
        _log.warning('comptage البطاقة البيداغوجية : %s', e)
    donnees = dict(memo_data, pages=None)
    return max(_pages(generer_pdf_memo, donnees), 1) + total


def donnees_shahadat(lettre_id, formation_id, participant_id=None, cfg=None):
    """(données de la دورة, liste des مشاركين حاضرين) pour les شهادات, ou
    (None, motif) si la présence n'a pas encore été enregistrée.

    Les présents viennent de ورقة الحضور (قسم المستحقّات) ; l'ordre est
    l'ordre militaire, comme la القائمة الإسمية."""
    from core.database import get_connection
    detail, formation = _formation(lettre_id, formation_id)
    if not formation:
        return None, 'الدورة غير موجودة'
    conn = get_connection()
    try:
        mu = conn.execute('SELECT hodour_at FROM mustahaqqat WHERE formation_id=?',
                          (formation_id,)).fetchone()
        if not mu or not mu['hodour_at']:
            return None, ('لم تُسجَّل ورقة الحضور بعد: أدخل الحضور من قسم '
                          'المستحقّات المالية ← ورقة الحضور، ثمّ أعد المحاولة.')
        rows = [dict(r) for r in conn.execute('''
            SELECT p.id, p.nom_prenom, p.grade, p.identifiant_unique, p.sexe,
                   p.lieu_travail
            FROM participants p
            JOIN mustahaqqat_hodour h
                 ON h.participant_id = p.id AND h.formation_id = p.formation_id
            WHERE p.formation_id = ? AND h.present = 1
            ORDER BY p.ordre''', (formation_id,)).fetchall()]
    finally:
        conn.close()
    if participant_id is not None:
        rows = [r for r in rows if r['id'] == participant_id]
    if not rows:
        return None, 'لا يوجد مشارك حاضر تُسلَّم له شهادة'
    cfg = cfg if cfg is not None else get_config()
    donnees = {
        'titre':           formation.get('titre', ''),
        'date_formation':  formation.get('date_formation', ''),
        'date_fin':        formation.get('date_fin') or '',    # V2
        'lieu_formation':  formation.get('lieu_formation', ''),
        'nom_formateur':   formation.get('nom_formateur', ''),
        'grade_formateur': formation.get('grade', ''),
        **gel.champs_pdf(cfg, lettre_id),
    }
    return donnees, _arabe.trier_par_grade(rows)
