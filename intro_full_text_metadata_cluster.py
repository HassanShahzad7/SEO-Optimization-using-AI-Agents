import configparser
import os
import pymysql
import pandas as pd
import json
import argparse
import spacy
from sklearn.cluster import KMeans
from collections import Counter
import numpy as np
from typing import Dict, Any, Optional, List
from logging import Logger
from openai import OpenAI, AsyncOpenAI
import asyncio
from pandas import DataFrame
import pymysql.cursors
from warnings import simplefilter
from sklearn.exceptions import ConvergenceWarning
from prompt import get_model , get_prompt
from helperfunctions import getlogger, percentage, aggregate_into_few, process_text, clean_text, write_into_the_json_file, current_state, do_update, updatetags, getFieldRecord
from nltk.tokenize import word_tokenize
import nltk
from log_handler import log_error as log_if_error, log_info
simplefilter("ignore", category=ConvergenceWarning)
nltk.download('punkt')

# Load spaCy model
nlp = spacy.load('en_core_web_md')

client = OpenAI(api_key=os.getenv("OPENAI_SECRET_KEY"))

global_normalized_tags_list = []


config = configparser.ConfigParser(interpolation=None)
config.read(os.path.join(os.path.dirname(__file__), "config.ini"))
db_prefix=config.get("mysql","prefix"),
db_prefix = db_prefix[0]
# max_run_count =0    # globelvariable for max record run 


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

