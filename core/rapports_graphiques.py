# -*- coding: utf-8 -*-
"""V3 — Phase 5 : التّقرير البياني والتّحليلي.

• donnees(periode, n_annees, critere) : tout ce que la page « التّقارير »
  affiche — indicateurs clés avec leur évolution, graphiques (décrits comme
  des données : le même dictionnaire sert à la page, au PDF et à l'export HTML
  interactif), phrases d'analyse, liste des دورات.
• pdf_graphique(d, chemin, base_dir) : le rapport graphique en PDF (A4),
  graphiques dessinés directement avec ReportLab (aucune dépendance).

Règles des graphiques (voir la page statistiques) : une seule mesure par
graphique (jamais deux échelles), valeurs écrites sur chaque barre, un
tableau équivalent sous chaque graphique, couleurs catégorielles à ordre fixe
réservées aux répartitions (genre)."""
from datetime import date

from core import rapports_moteur as rm
from core import classification as cls
from core import validation as _validation
from core import identite as idt
from core.rapport_ecrit import dec, pct, nb

# Palette validée (dataviz) — clair / sombre gérés côté CSS ; PDF = clair.
SERIE = '#2a78d6'
CATEGORIELLES = ('#2a78d6', '#eb6834', '#1baf7a', '#eda100', '#e87ba4')
NEUTRE = '#9aa3ad'

INDICATEURS = (  # (clé du résumé, libellé, unité, « une baisse est favorable »)
    ('activites', 'الأنشطة المنجزة', '', False),
    ('jours', 'أيّام التّكوين', '', False),
    ('participants', 'المشاركون', '', False),
    ('uniques', 'المشاركون دون تكرار', '', False),
    ('moyenne', 'معدّل المشاركين / نشاط', '', False),
    ('taux_presence', 'نسبة الحضور', '%', False),
    ('absents', 'الغيابات', '', True),
    ('formateurs', 'المكوّنون', '', False),
)


def _graphe(gid, titre, libelles, valeurs, forme='barres_v', unite='', sous='', maxi=None,
            couleurs=None, accent=None):
    return {'id': gid, 'titre': titre, 'sous': sous, 'forme': forme, 'unite': unite,
            'libelles': [str(x) for x in libelles], 'valeurs': [float(v or 0) for v in valeurs],
            'max': maxi, 'couleurs': couleurs, 'accent': accent}


def _evol(actuel, precedent):
    if actuel is None or precedent is None:
        return None
    return rm.evolution(actuel, precedent)


