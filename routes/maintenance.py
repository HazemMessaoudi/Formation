"""V3.1 — النسخة المرآة, استرجاع المنظومة, الأرشيف السّنوي et إشعارات المشرف.

• /secours : seule page servie quand la base est abîmée (app._mode_secours).
  La restauration exige l'identifiant et le mot de passe d'un مشرف عام,
  vérifiés DANS la copie choisie : la base courante est illisible.
• /parametres/miroir/* : emplacement supplémentaire, copie immédiate,
  restauration manuelle (la base remplacée est mise de côté).
• /parametres/archive?annee=AAAA : téléchargement d'une archive annuelle.
• /notifications : إشعارات du مشرف عام (lecture seule du سجلّ التّدقيق).
"""
import os

from flask import (request, redirect, url_for, flash, session, render_template,
                   send_file, jsonify)

from core import database as _db
from core import miroir
from core import notifications
from core.database import journaliser


def _retour_parametres():
    return redirect(url_for('parametres') + '#carteMiroir')


def register(app, ctx):
    admin_required = ctx['admin_required']

    # ─── Base abîmée : page de restauration ─────────────────────────────────

    @app.route('/secours', methods=['GET'])
    def secours():
        if not miroir.ETAT.get('secours'):
            return redirect(url_for('accueil'))
        return render_template('secours.html', copies=miroir.copies_disponibles())

    @app.route('/secours/restaurer', methods=['POST'])
    def secours_restaurer():
        if not miroir.ETAT.get('secours'):
            return redirect(url_for('accueil'))
        copie = request.form.get('copie', '')
        connues = {c['chemin'] for c in miroir.copies_disponibles()}
        if copie not in connues:
            flash('اختر نسخة من القائمة', 'error')
            return redirect(url_for('secours'))
        if not miroir.verifier_admin_dans(copie, request.form.get('utilisateur'),
                                          request.form.get('mot_de_passe')):
            flash('اسم المستخدم أو كلمة المرور غير صحيحة، أو الحساب ليس مشرفًا عامًّا في هذه النسخة', 'error')
            return redirect(url_for('secours'))
        try:
            info = miroir.restaurer_depuis(copie, motif='endommagee')
            _db.init_db()
        except Exception as e:
            app.logger.exception('restauration de secours')
            flash('فشل الاسترجاع: ' + str(e)[:120], 'error')
            return redirect(url_for('secours'))
        miroir.ETAT['secours'] = ''
        journaliser(request.form.get('utilisateur', ''), 'استرجاع القاعدة بعد تلفها',
                    info.get('source', ''), 'نسخة بتاريخ ' + info.get('date_copie', ''))
        miroir.ecrire_miroir()
        session.clear()
        flash('تمّ استرجاع قاعدة البيانات بنجاح. سجّل الدخول من جديد.', 'success')
        return redirect(url_for('login'))

    # ─── Réglages de la miroir (مشرف عام) ────────────────────────────────────

    @app.route('/parametres/miroir', methods=['POST'])
    @admin_required
    def parametres_miroir():
        chemin = '' if request.form.get('defaut') == '1' else request.form.get('emplacement', '')
        try:
            miroir.definir_emplacement(chemin)
        except ValueError as e:
            flash(str(e), 'error')
            return _retour_parametres()
        n = miroir.ecrire_miroir()
        journaliser(session.get('username'), 'تغيير مكان النسخة المرآة', chemin or 'المكان الافتراضي', '')
        if chemin and n < len(miroir.dossiers_miroir()):
            flash('حُفظ المكان، لكن تعذّر نسخ المرآة إليه الآن: ' + miroir.ETAT.get('erreur', ''), 'warning')
        else:
            flash('تمّ حفظ مكان النسخة المرآة وتحيينها', 'success')
        return _retour_parametres()

    @app.route('/parametres/miroir/maintenant', methods=['POST'])
    @admin_required
    def miroir_maintenant():
        n = miroir.ecrire_miroir()
        if n:
            flash('تمّ تحيين النسخة المرآة', 'success')
        else:
            flash('تعذّر تحيين النسخة المرآة: ' + miroir.ETAT.get('erreur', ''), 'error')
        return _retour_parametres()

    @app.route('/parametres/miroir/restaurer', methods=['POST'])
    @admin_required
    def miroir_restaurer():
        copie = request.form.get('copie', '')
        try:
            info = miroir.restaurer_depuis(copie, motif='manuelle')
            _db.init_db()
        except ValueError as e:
            flash(str(e), 'error')
            return _retour_parametres()
        except Exception as e:
            app.logger.exception('restauration manuelle')
            flash('فشل الاسترجاع: ' + str(e)[:120], 'error')
            return _retour_parametres()
        utilisateur = session.get('username')
        journaliser(utilisateur, 'استرجاع القاعدة من نسخة سابقة',
                    info.get('source', ''), 'نسخة بتاريخ ' + info.get('date_copie', ''))
        session.clear()
        flash('تمّ استرجاع النسخة. سجّل الدخول من جديد.', 'success')
        return redirect(url_for('login'))

    @app.route('/parametres/miroir/acquitter', methods=['POST'])
    @admin_required
    def miroir_acquitter():
        miroir.effacer_marque_restauration()
        suivant = request.form.get('suivant') or ''
        if not suivant.startswith('/') or suivant.startswith('//'):
            suivant = url_for('accueil')
        return redirect(suivant)

    @app.route('/parametres/archive')
    @admin_required
    def archive_telecharger():
        annee = (request.args.get('annee') or '').strip()
        cible = next((a for a in miroir.archives() if str(a['annee']) == annee), None)
        if not cible:
            flash('الأرشيف المطلوب غير موجود', 'error')
            return _retour_parametres()
        journaliser(session.get('username'), 'تنزيل أرشيف سنة', annee, '')
        return send_file(cible['chemin'], as_attachment=True,
                         download_name=os.path.basename(cible['chemin']))

    # ─── إشعارات المشرف العام ────────────────────────────────────────────────

    @app.route('/notifications')
    @admin_required
    def notifications_page():
        r = notifications.resume(session.get('username'), limite=300)
        return render_template('notifications.html', r=r)

    @app.route('/notifications/lues', methods=['POST'])
    @admin_required
    def notifications_lues():
        notifications.marquer_lues(session.get('username'))
        if request.headers.get('X-CSRF-Token') or request.is_json:
            return jsonify({'ok': True})
        suivant = request.form.get('suivant') or ''
        if not suivant.startswith('/') or suivant.startswith('//'):
            suivant = url_for('notifications_page')
        return redirect(suivant)
