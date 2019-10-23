
import os
import tkinter as tk
from tkinter import ttk
from tkinter import filedialog
from tkinter import messagebox
from project import Project

class App(tk.Tk):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.protocol(u'WM_DELETE_WINDOW', self._quit_toolbox)

        tk.Tk.wm_title(self, 'SHARKtools installation')

        self.project = Project()
        self.log = self.project.log

        self._set_frame()

        self.resizable(False, False)

        self._set_labelframe_root_dir()
        self._set_labeleframe_python_path()
        self._set_labaleframe_plugins()
        self._set_labaleframe_steps()

    def _set_frame(self):
        k = dict(padx=10,
                 pady=10,
                 sticky='nsew')
        self.labelframe_root_dir = tk.LabelFrame(self, text='Var vill du installera SHARKtools?')
        self.labelframe_root_dir.grid(row=0, column=0, **k)

        self.labeleframe_python_path = tk.LabelFrame(self, text='Vilken är sökvägen till Python36?')
        self.labeleframe_python_path.grid(row=1, column=0, **k)

        self.labelframe_plugins = tk.LabelFrame(self, text='Vilka plugins vill du installera?', fg='red')
        self.labelframe_plugins.grid(row=2, column=0, **k)

        self.labelframe_steps = tk.LabelFrame(self, text='Vilka steg vill du göra?')
        self.labelframe_steps.grid(row=3, column=0, **k)

        self.button_continue = tk.Button(self, text='Fortsätt', command=self._continue)
        self.button_continue.grid(row=4, column=0, **k)

        self.stringvar_info = tk.StringVar()
        self.label_info = tk.Label(self, textvariable=self.stringvar_info)
        self.label_info.grid(row=5, column=0, **k)

        grid_configure(self)
        grid_configure(self.labelframe_root_dir)
        grid_configure(self.labelframe_plugins)
        grid_configure(self.labelframe_steps)

    def _set_labelframe_root_dir(self):
        frame = self.labelframe_root_dir
        k = dict(padx=10,
                 pady=10,
                 sticky='nsew')

        self.button_get_root_dir = tk.Button(frame, text='Välj', command=self._get_root_dir)
        self.button_get_root_dir.grid(row=0, column=0, **k)
        self.stringvar_root_dir = tk.StringVar()
        self.label_root_dir = tk.Label(frame, textvariable=self.stringvar_root_dir)
        self.label_root_dir.grid(row=1, column=0, **k)
        self.stringvar_root_dir.set(self.project.directory)

    def _set_labeleframe_python_path(self):
        frame = self.labeleframe_python_path
        k = dict(padx=10,
                 pady=10,
                 sticky='nsew')

        self.button_get_python_path = tk.Button(frame, text='Välj', command=self._get_python_path)
        self.button_get_python_path.grid(row=0, column=0, **k)
        self.stringvar_python_path = tk.StringVar()
        self.label_python_path = tk.Label(frame, textvariable=self.stringvar_python_path)
        self.label_python_path.grid(row=1, column=0, **k)
        text = self.project.python_exe
        if self.project.python_exe is None:
            text = '<No python.exe found>'
        self.stringvar_python_path.set(text)

    def _set_labaleframe_plugins(self):
        frame = self.labelframe_plugins
        k = dict(padx=10,
                 pady=5,
                 sticky='nsew')
        self.boolvars_plugins = {}
        self.checkbuttons_plugins = {}
        r = 0
        for plugin in self.project.available_plugins:
            self.boolvars_plugins[plugin] = tk.BooleanVar()
            self.checkbuttons_plugins[plugin] = tk.Checkbutton(frame, text=plugin, variable=self.boolvars_plugins[plugin])
            self.checkbuttons_plugins[plugin].grid(row=r, column=0, **k)
            r += 1

    def _set_labaleframe_steps(self):
        frame = self.labelframe_steps
        k = dict(padx=10,
                 pady=5,
                 sticky='nsew')
        items = list(self.project.steps)
        self.steps_widget = CheckbuttonWidget(frame,
                                              items=items,
                                              pre_checked_items=items,
                                              **k)

    def _continue(self):
        """
        Makes some checks and runs all steps.
        :return:
        """
        steps_to_run = self.steps_widget.get_checked_item_list()

        # Add plugins
        selected_plugins = [plugin for plugin in self.boolvars_plugins if self.boolvars_plugins[plugin].get()]
        for step in steps_to_run:
            if 'miljö' in step:
                python_path = self.stringvar_python_path.get()
                if not python_path or not os.path.exists(python_path):
                    messagebox.showinfo('Python', f'Kan inte hitta python.exe!\n{python_path}')
                    return

                if not selected_plugins:
                    messagebox.showinfo('Plugins', 'Du har inte valt någon plugin!')
                    return

        self.project.select_plugins(selected_plugins)

        # Setup project
        self.project.setup_project()

        self.label_info.config(fg='red')
        bg_color = self.button_continue.cget('bg')
        self.button_continue.config(bg='red', text='Installerar...')
        # Run steps
        for step in steps_to_run:
            words = step.split()
            words[0] = words[0] + 'r'
            text = ' '.join(words) + '...'
            self.stringvar_info.set(text)
            self.label_info.update_idletasks()
            self.project.run_step(step)

        self.button_continue.config(bg=bg_color, text='Installera')

        self.label_info.config(fg='green')
        self.stringvar_info.set('KLART!')

    def _get_root_dir(self):
        directory = filedialog.askdirectory()
        if not directory:
            directory = ''
        self.project.directory = directory
        self.stringvar_root_dir.set(self.project.directory)

    def _get_python_path(self):
        file_path = filedialog.askopenfilename(filetypes=[('Python exicutable', '*.exe')])
        if not file_path:
            return
        if not file_path.endswith('python.exe'):
            self.log.warning('Not a valid python.exe file')
            messagebox.showwarning('Select python.exe', 'Not a valid python path!')
            return
        self.project.set_python_path(file_path)
        self.stringvar_python_path.set(self.project.python_exe)

    def _quit_toolbox(self):
        self.destroy()  # Closes window
        self.quit()  # Terminates program


