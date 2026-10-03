# -*- coding: utf-8 -*-
"""Conversion de nombres, d'heures et de dates en toutes lettres arabes.

Utilisé par la مذكرة (étape 6) pour produire des tournures du type :
    14        → « أربعة عشر »
    « 08:30 » → « الثّامنة والنّصف صباحا »
    2026-09-23 → « 23 سبتمبر 2026 »
"""

import re

# ── Nombres ──────────────────────────────────────────────────────────────────
# Forme employée devant un nom masculin : « أربعة عشر مشاركا »
_UNITES = ['', 'واحد', 'اثنان', 'ثلاثة', 'أربعة', 'خمسة',
           'ستّة', 'سبعة', 'ثمانية', 'تسعة']

_TEENS = {
    11: 'أحد عشر',    12: 'اثنا عشر',   13: 'ثلاثة عشر',
    14: 'أربعة عشر',  15: 'خمسة عشر',   16: 'ستّة عشر',
    17: 'سبعة عشر',   18: 'ثمانية عشر', 19: 'تسعة عشر',
}

_DIZAINES = {
    10: 'عشرة',   20: 'عشرون',  30: 'ثلاثون', 40: 'أربعون', 50: 'خمسون',
    60: 'ستّون',  70: 'سبعون',  80: 'ثمانون', 90: 'تسعون',
}

_CENTAINES = {
    100: 'مائة',       200: 'مائتان',     300: 'ثلاثمائة',
    400: 'أربعمائة',   500: 'خمسمائة',    600: 'ستّمائة',
    700: 'سبعمائة',    800: 'ثمانمائة',   900: 'تسعمائة',
}


def nombre_en_lettres(n):
    """Entier (1-999) → toutes lettres arabes. Retourne '' si invalide."""
    try:
        n = int(n)
    except (TypeError, ValueError):
        return ''
    if n <= 0:
        return ''
    if n < 10:
        return _UNITES[n]
    if n == 10:
        return _DIZAINES[10]
    if n in _TEENS:
        return _TEENS[n]
    if n < 100:
        d, u = divmod(n, 10)
        dz = _DIZAINES[d * 10]
        return f'{_UNITES[u]} و{dz}' if u else dz
    if n < 1000:
        ct, reste = divmod(n, 100)
        base = _CENTAINES.get(ct * 100, '')
        if not base:
            return str(n)
        return base if not reste else f'{base} و{nombre_en_lettres(reste)}'
    return str(n)


def nombre_complet(n):
    """Entier 0 – 999 999 → toutes lettres (« ألف وخمسمائة وعشرون »)."""
    try:
        n = int(n)
    except (TypeError, ValueError):
        return ''
    if n <= 0:
        return 'صفر' if n == 0 else ''
    if n < 1000:
        return nombre_en_lettres(n)
    if n > 999999:
        return str(n)
    m, reste = divmod(n, 1000)
    if m == 1:
        milliers = 'ألف'
    elif m == 2:
        milliers = 'ألفان'
    elif 3 <= m <= 10:
        milliers = f'{nombre_en_lettres(m)} آلاف'
    elif m % 100 in range(11, 100):
        milliers = f'{nombre_en_lettres(m)} ألفا'
    else:
        milliers = f'{nombre_en_lettres(m)} ألف'
    return milliers if not reste else f'{milliers} و{nombre_en_lettres(reste)}'


def quantite_en_lettres(n, singulier, singulier_mansoub, duel, pluriel):
    """Nombre + nom compté, au nominatif (« مبلغ قدره … ») :
        1 → « دينار واحد »      2 → « ديناران »
        …3 – …10 → « … دنانير »  …11 – …99 → « … دينارا »
        …00, …01, …02 (≥ 100) → « … دينار »"""
    try:
        n = int(n)
    except (TypeError, ValueError):
        return ''
    if n <= 0:
        return ''
    if n == 1:
        return f'{singulier} واحد'
    if n == 2:
        return duel
    if n >= 1000 and n % 1000 == 0 and n <= 999000:
        # Milliers ronds suivis du nom : إضافة — « ألفا دينار »، « اثنا عشر ألف دينار ».
        m = n // 1000
        if m == 1:
            return f'ألف {singulier}'
        if m == 2:
            return f'ألفا {singulier}'
        if 3 <= m <= 10:
            return f'{nombre_en_lettres(m)} آلاف {singulier}'
        return f'{nombre_en_lettres(m)} ألف {singulier}'
    queue = n % 100
    if 3 <= queue <= 10:
        nom = pluriel
    elif 11 <= queue <= 99:
        nom = singulier_mansoub
    else:
        nom = singulier
    return f'{nombre_complet(n)} {nom}'


