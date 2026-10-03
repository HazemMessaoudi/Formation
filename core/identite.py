# -*- coding: utf-8 -*-
"""
هويّة المركز — المصدر الوحيد للحقيقة
=====================================

قبل الإصدار 58 كانت بيانات مركز القصرين واسم رئيسه مكتوبة حرفيّا داخل
الشّيفرة في أكثر من أربعين موضعا. هذا يمنع توزيع المنظومة على بقيّة مراكز
التّكوين الدّيواني، ويُخشى منه أن يُمضي مسؤولٌ وثيقةً باسم مسؤولٍ آخر.

هذا الملفّ يجمع كلّ تلك القيم في مكان واحد ويصنّفها إلى:

    DEFAUTS_NATIONAUX : قيم مشتركة بين جميع المراكز (المدرسة الوطنيّة،
                        المدير العامّ، بادئة المرجع…) — لها قيم افتراضيّة حقيقيّة.

    DEFAUTS_CENTRE    : قيم خاصّة بكلّ مركز (الاسم، المدينة، رئيس المركز،
                        المدير الجهوي…) — قيمها الافتراضيّة فارغة عمدا،
                        يملؤها معالج التّنصيب عند أوّل تشغيل.

قاعدة صارمة: لا تُولَّد قواعد النّحو العربي داخل الشّيفرة. حرف الجرّ يُخزَّن
داخل القيمة نفسها (يكتب المستعمل «بالوسط الغربي» أو «ببنزرت»)، لأنّ أيّ
اشتقاق آلي يُخطئ حتما في مثل «بنزرت».

الوحدة لا تستورد أيّ وحدة أخرى من المشروع: يجوز لقاعدة البيانات
وللمولّدات وللمسارات أن تستوردها دون خطر الاستيراد الدّائري.
"""

# ─── الإصدار ──────────────────────────────────────────────────────────────────

VERSION_APP = '1.0'
VERSION_LABEL = 'الإصدار 1.0'


# ─── قيم وطنيّة: مشتركة بين كلّ مراكز التّكوين الدّيواني ───────────────────────

DEFAUTS_NATIONAUX = {
    'ref_prefix':              'END-3-01-02',
    'titre_directeur_general': 'العميد',
    'nom_directeur_general':   'عبد الحكيم عبيدي',
    'ecole_email':             'end.dfrs@douane.gov.tn',
    'ecole_tel':               '72205722',
    'ecole_fax':               '72205636',
    'ecole_web':               'www.douane.gov.tn/structures-de-formation',
    'ecole_adresse':           'المدرسة الوطنيّة للدّيوانة – فندق الجديد – نابل – 8012',
}


# ─── قيم خاصّة بالمركز: فارغة افتراضيّا ───────────────────────────────────────
#
#   nom_centre        : الاسم الكامل كما يظهر في ترويسة المراسلات.
#   nom_centre_ba     : الاسم نفسه مسبوقا بحرف الجرّ («بمركز…» / «بالمركز…»).
#   ville_centre      : المدينة، تُستعمل في سطر التّاريخ «القصرين في ...».
#   entete_centre_1/2 : سطرا المركز في ترويسة برنامج الدّورة (سطران لضيق المجال).
#   destination_dr    : وجهة مراسلة المدير الجهوي، كاملة بحرف الجرّ.
#   nom/titre_responsable : رئيس المركز الذي يُمضي الوثائق.
#   admin_regionale   : الإدارة الجهويّة المرجعيّة (تُستعمل في ربط المشاركين).
#   unite_garde       : وحدة الحرس الدّيواني المرجعيّة.
#   lieu_formation_defaut : قاعة التّكوين التي تُقترح تلقائيّا.

DEFAUTS_CENTRE = {
    'nom_centre':            '',
    'nom_centre_ba':         '',
    'ville_centre':          '',
    'entete_centre_1':       '',
    'entete_centre_2':       '',
    'destination_dr':        '',
    'nom_responsable':       '',
    'titre_responsable':     '',
    'admin_regionale':       '',
    'unite_garde':           '',
    'lieu_formation_defaut': '',
}

# مفاتيح يملؤها معالج التّنصيب (المرحلة ب)
CLES_CENTRE = tuple(DEFAUTS_CENTRE.keys())
CLES_NATIONALES = tuple(DEFAUTS_NATIONAUX.keys())

