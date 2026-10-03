# -*- coding: utf-8 -*-
"""v1.7 — Paquet D : ملفّ الدورة (Word/ZIP), شهادات المشاركة, طباعة السّجلّ."""

import io
import re
import zipfile

import pytest

from core import docx_ecrivain as dx
from core import dossier_word

H = {'X-CSRF-Token': 'jeton-de-test'}


def _dorra(db, *, bataqa=True, programme=True, memo=True, hodour=True, femme=False):
    annee = db.annee_registre()
    lid = db.save_programme(
        'interne', 'فيفري', annee,
        [{'titre': 'النزاعات الديوانية', 'grade': 'المقدم', 'nom_formateur': 'السايحي ماهر',
          'lieu_travail': '', 'date_formation': f'{annee}-02-12', 'periode': 'صباحا',
          'lieu_formation': 'مركز التكوين الجهوي بالقصرين'}],
        'حازم مسعودي', 'النقيب')
    db.verrouiller_lettre(lid, 'interne')
    fid = db.get_lettre_detail(lid)['formations'][0]['id']
    db.save_participants(lid, fid, [
        {'nom_prenom': 'مشارك وهمي أوّل', 'grade': 'الملازم', 'identifiant_unique': '90000001',
         'lieu_travail': 'مكتب وهمي', 'jiha_marjiiya': '', 'sexe': 'أنثى' if femme else 'ذكر'},
        {'nom_prenom': 'مشارك وهمي ثان', 'grade': 'النقيب', 'identifiant_unique': '90000002',
         'lieu_travail': 'مكتب وهمي', 'jiha_marjiiya': '', 'sexe': 'ذكر'},
        {'nom_prenom': 'مشارك غائب', 'grade': 'الوكيل', 'identifiant_unique': '90000003',
         'lieu_travail': 'فرقة وهمية', 'jiha_marjiiya': '', 'sexe': 'ذكر'}])
    if bataqa:
        db.save_bataqa_data(fid, {'mustahdafun': 'أعوان', 'mahawer': 'محور 1\nمحور 2',
                                  'objectifs': 'هدف', 'methodes_pedagogiques': 'عرض'})
    if programme:
        db.save_programme_data(fid, {'reference': 'م', 'moment': 'صباحا', 'rows': [
            {'type': 'row', 'activity': 'حصّة أولى', 'participants': 'المقدم السايحي ماهر',
             'time_debut': '08:30', 'time_fin': '10:00', 'time': 'من 08:30 إلى 10:00'},
            {'type': 'row', 'activity': 'حصّة ثانية', 'participants': 'المقدم السايحي ماهر',
             'time_debut': '10:15', 'time_fin': '12:30', 'time': 'من 10:15 إلى 12:30'}]})
    if memo:
        db.save_memo_data(fid, {'objet': 'تنظيم دورة', 'corps': 'وبعد، نصّ المذكّرة.\nوالسلام.',
                                'moujah': [{'nom': 'الإدارة الجهوية بالقصرين'}]}, confirmer=True)
    if hodour:
        db.finaliser_formation(fid)
        hs = db.get_hodour(fid)
        db.save_hodour(fid, {x['id']: (x['nom_prenom'] != 'مشارك غائب') for x in hs})
    return lid, fid


def _xml(docx_octets):
    with zipfile.ZipFile(io.BytesIO(docx_octets)) as z:
        return z.read('word/document.xml').decode('utf-8')


def _texte(docx_octets):
    return ''.join(re.findall(r'<w:t[^>]*>([^<]*)</w:t>', _xml(docx_octets)))


# ═══ Écrivain docx ══════════════════════════════════════════════════════════

def test_docx_minimal_valide():
    doc = dx.DocumentWord(titre='اختبار')
    doc.ajouter(dx.paragraphe('نصّ عربي & <خاصّ>', taille=14, gras=True))
    octets = doc.octets()
    with zipfile.ZipFile(io.BytesIO(octets)) as z:
        noms = set(z.namelist())
        assert {'[Content_Types].xml', '_rels/.rels', 'word/document.xml',
                'word/styles.xml', 'word/_rels/document.xml.rels'} <= noms
        xml = z.read('word/document.xml').decode('utf-8')
    assert '&amp;' in xml and '&lt;خاصّ&gt;' in xml         # échappement
    assert '<w:bidi/>' in xml and '<w:szCs w:val="28"/>' in xml and '<w:bCs/>' in xml


def test_alignements_logiques():
    assert 'w:val="start"' in dx.paragraphe('x', align='droite')
    assert 'w:val="end"' in dx.paragraphe('x', align='gauche')
    assert 'w:val="end"' in dx.paragraphe('x', align='droite', ltr=True)


