# -*- coding: utf-8 -*-
"""الجهات المرجعيّة — إدارة قائمة الإدارات الجهويّة ووحدات الحرس الدّيواني.

Pourquoi une page à part
========================
La جهة d'un مكوّن ou d'un مشارك était saisie à la main, en toutes lettres, à
chaque fois. Le même service finissait écrit de trois ou quatre manières
(« الادارة الجهوية بالقصرين », « الإدارة الجهويّة للدّيوانة بالقصرين »…) et le
classement des مشاركين par جهة devenait impossible : deux orthographes, deux
groupes. Une liste tenue en un seul endroit règle le problème à la source.

Ce que la page permet, et ce qu'elle ne permet pas
=================================================
Elle ajoute et retire des libellés. Elle ne renomme pas : les جهات déjà
inscrites sur les fiches sont stockées en toutes lettres, pas par référence,
donc retirer une جهة de la liste ne touche à aucune fiche existante — c'est
voulu, une correction de liste ne doit pas réécrire l'historique.
"""

from datetime import datetime

from flask import render_template, request, redirect, url_for, flash, session

from core import regions
from core.database import (
    get_jihat_groupees, add_jiha, delete_jiha, journaliser,
)


def register(app, ctx):
    login_required = ctx['login_required']

    @app.route('/jihat')
    @login_required
    def liste_jihat():
        return render_template(
            'jihat.html',
            groupes=get_jihat_groupees(),
            types=regions.TYPES,
            libelles=regions.LIBELLES_TYPES,
            exemple_garde=regions.EXEMPLE_GARDE,
            now_year=datetime.now().year,
        )

    @app.route('/jihat/ajouter', methods=['POST'])
    @login_required
    def ajouter_jiha():
        nom = (request.form.get('nom') or '').strip()
        type_jiha = (request.form.get('type') or regions.TYPE_AUTRE).strip()
        if not nom:
            flash('يرجى إدخال اسم الجهة', 'error')
        elif add_jiha(nom, type_jiha):
            journaliser(session.get('username'), 'إضافة جهة مرجعيّة', nom, type_jiha)
            flash('تمّت إضافة الجهة', 'success')
        else:
            flash('الجهة موجودة في القائمة', 'error')
        return redirect(url_for('liste_jihat'))

    @app.route('/jihat/<int:jiha_id>/supprimer', methods=['POST'])
    @login_required
    def supprimer_jiha(jiha_id):
        if delete_jiha(jiha_id):
            journaliser(session.get('username'), 'حذف جهة مرجعيّة', str(jiha_id))
            flash('تمّ حذف الجهة من القائمة. البيانات المسجّلة سابقا لم تتغيّر.',
                  'success')
        else:
            flash('تعذّر الحذف', 'error')
        return redirect(url_for('liste_jihat'))
