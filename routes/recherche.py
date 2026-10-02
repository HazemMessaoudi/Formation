"""Recherche unifiée (v1.5 — D4) : /api/recherche?q=…"""
from flask import request, jsonify, url_for

from core import recherche as _r


def register(app, ctx):
    login_required = ctx['login_required']

    @app.route('/api/recherche')
    @login_required
    def api_recherche():
        q = (request.args.get('q') or '').strip()[:100]
        groupes = _r.rechercher(q)
        for g in groupes:
            for x in g['resultats']:
                endpoint, args = x.pop('cible')
                x['url'] = url_for(endpoint, **args)
        return jsonify({'q': q, 'groupes': groupes})
