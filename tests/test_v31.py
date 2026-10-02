# -*- coding: utf-8 -*-
"""V3.1 — النسخة المرآة, استرجاع المنظومة, الأرشيف السّنوي, إشعارات المشرف."""
import os
import sqlite3
import stat

import pytest


@pytest.fixture()
def isole(tmp_path, monkeypatch):
    """Miroir et data/ propres à chaque test (la clé d'installation dépend
    du chemin de data/)."""
    monkeypatch.setenv('FK_MIROIR_DIR', str(tmp_path / 'miroir'))
    monkeypatch.setenv('FK_DATA_DIR', str(tmp_path / 'data'))
    from core import miroir
    monkeypatch.setitem(miroir.ETAT, 'secours', '')
    return tmp_path


def _db_path():
    import core.database as database
    return database.DB_PATH


# ═══ 1 أ — écriture de la miroir ═════════════════════════════════════════════

def test_miroir_ecrite_hors_du_programme_et_saine(db, isole):
    from core import miroir
    assert miroir.ecrire_miroir() == 1
    d = miroir.dossiers_miroir()[0]
    assert d.startswith(str(isole / 'miroir'))
    f = os.path.join(d, miroir.NOM_MIROIR)
    assert miroir.base_saine(f)
    assert os.path.isfile(os.path.join(d, miroir.NOM_INFO))
    miroir.ecrire_miroir()                                    # 2ᵉ écriture : rotation
    assert os.path.isfile(os.path.join(d, miroir.NOM_PRECEDENT))


def test_miroir_propre_a_chaque_installation(isole):
    from core import miroir
    assert miroir.cle_installation('/a/data') != miroir.cle_installation('/b/data')


def test_emplacement_supplementaire(db, isole):
    from core import miroir, chemins
    with pytest.raises(ValueError):
        miroir.definir_emplacement(str(isole / 'inexistant'))
    with pytest.raises(ValueError):                       # dans le dossier du programme
        miroir.definir_emplacement(chemins.dossier_application())
    autre = isole / 'disque_d'
    autre.mkdir()
    miroir.definir_emplacement(str(autre))
    assert len(miroir.dossiers_miroir()) == 2
    assert miroir.ecrire_miroir() == 2
    assert miroir.base_saine(os.path.join(miroir.dossiers_miroir()[1], miroir.NOM_MIROIR))
    miroir.definir_emplacement('')
    assert len(miroir.dossiers_miroir()) == 1


# ═══ 1 ب — base absente : restauration automatique ═══════════════════════════

def test_base_absente_restauree_au_demarrage(db, isole):
    from core import miroir
    db.update_config('nom_centre', 'مركز وهمي')
    miroir.ecrire_miroir()
    os.remove(_db_path())
    assert miroir.demarrer(_db_path(), db.init_db) == 'restauree'
    assert db.get_config()['nom_centre'] == 'مركز وهمي'
    marque = miroir.lire_marque_restauration()
    assert marque and marque['motif'] == 'absente' and marque['origine'] == 'miroir'
    assert any(j['action'] == 'استرجاع آليّ للقاعدة من النسخة المرآة' for j in db.get_journal(5))
    miroir.effacer_marque_restauration()
    assert miroir.lire_marque_restauration() is None


def test_base_absente_sans_copie_reste_neuve(db, isole):
    from core import miroir
    os.remove(_db_path())
    assert miroir.demarrer(_db_path(), db.init_db) == 'neuve'
    assert os.path.isfile(_db_path())


def test_base_absente_repli_sur_sauvegarde(db, isole):
    from core import miroir
    assert db.backup_db()                                 # data/backups seulement
    os.remove(_db_path())
    assert miroir.demarrer(_db_path(), db.init_db) == 'restauree'
    assert miroir.lire_marque_restauration()['origine'] == 'sauvegarde'


# ═══ 1 ج — base abîmée : rien n'est écrasé, page de restauration ══════════════

def _abimer(chemin):
    with open(chemin, 'r+b') as fh:
        fh.seek(0)
        fh.write(b'ceci n est plus une base sqlite' * 4)


