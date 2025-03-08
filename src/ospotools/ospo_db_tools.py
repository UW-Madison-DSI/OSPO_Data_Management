import dotenv
import re
import requests
import json
import datetime
from crossref.restful import Works
from psycopg2 import sql
import psycopg2
import os
import validators
from github import Github
from github import Auth
from github.GithubException import UnknownObjectException

class osdb(object):
    conn = None
    def __init__(self):
        dotenv.load_dotenv()
        conn_dict = json.loads(os.getenv('OSDB_CONNECT'))
        self.conn = psycopg2.connect(**conn_dict, connect_timeout=5)
    def check_repository(self, repo:str):
        """_Is the repository in the OSPO Database?_

        Args:
            conn (psycopg2.extensions.connection): _A valid psycopg2 connection to the OSPO database._
            repo (_str_): _A valid repository URL string._

        Returns:
            _tuple_: _A valid repositoryid (from the OSPO database), or None._
        """
        repos = None
        clean_repo = clean_repo_name(repo)
        check = """SELECT repositoryid
                   FROM repositories
                   WHERE url = %s"""
        with self.conn.cursor() as cur:
            cur.execute(check, (clean_repo,))
            # There is a constraint on unique URLs
            repos = cur.fetchone()
        return repos

def clean_repo_name(repo_name:str) -> str:
    """_Clean a repository URL so that it conforms to expected format._
    
    This function takes a name and clears out terminal whitespace as well 
    as non-printing ASCII characters to ensure consistency across function
    calls.

    Finally, tests that the cleaned up repository name is actually a
    valid URL.
    
    Args:
        repo_name (_str_): _The passed name of a code repository._

    Returns:
        _str_: _A cleaned repository URL, with an https prefix._
    """
    repo_check = None
    if repo_name is None:
        # Nothing passed in, we pass nothing back out.
        return None
    # remove non printing characters
    repo_sub = re.sub(r'[/., ]*$',
                      '',
                      "".join([i for i in repo_name if i.isprintable()]))
    repo_sub = re.sub(r' ', '', repo_sub)
    if not re.search('^http[s]{,1}://.*', repo_sub):
        # We allow http if it's in the paper, but should be https otherwise.
        repo_check = f'https://{re.sub('/[^\x20-\x7E]+$', '', repo_sub)}'
    else:
        repo_check = re.sub(r'^http://', 'https://', repo_sub)
    return repo_check

def check_repository_url(conn, repo:str, verbose:bool = True, update:bool = True) -> object:
    """_Validate the repository path using a HEAD call._
    This 

    Args:
        repo (_str_): _A cleaned repository URL_
        verbose (_bool_): _Should we return text describing any issues? (Default: False)_
    Returns:
        _object_: _Returns True if the HEAD call returns 200._
    """
    if repo is None:
        return False
    check_repo = clean_repo_name(repo)
    valid_repo = validators.url(check_repo)
    if not valid_repo:
        if verbose:
            print(f"The passed URL for the repository {check_repo} is not a valid URL.")
        return {"status": False, "redirect": None}
    try:
        check = requests.head(check_repo, allow_redirects=True)
        match check.status_code:
            case 200:
                if check.url == check_repo:
                    return {"status": True, "redirect": None }    
            case 401:
                if update:
                    update_repo_404(conn, repo, verbose)
                return {"status": False, "redirect": 401 }
            case 403:
                if update:
                    update_repo_404(conn, repo, verbose)
                return {"status": False, "redirect": 403 }
            case 404:
                if update:
                    update_repo_404(conn, repo, verbose)
                return {"status": False, "redirect": 404 }
    except Exception as e:
        print(f'Failed to resolve: {e}')
    return {"status": False, "redirect": None }

def check_doi(doi:str) -> str:
    """_Make sure that the DOI is valid._

    Args:
        doi (str): _A valid DOI string_

    Returns:
        str: _Returns a valid DOI, or None if the DOI is invalid._
    """     
    return doi

def check_repository_db(conn:psycopg2.extensions.connection, repo:str) -> tuple:
    """_Is the repository in the OSPO Database?_

    Args:
        conn (psycopg2.extensions.connection): _A valid psycopg2 connection to the OSPO database._
        repo (_str_): _A valid repository URL string._

    Returns:
        _tuple_: _A valid repositoryid (from the OSPO database), or None._
    """
    repos = None
    clean_repo = clean_repo_name(repo)
    check = """SELECT repositoryid
               FROM repositories
               WHERE url = %s"""
    with conn.cursor() as cur:
        cur.execute(check, (clean_repo,))
        # There is a constraint on unique URLs
        repos = cur.fetchone()
    return repos