def donnees(periode, n_annees=1, critere='finalisees'):
    """Toutes les données de la page / du PDF / de l'export HTML."""
    n_annees = max(1, min(5, int(n_annees or 1)))
    r = rm.calculer(periode, critere)
    cmp = rm.comparer(periode, n_annees, critere)
    cour = cmp['courant']
    ref = cmp['precedents'][0] if cmp['precedents'] else None
    serie = list(reversed(cmp['precedents'])) + [cour]          # du plus ancien au courant

    kpis = []
    for cle, lib, unite, baisse_ok in INDICATEURS:
        v = cour.get(cle)
        pv = ref.get(cle) if ref else None
        ev = _evol(v, pv) if ref and ref['activites'] else None
        kpis.append({'cle': cle, 'libelle': lib, 'unite': unite, 'valeur': v,
                     'texte': (pct(v) if unite == '%' else dec(v)) if v is not None else '—',
                     'precedent': pv, 'evolution': ev, 'baisse_favorable': baisse_ok,
                     'precedent_texte': ((pct(pv) if unite == '%' else dec(pv))
                                         if pv is not None else ''),
                     'reference': ref['libelle_court'] if ref else ''})
    if r['realisation']['taux'] is not None:
        kpis.append({'cle': 'taux_realisation', 'libelle': 'نسبة إنجاز المخطّط', 'unite': '%',
                     'valeur': r['realisation']['taux'], 'texte': pct(r['realisation']['taux']),
                     'precedent': None, 'precedent_texte': '', 'evolution': None, 'baisse_favorable': False,
                     'reference': f"{r['realisation']['realisees_plan']} / "
                                  f"{r['realisation']['programmees']}"})

    ans = [s['libelle_court'] for s in serie]
    act, part, pres, form = r['activites'], r['participants'], r['presence'], r['formateurs']
    sections = [
        {'id': 'comparaison', 'titre': f'المقارنة مع نفس الفترة من السّنوات السّابقة ({len(serie)} سنوات)'
         if len(serie) > 2 else 'المقارنة مع نفس الفترة من السّنة السّابقة',
         'graphes': [
             _graphe('cmp_act', 'الأنشطة المنجزة', ans, [s['activites'] for s in serie],
                     accent=len(serie) - 1),
             _graphe('cmp_part', 'المشاركون', ans, [s['participants'] for s in serie],
                     accent=len(serie) - 1),
             _graphe('cmp_abs', 'الغيابات', ans, [s['absents'] for s in serie],
                     accent=len(serie) - 1),
             _graphe('cmp_pres', 'نسبة الحضور', ans, [s['taux_presence'] for s in serie],
                     unite='%', maxi=100, accent=len(serie) - 1),
         ]},
        {'id': 'mois', 'titre': 'النّشاط حسب الأشهر', 'graphes': [
            _graphe('mois_act', 'الأنشطة حسب الأشهر', [m['mois'] for m in r['par_mois']],
                    [m['activites'] for m in r['par_mois']]),
            _graphe('mois_part', 'المشاركون حسب الأشهر', [m['mois'] for m in r['par_mois']],
                    [m['participants'] for m in r['par_mois']]),
        ]},
        {'id': 'activites', 'titre': 'الأنشطة التّكوينيّة', 'graphes': [
            _graphe('cat_act', 'الأنشطة حسب التّصنيف', [c['categorie'] for c in act['categories']],
                    [c['activites'] for c in act['categories']], forme='barres_h'),
            _graphe('cat_jours', 'أيّام التّكوين حسب التّصنيف',
                    [c['categorie'] for c in act['categories']],
                    [c['jours'] for c in act['categories']], forme='barres_h'),
            _graphe('niveau', 'الأنشطة حسب المستوى', [x['valeur'] for x in r['par_niveau']],
                    [x['activites'] for x in r['par_niveau']], forme='barres_h'),
            _graphe('mode', 'الأنشطة حسب الصّيغة', [x['valeur'] for x in r['par_mode']],
                    [x['activites'] for x in r['par_mode']], forme='barres_h'),
        ]},
        {'id': 'participants', 'titre': 'المشاركون والحضور', 'graphes': [
            _graphe('part_cat', 'المشاركون حسب الصّفة', list(part['par_categorie']),
                    list(part['par_categorie'].values()), forme='barres_h'),
            _graphe('part_sexe', 'المشاركون حسب الجنس', list(part['par_sexe']),
                    list(part['par_sexe'].values()), forme='pile',
                    couleurs=[CATEGORIELLES[0], CATEGORIELLES[1], NEUTRE]),
            _graphe('pres_cat', 'نسبة الحضور حسب الصّفة', list(pres['par_categorie']),
                    [b['taux_presence'] for b in pres['par_categorie'].values()],
                    forme='barres_h', unite='%', maxi=100),
            _graphe('part_fiaa', 'المشاركون حسب الفئة العمريّة', list(part['par_fiaa']),
                    list(part['par_fiaa'].values()), forme='pile',
                    couleurs=[CATEGORIELLES[2], CATEGORIELLES[3], NEUTRE]),
        ]},
        {'id': 'formateurs', 'titre': 'المكوّنون', 'graphes': [
            _graphe('form_cat', 'المكوّنون حسب الصّنف', list(form['par_categorie']),
                    list(form['par_categorie'].values()), forme='barres_h'),
            _graphe('form_top', 'أكثر المكوّنين نشاطا (عدد الأنشطة)',
                    [f"{x['grade']} {x['nom']}".strip() for x in r['par_formateur'][:8]],
                    [x['activites'] for x in r['par_formateur'][:8]], forme='barres_h'),
        ]},
    ]
    d = {'periode': periode, 'critere': critere, 'n_annees': n_annees,
         'kpis': kpis, 'sections': sections, 'serie': serie,
         'dorrat': r['par_dorra'], 'non_finalisees': r['non_finalisees'],
         'realisation': r['realisation'], 'resume': cour, 'reference': ref}
    d['analyses'] = analyses(r, cmp, serie)
    return d


