# -*- coding: utf-8 -*-
"""«إضافة إسم جديد» — تحميل بطاقة شخص من ملفّ (v1.4e).

Les fixtures reproduisent la «بطاقة إرشادات حول المكوّن» (libellés à
droite, valeurs dans des cases fusionnées, deux paires sur certaines lignes,
cases d'en-tête et de pied sans rapport) — avec des données FICTIVES.
"""
import io
import json
import os

import pytest

from core import fiche_mkow_import as F

ICI = os.path.join(os.path.dirname(__file__), 'fixtures', 'fiche')
ATTENDU = json.load(open(os.path.join(ICI, 'attendu.json'), encoding='utf-8'))
JETON = {'X-CSRF-Token': 'jeton-de-test'}


@pytest.mark.parametrize('fichier', ['fiche_rtl.xlsx', 'fiche_ltr.xlsx', 'fiche_rtl.xls',
                                     'fiche.docx', 'fiche.doc'])
def test_chaque_خانة_est_lue_dans_chaque_format(fichier):
    champs, avert = F.analyser(open(os.path.join(ICI, fichier), 'rb').read(), fichier)
    fautes = {k: (champs.get(k), v) for k, v in ATTENDU.items() if champs.get(k) != v}
    assert not fautes, fautes
    # La fiche officielle n'a pas de « مكان العمل » : repris de « الإدارة », signalé.
    assert champs['lieu_travail'] == champs['administration']
    assert len(avert) == 1 and 'مكان العمل' in avert[0]


def test_deux_paires_sur_une_ligne():
    """« رقم بطاقة التعريف | … | الصادرة بتاريخ | … » : deux valeurs, pas une."""
    champs, _ = F.analyser(open(os.path.join(ICI, 'fiche_rtl.xlsx'), 'rb').read(), 'x.xlsx')
    assert champs['cin'] == '01234567' and champs['cin_date'] == '2020-01-13'
    assert champs['telephone_gsm'] == '98765432' and champs['telephone_adm'] == '77123456'


def test_une_valeur_qui_commence_comme_un_libelle_reste_une_valeur():
    """« البنك الوطني الفلاحي » commence par le libellé « البنك »."""
    champs, _ = F.analyser(open(os.path.join(ICI, 'fiche.docx'), 'rb').read(), 'x.docx')
    assert champs['banque'] == 'البنك الوطني الفلاحي'


def test_les_pieges_d_excel_sont_signales():
    champs, avert = F.analyser(open(os.path.join(ICI, 'fiche_nombres.xlsx'), 'rb').read(), 'x.xlsx')
    assert champs['cin'] == '01234567'                        # zéro de tête rendu
    assert any('الصفر الأوّل' in a for a in avert)
    assert any('15 رقمًا' in a for a in avert)                # compte possiblement arrondi


@pytest.mark.parametrize('brut,iso', [
    ('13/01/2020', '2020-01-13'), ('2020-01-13', '2020-01-13'), ('13-1-2020', '2020-01-13'),
    ('13 جانفي 2020', '2020-01-13'), ('١٣/٠١/٢٠٢٠', '2020-01-13'), ('31/02/2020', ''), ('غدا', ''),
])
def test_les_dates(brut, iso):
    assert F.lire_date(brut) == iso


def test_le_nom_se_reaffiche_tel_qu_il_est_ecrit():
    """nom + ' ' + prenom = exactement ce que porte la fiche, sans deviner."""
    champs, _ = F.normaliser_valeurs({'nom_complet': 'منى بن عمر'})
    assert (champs['nom'] + ' ' + champs['prenom']) == 'منى بن عمر'


def test_la_رتبة_est_rapprochee_de_la_liste():
    grades = ['العميد', 'النقيب', 'الملازم أول']
    assert F.rapprocher_grade('نقيب', grades) == 'النقيب'
    assert F.rapprocher_grade('نقيب للديوانة', grades) == 'النقيب'
    assert F.rapprocher_grade('وكيل الشرطة', grades) == ''


def test_format_refuse():
    with pytest.raises(F.ErreurFiche):
        F.analyser(b'x', 'photo.png')


# ─── routes ──────────────────────────────────────────────────────────────────

def _envoyer(client, nom):
    data = open(os.path.join(ICI, nom), 'rb').read()
    return client.post('/mkowin/importer-fiche', headers=JETON,
                       data={'fichier': (io.BytesIO(data), nom)},
                       content_type='multipart/form-data').get_json()


def test_la_route_renvoie_les_champs_sans_rien_enregistrer(client, db):
    avant = len(db.get_mkowin())
    j = _envoyer(client, 'fiche_rtl.xlsx')
    assert j['succes'] and j['champs']['identifiant_unique'] == '1234567890'
    assert j['champs']['grade'] == 'النقيب'              # graphie de la liste
    assert j['existe'] is None
    assert len(db.get_mkowin()) == avant                   # rien d'écrit


def test_la_route_signale_une_personne_deja_inscrite(client, db):
    db.add_mkow({'grade': 'النقيب', 'nom': 'سامي', 'prenom': 'بن صالح',
                 'identifiant_unique': '1234567890'})
    j = _envoyer(client, 'fiche.docx')
    assert j['existe'] and j['existe']['nom'] == 'سامي بن صالح'


def test_l_ajout_refuse_un_doublon(client, db):
    db.add_mkow({'grade': 'النقيب', 'nom': 'سامي', 'prenom': 'بن صالح', 'cin': '01234567'})
    avant = len(db.get_mkowin())
    r = client.post('/mkowin/ajouter', data={
        '_csrf': 'jeton-de-test', 'grade': 'النقيب', 'nom': 'سامي', 'prenom': 'بن صالح',
        'cin': '01234567', 'telephone_gsm': '98765432'})
    assert r.status_code == 200
    assert 'مسجَّل مسبقًا' in r.get_data(as_text=True)
    assert len(db.get_mkowin()) == avant


def test_la_page_propose_le_chargement(client):
    html = client.get('/mkowin/ajouter').get_data(as_text=True)
    assert 'id="ficheFile"' in html and 'lireFiche' in html
    assert '.doc,.docx,.xls,.xlsx' in html
    assert 'placeholder="الاسم"' in html and 'placeholder="اللقب"' in html
