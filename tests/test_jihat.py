# -*- coding: utf-8 -*-
"""المرحلة ج — الجهات المرجعيّة، خانة الجهة، ومسار التّرقية من إصدار سابق.

الاختبار المركزي هنا ليس اختبار ميزة جديدة بل اختبار عدم فقدان بيان:
نموذج قديم لا يعرض خانة `jiha_marjiiya` يجب ألّا يمحوها. هذا النّوع من
الأعطاب لا يُلاحَظ إلّا بعد أشهر، حين يكتشف المستعمل أنّ جهات مكوّنيه
اختفت دون أن يمسّها أحد.
"""

import os
import sqlite3
import tempfile

import pytest

from core import regions


def _creer_mkow(db, **champs):
    """Crée un مكوّن et rend son identifiant.

    `add_mkow` rend un booléen, pas un id — les vues n'en ont jamais eu besoin.
    Les tests, si : on relit la liste pour retrouver la fiche qu'on vient
    d'écrire plutôt que de supposer qu'elle porte le numéro 1.
    """
    assert db.add_mkow(champs) is True
    return db.get_mkowin()[-1]['id']


# ─── الغرس ───────────────────────────────────────────────────────────────────

def test_semis_pose_les_vingt_quatre_administrations(db):
    noms = db.noms_jihat()
    assert len(noms) == regions.NB_GOUVERNORATS
    assert 'الإدارة الجهويّة للدّيوانة بالقصرين' in noms
    assert 'الإدارة الجهويّة للدّيوانة ببنزرت' in noms


def test_semis_idempotent(db):
    """`init_db` s'exécute à chaque démarrage : deux passages, pas de doublon."""
    avant = len(db.noms_jihat())
    db.init_db()
    db.init_db()
    assert len(db.noms_jihat()) == avant


def test_semis_ajoute_les_jihat_propres_du_centre(db):
    db.update_config('admin_regionale', 'الإدارة الجهويّة للدّيوانة بالقصرين')
    db.update_config('unite_garde', 'الوحدة الرّابعة للحرس الدّيواني بقفصة')
    db.semer_jihat()

    noms = db.noms_jihat()
    # L'إدارة du centre figure déjà dans les 24 : pas de doublon.
    assert len(noms) == regions.NB_GOUVERNORATS + 1
    assert 'الوحدة الرّابعة للحرس الدّيواني بقفصة' in noms

    gardes = db.get_jihat(regions.TYPE_GARDE)
    assert [g['nom'] for g in gardes] == ['الوحدة الرّابعة للحرس الدّيواني بقفصة']


def test_semis_admin_hors_liste_est_ajoutee(db):
    """Un centre dont l'إدارة s'écrit autrement doit tout de même la trouver."""
    db.update_config('admin_regionale', 'الإدارة الجهويّة للدّيوانة بالوسط الغربي')
    db.semer_jihat()
    assert 'الإدارة الجهويّة للدّيوانة بالوسط الغربي' in db.noms_jihat()


# ─── الإضافة والحذف ──────────────────────────────────────────────────────────

def test_add_jiha(db):
    assert db.add_jiha('وحدة جديدة للحرس الدّيواني', regions.TYPE_GARDE) is True
    assert 'وحدة جديدة للحرس الدّيواني' in db.noms_jihat()


def test_add_jiha_doublon_refuse(db):
    db.add_jiha('جهة مكرّرة', regions.TYPE_AUTRE)
    assert db.add_jiha('جهة مكرّرة', regions.TYPE_AUTRE) is False


def test_add_jiha_meme_nom_deux_familles(db):
    """L'unicité porte sur (type, nom) : le même libellé peut exister deux fois."""
    assert db.add_jiha('جهة مزدوجة', regions.TYPE_GARDE) is True
    assert db.add_jiha('جهة مزدوجة', regions.TYPE_AUTRE) is True


