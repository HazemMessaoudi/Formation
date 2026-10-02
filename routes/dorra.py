"""Routes par dorra : participants, بطاقة بيداغوجية, برنامج, مذكرة, étapes."""

import re
from flask import request, jsonify, session

from core.database import (
    get_lettre_detail, get_connection, get_config,
    get_participants, save_participants, formation_est_finalisee,
    get_bataqa_data, save_bataqa_data,
    get_programme_data, save_programme_data,
    get_memo_data, save_memo_data, finaliser_formation, deverrouiller_formation,
    valider_etape, journaliser,
    etats_dorrat, etape_autorisee, annuler_dorra,
    dorrat_simultanees, completer_fiches_depuis_participants,
    bataqa_derives, actualiser_bataqa_apres_participants,
    get_programme_jours, save_programme_jour, formation_est_multi_jours,
)
from core import conflits
from core.validation import verifier_choix


def register(app, ctx):
    login_required = ctx['login_required']
    admin_required = ctx['admin_required']

    # ─── API : formations list for a letter ──────────────────────────────────

    @app.route('/lettre/<int:lettre_id>/formations', methods=['GET'])
    @login_required
    def api_get_formations(lettre_id):
        detail = get_lettre_detail(lettre_id)
        if not detail:
            return jsonify({'erreur': 'غير موجود'}), 404
        return jsonify({'formations': detail['formations']})

    @app.route('/lettre/<int:lettre_id>/formations/etats', methods=['GET'])
    @login_required
    def api_etats_dorrat(lettre_id):
        """Avancement de chaque dorra : quelles étapes sont achevées et
        lesquelles l'agent a le droit d'ouvrir. C'est le serveur qui décide ;
        l'interface ne fait que refléter cette réponse."""
        return jsonify({'etats': {str(k): v for k, v in etats_dorrat(lettre_id).items()}})

    @app.route('/lettre/<int:lettre_id>/formations/<int:formation_id>/annuler',
               methods=['POST'])
    @login_required
    def api_annuler_dorra(lettre_id, formation_id):
        """فسخ دورة واحدة, sans toucher aux autres dorrat du même programme."""
        ok, msg = annuler_dorra(formation_id)
        if ok:
            journaliser(session.get('username'), 'فسخ دورة تكوينية',
                        f'دورة #{formation_id}', msg)
            app.logger.info('Dorra %s fsakhée par %s', formation_id,
                            session.get('username'))
            return jsonify({'succes': True})
        return jsonify({'succes': False, 'erreur': msg}), 400

    # ─── API : participants ────────────────────────────────────────────────────

    @app.route('/lettre/<int:lettre_id>/formations/<int:formation_id>/participants', methods=['GET'])
    @login_required
    def api_get_participants(lettre_id, formation_id):
        parts = get_participants(lettre_id, formation_id)
        return jsonify({'participants': parts})

    @app.route('/lettre/<int:lettre_id>/formations/<int:formation_id>/participants', methods=['POST'])
    @login_required
    def api_save_participants(lettre_id, formation_id):
        if formation_est_finalisee(formation_id):
            return jsonify({'erreur': 'الدورة مسجَّلة نهائيًّا ولا يمكن تعديلها'}), 403
        data = request.get_json(silent=True) or {}
        brut = data.get('participants', [])
        if not isinstance(brut, list):
            return jsonify({'erreur': 'معطيات المتكوّنين غير صالحة'}), 400
        participants = [p for p in brut
                        if isinstance(p, dict) and str(p.get('nom_prenom') or '').strip()]
        # الخطوة 3 : لا تُستكمل إلا بمتكوّن واحد على الأقل.
        if not participants:
            return jsonify({'erreur': 'يجب اختيار متكوّن واحد على الأقل'}), 400

        # v1.6 — الجنس / الفئة العمريّة : l'une des options prévues.
        # v1.7.1 — et désormais OBLIGATOIRES pour chaque participant.
        for p in participants:
            nom_p = str(p.get('nom_prenom')).strip()
            if not str(p.get('sexe') or '').strip():
                return jsonify({'erreur': f'{nom_p}: يجب اختيار الجنس'}), 400
            if not str(p.get('fiaa_omria') or '').strip():
                return jsonify({'erreur': f'{nom_p}: يجب اختيار الفئة العمريّة'}), 400
            erreurs_choix = verifier_choix(p)
            if erreurs_choix:
                return jsonify({'erreur': f'{nom_p}: {erreurs_choix[0]}'}), 400

        # Block formateur from being added as participant
        conn = get_connection()
        formation_row = conn.execute(
            'SELECT nom_formateur FROM formations WHERE id=?', (formation_id,)
        ).fetchone()
        conn.close()
        if formation_row and formation_row['nom_formateur']:
            formateur = formation_row['nom_formateur'].strip().lower()
            conflict = next(
                (p for p in participants
                 if p.get('nom_prenom', '').strip().lower() == formateur),
                None
            )
            if conflict:
                return jsonify({
                    'erreur': f'لا يمكن إضافة المكوِّن "{conflict["nom_prenom"]}" كمشارك في نفس الدورة'
                }), 400

        # Vérification doublons identifiant_unique
        seen_ids = {}
        for p in participants:
            uid = p.get('identifiant_unique', '').strip()
            if uid:
                if uid in seen_ids:
                    return jsonify({
                        'erreur': f'المشارك بالمعرف الوحيد "{uid}" مضاف مرتين في القائمة'
                    }), 400
                seen_ids[uid] = True

        # Un مشارك ne peut pas suivre deux دورات au même moment, même dans
        # deux lieux différents (ni être l'مكوّن de l'autre).
        formation, simultanees = dorrat_simultanees(formation_id)
        if formation and simultanees:
            erreurs = conflits.conflits_de_participants(participants, formation, simultanees)
            if erreurs:
                return jsonify({
                    'erreur': 'لا يمكن لمشارك حضور دورتين في نفس التّاريخ ونفس الفترة:\n— '
                              + '\n— '.join(erreurs),
                    'conflits': erreurs}), 400

        # v1.7.1 : valeurs de l'البطاقة déduites des participants AVANT la
        # modification — pour savoir ensuite si elles avaient été gardées telles.
        anciens = bataqa_derives(lettre_id, formation_id)
        ok = save_participants(lettre_id, formation_id, participants)
        if ok:
            # v1.7.1 : البطاقة (المستهدفون / المصالح) suit la nouvelle liste
            # quand ces champs n'avaient pas été retouchés à la main ; la
            # مذكّرة non retouchée est, elle, toujours régénérée à la lecture.
            actualises = actualiser_bataqa_apres_participants(lettre_id, formation_id, anciens)
            # v1.7.1 : الجنس / الفئة العمريّة / مكان العمل choisis ici complètent
            # la fiche de la personne (sans jamais écraser une valeur saisie),
            # pour être proposés automatiquement la fois suivante.
            completer_fiches_depuis_participants(participants)
            memo = get_memo_data(lettre_id, formation_id) or {}
            return jsonify({'succes': True, 'bataqa_actualisee': actualises,
                            'memo_manuel': bool(memo.get('contenu_manuel'))})
        return jsonify({'erreur': 'خطأ في الحفظ'}), 500

    # ─── API البطاقة البيداغوجية — données (GET / POST) ─────────────────────

    @app.route('/lettre/<int:lettre_id>/formations/<int:formation_id>/bataqa/data', methods=['GET'])
    @login_required
    def api_get_bataqa_data(lettre_id, formation_id):
        data = get_bataqa_data(lettre_id, formation_id)
        if data is None:
            return jsonify({'erreur': 'الدورة غير موجودة'}), 404
        return jsonify(data)

    @app.route('/lettre/<int:lettre_id>/formations/<int:formation_id>/bataqa/data', methods=['POST'])
    @login_required
    def api_save_bataqa_data(lettre_id, formation_id):
        if formation_est_finalisee(formation_id):
            return jsonify({'erreur': 'الدورة مسجَّلة نهائيًّا ولا يمكن تعديلها'}), 403
        # Verify formation belongs to letter
        detail = get_lettre_detail(lettre_id)
        if not detail:
            return jsonify({'erreur': 'غير موجود'}), 404
        formation = next((f for f in detail['formations'] if f['id'] == formation_id), None)
        if not formation:
            return jsonify({'erreur': 'الدورة غير موجودة'}), 404

        data = request.get_json(silent=True) or {}

        # Server-side validation — use merged bataqa data so madda fields are resolved
        merged = get_bataqa_data(lettre_id, formation_id) or {}
        if not merged.get('titre', '').strip():
            return jsonify({'erreur': 'عنوان الدورة مطلوب'}), 400
        if not merged.get('date_formation', '').strip():
            return jsonify({'erreur': 'تاريخ الدورة مطلوب'}), 400
        if not merged.get('type_formation', '').strip():
            return jsonify({'erreur': 'نوع التكوين مطلوب'}), 400
        autorise, msg = etape_autorisee(formation_id, 'bataqa')
        if not autorise:
            return jsonify({'erreur': msg}), 400
        parts = get_participants(lettre_id, formation_id)

        ok = save_bataqa_data(formation_id, data)
        if ok:
            return jsonify({'succes': True, 'nb_participants': len(parts)})
        return jsonify({'erreur': 'خطأ في الحفظ'}), 500

    # ─── Programme (étape 5) ─────────────────────────────────────────────────

    @app.route('/lettre/<int:lettre_id>/formations/<int:formation_id>/programme/data', methods=['GET'])
    @login_required
    def api_get_programme_data(lettre_id, formation_id):
        data = get_programme_data(lettre_id, formation_id)
        if data is None:
            return jsonify({'erreur': 'غير موجود'}), 404
        return jsonify(data)

    def _minutes(hhmm):
        try:
            h, m = str(hhmm).split(':')[:2]
            return int(h) * 60 + int(m)
        except (ValueError, AttributeError):
            return None

    def _verifier_lignes(rows, apres_midi):
        """Contrôle serveur des فقرات d'un برنامج (d'un jour, ou d'UN jour d'une
        دورة متعدّدة الأيّام) : rend (lignes complètes, None) ou (None, refus).
        V2 : extrait tel quel de api_save_programme_data (mêmes règles, mêmes
        messages) pour servir aussi à la confirmation jour par jour."""
        data_rows = [r for r in rows if isinstance(r, dict) and r.get('type') == 'row']
        if not data_rows:
            return None, (jsonify({'erreur': 'يجب إضافة صفٍّ واحد على الأقل في البرنامج'}), 400)
        # Un صف كامل = التوقيت + بيان النشاط + المتدخّلون. Garde serveur : la
        # vérification du navigateur ne suffit pas pour un document officiel.
        # التوقيت : « من HH:MM إلى HH:MM », recomposé ici à partir des deux
        # sélecteurs d'heure pour que le PDF n'ait rien à calculer.
        # v1.6.1 : l'heure peut être tapée au clavier — « 8:30 » est ramené à
        # « 08:30 » ; une heure illisible (« 25:00 », « 8h7x ») est refusée.
        for r in data_rows:
            for cle in ('time_debut', 'time_fin'):
                v = (r.get(cle) or '').strip()
                if not v:
                    continue
                m = re.fullmatch(r'(\d{1,2}):(\d{2})', v)
                if not m or int(m.group(1)) > 23 or int(m.group(2)) > 59:
                    return None, (jsonify({'erreur': f'صيغة التوقيت «{v}» غير صحيحة '
                                                     '(مثال: 08:30).'}), 400)
                r[cle] = f'{int(m.group(1)):02d}:{m.group(2)}'
        for r in data_rows:
            debut = (r.get('time_debut') or '').strip()
            fin   = (r.get('time_fin') or '').strip()
            if debut and fin:
                r['time'] = f'من {debut} إلى {fin}'
            elif debut:
                r['time'] = f'انطلاقا من {debut}'
        complets = [r for r in data_rows
                    if (r.get('time') or '').strip()
                    and (r.get('activity') or '').strip()
                    and (r.get('participants') or '').strip()]
        if not complets:
            return None, (jsonify({'erreur': 'يجب تعمير صفٍّ واحد كامل على الأقل: '
                                             'التوقيت وبيان النشاط والمتدخّلون'}), 400)

        # Garde serveur : chaque plage (من → إلى) doit durer 15 min au moins.
        # Le navigateur avertit déjà à la saisie, mais un document officiel ne
        # peut dépendre du seul contrôle client.
        H_MIN, H_MAX = _minutes('08:00'), _minutes('17:00')
        # فترة مسائيّة : la journée de la دورة commence à 13:30.
        if apres_midi:
            H_MIN = _minutes('13:30')
        for r in complets:
            debut = (r.get('time_debut') or '').strip()
            fin   = (r.get('time_fin') or '').strip()
            if not (debut and fin):
                continue
            md, mf = _minutes(debut), _minutes(fin)
            if md is None or mf is None:
                continue
            # Bornes de la journée : 08:00–17:00.
            if md < H_MIN or md > H_MAX or mf < H_MIN or mf > H_MAX:
                plage = ('13:30–17:00، دورة في الفترة المسائيّة' if apres_midi
                         else '08:00–17:00')
                return None, (jsonify({'erreur': f'التوقيت «من {debut} إلى {fin}» خارج '
                                                 f'نطاق العمل ({plage}).'}), 400)
            # La fin doit suivre le début.
            if mf <= md:
                return None, (jsonify({'erreur': f'الصف «من {debut} إلى {fin}»: نهاية '
                                                 'التوقيت يجب أن تكون بعد بدايته.'}), 400)
            if mf - md < 15:
                return None, (jsonify({'erreur': f'الفترة «من {debut} إلى {fin}» أقصر من '
                                                 '15 دقيقة. لكلّ فقرة 15 دقيقة على الأقلّ.'}), 400)

        # Continuité : chaque صف doit démarrer à la fin du صف précédent —
        # jamais avant (le début est verrouillé côté client, garde serveur ici).
        fin_precedente = None
        for r in complets:
            debut = (r.get('time_debut') or '').strip()
            fin   = (r.get('time_fin') or '').strip()
            md, mf = _minutes(debut), _minutes(fin)
            if md is None or mf is None:
                continue
            if fin_precedente is not None and md < fin_precedente:
                return None, (jsonify({'erreur': 'يجب أن ينطلق كلّ صف من نهاية توقيت الصف '
                                                 'الذي قبله: التوقيت غير متواصل.'}), 400)
            fin_precedente = mf
        return complets, None

    @app.route('/lettre/<int:lettre_id>/formations/<int:formation_id>/programme/data', methods=['POST'])
    @login_required
    def api_save_programme_data(lettre_id, formation_id):
        if formation_est_finalisee(formation_id):
            return jsonify({'erreur': 'الدورة مسجَّلة نهائيًّا ولا يمكن تعديلها'}), 403
        autorise, msg = etape_autorisee(formation_id, 'programme')
        if not autorise:
            return jsonify({'erreur': msg}), 400
        # V2 : une دورة متعدّدة الأيّام se confirme jour par jour.
        if formation_est_multi_jours(formation_id):
            return jsonify({'erreur': 'هذه الدورة متعدّدة الأيّام: يُعمَّر برنامجها '
                                      'ويُؤكَّد يومًا بيوم.'}), 400
        body = request.get_json(force=True, silent=True) or {}
        rows = body.get('rows', [])
        if not isinstance(rows, list):
            return jsonify({'erreur': 'الصفوف غير صحيحة'}), 400
        conn = get_connection()
        try:
            _f = conn.execute('SELECT periode FROM formations WHERE id=?',
                              (formation_id,)).fetchone()
        finally:
            conn.close()
        apres_midi = bool(_f and (_f['periode'] or '').strip() == 'مساءا')
        complets, refus = _verifier_lignes(rows, apres_midi)
        if refus:
            return refus
        autres = [r for r in rows if isinstance(r, dict) and r.get('type') != 'row']
        ok = save_programme_data(formation_id, {
            'reference': body.get('reference', ''),
            'moment':    body.get('moment', 'صباحا'),
            'rows':      autres + complets,
        })
        if ok:
            return jsonify({'succes': True})
        return jsonify({'erreur': 'خطأ في الحفظ'}), 500

    # ─── V2 : برنامج دورة متعدّدة الأيّام, jour par jour ──────────────────────

    @app.route('/lettre/<int:lettre_id>/formations/<int:formation_id>/programme/jours',
               methods=['GET'])
    @login_required
    def api_get_programme_jours(lettre_id, formation_id):
        data = get_programme_jours(lettre_id, formation_id)
        if data is None:
            return jsonify({'erreur': 'غير موجود'}), 404
        return jsonify(data)

    @app.route('/lettre/<int:lettre_id>/formations/<int:formation_id>/programme/jour/<int:jour>',
               methods=['POST'])
    @login_required
    def api_save_programme_jour(lettre_id, formation_id, jour):
        """Confirme UN jour du برنامج. Le jour suivant ne s'ouvre qu'ensuite ;
        la confirmation du dernier jour achève l'étape 5."""
        detail = get_lettre_detail(lettre_id)
        if not detail or not any(f['id'] == formation_id for f in detail['formations']):
            return jsonify({'erreur': 'غير موجود'}), 404
        if formation_est_finalisee(formation_id):
            return jsonify({'erreur': 'الدورة مسجَّلة نهائيًّا ولا يمكن تعديلها'}), 403
        autorise, msg = etape_autorisee(formation_id, 'programme')
        if not autorise:
            return jsonify({'erreur': msg}), 400
        body = request.get_json(force=True, silent=True) or {}
        rows = body.get('rows', [])
        if not isinstance(rows, list):
            return jsonify({'erreur': 'الصفوف غير صحيحة'}), 400
        periode = (body.get('periode') or '').strip()
        if periode not in ('', 'صباحا', 'مساءا'):
            return jsonify({'erreur': 'الفترة غير صالحة'}), 400
        complets, refus = _verifier_lignes(rows, periode == 'مساءا')
        if refus:
            return refus
        ok, info = save_programme_jour(formation_id, jour, periode, complets)
        if not ok:
            return jsonify({'erreur': info}), 400
        if info['termine']:
            journaliser(session.get('username'), 'تأكيد برنامج دورة متعدّدة الأيّام',
                        f'دورة #{formation_id}', f"{info['nb_jours']} أيّام")
        return jsonify({'succes': True, **info})

    # ─── مذكرة تكوين داخلية (étape 6) ────────────────────────────────────────

    @app.route('/lettre/<int:lettre_id>/formations/<int:formation_id>/memo/data', methods=['GET'])
    @login_required
    def api_get_memo_data(lettre_id, formation_id):
        autorise, msg = etape_autorisee(formation_id, 'memo')
        if not autorise:
            return jsonify({'erreur': msg}), 400
        # ?auto=1 : texte régénéré à partir des données courantes (bouton
        # « إعادة التوليد التلقائي »), en ignorant les retouches sauvegardées.
        force_auto = request.args.get('auto') == '1'
        data = get_memo_data(lettre_id, formation_id, force_auto=force_auto)
        if data is None:
            return jsonify({'erreur': 'الدورة غير موجودة'}), 404
        cfg = get_config()
        data['titre_directeur_general'] = cfg.get('titre_directeur_general', 'العميد')
        data['nom_directeur_general']   = cfg.get('nom_directeur_general', '')
        return jsonify(data)

    @app.route('/lettre/<int:lettre_id>/formations/<int:formation_id>/memo/data', methods=['POST'])
    @login_required
    def api_save_memo_data(lettre_id, formation_id):
        # La مذكّرة ne s'ouvre qu'une fois la chaîne complète : مشاركون →
        # بطاقة → برنامج. C'est ce contrôle qui manquait : une dorra sans
        # participants pouvait produire sa مذكّرة النهائية.
        autorise, msg = etape_autorisee(formation_id, 'memo')
        if not autorise:
            return jsonify({'erreur': msg}), 400

        body = request.get_json(silent=True) or {}
        # « تسجيل التكوين » : simple enregistrement, sans validation du contenu
        if not body.get('confirmer', True):
            ok = save_memo_data(formation_id, get_memo_data(lettre_id, formation_id) or {},
                                confirmer=False)
            return (jsonify({'succes': True}) if ok
                    else (jsonify({'erreur': 'خطأ في الحفظ'}), 500))

        objet  = (body.get('objet') or '').strip()
        corps  = (body.get('corps') or '').strip()
        moujah = body.get('moujah', [])
        if not objet:
            return jsonify({'erreur': 'موضوع المذكرة مطلوب'}), 400
        if not corps:
            return jsonify({'erreur': 'نصّ المذكرة مطلوب'}), 400
        if not isinstance(moujah, list) or not [m for m in moujah
                                                if (m.get('nom') or '').strip()]:
            return jsonify({'erreur': 'يجب إضافة موجَّه إليه واحد على الأقلّ'}), 400

        ok = save_memo_data(formation_id, {
            'objet':          objet,
            'corps':          corps,
            'heure_debut':    body.get('heure_debut', ''),
            'contenu_manuel': body.get('contenu_manuel', False),
            'moujah':         moujah,
        }, confirmer=True)
        if ok:
            return jsonify({'succes': True})
        return jsonify({'erreur': 'تعذّر الحفظ — قد تكون الدورة مسجَّلة نهائيًّا'}), 500

    @app.route('/lettre/<int:lettre_id>/formations/<int:formation_id>/finaliser', methods=['POST'])
    @login_required
    def api_finaliser_formation(lettre_id, formation_id):
        """« تسجيل الدورة في المنظومة » — verrou définitif après impression de la مذكرة."""
        ok, info = finaliser_formation(formation_id)
        if ok:
            journaliser(session.get('username'), 'تسجيل دورة نهائيًّا في المنظومة',
                        f'دورة #{formation_id}', f'مراسلة #{lettre_id}')
            app.logger.info('Dorra %s finalisée par %s', formation_id, session.get('username'))
            return jsonify({'succes': True, 'finalise_at': info})
        return jsonify({'erreur': info}), 400

    MOTIF_MIN = 5

    @app.route('/lettre/<int:lettre_id>/formations/<int:formation_id>/deverrouiller',
               methods=['POST'])
    @admin_required
    def api_deverrouiller_formation(lettre_id, formation_id):
        """« التراجع للتحيين » (v1.6) — réservé au مشرف, motif obligatoire,
        consigné dans سجلّ العمليّات."""
        body = request.get_json(silent=True) or {}
        motif = ' '.join(str(body.get('motif') or '').split())
        if len(motif) < MOTIF_MIN:
            return jsonify({'erreur': f'سبب التراجع إجباري ({MOTIF_MIN} أحرف على الأقلّ)'}), 400
        conn = get_connection()
        try:
            f = conn.execute('SELECT lettre_id FROM formations WHERE id=?',
                             (formation_id,)).fetchone()
        finally:
            conn.close()
        if not f or f['lettre_id'] != lettre_id:
            return jsonify({'erreur': 'الدورة غير موجودة'}), 404
        ok, info = deverrouiller_formation(formation_id)
        if not ok:
            return jsonify({'erreur': info}), 400
        details = motif + (' — سقطت المصادقة النهائيّة على البرنامج' if info['scelle_leve'] else '')
        journaliser(session.get('username'), 'التراجع للتحيين',
                    f'دورة #{formation_id} ({info["titre"]})', details)
        app.logger.info('Dorra %s déverrouillée par %s', formation_id, session.get('username'))
        return jsonify({'succes': True, 'scelle_leve': info['scelle_leve']})

    # ─── Étapes ──────────────────────────────────────────────────────────────

    @app.route('/etape/lettre/<int:lettre_id>/<int:etape>', methods=['POST'])
    @login_required
    def valider_etape_lettre(lettre_id, etape):
        """Validate a letter-level step (etape 1 or 2, formation_id=None)."""
        if etape not in (1, 2):
            return jsonify({'ok': False, 'error': 'invalid etape'}), 400
        ok = valider_etape(lettre_id, None, etape)
        return jsonify({'ok': ok})

    @app.route('/etape/formation/<int:lettre_id>/<int:formation_id>/<int:etape>', methods=['POST'])
    @login_required
    def valider_etape_formation_route(lettre_id, formation_id, etape):
        """Validate a per-formation step (etape 3-9)."""
        if etape not in range(3, 10):
            return jsonify({'ok': False, 'error': 'invalid etape'}), 400
        ok = valider_etape(lettre_id, formation_id, etape)
        return jsonify({'ok': ok})