# كلّ المفاتيح القابلة للتّعديل من صفحة الإعدادات.
# تُستعمل في مسار /parametres وفي صفحة «هويّة المركز»: إضافة مفتاح جديد
# هنا تكفي لجعله قابلا للحفظ، دون تعديل المسارات.
CLES_EDITABLES = CLES_CENTRE + CLES_NATIONALES

DEFAUTS = dict(DEFAUTS_NATIONAUX)
DEFAUTS.update(DEFAUTS_CENTRE)
DEFAUTS['installation_faite'] = '0'
DEFAUTS['version_app'] = VERSION_APP


# ─── التّسمية المحايدة ────────────────────────────────────────────────────────
# تظهر فقط قبل إتمام التّنصيب، حتّى لا تبقى الوثيقة بلا ترويسة.

CENTRE_NEUTRE = 'مركز التّكوين الدّيواني'


# ─── قيم مركز القصرين التّاريخيّة ─────────────────────────────────────────────
#
# تُستعمل حصرا عند ترقية تنصيب قائم من إصدار سابق: تُنسخ إلى جدول config
# مرّة واحدة حتّى يبقى سلوك المنظومة مطابقا تماما لما كان عليه.
# لا تُستعمل أبدا في تنصيب جديد.

HERITAGE = {
    'nom_centre':            'مركز التكوين الديواني بالقصرين',
    'nom_centre_ba':         'بمركز التكوين الديواني بالقصرين',
    'ville_centre':          'القصرين',
    'entete_centre_1':       'المركز الجهوي للتّكوين الدّيواني',
    'entete_centre_2':       'بالوسط الغربي والقصرين',
    'destination_dr':        'السيد المدير الجهوي للديوانة بالقصرين',
    'nom_responsable':       'حازم مسعودي',
    'titre_responsable':     'النقيب',
    'admin_regionale':       'الإدارة الجهويّة للدّيوانة بالقصرين',
    'unite_garde':           'الوحدة الرّابعة للحرس الدّيواني بقفصة',
    'lieu_formation_defaut': 'مركز التكوين الجهوي بالقصرين',
}


# ─── قوائم المرجع للمعالج ─────────────────────────────────────────────────────
#
# تُستعمل في معالج التّنصيب وفي صفحة الإعدادات: الولايات الأربع والعشرون،
# مراكز التّكوين، رتب المسؤولين، وحدات الحرس، وقاعات التّكوين.

WILAYAS = [
    'تونس', 'أريانة', 'بن عروس', 'منوبة', 'نابل', 'زغوان', 'بنزرت',
    'باجة', 'جندوبة', 'الكاف', 'سليانة', 'سوسة', 'المنستير', 'المهدية',
    'صفاقس', 'القيروان', 'القصرين', 'سيدي بوزيد', 'قابس', 'مدنين',
    'تطاوين', 'قفصة', 'توزر', 'قبلي',
]

CENTRES_FORMATION = [f'مركز التكوين الديواني ب{w}' for w in WILAYAS]

#: Rتب سلك الدّيوانة, de العميد à العريف — et rien d'autre : ni رتب de la
#: شرطة (qui figuraient ici par erreur), ni اللواء, ni les رقباء sous العريف.
#: Libellés identiques à ceux du جدول الأصناف (core/mustahaqqat.py).
GRADES_RESPONSABLE = [
    'العميد', 'العقيد', 'المقدم', 'الرائد', 'النقيب',
    'الملازم أول', 'الملازم',
    'الوكيل أول', 'الوكيل',
    'العريف أعلى', 'العريف',
]

UNITES_GARDE = [
    'الوحدة الأولى للحرس الديواني بتونس',
    'الوحدة الثانية للحرس الديواني بجندوبة',
    'الوحدة الثالثة للحرس الديواني بسوسة',
    'الوحدة الرابعة للحرس الديواني بقفصة',
    'الوحدة الخامسة للحرس الديواني بمدنين',
    'الوحدة السادسة للحرس الديواني بصفاقس',
]

SALLES_FORMATION = [f'مركز التكوين الجهوي ب{w}' for w in WILAYAS]


# ─── ترويسة المؤسّسة ──────────────────────────────────────────────────────────
# سطور وطنيّة ثابتة لا تتغيّر من مركز إلى آخر.
# نسختان: عاديّة (المراسلات والبطاقة) ومشكولة (برنامج الدّورة) — تُحفظ كما هي
# حرفا بحرف حتّى لا يتغيّر شكل الوثائق الحاليّة.

