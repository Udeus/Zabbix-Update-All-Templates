import os
import argparse
import shutil
import urllib.request
import requests
import zipfile
import re
from time import strftime
from tabulate import tabulate
from utils import zabbix_url, get_file


help_command = [["help", "Show all commands"], ["templates", "Show all templates and ID"],
                ["backup", "Create backup one template"], ["backups", "Create backup all templates"],
                ["update templates", "Update all templates"], ["author", "About author"], ["exit", "Close script"]]

parser = argparse.ArgumentParser(description="Zabbix Update all templates | More info: https://github.com/Udeus/Zabbix-Update-All-Templates")
parser.add_argument("--url", type=str, help="Zabbix url address")
parser.add_argument("--token", type=str, help="API token")
args = parser.parse_args()


try:
    terminal_width = os.get_terminal_size().columns
except OSError:
    terminal_width = 80

if args.url:
    api_url = zabbix_url(args.url)
else:
    api_url = zabbix_url(input("Zabbix url address: "))


if args.token:
    api_token = args.token
else:
    api_token = input("Zabbix API token: ")


print(tabulate(help_command, headers=["Command", "Description"], tablefmt="psql"))
print("How to use: https://github.com/Udeus/Zabbix-Update-All-Templates")


def connect_api(api_date):
    request_header = {'Authorization': 'Bearer ' + api_token, 'Content-Type': 'application/json-rpc'}
    response = requests.post(api_url, data=api_date, headers=request_header)
    response = response.json()['result']

    return response


def get_zabbix_version():
    request_header = {'Content-Type': 'application/json-rpc'}
    api_date = '{"jsonrpc": "2.0","method": "apiinfo.version","params": [],"id": 1}'
    response = requests.post(api_url, data=api_date, headers=request_header)
    response = response.json()['result']
    return response


def get_templates():
    api_date = '{"jsonrpc": "2.0","method": "template.get","params": {"output": ["name", "groupid"]},"id": 1}'
    response = connect_api(api_date)
    print(tabulate(response, headers="keys", tablefmt="psql"))


def create_one_backup():
    template_id = input("Template ID: ")

    api_date = f'{{"jsonrpc": "2.0","method": "template.get","params": {{"output": ["name"],"templateids": "{template_id}"}},"id": 1}}'
    template_name = connect_api(api_date)[0]['name']

    api_date = f'{{"jsonrpc": "2.0","method": "configuration.export","params": {{"options": {{"templates": ["{template_id}"]}},"format": "yaml"}},"id": 1}}'
    response = connect_api(api_date)

    time_today = strftime("%d-%m-%Y")
    os.makedirs(f"backups/{time_today}", exist_ok=True)

    with open(f'backups/{time_today}/{template_name}.yaml', 'w') as f:
        f.write(response)

    print(f"Backup template {template_name} created")


def create_backups():
    api_date = '{"jsonrpc": "2.0","method": "template.get","params": {"output": ["name", "groupid"]},"id": 1}'
    resp_template_list = connect_api(api_date)

    template_number = 1
    list_length = len(resp_template_list)

    time_today = strftime("%d-%m-%Y")
    os.makedirs(f"backups/{time_today}", exist_ok=True)

    for item in resp_template_list:
        template_id = item['templateid']
        template_name = item['name']

        api_date = f'{{"jsonrpc": "2.0","method": "configuration.export","params": {{"options": {{"templates": ["{template_id}"]}},"format": "yaml"}},"id": 1}}'
        response = connect_api(api_date)

        print(f'{template_number}/{list_length}')
        template_number += 1

        with open(f'backups/{time_today}/{template_name}.yaml', 'w', encoding='utf-8') as f:
            f.write(response)

    print('All backups created')


def update_template(filename):
    data_file = get_file(filename)
    api_date = f'{{"jsonrpc": "2.0","method": "configuration.import","params": {{"format": "json","rules": {{"templates": {{"createMissing": true,"updateExisting": true}},"items": {{"createMissing": true,"updateExisting": true,"deleteMissing": true}},"triggers": {{"createMissing": true,"updateExisting": true,"deleteMissing": true}},"valueMaps": {{"createMissing": true,"updateExisting": false}}}},"source": {data_file} }},"id": 1}}'
    connect_api(api_date)
    print(f'Update: {filename}')


def download_templates():
    zabbix_version = get_zabbix_version()
    print(f'Downloading templates for Zabbix {zabbix_version}')
    zabbix_version = re.search("^([0-9].[0-9])", zabbix_version)

    repo_url = f'https://git.zabbix.com/rest/api/latest/projects/ZBX/repos/zabbix/archive?at=refs%2Fheads%2Frelease%2F{zabbix_version.group(0)}&format=zip'

    name_zip_file = "zabbix.zip"
    try:
        shutil.rmtree("templates")
    except:
        pass

    urllib.request.urlretrieve(repo_url, name_zip_file)

    with zipfile.ZipFile(name_zip_file, 'r') as zip_ref:
        zip_ref.extractall("tmp/")
    os.remove(name_zip_file)
    shutil.move("tmp/templates", "templates")
    shutil.rmtree("tmp")


def update_all_template():
    download_templates()
    for root, dirs, files in os.walk('templates'):
        for file in files:
            if file.endswith('.yaml'):
                template_file = os.path.join(root, file)
                update_template(template_file)
    print('All templates updated')


if api_token and api_url:
    while True:

        # Check URL API
        try:
            data = '{"jsonrpc":"2.0","method":"apiinfo.version","params":{},"id":1}'
            header = {'Content-Type': 'application/json-rpc'}

            response_api = requests.post(api_url, data=data, headers=header)
            response_api.raise_for_status()

        except requests.exceptions.RequestException as e:
            print(f"Error API: {e}")
            break

        except Exception as e:
            print(f"Error: {e}")
            break

        # Check API Token
        try:
            data = '{"jsonrpc": "2.0","method": "token.get","params": {"output": "extend"},"id": 1}'
            header = {'Authorization': 'Bearer ' + api_token, 'Content-Type': 'application/json-rpc'}

            response_api = requests.post(api_url, data=data, headers=header)
            response_api = response_api.json()["result"]

            command = input("Command: ")

        except Exception:
            print("Error API: Correct your token")
            break

        # Commands
        if command == "help":
            print(tabulate(help_command, headers=["Command", "Description"], tablefmt="psql"))
            print("How to use: https://github.com/Udeus/Zabbix-Update-All-Templates")
        elif command == "templates":
            get_templates()
        elif command == "backup":
            create_one_backup()
        elif command == "backups":
            create_backups()
        elif command == "update templates":
            update_all_template()
        elif command == "author":
            print("Created by Andrzej Pietryga")
            print("Github: https://github.com/Udeus/")
        elif command == "exit":
            print("Closing the script...")
            break
        else:
            print("Command not found")
