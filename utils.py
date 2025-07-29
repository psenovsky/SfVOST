"""
Název: sentiment.py
Popis: tento modul obsahuje společné funkkce pro projekt.

Autor: Pavel Šenovský
Verze: 0.1
Datum: 2025-06-25
"""

import configparser                                     # práce s konfiguračními soubory typu init
import os

def check_config_ini():
    """
    Provede kontrolu integrity konfiguračního souboru. Pokud je konfigurační soubor v pořádku vrátí jeho slovník.

    Returns
    -------
    conf
        zpracovaný konfigurační soubor ve formě slovníku
    """
    config = configparser.RawConfigParser()
    if not os.path.exists('config.ini'):
        print("❌ konfigurační soubor: config.ini neexistuje")
        exit()
    config.read('config.ini')
    rk = ['host', 'port', 'user', 'password', 'dbname', 'charset']
    check_config_section(config, 'database', rk)
    rk = ['historie_dni', 'zpozdeni_mezi_dotazy']
    check_config_section(config, 'casove_limity', rk)
    rk = ['user', 'password']
    check_config_section(config, 'BlueSky', rk)
    rk = ['version']
    check_config_section(config, 'general', rk)
    return config

def check_config_section(config, section, keys):
    """
    Zkontroluje zda zadaná sekce a její povinné klíče existují v konfiguračním souboru.

    Parameters
    ----------
    config :configparser.RawConfigParser
        slovník s konfigurací, který se má zkontrolovat.
    section : str
        Jméno sekce, která se má zkontrolovat.
    keys : list of str
        Povinné klíče kontrolované sekce.
    config : dict
        konfigurační slovník.

    Raises
    ------
    SystemExit
        Pokud sekce nebo jakákoliv její povinná čast nejsou v konfiguračním souboru přítomny.
    """
    if section not in config:
        print(f"❌ V konfiguračním souboru chybí [{section}]] sekce.")
        exit()
    missing_keys = [key for key in keys if key not in config[section]]
    if missing_keys:
        print(f"❌ V konfikuračním souboru config.ini v sekci [{section}] chybí: {', '.join(missing_keys)}")
        exit()