def _sens(ev):
    if ev is None:
        return ''
    if ev > 0:
        return f'بارتفاع نسبته {pct(ev)}'
    if ev < 0:
        return f'بانخفاض نسبته {pct(abs(ev))}'
    return 'باستقرار'


def analyses(r, cmp, serie):
    """Constats en phrases courtes (partie « تحليلي » du rapport)."""
    out = []
    cour = cmp['courant']
    ref = cmp['precedents'][0] if cmp['precedents'] else None
    utile = ref and ref['activites']
    if not cour['activites']:
        return ['لا توجد أنشطة محتسبة في هذه الفترة.']
    t = f"بلغ عدد الأنشطة المنجزة {nb(cour['activites'], 'nashat')} بمجموع {nb(cour['jours'], 'yawm')} من التّكوين"
    if utile:
        t += (f" مقابل {ref['activites']} خلال {ref['libelle_court']} "
              f"({_sens(cmp['evolution_activites'])})")
    out.append(t + '.')
    t = f"انتفع بهذه الأنشطة {nb(cour['participants'], 'moucharik')} ({cour['uniques']} دون تكرار)"
    if utile:
        t += f" مقابل {ref['participants']} ({_sens(cmp['evolution_participants'])})"
    out.append(t + f"، أي بمعدّل {dec(cour['moyenne'])} مشاركا لكلّ نشاط.")
    t = f"بلغت نسبة الحضور {pct(cour['taux_presence'])} بـ {nb(cour['absents'], 'ghiyab')}"
    if utile and ref['absents']:
        t += f" مقابل {nb(ref['absents'], 'ghiyab')} خلال {ref['libelle_court']} ({_sens(cmp['evolution_absences'])})"
    out.append(t + '.')
    if r['par_mois']:
        m = max(r['par_mois'], key=lambda x: (x['activites'], x['participants']))
        if m['activites']:
            out.append(f"سجّل شهر {m['mois']} أعلى نشاط بـ {nb(m['activites'], 'nashat')} و"
                       f"{nb(m['participants'], 'moucharik')}.")
    cats = sorted(r['activites']['categories'], key=lambda c: -c['activites'])
    if cats and cats[0]['activites']:
        part = 100.0 * cats[0]['activites'] / cour['activites']
        out.append(f"استأثر صنف «{cats[0]['categorie']}» بنسبة {pct(round(part, 1))} من الأنشطة.")
    blocs = [(k, b) for k, b in r['presence']['par_categorie'].items() if b['total']]
    if len(blocs) > 1:
        k, b = min(blocs, key=lambda x: x[1]['taux_presence'])
        out.append(f"أدنى نسبة حضور سُجّلت لدى فئة «{k}» ({pct(b['taux_presence'])}).")
    ps = r['participants']['part_sexe']
    out.append(f"توزّع المشاركون بين {pct(ps.get('ذكر', 0))} من الذّكور و{pct(ps.get('أنثى', 0))} "
               f"من الإناث.")
    if r['par_formateur']:
        f = r['par_formateur'][0]
        out.append(f"أكثر المكوّنين نشاطا: {(f['grade'] + ' ' + f['nom']).strip()} "
                   f"بـ {nb(f['activites'], 'nashat')}.")
    re_ = r['realisation']
    if re_['taux'] is not None:
        out.append(f"نسبة إنجاز المخطّط الجهوي: {pct(re_['taux'])} ({re_['realisees_plan']} من "
                   f"{re_['programmees']} دورة مبرمجة لسنة {re_['annee']}).")
    avec = [s for s in serie if s['activites']]
    if len(avec) > 2 or (len(avec) == 2 and len(serie) > 2):
        premier, dernier = avec[0], serie[-1]
        out.append(f"على امتداد {'سنتين' if len(avec) == 2 else str(len(avec)) + ' سنوات'} ({premier['libelle_court']} ← "
                   f"{dernier['libelle_court']}) تطوّر عدد الأنشطة من {premier['activites']} إلى "
                   f"{dernier['activites']} وعدد المشاركين من {premier['participants']} إلى "
                   f"{dernier['participants']}.")
    if r['non_finalisees']:
        out.append(f"ملاحظة: {r['non_finalisees']} دورة غير مختومة لم تُحتسب.")
    return out


# ═══════════════════════════════════════════════════════════════════════════
#  PDF
# ═══════════════════════════════════════════════════════════════════════════

