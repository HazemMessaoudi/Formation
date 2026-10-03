# -*- coding: utf-8 -*-
"""V3 — Phase 4 : التّقرير الكتابي (نصف سنوي / ثلاثي / سنوي / فترة محدّدة).

• contenu(periode, config, brouillon) : tout le rapport sous forme de données
  — textes générés automatiquement à partir du moteur (core.rapports_moteur),
  tableaux, signature — avec, par-dessus, les corrections de l'utilisateur
  (brouillon enregistré dans `config`, une clé par période).
• docx_rapport(c) : le rapport en Word (.docx), sans dépendance.
• pdf_rapport(c, chemin, base_dir) : le même rapport en PDF (ReportLab).

La mise en page reproduit le modèle officiel « التّقرير النّصف سنوي لنشاط
مركز التّكوين الجهوي » : ترويسة à droite, date à gauche, titre centré, titres
de parties gras soulignés, corps justifié avec retrait de première ligne,
chiffres en gras, tableaux à bandeau bleu (#8DB3E2) et cases bleu clair
(#DBE5F1), numéro de page centré en pied de page.
"""
import json
import re
from datetime import date

from core import rapports_moteur as rm
from core import rapports_defauts as rd
from core import identite as idt
from core import classification as cls

# ─── Constantes de présentation ─────────────────────────────────────────────

BLEU_BANDEAU = '8DB3E2'
BLEU_CLAIR = 'DBE5F1'
CADRE_PLAN = 'تنفيذ المخطّط السّنوي للتّكوين للمدرسة الوطنيّة للدّيوانة'
CADRE_COOP = 'التّعاون الوطني'
CADRE_HORS = 'الأنشطة المنجزة خارج المخطّط السّنوي للتّكوين'
PREFIXE_BROUILLON = 'rapport_brouillon_'

TITRES_TYPE = {'trimestre': 'التّقرير الثّلاثي', 'semestre': 'التّقرير النّصف سنوي',
               'annee': 'التّقرير السّنوي'}

# Champs modifiables avant impression, dans l'ordre du rapport :
# (clé, libellé affiché dans la page d'édition, nature)
#   nature 'p'  : paragraphe(s) — une ligne vide sépare deux paragraphes ;
#   nature 'l'  : liste — un élément par ligne ;
#   nature 't'  : texte d'introduction + puces « - » (صلاحيّات).
CHAMPS = (
    ('titre', 'عنوان التّقرير', 'c'),
    ('date', 'تاريخ التّقرير', 'c'),
    ('intro1', '1. المهامّ والتّنظيم الهيكلي', 'p'),
    ('taches', '1.1 الصّلاحيّات (سطر تمهيدي ثمّ سطر يبدأ بـ«-» لكلّ صلاحيّة)', 't'),
    ('structure', '2.1 التّنظيم الهيكلي', 'p'),
    ('rh', '2. الموارد البشريّة — الفقرة', 'p'),
    ('rh_note', '2. الموارد البشريّة — ملاحظة بعد الجدول', 'p'),
    ('act_intro', '3. عدد الأنشطة المنجزة', 'p'),
    ('act_repartition', '3. توزّع الأنشطة', 'p'),
    ('realisation', '3. نسبة الإنجاز', 'p'),
    ('part_intro', '3. عدد المنتفعين', 'p'),
    ('part_moyenne', '3. معدّل المشاركة', 'p'),
    ('part_puces', '3. معدّل المشاركة حسب الصّفة (عنصر في كلّ سطر)', 'l'),
    ('part_sexe', '3. المشاركة حسب الجنس', 'p'),
    ('presence', '3. نسبة الحضور', 'p'),
    ('absences', '3. الغيابات', 'p'),
    ('form_intro', '3. عدد المكوّنين', 'p'),
    ('form_sexe', '3. المكوّنون حسب الجنس', 'p'),
    ('difficultes', '4. الصّعوبات والإشكاليّات (عنصر في كلّ سطر)', 'l'),
    ('propositions', '5. المقترحات (عنصر في كلّ سطر)', 'l'),
    ('signature_titre', 'الإمضاء — الصّفة', 'c'),
    ('signature_nom', 'الإمضاء — الرّتبة والاسم', 'c'),
)
CLES_CHAMPS = tuple(c[0] for c in CHAMPS)
NATURE = {c[0]: c[2] for c in CHAMPS}

# ─── Nombres et accords ─────────────────────────────────────────────────────

_RE_NOMBRE = re.compile(r'(\(?\d+(?:[.,]\d+)*\s?%?\)?)')

_MOTS = {  # (منصوب مفرد ، مجرور مفرد ، جمع)
    'nashat': ('نشاطا', 'نشاط', 'أنشطة'),
    'nashat_tak': ('نشاطا تكوينيّا', 'نشاط تكوينيّ', 'أنشطة تكوينيّة'),
    'yawm': ('يوما', 'يوم', 'أيّام'),
    'moucharik': ('مشاركا', 'مشارك', 'مشاركين'),
    'ghiyab': ('غيابا', 'غياب', 'غيابات'),
    'mokawin': ('مكوّنا', 'مكوّن', 'مكوّنين'),
    'mokawina': ('مكوّنة', 'مكوّنة', 'مكوّنات'),
    'mouahal': ('مؤهّلا', 'مؤهّل', 'مؤهّلين'),
    'mouwadhaf': ('موظّفا', 'موظّف', 'موظّفين'),
}


def n2(v):
    """Entier sur deux chiffres au moins (« 03 », « 16 », « 151 »)."""
    try:
        return f'{int(round(float(v or 0))):02d}'
    except (TypeError, ValueError):
        return '00'


def dec(v):
    """Décimal « naturel » : 5.5 / 9.43 / 72 (jamais « 72.0 »)."""
    try:
        v = round(float(v or 0), 2)
    except (TypeError, ValueError):
        return '0'
    if v == int(v):
        return str(int(v))
    return f'{v:.2f}'.rstrip('0').rstrip('.')


def pct(v):
    return dec(v) + '%'


