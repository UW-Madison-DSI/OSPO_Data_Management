import psycopg2
import dotenv
import json
import os
import ospotools.ospo_db_tools as odt


def test_repotest_str_inputs():
    assert odt.repotest(None)['repo'] is None, "Function accepts None types, returns None." 
    assert odt.repotest(1234)['repo'] is None, "Function accepts int types, returns None."
    assert odt.repotest("implementing the tidal adaptation of WRTDS is available for download at https://github.com/fawda123/WRTDStidal. SUPPORTING INFORMATION Additional supporting")['repo'] == "github.com/fawda123/WRTDStidal", "Function accepts string types, returns the repository properly."

def test_repotest():
    simple_string_repo = "This has a repo at https://github.com/SimonGoring/reponame"
    result = odt.repotest(simple_string_repo)
    assert result['repo'] == "github.com/SimonGoring/reponame", "Did not find the proper repository name."
    assert result['highlight'] == simple_string_repo, "Highlight is not being returned from repotest."
    
    no_repo = "This result is just a result."
    result = odt.repotest(no_repo)
    assert result['repo'] is None, "Matched a repository name that wasn't there."
    assert result['highlight'] == no_repo, "Highlight is not being returned from repotest."

    complex_string_repo = "This has a repo at https://github.com/SimonGoring/reponame and at https://github.com/SimonGoring/reponameb"
    result = odt.repotest(complex_string_repo)
    assert result['repo'] == "github.com/SimonGoring/reponame", "Matched a repository name that wasn't there."
    assert result['highlight'] == complex_string_repo, "Highlight is not being returned from repotest."
