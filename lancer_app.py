# -*- coding: utf-8 -*-
"""Point d'entrée du programme (exécutable Windows ou `python lancer_app.py`).

1.0 — le programme s'ouvre dans SA fenêtre :

  1. une seule instance : relancé alors qu'il tourne déjà, il remet la
     fenêtre ouverte au premier plan (ou rouvre l'adresse) et s'arrête ;
  2. port : 5055, ou à défaut le premier libre de 5056 à 5065 (retenu) ;
  3. base : restaurée depuis la نسخة المرآة si elle manque, sauvegarde,
     migrations (core/miroir.py) ;
  4. serveur Waitress dans un fil d'exécution ;
  5. affichage, du plus au moins intégré (core/lanceur.py) :
     fenêtre WebView2 → Edge en mode application → navigateur par défaut ;
  6. à la fermeture : miroir à jour, arrêt propre.

Plus de console : tout est écrit dans data/logs/lanceur.log, et une erreur
bloquante s'affiche dans une boîte de dialogue en arabe.
"""
import logging
import os
import sys
import threading
import time
import webbrowser

_log = logging.getLogger('formation.lancer_app')
_SESSION = {}           # serveur en cours (pour l'arrêt depuis un autre fil)


def recuperer_admin():
    """`FormationKasserine.exe --recuperer-admin` (compatibilité) — l'outil
    console livré est désormais RecupererAdmin.exe (recuperer_admin.bat)."""
    from core import recuperation, chemins
    code = recuperation.executer_console(chemins.chemin_base())
    sys.exit(code)


def _preparer_journal(donnees):
    """Sans console, stdout / stderr n'existent pas : ils vont au journal."""
    from logging.handlers import RotatingFileHandler
    dossier = os.path.join(donnees, 'logs')
    os.makedirs(dossier, exist_ok=True)
    h = RotatingFileHandler(os.path.join(dossier, 'lanceur.log'), maxBytes=500_000,
                            backupCount=2, encoding='utf-8')
    h.setFormatter(logging.Formatter('%(asctime)s [%(levelname)s] %(name)s: %(message)s'))
    racine = logging.getLogger('formation')
    racine.addHandler(h)
    racine.setLevel(logging.INFO)
    if sys.stdout is None or sys.stderr is None:
        flux = open(os.path.join(dossier, 'console.log'), 'a', encoding='utf-8', buffering=1)
        sys.stdout = sys.stdout or flux
        sys.stderr = sys.stderr or flux


def _dire(texte):
    _log.info(texte)
    try:
        print(texte)
    except Exception:
        pass


def main():
    if '--recuperer-admin' in sys.argv[1:]:
        recuperer_admin()
        return
    from core import chemins, lanceur
    donnees = chemins.dossier_donnees()
    _preparer_journal(donnees)
    try:
        _demarrer(donnees)
    except SystemExit:
        raise
    except Exception:
        _log.exception('Démarrage impossible')
        lanceur.message_erreur(lanceur.MESSAGES['demarrage'])
        os._exit(1)


def _demarrer(donnees):
    from core import chemins, lanceur, identite

    _log.info('— Démarrage %s (figé=%s, python %s)', identite.VERSION_APP,
              chemins.est_fige(), sys.version.split()[0])

    # 1) Instance unique
    inst = lanceur.instance_active(donnees)
    if inst:
        _log.info('Instance déjà ouverte : %s', inst)
        if inst.get('mode') == 'fenetre' and lanceur.amener_au_premier_plan():
            return
        webbrowser.open(f"http://127.0.0.1:{inst['port']}/")
        return

    # 2) Port
    port = lanceur.choisir_port(donnees)
    if port is None:
        lanceur.message_erreur(lanceur.MESSAGES['ports'])
        return
    url = f'http://127.0.0.1:{port}/'
    _log.info('Port retenu : %s', port)

    # 3) Données et base
    deplaces = chemins.migrer_ancien_emplacement()
    if deplaces:
        _dire(f"✓ Données rapatriées dans data/ : {', '.join(deplaces)}")
    chemins.purger_fichiers_transitoires()

    import core.database as database
    database.DB_PATH = chemins.chemin_base()
    from core import miroir

    def _sauvegarde():
        chemin = database.backup_db()
        if chemin:
            _dire(f'✓ Sauvegarde créée → {os.path.basename(chemin)}')

    etat = miroir.demarrer(database.DB_PATH, database.init_db, _sauvegarde)
    _log.info('Base : %s', etat)

    # 4) Serveur
    from app import app
    serveur = _serveur(app, port)
    _SESSION['serveur'] = serveur
    lanceur.ecrire_instance(donnees, port, 'demarrage')

    # 5) Affichage
    webview2 = lanceur.version_webview2()
    if lanceur.windows_10_ou_plus() and not webview2:
        lanceur.lancer_installation_webview2(
            lanceur.installateur_webview2(chemins.dossier_application()), donnees)
    if chemins.est_fige():
        lanceur.creer_raccourci_bureau(sys.executable, donnees)

    force = (os.environ.get('FK_MODE') or '').strip()
    modes = [force] if force in ('fenetre', 'edge', 'navigateur') else lanceur.modes_possibles(
        webview2=webview2, pywebview_ok=_pywebview_disponible(), edge=lanceur.chemin_edge())
    _log.info('WebView2 : %s — modes : %s', webview2 or 'absent', modes)

    for mode in modes:
        fonction = {'fenetre': _mode_fenetre, 'edge': _mode_edge,
                    'navigateur': _mode_navigateur}[mode]
        try:
            lanceur.maj_mode_instance(donnees, mode)
            if fonction(url, port, donnees):
                _log.info('Session terminée (mode %s)', mode)
                break
            _log.warning('Mode %s indisponible : mode suivant', mode)
        except Exception:
            _log.exception('Mode %s en échec : mode suivant', mode)

    # 6) Arrêt
    _arreter(serveur, donnees)


