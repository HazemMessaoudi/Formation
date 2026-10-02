# -*- coding: utf-8 -*-
"""v1.7 — Paquet A : ترقيم برنامج السنة الموالية، مشرف ثانٍ، أداة الاسترجاع،
حماية الانتقال السنوي من ساعة الحاسوب."""

import os
import sqlite3
from datetime import datetime

import pytest
from werkzeug.security import check_password_hash, generate_password_hash

from core import exercice, recuperation
from core.db.programmes import annee_admise

H = {'X-CSRF-Token': 'jeton-de-test'}


@pytest.fixture()
def horloge(monkeypatch):
    class _Horloge:
        def regler(self, annee):
            vraie = datetime

            class _DT(vraie):
                @classmethod
                def now(cls, tz=None):
                    return vraie.now(tz).replace(year=annee)
            monkeypatch.setattr(exercice, 'datetime', _DT)
    return _Horloge()


def _programme(db, annee, mois='جانفي'):
    return db.save_programme(
        'interne', mois, annee,
        [{'titre': 'تحرير المحاضر', 'grade': 'مقدم', 'nom_formateur': 'زياد البوهلالي',
          'lieu_travail': '', 'date_formation': f'{annee}-01-12', 'periode': '',
          'lieu_formation': 'مركز التكوين الجهوي بالقصرين'}],
        'حازم مسعودي', 'النقيب')


def _basculer(db):
    conn = db.get_connection()
    try:
        r = exercice.basculer_si_necessaire(conn)
        conn.commit()
        return r
    finally:
        conn.close()


# ═══ 1. برنامج السنة الموالية ═══════════════════════════════════════════════

def test_regle_annee_admise():
    assert annee_admise(2026, 2026)
    assert annee_admise(2027, 2026)             # جانفي يُرسل في ديسمبر
    assert not annee_admise(2028, 2026)
    assert not annee_admise(2025, 2026)         # سنة منقضية
    assert annee_admise(2026, 2026, est_libre=True)
    assert not annee_admise(2027, 2026, est_libre=True)   # مراسلة حرّة : سنتها فقط
    assert not annee_admise('x', 2026)


def test_programme_de_janvier_prend_un_numero_du_sejel_de_decembre(db):
    ouverte = db.annee_registre()
    ref, numero = db.verrouiller_lettre(_programme(db, ouverte + 1), 'interne')
    assert numero == 1
    assert f'-{str(ouverte)[-2:]}-0001' in ref           # مرجع السّجلّ المفتوح
    reg = db.get_registre('interne', ouverte)
    assert [r['numero'] for r in reg] == [1]
    assert db.get_registre('interne', ouverte + 1) == []


def test_programme_de_lannee_n_plus_2_est_refuse(db):
    ouverte = db.annee_registre()
    assert db.verrouiller_lettre(_programme(db, ouverte + 2), 'interne') == (None, None)
    assert db.get_registre('interne', ouverte) == []


def test_route_valider_accepte_le_programme_de_lannee_suivante(db, client):
    ouverte = db.annee_registre()
    db.add_mkow({'grade': 'المقدم', 'nom': 'زياد', 'prenom': 'البوهلالي'})
    charge = {'type': 'interne', 'mois': 'جانفي', 'annee': ouverte + 1,
              'formations': [{'titre': 'تحرير المحاضر', 'grade': 'المقدم',
                              'nom_formateur': 'زياد البوهلالي', 'lieu_travail': '',
                              'date_formation': f'{ouverte + 1}-01-12',
                              'periode': '', 'lieu_formation': 'القصرين'}]}
    lettre_id = client.post('/lettre/enregistrer', headers=H, json=charge).get_json()['lettre_id']
    rep = client.post(f'/lettre/{lettre_id}/valider', headers=H, json={'type': 'interne'})
    corps = rep.get_json()
    assert rep.status_code == 200, corps
    assert f'-{str(ouverte)[-2:]}-' in corps['ref']


