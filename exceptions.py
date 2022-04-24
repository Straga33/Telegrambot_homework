class CheckStatusEndpoint(Exception):
    def __init__(self, text):
        self.txt = text

class CheckHomeworksInResponse(Exception):
    def __init__(self, text):
        self.txt = text

class CheckHomeworkStatus(Exception):
    def __init__(self, text):
        self.txt = text

class DebugHomeworkStatus(Exception):
    def __init__(self, text):
        self.txt = text