def _pywebview_disponible():
    try:
        import importlib.util
        return importlib.util.find_spec('webview') is not None
    except Exception:
        _log.warning('pywebview indisponible', exc_info=True)
        return False


def _serveur(app, port):
    from waitress import create_server
    serveur = create_server(app, host='127.0.0.1', port=port, threads=8)
    threading.Thread(target=serveur.run, name='waitress', daemon=True).start()
    _dire(f'✓ Serveur démarré → http://127.0.0.1:{port}')
    return serveur


def _attendre_serveur(port, delai=60):
    from core import lanceur
    fin = time.time() + delai
    while time.time() < fin:
        if lanceur.port_repond(port, 0.3):
            return True
        time.sleep(0.2)
    return False


# ─── Mode 1 : fenêtre native (WebView2) ──────────────────────────────────────

def _mode_fenetre(url, port, donnees):
    from core import chemins, identite, lanceur
    import webview
    if os.name == 'nt':
        # Sans WebView2, pywebview se rabattrait EN SILENCE sur Internet
        # Explorer : on refuse ce moteur et on passe au mode suivant.
        from webview.platforms import winforms
        if getattr(winforms, 'renderer', '') != 'edgechromium':
            _log.warning('Moteur pywebview = %s', getattr(winforms, 'renderer', '?'))
            return False
    webview.settings['ALLOW_DOWNLOADS'] = True
    webview.settings['OPEN_EXTERNAL_LINKS_IN_BROWSER'] = False
    if os.name == 'nt':
        _fenetres_secondaires(webview, url)

    profil = os.path.join(lanceur.dossier_ui(donnees), 'webview')
    if lanceur.vider_cache_si_nouvelle_version(profil, identite.VERSION_APP):
        _log.info('Caches de la fenêtre vidés (nouvelle version %s)', identite.VERSION_APP)
    e = lanceur.etat_fenetre(donnees)
    localisation = {'global.quitConfirmation': lanceur.MESSAGES['fermer'],
                    'global.ok': 'نعم', 'global.quit': 'إغلاق', 'global.cancel': 'لا',
                    'global.saveFile': 'حفظ الملفّ',
                    'windows.fileFilter.allFiles': 'كلّ الملفّات',
                    'windows.fileFilter.otherFiles': 'ملفّات أخرى'}
    fenetre = webview.create_window(
        lanceur.TITRE, html=lanceur.html_accueil(chemins.dossier_ressources(), identite.VERSION_APP),
        width=e['width'], height=e['height'], x=e['x'], y=e['y'], min_size=lanceur.TAILLE_MIN,
        maximized=e['maximized'], confirm_close=True, background_color='#f0f2f6',
        text_select=True, zoomable=True, localization=localisation)

    etat = {'max': e['maximized'], 'vue': False, 'w': e['width'], 'h': e['height'],
            'x': e['x'], 'y': e['y']}

    def _max():
        etat['max'] = True

    def _normale():
        etat['max'] = False

    def _vue():
        etat['vue'] = True

    def _taille(width, height):
        if not etat['max'] and width and height:
            etat['w'], etat['h'] = width, height

    def _position(x, y):
        if not etat['max']:
            etat['x'], etat['y'] = x, y

    def _fermeture():
        # Pas d'appel à la fenêtre ici (fil de l'interface) : la taille et la
        # position viennent des évènements « resized » et « moved ».
        lanceur.enregistrer_fenetre(donnees, etat['w'], etat['h'], etat['x'], etat['y'],
                                    etat['max'])

    fenetre.events.maximized += _max
    fenetre.events.restored += _normale
    fenetre.events.shown += _vue
    fenetre.events.resized += _taille
    fenetre.events.moved += _position
    fenetre.events.closing += _fermeture

    def _veille():
        # Point و : la fenêtre ne s'est pas affichée (moteur bloqué, erreur
        # .NET…) → pile des fils au journal, puis ouverture dans le navigateur.
        if etat['vue']:
            return
        _log.error("Fenêtre non affichée après %s s : passage au navigateur",
                   lanceur.DELAI_FENETRE)
        _pile_des_fils(donnees)
        lanceur.maj_mode_instance(donnees, 'navigateur')
        webbrowser.open(url)
        _attendre_inactivite()
        _arreter(_SESSION.get('serveur'), donnees)

    minuterie = threading.Timer(lanceur.DELAI_FENETRE, _veille)
    minuterie.daemon = True

    def _charger(f):
        if _attendre_serveur(port):
            f.load_url(url)
        else:
            _log.error('Le serveur ne répond pas sur %s', port)
            f.destroy()

    # WinForms n'accepte qu'un vrai .ico (un .png fait tomber le fil .NET)
    icone = os.path.join(chemins.dossier_ressources(), 'static', 'images', 'icone.ico')
    minuterie.start()
    try:
        webview.start(_charger, (fenetre,), gui='edgechromium', private_mode=False,
                      storage_path=profil, localization=localisation,
                      icon=icone if os.path.isfile(icone) else None)
    finally:
        minuterie.cancel()
    return etat['vue']


