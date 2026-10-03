"""Connexion, déconnexion et changement de mot de passe."""

import time
from flask import render_template, request, redirect, url_for, flash, session

from core.database import (
    check_credentials, get_user_role, user_doit_changer_mdp,
    update_user_password, journaliser, get_config,
    minutes_de_blocage, noter_echec, remettre_a_zero_echecs, longueur_min_mdp,
    ECHECS_MAX, BLOCAGE_MINUTES,
)


def register(app, ctx):
    _jeton_csrf = ctx['_jeton_csrf']

    # ─── Login / Logout ──────────────────────────────────────────────────────

    # v1.0 — TOUTE entrée dans la منظومة débouche sur la شاشة رئيسية aux
    # trois portes. Avant la 1.0 c'était لوحة القيادة ; la redirection
    # `/` → `/accueil` ne suffisait pas, car le lanceur ouvre `/`, le حارس
    # renvoie vers `/login`, et c'est `/login` qui décide où l'on atterrit.
    ECRAN_DACCUEIL = 'accueil'

    @app.route('/login', methods=['GET', 'POST'])
    def login():
        if 'username' in session:
            return redirect(url_for(ECRAN_DACCUEIL))
        error = None
        if request.method == 'POST':
            username = request.form.get('username', '').strip()
            password = request.form.get('password', '')
            # v1.7 : compte bloqué quelques minutes après 5 échecs consécutifs.
            reste = minutes_de_blocage(username) if username else 0
            if reste:
                app.logger.warning('Connexion refusée (compte bloqué): %s', username)
                return render_template(
                    'login.html', info=None,
                    error=f'تمّ إيقاف هذا الحساب مؤقّتًا بعد {ECHECS_MAX} محاولات خاطئة. '
                          f'أعد المحاولة بعد {reste} دقيقة.')
            if check_credentials(username, password):
                remettre_a_zero_echecs(username)
                session.clear()                      # évite la fixation de session
                session['username'] = username
                session['role'] = get_user_role(username)
                session['doit_changer_mdp'] = user_doit_changer_mdp(username)
                # La session est liée à CETTE base (voir _valider_session).
                session['_instance'] = get_config().get('instance_id', '')
                session['_vu'] = int(time.time())       # S3 : début d'activité
                _jeton_csrf()
                journaliser(username, 'دخول إلى النظام')
                app.logger.info('Connexion réussie: %s', username)
                # V3.1 — إشعارات : le مشرف عام voit d'emblée ce qui a changé
                if session['role'] == 'admin':
                    from core import notifications as _notifs
                    message = _notifs.message_connexion(username)
                    if message:
                        flash(message, 'info')
                if session['doit_changer_mdp']:
                    return redirect(url_for('changer_mot_de_passe'))
                return redirect(url_for(ECRAN_DACCUEIL))
            app.logger.warning('Échec de connexion pour: %s', username)
            error = 'اسم المستخدم أو كلمة المرور غير صحيحة'
            if username and noter_echec(username):
                journaliser(username, 'إيقاف مؤقّت للحساب بعد محاولات دخول خاطئة', '',
                            f'{ECHECS_MAX} محاولات — {BLOCAGE_MINUTES} دقائق')
                error = (f'تمّ إيقاف هذا الحساب مؤقّتًا بعد {ECHECS_MAX} محاولات خاطئة. '
                         f'أعد المحاولة بعد {BLOCAGE_MINUTES} دقائق.')
        # S3 : retour après une déconnexion automatique pour inactivité.
        info = None
        if request.args.get('expire') and not error:
            info = 'تمّ إغلاق الجلسة تلقائيًّا بعد فترة من عدم النشاط. يرجى تسجيل الدخول من جديد.'
        return render_template('login.html', error=error, info=info)

    @app.route('/logout')
    def logout():
        utilisateur = session.get('username')
        auto = bool(request.args.get('inactivite'))
        if utilisateur:
            journaliser(utilisateur, 'خروج تلقائي بسبب عدم النشاط' if auto else 'خروج من النظام')
        session.clear()
        return redirect(url_for('login', expire=1) if auto else url_for('login'))

    @app.route('/changer-mot-de-passe', methods=['GET', 'POST'])
    def changer_mot_de_passe():
        """Changement obligatoire du mot de passe par défaut, et changement
        volontaire à tout moment."""
        if 'username' not in session:
            return redirect(url_for('login'))
        username = session['username']
        erreur = None
        if request.method == 'POST':
            actuel  = request.form.get('actuel', '')
            nouveau = request.form.get('nouveau', '')
            confirm = request.form.get('confirmation', '')
            if not check_credentials(username, actuel):
                erreur = 'كلمة المرور الحالية غير صحيحة'
            elif len(nouveau) < longueur_min_mdp(get_user_role(username)):
                erreur = ('كلمة المرور الجديدة يجب أن تتكوّن من '
                          f'{longueur_min_mdp(get_user_role(username))} رموز على الأقلّ')
            elif nouveau != confirm:
                erreur = 'كلمتا المرور غير متطابقتين'
            elif nouveau == actuel:
                erreur = 'كلمة المرور الجديدة يجب أن تختلف عن الحالية'
            else:
                update_user_password(username, nouveau)
                session['doit_changer_mdp'] = False
                journaliser(username, 'تغيير كلمة المرور')
                app.logger.info('Mot de passe changé: %s', username)
                flash('تمّ تغيير كلمة المرور بنجاح', 'success')
                return redirect(url_for(ECRAN_DACCUEIL))
        return render_template('changer_mot_de_passe.html', erreur=erreur,
                               oblige=bool(session.get('doit_changer_mdp')),
                               longueur_min=longueur_min_mdp(get_user_role(username)))
