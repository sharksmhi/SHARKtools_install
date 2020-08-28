import collections
import datetime
import os
import re
import shutil
import subprocess
import sys
import urllib.request
import zipfile


import exceptions


class Project(object):
    def __init__(self):

        directory = 'C:\\'  # property

        self.python_exe = None

        self.venv_name = 'venv_py36_sharktools'

        self.available_plugins = []
        self.selected_plugins = []

        self.steps = collections.OrderedDict({'Ladda ner programmet': self.download_program,
                                              'Ladda ner plugins': self.download_plugins,
                                              'Ladda ner sharkpylib': self.download_sharkpylib,
                                              'Skapa virtuell python-miljö': self.create_environment,
                                              # 'Installera python-paket': self.install_packages,
                                              'Skapa körbar bat-fil': self.create_run_program_file})

        self.directory = directory

        self.log = Log()

        self._find_plugins()

        self._find_python_exe()

    @property
    def directory(self):
        """
        Project will be created under this directory.
        :param directory: str
        :return:
        """
        return self.__directory

    @directory.setter
    def directory(self, directory):
        self.root_directory = directory
        self.__directory = os.path.join(directory, 'SHARKtools')
        self.program_directory = os.path.join(self.directory, 'SHARKtools')
        self.sharkpylib_directory = os.path.join(self.program_directory, 'sharkpylib')
        self.plugins_directory = os.path.join(self.program_directory, 'plugins')
        self.temp_directory = os.path.join(self.directory, '_temp_sharktools')
        self.temp_plugins_dir = os.path.join(self.temp_directory, 'temp_plugins')
        self.temp_sharkpylib_dir = os.path.join(self.temp_directory, 'temp_sharkpylib')
        self.wheels_directory = os.path.join(self.directory, 'wheels')
        self.install_history_directory = os.path.join(self.directory, 'install_history')
        self.venv_directory = os.path.join(self.directory, self.venv_name)

        self.batch_file_create_venv = os.path.join(self.install_history_directory, 'create_venv.bat')
        self.batch_file_install_requirements = os.path.join(self.install_history_directory, 'install_requirements.bat')
        self.batch_file_run_program = os.path.join(self.directory, 'run_program.bat')

        self.log_file_path = os.path.join(self.install_history_directory, 'install.log')

        self.requirements_file_path = os.path.join(self.install_history_directory, 'requirements.txt')

    def run_step(self, step):
        """
        Step matches keys in self.steps
        :param step: str
        :return:
        """
        func = self.steps.get(step)
        if func:
            func()
            return True
        return False

    def setup_project(self):
        """
        Sets up the project. Copies files from self.temp_directory. Main program and plugins.
        :return:
        """

        if self.directory is None:
            self.log.exception('Project directory not set!')
            raise ValueError

        if not os.path.exists(self.directory):
            os.makedirs(self.directory)

        if not os.path.exists(self.wheels_directory):
            os.makedirs(self.wheels_directory)

        if not os.path.exists(self.install_history_directory):
            os.makedirs(self.install_history_directory)

        self.log.set_file_path(self.log_file_path)

    def download_program(self):
        self._reset_directory(self.temp_directory)
        self._download_main_program_from_github()
        self._unzip_files()
        self._copy_main_program()
        self._create_requiriemnts_file()
        # self._delete(self.temp_directory)

    def download_plugins(self):
        self._reset_directory(self.temp_directory)
        self._download_plugins_from_github()
        self._unzip_files()
        self._copy_plugins()
        self._create_requiriemnts_file()

    def create_environment(self):
        """
        Create a batch file and run it to create a virtual environment.
        :return:
        """
        # Delete old environment
        venv_dir = os.path.join(self.directory, self.venv_name)
        self._delete(venv_dir)

        # Create file
        self._create_batch_environment_file()

        # Run file
        self._run_batch_file(self.batch_file_create_venv)

        # Install python packages
        self.install_packages()

    def install_packages(self):
        """
        Installs packages in self.requirements_file_path into the virtual environment.
        Also installs pyproj and basemap if found in file.
        :return:
        """
        self._reset_directory(self.wheels_directory)
        # First check for wheel files
        with open(self.requirements_file_path) as fid:
            for line in fid:
                sline = line.strip()
                if sline.endswith('.whl'):
                    # Copy file
                    # TODO: Check bit version
                    file_name = sline.split(' ')[-1]
                    shutil.copy(os.path.join('wheels', file_name), os.path.join(self.wheels_directory, file_name))

        self._create_batch_install_requirements_file()
        
        if not os.path.exists(self.venv_directory):
            self.log.exception('No venv found')
            raise exceptions.MissingVenvException('Virtuell pythonmiljö saknas. Skapa en miljö innan du installerar paket!')

        self._run_batch_file(self.batch_file_install_requirements)

    def download_sharkpylib(self):
        self._reset_directory(self.temp_directory)
        if not self._check_path(self.temp_directory):
            self.log.warning(f'Not a valid path: {self.temp_directory}')
            raise Exception
        if not os.path.exists(self.temp_directory):
            os.makedirs(self.temp_directory)

        # Main program
        url = r'https://github.com/sharksmhi/sharkpylib/zipball/master/'
        urllib.request.urlretrieve(url, r'{}/sharkpylib.zip'.format(self.temp_directory))

        # Unzip
        file_list = os.listdir(self.temp_directory)
        for file_name in file_list:
            if file_name[:-4] == 'sharkpylib':
                file_path = os.path.join(self.temp_directory, file_name)
                with zipfile.ZipFile(file_path, "r") as zip_ref:
                    zip_ref.extractall(self.temp_directory)

        # Copy lib
        if not self._check_path(self.program_directory):
            self.log.warning(f'Not a valid path: {self.program_directory}')
            raise Exception
        all_files = os.listdir(self.temp_directory)
        for file_name in all_files:
            if f'-sharkpylib-' in file_name:
                source_dir = os.path.join(self.temp_directory, file_name, 'sharkpylib')
                self._delete(self.sharkpylib_directory)
                shutil.copytree(source_dir, self.sharkpylib_directory)
                break

        self._delete(self.temp_directory)

    def create_run_program_file(self):
        """
        Creates a batch file that can be used to run the program.
        :return:
        """
        if not self._check_path(self.batch_file_run_program):
            self.log.warning(f'Not a valid path: {self.batch_file_run_program}')

        # Check if all info exists
        if not os.path.exists(self.program_directory) or not os.listdir(self.program_directory):
            raise exceptions.CantRunProgramException('Huvudprogram är inte nedladdat')
        elif not os.path.exists(self.venv_directory) or not os.listdir(self.venv_directory):
            raise exceptions.CantRunProgramException('Virtuell miljö är inte skapad')
        elif not os.path.exists(self.sharkpylib_directory) or not os.listdir(self.sharkpylib_directory):
            raise exceptions.CantRunProgramException('sharkpylib är inte nedladdat')

        lines = []
        lines.append(f'call {self.venv_directory}\\Scripts\\activate')
        lines.append(f'python {self.program_directory}\\main.py')
        with open(self.batch_file_run_program, 'w') as fid:
            fid.write('\n'.join(lines))

    def _create_batch_install_requirements_file(self):
        """
        Creates a batch file that installs packages to the virtual environment.
        :return:
        """
        lines = []
        env_activate_path = os.path.join(self.venv_directory, 'Scripts\\activate')
        lines.append(f'call {env_activate_path}')

        lines.append('python -m pip install --upgrade pip')

        wheel_files = os.listdir(self.wheels_directory)

        # Look for pyproj
        for file_name in wheel_files[:]:
            if 'pyproj' in file_name:
                lines.append(f'pip install {os.path.join(self.wheels_directory, file_name)}')
                wheel_files.pop(wheel_files.index(file_name))

        # Install the rest
        for file_name in wheel_files:
            lines.append(f'pip install {os.path.join(self.wheels_directory, file_name)}')

        # Add requirements file
        lines.append(f'pip install -r {self.requirements_file_path}')

        with open(self.batch_file_install_requirements, 'w') as fid:
            fid.write('\n'.join(lines))

    def _create_requiriemnts_file(self):
        """
        Look for requirement files and stores valid lines in self.requirements_file_path
        :return:
        """
        lines = []
        for root, dirs, files in os.walk(self.program_directory, topdown=False):
            for name in files:
                if name == 'requirements.txt':
                    file_path = os.path.join(root, name)
                    with open(file_path) as fid:
                        for line in fid:
                            module = line.strip()
                            if module and module not in lines:
                                lines.append(module)

        # Write to file
        with open(self.requirements_file_path, 'w') as fid:
            fid.write('\n'.join(sorted(set(lines))))

    def _create_batch_environment_file(self):
        if not self._check_path(self.directory):
            self.log.exception(f'Not a valid directory: {self.directory}')
            raise NotADirectoryError('Not a valid directory')

        if not self.python_exe:
            self.log.exception('Invalid python.exe file')
            raise FileNotFoundError

        lines = []

        disk = self.directory[0]
        # Browse to disk
        lines.append(f'{disk}:')

        # Go to python environment directory
        lines.append(f'cd {self.directory}')

        # Create environment
        lines.append(f'call {self.python_exe} -m venv {self.venv_name}')

        with open(self.batch_file_create_venv, 'w') as fid:
            fid.write('\n'.join(lines))

    def select_plugins(self, plugins_list):
        for plugin in plugins_list:
            if plugin not in self.available_plugins:
                self.log.exception('Not a valid plugin: {}'.format(plugin))
                raise ValueError
            self.selected_plugins.append(plugin)

    def set_python_path(self, python_exe):
        """
        Sets the python directory (version) used to create the python environment.
        :param python_directory: str
        :return: None
        """
        if not os.path.exists(python_exe):
            self.log.exception('Not a valid python!')
            raise FileNotFoundError
        if not python_exe.endswith('python.exe'):
            self.log.exception('Not a valid python!')
            raise FileNotFoundError
        self.python_exe = python_exe
        self._save_python_path()

    def _find_plugins(self):
        try:
            resp = urllib.request.urlopen(r'https://github.com/sharksmhi/')
            data = resp.read().decode('UTF-8')
            #tool_strings = re.findall('SHARKtools\S+', data)
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
                        self.python_exe = os.path.join(path, file_name)
                        self.log.info(f'Found python path: {self.python_exe}')
                        return True
        self.log.warning('python.exe not found!')
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
                self.log.info(f'python.exe path taken from file: {self.python_exe}')
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
        if not self._check_path(self.temp_directory):
            self.log.warning(f'Not a valid path: {self.temp_directory}')
            raise Exception
        if not os.path.exists(self.temp_directory):
            os.makedirs(self.temp_directory)

        # Main program
        url = r'https://github.com/sharksmhi/SHARKtools/zipball/master/'
        urllib.request.urlretrieve(url, r'{}/SHARKtools.zip'.format(self.temp_directory))

    def _download_plugins_from_github(self):
        if not self._check_path(self.temp_directory):
            self.log.warning(f'Not a valid path: {self.temp_directory}')
            raise Exception
        if not os.path.exists(self.temp_directory):
            os.makedirs(self.temp_directory)

        # Plugins
        for plugin in self.selected_plugins:
            url = r'https://github.com/sharksmhi/{}/zipball/master/'.format(plugin)
            urllib.request.urlretrieve(url, r'{}/{}.zip'.format(self.temp_directory, plugin))

    def _unzip_files(self):
        # Unzip
        file_list = os.listdir(self.temp_directory)
        for file_name in file_list:
            if file_name[:-4] in (['SHARKtools'] + self.selected_plugins):
                file_path = os.path.join(self.temp_directory, file_name)
                with zipfile.ZipFile(file_path, "r") as zip_ref:
                    zip_ref.extractall(self.temp_directory)

    def _copy_main_program(self):
        if not self._check_path(self.program_directory):
            self.log.warning(f'Not a valid path: {self.program_directory}')
            raise Exception
        all_files = os.listdir(self.temp_directory)
        # Copy main program
        for file_name in all_files:
            if '-SHARKtools-' in file_name:
                # First save plugins
                self._save_subdirs_temporary()
                # Now copy main program
                source_dir = os.path.join(self.temp_directory, file_name)
                target_dir = os.path.join(self.program_directory)
                self._delete(target_dir)
                shutil.copytree(source_dir, target_dir)
                # Finally import temporary saved plugins
                self._import_temporary_subdirs_plugins()
                break

    def _save_subdirs_temporary(self):
        # Copy plugins
        self._make_directories(self.temp_directory)
        source_dir = self.plugins_directory
        self._make_directories(source_dir)
        self._delete(self.temp_plugins_dir)
        shutil.copytree(source_dir, self.temp_plugins_dir)

        # Copy sharkpylib
        source_dir = os.path.join(self.program_directory, 'sharkpylib')
        self._make_directories(source_dir)
        self._delete(self.temp_sharkpylib_dir)
        shutil.copytree(source_dir, self.temp_sharkpylib_dir)

    def _import_temporary_subdirs_plugins(self):
        # Copy plugins
        if not os.path.exists(self.temp_plugins_dir):
            self.log.warning(f'No temporary plugins: {self.temp_plugins_dir}')
            raise Exception
        plugin_dirs = os.listdir(self.temp_plugins_dir)
        for plugin_name in plugin_dirs:
            source_dir = os.path.join(self.temp_plugins_dir, plugin_name)
            target_dir = os.path.join(self.plugins_directory, plugin_name)
            self._delete(target_dir)
            shutil.copytree(source_dir, target_dir)
            self._delete(source_dir)

        # Copy sharkpylib
        if not os.path.exists(self.temp_sharkpylib_dir):
            self.log.warning(f'No temporary sharkpylib: {self.temp_sharkpylib_dir}')
            raise Exception
        source_dir = os.path.join(self.temp_sharkpylib_dir)
        target_dir = self.sharkpylib_directory
        self._delete(target_dir)
        shutil.copytree(source_dir, target_dir)
        self._delete(source_dir)

    def _copy_plugins(self):
        if not self._check_path(self.program_directory):
            self.log.warning(f'Not a valid path: {self.program_directory}')
            raise Exception
        all_files = os.listdir(self.temp_directory)
        for plugin in self.selected_plugins:
            for file_name in all_files:
                if f'-{plugin}-' in file_name:
                    source_dir = os.path.join(self.temp_directory, file_name)
                    target_dir = os.path.join(self.plugins_directory, plugin)
                    self._delete(target_dir)
                    shutil.copytree(source_dir, target_dir)
                    break

    def _run_batch_file(self, file_path):
        """
        This will run and delete the batch file.
        :return:
        """
        if not self._check_path(file_path) or not file_path.endswith('.bat'):
            self.log.info(f'Not a valid bat file {file_path}')
            raise Exception
        self.log.info(f'Running file {file_path}')
        subprocess.run(file_path)
        return True

    def _check_path(self, path):
        if 'SHARKtools' in path:
            return True
        return False

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
        if not os.path.exists(directory):
            os.makedirs(directory)

        