def check_last_crawl(conn:psycopg2.extensions.connection, repository:str) -> tuple:
    """_Check the repository to see when it was last crawled._

    Args:
        conn (psycopg2.extensions.connection): _A valid psycopg2 connection to the OSPO database._
        repository (str): _A valid repository URL from the database._

    Returns:
        tuple: _A tuple, returning the repository URL and the last crawl date._
    """
    crawl_check = """
        SELECT rp.url, MAX(rpc.crawl_at)
        FROM repositories AS rp
        INNER JOIN repositorycrawls AS rpc ON rp.repositoryid = rpc.repositoryid
        WHERE url = %s
        GROUP BY rp.url;"""
    with conn.cursor() as cur:
        cur.execute(crawl_check, (repository,))
        last_crawl = cur.fetchone()
    return last_crawl

def check_owner(conn:psycopg2.extensions.connection, owner:str) -> tuple:
    """_Get the owner ID for a repository._

    Args:
        conn (psycopg2.extensions.connection): _A valid psycopg2 connection to the OSPO database._
        owner (str): _description_

    Returns:
        tuple: _description_
    """
    owner_db = """
    SELECT ownerid FROM repositoryowners WHERE ownername = %s"""
    with conn.cursor() as cur:
        cur.execute(owner_db, (owner,))
        ownerid = cur.fetchone()
    return ownerid

def check_repository_owner(conn:psycopg2.extensions.connection, repository:str) -> tuple:
    owner_query = """
    SELECT rp.ownerid FROM repositories AS rp
    INNER JOIN repositoryowners AS rpo ON rpo.ownerid = rp.ownerid
    WHERE url = %s;"""
    with conn.cursor() as cur:
        cur.execute(owner_query, (repository,))
        ownerid = cur.fetchone()
    return ownerid

def update_repo_add_owner(conn:psycopg2.extensions.connection, 
                          repository:str,
                          auth:str = None,
                          update:bool = True,
                          manager:str = "GitHub") -> bool:
    """_Add the repository owner (the individual who created the repository) to the repo._

    We use the GitHub API to link the repository to its owner, when that link has not been made.
    From the owner we are able to obtain email addresses.

    Args:
        conn (psycopg2.extensions.connection): _A valid psycopg2 connection to the OSPO database._
        repository (str): _A text string identifying the repository._
        auth (str, optional): _Authentication for the GitHub API._. Defaults to None.
        update (bool, optional): _Should we make an effort to update the record if an owner is identified?_. Defaults to True.
        manager (str, optional): _On which platform do we have the repository?_. Defaults to "GitHub".

    Returns:
        bool: _Returns False if nothing is updated, otherwise, returns True._
    """
    if re.search(r'github\.com', repository) is None:
        # Currently only supports GitHub
        return False
    else:
        repository_id = check_repository_db(conn, repository)
        owner_id = check_repository_owner(conn, repository)
        if repository_id is None:
            return False
        if owner_id is not False and update is False:
            return None
    if auth is None:
        auth = os.getenv('GITHUB_TOKEN')
        if auth is None:
            return False
    G_AUTH = Auth.Token(auth)
    gi = Github(auth=G_AUTH)
    repo_string = re.findall(r'(github\.com\/)(.+?)$', repository)[0][1]
    repo_string = re.sub('/$', '', repo_string)
    if re.search('.+/.+$', repo_string):
        try:
            repo_object = gi.get_repo(repo_string)
            owner = repo_object.owner
        except UnknownObjectException:
            current_date = datetime.datetime.now()
            bad_repo_query = """
                INSERT INTO repositorycrawls (repositoryid, crawl_at, httpstatus)
                VALUES (%s, %s, %s);
                """
            try:
                with conn.cursor() as cur:
                    cur.execute(bad_repo_query, (repository_id, current_date, 404))
                conn.commit()
            except Exception:
                conn.rollback()
            return False
    else:
        owner = gi.get_user(repo_string)
    if owner is not None:
        owner_data = { 'ownername': owner.login,
                       'email': owner.email,
                       'isorganization': (owner.type or '') == 'Organization',
                       'biography': owner.bio,
                       'managername': manager }
    else:
        return False
    insert_owner = """
        INSERT INTO repositoryowners (ownername, email, isorganization, biography, managerid)
        VALUES
        (%(ownername)s, %(email)s, 
         %(isorganization)s, %(biography)s,
         (SELECT managerid FROM repositorymanagers WHERE managername = %(managername)s))
         ON CONFLICT (ownername, managerid) DO UPDATE
         SET email = EXCLUDED.email,
             isorganization = EXCLUDED.isorganization,
             biography = EXCLUDED.biography
        RETURNING ownerid;"""
    add_repo_owner = """
        UPDATE repositories
        SET ownerid = %s
        WHERE repositoryid = %s"""
    with conn.cursor() as cur:
        cur.execute(insert_owner, owner_data)
        owner_id = cur.fetchone()
        cur.execute(add_repo_owner, (owner_id[0], repository_id))
    conn.commit()
    return True

