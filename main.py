import os
import argparse
import shutil
import urllib.request
import requests
import zipfile
import re
import json
import logging
import config
from time import strftime
from tabulate import tabulate
from utils import zabbix_url, get_file


list_commands = [["help", "Show all commands"], ["templates", "Show all templates and ID"],
                 ["backup", "Create backup one template"], ["backups", "Create backup all templates"],
                 ["update templates", "Update all templates"], ["update template", "Update one template"],
                 ["author", "About author"], ["exit", "Close script"]]

parser = argparse.ArgumentParser(description="Zabbix Update all templates | More info: https://github.com/Udeus/Zabbix-Update-All-Templates")
parser.add_argument("--url", type=str, help="Zabbix url address")
parser.add_argument("--token", type=str, help="API token")
parser.add_argument("--update", action="store_true", help="Update all templates")
parser.add_argument("--no-verify", action="store_true", help="Turn off verify SSL")
args = parser.parse_args()

logging.basicConfig(filename='actions.log', format="[%(asctime)s]%(message)s", datefmt="%Y-%m-%d %H:%M", level=logging.INFO)

verify_ssl = not args.no_verify
zabbix_version = None

if not verify_ssl:
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

try:
    terminal_width = os.get_terminal_size().columns
except OSError:
    terminal_width = 80

if config.zabbix_url:
    api_url = zabbix_url(config.zabbix_url)
elif args.url:
    api_url = zabbix_url(args.url)
else:
    api_url = zabbix_url(input("Zabbix url address: "))

if config.zabbix_api_token:
    api_token = config.zabbix_api_token
elif args.token:
    api_token = args.token
else:
    api_token = input("Zabbix API token: ")


def connect_api(api_date, api_header=False):
    if zabbix_version == '6.0':
        api_header = {'Content-Type': 'application/json-rpc'}
        api_date = json.loads(api_date)
        api_date['auth'] = api_token
        api_date = json.dumps(api_date)
    elif not api_header and not zabbix_version == '6.0':
        api_header = {'Authorization': 'Bearer ' + api_token, 'Content-Type': 'application/json-rpc'}

    response = requests.post(api_url, data=api_date, headers=api_header, verify=verify_ssl)

    try:
        response = response.json()['result']
    except KeyError:
        response = response.json()['error']
        print(f'API error: {response}')

    return response


try:
    data = '{"jsonrpc":"2.0","method":"apiinfo.version","params":{},"id":1}'
    header = {'Content-Type': 'application/json-rpc'}

    zabbix_version = connect_api(data, header)
    zabbix_version = re.search("^([0-9].[0-9])", zabbix_version).group(0)

except requests.exceptions.SSLError as e:
    print(f"Error SSL: {e}")
    quit()

except requests.exceptions.RequestException as e:
    print(f"Error API: {e}")
    quit()

except Exception as e:
    print(f"Error: {e}")
    quit()


# Check API Token
try:
    data = '{"jsonrpc": "2.0","method": "token.get","params": {"output": "extend"},"id": 1}'
    header = {'Authorization': 'Bearer ' + api_token, 'Content-Type': 'application/json-rpc'}

    connect_api(data, header)

except Exception:
    print("Error API: Correct your token")
    quit()


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

    logging.info(f'[BACKUP] Backup {template_name} template created')

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

    logging.info(f'[BACKUP] All backups created')
    print('All backups created')


def update_template(filename):
    print(f'Update: {filename}')
    data_file = get_file(filename)
    api_date = f'{{"jsonrpc": "2.0","method": "configuration.import","params": {{"format": "json","rules": {{"templates": {{"createMissing": true,"updateExisting": true}},"items": {{"createMissing": true,"updateExisting": true,"deleteMissing": true}},"triggers": {{"createMissing": true,"updateExisting": true,"deleteMissing": true}},"valueMaps": {{"createMissing": true,"updateExisting": false}}}},"source": {data_file} }},"id": 1}}'
    connect_api(api_date)


def download_templates():
    print(f'Downloading all templates for Zabbix')

    repo_url = f'https://git.zabbix.com/rest/api/latest/projects/ZBX/repos/zabbix/archive?at=refs%2Fheads%2Frelease%2F{zabbix_version}&format=zip'

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
    for root, dirs, files in os.walk('templates'):
        for file in files:
            if file.endswith('.yaml'):
                template_file = os.path.join(root, file)
                update_template(template_file)

    logging.info(f'[TEMPLATE] Updated all templates')
    print('All templates updated')


def update_one_template():
    template_name = input("Template Name: ")
    full_template_name = f'name: \'{template_name}\''

    for root, dirs, files in os.walk('templates'):
        for file in files:
            if file.endswith('.yaml'):
                file_path = os.path.join(root, file)
                try:
                    with open(file_path, 'r', encoding='utf-8') as file:
                        content = file.read()
                        if full_template_name in content:
                            update_template(file_path)
                except Exception as e:
                    print(f"Error file {file_path}: {e}")

    logging.info(f'[TEMPLATE] Updated template {template_name}')
    print(f'Updated template {template_name}')


def help_command():
    print(tabulate(list_commands, headers=["Command", "Description"], tablefmt="psql"))
    print("How to use: https://github.com/Udeus/Zabbix-Update-All-Templates")


def author_script():
    print("Created by Andrzej Pietryga")
    print("Github: https://github.com/Udeus/")


def exit_script():
    print("Closing the script...")
    shutil.rmtree("templates")
    quit()


commands = {'help': help_command,
            'templates': get_templates,
            'backup': create_one_backup,
            'backups': create_backups,
            'update templates': update_all_template,
            'update template': update_one_template,
            'author': author_script,
            'exit': exit_script}


def excute_command():
    command = input("Command: ")
    action = commands.get(command)
    if action:
        action()
    else:
        print("Command not found")


if api_token and api_url:
    download_templates()
    help_command()

    if args.update:
        update_all_template()
        quit()
    while True:
        excute_command()
