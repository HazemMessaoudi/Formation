"""المكونين — liste, fiche, ajout, modification et suppression des formateurs."""

from datetime import datetime

import logging as _logging

from flask import render_template, request, redirect, url_for, flash, jsonify, session

from core.database import (
    get_grades, get_mkowin, get_mkow, add_mkow, update_mkow, delete_mkow,
    delete_mkowin_lot, noms_jihat, get_connection, suggestions_mkowin,
    nb_dorrat_liees_mkow, journaliser,
    dorrat_liees_mkowin,
)
from core import fiche_mkow_import as _fiche
from core.validation import verifier_identite, verifier_choix

_log = _logging.getLogger('formation.' + __name__)


def _deja_inscrit(identifiant='', cin='', sauf=None):
    """La fiche qui porte déjà ce معرّف وحيد ou ce رقم بطاقة تعريف, ou None.

    Deux fiches pour une même personne, c'est deux وثائق خلاص possibles pour
    un seul مكوّن : l'ajout est refusé et l'agent envoyé vers la fiche."""
    identifiant, cin = (identifiant or '').strip(), (cin or '').strip()
    if not identifiant and not cin:
        return None
    conn = get_connection()
    try:
        for col, val in (('identifiant_unique', identifiant), ('cin', cin)):
            if not val:
                continue
            sql = f"SELECT id, nom, prenom, {col} AS cle FROM mkowin WHERE TRIM({col}) = ?"
            args = [val]
            if sauf:
                sql += ' AND id <> ?'
                args.append(sauf)
            r = conn.execute(sql, args).fetchone()
            if r:
                return dict(r, par=col)
        return None
    finally:
        conn.close()
from core.database import _CHAMPS_MKOW


def _mkow_from_form(form):
    """Ne retourne que les خانات réellement présentes dans le formulaire.

    La différence avec l'ancienne version — qui retournait les vingt et une
    خانات, absentes comprises, sous forme de chaînes vides — n'est pas
    cosmétique. Depuis la v58 la fiche du مكوّن porte une خانة de plus
    (`jiha_marjiiya`). Un formulaire qui ne l'affiche pas aurait, à chaque
    enregistrement, renvoyé une valeur vide pour elle et effacé la جهة du
    مكوّن sans que personne ne le voie.

    Ce qui n'est pas montré n'est pas soumis, et ce qui n'est pas soumis
    n'est pas écrit : `update_mkow` applique la même règle côté قاعدة.
    """
    data = {}
    for cle in _CHAMPS_MKOW:
        if cle in form:
            data[cle] = form.get(cle, '').strip()
    return data


