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

hits = [{"doi": "10.1016/j.rse.2016.03.035", "highlight": {"repo": "github.com/downloads/bcdev", "highlight": "Re\ufb02ectance Algorithm Theoretical Basis Document (ATBD), available at: http://github.com/downloads/bcdev/beam-merisaatsr-synergy/synergy-land_aerosol-atbd.pdf"}, "status": "Invalid repository name."},
{"doi": "10.1111/nyas.13281", "highlight": {"repo": "github.com/G-Node/nix", "highlight": "utility to address the needs outlined here.28 The NIX project (https://github.com/G-Node/nix/ wiki), derived from the previously published"}, "status": "Exception Error."},
{"doi": "10.1111/1752-1688.12489", "highlight": {"repo": "github.com/fawda123/WRTDStidal", "highlight": "implementing the tidal adaptation of WRTDS is available for download at https://github.com/fawda123/WRTDStidal. SUPPORTING INFORMATION Additional supporting"}, "status": "Exception Error."},
{"doi": "10.1111/evo.13012", "highlight": {"repo": "github.com/ropensci/taxize", "highlight": "information from around the web. R package ver. 0.3.0. Available via https://github.com/ropensci/taxize. Cristol, D. A., E. B. Reynolds, J. E. Leclerc,"}, "status": "Exception Error."},
]

def test_repotest():
    strings = [1233,
               "implementing the tidal adaptation of WRTDS is available for download at https://github.com/fawda123/WRTDStidal. SUPPORTING INFORMATION Additional supporting",
               None,
               "https://github.com/SimonGoring"]
    test_outcomes = [odt.repotest(i) for i in strings]
    assert odt.repotest(None)['repo'] is None, "Function accepts None types, returns None." 
    assert odt.repotest(1234)['repo'] is None, "Function accepts int types, returns None."
    assert odt.repotest("implementing the tidal adaptation of WRTDS is available for download at https://github.com/fawda123/WRTDStidal. SUPPORTING INFORMATION Additional supporting")['repo'] == "github.com/fawda123/WRTDStidal", "Function accepts string types, returns the repository properly."
