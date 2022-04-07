import datetime
import subprocess
from pathlib import Path


class Backup:
    _working_dir = None
    _source_path = None
    _backup_path = None
    options = dict(must_include_subdirs=[],
                   do_not_copy_subdirs=[])

    def __init__(self, working_dir, **options):
        path = Path(working_dir)
        if not path.exists():
            raise NotADirectoryError(f'Woking directory does not exist: {path}')
        if not path.is_dir():
            raise NotADirectoryError(f'Given working path is not a directory')
        self._working_dir = path
        self.options.update(options)

    @property
    def source_directory(self):
        return self._source_path

    def set_source_directory(self, path):
        path = Path(path)
        if not path.is_dir():
            raise NotADirectoryError(path)
        if self.options.get('must_include_subdirs'):
            subdirs = [p.name for p in list(path.iterdir())]
            if not all([name in subdirs for name in self.options.get('must_include_subdirs')]):
                raise Exception(f'Mappen måste innehålla undermapar: {"; ".join(self.options.get("must_include_subdirs"))}')
        self._source_path = path
        self._backup_path = None

    @property
    def backup_directory(self):
        return self._backup_path

    def set_backup_directory(self, path):
        if not self._source_path:
            raise Exception('Välj källmapp först!')
        path = Path(path)
        if not path.is_dir():
            raise NotADirectoryError(path)
        bstring = f'backup_{self._source_path.name}'
        date_string = datetime.datetime.now().strftime('%Y%m%d')
        subdir = f'{bstring}_{date_string}'
        if path.name.startswith(bstring):
            path = path.parent
        if path.name != subdir:
            path = Path(path, subdir)
        self._backup_path = path

    def backup(self):
        if not self._source_path:
            raise NotADirectoryError('Ingen källmapp satt')
        if not self._backup_path:
            raise NotADirectoryError('Ingen backupmapp satt')
        if not self._backup_path.exists():
            self._backup_path.mkdir(parents=True, exist_ok=True)
        if list(self._backup_path.iterdir()):
            raise Exception(f'Backupmappen måste vara tom: {self._backup_path}')
        path = Path(self._working_dir, 'backup.bat')
        dont_copy_str = '/xd ' + ' '.join(self.options.get('do_not_copy_subdirs'))
        with open(path, 'w') as fid:
            fid.write(f'robocopy {self._source_path} {self._backup_path} /s {dont_copy_str}')
        subprocess.call([str(path)])
