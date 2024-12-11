import logging
import hashlib
from logging import Logger
from copy import copy
from pandas import DataFrame
import math
import re
import tiktoken
from bs4 import BeautifulSoup
import pandas as pd
import json
import os
tokenizer = tiktoken.get_encoding("cl100k_base")
from pymysql import Connection,MySQLError
from datetime import datetime
import configparser
from log_handler import log_info
from typing import Dict, Any, Optional, List
from langchain.schema import HumanMessage

config = configparser.ConfigParser(interpolation=None)
config.read(os.path.join(os.path.dirname(__file__), "config.ini"))
db_prefix=config.get("mysql","prefix"),
db_prefix = db_prefix[0]
taglogfile_name=config.get('metadata-01',"tag_log_file")

h1_max_length = int(config.get('max_length', 'h1_tag'))
title_max_length = int(config.get('max_length', 'title'))
description_max_length = int(config.get('max_length', 'description'))

existing_tags_list= []


class ColoredFormatter(logging.Formatter):
    datefmt = "%Y-%m-%d %H:%M:%S"
    MAPPING = {
        'DEBUG'   : 37, # white
        'INFO'    : 36, # cyan
        'WARNING' : 33, # yellow
        'ERROR'   : 31, # red
        'CRITICAL': 41, # white on red bg
    }
    PREFIX = '\033['
    SUFFIX = '\033[0m'

    def __init__(self, patern):
        logging.Formatter.__init__(self, patern)

    def format(self, record):
        colored_record = copy(record)
        levelname = colored_record.levelname
        seq = ColoredFormatter.MAPPING.get(levelname, 37) # default white
        colored_levelname = ('{0}{1}m{2}{3}') \
            .format(ColoredFormatter.PREFIX, seq, levelname, ColoredFormatter.SUFFIX)
        colored_record.levelname = colored_levelname
        return logging.Formatter.format(self, colored_record)
    

def getlogger(name, level=logging.INFO):
    logger=logging.getLogger(name)
    logger.setLevel(level)

    file=logging.FileHandler(name)
    file.setFormatter(logging.Formatter(fmt='%(asctime)s - %(levelname)s - %(message)s',datefmt='%Y-%m-%d %H:%M:%S'))
    logger.addHandler(file)

    console=logging.StreamHandler()
    console.setFormatter(ColoredFormatter("%(asctime)s - %(levelname)s - %(message)s"))
    logger.addHandler(console)
    return logger


def get_sha1_hash(data):
    result = hashlib.sha224(data.encode()) 
    return result.hexdigest()


def split_into_many(text: str, max_tokens: int = 100) -> list[str]:
        """
        spliting the text into the given pattern and add the spliting text in a one sentence which split text 
            have token length less than 100
            """
        sentences = re.split("(?<=[.。!?।]) +", text)
        n_tokens = [len(tokenizer.encode(" " + sentence)) for sentence in sentences]
        for i, (sentence, token) in enumerate(zip(sentences, n_tokens)):
            if token > max_tokens:
                extra_sentences = sentence.splitlines(keepends=True)
                extra_tokens = [
                    len(tokenizer.encode(" " + extra_sentence))
                    for extra_sentence in extra_sentences
                ]
                del n_tokens[i]
                del sentences[i]
                n_tokens[i:i] = extra_tokens
                sentences[i:i] = extra_sentences

        chunks = []
        tokens_so_far = 0
        chunk = []
        for i, (sentence, token) in enumerate(zip(sentences, n_tokens)):
            if tokens_so_far + token > max_tokens or (i == (len(n_tokens) - 1)):
                chunks.append(" ".join(chunk))
                chunk = []
                tokens_so_far = 0

            chunk.append(sentence)
            tokens_so_far += token + 1

        return chunks



