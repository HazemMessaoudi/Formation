# -*- coding: utf-8 -*-
"""1.0 — النافذة الخاصّة بالبرنامج : décisions et outils du lanceur.

Ordre des modes (le premier qui marche gagne ; aucun blocage possible) :

  1. « fenetre »    — fenêtre native pywebview sur le moteur Edge WebView2
                      (Windows 10+, WebView2 présent) ;
  2. « edge »       — Microsoft Edge en mode application (--app, sans barre
                      d'adresse), profil propre au programme ;
  3. « navigateur » — le navigateur par défaut, comme avant.

Windows 7/8 : directement « navigateur ». WebView2 absent : son installateur
complet (Outils/MicrosoftEdgeWebView2RuntimeInstaller*.exe), s'il est livré,
est lancé en silence, sans droits d'administrateur ; le programme s'ouvre
aussitôt par le mode suivant, et en fenêtre au démarrage d'après.

Tout ce qui touche au système (registre, fenêtres, processus) est isolé dans
de petites fonctions, remplaçables dans les tests. L'état du lanceur vit
dans data/ui/ (port retenu, taille de la fenêtre, profil du navigateur).
"""

import glob
import json
import logging as _logging
import os
import shutil
import socket
import subprocess
import sys
import time

_log = _logging.getLogger('formation.' + __name__)

TITRE = 'نظام إدارة التكوين الديواني'
PORT_DEFAUT = 5055
PORTS = tuple(range(5055, 5066))           # 5055, puis 5056 … 5065
CLE_WEBVIEW2 = '{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}'
DELAI_REESSAI_INSTALLATION = 30 * 60      # s : pas deux installations en 30 min
INACTIVITE_MAX = int(os.environ.get('FK_INACTIVITE_MAX') or 3 * 3600)   # s : arrêt auto (navigateur)
TAILLE_MIN = (1000, 650)
# s : si la fenêtre ne s'est pas affichée dans ce délai, le programme
# s'ouvre dans le navigateur (point و : « tout problème → navigateur »)
DELAI_FENETRE = int(os.environ.get('FK_DELAI_FENETRE') or 45)

MESSAGES = {
    'ports': 'تعذّر تشغيل البرنامج: كلّ المنافذ من 5055 إلى 5065 مشغولة ببرامج أخرى.\n'
             'أغلق البرامج الأخرى أو أعد تشغيل الحاسوب ثمّ أعد المحاولة.',
    'demarrage': 'تعذّر تشغيل البرنامج.\nالتفاصيل مسجّلة في الملفّ data\\logs\\lanceur.log',
    'fermer': 'هل تريد إغلاق البرنامج؟',
}


# ─── Fichiers d'état (data/ui/) ──────────────────────────────────────────────

def dossier_ui(dossier_donnees):
    d = os.path.join(dossier_donnees, 'ui')
    os.makedirs(d, exist_ok=True)
    return d


def lire_json(chemin, defaut=None):
    try:
        with open(chemin, encoding='utf-8') as fh:
            v = json.load(fh)
        return v if isinstance(v, dict) else (defaut if defaut is not None else {})
    except (OSError, ValueError):
        return defaut if defaut is not None else {}


def ecrire_json(chemin, valeur):
    tmp = chemin + '.tmp'
    try:
        with open(tmp, 'w', encoding='utf-8') as fh:
            json.dump(valeur, fh, ensure_ascii=False)
        os.replace(tmp, chemin)
        return True
    except OSError:
        _log.warning('ecrire_json : %s', chemin, exc_info=True)
        return False


# ─── Ports ───────────────────────────────────────────────────────────────────

def port_libre(port):
    """True si 127.0.0.1:port peut être pris maintenant."""
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        if os.name == 'nt':
            s.setsockopt(socket.SOL_SOCKET, getattr(socket, 'SO_EXCLUSIVEADDRUSE', 0x4), 1)
        s.bind(('127.0.0.1', int(port)))
        return True
    except OSError:
        return False
    finally:
        s.close()


