# -*- coding: utf-8 -*-
"""V3 — Phase 6 : البطاقة التّقييميّة للمشارك.

Retrouve un مشارك par son المعرّف الوحيد ou par son nom (forme normalisée :
sans حركات, hamzas unifiées…), puis rassemble TOUTES ses participations :
دورات suivies, حضور / غياب, jours, répartition par année, تصنيف, مستوى,
avec un مؤشّر المواظبة et la comparaison à la moyenne des مشاركين du مركز.

Identité d'une personne : son المعرّف الوحيد quand il existe ; les lignes
sans معرّف portant exactement le même nom (normalisé) lui sont rattachées.
Lecture seule : rien n'est écrit en base."""
from importlib import import_module

import_module('core.database')  # la façade doit être chargée (core.db._base s'y réfère)
from core.db._base import get_connection
from core.recherche import normaliser
from core import classification as cls
from core import jours as _jours
from core.rapports_moteur import categorie_participant, _table_groupes, _pct

LIMITE = 25

# Seuils du مؤشّر المواظبة (taux de حضور sur les دورات مختومة)
MAWADHABA = ((95, 'ممتازة'), (85, 'جيّدة'), (70, 'متوسّطة'), (0, 'ضعيفة'))


def _participations(conn):
    return [dict(r) for r in conn.execute('''
        SELECT p.id, p.formation_id, p.nom_prenom, p.grade, p.identifiant_unique,
               p.lieu_travail, p.jiha_marjiiya, p.sexe, p.fiaa_omria,
               f.titre, f.date_formation, f.date_fin, f.nom_formateur, f.grade AS grade_formateur,
               f.lieu_formation, f.mode_formation, f.niveau_formation, f.cooperation, f.hors_plan,
               l.annee, l.mois, COALESCE(mf.finalise_at, '') AS finalise_at,
               h.present AS present_brut
        FROM participants p
        JOIN formations f ON f.id = p.formation_id AND f.lettre_id = p.lettre_id
        JOIN lettres l ON l.id = f.lettre_id
        LEFT JOIN memo_formations mf ON mf.formation_id = f.id
        LEFT JOIN mustahaqqat_hodour h ON h.formation_id = p.formation_id AND h.participant_id = p.id
        WHERE (l.categorie = 'programme' OR l.categorie IS NULL)
          AND TRIM(COALESCE(p.nom_prenom, '')) != ''
    ''').fetchall()]


def _cle(p):
    ident = str(p.get('identifiant_unique') or '').strip()
    return ('id:' + ident) if ident else ('nom:' + normaliser(p.get('nom_prenom')))


def rechercher(q, limite=LIMITE):
    """Personnes correspondant à la requête (tous les mots, dans le nom ou
    l'معرّف). Rend [{cle, nom, grade, identifiant, dorrat, derniere}]."""
    mots = normaliser(q).split()
    if not mots:
        return []
    conn = get_connection()
    try:
        lignes = _participations(conn)
    finally:
        conn.close()
    personnes = {}
    for p in lignes:
        cible = normaliser(f"{p['nom_prenom']} {p['identifiant_unique'] or ''}")
        if not all(m in cible for m in mots):
            continue
        k = _cle(p)
        x = personnes.setdefault(k, {'cle': k, 'nom': p['nom_prenom'], 'grade': p['grade'] or '',
                                     'identifiant': (p['identifiant_unique'] or '').strip(),
                                     'dorrat': 0, 'derniere': ''})
        x['dorrat'] += 1
        if (p['date_formation'] or '') >= x['derniere']:
            x['derniere'] = p['date_formation'] or ''
            x['nom'], x['grade'] = p['nom_prenom'], p['grade'] or x['grade']
    res = sorted(personnes.values(), key=lambda x: (-x['dorrat'], normaliser(x['nom'])))
    return res[:limite]


def _appartient(p, cle, noms_rattaches):
    k = _cle(p)
    if k == cle:
        return True
    # ligne sans معرّف portant le nom d'une personne identifiée
    return k.startswith('nom:') and k[4:] in noms_rattaches


