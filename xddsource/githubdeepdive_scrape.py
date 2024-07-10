"""GitHub Python scraper.

Linking to github repositories to find all repositories that contain code
cited by journal articles in GeoDeepDive.

"""

import json
import requests
import re
import os
import dotenv
import psycopg2
import datetime
import gddospo.ospo_db_tools as gdo
import gddospo.gdd_tools as gdt

dotenv.load_dotenv()
conn_dict = json.loads(os.getenv('OSDB_CONNECT'))

conn = psycopg2.connect(**conn_dict, connect_timeout=5)

pausetime = 2

thing = 0
maxhits = 0

# This will generate a large-ish number of papers and grants.
gddurl = ("https://geodeepdive.org/api/snippets?"
          + "term=gitlab.com,bitbucket.com,github.com"
          + "&clean&full_results")

hits = True
paperCt = 0

resultset = {'good':[], 'bad':[]}

while hits:
    print('Have run ' + str(paperCt)
          + ' papers, looking for ' + str(maxhits))
    try:
        results = requests.get(gddurl)
    except requests.exceptions.MissingSchema:
        break
    if results.status_code == 200:
        output = results.json()
        gddurl = output.get('success').get('next_page')
        maxhits = output.get('success').get('hits')
        if len(output.get('success').get('data')) > 0:
            data = output['success']['data']
            for papers in data:
                if gdo.check_publication_db(conn, papers['doi']) is None:
                    print("Running " + papers['doi'])
                    repohits = map(lambda x: gdt.repotest(x), papers['highlight'])
                    repohit = list(repohits)
                    if any(repohit):
                        for hit in repohit:
                            if hit is not None:
                                newid = gdo.add_repo_db(conn, hit['repo'], 'xDD Pipeline Submission')
                            if newid is not None:
                                newpub = gdo.add_publication_db(conn, papers.get('doi'), 'xDD Pipeline Submission')
                                if newpub is not None:
                                    gdo.link_publication_repository_db(conn, newpub, newid, 'xDD API Scraper')
                                    print('Linked this publication and repository.')
                                    resultset['good'].append({'doi': papers.get('doi'), 'highlight': hit})
                                else:
                                    print(f"Failed to add {papers.get('doi')} to the database.")
                                    resultset['bad'].append({'doi': papers.get('doi'), 'highlight': hit})
                            else:
                                print(f"Failed to add repository {hit['repo']} to the database.")
                                resultset['bad'].append({'doi': papers.get('doi'), 'highlight': hit})
                paperCt = paperCt + 1
        else:
            break
