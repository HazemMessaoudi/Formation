# -*- coding: utf-8 -*-
"""تحميل بطاقة بيداغوجيّة — ملفّات Word حقيقيّة (v1.4e).

Incident v1.4d : une بطاقة enregistrée en .doc (Word 97-2003) remplissait
6 خانات sur 10, dont 4 FAUSSES — le عنوان dans «المستهدفون», les محاور dans
«الأهداف», les طرق dans «المعينات», le إعداد dans «التجهيزات».

Les fichiers de `fixtures/bataqa/` sont de VRAIS fichiers Word (produits une
fois par LibreOffice) : huit mises en page, chacune en .doc, .docx, et .docx
réécrit par un autre logiciel (`__lo`). `verites.json` porte, pour chacune,
ce qui est réellement écrit dans la بطاقة. Chaque خانة est comparée.
"""
import json
import os

import pytest

from core import bataqa_import as B
from core.importation import _normaliser as N

ICI = os.path.join(os.path.dirname(__file__), 'fixtures', 'bataqa')
VERITES = json.load(open(os.path.join(ICI, 'verites.json'), encoding='utf-8'))

CHAMPS = [('titre', 'titre'), ('type_formation', 'type'),
          ('mustahdafun', 'mustahdafun'), ('lieu_formation_defaut', 'lieu'),
          ('mahawer', 'mahawer'), ('objectifs', 'objectifs'),
          ('methodes_pedagogiques', 'methodes'), ('moyens_pedagogiques', 'moyens'),
          ('preparation_materielle', 'preparation'), ('equipements', 'equipements')]

CAS = [(nom, suffixe) for nom in sorted(VERITES)
       for suffixe in ('.doc', '.docx', '__lo.docx')]


def _lignes(x):
    return [N(l).rstrip(' .') for l in (x if isinstance(x, list) else ([x] if x else []))]


@pytest.mark.parametrize('nom,suffixe', CAS, ids=[f'{n}{s}' for n, s in CAS])
def test_chaque_خانة_recoit_exactement_ce_que_porte_la_بطاقة(nom, suffixe):
    chemin = os.path.join(ICI, nom + suffixe)
    lu = B.analyser(open(chemin, 'rb').read(), chemin)
    v = VERITES[nom]
    fautes = []
    for cle, vk in CHAMPS:
        attendu = _lignes(v[vk])
        obtenu = _lignes((lu.get(cle) or '').splitlines())
        if attendu != obtenu:
            fautes.append(f'{cle}: lu {obtenu[:2]}… attendu {attendu[:2]}…')
    assert not fautes, '\n'.join(fautes)


def test_le_doc_de_l_incident_ne_melange_plus_aucune_colonne():
    """Les quatre confusions constatées, nommément."""
    lu = B.analyser(open(os.path.join(ICI, 'v1_replique_utilisateur.doc'), 'rb').read(), 'x.doc')
    assert lu['titre'] == 'إستعمال وصيانة الأسلحة'
    assert 'إستعمال وصيانة الأسلحة' not in lu['mustahdafun']
    assert not set(lu['mahawer'].splitlines()) & set(lu['objectifs'].splitlines())
    assert 'العصف الذهني' not in lu['moyens_pedagogiques']
    assert lu['equipements'] == 'لاشئ'
    assert lu['preparation_materielle'].startswith('قاعة تدريس')


def test_le_doc_est_lu_par_sa_structure_et_non_par_balayage():
    """Le texte vient du flux WordDocument : aucun octet interne (noms de
    styles, table OLE) ne se glisse dans le texte lu."""
    texte = B._texte_word97(open(os.path.join(ICI, 'v1_replique_utilisateur.doc'), 'rb').read())
    assert 'موضوع التكوين' in texte and '\x07' in texte
    for intrus in ('Root Entry', 'Heading 1', 'Normal'):
        assert intrus not in texte


def test_un_doc_protege_ou_corrompu_donne_un_message_clair():
    with pytest.raises(B.ErreurBataqa):
        B.analyser(b'\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1' + b'\x00' * 600, 'x.doc')
    with pytest.raises(B.ErreurBataqa):
        B.analyser(b'pas un fichier word', 'x.doc')


def test_deux_colonnes_aplaties_ne_sont_jamais_devinees():
    """Lecture linéaire d'un tableau aplati : «محاور | أهداف» côte à côte ne
    doit rien attribuer plutôt que de mélanger les deux colonnes."""
    r = B._depuis_paras(['محاور الدورة', 'أهداف الدورة', 'أ', 'ب', 'ج', 'د'], strict=True)
    assert 'mahawer' not in r and 'objectifs' not in r


def test_le_titre_du_document_supplee_un_عنوان_absent():
    assert B._titre_depuis_texte(['الدورة التكوينيّة حول " الفوترة الإلكترونيّة "']) \
        == 'الفوترة الإلكترونيّة'