def port_repond(port, delai=0.5):
    try:
        with socket.create_connection(('127.0.0.1', int(port)), timeout=delai):
            return True
    except (OSError, ValueError, TypeError):
        return False


def choisir_port(dossier_donnees, est_libre=port_libre):
    """Le port retenu la dernière fois s'il est libre, sinon le premier libre
    de 5055 à 5065 (retenu pour la suite). None si tous sont pris."""
    chemin = os.path.join(dossier_ui(dossier_donnees), 'port.json')
    retenu = lire_json(chemin).get('port')
    candidats = ([retenu] if retenu in PORTS else []) + [p for p in PORTS if p != retenu]
    for p in candidats:
        if est_libre(p):
            if p != retenu:
                ecrire_json(chemin, {'port': p})
            return p
    return None


# ─── Instance unique ─────────────────────────────────────────────────────────

def pid_vivant(pid):
    try:
        pid = int(pid)
    except (TypeError, ValueError):
        return False
    if pid <= 0:
        return False
    if os.name == 'nt':
        import ctypes
        k32 = ctypes.windll.kernel32
        h = k32.OpenProcess(0x1000, False, pid)        # QUERY_LIMITED_INFORMATION
        if not h:
            return False
        try:
            code = ctypes.c_ulong()
            return bool(k32.GetExitCodeProcess(h, ctypes.byref(code))) and code.value == 259
        finally:
            k32.CloseHandle(h)
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def _chemin_instance(dossier_donnees):
    return os.path.join(dossier_ui(dossier_donnees), 'instance.json')


def ecrire_instance(dossier_donnees, port, mode, pid=None):
    return ecrire_json(_chemin_instance(dossier_donnees),
                       {'pid': pid or os.getpid(), 'port': port, 'mode': mode,
                        'depuis': time.strftime('%Y-%m-%d %H:%M:%S')})


def maj_mode_instance(dossier_donnees, mode):
    inst = lire_json(_chemin_instance(dossier_donnees))
    if inst.get('pid') == os.getpid():
        inst['mode'] = mode
        ecrire_json(_chemin_instance(dossier_donnees), inst)


def effacer_instance(dossier_donnees):
    inst = lire_json(_chemin_instance(dossier_donnees))
    if not inst or inst.get('pid') == os.getpid():
        try:
            os.remove(_chemin_instance(dossier_donnees))
        except OSError:
            pass


def instance_active(dossier_donnees, vivant=pid_vivant, repond=port_repond):
    """L'instance déjà ouverte de CETTE installation ({pid, port, mode}),
    ou None. Un fichier laissé par un arrêt brutal est ignoré."""
    inst = lire_json(_chemin_instance(dossier_donnees))
    if not inst or inst.get('pid') == os.getpid():
        return None
    if vivant(inst.get('pid')) and repond(inst.get('port')):
        return inst
    return None


def amener_au_premier_plan(titre=TITRE):
    """Fenêtre déjà ouverte : restaurée et mise devant. True si trouvée."""
    if os.name != 'nt':
        return False
    try:
        import ctypes
        u32 = ctypes.windll.user32
        hwnd = u32.FindWindowW(None, titre)
        if not hwnd:
            return False
        if u32.IsIconic(hwnd):
            u32.ShowWindow(hwnd, 9)                      # SW_RESTORE
        u32.ShowWindow(hwnd, 5)                          # SW_SHOW
        u32.SetForegroundWindow(hwnd)
        return True
    except Exception:
        _log.warning('amener_au_premier_plan : échec', exc_info=True)
        return False


# ─── Système : version de Windows, WebView2, Edge ────────────────────────────

def windows_10_ou_plus():
    if os.name != 'nt':
        return False
    try:
        return sys.getwindowsversion().major >= 10
    except Exception:
        return False


