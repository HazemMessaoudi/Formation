# -*- coding: utf-8 -*-
"""v1.6 — الحزمة هـ : قائمة المشاركين · بطاقة حضور · برنامج الدورة conformes
aux documents Word officiels (polices, gras, tailles, traits, couleurs).

Les pièces sont composées sur un canevas « enregistreur » : chaque texte est
noté avec sa police et sa taille, chaque épaisseur de trait et chaque couleur
de fond. On vérifie ainsi le STYLE, pas seulement l'existence du fichier.
Données fictives uniquement."""
import hashlib
import inspect
import os
import re

import pytest
from reportlab.pdfgen import canvas as rl_canvas

from core import pdf_generator as pg

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JETON = {'X-CSRF-Token': 'jeton-de-test'}


# ─── Canevas enregistreur ────────────────────────────────────────────────────

class _Enregistreur(rl_canvas.Canvas):
    derniers = []

    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self.textes, self.traits, self.fonds, self.page = [], set(), set(), 1
        _Enregistreur.derniers.append(self)

    def _noter(self, t):
        self.textes.append((self._fontname, round(self._fontsize, 2), t, self.page))

    def drawString(self, x, y, t, *a, **k):
        self._noter(t)
        return super().drawString(x, y, t, *a, **k)

    def drawCentredString(self, x, y, t, *a, **k):
        self._noter(t)
        return super().drawCentredString(x, y, t, *a, **k)

    def drawRightString(self, x, y, t, *a, **k):
        self._noter(t)
        return super().drawRightString(x, y, t, *a, **k)

    def setLineWidth(self, w):
        self.traits.add(round(w, 3))
        return super().setLineWidth(w)

    def setFillColor(self, col, *a, **k):
        if hasattr(col, 'hexval'):
            self.fonds.add(col.hexval().lower())
        return super().setFillColor(col, *a, **k)

    def showPage(self):
        if not getattr(self, '_final', False):   # save() ferme la dernière page
            self.page += 1
        return super().showPage()

    def save(self):
        self._final = True
        return super().save()


@pytest.fixture()
def enreg(monkeypatch):
    _Enregistreur.derniers = []
    monkeypatch.setattr(pg.canvas, 'Canvas', _Enregistreur)
    return _Enregistreur


def _parts(n, lieux=None):
    grades = ['عقيد', 'مقدم', 'رائد', 'نقيب', 'ملازم أول', 'ملازم']
    out = []
    for i in range(n):
        out.append({'nom_prenom': f'مشارك تجريبي {i + 1}', 'grade': grades[i % len(grades)],
                    'identifiant_unique': str(90000000 + i),
                    'lieu_travail': (lieux[i] if lieux else f'مكتب وهمي {i % 3}')})
    return out


COMMUN = {'titre': 'إعداد الطلبات', 'date_formation': '2026-06-24',
          'ville_centre': 'القصرين', 'nom_centre': 'مركز التكوين الديواني بالقصرين'}


def _programme(n_lignes=4, **extra):
    rows = [{'type': 'row', 'time': f'من {8 + i:02d}:00 إلى {9 + i:02d}:00',
             'activity': f'نشاط تجريبي {i + 1}', 'participants': 'المقدم مكوّن وهمي'}
            for i in range(n_lignes)]
    return {'theme': 'إعداد الطلبات', 'date_formation': '2026-06-24', 'moment': '',
            'ville_centre': 'القصرين', 'nom_centre': 'مركز التكوين الديواني بالقصرين',
            'rows': rows, **extra}


def _textes(c, texte):
    v = pg._arh(texte)
    return [(f, s, p) for f, s, t, p in c.textes if t == v]


# ─── 1. Format : A4, comme les documents Word ────────────────────────────────

