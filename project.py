import collections
import os
import re
import shutil
import subprocess
import sys
import urllib.request
import zipfile
import string
import logging
import logging.handlers
import struct
import yaml

# from configparser import ConfigParser
from pathlib import Path

import exceptions

if getattr(sys, 'frozen', False):
    # THIS_FILE_PATH = Path(os.path.dirname(sys.executable))
    THIS_FILE_PATH = Path(sys.executable)
elif __file__:
    THIS_FILE_PATH = Path(__file__)


class Project(object):
    def __init__(self, logger=None):
        
        self.logger = logger
        if not logger:
            self.logging_level = 'DEBUG'
            self.logging_format = '%(asctime)s [%(levelname)10s]    %(pathname)s [%(lineno)d] => %(funcName)s():    %(message)s'
            self._setup_logger()

        self._python_path = None
        self._python_version = None

        self.venv_name = 'venv'

        self._bit_version = struct.calcsize("P") * 8

        self.available_plugins = []
        self.selected_plugins = []

        self.copied_packages = []

        self.steps = collections.OrderedDict({'Ladda ner programmet': self.download_program,
                                              'Ladda ner plugins': self.download_plugins,
                                              'Ladda ner smhi-paket': self.download_packages,
                                              'Skapa virtuell python-miljö': self.create_environment,
                                              'Installera python-paket (requirements)': self.install_packages,
                                              'Skapa körbar bat-fil': self.create_run_program_file})

        self.directory = 'C:/'

        self._find_plugins()

        self._find_python_exe()

    def _setup_logger(self, **kwargs):
        name = Path(__file__).stem
        self.logger = logging.getLogger(name)
        self.logger.setLevel(self.logging_level)
        directory = Path(THIS_FILE_PATH.parent, 'log')
        if not directory.exists():
            os.makedirs(directory)
        file_path = Path(directory, 'install.log')
        handler = logging.handlers.TimedRotatingFileHandler(str(file_path), when='D', interval=1, backupCount=7)
        formatter = logging.Formatter(self.logging_format)
        handler.setFormatter(formatter)
        self.logger.addHandler(handler)

    @property
    def directory(self):
        """
        Project will be created under this directory.
        """
        return self.__directory

    @directory.setter
    def directory(self, directory):
        self.root_directory = directory
        self.__directory = Path(directory, 'SHARKtools')

        self.program_directory = Path(self.directory, 'SHARKtools')
        self.plugins_directory = Path(self.program_directory, 'plugins')
        self.package_directory = self.program_directory

        self.wheels_source_directory = Path(THIS_FILE_PATH.parent, 'wheels')
        self.smhi_packages_config_file = Path(THIS_FILE_PATH.parent, 'sharksmhi_packages.yaml')

        self.install_history_directory = Path(self.directory, 'install_history')
        self.wheels_directory = Path(self.install_history_directory, 'wheels')

        self.venv_directory = Path(self.program_directory, self.venv_name)

        self.temp_directory = Path(self.directory, '_temp_sharktools')
        self.temp_program_dir = Path(self.temp_directory, 'temp_program')
        self.temp_plugins_dir = Path(self.temp_directory, 'temp_plugins')
        self.temp_packages_dir = Path(self.temp_directory, 'temp_packages')
        self.temp_move_plugins_dir = Path(self.temp_directory, 'temp_subdirs')

        self.batch_file_create_venv = Path(self.install_history_directory, 'create_venv.bat')
        self.batch_file_install_requirements = Path(self.install_history_directory, 'install_requirements.bat')
        self.batch_file_run_program = Path(self.directory, 'run_program.bat')

        self.log_file_path = Path(self.install_history_directory, 'install.log')

        self.requirements_file_path = Path(self.install_history_directory, 'requirements.txt')

        self.git_root_url = 'https://github.com/sharksmhi/'

    def run_step(self, step, **kwargs):
        """
        Step matches keys in self.steps
        :param step: str
        :return:
        """
        if kwargs.get('use_git'):
            self.package_directory = self.directory
        else:
            self.package_directory = self.program_directory
        func = self.steps.get(step)
        if func:
            all_ok = func(**kwargs)
            return all_ok

    def setup_project(self):
        """
        Sets up the project. Copies files from self.temp_directory. Main program and plugins.
        :return:
        """

        if self.directory is None:
            self.logger.error('Project directory not set!')
            raise NotADirectoryError('No directory found')

        if not os.path.exists(self.directory):
            os.makedirs(self.directory)

        if not os.path.exists(self.wheels_directory):
            os.makedirs(self.wheels_directory)

        if not os.path.exists(self.install_history_directory):
            os.makedirs(self.install_history_directory)

    def download_program(self, use_git=False, **kwargs):
        # self._reset_directory(self.temp_program_dir)
        if use_git:
            self._clone_or_pull_main_program()
        else:
            self._download_main_program_from_github()
            self._unzip_main_program()
            self._copy_main_program()

    def _clone_or_pull_main_program(self):
        if 'SHARKtools' in [path.name for path in self.directory.iterdir()]:
            self._pull_main_program()
        else:
            self._clone_main_program()

    def _clone_main_program(self):
        file_path = Path(self.install_history_directory, 'git_clone_main_program.bat')
        lines = [f'cd {self.directory}',
                 f'git clone {self.git_root_url}SHARKtools.git"']
        with open(file_path, 'w') as fid:
            fid.write('\n'.join(lines))
        self._run_batch_file(file_path)

    def _pull_main_program(self):
        file_path = Path(self.install_history_directory, 'git_pull_main_program.bat')
        lines = [f'cd {self.program_directory}',
                 f'git pull']
        with open(file_path, 'w') as fid:
            fid.write('\n'.join(lines))
        self._run_batch_file(file_path)

    def download_plugins(self, use_git=False, **kwargs):
        # self._reset_directory(self.temp_plugins_dir)
        self._create_directory(self.plugins_directory)
        if use_git:
            self._clone_or_pull_plugins()
        else:
            self._download_plugins_from_github()
            self._unzip_plugins()
            self._copy_plugins()

    def _clone_or_pull_plugins(self):
        installed_plugins = [path.name for path in self.plugins_directory.iterdir()]
        for plugin in self.selected_plugins:
            if plugin in installed_plugins:
                self._pull_plugin(plugin)
            else:
                self._clone_plugin(plugin)

    def _clone_plugin(self, plugin):
        file_path = Path(self.install_history_directory, f'git_clone_plugin_{plugin}.bat')
        lines = [f'cd {self.plugins_directory}',
                 f'git clone {self.git_root_url}{plugin}.git"']
        with open(file_path, 'w') as fid:
            fid.write('\n'.join(lines))
        self._run_batch_file(file_path)

    def _pull_plugin(self, plugin):
        file_path = Path(self.install_history_directory, f'git_pull_plugin_{plugin}.bat')
        lines = [f'cd {Path(self.plugins_directory, plugin)}',
                 f'git pull']
        with open(file_path, 'w') as fid:
            fid.write('\n'.join(lines))
        self._run_batch_file(file_path)

    def download_packages(self, use_git=False, **kwargs):
        # self._reset_directory(self.temp_packages_dir)
        if use_git:
            self._clone_or_pull_packages()
        else:
            self._download_packages_from_github()
            self._unzip_packages()
            self._copy_packages()

    def _clone_or_pull_packages(self):
        installed_packages = [path.name for path in self.directory.iterdir()]
        for pack in self._get_packages_to_download_from_github():
            if pack in installed_packages:
                self._pull_package(pack)
            else:
                self._clone_package(pack)

    def _clone_package(self, pack):
        file_path = Path(self.install_history_directory, f'git_clone_package_{pack}.bat')
        lines = [f'cd {self.package_directory}',
                 f'git clone {self.git_root_url}{pack}.git"']
        with open(file_path, 'w') as fid:
            fid.write('\n'.join(lines))
        self._run_batch_file(file_path)

    def _pull_package(self, pack):
        file_path = Path(self.install_history_directory, f'git_pull_package_{pack}.bat')
        lines = [f'cd {Path(self.package_directory, pack)}',
                 f'git pull']
        with open(file_path, 'w') as fid:
            fid.write('\n'.join(lines))
        self._run_batch_file(file_path)

    def create_environment(self, **kwargs):
        """
        Create a batch file and run it to create a virtual environment.
        :return:
        """
        # Delete old environment
        self._delete(self.venv_directory)

        # Create file
        self._create_batch_environment_file()

        # Run file
        self._run_batch_file(self.batch_file_create_venv)

        self._create_pth_file()

        # Install python packages
        # self.install_packages()

    def install_packages(self, **kwargs):
        """
        Installs packages in self.requirements_file_path into the virtual environment.
        :return:
        """
        if not os.path.exists(self.venv_directory):
            self.logger.error('No venv found')
            raise exceptions.MissingVenvException('Virtuell pythonmiljö saknas. Skapa en miljö innan du installerar paket!')

        all_ok = True
        if not self.wheels_source_directory.exists():
            os.makedirs(self.wheels_source_directory)
        # self._copy_wheels()
        self._create_requirements_file()
        self._create_batch_install_requirements_file()

        self._run_batch_file(self.batch_file_install_requirements)

        self._create_pth_file()

        return all_ok

    def _create_pth_file(self):
        packages = self._get_packages_to_download_from_github()
        paths = {path.name: path for path in self.package_directory.iterdir()}
        lines = []
        for pack in packages:
            path = paths.get(pack)
            if not path:
                continue
            lines.append(str(path))

        file_path = Path(self.venv_directory, 'Lib', 'site-packages', '.pth')
        with open(file_path, 'w') as fid:
            fid.write('\n'.join(lines))

    def _get_wheel_rel_path_for_package(self, package):
        path = self._get_wheel_path_for_package(package)
        if not path:
            return
        return f'./{path.relative_to(self.install_history_directory)}'.replace('\\', '/')

    def _get_wheel_path_for_package(self, package):
        if not self.install_history_directory:
            return
        if not self.wheels_directory.exists():
            return

        pack = package.lower()
        for path in self.wheels_directory.iterdir():
            if path.suffix != '.whl':
                continue
            name = path.name.lower()
            if pack in name:
                if (f'cp{self._python_version}' in name and f'{self._bit_version}.whl' in name) or 'none-any' in name:
                    return path

    def _old_copy_wheels(self):
        if not self.wheels_directory.exists():
            os.makedirs(self.wheels_directory)
        existing_wheels = [path.name for path in self.wheels_directory.iterdir()]
        for path in self.wheels_source_directory.iterdir():
            if path.name in existing_wheels:
                continue
            name = path.name.lower()
            print('self._python_version', self._python_version)
            print('self._bit_version', self._bit_version)
            if (f'cp{self._python_version}' in name and f'{self._bit_version}.whl' in name) or 'none-any' in name:
                shutil.copy2(str(path), str(Path(self.wheels_directory, path.name)))

    def _get_source_wheel_for_package(self, package, and_not=None):
        pack = package.lower()
        for path in self.wheels_source_directory.iterdir():
            name = path.name.lower()
            if and_not and and_not in name:
                continue
            if pack not in name:
                continue
            if (f'cp{self._python_version}' in name and f'{self._bit_version}.whl' in name) or 'none-any' in name:
                return path

    def _copy_wheel_to_local(self, source_path):
        if not source_path.exists():
            return
        target_path = Path(self.wheels_directory, source_path.name)
        if target_path.exists():
            return
        if not self.wheels_directory.exists():
            os.makedirs(self.wheels_directory)
        shutil.copy2(str(source_path), str(target_path))

    def _create_requirements_file(self, use_git=False):
        """
        Look for requirement files and stores valid lines in self.requirements_file_path
        :return:
        """
        local_packages = [path.name for path in self.package_directory.iterdir()]

        lines = []
        if 'ctdpy' in local_packages:
            lines.extend(['shapely', 'gdal', 'fiona', 'six', 'rtree', 'geopandas'])

        for root, dirs, files in os.walk(self.package_directory, topdown=False):
            for name in files:
                if name == 'requirements.txt':
                    file_path = Path(root, name)
                    with open(file_path) as fid:
                        for line in fid:
                            module = line.strip()
                            if module.startswith('#'):
                                continue
                            if module and module not in lines:
                                lines.append(module)

        # Remove duplicates
        keep_dict = {}
        for item in set(lines):
            item = item.strip()
            # if item.startswith('#'):
            #     continue
            split_item = item.strip().split('==')
            pack = split_item[0]
            keep_dict.setdefault(pack, set())
            keep_dict[pack].add(item)

        keep_pip_list = []
        keep_wheel_list = []
        for pack, value in keep_dict.items():
            if pack in local_packages:
                continue
            and_not = None
            if pack == 'pandas':
                and_not = 'geopandas'
            source_wheel_path = self._get_source_wheel_for_package(pack, and_not=and_not)
            if source_wheel_path:
                self._copy_wheel_to_local(source_wheel_path)
            wheel_path = self._get_wheel_rel_path_for_package(pack)
            if wheel_path:
                keep_wheel_list.append(wheel_path)
            else:
                if len(value) == 1:
                    keep_pip_list.append(list(value)[0])
                else:
                    keep_pip_list.append(pack)

        # Write to file
        keep_list = keep_wheel_list + keep_pip_list
        with open(self.requirements_file_path, 'w') as fid:
            fid.write('\n'.join(keep_list))

    def old_create_requirements_file_pipwin(self):
        """
        Look for requirement files and stores valid lines in self.requirements_file_path
        :return:
        """
        lines = {} # Is sorted by default
        for root, dirs, files in os.walk(self.program_directory, topdown=False):
            for name in files:
                if name == 'requirements.txt':
                    file_path = Path(root, name)
                    print(file_path)
                    with open(file_path) as fid:
                        for line in fid:
                            line = line.strip()
                            if not line:
                                continue
                            if line.startswith('# '):
                                continue
                            module = line
                            module_name = module
                            wheel = False
                            module_nr = 0
                            if line.startswith('#wheel'):
                                wheel = True
                                module = module.split(' ')[1]
                                module_name = module
                            if '==' in module:
                                module_name, module_nr = module.split('==')
                                module_nr = int(module_nr.replace('.', ''))
                            if module_name not in lines:
                                print('0', module_name)
                                lines[module_name] = dict(text=f'{line} \t# {file_path}',
                                                          nr=module_nr,
                                                          wheel=wheel)
                            else:
                                if not wheel and lines[module_name]['wheel']:
                                    continue
                                if wheel and not lines[module_name]['wheel']:
                                    lines[module_name] = dict(text=f'{line} \t# {file_path}',
                                                              nr=module_nr,
                                                              wheel=wheel)
                                    continue
                                if module_nr > lines[module_name]['nr']:
                                    lines[module_name] = dict(text=f'{line} \t# {file_path}',
                                                              nr=module_nr,
                                                              wheel=wheel)
                                    continue

        # Write to file
        with open(self.requirements_file_path, 'w') as fid:
            fid.write('\n'.join([lines[key]['text'] for key in lines]))

    def _get_requirements_list_from_url(self, url):
        try:
            with urllib.request.urlopen(url) as f:
                content_str = f.read().decode('utf-8')
                return [item.strip() for item in content_str.split('\n')]
        except Exception as e:
            self.logger.error(f'Could not download info from URL: {url}')
            raise

    def _get_packages_to_download_from_github(self):
        to_download = {}
        if not self.smhi_packages_config_file.exists():
            raise FileNotFoundError(self.smhi_packages_config_file)
        with open(self.smhi_packages_config_file) as fid:
            data = yaml.load(fid, Loader=yaml.FullLoader)
            for plugin, item_list in data.items():
                for item in item_list:
                    pack, url = [value.strip() for value in item.split('=')]
                    to_download[pack] = url
        return to_download

    def _download_packages_from_github(self):
        packages_to_download = self._get_packages_to_download_from_github()
        for pack, url in packages_to_download.items():
            self._download_package_from_github(pack, url)

    def _download_package_from_github(self, package, url):
        urllib.request.urlretrieve(url, r'{}/{}.zip'.format(self.temp_packages_dir, package))

    def _copy_packages(self):
        self.copied_packages = []
        self._check_path(self.temp_packages_dir)
        all_dirs = os.listdir(self.temp_packages_dir)
        for _dir in all_dirs:
            match = re.findall('-.*-', _dir)
            if not match:
                continue
            package = match[0].strip('-')
            source_dir = Path(self.temp_packages_dir, _dir, package)
            target_dir = Path(self.program_directory, package)
            self._delete(target_dir)
            shutil.copytree(source_dir, target_dir)

            # Copy requirements.txt
            source_req_file_path = Path(self.temp_packages_dir, _dir, 'requirements.txt')
            if source_req_file_path.exists():
                target_req_file_path = Path(target_dir, 'requirements.txt')
                shutil.copy2(source_req_file_path, target_req_file_path)

            self.logger.info(f'Package {package} copied to {target_dir}')
            self.copied_packages.append(package)

    def create_run_program_file(self, **kwargs):
        """
        Creates a batch file that can be used to run the program.
        :return:
        """
        self._check_path(self.batch_file_run_program)

        # Check if all info exists
        if not os.path.exists(self.program_directory) or not os.listdir(self.program_directory):
            raise exceptions.CantRunProgramException('Huvudprogram är inte nedladdat')
        elif not os.path.exists(self.venv_directory) or not os.listdir(self.venv_directory):
            raise exceptions.CantRunProgramException('Virtuell miljö är inte skapad')
        # elif not os.path.exists(self.sharkpylib_directory) or not os.listdir(self.sharkpylib_directory):
        #     raise exceptions.CantRunProgramException('sharkpylib är inte nedladdat')

        lines = []
        lines.append(f'call {Path(self.venv_directory, "Scripts", "activate")}')
        lines.append(f'cd {self.program_directory}')
        lines.append(f'python main.py')
        lines.append(f'pause')
        with open(self.batch_file_run_program, 'w') as fid:
            fid.write('\n'.join(lines))

    def _create_batch_install_requirements_file(self):
        """
        Creates a batch file that installs packages to the virtual environment.
        :return:
        """
        lines = []
        env_activate_path = Path(self.venv_directory, 'Scripts', 'activate')
        lines.append(f'call {env_activate_path}')

        lines.append('python -m pip install --upgrade pip')

        # wheel_files = os.listdir(self.wheels_directory)
        #
        # # Look for pyproj
        # for file_name in wheel_files[:]:
        #     if 'pyproj' in file_name:
        #         lines.append(f'pip install {Path(self.wheels_directory, file_name)}')
        #         wheel_files.pop(wheel_files.index(file_name))
        #
        # # Install the rest
        # for file_name in wheel_files:
        #     lines.append(f'pip install {Path(self.wheels_directory, file_name)}')

        # Add requirements file
        lines.append(f'pip install -r {self.requirements_file_path}')

        # with open(self.requirements_file_path) as fid:
        #     for line in fid:
        #         line = line.strip()
        #         if line.startswith('#reinstall'):
        #             pack = line.split(' ')[1]
        #             lines.append(f'pip install --upgrade --force-reinstall {pack}')

        with open(self.batch_file_install_requirements, 'w') as fid:
            fid.write('\n'.join(lines))

    def old_create_batch_install_requirements_file_pipwin(self):
        """
        Creates a batch file that installs packages to the virtual environment.
        :return:
        """
        lines = []
        env_activate_path = Path(self.venv_directory, 'Scripts', 'activate')
        lines.append(f'call {env_activate_path}')

        lines.append('python -m pip install --upgrade pip')

        lines.append('')
        lines.append('pip install wheel')
        lines.append('pip install pipwin')

        with open(self.requirements_file_path) as fid:
            for line in fid:
                line = line.strip()
                if line.startswith('#wheel'):
                    pack = line.split(' ')[1]
                    lines.append(f'pipwin install {pack}')

        # Add requirements file
        lines.append('')
        lines.append(f'pip install -r {self.requirements_file_path}')

        lines.append('')
        with open(self.requirements_file_path) as fid:
            for line in fid:
                line = line.strip()
                if line.startswith('#reinstall'):
                    pack = line.split(' ')[1]
                    lines.append(f'pip install --upgrade --force-reinstall {pack}')

        with open(self.batch_file_install_requirements, 'w') as fid:
            fid.write('\n'.join(lines))

    def _create_batch_environment_file(self):
        self._check_path(self.directory)

        if not self._python_path:
            self.logger.error('Invalid python.exe file')
            raise FileNotFoundError

        lines = []

        disk = str(self.venv_directory.parent)[0]
        # Browse to disk
        lines.append(f'{disk}:')

        # Go to python environment directory
        lines.append(f'cd {self.venv_directory.parent}')

        # Create environment
        lines.append(f'call {self._python_path} -m venv {self.venv_name}')

        with open(self.batch_file_create_venv, 'w') as fid:
            fid.write('\n'.join(lines))

    def select_plugins(self, plugins_list):
        for plugin in plugins_list:
            if plugin not in self.available_plugins:
                self.logger.error('Not a valid plugin: {}'.format(plugin))
                raise ValueError
            self.selected_plugins.append(plugin)

    def set_python_path(self, python_exe):
        """
        Sets the python directory (version) used to create the python environment.
        :param python_directory: str
        :return: None
        """
        python_exe = Path(python_exe)
        if not python_exe.exists():
            self.logger.error('Not a valid python!')
            raise FileNotFoundError
        if not python_exe.name =='python.exe':
            self.logger.error('Not a valid python!')
            raise FileNotFoundError
        self._python_path = python_exe
        self._python_version = ''.join([s for s in list(str(self._python_path.parent.name)) if s in string.digits + '-'])
        self._save_python_path()

    def get_python_path(self):
        return self._python_path

    def _find_plugins(self):
        try:
            resp = urllib.request.urlopen(r'https://github.com/orgs/sharksmhi/repositories')
            data = resp.read().decode('UTF-8')
            self.available_plugins = sorted(set(re.findall('SHARKtools_[a-zA-Z0-9_]+', data)))
            # Remove SHARKtools_install (this program)
            if 'SHARKtools_install' in self.available_plugins:
                self.available_plugins.pop(self.available_plugins.index('SHARKtools_install'))
            self._save_plugins()
        except:
            self._load_plugins()

    def _find_python_exe(self, root_folder='C:/'):
        self._python_path = None
        if self._load_python_path():
            return True

        for path in sorted(sys.path):
            if 'python36' in path.lower():
                file_list = os.listdir(path)
                for file_name in file_list:
                    if file_name == 'python.exe':
                        self._python_path = Path(path, file_name)
                        self.logger.info(f'Found python path: {self._python_path}')
                        return True
        self.logger.warning('python.exe not found!')
        return False

    def _save_python_path(self):
        if not self._python_path:
            return False
        with open('python_path', 'w') as fid:
            fid.write(str(self._python_path))
        return True

    def _load_python_path(self):
        self._python_path = None
        if not os.path.exists('python_path'):
            return False
        with open('python_path') as fid:
            line = fid.readline().strip()
            if line and os.path.exists(line):
                self._python_path = line
                self.logger.info(f'python.exe path taken from file: {self._python_path}')
                return True
        return False

    def _save_plugins(self):
        with open(Path(THIS_FILE_PATH.parent, 'plugins'), 'w') as fid:
            fid.write('\n'.join(self.available_plugins))

    def _load_plugins(self):
        self.available_plugins = []
        with open(Path(THIS_FILE_PATH.parent, 'plugins')) as fid:
            for line in fid:
                line = line.strip()
                if line:
                    self.available_plugins.append(line)
        self.available_plugins = sorted(self.available_plugins)
        if self.available_plugins:
            return True
        else:
            return False

    def _download_main_program_from_github(self):
        self._check_path(self.temp_program_dir)
        url = r'https://github.com/sharksmhi/SHARKtools/zipball/master/'
        urllib.request.urlretrieve(url, r'{}/SHARKtools.zip'.format(self.temp_program_dir))

    def _download_plugins_from_github(self):
        self._reset_directory(self.temp_plugins_dir)

        # Plugins
        for plugin in self.selected_plugins:
            url = r'https://github.com/sharksmhi/{}/zipball/main/'.format(plugin)
            item = r'{}/{}.zip'.format(self.temp_plugins_dir, plugin)
            print('url', url)
            print('item', item)
            urllib.request.urlretrieve(url, item)

    # def _unzip_files(self):
    #     # Unzip
    #     file_list = os.listdir(self.temp_directory)
    #     for file_name in file_list:
    #         if file_name[:-4] in (['SHARKtools'] + self.selected_plugins):
    #             file_path = Path(self.temp_directory, file_name)
    #             with zipfile.ZipFile(file_path, "r") as zip_ref:
    #                 zip_ref.extractall(self.temp_directory)

    def _unzip_files(self, directory):
        file_list = os.listdir(directory)
        for file_name in file_list:
            file_path = Path(directory, file_name)
            try:
                with zipfile.ZipFile(file_path, "r") as zip_ref:
                    zip_ref.extractall(directory)
            except Exception as e:
                print('Exception!!!')
                print(e)

    def _unzip_packages(self):
        self._unzip_files(self.temp_packages_dir)

    def _unzip_plugins(self):
        self._unzip_files(self.temp_plugins_dir)

    def _unzip_main_program(self):
        self._unzip_files(self.temp_program_dir)

    def _copy_main_program(self):
        self._check_path(self.program_directory)
        all_files = os.listdir(self.temp_program_dir)
        # Copy main program
        for file_name in all_files:
            if '-SHARKtools-' in file_name:
                # First save plugins
                self._save_subdirs_temporary()
                # Now copy main program
                source_dir = Path(self.temp_program_dir, file_name)
                target_dir = Path(self.program_directory)
                self._delete(target_dir)
                shutil.copytree(source_dir, target_dir)
                # Finally import temporary saved plugins
                self._import_temporary_subdirs_plugins()
                break

    def _save_subdirs_temporary(self):
        # Copy plugins
        self._create_directory(self.temp_move_plugins_dir)
        source_dir = self.plugins_directory
        self._create_directory(source_dir)
        self._delete(self.temp_move_plugins_dir)
        shutil.copytree(source_dir, self.temp_move_plugins_dir)

        # # Copy sharkpylib
        # source_dir = Path(self.program_directory, 'sharkpylib')
        # self._create_directory(source_dir)
        # self._delete(self.temp_packages_dir)
        # shutil.copytree(source_dir, self.temp_packages_dir)

    def _import_temporary_subdirs_plugins(self):
        # Copy plugins
        if not os.path.exists(self.temp_move_plugins_dir):
            self.logger.warning(f'No temporary plugins: {self.temp_move_plugins_dir}')
            raise Exception
        plugin_dirs = os.listdir(self.temp_move_plugins_dir)
        for plugin_name in plugin_dirs:
            source_dir = Path(self.temp_move_plugins_dir, plugin_name)
            target_dir = Path(self.plugins_directory, plugin_name)
            self._delete(target_dir)
            if not source_dir.is_dir():
                continue
            shutil.copytree(source_dir, target_dir)
            self._delete(source_dir)

        # # Copy sharkpylib
        # if not os.path.exists(self.temp_packages_dir):
        #     self.logger.warning(f'No temporary sharkpylib: {self.temp_packages_dir}')
        #     raise Exception
        # source_dir = Path(self.temp_packages_dir)
        # target_dir = self.sharkpylib_directory
        # self._delete(target_dir)
        # shutil.copytree(source_dir, target_dir)
        # self._delete(source_dir)

    def _copy_plugins(self):
        self._check_path(self.program_directory)
        all_files = os.listdir(self.temp_plugins_dir)
        for plugin in self.selected_plugins:
            for file_name in all_files:
                if f'-{plugin}-' in file_name:
                    source_dir = Path(self.temp_plugins_dir, file_name)
                    target_dir = Path(self.plugins_directory, plugin)
                    self._delete(target_dir)
                    shutil.copytree(source_dir, target_dir)
                    break

    def _run_batch_file(self, file_path):
        """
        This will run and delete the batch file.
        :return:
        """
        self._check_path(file_path)
        if file_path.suffix != '.bat':
            self.logger.info(f'Not a valid bat file {file_path}')
            raise Exception
        self.logger.info(f'Running file {file_path}')
        subprocess.run(str(file_path))
        return True

    def _check_path(self, path):
        if 'SHARKtools' in str(path):
            return True
        self.logger.error(f'Not a valid path: {path}')
        raise Exception

    def _delete(self, path):
        """
        Checks valid path (containing "sharktools") before deleting.
        :param path:
        :return:
        """
        if os.path.exists(path) and self._check_path(path):
            if os.path.isfile(path):
                os.remove(path)
            elif os.path.isdir(path):
                shutil.rmtree(path)
            else:
                return False
            return True
        return False

    def _reset_directory(self, directory):
        """
        Resets the given directory. First delete via self._delete to make sure root path is correct.
        Then makes directory tree. Also if non existing from the beginning.
        :param directory:
        :return:
        """
        self._delete(directory)
        self._create_directory(directory)

    def _create_directory(self, directory):
        self._check_path(directory)
        if not os.path.exists(directory):
            os.makedirs(directory)


if __name__ == '__main__':
    pass
    p = Project()
    p.setup_project()
    p.select_plugins(['SHARKtools_ctd_processing', 'SHARKtools_pre_system_Svea'])
    # p.download_program()
    # p.download_plugins()
    # p.download_packages()
    p.set_python_path(r'C:\Python36/python.exe')
    # p.create_environment()
    # p.install_packages()
    # p.install_packages()
    # p.create_run_program_file()