def update_repo_crawl_db(conn:psycopg2.extensions.connection, repo:str, auth:str = None, delay:int = 2) -> int:
    """_summary_

    Args:
        conn (psycopg2.extensions.connection): _A valid psycopg2 connection to the OSPO database._
        repository (_str_): _A valid URL string for a repository_
        auth (_str_, optional): _A valid GitHub (currently) authorization token._. Defaults to None.
        delay (int, optional): _description_. Defaults to 2.

    Returns:
        _type_: _description_
    """
    repository = clean_repo_name(repo)
    current_date = datetime.datetime.now()
    if re.search(r'github\.com\/.+\/.+$', repository) is None:
        # Currently only supports GitHub
        raise ValueError(f"Repository {repository} is not a Github repository. Only Github repositories are supported at this time.")
    else:
        repository_id = check_repository_db(conn, repository)
        owner_id = check_repository_owner(conn, repository)
        if repository_id is None:
            raise ValueError(f"Repository {repository} does not exist in the database.")
        if owner_id is None:
            update_repo_add_owner(conn, repository)
        crawl_check = check_last_crawl(conn, repository)
        if crawl_check is not None:
            if current_date - crawl_check[1] < datetime.timedelta(days = delay):
                raise ValueError(f"Last crawl date is within less than {delay} days of the current crawl.")
        if auth is None:
            auth = os.getenv('GITHUB_TOKEN')
            if auth is None:
                raise TypeError("The authentication token must be supplied explicitly or set as the environment variable GITHUB_TOKEN.")
        G_AUTH = Auth.Token(auth)
        gi = Github(auth=G_AUTH)
    repo_string = re.findall(r'(github\.com\/)(.+?)$', clean_repo_name(repository))[0][1]
    repo_object = gi.get_repo(repo_string)
    try:
        readme = repo_object.get_readme().decoded_content
    except UnknownObjectException as e:
        print(f"Repository {repo_string} has no README: {e}")
        readme = None
    license_name = repo_object.license
    if license_name is not None:
        license_name = license_name.name
    homepage = repo_object.homepage
    if homepage == '':
        homepage = None
    repo_values = {'repositoryid': repository_id,
                   'crawl_at': current_date,
                   'name': repo_object.name,
                   'description': repo_object.description,
                   'homepage': homepage,
                   'last_pushed': repo_object.last_modified_datetime,
                   'license_name': license_name,
                   'language': json.dumps(repo_object.get_languages()),
                   'topics': json.dumps(repo_object.get_topics()),
                   'readme': readme,
                   'stargazers': repo_object.stargazers_count,
                   'issues': repo_object.get_issues().totalCount,
                   'openissues': repo_object.open_issues_count,
                   'forks': repo_object.forks_count,
                   'raw': json.dumps(repo_object.raw_data)}
    insert_query = """
        INSERT INTO repositorycrawls (repositoryid, crawl_at,
                                      name, description, homepage,
                                      last_pushed, license_name,
                                      readme, stargazers, issues,
                                      openissues, forks, raw, language, topics)
        VALUES
        (%(repositoryid)s, %(crawl_at)s, %(name)s, %(description)s, %(homepage)s,
         %(last_pushed)s, %(license_name)s, %(readme)s,
         %(stargazers)s, %(issues)s, %(openissues)s, %(forks)s, %(raw)s, %(language)s, %(topics)s)"""
    with conn.cursor() as cur:
        cur.execute(insert_query, repo_values)
    conn.commit()
    return repository_id