def get_limit_rows(connection:pymysql.Connection,limit:int,offset:int,current_id:int,id:int, gte_date:str, id_desc:bool, counter:str): 
    # global max_run_count
    """ To get the records sequentially based  to limit """
  # Base SQL query
    if id:
        base_sql = f"SELECT c.id, c.introtext, c.fulltext, c.alias, c.images, c.title, c.catid FROM `{db_prefix}content` AS c"
    elif current_id != 0:
        offset=0
        base_sql = f"""
            SELECT c.id, c.introtext, c.fulltext, c.alias, c.images, c.title, c.catid as total FROM `{db_prefix}content` AS c
            LEFT JOIN `{db_prefix}categories` AS cat ON c.catid = cat.id
            WHERE c.`access` = 1
            AND cat.published = 1
            AND c.catid NOT IN (87, 89, 91, 98, 99, 100, 172, 197, 198, 199, 200, 202, 203, 217, 219)
            AND c.id >= {current_id}
        """
    else:
        base_sql = f"""
        SELECT c.id, c.introtext, c.fulltext, c.alias, c.images, c.title, c.catid as total FROM `{db_prefix}content` AS c
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

async def process_text_async(client, context, logger):
    """This function execute whwn contexts length is more than one """
    try:
        response = await client.chat.completions.create(
            model=get_model(),
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": f"Consise the context for further analysis to find the informative insights from the context: {context}"}
            ]
        )
        return response.choices[0].message.content.strip(), response.usage.completion_tokens
    except Exception as e:
        log_info(f"Async Process Text ERROR: {e}", log_type="error")
        return None, None


def process_context(contexts:list,logger:Logger, h1_title:str, metadesc:str, title:str, temperature=0):
    """ check the length if the contexts make a api call """
    metadata=[]
    n_tokens=[]

    if len(contexts) ==1:
        try:
            response = client.chat.completions.create(
                        model="gpt-3.5-turbo-0125",
                        # model = get_model(),    
                        temperature=0.1, 
                        response_format={ "type": "json_object" },
                        messages=get_prompt(contexts[0], h1_title=h1_title, metadesc=metadesc, title=title),
                        n=1,
                        stop=None,
                        max_tokens=1500,
                        
            )
            metadata.append(response.choices[0].message.content.strip())
            n_tokens.append(response.usage.completion_tokens)
        except Exception as e:
            log_info(f"Process Context ERROR : {e}", log_type="error")
    else:
        async def process_texts_async(contexts, logger):
            async with AsyncOpenAI(api_key=os.getenv('OPENAI_SECRET_KEY')) as client:
                tasks = [process_text_async(client, context, logger) for context in contexts]
                return await asyncio.gather(*tasks)

        results = asyncio.run(process_texts_async(contexts, logger))
        for meta, tokens in results:
            metadata.append(meta)
            n_tokens.append(tokens)
  
    return pd.DataFrame(data={'text':metadata,'n_tokens':n_tokens})


def process_df(df:DataFrame,logger:Logger, h1_title:str, metadesc:str, title:str):
    """ Aggredate the data into list elements"""
    contexts = aggregate_into_few(df=df,logger=logger)
    new_df = process_context(contexts=contexts,logger=logger, h1_title=h1_title, metadesc=metadesc, title=title)
    if len(new_df) > 1:
        return process_df(new_df,logger, h1_title=h1_title, metadesc=metadesc, title=title)
    return new_df




def extract_record_text(record:Dict[str,Any],logger:Logger,max_words:int,max_tokens:int, fieldRecord:Dict[str, Any]):
    """ process single  record  and extract the id introtext and fulltext .."""
    try:
        id=record.get('id')
        h1_title = record.get('title')
        metadesc = record.get('metadesc') 
        title = fieldRecord.get('value', '') if fieldRecord else ""
        introtext=record.get("introtext")
        fulltext=record.get("fulltext")
        if len(fulltext)>0:
            text=clean_text(fulltext=fulltext,logger=logger, max_words=max_words)
            df=process_text(text=text,logger=logger,max_tokens=max_tokens)
            df=process_df(df=df,logger=logger, h1_title=h1_title, metadesc=metadesc, title=title)
            log_info(f" Successfully processed  the record ID:{id}")
            return  str(df["text"][0]) 
        else:
            log_info(f"Record ID: {id} fulltext field has  empty string.")
            return None
    except Exception as e:
        log_info(f"Extract_record_text ERROR : {e}", log_type="error")

def tokenize_text(text):
    """
    Tokenizes the input text into individual words.

    Parameters:
    - text (str): Input text to tokenize.

    Returns:
    - List[str]: List of tokens (words).
    """
    tokens = word_tokenize(text)
    return tokens
      
def vectorize_tags(tags):
    vectors = []
    valid_tags = []
    for tag in tags:
        doc = nlp(tag)
        if doc.vector_norm > 0:
            vectors.append(doc.vector)
            valid_tags.append(tag)
    return np.array(vectors), valid_tags

def cluster_tags(vectors, num_clusters=5):
    n_samples, vector_dim = vectors.shape
    if n_samples < num_clusters:
        print(f"n_clusters {n_samples} changed with {n_samples}")
        num_clusters = n_samples
        # print(f"n_samples :{n_samples}")
    kmeans = KMeans(n_clusters=num_clusters, random_state=42)
    kmeans.fit(vectors)
    labels = kmeans.labels_
    return labels

def assign_broader_tags(tags, labels):
    cluster_to_tags = {}
    for tag, label in zip(tags, labels):
        if label not in cluster_to_tags:
            cluster_to_tags[label] = []
        cluster_to_tags[label].append(tag)
    
    broader_tags = {}
    for label, cluster_tags in cluster_to_tags.items():
        # Choose the most common tag as the representative tag
        # Alternatively, you can choose a more sophisticated method
        representative_tag = max(set(cluster_tags), key=cluster_tags.count)
        for tag in cluster_tags:
            broader_tags[tag] = representative_tag

    return broader_tags

def normalize_tags(tags, broader_tags):
    return [broader_tags.get(tag, tag) for tag in tags]



def generate_generic_tags(tags_list: List[str], min_count: int = 5, max_tags: int = 10) -> List[str]:
    # Tokenize tags and count occurrences
    tokens = []
    for tag in tags_list:
        tokens.extend(tag.lower().split())
    token_counts = Counter(tokens)
    
    # Filter tokens based on min_count and relevance criteria
    generic_tags = [token for token, count in token_counts.items() if count >= min_count]
    
    # Return up to max_tags generic tags
    return generic_tags[:max_tags]


def process_records(result: list, logger: Logger, total: int, counter: int, max_words: int, max_tokens: int, json_file: str, store_state_file: str, connection: pymysql.Connection, commit: bool = False, base_url: str = None):
    global global_normalized_tags_list  # Use the global normalized tags list
    for record in result:
        counter += 1
        try:
            log_info(f'{"*"*20} Processing ID: {record.get("id")} {"*"*20} ({counter}/{total} - {percentage(counter, total)})')
            log_info(f'ALIAS of Article: {record.get("alias")}')
            fieldRecord = getFieldRecord(connection, 29, record.get('id'))
            metadata = extract_record_text(record=record, logger=logger, max_words=max_words, max_tokens=max_tokens, fieldRecord=fieldRecord)
            
            if metadata is not None:
                dict_response = json.loads(metadata)
                log_if_error(dict_response, record, connection)

                # Extract tags from metadata
                tags = dict_response.get("Tags", [])
                filtered_tags = list(set(filter(lambda x: "_" not in x and "-" not in x, tags)))

                # Vectorize tags for the current record
                current_vectors, current_valid_tags = vectorize_tags(filtered_tags)

                # Update the global normalized tags list
                global_normalized_tags_list.extend(current_valid_tags)

                # Generate generic tags based on accumulated tags
                generic_tags = generate_generic_tags(global_normalized_tags_list)

                # Filter generic tags to keep only relevant ones
                relevant_generic_tags = set(generic_tags).intersection(set(current_valid_tags))

                # Ensure uniqueness and limit to a reasonable number
                # combined_tags = set(tags) | relevant_generic_tags

                # Cluster tags
                global_vectors, global_valid_tags = vectorize_tags(global_normalized_tags_list)
                num_clusters = min(10, len(global_valid_tags))
                if num_clusters < 1:
                    log_info(f'Not enough tags to form clusters for ID: {record.get("id")}', log_type="warn")
                    continue

                # labels = cluster_tags(global_vectors, num_clusters=num_clusters)
                # Cluster tags
                labels = cluster_tags(global_vectors, num_clusters=num_clusters)

                # Assign broader tags
                broader_tags_mapping = assign_broader_tags(global_valid_tags, labels)

                # broader_tags_mapping = {}  # Placeholder, replace with actual function if needed

                # Normalize tags for the current record
                normalized_tags = normalize_tags(tags, broader_tags_mapping)
                normalized_tags = set(normalized_tags)

                # Update metadata with normalized tags
                dict_response["Tags"] = filtered_tags

                # Log and save the updated metadata
                response = {"id": record.get('id'), "metadata": dict_response}
                log_info(f"Content id : {record['id']}, Tags : {dict_response['Tags']}")
                write_into_the_json_file(response=response, json_file=json_file)
                # Optionally update database with new tags
                if commit:
                    succeed = do_update(connection=connection, record=record, dict_response=dict_response, base_url=base_url, logger=logger)
                    if succeed:
                        pass  # Successful update
                current_id = record.get("id")
                current_state(store_state_file, id=current_id, counter=counter, mode="w")
        except KeyboardInterrupt as e:
            log_info(f"State saved till Record ID: {record.get('id')}", log_type="warn")
            raise e
        except Exception as e:
            log_info(f"Process records ERROR: {e}, Record ID: {record.get('id')}", log_type="error")

    return counter

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
    while True:
        try:
            result=get_limit_rows(connection=connection, limit=limit,offset=offset,current_id=current_id,id=id,gte_date=gte_date, id_desc=id_desc, counter=counter)
            total_records = len(result)
            if  not result:
                log_info(f'All records have been processed')
                break
            if len(result)==0:
                log_info(f'{"="*20} All records have been processed {"="*20}')
                break
            counter=process_records(result=result,logger=logger,total=total_records,counter=counter,max_words=max_words, max_tokens=max_tokens,json_file=json_file,store_state_file=store_state_file,commit=commit,connection=connection,base_url=base_url)
            current_id=result[-1]['id']
            log_info(f'{"="*20} All records have been processed {"="*20}')
            break
            # if id > 0:
            #     logger.info(f'{"="*20} All records have been processed {"="*20}')
            #     break
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