def tamyiz(n, mot):
    """Le تمييز du nombre : pluriel pour 0 et 3…10, مجرور après une centaine
    ronde, منصوب singulier sinon (« 16 نشاطا »، « 03 غيابات »، « 100 مشارك »)."""
    acc, gen, pl = _MOTS[mot]
    try:
        n = int(round(float(n or 0)))
    except (TypeError, ValueError):
        n = 0
    r = n % 100
    if n == 0 or 3 <= r <= 10:
        return pl
    if r == 0:
        return gen
    return acc


def nb(n, mot):
    """« 16 نشاطا » — nombre sur deux chiffres suivi de son تمييز."""
    return f'{n2(n)} {tamyiz(n, mot)}'


def avec_lam(nom):
    """« ل » + nom : « المركز… » → « للمركز… », « مركز… » → « لمركز… »."""
    nom = (nom or '').strip()
    return 'لل' + nom[2:] if nom.startswith('ال') else 'ل' + nom


def date_fr(d=None):
    d = d or date.today()
    return d.strftime('%d/%m/%Y')


# ─── Brouillon (corrections de l'utilisateur) ───────────────────────────────

def cle_brouillon(p):
    if p['type'] == 'plage':
        return f"{PREFIXE_BROUILLON}plage_{p['debut']}_{p['fin']}"
    return f"{PREFIXE_BROUILLON}{p['type']}_{p['annee']}_{p['n'] or 0}"


def lire_brouillon(config, p):
    brut = (config or {}).get(cle_brouillon(p)) or ''
    try:
        d = json.loads(brut) if brut.strip() else {}
    except ValueError:
        return {}
    return {k: str(v) for k, v in d.items() if k in CLES_CHAMPS and isinstance(v, str)} \
        if isinstance(d, dict) else {}


def _norm(v):
    return '\n'.join(l.rstrip() for l in str(v or '').replace('\r\n', '\n').strip().split('\n'))


def brouillon_depuis_formulaire(form, auto):
    """Ne garde que les champs qui DIFFÈRENT du texte automatique : un texte
    non retouché continue de suivre les chiffres (données complétées plus tard)."""
    d = {}
    for cle in CLES_CHAMPS:
        if cle not in form:
            continue
        v = _norm(form.get(cle))
        if v != _norm(auto.get(cle, '')):
            d[cle] = v
    return d


# ─── Génération des textes ──────────────────────────────────────────────────

def _cadres(categories):
    """« تنفيذ المخطّط … والتّعاون الوطني والأنشطة … » selon les catégories
    réellement représentées (le plan seul par défaut)."""
    n = {c['categorie']: c['activites'] for c in categories}
    parts = []
    if n.get(cls.CATEGORIE_PLAN) or not any(n.values()):
        parts.append(CADRE_PLAN)
    if n.get(cls.CATEGORIE_COOPERATION):
        parts.append(CADRE_COOP)
    if n.get(cls.CATEGORIE_HORS_PLAN):
        parts.append(CADRE_HORS)
    return ' و'.join(parts)


def _hayaa_rh(lignes):
    tot = {k: sum(int(l.get(k) or 0) for l in lignes) for k in rd.RH_HAYAA}
    non_nuls = [k for k, v in tot.items() if v]
    noms = {'off_sup': 'هيئة الضبّاط السّامين', 'officier': 'هيئة الضبّاط الأعوان',
            'sous_off': 'هيئة ضبّاط الصفّ'}
    if len(non_nuls) == 1:
        return f'من {noms[non_nuls[0]]}'
    return 'من مختلف الهيئات'


def _phrase_absences(c, L, r, cmp, annee):
    ab = r['presence']['global']['absents']
    if ab:
        base = (f'في ذات السّياق سجّل عدد الغيابات في الأنشطة التّكوينيّة التّي تمّ تنفيذها '
                f'{c} بعنوان نفس الفترة عدد {nb(ab, "ghiyab")} من جملة المنتفعين '
                f'بالأنشطة التّكوينيّة المنجزة بمختلف رتبهم وجنسهم.')
    else:
        base = (f'في ذات السّياق لم تُسجَّل أيّ غيابات في الأنشطة التّكوينيّة التّي تمّ '
                f'تنفيذها {c} بعنوان نفس الفترة.')
    precs = cmp.get('precedents') or []
    ref = precs[0] if precs else None
    if not ref or not ref['activites']:
        return base                        # pas d'année de référence exploitable
    abp = ref['absents']
    an_ref = f'سنة {annee - 1}'
    if not abp:
        return base + f' علما وأنّه لم تُسجَّل أيّ غيابات بعنوان نفس الفترة من {an_ref}.'
    ev = cmp.get('evolution_absences') or 0
    evp = cmp.get('evolution_participants') or 0
    if ev == 0:
        return base + (f' علما وأنّ عدد الغيابات سجّل استقرارا مقارنة بعدد الغيابات المسجّلة '
                       f'بعنوان نفس الفترة من {an_ref} والمقدّرة بـ {nb(abp, "ghiyab")}.')
    sens = 'انخفاضا' if ev < 0 else 'ارتفاعا'
    if abs(ev) >= 25:
        sens += ' هامّا'
    clause = ''
    if evp:
        mouv = 'ارتفاع' if evp > 0 else 'انخفاض'
        lien = 'رغم' if (evp > 0) == (ev < 0) else 'بالتّوازي مع'
        clause = f' {lien} {mouv} عدد المتكوّنين بعنوان نفس الفترة'
    return base + (f' علما وأنّ عدد الغيابات سجّل {sens} قدّر بنسبة مئويّة تعادل {pct(abs(ev))} '
                   f'مقارنة بعدد الغيابات المسجّلة بعنوان نفس الفترة من {an_ref} والمقدّرة '
                   f'بـ {nb(abp, "ghiyab")}{clause}.')


_PUCES_CAT = (
    (rm.P_OFFICIERS, 'من بين أعوان الدّيوانة المنتمين إلى هيئة الضّبّاط'),
    (rm.P_SOUS_OFF, 'من بين أعوان الدّيوانة المنتمين إلى هيئة ضبّاط الصفّ'),
    (rm.P_RAQIB, 'من بين أعوان الدّيوانة المنتمين إلى هيئة الرّقباء'),
    (rm.P_AUTRES, 'من بين المشاركين الآخرين'),
)


