# -*- coding: utf-8 -*-
"""وثائق الخلاص — المعالج ذو 4 خطوات، الحفظ، المعاينة، توليد PDF، الإعدادات.

Le module ne fabrique aucune donnée nouvelle : il assemble ce que la منظومة sait
déjà (core/khalas.assembler) et n'ajoute que les quelques champs propres au
règlement. La fiche du المكوّن est mise à jour à l'enregistrement — saisie une
fois, réutilisée ensuite ; les المراجع الإدارية vivent dans les إعدادات.
"""

from flask import (render_template, request, jsonify, send_file,
                   redirect, url_for, session, flash)

from core import khalas as _k
from core import pdf_khalas
from core.validation import verifier_identite
from core.database import (
    get_dorra_mustahaqqat, save_khalas_dorra, get_muqarrar_dorra,
    get_khalas_settings, set_khalas_settings, trouver_mkow_par_nom,
    candidats_mkow_par_nom,
    update_mkow, add_mkow, journaliser,
)

# Champs personnels stockés dans la fiche mkowin (réutilisés d'une دورة à l'autre)
CHAMPS_MKOW = ('cin', 'cin_date', 'identifiant_unique', 'adresse', 'telephone_gsm',
               'telephone_adm', 'diplome', 'degre', 'plan_fonctionnel',
               'administration', 'ministere', 'email', 'banque', 'agence', 'num_compte')
# Champs propres à la دورة saisis dans cet écran. Le مقرّر n'en fait PAS
# partie : il est saisi une fois, à l'entrée du قسم (écran «المقرّر»), et
# cet écran ne peut ni l'écraser ni l'effacer.
CHAMPS_DORRA = ('numero_mudhakkira',
                'tarkhis_numero', 'tarkhis_date', 'type_takwin',
                'heures_programmees', 'heures_realisees', 'notes')


