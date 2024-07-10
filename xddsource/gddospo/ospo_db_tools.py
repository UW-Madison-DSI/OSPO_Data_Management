import re
import requests
import json
import datetime
from crossref.restful import Works
from psycopg2 import sql
import os
from github import Github
from github import Auth
from github.GithubException import UnknownObjectException


def clean_repo_name(repo_name):
    """_Clean a repository URL so that it conforms to expected format._

    Args:
        repo_name (_str_): _The passed name of a code repository._

    Returns:
        _str_: _A cleaned repository URL, with an https prefix._
    """
    repo_check = None
    if repo_name is None:
        return None
    elif re.search('^http[s]://.*', repo_name):
        repo_check = re.sub('/$', '', repo_name)
    else:
        repo_check = 'https://' + re.sub('/$', '', repo_name)
    return repo_check

def check_repository_url(repo):
    """_Validate the repository path using a HEAD call._

    Args:
        repo (_str_): _A cleaned repository URL_

    Returns:
        _bool_: _Returns True if the HEAD call returns 200._
    """
    if repo is None:
        return False
    check_repo = clean_repo_name(repo)
    try:
        check = requests.head(check_repo)
        if check.status_code == 200:
            return True
    except Exception as e:
        print(f'Failed to resolve: {e}')
    return False

def check_repository_db(conn, repo):
    """_Is the repository in the OSPO Database?_

    Args:
        conn (_type_): _A valid database connection._
        repo (_type_): _A valid repository URL._

    Returns:
        _int_: _A valid repositoryid (from the OSPO database), or None._
    """
    cur = conn.cursor()
    check = """SELECT repositoryid
               FROM repositories
               WHERE url = %s"""
    cur.execute(check, (repo,))
    # There is a constraint on unique URLs
    repos = cur.fetchone()
    cur.close()
    return repos

def check_last_crawl(conn, repository):
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

def check_owner(conn, owner):
    owner_db = """
    SELECT ownerid FROM repositoryowners WHERE ownername = %s"""
    with conn.cursor() as cur:
        cur.execute(owner_db, (owner,))
        ownerid = cur.fetchone()
    return ownerid

def check_repository_owner(conn, repository):
    owner_query = """
    SELECT rp.ownerid FROM repositories AS rp
    INNER JOIN repositoryowners AS rpo ON rpo.ownerid = rp.ownerid
    WHERE url = %s;"""
    with conn.cursor() as cur:
        cur.execute(owner_query, (repository,))
        ownerid = cur.fetchone()
    return ownerid

def update_repo_add_owner(conn, repository, auth = None, update = True, manager = "GitHub"):
    if re.search(r'github\.com', repository) is None:
        # Currently only supports GitHub
        return False
    else:
        repository_id = check_repository_db(conn, repository)
        owner_id = check_repository_owner(conn, repository)
        if repository_id is None:
            return False
        if owner_id is not False and update is False:
            return False
    if auth is None:
        auth = os.getenv('GITHUB_TOKEN')
        if auth is None:
            return False
    G_AUTH = Auth.Token(auth)
    gi = Github(auth=G_AUTH)
    repo_string = re.findall(r'(github\.com\/)(.+?)$', repository)[0][1]
    repo_string = re.sub('/$', '', repo_string)
    if re.search('.+/.+$', repo_string):
        repo_object = gi.get_repo(repo_string)
        owner = repo_object.owner
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

