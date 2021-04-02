# This is application which build Congnitive services.
# create azure resource translator and use the key and connection, location to get the text translated.
# Upload the translated file to storage account and generate sas token on it.

import logging
import os
import requests, uuid

from azure.storage.blob import BlobServiceClient, generate_blob_sas, AccountSasPermissions
from datetime import datetime
from dateutil.relativedelta import relativedelta
from flask import Flask, render_template, request

from dotenv import load_dotenv
load_dotenv()

app = Flask(__name__)

# Setup logging to get the logs from the application
level = logging.DEBUG
format = f'%(asctime)s %(levelname)s %(name)s : %(message)s'
logging.basicConfig(filename='app.log', level=level, format=format)

@app.route('/', methods=['GET'])
def index():
    return render_template('index.html')

@app.route('/', methods=['POST'])
def index_post():
    """translate given string and put in file and upload to Azure storage account"""
    # Read values from the form
    original_text = request.form['text']
    target_language = request.form['language']

    # Load values from .env
    key = os.environ.get('KEY', '')
    endpoint = os.environ.get('ENDPOINT', '')
    location = os.environ.get('LOCATION', '')

    # Azure storage account details
    connections = {}
    connections['storageaccount_connection'] = os.environ.get('STORAGEACCOUNT_CONNECTION_STRING', '')
    connections['container_name'] = os.environ.get('CONTAINER_NAME', '')
    connections['account_name'] = os.environ.get('STORAGE_ACCOUNT_NAME', '')

    SASTOKEN_LIFE = os.environ.get('SASTOKEN_LIFE', '')

    # Construct the translator method
    path = '/translate?api-version=3.0'
    target_language_parameter = '&to=' + target_language
    constructed_url = endpoint + path + target_language_parameter

    # Set up header for post request
    headers = {
        'Ocp-Apim-Subscription-Key': key,
        'Ocp-Apim-Subscription-Region': location,
        'Content-type': 'application/json',
        'X-ClientTraceID': str(uuid.uuid4())
    }

    BASE_DIR = os.path.abspath(os.getcwd())

    # body of request
    body = [{'text': original_text}]

    # Make call using post
    translator_request = requests.post(constructed_url, headers=headers, json=body)
    # Retrieve JSON response
    translator_response = translator_request.json()
    # Retrieve transaltion response
    translated_text = translator_response[0]['translations'][0]['text']
    # Write translation to a file
    foldername = "translations"
    # path = BASE_DIR + "\\"+foldername
    path = os.path.abspath(os.getcwd()) + "/"+foldername
    if not os.path.exists(path):
        os.mkdir(path)
    out_filename = f'{BASE_DIR}/{foldername}/translated_file_{target_language}.txt'
    with open(out_filename, 'a', encoding='utf-8') as f:
        f.write('\n')
        f.write(f'{original_text}:{translated_text}')
    # print(translated_text)
    
    # Upload the written file to storage account and secure the file with SAS token
    filename = f'translated_file_{target_language}.txt'
    saslife = int(SASTOKEN_LIFE) # Generate token for mentioned months
    infile = f'translated_file_{target_language}.txt'
    inpath = f'{BASE_DIR}/{foldername}' # local path of the file

    url = upload_storageaccount(infile, inpath, connections)
    sas = generate_sastoken(filename, saslife, connections)
    return render_template(
        'results.html',
        storagepath=url,
        sas_token=sas,
    )


def generate_sastoken(filename, saslife, connections):
    container_name = connections.get('container_name')
    connection_string = connections.get('storageaccount_connection')
    try:
        blob_service_client = BlobServiceClient.from_connection_string(connection_string)
        # generateToken with expiry
        sas_token = generate_blob_sas(blob_service_client.account_name, 
                container_name=container_name, blob_name=filename,
                account_key=blob_service_client.credential.account_key,
                permission=AccountSasPermissions(read=True),
                expiry=datetime.now() + relativedelta(months=saslife))
        
        print(f'sas token generated: {sas_token}')
        app.logger.info(f'sas token generated: {sas_token}')
        return sas_token
    except Exception as e:
        print(f'failed to generate token for file {filename} error: {e}')
        app.logger.info(f'failed to generate token for file {filename} error:{e}')
        return None


def upload_storageaccount(infile, inpath, connections):
    connection_string = connections.get('storageaccount_connection')
    container_name = connections.get('container_name')
    account_name = connections.get('account_name')
    try:
        blob_service_client = BlobServiceClient.from_connection_string(connection_string)
        blob_client = blob_service_client.get_blob_client(container = container_name, blob = infile)

        # Upload the file data
        filepath = inpath + '/' + infile
        with open(filepath, 'rb') as data:
            blob_client.upload_blob(data, overwrite = True)
        
        url = f"https://{account_name}.blob.core.windows.net/{container_name}/{infile}"
        app.logger.info(f'Report {infile} uploaded to {url}')
        print(f'File {infile} uploaded to {url}')
        return url
    except Exception as e:
        print(f'failed to upload the report {infile} to {inpath}')
        app.logger.exception(f'failed to upload the report {infile} to {inpath}')
        return None