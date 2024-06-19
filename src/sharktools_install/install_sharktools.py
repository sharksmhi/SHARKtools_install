import datetime
import logging.handlers
import pathlib
import re
import subprocess
import sys

import flet as ft

logger = logging.getLogger(__name__)

if getattr(sys, 'frozen', False):
    THIS_DIRECTORY = pathlib.Path(sys.executable).parent
else:
    THIS_DIRECTORY = pathlib.Path(__file__).parent

COLORS = dict(
    processing='#453db3',
    pre_system='#953db3',

)


def get_plugin_color(plugin: str) -> str:
    for plug, color in COLORS.items():
        if plug in plugin:
            return color
    return '#555555'


def get_banner_color(status='bad'):
    if status == 'good':
        return '#3db847'
    elif status == 'working':
        return '#e9f562'
    return '#f73131'


class InstallSHARKtools:

    def __init__(self):
        self._wheel_paths = {}
        self._python_exe_path: pathlib.Path | None = None
        self._python_version: str | None = None
        self._install_root_directory: pathlib.Path | None = None
        self._install_directory: pathlib.Path | None = None

        self._install_info = []

        self._selected_plugins = {}

        self._save_wheel_paths()
        self._try_to_find_python_exe()

    def install(self):
        self._install_info.append(f'Installerar i mapp: {self.install_directory}')
        self._create_batch_environment_file()
        self._install_info.append(f'Använder pythonversion: {self._python_version} ({self._python_exe_path})')
        self._run_batch_environment_file()
        self._create_batch_install_plugins_file()
        self._run_batch_install_plugins_file()
        self._create_run_files()
        self._create_summary_file()

    def set_install_root_directory(self, root_path: pathlib.Path | str) -> None:
        if not root_path:
            raise NotADirectoryError(root_path)
        path = pathlib.Path(root_path)
        if not path.exists():
            raise NotADirectoryError(path)
        self._install_root_directory = path
        path = self._install_root_directory / f"SHARKtools_{datetime.datetime.now().strftime('%Y%m%d')}"
        # if path.exists():
        #     raise FileExistsError(f'Installationsmappen finns redan: {path}')
        path.mkdir(exist_ok=True)
        self._install_directory = path

    @property
    def install_directory(self):
        if not self._install_directory:
            raise NotADirectoryError('Ingen installationsmapp vald!')
        return self._install_directory

    @property
    def python_exe_path(self) -> pathlib.Path | None:
        return self._python_exe_path

    @python_exe_path.setter
    def python_exe_path(self, path: str | pathlib.Path):
        path = pathlib.Path(path)
        if not path.exists():
            raise FileExistsError(path)
        self._python_exe_path = path

    @property
    def plugins(self):
        return sorted(self._wheel_paths)

    def get_plugin_versions(self, plugin: str):
        return sorted(self._wheel_paths[plugin])

    def set_plugins(self, **kwargs: dict[str, list | str]) -> None:
        self._check_set_plugins(**kwargs)
        self._selected_plugins = kwargs

    def _check_set_plugins(self, **kwargs: dict[str, str]) -> None:
        for plugin, version in kwargs.items():
            if plugin not in self._wheel_paths:
                raise KeyError(f'Ogilltig plugin: {plugin}')
            if version not in self._wheel_paths[plugin]:
                raise KeyError(f'Ogilltig version för {plugin}: {version}')

    @property
    def _batch_file_create_venv(self) -> pathlib.Path:
        return self._install_files_directory / 'create_venv.bat'

    @property
    def _batch_file_install_plugins(self) -> pathlib.Path:
        return self._install_files_directory / 'install_plugins.bat'

    @property
    def batch_file_run(self) -> pathlib.Path:
        return self._install_directory / 'start_sharktools.bat'

    @property
    def summary_file_path(self) -> pathlib.Path:
        return self._install_files_directory / 'summary.txt'

    @property
    def pip_freeze_file_path(self) -> pathlib.Path:
        return self._install_files_directory / 'python_packages.txt'

    @property
    def _main_python_file_path(self) -> pathlib.Path:
        return self._install_directory / 'main.py'

    @property
    def _install_files_directory(self) -> pathlib.Path:
        path = self.install_directory / '_install'
        path.mkdir(exist_ok=True)
        return path

    @property
    def _venv_directory(self) -> pathlib.Path:
        return self.install_directory / 'venv'

    def _create_batch_environment_file(self):

        if not self.python_exe_path:
            return

        lines = []

        disk = str(self._venv_directory.parent)[0]
        # Browse to disk
        lines.append(f'{disk}:')

        # Go to python environment directory
        lines.append(f'cd {self._install_directory}')

        # Create environment
        lines.append(f'call {self._python_exe_path} -m venv venv')

        with open(self._batch_file_create_venv, 'w') as fid:
            fid.write('\n'.join(lines))

    def _run_batch_environment_file(self):
        subprocess.run([str(self._batch_file_create_venv)])

    def _create_batch_install_plugins_file(self):
        lines = []
        # Activate venv
        lines.append(f'call {self._venv_directory}/Scripts/activate')

        lines.append(f'python.exe -m pip install --upgrade pip')

        # Add plugins
        for plugin, version in self._selected_plugins.items():
            path = self._wheel_paths[plugin][version]
            lines.append(f'pip install {path}')
            self._install_info.append(f'Installerar plugin {path}')

        lines.append(f'pip freeze > {self.pip_freeze_file_path}')

        with open(self._batch_file_install_plugins, 'w') as fid:
            fid.write('\n'.join(lines))

    def _run_batch_install_plugins_file(self):
        subprocess.run([str(self._batch_file_install_plugins)])

    def _create_run_files(self):
        self._create_main_python_file()
        self._create_batch_run_file()

    def _create_main_python_file(self):
        lines = []
        lines.append('import sharktools')
        lines.append('sharktools.run_app()')
        with open(self._main_python_file_path, 'w') as fid:
            fid.write('\n'.join(lines))

    def _create_batch_run_file(self):
        lines = []
        # Activate venv
        lines.append(f'call {self._venv_directory}/Scripts/activate')

        lines.append(f'python {self._main_python_file_path}')

        with open(self.batch_file_run, 'w') as fid:
            fid.write('\n'.join(lines))

    def _create_summary_file(self):
        with open(self.summary_file_path, 'w') as fid:
            fid.write('\n'.join(self._install_info))

    def _save_wheel_paths(self) -> None:
        """Looks in program directory and save all wheel paths"""
        self._wheel_paths = {}
        for path in THIS_DIRECTORY.iterdir():
            if path.suffix != '.whl':
                continue
            name, version, rest = path.stem.split('-', 2)
            self._wheel_paths.setdefault(name, {})
            self._wheel_paths[name][version] = path

    def _try_to_find_python_exe(self) -> None:
        roots = [pathlib.Path('C:/'), pathlib.Path('C:/python/')]
        for root in roots:
            if not root.exists():
                continue
            # Searching C: for python 3.11
            for path in root.iterdir():
                if 'python' not in path.name.lower():
                    continue
                identify_path = path / 'Scripts' / 'pip3.11.exe'
                if not identify_path.exists():
                    continue
                self._python_exe_path = path / 'python.exe'
                self._save_python_version(path)
                return

    def _save_python_version(self, python_root_dir: pathlib.Path) -> None:
        self._python_version = None
        news_path = python_root_dir / 'NEWS.txt'
        if not  news_path.exists():
            return
        with open(news_path) as fid:
            for line in fid:
                if line.startswith("What's New"):
                    answer = re.search('[0-9.]+', line)
                    if answer:
                        self._python_version = answer.group()
                        return


