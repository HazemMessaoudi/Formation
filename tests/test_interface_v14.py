# -*- coding: utf-8 -*-
"""Les cinq corrections d'interface demandées après la v1.4.

Ce fichier ne teste pas l'esthétique — il verrouille cinq décisions que le
مستعمل a demandées explicitement et qu'une refonte future pourrait défaire
sans s'en apercevoir :

  1. Le تذييل de la شاشة رئيسية est ancré au bas de la fenêtre.
  2. Toute خانة de كلمة مرور porte un زر de révélation, à l'intérieur.
  3. Chaque قسم affiche SON nom sous le زر العودة.
  4. Les trois écrans de réglage vivent dans «الإعدادات», nulle part ailleurs.
  5. Le قسم إحصائيات n'a plus de liste déroulante mais un عرض تلقائي.
"""
import re

import pytest


@pytest.fixture()
def client_anonyme(db, monkeypatch):
    """Visiteur non authentifié : le seul à qui /login est servi."""
    import app as application
    db.update_config('installation_faite', '1')
    monkeypatch.setattr(application, 'get_connection', db.get_connection, raising=False)
    application.app.config.update(TESTING=True, WTF_CSRF_ENABLED=False)
    return application.app.test_client()


def _menu(html):
    """La قائمة du قسم seule — sans le reste de la page."""
    return html.split('nav-menu')[1].split('</ul>')[0]


def _section(html):
    """Le nom du قسم affiché sous le زر العودة."""
    m = re.search(r'class="nav-section-label"[^>]*>(.*?)</span>\s*</div>',
                  html, re.S)
    return ' '.join(m.group(1).split()) if m else None


# ─── 1. التذييل ──────────────────────────────────────────────────────────────

def test_le_pied_de_la_شاشة_رئيسية_est_ancre_en_bas(client):
    """« ارفعها للاعلى قليلا حتى تظهر دائما » : ancré, donc jamais coupé.

    La شاشة رئيسية tient en un écran : son تذييل est en `position:fixed`,
    et le contenu réserve la hauteur correspondante pour ne pas passer
    dessous."""
    html = client.get('/accueil').get_data(as_text=True)
    assert 'أنشأ من طرف حازم مسعودي' in html
    style = html.split('<style>')[1].split('</style>')[0]
    pied = style.split('.footer')[1].split('}')[0]
    assert 'position:fixed' in pied.replace(' ', '')
    assert 'bottom:0' in pied.replace(' ', '')
    # le wrap laisse la place au تذييل
    wrap = style.split('.accueil-wrap')[1].split('}')[0]
    assert 'padding' in wrap


# ─── 2. كلمات المرور ─────────────────────────────────────────────────────────

#  `/login` n'est servi qu'à un visiteur NON authentifié : le client connecté
#  en serait renvoyé vers la شاشة رئيسية et le test ne testerait rien.
PAGES_AVEC_MOT_DE_PASSE = [
    ('anonyme', '/login'),
    ('connecte', '/changer-mot-de-passe'),
    ('connecte', '/parametres'),
]


@pytest.mark.parametrize('qui,chemin', PAGES_AVEC_MOT_DE_PASSE)
def test_toute_خانة_كلمة_مرور_a_son_زر_رؤية(client, client_anonyme, qui, chemin):
    """Aucune خانة de كلمة مرور ne reste sans زر de révélation."""
    c = client_anonyme if qui == 'anonyme' else client
    html = c.get(chemin, follow_redirects=True).get_data(as_text=True)
    champs = re.findall(r'<input[^>]*type="password"[^>]*>', html)
    assert champs, f'aucune خانة كلمة مرور trouvée sur {chemin}'
    assert html.count('class="pwd-eye"') >= len(champs), (
        f'{chemin} : {len(champs)} خانة(ات) mais '
        f'{html.count(chr(34)+"pwd-eye"+chr(34))} زر')
    # chaque خانة est bien enveloppée : sans le wrap, le زر tombe SOUS la خانة
    for champ in champs:
        i = html.index(champ)
        assert 'pwd-wrap' in html[max(0, i - 400):i], (
            f'{chemin} : خانة hors de .pwd-wrap → le زر sortirait de la خانة')


def test_le_زر_est_place_a_l_interieur_a_droite():
    """La règle qui met le زر DANS la خانة, collé à droite."""
    for feuille in ('static/css/app.css', 'templates/login.html'):
        with open(feuille, encoding='utf-8') as f:
            css = f.read().replace(' ', '').replace('\n', '')
        assert '.pwd-wrap{position:relative' in css, feuille
        bloc = css.split('.pwd-eye{')[1].split('}')[0]
        assert 'position:absolute' in bloc, feuille
        assert 'right:' in bloc, feuille          # أقصى اليمين
        assert 'top:50%' in bloc, feuille         # centré dans la خانة


