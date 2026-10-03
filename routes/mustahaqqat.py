"""المستحقّات المالية — التأشير على الحضور، تحديد صنف الدورة (v1.0).

Le parcours, écran par écran :

  1. « برامج تكوين غير منجزة » — la liste des دورات enregistrées définitivement
     dont les مستحقّات restent à faire ; l'agent en choisit UNE.
  2. ورقة الحضور — chaque مشارك est pointé حاضر ou غائب ; rien de partiel
     n'est accepté.
  3. شاشة التأكيد — la منظومة annonce le صنف qu'elle a déduit des présents.
     موافقة → l'écran suivant ; رفض → retour au pointage.
  4. القيمة المالية والوثائق — à venir : c'est là que le barème s'applique.

Le صنف ne se saisit pas : il se déduit. C'est toute la raison d'être du
pointage — et la raison pour laquelle un refus ramène au pointage plutôt
qu'à un champ libre.
"""

import logging as _logging
_log = _logging.getLogger('formation.' + __name__)

from datetime import datetime, timedelta

from flask import render_template, request, jsonify, redirect, url_for, session, flash

from core import mustahaqqat as _m
from core import bareme_mali as _bm
from core import arabe as _arabe   # v1.7.1 : ordre des رتب à l'affichage
from core.database import (
    get_bareme_grades_detail, set_classe_grade, reinitialiser_bareme,
    dorrat_mustahaqqat_ghayr_manjaza, dorrat_mustahaqqat_manjaza,
    get_dorra_mustahaqqat, get_hodour, save_hodour, confirmer_classe, get_jours_dorra,
    reprendre_hodour, calculer_classe,
    get_stats_mustahaqqat, get_formateurs_mustahaqqat, get_stats_avancees,
    journaliser,
    calculer_mustahaqqat, confirmer_mustahaqqat, rouvrir_mustahaqqat,
    marquer_pret_validation,
    get_bareme_mali_grille, set_taux_bareme_mali, reinitialiser_bareme_mali,
    get_groupes_grades_detail, set_groupe_grade,
    get_muqarrar_dorra, muqarrar_manquant, save_muqarrar_dorra,
    get_khalas_settings, set_khalas_settings,
)


