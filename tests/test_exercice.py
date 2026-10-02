# -*- coding: utf-8 -*-
"""السّنة المحاسبيّة — سجلّ لكلّ سنة، ومرجعيّة دائمة لا تتجدّد.

Deux natures de données partagent le même fichier :

* **المرجعيّة** — الإعدادات, المكوّنون, الموادّ, الجهات. Elles appartiennent
  au مركز : la liste des أعوان ne se vide pas au 1er janvier.
* **السّنويّة** — المراسلات et surtout **الأعداد**. Au 1er janvier un سجلّ
  neuf s'ouvre, et la série repart.

Ce que ces tests défendent : le basculement est automatique, il ne recule
jamais, il ne touche pas à la مرجعيّة, et **il ne renumérote rien du
passé**. Un عدد de 2026 reste le عدد de 2026 pour toujours.
"""

from datetime import datetime

import pytest

from core import exercice


@pytest.fixture()
def horloge(monkeypatch):
    """Permet de faire avancer l'année sans attendre le 1er janvier."""
    class _Horloge:
        annee = datetime.now().year

        def regler(self, annee):
            self.annee = annee
            vraie = datetime

            class _DT(vraie):
                @classmethod
                def now(cls, tz=None):
                    base = vraie.now(tz)
                    return base.replace(year=annee)

            monkeypatch.setattr(exercice, 'datetime', _DT)
    return _Horloge()


def programme(db, mois='فيفري', annee=None):
    annee = annee or db.annee_registre()
    lettre_id = db.save_programme(
        'interne', mois, annee,
        [{'titre': 'تحرير المحاضر', 'grade': 'مقدم',
          'nom_formateur': 'زياد البوهلالي', 'lieu_travail': '',
          'date_formation': f'{annee}-02-10', 'periode': '',
          'lieu_formation': 'مركز التكوين الجهوي بالقصرين'}],
        'حازم مسعودي', 'النقيب')
    return lettre_id


# ─── السّنة المفتوحة ─────────────────────────────────────────────────────────

def test_une_base_neuve_ouvre_lannee_civile(db):
    assert db.annee_registre() == datetime.now().year


def test_la_manzouma_na_jamais_dannee_indeterminee(db):
    """Un réglage absent ou aberrant ne laisse pas la منظومة sans سجلّ."""
    conn = db.get_connection()
    try:
        for valeur in ('', 'أمس', '1200', '9999'):
            conn.execute("UPDATE config SET valeur=? WHERE cle='annee_exercice'",
                         (valeur,))
            assert exercice.annee_active(conn) == datetime.now().year
    finally:
        conn.close()


# ─── البسط: سجلّ جديد على رأس السّنة ──────────────────────────────────────────

def test_le_sejel_souvre_tout_seul_a_la_nouvelle_annee(db, horloge):
    ouverte = db.annee_registre()
    horloge.regler(ouverte + 1)

    conn = db.get_connection()
    try:
        bascule = exercice.basculer_si_necessaire(conn)
        conn.commit()
        assert bascule == (ouverte, ouverte + 1)
        assert exercice.annee_active(conn) == ouverte + 1
    finally:
        conn.close()


def test_la_serie_repart_a_un_dans_le_nouveau_sejel(db, horloge):
    """Le cœur de la règle : le عدد 1 de 2027 n'est pas la suite de 2026."""
    ouverte = db.annee_registre()
    for _ in range(3):
        db.verrouiller_lettre(programme(db), 'interne')
    assert db.prochain_numero_prevu('interne') == 4

    horloge.regler(ouverte + 1)
    conn = db.get_connection()
    try:
        exercice.basculer_si_necessaire(conn)
        conn.commit()
    finally:
        conn.close()

    assert db.annee_registre() == ouverte + 1
    assert db.prochain_numero_prevu('interne') == 1


def test_le_nouveau_sejel_respecte_le_numero_de_depart(db, horloge):
    """Un مركز qui reprend son سجلّ ورقي au 147 le retrouve chaque année."""
    ouverte = db.annee_registre()
    horloge.regler(ouverte + 1)
    conn = db.get_connection()
    try:
        exercice.basculer_si_necessaire(conn, {'interne': 147, 'externe': 12})
        conn.commit()
    finally:
        conn.close()
    assert db.prochain_numero_prevu('interne') == 147
    assert db.prochain_numero_prevu('externe') == 12


def test_le_basculement_ne_recule_jamais(db, horloge):
    """Une horloge faussée ne doit pas rouvrir un سجلّ clos."""
    ouverte = db.annee_registre()
    horloge.regler(ouverte - 3)
    conn = db.get_connection()
    try:
        assert exercice.basculer_si_necessaire(conn) is None
        assert exercice.annee_active(conn) == ouverte
    finally:
        conn.close()


def test_basculer_deux_fois_ne_fait_rien_de_plus(db, horloge):
    ouverte = db.annee_registre()
    horloge.regler(ouverte + 1)
    conn = db.get_connection()
    try:
        assert exercice.basculer_si_necessaire(conn) is not None
        conn.commit()
        assert exercice.basculer_si_necessaire(conn) is None
    finally:
        conn.close()


# ─── ما لا يتغيّر ────────────────────────────────────────────────────────────

def test_le_passe_nest_jamais_renumerote(db, horloge):
    """L'épreuve qui compte le plus : une مراسلة partie garde son عدد."""
    ouverte = db.annee_registre()
    lettre_id = programme(db)
    ref, numero = db.verrouiller_lettre(lettre_id, 'interne')

    horloge.regler(ouverte + 1)
    conn = db.get_connection()
    try:
        exercice.basculer_si_necessaire(conn)
        conn.commit()
    finally:
        conn.close()

    ancien = db.get_registre('interne', ouverte)
    assert len(ancien) == 1
    assert ancien[0]['numero'] == numero
    assert ancien[0]['ref_complet'] == ref
    assert db.get_registre('interne', ouverte + 1) == []