def textes_auto(p, config, r, cmp):
    """Tous les textes du rapport, générés à partir des chiffres."""
    nc = idt.nom_centre(config)
    c_ba = idt.centre_avec_ba(config)
    L = p['libelle']
    A = p['annee']
    act, part, pres, form = r['activites'], r['participants'], r['presence'], r['formateurs']
    cadre = _cadres(act['categories'])
    lignes_rh = rd.lire_rh(config)
    total_rh = rd.total_rh(lignes_rh)
    t = {}
    t['titre'] = (f'تقرير نشاط {nc} {avec_lam(L)}' if p['type'] == 'plage'
                  else f"{TITRES_TYPE[p['type']]} لنشاط {nc}")
    t['date'] = date_fr()
    t['intro1'] = rd.intro_section1(config)
    t['taches'] = rd.taches(config)
    t['structure'] = rd.structure(config)
    t['rh'] = (f'يعدّ {nc} ({n2(total_rh)}) {tamyiz(total_rh, "mouwadhaf")} {_hayaa_rh(lignes_rh)} '
               f'لسلك أعوان الدّيوانة وذلك وفقا للتّفصيل المبيّن بالجدول أدناه.')
    t['rh_note'] = (config.get(rd.CLE_RH_NOTE) or '').strip()

    # ── الأنشطة ──
    t['act_intro'] = (f'بلغ عدد الأنشطة التّكوينيّة التّي أشرف على تنفيذها {nc} بعنوان {L} '
                      f'والمندرجة تباعا في إطار {cadre}، {nb(act["total"], "nashat")} مقابل '
                      f'مدّة تكوين تعادل {nb(act["jours"], "yawm")} موزّعة وفقا للتّفصيل '
                      f'المبيّن بالجدول أدناه.')
    cats = {x['categorie']: x['activites'] for x in act['categories']}
    mixte = bool(cats.get(cls.CATEGORIE_COOPERATION) or cats.get(cls.CATEGORIE_HORS_PLAN))
    rep = (f'توزّعت أنشطة التّكوين المنجزة {c_ba} بعنوان {L} '
           + ('' if mixte else f'والمندرجة في إطار {cadre} ')
           + f'على {nb(act["total"], "nashat_tak")}')
    if mixte:
        det = []
        for cat, lib in ((cls.CATEGORIE_PLAN, f'في إطار {CADRE_PLAN}'),
                         (cls.CATEGORIE_COOPERATION, f'في إطار {CADRE_COOP}'),
                         (cls.CATEGORIE_HORS_PLAN, 'خارج المخطّط السّنوي للتّكوين')):
            if cats.get(cat):
                det.append(f'{n2(cats[cat])} {lib}')
        rep += '، منها ' + ' و'.join(det)
    t['act_repartition'] = rep + '.'
    taux = r['realisation']['taux']
    t['realisation'] = (f'بلغت نسبة إنجاز الأنشطة التّكوينيّة {c_ba} بعنوان {L} والمندرجة في '
                        f'إطار {CADRE_PLAN} {pct(taux) if taux is not None else "……%"} من جملة '
                        f'الأنشطة التّكوينيّة المقرّرة والمضمّنة بالمخطّط الجهوي للتّكوين '
                        f'بعنوان سنة {A}.')

    # ── المشاركون ──
    t['part_intro'] = (f'في ذات السّياق انتفع بمختلف الأنشطة التّكوينيّة التّي أشرف على تنفيذها '
                       f'{nc} بعنوان {L} والمندرجة في إطار {cadre} عدد '
                       f'{nb(part["total"], "moucharik")} من بين مختلف هيئات سلك أعوان الدّيوانة '
                       f'وذلك وفقا للتّفصيل المضمّن بالجدول أدناه:')
    t['part_moyenne'] = (f'بلغ معدّل المشاركة في الأنشطة التّكوينيّة التّي أشرف على تنفيذها {nc} '
                         f'بعنوان {L} والمندرجة في إطار {cadre} معدّل عدد {dec(part["moyenne"])} '
                         f'مشاركا بالنّسبة لكلّ نشاط تكويني مفصّلة على النّحو التّالي ذكره بحسب '
                         f'صفة المشاركين:')
    puces = [f'ما يعادل عدد {dec(part["moyenne_categorie"][k])} مشاركا {lib}'
             for k, lib in _PUCES_CAT if part['moyenne_categorie'].get(k)]
    t['part_puces'] = '\n'.join(x + ('.' if i == len(puces) - 1 else '،')
                                for i, x in enumerate(puces))
    h, f = 'ذكر', 'أنثى'
    ps = (f'في المقابل، بلغ معدّل مشاركة جنس الذّكور من مختلف هيئات سلك أعوان الدّيوانة في '
          f'الأنشطة التّكوينيّة التّي أشرف على تنفيذها {nc} بعنوان {L} والمندرجة في إطار {cadre} '
          f'{pct(part["part_sexe"][h])} أي ما يعادل {dec(part["moyenne_sexe"][h])} مشاركا في '
          f'النّشاط التّكويني الواحد مقابل {pct(part["part_sexe"][f])} من الإناث بمعدّل '
          f'{dec(part["moyenne_sexe"][f])} مشاركا في النّشاط التّكويني الواحد.')
    nd = part['par_sexe'].get(rm.NON_DEFINI, 0)
    if nd:
        ps += f' علما وأنّ عدد {nb(nd, "moucharik")} لم يُضبط جنسهم بقاعدة البيانات.'
    t['part_sexe'] = ps

    # ── الحضور والغياب ──
    t['presence'] = (f'في نفس الإطار، بلغت نسبة الحضور في مختلف الأنشطة التّكوينيّة التّي أشرف '
                     f'على تنفيذها {nc} بعنوان نفس الفترة والمندرجة في إطار {cadre} '
                     f'{pct(pres["global"]["taux_presence"])} من جملة عدد المنتفعين من تلكم '
                     f'الأنشطة. ويبيّن الجدول التّالي نسب الحضور والغياب بحسب أصناف هيئات سلك '
                     f'أعوان الدّيوانة وجنسهم.')
    t['absences'] = _phrase_absences(c_ba, L, r, cmp, A)

    # ── المكوّنون ──
    F = form['total']
    t['form_intro'] = (f'أشرف على تأمين مختلف الأنشطة التّكوينيّة التّي تمّ إنجازها {c_ba} بعنوان '
                       f'{L} والمندرجة في إطار {cadre} عدد {nb(F, "mokawin")} '
                       f'{tamyiz(F, "mouahal")} من بين إطارات وأعوان سلك الدّيوانة وذلك وفقا '
                       f'للتّفصيل المبيّن بالجدول أدناه.')
    fh, ff = form['par_sexe'].get(h, 0), form['par_sexe'].get(f, 0)
    fs = (f'بلغ عدد المكوّنين من جنس الذّكور من بين إطارات وأعوان سلك الدّيوانة اللّذين أمّنوا '
          f'مختلف الأنشطة التّي تمّ إنجازها بعنوان {L} عدد {nb(fh, "mokawin")} مقابل عدد '
          f'{nb(ff, "mokawina")} من جنس الإناث.')
    fnd = form['par_sexe'].get(rm.NON_DEFINI, 0)
    if fnd:
        fs += f' علما وأنّ عدد {nb(fnd, "mokawin")} لم يُضبط جنسهم (دون بطاقة مكوّن).'
    t['form_sexe'] = fs
    t['difficultes'] = ''
    t['propositions'] = ''
    titre_sig, nom_sig = idt.signataire(config)
    t['signature_titre'] = f'رئيس {nc}'
    t['signature_nom'] = ' '.join(x for x in (titre_sig, nom_sig) if x)
    return t