ENTETE_NATIONAL = (
    'الجمهورية التونسية',
    'وزارة المالية',
    'الإدارة العامة للديوانة',
    'المدرسة الوطنية للديوانة',
    'إدارة التكوين الجهوي والمختص',
)

ENTETE_NATIONAL_ORNE = (
    'الجمهوريّـة التّونسيّـة',
    'وزارة الماليّـة',
    'الإدارة العامّـة للدّيوانـة',
    'المدرسة الوطنيّـة للدّيوانـة',
    'إدارة التّكوين الجهوي والمختصّ',
)


# ─── قراءة القيم ──────────────────────────────────────────────────────────────

def val(config, cle, defaut=''):
    """قيمة مفتاح من config، وإلّا القيمة الافتراضيّة، وإلّا `defaut`.

    القيمة الفارغة في قاعدة البيانات تُعامَل كغياب، فتُستعمل القيمة
    الافتراضيّة (وهي فارغة بدورها بالنّسبة إلى مفاتيح المركز).
    """
    v = (config or {}).get(cle)
    if v is None or str(v).strip() == '':
        v = DEFAUTS.get(cle, defaut)
    if v is None or str(v).strip() == '':
        return defaut
    return str(v).strip()


def fusionner(config):
    """قاموس كامل: القيم الافتراضيّة ثمّ ما هو مخزَّن فوقها."""
    d = dict(DEFAUTS)
    for cle, valeur in (config or {}).items():
        if valeur is not None and str(valeur).strip() != '':
            d[cle] = str(valeur).strip()
        else:
            d.setdefault(cle, '')
    return d


def installation_faite(config):
    return str((config or {}).get('installation_faite', '0')).strip() == '1'


# ─── قيم مشتقّة ───────────────────────────────────────────────────────────────

def nom_centre(config, neutre=CENTRE_NEUTRE):
    """اسم المركز، أو التّسمية المحايدة إن لم يُنصَّب بعد."""
    return val(config, 'nom_centre') or neutre


def ville(config):
    """مدينة المركز — قد تكون فارغة قبل التّنصيب."""
    return val(config, 'ville_centre')


def prefixer_ba(nom):
    """يُلحق حرف الجرّ «بـ» باسم المركز.

    صحيحٌ في أسماء المراكز لأنّها تبدأ عادةً بـ«مركز» («مركز…» ← «بمركز…»)
    أو بأداة التّعريف «ال» («المركز…» ← «بالمركز…»)، وفي الحالتين يصحّ
    الإلصاق المباشر. أمّا التّجاوز اليدوي فمتاح لأيّ اسم شاذّ عبر حقل
    `nom_centre_ba` في صفحة الهويّة، ويُؤخذ قبل المرور من هنا.
    """
    nom = (nom or '').strip()
    if not nom:
        return nom
    return 'ب' + nom


def centre_avec_ba(config):
    """اسم المركز مسبوقا بحرف الجرّ، كما في «برنامج الدّورة … بالمركز …».

    إن ضبط المستعمل القيمة يدويّا في `nom_centre_ba` (صفحة الهويّة) أُخذت
    كما هي. وإلّا اشتُقّت آليّا بإلحاق «بـ» باسم المركز — وهو صحيحٌ في
    أسماء المراكز إذ تبدأ بـ«مركز» أو «المركز».
    """
    explicite = val(config, 'nom_centre_ba')
    if explicite:
        return explicite
    nc = val(config, 'nom_centre') or CENTRE_NEUTRE
    return prefixer_ba(nc)


def destination_dr(config):
    """وجهة مراسلة المدير الجهوي، كاملة كما ضبطها المركز."""
    return val(config, 'destination_dr')


def directeur_regional(config):
    """«السيّد المدير الجهوي للدّيوانة بـ…» — le مرجع النظر des مكاتب.

    Tiré, dans l'ordre, de la وجهة déjà réglée, de la الإدارة الجهويّة, puis
    de la ville du centre. Rend '' si rien de tout cela n'est connu."""
    dr = val(config, 'destination_dr').strip()
    if dr:
        return dr
    adm = val(config, 'admin_regionale').strip()
    if adm:
        import re as _re
        corps = _re.sub(r'^الإدارة\s+الجهوي[ّ]?ة\s*', '', adm)
        if corps != adm:
            return f'السيّد المدير الجهوي {corps}'.strip()
        return f'السيّد مدير {adm}'
    v = val(config, 'ville_centre').strip()
    return f'السيّد المدير الجهوي للدّيوانة ب{v}' if v else ''