def expression_comptee(n, singulier, duel, pluriel):
    """Nombre + nom accordé selon les règles du تمييز العدد arabe, dans un
    contexte où le مميز est attendu au génitif/accusatif (après « بـ »,
    « مشاركة »…) :

        1        → « <singulier> واحد »
        2        → « <duel> اثنان »
        3 – 10   → « <nombre> <pluriel> »        (جمع مجرور)
        11 – …   → « <nombre> <singulier> »       (مفرد منصوب / تمييز)

    Ex. expression_comptee(3, 'مشاركا', 'مشاركين', 'مشاركين') → « ثلاثة مشاركين »
        expression_comptee(14,'مشاركا', 'مشاركين', 'مشاركين') → « أربعة عشر مشاركا »
    """
    try:
        n = int(n)
    except (TypeError, ValueError):
        return ''
    if n <= 0:
        return ''
    if n == 1:
        return f'{singulier} واحد'
    if n == 2:
        return f'{duel} اثنان'
    if 3 <= n <= 10:
        return f'{nombre_en_lettres(n)} {pluriel}'
    return f'{nombre_en_lettres(n)} {singulier}'


def expression_participants(n):
    """« عدد المشاركين » correctement accordé dans un contexte génitif
    (« بمشاركة … »), selon les règles du تمييز العدد :

        1        → مشارك واحد           (مفرد)
        2        → مشاركين اثنين         (مثنّى مجرور)
        3 – 10   → ثلاثة … عشرة مشاركين  (جمع مجرور)
        11 – 99  → … مشاركا              (مفرد منصوب – تمييز)
        ≥ 100    → مائة … مشارك          (مفرد مجرور)

    Retourne « المشاركين » si le nombre est nul/invalide."""
    try:
        n = int(n)
    except (TypeError, ValueError):
        return 'المشاركين'
    if n <= 0:
        return 'المشاركين'
    if n == 1:
        return 'مشارك واحد'
    if n == 2:
        return 'مشاركين اثنين'
    if 3 <= n <= 10:
        return f'{nombre_en_lettres(n)} مشاركين'
    if n < 100:
        return f'{nombre_en_lettres(n)} مشاركا'
    return f'{nombre_en_lettres(n)} مشارك'


# ── Heures ───────────────────────────────────────────────────────────────────
_HEURES = {
    1: 'الواحدة',  2: 'الثّانية',  3: 'الثّالثة',  4: 'الرّابعة',
    5: 'الخامسة',  6: 'السّادسة',  7: 'السّابعة',  8: 'الثّامنة',
    9: 'التّاسعة', 10: 'العاشرة', 11: 'الحادية عشرة', 12: 'الثّانية عشرة',
}

# Chiffres arabo-indiens (orientaux et persans) → chiffres ASCII
_AR_DIGITS = str.maketrans('٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹',
                           '01234567890123456789')

HEURE_DEFAUT = 'الثّامنة والنّصف صباحا'


def parse_heure(txt):
    """Extrait (heure, minute) d'une chaîne libre : « 08:30 », « 8h30 »,
    « من 08:30 إلى 10:00 »… Retourne None si rien d'exploitable."""
    if not txt:
        return None
    s = str(txt).translate(_AR_DIGITS)
    m = re.search(r'(\d{1,2})\s*[:hH\.]\s*(\d{1,2})', s)
    if m:
        h, mi = int(m.group(1)), int(m.group(2))
    else:
        m = re.search(r'(\d{1,2})', s)
        if not m:
            return None
        h, mi = int(m.group(1)), 0
    if not (0 <= h <= 23 and 0 <= mi <= 59):
        return None
    return h, mi


def heure_en_lettres(txt, defaut=HEURE_DEFAUT):
    """« 08:30 » → « الثّامنة والنّصف صباحا »."""
    hm = parse_heure(txt)
    if not hm:
        return defaut
    h, mi = hm
    periode = 'صباحا' if h < 12 else 'بعد الزّوال'
    base = _HEURES[h % 12 or 12]
    if mi == 0:
        frac = ''
    elif mi == 15:
        frac = ' والرّبع'
    elif mi == 30:
        frac = ' والنّصف'
    elif mi == 45:
        frac = ' وثلاثة أرباع'
    else:
        frac = f' و{nombre_en_lettres(mi)} دقيقة'
    return f'{base}{frac} {periode}'


