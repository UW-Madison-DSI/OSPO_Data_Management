import json
import os
import dotenv
import psycopg2
import ospotools.ospo_db_tools as gdo

dotenv.load_dotenv()
conn_dict = json.loads(os.getenv('OSDB_CONNECT'))

conn = psycopg2.connect(**conn_dict, connect_timeout=5)

repos = gdo.get_repository_urls(conn)
dirty_names = [i[0] for i in repos if i[0] != gdo.clean_repo_name(i[0])]

for i in dirty_names:
    new_name = gdo.clean_repo_name(i)
    if gdo.check_repository_db(conn, new_name) is not None:
        update_name_query = """
            UPDATE repositories
            SET url = %s
            WHERE url = %s"""
        try:
            with conn.cursor() as cur:
                cur.execute(update_name_query, (new_name, i))
            conn.commit()
        except Exception as e:
            print(e)
            conn.rollback()
