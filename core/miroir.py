# -*- coding: utf-8 -*-
"""V3.1 — النسخة المرآة (miroir) et الأرشيف السّنوي.

Pourquoi : les sauvegardes automatiques (core/db/sauvegarde.py) vivent dans
`data/backups`, À CÔTÉ de la base. Qu'on supprime ou abîme le dossier du
programme, et la base part avec ses copies. La miroir est une copie tenue à
jour HORS du dossier du programme :

* emplacement par défaut, masqué : %LOCALAPPDATA%\\FormationKasserine\\miroir
  (hors Windows : ~/.formation_kasserine/miroir) ;
* emplacement supplémentaire au choix du مشرف (autre disque, dossier réseau),
  réglé depuis الإعدادات ; la copie par défaut est TOUJOURS tenue aussi ;
* chaque installation a son propre sous-dossier, tiré du chemin de son
  dossier `data/` : une installation neuve dans un autre dossier ne
  ressuscite jamais la base d'une autre.

Écriture : quelques secondes après chaque modification (regroupées), au
démarrage et sur demande. Copie SQLite cohérente → contrôle d'intégrité →
remplacement atomique ; la version précédente est gardée
(`formation_miroir_precedent.db`). Une base abîmée n'écrase donc jamais une
bonne miroir.

Démarrage (`preparer_base`) :
* base ABSENTE → restauration automatique depuis la miroir valide la plus
  récente (à défaut : la dernière copie de data/backups), signalée par un
  bandeau et au سجلّ التّدقيق ;
* base PRÉSENTE mais ABÎMÉE → rien n'est écrasé : le programme ouvre la page
  « استرجاع المنظومة » ; la restauration exige l'identifiant et le mot de
  passe d'un مشرف عام, vérifiés DANS la copie choisie.

الأرشيف السّنوي : à l'ouverture d'un سجلّ neuf, une copie figée de la base
(`archive_AAAA.db`, lecture seule) est rangée dans data/archives et dans la
miroir. Les données restent dans la base principale : les التّقارير comparent
les années sans rien aller chercher ailleurs.
"""

import glob
import hashlib
import json
import logging as _logging
import os
import shutil
import sqlite3
import stat
import threading
from datetime import datetime

from core import chemins

_log = _logging.getLogger('formation.' + __name__)

NOM_MIROIR = 'formation_miroir.db'
NOM_PRECEDENT = 'formation_miroir_precedent.db'
NOM_INFO = 'miroir.json'
NOM_MARQUE_RESTAURATION = 'restauration_miroir.json'
DELAI_REGROUPEMENT = 3.0          # secondes entre une modification et la copie

_verrou = threading.Lock()
_minuterie = {'t': None}
ETAT = {'derniere': '', 'erreur': '', 'secours': ''}


# ─── Emplacements ────────────────────────────────────────────────────────────

def dossier_racine_defaut():
    """Racine des miroirs de ce poste (variable FK_MIROIR_DIR pour les tests)."""
    d = os.environ.get('FK_MIROIR_DIR')
    if not d:
        base = os.environ.get('LOCALAPPDATA')
        d = (os.path.join(base, 'FormationKasserine', 'miroir') if base
             else os.path.join(os.path.expanduser('~'), '.formation_kasserine', 'miroir'))
    os.makedirs(d, exist_ok=True)
    _cacher(os.path.dirname(d) if not os.environ.get('FK_MIROIR_DIR') else d)
    return d


def _cacher(chemin):
    """Attribut « caché » (Windows) : protège d'une suppression par mégarde,
    ce n'est pas une protection de sécurité."""
    if os.name != 'nt':
        return
    try:
        import ctypes
        ctypes.windll.kernel32.SetFileAttributesW(str(chemin), 0x02)
    except Exception:
        _log.warning('_cacher : attribut ignoré', exc_info=True)


def cle_installation(dossier_donnees=None):
    """Identifiant stable de l'installation : empreinte du chemin de data/."""
    d = os.path.normcase(os.path.abspath(dossier_donnees or chemins.dossier_donnees()))
    return hashlib.sha1(d.encode('utf-8')).hexdigest()[:12]


