import dotenv
import json
import os
import pyarrow.parquet as pq
import psycopg2

dotenv.load_dotenv()
con_env = os.getenv('OSDB_CONNECT') or 'ERROR'
try:
    con_dict = json.loads(con_env)
except ValueError:
    print("Provide a valid json formatted connection string in a .env file.")
    print('e.g.: {"host": "localhost","port": 5432,"database": "neotoma","user": "postgres","password": "postgres"}')

conn = psycopg2.connect(**con_dict)
cur = conn.cursor()

repos = pq.read_table('source_data/repo.parquet').to_pylist()

# First pass in the owners
ownerset = set(i.get('owner') for i in repos)
for i in ownerset:
    
# Then pass in the repos
# Then pass in the crawled data


repos.  row_group(0).column(0)

aa = list(filter(lambda x: x.get('owner') == 'Sofia Alejandra Avila Nevarez', repos))