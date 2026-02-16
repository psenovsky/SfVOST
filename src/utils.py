"""
Název: util.py
Popis: tento modul obsahuje společné funkce pro projekt.

Autor: Pavel Šenovský
Datum: 2025-08-11
"""

import configparser  # práce s konfiguračními soubory typu init
import json  # zpracování JSON souborů
import os
from datetime import datetime


def check_config_ini():
    """
    Provede kontrolu integrity konfiguračního souboru. Pokud je konfigurační soubor v pořádku vrátí jeho slovník.

    Returns
    -------
    conf
        zpracovaný konfigurační soubor ve formě slovníku
    """
    config = configparser.RawConfigParser()
    project_root = os.path.dirname(os.path.abspath(__file__))
    config_path = os.path.join(project_root, "..", "config.ini")
    if not os.path.exists("config.ini"):
        return "❌ konfigurační soubor: config.ini neexistuje"

    error = ""
    config.read(config_path)
    rk = ["historie_dni", "zpozdeni_mezi_dotazy"]
    error += check_config_section(config, "casove_limity", rk)
    rk = ["user", "password"]
    error += check_config_section(config, "BlueSky", rk)
    rk = ["version"]
    error += check_config_section(config, "general", rk)
    rk = ["model", "max_tokens", "temperature", "host", "port"]
    error += check_config_section(config, "LLM", rk)
    if error != "":
        return error

    return config


def check_config_section(config, section, keys):
    """
    Zkontroluje zda zadaná sekce a její povinné klíče existují v konfiguračním souboru.

    Parameters
    ----------
    config : configparser.RawConfigParser
        slovník s konfigurací, který se má zkontrolovat.
    section : str
        Jméno sekce, která se má zkontrolovat.
    keys : list of str
        Povinné klíče kontrolované sekce.
    config : dict
        konfigurační slovník.

    Returns
    -------
    error : str
        chybně definované klíče v konfiguračním souboru.
    """
    if section not in config:
        return f"❌ V konfiguračním souboru chybí [{section}]] sekce."
    missing_keys = [key for key in keys if key not in config[section]]
    if missing_keys:
        return f"❌ V konfikuračním souboru config.ini v sekci [{section}] chybí: {', '.join(missing_keys)}"
    return ""


def is_valid_date(date_string):
    """
    Zkontroluje, zda řetězec je datum ve formátu YYYY-MM-DD.

    Parameters
    ----------
    date_string : str
        řetězec, který se má zkontrolovat.

    Returns
    -------
    True pokud je formát data validní, jinak vrací false.
    """
    try:
        datetime.strptime(date_string, "%Y-%m-%d")
        return True
    except ValueError:
        return False


def uloz_json(cesta, data):
    """
    Uloží data do json souboru.

    Parameters
    ----------
    cesta : str
        cesta k souboru, do kterého se má data uložit.
    data : dict
        data, která se mají uložit.
    """
    with open(cesta, "w", encoding="utf-8") as f:
        for post in data:
            print(post)
            f.write(post.model_dump_json())
            f.write("\n")
    print(f"✅ ... uloženo do souboru {cesta}")