def register(app, ctx):
    login_required = ctx['login_required']
    admin_required = ctx['admin_required']

    @app.route('/mkowin')
    @login_required
    def liste_mkowin():
        mkowin = get_mkowin()
        return render_template('mkowin/liste.html', mkowin=mkowin, now_year=datetime.now().year,
                               liees=dorrat_liees_mkowin() if session.get('role') == 'admin' else {})

    @app.route('/mkowin/ajouter', methods=['GET', 'POST'])
    @login_required
    def ajouter_mkow():
        grades = get_grades()
        if request.method == 'POST':
            data = _mkow_from_form(request.form)
            erreurs = verifier_identite(data) + verifier_choix(data)
            if erreurs:
                for e in erreurs:
                    flash(e, 'error')
                return render_template('mkowin/ajouter.html', grades=grades, jihat=noms_jihat(),
                                       suggestions=suggestions_mkowin(), valeurs=data,
                                       now_year=datetime.now().year)
            doublon = _deja_inscrit(data.get('identifiant_unique'), data.get('cin'))
            if not data.get('nom'):
                flash('يرجى إدخال اسم المكوِّن', 'error')
            elif doublon:
                quoi = 'المعرّف الوحيد' if doublon['par'] == 'identifiant_unique' else 'رقم بطاقة التعريف'
                flash(f'هذا الشخص مسجَّل مسبقًا ({quoi} {doublon["cle"]}): '
                      f'{doublon["nom"]} {doublon["prenom"] or ""}. افتح بطاقته لتحيينها.', 'error')
                return render_template('mkowin/ajouter.html', grades=grades, jihat=noms_jihat(), suggestions=suggestions_mkowin(),
                                       valeurs=data, doublon=doublon,
                                       now_year=datetime.now().year)
            else:
                if add_mkow(data):
                    flash('تمت إضافة المكوِّن بنجاح', 'success')
                    return redirect(url_for('liste_mkowin'))
                else:
                    flash('خطأ في الحفظ', 'error')
        return render_template('mkowin/ajouter.html', grades=grades,
                               jihat=noms_jihat(), suggestions=suggestions_mkowin(), now_year=datetime.now().year)

    @app.route('/mkowin/importer-fiche', methods=['POST'])
    @login_required
    def importer_fiche_mkow():
        """Lit une بطاقة شخص (doc/docx/xls/xlsx) et rend les خانات reconnues.

        N'enregistre RIEN : le navigateur pré-remplit le formulaire, l'agent
        relit et corrige, puis enregistre lui-même."""
        f = request.files.get('fichier')
        if not f or not f.filename:
            return jsonify({'succes': False, 'erreur': 'لم يتمّ اختيار ملفّ'}), 400
        try:
            champs, avert = _fiche.analyser(f.read(), f.filename)
        except _fiche.ErreurFiche as e:
            return jsonify({'succes': False, 'erreur': str(e)}), 400
        except Exception:
            _log.warning('importer_fiche_mkow : exception ignorée', exc_info=True)
            return jsonify({'succes': False, 'erreur': 'تعذّرت قراءة الملفّ.'}), 400
        if not champs:
            return jsonify({'succes': False,
                            'erreur': 'لم يتعرّف النظام على أيّ معطى شخصيّ في الملفّ.'}), 400
        # La رتبة doit être l'une des options de la liste.
        if champs.get('grade'):
            exacte = _fiche.rapprocher_grade(champs['grade'], get_grades())
            if exacte:
                champs['grade'] = exacte
            else:
                avert.append(f'الرتبة «{champs["grade"]}» غير موجودة في قائمة الرتب: اخترها يدويًّا.')
                champs.pop('grade')
        doublon = _deja_inscrit(champs.get('identifiant_unique'), champs.get('cin'))
        return jsonify({'succes': True, 'champs': champs, 'avertissements': avert,
                        'existe': ({'id': doublon['id'],
                                    'nom': f"{doublon['nom']} {doublon['prenom'] or ''}".strip(),
                                    'url': url_for('modifier_mkow', mkow_id=doublon['id'])}
                                   if doublon else None)})

    @app.route('/mkowin/<int:mkow_id>/modifier', methods=['GET', 'POST'])
    @login_required
    def modifier_mkow(mkow_id):
        mkow = get_mkow(mkow_id)
        if not mkow:
            return redirect(url_for('liste_mkowin'))
        grades = get_grades()
        if request.method == 'POST':
            data = _mkow_from_form(request.form)
            erreurs = verifier_identite(data) + verifier_choix(data)
            if erreurs:
                for e in erreurs:
                    flash(e, 'error')
                # La saisie de l'agent est gardée : il corrige la خانة fautive
                # sans retaper le reste de la fiche.
                return render_template('mkowin/modifier.html', mkow={**dict(mkow), **data},
                                       grades=grades, jihat=noms_jihat(),
                                       suggestions=suggestions_mkowin(), now_year=datetime.now().year)
            doublon = _deja_inscrit(data.get('identifiant_unique'), data.get('cin'), sauf=mkow_id)
            if doublon:
                flash(f'هذا المعرّف أو رقم بطاقة التعريف يخصّ بطاقة أخرى: '
                      f'{doublon["nom"]} {doublon["prenom"] or ""}.', 'error')
                return redirect(url_for('modifier_mkow', mkow_id=mkow_id))
            if update_mkow(mkow_id, data):
                flash('تم تحيين بيانات المكوِّن بنجاح', 'success')
                return redirect(url_for('fiche_mkow', mkow_id=mkow_id))
            flash('خطأ في الحفظ', 'error')
        return render_template('mkowin/modifier.html', mkow=mkow, grades=grades,
                               jihat=noms_jihat(), suggestions=suggestions_mkowin(), now_year=datetime.now().year)

    @app.route('/mkowin/<int:mkow_id>')
    @login_required
    def fiche_mkow(mkow_id):
        mkow = get_mkow(mkow_id)
        if not mkow:
            return redirect(url_for('liste_mkowin'))
        return render_template('mkowin/fiche.html', mkow=mkow, now_year=datetime.now().year,
                               nb_liees=nb_dorrat_liees_mkow(mkow_id))

    @app.route('/mkowin/<int:mkow_id>/supprimer', methods=['POST'])
    @admin_required
    def supprimer_mkow(mkow_id):
        mkow = get_mkow(mkow_id)
        nb = nb_dorrat_liees_mkow(mkow_id)
        delete_mkow(mkow_id)
        if mkow:
            journaliser(session.get('username'), 'حذف مكوّن',
                        f"{mkow.get('nom') or ''} {mkow.get('prenom') or ''}".strip(),
                        f'مرتبط بـ {nb} دورة' if nb else '')
        flash('تم حذف الإسم', 'success')
        return redirect(url_for('liste_mkowin'))

    @app.route('/mkowin/supprimer-lot', methods=['POST'])
    @admin_required
    def supprimer_mkowin_lot():
        """Suppression groupée depuis les cases à cocher de la liste."""
        ids = request.form.getlist('ids')
        n = delete_mkowin_lot(ids)
        flash(f'تم فسخ {n} إسم' if n else 'لم يتمّ اختيار أيّ إسم', 'success' if n else 'error')
        return redirect(url_for('liste_mkowin'))
