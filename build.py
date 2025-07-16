import PyInstaller.__main__

#
# PyInstaller.__main__.run([
#     'install_update.py', '-F'
# ])

print('======================')

PyInstaller.__main__.run([
    'cam_gige_test.py',
    "--onedir",
    "--contents-directory=.",
    '--noconfirm',
    '--add-data=static:static',
    '--add-data=save_images:save_images',
    '--add-data=settings.xml:.',
    '--add-data=icon:icon',
    '--icon=icon/icon.ico',
    '--noconsole',
    '--name=Metrol_Smartek_GigE.exe'
])
# '--noconsole',