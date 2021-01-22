import collections
import os
import re
import shutil
import subprocess
import sys
import urllib.request
import zipfile
import urllib.request
import platform

from configparser import ConfigParser
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

        self.python_exe = None

        self.venv_name = 'venv'

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

        self.wheels_directory = Path(self.directory, 'wheels')
        self.wheels_source_directory = Path(THIS_FILE_PATH.parent, 'wheels')
        self.smhi_packages_config_file = Path(THIS_FILE_PATH.parent, 'sharksmhi_packages.ini')

        self.install_history_directory = Path(self.directory, 'install_history')
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

    def run_step(self, step, **kwargs):
        """
        Step matches keys in self.steps
        :param step: str
        :return:
        """
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
            raise ValueError

        if not os.path.exists(self.directory):
            os.makedirs(self.directory)

        if not os.path.exists(self.wheels_directory):
            os.makedirs(self.wheels_directory)

        if not os.path.exists(self.install_history_directory):
            os.makedirs(self.install_history_directory)

    def download_program(self, **kwargs):
        self._reset_directory(self.temp_program_dir)
        self._download_main_program_from_github()
        self._unzip_main_program()
        self._copy_main_program()

    def download_plugins(self, **kwargs):
        self._reset_directory(self.temp_plugins_dir)
        self._download_plugins_from_github()
        self._unzip_plugins()
        self._copy_plugins()

    def download_packages(self, **kwargs):
        self._reset_directory(self.temp_packages_dir)
        self._download_packages_from_github()
        self._unzip_packages()
        self._copy_packages()

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

        # Install python packages
        # self.install_packages()

    def install_packages(self, use_pipwin=False, **kwargs):
        """
        Installs packages in self.requirements_file_path into the virtual environment.
        Also installs pyproj and basemap if found in file.
        :return:
        """
        all_ok = True
        copied_files = []
        if use_pipwin:
            self.logger.debug('Using pipwin')
            self._create_requirements_file_pipwin()
            self._create_batch_install_requirements_file_pipwin()
        else:
            if not self.wheels_source_directory.exists():
                os.makedirs(self.wheels_source_directory)
            self._create_requirements_file()
            self._reset_directory(self.wheels_directory)
            # First check for wheel files
            with open(self.requirements_file_path) as fid:
                for line in fid:
                    sline = line.strip()
                    if 'wheel' in sline:
                        name = sline.strip('#').strip().split()[1]
                        source_path = self._get_wheel_source_file_path(name)
                        if not source_path:
                            self.logger.error(f'Could not get wheel for name {name}')
                            all_ok = False
                        else:
                            if source_path not in copied_files:
                                shutil.copy(source_path, Path(self.wheels_directory, source_path.name))
                                copied_files.append(source_path)

                    # if sline.endswith('.whl'):
                    #     # Copy file
                    #     # TODO: Check bit version
                    #     file_name = sline.split(' ')[-1]
                    #     shutil.copy(Path('wheels', file_name), Path(self.wheels_directory, file_name))

            self._create_batch_install_requirements_file()
        
        if not os.path.exists(self.venv_directory):
            self.logger.error('No venv found')
            raise exceptions.MissingVenvException('Virtuell pythonmiljö saknas. Skapa en miljö innan du installerar paket!')
        if not use_pipwin:
            self._run_batch_file(self.batch_file_install_requirements)

        return all_ok

    def _get_wheel_source_file_path(self, name):
        bit_version = platform.architecture()[0][:2]
        for file_name in os.listdir(self.wheels_source_directory):
            if name in file_name and bit_version in file_name:
                return Path(self.wheels_source_directory, file_name)
        return None

    def _create_requirements_file(self):
        """
        Look for requirement files and stores valid lines in self.requirements_file_path
        :return:
        """
        lines = []
        for root, dirs, files in os.walk(self.program_directory, topdown=False):
            for name in files:
                if name == 'requirements.txt':
                    file_path = Path(root, name)
                    with open(file_path) as fid:
                        for line in fid:
                            module = line.strip()
                            if module and module not in lines:
                                lines.append(module)

        # Remove duplicates
        keep_dict = {}
        for item in sorted(set(lines)):
            item = item.strip()
            # if item.startswith('#'):
            #     continue
            split_item = item.strip().split('==')
            pack = split_item[0]
            keep_dict.setdefault(pack, set())
            keep_dict[pack].add(item)

        keep_list = []
        for key, value in keep_dict.items():
            if len(value) == 1:
                keep_list.append(list(value)[0])
            else:
                keep_list.append(key)

        # Write to file
        with open(self.requirements_file_path, 'w') as fid:
            fid.write('\n'.join(sorted(set(keep_list), reverse=True)))  # reverse to have the -e lines last

    def _create_requirements_file_pipwin(self):
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
        parser = ConfigParser()
        if not self.smhi_packages_config_file.exists():
            raise FileNotFoundError(self.smhi_packages_config_file)
        parser.read(str(self.smhi_packages_config_file))
        plugin_list = ['ALL'] + self.selected_plugins
        for plugin in parser.sections(): 
            if plugin not in plugin_list:
                continue
            for item in parser.items(plugin):
                pack, url = item
                to_download[pack] = url 
        return to_download

    def _download_packages_from_github(self):
        packages_to_download = self._get_packages_to_download_from_github()
        for pack, url in packages_to_download.items():
            print(pack, url)
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

        wheel_files = os.listdir(self.wheels_directory)

        # Look for pyproj
        for file_name in wheel_files[:]:
            if 'pyproj' in file_name:
                lines.append(f'pip install {Path(self.wheels_directory, file_name)}')
                wheel_files.pop(wheel_files.index(file_name))

        # Install the rest
        for file_name in wheel_files:
            lines.append(f'pip install {Path(self.wheels_directory, file_name)}')

        # Add requirements file
        lines.append(f'pip install -r {self.requirements_file_path}')

        with open(self.requirements_file_path) as fid:
            for line in fid:
                line = line.strip()
                if line.startswith('#reinstall'):
                    pack = line.split(' ')[1]
                    lines.append(f'pip install --upgrade --force-reinstall {pack}')

        with open(self.batch_file_install_requirements, 'w') as fid:
            fid.write('\n'.join(lines))

    def _create_batch_install_requirements_file_pipwin(self):
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

        if not self.python_exe:
            self.logger.error('Invalid python.exe file')
            raise FileNotFoundError

        lines = []

        disk = str(self.venv_directory.parent)[0]
        # Browse to disk
        lines.append(f'{disk}:')

        # Go to python environment directory
        lines.append(f'cd {self.venv_directory.parent}')

        # Create environment
        lines.append(f'call {self.python_exe} -m venv {self.venv_name}')

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
        if not os.path.exists(python_exe):
            self.logger.error('Not a valid python!')
            raise FileNotFoundError
        if not python_exe.endswith('python.exe'):
            self.logger.error('Not a valid python!')
            raise FileNotFoundError
        self.python_exe = python_exe
        self._save_python_path()

    def _find_plugins(self):
        try:
            resp = urllib.request.urlopen(r'https://github.com/sharksmhi/')
            data = resp.read().decode('UTF-8')
            self.available_plugins = sorted(set(re.findall('SHARKtools_[a-zA-Z0-9_]+', data)))
            # Remove SHARKtools_install (this program)
            if 'SHARKtools_install' in self.available_plugins:
                self.available_plugins.pop(self.available_plugins.index('SHARKtools_install'))
            self._save_plugins()
        except:
            self._load_plugins()

    def _find_python_exe(self, root_folder='C:/'):
        self.python_exe = None
        if self._load_python_path():
            return True

        for path in sorted(sys.path):
            if 'python36' in path.lower():
                file_list = os.listdir(path)
                for file_name in file_list:
                    if file_name == 'python.exe':
                        self.python_exe = Path(path, file_name)
                        self.logger.info(f'Found python path: {self.python_exe}')
                        return True
        self.logger.warning('python.exe not found!')
        return False

    def _save_python_path(self):
        if not self.python_exe:
            return False
        with open('python_path', 'w') as fid:
            fid.write(self.python_exe)
        return True

    def _load_python_path(self):
        self.python_exe = None
        if not os.path.exists('python_path'):
            return False
        with open('python_path') as fid:
            line = fid.readline().strip()
            if line and os.path.exists(line):
                self.python_exe = line
                self.logger.info(f'python.exe path taken from file: {self.python_exe}')
                return True
        return False

    def _save_plugins(self):
        with open('plugins', 'w') as fid:
            fid.write('\n'.join(self.available_plugins))

    def _load_plugins(self):
        self.available_plugins = []
        with open('plugins') as fid:
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
            url = r'https://github.com/sharksmhi/{}/zipball/master/'.format(plugin)
            urllib.request.urlretrieve(url, r'{}/{}.zip'.format(self.temp_plugins_dir, plugin))

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
        self._make_directories(self.temp_move_plugins_dir)
        source_dir = self.plugins_directory
        self._make_directories(source_dir)
        self._delete(self.temp_move_plugins_dir)
        shutil.copytree(source_dir, self.temp_move_plugins_dir)

        # # Copy sharkpylib
        # source_dir = Path(self.program_directory, 'sharkpylib')
        # self._make_directories(source_dir)
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
        Resets the given directory. Firsst delete via self._delete to make sure root path is correct.
        Then makes directory tree. Also if non existing from the beginning.
        :param directory:
        :return:
        """
        self._delete(directory)
        self._make_directories(directory)

    def _make_directories(self, directory):
        self._check_path(directory)
        if not os.path.exists(directory):
            os.makedirs(directory)


if __name__ == '__main__':
    pass
    # p = Project()
    # p.setup_project()
    # # p.select_plugins(['SHARKtools_qc_sensors', 'SHARKtools_tavastland'])
    # p.download_program()
    # p.download_packages()
    # # p.create_environment()
    # # p.install_packages()
    # # p.create_run_program_file()