def test_add_jiha_vide_refuse(db):
    assert db.add_jiha('   ', regions.TYPE_AUTRE) is False


def test_add_jiha_type_inconnu_devient_autre(db):
    db.add_jiha('جهة بصنف مجهول', 'n-importe-quoi')
    autres = [j['nom'] for j in db.get_jihat(regions.TYPE_AUTRE)]
    assert 'جهة بصنف مجهول' in autres


def test_delete_jiha_ne_touche_a_aucune_fiche(db):
    """Retirer une جهة de la liste ne réécrit pas l'historique."""
    db.add_jiha('جهة ستُحذف', regions.TYPE_AUTRE)
    jiha = [j for j in db.get_jihat() if j['nom'] == 'جهة ستُحذف'][0]

    mkow_id = _creer_mkow(db, nom='المكوّن', jiha_marjiiya='جهة ستُحذف')
    assert db.delete_jiha(jiha['id']) is True

    assert 'جهة ستُحذف' not in db.noms_jihat()
    assert db.get_mkow(mkow_id)['jiha_marjiiya'] == 'جهة ستُحذف'


def test_get_jihat_groupees_couvre_les_trois_familles(db):
    groupes = db.get_jihat_groupees()
    assert [g['type'] for g in groupes] == list(regions.TYPES)
    par_type = {g['type']: len(g['jihat']) for g in groupes}
    assert par_type[regions.TYPE_ADMIN] == regions.NB_GOUVERNORATS
    assert par_type[regions.TYPE_GARDE] == 0
    assert par_type[regions.TYPE_AUTRE] == 0


# ─── خانة الجهة في بطاقة المكوّن ─────────────────────────────────────────────

def test_add_mkow_enregistre_la_jiha(db):
    mkow_id = _creer_mkow(db, nom='البوهلالي زياد',
                          jiha_marjiiya='الإدارة الجهويّة للدّيوانة بالقصرين')
    assert db.get_mkow(mkow_id)['jiha_marjiiya'] == 'الإدارة الجهويّة للدّيوانة بالقصرين'


def test_update_mkow_partiel_preserve_les_champs_absents(db):
    mkow_id = _creer_mkow(db, nom='البوهلالي زياد', prenom='زياد',
                          jiha_marjiiya='الإدارة الجهويّة للدّيوانة بالقصرين')
    db.update_mkow(mkow_id, {'prenom': 'زياد المحيَّن'})

    mkow = db.get_mkow(mkow_id)
    assert mkow['prenom'] == 'زياد المحيَّن'
    assert mkow['jiha_marjiiya'] == 'الإدارة الجهويّة للدّيوانة بالقصرين'


def test_update_mkow_champ_soumis_vide_efface_bien(db):
    """Une خانة montrée puis vidée est un effacement voulu, pas un oubli."""
    mkow_id = _creer_mkow(db, nom='المكوّن', jiha_marjiiya='جهة ما')
    db.update_mkow(mkow_id, {'jiha_marjiiya': ''})
    assert db.get_mkow(mkow_id)['jiha_marjiiya'] == ''


def test_update_mkow_sans_champ_connu_echoue(db):
    """Un formulaire qui ne correspond plus à la قاعدة doit se voir, pas se taire."""
    mkow_id = _creer_mkow(db, nom='المكوّن')
    assert db.update_mkow(mkow_id, {'champ_inexistant': 'x'}) is False
    assert db.update_mkow(mkow_id, {}) is False


# ─── الانحدار الأهمّ : نموذج قديم لا يمحو الجهة ──────────────────────────────

