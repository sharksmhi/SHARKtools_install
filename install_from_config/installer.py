import yaml
from pathlib import Path
import sys
import logging
import subprocess

logger = logging.getLogger(__name__)


if getattr(sys, 'frozen', False):
    DIRECTORY = Path(sys.executable).parent
elif __file__:
    DIRECTORY = Path(__file__).parent


class Installer:
    _config = None
    _requirements = None
    _wheels = None
    _wheels_dir = None
    _python_path = None
    _install_root_directory = None
    _repos = None
    _plugins = None
    _venv_path = None
    _batch_lines = None
    _main_file_path = None
    _install_batch_path = None

    def __init__(self, input_file=None):
        if input_file:
            self._config_file = Path(input_file)
        else:
            self._config_file = Path(DIRECTORY, 'config.yaml')
        if not self._config_file.exists():
            raise FileNotFoundError(self._config_file)

        self._load_config_file()
        self._extract_data()
        
    @property
    def config_keys(self):
        return list(self._config.keys())

    @property
    def config(self):
        return self._config.copy()
        
    def _load_config_file(self):
        with open(self._config_file) as fid:
            self._config = yaml.safe_load(fid)

    def _extract_data(self):
        self._ext_python_path()
        self._ext_install_root_directory()
        self._ext_requirements()
        self._ext_wheels_dir()
        self._ext_wheels()
        self._ext_repos()
        self._ext_venv_path()
        self._ext_main_file_path()

    def _ext_python_path(self):
        self._python_path = Path(self._config.get('path_to_python'))
        if not self._python_path.exists():
            raise FileNotFoundError(f'Python path: {self._python_path}')

    def _ext_install_root_directory(self):
        self._install_root_directory = Path(self._config.get('install_root_directory'))
        if not self._install_root_directory.is_absolute():
            raise Exception('Install root directory needs to be absolute')
        if not self._install_root_directory.exists():
            self._install_root_directory.mkdir(parents=True, exist_ok=True)

    def _ext_requirements(self):
        self._requirements = self._config.get('requirements')

    def _ext_wheels(self):
        self._wheels = []
        for path in self._config.get('wheels'):
            path = Path(path)
            if not path.is_absolute():
                path = Path(self._wheels_dir, path)
            if not path.exists():
                raise FileNotFoundError(f'Cant find wheel file: {path}')
            self._wheels.append(path)

    def _ext_wheels_dir(self):
        self._wheels_dir = Path(self._config.get('wheels_directory', 'wheels'))
        if not self._wheels_dir.is_absolute():
            self._wheels_dir = Path(DIRECTORY, self._wheels_dir)

    def _ext_repos(self):
        def check_url(p):
            if not p.endswith('.git'):
                raise Exception(f'Not a valid repo: {p}')
            return p
        self._repos = []
        for url in self._config.get('repos'):
            if type(url) == list:
                self._repos.append((url[0], check_url(url[1])))
            else:
                self._repos.append(('', check_url(url)))

    def _ext_venv_path(self):
        self._venv_path = Path(self._config.get('virtual_environment_path'))
        if not self._venv_path.is_absolute():
            self._venv_path = Path(self._install_root_directory, self._venv_path)

    def _ext_main_file_path(self):
        self._main_file_path = Path(self._install_root_directory, self._config.get('main_file'))

    def _create_batch_lines(self):
        self._batch_lines = []
        self._batch_lines.append('ECHO OFF')
        self._batch_lines.append('cls')
        disk = str(self._install_root_directory)[0]
        self._batch_lines.append(f'cd {disk}:')
        self._add_venv_lines()
        self._activate_venv()  # IMPORTANT not to install anything to python root
        self._add_repo_lines()
        self._add_wheels_lines()
        self._add_requirements_lines()
        # self._batch_lines.append(f'pause')

    def _get_path_from_config(self, key, default_name, root_directory=None):
        suffix = Path(default_name).suffix
        file_name = self._config.get(key) or default_name
        if not str(file_name).endswith(suffix):
            file_name = file_name + suffix
        path = Path(file_name)
        if not path.is_absolute():
            root_directory = root_directory or DIRECTORY
            path = Path(root_directory, path)
        if not path.parent.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
        return path

    def _write_batch_lines(self):
        if not self._batch_lines:
            raise Exception('No lines to write to batch file')
        self._install_batch_path = self._get_path_from_config('install_file_name', 'install.bat')
        with open(self._install_batch_path, 'w') as fid:
            fid.write('\n'.join(self._batch_lines))

    def _add_venv_lines(self):
        self._section('Creating virtual environment')
        self._batch_lines.append('if exist ' + str(self._venv_path) + '\\ (')
        self._batch_lines.append('ECHO Virtual environment already exists')
        self._batch_lines.append(') else (')
        self._batch_lines.append(f'ECHO Creating virtual environment at {self._venv_path} using {self._python_path}')
        self._batch_lines.append(f'{self._python_path} -m venv {self._venv_path}')
        self._batch_lines.append(')')
        self._batch_lines.append('')

    def _add_repo_lines(self):
        self._section('Checking repositories')
        for repo in self._repos:
            stem = Path(repo[1]).stem
            local_path = Path(self._install_root_directory, repo[0], stem)
            self._if_else_repo_exists(local_path, repo[1])

    def _add_wheels_lines(self):
        self._section('Installing wheels')
        for wheel in self._wheels:
            self._batch_lines.append(f'pip install {wheel}')
            self._batch_lines.append('ECHO.')
        self._batch_lines.append('')

    def _add_requirements_lines(self):
        self._section('Installing requirements')
        for req in self._requirements:
            self._batch_lines.append(f'pip install {req}')
            self._batch_lines.append('ECHO.')
        self._batch_lines.append('')

    def _if_else_repo_exists(self, repo_path, repo_url):
        self._batch_lines.append('ECHO.')
        self._batch_lines.append(f'ECHO {repo_url} : {repo_path}')
        self._batch_lines.append('if exist ' + str(repo_path) + '\\ (')
        self._cd_reset_pull(repo_path)
        self._batch_lines.append(') else (')
        self._clone_repo(repo_path.parent, repo_url)
        self._batch_lines.append(')')

    def _cd_reset_pull(self, path):
        self._batch_lines.append(f'cd {path}')
        self._batch_lines.append('git reset --hard')
        # self._batch_lines.append('git checkout main')
        self._batch_lines.append('git pull')

    def _clone_repo(self, parent_directory, url):
        self._batch_lines.append(f'cd {parent_directory}')
        self._batch_lines.append(f'git clone {url}')

    def _activate_venv(self):
        self._section(f'Activating {self._venv_path}')
        activate_path = Path(self._venv_path, 'Scripts', 'activate')
        self._batch_lines.append(f'call {activate_path}')
        self._batch_lines.append(f'python -m pip install --upgrade pip')

    def _section(self, title=''):
        self._batch_lines.append('')
        self._batch_lines.append('')
        self._batch_lines.append('ECHO.')
        self._batch_lines.append('ECHO.')
        self._batch_lines.append(':: ' * 20)
        self._batch_lines.append(f'ECHO -- {title} --')

    # def _get_local_repo_paths(self):
    #     local_paths = []
    #     for repo in self._repos:
    #         stem = Path(repo[1]).stem
    #         local_path = Path(self._install_root_directory, repo[0], stem)
    #         local_paths.append(local_path)
    #     return local_paths

    def create_batch_file(self):
        self._create_batch_lines()
        self._write_batch_lines()

    def run_batch_file(self):
        if not self._install_batch_path or not self._install_batch_path.exists():
            return
        subprocess.call([str(self._install_batch_path)])

    def create_pth_file(self):
        local_paths = []
        for repo in self._config.get('repos'):
            if type(repo) == list:
                continue
            path = Path(repo)
            local_path = Path(self._install_root_directory, path.stem)
            local_paths.append(str(local_path))

        file_path = Path(self._venv_path, 'Lib', 'site-packages', '.pth')
        with open(file_path, 'w') as fid:
            fid.write('\n'.join(local_paths))

    def create_run_file(self):
        path = self._get_path_from_config('run_file_name', 'run.bat', root_directory=self._install_root_directory)
        with open(path, 'w') as fid:
            fid.write(f"CALL {Path(self._venv_path, 'Scripts', 'activate')}\n")
            fid.write(f'python {self._main_file_path}')


if __name__ == '__main__':
    c = Installer()
    c.create_batch_file()
