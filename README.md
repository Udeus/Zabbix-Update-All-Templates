# Zabbix-Update-All-Templates


[![](https://img.shields.io/badge/View-My_Profile-green?logo=GitHub)](https://github.com/Udeus)
[![](https://img.shields.io/badge/View-My_Repositories-blue?logo=GitHub)](https://github.com/Udeus?tab=repositories)
![](https://img.shields.io/github/license/udeus/zabbix-import-hosts)

Update all Zabbix templates

## Requirments
- Python 3.x + pip
- Zabbix server


## Install
`
pip install -r requirements.txt
`


## Usage
Run script:
`
python main.py --url <zabbix_address_url> --token <zabbix_api_token>
`

Example:
`
python main.py --url http://192.168.1.105 --token d36cab4cb00097b11bb97739828aed93ec521858de3e007a2d91a2047ff5a72d
`

#### or
`
python main.py
`
next type url and token api

## Commands

| Command          | Description                 |
|------------------|-----------------------------|
| help             | Show all commands           |
| templates        | Show all templates and ID   |
| backup           | Create backup one template  |
| backups          | Create backup all templates |
| update templates | Update all templates        |
| exit             | Close script                |

### License

License: https://github.com/Udeus/Zabbix-Update-All-Templates?tab=GPL-3.0-1-ov-file