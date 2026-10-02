import logging as _logging
_log = _logging.getLogger('formation.' + __name__)
import os
import sys
import time
from functools import wraps
from flask import (Flask, render_template, request, jsonify, redirect, url_for,
                   session, send_from_directory)


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

# v1.7 : seuls les noms réellement utilisés ici (les routes importent les leurs).
from core.database import (  # noqa: E402
    init_db, get_config, get_connection, get_user_role, user_doit_changer_mdp,
    journaliser, backup_db,
)
from core import identite  # noqa: E402
from core import chemins  # noqa: E402
from core import validation as _validation  # noqa: E402

app = Flask(__name__, template_folder='templates', static_folder='static')


# ─── Clé de session : générée une fois, conservée hors du code source ─────────

def _charger_secret_key():
    """La clé signe les cookies de session. Elle est générée aléatoirement à la
    première exécution puis relue : elle ne figure jamais dans le code source,
    et les sessions survivent aux redémarrages."""
    chemin = os.path.join(chemins.dossier_donnees(), 'secret_key')
    try:
        os.makedirs(os.path.dirname(chemin), exist_ok=True)
        if os.path.exists(chemin):
            with open(chemin, 'r', encoding='utf-8') as fh:
                cle = fh.read().strip()
            if cle:
                return cle
        cle = os.urandom(32).hex()
        with open(chemin, 'w', encoding='utf-8') as fh:
            fh.write(cle)
        try:                      # lecture réservée au propriétaire (POSIX)
            os.chmod(chemin, 0o600)
        except OSError:
            pass
        return cle
    except Exception:
        _log.warning('_charger_secret_key : exception ignorée', exc_info=True)
        # Dernier recours : clé éphémère (les sessions ne survivront pas au
        # redémarrage, mais l'application démarre quand même).
        return os.urandom(32).hex()


app.secret_key = _charger_secret_key()
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE='Lax',
    MAX_CONTENT_LENGTH=32 * 1024 * 1024,   # 32 Mo max par requête
)


# ─── Journalisation applicative ──────────────────────────────────────────────

def _configurer_logs():
    import logging
    from logging.handlers import RotatingFileHandler
    dossier = chemins.sous_dossier('logs')
    try:
        os.makedirs(dossier, exist_ok=True)
        handler = RotatingFileHandler(
            os.path.join(dossier, 'application.log'),
            maxBytes=1_000_000, backupCount=5, encoding='utf-8')
        handler.setFormatter(logging.Formatter(
            '%(asctime)s [%(levelname)s] %(message)s'))
        handler.setLevel(logging.INFO)
        app.logger.addHandler(handler)
        app.logger.setLevel(logging.INFO)
        # Toutes les couches (core/*, routes/*) journalisent sous « formation.* » :
        # les exceptions autrefois avalées en silence atterrissent dans ce fichier.
        journal = logging.getLogger('formation')
        if handler not in journal.handlers:
            journal.addHandler(handler)
        journal.setLevel(logging.INFO)
    except Exception as e:
        print(f"logs indisponibles: {e}")


_configurer_logs()


@app.errorhandler(Exception)
def _erreur_non_geree(e):
    """Toute erreur inattendue est tracée dans le journal au lieu de disparaître."""
    from werkzeug.exceptions import HTTPException
    if isinstance(e, HTTPException):
        return e
    app.logger.exception('Erreur non gérée sur %s', request.path)
    if request.path.startswith('/api/') or request.is_json:
        return jsonify({'erreur': 'حدث خطأ داخلي. راجع سجلّ التطبيق.'}), 500
    return render_template('erreur.html', message=str(e)), 500


# ─── V3.1 : base abîmée → seule la page « استرجاع المنظومة » est servie ────────

from core import miroir as _miroir  # noqa: E402

ENDPOINTS_SECOURS = {'secours', 'secours_restaurer', 'static', 'favicon'}


@app.before_request
def _noter_activite():
    """1.0 — en mode navigateur (sans fenêtre à surveiller), le lanceur arrête
    le programme après une longue inactivité."""
    from core import lanceur as _lanceur
    _lanceur.noter_activite()


