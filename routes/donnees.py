"""Données : exports Excel (v1.5 — D3, S1), copie de programme (P1),
التقرير السنوي (D1)."""
from datetime import datetime

from flask import request, redirect, url_for, flash, session, send_file, render_template

from core import exports, etats, graphiques, identite
from core.bareme_mali import formater_dinars
from core.arabe import MOIS_AR
from core.database import (
    get_mkowin, get_registre, annees_du_registre, annee_registre, get_dorrat_avec_memo,
    get_journal_filtre, journaliser, dupliquer_programme, get_lettre_detail,
    annees_rapport, rapport_annuel as _rapport_annuel, get_config,
)


def _envoyer(flux, nom):
    return send_file(flux, mimetype=exports.MIME_XLSX, as_attachment=True,
                     download_name=f'{nom}_{exports.horodatage()}.xlsx')


def register(app, ctx):
    login_required = ctx['login_required']
    admin_required = ctx['admin_required']

    # ─── D3 : exports ───────────────────────────────────────────────────────

    @app.route('/mkowin/exporter')
    @login_required
    def exporter_mkowin():
        liste = get_mkowin()
        journaliser(session.get('username'), 'تصدير قائمة الأسماء', 'Excel', f'{len(liste)} إسم')
        return _envoyer(exports.export_mkowin(liste), 'asmaa')

    @app.route('/registre/<type_lettre>/exporter')
    @login_required
    def exporter_registre(type_lettre):
        if type_lettre not in ('interne', 'externe'):
            type_lettre = 'interne'
        annee = request.args.get('annee', type=int)
        if annee not in annees_du_registre():
            annee = annee_registre()
        entrees = get_registre(type_lettre, annee)
        journaliser(session.get('username'), 'تصدير سجلّ المراسلات', type_lettre, str(annee))
        return _envoyer(exports.export_registre(entrees, type_lettre, annee),
                        f'sijil_{type_lettre}_{annee}')

    @app.route('/registre/<type_lettre>/pdf')
    @login_required
    def imprimer_registre(type_lettre):
        """v1.7 — السّجلّ السّنوي en PDF officiel (archivage papier)."""
        from io import BytesIO
        from core import pdf_registre, chemins
        from core.database import get_numeros_liberes, registre_lacunes
        if type_lettre not in ('interne', 'externe'):
            type_lettre = 'interne'
        annee = request.args.get('annee', type=int)
        if annee not in annees_du_registre():
            annee = annee_registre()
        chemin = pdf_registre.generer(
            get_registre(type_lettre, annee), type_lettre, annee, get_config(),
            ctx['BASE_DIR'],
            liberes=[r['numero'] for r in get_numeros_liberes(type_lettre, annee)],
            lacunes=registre_lacunes(type_lettre, annee),
            ouverte=(annee == annee_registre()))
        journaliser(session.get('username'), 'طباعة سجلّ المراسلات', type_lettre, str(annee))
        return send_file(BytesIO(chemins.lire_et_supprimer(chemin)), mimetype='application/pdf',
                         as_attachment=False, download_name=f'sijil_{type_lettre}_{annee}.pdf')

    @app.route('/programmes/exporter')
    @login_required
    def exporter_dorrat():
        dorrat = get_dorrat_avec_memo()
        for d in dorrat:
            d['etat'] = etats.etat_dorra(d)
            d['etat_fin'] = etats.etat_finances(d)
        journaliser(session.get('username'), 'تصدير الدورات التكوينية', 'Excel', f'{len(dorrat)} دورة')
        return _envoyer(exports.export_dorrat(dorrat), 'dorrat')

    @app.route('/journal/exporter')
    @admin_required
    def exporter_journal():
        entrees = get_journal_filtre(**_filtres_journal(), limite=20000)
        return _envoyer(exports.export_journal(entrees), 'journal')

    # ─── D1 : التقرير السنوي ─────────────────────────────────────────────────

    app.add_template_filter(lambda v: formater_dinars(v or 0), 'dinars')

    def _annee_choisie():
        annees = annees_rapport()
        a = request.args.get('annee', type=int)
        return (a if a in annees else annees[0]), annees

    @app.route('/statistiques/rapport-annuel')
    @login_required
    def rapport_annuel():
        annee, annees = _annee_choisie()
        r = _rapport_annuel(annee)
        libs = [m['mois'] for m in r['par_mois']]
        g_dorrat = graphiques.colonnes(libs, [m['dorrat'] for m in r['par_mois']], unite='دورة')
        g_montant = graphiques.colonnes(libs, [round(m['montant'], 3) for m in r['par_mois']],
                                        format_valeur=lambda v: formater_dinars(v), unite='د')
        return render_template('rapport_annuel.html', r=r, annees=annees,
                               g_dorrat=g_dorrat, g_montant=g_montant,
                               now_year=datetime.now().year)

    @app.route('/statistiques/rapport-annuel/exporter')
    @login_required
    def exporter_rapport_annuel():
        annee, _ = _annee_choisie()
        r = _rapport_annuel(annee)
        journaliser(session.get('username'), 'تصدير التقرير السنوي', 'Excel', str(annee))
        return _envoyer(exports.export_rapport(r, identite.nom_centre(get_config())),
                        f'taqrir_{annee}')

    # ─── P1 : نسخ برنامج ─────────────────────────────────────────────────────

    @app.route('/lettre/<int:lettre_id>/dupliquer', methods=['POST'])
    @login_required
    def dupliquer_lettre(lettre_id):
        mois = (request.form.get('mois') or '').strip()
        annee = request.form.get('annee', type=int)
        if mois not in MOIS_AR or not annee or not (2000 <= annee <= 2100):
            flash('يرجى اختيار شهر وسنة صحيحين للبرنامج الجديد', 'error')
            return redirect(request.referrer or url_for('liste_programmes'))
        source = get_lettre_detail(lettre_id)
        nouveau = dupliquer_programme(lettre_id, mois, annee)
        if not nouveau:
            flash('البرنامج المطلوب نسخه غير موجود', 'error')
            return redirect(url_for('liste_programmes'))
        ref = (source or {}).get('lettre', {}).get('ref_complet') or f'#{lettre_id}'
        journaliser(session.get('username'), 'نسخ برنامج تكوين', f'مراسلة #{nouveau}',
                    f'عن {ref} ← {mois} {annee}')
        flash(f'تمّ إنشاء نسخة من البرنامج لشهر {mois} {annee}. أدخل تواريخ الدورات ثمّ واصل كالمعتاد.',
              'success')
        return redirect(url_for('nouvelle_lettre', modifier=nouveau))


def _filtres_journal():
    """Filtres de /journal, lus dans la requête et nettoyés."""
    def _date(v):
        v = (v or '').strip()[:10]
        try:
            datetime.strptime(v, '%Y-%m-%d')
            return v
        except ValueError:
            return ''
    return {
        'utilisateur': (request.args.get('utilisateur') or '').strip()[:80],
        'du': _date(request.args.get('du')),
        'au': _date(request.args.get('au')),
        'q': (request.args.get('q') or '').strip()[:120],
    }
