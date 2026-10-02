# -*- coding: utf-8 -*-
"""معالج التّنصيب — يُطرح مرّة واحدة عند أوّل تشغيل (الإصدار 58).

قبل هذا الإصدار كانت المنظومة مفصّلة على مركز واحد: اسمه ورئيسه ومديره
الجهوي مكتوبة في الشّيفرة. صار كلّ ذلك معطى يُسأل عنه المستعمل هنا.

مبدآن يحكمان هذا الملفّ:

  1. لا تُحفظ إلّا خانات الخطوة المعروضة. خطوة لا تعرض مفتاحا لا يمكنها
     أبدا أن تمحوه — القاعدة نفسها المعتمدة في /parametres.

  2. الجواب يُحفظ فور تقديمه، لا عند نهاية المعالج. انقطاع الكهرباء في
     منتصف التّنصيب لا يُضيع ما أُدخل؛ يُستأنف المعالج من حيث توقّف.

`installation_faite` لا يُضبط إلّا بعد عرض ملخّص كامل ومصادقة المستعمل
عليه: ما دام لم يُضبط، تُوجّه كلّ الصّفحات إلى هنا (الحارس في app.py).
"""

from datetime import datetime

from flask import render_template, request, redirect, url_for, flash, session

from core import identite
from core.database import (
    get_config, update_config, journaliser,
    definir_numero_depart, prochain_numero_prevu, plancher_numero,
    semer_jihat,
)