def _fichier_emplacement():
    return os.path.join(dossier_racine_defaut(), cle_installation() + '.emplacement')


def emplacement_personnalise():
    """Dossier supplémentaire choisi par le مشرف ('' si aucun)."""
    try:
        with open(_fichier_emplacement(), encoding='utf-8') as fh:
            return fh.read().strip()
    except OSError:
        return ''


def dossiers_miroir():
    """Dossiers où la miroir de CETTE installation est tenue : toujours le
    dossier par défaut, plus l'emplacement personnalisé s'il est réglé."""
    cle = cle_installation()
    res = [os.path.join(dossier_racine_defaut(), cle)]
    perso = emplacement_personnalise()
    if perso:
        res.append(os.path.join(perso, 'miroir_formation_kasserine', cle))
    return res


def dossier_miroir_principal():
    return dossiers_miroir()[-1]


def _dans_donnees(chemin):
    donnees = os.path.normcase(os.path.abspath(chemins.dossier_application()))
    cible = os.path.normcase(os.path.abspath(chemin))
    return cible == donnees or cible.startswith(donnees + os.sep)


def definir_emplacement(chemin):
    """Règle (ou efface avec '') l'emplacement supplémentaire. Lève
    ValueError (message arabe) si le dossier ne convient pas."""
    chemin = (chemin or '').strip().strip('"')
    if chemin:
        if not os.path.isdir(chemin):
            raise ValueError('المجلّد غير موجود أو غير متاح')
        if _dans_donnees(chemin):
            raise ValueError('هذا المكان داخل مجلّد البرنامج نفسه: اختر مكانًا خارجه')
        essai = os.path.join(chemin, '.essai_ecriture_fk')
        try:
            with open(essai, 'w', encoding='utf-8') as fh:
                fh.write('ok')
            os.remove(essai)
        except OSError:
            raise ValueError('تعذّرت الكتابة في هذا المجلّد')
    with open(_fichier_emplacement(), 'w', encoding='utf-8') as fh:
        fh.write(os.path.abspath(chemin) if chemin else '')
    return chemin


# ─── Écriture de la miroir ───────────────────────────────────────────────────

def _copie_verifiee(source, dest):
    """Copie SQLite cohérente de `source` vers `dest`, puis quick_check.
    Lève RuntimeError si la copie n'est pas saine (dest supprimé)."""
    src = sqlite3.connect(source)
    try:
        dst = sqlite3.connect(dest)
        try:
            with dst:
                src.backup(dst)
            verdict = dst.execute('PRAGMA quick_check').fetchone()[0]
        finally:
            dst.close()
    finally:
        src.close()
    if verdict != 'ok':
        try:
            os.remove(dest)
        except OSError:
            pass
        raise RuntimeError(f'quick_check : {verdict}')


def _nom_centre(chemin_base):
    try:
        conn = sqlite3.connect(chemin_base)
        try:
            r = conn.execute("SELECT valeur FROM config WHERE cle='nom_centre'").fetchone()
            return r[0] if r else ''
        finally:
            conn.close()
    except sqlite3.Error:
        return ''