# ── Dates ────────────────────────────────────────────────────────────────────
MOIS_AR = ['جانفي', 'فيفري', 'مارس', 'أفريل', 'ماي', 'جوان',
           'جويلية', 'أوت', 'سبتمبر', 'أكتوبر', 'نوفمبر', 'ديسمبر']

JOURS_AR = ['الاثنين', 'الثلاثاء', 'الأربعاء', 'الخميس',
            'الجمعة', 'السبت', 'الأحد']


def date_longue(iso):
    """« 2026-09-23 » → « 23 سبتمبر 2026 ». Renvoie la chaîne telle quelle
    si elle n'est pas au format ISO."""
    if not iso:
        return ''
    try:
        from datetime import datetime as _dt
        d = _dt.strptime(str(iso).strip(), '%Y-%m-%d')
        return f'{d.day} {MOIS_AR[d.month - 1]} {d.year}'
    except Exception:
        return str(iso)


def jour_semaine(iso):
    """« 2026-09-23 » → « الأربعاء ». Chaîne vide si format invalide."""
    if not iso:
        return ''
    try:
        from datetime import datetime as _dt
        d = _dt.strptime(str(iso).strip(), '%Y-%m-%d')
        return JOURS_AR[d.weekday()]
    except Exception:
        return ''


# ══════════════════════════════════════════════════════════════════════════════
#  HIÉRARCHIE — rattachement des services et classement des grades
# ══════════════════════════════════════════════════════════════════════════════

# Grades d'OFFICIERS   : de عميد à ملازم
GRADES_OFFICIERS = [
    'عميد', 'عقيد', 'مقدم', 'رائد', 'نقيب', 'ملازم أول', 'ملازم',
]
# Grades de SOUS-OFFICIERS : de وكيل أول à عريف
GRADES_SOUS_OFFICIERS = [
    'وكيل أول', 'وكيل', 'رقيب أول', 'رقيب', 'عريف أول', 'عريف',
]


def normaliser_ar(txt):
    """Supprime le tashkil, l'article « ال » initial et normalise les espaces."""
    s = str(txt or '').strip()
    s = re.sub(r'[ً-ْٰـ]', '', s)   # tashkil + kashida
    s = re.sub(r'\s+', ' ', s).strip()
    if s.startswith('ال'):
        s = s[2:]
    return s.strip()


def categorie_grade(grade):
    """'officier' | 'sous_officier' | '' selon le grade d'un participant."""
    g = normaliser_ar(grade)
    if not g:
        return ''
    for t in GRADES_OFFICIERS:
        if g.startswith(normaliser_ar(t)):
            return 'officier'
    for t in GRADES_SOUS_OFFICIERS:
        if g.startswith(normaliser_ar(t)):
            return 'sous_officier'
    return ''


# Ordre militaire décroissant (du plus élevé au plus bas) — sert au tri de la
# قائمة المشاركين : officiers d'abord (عميد → ملازم), puis sous-officiers
# (وكيل أول → عريف), puis civils (سيّد/سيّدة), puis inconnus.
_ORDRE_MILITAIRE = GRADES_OFFICIERS + GRADES_SOUS_OFFICIERS


def rang_grade(grade):
    """Indice de tri d'un grade selon la hiérarchie militaire (0 = le plus
    élevé). Les grades non reconnus sont renvoyés en fin de liste."""
    g = normaliser_ar(grade)
    if not g:
        return 9999
    for i, t in enumerate(_ORDRE_MILITAIRE):
        if g.startswith(normaliser_ar(t)):
            return i
    # Civils explicites (سيّد / سيّدة) juste après les militaires
    if g.startswith('سيد') or g.startswith('سيدة'):
        return len(_ORDRE_MILITAIRE) + 1
    return 9999


def trier_par_grade(participants, cle_grade='grade'):
    """Retourne la liste des participants triée par ordre militaire décroissant,
    en conservant l'ordre de saisie comme départage (tri stable)."""
    return sorted(participants or [],
                  key=lambda p: rang_grade((p or {}).get(cle_grade, '')))


def phrase_grades(grades, defaut='ضبّاط وضبّاط صف'):
    """Tournure arabe correspondant aux grades RÉELLEMENT présents :
        officiers seuls        → « ضبّاط »
        sous-officiers seuls   → « ضبّاط صف »
        les deux / inconnu     → « ضبّاط وضبّاط صف »"""
    cats = {categorie_grade(g) for g in (grades or [])}
    cats.discard('')
    if cats == {'officier'}:
        return 'ضبّاط'
    if cats == {'sous_officier'}:
        return 'ضبّاط صف'
    if cats == {'officier', 'sous_officier'}:
        return 'ضبّاط وضبّاط صف'
    return defaut


