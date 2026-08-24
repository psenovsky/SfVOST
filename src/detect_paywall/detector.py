# -*- coding: utf-8 -*-

"""Hlavní logika detektoru paywall."""

import json as _json
import os
import re
from bs4 import BeautifulSoup
from urllib.parse import urlparse as _parse_url


def check_paywall(html: str, source_url: str) -> bool:
    """Zkontroluje, zda je stránka paywalled.

    Postup (fallback chain):
      1. Načte pravidla pro zdroj z rules.json podle URL
      2. Pro každý zdroj: kontrola metatagů (regex matching)
      3. Fallback: analyza poměru textu k obrázkům na stránce

    Parameters
    ----------
    html : str
        HTML obsah stránky.
    source_url : str
        URL zdroje článku (např. 'zpravy.iDNES.cz', 'lidesnema.cz').

    Vrací
    -----
    bool
        True pokud detekuje paywall, False jinak.

    Examples
    --------
    >>> check_paywall('<html>...<meta name="cXenseParse:qiw-content" content="premium">...</html>', 'zpravy.iDNES.cz')
    True
    """
    if not html or not source_url:
        return False

    soup = BeautifulSoup(html, "html.parser")
    # iDnes, ?Lidovky
    meta_tag = soup.find("meta", attrs={"name": "cXenseParse:qiw-content", "content": "premium"})
    if meta_tag:
        return True

    # parlamentnilisty.cz
    subscription_box = soup.find("div", class_="article-subscription-box")
    if subscription_box:
        return True

    return False

    # TODO předělat
    # Extrahovat zdroj z URL (např. https://zpravy.iDNES.cz/... -> zpravy.iDNES.cz)
    # domain = _extract_domain(source_url)
    # if not domain:
    #     return False

    # # Načíst pravidla pro tento zdroj
    # rules = get_rules(domain)
    # if not rules:
    #     return _fallback_check(html, source_url)

    # # Kontrola metatagů podle pravidel tohoto zdroje
    # for meta_rule in rules.get("meta_tags", []):
    #     if _check_meta_tag(html, meta_rule):
    #         return True

    # # Fallback: pokud žádná pravidla neposkytla jasný výsledek
    # fallback = rules.get("fallback")
    # if fallback is not None and _fallback_check(html, source_url):
    #     return True

    # return False


def _extract_domain(url: str) -> str:
    """Extrahuje doménu z URL (např. https://zpravy.iDNES.cz/... -> zpravy.iDNES.cz)."""
    if not url or "://" not in url:
        return ""

    try:
        parsed = _parse_url(url)
        domain = parsed.netloc.lower()
        # Odstranit port pokud existuje
        domain = domain.split(":")[0]
        return domain
    except Exception:
        return ""


def _check_meta_tag(html: str, rule: dict) -> bool:
    """Kontrola jednoho metatagu podle pravidla.

    Parameters
    ----------
    html : str
        HTML obsah stránky.
    rule : dict
        Pravidlo pro detekci metatagů. Musí obsahovat 'name' a 'value_contains'.

        Optional fields:
        - content_type: 'meta_refresh' (pro robots meta-refresh)
        - contains_url_pattern: regex pattern pro kontrolu obsahu

    Vrací
    -----
    bool
        True pokud pravidlo splněno, False jinak.
    """
    name = rule.get("name", "")

    # Provede se kontrola metatagů podle jejich typu
    if "meta_refresh" in rule.get("content_type", ""):
        return _check_meta_refresh(html, name, rule)
    elif "value_contains" in rule:
        return _check_meta_value_contains(html, name, rule)
    else:
        # Default kontrola metatagů podle názvu a hodnoty
        if not name:
            return False

        match = re.search(
            rf'<meta[^>]*name=["\']?{re.escape(name)}["\']?[^>]*content=["\']([^"\']+?)["\']',
            html, re.IGNORECASE | re.DOTALL
        )

        if not match:
            return False

        content = match.group(1)

        # Kontrola podle pravidel
        for key in ["value_contains", "content_type"]:
            if key in rule and rule[key]:
                if rule[key] in content.lower():
                    return True

        return False


def _check_meta_value_contains(html: str, name: str, rule: dict) -> bool:
    """Kontrola metatagů podle názvu a hodnoty."""
    match = re.search(
        rf'<meta[^>]*name=["\']?{re.escape(name)}["\']?[^>]*content=["\']([^"\']+?)["\']',
        html, re.IGNORECASE | re.DOTALL
    )

    if not match:
        return False

    content = match.group(1)

    # Kontrola podle pravidel
    for key in ["value_contains", "content_type"]:
        value_to_find = rule.get(key, None)
        if value_to_find and value_to_find in content.lower():
            return True

    return False


