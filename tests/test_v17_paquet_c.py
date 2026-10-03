# -*- coding: utf-8 -*-
"""v1.7 — Paquet C : رتب ملغاة، رتب افتراضيّة، دقّة مالية، شارتا الشاشة
الرئيسيّة، حماية الدخول، الختم الرقمي."""

import os
import sqlite3
from datetime import datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP

import pytest

from core import bareme_mali as bm
from core import mustahaqqat as mst
from core import khalas

H = {'X-CSRF-Token': 'jeton-de-test'}


# ═══ 3. الرتب ═══════════════════════════════════════════════════════════════

def test_rutab_malghat_hors_des_tables_par_defaut():
    assert bm.groupe_du_grade('الملازم أعلى') == bm.GROUPE_INCONNU
    assert bm.groupe_du_grade('وكيل أعلى للديوانة') == bm.GROUPE_INCONNU
    assert 'الملازم أعلى' not in bm.GRADES_PAR_GROUPE['II']
    assert 'أعلى' not in bm.LIBELLES_GROUPES['II']
    assert bm.LIBELLES_GROUPES['IV'] == 'المجموعة IV — من وكيل أول إلى عريف'
    assert mst.classe_du_grade('الملازم أعلى') == mst.CLASSE_INCONNUE


def test_rutab_restantes_intactes():
    for g, attendu in (('الرائد', 'II'), ('النقيب', 'II'), ('الوكيل أول', 'IV'),
                       ('العريف الأعلى', 'IV'), ('العريف', 'IV'), ('المقدم', 'I')):
        assert bm.groupe_du_grade(g) == attendu, g


def test_migration_retire_les_rutab_malghat(db):
    conn = db.get_connection()
    try:
        conn.execute("INSERT OR IGNORE INTO grades (nom) VALUES ('الملازم أعلى')")
        conn.execute("INSERT OR REPLACE INTO mustahaqqat_groupes (grade, groupe) VALUES ('الملازم أعلى','II')")
        conn.execute("INSERT OR REPLACE INTO mustahaqqat_groupes (grade, groupe) VALUES ('وكيل أعلى للديوانة','IV')")
        conn.execute("DELETE FROM config WHERE cle='v17_rutab_retirees'")
        conn.commit()
    finally:
        conn.close()
    db.init_db()
    conn = db.get_connection()
    try:
        assert not conn.execute("SELECT 1 FROM grades WHERE nom='الملازم أعلى'").fetchone()
        assert not conn.execute("SELECT 1 FROM mustahaqqat_groupes WHERE grade LIKE '%أعلى%' "
                                "AND grade NOT LIKE '%عريف%'").fetchone()
        # العريف الأعلى reste
        assert conn.execute("SELECT 1 FROM mustahaqqat_groupes WHERE grade='العريف الأعلى'").fetchone()
    finally:
        conn.close()


def test_migration_une_seule_fois(db):
    db.add_grade('الملازم أعلى')          # réintroduite délibérément par le centre
    db.init_db()
    assert 'الملازم أعلى' in db.get_grades()


def test_rutab_par_defaut_completees(db):
    g = db.get_grades()
    assert 'اللواء' in g and 'العريف الأعلى' in g
    assert mst.classe_du_grade('اللواء') == 'أ1'
    assert mst.classe_du_grade('العريف الأعلى') == 'ب'


def test_raqib_hors_du_bareme_message_clair():
    r = bm.chiffrer([{'de': '08:00', 'a': '10:00'}], 'ب', 'الرقيب أول')
    assert not r['chiffrable']
    assert any('خارج الجدول المالي' in m for m in r['motifs'])


# ═══ 9. الدقّة المالية ══════════════════════════════════════════════════════

def _attendu(brut, taux):
    b = Decimal(str(brut)).quantize(Decimal('0.001'), ROUND_HALF_UP)
    a = (b * Decimal(str(taux)) / 100).quantize(Decimal('0.001'), ROUND_HALF_UP)
    return a, b - a


def test_retenues_cas_signale():
    assert khalas.retenues(5.25, 15) == (0.788, 4.462)


def test_retenues_balayage_exhaustif():
    """Toutes les combinaisons taux × heures × نسبة réalistes : zéro écart."""
    for t_m in range(5000, 30001, 125):            # 5.000 → 30.000 par 0.125
        for h in range(1, 13):
            brut = bm.calculer_montant(h, t_m / 1000)
            for taux in (10, 12.5, 15, 20):
                a, n = khalas.retenues(brut, taux)
                ea, en = _attendu(Decimal(t_m) / 1000 * h, taux)
                assert Decimal(str(a)) == ea and Decimal(str(n)) == en, (t_m, h, taux)


