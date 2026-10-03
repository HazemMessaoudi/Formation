"""Accès aux données — FAÇADE.

Depuis la v1.4 le code vit dans core/db/<domaine>.py ; ce module définit
le chemin de la base et la connexion, puis ré-exporte TOUS les noms
d'origine : `from core.database import X` fonctionne comme avant.

  core/db/sauvegarde.py    sauvegardes automatiques
  core/db/registre.py      registre des numéros d'enregistrement
  core/db/referentiels.py  config, رتب, أماكن, جهات
  core/db/mkowin.py        المكوّنون
  core/db/mawad.py         المواد
  core/db/programmes.py    برامج / دورات / مراسلات
  core/db/utilisateurs.py  utilisateurs, journal d'audit
  core/db/mustahaqqat.py   المستحقّات المالية
  core/db/statistiques.py  لوحة القيادة
  core/db/khalas.py        وثائق الخلاص
  core/db/schema.py        init_db / migrations
"""
import logging as _logging
_log = _logging.getLogger('formation.' + __name__)
import sqlite3
import os
import json
from werkzeug.security import generate_password_hash, check_password_hash

from core import identite
from core import exercice as _exercice
from core import regions
from core import mustahaqqat as _mustahaqqat
from core import bareme_mali as _bareme_mali

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# v1.7 : la base vit dans data/ À CÔTÉ de l'exécutable (core/chemins.py), et
# non dans le dossier d'extraction de PyInstaller.
from core import chemins as _chemins  # noqa: E402
DB_PATH = _chemins.chemin_base()


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    # Intégrité référentielle réellement appliquée : sans cette directive les
    # clauses ON DELETE CASCADE des tables sont ignorées par SQLite et des
    # lignes orphelines s'accumulent silencieusement.
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


