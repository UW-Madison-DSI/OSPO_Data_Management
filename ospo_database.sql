CREATE DATABASE ospowisconsin;

CREATE DOMAIN url AS text
CHECK (VALUE ~ 'https?:\/\/(www\.)?[-a-zA-Z0-9@:%._\+~#=]{2,255}\.[a-z]{2,9}\y([-a-zA-Z0-9@:%_\+.,~#?!&>//=]*)$');
COMMENT ON DOMAIN url IS 'match URLs (http or https)';

CREATE DOMAIN doi AS TEXT
CHECK (VALUE ~* '^10.\d{4,9}/[-._;()/:A-Z0-9]+$');
COMMENT ON DOMAIN doi IS 'match DOIs (from shoulder)';

-- FIXED VOCABULARY TABLES
CREATE TABLE uwrelations (
    uwrelationid serial PRIMARY KEY,
    uwrelation text,
    uwrelationdescription text,
    CONSTRAINT singlerelationship UNIQUE (uwrelation)
);

INSERT INTO uwrelations(uwrelation, uwrelationdescription)
VALUES 
    ('OSPO Survey', 'A repository submitted by an individual through an OSPO survey'),
    ('UW Mention','The repository specifically mentions UWisc, or support from UW-Madison'),
    ('UW Organization','The repository is owned by an organization affiliated with UW Madison'),
    ('UW Person','The individual is affiliated with the University of Wisconsin.'),
    ('Keyword Search', 'A repository found through a search of repositories using specific search terms.');

CREATE TABLE ospoimportsources (
    sourceid serial PRIMARY KEY,
    sourcename text NOT NULL,
    sourcedescription text,
    CONSTRAINT singlesourcename UNIQUE(sourcename)
);

INSERT INTO ospoimportsources (sourcename, sourcedescription)
VALUES
('Direct Submission', 'The object was submitted by a user via an API or website'),
('Bulk Submission OSPO', 'The object was submitted directly by the OSPO office'),
('xDD Pipeline Submission', 'The object was added through a programmatic workflow using xDD'),
('OpenAlex Search', 'A search for records using the OpenAlex API.');

-- RESEARCH ENTITIES
CREATE TABLE publications(
    publicationid SERIAL PRIMARY KEY,
    doi doi,
    title text,
    subtitle text,
    author text,
    subject text,
    abstract text,
    containertitle text,
    language text,
    published text,
    publisher text,
    articleurl url,
    crossrefmeta jsonb,
    dateadded timestamp,
    CONSTRAINT singledoi UNIQUE(doi)
);

CREATE TABLE uwpublications(
    publicationid INT references publications(publicationid),
    uwrelationid INT references uwrelations(uwrelationid),
    sourceid INT references ospoimportsources(sourceid),
    CONSTRAINT oneuwlink UNIQUE(publicationid, uwrelationid, sourceid)
);

CREATE TABLE repositorymanager(
    managerid SERIAL PRIMARY KEY,
    managername text UNIQUE,
    managerdescription text,
    baseurl url,
    apiurl url
);

INSERT INTO repositorymanagers (managername, managerdescription, baseurl, apiurl)
VALUES
('GitHub', 'The primary GitHub hosting organization.', 'https://github.com', 'https://api.github.com'),
('GitLab -- UW', 'Wisconsin''s implementation of GitLab.', 'https://gitlab.uwmadison.com', 'https://gitlab.uwmadison.com/api'),
('BitBucket', 'The primary Atlassian code repository', 'https://bitbucket.org', 'https://api.bitbucket.org/2.0');

CREATE TABLE repositoryowners(
    ownerid SERIAL PRIMARY KEY,
    ownername text,
    isorganization boolean,
    managerid INT REFERENCES repositorymanager(managerid),
    CONSTRAINT onenamemanager UNIQUE(ownername, managerid)
);