def fiche(cle, annee=None):
    """Toutes les données de la بطاقة ; None si la personne est inconnue.
    `annee` (facultatif) limite la بطاقة à une année."""
    conn = get_connection()
    try:
        lignes = _participations(conn)
        table = _table_groupes(conn)
    finally:
        conn.close()
    noms = set()
    if cle.startswith('id:'):
        noms = {normaliser(p['nom_prenom']) for p in lignes if _cle(p) == cle}
    siennes = [p for p in lignes if _appartient(p, cle, noms)]
    if not siennes:
        return None
    annees = sorted({int(p['annee']) for p in siennes if p['annee']}, reverse=True)
    if annee:
        siennes = [p for p in siennes if str(p['annee']) == str(annee)]

    recente = max(siennes or [p for p in lignes if _appartient(p, cle, noms)],
                  key=lambda p: (p['date_formation'] or '', p['id']))
    def premier_non_vide(champ):
        for p in sorted(siennes, key=lambda x: x['date_formation'] or '', reverse=True):
            if str(p.get(champ) or '').strip():
                return p[champ]
        return ''
    identite = {'nom': recente['nom_prenom'], 'grade': recente['grade'] or '',
                'identifiant': premier_non_vide('identifiant_unique'),
                'sexe': premier_non_vide('sexe'), 'fiaa': premier_non_vide('fiaa_omria'),
                'lieu_travail': premier_non_vide('lieu_travail'),
                'jiha': premier_non_vide('jiha_marjiiya'),
                'categorie': categorie_participant(recente['grade'], table)}

    dorrat = []
    for p in sorted(siennes, key=lambda x: (x['date_formation'] or '', x['id']), reverse=True):
        finalisee = bool(p['finalise_at'])
        present = None if not finalisee else bool(p['present_brut'] if p['present_brut'] is not None else 1)
        dorrat.append({
            'titre': p['titre'] or '', 'date_formation': p['date_formation'] or '',
            'date_fin': p['date_fin'] or '',
            'jours': _jours.nombre_de_jours(p['date_formation'], p['date_fin']),
            'formateur': f"{p['grade_formateur'] or ''} {p['nom_formateur'] or ''}".strip(),
            'lieu': p['lieu_formation'] or '', 'annee': p['annee'],
            'categorie': cls.categorie_rapport(p),
            'niveau': p['niveau_formation'] if p['niveau_formation'] in cls.NIVEAUX else cls.NIVEAU_DEFAUT,
            'mode': p['mode_formation'] if p['mode_formation'] in cls.MODES else cls.MODE_DEFAUT,
            'finalisee': finalisee, 'present': present,
            'grade_alors': p['grade'] or ''})

    closes = [d for d in dorrat if d['finalisee']]
    presents = [d for d in closes if d['present']]
    absences = len(closes) - len(presents)
    taux = _pct(len(presents), len(closes)) if closes else None
    mawadhaba = None
    if taux is not None:
        mawadhaba = next(lib for seuil, lib in MAWADHABA if taux >= seuil)

    def regrouper(champ, valeurs=None):
        vals = valeurs or sorted({d[champ] for d in dorrat})      # années : de la plus ancienne
        out = []
        for v in vals:
            sel = [d for d in dorrat if d[champ] == v]
            if not sel and valeurs:
                continue
            cl = [d for d in sel if d['finalisee']]
            out.append({'valeur': v, 'dorrat': len(sel),
                        'jours': sum(d['jours'] for d in sel if d['present'] is not False),
                        'absences': sum(1 for d in cl if not d['present'])})
        return out

    # Référence : nombre moyen de دورات par مشارك du مركز (mêmes années)
    ref_lignes = [p for p in lignes if not annee or str(p['annee']) == str(annee)]
    nb_personnes = len({_cle(p) for p in ref_lignes}) or 1
    moyenne_centre = round(len(ref_lignes) / nb_personnes, 2)

    return {
        'cle': cle, 'identite': identite, 'annees': annees, 'annee': annee,
        'dorrat': dorrat,
        'totaux': {'dorrat': len(dorrat), 'closes': len(closes),
                   'en_cours': len(dorrat) - len(closes),
                   'jours': sum(d['jours'] for d in dorrat if d['present'] is not False),
                   'presences': len(presents), 'absences': absences, 'taux_presence': taux,
                   'mawadhaba': mawadhaba, 'moyenne_centre': moyenne_centre,
                   'premiere': min((d['date_formation'] for d in dorrat if d['date_formation']),
                                   default=''),
                   'derniere': max((d['date_formation'] for d in dorrat if d['date_formation']),
                                   default='')},
        'par_annee': regrouper('annee'),
        'par_categorie': regrouper('categorie', list(cls.CATEGORIES_RAPPORT)),
        'par_niveau': regrouper('niveau', list(cls.NIVEAUX)),
        'par_mode': regrouper('mode', list(cls.MODES)),
    }


