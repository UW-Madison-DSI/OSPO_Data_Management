"""_Crawl all GitHub repositories stored in the OSPO database with a given delay._
"""

import json
import os
import dotenv
import psycopg2
import ospotools.ospo_db_tools as gdo
import ospotools.ospo_uw_tools as gdw
from github import Github
from github import Auth

dotenv.load_dotenv()
conn_dict = json.loads(os.getenv('OSDB_CONNECT'))

conn = psycopg2.connect(**conn_dict, connect_timeout=5)


def get_repo_count(conn, ownername):
    user_repos = """SELECT COUNT(*)
                    FROM repositories AS rp
                    INNER JOIN repositoryowners AS rpo ON rpo.ownerid = rp.ownerid
                    WHERE rpo.ownername = %s"""
    with conn.cursor() as cur:
        cur.execute(user_repos, (ownername,))
        owners = cur.fetchone()
    return owners[0]


# First, query all repositories that don't have "owner" information:
unscanned_owners = """SELECT ownername FROM repositoryowners;"""

with conn.cursor() as cur:
    cur.execute(unscanned_owners)
    owners = cur.fetchall()

auth = os.getenv('GITHUB_TOKEN')
G_AUTH = Auth.Token(auth)
gi = Github(auth=G_AUTH)

for i in owners:
    print(f'Running user {i[0]}.')
    user = gi.get_user(i[0])
    repos = user.get_repos()
    repo_count = get_repo_count(conn, i[0])
    if repos.totalCount > 0 and repo_count < repos.totalCount:
        for repo in repos:
            try:
                new_id = gdo.add_repo_db(conn, repo = repo.html_url, source="Fill in the repositories from the set of existing users.")
            except Exception as e:
                conn.rollback()
                print(f"Error for {i[0]}\nException: {e}")
