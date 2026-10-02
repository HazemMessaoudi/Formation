"""Sécurité et maintenance (v1.5).

• S3 — déconnexion automatique après inactivité : réglage du délai
  (/parametres/securite) et prolongation d'une session ACTIVE (/api/ping).
  Le contrôle lui-même vit dans app._valider_session, qui s'applique à
  toutes les requêtes.
• S2 — sauvegarde : téléchargement d'une copie cohérente de la base (zip),
  et création immédiate d'une copie dans data/backups/.
"""
import glob
import os
import sqlite3
import tempfile
import zipfile
from datetime import datetime
from io import BytesIO

from flask import request, redirect, url_for, flash, session, jsonify, send_file

from core import database as _db
from core.database import update_config, journaliser, backup_db
from core.securite import DELAIS_INACTIVITE


def register(app, ctx):
    login_required = ctx['login_required']
    admin_required = ctx['admin_required']

    @app.route('/api/ping', methods=['POST'])
    @login_required
    def api_ping():
        """Appelé par le navigateur tant que l'utilisateur interagit avec la
        page (saisie longue sans requête) : _valider_session a déjà rafraîchi
        l'horodatage de la session, il n'y a rien d'autre à faire."""
        return jsonify({'ok': True})

    @app.route('/parametres/securite', methods=['POST'])
    @admin_required
    def parametres_securite():
        try:
            delai = int(request.form.get('delai_inactivite', ''))
        except ValueError:
            delai = -1
        if delai not in DELAIS_INACTIVITE:
            flash('قيمة غير مقبولة لمدّة عدم النشاط', 'error')
            return redirect(url_for('parametres'))
        update_config('delai_inactivite', str(delai))
        journaliser(session.get('username'), 'تعديل مدّة الخروج التلقائي', 'config',
                    'معطّل' if delai == 0 else f'{delai} دقيقة')
        flash('تمّ إيقاف الخروج التلقائي' if delai == 0 else
              f'تمّ الحفظ: خروج تلقائي بعد {delai} دقيقة من عدم النشاط', 'success')
        return redirect(url_for('parametres'))


    # ─── v1.7 : السّجلّ السّنوي — annonce et ouverture confirmée ─────────────

    @app.route('/exercice/acquitter', methods=['POST'])
    @login_required
    def exercice_acquitter():
        from core import exercice as _ex
        conn = _db.get_connection()
        try:
            _ex.acquitter_annonce(conn)
            conn.commit()
        finally:
            conn.close()
        suivant = request.form.get('suivant') or ''
        if not suivant.startswith('/') or suivant.startswith('//'):
            suivant = url_for('accueil')
        return redirect(suivant)

    @app.route('/exercice/ouvrir', methods=['POST'])
    @admin_required
    def exercice_ouvrir():
        """Ouverture confirmée du سجلّ de l'année système, après une alerte
        d'horloge (saut de plus d'une année)."""
        from core import exercice as _ex
        cfg = _db.get_config()
        conn = _db.get_connection()
        try:
            try:
                anc, nouv = _ex.ouvrir_annee_confirmee(conn, request.form.get('annee', ''), {
                    'interne': cfg.get('numero_depart_interne') or 1,
                    'externe': cfg.get('numero_depart_externe') or 1,
                })
                conn.commit()
            except (TypeError, ValueError) as e:
                flash(str(e) if str(e) and not str(e).startswith('invalid') else 'سنة غير صالحة', 'error')
                return redirect(url_for('accueil'))
        finally:
            conn.close()
        journaliser(session.get('username'), 'فتح سجلّ سنة جديدة بتأكيد المشرف',
                    str(nouv), f'السّجلّ السابق: {anc}')
        flash(f'تمّ فتح سجلّ سنة {nouv}', 'success')
        return redirect(url_for('accueil'))

    # ─── S2 : sauvegardes ────────────────────────────────────────────────────

    @app.route('/parametres/sauvegarde/telecharger')
    @admin_required
    def telecharger_sauvegarde():
        """Copie COHÉRENTE de la base (API de sauvegarde SQLite : valable même
        pendant l'utilisation), vérifiée (integrity_check), compressée."""
        stamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        dossier = tempfile.mkdtemp(prefix='sauv_')
        copie = os.path.join(dossier, 'formation.db')
        try:
            src = sqlite3.connect(_db.DB_PATH)
            dst = sqlite3.connect(copie)
            with dst:
                src.backup(dst)
            verdict = dst.execute('PRAGMA integrity_check').fetchone()[0]
            dst.close()
            src.close()
            if verdict != 'ok':
                flash('تعذّر إعداد النسخة: فحص سلامة القاعدة لم ينجح (' + str(verdict)[:80] + ')', 'error')
                return redirect(url_for('parametres'))
            flux = BytesIO()
            with zipfile.ZipFile(flux, 'w', zipfile.ZIP_DEFLATED) as z:
                z.write(copie, 'formation.db')
                z.writestr('LISEZ-MOI.txt', (
                    'نسخة احتياطية من قاعدة بيانات نظام إدارة التكوين\n'
                    f'تاريخ النسخة: {datetime.now():%Y-%m-%d %H:%M:%S}\n'
                    'للاسترجاع: أغلق البرنامج، ثمّ ضع الملفّ formation.db مكان الملفّ '
                    'الموجود في المجلّد data/ ثمّ أعد تشغيل البرنامج.\n').encode('utf-8'))
            flux.seek(0)
        finally:
            for f in glob.glob(os.path.join(dossier, '*')):
                try:
                    os.remove(f)
                except OSError:
                    pass
            try:
                os.rmdir(dossier)
            except OSError:
                pass
        journaliser(session.get('username'), 'تنزيل نسخة احتياطية', 'formation.db', stamp)
        return send_file(flux, mimetype='application/zip', as_attachment=True,
                         download_name=f'sauvegarde_formation_{stamp}.zip')

    @app.route('/parametres/cachet', methods=['POST'])
    @admin_required
    def parametres_cachet():
        """v1.7 — الختم الرّقمي : désactivé par défaut, activable par le
        مشرف عام seul."""
        actif = '1' if request.form.get('cachet_actif') == '1' else '0'
        update_config('cachet_actif', actif)
        journaliser(session.get('username'), 'تفعيل الختم الرقمي' if actif == '1'
                    else 'تعطيل الختم الرقمي', 'config', '')
        flash('تمّ تفعيل الختم الرقمي على الوثائق' if actif == '1'
              else 'تمّ تعطيل الختم الرقمي', 'success')
        return redirect(url_for('parametres') + '#carteSecurite')

    @app.route('/parametres/sauvegarde/externe', methods=['POST'])
    @admin_required
    def sauvegarde_externe():
        """v1.7 — copie vérifiée vers une clé USB / un disque / un dossier."""
        from core.database import copier_vers_externe
        destination = (request.form.get('chemin') or '').strip() or \
                      (request.form.get('lecteur') or '').strip()
        try:
            chemin = copier_vers_externe(destination)
        except ValueError as e:
            flash(str(e), 'error')
            return redirect(url_for('parametres') + '#carteSecurite')
        journaliser(session.get('username'), 'نسخة احتياطيّة خارجيّة', destination,
                    os.path.basename(chemin))
        flash('تمّت النسخة الخارجيّة بنجاح وفُحصت سلامتها: ' + chemin, 'success')
        return redirect(url_for('parametres') + '#carteSecurite')

    @app.route('/parametres/sauvegarde/creer', methods=['POST'])
    @admin_required
    def creer_sauvegarde():
        chemin = backup_db()
        if not chemin:
            flash('تعذّر إنشاء النسخة الاحتياطيّة', 'error')
        else:
            journaliser(session.get('username'), 'إنشاء نسخة احتياطية', os.path.basename(chemin), '')
            flash('تمّ إنشاء نسخة احتياطيّة في مجلّد البرنامج: ' + os.path.basename(chemin), 'success')
        return redirect(url_for('parametres') + '#carteSecurite')


def etat_sauvegardes():
    """(nombre de copies automatiques, date de la plus récente ou '')."""
    dossier = os.path.join(os.path.dirname(_db.DB_PATH), 'backups')
    fichiers = sorted(glob.glob(os.path.join(dossier, 'formation_*.db')))
    if not fichiers:
        return 0, ''
    return len(fichiers), datetime.fromtimestamp(os.path.getmtime(fichiers[-1])).strftime('%Y-%m-%d %H:%M')
