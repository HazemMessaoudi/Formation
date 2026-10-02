# -*- coding: utf-8 -*-
"""المكوّنون / الأشخاص : lecture, recherche (autocomplétion), CRUD.

Extrait de core/database.py (v1.4) — importer depuis core.database, qui
ré-exporte tout : les appelants existants restent inchangés."""


from core.db._base import _log, get_connection


# ─── Mkowin (Trainers) ────────────────────────────────────────────────────────

GRADE_ORDER = [
    'عميد للديوانة', 'عقيد للديوانة', 'مقدم للديوانة', 'رائد للديوانة',
    'نقيب للديوانة', 'النقيب',
    'ملازم أول صنف أ2 للديوانة', 'ملازم للديوانة',
    'وكيل أول للديوانة', 'وكيل للديوانة',
    'عريف أعلى للديوانة', 'عريف للديوانة',
    'طبيب الصحة العمومية', 'ممرض رئيس للصحة العمومية',
    'عامل صنف 2', 'عامل صنف 3', 'عامل صنف 4', 'عامل صنف 5', 'عامل صنف 6',
]

_ORDRE_RUTAB = [
    'لواء', 'عميد', 'عقيد', 'مقدم', 'رائد', 'نقيب',
    'ملازم اول صنف 1', 'ملازم اول', 'ملازم اول صنف 2', 'ملازم',
    'وكيل اول', 'وكيل', 'عريف اعلي', 'عريف اول', 'عريف', 'رقيب اول', 'رقيب',
    'طبيب صحه عموميه', 'ممرض رييس للصحه عموميه',
    'عامل صنف 2', 'عامل صنف 3', 'عامل صنف 4', 'عامل صنف 5', 'عامل صنف 6',
]


def rang_grade(grade):
    """Rang hiérarchique d'une رتبة, quelle que soit sa graphie
    (« النقيب » = « نقيب للديوانة » ; « صنف أ2 » = « صنف 2 »)."""
    from core.mustahaqqat import normaliser_grade
    cle = normaliser_grade(grade)
    if cle in _ORDRE_RUTAB:
        return _ORDRE_RUTAB.index(cle)
    # « مقدم xxx » : on retient la racine connue la plus longue
    for i, r in sorted(enumerate(_ORDRE_RUTAB), key=lambda t: -len(t[1])):
        if cle.startswith(r + ' '):
            return i
    return len(_ORDRE_RUTAB)


def get_mkowin():
    conn = get_connection()
    rows = conn.execute('SELECT * FROM mkowin').fetchall()
    conn.close()
    data = [dict(r) for r in rows]
    data.sort(key=lambda m: (rang_grade(m.get('grade')), m.get('nom') or '',
                             m.get('prenom') or ''))
    return data

#: Champs exposés à l'autocomplétion : jamais de CIN, compte bancaire, adresse…
#: v1.6 : الجنس et الفئة العمريّة y figurent pour pré-remplir la ligne du
#: مشارك (statistiques seulement) — ni l'un ni l'autre n'identifie la personne.
CHAMPS_MKOW_PUBLICS = ('nom', 'prenom', 'grade', 'lieu_travail',
                       'identifiant_unique', 'jiha_marjiiya', 'sexe', 'fiaa_omria')


def nom_complet_mkow(m):
    """« nom prenom » tel qu'affiché et saisi partout dans la منظومة."""
    nom = m.get('nom') or ''
    prenom = m.get('prenom') or ''
    return (nom + (' ' + prenom if prenom else '')).strip()


def _mkow_public(m):
    return {c: (m.get(c) or '') for c in CHAMPS_MKOW_PUBLICS}


def rechercher_mkowin(q='', limite=40):
    """Recherche pour l'autocomplétion (remplace l'injection intégrale de la
    table dans la page). Même règle que l'ancien filtre côté navigateur :
    le texte cherché est contenu dans le nom complet, la رتبة ou مكان العمل
    (insensible à la casse), ordre des رتب conservé, `limite` résultats max."""
    q = (q or '').strip().lower()
    try:
        limite = max(1, min(int(limite), 200))
    except (TypeError, ValueError):
        limite = 40
    res = []
    for m in get_mkowin():
        if (not q or q in nom_complet_mkow(m).lower()
                or q in (m.get('grade') or '').lower()
                or q in (m.get('lieu_travail') or '').lower()):
            res.append(_mkow_public(m))
            if len(res) >= limite:
                break
    return res


