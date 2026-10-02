# -*- coding: utf-8 -*-
"""Réglages de sécurité de session (v1.5 — S3)."""

DELAIS_INACTIVITE = (0, 15, 30, 60, 120)      # minutes ; 0 = jamais
DELAI_INACTIVITE_DEFAUT = 30


def delai_inactivite(cfg):
    """Délai d'inactivité réglé (minutes), borné aux valeurs proposées.
    Une valeur absente ou illisible retombe sur le défaut, jamais sur 0 :
    une base corrompue ne doit pas désactiver silencieusement la protection."""
    try:
        v = int(str((cfg or {}).get('delai_inactivite', DELAI_INACTIVITE_DEFAUT)).strip())
    except (TypeError, ValueError):
        return DELAI_INACTIVITE_DEFAUT
    return v if v in DELAIS_INACTIVITE else DELAI_INACTIVITE_DEFAUT
