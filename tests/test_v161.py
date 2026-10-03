# -*- coding: utf-8 -*-
"""v1.6.1 — تصحيحات بعد الإصدار 1.6 (données fictives uniquement).

 1. « بالقصرين » centrée dans la ترويسة des trois pièces Word.
 2. البطاقة البيداغوجية : tableau extensible, rendu habituel inchangé.
 3. التوقيت : saisie au clavier (normalisée) ou choix dans la liste.
 4. خانة Page toujours remplie dans les مراسلات.
 5. تاريخ المقرّر strictement postérieur à la دورة.
 6. الإحصائيات : الجنس/الفئة toujours affichés (test dans test_v16_paquet_c).
 7. التقرير السنوي : المشاركون حسب الجنس.
 8. Police de départ : القاهرة.
 +  تنبيه « تاريخ الدورة في الماضي » et impression A4 des الإحصائيات.
"""
import io
import os
import re

import pytest
from reportlab.pdfgen import canvas as rl_canvas

from core import pdf_generator as pg

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JETON = {'X-CSRF-Token': 'jeton-de-test'}


def _lire(chemin):
    with open(os.path.join(BASE, chemin), encoding='utf-8') as f:
        return f.read()


# ─── Canevas enregistreur : méthode, position et texte de chaque tracé ──────

class _Rec(rl_canvas.Canvas):
    derniers = []

    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self.textes, self.rects, self.page = [], [], 1
        self.tailles = {}           # texte → tailles de police utilisées
        _Rec.derniers.append(self)

    def _taille(self, t):
        self.tailles.setdefault(t, []).append(round(self._fontsize, 2))

    def drawString(self, x, y, t, *a, **k):
        self._taille(t)
        self.textes.append(('g', x, y, t, self.page))
        return super().drawString(x, y, t, *a, **k)

    def drawCentredString(self, x, y, t, *a, **k):
        self._taille(t)
        self.textes.append(('c', x, y, t, self.page))
        return super().drawCentredString(x, y, t, *a, **k)

    def drawRightString(self, x, y, t, *a, **k):
        self._taille(t)
        self.textes.append(('d', x, y, t, self.page))
        return super().drawRightString(x, y, t, *a, **k)

    def rect(self, x, y, w, h, *a, **k):
        self.rects.append(tuple(round(v, 2) for v in (x, y, w, h)))
        return super().rect(x, y, w, h, *a, **k)

    def showPage(self):
        if not getattr(self, '_final', False):
            self.page += 1
        return super().showPage()

    def save(self):
        self._final = True
        return super().save()


@pytest.fixture()
def rec(monkeypatch):
    _Rec.derniers = []
    monkeypatch.setattr(pg.canvas, 'Canvas', _Rec)
    return _Rec


# ─── 1. « بالقصرين » au centre du bloc ─────────────────────────────────────

def test_bloc_institution_ligne_courte_centree(rec):
    pg._register_fonts(BASE)
    c = _Rec(io.BytesIO(), pagesize=(pg.A4_W, pg.A4_H))
    from core import identite
    pg._bloc_institution(c, identite.ENTETE_NATIONAL, ['مركز التكوين الديواني بالقصرين'],
                         500.0, 800.0, 14.0)
    centrees = {t: x for m, x, y, t, p in c.textes if m == 'c'}
    assert pg._arh('بالقصرين') in centrees, 'la ligne courte doit être centrée'
    # même axe que « وزارة المالية » (étirée par tatwīl, d'où un texte variable)
    x_ministere = [x for t, x in centrees.items() if t != pg._arh('بالقصرين')]
    assert len(x_ministere) == 1
    assert abs(centrees[pg._arh('بالقصرين')] - x_ministere[0]) < 0.01
    # plus jamais collée à droite
    assert not [t for m, x, y, t, p in c.textes if m == 'd' and t == pg._arh('بالقصرين')]


PARTS = [{'nom_prenom': f'مشارك تجريبي {i}', 'grade': 'ملازم', 'identifiant_unique': str(90000000 + i),
          'lieu_travail': 'مكتب وهمي'} for i in range(3)]
COMMUN = {'titre': 'إعداد الطلبات', 'date_formation': '2026-06-24', 'ville_centre': 'القصرين',
          'nom_centre': 'مركز التكوين الديواني بالقصرين'}


@pytest.mark.parametrize('gen, donnees', [
    ('generer_pdf_participants', {**COMMUN, 'participants': PARTS}),
    ('generer_pdf_bataqa_hodour', {**COMMUN, 'participants': PARTS}),
    ('generer_pdf_programme', {'theme': 'إعداد الطلبات', 'date_formation': '2026-06-24',
                               'moment': '', 'ville_centre': 'القصرين',
                               'nom_centre': 'مركز التكوين الديواني بالقصرين',
                               'rows': [{'type': 'row', 'time': 'من 08:30 إلى 09:00',
                                         'activity': 'استقبال', 'participants': 'مكوّن وهمي'}]}),
])
def test_trois_pieces_ville_centree(rec, gen, donnees):
    os.remove(getattr(pg, gen)(donnees, BASE))
    c = rec.derniers[-1]
    methodes = [m for m, x, y, t, p in c.textes if t == pg._arh('بالقصرين')]
    assert methodes == ['c']


