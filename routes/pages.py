"""Pages principales : accueil, tableau de bord, paramètres, journal, listes."""
import logging as _logging

from core import etats
from core.securite import delai_inactivite

from datetime import datetime

from flask import render_template, request, redirect, url_for, flash, session

from core import identite
from core.database import (
    get_stats, get_journal, get_config, get_grades, get_lieux, update_config,
    get_users, get_dorrat_avec_memo, get_programmes_inacheves, get_lettres_libres,
    get_registre, registre_lacunes, get_numeros_liberes,
    journaliser, annee_registre, annees_du_registre, get_stats_avancees,
)


_log = _logging.getLogger('formation.' + __name__)


def _cachet_present():
    """v1.7 — une image de ختم est-elle disponible (data/ ou static/images/) ?"""
    import os
    from core import chemins
    return any(os.path.exists(p) for p in (
        os.path.join(chemins.dossier_donnees(), 'cachet.png'),
        os.path.join(chemins.dossier_ressources(), 'static', 'images', 'cachet.png')))


def _miroir_etat():
    """V3.1 — état de la نسخة المرآة et des archives pour la page الإعدادات."""
    from core import miroir
    try:
        e = miroir.etat()
        e['copies'] = miroir.copies_disponibles(avec_sauvegardes=False)
        return e
    except Exception:
        _log.warning('_miroir_etat : exception ignorée', exc_info=True)
        return None