# ─── Tableaux ───────────────────────────────────────────────────────────────

def _cel(t, fond=None, taille=12, span=1, vm=None, gras=True):
    return {'t': str(t), 'fond': fond, 'taille': taille, 'span': span, 'vm': vm, 'gras': gras}


def _bandeau(titre, n_col):
    return [_cel(titre, BLEU_BANDEAU, 14, span=n_col)]


def tableau_rh(config):
    lignes = rd.lire_rh(config)
    if not lignes:
        lignes = [{'niveau': rd.NIVEAUX_RH[0], **{k: 0 for k in rd.RH_CLES}}]
    largeurs = [1.75, 1.25, 1.5, 1.25, 1.5, 1.0, 1.0, 1.25, 1.5, 1.75, 1.25, 1.5, 1.75]
    groupes = []
    for g in rd.RH_GROUPES:
        groupes.append(_cel(g, BLEU_CLAIR, 13, span=sum(1 for c in rd.RH_COLONNES if c[2] == g)))
    rows = [
        _bandeau(f'توزيع العديد الحالي {idt.centre_avec_ba(config)}', len(largeurs)),
        [_cel('المستوى', BLEU_CLAIR, 12, vm='debut'), _cel('العدد', BLEU_CLAIR, 12, vm='debut')]
        + groupes,
        [_cel('', BLEU_CLAIR, vm='suite'), _cel('', BLEU_CLAIR, vm='suite')]
        + [_cel(c[1], None, 9) for c in rd.RH_COLONNES],
    ]
    for l in lignes:
        rows.append([_cel(l['niveau'], BLEU_CLAIR, 12), _cel(n2(rd.total_ligne(l)), BLEU_CLAIR)]
                    + [_cel(n2(l.get(k)), BLEU_CLAIR) for k in rd.RH_CLES])
    if len(lignes) > 1:
        rows.append([_cel('المجموع', BLEU_CLAIR, 12), _cel(n2(rd.total_rh(lignes)), BLEU_CLAIR)]
                    + [_cel(n2(sum(int(l.get(k) or 0) for l in lignes)), BLEU_CLAIR)
                       for k in rd.RH_CLES])
    return {'cle': 'rh', 'largeurs': largeurs, 'lignes': rows}


def tableau_categories(r, L):
    largeurs = [6.25, 4.2, 3.45]
    rows = [_bandeau(f'توزيع الأنشطة التّكوينيّة بعنوان {L}', 3),
            [_cel('تصنيف النّشاط', BLEU_CLAIR, 13), _cel('عدد الأنشطة المنجزة', BLEU_CLAIR, 13),
             _cel('مدّة التّكوين', BLEU_CLAIR, 13)]]
    for c in r['activites']['categories']:
        rows.append([_cel(c['categorie'], BLEU_CLAIR, 13), _cel(n2(c['activites']), None, 13),
                     _cel(n2(c['jours']), None, 13)])
    rows.append([_cel('المجموع العامّ', BLEU_CLAIR, 13),
                 _cel(n2(r['activites']['total']), BLEU_CLAIR, 13),
                 _cel(n2(r['activites']['jours']), BLEU_CLAIR, 13)])
    return {'cle': 'categories', 'largeurs': largeurs, 'lignes': rows}


_LARG_7 = [4.05, 2.03, 2.03, 1.88, 1.89, 1.93, 1.93]


def _entete_7(premier, cats):
    return ([_cel(premier, BLEU_CLAIR, 13)] + [_cel(k, 'FFFFFF', 13) for k in cats]
            + [_cel('ذكور', 'FFFFFF', 13), _cel('إناث', 'FFFFFF', 13)])


def tableau_participants(r, L):
    p = r['participants']
    rows = [_bandeau(f'توزيع المنتفعين بالأنشطة التّكوينيّة بعنوان {L}', 7),
            _entete_7('العدد الجملي للمشاركين', rm.CATEGORIES_PARTICIPANTS),
            [_cel(n2(p['total']), BLEU_CLAIR, 13)]
            + [_cel(n2(p['par_categorie'][k]), 'FFFFFF', 13) for k in rm.CATEGORIES_PARTICIPANTS]
            + [_cel(n2(p['par_sexe']['ذكر']), 'FFFFFF', 13),
               _cel(n2(p['par_sexe']['أنثى']), 'FFFFFF', 13)]]
    return {'cle': 'participants', 'largeurs': _LARG_7, 'lignes': rows}


def _taux(bloc, cle):
    return pct(bloc[cle]) if bloc['total'] else '00.0%'