def completer_fiches_depuis_participants(participants):
    """v1.7.1 — Complète les fiches (mkowin) à partir d'une قائمة المشاركين
    confirmée : الجنس, الفئة العمريّة et مكان العمل choisis pour un participant
    sont reportés sur SA fiche (retrouvée par المعرّف الوحيد) quand la case de
    la fiche est vide. Jamais d'écrasement. Rend le nombre de fiches touchées."""
    from core import validation as _v
    touchees = 0
    conn = get_connection()
    try:
        for p in participants or []:
            ident = str(p.get('identifiant_unique') or '').strip()
            if not ident:
                continue
            fiche = conn.execute(
                'SELECT id, sexe, fiaa_omria, lieu_travail FROM mkowin '
                'WHERE TRIM(identifiant_unique)=? LIMIT 1', (ident,)).fetchone()
            if not fiche:
                continue
            maj = {}
            sexe = str(p.get('sexe') or '').strip()
            fiaa = str(p.get('fiaa_omria') or '').strip()
            lieu = str(p.get('lieu_travail') or '').strip()
            if sexe in _v.SEXES and not (fiche['sexe'] or '').strip():
                maj['sexe'] = sexe
            if fiaa in _v.FIAAT and not (fiche['fiaa_omria'] or '').strip():
                maj['fiaa_omria'] = fiaa
            if lieu and not (fiche['lieu_travail'] or '').strip():
                maj['lieu_travail'] = lieu
            if maj:
                conn.execute('UPDATE mkowin SET ' + ', '.join(f'{c}=?' for c in maj)
                             + ' WHERE id=?', (*maj.values(), fiche['id']))
                touchees += 1
        conn.commit()
    except Exception:
        _log.exception('completer_fiches_depuis_participants')
    finally:
        conn.close()
    return touchees


def mkowin_par_noms(noms):
    """Fiches publiques des personnes dont le nom complet figure dans `noms`
    (correspondance exacte) — pour réafficher un programme en modification."""
    voulus = {(n or '').strip() for n in noms if (n or '').strip()}
    if not voulus:
        return []
    return [_mkow_public(m) for m in get_mkowin() if nom_complet_mkow(m) in voulus]


def get_mkow(mkow_id):
    conn = get_connection()
    row = conn.execute('SELECT * FROM mkowin WHERE id = ?', (mkow_id,)).fetchone()
    conn.close()
    return dict(row) if row else None

_CHAMPS_MKOW = (
    'grade', 'nom', 'prenom', 'cin', 'cin_date', 'identifiant_unique',
    'adresse', 'telephone_gsm', 'telephone_adm', 'diplome', 'degre',
    'plan_fonctionnel', 'administration', 'ministere', 'lieu_travail',
    'specialite', 'email', 'banque', 'agence', 'num_compte', 'notes',
    'jiha_marjiiya', 'sexe', 'fiaa_omria',
)

_CHAMPS_MADDA = (
    'titre', 'type_formation', 'mahawer', 'objectifs', 'methodes_pedagogiques',
    'moyens_pedagogiques', 'preparation_materielle', 'equipements',
    'mustahdafun', 'lieu_formation_defaut',
)


def _completer(data, champs):
    """Complète les clés absentes par une chaîne vide : un formulaire partiel
    ne doit jamais faire échouer l'enregistrement sur un paramètre manquant."""
    plein = {c: '' for c in champs}
    plein.update({k: v for k, v in (data or {}).items() if k in champs})
    return plein


def add_mkow(data):
    data = _completer(data, _CHAMPS_MKOW)
    conn = get_connection()
    try:
        conn.execute('''
            INSERT INTO mkowin (grade, nom, prenom, cin, cin_date, identifiant_unique,
            adresse, telephone_gsm, telephone_adm, diplome, degre, plan_fonctionnel,
            administration, ministere, lieu_travail, specialite, email,
            banque, agence, num_compte, notes, jiha_marjiiya, sexe, fiaa_omria)
            VALUES (:grade, :nom, :prenom, :cin, :cin_date, :identifiant_unique,
            :adresse, :telephone_gsm, :telephone_adm, :diplome, :degre, :plan_fonctionnel,
            :administration, :ministere, :lieu_travail, :specialite, :email,
            :banque, :agence, :num_compte, :notes, :jiha_marjiiya, :sexe, :fiaa_omria)
        ''', data)
        conn.commit()
        return True
    except Exception as e:
        _log.exception(f"add_mkow error: {e}")
        return False
    finally:
        conn.close()