def aggregate_into_few(df:DataFrame,logger:Logger):

    """
    Aggregate the text into list elements by adding the multiple
      rows into one single list element with 1000 token size
        and if the token exceeds by 1000 then it will add up into the new index of the list
    """
    aggregate_text=[]
    current_text=""
    current_length=0
    max_index = len(df["n_tokens"]) - 1
    token_length = sum(df["n_tokens"])
    if max_index == 0:
        return df["text"]
    if token_length > 1000:
        max_length = round(token_length / math.ceil(token_length / 1000)) + 100
    else:
        max_length = 1000
    for i, row in df.iterrows():
        current_length+=row['n_tokens']
        if current_length>max_length:
            aggregate_text.append(current_text)
            current_length=0
            current_text=""
        current_text+=row['text']

        if max_index==i:
            aggregate_text.append(current_text)
    return aggregate_text


def clean_text(fulltext:str,max_words:int):
    """Converting the text to a soup and extracting only text from the soup  and  the spliting the text based on the max words 
         and return the text """
    soup=BeautifulSoup(fulltext,'html.parser')
    text=soup.get_text(separator=" ")
    cleaned_string = re.sub(r'\n\s*\n', '\n',text)
    split_text=cleaned_string.split()
    if len(split_text)>max_words:
        cleaned_string=" ".join(split_text[:max_words])
    return cleaned_string


def process_text(text:str,max_tokens:int):
    """ Apply a tokenization to the text to count the token if the token length is greater then max_token then 
      forward the text to split into many function to split the text into multiple rows with token lenggth 100  """
    tokens = len(tokenizer.encode(text))
    if tokens > max_tokens:
        chunks=split_into_many(text)
        df=pd.DataFrame(chunks,columns=['text'])
        df['n_tokens']=df.text.apply(lambda x : len(tokenizer.encode(x)))
        return df
    else:
        df=pd.DataFrame([text],columns=['text'])
        df['n_tokens']=df.text.apply(lambda x : len(tokenizer.encode(x)))
        return df
        

def write_into_the_json_file(response:dict,json_file:str):
    """Append a record to a JSON file"""
    try:
        with open(json_file,'r+') as file:
            filedata=json.load(file)
            filedata.append(response)
            file.seek(0)
            json.dump(filedata, file, indent=4)
    except FileNotFoundError:
        with open(json_file, 'w') as file:
            json.dump([response], file, indent=4)
    except json.JSONDecodeError:
        with open(json_file, 'w') as file:
            json.dump([response], file, indent=4)


def current_state(index_filename: str, id: int = 0, counter: int = 0, mode='r'):
    """ To store the current state """
    filename = os.fspath(index_filename)
    baseFilename = os.path.abspath(filename)
    if os.path.exists(baseFilename) == False or mode == 'w':
        with open(index_filename, 'w') as f:
            json.dump({
                'id': id,
                'counter': counter
            }, f, indent=4)
        return id, counter
    else:
        with open(baseFilename, 'r') as f:
            data = json.load(f)
            return int(data.get('id')), int(data.get('counter'))



def percentage(number, total):
    per = float(number)/float(total)
    to_str = "{:.1%}".format(per)
    return to_str

def get_path_from_cateories_table(connection,catid):
    if not catid:
        return None
    sql=f"SELECT c.path FROM {db_prefix}categories as c WHERE id={catid}"
    with connection.cursor() as cursor:
        cursor.execute(sql)
        record=cursor.fetchone()
    path=record.get('path')
    if path=="uncategorised":
        return None
    return path


def get_record(connection,alias):
    # sql=f"SELECT c.id,c.title,c.url,c.opengraph,c.twitterCards FROM {db_prefix}easyfrontendseo as c WHERE `url` LIKE '%{alias}%'"
    sql = """
        SELECT 
            c.id,
            c.title,
            c.url,
            c.opengraph,
            c.twitterCards,
            LOCATE('{alias}', c.url) AS position_score,
            CASE 
                WHEN c.url = '{alias}' THEN 1
                ELSE 0
            END AS exact_match_bonus,
            (LOCATE('{alias}', c.url) * 1000) - 
            CASE 
                WHEN c.url = '{alias}' THEN 1
                ELSE 0
            END AS final_score
        FROM 
            xu5gc_easyfrontendseo AS c
        WHERE 
            c.url LIKE '%{alias}%'
        ORDER BY 
            final_score ASC
        LIMIT 1;

    """
    with connection.cursor() as cursor:
        cursor.execute(sql)
        record=cursor.fetchone()
    return record