def version_webview2():
    """Version du runtime WebView2 installé ('' si absent). Mêmes clés que
    pywebview (machine 64 bits, machine 32 bits, utilisateur)."""
    if os.name != 'nt':
        return ''
    import winreg
    chemins = (
        (winreg.HKEY_LOCAL_MACHINE, rf'SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\Clients\{CLE_WEBVIEW2}'),
        (winreg.HKEY_LOCAL_MACHINE, rf'SOFTWARE\Microsoft\EdgeUpdate\Clients\{CLE_WEBVIEW2}'),
        (winreg.HKEY_CURRENT_USER, rf'SOFTWARE\Microsoft\EdgeUpdate\Clients\{CLE_WEBVIEW2}'),
    )
    for racine, chemin in chemins:
        try:
            with winreg.OpenKey(racine, chemin) as cle:
                v = str(winreg.QueryValueEx(cle, 'pv')[0] or '')
                if v and v != '0.0.0.0':
                    return v
        except OSError:
            continue
    return ''


def installateur_webview2(dossier_application):
    """Chemin de l'installateur complet livré dans Outils/ ('' si absent)."""
    for nom in ('Outils', 'outils'):
        trouves = sorted(glob.glob(os.path.join(
            dossier_application, nom, 'MicrosoftEdgeWebView2RuntimeInstaller*.exe')))
        if trouves:
            # x64 d'abord sur une machine 64 bits, sinon x86
            x64 = [f for f in trouves if 'X64' in os.path.basename(f).upper()]
            x86 = [f for f in trouves if 'X86' in os.path.basename(f).upper()]
            est64 = os.environ.get('PROCESSOR_ARCHITECTURE', '').endswith('64') or \
                os.environ.get('PROCESSOR_ARCHITEW6432', '')
            return (x64 or trouves)[0] if est64 else (x86 or trouves)[0]
    return ''


def lancer_installation_webview2(installateur, dossier_donnees, maintenant=None,
                                 executer=None):
    """Installation silencieuse en arrière-plan (sans droits d'administrateur :
    installation « par utilisateur »). Une seule tentative par 30 minutes.
    Renvoie True si l'installateur a été lancé."""
    if not installateur or not os.path.isfile(installateur):
        return False
    maintenant = maintenant or time.time()
    chemin = os.path.join(dossier_ui(dossier_donnees), 'webview2_installation.json')
    dernier = lire_json(chemin).get('lance')
    if dernier is not None and maintenant - float(dernier) < DELAI_REESSAI_INSTALLATION:
        return False
    executer = executer or _executer_detache
    try:
        executer([installateur, '/silent', '/install'])
    except Exception:
        _log.warning('installation WebView2 : échec du lancement', exc_info=True)
        return False
    ecrire_json(chemin, {'lance': maintenant, 'installateur': os.path.basename(installateur)})
    _log.info('Installation de WebView2 lancée : %s', installateur)
    return True


def _executer_detache(commande):
    drapeaux = 0
    if os.name == 'nt':
        drapeaux = 0x00000008 | 0x08000000       # DETACHED_PROCESS | CREATE_NO_WINDOW
    subprocess.Popen(commande, creationflags=drapeaux, close_fds=True,
                     stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                     stderr=subprocess.DEVNULL)


def chemin_edge():
    if os.name != 'nt':
        return ''
    bases = [os.environ.get(v, '') for v in ('ProgramFiles(x86)', 'ProgramFiles', 'LOCALAPPDATA')]
    for b in bases:
        if b:
            f = os.path.join(b, 'Microsoft', 'Edge', 'Application', 'msedge.exe')
            if os.path.isfile(f):
                return f
    return ''


def modes_possibles(win10=None, webview2='', pywebview_ok=True, edge=''):
    """Ordre des modes à essayer, du plus au moins intégré."""
    win10 = windows_10_ou_plus() if win10 is None else win10
    if not win10:
        return ['navigateur']
    modes = []
    if webview2 and pywebview_ok:
        modes.append('fenetre')
    if edge:
        modes.append('edge')
    modes.append('navigateur')
    return modes


