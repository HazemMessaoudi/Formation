"""مراسلات — programmes de formation et مراسلات حرة (saisie, validation, détail)."""

import logging as _logging
_log = _logging.getLogger('formation.' + __name__)

from datetime import datetime

from flask import render_template, request, jsonify, redirect, url_for, session

from core import identite, periode, conflits
from core.database import (
    candidats_mkow_par_nom, programme_est_scelle,
    get_grades, get_config, get_mawad, get_lieux, mkowin_par_noms,
    get_lettre_detail, programme_est_complet,
    save_programme, update_programme, verrouiller_lettre,
    save_lettre_libre, update_lettre_libre,
    delete_programme_inacheve, get_connection, journaliser,
    noms_jihat, get_jihat, get_dr_lettres, annee_registre,
    attribuer_numero_dr, annuler_dr_lettre,
    revue_dorra, revue_programme, sceller_programme, dorrat_aux_dates,
    annee_admise,
)



class _SaisieInvalide(ValueError):
    pass


def _annee_de(data):
    """Année d'un corps JSON : entier plausible, sinon refus propre (400)."""
    v = data.get('annee')
    if v in (None, ''):
        return datetime.now().year
    try:
        a = int(str(v).strip())
    except (TypeError, ValueError):
        raise _SaisieInvalide('السنة غير صالحة')
    if not 2000 <= a <= 2100:
        raise _SaisieInvalide('السنة غير صالحة')
    return a


def _formations_de(data):
    f = data.get('formations', [])
    if not isinstance(f, list) or not all(isinstance(x, dict) for x in f):
        raise _SaisieInvalide('معطيات الدورات غير صالحة')
    return f


def _texte(data, cle):
    v = data.get(cle, '')
    return v.strip() if isinstance(v, str) else ''