def get_prepare_json(record,description,base_url,image_tag):
    opengarph_json_data = {
                "title": record['title'],
                "description": description,
                "image": image_tag,
                "type": "article",
                "site_name": "Linux Security",
                "url": f"{base_url}/{record['url']}",
                "image:alt": record['title']
            }
    twitter_Cards_json_data = {
        "title": record['title'],
        "description": description,
        "image": image_tag,
        "card":"summary_large_image",
        "site":"lnxsec",
        "creator":"lnxsec",
        "image:alt": record['title']
    }
    opengarph_json_data = json.dumps(opengarph_json_data)
    twitter_Cards_json_data=json.dumps(twitter_Cards_json_data)
    return opengarph_json_data,twitter_Cards_json_data

def get_prepare_json_for_new_entry(title,description,url,base_url,image_tag):
    opengarph_json_data = {
                "title": title,
                "description": description,
                "image": image_tag,
                "type": "article",
                "site_name": "Linux Security",
                "url": f"{base_url}/{url}",
                "image:alt": title
            }
    twitter_Cards_json_data = {
        "title":title,
        "description": description,
        "image": image_tag,
        "card":"summary_large_image",
        "site":"lnxsec",
        "creator":"lnxsec",
        "image:alt": title
    }
    opengarph_json_data = json.dumps(opengarph_json_data)
    twitter_Cards_json_data=json.dumps(twitter_Cards_json_data)
    return opengarph_json_data,twitter_Cards_json_data

def do_update(connection: Connection, record:dict, dict_response:dict, base_url:str, image_dict_tag:str, text_tagged:str, logger):
    content_table_id=record.get("id")
    description=dict_response["Description"]
    alias=record["alias"]
    tags=dict_response["Tags"]
    content_id=record["id"]
    title=dict_response['Title']
    h1_title=dict_response['H1']
    content_table_title=record.get("title")
    catid=record.get("catid")
    images=record.get("images")
    metadata=dict_response["Keywords"]
    try: 
        if len(description)>description_max_length:
            print(f" The description length of {content_table_id} is {len(description)} -- ")
        images=json.loads(images)['image_fulltext'] if images!="" else ""
        image_tag=f"{base_url}/{images}" if images!="" else ""
        if metadata is None and description is None:
            return False
        if len(metadata)>=1:
            metadata=",".join(metadata)
        record=get_record(connection,alias)
        if h1_title != title:
            updatecontent(connection, logger, h1_title, description, alias, image_dict_tag, text_tagged)
            updatefieldvalue(connection, logger, title, content_table_id)
            updateeasyfrontendseo(record,description,base_url,image_tag, metadata,content_table_id,content_table_title,connection,catid,alias,logger)
        if tags:
            # excluded_catids = [87, 89, 91, 98, 99, 100, 172, 197, 198, 199, 200, 202, 203, 217, 219]
            # #need to confirm 
            # if content_id not in excluded_catids:
            updatetags(connection,content_id,tags)

    except MySQLError as e:
        connection.rollback()
        raise e
    except Exception as e:
        log_info(json.dumps({"id":content_table_id,"message":str(e)}))

def getFieldRecord(connection, field_id, id):
    sql = f"SELECT * FROM {db_prefix}fields_values WHERE field_id = %s AND item_id = %s;"
    args = (field_id, id)

    with connection.cursor() as cursor:
        cursor.execute(sql, args)
        record = cursor.fetchone()
    return record

def updatefieldvalue(connection, logger, title, id, field_id=29):
    # Check if title is valid
    title = checkTitle(connection, title, field_id)
    record = getFieldRecord(connection, field_id, id)

    # Prepare SQL for update or insert
    if record:
        sql = f"""
            UPDATE {db_prefix}fields_values
            SET value = %s
            WHERE field_id = %s AND item_id = %s;
        """
        args = (title, field_id, id)
    else:
        sql = f"""
            INSERT INTO {db_prefix}fields_values (value, item_id, field_id)
            VALUES (%s, %s, %s);
        """
        args = (title, id, field_id)
    # Execute the SQL command
    with connection.cursor() as cursor:
        cursor.execute(sql, args)
        connection.commit()
        log_info(f'Inserted/Updated into {db_prefix}fields_values (field_id={field_id}, value={title})')
    
    return True

