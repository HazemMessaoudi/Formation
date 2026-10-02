# -*- coding: utf-8 -*-
"""تجميد هويّة الوثيقة عند التّأكيد.

Une مراسلة qui a pris son عدد est partie. Elle porte le nom du مركز, celui
du responsable et son titre tels qu'ils étaient **ce jour-là**. Si le مركز
change de responsable en mars, réimprimer la مراسلة de janvier doit rendre
la مراسلة de janvier — avec le responsable de janvier — et non une pièce
retouchée après coup. Un document officiel ne se réécrit pas.

Sans ce gel, le simple fait de corriger une faute de frappe dans les
إعدادات modifierait rétroactivement toutes les correspondances déjà
enregistrées à la منظومة. C'est précisément ce que la distribution à
plusieurs مراكز rendrait fréquent.

Le gel est pris une fois, au moment où la مراسلة du برنامج est confirmée, et
vaut pour toutes les pièces de ce برنامج : مراسلة, مراسلات المديرين
الجهويّين, برنامج الدّورة, القائمة الإسميّة, البطاقة البيداغوجيّة, مذكّرة.
Elles appartiennent au même acte et doivent parler d'une seule voix.

Ce module n'échoue jamais bruyamment : un gel manquant ou illisible rend
l'identité d'aujourd'hui. Mieux vaut une وثيقة imprimée avec l'identité
courante qu'une وثيقة non imprimée.
"""

import logging as _logging
_log = _logging.getLogger('formation.' + __name__)

import json

from core import identite


#: Les خانات gelées : l'identité du مركز et de son responsable. Le contenu
#: métier (دورات, مشاركون, مواد) vit déjà dans ses propres tables et ne
#: change pas tout seul ; seule l'identité, qui vient des إعدادات, le peut.
CHAMPS_GELES = (
    'nom_responsable', 'titre_responsable', 'nom_centre', 'nom_centre_ba',
    'ville_centre', 'entete_centre_1', 'entete_centre_2', 'destination_dr',
)


def _table(conn):
    conn.execute('''
        CREATE TABLE IF NOT EXISTS documents_geles (
            lettre_id  INTEGER PRIMARY KEY,
            donnees    TEXT NOT NULL,
            gele_at    TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')


def figer(conn, lettre_id, config):
    """Fige l'identité de ce برنامج, si elle ne l'est pas déjà.

    Appelé dans la transaction qui attribue le عدد : le gel et le عدد
    naissent ensemble, sinon une panne entre les deux laisserait une مراسلة
    numérotée sans identité figée.

    Un second appel ne réécrit rien — on ne regèle pas un document parti.
    """
    try:
        _table(conn)
        donnees = {c: v for c, v in identite.champs_pdf(config).items()
                   if c in CHAMPS_GELES}
        conn.execute(
            'INSERT OR IGNORE INTO documents_geles (lettre_id, donnees) VALUES (?,?)',
            (lettre_id, json.dumps(donnees, ensure_ascii=False)))
        return True
    except Exception:
        _log.warning('figer : exception ignorée', exc_info=True)
        # Un gel raté ne doit pas empêcher une مراسلة d'être confirmée.
        return False


def lire(conn, lettre_id):
    """Rend l'identité gelée de ce برنامج, ou None s'il n'y en a pas."""
    try:
        _table(conn)
        row = conn.execute('SELECT donnees FROM documents_geles WHERE lettre_id=?',
                           (lettre_id,)).fetchone()
        if not row:
            return None
        donnees = json.loads(row['donnees'])
        return donnees if isinstance(donnees, dict) and donnees else None
    except Exception:
        _log.warning('lire : exception ignorée', exc_info=True)
        return None


def champs_pdf(config, lettre_id=None):
    """Les حقول d'identité à mettre dans une وثيقة de ce برنامج.

    Rend l'identité **du jour du تأكيد** quand elle a été gelée, et celle
    d'aujourd'hui sinon — brouillon non encore confirmé, ou base antérieure
    à cette version.

    C'est le seul point d'entrée que les مسارات doivent connaître : il
    remplace `identite.champs_pdf(cfg)` partout où une وثيقة est produite.
    """
    courants = identite.champs_pdf(config)
    if not lettre_id:
        return courants
    from core.database import get_connection
    conn = get_connection()
    try:
        geles = lire(conn, lettre_id)
    finally:
        conn.close()
    if not geles:
        return courants
    # Une خانة apparue après le gel (nouvelle version de la منظومة) prend sa
    # valeur du jour : le gel complète l'identité courante, il ne l'ampute pas.
    fusion = dict(courants)
    fusion.update({c: v for c, v in geles.items() if c in CHAMPS_GELES})
    return fusion