def insert_repository_db(conn:psycopg2.extensions.connection,
                         repo:str,
                         verbose:bool = True,
                         crawl:bool = True):
    """_Add a new repository to the OSPO Database_

    Args:
        conn (psycopg2.extensions.connection): _A valid psycopg2 connection to the OSPO database._
        repo (_type_): _A URL string for a repository._
        verbose (bool, optional): _Should the function return verbose text_? Defaults to True.
        crawl (bool, optional): _On repository insert should we also run a crawl_? Defaults to True.

    Returns:
        _type_: _description_
    """    
    cur = conn.cursor()
    insert = """INSERT INTO repositories(url)
                VALUES (%s)
                ON CONFLICT DO NOTHING
                RETURNING repositoryid;"""
    cur.execute(insert, (repo,))
    result = cur.fetchone()
    conn.commit()
    if crawl:
        update_repo_crawl_db(conn, repo)
    if verbose:
        print(f"Added the repository {repo} to the database.")
    cur.close()
    return result

def clean_crossref_array(value):
    if value is None:
        return None
    elif isinstance(value, str):
        return value
    elif isinstance(value, list):
        if len(value) == 0:
            return None
        elif len(value) == 1:
            return value[0]
        else:
            return ' '.join(value)

def get_datetime(dt_list:list) -> datetime.date:
    """_Get a datetime object from the Crossref date time object._

    Args:
        dt_list (list): _A list of year, month date values._

    Returns:
        datetime.date: _The datetime stamp for the list._
    """    
    if all([isinstance(i, list) for i in dt_list]):
        date_list = dt_list[0]
    else:
        date_list = dt_list
    date_length = len(date_list)
    match date_length:
        case 1:
            return datetime.date(date_list[0], 1, 1)
        case 2:
            return datetime.date(date_list[0], date_list[1], 1)
        case 3:
            return datetime.date(date_list[0], date_list[1], date_list[2])
        case _:
            return None

def add_repository_source(conn:psycopg2.extensions.connection, repositoryid:int, source:str) -> None:
    """_summary_

    Args:
        conn (psycopg2.extensions.connection): _A valid psycopg2 connection object._
        repositoryid (int): _A valid repository ID integer._
        source (str): _A string to explain the source from which the repository was discovered._
    """    
    cur = conn.cursor()
    insert_source = """INSERT INTO repositorysources(repositoryid, sourceid)
                VALUES (%s, (SELECT sourceid FROM ospoimportsources WHERE sourcename = %s))
                ON CONFLICT DO NOTHING;"""
    if isinstance(repositoryid, tuple):
        repositoryid = repositoryid[0]
    cur.execute(insert_source, (repositoryid, source))
    conn.commit()
    cur.close()

def update_repo_404(conn:psycopg2.extensions.connection, repo:str, verbose:bool = False) -> object:
    """_When a repository gets a 404, identify the failure._

    Args:
        conn (psycopg2.extensions.connection): _A valid psycopg2 connection to the OSPO database._
        repo (str): _A URL identifying a repository in the database._
        verbose (bool, optional): _Should the function return text to the screen?_. Defaults to False.

    Returns:
        object: _An object with elements `repository` and `status`._
    """    
    repoid = check_repository_db(conn, repo)
    if repoid:
        bad_repo_query = """
            INSERT INTO repoqualitychecks (repositoryid, badstatus)
            VALUES (%s, 404)
            ON CONFLICT DO NOTHING;
            """
        try:
            with conn.cursor() as cur:
                cur.execute(bad_repo_query, (repoid[0], ))
            conn.commit()
            if verbose:
                print(f'Repository {repo} is in the database but can''t be found. Updated quality checks.')
            return {"repository": repoid, "status": 400}
        except Exception as e:
            print(f"Failed to update.\n{e}")
            conn.rollback()

def add_repo_db(conn:psycopg2.extensions.connection, repo, source, verbose = True):
    """_Add a repository to the OSPO database_

    Args:
        conn (psycopg2.extensions.connection): _A valid psycopg2 connection to the OSPO database._
        repo (_str_): _A string representing the repository location._
        source (_str_): _A valid source type from which the repository was obtained._

    Returns:
        _int_: _The repositoryid for the new repository._
    """
    repo_check = clean_repo_name(repo)
    test_name = validators.url(repo_check)
    if repo_check is None:
        if verbose:
            print(f'Repository {repo_check} (from {repo}) does not have a valid name.')
        return None
    if not test_name:
        if verbose:
            print(f'Repository {repo_check} (from {repo}) is not a valid URL.')
        return None
    repositoryid = check_repository_db(conn, repo_check)
    if repositoryid is None:
        repositoryid = insert_repository_db(conn, repo_check)
        if verbose:
            print(f"Inserted the repository {repo_check} to the database.")
    else:
        if verbose:
            print(f"The repository {repo_check} was already in the database.")
    if isinstance(repositoryid, tuple):
        repositoryid = repositoryid[0]
    add_repository_source(conn, repositoryid, source)
    check_url = check_repository_url(conn, repo = repo_check)
    if not check_url.get('status'):
        update_repo_404(conn, repo_check)
        return None
    elif check_url.get('redirect'):
        redir_repo_query = """
                INSERT INTO repoqualitychecks (repositoryid, badstatus, url)
                VALUES (%s, 301, %s);
                """
        try:
            with conn.cursor() as cur:
                cur.execute(redir_repo_query, (repositoryid, 301, check_url.get('redirect')))
            conn.commit()
        except Exception:
            conn.rollback()
        if verbose:
            print(f'Repository {repo_check} (from {repo}) does not appear to exist.')
        return None
    return repositoryid