def admin_regionale(config):
    """الإدارة الجهويّة المرجعيّة : la valeur réglée, sinon dérivée de la وجهة
    du DR, sinon de la ville du centre. Jamais vide dès que la ville est connue
    — sinon la مذكّرة et la بطاقة citeraient « مكتب… » au lieu de sa direction."""
    adm = val(config, 'admin_regionale').strip()
    if adm:
        return adm
    der = deriver_admin_regionale(val(config, 'destination_dr'))
    if der:
        return der
    v = val(config, 'ville_centre').strip()
    return f'الإدارة الجهويّة للدّيوانة ب{v}' if v else ''


def chef_unite_garde(config):
    """«السيّد رئيس الوحدة … للحرس الدّيواني بـ…» — le مرجع النظر des فرق."""
    u = val(config, 'unite_garde').strip()
    return f'السيّد رئيس {u}' if u else ''


def lignes_entete_centre(config):
    """سطر أو سطرا المركز في ترويسة برنامج الدّورة."""
    lignes = [val(config, 'entete_centre_1'), val(config, 'entete_centre_2')]
    lignes = [l for l in lignes if l]
    if lignes:
        return lignes
    nc = val(config, 'nom_centre')
    return [nc] if nc else []


def entete_programme(config):
    """الترويسة الكاملة لبرنامج الدّورة: وطنيّة مشكولة + سطور المركز."""
    return list(ENTETE_NATIONAL_ORNE) + lignes_entete_centre(config)


def ligne_date(config, texte_date):
    """«المدينة في <التّاريخ>» — ودون المدينة إن لم تُضبط بعد."""
    v = ville(config)
    texte_date = (texte_date or '').strip()
    if not texte_date:
        return ''
    return f'{v} في {texte_date}' if v else texte_date


def signataire(config):
    """(الرّتبة، الاسم) لرئيس المركز — قد يكونان فارغين قبل التّنصيب."""
    return val(config, 'titre_responsable'), val(config, 'nom_responsable')


def champs_pdf(config):
    """حقول الهويّة التي تحتاجها كلّ مولّدات الوثائق.

    تُدمج في قاموس الوثيقة دفعة واحدة، فلا يبقى في المسارات أيّ قيمة
    مكتوبة حرفيّا:  pdf_data = {..., **identite.champs_pdf(cfg)}
    """
    return {
        'nom_responsable':   val(config, 'nom_responsable'),
        'titre_responsable': val(config, 'titre_responsable'),
        'nom_centre':        nom_centre(config),
        'nom_centre_ba':     centre_avec_ba(config),
        'ville_centre':      ville(config),
        'entete_centre_1':   val(config, 'entete_centre_1'),
        'entete_centre_2':   val(config, 'entete_centre_2'),
        'destination_dr':    destination_dr(config),
    }


# ─── معالج التّنصيب (المرحلة ب) ───────────────────────────────────────────────
#
# ثماني أسئلة تُطرح مرّة واحدة عند أوّل تشغيل، ولا شيء غيرها: كلّ سؤال يقابل
# قيمة كانت مكتوبة حرفيّا في الشّيفرة قبل الإصدار 58.
#
# حُذف منذ الإصدار 61 سؤالان كانا يُثقلان المعالج دون فائدة:
#   • «الاسم مسبوقا بالباء»  →  يُشتقّ آليّا من اسم المركز عبر centre_avec_ba().
#   • «ترويسة المركز» (سطران) →  تعود آليّا إلى اسم المركز عبر lignes_entete_centre().
# ويبقى تعديل القيمتين ممكنا لاحقا من صفحة «هويّة المركز» عند الحاجة.
#
# البنية معطيات لا شيفرة: المسار والقالب عامّان، فإضافة سؤال جديد لا تقتضي
# إلّا إضافة عنصر هنا.
#
#   numero      : رتبة الخطوة (تبدأ من 1)
#   titre       : عنوان الخطوة
#   question    : السّؤال كما يُطرح على المستعمل
#   aide        : توضيح يظهر تحت السّؤال (اختياري)
#   champs      : خانة أو خانتان، لكلّ واحدة cle و label و exemple و obligatoire
#   type        : 'config' (الافتراضي) أو 'numeros' للخطوة الأخيرة

