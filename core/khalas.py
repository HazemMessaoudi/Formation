# -*- coding: utf-8 -*-
"""وثائق الخلاص — نقطة التجميع الموحّدة والحسابات.

Un seul assemblage : à partir d'une دورة, on réunit tout ce que la منظومة
connaît déjà (الدورة، المستحقّات، fiche المكوّن، هويّة المركز) plus les quelques
champs propres au module (المراجع الإدارية، نوع التكوين…). Les quatre documents
puisent dans ce MÊME dict : une donnée commune n'est saisie qu'une fois, et une
modification se répercute partout.

Le principe est « modèle officiel → injection des données », jamais l'inverse :
ce module ne fait que fournir les valeurs ; la mise en page reste celle des
modèles (voir core/pdf_khalas.py).
"""

import logging as _logging
_log = _logging.getLogger('formation.' + __name__)

from core import arabe, identite, bareme_mali
from core import mustahaqqat as _mst
from core.database import (
    get_dorra_mustahaqqat, calculer_mustahaqqat, get_config,
    get_khalas_settings, get_khalas_dorra, trouver_mkow_par_nom,
    get_bareme_grades,
)


LIBELLES_TYPE_TAKWIN = {'mustamir': 'تكوين مستمر', 'tahili': 'تكوين تأهيلي'}


def _num(v):
    try:
        return float(v or 0)
    except (TypeError, ValueError):
        return 0.0


def montant_lettres(montant):
    """« 24.000 » → « أربعة وعشرون دينارا » ; millimes ajoutés s'ils existent.

    Reproduit la graphie des modèles : les دنانير en toutes lettres, puis, le
    cas échéant, « و… مليم »."""
    # v1.7 : lecture décimale exacte (plus d'erreur de flottant sur les millimes).
    try:
        d = bareme_mali.arrondir_millime(bareme_mali.dec(montant))
    except (TypeError, ValueError, ArithmeticError):
        d = bareme_mali.arrondir_millime(0)
    dinars = int(d)
    millimes = int((d - dinars) * 1000)
    parts = []
    if dinars:
        parts.append(arabe.quantite_en_lettres(dinars, 'دينار', 'دينارا', 'ديناران', 'دنانير'))
    if millimes:
        parts.append(arabe.quantite_en_lettres(millimes, 'مليم', 'مليما', 'مليمان', 'مليمات'))
    txt = ' و'.join(parts) if parts else 'صفر دينار'
    return txt


def retenues(brut, taux_adaat):
    """(الأداءات, الصّافي) — v1.7 : calcul décimal exact, arrondi au millime
    « نصف فما فوق » (5.250 × 15 % = 0.788, et non 0.787)."""
    b = bareme_mali.arrondir_millime(bareme_mali.dec(brut or 0))
    a = bareme_mali.arrondir_millime(b * bareme_mali.dec(taux_adaat) / 100)
    return float(a), float(b - a)


def champs_manquants(data):
    """Champs obligatoires vides — pour la validation avant impression.
    Renvoie une liste de libellés lisibles (vide si tout est présent)."""
    manque = []
    exige = [
        ('formateur_nom',       'اسم المكوّن'),
        ('identifiant_unique',  'المعرف الوحيد'),
        ('cin',                 'رقم بطاقة التعريف الوطنية'),
        ('num_compte',          'الهوية البنكية أو البريدية'),
        ('numero_mudhakkira',   'عدد المذكرة'),
        ('muqarrar_numero',     'عدد المقرّر'),
        ('muqarrar_date',       'تاريخ المقرّر'),
    ]
    for cle, libelle in exige:
        if not str(data.get(cle) or '').strip():
            manque.append(libelle)
    if not data.get('chiffrable'):
        manque.append('احتساب المستحقّات (المبلغ غير قابل للاحتساب بعد)')
    return manque


