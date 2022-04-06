import json
import re
import sys
import tkinter as tk
from pathlib import Path
from tkinter import filedialog
from tkinter import messagebox
from tkinter import ttk
import subprocess
import datetime

import screeninfo

from install_from_config.installer import Installer

if getattr(sys, 'frozen', False):
    DIRECTORY = Path(sys.executable).parent
elif __file__:
    DIRECTORY = Path(__file__).parent


class MainApp(tk.Tk):
    """
    This class contains the main window (page), "container", for
    the GISMOtoolbox application.
    Additional pages in the application are stored under self.frames.
    The container is the parent frame that is passed to other pages.
    self is also passed to the other pages objects and should there be given the name
    "self.controller".
    Toolboxsettings and logfile can be reached in all page objects by calling
    "self.controller.settings" and "self.controller.logfile" respectively.
    """

    # ===========================================================================
    def __init__(self,  *args, **kwargs):
        tk.Tk.__init__(self, *args, **kwargs)
        self.withdraw()
        self.protocol('WM_DELETE_WINDOW', self._quit_toolbox)

        self._installer = None

        self._saves = SaveSelection('install')
        self._build()
        self._saves.load_selection()
        self._load_installer()
        self._set_geometry()
        self.deiconify()

    def _set_geometry(self):
        def_geo = '800x600+50+50'
        geo = self._saves.get('geometry') or def_geo
        if len(screeninfo.get_monitors()) == 1:
            monitor = screeninfo.get_monitors()[0]
            sc, lr, ud = geo.split('+')
            w, h = sc.split('x')
            if lr[0] == '-':
                geo = def_geo
            elif ud[0] == '-':
                geo = def_geo
            elif (int(lr) + int(w)) > monitor.width:
                geo = def_geo
            elif (int(ud) + int(h)) > monitor.height:
                geo = def_geo
        self.geometry(geo)

    def _quit_toolbox(self):
        self._saves.save_selection()
        self._saves.set('geometry', self.geometry())
        self.destroy()  # Closes window
        self.quit()  # Terminates program

    def _build(self):
        self._main_notebook = NotebookWidget(self, frames=['Installera / Uppdatera SHARKtools', 'Backup SHARKtools'])
        install_frame = self._main_notebook('Installera / Uppdatera SHARKtools')
        backup_frame = tk.Frame(self._main_notebook('Backup SHARKtools'))
        backup_frame.grid(row=0, column=0, sticky='nw')
        grid_configure(self, nr_rows=1, nr_columns=1)
        grid_configure(self._main_notebook('Backup SHARKtools'), nr_rows=1, nr_columns=1)

        # INSTALL
        tk.Button(install_frame, text='Välj konfigurationsfil', command=self._ask_config_file).grid(row=0, column=0)
        self._stringvar_config_file = tk.StringVar()
        tk.Label(install_frame, textvariable=self._stringvar_config_file).grid(row=1, column=0)

        self._frame_notebook = tk.Frame(install_frame)
        self._frame_notebook.grid(row=2, column=0, sticky='nw')
        self._notebook = None

        tk.Button(install_frame, text='Installera', command=self._install).grid(row=3, column=0)

        grid_configure(install_frame, nr_rows=4, nr_columns=2)

        self._saves.add('config_file', self._stringvar_config_file)

        # BACKUP
        layout = dict(sticky='nw',
                      padx='5',
                      pady='5')
        tk.Button(backup_frame, text='Sökväg till installationen', command=self._ask_install_root).grid(row=0, column=0, **layout)
        self._stringvar_install_root = tk.StringVar()
        tk.Label(backup_frame, textvariable=self._stringvar_install_root).grid(row=0, column=1, **layout)

        tk.Button(backup_frame, text='Sökväg till backupmapp', command=self._ask_backup_dir).grid(row=1, column=0, **layout)
        self._stringvar_backup_dir = tk.StringVar()
        tk.Label(backup_frame, textvariable=self._stringvar_backup_dir).grid(row=1, column=1, **layout)

        tk.Button(backup_frame, text='Gör backup', command=self._backup).grid(row=2, column=0, **layout)

        grid_configure(backup_frame, nr_rows=3, nr_columns=1)

        self._saves.add('install_root_file', self._stringvar_install_root)
        self._saves.add('backup_dir', self._stringvar_backup_dir)

    def _backup(self):
        date_string = datetime.datetime.now().strftime('%Y%m%d')
        path = Path(DIRECTORY, 'backup.bat')
        install_root = self._stringvar_install_root.get()
        if not install_root:
            messagebox.showwarning('Backup', 'Ogilltig källmapp för backup')
            return
        install_root = Path(install_root)
        if not install_root.exists() or install_root.is_file():
            messagebox.showwarning('Backup', 'Ogilltig källmapp för backup')
            return
        if 'SHARKtools' not in [p.stem for p in install_root.iterdir()]:
            messagebox.showwarning('Installationsmapp', f'Kan inte hitta SHARKtools i valda mapp: {path}')
            return

        backup_dir = self._stringvar_backup_dir.get()
        if not backup_dir:
            messagebox.showwarning('Backup', 'Ogilltig destination för backup')
            return
        backup_dir = Path(backup_dir)
        if not backup_dir.exists() or install_root.is_file():
            messagebox.showwarning('Backup', 'Ogilltig destination för backup')
            return
        subdir = f'backup_{install_root.name}_{date_string}'
        if backup_dir.name != subdir:
            backup_dir = Path(backup_dir, subdir)
        backup_dir.mkdir(parents=True, exist_ok=True)
        if list(backup_dir.iterdir()):
            messagebox.showwarning('Backupmap', f'Backupmappen måste vara tom: {path}')
            return

        with open(path, 'w') as fid:
            fid.write(f'robocopy {install_root} {backup_dir} /s /xd .git .idea venv SHARKtoolbox_install __pycache__')
        subprocess.call([str(path)])
        messagebox.showinfo('Backup', 'Backup klar!!')

    def _ask_backup_dir(self):
        install_directory = self._saves.get('open_install_directory')
        directory = filedialog.askdirectory(initialdir=install_directory)
        if not directory:
            return
        path = Path(directory)
        self._saves.set('open_install_directory', str(path.parent))
        self._stringvar_backup_dir.set(str(path))

    def _ask_install_root(self):
        install_directory = self._saves.get('open_install_directory')
        directory = filedialog.askdirectory(initialdir=install_directory)
        if not directory:
            return
        path = Path(directory)
        self._saves.set('open_install_directory', str(path.parent))
        self._stringvar_install_root.set(str(path))

    def _ask_config_file(self):
        open_directory = self._saves.get('open_directory')
        file_path = filedialog.askopenfilename(initialdir=open_directory,
                                               filetypes=[('yaml config file', '*.yaml')])
        if not file_path:
            return
        path = Path(file_path)
        self._saves.set('open_directory', str(path.parent))
        self._stringvar_config_file.set(str(path))
        self._load_installer()

    def _load_installer(self):
        config_file = self._stringvar_config_file.get()
        if not config_file or not Path(config_file).exists():
            return
        self._installer = Installer(config_file)
        self._update_notebook()

    def _update_notebook(self):
        if self._notebook:
            self._notebook.destroy()
        config = self._installer.config
        dirs = ['General'] + [key for key in sorted(config) if type(config[key])==list]
        self._notebook = NotebookWidget(self._frame_notebook, frames=dirs, row=0, column=0)
        grid_configure(self._frame_notebook, nr_rows=1, nr_columns=1)
        general_index = 0
        general_frame = tk.Frame(self._notebook('General'))
        general_frame.grid(sticky='nw')
        for key, value in config.items():
            if type(value) == list:
                frame = tk.Frame(self._notebook(key))
                frame.grid(sticky='nw')
                for r, item in enumerate(value):
                    tk.Label(frame, text=str(item)).grid(row=r, column=0, sticky='nw')
                grid_configure(self._notebook(key), nr_rows=r+1)
            else:
                tk.Label(general_frame, text=key).grid(row=general_index, column=0, sticky='nw')
                tk.Label(general_frame, text=value).grid(row=general_index, column=1, sticky='nw')
                general_index += 1
        grid_configure(self._notebook('General'), nr_rows=general_index + 1, nr_columns=2)

    def _install(self):
        if not self._installer:
            return
        self._installer.create_batch_file()
        self._installer.run_batch_file()
        self._installer.create_pth_file()
        self._installer.create_run_file()
        messagebox.showinfo('Installera', 'Installationen är klar!')