def test_cellule_se_termine_par_un_paragraphe():
    t = dx.tableau([2], [dx.ligne([dx.cellule('<w:p/>', 2)])])
    cel = dx.cellule([t], 3)
    assert cel.rstrip().endswith('</w:p></w:tc>')


def test_tableau_rtl():
    t = dx.tableau([1, 2], [dx.ligne([dx.cellule(dx.paragraphe('أ'), 1),
                                     dx.cellule(dx.paragraphe('ب'), 2)])])
    assert '<w:bidiVisual/>' in t and 'w:val="double"' in t


def test_image_integree(tmp_path):
    import os
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    doc = dx.DocumentWord()
    doc.ajouter(doc.image(os.path.join(base, 'static', 'images', 'logo.jpg'), 2, 3))
    with zipfile.ZipFile(io.BytesIO(doc.octets())) as z:
        assert 'word/media/image1.jpeg' in z.namelist()
        assert 'rIdImg1' in z.read('word/_rels/document.xml.rels').decode()


# ═══ 4. ملفّ الدورة ═════════════════════════════════════════════════════════

def test_dossier_complet(db, client):
    lid, fid = _dorra(db)
    r = client.get(f'/lettre/{lid}/formations/{fid}/dossier.zip')
    assert r.status_code == 200 and r.mimetype == 'application/zip'
    with zipfile.ZipFile(io.BytesIO(r.data)) as z:
        noms = z.namelist()
        assert noms == ['1_المذكرة.docx', '2_برنامج_الدورة.docx',
                        '3_القائمة_الإسمية_للمشاركين.docx', '4_البطاقة_البيداغوجية.docx',
                        '5_بطاقة_الحضور.docx']
        memo = z.read('1_المذكرة.docx')
        prog = z.read('2_برنامج_الدورة.docx')
        liste = z.read('3_القائمة_الإسمية_للمشاركين.docx')
        hod = z.read('5_بطاقة_الحضور.docx')
    from core import dossier_dorra as dd
    objet = dd.donnees_memo(lid, fid)['objet']          # même objet que le PDF
    assert objet and objet in _texte(memo) and 'مذكّــــرة' in _texte(memo)
    assert re.search(r'\d+/\d+', _texte(memo))                   # خانة Page remplie
    assert 'حصّة أولى' in _texte(prog) and 'من 08:30 إلى 10:00' in _texte(prog)
    t = _texte(liste)
    # ordre militaire : النقيب avant الملازم
    assert t.index('مشارك وهمي ثان') < t.index('مشارك وهمي أوّل')
    assert 'الإمضاء' in _texte(hod) and 'السايحي ماهر' in _texte(hod)
    assert any(j['action'] == 'تحميل ملفّ الدورة (Word)' for j in db.get_journal(5))


def test_dossier_memo_meme_pagination_que_le_pdf(db, client):
    lid, fid = _dorra(db)
    from core import dossier_dorra as dd
    import os
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    donnees = dd.donnees_memo(lid, fid)
    n = dd.pages_du_dossier(lid, fid, donnees, base)
    r = client.get(f'/lettre/{lid}/formations/{fid}/dossier.zip')
    with zipfile.ZipFile(io.BytesIO(r.data)) as z:
        assert f'{n}/{n}' in _texte(z.read('1_المذكرة.docx'))


def test_dossier_incomplet_avec_note(db, client):
    lid, fid = _dorra(db, bataqa=False, programme=False, memo=False, hodour=False)
    r = client.get(f'/lettre/{lid}/formations/{fid}/dossier.zip')
    with zipfile.ZipFile(io.BytesIO(r.data)) as z:
        noms = z.namelist()
        assert '3_القائمة_الإسمية_للمشاركين.docx' in noms and '5_بطاقة_الحضور.docx' in noms
        assert '1_المذكرة.docx' not in noms and '2_برنامج_الدورة.docx' not in noms
        note = z.read('ملاحظة.txt').decode('utf-8-sig')
    assert 'المذكّرة' in note and 'برنامج الدورة' in note and 'البطاقة البيداغوجية' in note


def test_dossier_sans_aucune_piece(db, client):
    annee = db.annee_registre()
    lid = db.save_programme('interne', 'فيفري', annee, [
        {'titre': 'ت', 'grade': 'المقدم', 'nom_formateur': 'س', 'lieu_travail': '',
         'date_formation': f'{annee}-02-12', 'periode': '', 'lieu_formation': 'ق'}], 'ح', 'ن')
    fid = db.get_lettre_detail(lid)['formations'][0]['id']
    r = client.get(f'/lettre/{lid}/formations/{fid}/dossier.zip')
    assert r.status_code == 302


def test_dossier_dorra_inconnue(db, client, programme):
    assert client.get(f"/lettre/{programme['lettre_id']}/formations/99999/dossier.zip"
                      ).status_code == 404


