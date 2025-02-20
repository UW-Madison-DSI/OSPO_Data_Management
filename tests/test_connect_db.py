import pytest
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

def test_check_repo():
    repos = ["https://github.com/G-Node/nix","github.com/G-Node/nix"]
    clean_repos = [odt.clean_repo_name(i) for i in repos]
    object = [odt.check_repository_db(Connector().conn, i) for i in clean_repos]
    assert type(object[0]) is tuple, "This connection should have returned an object."
    assert all([i == object[0] for i in object]), "All repos should be the same, but they aren't."


