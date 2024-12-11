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
from helperfunctions import getlogger, percentage, aggregate_into_few, process_text, clean_text, write_into_the_json_file, current_state, do_update, updatetags, getFieldRecord, images_extraction, process_image_paths, images_tag_initialization
from nltk.tokenize import word_tokenize
import nltk
from log_handler import log_error as log_if_error, log_info
simplefilter("ignore", category=ConvergenceWarning)
nltk.download('punkt')
from crewai import Task, Crew, Agent
from langchain.chat_models import ChatOpenAI
import ast
from io import BytesIO
from PIL import Image
import base64
from langchain.schema import HumanMessage
import requests

# Load spaCy model
nlp = spacy.load('en_core_web_md')

global_normalized_tags_list = []


config = configparser.ConfigParser(interpolation=None)
config.read(os.path.join(os.path.dirname(__file__), "config.ini"))
db_prefix=config.get("mysql","prefix"),
db_prefix = db_prefix[0]

client = OpenAI(api_key=config.get("chatgpt", "OPENAI_SECRET_KEY"))
# Set the API key as an environment variable
os.environ["OPENAI_API_KEY"] = config.get("chatgpt", "OPENAI_SECRET_KEY")
# max_run_count =0    # globelvariable for max record run
print(client)
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
        base_sql = f"SELECT c.id, CONCAT(c.introtext, ' ', c.fulltext) AS text, c.fulltext, c.alias, c.images, c.title, c.catid FROM `{db_prefix}content` AS c"
    elif current_id != 0:
        offset=0
        base_sql = f"""
            SELECT c.id, CONCAT(c.introtext, ' ', c.fulltext) AS text, c.fulltext, c.alias, c.images, c.title, c.catid as total FROM `{db_prefix}content` AS c
            LEFT JOIN `{db_prefix}categories` AS cat ON c.catid = cat.id
            WHERE c.`access` = 1
            AND cat.published = 1
            AND c.catid NOT IN (87, 89, 91, 98, 99, 100, 172, 197, 198, 199, 200, 202, 203, 217, 219)
            AND c.id >= {current_id}
        """
    else:
        base_sql = f"""
        SELECT c.id, CONCAT(c.introtext, ' ', c.fulltext) AS text, c.fulltext, c.alias, c.images, c.title, c.catid as total FROM `{db_prefix}content` AS c
        LEFT JOIN `{db_prefix}categories` AS cat ON c.catid = cat.id
        WHERE c.`access` = 1
        AND cat.published = 1
        AND c.catid NOT IN (87, 89, 91, 98, 99, 100, 172, 197, 198, 199, 200, 202, 203, 217, 219)
        """

    # Rest of the function remains the same
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

def get_model():
    get_gpt_model = config.get("chatgpt", "gpt_model")
    model = int(get_gpt_model[0]) if get_gpt_model else 1
    gpt_model = {
        1: "gpt-3.5-turbo-1106",
        2: "gpt-4",
        3: "gpt-3.5-turbo",
        4: "gpt-4o-mini",
        5: "gpt-4-turbo",
        6: "o1-preview",
        7: "gpt-4o"
    }
    return gpt_model.get(model, "gpt-3.5-turbo-1106")

def create_llm():
    return ChatOpenAI(
        model_name=get_model(),
        temperature=0.05,
        openai_api_key=os.environ["OPENAI_API_KEY"],
        model_kwargs={"response_format": {"type": "json_object"}}
    )

def encode_image(image_url):
    response = requests.get(image_url)
    img = Image.open(BytesIO(response.content))
    img = img.convert('RGB')
    buffered = BytesIO()
    img.save(buffered, format="JPEG")
    return base64.b64encode(buffered.getvalue()).decode('utf-8')

def get_alt_tag(llm, image_link):
        if not image_link:
            return ""
        
        base64_image = encode_image(image_link)
        messages = [
            HumanMessage(
                content=[
                    {
                        "type": "text", 
                        "text": "Generate a concise and descriptive alt tag of 125 characters for this image, focusing on its main subject and context. The alt tag should be suitable for SEO and accessibility purposes. Respond with a JSON object containing a single key 'alt_tag' with the generated alt tag as its value."
                    },
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{base64_image}"
                        }
                    }
                ]
            )
        ]
        response = llm.invoke(messages)
        return json.loads(response.content).get('alt_tag', '')