class NotebookWidget(ttk.Notebook):

    def __init__(self,
                 parent,
                 frames=[],
                 notebook_prop={},
                 place=(),
                 **kwargs):

        self.frame_list = frames
        self.notebook_prop = {}
        self.notebook_prop.update(notebook_prop)

        self.grid_notebook = {'padx': 5,
                              'pady': 5,
                              'sticky': 'nsew'}
        self.grid_notebook.update(kwargs)

        ttk.Notebook.__init__(self, parent, **self.notebook_prop)
        if place:
            self.place(relx=place[0], rely=place[1], anchor=tk.CENTER)
        else:
            self.grid(**self.grid_notebook)

        self.frame_dict = {}
        self._set_frame()

    def __call__(self, tab):
        """ Returnf a referens to the frame with the provided name"""
        return self.frame_dict.get(tab)

    # ===========================================================================
    def _set_frame(self):

        for frame in self.frame_list:
            name = frame.strip(u'?')
            name = u'frame_' + name.lower().replace(u' ', u'_').replace('ä', 'a').replace('å', 'a').replace('ö', 'o')
            notebook_frame = tk.Frame(self)
            setattr(self, name, notebook_frame)
            self.add(notebook_frame, text=frame)
            self.frame_dict[frame] = notebook_frame
            #            grid_configure(self.frame_dict[frame]) # Done when setting frame content
            grid_configure(notebook_frame)
        grid_configure(self)

        # ===========================================================================

    def select_frame(self, frame):
        if frame in self.frame_dict:
            self.select(self.frame_dict[frame])
            return True
        else:
            return False

    def get_selected_tab(self):
        return self.tab(self.select(), "text")

    # ===========================================================================
    def get_frame(self, frame):
        return self.frame_dict[frame]

    def set_state(self, state, *args, rest=None):
        if rest:
            for frame in self.frame_list:
                self.tab(self.frame_dict[frame], state=rest)
        if not args:
            args = self.frame_list
        for frame in args:
            self.tab(self.frame_dict[frame], state=state)