CREATE TABLE repositories(
    repositoryid serial primary key,
    url url,
    created_at timestamp,
    ownerid int references repositoryowners(ownerid) ON DELETE CASCADE,
    CONSTRAINT uniqueurl UNIQUE(url)
);

CREATE TABLE people (
    personid SERIAL PRIMARY KEY,
    personname text,
    personidentifier text,
    CONSTRAINT uniqueperson UNIQUE (personname, personidentifier)
);

-- RELATIONSHIP TABLES
CREATE TABLE publicationlinks (
    publicationlinkid SERIAL PRIMARY KEY,
    publicationlinksource TEXT,
    publicationlinkdescription TEXT,
    CONSTRAINT singlelinktype UNIQUE(publicationlinksource));

INSERT INTO publicationlinks(publicationlinksource, publicationlinkdescription)
VALUES
('xDD API Scraper', 'A Python toolkit to extract GitHub and other online repository tools'),
('User Submitted', 'A user submitted link between code and publication.'),
('CrossRef Link', 'A reference to a GitHub repository extracted from CrossRef metadata.');


CREATE TABLE publicationrepolinks (
    publicationlinkid INT references publicationlinks(publicationlinkid),
    repositoryid INT references repositories(repositoryid),
    publicationid INT references publications(publicationid),
    CONSTRAINT uniquelink UNIQUE(publicationlinkid, repositoryid, publicationid)
);

CREATE TABLE publicationimport (
    publicationid INT REFERENCES publications(publicationid),
    sourceid INT REFERENCES ospoimportsources(sourceid),
    CONSTRAINT uniqueimport UNIQUE(publicationid, sourceid)
);

CREATE TABLE repositorypublications (
    publicationid INT REFERENCES publications(publicationid),
    repositoryid INT REFERENCES repositories(repositoryid),
    linksourceid INT REFERENCES publicationlinks(publicationlinkid),
    CONSTRAINT defineitonce UNIQUE(publicationid, repositoryid, linksourceid)
);

CREATE TABLE personauthor (
    personid INT REFERENCES people(personid),
    publicationid INT REFERENCES publications(publicationid),
    CONSTRAINT singlepaperperson UNIQUE(personid, publicationid)
);

CREATE TABLE personowner (
    personid INT REFERENCES people(personid),
    ownerid INT REFERENCES repositoryowners(ownerid),
    CONSTRAINT singleownerrperson UNIQUE(personid, ownerid)
);

CREATE TABLE repositorycrawls (
    crawlid serial PRIMARY KEY,
    repositoryid int REFERENCES repositories(repositoryid),
    crawl_at timestamp,
    name text,
    description text,
    homepage url,
    last_pushed timestamp,
    license_key text,
    license_name text,
    readme text,
    readmeimages boolean,
    stargazers int,
    issues int,
    openissues int,
    forks int,
    watchers int,
    CONSTRAINT crawlitonce UNIQUE(repositoryid, crawl_at));

CREATE TABLE repoqualitychecks (
    crawlid INT REFERENCES repositorycrawls(crawlid),
    repositoryid int REFERENCES repositories(repositoryid),
    hasreadme BOOLEAN,
    readmelength INT,
    codeofconduct BOOLEAN,
    topics BOOLEAN,
    releases INT,
    dois BOOLEAN,
    CONSTRAINT checkqualityonce UNIQUE(crawlid, repositoryid)
);

CREATE TABLE uwrepositories (
    repositoryid INT REFERENCES repositories(repositoryid),
    uwrelationid INT REFERENCES uwrelations(uwrelationid),
    CONSTRAINT unique_rel UNIQUE (repositoryid, uwrelationid)
);

CREATE TABLE repositorysources (
    repositoryid INT REFERENCES repositories(repositoryid),
    sourceid INT REFERENCES ospoimportsources(sourceid),
    CONSTRAINT unique_sourcerel UNIQUE (repositoryid, sourceid)
);
