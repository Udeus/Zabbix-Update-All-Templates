import json
import yaml
import os
from dotenv import load_dotenv

load_dotenv()


def get_config_value(env_var, arg_value=None, input_prompt=None):
    value = os.getenv(env_var)

    if value:
        return value.strip()

    if arg_value:
        return arg_value.strip()

    if input_prompt:
        return input(input_prompt).strip()

    raise ValueError(f"Configuration value for '{env_var}' is missing.")


def zabbix_url(url):
    if not url.endswith('/api_jsonrpc.php'):
        if not url.endswith('/'):
            url += '/'
        url += 'api_jsonrpc.php'
    if not url.startswith(('http://', 'https://')):
        url = f"https://{url}"
    return url


def get_file(filename):
    with open(filename, 'r', encoding='utf-8') as file:
        data = yaml.safe_load(file)
        data = json.dumps(data)
        data = json.dumps(data)
        return data