def update_mkow(mkow_id, data):
    """Met à jour UNIQUEMENT les champs réellement transmis.

    « On n'écrit que ce qu'on montre » — la règle déjà appliquée au معالج
    التّنصيب et à /parametres. Elle devient indispensable ici à partir de la
    v58 : la fiche du مكوّن a gagné une خانة (`jiha_marjiiya`) que les
    formulaires antérieurs ne présentent pas. Avec l'ancienne écriture
    intégrale, ouvrir puis enregistrer une fiche depuis une page qui ignore
    cette خانة l'aurait effacée sans un mot — une perte silencieuse, la pire
    espèce. Ce qui n'est pas soumis n'est plus touché.

    Une خانة soumise vide reste, elle, un effacement voulu : le مستعمل l'a vue
    et l'a vidée.
    """
    champs = [c for c in _CHAMPS_MKOW if c in (data or {})]
    if not champs:
        # Aucun champ connu n'a été transmis : ce n'est pas une modification
        # vide, c'est un formulaire qui ne correspond plus à la قاعدة. On le
        # signale plutôt que de prétendre avoir enregistré.
        return False
    conn = get_connection()
    try:
        affectations = ', '.join(f'{c}=:{c}' for c in champs)
        valeurs = {c: data[c] for c in champs}
        conn.execute(f'UPDATE mkowin SET {affectations} WHERE id=:id',
                     {**valeurs, 'id': mkow_id})
        conn.commit()
        return True
    except Exception as e:
        _log.exception(f"update_mkow error: {e}")
        return False
    finally:
        conn.close()

def delete_mkow(mkow_id):
    conn = get_connection()
    try:
        # mawad.mkow_id référence mkowin(id) sans ON DELETE : on détache d'abord
        # les matières concernées (équivalent d'un SET NULL) sinon la contrainte
        # d'intégrité bloquerait la suppression.
        conn.execute('UPDATE mawad SET mkow_id = NULL WHERE mkow_id = ?', (mkow_id,))
        conn.execute('DELETE FROM mkowin WHERE id = ?', (mkow_id,))
        conn.commit()
        return True
    except Exception as e:
        _log.exception(f"delete_mkow error: {e}")
        return False
    finally:
        conn.close()


def dorrat_liees_mkowin():
    """{id fiche: nombre de دورات dont le مكوّن porte ce nom}. Rapprochement
    tolérant aux espaces et à l'ordre nom/prénom (cf. candidats_mkow_par_nom).
    Sert à avertir avant une suppression : la fiche disparaît, les دورات
    restent mais ne retrouvent plus la fiche (وثيقة الخلاص, المستحقّات)."""
    conn = get_connection()
    try:
        compte = {}
        for r in conn.execute('SELECT nom_formateur FROM formations').fetchall():
            n = ' '.join(str(r[0] or '').split())
            if n:
                compte[n] = compte.get(n, 0) + 1
        res = {}
        for m in conn.execute('SELECT id, nom, prenom FROM mkowin').fetchall():
            n = ' '.join(str(m['nom'] or '').split())
            p = ' '.join(str(m['prenom'] or '').split())
            formes = {f for f in (n, f'{n} {p}'.strip(), f'{p} {n}'.strip()) if f}
            nb = sum(compte.get(f, 0) for f in formes)
            if nb:
                res[m['id']] = nb
        return res
    except Exception:
        _log.warning('dorrat_liees_mkowin : exception ignorée', exc_info=True)
        return {}
    finally:
        conn.close()


def nb_dorrat_liees_mkow(mkow_id):
    return dorrat_liees_mkowin().get(mkow_id, 0)


def delete_mkowin_lot(ids):
    """Suppression groupée d'une sélection de personnes. Retourne le nombre
    de lignes réellement supprimées."""
    ids = [int(i) for i in (ids or []) if str(i).strip().isdigit()]
    if not ids:
        return 0
    conn = get_connection()
    try:
        marks = ','.join('?' * len(ids))
        # Détacher les matières rattachées avant suppression (cf. delete_mkow)
        conn.execute(f'UPDATE mawad SET mkow_id = NULL WHERE mkow_id IN ({marks})', ids)
        cur = conn.execute(f'DELETE FROM mkowin WHERE id IN ({marks})', ids)
        conn.commit()
        return cur.rowcount
    except Exception as e:
        _log.exception(f"delete_mkowin_lot error: {e}")
        return 0
    finally:
        conn.close()


# ─── Suggestions de saisie (v1.5 — A10) ─────────────────────────────────────
# Colonnes dont les valeurs se répètent d'une fiche à l'autre : on propose
# celles déjà saisies (liste <datalist>), sans jamais les imposer.
CHAMPS_SUGGERES = ('administration', 'lieu_travail', 'ministere', 'banque', 'agence',
                   'specialite', 'diplome', 'plan_fonctionnel', 'degre')


def suggestions_mkowin(limite=150):
    """{colonne: [valeurs distinctes, les plus fréquentes d'abord]}."""
    conn = get_connection()
    try:
        out = {}
        for col in CHAMPS_SUGGERES:           # noms de colonnes fixes : pas d'injection
            rows = conn.execute(
                f"SELECT TRIM({col}) AS v, COUNT(*) AS n FROM mkowin "
                f"WHERE {col} IS NOT NULL AND TRIM({col}) != '' "
                f"GROUP BY TRIM({col}) ORDER BY n DESC, v LIMIT ?", (limite,)).fetchall()
            out[col] = [r['v'] for r in rows]
        return out
    finally:
        conn.close()
