import configparser
import os
import pymysql
import pandas as pd
import json
import argparse
from collections import Counter
import numpy as np
from typing import Dict, Any, Optional, List
from logging import Logger
import asyncio
import hashlib
from pandas import DataFrame
import pymysql.cursors
from warnings import simplefilter
from log_handler import log_error as log_if_error, log_info
from helperfunctions import getlogger, percentage, aggregate_into_few, process_text, clean_text, write_into_the_json_file, current_state, do_update, updatetags, getFieldRecord

global_normalized_tags_list = []


config = configparser.ConfigParser(interpolation=None)
config.read(os.path.join(os.path.dirname(__file__), "config.ini"))
db_prefix=config.get("mysql","prefix"),
db_prefix = db_prefix[0]

def get_db_connection(config,logger):
    """
    established a database connection
    """
    try:
        # Connect to the database
        connection= pymysql.connect(
            host=config.get("mysql", "host"),
            port=int(config.get("mysql", "port")),
            user=config.get("mysql", "user"),
            password=config.get("mysql", "password"),
            database=config.get("mysql", "database"),
            cursorclass=pymysql.cursors.DictCursor,
        )
        return connection
    except pymysql.MySQLError as e:
        log_info(f"Get db connection ERROR : {e}", log_type="error")
        raise e
    
def get_limit_rows(connection:pymysql.Connection,limit:int,offset:int,current_id:int,id:int, gte_date:str, id_desc:bool, counter:str):
    # global max_run_count
    """ To get the records sequentially based  to limit """
  # Base SQL query
    if id:
        base_sql = f"SELECT c.id, c.alias FROM `{db_prefix}content` AS c"
    elif current_id != 0:
        offset=0
        base_sql = f"""
            SELECT c.id, c.alias FROM `{db_prefix}content` AS c
            LEFT JOIN `{db_prefix}categories` AS cat ON c.catid = cat.id
            WHERE c.`access` = 1
            AND cat.published = 1
            AND c.catid NOT IN (87, 89, 91, 98, 99, 100, 172, 197, 198, 199, 200, 202, 203, 217, 219)
            AND c.id >= {current_id}
        """
    else:
        base_sql = f"""
        SELECT c.id, c.alias FROM `{db_prefix}content` AS c
        LEFT JOIN `{db_prefix}categories` AS cat ON c.catid = cat.id
        WHERE c.`access` = 1
        AND cat.published = 1
        AND c.catid NOT IN (87, 89, 91, 98, 99, 100, 172, 197, 198, 199, 200, 202, 203, 217, 219)
        """

    where_clauses = []
    args = []

    # Add conditions based on id and gte_date
    if id > 0:
        where_clauses.append("c.id = %s")
        args.append(id)

    if not id and gte_date:
        where_clauses.append("c.created > %s")
        args.append(gte_date)

    # Construct WHERE clause
    if where_clauses:
        where_clause = " AND ".join(where_clauses)
        if id:
            where_clause = " WHERE " + where_clause
        else:
            where_clause = " AND " + where_clause
    else:
        where_clause = ""

    # Construct ORDER BY clause
    # order_by_clause = " ORDER BY c.id DESC" if id_desc else ""

    # Construct LIMIT and OFFSET clause
    limit_offset_clause = ""
    if not id and limit != 0:
        limit_offset_clause += " LIMIT %s"
        args.append(limit)
    if not id and offset != 0:
        limit_offset_clause += " OFFSET %s"
        args.append(offset)

    # Combine the parts to form the final SQL query
    sql = base_sql + where_clause + limit_offset_clause
    with connection.cursor() as cursor:
        cursor.execute(sql, args)
        result = cursor.fetchall()
    return result

def get_total_rows(config,connection):
    """ To get the length the database records """
    runfortags = bool(int(config.get("metadata-01","runfortags")))

    # if runfortags:
    Sql = f'''SELECT COUNT(*)  as total FROM `{db_prefix}content` AS c
            LEFT JOIN `{db_prefix}categories` AS cat ON c.catid = cat.id
            WHERE c.`access` = 1
            AND cat.published = 1
            AND c.catid NOT IN (87, 89, 91, 98, 99, 100, 172, 197, 198, 199, 200, 202, 203, 217, 219);'''
    # else:
    #     Sql= f"SELECT count(id) as total FROM {db_prefix}content"
    with connection.cursor() as cursor:
        cursor.execute(Sql)
        result=cursor.fetchone()

        return result

def get_sha1_hash(data):
    """ dvw result = hashlib.sha224(data.encode()) """
    result = hashlib.sha1(data.encode())
    return result.hexdigest()

def main(id: Optional[int] = 0,commit: bool = False,):
    '''
    This is the main fucntion that extracts the required data from the config file
    '''
    config = configparser.ConfigParser(interpolation=None)
    config.read(os.path.join(os.path.dirname(__file__), "config.ini"))
    log_file_name=config.get('metadata-01',"log_file")
    store_state_file = config.get("metadata-01", "store_state_file")
    logger=getlogger(name=log_file_name)
    json_file=config.get('metadata-01',"json_file")
    limit:int=config.getint("metadata-01","limit", fallback=0)
    offset:int=config.getint("metadata-01","offset", fallback=0)
    id_desc:bool=bool(config.getint("metadata-01","id_desc"))
    gte_date:int=config.get("metadata-01","gte_date",fallback=None)
    current_id:int=config.getint("metadata-01","current_id")
    counter:int=config.getint("metadata-01","counter")
    max_words:int=config.getint("metadata-01","max_words")
    max_tokens:int=config.getint("metadata-01","max_tokens")
    base_url:str=config.get("metadata-01","base_url")

    connection=get_db_connection(config,logger)
    if id:
        total_records = 1
    else:
        total_records=get_total_rows(config,connection).get('total')
    # if limit < total_records:
    #     total_records = limit
    # max_records  = config.get("metadata-01","max_record_run")
    # max_records_runs = int(max_records) if max_records else total_records

    log_info(f'{"="*20} Total records : {total_records} {"="*20}')
    current_id, counter = current_state(store_state_file, mode="r")
    counter = 0

    try:
        result=get_limit_rows(connection=connection, limit=limit,offset=offset,current_id=current_id,id=id,gte_date=gte_date, id_desc=id_desc, counter=counter)
        # print(result)
        aliases = [i['alias'] for i in result]
        for alias in aliases:
            print(alias, get_sha1_hash(alias))
    except Exception as e:
        log_info(f"ERROR : {e}", log_type="error")
        current_id=result[-1]['id']

if __name__ =="__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--id", default=0, type=int, help="Check for specific ID")
    parser.add_argument("--commit", action="store_true", help="Update the database")
    args = parser.parse_args()
    specific_id = args.id
    is_commit=args.commit
    main(id=specific_id,commit=is_commit,)