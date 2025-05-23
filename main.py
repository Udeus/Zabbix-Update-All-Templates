import argparse
import json
import logging
import re
import os
import shutil
import urllib.request
from zipfile import ZipFile
from time import strftime

import requests
from tabulate import tabulate

from utils import zabbix_url, get_file, get_config_value, get_next_backup_id


COMMANDS_LIST = [["help", "Show all commands"],
                 ["template list", "Show all templates and ID"],
                 ["template update", "Update one template"],
                 ["template update all", "Update all templates"],
                 ["backup create", "Create backup of one template"],
                 ["backup create all", "Create backup of all templates"],
                 ["backup list", "Show list of all backups"],
                 ["backup restore", "Restore selected backup"],
                 ["backup delete", "Delete selected backup"],
                 ["about", "About script"],
                 ["exit", "Close script"]]

SCRIPT_INFO = [["Version", "1.0"], ["Author", "Andrzej Pietryga"], ["Contact", "https://github.com/Udeus"],
               ["License", "GPL-3.0"], ["Repository", "https://github.com/Udeus/Zabbix-Update-All-Templates"]]

parser = argparse.ArgumentParser(description="Zabbix Update all templates | More info: https://github.com/Udeus/Zabbix-Update-All-Templates")
parser.add_argument("--url", type=str, help="Zabbix url address")
parser.add_argument("--token", type=str, help="API token")
parser.add_argument("--update", action="store_true", help="Update all templates")
parser.add_argument("--no-verify", action="store_true", help="Turn off verify SSL")
args = parser.parse_args()

logging.basicConfig(filename='actions.log', format="[%(asctime)s]%(message)s", datefmt="%Y-%m-%d %H:%M", level=logging.INFO, encoding='utf-8')

verify_ssl = not args.no_verify
zabbix_version = None

if not verify_ssl:
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

try:
    terminal_width = os.get_terminal_size().columns
except OSError:
    terminal_width = 80


api_url = zabbix_url(
    get_config_value(
        env_var='ZABBIX_URL',
        arg_value=args.url,
        input_prompt="Zabbix url address: "
    )
)


api_token = get_config_value(
    env_var='ZABBIX_API_TOKEN',
    arg_value=args.token,
    input_prompt="Zabbix API token: "
)


def connect_api(api_date, api_header=False):
    if zabbix_version == '6.0':
        api_header = {'Content-Type': 'application/json-rpc'}
        api_date = json.loads(api_date)
        api_date['auth'] = api_token
        api_date = json.dumps(api_date)
    elif not api_header and zabbix_version != '6.0':
        api_header = {'Authorization': 'Bearer ' + api_token, 'Content-Type': 'application/json-rpc'}

    response = requests.post(api_url, data=api_date, headers=api_header, verify=verify_ssl)

    try:
        response = response.json()['result']
    except KeyError as e:
        logging.error(f"Unexpected error: {e}")
        response = response.json()['error']
        print(f'API error: {response}')

    return response


try:
    data = '{"jsonrpc":"2.0","method":"apiinfo.version","params":{},"id":1}'
    header = {'Content-Type': 'application/json-rpc'}

    zabbix_version = connect_api(data, header)
    zabbix_version = re.search("^([0-9].[0-9])", zabbix_version).group(0)

except requests.exceptions.SSLError as e:
    logging.error(f"Unexpected error: {e}")
    print(f"Error SSL: {e}")
    quit()

except requests.exceptions.RequestException as e:
    logging.error(f"Unexpected error: {e}")
    print(f"Error API: {e}")
    quit()

except Exception as e:
    logging.error(f"Unexpected error: {e}")
    print(f"Error: {e}")
    quit()


# Check API Token
try:
    data = '{"jsonrpc": "2.0","method": "token.get","params": {"output": "extend"},"id": 1}'
    header = {'Authorization': 'Bearer ' + api_token, 'Content-Type': 'application/json-rpc'}

    connect_api(data, header)

except Exception:
    logging.error("Error API: Correct your token")
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

    backup_id = get_next_backup_id()
    date_create = strftime("%d.%m.%Y")
    time_create = strftime("%H.%M")
    backup_path = f"backups/{backup_id}-{date_create}-{time_create}"
    os.makedirs(backup_path, exist_ok=True)

    with open(f'backups/{backup_id}-{date_create}-{time_create}/{template_name}.yaml', 'w', encoding='utf-8') as f:
        f.write(response)

    logging.info(f'[BACKUP] Backup {template_name} template created')

    print(f"Backup template {template_name} created")