def register(app, ctx):
    login_required = ctx['login_required']
    admin_required = ctx['admin_required']

    def _annee():
        return datetime.now().year

    # ─── الشاشة الرئيسية ─────────────────────────────────────────────────────

    @app.route('/accueil')
    @login_required
    def accueil():
        """Les trois portes de la منظومة. C'est désormais la page d'entrée.

        On y joint le nombre de دورات dont les مستحقّات restent à faire — une
        lecture seule, pour le mot de bienvenue. Aucun calcul métier nouveau."""
        try:
            nb_en_cours = len(dorrat_mustahaqqat_ghayr_manjaza())
        except Exception:
            _log.warning('accueil : exception ignorée', exc_info=True)
            nb_en_cours = 0
        # v1.7 : deux compteurs distincts — l'ancienne pastille annonçait
        # « كل البرامج منجزة » alors que des برامج étaient en retard.
        try:
            from core.database import donnees_tableau_de_bord
            nb_retard = len(donnees_tableau_de_bord().get('en_retard') or [])
        except Exception:
            _log.warning('accueil (retard) : exception ignorée', exc_info=True)
            nb_retard = 0
        # V3 : bandeau « جدول العديد » (tant qu'il n'est ni rempli ni reporté).
        try:
            from core import rapports_defauts
            from core.database import get_config
            rh_a_demander = rapports_defauts.rh_a_demander(get_config())
        except Exception:
            _log.warning('accueil (rh) : exception ignorée', exc_info=True)
            rh_a_demander = False
        # V3 : مؤشّرات السّنة (lecture seule ; jamais bloquant pour l'accueil).
        try:
            from core import rapports_graphiques
            kpis = rapports_graphiques.kpis_accueil()
        except Exception:
            _log.warning('accueil (kpis) : exception ignorée', exc_info=True)
            kpis = None
        return render_template('accueil.html', now_year=_annee(),
                               nb_en_cours=nb_en_cours, nb_retard=nb_retard,
                               rh_a_demander=rh_a_demander, kpis=kpis)

    # ─── لوحة القيادة — المستحقّات ───────────────────────────────────────────

    @app.route('/mustahaqqat')
    @login_required
    def mustahaqqat_dashboard():
        return render_template('mustahaqqat/dashboard.html',
                               stats=get_stats_mustahaqqat(),
                               classes=_m.CLASSES,
                               recentes=dorrat_mustahaqqat_ghayr_manjaza()[:5],
                               now_year=_annee())

    # ─── قائمة الأسماء — المكوّنون ───────────────────────────────────────────

    @app.route('/mustahaqqat/mkowin')
    @login_required
    def mustahaqqat_mkowin():
        return render_template('mustahaqqat/mkowin.html',
                               formateurs=get_formateurs_mustahaqqat(),
                               now_year=_annee())

    # ─── برامج تكوين غير منجزة  (الشاشة 1) ───────────────────────────────────

    @app.route('/mustahaqqat/dorrat/ghayr-manjaza')
    @login_required
    def mustahaqqat_ghayr_manjaza():
        return render_template('mustahaqqat/dorrat_ghayr_manjaza.html',
                               dorrat=dorrat_mustahaqqat_ghayr_manjaza(),
                               now_year=_annee())

    @app.route('/mustahaqqat/dorrat/manjaza')
    @login_required
    def mustahaqqat_manjaza():
        return render_template('mustahaqqat/dorrat_manjaza.html',
                               dorrat=dorrat_mustahaqqat_manjaza(),
                               now_year=_annee())

    # ─── المقرّر  (الشاشة 1 مكرّر) ───────────────────────────────────────────
    #
    # « لا يمكن إسناد مستحقّات مالية بدون وجود مقرّر » : chaque دورة a SON
    # مقرّر (عدد + تاريخ). Il est demandé dès que la دورة est choisie, et tant
    # qu'il manque, ni pointage, ni صنف, ni montant ne sont acceptés.

    _REFUS_MUQARRAR = 'لا يمكن إسناد مستحقّات مالية دون مقرّر: أدخل عدد المقرّر وتاريخه أوّلا.'

    def _suite_sure(cible, formation_id):
        # Retour autorisé vers un écran INTERNE seulement.
        if cible and cible.startswith('/mustahaqqat/') and '//' not in cible:
            return cible
        return url_for('mustahaqqat_hodour', formation_id=formation_id)

    def _date_iso(v):
        try:
            return datetime.strptime(v[:10], '%Y-%m-%d').date()
        except (ValueError, TypeError):
            return None

    def _lendemain(v):
        d = _date_iso(v or '')
        return (d + timedelta(days=1)).strftime('%Y-%m-%d') if d else ''

    @app.route('/mustahaqqat/dorra/<int:formation_id>/muqarrar', methods=['GET', 'POST'])
    @login_required
    def mustahaqqat_muqarrar(formation_id):
        dorra = get_dorra_mustahaqqat(formation_id)
        if not dorra:
            flash('الدورة غير مسجَّلة نهائيًّا في المنظومة', 'error')
            return redirect(url_for('mustahaqqat_ghayr_manjaza'))
        suite = _suite_sure(request.values.get('suite', ''), formation_id)
        numero, date_m = get_muqarrar_dorra(formation_id)
        erreurs = []
        if request.method == 'POST':
            numero = (request.form.get('muqarrar_numero') or '').strip()
            date_m = (request.form.get('muqarrar_date') or '').strip()
            if not numero:
                erreurs.append('عدد المقرّر وجوبيّ.')
            try:
                d_muq = datetime.strptime(date_m, '%Y-%m-%d').date()
            except ValueError:
                d_muq = None
                erreurs.append('تاريخ المقرّر وجوبيّ.')
            # v1.6.1 : le مقرّر est pris APRÈS la دورة — jamais le jour même,
            # jamais avant.
            # V2 : après le DERNIER jour d'une دورة متعدّدة الأيّام
            d_form = _date_iso((dorra.get('derniere_date') or dorra.get('date_formation') or '').strip())
            if d_muq and d_form and d_muq <= d_form:
                # \u2066…\u2069 : la date ISO reste lisible dans la phrase arabe.
                erreurs.append(f'تاريخ المقرّر يجب أن يكون بعد تاريخ الدورة '
                               f'(\u2066{d_form.strftime("%Y-%m-%d")}\u2069)، لا في نفس اليوم ولا قبله.')
            if not erreurs:
                save_muqarrar_dorra(formation_id, numero, date_m)
                journaliser(session.get('username'), 'إدخال مقرّر الدورة',
                            f'دورة #{formation_id}', f'عدد {numero} بتاريخ {date_m}')
                return redirect(suite)
        return render_template('mustahaqqat/muqarrar.html', dorra=dorra,
                               numero=numero, date_m=date_m, erreurs=erreurs,
                               date_min=_lendemain(dorra.get('derniere_date') or dorra.get('date_formation')),
                               suite=suite, now_year=_annee())

    # ─── ورقة الحضور  (الشاشة 2) ─────────────────────────────────────────────

    @app.route('/mustahaqqat/dorra/<int:formation_id>/hodour')
    @login_required
    def mustahaqqat_hodour(formation_id):
        dorra = get_dorra_mustahaqqat(formation_id)
        if not dorra:
            flash('الدورة غير مسجَّلة نهائيًّا في المنظومة', 'error')
            return redirect(url_for('mustahaqqat_ghayr_manjaza'))
        if dorra['etat'] == 'acheve':
            flash('مستحقّات هذه الدورة منجزة', 'error')
            return redirect(url_for('mustahaqqat_manjaza'))
        if muqarrar_manquant(formation_id):
            return redirect(url_for('mustahaqqat_muqarrar', formation_id=formation_id))
        return render_template('mustahaqqat/hodour.html',
                               dorra=dorra,
                               jours=get_jours_dorra(formation_id),     # V2
                               participants=_arabe.trier_par_grade(get_hodour(formation_id)),
                               classes=_m.CLASSES,
                               libelles=_m.LIBELLES_CLASSES,
                               now_year=_annee())

    @app.route('/mustahaqqat/dorra/<int:formation_id>/hodour', methods=['POST'])
    @login_required
    def api_save_hodour(formation_id):
        """Enregistre le pointage et RENVOIE le صنف déduit — sans l'appliquer.
        L'écran de confirmation s'appuie sur cette réponse ; c'est l'agent qui
        tranche à l'étape suivante."""
        if muqarrar_manquant(formation_id):
            return jsonify({'erreur': _REFUS_MUQARRAR,
                            'muqarrar': url_for('mustahaqqat_muqarrar',
                                                formation_id=formation_id)}), 400

        body = request.get_json(silent=True) or {}
        brut = body.get('presences') or {}
        if not isinstance(brut, dict):
            return jsonify({'erreur': 'قائمة الحضور غير صحيحة'}), 400
        presences = {}
        for cle, valeur in brut.items():
            try:
                # V2 : {jour : حاضر} par مشارك pour une دورة متعدّدة الأيّام
                presences[int(cle)] = ({str(k): bool(v) for k, v in valeur.items()}
                                       if isinstance(valeur, dict) else bool(valeur))
            except (TypeError, ValueError, AttributeError):
                return jsonify({'erreur': 'قائمة الحضور غير صحيحة'}), 400

        ok, resultat = save_hodour(formation_id, presences)
        if not ok:
            return jsonify({'erreur': resultat}), 400
        journaliser(session.get('username'), 'التأشير على ورقة الحضور',
                    f'دورة #{formation_id}',
                    f"حاضرون: {resultat['nb_presents']} — غائبون: {resultat['nb_absents']}")
        return jsonify({'succes': True, **resultat})

    # ─── تأكيد الصنف ─────────────────────────────────────────────────────────

    @app.route('/mustahaqqat/dorra/<int:formation_id>/classe', methods=['POST'])
    @login_required
    def api_confirmer_classe(formation_id):
        if muqarrar_manquant(formation_id):
            return jsonify({'erreur': _REFUS_MUQARRAR,
                            'muqarrar': url_for('mustahaqqat_muqarrar',
                                                formation_id=formation_id)}), 400
        body = request.get_json(silent=True) or {}
        classe = (body.get('classe') or '').strip()
        ok, info = confirmer_classe(formation_id, classe)
        if not ok:
            return jsonify({'erreur': info}), 400
        journaliser(session.get('username'), 'تصنيف دورة تكوينية',
                    f'دورة #{formation_id}', f'الصنف {classe}')
        app.logger.info('Dorra %s classée %s par %s', formation_id, classe,
                        session.get('username'))
        return jsonify({'succes': True, 'classe': classe, 'classe_at': info,
                        'suite': url_for('mustahaqqat_qima',
                                         formation_id=formation_id)})

    @app.route('/mustahaqqat/dorra/<int:formation_id>/reprendre', methods=['POST'])
    @login_required
    def api_reprendre_hodour(formation_id):
        """« رفض » : le صنف proposé est écarté et l'agent revient au pointage."""
        reprendre_hodour(formation_id)
        return jsonify({'succes': True,
                        'hodour': url_for('mustahaqqat_hodour',
                                          formation_id=formation_id)})

    # ─── القيمة المالية — الشاشة التلخيصية  (الشاشة 3) ───────────────────────

    @app.route('/mustahaqqat/dorra/<int:formation_id>/qima')
    @login_required
    def mustahaqqat_qima(formation_id):
        """La شاشة تلخيصية : tout ce qui fonde le montant, avant de l'arrêter.

        Rien n'y est saisi. Les ساعات viennent du برنامج, le صنف du pointage,
        le سعر du جدول المالي — l'agent ne fait que voir et approuver. C'est
        pourquoi l'écran montre AUSSI la durée réelle à côté de la durée
        payée : approuver sans voir d'où vient le chiffre n'est pas approuver.
        """
        dorra = get_dorra_mustahaqqat(formation_id)
        if not dorra:
            flash('الدورة غير مسجَّلة نهائيًّا في المنظومة', 'error')
            return redirect(url_for('mustahaqqat_ghayr_manjaza'))
        if muqarrar_manquant(formation_id):
            return redirect(url_for('mustahaqqat_muqarrar', formation_id=formation_id))
        if not dorra.get('mu_classe'):
            flash('يجب تحديد صنف الدورة أوّلا', 'error')
            return redirect(url_for('mustahaqqat_hodour', formation_id=formation_id))
        classe, repart, ex_aequo, nb_p, nb_a = calculer_classe(formation_id)
        return render_template('mustahaqqat/qima.html',
                               dorra=dorra,
                               jours=get_jours_dorra(formation_id),     # V2
                               participants=_arabe.trier_par_grade(get_hodour(formation_id)),
                               repartition=repart,
                               classes=_m.CLASSES,
                               libelles=_m.LIBELLES_CLASSES,
                               nb_presents=nb_p, nb_absents=nb_a,
                               chiffrage=calculer_mustahaqqat(formation_id),
                               now_year=_annee())

    @app.route('/mustahaqqat/dorra/<int:formation_id>/pret', methods=['POST'])
    @login_required
    def api_pret_validation(formation_id):
        """v1.6 — « جاهز للمصادقة » : l'agent signale au مشرف عام que la دورة
        est prête ; seul ce dernier arrête les مستحقّات (التأكيد النهائي)."""
        if muqarrar_manquant(formation_id):
            return jsonify({'erreur': _REFUS_MUQARRAR,
                            'muqarrar': url_for('mustahaqqat_muqarrar',
                                                formation_id=formation_id)}), 400
        ok, info = marquer_pret_validation(formation_id, session.get('username') or '')
        if not ok:
            return jsonify({'erreur': info}), 400
        journaliser(session.get('username'), 'دورة جاهزة للمصادقة',
                    f'دورة #{formation_id}', '')
        return jsonify({'succes': True, 'pret_at': info})

    @app.route('/mustahaqqat/dorra/<int:formation_id>/qima', methods=['POST'])
    @admin_required
    def api_confirmer_qima(formation_id):
        """« التأكيد النهائي » sur la شاشة التلخيصية : les مستحقّات sont
        arrêtées. Réservé au مشرف عام depuis la v1.6."""
        if muqarrar_manquant(formation_id):
            return jsonify({'erreur': _REFUS_MUQARRAR,
                            'muqarrar': url_for('mustahaqqat_muqarrar',
                                                formation_id=formation_id)}), 400

        ok, info = confirmer_mustahaqqat(formation_id)
        if not ok:
            return jsonify({'erreur': info}), 400
        journaliser(session.get('username'), 'إنجاز المستحقّات المالية',
                    f'دورة #{formation_id}',
                    f"{info['heures']} ساعة — {info['montant_texte']} د")
        app.logger.info('Mustahaqqat dorra %s arrêtées à %s par %s',
                        formation_id, info['montant_texte'],
                        session.get('username'))
        return jsonify({'succes': True, **info,
                        'suite': url_for('mustahaqqat_manjaza')})

    @app.route('/mustahaqqat/dorra/<int:formation_id>/rouvrir', methods=['POST'])
    @login_required
    def api_rouvrir_mustahaqqat(formation_id):
        """Rouvrir une dorra achevée reste du ressort du مشرف عام : c'est
        défaire un montant approuvé."""
        if session.get('role') != 'admin':
            return jsonify({'erreur': 'إعادة فتح المستحقّات من مشمولات المشرف العام'}), 403
        rouvrir_mustahaqqat(formation_id)
        journaliser(session.get('username'), 'إعادة فتح المستحقّات المالية',
                    f'دورة #{formation_id}', '')
        return jsonify({'succes': True,
                        'suite': url_for('mustahaqqat_qima',
                                         formation_id=formation_id)})

    # ─── جدول الأصناف (رتبة → صنف) ───────────────────────────────────────────

    @app.route('/mustahaqqat/bareme', methods=['GET', 'POST'])
    @login_required
    def mustahaqqat_bareme():
        """Le barème officiel est semé au premier démarrage ; cette page le
        rend corrigible — une رتبة ajoutée par le centre doit pouvoir recevoir
        son صنف sans toucher au code."""
        if request.method == 'POST':
            if not session.get('role') == 'admin':
                flash('تعديل جدول الأصناف من مشمولات المشرف العام', 'error')
                return redirect(url_for('mustahaqqat_bareme'))
            if request.form.get('action') == 'reinitialiser':
                reinitialiser_bareme()
                journaliser(session.get('username'), 'إرجاع جدول الأصناف الرسمي',
                            'mustahaqqat_grades', '')
                flash('تمّ إرجاع الجدول الرسمي', 'success')
                return redirect(url_for('mustahaqqat_bareme'))
            modifiees = 0
            for cle, valeur in request.form.items():
                if not cle.startswith('classe__'):
                    continue
                grade = cle[len('classe__'):]
                if set_classe_grade(grade, (valeur or '').strip()):
                    modifiees += 1
            journaliser(session.get('username'), 'تعديل جدول الأصناف',
                        'mustahaqqat_grades', f'{modifiees} رتبة')
            flash('تمّ حفظ جدول الأصناف', 'success')
            return redirect(url_for('mustahaqqat_bareme'))
        return render_template('mustahaqqat/bareme.html',
                               bareme=get_bareme_grades_detail(),
                               classes=_m.CLASSES,
                               libelles=_m.LIBELLES_CLASSES,
                               now_year=_annee())

    # ─── الجدول المالي (الأسعار والمجموعات) ──────────────────────────────────

    @app.route('/mustahaqqat/bareme-mali', methods=['GET', 'POST'])
    @login_required
    def mustahaqqat_bareme_mali():
        """Le جدول المالي, modifiable : « ثم تقوم باضافتها للإعدادات حيث يمكن
        تحيينها ». Un texte réglementaire révisé se répercute ici, sans
        toucher au code — et sans réécrire les dorrat déjà arrêtées, dont le
        chiffrage est figé en base."""
        if request.method == 'POST':
            if session.get('role') != 'admin':
                flash('تعديل الجدول المالي من مشمولات المشرف العام', 'error')
                return redirect(url_for('mustahaqqat_bareme_mali'))

            if request.form.get('action') == 'reinitialiser':
                reinitialiser_bareme_mali()
                journaliser(session.get('username'), 'إرجاع الجدول المالي الرسمي',
                            'mustahaqqat_bareme_mali', '')
                flash('تمّ إرجاع الجدول المالي الرسمي', 'success')
                return redirect(url_for('mustahaqqat_bareme_mali'))

            # نسبة الأداءات : un pourcentage entre 0 et 100, rien d'autre.
            brut_taux = (request.form.get('taux_adaat') or '').strip().replace(',', '.')
            if brut_taux:
                try:
                    v = float(brut_taux)
                    if not 0 <= v <= 100:
                        raise ValueError
                except ValueError:
                    flash('نسبة الأداءات يجب أن تكون عددًا بين 0 و100', 'error')
                    return redirect(url_for('mustahaqqat_bareme_mali'))
                set_khalas_settings({'taux_adaat': f'{v:g}'})

            taux_modifies = groupes_modifies = 0
            for cle, valeur in request.form.items():
                if cle.startswith('taux__'):
                    # taux__<groupe>__<colonne>
                    parties = cle[len('taux__'):].split('__', 1)
                    if len(parties) == 2 and set_taux_bareme_mali(
                            parties[0], parties[1], valeur):
                        taux_modifies += 1
                elif cle.startswith('groupe__'):
                    grade = cle[len('groupe__'):]
                    if set_groupe_grade(grade, (valeur or '').strip()):
                        groupes_modifies += 1

            journaliser(session.get('username'), 'تعديل الجدول المالي',
                        'mustahaqqat_bareme_mali',
                        f'{taux_modifies} سعرًا — {groupes_modifies} رتبة')
            flash('تمّ حفظ الجدول المالي', 'success')
            return redirect(url_for('mustahaqqat_bareme_mali'))

        return render_template('mustahaqqat/bareme_mali.html',
                               taux_adaat=get_khalas_settings().get('taux_adaat', '15'),
                               grille=get_bareme_mali_grille(),
                               rattachements=get_groupes_grades_detail(),
                               groupes=_bm.GROUPES,
                               colonnes=_bm.COLONNES,
                               libelles_colonnes=_bm.LIBELLES_COLONNES,
                               libelles_groupes=_bm.LIBELLES_GROUPES,
                               libelles_groupes_courts=_bm.LIBELLES_GROUPES_COURTS,
                               now_year=_annee())

    # ─── إحصائيات ────────────────────────────────────────────────────────────

    @app.route('/statistiques')
    @login_required
    def statistiques():
        return render_template('statistiques.html',
                               s=get_stats_avancees(),
                               classes=_m.CLASSES,
                               libelles=_m.LIBELLES_CLASSES,
                               now_year=_annee())