def test_base_abimee_non_ecrasee(db, isole):
    from core import miroir
    miroir.ecrire_miroir()
    _abimer(_db_path())
    avant = open(_db_path(), 'rb').read()
    assert miroir.demarrer(_db_path(), db.init_db) == 'endommagee'
    assert miroir.ETAT['secours'] == 'endommagee'
    assert open(_db_path(), 'rb').read() == avant


def _mdp_admin(db):
    db.update_user_password('admin', 'secret123')
    conn = db.get_connection()
    try:
        conn.execute("UPDATE users SET doit_changer_mdp=0 WHERE username='admin'")
        conn.commit()
    finally:
        conn.close()


def test_page_de_secours_exige_un_admin_de_la_copie(db, client, isole):
    from core import miroir
    _mdp_admin(db)
    miroir.ecrire_miroir()
    copie = miroir.copies_disponibles()[0]['chemin']
    assert miroir.verifier_admin_dans(copie, 'admin', 'secret123')
    assert not miroir.verifier_admin_dans(copie, 'admin', 'faux')
    miroir.ETAT['secours'] = 'endommagee'
    r = client.get('/accueil')
    assert r.status_code == 302 and r.headers['Location'].endswith('/secours')
    assert client.get('/api/grades').status_code == 503
    html = client.get('/secours').get_data(as_text=True)
    assert 'قاعدة البيانات تالفة' in html and 'النسخة المرآة' in html
    d = {'_csrf': 'jeton-de-test', 'copie': copie, 'utilisateur': 'admin'}
    client.post('/secours/restaurer', data=dict(d, mot_de_passe='faux'))
    assert miroir.ETAT['secours'] == 'endommagee'
    r = client.post('/secours/restaurer', data=dict(d, mot_de_passe='secret123'))
    assert r.status_code == 302 and miroir.ETAT['secours'] == ''
    remplacees = os.listdir(os.path.join(os.path.dirname(_db_path()), 'backups'))
    assert any(n.startswith('remplacee_') for n in remplacees)
    assert client.get('/secours').status_code == 302      # plus de secours


def test_restauration_manuelle_depuis_les_parametres(db, client, isole):
    from core import miroir
    db.update_config('nom_centre', 'قبل')
    miroir.ecrire_miroir()
    db.update_config('nom_centre', 'بعد')
    copie = miroir.copies_disponibles(avec_sauvegardes=False)[0]['chemin']
    html = client.get('/parametres').get_data(as_text=True)
    assert 'id="carteMiroir"' in html and 'استرجاع من المرآة' in html
    r = client.post('/parametres/miroir/restaurer', data={'_csrf': 'jeton-de-test', 'copie': copie})
    assert r.status_code == 302
    assert db.get_config()['nom_centre'] == 'قبل'
    r = client.post('/parametres/miroir/restaurer', data={'_csrf': 'jeton-de-test',
                                                         'copie': '/nulle/part.db'})
    assert db.get_config()['nom_centre'] == 'قبل'


# ═══ 2 ب — الأرشيف السّنوي ═════════════════════════════════════════════════════

def _programme(db):
    annee = db.annee_registre()
    lid = db.save_programme('interne', 'فيفري', annee, [
        {'titre': 'دورة وهمية', 'grade': 'المقدم', 'nom_formateur': 'مكوّن وهمي',
         'lieu_travail': '', 'date_formation': f'{annee}-02-12', 'periode': 'صباحا',
         'lieu_formation': 'قاعة وهمية'}], 'مسؤول وهمي', 'النقيب')
    db.verrouiller_lettre(lid, 'interne')
    return annee


def test_archive_annuelle_a_l_ouverture_d_une_annee(db, isole):
    from core import miroir
    annee = _programme(db)
    assert miroir.creer_archive_si_necessaire() is None      # année en cours : rien
    db.update_config('annee_exercice', str(annee + 1))
    chemin = miroir.creer_archive_si_necessaire()
    assert chemin and chemin.endswith(f'archive_{annee}.db') and miroir.base_saine(chemin)
    assert not os.stat(chemin).st_mode & stat.S_IWUSR       # lecture seule
    assert miroir.creer_archive_si_necessaire() is None      # une seule fois
    assert [a['annee'] for a in miroir.archives()] == [annee]
    assert os.path.isfile(os.path.join(miroir.dossiers_miroir()[0], 'archives', f'archive_{annee}.db'))
    # les données restent dans la base principale
    conn = sqlite3.connect(_db_path())
    try:
        assert conn.execute('SELECT COUNT(*) FROM registre WHERE annee=?', (annee,)).fetchone()[0]
    finally:
        conn.close()
    os.chmod(chemin, stat.S_IWUSR | stat.S_IRUSR)