ETAPES_INSTALLATION = (
    # ── الخطوة 1 : اسم المركز — قائمة منسدلة بالمراكز الأربعة والعشرين ──────
    {
        'numero': 1,
        'titre': 'اسم المركز',
        'question': 'ما هو اسم مركزكم؟',
        'aide': 'يظهر هذا الاسم في المراسلات والقائمة الإسميّة والبطاقة البيداغوجيّة.',
        'champs': (
            {'cle': 'nom_centre', 'label': 'اسم المركز',
             'type_champ': 'select',
             'options': CENTRES_FORMATION,
             'allow_new': True, 'key_extras': 'extras_centres',
             'exemple': 'مركز التكوين الديواني بالقصرين', 'obligatoire': True},
        ),
    },
    # ── الخطوة 2 : رمز المركز — END-3-XX-XX ─────────────────────────────────
    {
        'numero': 2,
        'titre': 'رمز المركز',
        'question': 'ما هو رمز المركز؟',
        'aide': 'يظهر رمز المركز في مراجع المراسلات. '
                'أدخل الجزأين الأخيرين: مثلا 01 ثمّ 02 ليكون الرّمز END-3-01-02.',
        'type': 'code_centre',
        'champs': (
            {'cle': 'ref_prefix', 'label': 'رمز المركز',
             'type_champ': 'code_centre', 'obligatoire': True},
        ),
    },
    # ── الخطوة 3 : المدينة — قائمة منسدلة بالولايات ─────────────────────────
    {
        'numero': 3,
        'titre': 'المدينة',
        'question': 'في أيّ مدينة يوجد المركز؟',
        'aide': 'تُستعمل في سطر التّاريخ أعلى كلّ مراسلة: «القصرين في 12 جانفي 2026».',
        'champs': (
            {'cle': 'ville_centre', 'label': 'المدينة',
             'type_champ': 'select',
             'options': WILAYAS,
             'allow_new': True, 'key_extras': 'extras_wilayas',
             'exemple': 'القصرين', 'obligatoire': True},
        ),
    },
    # ── الخطوة 4 : المسؤول الممضي — رتبة من قائمة + اسم نصّي ───────────────
    {
        'numero': 4,
        'titre': 'المسؤول الممضي',
        'question': 'من يُمضي مراسلات المركز؟',
        'aide': '⚠ يظهر هذا الاسم أسفل كلّ وثيقة يُصدرها المركز. '
                'يمكن تغييره لاحقا من صفحة «الإعدادات» عند تغيّر المسؤول.',
        'champs': (
            {'cle': 'titre_responsable', 'label': 'الرّتبة',
             'type_champ': 'select',
             'options': GRADES_RESPONSABLE,
             'allow_new': False,
             'exemple': 'النقيب', 'obligatoire': True},
            {'cle': 'nom_responsable', 'label': 'الاسم واللّقب',
             'type_champ': 'text',
             'exemple': 'الاسم الكامل', 'obligatoire': True},
        ),
    },
    # ── الخطوة 5 : وحدة الحرس — قائمة بالوحدات السّتّ ──────────────────────
    {
        'numero': 5,
        'titre': 'وحدة الحرس الدّيواني',
        'question': 'ما هي وحدة الحرس الدّيواني المرجعيّة؟',
        'aide': '',
        'champs': (
            {'cle': 'unite_garde', 'label': 'وحدة الحرس',
             'type_champ': 'select',
             'options': UNITES_GARDE,
             'allow_new': True, 'key_extras': 'extras_unites_garde',
             'exemple': 'الوحدة الرّابعة للحرس الدّيواني بقفصة', 'obligatoire': False},
        ),
    },
    # ── الخطوة 6 : قاعة التّكوين — قائمة بأربع وعشرين قاعة ─────────────────
    {
        'numero': 6,
        'titre': 'قاعة التّكوين',
        'question': 'ما هي قاعة التّكوين التي تُقترح تلقائيّا عند إنشاء دورة؟',
        'aide': 'مجرّد اقتراح: يبقى تغييرها ممكنا في كلّ دورة.',
        'champs': (
            {'cle': 'lieu_formation_defaut', 'label': 'القاعة',
             'type_champ': 'select',
             'options': SALLES_FORMATION,
             'allow_new': True, 'key_extras': 'extras_salles',
             'exemple': 'مركز التكوين الجهوي بالقصرين', 'obligatoire': False},
        ),
    },
    # ── الخطوة 7 : أرقام انطلاق المراسلات ───────────────────────────────────
    {
        'numero': 7,
        'titre': 'أرقام انطلاق المراسلات',
        'question': 'من أيّ عدد تنطلق كلّ سلسلة من سلسلتَي المراسلات؟',
        'aide': 'إن كان لديكم سجلّ ورقي جار، اكتبوا العدد الذي يلي آخر عدد '
                'أسندتموه بخطّ اليد. وإن كنتم تنطلقون من الصّفر فاتركوا 1. '
                'السّلسلتان مستقلّتان تماما ولا تقترض إحداهما من الأخرى.',
        'type': 'numeros',
        'champs': (
            {'cle': 'numero_depart_interne', 'label': 'أوّل عدد للمراسلات الدّاخليّة',
             'type_champ': 'text', 'exemple': '1', 'obligatoire': True},
            {'cle': 'numero_depart_externe', 'label': 'أوّل عدد للمراسلات الخارجيّة',
             'type_champ': 'text', 'exemple': '1', 'obligatoire': True},
        ),
    },
)