def test_le_sejel_ancien_reste_lisible(db, horloge):
    """السّنوات الماضية تُقرأ وتُطبع : c'est la raison d'être de l'archive."""
    ouverte = db.annee_registre()
    db.verrouiller_lettre(programme(db), 'interne')
    horloge.regler(ouverte + 1)
    conn = db.get_connection()
    try:
        exercice.basculer_si_necessaire(conn)
        conn.commit()
    finally:
        conn.close()

    assert ouverte in db.annees_du_registre()
    assert (ouverte + 1) in db.annees_du_registre()
    assert len(db.get_registre('interne', ouverte)) == 1


def test_la_reference_ne_se_vide_pas_a_la_nouvelle_annee(db, horloge):
    """المرجعيّة ملك المركز لا ملك السّنة : la liste des أعوان ne se vide pas."""
    db.add_mkow({'identifiant_unique': '77001', 'nom': 'زياد',
                 'prenom': 'البوهلالي', 'grade': 'عريف'})
    db.add_jiha('وحدة الحرس الدّيواني بالقصرين')
    db.update_config('nom_responsable', 'حازم مسعودي')
    jihat_avant = db.noms_jihat()

    horloge.regler(db.annee_registre() + 1)
    conn = db.get_connection()
    try:
        exercice.basculer_si_necessaire(conn)
        conn.commit()
    finally:
        conn.close()

    assert len(db.get_mkowin()) == 1
    assert db.get_mkowin()[0]['identifiant_unique'] == '77001'
    assert db.noms_jihat() == jihat_avant
    assert 'وحدة الحرس الدّيواني بالقصرين' in db.noms_jihat()
    assert db.get_config()['nom_responsable'] == 'حازم مسعودي'


def test_deux_annees_peuvent_porter_le_meme_numero(db, horloge):
    """Le عدد 1 existe dans chaque سجلّ : ce sont deux registres, pas un."""
    ouverte = db.annee_registre()
    _, n1 = db.verrouiller_lettre(programme(db), 'interne')

    horloge.regler(ouverte + 1)
    conn = db.get_connection()
    try:
        exercice.basculer_si_necessaire(conn)
        conn.commit()
    finally:
        conn.close()

    _, n2 = db.verrouiller_lettre(
        programme(db, annee=ouverte + 1), 'interne')
    assert n1 == n2 == 1
    assert len(db.get_registre('interne', ouverte)) == 1
    assert len(db.get_registre('interne', ouverte + 1)) == 1


def test_le_marjaa_porte_les_deux_chiffres_du_sejel(db, horloge):
    """«-26-» vient du سجلّ, non de l'horloge : signer le 2 janvier ne le change pas."""
    ouverte = db.annee_registre()
    ref, _ = db.verrouiller_lettre(programme(db), 'interne')
    assert f'-{str(ouverte)[-2:]}-' in ref


# ─── الصّفحة ─────────────────────────────────────────────────────────────────

def test_la_page_du_registre_affiche_lannee_ouverte(db, client):
    rep = client.get('/registre/interne')
    assert rep.status_code == 200
    assert str(db.annee_registre()) in rep.data.decode('utf-8')


def test_un_sejel_ancien_saffiche_et_se_dit_clos(db, client, horloge):
    ouverte = db.annee_registre()
    db.verrouiller_lettre(programme(db), 'interne')
    horloge.regler(ouverte + 1)
    conn = db.get_connection()
    try:
        exercice.basculer_si_necessaire(conn)
        conn.commit()
    finally:
        conn.close()

    rep = client.get(f'/registre/interne?annee={ouverte}')
    corps = rep.data.decode('utf-8')
    assert rep.status_code == 200
    assert 'أُغلق' in corps
    assert str(ouverte) in corps


def test_une_annee_inconnue_retombe_sur_le_sejel_ouvert(db, client):
    rep = client.get('/registre/interne?annee=1999')
    assert rep.status_code == 200
    assert 'أُغلق' not in rep.data.decode('utf-8')


# ─── لا يُسند عدد من سجلّ سنة إلى مراسلة سنة أخرى ─────────────────────────────

def test_un_programme_dune_annee_ecoulee_est_refuse(db, client):
    # v1.7 : seule une année ÉCOULÉE est refusée (l'année suivante est admise).
    ouverte = db.annee_registre()
    charge = {'type': 'interne', 'mois': 'فيفري', 'annee': ouverte - 1,
              'formations': [{'titre': 'تحرير المحاضر', 'grade': 'مقدم',
                              'nom_formateur': 'زياد البوهلالي', 'lieu_travail': '',
                              'date_formation': f'{ouverte - 1}-02-10',
                              'periode': '', 'lieu_formation': 'القصرين'}]}
    lettre_id = client.post('/lettre/enregistrer',
                            headers={'X-CSRF-Token': 'jeton-de-test'},
                            json=charge).get_json()['lettre_id']
    rep = client.post(f'/lettre/{lettre_id}/valider',
                      headers={'X-CSRF-Token': 'jeton-de-test'},
                      json={'type': 'interne'})
    assert rep.status_code == 400
    assert str(ouverte) in rep.get_json()['erreur']
    # Rien n'a été consommé.
    assert db.get_registre('interne', ouverte) == []