# ─── Fenêtre : taille / position, cache après mise à jour ────────────────────

def _ecran_virtuel():
    """(x, y, largeur, hauteur) du bureau (tous écrans), ou None."""
    if os.name != 'nt':
        return None
    try:
        import ctypes
        m = ctypes.windll.user32.GetSystemMetrics
        return m(76), m(77), m(78), m(79)
    except Exception:
        return None


def etat_fenetre(dossier_donnees, ecran=None):
    """{'width','height','x','y','maximized'} — première fois : agrandie.
    Une position hors de l'écran (écran débranché…) est oubliée."""
    e = lire_json(os.path.join(dossier_ui(dossier_donnees), 'fenetre.json'))
    if not e:
        return {'width': 1280, 'height': 800, 'x': None, 'y': None, 'maximized': True}
    try:
        w = max(TAILLE_MIN[0], min(int(e.get('width', 1280)), 8000))
        h = max(TAILLE_MIN[1], min(int(e.get('height', 800)), 5000))
        x, y = e.get('x'), e.get('y')
        x = int(x) if x is not None else None
        y = int(y) if y is not None else None
    except (TypeError, ValueError):
        return {'width': 1280, 'height': 800, 'x': None, 'y': None, 'maximized': True}
    ecran = ecran if ecran is not None else _ecran_virtuel()
    if ecran and x is not None and y is not None:
        ex, ey, ew, eh = ecran
        if not (ex - 50 <= x <= ex + ew - 200 and ey - 50 <= y <= ey + eh - 100):
            x = y = None
    return {'width': w, 'height': h, 'x': x, 'y': y, 'maximized': bool(e.get('maximized'))}


def enregistrer_fenetre(dossier_donnees, width, height, x, y, maximized):
    return ecrire_json(os.path.join(dossier_ui(dossier_donnees), 'fenetre.json'),
                       {'width': width, 'height': height, 'x': x, 'y': y,
                        'maximized': bool(maximized)})


CACHES = ('Cache', 'Code Cache', 'GPUCache', 'Service Worker')


def vider_cache_si_nouvelle_version(dossier_profil, version):
    """Après une mise à jour : caches du moteur supprimés (fini Ctrl + F5).
    Le « Local Storage » (thème, police choisis) est conservé. Renvoie le
    nombre de dossiers vidés."""
    os.makedirs(dossier_profil, exist_ok=True)
    chemin = os.path.join(dossier_profil, 'version_programme.json')
    if lire_json(chemin).get('version') == version:
        return 0
    n = 0
    for racine, dossiers, _fichiers in os.walk(dossier_profil):
        for d in list(dossiers):
            if d in CACHES:
                shutil.rmtree(os.path.join(racine, d), ignore_errors=True)
                dossiers.remove(d)
                n += 1
    ecrire_json(chemin, {'version': version})
    return n


# ─── Raccourci sur le bureau ─────────────────────────────────────────────────

def dossier_bureau():
    if os.name != 'nt':
        return ''
    try:
        import ctypes
        from ctypes import wintypes
        buf = ctypes.create_unicode_buffer(wintypes.MAX_PATH)
        ctypes.windll.shell32.SHGetFolderPathW(None, 0x0010, None, 0, buf)   # CSIDL_DESKTOPDIRECTORY
        return buf.value
    except Exception:
        return os.path.join(os.path.expanduser('~'), 'Desktop')