def create_backups():
    api_date = '{"jsonrpc": "2.0","method": "template.get","params": {"output": ["name", "groupid"]},"id": 1}'
    resp_template_list = connect_api(api_date)

    template_number = 1
    list_length = len(resp_template_list)

    backup_id = get_next_backup_id()
    date_create = strftime("%d.%m.%Y")
    time_create = strftime("%H.%M")
    backup_path = f"backups/{backup_id}-{date_create}-{time_create}"
    os.makedirs(backup_path, exist_ok=True)

    for item in resp_template_list:
        template_id = item['templateid']
        template_name = item['name']

        api_date = f'{{"jsonrpc": "2.0","method": "configuration.export","params": {{"options": {{"templates": ["{template_id}"]}},"format": "yaml"}},"id": 1}}'
        response = connect_api(api_date)

        print(f'{template_number}/{list_length}')
        template_number += 1

        with open(f'backups/{backup_id}-{date_create}-{time_create}/{template_name}.yaml', 'w', encoding='utf-8') as f:
            f.write(response)

    logging.info(f'[BACKUP] All backups created')
    print('All backups created')


def list_backups():
    if not os.path.exists("backups"):
        print("No backups found")
        return

    backups_list = []
    for backup_dir in sorted(os.listdir("backups")):
        backup_path = os.path.join("backups", backup_dir)
        if os.path.isdir(backup_path):
            try:
                id_date_time = backup_dir.split('-')
                if len(id_date_time) == 3:
                    backup_id = id_date_time[0]
                    date = id_date_time[1]
                    time = id_date_time[2]

                    templates_count = len([f for f in os.listdir(backup_path) if f.endswith('.yaml')])
                    backups_list.append([backup_id, date, time, templates_count])
            except:
                continue

    if not backups_list:
        print("No backups found")
    else:
        print(tabulate(backups_list, headers=["ID", "Date", "Time", "Templates count"], tablefmt="psql"))


def delete_backup():
    list_backups()

    backup_id = input("Enter backup ID to delete: ")

    backup_to_delete = None
    for backup_dir in os.listdir("backups"):
        if backup_dir.startswith(f"{backup_id}-"):
            backup_to_delete = backup_dir
            break

    if backup_to_delete is None:
        print(f"Backup with ID {backup_id} not found. Use 'backup list' to see available backups.")
        return

    confirmation = input(f"Are you sure you want to delete backup {backup_to_delete}? (yes/no): ").strip().lower()

    if confirmation.lower() == 'yes':
        try:
            backup_path = os.path.join("backups", backup_to_delete)
            shutil.rmtree(backup_path)
            print(f"Backup {backup_to_delete} has been deleted")
            logging.info(f'[BACKUP] Deleted backup {backup_to_delete}')
        except Exception as e:
            print(f"Error occurred while deleting backup: {e}")
            logging.error(f'[BACKUP] Error deleting backup {backup_to_delete}: {e}')
    else:
        print("Backup deletion cancelled")


def restore_backup():
    list_backups()

    backup_id = input("Enter backup ID to restore: ")

    backup_to_restore = None
    for backup_dir in os.listdir("backups"):
        if backup_dir.startswith(f"{backup_id}-"):
            backup_to_restore = backup_dir
            break

    if backup_to_restore is None:
        print(f"Backup with ID {backup_id} not found. Use 'backup list' to see available backups.")
        return

    backup_path = os.path.join("backups", backup_to_restore)
    if not os.path.exists(backup_path):
        print(f"Backup directory does not exist: {backup_path}")
        return

    confirmation = input(f"Are you sure you want to restore backup {backup_to_restore}? (yes/no): ").strip().lower()

    if confirmation.lower() == 'yes':
        try:
            for file in os.listdir(backup_path):
                if file.endswith('.yaml'):
                    template_file = os.path.join(backup_path, file)
                    update_template(template_file)
                    print(f"Restored template: {file}")

            print(f"Successfully restored backup {backup_to_restore}")
            logging.info(f'[BACKUP] Restored backup {backup_to_restore}')
        except Exception as e:
            print(f"Error occurred while restoring backup: {e}")
            logging.error(f'[BACKUP] Error restoring backup {backup_to_restore}: {e}')
    else:
        print("Backup restoration cancelled")


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

    with ZipFile(name_zip_file, 'r') as zip_ref:
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
                    logging.error(f"Unexpected error: {e}")
                    print(f"Error file {file_path}: {e}")

    logging.info(f'[TEMPLATE] Updated template {template_name}')
    print(f'Updated template {template_name}')


def help_command():
    print(tabulate(COMMANDS_LIST, headers=["Command", "Description"], tablefmt="psql"))
    print("How to use: https://github.com/Udeus/Zabbix-Update-All-Templates")


def print_about():
    print(tabulate(SCRIPT_INFO, tablefmt="psql"))


def exit_script():
    print("Closing the script...")
    if os.path.exists("templates"):
        shutil.rmtree("templates")
    quit()


commands = {'help': help_command,
            'template list': get_templates,
            'template update': update_one_template,
            'template update all': update_all_template,
            'backup create': create_one_backup,
            'backup create all': create_backups,
            'backup list': list_backups,
            'backup restore': restore_backup,
            'backup delete': delete_backup,
            'about': print_about,
            'exit': exit_script}


def execute_command():
    command = input("Command: ").strip().lower()
    action = commands.get(command)
    if action:
        action()
    else:
        print("Command not found. Type 'help' to see available commands.")


if api_token and api_url:
    download_templates()
    help_command()

    if args.update:
        update_all_template()
        quit()
    while True:
        execute_command()
