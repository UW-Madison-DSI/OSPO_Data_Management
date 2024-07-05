# OSPO Open Data Scraper and Database

This project will work with the goals of the OSPO Project Office to support tracking and metadata enrichment of Open Software contributions using a PostgreSQL database and various tools to scrape and augment data associated with project repositories.

## Contributors

* Abe Megahed
* Jason Lo
* Allison Kittinger
* Simon Goring

## Project Goals

The project repository will represent a stand-alone tool to obtain data from various open code repositories, user contributions and organized submissions and store them in a central database. The tool will provide the ability to cross-link repositories to journal publications, individuals, grants and other data resources to allow researchers and administrators to assess the impact of open source contributions.

In addition, the database will be constructed in such a way that it will provide additional support to researchers themselves, by identifying opportunities for improvement though simple Open Source checklists, that will allow researchers to ensure a high level of quality in their open source contributions.

## Repository Structure

This repository contains code to initialize a PostgreSQL database [ospo_database.sql](ospo_database.sql)] and to populate it using data obtained by scraping various public code repository services. Raw data is contained within the [`source_data`](./source_data/) folder, however, some raw data, obtained through internal University of Wisconsin-Madison surveys has been excluded.

The `.env` file here is absent, but it should include the following two variables:

* `OSDB_CONNECT`: Representing a valid JSON connection string, with the following format:
  * `{"host": "YOURHOST","port": YOURPORT,"database": "DATABASENAME","user": "DATABASEUSER","password": "DATABASEPASSWORD"}`
* `GITHUB_TOKEN`: A valid github [Personal Access Token](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/managing-your-personal-access-tokens). Should have the general structure `github_pat_. . .`. 

```bash
└── .gitignore
└── .env
└── ospo_database.sql
└── README.md
└── requirements.txt
└── 📁xddsource
    └── crawl_repositories.py
    └── githubdeepdive_scrape.py
    └── dbsetup.py
    └── 📁gddospo
        └── __init__.py
        └── 📁__pycache__
            └── __init__.cpython-311.pyc
            └── gdd_tools.cpython-311.pyc
            └── ospo_db_tools.cpython-311.pyc
        └── gdd_tools.py
        └── ospo_db_tools.py
        └── ospo_uw_tools.py
    └── pyvenv.cfg
└── 📁source_data
    └── ospo_survey.csv
    └── repo.parquet
```

### The `gddospo` library

The main python code for this project is structured as a Python library, with tools for interacting with the database itself ([`ospo_db_tools.py`](./xddsource/gddospo/ospo_db_tools.py)), tools for assigning University of Wisconsin associations to repositories and publications once they've been ingested ([`ospo_uw_tools.py`](./xddsource/gddospo/ospo_uw_tools.py)), and tools for automated full-text scraping of research objects from the xDD API service ([`gdd_tools.py`](./xddsource/gddospo/gdd_tools.py)).

#### `ospo_db_tools`

This module includes functions to connect to the database and validate records (the `check_*()` functions), to insert new data (the `insert_*()` functions) to update records (the `update*()` functions) and to link records (the `link_*()` functions). Along with these, there are several helper functions that are used to clean dates, CrossRef records and repository URLs.

#### `ospo_uw_tools`

These functions are largely used to validate the assignation of "UW-Belonging" to publications and code repositories. Within the database structure we have several ways a research object can "belong" to the University. They are defined specifically in the `uwrelations` table. The `ospo_database.sql` file pre-populated this table with the following values:

* `OSPO Survey`: Assignment comes from a submission from the OSPO survey (the file `ospo_survey.csv` is ignored in the public database version)
* `UW Mention`: The University of Wisconsin is specifically mentioned in the repository, or paper.
* `UW Organization`: The repository organization is owned by a UW Entity.
* `UW Person`: The person who owns the repository has an affiliation with the University of Wisconsin
* `Keyword Search`: The affiliation was assigned based on a keyword search that included University of Wisconsin related terms.

#### `gdd_tools`

Functions developed to interact with the xDD system, to check for papers in GeoDeepDive and to then extract links within those papers that reference GitHub repositories.