class Saves:

    def __init__(self):
        self.file_path = Path(DIRECTORY, 'install_from_config_saves.json')
        self.data = {}
        self._load()

    def _load(self):
        """
        Loads dict from json
        :return:
        """
        if self.file_path.exists():
            with open(self.file_path) as fid:
                self.data = json.load(fid)

    def _save(self):
        """
        Writes information to json file.
        :return:
        """
        with open(self.file_path, 'w') as fid:
            json.dump(self.data, fid, indent=4, sort_keys=True)

    def set(self, key, value):
        self.data[key] = value
        self._save()

    def get(self, key, default=''):
        return self.data.get(key, default)


class SaveSelection:
    _saves = Saves()
    _saves_id_key = None
    _component_to_store = {}

    def __init__(self, saves_id_key):
        self._saves_id_key = saves_id_key

    def add(self, key, component):
        self._component_to_store[key] = component

    def get(self, key):
        data = self._saves.get(self._saves_id_key, {})
        return data.get(key)

    def set(self, key, value):
        data = self._saves.get(self._saves_id_key, {})
        data[key] = value
        self._saves.set(self._saves_id_key, data)

    def save_selection(self):
        data = {}
        for name, comp in self._component_to_store.items():
            try:
                data[name] = comp.get()
            except AttributeError:
                data[name] = comp
        self._saves.set(self._saves_id_key, data)

    def load_selection(self, **kwargs):
        data = self._saves.get(self._saves_id_key, {})
        for name, comp in self._component_to_store.items():
            try:
                value = data.get(name, None)
                if value is None:
                    continue
                comp.set(value)
            except AttributeError:
                pass


def grid_configure(frame, nr_rows=1, nr_columns=1, **kwargs):
    """
    Updated 20180825

    Put weighting on the given frame. Put weighting on the number of rows and columns given.
    kwargs with tag "row"(r) or "columns"(c, col) sets the number in tag as weighting.
    Example:
        c1=2 sets frame.grid_columnconfigure(1, weight=2)
    """
    row_weight = {}
    col_weight = {}

    # Get information from kwargs
    for key, value in kwargs.items():
        rc = int(re.findall('\d+', key)[0])
        if 'r' in key:
            row_weight[rc] = value
        elif 'c' in key:
            col_weight[rc] = value

            # Set weight
    for r in range(nr_rows):
        frame.grid_rowconfigure(r, weight=row_weight.get(r, 1))

    for c in range(nr_columns):
        frame.grid_columnconfigure(c, weight=col_weight.get(c, 1))


if __name__ == '__main__':
    app = MainApp()
    app.focus_force()
    app.mainloop()