def test_post_modifier_sans_jiha_ne_lefface_pas(db, client):
    """Le gabarit `mkowin/modifier.html` d'avant la v58 n'affiche pas la خانة.

    Il poste donc les vingt et un champs historiques, sans `jiha_marjiiya`.
    Avant la correction, chaque enregistrement effaçait la جهة en silence.
    """
    mkow_id = _creer_mkow(db, nom='البوهلالي زياد', prenom='زياد', grade='مقدم',
                          jiha_marjiiya='الإدارة الجهويّة للدّيوانة بالقصرين')

    ancien_formulaire = {c: '' for c in db._CHAMPS_MKOW if c != 'jiha_marjiiya'}
    ancien_formulaire.update({'nom': 'البوهلالي زياد', 'prenom': 'زياد',
                              'grade': 'مقدم', '_csrf': 'jeton-de-test'})

    rep = client.post(f'/mkowin/{mkow_id}/modifier', data=ancien_formulaire)
    assert rep.status_code in (200, 302)
    assert db.get_mkow(mkow_id)['jiha_marjiiya'] == 'الإدارة الجهويّة للدّيوانة بالقصرين'


def test_post_modifier_avec_jiha_la_met_a_jour(db, client):
    mkow_id = _creer_mkow(db, nom='المكوّن', jiha_marjiiya='جهة قديمة')
    client.post(f'/mkowin/{mkow_id}/modifier',
                data={'nom': 'المكوّن', 'jiha_marjiiya': 'جهة جديدة',
                      '_csrf': 'jeton-de-test'})
    assert db.get_mkow(mkow_id)['jiha_marjiiya'] == 'جهة جديدة'


# ─── خانة الجهة في المشاركين ─────────────────────────────────────────────────

def test_participants_conservent_la_jiha(db, programme):
    db.save_participants(programme['lettre_id'], programme['formation_id'], [
        {'nom': 'مشارك أوّل', 'grade': 'ملازم',
         'jiha_marjiiya': 'الإدارة الجهويّة للدّيوانة بقفصة'},
    ])
    parts = db.get_participants(programme['lettre_id'], programme['formation_id'])
    assert parts[0]['jiha_marjiiya'] == 'الإدارة الجهويّة للدّيوانة بقفصة'


def test_participants_sans_jiha_restent_valides(db, programme):
    """Les appels antérieurs à la v58 ne transmettent pas la clé : pas d'erreur."""
    db.save_participants(programme['lettre_id'], programme['formation_id'],
                         [{'nom': 'مشارك', 'grade': 'عريف'}])
    parts = db.get_participants(programme['lettre_id'], programme['formation_id'])
    assert parts[0]['jiha_marjiiya'] == ''


# ─── مسار التّرقية من قاعدة سابقة للإصدار 58 ─────────────────────────────────

def test_migration_base_anterieure(monkeypatch):
    """Une base en service depuis la v57 doit gagner les خانات sans rien perdre.

    On fabrique ici une قاعدة au schéma ancien — deux tables réduites, sans
    `jiha_marjiiya` — puis on lance `init_db()` par-dessus, exactement comme
    le fait le premier démarrage après mise à jour.
    """
    import core.database as database

    dossier = tempfile.mkdtemp(prefix='fk_v57_')
    chemin = os.path.join(dossier, 'formation.db')

    conn = sqlite3.connect(chemin)
    conn.executescript("""
        CREATE TABLE mkowin (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nom TEXT NOT NULL,
            prenom TEXT,
            grade TEXT,
            date_ajout TEXT
        );
        CREATE TABLE participants (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            formation_id INTEGER,
            nom TEXT,
            grade TEXT
        );
    """)
    conn.execute("INSERT INTO mkowin (nom, prenom, grade) VALUES (?,?,?)",
                 ('البوهلالي زياد', 'زياد', 'مقدم'))
    conn.execute("INSERT INTO participants (formation_id, nom, grade) VALUES (?,?,?)",
                 (1, 'مشارك قديم', 'عريف'))
    conn.commit()
    conn.close()

    monkeypatch.setattr(database, 'DB_PATH', chemin)
    database.init_db()

    conn = database.get_connection()
    try:
        cols_m = {c['name'] for c in conn.execute('PRAGMA table_info(mkowin)')}
        cols_p = {c['name'] for c in conn.execute('PRAGMA table_info(participants)')}
        assert 'jiha_marjiiya' in cols_m
        assert 'jiha_marjiiya' in cols_p

        # Les données d'avant la mise à jour sont intactes.
        assert conn.execute("SELECT nom FROM mkowin").fetchone()['nom'] == 'البوهلالي زياد'
        assert conn.execute("SELECT nom FROM participants").fetchone()['nom'] == 'مشارك قديم'

        # Et le semis a bien eu lieu sur cette base ancienne.
        assert conn.execute("SELECT COUNT(*) c FROM jihat").fetchone()['c'] \
            == regions.NB_GOUVERNORATS
    finally:
        conn.close()

    for f in os.listdir(dossier):
        try:
            os.remove(os.path.join(dossier, f))
        except OSError:
            pass