CM = 28.3465


def _rgb(c, h):
    h = h.lstrip('#')
    c.setFillColorRGB(int(h[:2], 16) / 255, int(h[2:4], 16) / 255, int(h[4:], 16) / 255)


def _stroke(c, h):
    h = h.lstrip('#')
    c.setStrokeColorRGB(int(h[:2], 16) / 255, int(h[2:4], 16) / 255, int(h[4:], 16) / 255)


def _fmt(v, unite):
    return pct(v) if unite == '%' else dec(v)


class _Pdf:
    def __init__(self, cv, base_dir, titre_pied):
        from core.pdf_generator import ar, F_AR, F_ARB
        self.c, self.ar, self.F, self.FB = cv, ar, F_AR, F_ARB
        self.W, self.H = 595.32, 841.92
        self.m = 1.3 * CM
        self.y = self.H - self.m
        self.page = 1
        self.titre_pied = titre_pied

    def pied(self):
        c = self.c
        c.setFillColorRGB(.4, .4, .4)
        c.setFont(self.F, 8)
        c.drawCentredString(self.W / 2, 0.8 * CM, str(self.page))
        c.drawRightString(self.W - self.m, 0.8 * CM, self.ar(self.titre_pied))
        c.setFillColorRGB(0, 0, 0)

    def saut(self):
        self.pied()
        self.c.showPage()
        self.page += 1
        self.y = self.H - self.m

    def assurer(self, h):
        if self.y - h < 1.4 * CM:
            self.saut()

    def texte_d(self, x, y, s, taille=10, gras=False, couleur='#111111'):
        _rgb(self.c, couleur)
        self.c.setFont(self.FB if gras else self.F, taille)
        self.c.drawRightString(x, y, self.ar(s))

    def texte_c(self, x, y, s, taille=10, gras=False, couleur='#111111'):
        _rgb(self.c, couleur)
        self.c.setFont(self.FB if gras else self.F, taille)
        self.c.drawCentredString(x, y, self.ar(s))

    def couper(self, s, taille, largeur, gras=False):
        from core.pdf_generator import _wrap_log
        return _wrap_log(self.c, s, self.FB if gras else self.F, taille, largeur)

    def titre_section(self, s, besoin=0):
        self.assurer(40 + besoin)
        self.y -= 22
        self.texte_d(self.W - self.m, self.y, s, 13, True, '#1a3a6b')
        _stroke(self.c, '#c8a84b')
        self.c.setLineWidth(1.4)
        self.c.line(self.m, self.y - 6, self.W - self.m, self.y - 6)
        self.y -= 14

    # ── graphiques (dans un cadre x0..x1, du haut `top`, hauteur h) ──
    def graphe(self, g, x0, x1, top, h):
        c = self.c
        _stroke(c, '#d0d8e4')
        c.setLineWidth(.6)
        c.roundRect(x0, top - h, x1 - x0, h, 6, stroke=1, fill=0)
        self.texte_d(x1 - 8, top - 16, g['titre'], 10, True)
        zone_top, zone_bas = top - 26, top - h + 8
        vals = g['valeurs']
        if not vals or not any(vals):
            self.texte_c((x0 + x1) / 2, (zone_top + zone_bas) / 2, 'لا توجد معطيات', 9,
                         couleur='#777777')
            return
        if g['forme'] == 'barres_v':
            self._barres_v(g, x0 + 8, x1 - 8, zone_top, zone_bas)
        elif g['forme'] == 'barres_h':
            self._barres_h(g, x0 + 8, x1 - 8, zone_top, zone_bas)
        else:
            self._pile(g, x0 + 8, x1 - 8, zone_top, zone_bas)

    def _barres_v(self, g, x0, x1, top, bas):
        c = self.c
        vals, libs, n = g['valeurs'], g['libelles'], len(g['valeurs'])
        base = bas + 24                         # place des libellés
        haut = top - 14                         # place des valeurs
        vmax = g['max'] or max(vals) or 1
        pas = (x1 - x0) / n
        lb = min(pas * 0.56, 34)
        _stroke(c, '#b8c2cf')
        c.setLineWidth(.6)
        c.line(x0, base, x1, base)
        for i, (v, lib) in enumerate(zip(vals, libs)):
            xc = x1 - pas * (i + 0.5)           # ordre RTL : le premier à droite
            hb = (haut - base) * (v / vmax) if vmax else 0
            accent = g.get('accent')
            _rgb(c, SERIE if accent is None or accent == i else '#b3bcc8')
            if hb > 0:
                c.roundRect(xc - lb / 2, base, lb, hb, 2.5, stroke=0, fill=1)
            self.texte_c(xc, base + hb + 3, _fmt(v, g['unite']), 7.5, True)
            lignes = self.couper(lib, 7, pas - 2)[:2]
            for k, l in enumerate(lignes):
                self.texte_c(xc, base - 9 - k * 8.5, l, 7, couleur='#444444')

    def _barres_h(self, g, x0, x1, top, bas):
        c = self.c
        vals, libs, n = g['valeurs'], g['libelles'], len(g['valeurs'])
        vmax = g['max'] or max(vals) or 1
        larg_lib = (x1 - x0) * 0.40
        xb = x1 - larg_lib                      # départ des barres (à droite)
        zone = xb - x0 - 30                     # place de la valeur à gauche
        pas = min((top - bas) / n, 24)
        eb = min(pas * 0.58, 13)
        for i, (v, lib) in enumerate(zip(vals, libs)):
            yc = top - pas * (i + 0.5)
            l = self.couper(lib, 7.5, larg_lib - 6)
            if len(l) > 1 and pas >= 18:            # deux lignes si la place le permet
                self.texte_d(x1, yc + 1, l[0], 7.5, couleur='#333333')
                self.texte_d(x1, yc - 7.5, l[1] + ('…' if len(l) > 2 else ''), 7.5,
                             couleur='#333333')
            else:
                self.texte_d(x1, yc - 3, l[0] + ('…' if len(l) > 1 else ''), 7.5,
                             couleur='#333333')
            w = zone * (v / vmax) if vmax else 0
            _rgb(c, SERIE)
            if w > 0:
                c.roundRect(xb - 4 - w, yc - eb / 2, w, eb, 2.5, stroke=0, fill=1)
            _rgb(c, '#111111')
            c.setFont(self.FB, 7.5)
            c.drawRightString(xb - 8 - w, yc - 3, _fmt(v, g['unite']))

    def _pile(self, g, x0, x1, top, bas):
        c = self.c
        vals, libs = g['valeurs'], g['libelles']
        total = sum(vals) or 1
        couleurs = g['couleurs'] or list(CATEGORIELLES)
        yb = (top + bas) / 2 + 4
        eb = 18
        x = x1
        for i, v in enumerate(vals):
            w = (x1 - x0) * v / total
            if w <= 0:
                continue
            _rgb(c, couleurs[i % len(couleurs)])
            c.rect(x - w + (1 if i else 0), yb, w - 1, eb, stroke=0, fill=1)
            if w > 30:
                c.setFillColorRGB(1, 1, 1)
                c.setFont(self.FB, 7.5)
                c.drawCentredString(x - w / 2, yb + 6, pct(round(100.0 * v / total, 1)))
            x -= w
        # légende (identité jamais portée par la seule couleur)
        xl = x1
        for i, (v, lib) in enumerate(zip(vals, libs)):
            s = f'{lib}: {dec(v)}'
            wtxt = c.stringWidth(self.ar(s), self.F, 7.5)
            _rgb(c, couleurs[i % len(couleurs)])
            c.rect(xl - 7, yb - 16, 7, 7, stroke=0, fill=1)
            self.texte_d(xl - 10, yb - 15.5, s, 7.5, couleur='#333333')
            xl -= wtxt + 24


