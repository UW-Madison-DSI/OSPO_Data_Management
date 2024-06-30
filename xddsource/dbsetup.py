import dotenv
import json
import os
import re
import psycopg2
import pyarrow.parquet as pq
import gddospo.ospo_db_tools as gdo

dotenv.load_dotenv()
conn_dict = json.loads(os.getenv('OSDB_CONNECT'))
conn_dict['port'] = 5432
conn = psycopg2.connect(**conn_dict, connect_timeout=5)

repos = pq.read_table('../source_data/repo.parquet').to_pylist()

# Add owners:
ownerset = set(i.get('owner') for i in repos)
for i in ownerset:
    with conn.cursor() as cur:
        cur.execute("""INSERT INTO repositoryowners(ownername) VALUES (%s)
                    ON CONFLICT DO NOTHING;""",
                    (i,))

conn.commit()

# Add repos:
for i in repos:
    i['url'] = re.sub('\.git$', '', i.get('url'))
    repositoryid = gdo.add_repo_db(conn, i.get('url'), 'Bulk Submision OSPO')
    with conn.cursor() as cur:
        try:
            cur.execute("""INSERT INTO uwrepositories (repositoryid, uwrelationid) VALUES
                            (%s, (SELECT uwrelationid FROM uwrelations WHERE uwrelation = 'Keyword Search'))
                            ON CONFLICT DO NOTHING;""",
                        (repositoryid,))
            conn.commit()
        except Exception as e:
            print(f"Error: {e}")
            conn.rollback()
