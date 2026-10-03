# -*- coding: utf-8 -*-
"""V3 — إعدادات التّقارير : textes par défaut et جدول العديد.

Tout ce qui est écrit ici reprend le modèle officiel du تقرير النّصف سنوي.
Les textes des أقسام 1.1 (الصّلاحيّات) et 1.2 (التّنظيم الهيكلي) sont
AUTOMATIQUES : tant que l'utilisateur ne les a pas modifiés, ils suivent le
nom du مركز et le نصّ قانوني réglés ailleurs. Dès qu'il les modifie, sa
version est enregistrée telle quelle.

Aucune fonction de ce module n'écrit en base : il ne fait que lire la config
(dict de get_config()) et rendre des textes ou des lignes normalisées."""

import json
import re

from core import identite

# ─── Clés de config ──────────────────────────────────────────────────────────

CLE_TEXTE_LEGAL = 'rapport_texte_legal'
CLE_FASL = 'rapport_fasl'
CLE_TACHES = 'rapport_taches'
CLE_STRUCTURE = 'rapport_structure'
CLE_RH = 'rapport_rh'
CLE_RH_NOTE = 'rapport_rh_note'
CLE_RH_IGNORE = 'rapport_rh_ignore'

TEXTE_LEGAL_DEFAUT = ('الأمر عدد 929 لسنة 2022 المؤرّخ في 07 ديسمبر 2022 والمتعلّق '
                      'بإحداث وضبط التّنظيم الإداري والمالي للمدرسة الوطنيّة للدّيوانة')
FASL_DEFAUT = 'الفصل الخامس عشر'

ADMIN_TUTELLE = 'إدارة التّكوين الجهوي والمختصّ بالمدرسة الوطنيّة للدّيوانة'

# Gabarits : {centre} = nom du مركز, {fasl}, {amr} = نصّ قانوني abrégé.
_TACHES_GABARIT = (
    'يشرف {centre} خاصّة على:\n'
    '- تأمين السّير العادي للعمل بالمركز\n'
    '- إعداد البرنامج السنوي للتّكوين على المستوى الجهوي\n'
    '- تنفيذ البرنامج السنوي للتّكوين على المستوى الجهوي\n'
    '- تنفيذ أنشطة تكوينيّة خارج المخطّط السنوي في مختلف المجالات ذات الصلة '
    'بالعمل الديواني\n'
    '- تنفيذ أنشطة تكوينيّة عرضيّة في المجال الدّيواني تحت إشراف ' + ADMIN_TUTELLE +
    ' (ندوات ومحاضرات).'
)
_STRUCTURE_GABARIT = 'عملا بأحكام {fasl} من {amr}، يضمّ {centre} عدد 01 مصلحة.'
_INTRO_GABARIT = ('عملا بمقتضيات {fasl} من {texte_legal}، يرجع {centre} هيكليّا '
                  'ووظيفيّا إلى ' + ADMIN_TUTELLE + '.')

# ─── جدول العديد (colonnes du modèle, dans l'ordre) ──────────────────────────
#
# (clé, libellé, groupe). « العدد » n'est pas saisi : c'est la somme de الهيئة.

RH_GROUPES = ('الهيئة', 'الجنس', 'الصّفة / الخطّة الوظيفيّة', 'الوضعيّة الإداريّة')
RH_COLONNES = (
    ('off_sup', 'ضابط.س', 'الهيئة'),
    ('officier', 'ضابط', 'الهيئة'),
    ('sous_off', 'ض. صفّ', 'الهيئة'),
    ('homme', 'ذكر', 'الجنس'),
    ('femme', 'أنثى', 'الجنس'),
    ('k_directeur', 'ك.مدير', 'الصّفة / الخطّة الوظيفيّة'),
    ('r_centre', 'ر. مركز', 'الصّفة / الخطّة الوظيفيّة'),
    ('r_service', 'ر. مصلحة', 'الصّفة / الخطّة الوظيفيّة'),
    ('administratif', 'إداري', 'الصّفة / الخطّة الوظيفيّة'),
    ('direct', 'مباشر', 'الوضعيّة الإداريّة'),
    ('non_direct', 'غير مباشر', 'الوضعيّة الإداريّة'),
)
RH_CLES = tuple(c[0] for c in RH_COLONNES)
RH_HAYAA = ('off_sup', 'officier', 'sous_off')
NIVEAUX_RH = ('جهوي', 'مركزي', 'مختص')
RH_MAX_LIGNES = 10


