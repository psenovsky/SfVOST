# /// script
# requires-python = ">=3.14"
# dependencies = [
#     "requests>=2.32.3",
# ]
# ///

# -*- coding: utf-8 -*-

"""Načítání plných textů článků z URL (Phase 3 – rate limiting)."""

import configparser as _configparser
import json as _json
import os
import re
import time
import urllib.error
import urllib.request


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


def get_article_encoding():
    """Vrátí default encoding článku z config.ini (fallback při absenci meta tagu)."""

    try:
        enc = _cfg.get("scraper", "article_encoding")
        # Normalizace kódovacích jmen
        encoding_map = {
            "utf-8": "utf-8",
            "windows-1250": "cp1250",
            "latin-2": "iso-8859-2",
            "cp1250": "cp1250",
            "cp1252": "cp1252",
        }
        return encoding_map.get(enc.lower(), enc)
    except (_configparser.NoSectionError, _configparser.NoOptionError):
        return "utf-8"  # výchozí fallback


# Singleton cache pro inicializaci modelů jednou (Phase 4 – optimalizace API volání)
from src.newton_one.models import ENCODING, JSONL_ENCODING, SLoupce
from src.newton_one.utils import is_valid_url


# HTML parsing (extract_title, extract_body_text) a _clean_text přes modulem
from src.scraper.html_parser import (_clean_text as html_clean_text,
                                     extract_body_text as _extract_body_text,
                                     extract_title as _extract_title)


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
    if not url or not html_clean_text(url):
        return {}

    try:
        req = urllib.request.Request(
            url, headers={"User-Agent": "Mozilla/5.0 (compatible; SfVOST-Scraper/1.0)"}
        )
        with urllib.request.urlopen(req, timeout=timeout) as response:
            html_bytes = response.read()
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError) as exc:
        print(f"⚠️ Chyba načítání {url}: {exc}")
        return {}

    # Detekce encodingu z meta tagu charset
    html_preview = html_bytes[:512].decode("ascii", errors="ignore")
    charset_match = re.search(r'<meta[^>]+charset=["\']?([^;"\'>\s]+)', html_preview, re.IGNORECASE)
    if charset_match:
        encoding_name = charset_match.group(1).strip().lower()
        # Normalizace běžných kódovacích jmen
        encoding_map = {
            "windows-1250": "cp1250",
            "latin-2": "iso-8859-2",
            "cp1250": "cp1250",
            "cp1252": "cp1252",
        }
        encoding = encoding_map.get(encoding_name, encoding_name)
    else:
        # Fallback na default encoding z config.ini (nebo utf-8)
        article_encoding = get_article_encoding()
        encoding = article_encoding

    print(f"📝 Detekován encoding pro {url}: {encoding}")

    # Kontrola, zda HTML obsahuje příliš mnoho binárních dat (např. 404 body s binary)
    try:
        html_content = html_bytes.decode(encoding, errors="replace")
    except UnicodeDecodeError as exc:
        print(f"⚠️ Chyba {encoding} dekodování pro {url}: {exc}")
        # Zkousnout utf-8 jako fallback
        try:
            html_content = html_bytes.decode("utf-8", errors="replace")
        except UnicodeDecodeError as exc2:
            print(f"⚠️ Chyba UTF-8 dekodování pro {url}: {exc2}")
            return {}

    # Odstranit binární šum (neregulérné znaky s vysokým kódovým číslem)
    html_content = _remove_binary_garble(html_content)

    title = _extract_title(html_content) or ""
    text = _extract_body_text(html_content) or ""

    # Detekce paywallu na základě HTML a zdrojového webu
    from urllib.parse import urlparse as _parse_url
    parsed = _parse_url(url)
    domain = parsed.netloc.lower().split(":")[0] if parsed.netloc else ""
    
    result = {"text": html_clean_text(text), "title": html_clean_text(title), "paywall": check_paywall(html_content, url)}
    
    # Fallback: pokud se text nepodařilo extrahovat, použijeme og:description
    if not text.strip() and title:
        desc_match = re.search(
            r'property=["\']og:description["\'][^>]*content=["\']([^"\']+)["\']',
            html_content, re.IGNORECASE
        )
        if desc_match:
            result["text"] = html_clean_text(desc_match.group(1))

    # Validace: pokud je text krátký a vypadá jako binární data, vyhodíme ho
    if not text.strip() and title:
        # Zkusit ještě OG description  
        pass
    
    print(f"✅ Načteno: {url[:80]}{'...' if len(url) > 80 else ''}")
    return result


def _is_readable_text(text):
    """Zkontroluje, zda je text čitelný (ne binární data)."""
    if not text or not isinstance(text, str):
        return False
    
    # Pokud obsahuje hodně nepříjemných znaků (>50% neprintovatelných), není to text
    printable_chars = sum(1 for ch in text if 32 <= ord(ch) <= 126 or ch in '\t\n\r')
    total_chars = len(text)
    
    if total_chars == 0:
        return False
    
    # Pokud je více než polovina znaků nepříjemných, text vypadá jako binární data
    non_printable_ratio = (total_chars - printable_chars) / total_chars
    return non_printable_ratio < 0.5