@pytest.mark.parametrize('gen, donnees', [
    ('generer_pdf_participants', {**COMMUN, 'participants': _parts(3)}),
    ('generer_pdf_bataqa_hodour', {**COMMUN, 'participants': _parts(3)}),
    ('generer_pdf_programme', _programme()),
])
def test_page_a4(gen, donnees):
    chemin = getattr(pg, gen)(donnees, BASE)
    data = open(chemin, 'rb').read()
    os.remove(chemin)
    assert data[:4] == b'%PDF'
    m = re.search(rb'/MediaBox\s*\[\s*0 0 ([\d.]+) ([\d.]+)', data)
    assert m and abs(float(m.group(1)) - 595.28) < 0.1 and abs(float(m.group(2)) - 841.89) < 0.1


# ─── 2. Polices, gras et tailles relevés sur les modèles ─────────────────────

def test_participants_styles(enreg):
    pg.generer_pdf_participants({**COMMUN, 'participants': _parts(3)}, BASE)
    c = enreg.derniers[-1]
    assert _textes(c, 'قائمة المشاركين') == [(pg.F_ARB, 18.0, 1)]
    for t in ('الدورة تكوينيّة حول " إعداد الطلبات "',
              'تحت إشراف مركز التكوين الديواني بالقصرين', 'القصرين في 24 جوان 2026'):
        assert _textes(c, t) == [(pg.F_ARB, 16.0, 1)], t
    assert _textes(c, 'فندق الجديد في :') == [(pg.F_ARB, 11.0, 1)]
    for t in ('مكان العمل', 'المعرّف الوحيد', 'الرّتبة', 'الإسم واللقب', 'ع/ر'):
        assert _textes(c, t) == [(pg.F_ARB, 12.0, 1)], t
    # corps : Arial NORMAL 14 ; numéro d'ordre : gras 12
    assert _textes(c, 'مشارك تجريبي 1') == [(pg.F_AR, 14.0, 1)]
    assert _textes(c, '90000000') == [(pg.F_AR, 14.0, 1)]
    assert [(f, s) for f, s, t, p in c.textes if t in ('01', '02', '03')] == [(pg.F_ARB, 12.0)] * 3
    # bloc institution : gras 12 (la ligne la plus longue fixe la largeur du bloc
    # et s'écrit telle quelle ; les autres sont étirées)
    assert _textes(c, 'إدارة التكوين الجهوي والمختص') == [(pg.F_ARB, 12.0, 1)]
    etirees = [(f, s) for f, s, t, p in c.textes if 'ـ' in t]
    assert etirees and set(etirees) == {(pg.F_ARB, 12.0)}


def test_hodour_styles(enreg):
    pg.generer_pdf_bataqa_hodour({**COMMUN, 'participants': _parts(2),
                                  'titre_responsable': 'النقيب', 'nom_responsable': 'مسؤول وهمي',
                                  'grade_formateur': 'المقدم', 'nom_formateur': 'مكوّن وهمي'}, BASE)
    c = enreg.derniers[-1]
    assert _textes(c, 'بطاقة حضور') == [(pg.F_ARB, 20.0, 1)]
    assert _textes(c, 'القصرين في :') == [(pg.F_ARB, 11.0, 1)]      # libellé du modèle
    for t in ('الإمضاء', 'الرّتبة', 'الإسم واللقب', 'ع/ر'):
        assert _textes(c, t) == [(pg.F_ARB, 12.0, 1)], t
    # pied : tout en gras 12
    for t in ('المكوّن', 'رئيس مركز التكوين الديواني بالقصرين', 'النقيب مسؤول وهمي',
              'المقدم مكوّن وهمي'):
        assert _textes(c, t) == [(pg.F_ARB, 12.0, 1)], t


def test_programme_styles(enreg):
    pg.generer_pdf_programme(_programme(2), BASE)
    c = enreg.derniers[-1]
    assert _textes(c, 'برنامج الدّورة التّكوينيّة') == [(pg.F_ARB, 20.0, 1)]
    assert _textes(c, 'يوم 24 جوان 2026') == [(pg.F_ARB, 16.0, 1)]
    assert _textes(c, 'فندق الجديد في:') == [(pg.F_ARB, 11.0, 1)]
    for t in ('المتدخّلون', 'بيان النشّاط', 'التّوقيت'):
        assert _textes(c, t) == [(pg.F_ARB, 12.0, 1)], t
    # ligne de date du tableau : ville + jour de semaine, gras 16
    assert _textes(c, 'القصرين يوم الأربعاء الموافق لـ 24 جوان 2026') == [(pg.F_ARB, 16.0, 1)]
    # corps : Arial GRAS dans les trois colonnes — v1.7.1 : 9 → 11 pt (plus lisible)
    for t in ('نشاط تجريبي 1', 'من 08:00 إلى 09:00', 'المقدم مكوّن وهمي'):
        assert all(x[:2] == (pg.F_ARB, 11.0) for x in _textes(c, t)) and _textes(c, t), t