def test_calculer_montant_exact():
    assert bm.calculer_montant(3, 5.255) == 15.765
    assert bm.calculer_montant(7, 11.5) == 80.5
    assert bm.calculer_montant(0, 12) is None
    assert bm.calculer_montant(3, None) is None


def test_formater_dinars():
    assert bm.formater_dinars(0.1 + 0.2) == '0.300'
    assert bm.formater_dinars(0.7875) == '0.788'
    assert bm.formater_dinars('12,5') == '12.500'
    assert bm.formater_dinars(None) == '' and bm.formater_dinars('x') == ''


def test_montant_en_lettres_exact():
    # Mêmes libellés qu'en v1.6.1 : seul le calcul des millimes change.
    assert khalas.montant_lettres(4.462) == 'أربعة دنانير وأربعمائة واثنان وستّون مليما'
    assert khalas.montant_lettres(0.1 + 0.2) == 'ثلاثمائة مليم'
    assert khalas.montant_lettres(75.5) == 'خمسة وسبعون دينارا وخمسمائة مليم'
    assert khalas.montant_lettres(1.001) == 'دينار واحد ومليم واحد'
    assert khalas.montant_lettres(0) == 'صفر دينار'
    assert khalas.montant_lettres('x') == 'صفر دينار'


# ═══ 10. شارتا الشاشة الرئيسيّة ═════════════════════════════════════════════

def test_accueil_sans_rien_en_attente(client):
    corps = client.get('/accueil').data.decode('utf-8')
    assert 'لا برامج متأخّرة ولا مستحقّات معلّقة' in corps
    assert 'كل البرامج منجزة' not in corps


def test_accueil_programme_en_retard(db, client):
    db.save_programme('interne', 'جانفي', 2025,
                      [{'titre': 'ت', 'grade': 'مقدم', 'nom_formateur': 'س', 'lieu_travail': '',
                        'date_formation': '2025-01-10', 'periode': '', 'lieu_formation': 'ق'}],
                      'ح', 'ن')
    corps = client.get('/accueil').data.decode('utf-8')
    assert 'برامج متأخّرة: <strong>1</strong>' in corps
    assert 'لا برامج متأخّرة' not in corps


# ═══ 15. حماية الدخول ═══════════════════════════════════════════════════════

def _client_anonyme():
    import app as application
    application.app.config.update(TESTING=True)
    return application.app.test_client()


def test_blocage_apres_cinq_echecs(db):
    db.add_user('agentx', 'secret123')
    c = _client_anonyme()
    for _ in range(4):
        r = c.post('/login', data={'username': 'agentx', 'password': 'faux'})
        assert 'غير صحيحة' in r.data.decode('utf-8')
    r = c.post('/login', data={'username': 'agentx', 'password': 'faux'})
    assert 'تمّ إيقاف هذا الحساب مؤقّتًا' in r.data.decode('utf-8')
    # même le BON mot de passe est refusé pendant le blocage
    r = c.post('/login', data={'username': 'agentx', 'password': 'secret123'})
    assert r.status_code == 200 and 'إيقاف' in r.data.decode('utf-8')
    assert any(j['action'].startswith('إيقاف مؤقّت للحساب') for j in db.get_journal(10))


def test_blocage_expire(db):
    db.add_user('agenty', 'secret123')
    for _ in range(5):
        db.noter_echec('agenty')
    assert db.minutes_de_blocage('agenty') in (4, 5)
    plus_tard = datetime.now() + timedelta(minutes=6)
    assert db.minutes_de_blocage('agenty', plus_tard) == 0


def test_succes_remet_le_compteur_a_zero(db):
    db.add_user('agentz', 'secret123')
    c = _client_anonyme()
    for _ in range(4):
        c.post('/login', data={'username': 'agentz', 'password': 'faux'})
    r = c.post('/login', data={'username': 'agentz', 'password': 'secret123'})
    assert r.status_code == 302
    conn = db.get_connection()
    try:
        assert conn.execute("SELECT echecs FROM users WHERE username='agentz'").fetchone()[0] == 0
    finally:
        conn.close()


def test_nom_inconnu_ne_plante_pas(db):
    c = _client_anonyme()
    for _ in range(6):
        r = c.post('/login', data={'username': 'personne', 'password': 'x'})
        assert r.status_code == 200