def register(app, ctx):
    login_required = ctx['login_required']
    admin_required = ctx['admin_required']
    BASE_DIR = ctx['BASE_DIR']

    @app.route('/journal')
    @admin_required
    def page_journal():
        # S1 (v1.5) : filtres par utilisateur, période et texte, côté serveur
        # — la recherche porte sur TOUT le journal, pas sur les 300 dernières.
        from routes.donnees import _filtres_journal
        from core.database import get_journal_filtre, utilisateurs_du_journal
        filtres = _filtres_journal()
        actif = any(filtres.values())
        entrees = get_journal_filtre(**filtres, limite=1000 if actif else 300)
        return render_template('journal.html', entrees=entrees, filtres=filtres,
                               filtre_actif=actif, utilisateurs=utilisateurs_du_journal(),
                               now_year=datetime.now().year)

    # ─── Pages principales ───────────────────────────────────────────────────

    @app.route('/')
    @login_required
    def index():
        # v1.0 — la منظومة ne s'ouvre plus sur لوحة القيادة mais sur la شاشة
        # رئيسية à trois portes : برامج تكوينية / مستحقات مالية / إحصائيات.
        # لوحة القيادة reste ce qu'elle était, derrière la première porte.
        return redirect(url_for('accueil'))

    # ─── لوحة القيادة ─────────────────────────────────────────────────────────

    @app.route('/dashboard')
    @login_required
    def dashboard():
        # D2 (v1.5) : ce qui demande l'attention, les دورات à venir, l'activité
        # de l'année (graphique + tableau) et, pour le مشرف, les dernières opérations.
        from core.database import donnees_tableau_de_bord
        from core import graphiques
        stats = get_stats()
        tb = donnees_tableau_de_bord()
        graphe = graphiques.colonnes([m['mois'] for m in tb['par_mois']],
                                     [m['dorrat'] for m in tb['par_mois']], unite='دورة')
        activite = get_journal(6) if session.get('role') == 'admin' else []
        # v1.7 : rappel de copie externe (مشرف عام seulement)
        from core.database import etat_sauvegarde_externe
        sauv_ext = etat_sauvegarde_externe(get_config()) if session.get('role') == 'admin' else None
        return render_template('dashboard.html', stats=stats, tb=tb, graphe=graphe,
                               activite=activite, now_year=datetime.now().year,
                               sauv_ext=sauv_ext)

    # ─── V3.2 — دليل الاستعمال ──────────────────────────────────────────────────
    @app.route('/dalil')
    @login_required
    def guide():
        from core import guide as _guide
        return render_template('guide.html', sommaire=_guide.sommaire(),
                               recherche={f['id']: _guide.texte_recherche(f) for f in _guide.FICHES},
                               titres={f['id']: f['titre'] for f in _guide.FICHES})

    # ─── التّعريف بالبرنامج ────────────────────────────────────────────────────
    @app.route('/tarif')
    @login_required
    def apropos():
        # La page s'ouvre sur les chiffres RÉELS du centre : on lit l'histoire
        # de sa propre منظومة, pas un mode d'emploi générique.
        try:
            s = get_stats_avancees()
        except Exception:
            s = {}
        chiffres = {
            'programmes':   s.get('programmes', 0),
            'dorrat':       s.get('dorrat', 0),
            'participants': s.get('participants_uniques', 0),
            'mawad':        s.get('mawad', 0),
        }
        return render_template('apropos.html', chiffres=chiffres,
                               now_year=datetime.now().year)

    # ─── إعدادات ─────────────────────────────────────────────────────────────

    @app.route('/parametres', methods=['GET', 'POST'])
    @login_required
    def parametres():
        config = get_config()
        grades = get_grades()
        lieux  = get_lieux()
        if request.method == 'POST':
            # v1.4e : ces clés sont l'IDENTITÉ du centre (nom, signataire,
            # بادئة المرجع…) — les mêmes que /parametres/centre, réservée au
            # مشرف عام. Un مستعمل pouvait les réécrire par ici.
            if session.get('role') != 'admin':
                flash('تعديل إعدادات المراسلات من مشمولات المشرف العام', 'error')
                return redirect(url_for('parametres'))
            # On n'enregistre QUE les champs réellement postés : un gabarit qui
            # n'affiche pas encore une clé ne doit jamais l'effacer.
            # La liste des clés vit dans core/identite.py (source unique).
            for _k in identite.CLES_EDITABLES:
                if _k in request.form:
                    update_config(_k, request.form.get(_k, '').strip())
            journaliser(session.get('username'), 'تعديل الإعدادات', 'config', '')
            flash('تم حفظ الإعدادات بنجاح', 'success')
            return redirect(url_for('parametres'))
        users = get_users()
        from routes.securite import etat_sauvegardes
        from core.database import lecteurs_amovibles, etat_sauvegarde_externe
        _sauv = etat_sauvegardes()
        # Police réellement utilisée pour composer les PDF (doit être « Arial »)
        from core.pdf_generator import _register_fonts, POLICE_ACTIVE
        _register_fonts(BASE_DIR)
        return render_template('parametres.html', config=config, grades=grades,
                               lieux=lieux, users=users, current_user=session.get('username'),
                               police=POLICE_ACTIVE,
                               delai_inactivite_regle=delai_inactivite(config),
                               sauvegardes_nb=_sauv[0], sauvegardes_derniere=_sauv[1],
                               lecteurs=lecteurs_amovibles() if session.get('role') == 'admin' else [],
                               sauv_ext=etat_sauvegarde_externe(config),
                               # V3.1 — نسخة مرآة, أرشيف سنوي
                               miroir_etat=_miroir_etat() if session.get('role') == 'admin' else None,
                               cachet_present=_cachet_present(),
                               now_year=datetime.now().year)

    # ─── هويّة المركز ────────────────────────────────────────────────────────
    #
    # Page ajoutée en v58 (diffusion multi-centres). Elle regroupe TOUT ce qui
    # distingue un centre d'un autre : ce sont exactement les valeurs qui
    # étaient écrites en dur dans le code avant cette version.

    @app.route('/parametres/centre', methods=['GET', 'POST'])
    @admin_required
    def parametres_centre():
        if request.method == 'POST':
            for _k in identite.CLES_EDITABLES:
                if _k in request.form:
                    update_config(_k, request.form.get(_k, '').strip())
            # Une identité renseignée vaut installation terminée.
            if (request.form.get('nom_centre', '').strip()
                    and request.form.get('nom_responsable', '').strip()):
                update_config('installation_faite', '1')
            journaliser(session.get('username'), 'تعديل هويّة المركز', 'config', '')
            flash('تم حفظ هويّة المركز بنجاح', 'success')
            return redirect(url_for('parametres_centre'))
        return render_template('parametres_centre.html',
                               config=identite.fusionner(get_config()),
                               now_year=datetime.now().year)

    # ─── الإطلاع على المراسلات ─────────────────────────────────────────────

    @app.route('/lettres')
    @login_required
    def liste_lettres():
        """Combined view — kept for backward compatibility (redirects to programmes)."""
        return redirect(url_for('liste_programmes'))

    @app.route('/programmes')
    @login_required
    def liste_programmes():
        # « الإطلاع على البرامج » : liste des DORRAT dont la مذكرة داخلية est
        # confirmée — une ligne par dorra, avec toutes ses données et ses documents.
        dorrat = get_dorrat_avec_memo()
        for d in dorrat:
            d['etat'] = etats.etat_dorra(d)
            d['etat_fin'] = etats.etat_finances(d)
        from core.arabe import MOIS_AR
        _auj = datetime.now()
        return render_template('lettres/liste_programmes.html', dorrat=dorrat,
                               mois_ar=MOIS_AR, mois_suivant=_auj.month % 12 + 1,
                               annee_suivante=_auj.year + (1 if _auj.month == 12 else 0),
                               now_year=datetime.now().year)

    @app.route('/formations-en-cours')
    @login_required
    def formations_en_cours():
        programmes = get_programmes_inacheves()
        for pr in programmes:
            pr['etats'] = etats.etats_programme(pr)
            pr['en_retard'] = etats.programme_en_retard(pr)
        return render_template('lettres/formations_en_cours.html',
                               programmes=programmes,
                               now_year=datetime.now().year)

    # ─── سجل المراسلات (داخلية / خارجية) ─────────────────────────────────────

    @app.route('/registre')
    @app.route('/registre/<type_lettre>')
    @login_required
    def registre_lettres(type_lettre='interne'):
        """Registre officiel des numéros d'enregistrement. Une série par type ;
        TOUTES les sources y figurent (برنامج تكوين، مراسلة حرة، مراسلة المدير
        الجهوي، مذكّرة) puisqu'elles consomment toutes le même compteur."""
        if type_lettre not in ('interne', 'externe'):
            type_lettre = 'interne'
        # Un سجلّ est annuel. Celui de l'année ouverte s'affiche par défaut ;
        # ceux des années écoulées se consultent et s'impriment, sans plus
        # jamais changer — c'est leur raison d'être.
        annees = annees_du_registre()
        ouverte = annee_registre()
        annee = request.args.get('annee', type=int)
        if annee not in annees:
            annee = ouverte
        return render_template('lettres/registre.html',
                               type_lettre=type_lettre,
                               entrees=get_registre(type_lettre, annee),
                               lacunes=registre_lacunes(type_lettre, annee),
                               liberes=get_numeros_liberes(type_lettre, annee),
                               annee=annee, annees=annees, annee_ouverte=ouverte,
                               now_year=datetime.now().year)

    @app.route('/lettres-libres')
    @login_required
    def liste_lettres_libres():
        lettres = get_lettres_libres()
        return render_template('lettres/liste_libres.html', lettres=lettres, now_year=datetime.now().year)