def checkH1Unique(connection, h1):
    sql = f"""
        SELECT COUNT(*) as total FROM `{db_prefix}content` as c
        WHERE c.title = %s;
    """
    args = (h1,)
    with connection.cursor() as cursor:
        cursor.execute(sql, args)
        result=cursor.fetchone()
    return not bool(result.get('total'))
    

def checkH1(connection, h1_title):
    if h1_title and len(h1_title) <= h1_max_length and checkH1Unique(connection, h1_title):
        return h1_title
    return ''

def checkTitleUnique(connection, title, field_id):
    sql = f"""
        SELECT COUNT(*) as total FROM `{db_prefix}content` as c
        WHERE c.title = %s;
    """
    args = (title,)
    with connection.cursor() as cursor:
        cursor.execute(sql, args)
        result=cursor.fetchone()
    return not bool(result.get('total'))

def checkTitle(connection, title, field_id):
    if title and len(title) <= title_max_length and checkTitleUnique(connection, title, field_id):
        return title
    return ''

def checkMetaDesc(connection, meta_desc):
    if meta_desc and len(meta_desc)<description_max_length:
        return meta_desc
    return ''


def updatecontent(connection, logger, h1_title:str, meta_desc:str, alias:str, image_dict_tag:str, text_tagged:str):
    #Confirm from Shubham if we want to check size of meta desc.
    h1_title = checkH1(connection, h1_title)
    meta_desc = checkMetaDesc(connection, meta_desc)

    set_values = []
    args = []
    if h1_title:
        set_values.append("title = %s")
        args.append(h1_title)

    if meta_desc:
        set_values.append("`metadesc` = %s")
        args.append(meta_desc)
    
    if image_dict_tag:
        set_values.append("`images` = %s")
        args.append(image_dict_tag)

    if text_tagged:
        set_values.append("`fulltext` = %s")
        args.append(text_tagged)

    if set_values:
        values_to_update = ", ".join(set_values)
        sql = f"""
            UPDATE {db_prefix}content
            SET {values_to_update}
            WHERE alias = %s;
        """
        args.append(alias)
        print(args)
        with connection.cursor() as cursor:
            cursor.execute(sql, args)
            connection.commit()
            log_info(f'Insert into {db_prefix}Content (title, metadesc)')
            return True
    log_info(f'Failed to insert into {db_prefix}Content (title, metadesc)', log_type="error")
    return False

def updateeasyfrontendseo(record,description,base_url,image_tag, metadata,content_table_id,content_table_title,connection,catid,alias,logger):
    dataset = {
        'keywords': metadata if metadata else record.get('metadata', ''),
        'description': description if description and len(description) < description_max_length else record.get('description', ''),
    }
    if record:
        dataset['id'] = record.get("id")
        dataset['opengraph'], dataset['twitterCards'] = get_prepare_json(record,description,base_url,image_tag)
        sql= f"""
            UPDATE {db_prefix}easyfrontendseo
            SET keywords = %s, description = %s, opengraph = %s, twitterCards = %s
            WHERE id = %s AND (opengraph IS NULL OR opengraph = '') AND (twitterCards IS NULL OR twitterCards = '')
        """
        args=(dataset["keywords"], dataset["description"], dataset["opengraph"], dataset["twitterCards"], dataset["id"])
    else:
        path=get_path_from_cateories_table(connection,catid)
        if path is not None:
            url=f"{path}/{alias}"
        else:
            url=alias
        dataset['opengraph'], dataset['twitterCards'] = get_prepare_json_for_new_entry(content_table_title,description,url,base_url,image_tag)
        urlHash = get_sha1_hash(alias)
        log_info(urlHash)
        log_info(len(urlHash))
        sql= sql=f"INSERT INTO {db_prefix}easyfrontendseo (url, title, description, keywords, generator,robots, openGraph, twitterCards, canonicalUrl,thumbnail, urlHash) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)"
        args = [
            url, 
            content_table_title, 
            dataset.get("description"),
            dataset.get("keywords"),
            "",
            "index, follow",
            dataset.get('opengraph'),
            dataset['twitterCards'],
            f"{base_url}/{url}",
            "",
            urlHash
        ]
    with connection.cursor() as cursor:
        cursor.execute(sql, args)
        connection.commit()
        log_info(f'ID:{content_table_id} "title":{content_table_title} "Alias": {alias} - has been updated in database')
        return True




