"""مواد التكوين — liste, fiche, ajout, modification et suppression des matières."""

import logging as _logging
_log = _logging.getLogger('formation.' + __name__)

import io
from datetime import datetime

from flask import (render_template, request, redirect, url_for, flash,
                   jsonify, send_file, session)

from core.database import (
    get_mkowin, get_mawad, get_madda, add_madda, update_madda, delete_madda,
    delete_mawad_lot, get_madda_by_titre, nb_dorrat_liees_madda, journaliser,
    dorrat_liees_mawad,
)
from core.bataqa_import import analyser, construire_modele, ErreurBataqa


def _madda_from_form(form):
    return {
        'titre':                   form.get('titre', '').strip(),
        'type_formation':          form.get('type_formation', 'أساسي').strip(),
        'mahawer':                 form.get('mahawer', '').strip(),
        'objectifs':               form.get('objectifs', '').strip(),
        'methodes_pedagogiques':   form.get('methodes_pedagogiques', '').strip(),
        'moyens_pedagogiques':     form.get('moyens_pedagogiques', '').strip(),
        'preparation_materielle':  form.get('preparation_materielle', '').strip(),
        'equipements':             form.get('equipements', '').strip(),
        'mustahdafun':             form.get('mustahdafun', '').strip(),
        'lieu_formation_defaut':   form.get('lieu_formation_defaut', '').strip(),
    }


def register(app, ctx):
    login_required = ctx['login_required']
    admin_required = ctx['admin_required']

    @app.route('/mawad')
    @login_required
    def liste_mawad():
        mawad = get_mawad()
        return render_template('mawad/liste.html', mawad=mawad, now_year=datetime.now().year,
                               liees=dorrat_liees_mawad() if session.get('role') == 'admin' else {})

    @app.route('/mawad/ajouter', methods=['GET', 'POST'])
    @login_required
    def ajouter_madda():
        mkowin = get_mkowin()
        if request.method == 'POST':
            data = _madda_from_form(request.form)
            remplacer_id = request.form.get('remplacer_id', type=int)
            if not data['titre']:
                flash('يرجى إدخال عنوان مادة التكوين', 'error')
            elif remplacer_id:
                # L'utilisateur a choisi « إلغاء القديم وتعويضه » sur un titre
                # déjà présent : on met à jour la fiche existante, sans doublon.
                if update_madda(remplacer_id, data):
                    flash('تمّ تعويض التكوين الموجود بالجديد', 'success')
                    return redirect(request.args.get('next', url_for('liste_mawad')))
                flash('خطأ في الحفظ', 'error')
            elif add_madda(data):
                flash('تمت إضافة مادة التكوين بنجاح', 'success')
                return redirect(request.args.get('next', url_for('liste_mawad')))
            else:
                flash('خطأ في الحفظ', 'error')
        return render_template('mawad/ajouter.html', mkowin=mkowin, now_year=datetime.now().year)

    @app.route('/mawad/modele-bataqa')
    @login_required
    def modele_bataqa():
        """Télécharge le قالب .xlsx d'une بطاقة بيداغوجية (lecture 100% fiable)."""
        data = construire_modele()
        return send_file(
            io.BytesIO(data),
            mimetype='application/vnd.openxmlformats-officedocument.'
                     'spreadsheetml.sheet',
            as_attachment=True, download_name='قالب_بطاقة_بيداغوجية.xlsx')

    @app.route('/mawad/importer', methods=['POST'])
    @login_required
    def importer_bataqa():
        """Lit un fichier بطاقة (xlsx/docx/قالب) et renvoie les خانات reconnues.

        Ne sauvegarde RIEN : c'est le navigateur qui pré-remplit le formulaire,
        et l'utilisateur relit avant d'enregistrer. Signale si le عنوان existe
        déjà (existe_id) pour laisser le choix : تعويض ou تغيير العنوان."""
        f = request.files.get('fichier')
        if not f or not f.filename:
            return jsonify({'succes': False, 'erreur': 'لم يتمّ اختيار ملفّ'}), 400
        try:
            champs = analyser(f.read(), f.filename)
        except ErreurBataqa as e:
            return jsonify({'succes': False, 'erreur': str(e)}), 400
        except Exception:
            _log.warning('importer_bataqa : exception ignorée', exc_info=True)
            return jsonify({'succes': False,
                            'erreur': 'تعذّرت قراءة الملفّ.'}), 400
        if not champs:
            return jsonify({'succes': False,
                            'erreur': 'لم يتعرّف النظام على أيّ حقل في الملفّ. '
                                      'استعمل القالب الجاهز لضمان القراءة.'}), 400
        existe_id = None
        if champs.get('titre'):
            m = get_madda_by_titre(champs['titre'])
            if m:
                existe_id = m['id']
        return jsonify({'succes': True, 'champs': champs, 'existe_id': existe_id})

    @app.route('/mawad/<int:madda_id>/modifier', methods=['GET', 'POST'])
    @login_required
    def modifier_madda(madda_id):
        madda = get_madda(madda_id)
        if not madda:
            return redirect(url_for('liste_mawad'))
        mkowin = get_mkowin()
        if request.method == 'POST':
            data = _madda_from_form(request.form)
            if update_madda(madda_id, data):
                flash('تم تحيين مادة التكوين بنجاح', 'success')
                return redirect(url_for('fiche_madda', madda_id=madda_id))
            flash('خطأ في الحفظ', 'error')
        return render_template('mawad/modifier.html', madda=madda, mkowin=mkowin, now_year=datetime.now().year)

    @app.route('/mawad/<int:madda_id>')
    @login_required
    def fiche_madda(madda_id):
        madda = get_madda(madda_id)
        if not madda:
            return redirect(url_for('liste_mawad'))
        return render_template('mawad/fiche.html', madda=madda, now_year=datetime.now().year,
                               nb_liees=nb_dorrat_liees_madda(madda_id))

    @app.route('/mawad/<int:madda_id>/supprimer', methods=['POST'])
    @admin_required
    def supprimer_madda(madda_id):
        madda = get_madda(madda_id)
        nb = nb_dorrat_liees_madda(madda_id)
        delete_madda(madda_id)
        if madda:
            journaliser(session.get('username'), 'حذف مادّة تكوين', madda.get('titre') or '',
                        f'مرتبطة بـ {nb} دورة' if nb else '')
        flash('تم حذف مادّة التكوين', 'success')
        return redirect(url_for('liste_mawad'))

    @app.route('/mawad/supprimer-lot', methods=['POST'])
    @admin_required
    def supprimer_mawad_lot():
        """Suppression groupée depuis les cases à cocher de la liste."""
        ids = request.form.getlist('ids')
        n = delete_mawad_lot(ids)
        flash(f'تم فسخ {n} مادّة تكوين' if n else 'لم يتمّ اختيار أيّ مادّة',
              'success' if n else 'error')
        return redirect(url_for('liste_mawad'))