def test_la_signature_de_l_ecran_de_connexion_est_lisible():
    """« الكتابة في الاسفل بالاسود غير واضحة » : elle prend la teinte du thème."""
    with open('templates/login.html', encoding='utf-8') as f:
        html = f.read()
    bloc = html.split('أنشأ من طرف حازم مسعودي')[0][-320:]
    assert 'var(--text-sub)' in bloc, 'la signature retombe en noir sur fond sombre'


# ─── 3. عنوان القسم ──────────────────────────────────────────────────────────

SECTIONS = [
    ('/dashboard',                     'برامج تكوينية'),
    ('/journal',                       'الإعدادات'),        # déplacé (v1.4d)
    ('/mustahaqqat',                   'مستحقات مالية'),
    ('/statistiques',                  'إحصائيات'),
    ('/parametres',                    'الإعدادات'),
    ('/parametres/centre',             'الإعدادات'),
    ('/mustahaqqat/bareme',            'الإعدادات'),
    ('/mustahaqqat/bareme-mali',       'الإعدادات'),
    ('/mustahaqqat/khalas/parametres', 'الإعدادات'),
]


@pytest.mark.parametrize('chemin,nom', SECTIONS)
def test_chaque_page_annonce_son_قسم_sous_le_زر(client, chemin, nom):
    """Le nom affiché est celui de la PORTE de l'accueil, pas du sous-titre."""
    html = client.get(chemin).get_data(as_text=True)
    lu = _section(html)
    assert lu is not None, f'{chemin} : aucun عنوان قسم sous le زر العودة'
    assert nom in lu, f'{chemin} : «{lu}» au lieu de «{nom}»'


# ─── 4. ما انتقل إلى الإعدادات ───────────────────────────────────────────────

REGLAGES_DEPLACES = ['جدول الأصناف', 'الجدول المالي', 'إعدادات وثائق الخلاص']


@pytest.mark.parametrize('titre', REGLAGES_DEPLACES)
def test_les_reglages_ont_quitte_le_قسم_des_مستحقات(client, titre):
    html = client.get('/mustahaqqat').get_data(as_text=True)
    assert titre not in _menu(html), f'«{titre}» est resté dans قائمة المستحقّات'


@pytest.mark.parametrize('titre', REGLAGES_DEPLACES)
def test_les_reglages_sont_bien_dans_les_إعدادات(client, titre):
    html = client.get('/parametres').get_data(as_text=True)
    assert titre in _menu(html), f'«{titre}» absent de قائمة الإعدادات'


def test_la_page_des_إعدادات_mene_aux_trois_ecrans(client):
    """Depuis la porte «الإعدادات», les trois écrans sont à un clic."""
    html = client.get('/parametres').get_data(as_text=True)
    for url in ('/mustahaqqat/bareme', '/mustahaqqat/bareme-mali',
                '/mustahaqqat/khalas/parametres'):
        assert url in html, f'{url} injoignable depuis /parametres'


def test_قائمة_الأسماء_est_devenue_قائمة_المكونين(client):
    menu = _menu(client.get('/mustahaqqat').get_data(as_text=True))
    assert 'قائمة المكونين' in menu
    assert 'قائمة الأسماء' not in menu


def test_تعريف_بالبرنامج_et_وصول_سريع_ont_disparu(client):
    """Retirés de la قائمة et de لوحة القيادة ; تعريف reste sur l'accueil."""
    dash = client.get('/dashboard').get_data(as_text=True)
    assert 'تعريف بالبرنامج' not in _menu(dash)
    assert 'quick-actions' not in dash
    assert 'وصول سريع' not in dash
    # mais la page elle-même reste atteignable depuis la شاشة رئيسية
    assert 'تعريف بالبرنامج' in client.get('/accueil').get_data(as_text=True)
    assert client.get('/tarif').status_code == 200      # endpoint `apropos`


# ─── 5. العرض التلقائي للإحصائيات ────────────────────────────────────────────

def test_les_إحصائيات_n_ont_plus_de_liste_deroulante(client):
    html = client.get('/statistiques').get_data(as_text=True)
    assert 'nav-select' not in html
    assert 'statNavGo' not in html
    assert '— انتقل إلى —' not in html


def test_les_إحصائيات_ont_un_عرض_تلقائي_qui_tourne(client):
    """Le carrousel existe, change tout seul, et se laisse arrêter."""
    html = client.get('/statistiques').get_data(as_text=True)
    assert 'id="carrousel"' in html
    assert 'id="vizScene"' in html
    assert 'DUREE = 3000' in html, 'le rythme demandé est de 3 secondes'
    for outil in ('vizPrev', 'vizNext', 'vizPause', 'vizPoints'):
        assert outil in html, f'{outil} manque : le مستعمل ne peut plus naviguer'


