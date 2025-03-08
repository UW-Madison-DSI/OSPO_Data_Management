"""_Assign ownership of repos to a "University of Wisconsin" Person_

   by: Simon Goring
   date: 7 March, 2025
   
   Here we define the person based on their having a UW email address.
   Currently, we cannot search repositories using approximate matching
   on the users email. Our workaround here is to search for repository
   owners who have listed a University of Wisconsin email as part of 
   their user metadata.

   From there we can assign all the repositories they manage to UW.

   This script is intended to run after any of the big data
   ingest steps.
"""

import json
import os
import dotenv
import psycopg2
import ospotools.ospo_db_tools as gdo
import ospotools.ospo_uw_tools as gdw

dotenv.load_dotenv()
conn_dict = json.loads(os.getenv('OSDB_CONNECT'))

conn = psycopg2.connect(**conn_dict, connect_timeout=5)

# Then look through those repositories and assign to UW if we see that the email is a wisc email. 
uw_owners = """SELECT DISTINCT rpo.ownername
               FROM repositories AS rp
               LEFT JOIN repositoryowners AS rpo ON rpo.ownerid = rp.ownerid
               WHERE rpo.email ILIKE '%wisc.edu%';"""

with conn.cursor() as cur:
    cur.execute(uw_owners)
    owners = cur.fetchall()

for i in owners:
    gdw.uw_validate_owners(conn,
                           owner = i[0],
                           relation = 'UW Person',
                           add_repos = False,
                           auth = None)