def test_aucun_texte_en_police_normale_hors_corps_des_listes(enreg):
    """Sur les modèles, seul le corps des listes est en Arial normal."""
    pg.generer_pdf_programme(_programme(3), BASE)
    assert all(f == pg.F_ARB for f, s, t, p in enreg.derniers[-1].textes)
    pg.generer_pdf_bataqa_hodour({**COMMUN, 'participants': _parts(2)}, BASE)
    normaux = {s for f, s, t, p in enreg.derniers[-1].textes if f == pg.F_AR}
    assert normaux == {14.0}


# ─── 3. Traits et couleurs ───────────────────────────────────────────────────

@pytest.mark.parametrize('gen, donnees, couleurs', [
    ('generer_pdf_participants', {**COMMUN, 'participants': _parts(3)}, {'0x5b9bd5'}),
    ('generer_pdf_bataqa_hodour', {**COMMUN, 'participants': _parts(3)}, {'0x5b9bd5'}),
    ('generer_pdf_programme', _programme(), {'0xb4c6e7', '0xd9e2f3'}),
])
def test_traits_doubles_et_fonds(enreg, gen, donnees, couleurs):
    getattr(pg, gen)(donnees, BASE)
    c = enreg.derniers[-1]
    # bordure double (trait plein + trait fin) et séparateurs simples
    assert {pg.TRAIT_EPAIS, pg.TRAIT_FIN, pg.TRAIT_SIMPLE} <= c.traits
    assert couleurs <= c.fonds


def test_constantes_des_modeles():
    assert pg.BLEU_ENTETE.hexval().lower() == '0x5b9bd5'
    assert pg.BLEU_COLONNES.hexval().lower() == '0xb4c6e7'
    assert pg.BLEU_DATE.hexval().lower() == '0xd9e2f3'
    assert pg.TRAIT_EPAIS > pg.TRAIT_FIN >= pg.TRAIT_SIMPLE


# ─── 4. Fusion des مكان العمل identiques et consécutifs ───────────────────────

def test_groupes_fusion():
    assert pg._groupes_fusion(['a', 'a', 'b', 'a', 'a', 'a']) == [(0, 1), (2, 2), (3, 5)]
    assert pg._groupes_fusion(['', '', 'x']) == [(0, 0), (1, 1), (2, 2)]   # vides : jamais fusionnés
    assert pg._groupes_fusion([]) == []


def test_participants_lieu_fusionne_ecrit_une_fois(enreg):
    lieux = ['مكتب ألف', 'فصيل وهمي', 'فصيل وهمي', 'فصيل وهمي', 'مكتب ألف']
    pg.generer_pdf_participants({**COMMUN, 'participants': _parts(5, lieux)}, BASE)
    c = enreg.derniers[-1]
    assert len(_textes(c, 'فصيل وهمي')) == 1
    assert len(_textes(c, 'مكتب ألف')) == 2        # deux lignes non consécutives


# ─── 5. Pagination ───────────────────────────────────────────────────────────

def test_participants_pagination_numeros_complets(enreg):
    pg.generer_pdf_participants({**COMMUN, 'participants': _parts(45)}, BASE)
    c = enreg.derniers[-1]
    assert c.page >= 2
    nums = [t for f, s, t, p in c.textes if re.fullmatch(r'\d\d', t)]
    assert nums == [f'{i:02d}' for i in range(1, 46)]
    # l'en-tête du tableau est repris sur chaque page
    assert {p for f, s, t, p in c.textes if t == pg._arh('مكان العمل')} == set(range(1, c.page + 1))