def updatetags(connection,content_id,tags):
    try:
        tag_logger=getlogger(name=taglogfile_name)
        # content_id= 356646
        # excluded_catids = (87, 89, 91, 98, 99, 100, 172, 197, 198, 199, 200, 202, 203, 217, 219)
        # Convert to lowercase and replace spaces with hyphens
        global existing_tags_list
        tags_alias = [tag.lower().replace(' ', '-') for tag in tags]
        with connection.cursor() as cursor:
            for al, tag in zip(tags_alias, tags):
                sql = f"SELECT * FROM {db_prefix}tags WHERE alias = %s"
                cursor.execute(sql, (al,))
                exiting_tags = cursor.fetchone()
                if exiting_tags:
                    if tag not in existing_tags_list:
                        existing_tags_list.append(tag)
                        print(f"{tag}  tag is already exists")
                    tag_id =exiting_tags["id"]
                    contentitem_tag_mapupdate(connection,content_id, tag_id)
                else:
                    lft = f"SELECT  max(rgt) from {db_prefix}tags"
                    lft = cursor.execute(lft)
                    max_lft = cursor.fetchone()
                    lft = max_lft["max(rgt)"]+1
                    rgt = lft+1
                    datatime = datetime.now()
                    sql = f'''INSERT INTO {db_prefix}tags (
                            parent_id, lft, rgt, level, path, title, alias, 
                            note, description, published, checked_out, checked_out_time, 
                            access, params, metadesc, metakey, metadata, created_user_id, 
                            created_time, created_by_alias, modified_user_id, modified_time, 
                            images, urls, hits, language, version, publish_up, publish_down
                        ) VALUES (
                            '1', %s, %s, '0', %s, %s, %s, 
                            '', '', '1', NULL, NULL, '1', '', '', 
                            '', '', '10', %s, '', '0', %s, 
                            '', '', '0', '*', '1', %s, NULL
                        )'''
                    cursor.execute(sql,(lft, rgt, al, tag, al ,datatime,datatime,datatime))
                
                    # Now you can work with the inserted record as neede
                    connection.commit()
                    sql = f"SELECT * FROM {db_prefix}tags  ORDER BY id DESC LIMIT 1"
                    cursor.execute(sql)
                    result = cursor.fetchone()
                    tag_id = result["id"]
                    log_info(f"Tag_id : {tag_id} , Tag :{tag} , content_id :{content_id} ")
                
                    contentitem_tag_mapupdate(connection,content_id, tag_id)
        return tags
    except Exception as e:
        print(e)



def contentitem_tag_mapupdate(connection,con_id, tag):
    try:
        tag_logger=getlogger(name=taglogfile_name)
        query = f"SELECT * FROM {db_prefix}contentitem_tag_map WHERE content_item_id = %s AND tag_id = %s"
        with connection.cursor() as cursor:
            cursor.execute(query, (con_id, tag))
            results = cursor.fetchone()
        if results:
            print(f" content_item_id : {con_id} and  tag_id {tag}  tag is already exists")
        else:
            with connection.cursor() as cursor:
                core_content = f"SELECT  max(core_content_id) from {db_prefix}contentitem_tag_map"
                cursor.execute(core_content)
                max_lft = cursor.fetchone()
                core_id = max_lft["max(core_content_id)"]+1
                datatime = datetime.now()
                sql = f"INSERT INTO {db_prefix}contentitem_tag_map (type_alias, core_content_id, content_item_id, tag_id, tag_date, type_id) VALUES ('com_content.article', %s, %s, %s, %s, '1')"
                # cursor.execute(sql)
                cursor.execute(sql,(core_id,con_id,tag,datatime))
                connection.commit()

    except Exception as e:
        print(e)