@app.before_request
def _mode_secours():
    if not _miroir.ETAT.get('secours') or request.endpoint in ENDPOINTS_SECOURS:
        return None
    if request.path.startswith('/api/') or request.is_json:
        return jsonify({'erreur': 'قاعدة البيانات تالفة: يجب استرجاع نسخة سليمة أوّلًا'}), 503
    return redirect(url_for('secours'))


@app.after_request
def _miroir_apres_modification(reponse):
    """V3.1 : toute modification réussie déclenche la mise à jour (regroupée)
    de la نسخة المرآة."""
    try:
        if (request.method in ('POST', 'PUT', 'PATCH', 'DELETE') and reponse.status_code < 400
                and not app.config.get('TESTING') and not _miroir.ETAT.get('secours')):
            _miroir.demander_miroir()
    except Exception:
        _log.warning('_miroir_apres_modification : exception ignorée', exc_info=True)
    return reponse


# ─── Protection CSRF (sans dépendance externe) ───────────────────────────────

CSRF_EXEMPT = {'login'}          # endpoints dispensés de jeton


def _jeton_csrf():
    """Jeton propre à la session, créé à la volée."""
    jeton = session.get('_csrf')
    if not jeton:
        jeton = os.urandom(24).hex()
        session['_csrf'] = jeton
    return jeton


@app.before_request
def _verifier_csrf():
    if request.method not in ('POST', 'PUT', 'PATCH', 'DELETE'):
        return None
    if request.endpoint in CSRF_EXEMPT:
        return None
    attendu = session.get('_csrf')
    if not attendu:
        return None            # pas encore de session établie
    fourni = (request.form.get('_csrf')
              or request.headers.get('X-CSRF-Token')
              or (request.get_json(silent=True) or {}).get('_csrf'))
    if fourni and _comparer_surement(fourni, attendu):
        return None
    app.logger.warning('Jeton CSRF invalide sur %s', request.path)
    if request.path.startswith('/api/') or request.is_json:
        return jsonify({'erreur': 'جلسة غير صالحة. يرجى إعادة تحميل الصفحة.'}), 400
    return render_template('erreur.html',
                           message='انتهت صلاحية الجلسة. يرجى إعادة تحميل الصفحة.'), 400


def _comparer_surement(a, b):
    import hmac
    return hmac.compare_digest(str(a), str(b))


# ─── Premier démarrage : le centre doit se présenter avant toute autre page ──

# Endpoints accessibles alors que l'installation n'est pas encore achevée.
# Tout le reste est renvoyé vers le معالج : une منظومة qui ne connaît ni le nom
# du centre ni celui du signataire produirait des مراسلات fausses, et un عدد
# consommé ne se reprend pas.
# S3 (v1.5) : délai d'inactivité — voir core/securite.py
from core.securite import delai_inactivite  # noqa: E402


ENDPOINTS_HORS_INSTALLATION = {
    'login', 'logout', 'static', 'changer_mot_de_passe',
    'installation', 'installation_etape', 'installation_resume', 'favicon',
}


@app.route('/favicon.ico')
def favicon():
    """Icône d'onglet (v1.5) : l'emblème de l'école, servi localement."""
    return send_from_directory(os.path.join(app.root_path, 'static', 'images'),
                               'favicon.png', mimetype='image/png', max_age=86400)


# ─── سجلّ التّدقيق : opérations de saisie journalisées d'office ─────────────
# endpoint → (action, formulaire HTML ?). Un formulaire réussi redirige (3xx) ;
# une API réussie répond 200 sans « erreur ».
_JOURNAL_AUTO = {
    'ajouter_mkow':              ('إضافة مكوّن', True),
    'modifier_mkow':             ('تعديل بطاقة مكوّن', True),
    'supprimer_mkow':            ('حذف مكوّن', True),
    'supprimer_mkowin_lot':      ('حذف مجموعة مكوّنين', True),
    'ajouter_madda':             ('إضافة مادّة', True),
    'modifier_madda':            ('تعديل مادّة', True),
    'supprimer_madda':           ('حذف مادّة', True),
    'supprimer_mawad_lot':       ('حذف مجموعة موادّ', True),
    'api_save_participants':     ('حفظ قائمة المتكوّنين', False),
    'api_save_bataqa_data':      ('حفظ البطاقة البيداغوجيّة', False),
    'api_save_programme_data':   ('حفظ برنامج الدّورة', False),
    'api_save_memo_data':        ('حفظ المذكّرة', False),
    'enregistrer_programme':     ('تسجيل برنامج تكوين (مسودّة)', False),
    'mettre_a_jour_programme':   ('تحيين برنامج تكوين', False),
    'enregistrer_lettre_libre':  ('تسجيل مراسلة حرّة (مسودّة)', False),
    'mettre_a_jour_lettre_libre': ('تحيين مراسلة حرّة', False),
}