def test_hodour_pied_une_seule_fois_en_derniere_page(enreg):
    pg.generer_pdf_bataqa_hodour({**COMMUN, 'participants': _parts(30),
                                  'titre_responsable': 'النقيب', 'nom_responsable': 'مسؤول وهمي'}, BASE)
    c = enreg.derniers[-1]
    assert c.page >= 2
    pied = _textes(c, 'المكوّن')
    assert len(pied) == 1 and pied[0][2] == c.page


def test_programme_long_continue_sur_page_suivante(enreg):
    pg.generer_pdf_programme(_programme(30), BASE)
    c = enreg.derniers[-1]
    assert c.page == 2
    # toutes les lignes sont imprimées (l'ancien générateur les tronquait)
    for i in range(1, 31):
        assert _textes(c, f'نشاط تجريبي {i}'), i
    assert [p for f, s, t, p in c.textes if t == pg._arh('التّوقيت')] == [1, 2]
    assert len(_textes(c, 'القصرين يوم الأربعاء الموافق لـ 24 جوان 2026')) == 1


def test_titre_trop_long_reduit_puis_coupe(enreg):
    long = 'موضوع تجريبي طويل جدّا ' * 6
    pg.generer_pdf_programme(_programme(2, theme=long), BASE)
    c = enreg.derniers[-1]
    sous = [s for f, s, t, p in c.textes if f == pg.F_ARB and 12.0 <= s < 16.0]
    assert sous and min(sous) >= pg.SW_MIN          # jamais sous 12 pt


def test_ligne_date_ignoree_si_date_invalide(enreg):
    pg.generer_pdf_programme(_programme(2, date_formation='غير محدد'), BASE)
    c = enreg.derniers[-1]
    assert not [t for f, s, t, p in c.textes if pg._arh('الموافق') in t]


def test_liste_vide_produit_quand_meme(enreg):
    chemin = pg.generer_pdf_participants({**COMMUN, 'participants': []}, BASE)
    assert open(chemin, 'rb').read(4) == b'%PDF'
    chemin = pg.generer_pdf_bataqa_hodour({**COMMUN, 'participants': []}, BASE)
    assert open(chemin, 'rb').read(4) == b'%PDF'


# ─── 6. Étirement (مدّ) et voyelles ───────────────────────────────────────────

@pytest.mark.parametrize('mot, attendu', [
    ('الجمهورية', 'الجمهوريـة'), ('المالية', 'الماليـة'), ('للديوانة', 'للديوانـة'),
    ('وزارة', 'وزارة'),          # ر ne se lie pas à la lettre suivante
    ('الجهوي', 'الجهوي'),        # و non plus
    ('الجمهوريّة', 'الجمهوريّـة'),   # tatwīl APRÈS la شدّة
])
def test_position_kashida(mot, attendu):
    assert pg._etirer_mot(mot, 1) == attendu


def test_kashida_approche_la_cible_sans_la_depasser():
    pg._register_fonts(BASE)
    c = rl_canvas.Canvas(os.devnull)
    nat = pg._w(c, pg._arh('الجمهورية التونسية'), pg.F_ARB, 12)
    cible = nat * 1.35
    t = pg._texte_kashida(c, 'الجمهورية التونسية', pg.F_ARB, 12, cible)
    w = pg._w(c, pg._arh(t), pg.F_ARB, 12)
    assert 'ـ' in t and w <= cible and cible - w < 2 * pg._w(c, 'ـ', pg.F_ARB, 12) + 1


def test_harakat_conservees_dans_les_pieces_word_seulement():
    pg._register_fonts(BASE)
    if pg._convention_harakat() is None:
        pytest.skip('police sans tracé de voyelles lisible')
    assert '\u0651' in pg._arh('التّوقيت')
    assert '\u0651' not in pg.ar('التّوقيت')      # autres pièces : inchangé


