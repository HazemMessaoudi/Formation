"""Toutes les routes qui composent et renvoient un PDF."""

from io import BytesIO

from core import chemins

from flask import request, jsonify, redirect, url_for, send_file, session, flash

from core.database import (
    programme_est_scelle,
    get_lettre_detail, get_config, attribuer_numero_dr, journaliser,
)
from core import identite, gel
from core import dossier_dorra
from core.pdf_generator import (generer_pdf, generer_pdf_libre, generer_pdf_participants,
                                generer_pdf_bataqa_hodour,
                                generer_pdf_directeur_regional, generer_pdf_bataqa,
                                generer_pdf_programme, generer_pdf_memo,
                                compter_pages_pdf)


def _flux(chemin):
    """v1.7 — le PDF est relu en mémoire et son fichier supprimé aussitôt :
    aucune copie de document officiel ne reste sur le disque."""
    return BytesIO(chemins.lire_et_supprimer(chemin))


def register(app, ctx):
    login_required = ctx['login_required']
    BASE_DIR = ctx['BASE_DIR']

    def _avec_pagination(generateur, donnees):
        """v1.6.1 — خانة Page toujours remplie : la مراسلة est composée une
        première fois pour compter ses pages RÉELLES, puis recomposée avec
        « n/n » dans l'en-tête (même convention que la مذكّرة)."""
        import os as _os
        donnees['pages'] = None
        provisoire = generateur(donnees, BASE_DIR)
        donnees['pages'] = compter_pages_pdf(provisoire) or 1
        final = generateur(donnees, BASE_DIR)
        if provisoire != final:
            try:
                _os.remove(provisoire)
            except OSError:
                pass
        return final

    @app.route('/lettre/libre/<int:lettre_id>/generer')
    @login_required
    def generer_lettre_libre(lettre_id):
        detail = get_lettre_detail(lettre_id)
        if not detail:
            return jsonify({'erreur': 'مراسلة غير موجودة'}), 404
        ltr         = detail['lettre']
        # 1.0 : un برنامج (ou une مراسلة d'une autre catégorie) n'est pas une
        # مراسلة حرّة — sans ce contrôle, l'adresse renvoyait une erreur 500.
        if (ltr.get('categorie') or 'programme') != 'libre':
            return redirect(url_for('detail_lettre', lettre_id=lettre_id))
        type_lettre = ltr['type']
        ref         = ltr['ref_complet']
        numero      = ltr['numero']
        if not ref:
            return redirect(url_for('detail_lettre', lettre_id=lettre_id))
        cfg = get_config()
        lettre_data = {
            'type':              type_lettre,
            'ref':               ref,
            'numero':            numero,
            'mois':              ltr['mois'],
            'annee':             ltr['annee'],
            'destinataire':      ltr.get('destinataire', ''),
            'objet':             ltr.get('objet', ''),
            'msahib':            ltr.get('msahib', '') or '',
            'corps':             ltr.get('corps') or '',
            'moujah_lahom':      ltr.get('moujah_lahom', '') or '',
            **gel.champs_pdf(cfg, lettre_id),
        }
        pdf_path = _avec_pagination(generer_pdf_libre, lettre_data)
        filename  = f"lettre_libre_{ref}.pdf"
        return send_file(_flux(pdf_path), mimetype='application/pdf',
                         as_attachment=False, download_name=filename)

    # ─── Génération PDF ──────────────────────────────────────────────────────

    @app.route('/lettre/<int:lettre_id>/generer', methods=['GET', 'POST'])
    @login_required
    def generer_lettre(lettre_id):
        detail = get_lettre_detail(lettre_id)
        if not detail:
            return jsonify({'erreur': 'برنامج غير موجود'}), 404

        ltr = detail['lettre']
        type_lettre = ltr['type']
        ref    = ltr['ref_complet']
        numero = ltr['numero']

        if not ref:
            return redirect(url_for('detail_lettre', lettre_id=lettre_id))

        cfg = get_config()
        lettre_data = {
            'type':             type_lettre,
            'ref':              ref,
            'numero':           numero,
            'mois':             ltr['mois'],
            'annee':            ltr['annee'],
            'formations':       detail['formations'],
            **gel.champs_pdf(cfg, lettre_id),
        }

        pdf_path = _avec_pagination(generer_pdf, lettre_data)
        filename = f"lettre_{ref}.pdf"
        return send_file(_flux(pdf_path), mimetype='application/pdf',
                         as_attachment=False, download_name=filename)

    @app.route('/lettre/<int:lettre_id>/formations/<int:formation_id>/participants/pdf')
    @login_required
    def generer_participants_pdf(lettre_id, formation_id):
        # v1.7 : données communes au PDF et au Word (core/dossier_dorra.py).
        # La قائمة النهائية respecte l'ordre militaire, quel que soit l'ordre de saisie.
        pdf_data = dossier_dorra.donnees_participants(lettre_id, formation_id)
        if not pdf_data:
            return jsonify({'erreur': 'الدورة غير موجودة'}), 404
        pdf_path = generer_pdf_participants(pdf_data, BASE_DIR)
        filename  = f"participants_{lettre_id}_{formation_id}.pdf"
        return send_file(_flux(pdf_path), mimetype='application/pdf',
                         as_attachment=False, download_name=filename)

    # ─── Génération PDF بطاقة الحضور (pièce autonome, hors numérotation) ──────

    @app.route('/lettre/<int:lettre_id>/formations/<int:formation_id>/hodour/pdf')
    @login_required
    def generer_hodour_pdf(lettre_id, formation_id):
        pdf_data = dossier_dorra.donnees_hodour(lettre_id, formation_id)
        if not pdf_data:
            return jsonify({'erreur': 'الدورة غير موجودة'}), 404
        pdf_path = generer_pdf_bataqa_hodour(pdf_data, BASE_DIR)
        filename  = f"hodour_{lettre_id}_{formation_id}.pdf"
        return send_file(_flux(pdf_path), mimetype='application/pdf',
                         as_attachment=False, download_name=filename)

    # ─── Génération PDF البطاقة البيداغوجية ──────────────────────────────────

    @app.route('/lettre/<int:lettre_id>/formations/<int:formation_id>/bataqa/pdf')
    @login_required
    def generer_bataqa_pdf(lettre_id, formation_id):
        # Données enregistrées (surcharges comprises)
        pdf_data = dossier_dorra.donnees_bataqa(lettre_id, formation_id)
        if not pdf_data:
            return jsonify({'erreur': 'غير موجود'}), 404
        pdf_path = generer_pdf_bataqa(pdf_data, BASE_DIR)
        filename = f"bataqa_{lettre_id}_{formation_id}.pdf"
        return send_file(_flux(pdf_path), mimetype='application/pdf',
                         as_attachment=False, download_name=filename)

    @app.route('/lettre/<int:lettre_id>/formations/<int:formation_id>/programme/pdf')
    @login_required
    def generer_programme_pdf(lettre_id, formation_id):
        pdf_data = dossier_dorra.donnees_programme(lettre_id, formation_id)
        if not pdf_data:
            return jsonify({'erreur': 'البرنامج غير مؤكد'}), 400
        pdf_path = generer_pdf_programme(pdf_data, BASE_DIR)
        filename = f"programme_{lettre_id}_{formation_id}.pdf"
        return send_file(_flux(pdf_path), mimetype='application/pdf',
                         as_attachment=False, download_name=filename)

    @app.route('/lettre/<int:lettre_id>/formations/<int:formation_id>/memo/pdf')
    @login_required
    def generer_memo_pdf(lettre_id, formation_id):
        pdf_data = dossier_dorra.donnees_memo(lettre_id, formation_id)
        if not pdf_data:
            return jsonify({'erreur': 'المذكرة غير مؤكّدة'}), 400
        # ── Nombre de feuillets du dossier (خانة Page) ───────────────────
        # Le dossier remis = المذكّرة + برنامج الدورة + القائمة الإسمية +
        # البطاقة البيداغوجية, comptés sur leurs PDF RÉELS ; jamais vide (1/1).
        pdf_data['pages'] = dossier_dorra.pages_du_dossier(lettre_id, formation_id,
                                                           pdf_data, BASE_DIR)
        pdf_path = generer_pdf_memo(pdf_data, BASE_DIR)
        filename = f"memo_{lettre_id}_{formation_id}.pdf"
        return send_file(_flux(pdf_path), mimetype='application/pdf',
                         as_attachment=False, download_name=filename)

    # ─── v1.7 : ملفّ الدورة كاملًا (ZIP de cinq pièces Word) ─────────────────

    @app.route('/lettre/<int:lettre_id>/formations/<int:formation_id>/dossier.zip')
    @login_required
    def telecharger_dossier_dorra(lettre_id, formation_id):
        from core import dossier_word
        detail = get_lettre_detail(lettre_id)
        formation = next((f for f in (detail or {}).get('formations', [])
                          if f['id'] == formation_id), None)
        if not formation:
            return jsonify({'erreur': 'الدورة غير موجودة'}), 404
        titre = (formation.get('titre') or '').strip()
        try:
            octets, absentes = dossier_word.archive_dorra(lettre_id, formation_id,
                                                          BASE_DIR, titre)
        except LookupError as e:
            flash(str(e), 'error')
            return redirect(request.referrer or url_for('detail_lettre', lettre_id=lettre_id))
        journaliser(session.get('username'), 'تحميل ملفّ الدورة (Word)',
                    f'دورة #{formation_id}',
                    'كامل' if not absentes else f'ناقص: {len(absentes)} وثيقة')
        # Nom lisible, sans caractères interdits sous Windows
        propre = ''.join(ch for ch in titre if ch not in '\\/:*?"<>|').strip()[:60]
        nom = f"ملف_الدورة_{formation.get('date_formation') or formation_id}"
        if propre:
            nom += '_' + propre.replace(' ', '_')
        return send_file(BytesIO(octets), mimetype='application/zip', as_attachment=True,
                         download_name=nom + '.zip')

    # ─── v1.7 : شهادات المشاركة (présents de ورقة الحضور) ─────────────────────

    @app.route('/lettre/<int:lettre_id>/formations/<int:formation_id>/shahadat/pdf')
    @login_required
    def generer_shahadat_pdf(lettre_id, formation_id):
        from core import pdf_shahadat
        pid = request.args.get('participant', type=int)
        donnees, presents = dossier_dorra.donnees_shahadat(lettre_id, formation_id, pid)
        if donnees is None:
            flash(presents, 'error')
            return redirect(request.referrer or url_for('detail_lettre', lettre_id=lettre_id))
        chemin = pdf_shahadat.generer(donnees, presents, BASE_DIR)
        journaliser(session.get('username'), 'طباعة شهادات المشاركة', f'دورة #{formation_id}',
                    f'{len(presents)} شهادة')
        return send_file(_flux(chemin), mimetype='application/pdf', as_attachment=False,
                         download_name=f'shahadat_{lettre_id}_{formation_id}.pdf')

    # ─── Génération PDF directeur régional (étape 2) ──────────────────────────

    @app.route('/lettre/<int:lettre_id>/generer-directeur-regional')
    @login_required
    def generer_lettre_directeur_regional(lettre_id):
        detail = get_lettre_detail(lettre_id)
        if not detail:
            return jsonify({'erreur': 'غير موجود'}), 404
        ltr = detail['lettre']
        cfg = get_config()

        # La destination par défaut vient des paramètres du centre : chaque
        # centre dépend d'une direction régionale différente. Elle est prise au
        # gel du برنامج : une مراسلة réimprimée garde la جهة qu'elle portait.
        destination = (request.args.get('destination') or '').strip() \
            or gel.champs_pdf(cfg, lettre_id).get('destination_dr') \
            or identite.destination_dr(cfg)
        # Type de correspondance choisi par l'utilisateur pour CETTE destination.
        # Défaut métier de l'étape 2 : مراسلة خارجية.
        type_mr = request.args.get('type_mr', '').strip()
        if type_mr not in ('interne', 'externe'):
            type_mr = 'externe'

        # ── Numéro d'enregistrement PROPRE à la مراسلة المدير الجهوي ─────────
        # Pris dans la série du type choisi (داخلية ou خارجية) : c'est une
        # correspondance distincte de celle du programme et elle ne doit JAMAIS
        # emprunter son numéro. Attribué une seule fois ; réimprimer ne
        # consomme aucun numéro supplémentaire.
        dr_ref, dr_num, dr_type, deja = attribuer_numero_dr(lettre_id, type_mr, destination)
        if not dr_ref:
            # Programme non confirmé, ou déjà scellé → aucun numéro ne peut être tiré.
            if programme_est_scelle(lettre_id):
                flash('البرنامج مصادق عليه نهائيًّا: لا يمكن ترقيم مراسلة جديدة لجهة أخرى.', 'error')
            return redirect(url_for('detail_lettre', lettre_id=lettre_id))
        if not deja:
            journaliser(session.get('username'), 'ترقيم مراسلة المدير الجهوي',
                        f'مراسلة #{lettre_id}',
                        f"{dr_ref} ({'خارجية' if dr_type == 'externe' else 'داخلية'})")

        lettre_data = {
            'type':              dr_type,
            'ref':               dr_ref,
            'numero':            dr_num,
            'mois':              ltr['mois'],
            'annee':             ltr['annee'],
            'formations':        detail['formations'],
            **gel.champs_pdf(cfg, lettre_id),
            'destination':       destination,
        }
        pdf_path = _avec_pagination(generer_pdf_directeur_regional, lettre_data)
        filename  = f"directeur_regional_{dr_ref}.pdf"
        return send_file(_flux(pdf_path), mimetype='application/pdf',
                         as_attachment=False, download_name=filename)