def test_fusion_lieu_de_travail(db):
    lid, fid = _dorra(db)
    from core import dossier_dorra as dd
    xml = _xml(dossier_word.word_participants(dd.donnees_participants(lid, fid), '.'))
    assert '<w:vMerge w:val="restart"/>' in xml and '<w:vMerge/>' in xml


def test_boutons_presents(db, client):
    lid, fid = _dorra(db)
    corps = client.get(f'/lettres/{lid}').data.decode('utf-8')
    assert 'تحميل ملفّ الدورة (Word)' in corps and 'طباعة شهائد المشاركين (2)' in corps
    from tests.conftest import js_programme
    src = open('templates/nouvelle_lettre.html', encoding='utf-8').read() + js_programme()
    assert 'btnDossier_' in src and 'telechargerDossier' in src


# ═══ 18. شهادات المشاركة ════════════════════════════════════════════════════

def test_shahadat_pour_les_presents_seulement(db, client):
    lid, fid = _dorra(db)
    from core import dossier_dorra as dd
    donnees, presents = dd.donnees_shahadat(lid, fid)
    assert [p['nom_prenom'] for p in presents] == ['مشارك وهمي ثان', 'مشارك وهمي أوّل']
    r = client.get(f'/lettre/{lid}/formations/{fid}/shahadat/pdf')
    assert r.status_code == 200 and r.data[:4] == b'%PDF'
    from core.pdf_generator import compter_pages_pdf
    import tempfile, os
    f = tempfile.NamedTemporaryFile(delete=False, suffix='.pdf')
    f.write(r.data); f.close()
    assert compter_pages_pdf(f.name) == 2
    os.remove(f.name)


def test_shahadat_une_seule(db, client):
    lid, fid = _dorra(db)
    from core import dossier_dorra as dd
    _d, presents = dd.donnees_shahadat(lid, fid)
    pid = presents[0]['id']
    _d, un = dd.donnees_shahadat(lid, fid, pid)
    assert len(un) == 1 and un[0]['id'] == pid


def test_shahadat_avant_la_feuille_de_presence(db, client):
    lid, fid = _dorra(db, hodour=False)
    from core import dossier_dorra as dd
    donnees, motif = dd.donnees_shahadat(lid, fid)
    assert donnees is None and 'ورقة الحضور' in motif
    r = client.get(f'/lettre/{lid}/formations/{fid}/shahadat/pdf')
    assert r.status_code == 302


def test_shahadat_accord_feminin(db, monkeypatch):
    lid, fid = _dorra(db, femme=True)
    from core import dossier_dorra as dd, pdf_shahadat
    import core.pdf_generator as pg
    textes = []
    orig = pg._arh
    monkeypatch.setattr(pg, '_arh', lambda t: (textes.append(t), orig(t))[1])
    donnees, presents = dd.donnees_shahadat(lid, fid)
    import os
    chemin = pdf_shahadat.generer(donnees, presents, os.path.dirname(os.path.dirname(
        os.path.abspath(__file__))))
    os.remove(chemin)
    assert any(t.startswith('قد شاركت في') for t in textes)       # la participante
    assert any(t.startswith('قد شارك في') for t in textes)        # le participant
    # V3.0.1 : les lignes « بتأطير » / « وقد سُلّمت » ne figurent plus
    assert not any('سُلّمت' in t or t.startswith('بتأطير') for t in textes)


# ═══ 19. طباعة السّجلّ ══════════════════════════════════════════════════════

def test_registre_pdf(db, client):
    _dorra(db)
    annee = db.annee_registre()
    r = client.get(f'/registre/interne/pdf?annee={annee}')
    assert r.status_code == 200 and r.data[:4] == b'%PDF'
    assert any(j['action'] == 'طباعة سجلّ المراسلات' for j in db.get_journal(5))


def test_registre_pdf_vide_et_externe(db, client):
    r = client.get('/registre/externe/pdf')
    assert r.status_code == 200 and r.data[:4] == b'%PDF'


def test_registre_pdf_long_pagine(db, monkeypatch):
    import os
    from core import pdf_registre
    from core.pdf_generator import compter_pages_pdf
    entrees = [{'numero': i, 'ref_complet': f'END-3-01-02-26-{i:04d}', 'source_label': 'مراسلة حرة',
                'objet': 'موضوع تجريبي طويل ' * (i % 4 + 1), 'statut': 'definitif',
                'date_attribution': '2026-03-01 10:00:00'} for i in range(1, 121)]
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    chemin = pdf_registre.generer(entrees, 'interne', 2025, db.get_config(), base,
                                  liberes=[7], lacunes=[9], ouverte=False)
    assert compter_pages_pdf(chemin) >= 3
    os.remove(chemin)


def test_bouton_impression_registre(db, client):
    assert 'طباعة السّجلّ (PDF)' in client.get('/registre/interne').data.decode('utf-8')
