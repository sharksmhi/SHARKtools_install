

class MissingVenvException(Exception):
    def __init__(self, msg):
        super().__init__(msg)


class CantRunProgramException(Exception):
    def __init__(self, msg):
        super().__init__(msg)