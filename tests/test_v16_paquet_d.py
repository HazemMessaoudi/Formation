# -*- coding: utf-8 -*-
"""v1.6 — الحزمة د : إزالة الشريط المتحرّك تحت عارض الإحصائيات فقط.

Le défilement automatique (3 s), les flèches, le bouton إيقاف et les نقاط
restent en place ; seul le شريط التقدّم disparaît."""
import re

import pytest


@pytest.fixture()
def html(client):
    r = client.get('/statistiques')
    assert r.status_code == 200
    return r.get_data(as_text=True)


@pytest.mark.parametrize('reste', [
    'viz-progress', 'vizBarre', 'elBarre', 'relancerBarre', 'vizAvance',
])
def test_barre_supprimee(html, reste):
    assert reste not in html


@pytest.mark.parametrize('garde', [
    'id="vizPoints"', 'id="vizPrev"', 'id="vizNext"', 'id="vizPause"',
    'function programmer()', 'function aller(n, manuel)',
])
def test_carrousel_conserve(html, garde):
    assert garde in html


def test_duree_trois_secondes(html):
    assert re.search(r'var DUREE\s*=\s*3000;', html)


def test_defilement_auto_toujours_programme(html):
    # le minuteur relance aller(idx + 1) toutes les DUREE ms
    assert re.search(r'setTimeout\(function \(\) \{ aller\(idx \+ 1\); programmer\(\); \}, DUREE\)', html)
    # et l'initialisation démarre le défilement
    assert re.search(r'peindre\(\);\s*programmer\(\);', html)


def test_pause_survol_tableau_suspendent(html):
    assert 'if (enPause || survol || tableOuverte) return;' in html
    assert html.count('clearTimeout(minuteur)') >= 4


def test_points_centres(html):
    m = re.search(r'\.viz-pied\s*\{([^}]*)\}', html)
    assert m and 'justify-content:center' in m.group(1).replace(' ', '')