def _fenetres_secondaires(webview, base):
    """« نافذة مستقلّة » (lien target=_blank, window.open) : pywebview le
    chargeait DANS la fenêtre principale, qui perdait alors le programme (ni
    bouton retour ni menu). Désormais : une seconde fenêtre du programme pour
    ses propres pages, le navigateur pour toute adresse extérieure."""
    from core import lanceur
    try:
        from webview.platforms import edgechromium
    except Exception:
        _log.warning('fenêtres secondaires indisponibles', exc_info=True)
        return False

    def _nouvelle_fenetre(self, sender, args):
        args.set_Handled(True)
        cible = str(args.get_Uri())

        def _ouvrir():
            # hors du fil de l'interface : create_window y renvoie l'appel
            try:
                if cible.startswith(base):
                    webview.create_window(lanceur.TITRE, cible, width=1100, height=800,
                                          min_size=(700, 500), background_color='#f0f2f6',
                                          text_select=True, zoomable=True)
                else:
                    webbrowser.open(cible)
            except Exception:
                _log.exception('Fenêtre secondaire : %s', cible)
                webbrowser.open(cible)

        threading.Thread(target=_ouvrir, name='fenetre-secondaire', daemon=True).start()

    edgechromium.EdgeChrome.on_new_window_request = _nouvelle_fenetre
    return True


def _pile_des_fils(donnees):
    try:
        import faulthandler
        with open(os.path.join(donnees, 'logs', 'pile_fenetre.txt'), 'w',
                  encoding='utf-8') as f:
            faulthandler.dump_traceback(file=f, all_threads=True)
    except Exception:
        _log.warning('pile des fils non écrite', exc_info=True)


# ─── Mode 2 : Edge en mode application ───────────────────────────────────────

def _mode_edge(url, port, donnees):
    import subprocess
    from core import lanceur
    edge = lanceur.chemin_edge()
    if not edge or not _attendre_serveur(port):
        return False
    profil = os.path.join(lanceur.dossier_ui(donnees), 'edge')
    debut = time.time()
    processus = subprocess.Popen([edge, f'--app={url}', f'--user-data-dir={profil}',
                                  '--no-first-run', '--no-default-browser-check',
                                  # interface arabe : pas de « ترجمة الصفحة ؟ » d'Edge
                                  '--disable-features=Translate,msEdgeTranslate',
                                  '--start-maximized'])
    processus.wait()
    if time.time() - debut < 8:
        # Edge a confié la fenêtre à une instance déjà ouverte : on ne sait
        # pas quand elle se ferme — même règle que le navigateur.
        _attendre_inactivite()
    return True


# ─── Mode 3 : navigateur par défaut ──────────────────────────────────────────

def _mode_navigateur(url, port, donnees):
    if not _attendre_serveur(port):
        return False
    webbrowser.open(url)
    _attendre_inactivite()
    return True


def _attendre_inactivite():
    """Sans fenêtre à surveiller, le programme s'arrête seul après
    INACTIVITE_MAX sans aucune requête (relancé, il rouvre l'adresse)."""
    from core import lanceur
    lanceur.noter_activite()
    pas = max(0.5, min(15, lanceur.INACTIVITE_MAX / 4))
    while lanceur.inactif_depuis() < lanceur.INACTIVITE_MAX:
        time.sleep(pas)
    _log.info('Arrêt après inactivité')


# ─── Arrêt ───────────────────────────────────────────────────────────────────

def _arreter(serveur, donnees):
    from core import lanceur, miroir
    try:
        miroir.ecrire_miroir()
    except Exception:
        _log.warning('miroir de fermeture ignorée', exc_info=True)
    lanceur.effacer_instance(donnees)
    try:
        if serveur is not None:
            serveur.close()
    except Exception:
        pass
    _log.info('— Arrêt')
    logging.shutdown()
    os._exit(0)


if __name__ == '__main__':
    main()