def generate_alt_tags(image_1_link, image_2_link, image_list_link):
    llm = create_llm()
    
    image_1_tag = get_alt_tag(llm, image_1_link)
    image_2_tag = get_alt_tag(llm, image_2_link)
    image_list_tag = [get_alt_tag(llm, img_link) for img_link in image_list_link] if image_list_link else []

    return image_1_tag, image_2_tag, image_list_tag


# log_info("LLM instance created")

# Update the content_generator and reviewer agents to use this llm
# Create agents only if llm is successfully initialized

content_generator = Agent(
    role='Content Generator',
    goal='Generate unique SEO content within specified character limits',
    backstory='You are an expert SEO consultant specializing in Linux security content.',
    allow_delegation=False,
    verbose=False,
    llm=create_llm()
)

reviewer = Agent(
    role='Content Reviewer',
    goal='Ensure generated content meets all specified constraints',
    backstory='You are a meticulous reviewer with an eye for detail and adherence to SEO guidelines.',
    allow_delegation=False,
    verbose=False,
    llm=create_llm()
)

    # log_info("Agents could not be created due to LLM initialization failure", log_type="error")

log_info("Agents created")

def generate_content_task(context: str, title: str, h1_title: str) -> Task:
    log_info("Generating content task")
    prompt = f"""
    Please reset any previous configuration or instructions. We are starting over. No previous information on instructions should be considered. You are a helpful SEO consultant with knowledge of how SEO keywords and tags impact search results and how to identify them within a given context.  The requirement is to create keywords, meta tags, meta description, title tag and H1 tag for an article within the Linux and open source context for an infosec professional audience.  

Definitions:
Linux Security: Linux security refers to the set of practices and measures used to protect Linux-based operating systems from various security threats and vulnerabilities. Linux is a widely used open-source operating system that has gained popularity due to its security features, stability, and flexibility.

Tags: High-level words within the Linux security and open source context that is directly related to the provided content. Tags are formed based only on the specific topic being discussed in the provided content.

Meta Keywords: Meta keywords are specific meta tags located in the HTML head section of a webpage containing a list of keywords that represent the content of the page for search engines.

Title Tag: A title tag (or <title> tag) is an HTML element that provides a webpage title for search engines and internet browsers to use. It can appear in search engine results and link previews for the pages. 

H1 Tag: An H1 tag is the HTML used to create the main title on a webpage and helps indicate the page’s primary topic to visitors and search engines. It contains an opening <h1> tag, the title text, and a closing </h1> tag. 

Description: A summarized description of the article which tells regarding what the article is about and its main takeaways.

Please follow these instructions explicitly, step by step.
1.  Extract 3-5 meta keywords relevant to the context without using overly generic terms relevant to the article's context, focusing on high-volume terms.
2.  Create a list of 5-7 relevant high-volume tags based on the specified criteria within the given Linux security context, focusing on the specific topics of interest directly related to the content. Use "{title}" and "{h1_title}" to provide useful content as a basis for your Tag. Tags must not include phrases including "Linux security" or "open source" or "open source security" or "cybersecurity" or "network security" that would apply to any article within the Linux security context. Tags must be case-insensitive, singular form, and use natural English words without underscores or hyphens.
3.  Create a title tag under 85 characters or 8 words, following SEO practices. For "Advisory" content, use unique terms (e.g., SLE-15-SP4, CVE numbers, ELSA identifiers) from the article for distinction and ensure it's different from any H1 tag. If applicable, include the application name with its version (e.g., gdk-pixbuf2-2.42.6-4). Use "{title}" to reflect the content accurately and uniquely. Title tag must not be the same as "{h1_title}" or "{title}".
4.  Generate an H1 tag according to SEO best practices. Title and H1 tags must not be the same. H1 Tag can be no longer than 9 words or 90 characters. H1 Tag should be very descriptive and contain more detail about the article than title tags. H1 tags should be close to the main synopsis of the article. Use "{title}" to provide useful content as a basis for your H1 tag to make it unique. H1 tag must not be the same as "{h1_title}" or "{title}".
5.  Identify the type of article as one of Advisory, which is content related to a security update of some kind, or Feature, which is a piece of news or a story that digs deep on a particular topic.
6.  The description should be generated so that it highlights main points of the article and it should not be longer than 150 characters. It should be unique and should not match with other descriptions generated before.


    Use provided "{title}" and "{h1_title}" as reference for uniqueness.
    Double-check all character and word counts before finalizing.

    Given Content: {context}

    Output the result as a JSON object.

    ###
Example Output:
{{
    "Keywords": ["Keyword1", "Keyword2", "Keyword3"],
    "Description": "A succinct summary that encapsulates the main points of the content, optimized for search engines and not exceeding 150 characters.",
    "Tags": ["Tag1", "Tag2", "Tag3", "Tag4", "Tag5", "Tag6", "Tag7" ],
    "Title": "Linux Security Article Title",
    "H1": "Linux Security H1 Tag",
    "Type": "Feature or Advisory"
}}
    """
    return Task(
        description=prompt,
        agent=content_generator,
        expected_output="A JSON object containing Keywords, Tags, Title, H1, Type, and Description."
    )

