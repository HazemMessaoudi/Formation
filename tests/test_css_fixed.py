# -*- coding: utf-8 -*-
"""Phase 2 (v1.4) : garde-fous contre la régression position:fixed de la v1.3.

Un transform (même « translateY(0) » figé par animation-fill-mode) sur
.main-content en faisait le bloc conteneur des listes d'autocomplétion, qui
s'affichaient décalées. Deux protections indépendantes sont vérifiées ici."""
import os
import re

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _lire(*chemin):
    return open(os.path.join(BASE, *chemin), encoding='utf-8').read()


def test_animation_page_sans_transform():
    css = _lire('static', 'css', 'app.css')
    m = re.search(r'@keyframes\s+pageIn\s*\{(.*?)\}\s*\}', css, re.S)
    assert m, 'keyframes pageIn introuvable'
    assert 'transform' not in m.group(1)


def test_main_content_sans_transform_au_repos():
    css = _lire('static', 'css', 'app.css')
    for bloc in re.findall(r'\.main-content\s*\{([^}]*)\}', css):
        assert not re.search(r'(^|;|\s)(transform|perspective|filter)\s*:', bloc), bloc


def test_listes_autocompletion_en_portail():
    """Les listes sont rattachées à <body> : aucun ancêtre ne peut les décaler."""
    html = _lire('templates', 'nouvelle_lettre.html') + __import__('tests.conftest', fromlist=['js_programme']).js_programme()
    assert 'document.body.appendChild(inp._acList)' in html
    # Au moment du choix, le champ est retrouvé via le lien liste → champ, pas
    # en cherchant la liste « à l'intérieur » de la ligne : elle n'y est plus.
    corps = html.split('function _acChoisir(', 1)[1].split('\nfunction ', 1)[0]
    assert "wrap.querySelector('.ac-list')" not in corps
    assert '_acChamp(el)' in corps


def test_autocompletion_unifiee():
    """Phase 3 : un seul moteur de liste pour formateur ET participant."""
    html = _lire('templates', 'nouvelle_lettre.html') + __import__('tests.conftest', fromlist=['js_programme']).js_programme()
    assert html.count('MKOWIN_INIT.filter(') <= 1          # un seul filtrage
    assert 'function pickAc(' not in html and 'function pickAcPart(' not in html
    assert 'function showAcList(inp)     { _acOuvrir(inp, _choixFormateur); }' in html
    assert 'function showAcListPart(inp) { _acOuvrir(inp, _choixParticipant); }' in html
    # Les valeurs ne transitent plus par des chaînes JS dans onmousedown
    assert 'pickAc(event' not in html and 'pickAcPart(event' not in html
    assert '_acEsc(_acNomComplet(m))' in html