def ecrire_miroir(chemin_base=None):
    """Met à jour la miroir dans chaque dossier. Renvoie le nombre de dossiers
    mis à jour (0 si la base est absente ou abîmée)."""
    chemin_base = chemin_base or _chemin_base_courant()
    if not os.path.isfile(chemin_base):
        return 0
    faits = 0
    with _verrou:
        for d in dossiers_miroir():
            try:
                os.makedirs(d, exist_ok=True)
                tmp = os.path.join(d, NOM_MIROIR + '.tmp')
                _copie_verifiee(chemin_base, tmp)
                courant = os.path.join(d, NOM_MIROIR)
                if os.path.exists(courant):
                    os.replace(courant, os.path.join(d, NOM_PRECEDENT))
                os.replace(tmp, courant)
                with open(os.path.join(d, NOM_INFO), 'w', encoding='utf-8') as fh:
                    json.dump({'date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                               'donnees': os.path.abspath(os.path.dirname(chemin_base)),
                               'centre': _nom_centre(courant)}, fh, ensure_ascii=False)
                faits += 1
            except Exception as e:
                ETAT['erreur'] = f'{d} : {str(e)[:120]}'
                _log.warning('ecrire_miroir : échec dans %s', d, exc_info=True)
    if faits:
        ETAT['derniere'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        if faits == len(dossiers_miroir()):
            ETAT['erreur'] = ''
    return faits


def demander_miroir():
    """Après une modification : copie regroupée quelques secondes plus tard
    (une rafale de requêtes ne produit qu'une copie)."""
    if _minuterie['t'] is not None and _minuterie['t'].is_alive():
        return
    t = threading.Timer(DELAI_REGROUPEMENT, _executer_minuterie)
    t.daemon = True
    _minuterie['t'] = t
    t.start()


def _executer_minuterie():
    try:
        ecrire_miroir()
    except Exception:
        _log.warning('miroir différée : exception ignorée', exc_info=True)


def _chemin_base_courant():
    import core.database as _db
    return _db.DB_PATH


# ─── Lecture : copies disponibles ────────────────────────────────────────────

def base_saine(chemin):
    """True si le fichier s'ouvre et passe PRAGMA quick_check."""
    if not os.path.isfile(chemin):
        return False
    try:
        conn = sqlite3.connect(f'file:{chemin}?mode=ro', uri=True)
        try:
            return conn.execute('PRAGMA quick_check').fetchone()[0] == 'ok'
        finally:
            conn.close()
    except sqlite3.Error:
        return False


def copies_disponibles(chemin_base=None, avec_sauvegardes=True):
    """Copies utilisables pour une restauration, de la plus récente à la plus
    ancienne : [{'chemin', 'date', 'taille', 'origine'}]. N'inclut que les
    fichiers sains."""
    chemin_base = chemin_base or _chemin_base_courant()
    res = []
    for d in dossiers_miroir():
        for nom, origine in ((NOM_MIROIR, 'miroir'), (NOM_PRECEDENT, 'miroir_precedent')):
            f = os.path.join(d, nom)
            if os.path.isfile(f):
                res.append((f, origine))
    if avec_sauvegardes:
        dossier = os.path.join(os.path.dirname(chemin_base), 'backups')
        for f in sorted(glob.glob(os.path.join(dossier, 'formation_*.db')))[-3:]:
            res.append((f, 'sauvegarde'))
    copies = []
    for f, origine in res:
        if base_saine(f):
            copies.append({'chemin': f, 'origine': origine,
                           'date': datetime.fromtimestamp(os.path.getmtime(f)).strftime('%Y-%m-%d %H:%M'),
                           'mtime': os.path.getmtime(f),
                           'taille': os.path.getsize(f)})
    copies.sort(key=lambda c: c['mtime'], reverse=True)
    return copies


# ─── Restauration ────────────────────────────────────────────────────────────

def _poser(copie, chemin_base):
    """Remplace la base par une copie (copie SQLite vérifiée puis remplacement
    atomique). Les fichiers -wal / -shm de l'ancienne base sont écartés."""
    tmp = chemin_base + '.restauration'
    _copie_verifiee(copie, tmp)
    for suffixe in ('-wal', '-shm'):
        try:
            os.remove(chemin_base + suffixe)
        except OSError:
            pass
    os.replace(tmp, chemin_base)


def _marquer_restauration(chemin_base, copie, motif):
    info = {'date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'), 'source': copie['chemin'],
            'origine': copie['origine'], 'date_copie': copie['date'], 'motif': motif}
    with open(os.path.join(os.path.dirname(chemin_base), NOM_MARQUE_RESTAURATION), 'w',
              encoding='utf-8') as fh:
        json.dump(info, fh, ensure_ascii=False)
    return info


def restaurer_si_absente(chemin_base):
    """Démarrage, AVANT init_db : si la base manque, pose la copie saine la
    plus récente. Renvoie l'info de restauration, ou None."""
    if os.path.exists(chemin_base):
        return None
    copies = copies_disponibles(chemin_base)
    if not copies:
        return None
    try:
        os.makedirs(os.path.dirname(chemin_base), exist_ok=True)
        _poser(copies[0]['chemin'], chemin_base)
    except Exception:
        _log.exception('restauration automatique impossible')
        return None
    info = _marquer_restauration(chemin_base, copies[0], 'absente')
    _log.warning('Base absente : restaurée depuis %s', copies[0]['chemin'])
    return info


