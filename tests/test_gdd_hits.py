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

def test_repotest():
    assert odt.repotest(None)['repo'] is None, "Function accepts None types, returns None." 
    assert odt.repotest(1234)['repo'] is None, "Function accepts int types, returns None."
    assert odt.repotest("implementing the tidal adaptation of WRTDS is available for download at https://github.com/fawda123/WRTDStidal. SUPPORTING INFORMATION Additional supporting")['repo'] == "github.com/fawda123/WRTDStidal", "Function accepts string types, returns the repository properly."
