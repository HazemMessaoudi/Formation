# -*- coding: utf-8 -*-
"""Sauvegardes de la base : automatiques, quotidiennes, externes (v1.7).

Extrait de core/database.py (v1.4) — importer depuis core.database, qui
ré-exporte tout : les appelants existants restent inchangés.

v1.7
  • une copie au démarrage (avant migration, comme avant) ET une copie
    quotidienne tant que le programme reste ouvert ;
  • conservation ÉTAGÉE au lieu des « 30 dernières » : un centre qui
    redémarre souvent ne perd plus ses copies anciennes ;
  • copie EXTERNE (clé USB, disque, dossier réseau), vérifiée, avec la date
    de la dernière copie externe pour le rappel du tableau de bord.
"""

import glob
import os
import re
import sqlite3
import threading
from datetime import datetime, timedelta

from core.db._base import _facade, _log

# ─── Politique de conservation ───────────────────────────────────────────────

BACKUP_KEEP = 30          # conservé pour compatibilité (plus utilisé par la purge)
GARDER_AUJOURDHUI = 5     # copies du jour gardées (démarrages successifs)
GARDER_JOURS = 7          # la plus récente de chacun des 7 derniers jours
GARDER_SEMAINES = 4       # la plus récente de chacune des 4 dernières semaines
GARDER_MOIS = 12          # la plus récente de chacun des 12 derniers mois
RAPPEL_EXTERNE_JOURS = 7  # rappel si aucune copie externe depuis 7 jours

_RE_NOM = re.compile(r'formation_(\d{8})_(\d{6})\.db$')
_verrou = threading.Lock()
_dernier_controle = {'jour': None}


def dossier_sauvegardes():
    d = os.path.join(os.path.dirname(_facade().DB_PATH), 'backups')
    os.makedirs(d, exist_ok=True)
    return d


def _horodatage(chemin):
    m = _RE_NOM.search(os.path.basename(chemin))
    if not m:
        return None
    try:
        return datetime.strptime(m.group(1) + m.group(2), '%Y%m%d%H%M%S')
    except ValueError:
        return None


def a_conserver(fichiers, maintenant=None):
    """Ensemble des fichiers à GARDER selon la politique étagée :

      • les 5 copies les plus récentes du jour ;
      • la plus récente de chacun des 7 derniers jours ;
      • la plus récente de chacune des 4 dernières semaines ;
      • la plus récente de chacun des 12 derniers mois.

    Pure (sans disque) : testable. `fichiers` = chemins nommés
    formation_AAAAMMJJ_HHMMSS.db ; un nom illisible est toujours gardé."""
    maintenant = maintenant or datetime.now()
    dates, garder = {}, set()
    for f in fichiers:
        h = _horodatage(f)
        if h is None:
            garder.add(f)
        else:
            dates[f] = h
    recents = sorted(dates, key=lambda f: dates[f], reverse=True)
    garder.update([f for f in recents if dates[f].date() == maintenant.date()][:GARDER_AUJOURDHUI])

    debut_jours = (maintenant - timedelta(days=GARDER_JOURS - 1)).date()
    debut_sem = (maintenant - timedelta(weeks=GARDER_SEMAINES - 1)).isocalendar()[:2]
    debut_mois = maintenant.year * 12 + maintenant.month - GARDER_MOIS
    periodes = (
        (lambda d: d.date(), lambda d: d.date() >= debut_jours),
        (lambda d: tuple(d.isocalendar()[:2]), lambda d: tuple(d.isocalendar()[:2]) >= tuple(debut_sem)),
        (lambda d: (d.year, d.month), lambda d: d.year * 12 + d.month > debut_mois),
    )
    for cle, dans_fenetre in periodes:
        vus = set()
        for f in recents:                 # du plus récent au plus ancien
            k = cle(dates[f])
            if k in vus:
                continue
            vus.add(k)
            if dans_fenetre(dates[f]):
                garder.add(f)
    return garder


def purger_sauvegardes(maintenant=None):
    """Supprime les copies que la politique étagée ne retient pas."""
    fichiers = glob.glob(os.path.join(dossier_sauvegardes(), 'formation_*.db'))
    garder = a_conserver(fichiers, maintenant)
    supprimes = 0
    for f in fichiers:
        if f not in garder:
            try:
                os.remove(f)
                supprimes += 1
            except OSError:
                _log.warning('purge sauvegarde impossible : %s', f, exc_info=True)
    return supprimes


def _copier_base(dest):
    """Copie cohérente (API de sauvegarde SQLite) puis contrôle d'intégrité.
    Lève en cas d'échec ; le fichier incomplet est supprimé."""
    src = sqlite3.connect(_facade().DB_PATH)
    try:
        dst = sqlite3.connect(dest)
        try:
            with dst:
                src.backup(dst)
            verdict = dst.execute('PRAGMA integrity_check').fetchone()[0]
        finally:
            dst.close()
    finally:
        src.close()
    if verdict != 'ok':
        try:
            os.remove(dest)
        except OSError:
            pass
        raise RuntimeError(f'integrity_check : {verdict}')