# ─── Ré-export (ordre = dépendances) ────────────────────────────────────────
from core.db.sauvegarde import (  # noqa: E402,F401
    BACKUP_KEEP, backup_db, purger_sauvegardes, a_conserver, dossier_sauvegardes,
    sauvegarde_quotidienne_si_necessaire, lecteurs_amovibles, copier_vers_externe,
    etat_sauvegarde_externe, DOSSIER_EXTERNE, GARDER_AUJOURDHUI, GARDER_JOURS,
    GARDER_SEMAINES, GARDER_MOIS, RAPPEL_EXTERNE_JOURS, _RE_NOM, _verrou,
    _dernier_controle, _horodatage, _copier_base, derniere_sauvegarde_du_jour,
)
from core.db.registre import (  # noqa: E402,F401
    _prochain_numero, _attribuer_numero, REGISTRE_SOURCES, _liberer_numero,
    liberer_numeros_programme, confirmer_numeros_programme, _creer_registre,
    annee_registre, annees_du_registre, get_registre, get_numeros_liberes,
    registre_lacunes, prochain_numero_prevu, plancher_numero, definir_numero_depart,
)
from core.db.referentiels import (  # noqa: E402,F401
    GRADES_DEFAUT, get_config, get_grades, add_grade, get_next_ref, get_lieux, add_lieu,
    delete_lieu, _semer_jihat, semer_jihat, get_jihat, get_jihat_groupees, noms_jihat,
    add_jiha, delete_jiha, update_config,
)
from core.db.mkowin import (  # noqa: E402,F401
    GRADE_ORDER, _ORDRE_RUTAB, rang_grade, get_mkowin, CHAMPS_MKOW_PUBLICS, nom_complet_mkow, _mkow_public,
    rechercher_mkowin, mkowin_par_noms, completer_fiches_depuis_participants, get_mkow, _CHAMPS_MKOW, _CHAMPS_MADDA,
    _completer, add_mkow, update_mkow, delete_mkow, delete_mkowin_lot,
    CHAMPS_SUGGERES, suggestions_mkowin, nb_dorrat_liees_mkow, dorrat_liees_mkowin,
)
from core.db.mawad import (  # noqa: E402,F401
    delete_madda, delete_mawad_lot, get_mawad, get_madda, get_madda_by_titre, add_madda,
    update_madda, nb_dorrat_liees_madda, dorrat_liees_mawad,
)
from core.db.programmes import (  # noqa: E402,F401
    annuler_dorra, _destinataire_de_jiha, delete_programme_inacheve, get_lettres_list, get_lettre_detail,
    save_programme, update_programme, finaliser_lettre, verrouiller_lettre,
    get_dr_lettres, attribuer_numero_dr, annuler_dr_lettre, revue_dorra,
    verifier_integrite_programme, revue_programme, sceller_programme,
    programme_est_scelle, save_lettre_libre, update_lettre_libre, ETAPES_DORRA,
    PREALABLE_ETAPE, LIBELLE_ETAPE, etat_dorra, etape_autorisee, etats_dorrat,
    dorrat_meme_jour, dorrat_aux_dates, dorrat_simultanees, moujah_regionaux, get_lettres_programmes, get_dorrat_avec_memo, get_lettres_libres,
    save_participants, get_participants, save_lettre, ETAPES_LABELS, valider_etape,
    get_etapes_lettre, get_etapes_formation, get_formations_en_cours,
    get_programmes_inacheves, programme_est_complet, get_bataqa_data, save_bataqa_data,
    get_programme_data, save_programme_data, MEMO_MSAHIB, MEMO_MOUJAH_TETE,
    MEMO_MOUJAH_FIN, MEMO_TYPES, _memo_corps_defaut, get_memo_data, save_memo_data,
    finaliser_formation, formation_est_finalisee, deverrouiller_formation,
    dupliquer_programme, annee_admise,
    _bataqa_derives, bataqa_derives, actualiser_bataqa_apres_participants,
    _date_fin_de, _classif_de, _jours_du_programme, _formation_multi, get_programme_jours,
    composer_lignes_jours, save_programme_jour, formation_est_multi_jours,
    _candidates_autour, _occupation,
)
from core.db.utilisateurs import (  # noqa: E402,F401
    get_users, add_user, update_user_password, get_user_role, set_user_role,
    user_doit_changer_mdp, journaliser, get_journal, delete_user, check_credentials,
    get_journal_filtre, utilisateurs_du_journal, nb_admins, changer_role,
    ECHECS_MAX, BLOCAGE_MINUTES, LONGUEUR_MIN_MDP, LONGUEUR_MIN_MDP_ADMIN, longueur_min_mdp,
    minutes_de_blocage, noter_echec, remettre_a_zero_echecs,
)
from core.db.mustahaqqat import (  # noqa: E402,F401
    get_bareme_grades, get_bareme_grades_detail, set_classe_grade, reinitialiser_bareme,
    _SQL_DORRA_MUSTAHAQQAT, _dorrat_mustahaqqat, _enrichir_dorra,
    dorrat_mustahaqqat_ghayr_manjaza, dorrat_mustahaqqat_manjaza, get_dorra_mustahaqqat,
    get_hodour, calculer_classe, save_hodour, confirmer_classe, reprendre_hodour,
    get_groupes_grades, get_groupes_grades_detail, set_groupe_grade, get_bareme_mali,
    set_taux_bareme_mali, reinitialiser_bareme_mali, get_bareme_mali_grille,
    _rows_programme, calculer_mustahaqqat, confirmer_mustahaqqat, rouvrir_mustahaqqat,
    marquer_pret_validation, dorrat_pretes_validation, _verifier_confirmable,
    get_jours_dorra, _presences_ponderees,
)
from core.db.statistiques import (  # noqa: E402,F401
    get_stats, get_stats_mustahaqqat, get_formateurs_mustahaqqat, get_stats_avancees,
)
from core.db.rapports import (  # noqa: E402,F401
    donnees_tableau_de_bord, annees_rapport, rapport_annuel, _PROGRAMME, _un, _par_mois,
    get_parametres_annuels, get_nb_programmees, set_parametre_annuel, supprimer_parametre_annuel,
)
from core.db.khalas import (
    get_muqarrar_dorra, muqarrar_manquant, save_muqarrar_dorra, KHALAS_SETTINGS_RETIRES,  # noqa: E402,F401
    KHALAS_SETTINGS_DEFAUTS, get_khalas_settings, set_khalas_settings, get_khalas_dorra,
    save_khalas_dorra, trouver_mkow_par_nom, candidats_mkow_par_nom, _norm_grade,
)
from core.db.suggestions import (  # noqa: E402,F401
    SEPARATEUR, LONGUEUR_MAX, NATURES, decouper_intervenants, _noter, memoriser_lignes,
    memoriser_programme, suggestions_programme,
)
from core.db.schema import (  # noqa: E402,F401
    init_db, version_schema, SCHEMA_VERSION, ETAPES,
    _etape_01_base_et_tables, _etape_02_colonnes_referentiel,
    _etape_03_identite_et_jihat, _etape_04_utilisateurs_et_lettres,
    _etape_05_lettres_dr, _etape_06_participants_et_pieces,
    _etape_07_unicite_et_registre, _etape_08_ouverture_annee,
    _etape_09_journal_roles_index, _etape_10_mustahaqqat,
    _etape_11_jadwal_mali, _etape_12_khalas,
    _etape_13_identite_base, _etape_14_suggestions_programme, _etape_15_dorrat_multi_jours,
    _etape_16_classification_rapports, _etape_17_notifications,
    _nettoyer_fantomes_dr,
)
