# -*- mode: python ; coding: utf-8 -*-
"""Recette PyInstaller — produit un exécutable Windows autonome.

Construction (sur une machine Windows, depuis le dossier du projet) :
    pip install pyinstaller
    pyinstaller formation_kasserine.spec

Le résultat se trouve dans dist/FormationKasserine/ : ce dossier se copie tel
quel sur n'importe quel poste Windows, SANS installer Python.

1.0 : deux exécutables dans le même dossier —
  • FormationKasserine.exe : le programme, SANS console (fenêtre propre) ;
  • RecupererAdmin.exe     : l'outil console de récupération du مشرف عام.

Le dossier `data/` n'est volontairement PAS embarqué : la base de données, les
sauvegardes et les journaux sont créés à côté de l'exécutable au premier
lancement, ce qui évite d'écraser les données lors d'une mise à jour.
"""

block_cipher = None
import os

HIDDEN = [
    'waitress',
    'arabic_reshaper',
    'bidi.algorithm',
    'reportlab.pdfbase._fontdata_enc_winansi',
    'reportlab.pdfbase._fontdata_enc_macroman',
    'reportlab.pdfbase._fontdata_widths_helvetica',
    # v1.4 : accès aux données découpé par domaine (importés par core.database)
    'core.db', 'core.db._base', 'core.db.sauvegarde', 'core.db.registre',
    'core.db.referentiels', 'core.db.mkowin', 'core.db.mawad', 'core.db.programmes',
    'core.db.utilisateurs', 'core.db.mustahaqqat', 'core.db.statistiques',
    'core.db.khalas', 'core.db.schema', 'core.db.rapports', 'core.db.suggestions',
    # v1.7 : générateurs PDF par document, chemins, Word, شهادات, سجلّ, استرجاع
    'core.pdf', 'core.pdf.mourasalat', 'core.pdf.pieces_word', 'core.pdf.bataqa',
    'core.pdf.memo', 'core.chemins', 'core.recuperation', 'core.docx_ecrivain',
    'core.dossier_dorra', 'core.dossier_word', 'core.pdf_shahadat', 'core.pdf_registre',
    # V3 / 1.0 : التّقارير, مرآة, إشعارات, دليل, lanceur
    'core.miroir', 'core.notifications', 'core.guide', 'core.lanceur',
    'core.rapports_moteur', 'core.rapport_ecrit', 'core.rapports_graphiques',
    'core.rapports_details', 'core.fiche_participant', 'core.classification',
    'core.rapports_defauts',
    # 1.0 : fenêtre native
    'webview', 'webview.platforms.winforms', 'webview.platforms.edgechromium', 'clr',
]
EXCLUDES = ['tkinter', 'matplotlib', 'numpy', 'pytest']
# 1.0 : icône Windows multi-tailles (16 → 256 px), tirée du شعار de l'école
ICONE = ('static/images/icone.ico' if os.path.exists('static/images/icone.ico')
         else 'static/images/logo.jpg' if os.path.exists('static/images/logo.jpg') else None)

a = Analysis(
    ['lancer_app.py'],
    pathex=['.'],
    binaries=[],
    datas=[
        ('templates', 'templates'),
        ('static',    'static'),
        ('fonts',     'fonts'),
    ],
    hiddenimports=HIDDEN,
    hookspath=[],
    runtime_hooks=[],
    excludes=EXCLUDES,
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)
b = Analysis(
    ['recuperer_admin.py'],
    pathex=['.'],
    binaries=[],
    datas=[],
    hiddenimports=['core.recuperation', 'core.chemins'],
    hookspath=[],
    runtime_hooks=[],
    excludes=EXCLUDES + ['webview', 'clr'],
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)
pyz_b = PYZ(b.pure, b.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='FormationKasserine',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,                # 1.0 : plus de console, le programme a SA fenêtre
    icon=ICONE,
)
exe_b = EXE(
    pyz_b,
    b.scripts,
    [],
    exclude_binaries=True,
    name='RecupererAdmin',
    debug=False,
    strip=False,
    upx=True,
    console=True,                 # outil en console : il pose des questions
    icon=ICONE,
)

coll = COLLECT(
    exe, a.binaries, a.zipfiles, a.datas,
    exe_b, b.binaries, b.zipfiles, b.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='FormationKasserine',
)