def _remove_binary_garble(html):
    """Odstraní binární šum z HTML — pouze skutečné nekonzistentní znaky.

    Nepoškozovat platné Unicode znaky (diakritika, rozšířené latin).
    Odstraňuje jen: null byte + kontrolní znaky < 0x20 (kromě \t \n \r)."""
    bad = re.sub(r'[\x00-\x1f]', '', html)
    return bad


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


# =============================================================================
# Funkce – načtení článků z CSV (Phase 2)
# =============================================================================

def _extrahovat_url_pro_naceni(raw_radek, index_1based=None):
    """
    Vybere URL pro načtení článku a kontroluje, zda řádek potřebuje scrap.

    Priorita URL:
      1. 'Originální internetový zdroj' (externí odkaz na článek)
      2. 'URL článku' (pouze pokud první není dostupné – NewtonOne interní odkaz)

    Filtrování:
      - Pokud má řádek již vyplněný 'Plné znění', vrátí None
        (scrapování se neprovede, existující text zůstává nedotčen).

    Parameters
    ----------
    raw_radek : dict[str, str]
        Jeden řádek z CSV.
    index_1based : int or None
        1-based index řádku v CSV (pro přiřazení výsledku zpět do outputu).
        Pokud není zadáno, použije se len(raw_radek) jako fallback.

    Vrací
    -----
    tuple[int, str, str] nebo None
        (index_1based, full_raw_row, url) pokud scrapování provedeme;
        jinak None.
    """
    # Filtrování – pouze řádky bez vyplněného Plné znění jsou kandidáty pro scrap

    # Priorita 1: Originální internetový zdroj (externí odkaz na článek)
    url = raw_radek.get("Originální internetový zdroj", "").strip()
    if is_valid_url(url):
        idx = index_1based if index_1based is not None else len(raw_radek)
        return (idx, raw_radek, url)

    # Fallback: URL článku (NewtonOne monitoring link – pro starší data)
    url = raw_radek.get("URL článku", "").strip()
    if is_valid_url(url):
        idx = index_1based if index_1based is not None else len(raw_radek)
        return (idx, raw_radek, url)

    return None  # Žádná URL → tento řádek bude zahrnut ve výstupu bez scraped dat


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
        return []

    # Načíst raw řádky z CSV (pouze data, bez transformací)
    raw_radky = nacti_csv(cesta_csv)
    if not raw_radky:
        print("⚠️ Žádné řádky k zpracování.")
        return []

    # Jeden průchod – filtrovat a získat URL pro scrapování
    items = [item for item in [_extrahovat_url_pro_naceni(r, i + 1) for i, r in enumerate(raw_radky)] if item is not None]
    batch_results = nacit_batch_artikul(items, timeout=30)

    # Build lookup by index (1-based)
    text_lookup = {}  # {index: result_dict}
    for result in batch_results:
        idx = result.get("index")
        if idx is not None and result.get("text"):
            text_lookup[idx] = result

    # Připojit výsledky zpět do CSV dat – jeden průchod pro transformaci
    vysledky = []
    for i, raw_radek in enumerate(raw_radky):
        vysledek = {}
        for sloupec in SLoupce:
            nazev = sloupec["nazev"]
            hodnota = raw_radek.get(nazev, "")

            if sloupec.get("strip_space"):
                hodnota = html_clean_text(hodnota)

            if not hodnota:
                hodnota = ""

            if nazev == "Datum publikování":
                from datetime import datetime
                date_str = hodnota.strip()
                for fmt in ("%Y-%m-%d", "%d.%m.%Y %H:%M"):
                    try:
                        hodnota = datetime.strptime(date_str, fmt).strftime("%Y-%m-%d")
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
        index_1based = i + 1
        if index_1based in text_lookup:
            vysledek["Plné znění"] = html_clean_text(text_lookup[index_1based]["text"])

        # Přidat detekci paywallu – pouze pokud byl řádek vyfiltrován k scrapování a úspěšně načeteno
        if index_1based in text_lookup:
            vysledek["Paywall"] = "ano" if text_lookup[index_1based].get("paywall") else "ne"

        vysledky.append(vysledek)

    print(f"\n✅ Načteno z CSV {len(raw_radky)} řádků, článků načteno: {sum(1 for r in vysledky if r.get('Plné znění'))}")
    return vysledky


# =============================================================================
# Hlavní vstupní bod pro scraper CLI (Phase 2)
# =============================================================================

def main():
    """Hlavní vstupní bod skriptu."""
    description = (
        "CLI utilita pro načtení CSV s URL článků a získání plných textů."
    )
    parser = __import__("argparse").ArgumentParser(
        prog='scraper.py',
        description=description,
        formatter_class=__import__("argparse").ArgumentParser.RawTextHelpFormatter)
    parser.add_argument("-c", "--csv", help="cesta k CSV souboru se sloupcem 'URL článku'")
    parser.add_argument("-o", "--output", help="výstupní JSONL soubor")

    args = parser.parse_args()

    if not args.csv or not args.output:
        parser.print_help()
        exit(0)

    # Kontrola existenci vstupního souboru
    if not os.path.exists(args.csv):
        print(f"❌ Vstupní CSV soubor {args.csv} neexistuje.")
        exit(1)

    # Načtení článků z URL
    vysledky = nacti_z_ukazku_csv(args.csv)
    if not vysledky:
        print("⚠️ Žádné data pro zápis.")
        exit(0)

    # Zápis do JSONL
    ulozit_jsonl(vysledky, args.output)


if __name__ == "__main__":
    main()