def _entier(v):
    try:
        n = int(str(v).strip() or 0)
    except (TypeError, ValueError):
        return 0
    return max(0, min(n, 999))


def normaliser_rh(lignes):
    """Liste de lignes propres : niveau non vide, compteurs entiers ≥ 0.
    Les lignes entièrement vides (niveau ET compteurs) sont écartées."""
    propres = []
    for l in (lignes or [])[:RH_MAX_LIGNES]:
        if not isinstance(l, dict):
            continue
        niveau = str(l.get('niveau') or '').strip()[:40]
        vals = {k: _entier(l.get(k)) for k in RH_CLES}
        if not niveau and not any(vals.values()):
            continue
        propres.append({'niveau': niveau or NIVEAUX_RH[0], **vals})
    return propres


def total_ligne(l):
    return sum(_entier(l.get(k)) for k in RH_HAYAA)


def lire_rh(config):
    """Lignes du جدول العديد enregistrées (liste, éventuellement vide)."""
    brut = (config or {}).get(CLE_RH) or ''
    try:
        return normaliser_rh(json.loads(brut)) if brut.strip() else []
    except (ValueError, AttributeError):
        return []


def serialiser_rh(lignes):
    return json.dumps(normaliser_rh(lignes), ensure_ascii=False)


def total_rh(lignes):
    return sum(total_ligne(l) for l in lignes)


def rh_a_demander(config):
    """Vrai si le bandeau d'accueil doit proposer de remplir le جدول العديد."""
    return not lire_rh(config) and str((config or {}).get(CLE_RH_IGNORE, '')).strip() != '1'


# ─── Textes ──────────────────────────────────────────────────────────────────

def _brut(config, cle):
    v = (config or {}).get(cle)
    return str(v).strip() if v is not None else ''


def texte_legal(config):
    return _brut(config, CLE_TEXTE_LEGAL) or TEXTE_LEGAL_DEFAUT


def fasl(config):
    return _brut(config, CLE_FASL) or FASL_DEFAUT


def amr_court(texte):
    """« الأمر عدد 929 لسنة 2022 » : le نصّ jusqu'à l'année incluse."""
    m = re.match(r'^(.*?لسنة\s*\d{4})', texte or '')
    return m.group(1).strip() if m else (texte or '').strip()


def _valeurs(config):
    tl = texte_legal(config)
    return {'centre': identite.nom_centre(config), 'fasl': fasl(config),
            'texte_legal': tl, 'amr': amr_court(tl)}


def taches_defaut(config):
    return _TACHES_GABARIT.format(**_valeurs(config))


def structure_defaut(config):
    return _STRUCTURE_GABARIT.format(**_valeurs(config))


def intro_section1(config):
    return _INTRO_GABARIT.format(**_valeurs(config))


def taches(config):
    return _brut(config, CLE_TACHES) or taches_defaut(config)


def structure(config):
    return _brut(config, CLE_STRUCTURE) or structure_defaut(config)


def valeur_a_stocker(poste, defaut):
    """Un texte identique au texte automatique n'est PAS figé en base : il
    continue ainsi de suivre un changement de nom du مركز."""
    poste = (poste or '').replace('\r\n', '\n').strip()
    return '' if poste == defaut.strip() else poste


def decouper_puces(texte):
    """(phrase d'introduction, [puces]) : les lignes « - … » sont des puces."""
    intro, puces = [], []
    for ligne in (texte or '').splitlines():
        s = ligne.strip()
        if not s:
            continue
        if s[:1] in ('-', '•', '*'):
            puces.append(s[1:].strip())
        elif puces:
            puces[-1] += ' ' + s
        else:
            intro.append(s)
    return ' '.join(intro), puces