def pdf_graphique(d, chemin, base_dir, config=None):
    """Écrit le تقرير بياني et تحليلي en PDF."""
    from reportlab.pdfgen import canvas as rl_canvas
    from core.pdf_generator import _register_fonts
    _register_fonts(base_dir)
    config = config or {}
    p = d['periode']
    titre = f"التّقرير البياني والتّحليلي — {p['libelle']}"
    cv = rl_canvas.Canvas(chemin, pagesize=(595.32, 841.92))
    cv.setTitle(titre)
    P = _Pdf(cv, base_dir, titre)
    W, m = P.W, P.m
    # ── en-tête ──
    y = P.y
    for l in [idt.ENTETE_NATIONAL_ORNE[1], idt.ENTETE_NATIONAL_ORNE[3]] + idt.lignes_entete_centre(config):
        y -= 12
        P.texte_d(W - m, y, l, 8.5, True)
    P.texte_c(m + 45, P.y - 12, date.today().strftime('%d/%m/%Y'), 8.5)
    y -= 26
    P.texte_c(W / 2, y, 'التّقرير البياني والتّحليلي لنشاط', 15, True, '#1a3a6b')
    y -= 20
    P.texte_c(W / 2, y, idt.nom_centre(config), 13, True, '#1a3a6b')
    y -= 18
    sous = p['libelle'] + ('' if d['critere'] == 'finalisees' else ' — مع الدّورات غير المختومة')
    P.texte_c(W / 2, y, sous, 11, couleur='#444444')
    P.y = y - 16
    # ── indicateurs ──
    kp = d['kpis']
    cols = 3
    gap = 8
    lw = (W - 2 * m - gap * (cols - 1)) / cols
    hk = 50
    for i, k in enumerate(kp):
        if i % cols == 0:
            P.assurer(hk + gap)
            top = P.y
            P.y -= hk + gap
        x1 = W - m - (i % cols) * (lw + gap)
        x0 = x1 - lw
        _rgb(cv, '#f3f6fb')
        _stroke(cv, '#d0d8e4')
        cv.setLineWidth(.6)
        cv.roundRect(x0, top - hk, lw, hk, 6, stroke=1, fill=1)
        _rgb(cv, SERIE)
        cv.rect(x1 - 3, top - hk + 6, 3, hk - 12, stroke=0, fill=1)
        P.texte_d(x1 - 10, top - 14, k['libelle'], 8.5, couleur='#444444')
        P.texte_d(x1 - 10, top - 33, k['texte'], 15, True, '#1a3a6b')
        if k['evolution'] is not None:
            fl = '▲' if k['evolution'] > 0 else ('▼' if k['evolution'] < 0 else '=')
            s = f"{fl} {pct(abs(k['evolution']))} مقارنة بـ {k['reference']}"
            P.texte_d(x1 - 10, top - 45, s.replace('▲', '+').replace('▼', '−'), 7.5,
                      couleur='#555555')
        elif k['cle'] == 'taux_realisation':
            P.texte_d(x1 - 10, top - 45, f"{k['reference']} دورة", 7.5, couleur='#555555')
    # ── analyse ──
    P.titre_section('أهمّ الاستنتاجات')
    for a in d['analyses']:
        lignes = P.couper(a, 9.5, W - 2 * m - 16)
        P.assurer(len(lignes) * 14 + 2)
        for k, l in enumerate(lignes):
            P.y -= 14
            if k == 0:
                _rgb(cv, SERIE)
                cv.circle(W - m - 3, P.y + 3, 2, stroke=0, fill=1)
            P.texte_d(W - m - 12, P.y, l, 9.5)
        P.y -= 2
    # ── graphiques : deux par ligne ──
    hg = 175
    for s in d['sections']:
        P.titre_section(s['titre'], besoin=hg + 8)
        gs = s['graphes']
        for i in range(0, len(gs), 2):
            P.assurer(hg + 8)
            top = P.y - 4
            lg = (W - 2 * m - 10) / 2
            for j, g in enumerate(gs[i:i + 2]):
                x1 = W - m - j * (lg + 10)
                P.graphe(g, x1 - lg, x1, top, hg)
            P.y = top - hg - 6
    # ── liste des دورات ──
    P.titre_section(f"قائمة الأنشطة المحتسبة ({len(d['dorrat'])})")
    cols_t = (('#', 0.05), ('الدّورة', 0.34), ('التّاريخ', 0.13), ('المكوّن', 0.2),
              ('الأيّام', 0.07), ('المشاركون', 0.1), ('الحضور', 0.11))
    lt = W - 2 * m

    def entete():
        P.assurer(40)
        P.y -= 16
        _rgb(cv, '#dbe5f1')
        cv.rect(m, P.y - 4, lt, 15, stroke=0, fill=1)
        x = W - m
        for lib, f in cols_t:
            P.texte_c(x - lt * f / 2, P.y, lib, 8, True)
            x -= lt * f
    entete()
    for n, dd in enumerate(d['dorrat'], 1):
        if P.y - 14 < 1.4 * CM:
            P.saut()
            entete()
        P.y -= 14
        valeurs = (str(n), dd['titre'], dd['date_formation'][8:10] + '/' + dd['date_formation'][5:7]
                   if dd['date_formation'] else '', (dd['grade'] + ' ' + dd['formateur']).strip(),
                   str(dd['jours']), str(dd['participants']), pct(dd['taux_presence']))
        x = W - m
        for (lib, f), v in zip(cols_t, valeurs):
            l = P.couper(v, 7.5, lt * f - 4)
            P.texte_c(x - lt * f / 2, P.y, l[0] + ('…' if len(l) > 1 else ''), 7.5)
            x -= lt * f
        _stroke(cv, '#e3e8ef')
        cv.setLineWidth(.4)
        cv.line(m, P.y - 4, W - m, P.y - 4)
    P.pied()
    cv.save()
    return chemin


