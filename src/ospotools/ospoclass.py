from github import Github
from github import Auth
from github.GithubException import UnknownObjectException

class OSPORepository:
    def __init__(self, repo):
        self.repository = repo