# ─── 2. البطاقة البيداغوجية extensible ───────────────────────────────────────

BATAQA_COURTE = {
    'theme': 'تحرير المحاضر', 'mustahdafun': 'أعوان الديوانة', 'nb_participants': 14,
    'services': ['الإدارة الجهوية للديوانة بالقصرين', 'فصيل وهمي'], 'type_formation': 'تكوين مستمر',
    'mahawer': 'محور وهمي أوّل\nمحور وهمي ثان', 'objectifs': 'هدف تجريبي', 'lieu_formation': 'قاعة 1',
    'date_formation': '2026-12-02', 'methodes': 'عرض\nنقاش', 'moyens': 'حاسوب\nعارض',
    'preparation': 'قاعة', 'equipements': 'عارض', 'nom_centre': 'مركز التكوين الديواني بالقصرين'}

# Cadres relevés sur la v1.6 avec le même contenu : le rendu habituel ne bouge pas.
RECTS_V16 = [
    (47.2, 604.2, 66.5, 27.51), (113.7, 604.2, 134.08, 27.51), (247.78, 604.2, 53.63, 27.51),
    (301.41, 604.2, 163.04, 27.51), (464.46, 604.2, 82.59, 27.51), (47.2, 536.48, 66.5, 67.72),
    (113.7, 536.48, 134.08, 67.72), (247.78, 536.48, 53.63, 67.72), (301.41, 536.48, 163.04, 67.72),
    (464.46, 536.48, 82.59, 67.72), (300.34, 485.69, 246.71, 33.86), (47.2, 485.69, 253.15, 33.86),
    (300.34, 415.85, 246.71, 69.84), (47.2, 415.85, 253.15, 69.84), (261.73, 349.19, 285.32, 29.63),
    (47.2, 349.19, 214.53, 29.63), (261.73, 286.76, 285.32, 62.43), (47.2, 286.76, 214.53, 62.43),
    (302.49, 221.15, 244.56, 27.51), (47.2, 221.15, 255.29, 27.51), (302.49, 153.43, 244.56, 67.72),
    (47.2, 153.43, 255.29, 67.72), (297.12, 86.77, 249.93, 27.51), (47.2, 86.77, 249.93, 27.51),
    (297.12, 60.31, 249.93, 26.45), (47.2, 60.31, 249.93, 26.45)]


def test_bataqa_contenu_habituel_inchange(rec):
    os.remove(pg.generer_pdf_bataqa(BATAQA_COURTE, BASE))
    c = rec.derniers[-1]
    assert c.rects == RECTS_V16
    assert c.page == 1


def test_bataqa_longue_s_allonge_sans_rien_perdre(rec):
    items = [f'المحور الوهمي رقم {i}: دراسة الإجراءات الديوانية المتعلّقة بالتصريح' for i in range(1, 13)]
    d = dict(BATAQA_COURTE, mahawer='\n'.join(items),
             services=[f'مصلحة وهمية رقم {i}' for i in range(1, 8)])
    chemin = pg.generer_pdf_bataqa(d, BASE)
    assert pg.compter_pages_pdf(chemin) == 2
    os.remove(chemin)
    c = rec.derniers[-1]
    textes = [t for m, x, y, t, p in c.textes]
    for i in range(1, 8):
        assert pg.ar(f'مصلحة وهمية رقم {i}') in textes
    # rien n'est tracé sous le bas utile de la page
    assert min(y for m, x, y, t, p in c.textes) > 20
    # la section 1 s'est allongée : sa ligne de données dépasse la hauteur du modèle
    assert max(h for x, y, w, h in c.rects) > 67.72


def test_bataqa_plus_haute_qu_une_page_continue_sans_perte(rec):
    n = 90
    d = dict(BATAQA_COURTE, mahawer='\n'.join(f'محور {i}' for i in range(1, n + 1)))
    chemin = pg.generer_pdf_bataqa(d, BASE)
    pages = pg.compter_pages_pdf(chemin)
    os.remove(chemin)
    c = rec.derniers[-1]
    textes = [t for m, x, y, t, p in c.textes]
    for i in range(1, n + 1):
        assert textes.count(pg.ar(f'محور {i}')) == 1, i
    assert pages >= 3
    assert min(y for m, x, y, t, p in c.textes) > 20
    # l'en-tête « محاور الدورة » est rappelé sur chaque page de suite
    assert textes.count(pg.ar('محاور الدورة')) >= 2
    # taille normale conservée : la liste est coupée, pas écrasée
    assert all(c.tailles[pg.ar(f'محور {i}')] == [12.0] for i in range(1, n + 1))