@app.after_request
def _journal_auto(reponse):
    try:
        if request.method != 'POST' or 'username' not in session:
            return reponse
        entree = _JOURNAL_AUTO.get(request.endpoint or '')
        if not entree:
            return reponse
        action, formulaire = entree
        if formulaire:
            ok = 300 <= reponse.status_code < 400
        else:
            ok = reponse.status_code == 200
            if ok and reponse.is_json:
                corps = reponse.get_json(silent=True) or {}
                ok = not corps.get('erreur') and corps.get('succes', True) is not False
        if ok:
            cible = ' '.join(f'{k}={v}' for k, v in (request.view_args or {}).items())
            journaliser(session.get('username'), action, cible or request.path, '')
    except Exception:
        _log.warning('_journal_auto : exception ignorée', exc_info=True)
    return reponse


@app.before_request
def _valider_session():
    """Une session n'ouvre que la base qui l'a émise, et que pour un compte
    qui y existe encore.

    Sans ce contrôle, un cookie resté dans le navigateur depuis une autre
    installation passait pour une connexion valide : la nouvelle منظومة
    s'ouvrait directement sur le معالج التّنصيب, sans écran de connexion ni
    changement du mot de passe initial. Le cookie est rejeté, on repart de
    l'écran de connexion — l'ordre voulu est : دخول ← تغيير كلمة المرور ← تنصيب.
    """
    if 'username' not in session or request.endpoint in ('static', 'favicon'):
        return None
    try:
        _cfg = get_config()
        attendu = _cfg.get('instance_id', '')
        valide = bool(attendu and session.get('_instance') == attendu
                      and _utilisateur_existe(session['username']))
    except Exception:
        _log.warning('_valider_session : exception ignorée', exc_info=True)
        return None
    if valide:
        # L'obligation de changer le mot de passe se relit en base : elle ne
        # s'éteint pas parce qu'un vieux cookie la disait levée.
        try:
            session['doit_changer_mdp'] = bool(user_doit_changer_mdp(session['username']))
            # v1.7 : le rôle se relit lui aussi à chaque requête — un compte
            # promu ou destitué par le مشرف عام l'est immédiatement, sans
            # attendre sa prochaine connexion.
            session['role'] = get_user_role(session['username'])
        except Exception:
            _log.warning('_valider_session : relecture ignorée', exc_info=True)
        # S3 (v1.5) : une session restée sans AUCUNE requête plus longtemps que
        # le délai réglé est close. Le navigateur prolonge la session d'un
        # utilisateur actif (voir /api/ping) : seul un poste abandonné expire.
        delai = delai_inactivite(_cfg)
        maintenant = time.time()
        try:
            vu = float(session.get('_vu') or 0)
        except (TypeError, ValueError):
            vu = 0
        if delai and vu and maintenant - vu > delai * 60:
            utilisateur = session.get('username')
            try:
                journaliser(utilisateur, 'خروج تلقائي بسبب عدم النشاط', '', f'{delai} دقيقة')
            except Exception:
                _log.warning('_valider_session : journal ignoré', exc_info=True)
            session.clear()
            if request.path.startswith('/api/') or request.is_json:
                return jsonify({'erreur': 'انتهت الجلسة بسبب عدم النشاط. يرجى تسجيل الدخول من جديد.',
                                'expire': True}), 401
            return redirect(url_for('login', expire=1))
        session['_vu'] = int(maintenant)
        return None
    session.clear()
    if request.path.startswith('/api/') or request.is_json:
        return jsonify({'erreur': 'انتهت الجلسة. يرجى تسجيل الدخول من جديد.'}), 401
    return redirect(url_for('login'))


def _utilisateur_existe(username):
    conn = get_connection()
    try:
        return conn.execute('SELECT 1 FROM users WHERE username=?',
                            (username,)).fetchone() is not None
    finally:
        conn.close()