def images_extraction(images, text):
    log_info("Starting image extraction")
    log_info(f"Raw images input: {images}")  # Add this debug line
    
    try:
        if images:
            # Try to fix common JSON formatting issues
            if isinstance(images, str):
                # Replace single quotes with double quotes
                images = images.replace("'", '"')
                # Add quotes to unquoted property names
                images = re.sub(r'(\{|\,)\s*([a-zA-Z0-9_]+)\s*:', r'\1"\2":', images)
            
            # Parse the JSON string
            images_dict = json.loads(images)
            
            # Extract image_intro and image_fulltext
            image_intro = images_dict.get('image_intro', '')
            image_fulltext = images_dict.get('image_fulltext', '')

            # Use regex to extract up to .jpg or .png
            pattern = r'(.*?\.(?:jpg|png))'
            
            image_intro_match = re.search(pattern, image_intro)
            image_fulltext_match = re.search(pattern, image_fulltext)

            image_intro_result = image_intro_match.group(1) if image_intro_match else ""
            image_fulltext_result = image_fulltext_match.group(1) if image_fulltext_match else ""
            
            # Extract images from 'text'
            text_images = []
            if text:
                img_pattern = r'<img\s+[^>]*src\s*=\s*["\']([^"\']+)["\'][^>]*>'
                img_matches = re.findall(img_pattern, text, re.IGNORECASE)
                text_images = img_matches  # This will be an empty list if no matches are found

            return image_intro_result, image_fulltext_result, text_images

    except json.JSONDecodeError as e:
        log_info(f"Error decoding JSON in images field: {str(e)}")
        log_info(f"Attempted to parse: {images}")
        return "", "", []
    except Exception as e:
        log_info(f"Error in images_extraction: {str(e)}")
        return "", "", []


def process_image_paths(image_1, image_2, image_list):
    base_url = 'https://linuxsecurity.com/'
    
    # Process image_1
    if image_1:
        image_1 = base_url + image_1
    
    # Process image_2
    if image_2:
        image_2 = base_url + image_2
    
    # Process image_list
    if image_list:
        image_list = [base_url + img for img in image_list]
    
    return image_1, image_2, image_list


def images_tag_initialization(images, text, image_tag_1, image_tag_2, image_list_tag):
    log_info("Starting images tag initialization")
    try:
        images_dict = {}
        text_tagged = text

        if images:
            # Try to fix common JSON formatting issues
            if isinstance(images, str):
                # Replace single quotes with double quotes
                images = images.replace("'", '"')
                # Add quotes to unquoted property names
                images = re.sub(r'(\{|\,)\s*([a-zA-Z0-9_]+)\s*:', r'\1"\2":', images)
            images_dict = json.loads(images)
            images_dict['image_intro_alt'] = image_tag_1 
            images_dict['image_fulltext_alt'] = image_tag_2 

            # Convert the dictionary back to a JSON string with double quotes
            images_dict = json.dumps(images_dict, ensure_ascii=False)

        if text and image_list_tag:
            # Find all img tags in the text
            img_pattern = r'<img\s+[^>]*src\s*=\s*["\']([^"\']+)["\'][^>]*>'
            img_matches = re.finditer(img_pattern, text, re.IGNORECASE)

            # Create a list of (start, end) positions for each img tag
            img_positions = [(m.start(), m.end()) for m in img_matches]

            # Reverse both lists to process from end to start (to avoid messing up string indexes)
            img_positions.reverse()
            image_list_tag.reverse()

            # Replace or add alt tags
            for (start, end), alt_text in zip(img_positions, image_list_tag):
                img_tag = text[start:end]
                if 'alt=' in img_tag:
                    # Replace existing alt
                    new_img_tag = re.sub(r'alt\s*=\s*"[^"]*"', f'alt="{alt_text}"', img_tag)
                else:
                    # Add new alt
                    new_img_tag = img_tag.replace('>', f' alt="{alt_text}">', 1)
                
                text_tagged = text_tagged[:start] + new_img_tag + text_tagged[end:]

        return images_dict, text_tagged

    except json.JSONDecodeError:
        log_info("Error decoding JSON in images field")
        return {}, text
    except Exception as e:
        log_info(f"Error in images_tag_initialization: {str(e)}")
        return {}, text