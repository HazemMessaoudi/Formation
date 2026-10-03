# -*- coding: utf-8 -*-
"""توريد المكوّنين من ملفّ إكسال — الصّفحة والتّقرير.

La page ne fait que trois choses : lire, montrer, écrire — dans cet ordre,
et la troisième seulement si l'agent l'a demandée. Le mode «تجربة» est actif
par défaut : on regarde d'abord ce qui se passerait, on décide ensuite. Une
liste de deux cents agents ne se verse pas dans une قائمة sur un clic.
"""

from datetime import datetime
from io import BytesIO

from flask import (render_template, request, flash,
                   send_file, session)

from core import importation
from core.database import get_mkowin, add_mkow, update_mkow, noms_jihat, journaliser

#: Un tableau d'agents pèse quelques dizaines de kilooctets. Au-delà de huit
#: mégaoctets ce n'est plus un tableau : on refuse avant de charger.
TAILLE_MAX = 8 * 1024 * 1024


def register(app, ctx):
    admin_required = ctx['admin_required']

    @app.route('/mkowin/importer', methods=['GET', 'POST'])
    @admin_required
    def importer_mkowin():
        contexte = dict(colonnes=importation.COLONNES,
                        modele=importation.COLONNES_MODELE,
                        max_lignes=importation.MAX_LIGNES,
                        fenetre=importation.FENETRE_ENTETE,
                        now_year=datetime.now().year,
                        rapport=None,
                        essai=True,
                        sans_id=False,
                        # v1.7.1 : استكمال proposé par défaut (ne remplit que le vide)
                        completer=True)

        if request.method != 'POST':
            return render_template('importation.html', **contexte)

        essai     = request.form.get('essai') == '1'
        sans_id   = request.form.get('sans_identifiant') == '1'
        completer = request.form.get('completer') == '1'
        contexte.update(essai=essai, sans_id=sans_id, completer=completer)

        fichier = request.files.get('fichier')
        if not fichier or not fichier.filename:
            flash('يرجى اختيار ملفّ', 'error')
            return render_template('importation.html', **contexte)

        octets = fichier.read(TAILLE_MAX + 1)
        if len(octets) > TAILLE_MAX:
            flash('الملفّ أكبر ممّا يُقبل (8 ميغا أكثر من كافٍ لقائمة أعوان).', 'error')
            return render_template('importation.html', **contexte)

        try:
            plan = importation.analyser(
                BytesIO(octets), get_mkowin(),
                accepter_sans_identifiant=sans_id,
                completer_existantes=completer)
        except importation.ErreurImportation as err:
            flash(str(err), 'error')
            return render_template('importation.html', **contexte)

        rapport = dict(plan)
        rapport['fichier'] = fichier.filename
        rapport['essai'] = essai
        rapport['ajoutes'] = 0
        rapport['completes'] = 0
        rapport['echecs'] = []

        if not essai:
            for numero, fiche in plan['a_ajouter']:
                if add_mkow(fiche):
                    rapport['ajoutes'] += 1
                else:
                    rapport['echecs'].append(
                        {'ligne': numero,
                         'nom': ' '.join(x for x in (fiche.get('nom', ''),
                                                     fiche.get('prenom', '')) if x),
                         'identifiant': fiche.get('identifiant_unique', ''),
                         'motif': 'تعذّر الحفظ في القائمة'})
            for numero, mkow_id, partiel in plan['a_completer']:
                if update_mkow(mkow_id, partiel):
                    rapport['completes'] += 1
                else:
                    rapport['echecs'].append(
                        {'ligne': numero, 'nom': '', 'identifiant': '',
                         'motif': 'تعذّر التّحيين'})
            journaliser(session.get('username'), 'توريد مكوّنين من ملفّ إكسال',
                        fichier.filename,
                        f"أُضيف {rapport['ajoutes']}، استُكمل {rapport['completes']}، "
                        f"رُفض {len(plan['rejetes'])}")
            app.logger.info('Importation %s : +%s, ~%s, -%s',
                            fichier.filename, rapport['ajoutes'],
                            rapport['completes'], len(plan['rejetes']))

        contexte['rapport'] = rapport
        return render_template('importation.html', **contexte)

    @app.route('/mkowin/importer/namouthaj')
    @admin_required
    def modele_importation():
        """Le نموذج à remplir : les عناوين exactes que la منظومة reconnaît."""
        jihat = noms_jihat()
        exemple = ['77001', 'عريف', 'زياد', 'البوهلالي',
                   'ميناء بنزرت', jihat[0] if jihat else '', '20 000 000']
        flux = importation.construire_modele([exemple])
        return send_file(
            flux, as_attachment=True, download_name='namouthaj_mkowin.xlsx',
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
