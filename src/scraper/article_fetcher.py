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


# Singleton cache pro inicializaci modelů jednou (Phase 4 – optimalizace API volání)
from src.newton_one.models import ENCODING, JSONL_ENCODING, SLoupce, UNICODE_WHITESPACE
from src.newton_one.utils import parse_url, is_valid_url


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
            html_bytes = response.read()
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError) as exc:
        print(f"⚠️ Chyba načítání {url}: {exc}")
        return {}

    # Kontrola, zda HTML obsahuje příliš mnoho binárních dat (např. 404 body s binary)
    try:
        html_content = html_bytes.decode("utf-8", errors="replace")
    except UnicodeDecodeError:
        print(f"⚠️ Chyba UTF-8 dekodování pro {url}")
        return {}

    # Odstranit binární šum (neregulérné znaky s vysokým kódovým číslem)
    html_content = _remove_binary_garble(html_content)

    title = _extract_title(html_content) or ""
    text = _extract_body_text(html_content) or ""

    # Detekce paywallu na základě HTML a zdrojového webu
    from urllib.parse import urlparse as _parse_url
    parsed = _parse_url(url)
    domain = parsed.netloc.lower().split(":")[0] if parsed.netloc else ""
    
    result = {"text": _clean_text(text), "title": _clean_text(title), "paywall": check_paywall(html_content, url)}
    
    # Fallback: pokud se text nepodařilo extrahovat, použijeme og:description
    if not text.strip() and title:
        desc_match = re.search(
            r'property=["\']og:description["\'][^>]*content=["\']([^"\']+)["\']',
            html_content, re.IGNORECASE
        )
        if desc_match:
            result["text"] = _clean_text(desc_match.group(1))

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
    """Odstraní binární šum z HTML (neregulérné znaky s vysokým kódovým číslem)."""
    # Odstranit znaky mimo rozsah běžného textu (prostore + printable ASCII + Unicode)
    return re.sub(r'[^\x20-\xff]', '', html)


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
    delay = get_scraper_delay()
    for i, url in enumerate(urls):
        vysledek = nacit_artikl(url, timeout=timeout)
        if vysledek:
            vysledek["index"] = i + 1  # 1-based index pro přiřazení zpět do CSV řádku
        results.append(vysledek)

        # Rate limiting – krátká prodleva mezi pokusy o načtení článku
        if delay > 0 and i < len(urls) - 1:
            time.sleep(delay)

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

    Postup (v pořadí pokusů – fallback chain):
      1. Odstranit <script> a <style> tagy
      2. Zkusit novinky-style: extrahovat z divu s class 'g_fp g_bG ogm-content__richContent'
         (deeply nested article content section)
      3. Zkusit <article> tag
      4. Zkusit <main> tag
      5. Filtr paragraphů – pro stránky, kde je text v <p> tagách (rozhlas-style)
      6. Fallback: strhnout HTML tags a vrátit čistý text

    Vrací
    -----
    str
        Čistý text článku, nebo prázdný string pokud nelze extrahovat.
    """
    # Odstranit scripty a style tagy
    html_content = re.sub(r'<script[^>]*>.*?</script>', '', html_content, flags=re.IGNORECASE | re.DOTALL)
    html_content = re.sub(r'<style[^>]*>.*?</style>', '', html_content, flags=re.IGNORECASE | re.DOTALL)

    # --- Strategie 1: novinky-style – ogm-content__richContent div (speakable paragraphs) ---
    idx = html_content.find('class="g_fp g_bG')
    if idx > 0 and (idx + 6) < len(html_content):
        depth, end_pos = 0, -1
        for i in range(idx, len(html_content)):
            if html_content[i:i+4] == '</div>':
                depth -= 1
                if depth < 0:
                    end_pos = i + 6; break
        
        # Fallback: pokud hloubkové vyhledání selže (novinky-style s nested divy), zkusit regex
        section_extracted = None
        if end_pos > 0 and (end_pos - idx) > 500:
            section_extracted = html_content[idx:end_pos]
        
        # Fallback regex pro extrakci speakable paragraphů (jednoduchší pattern bez nested quotes)  
        if not section_extracted:
            match = re.search(
                r'ogm-content__richContent[^"]*"[^>]*>(.*?)</div>',
                html_content[idx:], re.IGNORECASE | re.DOTALL
            )
            if match and match.end() > 0:
                section_extracted = html_content[match.start():idx + match.end()]

        # Extrahovat speakable paragraphy z ogm-content__richContent
        if section_extracted:
            speakable_paras = re.findall(r'class="[^"]*speakable[^<]*>(.*?)</div>', section_extracted[:10000], re.DOTALL)
        
            # Pokud nebyly nalezeny speakable paragraphy, zkusit všechny <p> v sekci
            if not speakable_paras:
                speakable_paras = re.findall(r'<p[^>]*>(.*?)</p>', section_extracted, re.DOTALL)
            
            article_text_parts = []
            for sp in speakable_paras:
                text_p = _strip_html(sp).strip()
                if len(text_p) > 30 and not any(kw in text_p.lower()[:80] for kw in ['reklama', 'souhlas']):
                    article_text_parts.append(text_p)
            
            if article_text_parts:
                combined = _strip_html(' '.join(article_text_parts))
                combined = re.sub(r'\s+', ' ', combined).strip()
                combined = re.sub(r'&[a-z]+;', ' ', combined)
                if len(combined) > 100:
                    return combined

    # --- Strategie 2: <article> tag ---
    match = re.search(r'<article[^>]*>(.*?)</article>', html_content, re.IGNORECASE | re.DOTALL)
    if match:
        text = _strip_html(match.group(1))
        if len(text.strip()) > 100:
            return text.strip()

    # --- Strategie 3: <main> tag ---
    match = re.search(r'<main[^>]*>(.*?)</main>', html_content, re.IGNORECASE | re.DOTALL)
    if match:
        text = _strip_html(match.group(1))
        if len(text.strip()) > 100:
            return text.strip()

    # --- Strategie 4: Filtr paragraphů (rozhlas-style) ---
    all_paras = re.findall(r'<p[^>]*>(.*?)</p>', html_content, re.DOTALL)
    if len(all_paras) > 5:
        article_paras = []
        
        # Procházíme od začátku – pro rozhlas-style jsou article texty hned na začátku
        for idx_p, p in enumerate(all_paras[:12]):
            text_p = _strip_html(p).strip()
            
            if not text_p:
                continue
            
            first_word = text_p.split()[0].lower() if text_p.split() else ""
            skip_keywords_first = ['menu', 'hlavní menu', 'zavřít menu', 'souhlas', 'cookies']
            
            # Kontrola prvního slova – pokud odpovídá navigaci/consent, přeskočíme
            if any(kw in first_word for kw in skip_keywords_first):
                continue
            
            # Kontrola celého <p> na klíčová slova (pro consent texty)
            p_lower_full = html_content.lower()
            
            consent_nav_keywords = ['reklama', 'souhlas', 'cookies', 'banner', 'prihlasit']
            if any(kw in p_lower_full for kw in consent_nav_keywords):
                continue
            
            # Kontrola: zda obsah <p> vypadá jako navigace (mnoho odkazů)  
            # Pokud text obsahuje několik nav-liNK-like vzorců, je to pravděpodobně navigace
            link_word_count = len(re.findall(r'[A-Z][a-záéíýůÁÉÍÝŮáéíýů]+(?:\s+[A-Z][a-záéíýůÁÉÍÝŮáéíýů]+)+', text_p.lower()))
            if link_word_count > 3 and len(text_p) < 500:
                # Mnoho krátkých slovní spojení = navigace
                continue
            
            # Zbývající <p> jsou article texty (musí mít minimální délku)
            if len(text_p) > 20:
                article_paras.append(text_p)
        
        combined = _strip_html(' '.join(article_paras))
        # Odstranit nadbytečné mezernaty a HTML entity
        combined = re.sub(r'\s+', ' ', combined).strip()
        combined = re.sub(r'&[a-z]+;', ' ', combined)
        if len(combined) > 100:
            return combined

    # --- Strategie 5: Fallback – body text bez scripts/styles ---
    text = _strip_html(html_content)
    
    # Odfiltruj consent/nav content z fallback textu
    paragraphs = [p.strip() for p in re.split(r'\s+', text) if len(p) > 20]
    if len(paragraphs) > 10:
        article_text = ' '.join(paragraphs[8:])
        article_text = _strip_html(article_text).strip()
        if len(article_text) > 100:
            return article_text
    
    # Fallback z OG description (pro paywalled stránky – iDNES, lidovky)
    desc_match = re.search(
        r'property=["\']og:description["\'][^>]*content=["\']([^"\']+)["\']',
        html_content, re.IGNORECASE
    )
    if desc_match:
        text = _strip_html(desc_match.group(1))
        # Odfiltruj HTML entity pro lepší čitelnost  
        text_clean = re.sub(r'&[a-z]+;', ' ', text).strip()
        if len(text_clean) > 50:
            return text_clean

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

def _extrahovat_url_pro_naceni(raw_radek):
    """
    Vyberne URL pro načtení článku z CSV řádku.

    Priorita:
      1. 'Originální internetový zdroj' (externí URL článku)
      2. 'URL článku' (pouze pokud první není dostupné)

    Parameters
    ----------
    raw_radek : dict[str, str]
        Jeden řádek z CSV.

    Vrací
    -----
    str nebo None
        URL k článku, která je plně externí a přístupná HTTP požadavkem.
    """
    # Priorita 1: Originální internetový zdroj (externí odkaz na článek)
    url = raw_radek.get("Originální internetový zdroj", "").strip()
    if is_valid_url(url):
        return url

    # Fallback: URL článku (NewtonOne monitoring link – pro starší data)
    url = raw_radek.get("URL článku", "").strip()
    if is_valid_url(url):
        # NewtonOne internal links are not fetchable as articles
        # but we still validate them so the pipeline continues gracefully
        return url

    return None


def nacti_z_ukazku_csv(cesta_csv):
    """
    Načte CSV soubor, extrahuje URL článků a pro každé platné URL načte plný text.

    Parameters
    ----------
    cesta_csv : str
        Cesta k vstupnímu CSV souboru (musí obsahovat sloupec 'Originální internetový zdroj'
        nebo alespoň 'URL článku').

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

    urls = [_extrahovat_url_pro_naceni(r) for r in raw_radky]
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

        # Přidat detekci paywallu (True → "ano", False → "ne")
        if i < len(batch_results):
            vysledek["Paywall"] = "ano" if batch_results[i].get("paywall") else "ne"

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
