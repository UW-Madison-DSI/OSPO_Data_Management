import json
import requests
import re
import os
import dotenv
import psycopg2
import datetime
import gddospo.ospo_db_tools as gdo
import gddospo.gdd_tools as gdt
import gddospo.ospo_uw_tools as gdw
from github import Github
from github import Auth
from github.GithubException import UnknownObjectException


dotenv.load_dotenv()
conn_dict = json.loads(os.getenv('OSDB_CONNECT'))

conn = psycopg2.connect(**conn_dict, connect_timeout=5)

query = """
    SELECT rp.*
    FROM repositories AS rp
    LEFT JOIN repoqualitychecks AS rpc ON rpc.repositoryid = rp.repositoryid
    WHERE
        created_at IS NULL
        AND rpc.badstatus IS NULL;"""

with conn.cursor() as cur:
    cur.execute(query)
    repos = cur.fetchall()

auth = os.getenv('GITHUB_TOKEN')
G_AUTH = Auth.Token(auth)
gi = Github(auth=G_AUTH)

for i in repos:
    repo_name = gdo.clean_repo_name(i[1])
    if i[1] == gdo.clean_repo_name(i[1]):
        repo_string = re.findall(r'(github\.com\/)(.+?)$', repo_name)
        if len(repo_string) == 0:
            continue
        try:
            repo_object = gi.get_repo(repo_string[0][1])
        except UnknownObjectException as e:
            bad_repo_query = """
                INSERT INTO repoqualitychecks (repositoryid, badstatus)
                VALUES (%s, %s);
                """
            try:
                with conn.cursor() as cur:
                    cur.execute(bad_repo_query, (i[0], e.status))
                conn.commit()
            except Exception as e:
                conn.rollback()
        else:
            try:    
                update_created_query = """
                    UPDATE repositories
                    SET created_at = %s
                    WHERE url = %s"""
                with conn.cursor() as cur:
                    cur.execute(update_created_query, (repo_object.created_at, repo_name))
                conn.commit()
            except Exception as e:
                print(e)
                conn.rollback()
                continue
