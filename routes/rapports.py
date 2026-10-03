# -*- coding: utf-8 -*-
"""V3 — إعدادات التّقارير (paramètres du module التّقارير).

• النصّ القانوني et الفصل : repris dans la section 1 du تقرير.
• نصوص الأقسام 1.1 / 1.2 : automatiques ; une version modifiée n'est
  enregistrée que si elle diffère du texte automatique.
• جدول العديد : seule donnée demandée au premier lancement (bandeau
  d'accueil), modifiable ici à tout moment.
• عدد الدّورات المبرمجة par année : base de نسبة الإنجاز.

Rien ici ne touche au déroulement des برامج : ce sont de simples réglages."""

import json
from datetime import datetime

from flask import render_template, request, redirect, url_for, session, flash

from core import rapports_defauts as rd
from core.database import (get_config, update_config, journaliser,
                           get_parametres_annuels, set_parametre_annuel,
                           supprimer_parametre_annuel)


def register(app, ctx):
    admin_required = ctx['admin_required']

    @app.route('/parametres/rapports', methods=['GET', 'POST'])
    @admin_required
    def parametres_rapports():
        if request.method == 'POST':
            action = request.form.get('action', 'textes')
            if action == 'annee':
                ok = set_parametre_annuel(request.form.get('annee'), request.form.get('nb'))
                if ok:
                    journaliser(session.get('username'), 'تحيين عدد الدّورات المبرمجة',
                                'config', request.form.get('annee', ''))
                    flash('تمّ حفظ عدد الدّورات المبرمجة', 'success')
                else:
                    flash('قيم غير صالحة: السّنة بين 2000 و2100 والعدد بين 0 و9999', 'error')
                return redirect(url_for('parametres_rapports') + '#annees')
            if action == 'supprimer_annee':
                if supprimer_parametre_annuel(request.form.get('annee')):
                    journaliser(session.get('username'), 'حذف عدد الدّورات المبرمجة',
                                'config', request.form.get('annee', ''))
                    flash('تمّ الحذف', 'success')
                return redirect(url_for('parametres_rapports') + '#annees')

            # action « textes » : النصّ القانوني, الأقسام 1.1 / 1.2, جدول العديد
            if rd.CLE_TEXTE_LEGAL in request.form:
                v = request.form.get(rd.CLE_TEXTE_LEGAL, '').strip()
                update_config(rd.CLE_TEXTE_LEGAL, '' if v == rd.TEXTE_LEGAL_DEFAUT else v)
            if rd.CLE_FASL in request.form:
                v = request.form.get(rd.CLE_FASL, '').strip()
                update_config(rd.CLE_FASL, '' if v == rd.FASL_DEFAUT else v)
            # Les défauts se calculent APRÈS le نصّ القانوني ci-dessus.
            config = get_config()
            if rd.CLE_TACHES in request.form:
                update_config(rd.CLE_TACHES, rd.valeur_a_stocker(
                    request.form.get(rd.CLE_TACHES), rd.taches_defaut(config)))
            if rd.CLE_STRUCTURE in request.form:
                update_config(rd.CLE_STRUCTURE, rd.valeur_a_stocker(
                    request.form.get(rd.CLE_STRUCTURE), rd.structure_defaut(config)))
            if rd.CLE_RH in request.form:
                try:
                    lignes = json.loads(request.form.get(rd.CLE_RH) or '[]')
                except ValueError:
                    lignes = None
                if isinstance(lignes, list):
                    update_config(rd.CLE_RH, rd.serialiser_rh(lignes))
            if rd.CLE_RH_NOTE in request.form:
                update_config(rd.CLE_RH_NOTE, request.form.get(rd.CLE_RH_NOTE, '').strip())
            # V3.0.1 — 4. عدد الدّورات المبرمجة : enregistré avec le reste de la page
            # (auparavant un formulaire séparé : la valeur saisie puis « حفظ إعدادات
            # التّقارير » était perdue, et l'alerte « لم يُضبط… » restait affichée).
            invalides = []
            for cle in request.form:
                if cle.startswith('nb_annee_'):
                    if not set_parametre_annuel(cle[len('nb_annee_'):], request.form.get(cle)):
                        invalides.append(cle[len('nb_annee_'):])
            nb_nouveau = (request.form.get('nouveau_nb') or '').strip()
            if nb_nouveau:
                if set_parametre_annuel(request.form.get('nouvelle_annee'), nb_nouveau):
                    journaliser(session.get('username'), 'تحيين عدد الدّورات المبرمجة',
                                'config', request.form.get('nouvelle_annee', ''))
                else:
                    invalides.append(request.form.get('nouvelle_annee') or '؟')
            journaliser(session.get('username'), 'تعديل إعدادات التّقارير', 'config', '')
            if invalides:
                flash('تمّ حفظ الإعدادات ما عدا عدد الدّورات المبرمجة لـ: ' + '، '.join(invalides)
                      + ' (السّنة بين 2000 و2100 والعدد بين 0 و9999)', 'error')
            else:
                flash('تمّ حفظ إعدادات التّقارير', 'success')
            return redirect(url_for('parametres_rapports') + ('#annees' if nb_nouveau else ''))

        config = get_config()
        lignes = rd.lire_rh(config)
        return render_template(
            'parametres_rapports.html',
            texte_legal=rd.texte_legal(config), texte_legal_defaut=rd.TEXTE_LEGAL_DEFAUT,
            fasl=rd.fasl(config), fasl_defaut=rd.FASL_DEFAUT,
            taches=rd.taches(config), taches_defaut=rd.taches_defaut(config),
            structure=rd.structure(config), structure_defaut=rd.structure_defaut(config),
            intro=rd.intro_section1(config),
            taches_modifie=bool(str(config.get(rd.CLE_TACHES) or '').strip()),
            structure_modifie=bool(str(config.get(rd.CLE_STRUCTURE) or '').strip()),
            rh_lignes=lignes, rh_total=rd.total_rh(lignes),
            rh_note=str(config.get(rd.CLE_RH_NOTE) or ''),
            rh_colonnes=rd.RH_COLONNES, rh_groupes=rd.RH_GROUPES, rh_hayaa=rd.RH_HAYAA,
            niveaux_rh=rd.NIVEAUX_RH, rh_max=rd.RH_MAX_LIGNES,
            annees=get_parametres_annuels(),
            now_year=datetime.now().year)

    @app.route('/parametres/rapports/rh-plus-tard', methods=['POST'])
    @admin_required
    def rapport_rh_plus_tard():
        """« لاحقا » : le bandeau d'accueil ne propose plus le جدول العديد
        (il reste accessible dans إعدادات التّقارير)."""
        update_config(rd.CLE_RH_IGNORE, '1')
        return redirect(url_for('accueil'))

    # ═════════════════════════════════════════════════════════════════════
    #  V3 — Phase 4 : التّقرير الكتابي (édition, PDF, Word)
    # ═════════════════════════════════════════════════════════════════════
    login_required = ctx['login_required']
    BASE_DIR = ctx['BASE_DIR']

    def _periode_demandee(source):
        """La période lue dans la requête ; par défaut, le dernier سداسي échu."""
        from core import rapports_moteur as rm
        aujourd_hui = datetime.now()
        t = source.get('type') or 'semestre'
        annee = source.get('annee') or (aujourd_hui.year if aujourd_hui.month > 6
                                        else aujourd_hui.year - 1)
        n = source.get('n') or (1 if aujourd_hui.month > 6 or 'annee' in source else 2)
        try:
            return rm.bornes_periode(annee, t, n, source.get('debut'), source.get('fin')), None
        except (ValueError, TypeError) as e:
            return rm.bornes_periode(aujourd_hui.year, 'annee'), str(e) or 'فترة غير صالحة'

    def _params(p):
        if p['type'] == 'plage':
            return {'type': 'plage', 'debut': p['debut'], 'fin': p['fin']}
        d = {'type': p['type'], 'annee': p['annee']}
        if p['n']:
            d['n'] = p['n']
        return d

    @app.route('/rapports/ecrit', methods=['GET'])
    @login_required
    def rapport_ecrit():
        from core import rapport_ecrit as rec
        p, erreur = _periode_demandee(request.args)
        if erreur:
            flash(erreur, 'error')
        c = rec.contenu(p, get_config())
        return render_template('rapport_ecrit.html', c=c, p=p, libelles={k: lib for k, lib, _ in rec.CHAMPS},
                               params=_params(p), annee_courante=datetime.now().year)

    @app.route('/rapports/ecrit/brouillon', methods=['POST'])
    @login_required
    def rapport_ecrit_brouillon():
        """Enregistre (ou efface, action=reinitialiser) les corrections de
        l'utilisateur pour la période ; répond en JSON aux appels fetch."""
        from core import rapport_ecrit as rec
        p, erreur = _periode_demandee(request.form)
        if erreur:
            return {'ok': False, 'message': erreur}, 400
        config = get_config()
        cle = rec.cle_brouillon(p)
        if request.form.get('action') == 'reinitialiser':
            update_config(cle, '')
            journaliser(session.get('username'), 'استرجاع النّصوص الآليّة للتّقرير', 'config', cle)
            message = 'تمّ استرجاع النّصوص الآليّة'
        else:
            auto = rec.contenu(p, config, brouillon={})['auto']
            d = rec.brouillon_depuis_formulaire(request.form, auto)
            update_config(cle, json.dumps(d, ensure_ascii=False) if d else '')
            journaliser(session.get('username'), 'حفظ مسودّة التّقرير الكتابي', 'config', cle)
            message = 'تمّ حفظ المسودّة'
        if request.headers.get('X-Requested-With') == 'fetch':
            return {'ok': True, 'message': message}
        flash(message, 'success')
        return redirect(url_for('rapport_ecrit', **_params(p)))

    def _nom_fichier(p, ext):
        base = {'trimestre': f"تقرير_ثلاثي_{p['n']}_{p['annee']}",
                'semestre': f"تقرير_نصف_سنوي_{p['n']}_{p['annee']}",
                'annee': f"تقرير_سنوي_{p['annee']}"}.get(p['type'])
        return f"{base or 'تقرير_' + p['debut'] + '_' + p['fin']}.{ext}"

    @app.route('/rapports/ecrit/pdf')
    @login_required
    def rapport_ecrit_pdf():
        from io import BytesIO
        from flask import send_file
        from core import chemins, rapport_ecrit as rec
        p, _ = _periode_demandee(request.args)
        c = rec.contenu(p, get_config())
        chemin = chemins.chemin_pdf_transitoire('rapport_ecrit')
        rec.pdf_rapport(c, chemin, BASE_DIR)
        return send_file(BytesIO(chemins.lire_et_supprimer(chemin)), mimetype='application/pdf',
                         as_attachment=bool(request.args.get('dl')),
                         download_name=_nom_fichier(p, 'pdf'))

    @app.route('/rapports/ecrit/word')
    @login_required
    def rapport_ecrit_word():
        from io import BytesIO
        from flask import send_file
        from core import rapport_ecrit as rec
        p, _ = _periode_demandee(request.args)
        c = rec.contenu(p, get_config())
        return send_file(BytesIO(rec.docx_rapport(c)), as_attachment=True,
                         mimetype='application/vnd.openxmlformats-officedocument.'
                                  'wordprocessingml.document',
                         download_name=_nom_fichier(p, 'docx'))

    # ═════════════════════════════════════════════════════════════════════
    #  V3 — Phase 5 : التّقرير البياني والتّحليلي (page, PDF, HTML interactif)
    # ═════════════════════════════════════════════════════════════════════

    def _options_graphique(source):
        try:
            annees = int(source.get('annees') or 2)
        except (TypeError, ValueError):
            annees = 2
        annees = max(2, min(5, annees))
        critere = 'toutes' if source.get('toutes') else 'finalisees'
        return annees - 1, critere

    def _params_graphique(p, n_annees, critere):
        d = _params(p)
        d['annees'] = n_annees + 1
        if critere == 'toutes':
            d['toutes'] = 1
        return d

    @app.route('/rapports')
    @login_required
    def rapports():
        from core import rapports_graphiques as rg
        p, erreur = _periode_demandee(request.args)
        if erreur:
            flash(erreur, 'error')
        n_annees, critere = _options_graphique(request.args)
        d = rg.donnees(p, n_annees, critere)
        return render_template('rapports.html', d=d, p=p, params_ecrit=_params(p),
                               params=_params_graphique(p, n_annees, critere))

    @app.route('/rapports/pdf')
    @login_required
    def rapports_pdf():
        from io import BytesIO
        from flask import send_file
        from core import chemins, rapports_graphiques as rg
        p, _ = _periode_demandee(request.args)
        n_annees, critere = _options_graphique(request.args)
        chemin = chemins.chemin_pdf_transitoire('rapport_graphique')
        rg.pdf_graphique(rg.donnees(p, n_annees, critere), chemin, BASE_DIR, get_config())
        return send_file(BytesIO(chemins.lire_et_supprimer(chemin)), mimetype='application/pdf',
                         as_attachment=bool(request.args.get('dl')),
                         download_name=_nom_fichier(p, 'pdf').replace('تقرير', 'تقرير_بياني', 1))

    # V3.0.1 — l'export « نسخة HTML تفاعليّة » a été retiré (demande du centre).

    # ═════════════════════════════════════════════════════════════════════
    #  V3 — Phase 6a : البطاقة التّقييميّة للمشارك
    # ═════════════════════════════════════════════════════════════════════

    def _annee_fiche(source):
        a = str(source.get('annee') or '').strip()
        return int(a) if a.isdigit() and 2000 <= int(a) <= 2100 else None

    @app.route('/rapports/participant')
    @login_required
    def rapport_participant():
        from core import fiche_participant as fp
        q = (request.args.get('q') or '').strip()[:80]
        cle = (request.args.get('p') or '').strip()[:200]
        annee = _annee_fiche(request.args)
        resultats = fp.rechercher(q) if q and not cle else []
        f = fp.fiche(cle, annee) if cle else None
        if cle and f is None:
            flash('لم يُعثر على هذا المشارك', 'error')
        graphes = None
        if f:
            graphes = {'sections': [{'graphes': [
                {'id': 'fp_annees', 'titre': 'الدّورات حسب السّنوات', 'forme': 'barres_v',
                 'unite': '', 'libelles': [str(x['valeur']) for x in f['par_annee']],
                 'valeurs': [x['dorrat'] for x in f['par_annee']], 'max': None,
                 'couleurs': None, 'accent': None},
                {'id': 'fp_niveau', 'titre': 'الدّورات حسب المستوى', 'forme': 'barres_h',
                 'unite': '', 'libelles': [x['valeur'] for x in f['par_niveau']],
                 'valeurs': [x['dorrat'] for x in f['par_niveau']], 'max': None,
                 'couleurs': None, 'accent': None},
                {'id': 'fp_categorie', 'titre': 'الدّورات حسب التّصنيف', 'forme': 'barres_h',
                 'unite': '', 'libelles': [x['valeur'] for x in f['par_categorie']],
                 'valeurs': [x['dorrat'] for x in f['par_categorie']], 'max': None,
                 'couleurs': None, 'accent': None},
            ]}]}
        return render_template('rapport_participant.html', q=q, resultats=resultats, f=f,
                               cle=cle, annee=annee, graphes=graphes)

    @app.route('/rapports/participant/recherche')
    @login_required
    def rapport_participant_recherche():
        """Suggestions (JSON) pendant la saisie."""
        from core import fiche_participant as fp
        q = (request.args.get('q') or '').strip()[:80]
        return {'resultats': fp.rechercher(q, 10) if len(q) >= 2 else []}

    @app.route('/rapports/participant/pdf')
    @login_required
    def rapport_participant_pdf():
        from io import BytesIO
        from flask import send_file, abort
        from core import chemins, fiche_participant as fp
        f = fp.fiche((request.args.get('p') or '').strip()[:200], _annee_fiche(request.args))
        if f is None:
            abort(404)
        chemin = chemins.chemin_pdf_transitoire('fiche_participant')
        fp.pdf_fiche(f, chemin, BASE_DIR, get_config())
        nom = '_'.join(f['identite']['nom'].split())
        return send_file(BytesIO(chemins.lire_et_supprimer(chemin)), mimetype='application/pdf',
                         as_attachment=bool(request.args.get('dl')),
                         download_name=f'بطاقة_تقييمية_{nom}.pdf')

    # ═════════════════════════════════════════════════════════════════════
    #  V3 — Phase 6b : التّقارير التّفصيليّة + Excel
    # ═════════════════════════════════════════════════════════════════════

    @app.route('/rapports/details')
    @login_required
    def rapports_details():
        from core import rapports_details as rdet
        p, erreur = _periode_demandee(request.args)
        if erreur:
            flash(erreur, 'error')
        critere = 'toutes' if request.args.get('toutes') else 'finalisees'
        d = rdet.tableaux(p, critere)
        params = _params(p)
        if critere == 'toutes':
            params['toutes'] = 1
        onglet = request.args.get('onglet') or 'resume'
        return render_template('rapports_details.html', d=d, p=p, params=params,
                               onglet=onglet if any(t['id'] == onglet for t in d['tableaux'])
                               else 'resume')

    @app.route('/rapports/details/excel')
    @login_required
    def rapports_details_excel():
        from flask import send_file
        from core import exports, identite as idt, rapports_details as rdet
        p, _ = _periode_demandee(request.args)
        critere = 'toutes' if request.args.get('toutes') else 'finalisees'
        flux = rdet.classeur(rdet.tableaux(p, critere), idt.nom_centre(get_config()))
        return send_file(flux, mimetype=exports.MIME_XLSX, as_attachment=True,
                         download_name=_nom_fichier(p, 'xlsx').replace('تقرير', 'تقارير_تفصيلية', 1))
