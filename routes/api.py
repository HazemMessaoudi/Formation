# -*- coding: utf-8 -*-
"""Points d'entrée JSON : grades, lieux, utilisateurs et brouillons.

Les noms de fonctions sont identiques à ceux d'origine : les endpoints utilisés
par url_for() dans les gabarits restent inchangés.
"""
from flask import request, jsonify, session

from core.database import (
    get_grades, add_grade,
    get_lieux, add_lieu, delete_lieu,
    get_users, add_user, update_user_password, delete_user,
    get_connection, get_programmes_inacheves, dorrat_meme_jour,
    rechercher_mkowin, journaliser, nb_admins, changer_role, remettre_a_zero_echecs,
    suggestions_programme, get_mkowin,
)


def register(app, ctx):
    login_required = ctx['login_required']
    admin_required = ctx['admin_required']

    @app.route('/api/grades', methods=['GET'])
    @login_required
    def api_grades():
        return jsonify(get_grades())

    @app.route('/api/grades', methods=['POST'])
    @login_required
    def api_add_grade():
        data = request.get_json(silent=True) or {}
        nom = data.get('nom', '').strip()
        if not nom:
            return jsonify({'erreur': 'الاسم فارغ'}), 400
        ok = add_grade(nom)
        if ok:
            return jsonify({'succes': True, 'nom': nom})
        return jsonify({'erreur': 'خطأ في الحفظ'}), 500

    @app.route('/api/grades/supprimer', methods=['POST'])
    @login_required
    def supprimer_grade():
        data = request.get_json(silent=True) or {}
        nom = data.get('nom', '').strip()
        if not nom:
            return jsonify({'erreur': 'الاسم فارغ'}), 400
        conn = get_connection()
        conn.execute('DELETE FROM grades WHERE nom = ?', (nom,))
        conn.commit()
        conn.close()
        return jsonify({'succes': True})

    @app.route('/api/lieux', methods=['GET'])
    @login_required
    def api_lieux():
        return jsonify(get_lieux())

    @app.route('/api/lieux', methods=['POST'])
    @login_required
    def api_add_lieu():
        data = request.get_json(silent=True) or {}
        nom = data.get('nom', '').strip()
        if not nom:
            return jsonify({'erreur': 'الاسم فارغ'}), 400
        ok = add_lieu(nom)
        return jsonify({'succes': ok})

    @app.route('/api/lieux/supprimer', methods=['POST'])
    @login_required
    def api_supprimer_lieu():
        data = request.get_json(silent=True) or {}
        nom = data.get('nom', '').strip()
        delete_lieu(nom)
        return jsonify({'succes': True})

    @app.route('/api/users', methods=['GET'])
    @login_required
    def api_get_users():
        return jsonify(get_users())

    @app.route('/api/users', methods=['POST'])
    @admin_required
    def api_add_user():
        data = request.get_json(silent=True) or {}
        username = data.get('username', '').strip()
        password = data.get('password', '').strip()
        if not username or not password:
            return jsonify({'erreur': 'اسم المستخدم وكلمة المرور مطلوبان'}), 400
        if len(password) < 6:
            return jsonify({'erreur': 'كلمة المرور يجب أن تتكوّن من 6 رموز على الأقلّ'}), 400
        role = 'admin' if data.get('role') == 'admin' else 'user'
        if role == 'admin' and len(password) < 8:
            return jsonify({'erreur': 'كلمة مرور المشرف العام يجب أن تتكوّن من 8 رموز على الأقلّ'}), 400
        if add_user(username, password, role):
            journaliser(session.get('username'), 'إضافة مستخدم', username,
                        'مشرف عام' if role == 'admin' else 'مستعمل')
            return jsonify({'succes': True})
        return jsonify({'erreur': 'اسم المستخدم موجود مسبقاً'}), 400

    @app.route('/api/users/role', methods=['POST'])
    @admin_required
    def api_changer_role():
        """v1.7 — مشرف ثانٍ : le مشرف عام peut élever un مستعمل au rang de
        مشرف عام, ou l'y retirer — jamais le sien, jamais le dernier."""
        data = request.get_json(silent=True) or {}
        username = (data.get('username') or '').strip()
        role = 'admin' if data.get('role') == 'admin' else 'user'
        if not username:
            return jsonify({'erreur': 'اسم المستخدم مطلوب'}), 400
        ok, msg = changer_role(username, role, session.get('username'))
        if not ok:
            return jsonify({'erreur': msg}), 400
        journaliser(session.get('username'), 'تغيير دور مستخدم', username,
                    'مشرف عام' if role == 'admin' else 'مستعمل')
        return jsonify({'succes': True})

    @app.route('/api/users/changer-mdp', methods=['POST'])
    @admin_required
    def api_change_password():
        """Réinitialisation du mot de passe d'un compte PAR LE مشرف عام.

        v1.4e : cette route n'exigeait qu'une connexion — n'importe quel
        مستعمل pouvait redéfinir le mot de passe du مشرف عام et prendre son
        compte. Un مستعمل change le SIEN par /changer-mot-de-passe, qui exige
        l'actuel. Un mot de passe posé ici par l'administrateur est provisoire :
        son titulaire devra le changer à la prochaine connexion."""
        data = request.get_json(silent=True) or {}
        username = (data.get('username') or '').strip()
        new_password = (data.get('new_password') or '').strip()
        if not username or not new_password:
            return jsonify({'erreur': 'بيانات ناقصة'}), 400
        if len(new_password) < 6:
            return jsonify({'erreur': 'كلمة المرور يجب أن تتكوّن من 6 رموز على الأقلّ'}), 400
        comptes = {u['username']: u for u in get_users()}
        if username not in comptes:
            return jsonify({'erreur': 'المستخدم غير موجود'}), 404
        if comptes[username].get('role') == 'admin' and len(new_password) < 8:
            return jsonify({'erreur': 'كلمة مرور المشرف العام يجب أن تتكوّن من 8 رموز على الأقلّ'}), 400
        if not update_user_password(username, new_password):
            return jsonify({'erreur': 'خطأ في تحديث كلمة المرور'}), 500
        remettre_a_zero_echecs(username)      # v1.7 : lève un éventuel blocage
        if username != session.get('username'):
            conn = get_connection()
            try:
                conn.execute('UPDATE users SET doit_changer_mdp=1 WHERE username=?', (username,))
                conn.commit()
            finally:
                conn.close()
        journaliser(session.get('username'), 'إعادة تعيين كلمة مرور', username, '')
        return jsonify({'succes': True})

    @app.route('/api/users/supprimer', methods=['POST'])
    @admin_required
    def api_delete_user():
        data = request.get_json(silent=True) or {}
        username = data.get('username', '').strip()
        if not username:
            return jsonify({'erreur': 'اسم المستخدم مطلوب'}), 400
        if username == session.get('username'):
            return jsonify({'erreur': 'لا يمكنك حذف حسابك الحالي'}), 400
        remaining = get_users()
        if len(remaining) <= 1:
            return jsonify({'erreur': 'يجب الإبقاء على مستخدم واحد على الأقل'}), 400
        cible = next((u for u in remaining if u['username'] == username), None)
        if cible and cible.get('role') == 'admin' and nb_admins() <= 1:
            return jsonify({'erreur': 'يجب الإبقاء على مشرف عام واحد على الأقلّ'}), 400
        if delete_user(username):
            journaliser(session.get('username'), 'حذف مستخدم', username, '')
            return jsonify({'succes': True})
        return jsonify({'erreur': 'خطأ في الحذف'}), 500

    @app.route('/api/drafts', methods=['GET'])
    @login_required
    def api_drafts():
        """Programmes de formation non encore achevés (à reprendre)."""
        drafts = [
            {
                'lettre_id':     r['id'],
                'mois':          r['mois'],
                'annee':         r['annee'],
                'type':          r['type'],
                'date_creation': r['date_creation'],
                'nb_formations': r['nb_formations'] or 0,
                'titres':        r['titres'] or '',
            }
            for r in get_programmes_inacheves()
        ]
        return jsonify({'drafts': drafts})

    @app.route('/api/programme/suggestions')
    @login_required
    def api_programme_suggestions():
        """v1.7.1 — Propositions pour le برنامج الدورة :
        « activites » : بيان النشاط déjà saisis (les plus utilisés d'abord) ;
        « intervenants » : المتدخّلون déjà saisis, puis toutes les fiches
        (الرتبة + الاسم واللقب), sans doublon."""
        intervenants = suggestions_programme('intervenant')
        vus = set(intervenants)
        for m in get_mkowin():
            nom = ' '.join(x for x in ((m.get('grade') or '').strip(),
                                       (m.get('nom') or '').strip(),
                                       (m.get('prenom') or '').strip()) if x)
            if nom and nom not in vus:
                vus.add(nom)
                intervenants.append(nom)
        return jsonify({'activites': suggestions_programme('activite'),
                        'intervenants': intervenants})

    @app.route('/api/mkowin/recherche')
    @login_required
    def api_mkowin_recherche():
        """Autocomplétion المكوّن / المشاركون : ?q=<texte>[&limite=40].
        Ne renvoie que les champs utiles à la saisie (CHAMPS_MKOW_PUBLICS)."""
        return jsonify(rechercher_mkowin(request.args.get('q', ''),
                                         request.args.get('limite', 40)))

    @app.route('/api/dorrat/meme-jour')
    @login_required
    def api_dorrat_meme_jour():
        """Dorrat déjà programmées le même jour — alerte avant de valider une
        nouvelle دورة à cette date."""
        date_f  = (request.args.get('date') or '').strip()
        exclure = request.args.get('lettre_id', type=int)
        dorrat = dorrat_meme_jour(date_f, exclure)
        return jsonify({
            'date': date_f,
            'nombre': len(dorrat),
            'dorrat': [
                {
                    'titre':          d.get('titre') or '',
                    'lieu_formation': d.get('lieu_formation') or '',
                    'periode':        d.get('periode') or '',
                    'nom_formateur':  d.get('nom_formateur') or '',
                    'ref':            d.get('ref_complet') or '',
                }
                for d in dorrat
            ],
        })
