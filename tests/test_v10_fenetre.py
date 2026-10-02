# -*- coding: utf-8 -*-
"""1.0 — النافذة الخاصّة بالبرنامج : logique du lanceur (core/lanceur.py) et
démarrage réel de lancer_app.py (mode navigateur, sans écran)."""
import json
import os
import socket
import subprocess
import sys
import time
import urllib.request

import pytest

from core import lanceur

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# ═══ Port (point هـ) ═════════════════════════════════════════════════════════

def test_port_par_defaut_puis_suivant_retenu(tmp_path):
    d = str(tmp_path)
    assert lanceur.choisir_port(d, est_libre=lambda p: True) == 5055
    # 5055 pris par un autre logiciel → 5056, retenu
    assert lanceur.choisir_port(d, est_libre=lambda p: p != 5055) == 5056
    assert json.load(open(os.path.join(d, 'ui', 'port.json')))['port'] == 5056
    # la fois suivante, le port retenu passe en premier même si 5055 est libre
    assert lanceur.choisir_port(d, est_libre=lambda p: True) == 5056
    assert lanceur.choisir_port(d, est_libre=lambda p: False) is None


def test_port_libre_reel():
    s = socket.socket()
    s.bind(('127.0.0.1', 0))
    s.listen(1)
    pris = s.getsockname()[1]
    try:
        assert not lanceur.port_libre(pris)
        assert lanceur.port_repond(pris)
    finally:
        s.close()


# ═══ Instance unique (point 4) ══════════════════════════════════════════════

def test_instance_active(tmp_path):
    d = str(tmp_path)
    assert lanceur.instance_active(d) is None
    lanceur.ecrire_instance(d, 5057, 'fenetre', pid=424242)
    inst = lanceur.instance_active(d, vivant=lambda p: True, repond=lambda p: True)
    assert inst['port'] == 5057 and inst['mode'] == 'fenetre'
    # arrêt brutal : processus mort ou port muet → ignorée
    assert lanceur.instance_active(d, vivant=lambda p: False, repond=lambda p: True) is None
    assert lanceur.instance_active(d, vivant=lambda p: True, repond=lambda p: False) is None
    # notre propre processus n'est jamais « l'autre instance »
    lanceur.ecrire_instance(d, 5057, 'fenetre')
    assert lanceur.instance_active(d, vivant=lambda p: True, repond=lambda p: True) is None
    lanceur.maj_mode_instance(d, 'edge')
    assert lanceur.lire_json(os.path.join(d, 'ui', 'instance.json'))['mode'] == 'edge'
    lanceur.effacer_instance(d)
    assert not os.path.exists(os.path.join(d, 'ui', 'instance.json'))


def test_pid_vivant():
    assert lanceur.pid_vivant(os.getpid())
    assert not lanceur.pid_vivant(0) and not lanceur.pid_vivant('x')


# ═══ Ordre des modes (points 1 et 7) ════════════════════════════════════════

def test_ordre_des_modes():
    m = lanceur.modes_possibles
    assert m(win10=True, webview2='120.0', pywebview_ok=True, edge='msedge') == \
        ['fenetre', 'edge', 'navigateur']
    assert m(win10=True, webview2='', edge='msedge') == ['edge', 'navigateur']
    assert m(win10=True, webview2='120.0', pywebview_ok=False, edge='') == ['navigateur']
    assert m(win10=False, webview2='120.0', edge='msedge') == ['navigateur']     # Windows 7/8


# ═══ Installation de WebView2 (point 6) ═════════════════════════════════════

def test_installateur_livre(tmp_path, monkeypatch):
    assert lanceur.installateur_webview2(str(tmp_path)) == ''
    outils = tmp_path / 'Outils'
    outils.mkdir()
    (outils / 'MicrosoftEdgeWebView2RuntimeInstallerX86.exe').write_bytes(b'x')
    (outils / 'MicrosoftEdgeWebView2RuntimeInstallerX64.exe').write_bytes(b'x')
    monkeypatch.setenv('PROCESSOR_ARCHITECTURE', 'AMD64')
    assert lanceur.installateur_webview2(str(tmp_path)).endswith('X64.exe')
    monkeypatch.setenv('PROCESSOR_ARCHITECTURE', 'x86')
    monkeypatch.delenv('PROCESSOR_ARCHITEW6432', raising=False)
    assert lanceur.installateur_webview2(str(tmp_path)).endswith('X86.exe')


def test_installation_silencieuse_une_fois_par_30_minutes(tmp_path):
    inst = tmp_path / 'MicrosoftEdgeWebView2RuntimeInstallerX64.exe'
    inst.write_bytes(b'x')
    appels = []
    d = str(tmp_path / 'data')
    assert lanceur.lancer_installation_webview2(str(inst), d, 1000, appels.append)
    assert appels == [[str(inst), '/silent', '/install']]
    assert not lanceur.lancer_installation_webview2(str(inst), d, 1000 + 60, appels.append)
    assert lanceur.lancer_installation_webview2(str(inst), d, 1000 + 31 * 60, appels.append)
    assert not lanceur.lancer_installation_webview2('', d, 99999, appels.append)
    assert len(appels) == 2


