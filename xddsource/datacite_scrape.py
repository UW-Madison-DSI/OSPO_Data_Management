import re
import json
from psycopg2 import sql
import os
import gddospo.ospo_db_tools as gdo
import gddospo.gdd_tools as gdt
from pytacite import DOIs, Clients, Events, Prefixes, ClientPrefixes, Providers, ProviderPrefixes
import dotenv
import psycopg2

dotenv.load_dotenv()
conn_dict = json.loads(os.getenv('OSDB_CONNECT'))

conn = psycopg2.connect(**conn_dict, connect_timeout=5)

def clean_dc_repo(repo_name):
    aa = re.search(r'(https://github.com/[a-z0-9]+(?:(?:(?:[._]|__|[-]*)[a-z0-9]+)+)?/[a-z0-9]+(?:(?:(?:[._]|__|[-]*)[a-z0-9]+)+)?)', repo_name)
    if aa:
        return aa.group(0)
    else:
        return None

client = Clients().query("Zenodo").get()
query = DOIs() \
    .filter(client_id=client[0]["id"]) \
    .filter(resource_type_id="software") \
    .filter(relatedIdentifers={"relatedIdentifiers.relatedIdentifier":'*github.com*'}) \
    .paginate(per_page=100)

for page in query:
    for record in page:
        record_attr = record.get("attributes")
        url = map(lambda x: clean_dc_repo(x.get("relatedIdentifier")), record_attr["relatedIdentifiers"])
        gitrepos = [i for i in url if i]
        if len(gitrepos) > 0:
            title = [i.get("title") for i in record_attr.get("titles")]
            description = [i.get("description") for i in record_attr.get("descriptions")]
            print(f"Running {record_attr.get("doi")}: {title[0]}")
            for repo in gitrepos:
                repoid = gdo.check_repository_db(conn, repo)
                if repoid is None:
                    repoid = gdo.add_repo_db(conn, repo, 'DataCite Submission')
                if repoid:
                    insertobj = {"doi": record_attr.get("doi"),
                                "datacitemeta": json.dumps(record),
                                "title": title[0],
                                "description": description[0],
                                 "repositoryid": repoid }
                    query = """INSERT INTO datacitepublication (doi, datacitemeta, title, description, repositoryid)
                                VALUES (%(doi)s, %(datacitemeta)s, %(title)s, %(description)s, %(repositoryid)s) 
                                ON CONFLICT (doi) DO UPDATE
                                SET datacitemeta = EXCLUDED.datacitemeta;"""
                    try:
                        with conn.cursor() as cur:
                            cur.execute(query, insertobj)
                        conn.commit()
                    except Exception as e:
                        print(e)
                        conn.rollback()

