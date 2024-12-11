import os
import csv
import configparser
import logging
from datetime import datetime

# Define the log directory and log files
LOG_DIR = 'logs'
LOG_FILES = {
    'h1_tags': 'h1_tags_logs.csv',
    'descriptions': 'descriptions_logs.csv',
    'title': 'title_logs.csv'
}

config = configparser.ConfigParser(interpolation=None)
config.read(os.path.join(os.path.dirname(__file__), "config.ini"))
LOG_FILE = config.get('metadata-01', 'log_file')
LOG_CSV = config.get('metadata-01', 'log_csv')
h1_max_length = int(config.get('max_length', 'h1_tag'))
title_max_length = int(config.get('max_length', 'title'))
description_max_length = int(config.get('max_length', 'description'))

# Ensure the log directory exists
os.makedirs(LOG_DIR, exist_ok=True)

def log_error(data_dictionary, record, connection, field_id=29):
    log_file_path = os.path.join(LOG_DIR, LOG_CSV)
    from helperfunctions import checkH1Unique, checkTitleUnique, getFieldRecord
    id = record.get('id')
    h1_tag = data_dictionary.get('H1')
    title = data_dictionary.get('Title')
    description = data_dictionary.get('Description')
    existing_h1_tag = record.get('title')
    fieldRecord = getFieldRecord(connection, field_id, id)
    existing_title = record.get('title')
    log_iteration(h1_tag, existing_h1_tag, title, existing_title, description)

    errors = {}
    if existing_h1_tag == h1_tag:
      errors['Existing Tag'] = "fail"

    if len(h1_tag) > h1_max_length:
        errors['H1 Max Length'] = "fail"

    if not checkH1Unique(connection, h1_tag):
        errors['H1 Unique'] = "fail"
    
    if len(title) > title_max_length:
        errors["Title Max Length"] = "fail"
        
    if not checkTitleUnique(connection, title, field_id):
        errors['Title Unique'] = "fail"
    
    if len(description) > description_max_length:
        errors['Description Length'] = "fail"

    log_entry = {
        'Timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'Article_ID': id,
        'Current H1': record.get('title'),
        'Proposed H1': h1_tag,
        'H1 Length': len(h1_tag),
        'Current Title': record.get('title'),
        'Proposed Title': title,
        'Description': description,
        'Title Length': len(title),
        'Same H1 Re-Generation': errors.get('Existing Tag', 'pass'),
        'H1 Max Length': errors.get('H1 Max Length', 'pass'),
        'H1 Unique': errors.get('H1 Unique', 'pass'),
        'Title Max Length': errors.get('Title Max Length', 'pass'),
        'Title Unique': errors.get('Title Unique', 'pass'),
        'Description Length Check': errors.get('Description Length', 'pass'),
        'Description Length': len(description)
    }

    # Write the log entry to the CSV file
    file_exists = os.path.exists(log_file_path)

    with open(log_file_path, 'a', newline='') as log_file:
        fieldnames = ['Timestamp', 'Article_ID', 'Current H1', 'Proposed H1', 'H1 Length', 'Current Title', 'Proposed Title', 'Description', 'Title Length', 'Same H1 Re-Generation', 'H1 Max Length', 'H1 Unique', 'Title Max Length', 'Title Unique', 'Description Length Check', 'Description Length']
        writer = csv.DictWriter(log_file, fieldnames=fieldnames)

        if not file_exists:
            writer.writeheader()

        writer.writerow(log_entry)

def setup_logger(logger, log_file_path, log_type):
    # Create a file handler
    file_handler = logging.FileHandler(log_file_path)
    # Create a console handler
    console_handler = logging.StreamHandler()

    # Set log levels for both handlers based on log_type
    level = {
        "info": logging.INFO,
        "error": logging.ERROR,
        "warn": logging.WARNING
    }.get(log_type, logging.INFO)

    file_handler.setLevel(level)
    console_handler.setLevel(level)

    # Create a logging format
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)

    # Add the handlers to the logger
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

def log_info(message, log_type="info"):
    # Create a logger object
    log_file_path = os.path.join(LOG_DIR, LOG_FILE)
    logger = logging.getLogger('log_info_logger')
    logger.setLevel(logging.DEBUG)  # Set to DEBUG to capture all levels of logging

    # Check if handlers already exist to avoid duplicate logs
    if not logger.hasHandlers():
        setup_logger(logger, log_file_path, log_type)

    # Log the provided message with appropriate log level
    if log_type == "error":
        logger.error(message)
    elif log_type == "warn":
        logger.warning(message)
    else:
        logger.info(message)

def log_iteration(h1_tag, existing_h1_tag, title, existing_title, description):
    log_info(f"Current H1 Title: {existing_h1_tag}, length:{len(existing_h1_tag)}")
    log_info(f"Proposed H1 Title: {h1_tag}, length:{len(h1_tag)}")
    log_info(f"Current Title: {existing_title}, length:{len(existing_title)}")
    log_info(f"Proposed Title: {title}, length:{len(title)}")
    log_info(f"Proposed Description: {description}, length:{len(description)}")