def register(app, ctx):
    login_required = ctx['login_required']
    admin_required = ctx['admin_required']
    BASE_DIR = ctx['BASE_DIR']

    # ─── المعالج ─────────────────────────────────────────────────────────────
    def _non_approuvee(formation_id):
        """وثائق الخلاص ne se produisent qu'après المصادقة على المستحقّات."""
        dorra = get_dorra_mustahaqqat(formation_id)
        if dorra and dorra.get('mu_etat') != 'acheve':
            flash('لا يمكن إعداد وثائق الخلاص قبل المصادقة على مستحقّات الدورة.', 'error')
            return redirect(url_for('mustahaqqat_manjaza'))
        return None

    @app.route('/mustahaqqat/dorra/<int:formation_id>/khalas')
    @login_required
    def khalas_assistant(formation_id):
        refus = _non_approuvee(formation_id)
        if refus:
            return refus
        data = _k.assembler(formation_id)
        if not data:
            flash('الدورة غير مسجَّلة نهائيًّا في المنظومة', 'error')
            return redirect(url_for('mustahaqqat_manjaza'))
        return render_template('mustahaqqat/khalas/assistant.html',
                               d=data,
                               manque=_k.champs_manquants(data),
                               docs=pdf_khalas.ORDRE,
                               titres=pdf_khalas.TITRES,
                               now_year=(data['date_iso'] or '')[:4])

    # ─── الحفظ ───────────────────────────────────────────────────────────────
    @app.route('/mustahaqqat/dorra/<int:formation_id>/khalas/save', methods=['POST'])
    @login_required
    def khalas_save(formation_id):
        dorra = get_dorra_mustahaqqat(formation_id)
        if not dorra:
            return jsonify({'erreur': 'الدورة غير موجودة'}), 404
        body = request.get_json(silent=True) or {}

        # 0) Contrôle strict avant toute écriture (v1.6) : cin = 8 chiffres,
        #    num_compte = 20 chiffres. Rien n'est enregistré si l'un est faux.
        perso = {c: body[c] for c in CHAMPS_MKOW if c in body}
        erreurs = verifier_identite(perso)
        if erreurs:
            return jsonify({'succes': False, 'erreur': ' ؛ '.join(erreurs)}), 400

        # 1) Champs propres à la دورة — le مقرّر déjà saisi est reporté tel quel.
        numero_m, date_m = get_muqarrar_dorra(formation_id)
        save_khalas_dorra(formation_id, {**{c: body.get(c, '') for c in CHAMPS_DORRA},
                                         'muqarrar_numero': numero_m,
                                         'muqarrar_date': date_m})

        # 2) Fiche du المكوّن — persistée pour être réutilisée ensuite
        cree = False
        if perso:
            trainer = trouver_mkow_par_nom(dorra.get('nom_formateur', ''),
                                           dorra.get('grade', ''))
            if trainer:
                update_mkow(trainer['id'], perso)
            elif len(candidats_mkow_par_nom(dorra.get('nom_formateur', ''))) > 1:
                # Homonymes non départagés : ne rien écrire dans la fiche d'autrui.
                journaliser(session.get('username'), 'حفظ وثائق الخلاص',
                            f'دورة #{formation_id}', 'تشابه أسماء: لم تُحيَّن بطاقة المكوّن')
                return jsonify({'succes': True, 'fiche_creee': False,
                                'avertissement': 'يوجد أكثر من مكوّن بنفس الاسم في قائمة الأسماء: '
                                                 'حُفظت معطيات الدورة فقط، حيّن بطاقة المكوّن يدويًّا.'})
            else:
                toks = (dorra.get('nom_formateur') or '').split()
                add_mkow({'grade': dorra.get('grade', ''),
                          'nom': toks[0] if toks else 'مكوّن',
                          'prenom': ' '.join(toks[1:]),
                          **perso})
                cree = True

        journaliser(session.get('username'), 'حفظ وثائق الخلاص',
                    f'دورة #{formation_id}', '')
        return jsonify({'succes': True, 'fiche_creee': cree})

    # ─── المعاينة / تحميل PDF ────────────────────────────────────────────────
    @app.route('/mustahaqqat/dorra/<int:formation_id>/khalas/pdf')
    @app.route('/mustahaqqat/dorra/<int:formation_id>/khalas/pdf/<doc>')
    @login_required
    def khalas_pdf(formation_id, doc=None):
        refus = _non_approuvee(formation_id)
        if refus:
            return refus
        data = _k.assembler(formation_id)
        if not data:
            flash('الدورة غير مسجَّلة نهائيًّا في المنظومة', 'error')
            return redirect(url_for('mustahaqqat_manjaza'))
        if doc and doc not in pdf_khalas.ORDRE and doc != 'all':
            return redirect(url_for('khalas_assistant', formation_id=formation_id))
        docs = pdf_khalas.ORDRE if (not doc or doc == 'all') else (doc,)
        chemin = pdf_khalas.generer(data, BASE_DIR, docs=docs)
        suffixe = 'complet' if len(docs) > 1 else doc
        # v1.7 : relu en mémoire puis supprimé — ces pièces portent CIN et RIB.
        from io import BytesIO
        from core import chemins
        return send_file(BytesIO(chemins.lire_et_supprimer(chemin)), mimetype='application/pdf',
                         as_attachment=bool(request.args.get('dl')),
                         download_name=f'وثائق_الخلاص_{formation_id}_{suffixe}.pdf')

    # ─── إعدادات وثائق الخلاص (المشرف العام) ─────────────────────────────────
    @app.route('/mustahaqqat/khalas/parametres', methods=['GET', 'POST'])
    @admin_required
    def khalas_parametres():
        if request.method == 'POST':
            # Le مقرّر est propre à chaque دورة ; نسبة الأداءات vit dans le
            # الجدول المالي. Ni l'un ni l'autre ne se règle ici.
            cles = ('ordre_tajir', 'ordre_1995', 'directeur_grade', 'directeur_nom',
                    'directeur_titre', 'ministere_ichraf')
            set_khalas_settings({c: request.form.get(c, '') for c in cles})
            journaliser(session.get('username'), 'تحيين إعدادات وثائق الخلاص', '', '')
            flash('تمّ حفظ إعدادات وثائق الخلاص', 'success')
            return redirect(url_for('khalas_parametres'))
        return render_template('mustahaqqat/khalas/parametres.html',
                               s=get_khalas_settings())