def review_content_task() -> Task:
    log_info("Generating review task")
    return Task(
        description="""
        Review the generated content and ensure it meets the following criteria and definition:
        
        Definitions:
Linux Security: Linux security refers to the set of practices and measures used to protect Linux-based operating systems from various security threats and vulnerabilities. Linux is a widely used open-source operating system that has gained popularity due to its security features, stability, and flexibility.

Tags: High-level words within the Linux security and open source context that is directly related to the provided content. Tags are formed based only on the specific topic being discussed in the provided content.

Meta Keywords: Meta keywords are specific meta tags located in the HTML head section of a webpage containing a list of keywords that represent the content of the page for search engines.

Title Tag: A title tag (or <title> tag) is an HTML element that provides a webpage title for search engines and internet browsers to use. It can appear in search engine results and link previews for the pages. 

H1 Tag: An H1 tag is the HTML used to create the main title on a webpage and helps indicate the page’s primary topic to visitors and search engines. It contains an opening <h1> tag, the title text, and a closing </h1> tag. 

Description: A summarized description of the article which tells regarding what the article is about and its main takeaways.

Criteria:
Please follow these instructions explicitly, step by step.
1.  Extract 3-5 meta keywords relevant to the context without using overly generic terms relevant to the article's context, focusing on high-volume terms.
2.  Create a list of 5-7 relevant high-volume tags based on the specified criteria within the given Linux security context, focusing on the specific topics of interest directly related to the content. Use "{title}" and "{h1_title}" to provide useful content as a basis for your Tag. Tags must not include phrases including "Linux security" or "open source" or "open source security" or "cybersecurity" or "network security" that would apply to any article within the Linux security context. Tags must be case-insensitive, singular form, and use natural English words without underscores or hyphens.
3.  Create a title tag under 85 characters or 8 words, following SEO practices. For "Advisory" content, use unique terms (e.g., SLE-15-SP4, CVE numbers, ELSA identifiers) from the article for distinction and ensure it's different from any H1 tag. If applicable, include the application name with its version (e.g., gdk-pixbuf2-2.42.6-4). Use "{title}" to reflect the content accurately and uniquely. Title tag must not be the same as "{h1_title}" or "{title}".
4.  Generate an H1 tag according to SEO best practices. Title and H1 tags must not be the same. H1 Tag can be no longer than 9 words or 90 characters. H1 Tag should be very descriptive and contain more detail about the article than title tags. H1 tags should be close to the main synopsis of the article. Use "{title}" to provide useful content as a basis for your H1 tag to make it unique. H1 tag must not be the same as "{h1_title}" or "{title}".
5.  Identify the type of article as one of Advisory, which is content related to a security update of some kind, or Feature, which is a piece of news or a story that digs deep on a particular topic.
6.  The description should be generated so that it highlights main points of the article and it should not be longer than 150 characters. It should be unique and should not match with other descriptions generated before.


    Use provided "{title}" and "{h1_title}" as reference for uniqueness.
    Double-check all character and word counts before finalizing.

        If any criteria are not met, return a JSON object with 'approved': false and 'feedback' explaining the issues in detail.
        If all criteria are met, return a JSON object with 'approved': true.
        """,
        agent=reviewer,
        expected_output="A JSON object with 'approved' (boolean) and 'feedback' (string) fields."
    )