@app.before_request
def _sauvegarde_quotidienne():
    """v1.7 : une copie par jour, même si le programme reste ouvert des
    jours entiers (la copie du démarrage ne suffisait plus)."""
    if request.endpoint in ('static', 'favicon') or app.config.get('TESTING'):
        return None
    try:
        from core.database import sauvegarde_quotidienne_si_necessaire
        chemin = sauvegarde_quotidienne_si_necessaire()
        if chemin:
            app.logger.info('Sauvegarde quotidienne: %s', chemin)
            # V3.1 : un nouveau jour — peut-être une nouvelle année : archive
            # figée de l'année close si elle manque encore.
            archive = _miroir.creer_archive_si_necessaire()
            if archive:
                app.logger.info('Archive annuelle: %s', archive)
    except Exception:
        _log.warning('_sauvegarde_quotidienne : exception ignorée', exc_info=True)
    return None


@app.before_request
def _exiger_installation():
    if request.endpoint is None or request.endpoint in ENDPOINTS_HORS_INSTALLATION:
        return None
    if 'username' not in session:
        return None            # login_required s'en chargera
    try:
        _cfg = get_config()
    except Exception:
        _log.warning('_exiger_installation : exception ignorée', exc_info=True)
        # Base illisible : ce n'est pas au حارس التّنصيب de le signaler.
        return None
    if identite.installation_faite(_cfg):
        return None
    if request.path.startswith('/api/') or request.is_json:
        return jsonify({'erreur': 'يجب إتمام تنصيب المركز قبل استعمال المنظومة'}), 409
    return redirect(url_for('installation'))


@app.template_filter('dates_dorra')
def _filtre_dates_dorra(f, vide='—'):
    """V2 — date d'une دورة pour les écrans : la date ISO telle qu'avant pour
    une دورة d'un jour ; « 2026-10-12 → 2026-10-14 · 3 أيّام » (isolé en
    LTR) pour une دورة متعدّدة الأيّام."""
    from markupsafe import Markup, escape
    from core import jours as _jours
    f = f or {}
    debut, fin = f.get('date_formation') or '', f.get('date_fin') or ''
    if not debut:
        return vide
    n = _jours.nombre_de_jours(debut, fin)
    if n <= 1:
        return debut
    js = _jours.jours_de_la_dorra(debut, fin)
    # Isolé en RTL : lisible aussi dans les cellules marquées dir="ltr".
    return Markup(f'<bdi dir="rtl">من <bdi dir="ltr">{escape(js[0])}</bdi> إلى '
                  f'<bdi dir="ltr">{escape(js[-1])}</bdi>'
                  f' <span class="badge-jours">{n} أيّام</span></bdi>')


@app.context_processor
def _injecter_contexte():
    """Rend le jeton CSRF, le rôle et l'identité du centre disponibles dans tous
    les gabarits. L'identité vient de la base : aucun gabarit ne doit contenir
    le nom d'un centre ou d'un responsable en dur (v58 — diffusion multi-centres).
    Une base non encore initialisée ne doit jamais empêcher l'affichage : on
    retombe alors sur les valeurs neutres de core/identite.py."""
    try:
        _cfg = get_config()
    except Exception:
        _log.warning('_injecter_contexte : exception ignorée', exc_info=True)
        _cfg = {}
    return {
        'csrf_token': _jeton_csrf(),
        'utilisateur_role': session.get('role', 'user'),
        'est_admin': session.get('role') == 'admin',
        'identite': identite.fusionner(_cfg),
        'nom_centre': identite.nom_centre(_cfg),
        'destination_dr': identite.destination_dr(_cfg),
        'version_app': identite.VERSION_APP,
        'version_label': identite.VERSION_LABEL,
        'delai_inactivite': delai_inactivite(_cfg) if 'username' in session else 0,
        # v1.6 — listes fermées الجنس / الفئة العمريّة (une seule source : core/validation)
        'SEXES': _validation.SEXES,
        'FIAAT': _validation.FIAAT,
        # v1.7 — alerte d'horloge / annonce d'un سجلّ neuf
        'exercice_etat': _etat_exercice() if 'username' in session else None,
        # V3.1 — base restaurée depuis la miroir (bandeau du مشرف)
        'restauration_miroir': (_miroir.lire_marque_restauration()
                                if session.get('role') == 'admin' else None),
        # V3.2 — bouton « ؟ » : fiche du دليل الاستعمال pour cette page
        'aide_fiche': _aide_fiche(),
        # V3.1 — إشعارات du مشرف عام
        'notifs': _notifs() if session.get('role') == 'admin' and 'username' in session else None,
    }