def test_convention_de_la_police_integree():
    """La police intégrée (Noto) trace ses voyelles à droite de l'origine :
    l'ordre visuel de python-bidi (voyelle avant sa lettre) est alors le bon."""
    pg._register_fonts(BASE)
    if not pg.POLICE_ACTIVE.get('arial'):
        assert pg._convention_harakat() == 'droite'
        v = pg._arh('الرّتبة')
        assert v[v.index('\u0651') + 1] == '\ufeae'     # شدّة juste avant le ر (forme finale)


def test_voyelles_deplacees_pour_police_tracee_a_gauche(monkeypatch):
    assert pg._voyelles_apres('ab\u0651cd') == 'abc\u0651d'
    monkeypatch.setattr(pg, '_convention_harakat', lambda: 'gauche')
    w = pg._arh('الرّتبة')
    assert w[w.index('\u0651') - 1] == '\ufeae'     # شدّة juste après le ر (forme finale)


def test_sans_convention_lisible_on_revient_a_ar(monkeypatch):
    monkeypatch.setattr(pg, '_convention_harakat', lambda: None)
    assert pg._arh('التّوقيت') == pg.ar('التّوقيت')


# ─── 7. Les autres pièces ne bougent pas ─────────────────────────────────────

# Empreintes du code source relevées AVANT la حزمة هـ.
# v1.7 : les quatre générateurs de مراسلات ne changent QUE leur fichier de
# sortie (transitoire, supprimé après envoi) et la garde du ختم (désactivé par
# défaut, activable par le مشرف) et le retrait de variables mortes — rendu
# vérifié identique au
# pixel près avec la v1.6.1 ; empreintes mises à jour en conséquence.
# V2 : إشعار et مراسلة المدير الجهوي — case « تاريخ التكوين » sur deux lignes
# (« من … » / « إلى … ») pour une دورة متعدّدة الأيّام seulement ; rendu d'une
# دورة d'un jour vérifié identique au pixel avec la v1.7.2 (tests/test_v2_multijours.py).
EMPREINTES = {
    'generer_pdf': 'ab3692244f23', 'generer_pdf_directeur_regional': '4c29737fd520',
    # generer_pdf_bataqa : modifiée volontairement en v1.6.1 (tableau extensible) ;
    # son rendu habituel reste identique — voir tests/test_v161.py.
    'generer_pdf_libre': '0a16dd880482',
    'generer_pdf_memo': '84d793904891', '_draw_entete': 'f964a1e2d6a0',
    # _draw_pied_ecole : v1.7.1, emblème de l'École ajouté en tête du pied de la
    # مذكّرة et texte décalé à gauche (demande du centre) — voir test_v171.py.
    '_draw_pied_ecole': '3600da955a4a', 'ar': 'fddb062fbe9c', '_wrap': '357025b02878',
    '_wrap_log': 'd0502f95c5ac', '_justify_rtl': '66a8dbe09dba', '_cell': '8e9705b5cab0',
    '_kashida': 'b23fd3779fbe', 'compter_pages_pdf': '7c9827c2e172',
}


@pytest.mark.parametrize('fonction', sorted(EMPREINTES))
def test_autres_generateurs_intacts(fonction):
    src = inspect.getsource(getattr(pg, fonction))
    assert hashlib.sha256(src.encode()).hexdigest()[:12] == EMPREINTES[fonction]


def test_page_des_autres_pieces_inchangee():
    assert (pg.PW, pg.PH) == (595.32, 830.64)


# ─── 8. Par les routes, sur une vraie دورة ───────────────────────────────────

def _dorra(db, lieux):
    annee = db.annee_registre()
    lid = db.save_programme(
        'interne', 'فيفري', annee,
        [{'titre': 'إجراءات تجريبية', 'grade': 'مقدم', 'nom_formateur': 'مكوّن وهمي',
          'lieu_travail': '', 'date_formation': f'{annee}-02-10', 'periode': '',
          'lieu_formation': 'قاعة 1'}], 'مسؤول وهمي', 'النقيب')
    db.verrouiller_lettre(lid, 'interne')
    fid = db.get_lettre_detail(lid)['formations'][0]['id']
    db.save_participants(lid, fid, [
        {'nom_prenom': p['nom_prenom'], 'grade': p['grade'], 'lieu_travail': p['lieu_travail'],
         'identifiant_unique': p['identifiant_unique'], 'jiha_marjiiya': ''}
        for p in _parts(len(lieux), lieux)])
    return lid, fid