def test_bataqa_legerement_plus_longue_reduite_sans_saut(rec):
    """Un léger débordement de la dernière section : réduite (≥ 10 pt) plutôt
    qu'envoyée seule sur une page 2 — ou reportée entière ; jamais coupée."""
    d = dict(BATAQA_COURTE, preparation='\n'.join(f'إعداد {i}' for i in range(1, 5)))
    chemin = pg.generer_pdf_bataqa(d, BASE)
    os.remove(chemin)
    c = rec.derniers[-1]
    textes = [t for m, x, y, t, p in c.textes]
    for i in range(1, 5):
        assert textes.count(pg.ar(f'إعداد {i}')) == 1
        assert c.tailles[pg.ar(f'إعداد {i}')][0] >= 10.0
    assert min(y for m, x, y, t, p in c.textes) > 20


# ─── 3. التوقيت au clavier ───────────────────────────────────────────────────

def _prealables(db, programme):
    db.save_participants(programme['lettre_id'], programme['formation_id'],
                         [{'nom_prenom': 'مشارك وهمي', 'grade': 'ملازم',
                           'identifiant_unique': '123', 'lieu_travail': 'القصرين'}])
    db.save_bataqa_data(programme['formation_id'], {'mahawer': 'المحاور'})


def test_heure_tapee_normalisee_par_le_serveur(client, db, programme):
    _prealables(db, programme)
    lid, fid = programme['lettre_id'], programme['formation_id']
    r = client.post(f'/lettre/{lid}/formations/{fid}/programme/data', headers=JETON, json={'rows': [
        {'type': 'row', 'time_debut': '8:30', 'time_fin': '9:45',
         'activity': 'استقبال', 'participants': 'مكوّن وهمي'}]})
    assert r.status_code == 200, r.get_json()
    ligne = db.get_programme_data(lid, fid)['rows'][0]
    assert (ligne['time_debut'], ligne['time_fin']) == ('08:30', '09:45')
    assert ligne['time'] == 'من 08:30 إلى 09:45'


@pytest.mark.parametrize('mauvaise', ['25:00', '8h7x', '08:75', 'abc'])
def test_heure_illisible_refusee(client, db, programme, mauvaise):
    _prealables(db, programme)
    lid, fid = programme['lettre_id'], programme['formation_id']
    r = client.post(f'/lettre/{lid}/formations/{fid}/programme/data', headers=JETON, json={'rows': [
        {'type': 'row', 'time_debut': '08:30', 'time_fin': mauvaise,
         'activity': 'استقبال', 'participants': 'مكوّن وهمي'}]})
    assert r.status_code == 400 and 'صيغة التوقيت' in r.get_json()['erreur']


def test_champ_heure_saisissable_avec_liste():
    from tests.conftest import js_programme
    html = _lire('templates/nouvelle_lettre.html') + js_programme()
    assert 'type="time" class="prow-time' not in html
    assert html.count('list="dl_heures"') == 2
    assert 'function _normaliserHeure' in html and '_prowOnTimeCommit' in html


# ─── 4. خانة Page toujours remplie ───────────────────────────────────────────

def test_page_remplie_dans_la_lettre_du_programme(client, db, programme, rec):
    db.verrouiller_lettre(programme['lettre_id'], 'interne')
    r = client.get(f"/lettre/{programme['lettre_id']}/generer")
    assert r.status_code == 200 and r.data[:4] == b'%PDF'
    c = rec.derniers[-1]
    pages = [t for m, x, y, t, p in c.textes if re.fullmatch(r'\d+/\d+', t)]
    assert pages and all(t == f'{c.page}/{c.page}' for t in pages)
    assert len(pages) == c.page          # sur chaque page


def test_page_de_la_memo_jamais_vide():
    src = _lire('routes/pdf.py')
    # v1.7 : comptage déplacé dans core/dossier_dorra.py (source commune PDF/Word).
    assert "max(_pages(generer_pdf_memo, donnees), 1) + total" in _lire('core/dossier_dorra.py')
    for gen in ('generer_pdf_libre', 'generer_pdf', 'generer_pdf_directeur_regional'):
        assert f'_avec_pagination({gen}, lettre_data)' in src


# ─── 5. تاريخ المقرّر après la دورة ──────────────────────────────────────────

def _dorra_sans_muqarrar(db):
    from tests.test_mustahaqqat import _dorra_enregistree, _p
    return _dorra_enregistree(db, [_p('خالد', 'العريف', '1')], muqarrar=False)