def process_context_with_crew(context: str, h1_title: str, metadesc: str, title: str, max_attempts: int = 5) -> Dict[str, Any]:
    for attempt in range(max_attempts):
        try:
            crew = Crew(
                agents=[content_generator, reviewer],
                tasks=[
                    generate_content_task(context, title, h1_title),
                    review_content_task()
                ],
                verbose=False
            )

            result = crew.kickoff()

            generated_content_raw = result.tasks_output[0].raw
            generated_content = json.loads(generated_content_raw.strip('```json\n'))
            
            review_result_raw = result.tasks_output[1].raw
            review_result = json.loads(review_result_raw.strip('```json\n'))
            
            if review_result.get('approved', False):
                return {
                    'text': generated_content,
                    'n_tokens': len(str(generated_content))
                }
            else:
                log_info(f"Attempt {attempt + 1} failed. Feedback: {review_result.get('feedback', 'No feedback provided')}")
        except Exception as e:
            log_info(f"Error in attempt {attempt + 1}: {str(e)}", log_type="error")
        
    log_info("Max attempts reached. Content generation failed.")
    return {'text': '', 'n_tokens': 0}

async def process_text_async(client, context):
    log_info("Starting process_text_async")
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

async def process_contexts(contexts: List[str], h1_title: str, metadesc: str, title: str) -> List[Dict[str, Any]]:
    log_info("Starting process_contexts")
    tasks = [process_context_with_crew(context, h1_title, metadesc, title) for context in contexts]
    return await asyncio.gather(*tasks)

def process_context(contexts: list, h1_title: str, metadesc: str, title: str):
    metadata = []
    n_tokens = []

    try:
        if len(contexts) == 1:
            result = process_context_with_crew(contexts[0], h1_title, metadesc, title)
            metadata.append(result['text'])
            n_tokens.append(result['n_tokens'])
        else:
            for context in contexts:
                result = process_context_with_crew(context, h1_title, metadesc, title)
                metadata.append(result['text'])
                n_tokens.append(result['n_tokens'])
    except Exception as e:
        log_info(f"Process Context ERROR : {e}", log_type="error")

    return pd.DataFrame(data={'text': metadata, 'n_tokens': n_tokens})

def extract_record_text(record: Dict[str, Any], max_words: int, max_tokens: int, fieldRecord: Dict[str, Any]):
    log_info("Starting extract_record_text")
    try:
        id = record.get('id')
        h1_title = record.get('title')
        metadesc = record.get('metadesc')
        title = record.get('title')
        text = record.get("text")
        fulltext = record.get("fulltext")
        images = record.get("images")
        if len(text) > 0:   
            log_info(f"Processing text for record ID: {id}")
            image_1, image_2, image_list = images_extraction(images=images, text=fulltext)
            image_1_link, image_2_link, image_list_link = process_image_paths(image_1, image_2, image_list)
            image_1_tag, image_2_tag, image_list_tag = generate_alt_tags(image_1_link, image_2_link, image_list_link)
            image_dict_tag, text_tagged = images_tag_initialization(images, fulltext, image_1_tag, image_2_tag, image_list_tag)
            text = clean_text(fulltext=text, max_words=max_words)
            df = process_text(text=text, max_tokens=max_tokens)
            df = process_context(contexts=[df], h1_title=h1_title, metadesc=metadesc, title=title)
            log_info(f"Successfully processed the record ID:{id}")
            return [str(df["text"][0]), image_dict_tag, text_tagged]
        else:
            log_info(f"Record ID: {id} fulltext field has empty string.")
            return None
    except Exception as e:
        log_info(f"Extract_record_text ERROR : {e}", log_type="error")
        return None

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
            metadata, image_dict_tag, text_tagged = extract_record_text(record=record, max_words=max_words, max_tokens=max_tokens, fieldRecord=fieldRecord)
            
            if metadata is not None:
                dict_response = ast.literal_eval(metadata)
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
                    succeed = do_update(connection=connection, record=record, dict_response=dict_response, base_url=base_url, image_dict_tag=image_dict_tag, text_tagged=text_tagged, logger=logger)
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