# ─── الصّفحة ─────────────────────────────────────────────────────────────────

def test_page_jihat_saffiche(db, client):
    rep = client.get('/jihat')
    assert rep.status_code == 200
    corps = rep.data.decode('utf-8')
    assert 'الإدارة الجهويّة للدّيوانة بالقصرين' in corps
    assert regions.LIBELLES_TYPES[regions.TYPE_GARDE] in corps


def test_page_jihat_ajout_et_suppression(db, client):
    client.post('/jihat/ajouter',
                data={'nom': 'وحدة اختباريّة', 'type': regions.TYPE_GARDE,
                      '_csrf': 'jeton-de-test'},
                follow_redirects=True)
    assert 'وحدة اختباريّة' in db.noms_jihat()

    jiha = [j for j in db.get_jihat() if j['nom'] == 'وحدة اختباريّة'][0]
    client.post(f'/jihat/{jiha["id"]}/supprimer',
                data={'_csrf': 'jeton-de-test'}, follow_redirects=True)
    assert 'وحدة اختباريّة' not in db.noms_jihat()


def test_page_jihat_ajout_vide_refuse(db, client):
    avant = len(db.noms_jihat())
    client.post('/jihat/ajouter',
                data={'nom': '   ', 'type': regions.TYPE_AUTRE,
                      '_csrf': 'jeton-de-test'},
                follow_redirects=True)
    assert len(db.noms_jihat()) == avant


def test_page_jihat_exige_installation(db, client_neuf):
    """Avant l'installation, toutes les pages mènent au معالج."""
    rep = client_neuf.get('/jihat')
    assert rep.status_code == 302
    assert '/installation' in rep.headers['Location']


# ─── عمود الجهة في جدول المشاركين ────────────────────────────────────────────

def test_page_nouvelle_lettre_propose_les_jihat(db, client):
    """La صفحة مراسلة جديدة doit porter la liste et la colonne.

    Un `<datalist>` propose sans contraindre : une جهة absente de la liste
    reste saisissable à la main. C'est le même principe que partout ailleurs
    dans la منظومة — le système n'ajoute ni ne retranche un caractère.
    """
    from tests.conftest import js_programme
    rep = client.get('/lettre/nouvelle')
    assert rep.status_code == 200
    corps = rep.data.decode('utf-8') + js_programme()
    # v1.7.1 : la colonne الجهة المرجعيّة est retirée de la قائمة المشاركين
    # (demande de l'utilisateur) ; la جهة suit la fiche, sans être affichée.
    assert 'id="dl_jihat"' in corps
    assert 'p-jiha' not in corps and 'tr.dataset.jiha' in corps
    assert 'الإدارة الجهويّة للدّيوانة بالقصرين' in corps