def verifier_admin_dans(fichier, utilisateur, mot_de_passe):
    """True si `utilisateur` est un مشرف عام de la copie `fichier` et que le
    mot de passe correspond (hash werkzeug de la copie)."""
    from werkzeug.security import check_password_hash
    try:
        conn = sqlite3.connect(f'file:{fichier}?mode=ro', uri=True)
        try:
            r = conn.execute('SELECT password_hash, role FROM users WHERE username=?',
                             ((utilisateur or '').strip(),)).fetchone()
        finally:
            conn.close()
    except sqlite3.Error:
        return False
    return bool(r and r[1] == 'admin' and check_password_hash(r[0], mot_de_passe or ''))


def restaurer_depuis(copie_chemin, chemin_base=None, motif='manuelle'):
    """Remplace la base courante par une copie connue (miroir ou sauvegarde).
    La base remplacée est d'abord mise de côté dans data/backups
    (`remplacee_AAAAMMJJ_HHMMSS.db`, hors de la purge automatique)."""
    chemin_base = chemin_base or _chemin_base_courant()
    connues = {c['chemin']: c for c in copies_disponibles(chemin_base)}
    copie = connues.get(copie_chemin)
    if not copie:
        raise ValueError('النسخة المختارة غير موجودة أو غير سليمة')
    with _verrou:
        if os.path.exists(chemin_base):
            cote = os.path.join(os.path.dirname(chemin_base), 'backups')
            os.makedirs(cote, exist_ok=True)
            try:
                shutil.copy2(chemin_base, os.path.join(
                    cote, f'remplacee_{datetime.now():%Y%m%d_%H%M%S}.db'))
            except OSError:
                _log.warning('copie de la base remplacée impossible', exc_info=True)
        _poser(copie['chemin'], chemin_base)
    return _marquer_restauration(chemin_base, copie, motif)


def lire_marque_restauration(chemin_base=None):
    chemin_base = chemin_base or _chemin_base_courant()
    try:
        with open(os.path.join(os.path.dirname(chemin_base), NOM_MARQUE_RESTAURATION),
                  encoding='utf-8') as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return None


def effacer_marque_restauration(chemin_base=None):
    chemin_base = chemin_base or _chemin_base_courant()
    chemins.supprimer(os.path.join(os.path.dirname(chemin_base), NOM_MARQUE_RESTAURATION))


# ─── Démarrage ───────────────────────────────────────────────────────────────

def preparer_base(chemin_base):
    """Appelé au démarrage AVANT la sauvegarde et init_db. Renvoie
    'restauree', 'endommagee', 'ok' ou 'neuve'."""
    ETAT['secours'] = ''
    if not os.path.exists(chemin_base):
        return 'restauree' if restaurer_si_absente(chemin_base) else 'neuve'
    if not base_saine(chemin_base):
        ETAT['secours'] = 'endommagee'
        _log.error('Base abîmée (quick_check) : page de restauration activée')
        return 'endommagee'
    return 'ok'


def apres_demarrage():
    """Après init_db : archive de l'année close si besoin, puis miroir."""
    try:
        creer_archive_si_necessaire()
    except Exception:
        _log.warning('archive annuelle : exception ignorée', exc_info=True)
    try:
        ecrire_miroir()
    except Exception:
        _log.warning('miroir de démarrage : exception ignorée', exc_info=True)


