# -*- coding: utf-8 -*-
"""V3.0.1 — corrections demandées après la mise en service de la V3.

 1. شهادة المشاركة : lignes « بتأطير … » et « وقد سُلّمت … » retirées
    (testé dans test_v17_paquet_d.test_shahadat_accord_feminin).
 2. الدورات المسجّلة : chaque دورة affiche le numéro de SA مذكّرة, pas celui
    du برنامج qu'elle partage avec d'autres دورات.
 3. نسخة HTML تفاعليّة retirée (test_v3_rapports.test_rapports_pdf_et_html).
 4. إعدادات التّقارير : le bouton « حفظ » vient après la section 4.
 5. عدد الدّورات المبرمجة enregistré par « حفظ إعدادات التّقارير » ; l'alerte
    « لم يُضبط… » disparaît.
 6. التقرير السنوي rangé sous التّقارير (test_v15_paquet_d.test_page_rapport_annuel).
 7. Graphiques en colonnes : toute colonne non nulle est étiquetée
    (test_v15_paquet_d.test_colonnes_geometrie).
"""


def _deux_dorrat_meme_programme(db):
    annee = db.annee_registre()
    lid = db.save_programme(
        'interne', 'فيفري', annee,
        [{'titre': 'دورة وهمية أولى', 'grade': 'المقدم', 'nom_formateur': 'مكوّن وهمي',
          'lieu_travail': '', 'date_formation': f'{annee}-02-10', 'periode': 'صباحا',
          'lieu_formation': 'مركز التكوين الجهوي بالقصرين'},
         {'titre': 'دورة وهمية ثانية', 'grade': 'النقيب', 'nom_formateur': 'مكوّن وهمي ثان',
          'lieu_travail': '', 'date_formation': f'{annee}-02-17', 'periode': 'صباحا',
          'lieu_formation': 'مركز التكوين الجهوي بالقصرين'}],
        'مسؤول وهمي', 'النقيب')
    db.verrouiller_lettre(lid, 'interne')
    fids = [f['id'] for f in db.get_lettre_detail(lid)['formations']]
    for k, fid in enumerate(fids):
        db.save_participants(lid, fid, [
            {'nom_prenom': f'مشارك وهمي {k}', 'grade': 'الملازم',
             'identifiant_unique': f'9100000{k}', 'lieu_travail': 'مكتب وهمي',
             'jiha_marjiiya': '', 'sexe': 'ذكر'}])
        db.save_bataqa_data(fid, {'mustahdafun': 'أعوان', 'mahawer': 'محور',
                                  'objectifs': 'هدف', 'methodes_pedagogiques': 'عرض'})
        db.save_programme_data(fid, {'reference': 'م', 'moment': 'صباحا', 'rows': [
            {'type': 'row', 'activity': 'حصّة', 'participants': 'مكوّن',
             'time_debut': '08:30', 'time_fin': '10:00', 'time': 'من 08:30 إلى 10:00'}]})
        db.save_memo_data(fid, {'objet': 'تنظيم دورة', 'corps': 'نصّ.',
                                'moujah': [{'nom': 'جهة وهمية'}]}, confirmer=True)
    return lid, fids


# ═══ 2. رقم كلّ دورة ═════════════════════════════════════════════════════════

def test_chaque_dorra_affiche_son_propre_numero(db, client):
    lid, fids = _deux_dorrat_meme_programme(db)
    dorrat = {d['id']: d for d in db.get_dorrat_avec_memo()}
    refs = [dorrat[f]['memo_ref'] for f in fids]
    assert all(refs) and refs[0] != refs[1]                   # deux numéros distincts
    assert dorrat[fids[0]]['lettre_ref'] == dorrat[fids[1]]['lettre_ref']   # même برنامج
    html = client.get('/programmes').get_data(as_text=True)
    for r in refs:
        assert f'title="مرجع المذكّرة الداخليّة للدورة">{r}</span>' in html
    assert 'مرجع المذكّرة الداخليّة' in html and 'مرجع البرنامج' in html


# ═══ 4 / 5. إعدادات التّقارير ═════════════════════════════════════════════════

def test_bouton_enregistrer_apres_section_4(client):
    html = client.get('/parametres/rapports').get_data(as_text=True)
    assert html.index('4 — عدد الدّورات المبرمجة') < html.index('💾 حفظ إعدادات التّقارير')
    assert 'form="formRapports" class="btn btn-add">💾' in html


def test_nombre_programme_enregistre_par_le_bouton_principal(db, client):
    from core.db.rapports import get_nb_programmees
    from core import rapports_moteur as rm, rapport_ecrit as re_
    r = client.post('/parametres/rapports', data={
        '_csrf': 'jeton-de-test', 'action': 'textes', 'nouvelle_annee': '2026', 'nouveau_nb': '12'})
    assert r.status_code == 302
    assert get_nb_programmees(2026) == 12
    # l'alerte « لم يُضبط عدد الدّورات المبرمجة » ne s'affiche plus
    p = rm.bornes_periode(2026, 'semestre', 1)
    alertes = re_.contenu(p, db.get_config())['alertes']
    assert not any('لم يُضبط عدد الدّورات المبرمجة' in a for a in alertes)
    # ligne existante modifiée depuis le tableau, même bouton
    client.post('/parametres/rapports', data={'_csrf': 'jeton-de-test', 'action': 'textes', 'nb_annee_2026': '15'})
    assert get_nb_programmees(2026) == 15
    # champ « إضافة » laissé vide : rien n'est touché
    client.post('/parametres/rapports', data={'_csrf': 'jeton-de-test', 'action': 'textes', 'nouvelle_annee': '2027',
                                              'nouveau_nb': ''})
    assert get_nb_programmees(2027) == 0
    # valeur invalide : refusée, le reste est enregistré
    client.post('/parametres/rapports', data={'_csrf': 'jeton-de-test', 'action': 'textes', 'nouvelle_annee': '1990',
                                              'nouveau_nb': '5'})
    assert get_nb_programmees(1990) == 0


def test_ancienne_action_annee_toujours_valide(client):
    from core.db.rapports import get_nb_programmees
    client.post('/parametres/rapports', data={'_csrf': 'jeton-de-test', 'action': 'annee', 'annee': '2028', 'nb': '7'})
    assert get_nb_programmees(2028) == 7