def test_page_nouvelle_lettre_colonnes_coherentes(db, client):
    """Autant de خانات dans l'entête que dans la ligne engendrée.

    Le jour où un عمود s'ajoute d'un côté seulement, le tableau se décale
    silencieusement : le نص d'un مشارك se retrouve sous un autre عنوان.
    On compte donc les deux.
    """
    from tests.conftest import js_programme
    corps = client.get('/lettre/nouvelle').data.decode('utf-8') + js_programme()
    entete = corps.split('<tbody id="ptbody_')[0].rsplit('<thead>', 1)[-1]
    ligne  = corps.split("tr.id = `prow_${fid}_${n}`;")[1].split('tbody.appendChild')[0]
    # v1.6 : +2 colonnes (الجنس، الفئة العمريّة) ; v1.7.1 : −1 (الجهة) → 8.
    assert entete.count('<th ') == ligne.count('<td ') == 8


def test_api_participants_transporte_la_jiha(db, client, programme):
    """Aller-retour complet : المتصفّح → الطّريق → القاعدة → العودة."""
    url = (f'/lettre/{programme["lettre_id"]}'
           f'/formations/{programme["formation_id"]}/participants')
    rep = client.post(url, headers={'X-CSRF-Token': 'jeton-de-test'},
                      json={'participants': [
        {'nom_prenom': 'بن صالح أيمن', 'grade': 'عريف',
         'identifiant_unique': '77001', 'lieu_travail': 'ميناء بنزرت',
         'jiha_marjiiya': 'الإدارة الجهويّة للدّيوانة ببنزرت', 'sexe': 'ذكر', 'fiaa_omria': 'أقلّ من 40 سنة'},
    ]})
    assert rep.status_code == 200

    parts = client.get(url).get_json()['participants']
    assert len(parts) == 1
    assert parts[0]['jiha_marjiiya'] == 'الإدارة الجهويّة للدّيوانة ببنزرت'


def test_api_participants_sans_jiha_reste_accepte(db, client, programme):
    """Une جهة non renseignée n'est pas une erreur : la خانة est facultative.

    Les انطلاقات anciennes et الاستيراد من ملفّ قديم n'en portent pas ;
    le refus aurait bloqué un travail qui n'a rien d'invalide.
    """
    url = (f'/lettre/{programme["lettre_id"]}'
           f'/formations/{programme["formation_id"]}/participants')
    rep = client.post(url, headers={'X-CSRF-Token': 'jeton-de-test'},
                      json={'participants': [
        {'nom_prenom': 'قاسمي سمير', 'grade': 'رقيب',
         'identifiant_unique': '77002', 'lieu_travail': 'مطار المنستير', 'sexe': 'ذكر', 'fiaa_omria': 'أقلّ من 40 سنة'},
    ]})
    assert rep.status_code == 200
    parts = client.get(url).get_json()['participants']
    assert parts[0]['jiha_marjiiya'] == ''


def test_detail_lettre_affiche_la_jiha_des_participants(db, client, programme):
    """Ce qui est saisi doit se revoir : la خانة n'est pas une impasse.

    La صفحة التّفاصيل est l'endroit où l'agent relit ce qu'il a enregistré
    avant d'imprimer. Une جهة saisie et jamais réaffichée serait une خانة
    qu'on remplit pour rien.
    """
    url = (f'/lettre/{programme["lettre_id"]}'
           f'/formations/{programme["formation_id"]}/participants')
    client.post(url, headers={'X-CSRF-Token': 'jeton-de-test'},
                json={'participants': [
        {'nom_prenom': 'بن صالح أيمن', 'grade': 'عريف',
         'identifiant_unique': '77001', 'lieu_travail': 'ميناء بنزرت',
         'jiha_marjiiya': 'الإدارة الجهويّة للدّيوانة ببنزرت', 'sexe': 'ذكر', 'fiaa_omria': 'أقلّ من 40 سنة'},
    ]})

    rep = client.get(f'/lettres/{programme["lettre_id"]}')
    assert rep.status_code == 200
    corps = rep.data.decode('utf-8')
    # v1.7.1 : الجهة n'est plus affichée ; الجنس / الفئة العمريّة le sont.
    assert 'الجهة المرجعيّة' not in corps
    assert 'ميناء بنزرت' in corps and 'أقلّ من 40 سنة' in corps