# ═══ Taille et position (point 5), cache après mise à jour (أ) ══════════════

def test_etat_de_la_fenetre(tmp_path):
    d = str(tmp_path)
    e = lanceur.etat_fenetre(d, ecran=(0, 0, 1920, 1080))
    assert e['maximized'] and e['x'] is None                 # 1re fois : agrandie
    lanceur.enregistrer_fenetre(d, 1100, 700, 100, 80, False)
    e = lanceur.etat_fenetre(d, ecran=(0, 0, 1920, 1080))
    assert (e['width'], e['height'], e['x'], e['y'], e['maximized']) == (1100, 700, 100, 80, False)
    # écran débranché : position oubliée, taille gardée
    lanceur.enregistrer_fenetre(d, 1100, 700, 3000, 80, False)
    e = lanceur.etat_fenetre(d, ecran=(0, 0, 1920, 1080))
    assert e['x'] is None and e['width'] == 1100
    # trop petite : taille minimale
    lanceur.enregistrer_fenetre(d, 300, 200, 10, 10, False)
    e = lanceur.etat_fenetre(d, ecran=(0, 0, 1920, 1080))
    assert (e['width'], e['height']) == lanceur.TAILLE_MIN


def test_cache_vide_apres_mise_a_jour_mais_pas_les_preferences(tmp_path):
    profil = tmp_path / 'webview'
    for sous in ('EBWebView/Default/Cache', 'EBWebView/Default/Code Cache',
                 'EBWebView/Default/Local Storage'):
        (profil / sous).mkdir(parents=True)
        (profil / sous / 'f').write_text('x')
    assert lanceur.vider_cache_si_nouvelle_version(str(profil), '1.0') == 2
    assert not (profil / 'EBWebView/Default/Cache').exists()
    assert (profil / 'EBWebView/Default/Local Storage/f').exists()        # thème gardé
    assert lanceur.vider_cache_si_nouvelle_version(str(profil), '1.0') == 0
    (profil / 'EBWebView/Default/Cache').mkdir()
    assert lanceur.vider_cache_si_nouvelle_version(str(profil), '1.1') == 1


# ═══ Raccourci (د), accueil (2), message d'erreur (هـ) ══════════════════════

def test_raccourci_cree_une_seule_fois(tmp_path):
    exe = tmp_path / 'FormationKasserine.exe'
    exe.write_bytes(b'x')
    bureau = tmp_path / 'Bureau'
    bureau.mkdir()
    appels = []
    d = str(tmp_path / 'data')
    lien = lanceur.creer_raccourci_bureau(str(exe), d, executer=appels.append, bureau=str(bureau))
    assert lien.endswith('.lnk') and len(appels) == 1 and appels[0][0] == 'powershell'
    assert str(exe) in appels[0][-1] and 'IconLocation' in appels[0][-1]
    assert lanceur.creer_raccourci_bureau(str(exe), d, executer=appels.append,
                                          bureau=str(bureau)) == ''
    assert len(appels) == 1


def test_ecran_d_accueil():
    html = lanceur.html_accueil(BASE, '1.0')
    assert lanceur.TITRE in html and 'الإصدار 1.0' in html
    assert 'data:image/jpeg;base64,' in html and 'http' not in html      # hors ligne


def test_messages_arabes():
    assert '5065' in lanceur.MESSAGES['ports'] and 'lanceur.log' in lanceur.MESSAGES['demarrage']
    assert lanceur.MESSAGES['fermer'] == 'هل تريد إغلاق البرنامج؟'


# ═══ Outil de récupération : quel que soit le port (هـ) ════════════════════

def test_recuperation_ne_confond_pas_un_autre_logiciel():
    from core import recuperation
    s = socket.socket()
    s.bind(('127.0.0.1', 0))
    s.listen(1)
    port = s.getsockname()[1]
    try:
        assert not recuperation.serveur_actif(port)      # port occupé, mais pas par nous
    finally:
        s.close()


# ═══ Démarrage réel (mode navigateur, sans écran) ═══════════════════════════

def _attendre(fonction, delai=60):
    fin = time.time() + delai
    while time.time() < fin:
        v = fonction()
        if v:
            return v
        time.sleep(0.3)
    return None


