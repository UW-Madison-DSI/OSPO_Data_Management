"""GitHub Python scraper.

Linking to github repositories to find all repositories that contain code
cited by journal articles in GeoDeepDive.

"""

import json
import requests
import os
import dotenv
import psycopg2
import ospotools.ospo_db_tools as gdo
import ospotools.gdd_tools as gdt
import pandas as pd
from time import sleep

dotenv.load_dotenv()
conn_dict = json.loads(os.getenv('OSDB_CONNECT'))

conn = psycopg2.connect(**conn_dict, connect_timeout=5)

pausetime = 2

thing = 0
maxhits = 0

# This will generate a large-ish number of papers and grants.
gddurl = ("https://geodeepdive.org/api/v1/snippets?"
          + "term=gitlab.com,bitbucket.com,github.com"
          + "&clean&full_results")

hits = True
paperCt = 0
data = []

resultset = {'good':[], 'bad':[]}

while hits:
    print(f'Have run {len(data)} papers, looking for {maxhits}')
    try:
        results = requests.get(gddurl)
    except requests.exceptions.MissingSchema:
        break
    if results.status_code == 200:
        output = results.json()
        gddurl = output.get('success').get('next_page')
        maxhits = output.get('success').get('hits')
        if len(output.get('success').get('data')) > 0:
            data = data + output['success']['data']

         
for papers in data:
    print(f"Running {papers['doi']} -- paper {paperCt}")
    repohits = map(lambda x: gdt.repotest(x), papers['highlight'])
    repohit = list(repohits)
    if any(repohit):
        outcome = gdo.process_gdd_hit(conn, papers['doi'], papers['highlight'])
        if len(outcome) > 0:
            conn.rollback()
            with open('failed_extract.json', 'a') as fe:
                fe.write(json.dumps(outcome) + '\n')
    paperCt = paperCt + 1

df = pd.read_json('failed_extract.json', lines=True)

records = list(map(json.loads, open('failed_extract.json')))

pd.json_normalize(records).to_csv('failed_extract.csv')