class FletApp:
    def __init__(self, log_in_console=False):
        self._log_in_console = log_in_console
        self.page = None
        self.file_picker = None

        self._install = InstallSHARKtools()

        self._plugins_selection = {}
        self._toggle_buttons = []

        self._dont_install_string = 'Installera inte'

        self.app = ft.app(target=self.main)

    @property
    def _log_directory(self):
        path = pathlib.Path(pathlib.Path.home(), 'logs')
        path.mkdir(parents=True, exist_ok=True)
        return path

    def main(self, page: ft.Page):
        self.page = page
        self.page.title = 'Installera SHARKtools'
        self.page.window_height = 600
        self.page.window_width = 1000
        self._initiate_pickers()
        self._build()
        self._initiate_banner()

        self._set_default_python_version()
        self._set_default_install_root_directory()

    def update_page(self):
        self.page.update()

    def _initiate_pickers(self):
        self._python_exe_picker = ft.FilePicker(on_result=self._on_pick_python_exe)
        self._install_root_directory_picker = ft.FilePicker(on_result=self._on_pick_install_root_dir)

        self.page.overlay.append(self._python_exe_picker)
        self.page.overlay.append(self._install_root_directory_picker)

    def _initiate_banner(self):
        self.banner_content = ft.Column()

        self.page.banner = ft.Banner(
            leading=ft.Icon(ft.icons.WARNING_AMBER_ROUNDED, color=ft.colors.AMBER, size=40),
            content=self.banner_content,
            force_actions_below=True,
            actions=[
                ft.TextButton("OK!", on_click=self._close_banner),
            ],
        )

    def _set_banner(self, color):
        self.banner_content = ft.Column()

        self.page.banner = ft.Banner(
            # bgcolor=ft.colors.AMBER_100,
            bgcolor=color,
            leading=ft.Icon(ft.icons.WARNING_AMBER_ROUNDED, color=ft.colors.AMBER, size=40),
            content=self.banner_content,
            force_actions_below=True,
            actions=[
                ft.TextButton("OK!", on_click=self._close_banner),
            ],
        )

    def _disable_toggle_buttons(self):
        for btn in self._toggle_buttons:
            btn.disabled = True
            btn.update()

    def _enable_toggle_buttons(self):
        for btn in self._toggle_buttons:
            btn.disabled = False
            btn.update()

    def _close_banner(self, e=None):
        if not self.page.banner.open:
            return
        self.page.banner.open = False
        self.page.update()

    # def _show_banner(self, e=None):
    def _show_banner(self):
        self.page.banner.open = True
        self.page.update()

    def _show_info(self, text, status='bad'):
        self._set_banner(get_banner_color(status))
        self.banner_content.controls = [ft.Text(text)]
        self._show_banner()

    def _build(self):
        root_layout = ft.Column(
            spacing=10,
            expand=True,
            # scroll=ft.ScrollMode.AUTO
        )
        root_layout.controls.append(self._get_install_python_container())
        root_layout.controls.append(self._get_install_directory_container())
        root_layout.controls.append(self._get_install_plugins_container())

        btn = ft.ElevatedButton(text='INSTALLERA', on_click=self._install_app)
        self._toggle_buttons.append(btn)
        root_layout.controls.append(btn)

        self.page.controls.append(root_layout)

        self.update_page()

    def _get_install_python_container(self):
        row = ft.Row()
        btn = ft.ElevatedButton('Ange sökväg till python (>=3.11)', on_click=lambda _:
        self._python_exe_picker.pick_files(
            dialog_title='Sökväg till Python (>=3.11)',
            allowed_extensions=['exe'],
            allow_multiple=False
        ))

        self._toggle_buttons.append(btn)

        self._python_path = ft.Text()

        row.controls.append(btn)
        row.controls.append(self._python_path)

        container = ft.Container(content=row,
                                 bgcolor='#999999',
                                 border_radius=10,
                                 padding=10,
                                 expand=False
                                 )

        return container

    def _get_install_directory_container(self):
        row = ft.Row()
        btn = ft.ElevatedButton('Ange rotkatalog för installationen', on_click=lambda _:
        self._install_root_directory_picker.get_directory_path(
            dialog_title='Rotkatalog för installationen'
        ))

        self._install_root_directory = ft.Text()

        self._toggle_buttons.append(btn)

        row.controls.append(btn)
        row.controls.append(self._install_root_directory)

        container = ft.Container(content=row,
                                 bgcolor='#999999',
                                 border_radius=10,
                                 padding=10,
                                 expand=False
                                 )

        return container

    def _get_install_plugins_container(self):
        row = ft.Row()
        for plugin in self._install.plugins:
            row.controls.append(self._get_plugin_container(plugin))

        container = ft.Container(content=row,
                                 bgcolor='#999999',
                                 border_radius=10,
                                 padding=10,
                                 expand=False,
                                 )

        return container

    def _get_plugin_container(self, plugin):
        radio_col = ft.Column()

        col = ft.Column()
        for version in self._install.get_plugin_versions(plugin):
            radio_col.controls.append(ft.Radio(value=version, label=version))
        radio_col.controls.append(ft.Radio(value=self._dont_install_string, label=self._dont_install_string))
        radio_group = ft.RadioGroup(content=radio_col)

        self._plugins_selection[plugin] = radio_group

        col.controls.append(ft.Text(plugin))
        col.controls.append(radio_group)
        container = ft.Container(content=col,
                                 bgcolor=get_plugin_color(plugin),
                                 border_radius=10,
                                 padding=10,
                                 expand=False
                                 )

        return container

    def _set_default_python_version(self):
        if self._install.python_exe_path:
            self._python_path.value = str(self._install.python_exe_path)
            self._python_path.update()

    def _set_default_install_root_directory(self):
        path = pathlib.Path(r'C:/sharktools_installs')
        path.mkdir(exist_ok=True)
        self._install_root_directory.value = str(path)
        self._install_root_directory.update()

    def _install_app(self, *args):
        root_dir = self._install_root_directory.value
        if not root_dir:
            self._show_info('Ingen installationsmapp vald')
            return
        python_path = self._python_path.value
        if not python_path:
            self._show_info('Ingen sökväg till python vald')
            return
        self._disable_toggle_buttons()
        self._show_info('Installerar...', status='working')
        self._install.set_install_root_directory(root_dir)
        self._install.set_plugins(**self._get_plugin_selection())
        self._install.install()
        self._enable_toggle_buttons()
        self._show_info(f'Installation klar. \nInfo i fil {self._install.summary_file_path}. '
                        f'\nKör program med {self._install.batch_file_run}', status='good')

    def _get_plugin_selection(self) -> dict[str, str]:
        plugins = {}
        for plugin, wid in self._plugins_selection.items():
            value = wid.value
            if not value or value == self._dont_install_string:
                continue
            plugins[plugin] = value
        return plugins

    def _on_pick_python_exe(self, e: ft.FilePickerResultEvent):
        self._close_banner()
        if not e.files:
            return
        path = e.files[0].path
        self._python_path.value = path
        self._python_path.update()

    def _on_pick_install_root_dir(self, e: ft.FilePickerResultEvent):
        self._close_banner()
        if not e.path:
            return
        self._install_root_directory.value = e.path
        self._install_root_directory.update()


def run_flet_app(log_in_console):
    app = FletApp(log_in_console=log_in_console)
    return app


if __name__ == '__main__':
    app = run_flet_app(True)