@pytest.mark.skipif(os.name == 'nt', reason='scénario sans écran (Linux)')
def test_demarrage_reel_instance_unique_et_arret(tmp_path):
    env = dict(os.environ, FK_DATA_DIR=str(tmp_path / 'data'), FK_MIROIR_DIR=str(tmp_path / 'm'),
               FK_MODE='navigateur', FK_INACTIVITE_MAX='6', BROWSER='true', PYTHONUTF8='1')
    p = subprocess.Popen([sys.executable, 'lancer_app.py'], cwd=BASE, env=env,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        inst_path = tmp_path / 'data' / 'ui' / 'instance.json'
        inst = _attendre(lambda: inst_path.exists() and json.loads(inst_path.read_text()))
        assert inst and inst['pid'] == p.pid
        port = inst['port']
        assert port in lanceur.PORTS
        html = _attendre(lambda: urllib.request.urlopen(
            f'http://127.0.0.1:{port}/login', timeout=2).read().decode('utf-8'))
        assert 'نظام إدارة التكوين' in html
        from core import recuperation
        assert recuperation.serveur_actif(port)
        # 2e lancement : détecte l'instance ouverte et s'arrête aussitôt
        p2 = subprocess.run([sys.executable, 'lancer_app.py'], cwd=BASE, env=env, timeout=60,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        assert p2.returncode == 0 and p.poll() is None
        # arrêt propre après inactivité : instance effacée, miroir écrite
        assert p.wait(timeout=60) == 0
        assert not inst_path.exists()
        assert list((tmp_path / 'm').rglob('formation_miroir.db'))
        journal = (tmp_path / 'data' / 'logs' / 'lanceur.log').read_text(encoding='utf-8')
        assert 'modes' in journal and 'Arrêt' in journal and 'Instance déjà ouverte' in journal
    finally:
        if p.poll() is None:
            p.kill()


# ═══ Icône .ico (WinForms refuse un .png) ═══════════════════════════════════

def test_icone_ico_multi_tailles():
    from PIL import Image
    chemin = os.path.join(BASE, 'static', 'images', 'icone.ico')
    im = Image.open(chemin)
    assert im.format == 'ICO'
    assert {(16, 16), (32, 32), (48, 48), (256, 256)} <= set(im.info['sizes'])
    spec = open(os.path.join(BASE, 'formation_kasserine.spec'), encoding='utf-8').read()
    assert 'icone.ico' in spec
    assert "'icone.ico'" in open(os.path.join(BASE, 'lancer_app.py'), encoding='utf-8').read()


# ═══ Point و : fenêtre jamais affichée → navigateur ═════════════════════════

class _Evenement:
    def __init__(self):
        self.fonctions = []

    def __iadd__(self, f):
        self.fonctions.append(f)
        return self


def _faux_webview(bloque):
    import types
    mod = types.ModuleType('webview')
    mod.settings = {}

    class Fenetre:
        def __init__(self):
            self.events = types.SimpleNamespace(**{n: _Evenement() for n in (
                'maximized', 'restored', 'shown', 'resized', 'moved', 'closing')})

    mod.fenetre = Fenetre()
    mod.create_window = lambda *a, **k: mod.fenetre

    def start(*a, **k):
        if bloque:
            time.sleep(3)                                # moteur bloqué
        else:
            for f in mod.fenetre.events.shown.fonctions:
                f()
    mod.start = start
    return mod


@pytest.mark.parametrize('bloque', [True, False])
def test_fenetre_non_affichee_bascule_vers_le_navigateur(tmp_path, monkeypatch, bloque):
    import lancer_app
    monkeypatch.setitem(sys.modules, 'webview', _faux_webview(bloque))
    monkeypatch.setattr(lanceur, 'DELAI_FENETRE', 1)
    appels = []
    monkeypatch.setattr(lancer_app.webbrowser, 'open', lambda u: appels.append(('ouvrir', u)))
    monkeypatch.setattr(lancer_app, '_attendre_inactivite', lambda: appels.append('attente'))
    monkeypatch.setattr(lancer_app, '_arreter', lambda s, d: appels.append('arret'))
    d = str(tmp_path)
    os.makedirs(os.path.join(d, 'logs'))
    lanceur.ecrire_instance(d, 5099, 'fenetre')
    vue = lancer_app._mode_fenetre('http://127.0.0.1:5099/', 5099, d)
    time.sleep(0.5)
    if bloque:
        assert vue is False
        assert appels == [('ouvrir', 'http://127.0.0.1:5099/'), 'attente', 'arret']
        assert lanceur.lire_json(os.path.join(d, 'ui', 'instance.json')).get('mode') == 'navigateur'
        assert os.path.getsize(os.path.join(d, 'logs', 'pile_fenetre.txt')) > 0
    else:
        assert vue is True and appels == []


# ═══ Simulation 2021 → 2028 : adresse de مراسلة حرّة sur un برنامج ══════════

def test_pdf_libre_d_un_programme_ne_plante_plus(client, programme):
    lid = programme['lettre_id']
    r = client.get(f'/lettre/libre/{lid}/generer')
    assert r.status_code == 302 and r.headers['Location'].endswith(f'/lettres/{lid}')
    assert client.get('/lettre/libre/999999/generer').status_code == 404


def test_fenetres_secondaires_seulement_sous_windows():
    src = open(os.path.join(BASE, 'lancer_app.py'), encoding='utf-8').read()
    assert "on_new_window_request = _nouvelle_fenetre" in src
    assert "if os.name == 'nt':\n        _fenetres_secondaires(webview, url)" in src


def test_pas_de_proposition_de_traduction():
    import glob
    for f in glob.glob(os.path.join(BASE, 'templates', '**', '*.html'), recursive=True):
        src = open(f, encoding='utf-8').read()
        if '<html' in src:
            assert '<html lang="ar" dir="rtl" translate="no">' in src, f
    assert '--disable-features=Translate' in open(os.path.join(BASE, 'lancer_app.py'),
                                                   encoding='utf-8').read()