def test_le_carrousel_couvre_les_trois_familles_de_رسوم(client):
    """« les diagrammes et les histogrammes et des courbes »."""
    html = client.get('/statistiques').get_data(as_text=True)
    for famille in ('منحنى', 'رسم بالأعمدة', 'رسم دائري'):
        assert famille in html, f'aucun {famille} dans le عرض'
    for dessinateur in ('function courbe', 'function colonnes', 'function anneau'):
        assert dessinateur in html, f'{dessinateur} absent'


def test_le_carrousel_est_nourri_par_les_memes_chiffres(client, programme):
    """Les séries du رسم sortent de la منظومة, pas d'un jeu d'essai figé."""
    import json
    html = client.get('/statistiques').get_data(as_text=True)
    brut = html.split('id="viz-data" type="application/json">')[1].split('</script>')[0]
    data = json.loads(brut)
    for cle in ('mois', 'annee', 'classes', 'grades', 'types', 'formateurs'):
        assert cle in data, f'série «{cle}» absente des معطيات du رسم'
    mois = [m for m, _n in data['mois']]
    assert mois[:3] == ['جانفي', 'فيفري', 'مارس'], 'une courbe se lit dans l\'ordre du calendrier'
    assert sum(n for _m, n in data['annee']) >= 1, 'le برنامج de test devrait compter'


def test_le_detail_reste_accessible_par_onglets(client):
    """« واجعل باقي التفاصيل في الأسفل ويمكن للمستعمل التنقل بينها »."""
    html = client.get('/statistiques').get_data(as_text=True)
    for panneau in ('d-kpi', 'd-part', 'd-dor', 'd-temps', 'd-mawad'):
        assert f'id="{panneau}"' in html, f'panneau {panneau} manquant'
        assert f'data-cible="{panneau}"' in html, f'onglet vers {panneau} manquant'


def test_le_رسم_double_ses_couleurs_par_un_tableau(client):
    """Trois teintes passent sous 3:1 en mode clair : le texte doit exister.

    C'est la contrepartie obligatoire de la palette retenue — sans ce
    doublon, l'information reposerait sur la seule couleur."""
    html = client.get('/statistiques').get_data(as_text=True)
    assert 'id="vizTable"' in html
    assert 'id="vizTableau"' in html
    assert 'viz-legende' in html, 'la légende nomme chaque part'


# ═══ v1.4d ═══════════════════════════════════════════════════════════════════

def test_les_رتب_du_معالج_sont_celles_de_la_ديوانة():
    """De العريف à العميد, sans aucune رتبة de la شرطة."""
    from core import identite
    rutab = identite.GRADES_RESPONSABLE
    assert rutab[0] == 'العميد' and rutab[-1] == 'العريف'
    assert not [r for r in rutab if 'شرطة' in r]
    assert 'اللواء' not in rutab and 'الرقيب' not in rutab


def test_le_معالج_propose_les_رتب_de_la_ديوانة(client_neuf):
    html = client_neuf.get('/installation/4').get_data(as_text=True)
    assert 'العريف أعلى' in html and 'وكيل الشرطة' not in html


def test_la_barre_de_l_accueil_ne_garde_que_trois_actions(client):
    # V3.2 : + « دليل الاستعمال » (deux actions auparavant)
    html = client.get('/accueil').get_data(as_text=True)
    barre = html.split('class="accueil-bar"')[1].split('</div>')[0]
    assert 'تعريف بالبرنامج' in barre and 'تسجيل الخروج' in barre and 'دليل الاستعمال' in barre
    assert 'سجلّ التدقيق' not in barre
    assert barre.count('<a ') == 3


def test_تعريف_بالبرنامج_n_appartient_a_aucun_قسم(client):
    html = client.get('/tarif').get_data(as_text=True)
    assert _section(html) is None, 'la page affiche un nom de قسم'
    assert 'nav-link' not in _menu(html), 'la page affiche une قائمة'
    assert 'nav-home-btn' in html                    # mais on peut revenir
    # lecture continue : plus d'accordéon à ouvrir
    assert '_toggleApropos' not in html
    for chapitre in ('مسار دورةٍ تكوينيّة', 'وثائقُ جاهزة للإمضاء', 'ما تضمنه المنظومة'):
        assert chapitre in html


def test_تعريف_بالبرنامج_ouvre_sur_les_chiffres_du_centre(client, db, programme):
    html = client.get('/tarif').get_data(as_text=True)
    assert 'ap-chiffre__val' in html and 'data-cible="1"' in html


def test_سجل_التدقيق_vit_dans_الإعدادات(client):
    assert 'page_journal' not in _menu(client.get('/dashboard').get_data(as_text=True))
    assert '/journal' not in _menu(client.get('/dashboard').get_data(as_text=True))
    assert '/journal' in _menu(client.get('/parametres').get_data(as_text=True))
    assert 'الإعدادات' in _section(client.get('/journal').get_data(as_text=True))