def tableau_presence(r, L):
    p, pr = r['participants'], r['presence']
    blocs = ([pr['global']] + [pr['par_categorie'][k] for k in rm.CATEGORIES_PARTICIPANTS]
             + [pr['par_sexe']['ذكر'], pr['par_sexe']['أنثى']])
    rows = [_bandeau(f'توزيع نسب الحضور والغياب بالأنشطة التّكوينيّة بعنوان {L}', 7),
            _entete_7('العدد الجملي للمشاركين', rm.CATEGORIES_PARTICIPANTS),
            [_cel(n2(p['total']), BLEU_CLAIR, 13)]
            + [_cel(n2(b['total']), 'FFFFFF', 13) for b in blocs[1:]]]
    for lib, cle in (('نسبة الحضور', 'taux_presence'), ('نسبة الغيابات', 'taux_absence')):
        rows.append([_cel(lib, BLEU_CLAIR, 12)] + [_cel(_taux(b, cle), 'FFFFFF', 12)
                                                   for b in blocs[1:]])
    return {'cle': 'presence', 'largeurs': _LARG_7, 'lignes': rows}


def tableau_formateurs(r, L):
    f = r['formateurs']
    rows = [_bandeau(f'توزيع المكوّنين المشرفين على الأنشطة التّكوينيّة بعنوان {L}', 7),
            _entete_7('العدد الجملي للمكوّنين', rm.CATEGORIES_FORMATEURS),
            [_cel(n2(f['total']), BLEU_CLAIR, 13)]
            + [_cel(n2(f['par_categorie'][k]), 'FFFFFF', 13) for k in rm.CATEGORIES_FORMATEURS]
            + [_cel(n2(f['par_sexe']['ذكر']), 'FFFFFF', 13),
               _cel(n2(f['par_sexe']['أنثى']), 'FFFFFF', 13)]]
    return {'cle': 'formateurs', 'largeurs': [4.05, 2.32, 2.25, 2.0, 2.0, 2.04, 1.66],
            'lignes': rows}


# ─── Contenu complet ────────────────────────────────────────────────────────

def contenu(periode, config, brouillon=None, calcul=None, comparaison=None):
    """Le rapport complet : textes (automatiques puis corrigés), tableaux,
    alertes. `calcul` / `comparaison` peuvent être fournis pour éviter de
    recalculer (tests, aperçu)."""
    config = config or {}
    r = calcul or rm.calculer(periode)
    cmp = comparaison or rm.comparer(periode, 1)
    auto = textes_auto(periode, config, r, cmp)
    brouillon = lire_brouillon(config, periode) if brouillon is None else brouillon
    textes = dict(auto)
    for k, v in brouillon.items():
        if k in textes:
            textes[k] = v
    L = periode['libelle']
    nc = idt.nom_centre(config)
    v = idt.ville(config)
    alertes = []
    if not r['activites']['total']:
        alertes.append('لا توجد أنشطة مختومة في هذه الفترة: الأرقام كلّها أصفار.')
    if r['non_finalisees']:
        alertes.append(f'{n2(r["non_finalisees"])} دورة/دورات من الفترة غير مختومة ولم تُحتسب '
                       f'(تُختم من «الختم والمستحقّات»).')
    if r['realisation']['taux'] is None:
        alertes.append(f'لم يُضبط عدد الدّورات المبرمجة لسنة {periode["annee"]}: نسبة الإنجاز '
                       f'ستظهر «……%» (الإعدادات ← التّقارير).')
    if not rd.lire_rh(config):
        alertes.append('جدول الموارد البشريّة غير مضبوط بعدُ (الإعدادات ← التّقارير).')
    if r['participants']['par_sexe'].get(rm.NON_DEFINI):
        alertes.append(f'{n2(r["participants"]["par_sexe"][rm.NON_DEFINI])} مشاركا دون جنس '
                       f'مضبوط.')
    if r['formateurs']['sans_fiche']:
        alertes.append(f'{n2(r["formateurs"]["sans_fiche"])} مكوّنا دون بطاقة بقائمة المكوّنين '
                       f'(الجنس والصّنف مستنتجان من الرّتبة).')
    if not textes['difficultes'].strip() or not textes['propositions'].strip():
        alertes.append('الفقرتان 4 (الصّعوبات) و5 (المقترحات) تُكتبان يدويّا — إن بقيتا '
                       'فارغتين تُطبع أسطر منقّطة.')
    return {
        'periode': periode,
        'cle_brouillon': cle_brouillon(periode),
        'entete': [l for i, l in enumerate(idt.ENTETE_NATIONAL_ORNE) if i != 2]
        + idt.lignes_entete_centre(config),
        'ligne_date': (f'{v} في: {textes["date"]}' if v else textes['date']).strip(),
        'nom_centre': nc,
        'textes': textes,
        'auto': auto,
        'modifies': sorted(k for k in brouillon if k in auto and brouillon[k] != auto[k]),
        'tableaux': {
            'rh': tableau_rh(config),
            'categories': tableau_categories(r, L),
            'participants': tableau_participants(r, L),
            'presence': tableau_presence(r, L),
            'formateurs': tableau_formateurs(r, L),
        },
        'alertes': alertes,
        'chiffres': {'activites': r['activites']['total'], 'jours': r['activites']['jours'],
                     'participants': r['participants']['total'],
                     'absents': r['presence']['global']['absents'],
                     'formateurs': r['formateurs']['total'],
                     'taux_realisation': r['realisation']['taux'],
                     'non_finalisees': r['non_finalisees']},
    }


# ─── Plan commun Word / PDF ─────────────────────────────────────────────────

def _paragraphes(texte):
    """Découpe un champ en paragraphes (une ligne = un paragraphe)."""
    return [l.strip() for l in str(texte or '').replace('\r\n', '\n').split('\n') if l.strip()]


def _elements(texte):
    """Éléments d'une liste : un par ligne, symboles de puce retirés."""
    return [re.sub(r'^[-•▪✓*]\s*', '', l) for l in _paragraphes(texte)]