def test_routes_des_trois_pieces(client, db):
    lid, fid = _dorra(db, ['مكتب ألف'] * 12 + ['مكتب باء'] * 30)
    for piece in ('participants', 'hodour'):
        r = client.get(f'/lettre/{lid}/formations/{fid}/{piece}/pdf')
        assert r.status_code == 200 and r.data[:4] == b'%PDF', piece
        assert b'/Count 2' in r.data or b'/Count 3' in r.data, piece   # 42 lignes → plusieurs pages
    # برنامج : chaîne complète (بطاقة confirmée → برنامج par la route)
    db.save_bataqa_data(fid, db.get_bataqa_data(lid, fid) or {})
    r = client.post(f'/lettre/{lid}/formations/{fid}/programme/data', headers=JETON, json={'rows': [
        {'type': 'row', 'time_debut': '08:30', 'time_fin': '09:00',
         'activity': 'استقبال المشاركين', 'participants': 'المقدم مكوّن وهمي'},
        {'type': 'row', 'time_debut': '09:00', 'time_fin': '12:00',
         'activity': 'محور تجريبي', 'participants': 'المقدم مكوّن وهمي'}]})
    assert r.status_code == 200, r.get_json()
    r = client.get(f'/lettre/{lid}/formations/{fid}/programme/pdf')
    assert r.status_code == 200 and r.data[:4] == b'%PDF'


def test_comptage_du_dossier_suit_les_pages_reelles(db):
    """Le nombre de feuillets de la مذكّرة lit les pages RÉELLES des annexes."""
    chemin = pg.generer_pdf_participants({**COMMUN, 'participants': _parts(45)}, BASE)
    assert pg.compter_pages_pdf(chemin) >= 2
    chemin = pg.generer_pdf_programme(_programme(3), BASE)
    assert pg.compter_pages_pdf(chemin) == 1


def test_version_1_6():
    # v1.7 : la version avance ; on vérifie seulement qu'elle n'a pas reculé
    from core import identite
    # 1.0 : numérotation repartie de 1.0 à la mise en service (format seul)
    majeur, mineur = (int(x) for x in identite.VERSION_APP.split('.')[:2])
    assert majeur >= 1 and mineur >= 0
    assert identite.VERSION_LABEL == 'الإصدار ' + identite.VERSION_APP


def test_rtba_longue_reduite_avant_coupure(enreg):
    """« رقيب للديوانة » : réduite si besoin (≥ 12 pt) sur UNE ligne plutôt que
    coupée — la liste garde la hauteur de ligne du modèle."""
    parts = [{'nom_prenom': 'مشارك وهمي', 'grade': 'رقيب للديوانة',
              'identifiant_unique': '90000001', 'lieu_travail': 'مكتب وهمي'}]
    pg.generer_pdf_participants({**COMMUN, 'participants': parts}, BASE)
    c = enreg.derniers[-1]
    g = _textes(c, 'رقيب للديوانة')
    assert len(g) == 1 and g[0][0] == pg.F_AR and pg.SW_MIN <= g[0][1] <= 14.0


def test_cellule_fusionnee_passe_a_la_ligne_sans_reduire(enreg):
    lieu = 'فصيل الحراسة والتفتيشات الديوانية بالقصرين وما جاورها من المعتمديات'
    pg.generer_pdf_participants({**COMMUN, 'participants': _parts(3, [lieu] * 3)}, BASE)
    c = enreg.derniers[-1]
    morceaux = [(f, s) for f, s, t, p in c.textes if f == pg.F_AR and s == 14.0
                and t not in {pg._arh(f'مشارك تجريبي {i}') for i in (1, 2, 3)}
                and not t.isdigit() and t not in {pg._arh(g) for g in ('عقيد', 'مقدم', 'رائد')}]
    assert len(morceaux) >= 2           # texte du groupe réparti sur plusieurs lignes, en 14 pt