def creer_raccourci_bureau(exe, dossier_donnees, executer=None, bureau=None):
    """Une seule fois par installation : raccourci « نظام إدارة التكوين » sur
    le bureau, à l'icône de l'exécutable. Renvoie le chemin créé ou ''."""
    marque = os.path.join(dossier_ui(dossier_donnees), 'raccourci.json')
    if lire_json(marque).get('fait'):
        return ''
    bureau = bureau if bureau is not None else dossier_bureau()
    if not bureau or not os.path.isdir(bureau) or not os.path.isfile(exe):
        return ''
    lien = os.path.join(bureau, 'نظام إدارة التكوين.lnk')

    def _ps(s):
        return s.replace("'", "''")
    script = (f"$s=(New-Object -ComObject WScript.Shell).CreateShortcut('{_ps(lien)}');"
              f"$s.TargetPath='{_ps(exe)}';$s.WorkingDirectory='{_ps(os.path.dirname(exe))}';"
              f"$s.IconLocation='{_ps(exe)},0';$s.Description='{_ps(TITRE)}';$s.Save()")
    executer = executer or _executer_attente
    try:
        executer(['powershell', '-NoProfile', '-NonInteractive', '-ExecutionPolicy', 'Bypass',
                  '-Command', script])
    except Exception:
        _log.warning('raccourci du bureau : échec', exc_info=True)
        return ''
    ecrire_json(marque, {'fait': True, 'chemin': lien})
    return lien


def _executer_attente(commande):
    drapeaux = 0x08000000 if os.name == 'nt' else 0          # CREATE_NO_WINDOW
    subprocess.run(commande, creationflags=drapeaux, timeout=30, check=False,
                   stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


# ─── Message d'erreur (plus de console) ──────────────────────────────────────

def message_erreur(texte, titre=TITRE):
    _log.error('Message à l utilisateur : %s', texte)
    if os.name == 'nt':
        try:
            import ctypes
            # MB_ICONERROR | MB_RIGHT | MB_RTLREADING | MB_SETFOREGROUND
            ctypes.windll.user32.MessageBoxW(None, texte, titre, 0x10 | 0x80000 | 0x100000 | 0x10000)
            return
        except Exception:
            pass
    try:
        print(texte)
    except Exception:
        pass


# ─── Activité (arrêt automatique en mode navigateur) ─────────────────────────

_activite = {'t': time.time()}


def noter_activite():
    _activite['t'] = time.time()


def inactif_depuis():
    return time.time() - _activite['t']


# ─── Écran d'accueil (pendant le démarrage) ──────────────────────────────────

def html_accueil(dossier_ressources, version):
    """Page affichée dans la fenêtre pendant que le serveur démarre."""
    import base64
    logo = ''
    try:
        with open(os.path.join(dossier_ressources, 'static', 'images', 'logo.jpg'), 'rb') as fh:
            logo = 'data:image/jpeg;base64,' + base64.b64encode(fh.read()).decode('ascii')
    except OSError:
        pass
    img = f'<img src="{logo}" alt="">' if logo else ''
    return f'''<!DOCTYPE html><html lang="ar" dir="rtl"><head><meta charset="utf-8">
<style>
html,body{{height:100%;margin:0}}
body{{display:flex;align-items:center;justify-content:center;background:#f0f2f6;
font-family:"Segoe UI",Tahoma,Arial,sans-serif;color:#1a3a6b}}
.c{{text-align:center}}
img{{width:110px;height:auto;border-radius:18px;background:#fff;padding:12px;
box-shadow:0 6px 24px rgba(26,58,107,.15)}}
h1{{font-size:26px;margin:22px 0 6px}}
p{{margin:0;color:#5a6680;font-size:14px}}
.b{{width:180px;height:4px;background:#d0d8e4;border-radius:2px;margin:22px auto 0;overflow:hidden}}
.b i{{display:block;width:40%;height:100%;background:#c8a84b;border-radius:2px;
animation:a 1.2s ease-in-out infinite}}
@keyframes a{{0%{{transform:translateX(160%)}}100%{{transform:translateX(-260%)}}}}
</style></head><body><div class="c">{img}
<h1>{TITRE}</h1><p>جاري تشغيل البرنامج… — الإصدار {version}</p>
<div class="b"><i></i></div></div></body></html>'''
