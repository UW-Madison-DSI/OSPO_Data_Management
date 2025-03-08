"""_Crawl all GitHub repositories stored in the OSPO database with a given delay._
"""

import json
import os
import dotenv
import psycopg2
import ospotools.ospo_db_tools as gdo

dotenv.load_dotenv()
conn_dict = json.loads(os.getenv('OSDB_CONNECT'))

conn = psycopg2.connect(**conn_dict, connect_timeout=5)

repos = gdo.get_repository_urls(conn)

# First, query all repositories that don't have "owner" information:
unscanned_queries = """SELECT DISTINCT url
                       FROM repositories AS rp
                       LEFT JOIN repositoryowners AS rpo ON rpo.ownerid = rp.ownerid
                       LEFT JOIN repositorycrawls AS rcl ON rcl.repositoryid = rp.repositoryid
                       WHERE rp.url ILIKE '%github%'
                         AND rp.ownerid IS NULL
                         AND ((NOT rcl.httpstatus = 404) or (rcl.httpstatus is null));"""

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