def plan(c):
    """Suite ordonnée de blocs, rendue à l'identique en Word et en PDF :
    ('titre', t) ('h', t) ('p', t) ('puce', t, symbole) ('tab', tableau)
    ('pointilles',) ('signature', [l1, l2])."""
    t, tab, nc = c['textes'], c['tableaux'], c['nom_centre']
    b = [('titre', t['titre'])]
    b.append(('h', '1. المهامّ والتّنظيم الهيكلي:'))
    b += [('p', x) for x in _paragraphes(t['intro1'])]
    b.append(('h', f'1.1 صلاحيّات {nc}:'))
    intro, puces = rd.decouper_puces(t['taches'])
    if intro:
        b.append(('p', intro))
    b += [('puce', x, '-') for x in puces]
    b.append(('h', f'2.1 التّنظيم الهيكلي {avec_lam(nc)}:'))
    b += [('p', x) for x in _paragraphes(t['structure'])]
    b.append(('h', '2. الموارد البشريّة:'))
    b += [('p', x) for x in _paragraphes(t['rh'])]
    b.append(('tab', tab['rh']))
    b += [('p', x) for x in _paragraphes(t['rh_note'])]
    b.append(('h', '3. الأنشطة التّكوينيّة المنجزة :'))
    b += [('p', x) for x in _paragraphes(t['act_intro'])]
    b.append(('tab', tab['categories']))
    for k in ('act_repartition', 'realisation', 'part_intro'):
        b += [('p', x) for x in _paragraphes(t[k])]
    b.append(('tab', tab['participants']))
    b += [('p', x) for x in _paragraphes(t['part_moyenne'])]
    b += [('puce', x, '✓') for x in _elements(t['part_puces'])]
    for k in ('part_sexe', 'presence'):
        b += [('p', x) for x in _paragraphes(t[k])]
    b.append(('tab', tab['presence']))
    for k in ('absences', 'form_intro'):
        b += [('p', x) for x in _paragraphes(t[k])]
    b.append(('tab', tab['formateurs']))
    b += [('p', x) for x in _paragraphes(t['form_sexe'])]
    b.append(('h', '4. الصّعوبات والإشكاليّات'))
    b.append(('p', 'تتمثّل الصّعوبات والإشكاليّات فيما يلي:'))
    elems = _elements(t['difficultes'])
    b += [('puce', x, '▪') for x in elems] if elems else [('pointilles',)]
    b.append(('h', '5. المقترحات:'))
    elems = _elements(t['propositions'])
    b += [('puce', x, '▪') for x in elems] if elems else [('pointilles',)]
    b.append(('signature', [t['signature_titre'], t['signature_nom']]))
    return b


# ═══════════════════════════════════════════════════════════════════════════
#  WORD
# ═══════════════════════════════════════════════════════════════════════════

W_CORPS, W_NOMBRE = 16, 14            # tailles du modèle (texte / chiffres gras)


def _w_runs(texte, taille=W_CORPS, gras=False, taille_nb=W_NOMBRE):
    from core import docx_ecrivain as dw
    out = []
    for i, part in enumerate(_RE_NOMBRE.split(texte)):
        if not part:
            continue
        if i % 2:
            out.append(dw.run(part, taille_nb if not gras else taille, gras=True, ltr=True))
        else:
            out.append(dw.run(part, taille, gras=gras))
    return out


def _w_tableau(tb):
    from core import docx_ecrivain as dw
    larg = tb['largeurs']
    lignes = []
    n = len(tb['lignes'])
    for i, row in enumerate(tb['lignes']):
        cells, col = [], 0
        for cel in row:
            w = sum(larg[col:col + cel['span']])
            col += cel['span']
            par = dw.paragraphe([dw.run(cel['t'], cel['taille'], gras=cel['gras'],
                                        ltr=bool(re.fullmatch(r'[\d.,%\s]+', cel['t'])))]
                                if cel['t'] else '', align='centre', taille=cel['taille'],
                                garder_suivant=i < n - 1)
            fond = cel['fond'] if cel['fond'] and cel['fond'] != 'FFFFFF' else None
            cells.append(dw.cellule([par], w, fond=fond, colonnes=cel['span'],
                                    fusion_v=cel['vm'], marges_cm=0.03))
        lignes.append(dw.ligne(cells, entete=(i == 0), hauteur_cm=0.62))
    return dw.tableau(larg, lignes, bordure_ext=('single', 6), bordure_h=('single', 4),
                      bordure_v=('single', 4), marge_cellule_cm=0.08)


def _w_indent(xml, first_cm=None, hanging_cm=None):
    from core import docx_ecrivain as dw
    if first_cm:
        attr = f'w:firstLine="{dw.tw(first_cm)}"'
    else:
        attr = f'w:hanging="{dw.tw(hanging_cm)}"'
    if '<w:ind ' in xml:
        return xml.replace('<w:ind ', f'<w:ind {attr} ', 1)
    return xml.replace('<w:jc ', f'<w:ind {attr}/><w:jc ', 1)


