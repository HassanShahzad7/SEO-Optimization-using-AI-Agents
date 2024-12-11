from typing import Dict, Any, Optional, List
import configparser
import os
from helperfunctions import getlogger
from logging import Logger
import argparse
from sqlalchemy import (
    create_engine, Table, MetaData, select, case, func, and_, alias, text, Index,
    Column, String, Integer
)
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import OperationalError
import time
import backoff

# Load configuration from the config.ini file
config = configparser.ConfigParser(interpolation=None)
config.read(os.path.join(os.path.dirname(__file__), "config.ini"))
db_prefix = config.get("mysql", "prefix")

# Function to create a database connection
@backoff.on_exception(backoff.expo, OperationalError, max_tries=5)
def get_db_connection(config, logger):
    """
    Establish a database connection with retry logic
    """
    try:
        engine = create_engine(
            f"mysql+pymysql://{config.get('mysql', 'user')}:{config.get('mysql', 'password')}@{config.get('mysql', 'host')}:{config.get('mysql', 'port')}/{config.get('mysql', 'database')}",
            pool_recycle=3600,  # Recycle connections after an hour
            pool_pre_ping=True  # Check connection validity before using
        )
        Session = sessionmaker(bind=engine)
        session = Session()
        return session, engine
    except Exception as e:
        logger.error(f"Get db connection ERROR: {e}")
        raise


def fetch_easyfrontendseo_table(table):
    """
    Fetch data from the easyfrontendseo table.
    """
    return select(table)


def fetch_content_table(table):
    """
    Prepare query for the content table.
    """
    return select(table)


def join_tables(session, easyfrontendseo_table, content_table):
    """
    Perform an optimized join between the two tables using SQLAlchemy's ORM capabilities,
    extracting the same information as the provided SQL query.
    """
    try:
        # Perform the join
        query = select(
            easyfrontendseo_table.c.id,
            content_table.c.alias,
            # content_table.c.alias_id,
            # easyfrontendseo_table.c.url,
            # easyfrontendseo_table.c.urlHash,
            content_table.c.title,
            func.concat(content_table.c.introtext, ' ', content_table.c.fulltext).label('entire_text')
        ).select_from(
            easyfrontendseo_table.join(
                content_table,
                easyfrontendseo_table.c.alias_id == content_table.c.alias_id
            )
        ).where(
            (content_table.c.deleted_at.is_(None)) &
            (easyfrontendseo_table.c.deleted_at.is_(None))
        ).limit(1).offset(3)

        # Execute the query with a chunk size to handle large datasets
        result = []
        for chunk in session.execute(query.execution_options(stream_results=True)).yield_per(1000):
            result.extend(chunk)

        return result

    except Exception as e:
        print(f"An error occurred during join: {e}")
        raise

    
def main(id: Optional[int] = 0, commit: bool = False):
    config = configparser.ConfigParser(interpolation=None)
    config.read(os.path.join(os.path.dirname(__file__), "config.ini"))
    log_file_name = config.get('metadata-01', "log_file")
    logger = getlogger(name=log_file_name)

    try:
        session, engine = get_db_connection(config, logger)
        print('connection made')

        # Reflect tables
        metadata = MetaData()
        easyfrontendseo_table = Table('xu5gc_easyfrontendseo', metadata, autoload_with=engine)
        content_table = Table('xu5gc_content', metadata, autoload_with=engine)
        print('did the metadata part')

        # Perform the join using SQLAlchemy
        joined_data = join_tables(session, easyfrontendseo_table, content_table)

        # Print or process the joined data
        print("Joined Data:")
        for row in joined_data:
            print(row)

    except OperationalError as e:
        logger.error(f"Database connection error: {e}")
        print(f"Database connection error: {e}")
    except Exception as e:
        logger.error(f"An error occurred: {e}")
        print(f"An error occurred: {e}")
    finally:
        if 'session' in locals():
            session.close()
    

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--id", default=0, type=int, help="Check for specific ID")
    parser.add_argument("--commit", action="store_true", help="Update the database")
    args = parser.parse_args()
    specific_id = args.id
    is_commit = args.commit
    main(id=specific_id, commit=is_commit)