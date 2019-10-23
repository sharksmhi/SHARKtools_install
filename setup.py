import cx_Freeze
import sys
import matplotlib

base = None

if sys.platform == 'win32':
    base = 'Win32GUI'

executables = [cx_Freeze.Executable('test_exe.py',
                                    base=base)]

cx_Freeze.setup(
    name='SHARKtoolbox',
    options={'build_exe': {'packages': ['Tkinter',
                                        'matplotlib',
                                        'mpl_toolkits.basemap'],
                           'include_files': []}},
    version='0.4.2',
    description='SHARKtoolbox, made by Shd!',
    executables=executables)