NB_ETAPES = len(ETAPES_INSTALLATION)


def etape_installation(numero):
    """خطوة التّنصيب ذات الرّتبة المطلوبة، أو None إن كانت خارج المجال."""
    try:
        numero = int(numero)
    except (TypeError, ValueError):
        return None
    for etape in ETAPES_INSTALLATION:
        if etape['numero'] == numero:
            return etape
    return None


def champs_obligatoires_manquants(etape, valeurs):
    """أسماء الخانات الوجوبيّة التي بقيت فارغة في هذه الخطوة."""
    manquants = []
    for champ in etape.get('champs', ()):
        if champ.get('obligatoire') and not str(valeurs.get(champ['cle'], '')).strip():
            manquants.append(champ['label'])
    return manquants


def recapitulatif(config):
    """كلّ أجوبة التّنصيب مرتّبة حسب الخطوات، للمراجعة قبل الحفظ النّهائي.

    يُرجع قائمة من (رتبة الخطوة، عنوانها، [(العنوان، القيمة)]) — الخطوة
    العاشرة (الأعداد) لا تُقرأ من config فتُترك للمسار.
    """
    out = []
    for etape in ETAPES_INSTALLATION:
        if etape.get('type') == 'numeros':
            continue
        lignes = [(c['label'], val(config, c['cle'])) for c in etape['champs']]
        out.append((etape['numero'], etape['titre'], lignes))
    return out


# ─── البذر في قاعدة البيانات ──────────────────────────────────────────────────

def seeder(conn, installation_existante):
    """يزرع مفاتيح الهويّة في جدول config.

    `installation_existante` : True إذا كان جدول config موجودا قبل هذا
    التّشغيل، أي أنّنا نرقّي تنصيبا قائما. في هذه الحالة تُزرع قيم القصرين
    التّاريخيّة ويُعتبر التّنصيب منجزا، فيبقى سلوك المنظومة مطابقا تماما.
    في التّنصيب الجديد تُزرع قيم فارغة ويُطلب معالج التّنصيب.

    البذر بـ INSERT OR IGNORE: لا يُلمس أيّ مفتاح ضبطه المستعمل.
    """
    source = dict(DEFAUTS_NATIONAUX)
    if installation_existante:
        source.update(HERITAGE)
        source['installation_faite'] = '1'
    else:
        source.update(DEFAUTS_CENTRE)
        source['installation_faite'] = '0'

    for cle, valeur in source.items():
        conn.execute('INSERT OR IGNORE INTO config (cle, valeur) VALUES (?, ?)',
                     (cle, valeur))

    # رقم الإصدار يُحدَّث دائما (ليس إعدادا يضبطه المستعمل)
    conn.execute('INSERT OR REPLACE INTO config (cle, valeur) VALUES (?, ?)',
                 ('version_app', VERSION_APP))


# ─── اشتقاق الإدارة الجهويّة من وجهة المدير الجهوي ───────────────────────────

def deriver_admin_regionale(destination_dr_val):
    """اشتقاق الإدارة الجهويّة من وجهة مراسلة المدير الجهوي.

    مثال:
        «السيد المدير الجهوي للديوانة بالقصرين»
        → «الإدارة الجهوية للديوانة بالقصرين»

    المنطق: إن وُجد «للديوانة» في الوجهة، أُخذ ما يتبعه حتّى نهاية السطر
    وأُضيف إليه «الإدارة الجهوية». وإلّا تُرجَع سلسلة فارغة.
    """
    import re
    val_clean = (destination_dr_val or '').strip()
    m = re.search(r'(للديوانة\b.*)', val_clean)
    if m:
        return ('الإدارة الجهوية ' + m.group(1).strip()).strip()
    return ''