def test_reinitialisation_par_le_mushrif_leve_le_blocage(db, client):
    db.add_user('agentw', 'secret123')
    for _ in range(5):
        db.noter_echec('agentw')
    client.post('/api/users/changer-mdp', headers=H,
                json={'username': 'agentw', 'new_password': 'nouveau123'})
    assert db.minutes_de_blocage('agentw') == 0


def test_outil_de_recuperation_leve_le_blocage(db):
    from core import recuperation
    for _ in range(5):
        db.noter_echec('admin')
    recuperation.recuperer(db.DB_PATH)
    assert db.minutes_de_blocage('admin') == 0


def test_mushrif_huit_caracteres_au_changement(db, client):
    db.update_user_password('admin', 'secret123')
    r = client.post('/changer-mot-de-passe', data={'_csrf': 'jeton-de-test', 'actuel': 'secret123',
                                                   'nouveau': 'abc1234', 'confirmation': 'abc1234'})
    assert 'يجب أن تتكوّن من 8 رموز' in r.data.decode('utf-8')
    r = client.post('/changer-mot-de-passe', data={'_csrf': 'jeton-de-test', 'actuel': 'secret123',
                                                   'nouveau': 'abcd1234', 'confirmation': 'abcd1234'})
    assert r.status_code == 302


def test_simple_utilisateur_six_caracteres(db, monkeypatch):
    from tests.conftest import _client_flask
    db.update_config('installation_faite', '1')
    c = _client_flask(db, monkeypatch, 'user')
    r = c.post('/changer-mot-de-passe', data={'_csrf': 'jeton-de-test', 'actuel': 'secret123',
                                              'nouveau': 'abc123', 'confirmation': 'abc123'})
    assert r.status_code == 302


def test_reinitialiser_un_mushrif_exige_huit(db, client):
    db.add_user('adm2', 'motdepasse8', 'admin')
    r = client.post('/api/users/changer-mdp', headers=H,
                    json={'username': 'adm2', 'new_password': 'abc123'})
    assert r.status_code == 400


# ═══ 16. الختم الرقمي ═══════════════════════════════════════════════════════

@pytest.fixture()
def cachet(db):
    from core import chemins
    from PIL import Image
    chemin = os.path.join(chemins.dossier_donnees(), 'cachet.png')
    Image.new('RGBA', (60, 60), (200, 0, 0, 255)).save(chemin)
    yield chemin
    os.remove(chemin)


def test_cachet_desactive_par_defaut(db, cachet):
    import core.pdf_generator as pg
    assert pg._chemin_cachet(os.path.dirname(os.path.dirname(__file__))) is None


def test_cachet_active_par_le_mushrif(db, client, cachet):
    import core.pdf_generator as pg
    r = client.post('/parametres/cachet', data={'_csrf': 'jeton-de-test', 'cachet_actif': '1'})
    assert r.status_code == 302 and db.get_config()['cachet_actif'] == '1'
    assert pg._chemin_cachet(os.path.dirname(os.path.dirname(__file__))) == cachet
    client.post('/parametres/cachet', data={'_csrf': 'jeton-de-test'})
    assert db.get_config()['cachet_actif'] == '0'
    assert pg._chemin_cachet('/') is None


def test_cachet_reserve_au_mushrif(db, monkeypatch):
    from tests.conftest import _client_flask
    db.update_config('installation_faite', '1')
    c = _client_flask(db, monkeypatch, 'user')
    assert c.post('/parametres/cachet', data={'_csrf': 'jeton-de-test',
                                             'cachet_actif': '1'}).status_code == 403
    assert db.get_config().get('cachet_actif', '0') != '1'


def test_cachet_appose_dans_le_pdf_quand_actif(db, client, cachet, programme):
    db.update_config('cachet_actif', '1')
    db.verrouiller_lettre(programme['lettre_id'], 'interne')
    avec = client.get(f"/lettre/{programme['lettre_id']}/generer").data
    db.update_config('cachet_actif', '0')
    sans = client.get(f"/lettre/{programme['lettre_id']}/generer").data
    assert b'/Subtype /Image' in avec or avec.count(b'/Image') > sans.count(b'/Image')
    assert len(avec) > len(sans)


def test_page_parametres_carte_cachet(db, client):
    corps = client.get('/parametres').data.decode('utf-8')
    assert 'الختم الرقمي على الوثائق' in corps and 'cachet.png' in corps
