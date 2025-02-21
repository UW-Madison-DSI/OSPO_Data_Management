import psycopg2
import dotenv
import json
import os
import ospotools.ospo_db_tools as odt

class Connector:
    def __init__(self):
        dotenv.load_dotenv()
        conn_dict = json.loads(os.getenv('OSDB_CONNECT'))
        self.conn = psycopg2.connect(**conn_dict, connect_timeout=5)

def test_process_gdd_hit():
    conn = Connector()
    doi = 'abcd'
    highlight = 'Nothing passed'