# -*- coding: utf-8 -*-
"""السّنة المحاسبيّة: قاعدة مرجعيّة دائمة، وقاعدة سنويّة تتجدّد.

Deux natures de données vivent dans le même fichier, et il ne faut pas les
confondre :

* **المرجعيّة** — les إعدادات du مركز, les مكوّنون, les موادّ, les جهات,
  les رتب. Elles appartiennent au مركز, pas à une année : la liste des
  أعوان ne se vide pas au 1er janvier.

* **السّنويّة** — les مراسلات, les دورات, les مشاركون et surtout **les
  أعداد**. Celles-là appartiennent à un exercice : au 1er janvier la série
  repart, et le سجلّ de l'année écoulée se referme.

C'est la règle des registres administratifs : على رأس كلّ سنة يُفتح سجلّ
جديد. Une مراسلة de 2027 ne prend pas le عدد qui suit la dernière de 2026 ;
elle prend le عدد 1 de 2027.

Le basculement est **automatique** : la منظومة le fait au démarrage, sans
rien demander. Un agent qui ouvre le programme le 2 janvier trouve sa
nouvelle série prête. Et les années écoulées **restent lisibles** depuis la
منظومة — on les consulte et on les imprime, on n'y écrit plus.

Ce module ne décide rien d'autre : il dit quelle année est ouverte, et il
ouvre la suivante quand elle est venue.
"""

import logging as _logging
_log = _logging.getLogger('formation.' + __name__)

from datetime import datetime

CLE = 'annee_exercice'
CLE_ALERTE = 'alerte_horloge'        # v1.7
CLE_ANNONCE = 'annonce_bascule'      # v1.7


def _config(conn, cle):
    row = conn.execute('SELECT valeur FROM config WHERE cle=?', (cle,)).fetchone()
    return row['valeur'] if row else None


def annee_active(conn):
    """L'année dont le سجلّ est ouvert.

    À défaut de réglage — base neuve ou antérieure à cette version — c'est
    l'année du système : la منظومة n'a jamais de سنة indéterminée.
    """
    brut = _config(conn, CLE)
    try:
        annee = int(brut)
    except (TypeError, ValueError):
        return datetime.now().year
    return annee if 2000 <= annee <= 2999 else datetime.now().year


def definir_annee(conn, annee):
    """Ouvre le سجلّ de cette année (sans rien effacer de la précédente)."""
    annee = int(annee)
    conn.execute(
        'INSERT INTO config (cle, valeur) VALUES (?,?) '
        'ON CONFLICT(cle) DO UPDATE SET valeur=excluded.valeur',
        (CLE, str(annee)))
    return annee


def annees_connues(conn):
    """Toutes les années qui portent quelque chose, la plus récente d'abord.

    Sert au sélecteur d'année : on ne propose que des سنوات qui ont un
    contenu, jamais une liste théorique.
    """
    annees = set()
    for table, colonne in (('registre', 'annee'), ('lettres', 'annee')):
        try:
            annees.update(r[0] for r in conn.execute(
                f'SELECT DISTINCT {colonne} FROM {table} '
                f'WHERE {colonne} IS NOT NULL') if r[0])
        except Exception:
            _log.warning('annees_connues : exception ignorée', exc_info=True)
            pass
    annees.add(annee_active(conn))
    return sorted(annees, reverse=True)


def basculer_si_necessaire(conn, depart=None):
    """Ouvre le سجلّ de l'année civile si celui en cours est d'une année passée.

    Appelé au démarrage. Le basculement ne déplace, ne copie et n'efface
    rien : il ouvre une série neuve à côté de l'ancienne. Les compteurs de
    la nouvelle année partent des أعداد de départ réglés au معالج التّنصيب —
    un مركز qui reprend son سجلّ ورقي au 147 le retrouve chaque année s'il
    l'a réglé ainsi — et de 1 sinon.

    Ne recule JAMAIS : si l'horloge de la machine est fausse et rend une
    année antérieure, on garde le سجلّ ouvert. Reculer rouvrirait une série
    close et ferait resservir des أعداد déjà partis sur papier.

    Renvoie (ancienne, nouvelle) si un سجلّ a été ouvert, None sinon.
    """
    ouverte = annee_active(conn)
    civile = datetime.now().year
    if civile <= ouverte:
        _config_set(conn, CLE_ALERTE, '')
        return None

    # v1.7 — Garde-fou de l'horloge : on n'ouvre AUTOMATIQUEMENT que le سجلّ
    # de l'année qui suit immédiatement. Une horloge qui saute plusieurs
    # années (pile de la carte mère, date mal saisie) ouvrirait un سجلّ
    # lointain sans retour possible : on s'abstient, on signale, et seul le
    # مشرف عام peut confirmer l'ouverture (ouvrir_annee_confirmee).
    if civile > ouverte + 1:
        _config_set(conn, CLE_ALERTE, str(civile))
        _log.warning('Horloge : année système %s, سجلّ ouvert %s — ouverture suspendue',
                     civile, ouverte)
        return None
    return _ouvrir(conn, ouverte, civile, depart)


def _config_set(conn, cle, valeur):
    conn.execute(
        'INSERT INTO config (cle, valeur) VALUES (?,?) '
        'ON CONFLICT(cle) DO UPDATE SET valeur=excluded.valeur', (cle, valeur))


def alerte_horloge(conn):
    """Année système suspecte (> سجلّ ouvert + 1), ou None."""
    try:
        v = int(_config(conn, CLE_ALERTE) or 0)
    except (TypeError, ValueError):
        return None
    return v or None


def annonce_bascule(conn):
    """(ancienne, nouvelle) si un سجلّ vient d'être ouvert et n'a pas encore
    été annoncé à l'utilisateur, None sinon."""
    brut = _config(conn, CLE_ANNONCE) or ''
    try:
        a, b = (int(x) for x in brut.split('-'))
        return (a, b)
    except (TypeError, ValueError):
        return None


def acquitter_annonce(conn):
    _config_set(conn, CLE_ANNONCE, '')


def ouvrir_annee_confirmee(conn, annee, depart=None):
    """Ouverture CONFIRMÉE par le مشرف عام (après une alerte d'horloge).

    N'ouvre que l'année système courante, jamais une année antérieure ou
    égale au سجلّ ouvert. Renvoie (ancienne, nouvelle) ou lève ValueError."""
    annee = int(annee)
    ouverte = annee_active(conn)
    if annee <= ouverte:
        raise ValueError('السنة المطلوبة ليست لاحقة للسّجلّ المفتوح')
    if annee != datetime.now().year:
        raise ValueError('لا يُفتح إلّا سجلّ سنة تاريخ الحاسوب الحالي')
    return _ouvrir(conn, ouverte, annee, depart)


def _ouvrir(conn, ouverte, civile, depart):
    definir_annee(conn, civile)
    _config_set(conn, CLE_ALERTE, '')
    _config_set(conn, CLE_ANNONCE, f'{ouverte}-{civile}')
    for serie in ('interne', 'externe'):
        premier = 1
        if depart:
            try:
                premier = max(1, int(depart.get(serie, 1)))
            except (TypeError, ValueError):
                premier = 1
        conn.execute(
            'INSERT OR IGNORE INTO compteurs (annee, type, valeur) VALUES (?,?,?)',
            (civile, serie, premier - 1))
    return (ouverte, civile)
