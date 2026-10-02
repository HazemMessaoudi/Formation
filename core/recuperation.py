# -*- coding: utf-8 -*-
"""Récupération locale du compte مشرف عام (v1.7).

Quand le seul مشرف عام a oublié son mot de passe, plus personne ne peut
confirmer les مستحقّات, déverrouiller une دورة, lire l'يوميّات ni faire une
sauvegarde. Cet outil, lancé SUR LE POSTE par `recuperer_admin.bat`, programme
fermé :

  1. choisit le compte مشرف عام à récupérer (s'il y en a plusieurs, on
     demande lequel, par son numéro) ;
  2. lui pose un mot de passe PROVISOIRE aléatoire, affiché à l'écran ;
  3. l'oblige à le changer à la prochaine connexion ;
  4. lève un éventuel blocage de connexion (trop d'essais) ;
  5. consigne l'opération dans le سجلّ التّدقيق.

S'il n'existe plus AUCUN مشرف عام (base abîmée à la main), le compte
historique « admin » est rétabli comme مشرف عام.

L'outil ne passe PAS par le serveur : il n'a besoin que de la base. La
sécurité repose sur l'accès physique au poste (même règle que la base
elle-même, qui se copie avec l'explorateur).
"""

import os
import secrets
import socket
import sqlite3
from datetime import datetime

from werkzeug.security import generate_password_hash

#: Alphabet sans caractères ambigus (0/O, 1/l/I) : le mot de passe se recopie
#: à la main depuis l'écran.
_ALPHABET = 'ABCDEFGHJKLMNPQRSTUVWXYZabcdefghjkmnpqrstuvwxyz23456789'
LONGUEUR_PROVISOIRE = 10
PORT_APPLICATION = 5055


def mot_de_passe_provisoire(longueur=LONGUEUR_PROVISOIRE):
    return ''.join(secrets.choice(_ALPHABET) for _ in range(longueur))


PORTS_APPLICATION = tuple(range(5055, 5066))     # 1.0 : 5055 ou 5056 … 5065


def _est_la_mandhouma(port):
    """Le port répond-il, et est-ce bien NOTRE programme ? (1.0 : un autre
    logiciel peut occuper 5055 ; seul notre écran de connexion compte)."""
    import urllib.request
    try:
        with socket.create_connection(('127.0.0.1', port), timeout=0.5):
            pass
    except OSError:
        return False
    try:
        with urllib.request.urlopen(f'http://127.0.0.1:{port}/login', timeout=2) as r:
            return 'نظام إدارة التكوين' in r.read(200_000).decode('utf-8', 'replace')
    except Exception:
        return False


def serveur_actif(port=None):
    """Vrai si la منظومة tourne encore, quel que soit le port retenu."""
    ports = (port,) if port else PORTS_APPLICATION
    return any(_est_la_mandhouma(p) for p in ports)


def comptes_admin(db_path):
    conn = sqlite3.connect(db_path)
    try:
        return [r[0] for r in conn.execute(
            "SELECT username FROM users WHERE role='admin' ORDER BY id")]
    finally:
        conn.close()


def recuperer(db_path, username=None, mot_de_passe=None):
    """Réinitialise le mot de passe d'un مشرف عام. Renvoie (username, mdp).

    `username` : le compte visé ; None = l'unique مشرف (ou « admin » rétabli
    s'il n'en reste aucun). Lève ValueError si le compte n'est pas un مشرف."""
    if not os.path.exists(db_path):
        raise FileNotFoundError(db_path)
    mdp = mot_de_passe or mot_de_passe_provisoire()
    conn = sqlite3.connect(db_path)
    try:
        admins = [r[0] for r in conn.execute(
            "SELECT username FROM users WHERE role='admin' ORDER BY id")]
        if username is None:
            if len(admins) > 1:
                raise ValueError('plusieurs comptes مشرف عام : préciser lequel')
            if admins:
                username = admins[0]
            else:
                username = 'admin'
                if conn.execute("SELECT 1 FROM users WHERE username='admin'").fetchone():
                    conn.execute("UPDATE users SET role='admin' WHERE username='admin'")
                else:
                    conn.execute("INSERT INTO users (username, password_hash, role) "
                                 "VALUES ('admin', '', 'admin')")
        elif username not in admins:
            raise ValueError(f'« {username} » n\'est pas un compte مشرف عام')
        conn.execute('UPDATE users SET password_hash=?, doit_changer_mdp=1 WHERE username=?',
                     (generate_password_hash(mdp), username))
        # Blocage de connexion (v1.7) levé, s'il existe.
        cols = {c[1] for c in conn.execute('PRAGMA table_info(users)')}
        if 'echecs' in cols:
            conn.execute('UPDATE users SET echecs=0, bloque_jusqua=NULL WHERE username=?',
                         (username,))
        tables = {r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'")}
        if 'journal' in tables:
            conn.execute(
                'INSERT INTO journal (horodatage, utilisateur, action, cible, details) '
                'VALUES (?,?,?,?,?)',
                (datetime.now().strftime('%Y-%m-%d %H:%M:%S'), 'أداة الاسترجاع',
                 'استرجاع كلمة مرور المشرف العام (أداة محلّية)', username,
                 'كلمة مرور مؤقّتة — تغييرها إجباري عند الدخول'))
        conn.commit()
    finally:
        conn.close()
    return username, mdp


def _afficher(ligne):
    """print() qui ne plante jamais sur une console non UTF-8."""
    import sys
    codage = getattr(sys.stdout, 'encoding', None) or 'utf-8'
    try:
        str(ligne).encode(codage)
    except (UnicodeEncodeError, LookupError):
        ligne = str(ligne).encode('ascii', 'replace').decode('ascii')
    print(ligne)


def executer_console(db_path, entree=input, sortie=_afficher):
    """Déroulé interactif (console Windows). Renvoie le code de sortie."""
    sortie('')
    sortie('=' * 60)
    sortie('  Recuperation du compte administrateur (مشرف عام)')
    sortie('=' * 60)
    if serveur_actif():
        sortie('')
        sortie("[!] Le programme est encore ouvert. Fermez-le puis relancez cet outil.")
        sortie('    أغلق البرنامج أوّلًا ثمّ أعد تشغيل الأداة.')
        return 2
    if not os.path.exists(db_path):
        sortie(f'[ERREUR] Base introuvable : {db_path}')
        return 1
    admins = comptes_admin(db_path)
    cible = None
    if len(admins) > 1:
        sortie('')
        sortie('Comptes administrateurs :')
        for i, nom in enumerate(admins, 1):
            sortie(f'   {i}) {nom}')
        try:
            choix = (entree('Numero du compte a recuperer : ') or '').strip()
        except (EOFError, KeyboardInterrupt):
            choix = ''
        try:
            cible = admins[int(choix) - 1]
            if int(choix) < 1:
                raise IndexError
        except (ValueError, IndexError):
            sortie('[ERREUR] Choix invalide. Aucune modification.')
            return 1
    try:
        nom, mdp = recuperer(db_path, cible)
    except Exception as e:  # noqa: BLE001 — message lisible pour l'agent
        sortie(f'[ERREUR] {e}')
        return 1
    sortie('')
    sortie('[OK] Mot de passe provisoire pose.')
    sortie(f'     Compte              : {nom}')
    sortie(f'     Mot de passe        : {mdp}')
    sortie('')
    sortie('  Notez-le, lancez le programme et connectez-vous :')
    sortie('  un nouveau mot de passe vous sera demande immediatement.')
    sortie('  سجّل كلمة المرور المؤقّتة، ثمّ ادخل إلى البرنامج وغيّرها فورًا.')
    return 0