def _aide_fiche():
    from core import guide as _guide
    try:
        return _guide.fiche_pour(request.endpoint)
    except Exception:
        _log.warning('_aide_fiche : exception ignorée', exc_info=True)
        return ''


def _notifs():
    from core import notifications as _n
    try:
        return _n.resume(session.get('username'))
    except Exception:
        _log.warning('_notifs : exception ignorée', exc_info=True)
        return None


def _etat_exercice():
    from core import exercice as _ex
    try:
        conn = get_connection()
        try:
            return {'ouverte': _ex.annee_active(conn),
                    'alerte': _ex.alerte_horloge(conn),
                    'annonce': _ex.annonce_bascule(conn)}
        finally:
            conn.close()
    except Exception:
        _log.warning('_etat_exercice : exception ignorée', exc_info=True)
        return None


# ─── Auth helpers ────────────────────────────────────────────────────────────

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'username' not in session:
            return redirect(url_for('login'))
        # Mot de passe par défaut encore en place → passage obligatoire par la
        # page de changement avant toute autre action.
        if session.get('doit_changer_mdp') and request.endpoint not in (
                'changer_mot_de_passe', 'logout', 'static'):
            return redirect(url_for('changer_mot_de_passe'))
        return f(*args, **kwargs)
    return decorated


def admin_required(f):
    """Réservé aux مشرف عام."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'username' not in session:
            return redirect(url_for('login'))
        if session.get('doit_changer_mdp') and request.endpoint not in (
                'changer_mot_de_passe', 'logout', 'static'):
            return redirect(url_for('changer_mot_de_passe'))
        if session.get('role') != 'admin':
            app.logger.warning('Accès admin refusé à %s sur %s',
                               session.get('username'), request.path)
            # fetch() (ui.js ajoute X-CSRF-Token) attend du JSON, pas une page.
            if (request.path.startswith('/api/') or request.is_json
                    or request.headers.get('X-CSRF-Token')):
                return jsonify({'erreur': 'هذه العمليّة من مشمولات المشرف العام'}), 403
            return render_template(
                'erreur.html',
                message='هذه الصفحة من مشمولات المشرف العام فقط.'), 403
        return f(*args, **kwargs)
    return decorated


# ─── Enregistrement des routes (regroupées par domaine dans routes/) ─────────

from routes import register_all

register_all(app, {
    'login_required': login_required,
    'admin_required': admin_required,
    '_jeton_csrf':    _jeton_csrf,
    'BASE_DIR':       BASE_DIR,
})


# ─── Lancement ───────────────────────────────────────────────────────────────

if __name__ == '__main__':
    # 1) Sauvegarde AVANT toute migration : si une migration se passait mal,
    #    la base d'origine reste intacte dans data/backups/.
    # v1.7 : aucun PDF ne survit à sa requête — reliquats purgés au démarrage.
    chemins.purger_fichiers_transitoires()

    def _sauvegarde_demarrage():
        chemin_sauvegarde = backup_db()
        if chemin_sauvegarde:
            print(f"✓ Sauvegarde créée → {os.path.basename(chemin_sauvegarde)}")
            app.logger.info('Sauvegarde de démarrage: %s', chemin_sauvegarde)

    # 2) V3.1 : miroir (restauration si la base manque), sauvegarde, puis
    #    création / migration du schéma, archive annuelle et miroir.
    import core.database as _database
    _miroir.demarrer(_database.DB_PATH, init_db, _sauvegarde_demarrage)

    port = 5055
    print(f"✓ Serveur démarré → http://127.0.0.1:{port}")
    app.logger.info('Démarrage de l application sur le port %s', port)
    try:
        from waitress import serve
        serve(app, host='127.0.0.1', port=port)
    except ImportError:
        # Repli sans waitress — JAMAIS en mode debug : le débogueur Werkzeug
        # expose une console d'exécution de code.
        print("waitress introuvable — repli sur le serveur de développement")
        app.run(host='127.0.0.1', port=port, debug=False)