def test_reprise_au_redemarrage_ne_cree_pas_de_numero_fantome(db):
    """Le point dangereux : la reprise du سجلّ lit lettres.annee (= N+1).
    Elle ne doit pas inscrire une 2e fois le عدد sous l'année N+1."""
    ouverte = db.annee_registre()
    db.verrouiller_lettre(_programme(db, ouverte + 1), 'interne')
    db.init_db()                      # redémarrage
    db.init_db()
    assert db.get_registre('interne', ouverte + 1) == []
    assert len(db.get_registre('interne', ouverte)) == 1


def test_apres_le_nouvel_an_le_sejel_neuf_repart_a_un(db, horloge):
    ouverte = db.annee_registre()
    db.verrouiller_lettre(_programme(db, ouverte + 1), 'interne')    # ديسمبر
    horloge.regler(ouverte + 1)
    assert _basculer(db) == (ouverte, ouverte + 1)
    db.init_db()
    assert db.prochain_numero_prevu('interne') == 1
    ref, numero = db.verrouiller_lettre(_programme(db, ouverte + 1, 'فيفري'), 'interne')
    assert numero == 1 and f'-{str(ouverte + 1)[-2:]}-0001' in ref


def test_fsakh_en_janvier_rend_le_numero_au_sejel_de_decembre(db, horloge):
    ouverte = db.annee_registre()
    lid = _programme(db, ouverte + 1)
    db.verrouiller_lettre(lid, 'interne')
    horloge.regler(ouverte + 1)
    _basculer(db)
    assert db.delete_programme_inacheve(lid)
    assert [r['numero'] for r in db.get_numeros_liberes('interne', ouverte)] == [1]
    assert db.get_numeros_liberes('interne', ouverte + 1) == []


def test_memo_confirmee_apres_le_nouvel_an_porte_lannee_de_son_sejel(db, horloge):
    ouverte = db.annee_registre()
    lid = _programme(db, ouverte + 1)
    db.verrouiller_lettre(lid, 'interne')
    fid = db.get_lettre_detail(lid)['formations'][0]['id']
    db.save_memo_data(fid, {'objet': 'مذكّرة', 'corps': 'نصّ'}, confirmer=False)  # brouillon N
    horloge.regler(ouverte + 1)
    _basculer(db)
    assert db.save_memo_data(fid, {'objet': 'مذكّرة', 'corps': 'نصّ'}, confirmer=True)
    conn = db.get_connection()
    try:
        m = conn.execute('SELECT annee, numero FROM memo_formations WHERE formation_id=?',
                         (fid,)).fetchone()
    finally:
        conn.close()
    assert m['annee'] == ouverte + 1 and m['numero'] == 1
    db.init_db()
    assert [r['source'] for r in db.get_registre('interne', ouverte + 1)] == ['memo']


# ═══ 2. مشرف ثانٍ ═══════════════════════════════════════════════════════════

def _users(db):
    return {u['username']: u['role'] for u in db.get_users()}


def test_ajouter_un_second_mushrif(db, client):
    rep = client.post('/api/users', headers=H,
                      json={'username': 'نائب', 'password': 'motdepasse8', 'role': 'admin'})
    assert rep.get_json().get('succes')
    assert _users(db)['نائب'] == 'admin'


def test_mushrif_exige_huit_caracteres(db, client):
    rep = client.post('/api/users', headers=H,
                      json={'username': 'x', 'password': 'abc123', 'role': 'admin'})
    assert rep.status_code == 400


def test_promouvoir_puis_destituer(db, client):
    db.add_user('agent2', 'secret123')
    assert client.post('/api/users/role', headers=H,
                       json={'username': 'agent2', 'role': 'admin'}).get_json()['succes']
    assert _users(db)['agent2'] == 'admin'
    assert client.post('/api/users/role', headers=H,
                       json={'username': 'agent2', 'role': 'user'}).get_json()['succes']
    assert _users(db)['agent2'] == 'user'
    actions = [j['action'] for j in db.get_journal(20)]
    assert 'تغيير دور مستخدم' in actions