def docx_rapport(c):
    """Le rapport en .docx (octets)."""
    from core import docx_ecrivain as dw
    doc = dw.DocumentWord(marges_cm=(1.2, 1.25, 1.6, 1.5), titre=c['textes']['titre'])
    P = dw.paragraphe
    # ── ترويسة (bloc centré à droite) + date à gauche ──
    ent = [P(l, align='centre', taille=12, gras=True) for l in c['entete']]
    date_p = P(c['ligne_date'], align='gauche', taille=12, gras=True)
    doc.ajouter(dw.tableau([9.0, 9.25], [dw.ligne([dw.cellule(ent, 9.0, valign='top'),
                                                  dw.cellule([date_p], 9.25, valign='top')],
                                                 insecable=False)],
                           bordure_ext=None, bordure_h=None, bordure_v=None, centre=False,
                           marge_cellule_cm=0.0))
    for bloc in plan(c):
        nature = bloc[0]
        if nature == 'titre':
            doc.ajouter(P('', taille=12), P('', taille=12),
                        P(bloc[1], align='centre', taille=20, gras=True, apres=6),
                        *[P('', taille=12) for _ in range(5)])
        elif nature == 'h':
            doc.ajouter(P([dw.run(bloc[1], W_CORPS, gras=True, souligne=True)],
                          align='droite', taille=W_CORPS, avant=8, apres=4,
                          garder_suivant=True))
        elif nature == 'p':
            doc.ajouter(_w_indent(P(_w_runs(bloc[1]), align='justifie', taille=W_CORPS,
                                    apres=6), first_cm=1.0))
        elif nature == 'puce':
            sym = bloc[2]
            police = 'Segoe UI Symbol' if sym == '✓' else 'Arial'
            runs = [dw.run(sym + ' ', W_CORPS, police=police)] + _w_runs(bloc[1])
            doc.ajouter(_w_indent(P(runs, align='justifie', taille=W_CORPS, apres=2,
                                    retrait_debut=1.3), hanging_cm=0.6))
        elif nature == 'tab':
            doc.ajouter(P('', taille=6, garder_suivant=True), _w_tableau(bloc[1]),
                        P('', taille=8))
        elif nature == 'pointilles':
            for _ in range(3):
                doc.ajouter(P('.' * 110, align='centre', taille=12, apres=6))
        elif nature == 'signature':
            sig = [P(l, align='centre', taille=14, gras=True, apres=10) for l in bloc[1] if l]
            doc.ajouter(P('', taille=12), P('', taille=12),
                        dw.tableau([7.25, 11.0], [dw.ligne([dw.cellule([P('')], 7.25),
                                                           dw.cellule(sig, 11.0)])],
                                   bordure_ext=None, bordure_h=None, bordure_v=None,
                                   centre=False, marge_cellule_cm=0.0))
    num = ('<w:r><w:rPr><w:sz w:val="18"/><w:szCs w:val="18"/></w:rPr>'
           '<w:fldChar w:fldCharType="begin"/></w:r><w:r><w:rPr><w:sz w:val="18"/>'
           '<w:szCs w:val="18"/></w:rPr><w:instrText xml:space="preserve"> PAGE </w:instrText>'
           '</w:r><w:r><w:rPr><w:sz w:val="18"/><w:szCs w:val="18"/></w:rPr>'
           '<w:fldChar w:fldCharType="end"/></w:r>')
    doc.pied = [P([num], align='centre', taille=9)]
    return doc.octets()


# ═══════════════════════════════════════════════════════════════════════════
#  PDF
# ═══════════════════════════════════════════════════════════════════════════

CM = 28.3465
P_CORPS = 15.0                  # taille du corps (police KasAr ≈ Arial 16 du modèle)
P_NOMBRE = 13.0
P_INTERLIGNE = 1.7             # pas de ligne / taille (rendu aéré du modèle)
P_RETRAIT = 1.0 * CM


class _MiseEnPage:
    """Composition du PDF : curseur vertical, sauts de page, pied de page."""

    def __init__(self, canvas_, largeur, hauteur):
        self.c = canvas_
        self.W, self.H = largeur, hauteur
        self.xr = self.W - 1.25 * CM
        self.xl = 1.5 * CM
        self.haut = self.H - 1.2 * CM
        self.bas = 1.8 * CM
        self.y = self.haut
        self.page = 1

    # ── pages ──
    def _pied(self):
        from core.pdf_generator import F_AR
        self.c.setFont(F_AR, 9)
        self.c.setFillColorRGB(0, 0, 0)
        self.c.drawCentredString(self.W / 2, 0.9 * CM, str(self.page))

    def nouvelle_page(self):
        self._pied()
        self.c.showPage()
        self.page += 1
        self.y = self.haut

    def assurer(self, h):
        if self.y - h < self.bas:
            self.nouvelle_page()

    def terminer(self):
        self._pied()
        self.c.save()

    # ── texte ──
    def _mots(self, texte, taille, gras):
        from core.pdf_generator import ar, F_AR, F_ARB
        mots = []
        for m in str(texte).split():
            chiffre = bool(re.search(r'\d', m))
            font = F_ARB if (gras or chiffre) else F_AR
            size = P_NOMBRE * taille / P_CORPS if (chiffre and not gras) else taille
            vis = ar(m)
            mots.append((vis, font, size, self.c.stringWidth(vis, font, size)))
        return mots

    def paragraphe(self, texte, taille=P_CORPS, gras=False, retrait1=P_RETRAIT, x_droite=None,
                   apres=None, align='justifie', souligne=False, avant_ligne=None):
        """Paragraphe RTL justifié, chiffres en gras ; `avant_ligne(y)` dessine
        un symbole de puce à la hauteur de la première ligne."""
        from core.pdf_generator import F_AR
        xr = x_droite if x_droite is not None else self.xr
        larg = xr - self.xl
        mots = self._mots(texte, taille, gras)
        if not mots:
            return
        esp = self.c.stringWidth(' ', F_AR, taille)
        lignes, cur, w = [], [], 0.0
        for m in mots:
            dispo = larg - (retrait1 if not lignes else 0)
            ajout = m[3] + (esp if cur else 0)
            if cur and w + ajout > dispo:
                lignes.append(cur)
                cur, w = [m], m[3]
            else:
                cur.append(m)
                w += ajout
        if cur:
            lignes.append(cur)
        pas = taille * P_INTERLIGNE
        for i, ligne in enumerate(lignes):
            self.assurer(pas)
            self.y -= pas
            x0 = xr - (retrait1 if i == 0 else 0)
            dispo = x0 - self.xl
            total = sum(m[3] for m in ligne)
            derniere = i == len(lignes) - 1
            if align == 'justifie' and not derniere and len(ligne) > 1:
                gap = (dispo - total) / (len(ligne) - 1)
            else:
                gap = esp
            if align == 'centre':
                x0 = self.xl + (larg + total + gap * (len(ligne) - 1)) / 2
            if i == 0 and avant_ligne:
                avant_ligne(self.y)
            x = x0
            for vis, font, size, wm in ligne:
                self.c.setFont(font, size)
                self.c.drawString(x - wm, self.y, vis)
                x -= wm + gap
            if souligne:
                self.c.setLineWidth(0.8)
                self.c.line(x + gap, self.y - 2.5, x0, self.y - 2.5)
        self.y -= taille * 0.45 if apres is None else apres

    # ── tableaux ──
    def tableau(self, tb):
        from core.pdf_generator import ar, _wrap_log, F_AR, F_ARB
        c = self.c
        larg = [l * CM for l in tb['largeurs']]
        total_w = sum(larg)
        x_droite = (self.xr + self.xl) / 2 + total_w / 2
        bords = [x_droite]
        for l in larg:
            bords.append(bords[-1] - l)
        # grille : position de chaque cellule et hauteur de chaque ligne
        grille, hauteurs = [], []
        for row in tb['lignes']:
            col, cells, h = 0, [], 0.72 * CM
            for cel in row:
                x1, x0 = bords[col], bords[col + cel['span']]
                font = F_ARB if cel['gras'] else F_AR
                size = cel['taille'] * 0.9
                lignes = _wrap_log(c, cel['t'], font, size, (x1 - x0) - 4) if cel['t'] else []
                cells.append((cel, col, x0, x1, font, size, lignes))
                if cel['vm'] is None:
                    h = max(h, len(lignes) * size * 1.3 + 6)
                col += cel['span']
            grille.append(cells)
            hauteurs.append(h)
        self.assurer(sum(hauteurs) + 4)
        self.y -= 4
        tops = []
        y = self.y
        for h in hauteurs:
            tops.append(y)
            y -= h
        for i, cells in enumerate(grille):
            for cel, col, x0, x1, font, size, lignes in cells:
                if cel['vm'] == 'suite':
                    continue
                h = hauteurs[i]
                if cel['vm'] == 'debut':        # étendre sur les lignes « suite »
                    j = i + 1
                    while j < len(grille) and any(k[1] == col and k[0]['vm'] == 'suite'
                                                  for k in grille[j]):
                        h += hauteurs[j]
                        j += 1
                top = tops[i]
                if cel['fond'] and cel['fond'] != 'FFFFFF':
                    f = cel['fond']
                    c.setFillColorRGB(int(f[:2], 16) / 255, int(f[2:4], 16) / 255,
                                      int(f[4:], 16) / 255)
                    c.rect(x0, top - h, x1 - x0, h, stroke=0, fill=1)
                c.setFillColorRGB(0, 0, 0)
                c.setLineWidth(0.6)
                c.rect(x0, top - h, x1 - x0, h, stroke=1, fill=0)
                pas = size * 1.3
                ybase = top - h / 2 + (len(lignes) * pas) / 2 - size * 0.95
                for k, l in enumerate(lignes):
                    c.setFont(font, size)
                    c.drawCentredString((x0 + x1) / 2, ybase - k * pas, ar(l))
        c.setLineWidth(1.0)
        c.rect(bords[-1], y, total_w, self.y - y, stroke=1, fill=0)
        self.y = y - 10


