"""_Add records from GitHub by searching all repositories where
    the user company is listed as "University of Wisconsin"._
"""

import dotenv
import json
from crossref.restful import Works
import psycopg2
import os
from github import Github
from github import Auth
from github.GithubException import UnknownObjectException
import ospotools.ospo_db_tools as gdo
import ospotools.ospo_uw_tools as gdw

dotenv.load_dotenv()
conn_dict = json.loads(os.getenv('OSDB_CONNECT'))

conn = psycopg2.connect(**conn_dict, connect_timeout=5)

auth = os.getenv('GITHUB_TOKEN')
G_AUTH = Auth.Token(auth)
gi = Github(auth=G_AUTH)

for i in ['followers', 'repositories', 'joined']:
    for k in ['asc', 'desc']:
        result = gi.search_users(query='"University of Wisconsin" in:company', order = k, sort = i)
        for user in result:
            owner_exists = gdo.check_owner(conn, user.login)
            repos = user.get_repos()
            if repos.totalCount > 0:
                try:
                    for repo in repos:
                        new_id = gdo.add_repo_db(conn, repo = repo.html_url, source="UW Person Search (by Company Name)")
                    gdw.uw_validate_owners(conn, user.login, relation = 'UW Person', add_repos = False)
                except:
                    conn.rollback()


for user in result:
    try:
        gdw.uw_validate_owners(conn, user.login, relation = 'UW Person', add_repos = False)
    except:
        conn.rollback()

user.login = 'SimonGoring'