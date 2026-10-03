"""Enregistrement des routes, regroupées par domaine.

Chaque module expose `register(app, ctx)` et déclare ses vues avec
`@app.route(...)` exactement comme avant : les noms de fonctions — donc les
noms d'endpoints utilisés par `url_for()` dans les gabarits — sont inchangés.
Aucun Blueprint n'est utilisé, précisément pour ne pas préfixer ces noms.
"""

from . import (auth, pages, mkowin, mawad, programme, dorra, pdf, api,
               installation, jihat, importation, mustahaqqat, khalas, securite, donnees, recherche,
               rapports, maintenance)

MODULES = (auth, pages, mkowin, mawad, programme, dorra, pdf, api,
           installation, jihat, importation, mustahaqqat, khalas, securite, donnees, recherche,
           rapports, maintenance)


def register_all(app, ctx):
    """ctx porte les helpers partagés définis dans app.py (décorateurs, etc.)."""
    for module in MODULES:
        module.register(app, ctx)