class CheckbuttonWidget(tk.Frame):
    """
    Frame to hold tk.Checkbuttons.
    Names of checkbuttons are listed in "items".
    Option to:
        include a "Select all" checkbutton at the bottom
        allow simular parameters to be selected (ex. SALT_BTL and SALT_CTD can not be checked att the same time if
            allow_simular_parameters_to_be_checked=False
    """

    def __init__(self,
                 parent,
                 items=[],
                 pre_checked_items=[],
                 nr_rows_per_column=10,
                 include_select_all=True,
                 allow_simular_parameters_to_be_checked=True,
                 colors={},
                 sort_items=False,
                 prop_cbuttons={},
                 grid_cbuttons={},
                 prop_frame={},
                 font=(),
                 **kwargs):

        # Save inputs
        self.prop_frame = {}
        self.prop_frame.update(prop_frame)

        self.grid_frame = {'row': 0,
                           'column': 0,
                           'sticky': 'w',
                           'rowspan': 1,
                           'columnspan': 1}
        self.grid_frame.update(kwargs)

        self.prop_cbuttons = {}
        self.prop_cbuttons.update(prop_cbuttons)

        self.grid_cbuttons = {'sticky': 'w',
                              'padx': 2,
                              'pady': 0}
        self.grid_cbuttons.update(grid_cbuttons)

        self.pre_checked_items = pre_checked_items[:]
        self.nr_rows_per_column = nr_rows_per_column
        self.include_select_all = include_select_all
        self.allow_simular_parameters_to_be_checked = allow_simular_parameters_to_be_checked
        self.colors = colors

        if sort_items:
            self.items = sorted(items)
        else:
            self.items = items[:]

        self.cbutton = {}
        self.booleanvar = {}
        self.disabled_list = []

        # Create frame
        tk.Frame.__init__(self, parent, **self.prop_frame)
        self.grid(**self.grid_frame)

        self._set_frame()

    # ===========================================================================
    def _set_frame(self):
        r = 0
        c = 0

        for item in self.items:
            self.booleanvar[item] = tk.BooleanVar()
            self.cbutton[item] = tk.Checkbutton(self,
                                                text=item,
                                                variable=self.booleanvar[item],
                                                command=lambda item=item: self._on_select_item(item),
                                                **self.prop_cbuttons)
            self.cbutton[item].grid(row=r, column=c, **self.grid_cbuttons)
            if item in self.pre_checked_items:
                self.booleanvar[item].set(True)
            if item in self.colors:
                self.cbutton[item].config(fg=self.colors[item])
            r += 1
            if not r % self.nr_rows_per_column:
                c += 1
                r = 0

        if self.include_select_all:
            prop = dict((k, v) for k, v in self.prop_cbuttons.items() if k in ['padx', 'pady'])
            ttk.Separator(self, orient=u'horizontal').grid(row=r, column=c, sticky=u'ew', **prop)
            r += 1
            self.booleavar_select_all = tk.BooleanVar()
            self.cbutton_select_all = tk.Checkbutton(self,
                                                     text='Välj alla',
                                                     variable=self.booleavar_select_all,
                                                     command=self._on_select_all,
                                                     **self.prop_cbuttons)
            self.cbutton_select_all.grid(row=r, column=c, **self.grid_cbuttons)

            if self.items == self.pre_checked_items:
                self.booleavar_select_all.set(True)

    # ===========================================================================
    def _on_select_item(self, source_item):

        if not self.allow_simular_parameters_to_be_checked:
            if self.booleanvar[source_item].get():
                for item in self.items:
                    if self.booleanvar[item].get() and item != source_item and item.startswith(source_item[:4]):
                        self.cbutton[item].deselect()

        if self.include_select_all:
            if all([self.booleanvar[item].get() for item in self.items]):
                self.cbutton_select_all.select()
            else:
                self.cbutton_select_all.deselect()

    # ===========================================================================
    def _on_select_all(self):
        if self.booleavar_select_all.get():
            for item in self.items:
                if item not in self.disabled_list:
                    self.cbutton[item].select()
        else:
            for item in self.items:
                self.cbutton[item].deselect()

    # ===========================================================================
    def _add_to_disabled(self, item):
        if item not in self.disabled_list:
            self.disabled_list.append(item)
        self._check_disable_list()

    # ===========================================================================
    def _remove_from_disabled(self, item):
        if item in self.disabled_list:
            self.disabled_list.pop(self.disabled_list.index(item))
            self._check_disable_list()

    # ===========================================================================
    def _check_disable_list(self):
        # print('%%'*50)
        # print(sorted(self.disabled_list))
        # print(sorted(self.items))
        try:
            if not self.disabled_list:
                self.cbutton_select_all.config(state=u'normal')
            elif sorted(self.disabled_list) == sorted(self.items):
                self.cbutton_select_all.config(state=u'disabled')
            else:
                self.cbutton_select_all.config(state=u'normal')
        except:
            pass

    # ===========================================================================
    def reset_selection(self):
        for item in self.items:
            self.cbutton[item].deselect()
            self.activate(item)
        try:
            self.cbutton_select_all.deselect()
        except:
            pass

    def select(self, item):
        if item in self.cbutton:
            self.cbutton[item].select()

    # ===========================================================================
    def deactivate(self, item):
        self.cbutton[item].deselect()
        self.cbutton[item].config(state=u'disabled')
        self._add_to_disabled(item)

    def deactivate_all(self):
        for item in self.cbutton:
            self.deactivate(item)

    # ===========================================================================
    def activate(self, item):
        self.cbutton[item].config(state=u'normal')
        self._remove_from_disabled(item)

    def activate_all(self):
        for item in self.cbutton:
            self.activate(item)

    def set_value(self, values):
        """
        Sets values. First diactivate and thena activate values if string or list.
        :param values:
        :return:
        """
        self.reset_selection()
        if type(values) == str:
            values = [values]

        for item in values:
            if item in self.cbutton:
                self.select(item)

    def get_value(self):
        """
        Returns all checkt items as a list.
        :return:
        """
        return self.get_checked_item_list()

    # ===========================================================================
    def get_checked_item_list(self):
        return_list = []
        for item in self.items:
            if self.booleanvar[item].get():
                return_list.append(item)

        return return_list

    # ===========================================================================
    def change_color(self, item, new_color):
        self.cbutton[item].config(fg=new_color)
        self.cbutton[item].update_idletasks()
        self.cbutton[item].update()
        self.update()
        self.update_idletasks()


def grid_configure(frame, rows={}, columns={}):
    """
    Put weighting on the given frame. Rows an collumns that ar not in rows and columns will get weight 1.
    """
    for r in range(30):
        if r in rows:
            frame.grid_rowconfigure(r, weight=rows[r])
        else:
            frame.grid_rowconfigure(r, weight=1)

    for c in range(30):
        if c in columns:
            frame.grid_columnconfigure(c, weight=columns[c])
        else:
            frame.grid_columnconfigure(c, weight=1)


if __name__ == '__main__':
    app = App()
    app.mainloop()