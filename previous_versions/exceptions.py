

class MissingVenvException(Exception):
    def __init__(self, msg=''):
        super().__init__(msg)


class CantRunProgramException(Exception):
    def __init__(self, msg=''):
        super().__init__(msg)


class NoPythonExeFound(Exception):
    def __init__(self, msg=''):
        super().__init__(msg='')


class NoPluginsSelected(Exception):
    def __init__(self, msg=''):
        super().__init__(msg)