def register(app, ctx):
    login_required = ctx['login_required']

    def _est_admin():
        return session.get('role') == 'admin'

    def _etapes_visibles():
        return list(identite.ETAPES_INSTALLATION)

    def _enrichir_etape(etape, cfg):
        """Enrichit les champs 'select' avec options_liste = prédéfinies + extras."""
        etape2 = dict(etape)
        champs2 = []
        for c in etape.get('champs', ()):
            c2 = dict(c)
            if c.get('type_champ') == 'select':
                opts = list(c.get('options', []))
                key_extras = c.get('key_extras')
                if key_extras:
                    extras_str = (cfg or {}).get(key_extras, '')
                    if extras_str:
                        for e in extras_str.split('|'):
                            e = e.strip()
                            if e and e not in opts:
                                opts.append(e)
                c2['options_liste'] = opts
            champs2.append(c2)
        etape2['champs'] = champs2
        return etape2

    def _rendre(etape, valeurs, erreurs=(), cfg=None):
        if cfg is None:
            cfg = get_config()
        etape_enrichi = _enrichir_etape(etape, cfg)
        visibles = _etapes_visibles()
        numeros_vis = [e['numero'] for e in visibles]
        try:
            idx = numeros_vis.index(etape['numero'])
        except ValueError:
            idx = 0
        rang_affiche = idx + 1
        numero_precedent = numeros_vis[idx - 1] if idx > 0 else None
        return render_template(
            'installation.html',
            etape=etape_enrichi,
            valeurs=valeurs,
            erreurs=list(erreurs),
            nb_etapes=len(visibles),
            rang_affiche=rang_affiche,
            numero_precedent=numero_precedent,
            now_year=datetime.now().year,
        )

    # ─── نقطة الدّخول ────────────────────────────────────────────────────────

    @app.route('/installation')
    @login_required
    def installation():
        return redirect(url_for('installation_etape', numero=1))

    # ─── خطوة من خطوات المعالج ───────────────────────────────────────────────

    @app.route('/installation/<int:numero>', methods=['GET', 'POST'])
    @login_required
    def installation_etape(numero):
        cfg = get_config()
        if identite.installation_faite(cfg):
            # التّنصيب منجز: لا يُعاد المعالج، وتُعدَّل الهويّة من صفحتها.
            return redirect(url_for('parametres_centre')) if _est_admin() \
                else redirect(url_for('accueil'))
        if not _est_admin():
            return render_template('installation_attente.html',
                                   now_year=datetime.now().year)

        etape = identite.etape_installation(numero)
        if etape is None:
            return redirect(url_for('installation_etape', numero=1))

        type_etape = etape.get('type', '')
        numeros = type_etape == 'numeros'
        code_centre = type_etape == 'code_centre'

        if request.method == 'POST':
            if code_centre:
                # رمز المركز: END-3-XX-XX
                part1 = (request.form.get('_code_part1', '') or '').strip().zfill(2)
                part2 = (request.form.get('_code_part2', '') or '').strip().zfill(2)
                valeurs = {'ref_prefix': f'END-3-{part1}-{part2}',
                           '_code_part1': part1, '_code_part2': part2}
                erreurs = []
                if not part1.strip('0') or not part2.strip('0'):
                    erreurs.append('رمز المركز وجوبي: أدخل الجزأين الأخيرين (مثال: 01-02)')
                if not erreurs:
                    update_config('ref_prefix', valeurs['ref_prefix'])

            elif numeros:
                valeurs = {c['cle']: (request.form.get(c['cle'], '') or '').strip()
                           for c in etape['champs']}
                erreurs = [f'خانة «{lbl}» وجوبيّة'
                           for lbl in identite.champs_obligatoires_manquants(etape, valeurs)]
                if not erreurs:
                    # الأعداد ليست إعدادات: تُضبط في عدّادات السّلسلتين.
                    for cle, serie in (('numero_depart_interne', 'interne'),
                                       ('numero_depart_externe', 'externe')):
                        try:
                            definir_numero_depart(serie, valeurs[cle])
                        except ValueError as e:
                            erreurs.append(str(e))

            else:
                # خانات عادية: نصّ أو قائمة منسدلة مع إمكانية الإضافة
                valeurs = {}
                for c in etape['champs']:
                    cle = c['cle']
                    extra = (request.form.get(f'_extra_{cle}', '') or '').strip()
                    if extra:
                        # المستعمل أضاف عنصرا جديدا
                        valeurs[cle] = extra
                        key_extras = c.get('key_extras')
                        if key_extras:
                            ancien = (cfg or {}).get(key_extras, '')
                            deja = [x.strip() for x in ancien.split('|') if x.strip()] \
                                   if ancien else []
                            if extra not in deja:
                                deja.append(extra)
                            update_config(key_extras, '|'.join(deja))
                    else:
                        valeurs[cle] = (request.form.get(cle, '') or '').strip()
                erreurs = [f'خانة «{lbl}» وجوبيّة'
                           for lbl in identite.champs_obligatoires_manquants(etape, valeurs)]
                if not erreurs:
                    for cle, valeur in valeurs.items():
                        update_config(cle, valeur)

            if erreurs:
                return _rendre(etape, valeurs, erreurs, cfg)

            journaliser(session.get('username'), 'تنصيب المنظومة',
                        'installation', f"الخطوة {etape['numero']}")
            if etape['numero'] >= identite.NB_ETAPES:
                return redirect(url_for('installation_resume'))
            prochaine = etape['numero'] + 1
            return redirect(url_for('installation_etape', numero=prochaine))

        # ── GET : القيم المحفوظة ──────────────────────────────────────────────
        if numeros:
            valeurs = {'numero_depart_interne': str(prochain_numero_prevu('interne')),
                       'numero_depart_externe': str(prochain_numero_prevu('externe'))}
        elif code_centre:
            ref = identite.val(cfg, 'ref_prefix') or 'END-3-01-02'
            parts = ref.split('-')
            valeurs = {
                'ref_prefix': ref,
                '_code_part1': parts[2] if len(parts) > 2 else '01',
                '_code_part2': parts[3] if len(parts) > 3 else '02',
            }
        else:
            valeurs = {c['cle']: identite.val(cfg, c['cle']) for c in etape['champs']}
        return _rendre(etape, valeurs, cfg=cfg)

    # ─── الملخّص والمصادقة ───────────────────────────────────────────────────

    @app.route('/installation/resume', methods=['GET', 'POST'])
    @login_required
    def installation_resume():
        cfg = get_config()
        if identite.installation_faite(cfg):
            return redirect(url_for('parametres_centre')) if _est_admin() \
                else redirect(url_for('accueil'))
        if not _est_admin():
            return render_template('installation_attente.html',
                                   now_year=datetime.now().year)

        if request.method == 'POST':
            manquants = [c.get('label', c['cle'])
                         for etape in identite.ETAPES_INSTALLATION
                         if etape.get('type') not in ('numeros', 'code_centre')
                         for c in etape['champs']
                         if c.get('obligatoire') and not identite.val(cfg, c['cle'])]
            if manquants:
                flash('لا يمكن إتمام التّنصيب: ' + '، '.join(manquants), 'error')
                return redirect(url_for('installation_etape', numero=1))
            update_config('installation_faite', '1')
            # زرع الجهات المرجعية (وحدة الحرس، الإدارة الجهوية…) في القاعدة
            semer_jihat()
            journaliser(session.get('username'), 'إتمام التّنصيب', 'installation',
                        identite.nom_centre(get_config()))
            flash('تمّ تنصيب المنظومة بنجاح. مرحبا بكم.', 'success')
            return redirect(url_for('accueil'))

        return render_template(
            'installation_resume.html',
            sections=identite.recapitulatif(cfg),
            depart_interne=prochain_numero_prevu('interne'),
            depart_externe=prochain_numero_prevu('externe'),
            plancher_interne=plancher_numero('interne'),
            plancher_externe=plancher_numero('externe'),
            nb_etapes=len(_etapes_visibles()),
            now_year=datetime.now().year,
        )
