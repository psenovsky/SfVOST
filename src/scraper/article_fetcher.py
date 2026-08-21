# -*- coding: utf-8 -*-

"""Načítání plných textů článků z URL (Phase 2)."""

import json as _json
import os
import re
import urllib.error
import urllib.request


from src.newton_one.data_io import nacti_csv, ulozit_jsonl
from src.newton_one.models import ENCODING, JSONL_ENCODING, SLoupce, UNICODE_WHITESPACE


# =============================================================================
# Funkce – načítání článku z URL
# =============================================================================

def _clean_text(text):
    """Odstraní Unicode whitespace z textu."""
    return "".join(ch for ch in text if ch not in UNICODE_WHITESPACE).strip()


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
    if not url or not _clean_text(url):
        return {}

    try:
        req = urllib.request.Request(
            url, headers={"User-Agent": "Mozilla/5.0 (compatible; SfVOST-Scraper/1.0)"}
        )
        with urllib.request.urlopen(req, timeout=timeout) as response:
            html_content = response.read().decode("utf-8", errors="ignore")
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError) as exc:
        print(f"⚠️ Chyba načítání {url}: {exc}")
        return {}

    title = _extract_title(html_content) or ""
    text = _extract_body_text(html_content) or ""

    result = {"text": _clean_text(text), "title": _clean_text(title)}
    print(f"✅ Načteno: {url[:80]}{'...' if len(url) > 80 else ''}")
    return result


def nacit_batch_artikul(urls, timeout=30):
    """
    Načte plné texty článků z daného seznamu URL.

    Parameters
    ----------
    urls : list[str]
        Seznam URL k článkům.
    timeout : int
        Časový limit v sekundách pro HTTP požadavek (výchozí 30s).

    Vrací
    -----
    list[dict]
        Výsledky odpovídající pořadí vstupních URL. Prázdný dict pro chybné URL.
    """
    results = []
    for i, url in enumerate(urls):
        vysledek = nacit_artikl(url, timeout=timeout)
        if vysledek:
            vysledek["index"] = i + 1  # 1-based index pro přiřazení zpět do CSV řádku
        results.append(vysledek)

    print(f"\n✅ Batch načteno {len(results)} URL, úspěšně: {sum(1 for r in results if r.get('text'))}")
    return results


# =============================================================================
# Funkce – parsing HTML (základní extrakce textu)
# =============================================================================

def _extract_title(html_content):
    """Extrahuje title z HTML obsahu."""
    # Zkusit <title> tag
    match = re.search(r'<title[^>]*>(.*?)</title>', html_content, re.IGNORECASE | re.DOTALL)
    if match:
        return _clean_text(match.group(1))

    # Fallback: meta description / og:title
    match = re.search(r'<meta[^>]+property=["\']og:title["\'][^>]*content=["\']([^"\']+)["\']', html_content, re.IGNORECASE)
    if match:
        return _clean_text(match.group(1))

    # Fallback: <h1> jako fallback
    match = re.search(r'<h1[^>]*>(.*?)</h1>', html_content, re.IGNORECASE | re.DOTALL)
    if match:
        return _clean_text(match.group(1))

    return ""


def _extract_body_text(html_content):
    """
    Extrahuje hlavní textový obsah z HTML.

    Postup:
      1. Odstranit <script> a <style> tagy
      2. Zůstat s čistým HTML bez skriptů
      3. Získat první <main>, <article>, nebo <body> text
      4. Strhnout HTML tags a vrátit čistý text
    """
    # Odstranit scripty
    html_content = re.sub(r'<script[^>]*>.*?</script>', '', html_content, flags=re.IGNORECASE | re.DOTALL)
    # Odstranit style
    html_content = re.sub(r'<style[^>]*>.*?</style>', '', html_content, flags=re.IGNORECASE | re.DOTALL)

    # Zkusit <main> tag
    match = re.search(r'<main[^>]*>(.*?)</main>', html_content, re.IGNORECASE | re.DOTALL)
    if match:
        text = _strip_html(match.group(1))
        if text.strip():
            return text

    # Zkusit <article> tag
    match = re.search(r'<article[^>]*>(.*?)</article>', html_content, re.IGNORECASE | re.DOTALL)
    if match:
        text = _strip_html(match.group(1))
        if text.strip():
            return text

    # Zkusit <body> tag
    match = re.search(r'<body[^>]*>(.*?)</body>', html_content, re.IGNORECASE | re.DOTALL)
    if match:
        text = _strip_html(match.group(1))
        if text.strip():
            return text

    # Fallback: všechny text z HTML (bez scripts/styles)
    text = _strip_html(html_content)
    if text.strip():
        return text

    return ""


def _strip_html(html):
    """Strhne HTML tags a vrátí čistý text."""
    # Odstranit attributes (např. <p class="..."> → <p>)
    html = re.sub(r'<(/?[^>]+)\s+([^>]*)>', r'<\1', html)
    # Odstranit zbylé tags
    text = re.sub(r'<[^>]+>', ' ', html)
    return _clean_text(text)


# =============================================================================
# Funkce – načtení článků z CSV (Phase 2)
# =============================================================================

def nacti_z_ukazku_csv(cesta_csv):
    """
    Načte CSV soubor, extrahuje URL článku a pro každé platné URL načte plný text.

    Parameters
    ----------
    cesta_csv : str
        Cesta k vstupnímu CSV souboru (musí obsahovat sloupec 'URL článku').

    Vrací
    -----
    list[dict]
        Seznam přetvořených řádků s přidaným 'Plné znění' z načteného URL.
        Řádky bez platného URL se vrátí s prázdným textem.
    """
    if not os.path.exists(cesta_csv):
        print(f"❌ Vstupní CSV soubor neexistuje: {cesta_csv}")
        return []

    # Načíst raw řádky z CSV (pouze data, bez transformací)
    raw_radky = nacti_csv(cesta_csv)
    if not raw_radky:
        print("⚠️ Žádné řádky k zpracování.")
        return []

    urls = [r.get("URL článku", "") for r in raw_radky]
    batch_results = nacit_batch_artikul(urls)

    # Připojit výsledky zpět do CSV dat
    vysledky = []
    for i, raw_radek in enumerate(raw_radky):
        vysledek = {}
        for sloupec in SLoupce:
            nazev = sloupec["nazev"]
            hodnota = raw_radek.get(nazev, "")

            if sloupec.get("strip_space"):
                hodnota = _clean_text(hodnota)

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

        # Přidat načtený text článku
        if i < len(batch_results) and batch_results[i].get("text"):
            vysledek["Plné znění"] = batch_results[i]["text"]
        else:
            vysledek["Plné znění"] = ""

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
