"""_Crawl all GitHub repositories stored in the OSPO database with a given delay._
   This should be a script that runs periodically.
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

#for i in repos:
#    gdo.update_repo_name_db(conn, i[0])

unscanned_queries = """SELECT rp.url
                       FROM repositories AS rp
                       LEFT JOIN repositorycrawls AS rpc ON rp.repositoryid = rpc.repositoryid
                       LEFT JOIN repoqualitychecks AS rpqc ON rpc.repositoryid = rp.repositoryid
                       WHERE rpc.crawl_at < LOCALTIMESTAMP - INTERVAL '2 week'
                       AND rpqc.badstatus IS NULL;"""

with conn.cursor() as cur:
    cur.execute(unscanned_queries)
    repos = cur.fetchall()

for i in repos:
    try:
        gdo.update_repo_crawl_db(conn, i[0])
        # gdo.update_repo_add_owner(conn, i[0])
        print(i[0])
    except Exception as e:
        conn.rollback()
        print(f"Error for {i[0]}\nException: {e}")