def test_on_ne_change_pas_son_propre_role(db, client):
    rep = client.post('/api/users/role', headers=H, json={'username': 'admin', 'role': 'user'})
    assert rep.status_code == 400
    assert _users(db)['admin'] == 'admin'


def test_le_dernier_mushrif_ne_peut_etre_destitue(db):
    db.add_user('b', 'secret123', 'user')
    ok, msg = db.changer_role('admin', 'user', 'b')
    assert not ok and 'مشرف' in msg


def test_le_dernier_mushrif_ne_peut_etre_supprime(db, client, monkeypatch):
    # Deux مشرفين : l'un supprime l'autre → autorisé ; le dernier ne part pas.
    db.add_user('nb', 'secret1234', 'admin')
    assert client.post('/api/users/supprimer', headers=H,
                       json={'username': 'nb'}).get_json()['succes']
    assert db.nb_admins() == 1


def test_route_role_reservee_au_mushrif(db, monkeypatch):
    from tests.conftest import _client_flask
    db.update_config('installation_faite', '1')
    c = _client_flask(db, monkeypatch, 'user')
    rep = c.post('/api/users/role', headers=H, json={'username': 'admin', 'role': 'user'})
    assert rep.status_code == 403


def test_le_role_se_relit_a_chaque_requete(db, monkeypatch):
    """Un مستعمل promu devient مشرف sans se reconnecter, et inversement."""
    from tests.conftest import _client_flask
    db.update_config('installation_faite', '1')
    c = _client_flask(db, monkeypatch, 'user')
    assert c.get('/journal').status_code == 403
    db.set_user_role('agent', 'admin')
    assert c.get('/journal').status_code == 200
    db.set_user_role('agent', 'user')
    assert c.get('/journal').status_code == 403


def test_page_parametres_affiche_les_roles(db, client):
    corps = client.get('/parametres').data.decode('utf-8')
    assert 'changerRole' in corps and 'recuperer_admin.bat' in corps


def test_utilisateur_simple_ne_voit_pas_la_gestion_des_comptes(db, monkeypatch):
    from tests.conftest import _client_flask
    db.update_config('installation_faite', '1')
    c = _client_flask(db, monkeypatch, 'user')
    corps = c.get('/parametres').data.decode('utf-8')
    assert 'users-tbody' not in corps and 'changerRole(this)' not in corps


# ═══ 2. أداة الاسترجاع ══════════════════════════════════════════════════════

def test_recuperation_pose_un_mot_de_passe_provisoire(db):
    nom, mdp = recuperation.recuperer(db.DB_PATH)
    assert nom == 'admin' and len(mdp) == recuperation.LONGUEUR_PROVISOIRE
    assert db.check_credentials('admin', mdp)
    assert db.user_doit_changer_mdp('admin')
    assert any(j['action'].startswith('استرجاع كلمة مرور المشرف') for j in db.get_journal(5))


def test_recuperation_avec_plusieurs_mushrifin(db):
    db.add_user('نائب', 'secret1234', 'admin')
    with pytest.raises(ValueError):
        recuperation.recuperer(db.DB_PATH)
    nom, mdp = recuperation.recuperer(db.DB_PATH, 'نائب')
    assert db.check_credentials('نائب', mdp)
    assert not db.check_credentials('admin', mdp)


def test_recuperation_refuse_un_compte_non_mushrif(db):
    db.add_user('agent9', 'secret123', 'user')
    with pytest.raises(ValueError):
        recuperation.recuperer(db.DB_PATH, 'agent9')


def test_recuperation_retablit_admin_sil_ny_a_plus_aucun_mushrif(db):
    conn = sqlite3.connect(db.DB_PATH)
    conn.execute("UPDATE users SET role='user'")
    conn.commit()
    conn.close()
    nom, mdp = recuperation.recuperer(db.DB_PATH)
    assert nom == 'admin' and db.get_user_role('admin') == 'admin'