def test_archive_telechargeable(db, client, isole):
    from core import miroir
    annee = _programme(db)
    db.update_config('annee_exercice', str(annee + 1))
    chemin = miroir.creer_archive_si_necessaire()
    r = client.get(f'/parametres/archive?annee={annee}')
    assert r.status_code == 200 and r.data[:15] == b'SQLite format 3'
    assert client.get('/parametres/archive?annee=1999').status_code == 302
    os.chmod(chemin, stat.S_IWUSR | stat.S_IRUSR)


# ═══ 3 — إشعارات المشرف العام ═══════════════════════════════════════════════

def test_colonne_notif_vu(db):
    conn = db.get_connection()
    try:
        assert 'notif_vu' in {c['name'] for c in conn.execute('PRAGMA table_info(users)')}
    finally:
        conn.close()


def test_notifications_des_autres_utilisateurs(db, client):
    from core import notifications as n
    assert n.resume('admin')['nb'] == 0                     # point de départ
    db.journaliser('agent', 'تحيين برنامج تكوين', 'lettre_id=1')
    db.journaliser('agent', 'طباعة شهادات المشاركة', 'x')   # pas un تحيين
    db.journaliser('agent', 'دخول إلى النظام')               # pas un تحيين
    db.journaliser('admin', 'تعديل الإعدادات', 'config')     # sa propre action
    db.journaliser('admin2', 'حذف مكوّن', '7')               # un autre مشرف
    r = n.resume('admin')
    assert r['nb'] == 2 and [e['action'] for e in r['liste']] == ['حذف مكوّن', 'تحيين برنامج تكوين']
    assert r['auteurs'] == ['admin2', 'agent']
    assert 'العدد: 2' in n.message_connexion('admin')
    n.marquer_lues('admin')
    assert n.resume('admin')['nb'] == 0 and n.message_connexion('admin') == ''


def test_cloche_et_page_des_notifications(db, client):
    from core import notifications as n
    n.resume('admin')
    db.journaliser('agent', 'تسجيل دورة نهائيًّا في المنظومة', 'formation_id=3')
    html = client.get('/programmes').get_data(as_text=True)
    assert 'id="notifNav"' in html and 'class="notif-compte">1<' in html
    assert 'تسجيل دورة نهائيًّا في المنظومة' in html
    assert '🔔 تحيينات جديدة' in client.get('/accueil').get_data(as_text=True)
    page = client.get('/notifications').get_data(as_text=True)
    assert 'تسجيل دورة نهائيًّا في المنظومة' in page and 'تمّت القراءة' in page
    r = client.post('/notifications/lues', data={'_csrf': 'jeton-de-test', 'suivant': '/programmes'})
    assert r.status_code == 302 and r.headers['Location'].endswith('/programmes')
    assert 'class="notif-compte"' not in client.get('/programmes').get_data(as_text=True)


def test_pas_de_cloche_pour_un_simple_utilisateur(db, monkeypatch):
    from tests.conftest import _client_flask
    db.update_config('installation_faite', '1')
    c = _client_flask(db, monkeypatch, 'user')
    assert 'id="notifNav"' not in c.get('/programmes').get_data(as_text=True)
    assert c.get('/notifications').status_code == 403


def test_message_a_la_connexion_du_mashrif(db, client):
    import app as application
    from core import notifications as n
    n.resume('admin')
    db.journaliser('agent', 'إنجاز المستحقّات المالية', 'formation_id=2')
    _mdp_admin(db)
    c = application.app.test_client()
    r = c.post('/login', data={'username': 'admin', 'password': 'secret123'}, follow_redirects=True)
    assert 'تحيينات جديدة منذ آخر اطّلاع لك' in r.get_data(as_text=True)