def _check_meta_refresh(html: str, name: str, rule: dict) -> bool:
    """Kontrola metatagů pro robots meta-refresh."""
    match = re.search(
        rf'<meta[^>]*name=["\']?{re.escape(name)}["\']?[^>]*content=["\']([^"\']+?)["\']',
        html, re.IGNORECASE | re.DOTALL
    )

    if not match:
        return False

    content = match.group(1)

    # Kontrola URL pattern v obsahu meta-refresh
    url_pattern = rule.get("contains_url_pattern", "")
    if url_pattern and re.search(url_pattern, content):
        return True

    return False


def _fallback_check(html: str, source_url: str) -> bool:
    """Fallback: analyza poměru textu k obrázkům na stránce.

    Pokud je méně než 70% obsahu text (podle poměru textových elementů k celkovému obsahu),
    předpokládáme paywall.

    Parameters
    ----------
    html : str
        HTML obsah stránky.
    source_url : str
        URL zdroje článku.

    Vrací
    -----
    bool
        True pokud detekuje paywall, False jinak.
    """
    if not html:
        return False

    # Odstranit skripty a styly pro lepší analýzu
    clean_html = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.IGNORECASE | re.DOTALL)
    clean_html = re.sub(r'<style[^>]*>.*?</style>', '', clean_html, flags=re.IGNORECASE | re.DOTALL)

    # Odhadnout poměr textu k obrázkům
    text_count = len(re.findall(r'<p[^>]*>|<span[^>]*>|<div[^>]*>|<section[^>]*>', clean_html))
    img_count = len(re.findall(r'<img[^>]+src=', html, re.IGNORECASE))

    # Celkový počet elementů na stránce (text + obrázky)
    total_elements = text_count + img_count

    if total_elements == 0:
        return False

    # Pokud je méně než 70% obsahu text (podle poměru textových elementů k celkovému obsahu),
    # předpokládáme paywall
    text_ratio = text_count / total_elements

    min_ratio = _get_min_text_ratio()

    return text_ratio < min_ratio


def _get_min_text_ratio() -> float:
    """Vrátí minimální poměr textu k celkovému obsahu pro detekci paywall."""
    try:
        rules_path = os.path.join(os.path.dirname(__file__), "rules.json")
        with open(rules_path, "r", encoding="utf-8") as f:
            data = _json.load(f)

        defaults = data.get("defaults", {})
        return defaults.get("min_text_ratio_for_paywall", 0.3)
    except Exception:
        return 0.3


# =============================================================================
# Funkce – načtení pravidel pro zdroj (rozšiřitelnost!)
# =============================================================================

def get_rules(domain: str) -> dict:
    """Načte pravidla pro daný zdroj z rules.json.

    Parameters
    ----------
    domain : str
        Doména zdroje (např. 'zpravy.iDNES.cz', 'lidesnema.cz').

    Vrací
    -----
    dict nebo None
        Pravidla pro daný zdroj, nebo None pokud pravidla neexistují.

    Examples
    --------
    >>> get_rules('zpravy.iDNES.cz')
    {'meta_tags': [...], 'fallback': ...}

    Notes
    -----
    Pro přidání nového zdroje: přidejte jeho pravidla do src/detect_paywall/rules.json
    """
    if not domain:
        return None

    # Normalizace domény na malá písmena pro case-insensitive matching
    domain_lower = domain.lower()

    try:
        rules_path = os.path.join(os.path.dirname(__file__), "rules.json")

        # Kontrola zda soubor existuje (pro případ, že se pravidla ještě nevytvořila)
        if not os.path.exists(rules_path):
            return None

        with open(rules_path, "r", encoding="utf-8") as f:
            data = _json.load(f)

        sources = data.get("sources", {})
        # Normalizace klíčů na malá písmena pro case-insensitive matching s doménou ze URL
        sources_lower = {k.lower(): v for k, v in sources.items()}

        # Hledat přesně podle domény nebo prefix (např. 'www.zpravy.iDNES.cz' -> 'zpravy.iDNES.cz')
        exact_match = sources_lower.get(domain_lower, None)
        if exact_match:
            return exact_match

        # Fallback: hledat prefix (např. 'zpravy.iDNES.cz' -> 'www.zpravy.iDNES.cz' nebo naopak)
        for source_domain in sources_lower.keys():
            if domain_lower == source_domain or domain_lower.startswith(source_domain + ".") or \
               source_domain.startswith(domain_lower + "."):
                return sources_lower[source_domain]

        # Zkusit najít pravidla podle části domény (např. 'iDNES.cz' -> 'zpravy.iDNES.cz')
        parts = domain_lower.split(".")
        for i in range(len(parts) - 1, -1, -1):
            partial_domain = ".".join(parts[i:])
            if partial_domain in sources_lower:
                return sources_lower[partial_domain]

        # Pokud nic nevyšlo, zkusit hledat podle nejdelší části domény (např. 'zpravy.iDNES.cz' -> 'iDNES.cz')
        for source_domain in sources_lower.keys():
            if domain_lower.endswith("." + source_domain) or domain_lower == source_domain:
                return sources_lower[source_domain]
        return None

    except Exception as e:
        print(f"⚠️ Chyba při načítání pravidel pro zdroj {domain}: {e}")
        return None