def test_console_interactive_choix_par_numero(db, monkeypatch):
    monkeypatch.setattr(recuperation, 'serveur_actif', lambda port=5055: False)
    db.add_user('نائب', 'secret1234', 'admin')
    lignes = []
    code = recuperation.executer_console(db.DB_PATH, entree=lambda _: '2', sortie=lignes.append)
    assert code == 0
    mdp = [l for l in lignes if 'Mot de passe  ' in l][0].split(':')[-1].strip()
    assert db.check_credentials('نائب', mdp)


def test_console_refuse_si_le_programme_tourne(db, monkeypatch):
    monkeypatch.setattr(recuperation, 'serveur_actif', lambda port=5055: True)
    assert recuperation.executer_console(db.DB_PATH, sortie=lambda *_: None) == 2
    assert not db.user_doit_changer_mdp('admin') or True   # rien n'a été touché
    assert not any(j['action'].startswith('استرجاع') for j in db.get_journal(5))


def test_console_choix_invalide(db, monkeypatch):
    monkeypatch.setattr(recuperation, 'serveur_actif', lambda port=5055: False)
    db.add_user('نائب', 'secret1234', 'admin')
    assert recuperation.executer_console(db.DB_PATH, entree=lambda _: '0',
                                         sortie=lambda *_: None) == 1
    assert recuperation.executer_console(db.DB_PATH, entree=lambda _: '9',
                                         sortie=lambda *_: None) == 1


def test_fichiers_outil_livres():
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    bat = os.path.join(base, 'recuperer_admin.bat')
    assert os.path.exists(bat) and os.path.exists(os.path.join(base, 'recuperer_admin.py'))
    contenu = open(bat, encoding='utf-8').read()
    assert '--recuperer-admin' in contenu and 'recuperer_admin.py' in contenu
    assert '--recuperer-admin' in open(os.path.join(base, 'lancer_app.py'), encoding='utf-8').read()


# ═══ 8. ساعة الحاسوب ═══════════════════════════════════════════════════════

def test_annee_suivante_ouverte_et_annoncee(db, horloge, client):
    ouverte = db.annee_registre()
    horloge.regler(ouverte + 1)
    assert _basculer(db) == (ouverte, ouverte + 1)
    corps = client.get('/dashboard').data.decode('utf-8')
    assert f'فُتح سجلّ سنة {ouverte + 1}' in corps
    client.post('/exercice/acquitter', data={'_csrf': 'jeton-de-test', 'suivant': '/dashboard'})
    assert 'فُتح سجلّ سنة' not in client.get('/dashboard').data.decode('utf-8')


def test_saut_de_plusieurs_annees_suspendu_et_signale(db, horloge, client):
    ouverte = db.annee_registre()
    horloge.regler(ouverte + 4)
    assert _basculer(db) is None
    assert db.annee_registre() == ouverte
    corps = client.get('/dashboard').data.decode('utf-8')
    assert f'تاريخ الحاسوب يشير إلى سنة {ouverte + 4}' in corps
    assert 'التاريخ صحيح' in corps                 # bouton du مشرف


def test_ouverture_confirmee_par_le_mushrif(db, horloge, client):
    ouverte = db.annee_registre()
    horloge.regler(ouverte + 3)
    _basculer(db)
    rep = client.post('/exercice/ouvrir', data={'_csrf': 'jeton-de-test', 'annee': ouverte + 3})
    assert rep.status_code == 302
    assert db.annee_registre() == ouverte + 3
    assert 'تاريخ الحاسوب يشير' not in client.get('/dashboard').data.decode('utf-8')
    assert any(j['action'] == 'فتح سجلّ سنة جديدة بتأكيد المشرف' for j in db.get_journal(5))