def update_repo_name_db(conn:psycopg2.extensions.connection, repository, drop = True):
    if re.search('/$', repository):
        true_repo_id = check_repository_db(conn, repo = repository)
        new_repo_id = check_repository_db(conn, repo = re.sub('/$', '', repository))
    else:
        return None
    if new_repo_id is None:
        update_repo_name = """
            UPDATE repositories
            SET url = %s
            WHERE url = %s"""
        with conn.cursor() as cur:
            cur.execute(update_repo_name, (re.sub('/$', '', repository), repository))
        conn.commit()
    else:
        tables = ['repositorycrawls', 'uwrepositories',
                  'publicationrepolinks', 'repoqualitychecks',
                  'repositorypublications', 'repositorysources']
        reassign_repoid = """
            SELECT * FROM {table}
            WHERE repositoryid = %s;
        """
        for j in tables:
            table_call = sql.SQL(reassign_repoid).format(table=sql.Identifier(j))
            with conn.cursor() as cur:
                cur.execute(table_call, (true_repo_id[0],))
                output = cur.fetchall()
                []
        delete_duplicate = """
        DELETE FROM repositories
        WHERE url = %s;"""
        with conn.cursor() as cur:
            cur.execute(reassign_duplicate, (new_repo_id, true_repo_id))
            cur.execute(delete_duplicate, (repository,))
        conn.commit()
    return None

def check_publication_db(conn:psycopg2.extensions.connection, doi:str):
    cur = conn.cursor()
    check = """SELECT publicationid
               FROM publications
               WHERE doi = %s"""
    try:
        cur.execute(check, (doi,))
        # There is a constraint on unique URLs
        pubs = cur.fetchone()
        cur.close()
    except Exception as e:
        print(e)
        conn.rollback()
        pubs = None
    return pubs

def insert_publication_db(conn:psycopg2.extensions.connection, doi:str):
    cur = conn.cursor()
    insert = """INSERT INTO publications(doi)
                VALUES (%s)
                ON CONFLICT DO NOTHING
                RETURNING publicationid;"""
    cur.execute(insert, (doi,))
    result = cur.fetchone()
    conn.commit()
    cur.close()
    return result

def add_publication_source(conn:psycopg2.extensions.connection, publicationid, source):
    cur = conn.cursor()
    insert_source = """INSERT INTO publicationimport(publicationid, sourceid)
                VALUES (%s, (SELECT sourceid FROM ospoimportsources WHERE sourcename = %s))
                ON CONFLICT DO NOTHING;"""
    if isinstance(publicationid, tuple):
        publicationid = publicationid[0]
    cur.execute(insert_source, (publicationid, source))
    conn.commit()
    cur.close()

def add_publication_db(conn:psycopg2.extensions.connection, doi:str, source):
    """_Add a new publication to the database and fetch relevant metadata._

    Args:
        conn (psycopg2.extensions.connection): _A valid psycopg2 connection to the OSPO database._
        doi (_type_): _A valid crossref DOI_
        source (_type_): _A valid publication source from the OSPO source table._

    Returns:
        _int_: _An integer value for the new publication id generated._
    """
    publicationid = check_publication_db(conn, doi)
    if publicationid is None:
        publicationid = insert_publication_db(conn, doi)
        pubupdateid = add_crossref_meta(conn, doi)
    add_publication_source(conn, publicationid, source)
    return publicationid