def _coche(c, x, y, taille):
    """Petite coche ✓ dessinée (la police arabe n'a pas le glyphe)."""
    c.setLineWidth(1.1)
    s = taille * 0.55
    p = c.beginPath()
    p.moveTo(x, y + s * 0.45)
    p.lineTo(x + s * 0.35, y + s * 0.1)
    p.lineTo(x + s, y + s * 0.85)
    c.drawPath(p, stroke=1, fill=0)


def pdf_rapport(c, chemin, base_dir):
    """Écrit le rapport PDF dans `chemin`."""
    from reportlab.pdfgen import canvas as rl_canvas
    from core.pdf_generator import _register_fonts, ar, F_AR, F_ARB
    _register_fonts(base_dir)
    A4W, A4H = 595.32, 841.92
    cv = rl_canvas.Canvas(chemin, pagesize=(A4W, A4H))
    cv.setTitle(c['textes']['titre'])
    m = _MiseEnPage(cv, A4W, A4H)
    # ── ترويسة ──
    taille_e, pas_e = 11.5, 17.5
    larg_e = max(cv.stringWidth(ar(l), F_ARB, taille_e) for l in c['entete']) if c['entete'] else 0
    xc = m.xr - larg_e / 2
    y = m.haut
    for l in c['entete']:
        y -= pas_e
        cv.setFont(F_ARB, taille_e)
        cv.drawCentredString(xc, y, ar(l))
    cv.setFont(F_ARB, taille_e)
    cv.drawString(m.xl, m.haut - pas_e, ar(c['ligne_date']))
    m.y = y - 2 * pas_e
    for bloc in plan(c):
        nature = bloc[0]
        if nature == 'titre':
            m.paragraphe(bloc[1], taille=19, gras=True, retrait1=0, align='centre', apres=0)
            m.y -= 4.4 * P_CORPS * P_INTERLIGNE
        elif nature == 'h':
            m.assurer(P_CORPS * P_INTERLIGNE * 3.2)
            m.y -= 4
            m.paragraphe(bloc[1], gras=True, retrait1=0, align='droite', souligne=True, apres=2)
        elif nature == 'p':
            m.paragraphe(bloc[1])
        elif nature == 'puce':
            sym = bloc[2]
            x_sym = m.xr - 0.75 * CM

            def dessin(yl, sym=sym, x_sym=x_sym):
                cv.setFillColorRGB(0, 0, 0)
                if sym == '✓':
                    _coche(cv, x_sym + 2, yl, P_CORPS)
                elif sym == '▪':
                    cv.rect(x_sym + 4, yl + 3, 4.2, 4.2, stroke=0, fill=1)
                else:
                    cv.setFont(F_AR, P_CORPS)
                    cv.drawString(x_sym + 4, yl, '-')
            m.paragraphe(bloc[1], retrait1=0, x_droite=m.xr - 1.3 * CM, avant_ligne=dessin,
                         apres=1)
        elif nature == 'tab':
            m.tableau(bloc[1])
        elif nature == 'pointilles':
            for _ in range(3):
                m.assurer(P_CORPS * P_INTERLIGNE)
                m.y -= P_CORPS * P_INTERLIGNE
                cv.setFont(F_AR, P_CORPS)
                pt = '.' * int((m.xr - m.xl - P_RETRAIT) / cv.stringWidth('.', F_AR, P_CORPS))
                cv.drawRightString(m.xr, m.y, pt)
        elif nature == 'signature':
            lignes = [l for l in bloc[1] if l]
            m.assurer(len(lignes) * 30 + 40)
            m.y -= 30
            larg_max = max(cv.stringWidth(ar(l), F_ARB, 12.5) for l in lignes) if lignes else 0
            xs = max(m.xl + 4.6 * CM, m.xl + larg_max / 2)
            for l in lignes:
                cv.setFont(F_ARB, 12.5)
                cv.drawCentredString(xs, m.y, ar(l))
                m.y -= 26
    m.terminer()
    return chemin