@pytest.mark.parametrize('jour, accepte', [('02-09', False), ('02-10', False), ('02-11', True)])
def test_date_du_muqarrar(client, db, jour, accepte):
    _lid, fid = _dorra_sans_muqarrar(db)          # دورة du {annee}-02-10
    a = db.annee_registre()
    r = client.post(f'/mustahaqqat/dorra/{fid}/muqarrar',
                    data={'_csrf': 'jeton-de-test', 'muqarrar_numero': '2026/9',
                          'muqarrar_date': f'{a}-{jour}'})
    if accepte:
        assert r.status_code == 302
        assert db.get_muqarrar_dorra(fid) == ('2026/9', f'{a}-{jour}')
    else:
        assert r.status_code == 200
        assert 'يجب أن يكون بعد تاريخ الدورة' in r.get_data(as_text=True)
        assert db.get_muqarrar_dorra(fid) == ('', '')


def test_formulaire_muqarrar_borne_la_date(client, db):
    _lid, fid = _dorra_sans_muqarrar(db)
    html = client.get(f'/mustahaqqat/dorra/{fid}/muqarrar').get_data(as_text=True)
    assert f'min="{db.annee_registre()}-02-11"' in html


# ─── 7. التقرير السنوي : الجنس ───────────────────────────────────────────────

def test_rapport_annuel_par_sexe(client, db, programme):
    from core.validation import SEXES
    h, f = SEXES
    db.save_participants(programme['lettre_id'], programme['formation_id'], [
        {'nom_prenom': 'مشارك 1', 'grade': 'ملازم', 'identifiant_unique': '1', 'lieu_travail': 'x', 'sexe': h},
        {'nom_prenom': 'مشارك 2', 'grade': 'ملازم', 'identifiant_unique': '2', 'lieu_travail': 'x', 'sexe': h},
        {'nom_prenom': 'مشاركة 3', 'grade': 'ملازم', 'identifiant_unique': '3', 'lieu_travail': 'x', 'sexe': f},
        {'nom_prenom': 'مشارك 4', 'grade': 'ملازم', 'identifiant_unique': '4', 'lieu_travail': 'x'},
    ])
    r = db.rapport_annuel(2026)
    par = {x['sexe']: (x['participations'], x['uniques']) for x in r['par_sexe']}
    assert par == {h: (2, 2), f: (1, 1), 'غير محدّد': (1, 1)}
    assert [x['sexe'] for x in r['par_sexe']] == [h, f, 'غير محدّد']
    assert sum(x['part'] for x in r['par_sexe']) == pytest.approx(100, abs=0.2)
    html = client.get('/statistiques/rapport-annuel?annee=2026').get_data(as_text=True)
    assert 'المشاركون حسب الجنس' in html and 'id="rapSexe"' in html


def test_rapport_annuel_sans_participant(db):
    from core.validation import SEXES
    r = db.rapport_annuel(2026)
    assert [(x['sexe'], x['participations']) for x in r['par_sexe']] == [(s, 0) for s in SEXES]


# ─── 8. القاهرة par défaut ───────────────────────────────────────────────────

def test_police_par_defaut_cairo():
    css = _lire('static/css/app.css')
    assert 'body:not([data-police="amiri"]) { font-size: 15px; }' in css
    assert "body:not([data-police=\"amiri\"]) button { font-family: 'Cairo'" in css
    js = _lire('static/js/ui.js')
    assert "lire('app_police_choix') === 'amiri' ? 'amiri' : 'cairo'" in js
    base = _lire('templates/base.html')
    assert 'APP_PREFS.setPolice(APP_PREFS.police(), false);' in base
    assert base.index('data-police-choix="cairo"') < base.index('data-police-choix="amiri"')
    assert "font-family:'Amiri',sans-serif" not in _lire('templates/login.html')


# ─── Propositions retenues ───────────────────────────────────────────────────

def test_avis_date_passee_non_bloquant(client, db, programme):
    from tests.conftest import js_programme
    html = client.get(f"/lettre/nouvelle?modifier={programme['lettre_id']}").get_data(as_text=True) + js_programme()
    assert 'id="dorraPasseeAvis"' in html and 'function _datePassee' in html
    assert 'مضى تاريخها' in html


def test_statistiques_imprimables_a4(client, db):
    html = client.get('/statistiques').get_data(as_text=True)
    assert 'id="btnImprimerStats"' in html and 'window.imprimerStats' in html
    assert '@page { size: A4 portrait; margin: 12mm; }' in html
    assert html.count('class="print-only pan-titre"') == 5


def test_version():
    from core import identite
    # v1.7 : le numéro de version avance (1.6.1 → 1.7)
    # 1.0 : numérotation repartie de 1.0 pour la mise en service (ex-3.2 + fenêtre)
    assert identite.VERSION_APP == '1.0' and identite.VERSION_LABEL == 'الإصدار 1.0'