# Mots-clés identifiant le type de structure d'affectation d'un participant.
# Les services rattachés à la direction RÉGIONALE (bureaux, recettes, ou une
# direction/section régionale elle-même) sont tous ramenés à l'administration
# régionale. Les فرق sont ramenées à l'unité de la garde douanière.
_MOTS_BUREAU = ('مكتب', 'مكاتب', 'قباضة', 'قباضات',
                'الادارة الجهوية', 'ادارة جهوية', 'الجهوية للديوانة')
_MOTS_FIRQA  = ('فرقة', 'فرق', 'سرية', 'فصيل', 'الحرس الديواني', 'الوحدة')


def type_service(nom):
    """'bureau' (rattaché à une direction régionale), 'firqa' (rattachée à une
    unité de la garde douanière) ou '' (structure autonome)."""
    n = normaliser_ar(nom)
    if not n:
        return ''
    if any(m in n for m in _MOTS_FIRQA):
        return 'firqa'
    if any(m in n for m in _MOTS_BUREAU):
        return 'bureau'
    return ''


def rattachement_services(services, admin_regionale='', unite_garde=''):
    """Remplace les MKATEB par leur direction régionale de rattachement et les
    FIRAQ par leur unité de garde douanière — inutile de les détailler.

    Retourne {'mot': …, 'entites': […], 'phrase': '… و …'} où `mot` est le nom
    collectif à employer dans la phrase (« المكاتب », « الفرق », « المكاتب والفرق »).
    """
    a_bureau = a_firqa = False
    entites = []
    for s in (services or []):
        # Un service peut venir avec la جهة المرجعيّة de l'agent : (service, جهة).
        # Elle prime sur la جهة du centre — un مكتب de سيدي بوزيد relève de SA
        # direction régionale, pas de celle du centre formateur.
        jiha = ''
        if isinstance(s, (tuple, list)):
            s, jiha = (list(s) + ['', ''])[:2]
            jiha = str(jiha or '').strip()
        s = str(s or '').strip()
        if not s:
            continue
        t = type_service(s)
        if t == 'firqa':
            a_firqa = True
            e = jiha or (unite_garde or '').strip() or s
        elif t == 'bureau':
            a_bureau = True
            e = jiha or (admin_regionale or '').strip() or s
        else:
            e = s
        if e and e not in entites:
            entites.append(e)

    if a_bureau and a_firqa:
        mot = 'المكاتب والفرق'
    elif a_firqa:
        mot = 'الفرق'
    elif a_bureau:
        mot = 'المكاتب'
    else:
        mot = 'المصالح'
    return {'mot': mot, 'entites': entites, 'phrase': ' و'.join(entites)}


def derive_mustahdafun(participants, admin_regionale='', unite_garde='',
                       cle_grade='grade', cle_service='lieu_travail'):
    """« المستهدفون بالتّكوين » déduit des participants RÉELLEMENT inscrits.

    Combine deux dimensions déjà calculées ailleurs :
      • les grades présents      → « ضبّاط » / « ضبّاط صف » / « ضبّاط وضبّاط صف »
        (via phrase_grades) ;
      • les جهات/مصالح de rattachement, MKATEB ramenés à l'administration
        régionale et FIRAQ à l'unité de garde (via rattachement_services).

    Assemblés par « من » — connecteur neutre qui évite les fautes d'accord
    du collage direct :

        « ضبّاط وضبّاط صف من الإدارة الجهويّة للدّيوانة بالقصرين
          والوحدة الرّابعة للحرس الدّيواني بقفصة »

    Retourne '' si aucun participant n'est inscrit, pour que l'appelant
    retombe sur la valeur par défaut de la مادّة sans rien écraser.
    """
    parts = participants or []
    if not parts:
        return ''

    grades = [(p or {}).get(cle_grade, '') for p in parts]
    services = [((p or {}).get(cle_service, ''), (p or {}).get('jiha_marjiiya', ''))
                for p in parts]

    phrase = phrase_grades(grades)

    entites = rattachement_services(
        services, admin_regionale=admin_regionale, unite_garde=unite_garde
    )['entites']

    if not entites:
        return phrase
    return f'{phrase} من {" و".join(entites)}'
