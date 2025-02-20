from ospotools.ospo_db_tools import clean_repo_name
import re

def test_cleaning_names():
    NAMES = ['htp:/github.cam/robot',
             'robot/package toast.',
             'https://github.com/harrietlau/ Complex- Viscosity',
             'http://github.com/SimonGoring/repo',
             'http://github.com/SimonGoring/repo,',
             'http://github.com/SimonGoring/repo.',
             'http://github.com/SimonGoring/repo ',
             None]
    cleaned = [clean_repo_name(i) for i in NAMES]
    assert len([i for i in cleaned if i]) == len(NAMES) - 1, "None values are not being passed properly."
    assert all([re.match('^https://', i) for i in cleaned if i]), "'https:// is not being prepended properly."
    assert all([len(i) == len(i.strip()) for i in cleaned if i]), "Whitespace is not being properly removed."