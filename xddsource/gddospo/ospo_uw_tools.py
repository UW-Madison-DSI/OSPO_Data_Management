import psycopg2
import re
from pyalex import Works
import pyalex
import itertools
import requests
import os
from github import Github
from github import Auth
from github.GithubException import UnknownObjectException
from psycopg2.extras import execute_values
from .ospo_db_tools import check_owner, insert_repository_db

def uw_validate_authors(openalex_record, lineage = "https://openalex.org/I135310074"):
    """_Check if an author is from the UW system._

    Args:
        openalex_record (_obj_): _This is an object passed from the _
        lineage (str, optional): _description_. Defaults to "https://openalex.org/I135310074".

    Returns:
        _type_: _description_
    """
    authors = openalex_record.get('authorships')
    if len(authors) > 0:
        institutions = [i.get('lineage') for i in authors[0].get('institutions')]
        combined = set(itertools.chain.from_iterable(institutions))
        if lineage in combined:
            return True
        else:
            return False
    else:
        return False

def uw_publication_check(conn, doi, add_valid = True, add_invalid = True):
    """_Check to see if the Publication has a link to the University of Wisconsin_
    Args:
        conn (_type_): _A valid database connection._
        doi (_type_): _A valid DOI_
        add_valid (bool, optional): _Should a valid link to a University of Wisconsin author be added to the database?_. Defaults to True.
        add_invalid (bool, optional): _Should we record a lack of a valid link to the database? May be useful if more than one method of validation is used_. Defaults to True.
    Returns:
        _None_: _This function returns nothing._
    """
    pyalex.config.email = "goring@wisc.edu"
    add_uwpub = """
        INSERT INTO uwpublications(publicationid, uwrelationid, sourceid, valid)
        VALUES
        (%s,
        (SELECT uwrelationid FROM uwrelations WHERE uwrelation = 'UW Person'),
        (SELECT sourceid FROM ospoimportsources WHERE sourcename = 'OpenAlex Search'),
        %s);"""
    pub_search = """
        SELECT publicationid FROM publications
        WHERE doi = %s;"""
    with conn.cursor() as cur:
        cur.execute(pub_search, (doi,))
        pubid = cur.fetchone()
        try:
            openalex_record = Works()['https://doi.org/' + doi]
        except requests.exceptions.HTTPError as e:
            print(f"Could not get source record for {doi}. Skipping: {e}")
            return None
        if uw_validate_authors(openalex_record):
            print(f"Link to the University of Wisconsin for {doi} based on OpenAlex records.")
            if add_valid:
                cur.execute(add_uwpub, (pubid[0], True))    
                conn.commit()
        elif not uw_validate_authors(openalex_record):
            print(f"Non-link to the University of Wisconsin for {doi} based on OpenAlex records.")
            if add_invalid:
                cur.execute(add_uwpub, (pubid[0], False))
                conn.commit()     
    return None

def check_all_pubs(conn, source = 'OpenAlex Search'):
    """_Uses a defined source (currently only OpenAlex) to check if authors are from UW._

    Args:
        conn (_connection_): _A valid psycopg2 connection object._
        source (str, optional): _description_. Defaults to 'OpenAlex Search'.

    Returns:
        _None_: _The function updates the database but does not return a result._
    """
    valid_source = """
        SELECT sourceid
        FROM ospoimportsources
        WHERE sourcename = %s;"""
    unchecked_query = """
        SELECT doi
        FROM publications AS pub
        WHERE 
        NOT pub.publicationid = ANY(
            (SELECT publicationid FROM uwpublications WHERE sourceid = %s));"""
    with conn.cursor() as cur:
        cur.execute(valid_source, (source,))
        sourceid = cur.fetchone()
        if sourceid is None:
            print('Not a valid source.')
            return None
        cur.execute(unchecked_query, sourceid)
        dois = cur.fetchall()
    for i in dois:
        uw_publication_check(conn, i[0], add_valid = True, add_invalid = True)

def uw_validate_owners(conn, owner, relation = 'UW Person', add_repos = True, auth = None):
    """_Assign a repository owner to a UW affiliation._

    Args:
        conn (_type_): _description_
        owner (_type_): _description_
        validation (str, optional): _description_. Defaults to 'UW Person'.
        add_repos (bool, optional): _description_. Defaults to True.
        auth (_type_, optional): _description_. Defaults to None.

    Returns:
        _type_: _description_
    """
    with conn.cursor() as cur:
        cur.execute("SELECT uwrelationid FROM uwrelations WHERE uwrelation = %s",
                               (relation,))
        uwrelationid = cur.fetchone()
    if uwrelationid is None:
        return False
    owner_id = check_owner(conn, owner)
    if owner_id is None:
        return False
    if auth is None:
        auth = os.getenv('GITHUB_TOKEN')
        if auth is None:
            return False
    G_AUTH = Auth.Token(auth)
    gi = Github(auth=G_AUTH)
    if check_owner(conn, owner) is None:
        return False
    uw_user = gi.get_user(owner)
    if add_repos:
        uw_repos = uw_user.get_repos()
        for i in uw_repos:
            insert_repository_db(conn, i.html_url, crawl = False)
    get_users_repos = """
        SELECT repositoryid
        FROM repositories AS rp
        INNER JOIN repositoryowners AS ro ON rp.ownerid = ro.ownerid
        WHERE ownername = %s"""
    with conn.cursor() as cur:
        cur.execute(get_users_repos, (owner,))
        owner_repos = cur.fetchall()
    add_account = [[i[0], uwrelationid[0]] for i in owner_repos]
    insert_query = """INSERT INTO uwrepositories (repositoryid, uwrelationid) VALUES %s
                      ON CONFLICT DO NOTHING;"""
    with conn.cursor() as cur:
        execute_values(cur, insert_query, add_account)
    conn.commit()
