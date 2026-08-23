# -*- coding: utf-8 -*-

# /// script
# requires-python = ">=3.14"
# dependencies = [
#     "requests>=2.32.3",
# ]
# ///

# -*- coding: utf-8 -*-

"""Načítání plných textů článků z URL (Phase 3 – rate limiting)."""

import configparser as _configparser
import datetime as _datetime
import os
import re
import requests
import time
import urllib.error
import urllib.request
from bs4 import BeautifulSoup
from urllib.parse import urlparse as _parse_url


from src.detect_paywall import check_paywall
from src.newton_one.data_io import nacti_csv, ulozit_jsonl


# Načtení konfigurace scraperu z config.ini (Phase 3 – rate limiting)
_scraper_config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "config.ini")
_cfg = _configparser.ConfigParser()
_cfg.read(_scraper_config_path)



def get_scraper_delay():
    """Vrátí prodlevu mezi pokusy o načtení článku (v sekundách)."""

    try:
        delay_str = _cfg.get("scraper", "delay")
        return int(delay_str)
    except (_configparser.NoSectionError, _configparser.NoOptionError):
        return 5


ENCODING_MAP: dict[str, str] = {
    "windows-1250": "cp1250",
    "latin-2": "iso-8859-2",
    "cp1250": "cp1250",
    "cp1252": "cp1252",
}


def get_article_encoding():
    """Vrátí default encoding článku z config.ini (fallback při absenci meta tagu)."""

    try:
        enc = _cfg.get("scraper", "article_encoding")
        return ENCODING_MAP.get(enc.lower(), enc)
    except (_configparser.NoSectionError, _configparser.NoOptionError):
        return "utf-8"  # výchozí fallback


# Singleton cache pro inicializaci modelů jednou (Phase 4 – optimalizace API volání)
from src.newton_one.models import ENCODING, JSONL_ENCODING, SLoupce
from src.newton_one.utils import is_valid_url


# HTML parsing (extract_title, extract_body_text) a _clean_text přes modulem
from src.scraper.html_parser import (_clean_text as html_clean_text,
                                     extract_body_text as _extract_body_text,
                                     extract_title as _extract_title,
                                     _remove_binary_garble)


# =============================================================================
# Funkce – načítání článku z URL
# =============================================================================


def nacit_artikl(url, timeout=30):
    """
    Načte plný text článku z dané URL.

    Parameters
    ----------
    url : str
        URL k článku (https://...).
    timeout : int
        Časový limit v sekundách pro HTTP požadavek (výchozí 30s).

    Vrací
    -----
    dict
        {'text': '<vyčistěný text článku>', 'title': '<název článku>'}
        Pokud je URL neplatná nebo se načtení nepodaří, vrátí prázdný dict.
    """

    if not url:
        return {}

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept-Language": "cs-CZ,cs;q=0.9,en;q=0.8",
    }

    # Cookie, která iDNES říká, že byl udělen souhlas
    cookies = {
        "dCMP": "mafra=1111,all=1,reklama=1,part=0,cpex=1,google=1,gemius=1,id5=1,nase=1111,groupm=1,piano=1,seznam=1,geozo=0,czaid=1,click=1,vendors=full,verze=2,",
        "adsCMP": "czaid=1,groupm=1,id5=1,gemius=1,seznam=1,cpex=1,piano=1,full=1,base=1,google=1,purposes=1,firstPurpose=1,publisher=1111"
    }

    response = None
    text = None
    title = None
    try:
        response = requests.get(url, headers=headers, cookies=cookies)
        response.raise_for_status()
    except requests.RequestException as exc:
        print(f"⚠️ Chyba načítání {url}: {exc}")
        return {"text": "", "title": "", "paywall": "ne"}

    # Detekce encodingu z meta tagu charset (nebo fallback)
    soup = BeautifulSoup(response.content, "html.parser")
    print(f"📝 Detekován encoding pro {url}: {soup.original_encoding}")
    html = str(soup)
    if soup.title:
        title = soup.title.string
    else:
        title = ""
    text = _extract_body_text(html) or ""

    # TODO asi nepotřebuji - otextovat
    # Detekce paywallu na základě HTML a zdrojového webu
    # parsed = _parse_url(url)
    # domain = parsed.netloc.lower().split(":")[0] if parsed.netloc else ""

    result = {"text": text, "title": title, "paywall": check_paywall(html, url)}

    # Validace: pokud je text krátký a vypadá jako binární data, vyhodíme ho

    print(f"✅ Načteno: {url[:80]}{'...' if len(url) > 80 else ''}")
    return result