def constantes_js():
    """Libellés / couleurs utiles au script des graphiques."""
    return {'serie': SERIE, 'categorielles': list(CATEGORIELLES), 'neutre': NEUTRE,
            'sexes': list(_validation.SEXES), 'modes': list(cls.MODES)}


# ═══════════════════════════════════════════════════════════════════════════
#  Phase 6c — مؤشّرات الشّاشة الرّئيسيّة : السّنة الجارية / السّنة الماضية
# ═══════════════════════════════════════════════════════════════════════════

def _meme_jour(d, annee):
    try:
        return d.replace(year=annee)
    except ValueError:                      # 29 février
        return d.replace(year=annee, day=28)


def kpis_accueil(aujourd_hui=None):
    """Depuis le 1er janvier jusqu'à aujourd'hui, comparé à la MÊME période de
    l'année précédente (comparer une année entamée à une année entière
    fausserait tout) ; plus les الأنشطة de chaque mois des deux années."""
    auj = aujourd_hui or date.today()
    y = auj.year
    cour = rm.calculer(rm.bornes_periode(type_periode='plage', debut=f'{y}-01-01',
                                         fin=auj.isoformat()), avec_details=False)
    prec = rm.calculer(rm.bornes_periode(type_periode='plage', debut=f'{y - 1}-01-01',
                                         fin=_meme_jour(auj, y - 1).isoformat()),
                       avec_details=False)

    def indic(lib, v, pv, unite=''):
        ev = rm.evolution(v, pv) if pv else None
        return {'libelle': lib, 'valeur': v, 'texte': pct(v) if unite == '%' else dec(v),
                'precedent': pv, 'precedent_texte': pct(pv) if unite == '%' else dec(pv),
                'evolution': ev}
    kp = [indic('الأنشطة المنجزة', cour['activites']['total'], prec['activites']['total']),
          indic('المشاركون', cour['participants']['total'], prec['participants']['total']),
          indic('أيّام التّكوين', cour['activites']['jours'], prec['activites']['jours']),
          indic('نسبة الحضور', cour['presence']['global']['taux_presence'],
                prec['presence']['global']['taux_presence'], '%')]
    if not prec['activites']['total']:
        kp[3]['evolution'] = None
    mois_c = rm.calculer(rm.bornes_periode(y, 'annee'))['par_mois']
    mois_p = rm.calculer(rm.bornes_periode(y - 1, 'annee'))['par_mois']
    graphe = {'id': 'accueil_mois', 'titre': f'الأنشطة المنجزة حسب الأشهر: {y} مقابل {y - 1}',
              'forme': 'barres_g', 'unite': '', 'max': None, 'accent': None, 'couleurs': None,
              'libelles': [m['mois'] for m in mois_c],
              'valeurs': [m['activites'] for m in mois_c],
              'series': [{'nom': str(y), 'valeurs': [m['activites'] for m in mois_c],
                          'classe': 'rg-barre'},
                         {'nom': str(y - 1), 'valeurs': [m['activites'] for m in mois_p],
                          'classe': 'rg-barre rg-barre--pale'}],
              'mois_courant': auj.month}
    return {'annee': y, 'jusqu_au': auj.strftime('%d/%m'), 'indicateurs': kp,
            'sections': [{'graphes': [graphe]}],
            'vide': not cour['activites']['total'] and not prec['activites']['total']}