def update_repo_crawl_db(conn, repository, auth = None, delay = 2):
    """_summary_

    Args:
        conn (_type_): _A valid psycopg2 connection._
        repository (_str_): _A valid URL string for a repository_
        auth (_str_, optional): _A valid GitHub (currently) authorization token._. Defaults to None.
        delay (int, optional): _description_. Defaults to 2.

    Returns:
        _type_: _description_
    """    
    current_date = datetime.datetime.now()
    if re.search('github\.com\/.+$', repository) is None:
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
                raise ValueError("Last crawl date is within less than {delay} days of the current crawl.")
        if auth is None:
            auth = os.getenv('GITHUB_TOKEN')
            if auth is None:
                raise TypeError("The authentication token must be supplied explicitly or set as the environment variable GITHUB_TOKEN.")
        G_AUTH = Auth.Token(auth)
        gi = Github(auth=G_AUTH)
    repo_string = re.findall(r'(github\.com\/)(.+?)$', repository)[0][1]
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
                   'readme': readme,
                   'stargazers': repo_object.stargazers_count,
                   'issues': repo_object.get_issues().totalCount,
                   'openissues': repo_object.open_issues_count,
                   'forks': repo_object.forks_count,
                   'watchers': repo_object.watchers}
    insert_query = """
        INSERT INTO repositorycrawls (repositoryid, crawl_at,
                                      name, description, homepage,
                                      last_pushed, license_name,
                                      readme, stargazers, issues,
                                      openissues, forks, watchers)
        VALUES
        (%(repositoryid)s, %(crawl_at)s, %(name)s, %(description)s, %(homepage)s,
         %(last_pushed)s, %(license_name)s, %(readme)s,
         %(stargazers)s, %(issues)s, %(openissues)s, %(forks)s, %(watchers)s)"""
    with conn.cursor() as cur:
        cur.execute(insert_query, repo_values)
    conn.commit()
    return True

def insert_repository_db(conn, repo, verbose = True, crawl = True):
    """_Add a new repository to the OSPO Database_

    Args:
        conn (_connection_): _A psycopg2 connection object._
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

def get_datetime(dt_list):
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

def add_repository_source(conn, repositoryid, source):
    cur = conn.cursor()
    insert_source = """INSERT INTO repositorysources(repositoryid, sourceid)
                VALUES (%s, (SELECT sourceid FROM ospoimportsources WHERE sourcename = %s))
                ON CONFLICT DO NOTHING;"""
    if isinstance(repositoryid, tuple):
        repositoryid = repositoryid[0]
    cur.execute(insert_source, (repositoryid, source))
    conn.commit()
    cur.close()

def add_repo_db(conn, repo, source, verbose = True):
    """_Add a repository to the OSPO database_

    Args:
        conn (_type_): _A psycopg2 connection object, to the OSPO database._
        repo (_str_): _A string representing the repository location._
        source (_str_): _A valid source type from which the repository was obtained._

    Returns:
        _int_: _The repositoryid for the new repository._
    """
    repo_check = clean_repo_name(repo)
    if repo_check is None:
        if verbose:
            print(f'Repository {repo_check} (from {repo}) does not have a valid name.')
        return None
    if not check_repository_url(repo_check):
        if verbose:
            print(f'Repository {repo_check} (from {repo}) does not appear to exist.')
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
    return repositoryid

def update_repo_name_db(conn, repository, drop = True):
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

def check_publication_db(conn, doi):
    cur = conn.cursor()
    check = """SELECT publicationid
               FROM publications
               WHERE doi = %s"""
    cur.execute(check, (doi,))
    # There is a constraint on unique URLs
    pubs = cur.fetchone()
    cur.close()
    return pubs

def insert_publication_db(conn, doi):
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

def add_publication_source(conn, publicationid, source):
    cur = conn.cursor()
    insert_source = """INSERT INTO publicationimport(publicationid, sourceid)
                VALUES (%s, (SELECT sourceid FROM ospoimportsources WHERE sourcename = %s))
                ON CONFLICT DO NOTHING;"""
    if isinstance(publicationid, tuple):
        publicationid = publicationid[0]
    cur.execute(insert_source, (publicationid, source))
    conn.commit()
    cur.close()

def add_publication_db(conn, doi, source):
    """_Add a new publication to the database and fetch relevant metadata._

    Args:
        conn (_type_): _A psycopg2 connection object._
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

def add_crossref_meta(conn, doi):
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

def link_publication_repository_db(conn, publicationid, repositoryid, source):
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

def get_repository_urls(conn):
    repo_query = """
    SELECT url FROM repositories;"""
    with conn.cursor() as cur:
        cur.execute(repo_query)
        results = cur.fetchall()
    return list(results)