def backup_db(keep=BACKUP_KEEP):
    """Copie horodatée de la base dans data/backups/, puis purge étagée.
    Retourne le chemin créé, ou None si rien à sauvegarder / échec."""
    if not os.path.exists(_facade().DB_PATH):
        return None
    stamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    dest = os.path.join(dossier_sauvegardes(), f'formation_{stamp}.db')
    if os.path.exists(dest):          # deux copies dans la même seconde
        return dest
    try:
        with _verrou:
            _copier_base(dest)
    except Exception as e:
        _log.exception(f"backup_db error: {e}")
        return None
    try:
        purger_sauvegardes()
    except Exception:
        _log.warning('backup_db : purge ignorée', exc_info=True)
    return dest


def derniere_sauvegarde_du_jour(jour=None):
    jour = (jour or datetime.now()).strftime('%Y%m%d')
    fichiers = sorted(glob.glob(os.path.join(dossier_sauvegardes(), f'formation_{jour}_*.db')))
    return fichiers[-1] if fichiers else None


def sauvegarde_quotidienne_si_necessaire():
    """Appelée à chaque requête (coût : une comparaison de dates) : crée la
    copie du jour si elle manque — le programme resté ouvert plusieurs jours
    reçoit ainsi une copie par jour. Renvoie le chemin créé ou None."""
    aujourd_hui = datetime.now().date()
    if _dernier_controle['jour'] == aujourd_hui:
        return None
    _dernier_controle['jour'] = aujourd_hui
    if derniere_sauvegarde_du_jour():
        return None
    return backup_db()


# ─── Copie externe (clé USB, disque, dossier réseau) ─────────────────────────

DOSSIER_EXTERNE = 'نسخ_منظومة_التكوين'


def lecteurs_amovibles():
    """Lecteurs proposés pour la copie externe (Windows) : amovibles d'abord,
    puis les autres disques, hors disque du programme. Liste de dicts
    {'racine': 'E:\\\\', 'amovible': bool}. Vide hors Windows."""
    if os.name != 'nt':
        return []
    try:
        import ctypes
        import string
        masque = ctypes.windll.kernel32.GetLogicalDrives()
        disque_prog = os.path.splitdrive(os.path.abspath(_facade().DB_PATH))[0].upper()
        res = []
        for i, lettre in enumerate(string.ascii_uppercase):
            if not masque & (1 << i):
                continue
            racine = f'{lettre}:\\'
            if f'{lettre}:' == disque_prog:
                continue
            t = ctypes.windll.kernel32.GetDriveTypeW(racine)
            if t in (2, 3, 4):          # amovible, fixe, réseau
                res.append({'racine': racine, 'amovible': t == 2})
        return sorted(res, key=lambda d: (not d['amovible'], d['racine']))
    except Exception:
        _log.warning('lecteurs_amovibles : exception ignorée', exc_info=True)
        return []


def copier_vers_externe(destination):
    """Copie vérifiée de la base vers `destination` (racine d'un lecteur ou
    dossier). Crée un sous-dossier « نسخ_منظومة_التكوين » et y range
    formation_AAAAMMJJ_HHMMSS.db. Refuse le dossier du programme lui-même
    (ce ne serait pas une copie externe). Renvoie le chemin créé ; lève
    ValueError (message arabe) sinon."""
    destination = (destination or '').strip().strip('"')
    if not destination:
        raise ValueError('اختر وجهة النسخ')
    if not os.path.isdir(destination):
        raise ValueError('الوجهة غير موجودة أو غير متاحة (هل المفتاح موصول؟)')
    donnees = os.path.normcase(os.path.abspath(os.path.dirname(_facade().DB_PATH)))
    cible_abs = os.path.normcase(os.path.abspath(destination))
    if cible_abs == donnees or cible_abs.startswith(donnees + os.sep):
        raise ValueError('هذه الوجهة داخل مجلّد البرنامج نفسه، وليست نسخة خارجيّة')
    dossier = os.path.join(destination, DOSSIER_EXTERNE)
    try:
        os.makedirs(dossier, exist_ok=True)
    except OSError:
        raise ValueError('تعذّرت الكتابة في الوجهة (محميّة ضدّ الكتابة أو ممتلئة؟)')
    dest = os.path.join(dossier, f"formation_{datetime.now():%Y%m%d_%H%M%S}.db")
    try:
        with _verrou:
            _copier_base(dest)
    except Exception as e:
        _log.exception(f'copie externe : {e}')
        raise ValueError('فشل النسخ أو فحص سلامة النسخة: ' + str(e)[:80])
    conn = _facade().get_connection()
    try:
        for cle, val in (('derniere_sauvegarde_externe', datetime.now().strftime('%Y-%m-%d %H:%M')),
                         ('destination_sauvegarde_externe', destination)):
            conn.execute('INSERT INTO config (cle, valeur) VALUES (?,?) '
                         'ON CONFLICT(cle) DO UPDATE SET valeur=excluded.valeur', (cle, val))
        conn.commit()
    finally:
        conn.close()
    return dest


def etat_sauvegarde_externe(cfg, maintenant=None):
    """{'derniere': 'AAAA-MM-JJ HH:MM' | '', 'jours': int | None,
        'rappel': bool, 'destination': str}"""
    maintenant = maintenant or datetime.now()
    brut = (cfg or {}).get('derniere_sauvegarde_externe', '') or ''
    jours = None
    try:
        jours = (maintenant - datetime.strptime(brut, '%Y-%m-%d %H:%M')).days
    except ValueError:
        pass
    return {'derniere': brut, 'jours': jours,
            'rappel': jours is None or jours >= RAPPEL_EXTERNE_JOURS,
            'destination': (cfg or {}).get('destination_sauvegarde_externe', '') or ''}