def register(app, ctx):
    login_required = ctx['login_required']
    app.register_error_handler(
        _SaisieInvalide, lambda e: (jsonify({'erreur': str(e)}), 400))

    def _refus_de_lieu(formations, lettre_id=None):
        """Même تاريخ + même فترة + même مكان : refus, avec la liste des cas."""
        # V2 : tous les jours d'une دورة متعدّدة الأيّام sont contrôlés.
        existantes = dorrat_aux_dates(
            [d for f in formations or [] for d in (conflits.jours_occupes(f)
                                                   or [f.get('date_formation')])],
            lettre_id)
        erreurs = conflits.conflits_de_lieu(formations, existantes)
        if not erreurs:
            return None
        return jsonify({'erreur': 'لا يمكن برمجة دورتين في نفس المكان ونفس الفترة:\n— '
                                  + '\n— '.join(erreurs),
                        'conflits': erreurs}), 400

    # ─── مراسلات – nouvelle lettre ───────────────────────────────────────────

    @app.route('/lettre/nouvelle')
    @login_required
    def nouvelle_lettre():
        grades  = get_grades()
        config  = get_config()
        mawad   = get_mawad()
        lieux   = get_lieux()
        # Mode modification : ?modifier=<id>
        modifier_id   = request.args.get('modifier', type=int)
        lettre_edit   = None
        formations_edit = []
        if modifier_id:
            detail = get_lettre_detail(modifier_id)
            if detail and (detail['lettre'].get('categorie') or 'programme') == 'programme':
                # Un programme entièrement achevé (toutes ses dorrat enregistrées)
                # → lecture seule. Sinon on l'ouvre pour reprendre le travail, même
                # s'il a déjà été confirmé (verrouille=1, en cours de dorrat).
                if programme_est_complet(modifier_id):
                    return redirect(url_for('detail_lettre', lettre_id=modifier_id))
                lettre_edit      = detail['lettre']
                formations_edit  = detail['formations']
        # Plus d'injection de toute la table مكوّنون (v1.4) : l'autocomplétion
        # interroge /api/mkowin/recherche. Seules les fiches publiques des
        # مكوّنين déjà présents dans le programme modifié sont fournies.
        mkowin = mkowin_par_noms(f.get('nom_formateur') for f in formations_edit)
        return render_template('nouvelle_lettre.html',
                               grades=grades, config=config,
                               mawad=mawad, lieux=lieux, mkowin=mkowin,
                               jihat=noms_jihat(),
                               jihat_admin=[j['nom'] for j in get_jihat('admin')],
                               jihat_garde=[j['nom'] for j in get_jihat('garde')],
                               now_year=datetime.now().year,
                               lettre_edit=lettre_edit,
                               formations_edit=formations_edit)

    # ─── مراسلات – sauvegarde du programme (sans PDF) ────────────────────────

    @app.route('/lettre/enregistrer', methods=['POST'])
    @login_required
    def enregistrer_programme():
        data = request.get_json(silent=True) or {}
        type_lettre = data.get('type', 'interne')
        mois        = data.get('mois', '')
        annee       = _annee_de(data)
        formations  = _formations_de(data)
        refus = _refus_de_lieu(formations)
        if refus:
            return refus
        cfg         = get_config()
        titre_resp, nom_resp = identite.signataire(cfg)

        lettre_id = save_programme(type_lettre, mois, annee, formations, nom_resp, titre_resp)
        return jsonify({'succes': True, 'lettre_id': lettre_id})

    @app.route('/lettre/<int:lettre_id>/mettre-a-jour', methods=['POST'])
    @login_required
    def mettre_a_jour_programme(lettre_id):
        data        = request.get_json(silent=True) or {}
        type_lettre = data.get('type', 'interne')
        mois        = data.get('mois', '')
        annee       = _annee_de(data)
        formations  = _formations_de(data)
        refus = _refus_de_lieu(formations, lettre_id)
        if refus:
            return refus
        ok = update_programme(lettre_id, type_lettre, mois, annee, formations)
        if ok is False:
            return jsonify({'erreur': 'المراسلة مُغلقة ولا يمكن تعديلها'}), 403
        return jsonify({'succes': True})

    @app.route('/lettre/autosave', methods=['POST'])
    @login_required
    def autosave_programme():
        """Sauvegarde INDULGENTE d'un brouillon (appelée par l'autosave périodique et
        par navigator.sendBeacon au moment de quitter la page). Accepte du JSON
        classique OU un corps brut (beacon). Crée ou met à jour un brouillon
        verrouille=0 afin qu'il apparaisse dans « إستكمال برنامج تكوين »."""
        import json as _json
        data = request.get_json(silent=True)
        if data is None:
            try:
                data = _json.loads(request.get_data(as_text=True) or '{}')
            except Exception:
                _log.warning('autosave_programme : exception ignorée', exc_info=True)
                data = {}
        type_lettre = data.get('type', 'interne')
        mois        = data.get('mois', '')
        try:
            annee = int(data.get('annee') or datetime.now().year)
        except (TypeError, ValueError):
            annee = datetime.now().year
        formations = data.get('formations', []) or []
        # Rien d'utile à enregistrer → on ne crée pas de ligne vide
        a_titre = any((f.get('titre') or '').strip() for f in formations)
        if not (mois or a_titre):
            return jsonify({'succes': False}), 200

        lettre_id = data.get('lettre_id')
        if lettre_id:
            ok = update_programme(int(lettre_id), type_lettre, mois, annee, formations)
            if ok is False:
                return jsonify({'succes': False}), 200
            return jsonify({'succes': True, 'lettre_id': int(lettre_id)})
        cfg        = get_config()
        titre_resp, nom_resp = identite.signataire(cfg)
        new_id = save_programme(type_lettre, mois, annee, formations, nom_resp, titre_resp)
        return jsonify({'succes': True, 'lettre_id': new_id})

    @app.route('/lettre/<int:lettre_id>/valider', methods=['POST'])
    @login_required
    def valider_programme(lettre_id):
        data = request.get_json(silent=True) or {}
        type_lettre = data.get('type', 'interne')
        if type_lettre not in ('interne', 'externe'):
            return jsonify({'erreur': 'نوع المراسلة غير صالح'}), 400

        # ── Les dates sont contrôlées ICI, et nulle part avant ──────────────
        # Le تأكيد est le point de non-retour : la مراسلة prend son عدد et
        # devient un acte officiel. Une دورة datée hors du شهر du برنامج
        # appartient à un autre برنامج — دورة فيفري في فيفري. Pendant la
        # saisie au contraire on ne refuse rien : un brouillon porte des
        # dates provisoires, et les refuser ferait perdre le travail.
        detail = get_lettre_detail(lettre_id)
        if detail:
            # Le سجلّ ouvert est celui d'une année : on n'y inscrit pas un
            # برنامج d'une autre. Le عدد viendrait de cette série-ci alors que
            # la مراسلة se dirait d'une autre année — un سجلّ qui se
            # contredit lui-même.
            annee_lettre = detail['lettre'].get('annee')
            annee_sejel = annee_registre()
            try:
                annee_int = int(annee_lettre) if annee_lettre else None
            except (TypeError, ValueError):
                return jsonify({'erreur': 'سنة البرنامج غير صالحة'}), 400
            # v1.7 : برنامج السنة الموالية (جانفي يُرسَل في ديسمبر) يأخذ عدده
            # من السّجلّ المفتوح يوم الإصدار. Seul un برنامج d'une année
            # écoulée reste refusé.
            if annee_int and not annee_admise(annee_int, annee_sejel):
                return jsonify({'erreur':
                    f'البرنامج لسنة {annee_lettre} والسّجلّ المفتوح هو سجلّ '
                    f'{annee_sejel}. يُقبل برنامج السنة الجارية أو السنة الموالية '
                    f'فقط، ولا يُسند عدد لبرنامج سنة منقضية.'}), 400

            erreurs = periode.verifier_dates(detail['lettre'].get('mois'),
                                             detail['lettre'].get('annee'),
                                             detail['formations'])
            if erreurs:
                return jsonify({'erreur': 'تواريخ خارج شهر البرنامج:\n— '
                                          + '\n— '.join(erreurs)}), 400
            # Dernier verrou : un brouillon enregistré par l'autosauvegarde
            # (indulgente) ne doit pas prendre son عدد avec une salle occupée.
            refus = _refus_de_lieu(detail['formations'], lettre_id)
            if refus:
                return refus
            # Chaque مكوّن doit figurer dans قائمة الأسماء : c'est sa fiche qui
            # nourrira ensuite المستحقّات et وثائق الخلاص.
            inconnus = sorted({(f.get('nom_formateur') or '').strip()
                               for f in detail['formations']
                               if (f.get('nom_formateur') or '').strip()
                               and not candidats_mkow_par_nom(f.get('nom_formateur'))})
            if inconnus:
                return jsonify({'erreur': 'مكوّن غير مسجَّل في قائمة الأسماء:\n— '
                                          + '\n— '.join(inconnus)
                                          + '\nأضفه إلى قائمة الأسماء قبل التأكيد.'}), 400

        ref, numero = verrouiller_lettre(lettre_id, type_lettre)
        if ref:
            journaliser(session.get('username'), 'تأكيد وإغلاق برنامج تكوين',
                        f'مراسلة #{lettre_id}', ref)
            app.logger.info('Programme %s verrouillé (%s) par %s',
                            lettre_id, ref, session.get('username'))
            return jsonify({'succes': True, 'ref': ref, 'lettre_id': lettre_id})
        return jsonify({'erreur': 'خطأ في التأكيد'}), 500

    # ─── الخطوة 2 : مراسلات المديرين الجهويّين (ترقيم / فسخ / مراجعة) ──────────

    @app.route('/lettre/<int:lettre_id>/dr', methods=['GET'])
    @login_required
    def liste_dr(lettre_id):
        """Les مراسلات المديرين الجهويّين déjà tirées, pour rafraîchir l'écran
        sans recharger toute la page."""
        return jsonify({'dr_lettres': get_dr_lettres(lettre_id)})

    @app.route('/lettre/<int:lettre_id>/dr/attribuer', methods=['POST'])
    @login_required
    def attribuer_dr(lettre_id):
        """Tire (une seule fois) le عدد d'une مراسلة مدير جهوي. Réutilise le عدد
        existant si la même جهة a déjà la sienne — réimprimer ne consomme rien.
        C'est cet appel, et non l'ouverture du PDF, qui fait foi du tirage."""
        data = request.get_json(silent=True) or {}
        destination = (data.get('destination') or '').strip()
        type_mr     = (data.get('type_mr') or 'externe').strip()
        if not destination:
            return jsonify({'erreur': 'يرجى كتابة الجهة الموجَّه إليها'}), 400
        ref, num, typ, deja = attribuer_numero_dr(lettre_id, type_mr, destination)
        if not ref:
            if programme_est_scelle(lettre_id):
                return jsonify({'erreur': 'البرنامج مصادق عليه نهائيًّا: لا يمكن ترقيم مراسلة جديدة.'}), 400
            return jsonify({'erreur': 'يجب تأكيد البرنامج أوّلا قبل ترقيم مراسلة المدير الجهوي'}), 400
        if not deja:
            journaliser(session.get('username'), 'ترقيم مراسلة المدير الجهوي',
                        f'مراسلة #{lettre_id}',
                        f"{ref} ({'خارجية' if typ == 'externe' else 'داخلية'})")
        return jsonify({'succes': True, 'ref': ref, 'numero': num, 'type': typ,
                        'deja': deja, 'destination': destination})

    @app.route('/lettre/<int:lettre_id>/dr/<int:dr_id>/annuler', methods=['POST'])
    @login_required
    def annuler_dr(lettre_id, dr_id):
        """فسخ مراسلة مدير جهوي واحدة : son عدد revient au pool. C'est le
        correctif du défaut de l'étape 2 — retirer une مراسلة libère son عدد."""
        ok, info = annuler_dr_lettre(dr_id)
        if ok:
            journaliser(session.get('username'), 'فسخ مراسلة المدير الجهوي',
                        f'مراسلة #{lettre_id}', info)
            app.logger.info('مراسلة مدير جهوي %s fsakhée par %s', dr_id,
                            session.get('username'))
            return jsonify({'succes': True, 'ref': info})
        return jsonify({'succes': False, 'erreur': info}), 400

    # ─── المراجعة النهائيّة : الدورة، ثمّ البرنامج، ثمّ المصادقة ───────────────

    @app.route('/lettre/<int:lettre_id>/formations/<int:formation_id>/revue', methods=['GET'])
    @login_required
    def revue_dorra_route(lettre_id, formation_id):
        r = revue_dorra(formation_id)
        if r is None:
            return jsonify({'erreur': 'الدورة غير موجودة'}), 404
        return jsonify(r)

    @app.route('/lettre/<int:lettre_id>/revue', methods=['GET'])
    @login_required
    def revue_programme_route(lettre_id):
        r = revue_programme(lettre_id)
        if r is None:
            return jsonify({'erreur': 'البرنامج غير موجود'}), 404
        return jsonify(r)

    @app.route('/lettre/<int:lettre_id>/sceller', methods=['POST'])
    @login_required
    def sceller_programme_route(lettre_id):
        """المصادقة النهائيّة : ne scelle qu'après vérification de سلامة
        المعطيات وترقيم المراسلات ; refuse en nommant ce qui cloche."""
        ok, info = sceller_programme(lettre_id)
        if ok:
            journaliser(session.get('username'), 'مصادقة نهائيّة على البرنامج',
                        f'مراسلة #{lettre_id}', str(info))
            app.logger.info('Programme %s scellé par %s', lettre_id,
                            session.get('username'))
            return jsonify({'succes': True, 'scelle_at': info})
        return jsonify({'succes': False, 'problemes': info}), 400

    # ─── مراسلات حرة – nouvelle lettre libre ─────────────────────────────────

    @app.route('/lettre/libre/nouvelle')
    @login_required
    def nouvelle_lettre_libre():
        # Mode modification : ?modifier=<id>
        modifier_id = request.args.get('modifier', type=int)
        lettre_edit = None
        if modifier_id:
            detail = get_lettre_detail(modifier_id)
            if detail and detail['lettre'].get('categorie') == 'libre':
                if detail['lettre'].get('verrouille'):
                    return redirect(url_for('detail_lettre', lettre_id=modifier_id))
                lettre_edit = detail['lettre']
        return render_template('nouvelle_lettre_libre.html',
                               now_year=datetime.now().year,
                               lettre_edit=lettre_edit)

    @app.route('/lettre/libre/enregistrer', methods=['POST'])
    @login_required
    def enregistrer_lettre_libre():
        data       = request.get_json(silent=True) or {}
        type_l     = data.get('type', 'interne')
        mois       = data.get('mois', '')
        annee      = _annee_de(data)
        destinataire = _texte(data, 'destinataire')
        objet      = _texte(data, 'objet')
        corps      = _texte(data, 'corps')
        cfg        = get_config()
        titre_resp, nom_resp = identite.signataire(cfg)
        msahib       = _texte(data, 'msahib')
        moujah_lahom = data.get('moujah_lahom', '')
        import json as _json
        if isinstance(moujah_lahom, list):
            moujah_lahom = _json.dumps(moujah_lahom, ensure_ascii=False)
        lettre_id  = save_lettre_libre(type_l, mois, annee, destinataire, objet, corps,
                                       nom_resp, titre_resp, msahib, moujah_lahom)
        return jsonify({'succes': True, 'lettre_id': lettre_id})

    @app.route('/lettre/libre/<int:lettre_id>/mettre-a-jour', methods=['POST'])
    @login_required
    def mettre_a_jour_lettre_libre(lettre_id):
        data         = request.get_json(silent=True) or {}
        type_l       = data.get('type', 'interne')
        mois         = data.get('mois', '')
        annee        = _annee_de(data)
        destinataire = _texte(data, 'destinataire')
        objet        = _texte(data, 'objet')
        corps        = _texte(data, 'corps')
        msahib       = _texte(data, 'msahib')
        moujah_lahom = data.get('moujah_lahom', '')
        import json as _json
        if isinstance(moujah_lahom, list):
            moujah_lahom = _json.dumps(moujah_lahom, ensure_ascii=False)
        ok = update_lettre_libre(lettre_id, type_l, mois, annee, destinataire, objet, corps,
                                  msahib, moujah_lahom)
        if ok is False:
            return jsonify({'erreur': 'المراسلة مُغلقة ولا يمكن تعديلها'}), 403
        return jsonify({'succes': True})

    @app.route('/lettre/libre/<int:lettre_id>/valider', methods=['POST'])
    @login_required
    def valider_lettre_libre(lettre_id):
        data = request.get_json(silent=True) or {}
        type_lettre = data.get('type', 'interne')
        if type_lettre not in ('interne', 'externe'):
            return jsonify({'erreur': 'نوع المراسلة غير صحيح'}), 400
        detail = get_lettre_detail(lettre_id)
        if not detail:
            return jsonify({'erreur': 'المراسلة غير موجودة'}), 404
        # v1.4e : ce point d'entrée est celui des مراسلات حرّة SEULEMENT. Un
        # برنامج qui passait par ici prenait son عدد sans aucun de ses contrôles
        # (mois, année, salle occupée).
        if (detail['lettre'].get('categorie') or 'programme') != 'libre':
            return jsonify({'erreur': 'هذه ليست مراسلة حرّة: يُؤكَّد البرنامج من شاشته.'}), 400
        # Même règle que pour les برامج : on n'inscrit pas au سجلّ d'une année
        # une مراسلة datée d'une autre (le numéro se heurterait ensuite à celui
        # du سجلّ de cette autre année).
        annee_lettre = detail['lettre'].get('annee')
        annee_sejel = annee_registre()
        try:
            if annee_lettre and int(annee_lettre) != annee_sejel:
                return jsonify({'erreur':
                    f'المراسلة مؤرّخة بسنة {annee_lettre} والسّجلّ المفتوح هو سجلّ '
                    f'{annee_sejel}. لا يُسند عدد من سجلّ سنة إلى مراسلة سنة أخرى.'}), 400
        except (TypeError, ValueError):
            return jsonify({'erreur': 'سنة المراسلة غير صحيحة'}), 400
        ref, numero = verrouiller_lettre(lettre_id, type_lettre)
        if ref:
            journaliser(session.get('username'), 'تأكيد وإغلاق برنامج تكوين',
                        f'مراسلة #{lettre_id}', ref)
            app.logger.info('Programme %s verrouillé (%s) par %s',
                            lettre_id, ref, session.get('username'))
            return jsonify({'succes': True, 'ref': ref, 'lettre_id': lettre_id})
        return jsonify({'erreur': 'خطأ في التأكيد'}), 500

    @app.route('/lettre/<int:lettre_id>/annuler', methods=['POST'])
    @login_required
    def annuler_programme(lettre_id):
        """Fsakh (annulation) d'un programme de formation non encore enregistré."""
        ok = delete_programme_inacheve(lettre_id)
        if ok:
            journaliser(session.get('username'), 'فسخ برنامج تكوين', f'مراسلة #{lettre_id}')
            app.logger.info('Programme %s supprimé par %s', lettre_id, session.get('username'))
        return jsonify({'succes': ok})

    @app.route('/lettres/<int:lettre_id>')
    @login_required
    def detail_lettre(lettre_id):
        detail = get_lettre_detail(lettre_id)
        if not detail:
            return redirect(url_for('liste_programmes'))
        ltr = detail['lettre']
        categorie = ltr.get('categorie') or 'programme'
        if categorie == 'libre':
            return render_template('lettres/detail_libre.html', lettre=ltr,
                                   now_year=datetime.now().year)

        # Pour chaque dorra : nombre de participants + état de chaque document,
        # afin d'afficher le détail complet et de n'activer que les PDF prêts.
        formations = [dict(f) for f in detail['formations']]
        conn = get_connection()
        try:
            for f in formations:
                fid = f['id']
                f['participants'] = [dict(p) for p in conn.execute(
                    'SELECT nom_prenom, grade, identifiant_unique, lieu_travail, '
                    'jiha_marjiiya, sexe, fiaa_omria '
                    'FROM participants WHERE lettre_id=? AND formation_id=? ORDER BY ordre',
                    (lettre_id, fid)).fetchall()]
                f['nb_participants'] = len(f['participants'])
                for table, cle in (('bataqa_formations', 'bataqa'),
                                   ('programme_formations', 'programme'),
                                   ('memo_formations', 'memo')):
                    try:
                        row = conn.execute(
                            f'SELECT confirmed_at FROM {table} WHERE formation_id=?',
                            (fid,)).fetchone()
                        f[cle + '_ok'] = bool(row and row['confirmed_at'])
                    except Exception:
                        _log.warning('detail_lettre : exception ignorée', exc_info=True)
                        f[cle + '_ok'] = False
                # v1.7 : شهادات — possibles dès que la ورقة الحضور est enregistrée
                try:
                    mu = conn.execute('SELECT hodour_at FROM mustahaqqat WHERE formation_id=?',
                                      (fid,)).fetchone()
                    f['nb_presents'] = conn.execute(
                        'SELECT COUNT(*) FROM mustahaqqat_hodour WHERE formation_id=? '
                        'AND present=1', (fid,)).fetchone()[0] if (mu and mu['hodour_at']) else 0
                except Exception:
                    _log.warning('detail_lettre (présents) : exception ignorée', exc_info=True)
                    f['nb_presents'] = 0
        finally:
            conn.close()

        # Les مراسلات المديرين الجهويّين déjà tirées : l'agent doit voir ce qui
        # est parti et sous quel عدد avant d'en demander une de plus.
        cfg = get_config()
        return render_template('lettres/detail.html', lettre=ltr,
                               formations=formations,
                               dr_lettres=get_dr_lettres(lettre_id),
                               destination_dr=identite.destination_dr(cfg),
                               jihat=noms_jihat(),
                               now_year=datetime.now().year)
