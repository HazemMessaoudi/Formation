# -*- coding: utf-8 -*-
"""v1.7 — Paquet F : découpage des gros fichiers SANS changement de comportement."""

import inspect
import os
import re
import subprocess

import pytest

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JS = ['01_etape1_et_2.js', '02_participants.js', '03_bataqa_programme.js',
      '04_progression_memo.js', '05_autocompletion.js', '06_autosauvegarde_init.js']


# ═══ JavaScript de la page إعداد برنامج التكوين ═════════════════════════════

def test_gabarit_allege_et_scripts_dans_l_ordre():
    tpl = open(os.path.join(BASE, 'templates', 'nouvelle_lettre.html'), encoding='utf-8').read()
    assert tpl.count('\n') < 500                    # 3003 lignes auparavant
    positions = [tpl.index(f"js/programme/{n}") for n in JS]
    assert positions == sorted(positions)           # 01 → 06
    # le seul script en ligne restant ne porte que les données du serveur
    en_ligne = re.findall(r'<script>(.*?)</script>', tpl, re.S)
    assert len(en_ligne) == 1 and 'function ' not in en_ligne[0]
    assert 'const PAGE = {' in en_ligne[0]


def test_aucun_jinja_dans_les_fichiers_js():
    for n in JS:
        s = open(os.path.join(BASE, 'static', 'js', 'programme', n), encoding='utf-8').read()
        assert '{{' not in s and '{%' not in s, n


def test_js_syntaxe_valide():
    node = subprocess.run(['node', '--version'], capture_output=True)
    if node.returncode != 0:
        pytest.skip('node absent')
    for n in JS:
        r = subprocess.run(['node', '--check', os.path.join(BASE, 'static', 'js', 'programme', n)],
                           capture_output=True, text=True)
        assert r.returncode == 0, (n, r.stderr)


def test_pas_de_fonction_en_double():
    noms = []
    for n in JS:
        s = open(os.path.join(BASE, 'static', 'js', 'programme', n), encoding='utf-8').read()
        noms += re.findall(r'^(?:async )?function (\w+)', s, re.M)
    assert len(noms) == len(set(noms))


@pytest.mark.parametrize('etat, url', [('nouveau', '/lettre/nouvelle'),
                                       ('brouillon', '/lettre/nouvelle?modifier={lid}')])
def test_etat_de_page_transmis(client, db, programme, etat, url):
    html = client.get(url.format(lid=programme['lettre_id'])).get_data(as_text=True)
    assert f'etat: "{etat}"' in html


def test_etat_verrouille_et_reference(client, db, programme):
    ref, _n = db.verrouiller_lettre(programme['lettre_id'], 'interne')
    html = client.get(f"/lettre/nouvelle?modifier={programme['lettre_id']}").get_data(as_text=True)
    assert 'etat: "verrouille"' in html and f'refVerrouille: "{ref}"' in html


def test_scripts_servis(client):
    for n in JS:
        r = client.get(f'/static/js/programme/{n}')
        assert r.status_code == 200 and len(r.data) > 1000
        r.close()


# ═══ Générateurs PDF par document ═══════════════════════════════════════════

def test_facade_pdf_generator():
    import core.pdf_generator as pg
    from core.pdf import mourasalat, pieces_word, bataqa, memo
    assert pg.generer_pdf is mourasalat.generer_pdf
    assert pg.generer_pdf_libre is mourasalat.generer_pdf_libre
    assert pg.generer_pdf_participants is pieces_word.generer_pdf_participants
    assert pg.generer_pdf_programme is pieces_word.generer_pdf_programme
    assert pg.generer_pdf_bataqa is bataqa.generer_pdf_bataqa
    assert pg.generer_pdf_memo is memo.generer_pdf_memo
    assert pg.canvas.__name__ == 'reportlab.pdfgen.canvas'
    src = open(os.path.join(BASE, 'core', 'pdf_generator.py'), encoding='utf-8').read()
    assert src.count('\n') < 1100 and 'def generer_' not in src


# ═══ Schéma : étapes numérotées ═════════════════════════════════════════════

def test_etapes_numerotees_dans_l_ordre():
    from core.db import schema
    noms = [e.__name__ for e in schema.ETAPES]
    assert noms == sorted(noms) and len(noms) == 17   # V3.1 : étape 17 (إشعارات)
    assert all(re.match(r'_etape_\d{2}_\w+', n) for n in noms)
    assert inspect.getsource(schema.init_db).count('\n') < 30


def test_version_de_schema(db):
    from core.db import schema
    assert db.version_schema() == schema.SCHEMA_VERSION == 21   # V3.1


def test_init_db_idempotent(db):
    conn = db.get_connection()
    try:
        avant = [tuple(r) for r in conn.execute(
            "SELECT type, name, sql FROM sqlite_master ORDER BY name")]
    finally:
        conn.close()
    db.init_db()
    db.init_db()
    conn = db.get_connection()
    try:
        apres = [tuple(r) for r in conn.execute(
            "SELECT type, name, sql FROM sqlite_master ORDER BY name")]
    finally:
        conn.close()
    assert avant == apres