def add_crossref_meta(conn:psycopg2.extensions.connection, doi:str):
    cur = conn.cursor()
    works = Works()
    paper_cross = works.doi(doi)
    if paper_cross:
        paper_cross_up = {'title': clean_crossref_array(paper_cross.get('title')),
                        'subtitle': clean_crossref_array(paper_cross.get('subtitle')),
                        'author': json.dumps(paper_cross.get('author')),
                        'subject': paper_cross.get('subject'),
                        'abstract': paper_cross.get('abstract'),
                        'containertitle': clean_crossref_array(paper_cross.get('container-title')),
                        'language': paper_cross.get('language'),
                        'published': get_datetime(paper_cross.get('published').get('date-parts')),
                        'publisher': paper_cross.get('publisher'),
                        'articleurl': paper_cross.get('URL'),
                        'dateadded': datetime.datetime.now(),
                        'crossrefmeta': json.dumps(paper_cross),
                        'doi': paper_cross.get('DOI')}
        pubquery = """UPDATE publications
                        SET title = %(title)s,
                            subtitle = %(subtitle)s,
                            author = %(author)s,
                            subject = %(subject)s,
                            abstract = %(abstract)s,
                            containertitle = %(containertitle)s,
                            language = %(language)s,
                            published = %(published)s,
                            publisher = %(publisher)s,
                            articleurl = %(articleurl)s,
                            crossrefmeta = %(crossrefmeta)s,
                            dateadded = %(dateadded)s
                    WHERE doi = %(doi)s
                    RETURNING doi"""
        cur.execute(pubquery, paper_cross_up)
        conn.commit()
        cur.close()
    return None

def link_publication_repository_db(conn:psycopg2.extensions.connection, publicationid, repositoryid, source):
    cur = conn.cursor()
    insert_link = """INSERT INTO publicationrepolinks (publicationlinkid, publicationid, repositoryid)
                     VALUES ((SELECT publicationlinkid
                              FROM publicationlinks
                              WHERE publicationlinksource = %s),
                              %s,
                              %s)
                              ON CONFLICT DO NOTHING;"""
    cur.execute(insert_link, (source, publicationid, repositoryid))
    conn.commit()
    cur.close()

def get_repository_urls(conn:psycopg2.extensions.connection):
    repo_query = """
    SELECT url FROM repositories;"""
    with conn.cursor() as cur:
        cur.execute(repo_query)
        results = cur.fetchall()
    return list(results)

def process_gdd_hit(conn:psycopg2.extensions.connection, doi:str, highlight:str) -> list:
    """_Take a geodeepdive result and process its components._

    Args:
        conn (psycopg2.extensions.connection): _A valid psycopg2 connection to the OSPO database._
        doi (_string_): _A valid DOI_
        highlight (_list_): _An array of strings that represent text highlights from a GeoDeepDive PDF._

    Returns:
        list: _A list with all the  with elements `repository` and `status`._
    """
    outcome = []
    # Are repositories referenced in the highlights (we may have more than one highlight)?
    valid_repositories = [repotest(i) for i in highlight]
    for light in valid_repositories:
        if light['repo'] is not None:
            try:
                # We're going to run through all the steps. If any fails, we need to move on.
                newid = check_repository_db(conn, light['repo'])
                pub_id = add_publication_db(conn, doi, 'xDD Pipeline Submission')
                if newid is None:
                    # The repository is not already in the database:
                    newid = add_repo_db(conn, light['repo'], 'xDD Pipeline Submission')
                if pub_id is not None:
                    # The pub_id does an upsert and returns the proper ID whether or not the
                    # paper was already in the database.
                    link_publication_repository_db(conn, pub_id, newid, 'xDD API Scraper')
                    print('Linked this publication and repository.')
            except:    
                print(f"Failed to add content of {doi} to the database: Insertion or update error.")
                outcome.append({'doi': doi, 'highlight': light['highlight'], 'status': 'Invalid publication.'})
    return outcome

def repotest(string:str) -> object:
    """_Check if there is a valid repository link within a text string._
    
    Currently this only returns a single repository per string. Ideally we'd return
    an object for each repository found within a particular string.

    Args:
        string (str): _A text string or snippet that may or may not contain a valid code repository._

    Returns:
        object: _A Python object with keys `repo` and `highlight`. The `repo` is the extracted repository string._
    """    
    output = {'repo': None, 'highlight': string}
    if type(string) is str:
        test = re.search(r'((github)|(gitlab)|(bitbucket)).com\/((\s{0,1})[\w,\-,\_]+\/*){1,2}', string)
        if test is None:
            output = {'repo': None, 'highlight': string}
        else:
            test_no_space = re.sub(r'\s', '', test[0])
            test_no_punct = re.sub(r'[^\w\s]$', '', test_no_space)
            output = {'repo': test_no_punct, 'highlight': string}
    return output
