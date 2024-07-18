"""_Crawl all GitHub repositories stored in the OSPO database with a given delay._
"""

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

dotenv.load_dotenv()
conn_dict = json.loads(os.getenv('OSDB_CONNECT'))

conn = psycopg2.connect(**conn_dict, connect_timeout=5)

repos = gdo.get_repository_urls(conn)

#for i in repos:
#    gdo.update_repo_name_db(conn, i[0])

unscanned_queries = """SELECT DISTINCT url
                       FROM repositories AS rp
                       LEFT JOIN repositoryowners AS rpo ON rpo.ownerid = rp.ownerid
                       WHERE rp.url ILIKE '%github%' AND rpo.managerid IS NULL;"""
with conn.cursor() as cur:
    cur.execute(unscanned_queries)
    repos = cur.fetchall()

for i in repos:
    try:
        gdo.update_repo_add_owner(conn, i[0])
        print(i[0])
    except Exception as e:
        conn.rollback()
        print(f"Error for {i[0]}\nException: {e}")

uw_owners = """SELECT DISTINCT rpo.ownername
               FROM repositories AS rp
               LEFT JOIN repositoryowners AS rpo ON rpo.ownerid = rp.ownerid
               WHERE rpo.email ILIKE '%wisc.edu%';"""
with conn.cursor() as cur:
    cur.execute(uw_owners)
    owners = cur.fetchall()

for i in owners:
    gdw.uw_validate_owners(conn,
                           owner = i[0],
                           relation = 'UW Person',
                           add_repos = True,
                           auth = None)
