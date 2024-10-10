import json
import yaml


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
