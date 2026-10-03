# -*- coding: utf-8 -*-
"""V3 — تصنيف الدّورات (نمط, مستوى, تعاون, خارج المخطّط).

Ces quatre champs servent UNIQUEMENT aux إحصائيّات et aux تقارير : ils n'ont
aucun effet sur le déroulement d'un برنامج (étapes, وثائق, أرقام).

Toute valeur inconnue ou absente retombe sur la valeur par défaut, de sorte
qu'un ancien brouillon (sans ces champs) reste valide."""

MODES = ('حضوري', 'عن بعد')
NIVEAUX = ('جهوي', 'مركزي', 'مختص')
COOPERATIONS = ('', 'وطني', 'دولي')

MODE_DEFAUT = MODES[0]
NIVEAU_DEFAUT = NIVEAUX[0]

CHAMPS = ('mode_formation', 'niveau_formation', 'cooperation', 'hors_plan')

# Catégories du جدول « توزيع الأنشطة » du تقرير (modèle officiel).
CATEGORIE_PLAN = 'تنفيذ المخطّط السّنوي للتّكوين'
CATEGORIE_COOPERATION = 'التّعاون الوطني'
CATEGORIE_HORS_PLAN = 'خارج المخطّط السّنوي للتّكوين'
CATEGORIES_RAPPORT = (CATEGORIE_PLAN, CATEGORIE_COOPERATION, CATEGORIE_HORS_PLAN)


def _texte(v):
    return str(v).strip() if v is not None else ''


def _booleen(v):
    if isinstance(v, bool):
        return 1 if v else 0
    return 1 if _texte(v).lower() in ('1', 'true', 'on', 'oui', 'نعم') else 0


def normaliser(f, anciennes=None):
    """Renvoie les 4 champs normalisés d'une دورة (dict).

    `anciennes` : valeurs déjà enregistrées pour cette دورة ; une clé ABSENTE
    du payload les conserve (autosauvegarde d'un ancien onglet resté ouvert),
    une clé présente mais invalide retombe sur la valeur par défaut."""
    anciennes = anciennes or {}

    def _pris(cle):
        return f[cle] if cle in f else anciennes.get(cle)

    mode = _texte(_pris('mode_formation'))
    niveau = _texte(_pris('niveau_formation'))
    coop = _texte(_pris('cooperation'))
    if coop.lower() in ('1', 'true', 'on'):
        coop = 'وطني'
    return {
        'mode_formation': mode if mode in MODES else MODE_DEFAUT,
        'niveau_formation': niveau if niveau in NIVEAUX else NIVEAU_DEFAUT,
        'cooperation': coop if coop in COOPERATIONS else '',
        'hors_plan': _booleen(_pris('hors_plan')),
    }


def categorie_rapport(f):
    """Catégorie d'une دورة dans le تقرير : خارج المخطّط l'emporte, puis
    التّعاون, sinon تنفيذ المخطّط السّنوي."""
    if _booleen(f.get('hors_plan')):
        return CATEGORIE_HORS_PLAN
    if _texte(f.get('cooperation')) in ('وطني', 'دولي'):
        return CATEGORIE_COOPERATION
    return CATEGORIE_PLAN