# ═══════════════════════════════════════════════════════════════════════════
#  PDF — une page A4 (suite sur d'autres pages si l'historique est long)
# ═══════════════════════════════════════════════════════════════════════════

def _fr(iso):
    return f'{iso[8:10]}/{iso[5:7]}/{iso[:4]}' if iso and len(iso) >= 10 else (iso or '')


def pdf_fiche(f, chemin, base_dir, config=None):
    from datetime import date
    from reportlab.pdfgen import canvas as rl_canvas
    from core.pdf_generator import _register_fonts, ar, F_AR, F_ARB, _wrap_log
    from core import identite as idt
    from core.rapport_ecrit import dec, pct
    _register_fonts(base_dir)
    config = config or {}
    W, H = 595.32, 841.92
    CM = 28.3465
    m = 1.4 * CM
    cv = rl_canvas.Canvas(chemin, pagesize=(W, H))
    ident = f['identite']
    cv.setTitle(f"البطاقة التقييمية — {ident['nom']}")
    etat = {'y': H - m, 'page': 1}

    def couleur(h):
        h = h.lstrip('#')
        cv.setFillColorRGB(int(h[:2], 16) / 255, int(h[2:4], 16) / 255, int(h[4:], 16) / 255)

    def d(x, y, s, t=10, g=False, c='#111111'):
        couleur(c)
        cv.setFont(F_ARB if g else F_AR, t)
        cv.drawRightString(x, y, ar(s))

    def ce(x, y, s, t=10, g=False, c='#111111'):
        couleur(c)
        cv.setFont(F_ARB if g else F_AR, t)
        cv.drawCentredString(x, y, ar(s))

    def pied():
        cv.setFont(F_AR, 8)
        couleur('#666666')
        cv.drawCentredString(W / 2, 0.8 * CM, str(etat['page']))
        cv.drawString(m, 0.8 * CM, date.today().strftime('%d/%m/%Y'))

    def saut():
        pied()
        cv.showPage()
        etat['page'] += 1
        etat['y'] = H - m

    # ── en-tête ──
    y = etat['y']
    for l in [l for i, l in enumerate(idt.ENTETE_NATIONAL_ORNE) if i != 2] + idt.lignes_entete_centre(config):
        y -= 12.5
        d(W - m, y, l, 9, True)
    y -= 30
    ce(W / 2, y, 'البطاقة التّقييميّة للمشارك', 17, True, '#1a3a6b')
    y -= 18
    ce(W / 2, y, f"سنة {f['annee']}" if f['annee'] else 'كلّ السّنوات', 10.5, c='#444444')
    # ── identité ──
    y -= 22
    champs = (('الاسم واللّقب', ident['nom']), ('الرّتبة', ident['grade']),
              ('المعرّف الوحيد', ident['identifiant'] or '—'), ('الصّفة', ident['categorie']),
              ('الجنس', ident['sexe'] or '—'), ('الفئة العمريّة', ident['fiaa'] or '—'),
              ('مكان العمل', ident['lieu_travail'] or '—'), ('الجهة المرجعيّة', ident['jiha'] or '—'))
    hl = 19
    haut = hl * 4 + 10
    couleur('#f3f6fb')
    cv.setStrokeColorRGB(.82, .85, .89)
    cv.roundRect(m, y - haut, W - 2 * m, haut, 6, stroke=1, fill=1)
    col_w = (W - 2 * m) / 2
    for i, (lib, val) in enumerate(champs):
        cx = W - m - 10 - (i % 2) * col_w
        cy = y - 18 - (i // 2) * hl
        d(cx, cy, lib + ' :', 9.5, c='#555555')
        lw = cv.stringWidth(ar(lib + ' :'), F_AR, 9.5)
        val = _wrap_log(cv, str(val), F_ARB, 10, col_w - lw - 26)[0]
        d(cx - lw - 6, cy, val, 10, True)
    y -= haut + 16
    # ── indicateurs ──
    t = f['totaux']
    kp = (('الدّورات', str(t['dorrat'])), ('أيّام التّكوين', str(t['jours'])),
          ('نسبة الحضور', pct(t['taux_presence']) if t['taux_presence'] is not None else '—'),
          ('الغيابات', str(t['absences'])), ('مؤشّر المواظبة', t['mawadhaba'] or '—'),
          ('معدّل المركز / مشارك', dec(t['moyenne_centre'])))
    lw = (W - 2 * m - 5 * 6) / 6
    for i, (lib, val) in enumerate(kp):
        x1 = W - m - i * (lw + 6)
        couleur('#ffffff')
        cv.setStrokeColorRGB(.82, .85, .89)
        cv.roundRect(x1 - lw, y - 46, lw, 46, 5, stroke=1, fill=1)
        couleur('#2a78d6')
        cv.rect(x1 - lw + 6, y - 3, lw - 12, 2.5, stroke=0, fill=1)
        ce(x1 - lw / 2, y - 18, lib, 7.5, c='#555555')
        ce(x1 - lw / 2, y - 37, val, 13, True, '#1a3a6b')
    y -= 62
    if t['en_cours']:
        d(W - m, y, f"ملاحظة: {t['en_cours']} دورة غير مختومة بعدُ — الحضور فيها غير محتسب.", 8.5,
          c='#7a5a00')
        y -= 16
    # ── par année (barres) ──
    if len(f['par_annee']) > 1:
        d(W - m, y, 'الدّورات حسب السّنوات', 11, True, '#1a3a6b')
        y -= 10
        pa = f['par_annee']
        vmax = max(x['dorrat'] for x in pa) or 1
        hz = 70
        pas = min((W - 2 * m) / len(pa), 70)
        base = y - hz
        for i, x in enumerate(pa):
            xc = W - m - pas * (i + 0.5)
            hb = (hz - 18) * x['dorrat'] / vmax
            couleur('#2a78d6')
            cv.roundRect(xc - 12, base, 24, hb, 2, stroke=0, fill=1)
            ce(xc, base + hb + 3, str(x['dorrat']), 8, True)
            ce(xc, base - 10, str(x['valeur']), 8, c='#444444')
        y = base - 26
    # ── historique ──
    d(W - m, y, 'سجلّ الدّورات', 11, True, '#1a3a6b')
    y -= 8
    cols = (('#', .05), ('الدّورة', .34), ('التّاريخ', .13), ('الأيّام', .07),
            ('المكوّن', .21), ('المستوى', .09), ('الحضور', .11))
    lt = W - 2 * m

    def entete(y):
        couleur('#dbe5f1')
        cv.rect(m, y - 15, lt, 15, stroke=0, fill=1)
        x = W - m
        for lib, fr in cols:
            ce(x - lt * fr / 2, y - 11, lib, 8, True)
            x -= lt * fr
        return y - 15

    y = entete(y)
    for n, dd in enumerate(f['dorrat'], 1):
        if y - 15 < 1.6 * CM:
            saut()
            y = entete(etat['y'])
        y -= 15
        pres = ('—' if dd['present'] is None else ('حاضر' if dd['present'] else 'غائب'))
        vals = (str(n), dd['titre'], _fr(dd['date_formation']), str(dd['jours']), dd['formateur'],
                dd['niveau'], pres)
        x = W - m
        for (lib, fr), v in zip(cols, vals):
            l = _wrap_log(cv, v, F_AR, 8, lt * fr - 4)
            ce(x - lt * fr / 2, y + 4, l[0] + ('…' if len(l) > 1 else ''), 8,
               g=(lib == 'الحضور' and v == 'غائب'), c='#b42318' if v == 'غائب' else '#111111')
            x -= lt * fr
        cv.setStrokeColorRGB(.89, .91, .94)
        cv.line(m, y, W - m, y)
    # ── signature ──
    if y - 80 < 1.6 * CM:
        saut()
        y = etat['y']
    y -= 40
    titre_sig, nom_sig = idt.signataire(config)
    xs = m + 4.5 * CM
    ce(xs, y, f"رئيس {idt.nom_centre(config)}", 10, True)
    ce(xs, y - 18, ' '.join(x for x in (titre_sig, nom_sig) if x), 10, True)
    pied()
    cv.save()
    return chemin