def nacit_batch_artikul(items, timeout=30):
    """
    Načte plné texty článků z daného seznamu URL.

    Parameters
    ----------
    items : list[tuple[int, dict[str, str], str]]
        Seznam (index_1based, raw_radek, url) k článkům.
    timeout : int
        Časový limit v sekundách pro HTTP požadavek (výchozí 30s).

    Vrací
    -----
    list[dict]
        Výsledky odpovídající pořadí vstupních URL. Prázdný dict pro chybné URL.
    """
    results = []
    delay = get_scraper_delay()
    for i, (index_1based, raw_radek, url) in enumerate(items):
        vysledek = nacit_artikl(url, timeout=timeout)
        if vysledek:
            vysledek["index"] = index_1based  # 1-based index pro přiřazení zpět do CSV řádku
        results.append(vysledek)

        # Rate limiting – krátká prodleva mezi pokusy o načtení článku
        if delay > 0 and i < len(items) - 1:
            time.sleep(delay)

    print(f"\n✅ Batch načteno {len(results)} URL, úspěšně: {sum(1 for r in results if r.get('text'))}")
    return results


def nacti_z_ukazku_csv(cesta_csv):
    """
    Načte CSV soubor, extrahuje URL článků a pro každé platné URL načte plný text.

    Logika: jeden průchod daty – při čtení řádku se rozhodneme, zda jej scrapovat
    (pokud nemá Plné znění vyplněno). Načtené výsledky jsou později připojeny
    k odpovídajícímu řádku.

    Parameters
    ----------
    cesta_csv : str
        Cesta k vstupnímu CSV souboru.

    Vrací
    -----
    list[dict]
        Seznam přetvořených řádků se sloupci z CSV a případně s vyplněným
        'Plné znění' a 'Paywall'.
    """
    if not os.path.exists(cesta_csv):
        print(f"❌ Vstupní CSV soubor neexistuje: {cesta_csv}")
        exit()

    # Načíst raw řádky z CSV (pouze data, bez transformací)
    raw_radky = nacti_csv(cesta_csv)
    if not raw_radky:
        print("⚠️ Žádné řádky k zpracování.")
        return []

    # Připojit výsledky zpět do CSV dat – jeden průchod pro transformaci
    vysledky = []

    for raw_radek in raw_radky:
        vysledek = {}
        for sloupec in SLoupce:
            nazev = sloupec["nazev"]
            if nazev not in raw_radek:
                continue

            hodnota = raw_radek[nazev]

            if sloupec.get("strip_space"):
                hodnota = html_clean_text(hodnota)

            if not hodnota:
                hodnota = ""

            if nazev == "Datum publikování":
                date_str = hodnota.strip()
                for fmt in ("%Y-%m-%d", "%d.%m.%Y %H:%M"):
                    try:
                        hodnota = _datetime.datetime.strptime(date_str, fmt).strftime("%Y-%m-%d")
                        break
                    except ValueError:
                        continue

            if nazev == "Dosah" and sloupec.get("typ") == int:
                try:
                    hodnota = int(float(hodnota))
                except (ValueError, TypeError):
                    hodnota = ""

            vysledek[nazev] = hodnota

        # Přidat načtený text článku – pouze pokud byl řádek vyfiltrován k scrapování a úspěšně načeteno
        if raw_radek["Plné znění"] == "":
            t = nacit_artikl(raw_radek["Originální internetový zdroj"])
            vysledek["Plné znění"] = t["text"]
            vysledek["Paywall"] = t["paywall"]
        else:
            vysledek["Plné znění"] = raw_radek["Plné znění"]
            vysledek["Paywall"] = "ne"

        vysledky.append(vysledek)

    print(f"\n✅ Načteno z CSV {len(raw_radky)} řádků, článků načteno: {sum(1 for r in vysledky if r.get('Plné znění'))}")
    return vysledky