def assembler(formation_id):
    """Dict unique alimentant les quatre documents ; None si la دورة n'existe pas."""
    dorra = get_dorra_mustahaqqat(formation_id)
    if not dorra:
        return None

    calc = calculer_mustahaqqat(formation_id) or {}
    settings = get_khalas_settings()
    saved = get_khalas_dorra(formation_id)
    config = get_config()
    trainer = trouver_mkow_par_nom(dorra.get('nom_formateur', ''),
                                   dorra.get('grade', '')) or {}

    # Catégorie de la RANG du formateur (وكيل → ب). C'est ce صنف/درجة qui figure
    # dans les وثائق الخلاص : il suit le grade du المكوّن, pas le صنف de la دورة.
    try:
        grade_categorie = _mst.classe_du_grade(dorra.get('grade', ''), get_bareme_grades())
    except Exception:
        _log.warning('assembler : exception ignorée', exc_info=True)
        grade_categorie = ''

    fmt = bareme_mali.formater_dinars

    # ── Montants ─────────────────────────────────────────────────────────────
    brut = _num(calc.get('montant') if calc.get('montant') is not None
                else dorra.get('mu_montant'))
    heures = calc.get('heures') or dorra.get('mu_heures') or 0
    taux = _num(calc.get('taux'))
    try:
        taux_adaat = float(settings.get('taux_adaat') or 15)
    except (TypeError, ValueError):
        taux_adaat = 15.0
    adaat, net = retenues(brut, taux_adaat)

    # ── Session ──────────────────────────────────────────────────────────────
    date_iso = dorra.get('date_formation') or ''
    try:
        date_longue = arabe.date_longue(date_iso) if date_iso else ''
    except Exception:
        _log.warning('assembler : exception ignorée', exc_info=True)
        date_longue = date_iso
    # V2 — دورة متعدّدة الأيّام : la période dans le corps des وثائق, le
    # DERNIER jour pour les dates de signature et le contrôle du مقرّر.
    from core import jours as _jours
    multi = _jours.est_multi_jours(date_iso, dorra.get('date_fin'))
    date_fin_iso = _jours.derniere_date(dorra) if multi else date_iso
    date_signature = date_longue
    if multi:
        date_longue = _jours.plage_longue(date_iso, dorra.get('date_fin'))
        date_signature = arabe.date_longue(date_fin_iso)
    type_takwin = saved.get('type_takwin') or 'mustamir'
    heures_prog = saved.get('heures_programmees') or (str(heures) if heures else '')
    heures_real = saved.get('heures_realisees') or (str(heures) if heures else '')

    lieu = (dorra.get('lieu_formation')
            or identite.val(config, 'lieu_formation_defaut')
            or identite.nom_centre(config))

    return {
        'formation_id': formation_id,

        # ── Session / دورة ──
        'titre':       dorra.get('titre', ''),
        'classe':      dorra.get('classe') or dorra.get('mu_classe') or '',
        'grade_categorie': grade_categorie,   # صنف رتبة المكوّن (للوثائق)
        'date_iso':    date_iso,
        'date_longue': date_longue,
        'multi':          multi,            # V2
        'date_fin_iso':   date_fin_iso,     # V2 : dernier jour
        'date_signature': date_signature,   # V2 : « في 14 أكتوبر 2026 »
        'lieu':        lieu,
        'heures':      heures,
        'heures_prog': heures_prog,
        'heures_real': heures_real,
        'type_takwin':         type_takwin,
        'type_takwin_libelle': LIBELLES_TYPE_TAKWIN.get(type_takwin, ''),

        # ── Financier ──
        'taux':       taux,   'taux_texte':  fmt(taux) if taux else '',
        'brut':       brut,   'brut_texte':  fmt(brut),
        'taux_adaat': taux_adaat,
        'adaat':      adaat,  'adaat_texte': fmt(adaat),
        'net':        net,    'net_texte':   fmt(net),
        'montant_lettres': montant_lettres(brut),
        'chiffrable': calc.get('chiffrable', False),
        'motifs':     calc.get('motifs', []),
        'groupe':     calc.get('groupe', '') or dorra.get('mu_groupe', ''),

        # ── Formateur : identité de la dorra ──
        'formateur_nom':   dorra.get('nom_formateur', ''),
        'formateur_grade': dorra.get('grade', ''),

        # ── Formateur : fiche mkowin (peut être vide → à compléter) ──
        'cin':                trainer.get('cin', ''),
        'cin_date':           trainer.get('cin_date', ''),
        'identifiant_unique': trainer.get('identifiant_unique', ''),
        'adresse':            trainer.get('adresse', ''),
        'telephone_gsm':      trainer.get('telephone_gsm', ''),
        'telephone_adm':      trainer.get('telephone_adm', ''),
        'diplome':            trainer.get('diplome', ''),
        'degre':              trainer.get('degre', ''),
        'plan_fonctionnel':   trainer.get('plan_fonctionnel', ''),
        'administration':     trainer.get('administration', '') or trainer.get('lieu_travail', ''),
        'ministere':          trainer.get('ministere', '') or settings.get('ministere_ichraf', ''),
        'lieu_travail':       trainer.get('lieu_travail', ''),
        'email':              trainer.get('email', ''),
        'banque':             trainer.get('banque', ''),
        'agence':             trainer.get('agence', ''),
        'num_compte':         trainer.get('num_compte', ''),
        'mkow_id':            trainer.get('id'),
        'mkow_trouve':        bool(trainer),

        # ── Références administratives (settings, surchargeables par dorra) ──
        'numero_mudhakkira': saved.get('numero_mudhakkira', ''),
        'ordre_tajir':       settings.get('ordre_tajir', ''),
        'ordre_1995':        settings.get('ordre_1995', ''),
        # Le مقرّر est celui de LA دورة, saisi à l'entrée du قسم — jamais un
        # réglage global. Stocké en ISO, imprimé en toutes lettres.
        'muqarrar_numero':   (saved.get('muqarrar_numero') or '').strip(),
        'muqarrar_date_iso': (saved.get('muqarrar_date') or '').strip(),
        'muqarrar_date':     arabe.date_longue((saved.get('muqarrar_date') or '').strip()),
        'tarkhis_numero':    saved.get('tarkhis_numero', ''),
        'tarkhis_date':      saved.get('tarkhis_date', ''),
        'notes':             saved.get('notes', ''),

        # ── Centre / direction ──
        'nom_centre':      identite.nom_centre(config),
        'nom_centre_ba':   identite.centre_avec_ba(config),
        'ville':           identite.ville(config) or 'تونس',
        'directeur_grade': settings.get('directeur_grade', ''),
        'directeur_nom':   settings.get('directeur_nom', ''),
        'directeur_titre': settings.get('directeur_titre', ''),
        'ministere_ichraf': settings.get('ministere_ichraf', ''),
    }