class Log(object):
    """
    Simple log file.
    """
    def __init__(self, file_path=None):
        if file_path and 'SHARKtools' not in file_path:
            raise ValueError('Invalid log file path')
        self.file_path = file_path
        self.lines = []
        self._add(f'Installation started at: {datetime.datetime.now().strftime("%Y-%m-%d %H:%M")}' + '\n')

    def set_file_path(self, file_path):
        if 'SHARKtools' not in file_path:
            raise ValueError('Invalid log file path')
        self.file_path = file_path

    def _delete_file(self):
        if os.path.exists(self.file_path):
            os.remove(self.file_path)

    def info(self, text):
        self._add(f'INFO: {text}')

    def warning(self, text):
        self._add(f'WARNING: {text}')

    def exception(self, text):
        self._add(f'EXCEPTION: {text}')

    def _add(self, text):
        if not self.file_path:
            self.lines.append(text)
            return
        elif not os.path.exists(self.file_path):
            if self.lines:
                with open(self.file_path, 'w') as fid:
                    fid.write('\n'.join(self.lines) + '\n')
                self.lines = []
        if not os.path.exists(self.file_path):
            with open(self.file_path, 'w') as fid:
                fid.write(text + '\n')
        else:
            with open(self.file_path, 'a') as fid:
                fid.write(text + '\n')


if __name__ == '__main__':
    pass
    # p = Project()
    # p.setup_project()
    # # p.select_plugins(['SHARKtools_qc_sensors', 'SHARKtools_tavastland'])
    # p.download_program()
    # p.download_sharkpylib()
    # # p.create_environment()
    # # p.install_packages()
    # # p.create_run_program_file()