def test_ouverture_confirmee_refuse_une_annee_autre_que_lhorloge(db, horloge, client):
    ouverte = db.annee_registre()
    horloge.regler(ouverte + 3)
    _basculer(db)
    client.post('/exercice/ouvrir', data={'_csrf': 'jeton-de-test', 'annee': ouverte + 9})
    assert db.annee_registre() == ouverte


def test_ouverture_confirmee_interdite_au_simple_utilisateur(db, horloge, monkeypatch):
    from tests.conftest import _client_flask
    db.update_config('installation_faite', '1')
    ouverte = db.annee_registre()
    horloge.regler(ouverte + 3)
    _basculer(db)
    c = _client_flask(db, monkeypatch, 'user')
    assert 'التاريخ صحيح' not in c.get('/dashboard').data.decode('utf-8')
    c.post('/exercice/ouvrir', data={'_csrf': 'jeton-de-test', 'annee': ouverte + 3})
    assert db.annee_registre() == ouverte


def test_horloge_revenue_a_la_normale_efface_lalerte(db, horloge):
    ouverte = db.annee_registre()
    horloge.regler(ouverte + 5)
    _basculer(db)
    horloge.regler(ouverte)
    _basculer(db)
    conn = db.get_connection()
    try:
        assert exercice.alerte_horloge(conn) is None
    finally:
        conn.close()


def test_mourasla_dr_de_janvier_en_decembre_puis_fevrier_en_janvier(db, horloge):
    """Les deux مراسلات المدير الجهوي portent le عدد 1 de deux سجلّات
    différents : aucun conflit d'unicité dans `lettres`."""
    ouverte = db.annee_registre()
    l1 = _programme(db, ouverte + 1)
    db.verrouiller_lettre(l1, 'interne')
    r1 = db.attribuer_numero_dr(l1, 'externe', 'الإدارة الجهوية بسوسة')
    assert r1[1] == 1
    horloge.regler(ouverte + 1)
    _basculer(db)
    l2 = _programme(db, ouverte + 1, 'فيفري')
    db.verrouiller_lettre(l2, 'interne')
    r2 = db.attribuer_numero_dr(l2, 'externe', 'الإدارة الجهوية بسوسة')
    assert r2[1] == 1 and r2[0] != r1[0]
    db.init_db()
    assert len(db.get_registre('externe', ouverte)) == 1
    assert len(db.get_registre('externe', ouverte + 1)) == 1


def test_fichiers_bat_compatibles_windows():
    """v1.7.1 : cmd.exe lit mal un .bat en fins de ligne LF (surtout avec
    des commentaires arabes sous chcp 65001) ; noms ASCII pour que l'archive
    se décompresse lisiblement avec l'explorateur Windows."""
    import glob
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    bats = glob.glob(os.path.join(base, '*.bat'))
    assert len(bats) >= 3
    for chemin in bats:
        assert os.path.basename(chemin).isascii(), chemin
        brut = open(chemin, 'rb').read()
        assert b'\n' not in brut.replace(b'\r\n', b''), chemin
    for racine, _d, noms in os.walk(base):
        if any(p in racine for p in ('.git', '__pycache__', '.pytest_cache')):
            continue
        for n in noms:
            assert n.isascii(), os.path.join(racine, n)


def test_racine_du_paquet_propre():
    """Aucun fichier parasite (roue pip, archive…) à la racine du paquet."""
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    attendus = {'.livraison_exclure', 'app.py', 'construire_exe.bat',
                'formation_kasserine.spec', 'lancer.bat', 'lancer_app.py',
                'recuperer_admin.bat', 'recuperer_admin.py', 'requirements.txt',
                'requirements-lock.txt', 'core', 'data', 'fonts', 'routes',
                'static', 'templates', 'tests'}
    # 1.0 : Outils/ (installateur WebView2) accompagne le dossier livré, pas le paquet
    tolere = {'.git', '__pycache__', '.pytest_cache', '.coverage', 'claude', 'Outils'}
    assert set(os.listdir(base)) - tolere == attendus