def demarrer(chemin_base, init_db, backup_db=None):
    """Séquence commune à app.py et lancer_app.py. Renvoie l'état."""
    etat = preparer_base(chemin_base)
    if etat == 'endommagee':
        return etat
    if backup_db:
        backup_db()
    try:
        init_db()
    except Exception:
        _log.exception('init_db a échoué : page de restauration activée')
        ETAT['secours'] = 'endommagee'
        return 'endommagee'
    if etat == 'restauree':
        info = lire_marque_restauration(chemin_base) or {}
        try:
            import core.database as _db
            _db.journaliser('', 'استرجاع آليّ للقاعدة من النسخة المرآة',
                            info.get('source', ''), 'نسخة بتاريخ ' + info.get('date_copie', ''))
        except Exception:
            _log.warning('journal de restauration ignoré', exc_info=True)
    apres_demarrage()
    return etat


# ─── Archive annuelle ────────────────────────────────────────────────────────

def dossier_archives():
    return chemins.sous_dossier('archives')


def chemin_archive(annee):
    return os.path.join(dossier_archives(), f'archive_{int(annee)}.db')


def _annee_ouverte(conn):
    from core import exercice
    conn.row_factory = sqlite3.Row
    return exercice.annee_active(conn)


def creer_archive_si_necessaire(chemin_base=None):
    """Si le سجلّ ouvert est celui de l'année N et que l'année N-1 a des
    données sans archive, crée archive_(N-1).db (figée, lecture seule) dans
    data/archives et dans la miroir. Renvoie le chemin créé ou None."""
    chemin_base = chemin_base or _chemin_base_courant()
    if not os.path.isfile(chemin_base):
        return None
    conn = sqlite3.connect(chemin_base)
    try:
        annee = _annee_ouverte(conn) - 1
        a_des_donnees = conn.execute(
            'SELECT 1 FROM registre WHERE annee=? LIMIT 1', (annee,)).fetchone()
    except sqlite3.Error:
        return None
    finally:
        conn.close()
    dest = chemin_archive(annee)
    if not a_des_donnees or os.path.exists(dest):
        return None
    with _verrou:
        _copie_verifiee(chemin_base, dest)
    try:
        os.chmod(dest, stat.S_IREAD | stat.S_IRGRP | stat.S_IROTH)
    except OSError:
        pass
    for d in dossiers_miroir():
        try:
            cible = os.path.join(d, 'archives')
            os.makedirs(cible, exist_ok=True)
            if not os.path.exists(os.path.join(cible, os.path.basename(dest))):
                shutil.copy2(dest, cible)
        except OSError:
            _log.warning('copie de l archive vers la miroir impossible', exc_info=True)
    _log.info('Archive annuelle créée : %s', dest)
    return dest


def archives():
    """[{'annee', 'chemin', 'date', 'taille'}] des archives, la plus récente d'abord."""
    res = []
    for f in glob.glob(os.path.join(dossier_archives(), 'archive_*.db')):
        try:
            annee = int(os.path.basename(f)[8:12])
        except ValueError:
            continue
        res.append({'annee': annee, 'chemin': f, 'taille': os.path.getsize(f),
                    'date': datetime.fromtimestamp(os.path.getmtime(f)).strftime('%Y-%m-%d')})
    return sorted(res, key=lambda a: a['annee'], reverse=True)


# ─── État pour la page الإعدادات ─────────────────────────────────────────────

def taille_lisible(octets):
    o = float(octets or 0)
    for unite in ('بايت', 'ك.ب', 'م.ب', 'غ.ب'):
        if o < 1024 or unite == 'غ.ب':
            return f'{o:.0f} {unite}' if unite == 'بايت' else f'{o:.1f} {unite}'
        o /= 1024


def etat(chemin_base=None):
    chemin_base = chemin_base or _chemin_base_courant()
    derniere = ETAT['derniere']
    if not derniere:
        f = os.path.join(dossier_miroir_principal(), NOM_MIROIR)
        if os.path.isfile(f):
            derniere = datetime.fromtimestamp(os.path.getmtime(f)).strftime('%Y-%m-%d %H:%M:%S')
    taille = os.path.getsize(chemin_base) if os.path.isfile(chemin_base) else 0
    return {'dossier_defaut': dossiers_miroir()[0],
            'emplacement': emplacement_personnalise(),
            'derniere': derniere, 'erreur': ETAT['erreur'],
            'taille_base': taille_lisible(taille),
            'archives': [dict(a, taille_txt=taille_lisible(a['taille'])) for a in archives()]}

