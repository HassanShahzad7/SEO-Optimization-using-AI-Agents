import configparser
import os
from helperfunctions import getlogger, percentage,aggregate_into_few,process_text,clean_text,write_into_the_json_file,current_state
import pymysql
import pymysql.cursors
from logging import Logger
from typing import Dict, Any,Optional,List
from openai import OpenAI,AsyncOpenAI
import asyncio
import pandas as pd
from pandas import DataFrame
import json
import argparse
from concurrent.futures import ThreadPoolExecutor,as_completed
import threading

client = OpenAI(api_key=os.getenv("OPENAI_SECRET_KEY"))



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
        logger.error(f"Get db connection ERROR : {e}")
        raise e
    
def get_total_rows(connection):
    """ To get the length the database records """
    Sql="SELECT count(id) as total FROM aa_xu5gc_content"
    with connection.cursor() as cursor:
        cursor.execute(Sql)
        result=cursor.fetchone()
        return result

def get_limit_rows(connection:pymysql.Connection,limit:int,current_id:int,id:int):
    """ To get the records sequentially based  to limit """
    if id > 0:
        sql = "SELECT c.id, c.introtext, c.fulltext FROM aa_xu5gc_content AS c WHERE id =%s"
        args = id
    elif current_id>0:
        sql="SELECT c.id , c.introtext , c.fulltext FROM aa_xu5gc_content AS c  WHERE id > %s ORDER BY id LIMIT %s" 
        args=(current_id,limit)
    else:
        sql="SELECT c.id , c.introtext , c.fulltext FROM aa_xu5gc_content AS c ORDER BY id LIMIT %s" 
        args=limit
    with connection.cursor() as cursor:
        cursor.execute(sql,args)
        result=cursor.fetchall()
    return result

async def process_text_async(client, context, logger):
    try:
        response = await client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": f"Generate meta keywords and description for: {context}"}
            ]
        )
        return response.choices[0].message.content.strip(), response.usage.completion_tokens
    except Exception as e:
        logger.error(f"Async Process Text ERROR: {e}")
        return None, None


def process_context(contexts:list,logger:Logger):
    metadata=[]
    n_tokens=[]
    if len(contexts) ==1:
        try:
            response = client.chat.completions.create(
            model="gpt-3.5-turbo",  # Specify the GPT-3.5-turbo model
            messages=[{"role": "system", "content": "You are a helpful assistant skilled in SEO."},
                    {"role": "user", "content": f"""
                     Analyze the following text and generate set of relevant meta keywords and a concise meta description suitable for SEO:

                    First, write the meta keywords , then separate meta description with a newline.\n\n"
                    Text: \"{contexts[0]}\"\n\n"
                    Meta Keywords:\n"
                    Meta Description:\n\n"
                    
                    The meta keywords and meta description should be relevant of the given text for web search optimization."""}]
            )
            metadata.append(response.choices[0].message.content.strip())
            n_tokens.append(response.usage.completion_tokens)
        except Exception as e:
            logger.error(f"Process Context ERROR : {e}")
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


def process_df(df:DataFrame,logger:Logger):
    """ Aggredate the data into list elements"""
    contexts = aggregate_into_few(df=df,logger=logger)
    new_df = process_context(contexts=contexts,logger=logger)
    if len(new_df) > 1:
        return process_df(new_df,logger)
    return new_df




def extract_record_text(record:Dict[str,Any],logger:Logger,max_words:int,max_tokens:int):
    """ process single  record  and extract the id introtext and fulltext .."""
    try:
        id=record.get('id')
        introtext=record.get("introtext")
        fulltext=record.get("fulltext")
        if len(fulltext)>0:
            text=clean_text(fulltext=fulltext,logger=logger, max_words=max_words)
            df=process_text(text=text,logger=logger,max_tokens=max_tokens)
            df=process_df(df=df,logger=logger)
            logger.info(f" Successfully processed  the record ID:{id}")
            return  str(df["text"][0]) 
        else:
            logger.info(f"Record ID: {id} fulltext field has  empty string.")
            return None
    except Exception as e:
        logger.error(f"Extract_record_text ERROR : {e}")




def process_records(result:list,logger:Logger, total:int,counter:int,max_words:int, max_tokens:int,json_file:str,store_state_file:str):
    """Process the extracting records """
    for record in result:
        counter+=1
        try:
            logger.info(f'{"*"*20} Processing ID: {record.get("id")} {"*"*20} ({counter}/{total} - {percentage(counter, total)})')
            metadata=extract_record_text(record=record,logger=logger,max_words=max_words,max_tokens=max_tokens)
            if metadata is not None:
                metadata = metadata.replace('\\n\\n', '\n\n')
                dict_response = {item.split(':', 1)[0]: item.split(':', 1)[1] for item in metadata.split("\n\n") if ':' in item}
                response={"id":record.get('id'),"metadata":dict_response}
                write_into_the_json_file(response=response,json_file=json_file)
        except KeyboardInterrupt as e:
            current_id = record.get("id")
            current_state(store_state_file, id=current_id, counter=counter, mode="w")
            logger.info(f"State save till Record ID: {record.get('id')}")
            raise e
        except Exception as e:
            logger.error(f"Process records ERROR : {e} Record_id: {record.get('id')}")
    return counter
      


def process_batch(batch, logger, total_records, max_words, max_tokens, json_file, store_state_file,counter):
    # Acquire a lock to ensure thread-safe operations for shared resources
    lock = threading.Lock()
    with lock:
        counter = process_records(result=batch, logger=logger, total=total_records, counter=counter, max_words=max_words, max_tokens=max_tokens, json_file=json_file, store_state_file=store_state_file)
    return batch[-1]['id'], counter


def main(id: Optional[int] = 0):
    '''
    This is the main fucntion that extracts the required data from the config file
    '''
    config = configparser.ConfigParser(interpolation=None)
    config.read(os.path.join(os.path.dirname(__file__), "config.ini"))
    log_file_name=config.get('metadata-01',"log_file")
    store_state_file = config.get("metadata-01", "store_state_file")
    logger=getlogger(name=log_file_name)
    json_file=config.get('metadata-01',"json_file")
    limit:int=config.getint("metadata-01","limit")
    current_id:int=config.getint("metadata-01","current_id")
    counter:int=config.getint("metadata-01","counter")
    max_words:int=config.getint("metadata-01","max_words")
    max_tokens:int=config.getint("metadata-01","max_tokens")
    connection=get_db_connection(config,logger)
    total_records=get_total_rows(connection).get('total')
    logger.info(f'{"="*20} Total records : {total_records} {"="*20}')
    current_id, counter = current_state(store_state_file, mode="r")
    try:
        with ThreadPoolExecutor() as executor:
            future_to_batch = {}
            while True:
           
                result=get_limit_rows(connection=connection, limit=limit,current_id=current_id,id=id)
                if len(result)==0:
                    logger.info(f'{"="*20} All records have been processed {"="*20}')
                    break
                future = executor.submit(process_batch, result, logger, total_records, max_words, max_tokens, json_file, store_state_file,counter)
                future_to_batch[future] = result
                for future in as_completed(future_to_batch):
                    current_id, counter = future.result()
                if id > 0:
                    logger.info(f'{"="*20} All records have been processed {"="*20}')
                    break
    except KeyboardInterrupt:
        logger.info(f"State save till Record ID: {current_id}")
        current_state(store_state_file, id=current_id, counter=counter, mode="w")

            
        


if __name__ =="__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--id", default=0, type=int, help="Check for specific ID")
    args = parser.parse_args()
    specific_id = args.id
    main(id=specific_id)

