# -*- coding: utf-8 -*-

"""Parsing HTML – extrakce titulků a textového obsahu z HTML článků."""

import re as _re


from src.newton_one.models import UNICODE_WHITESPACE


def _clean_text(text):
    """Odstraní Unicode whitespace z textu."""
    return "".join(ch for ch in text if ch not in UNICODE_WHITESPACE).strip()


def _decode_html_entities(text):
    """Dekoduje HTML entity reference (&#NNN; &#xHHH; &name;) na skutečné znaky."""
    import html as _html_module
    return _html_module.unescape(text)

 
def _remove_binary_garble(html):
    """Odstraní binární šum z HTML (neregulérné znaky s vysokým kódovým číslem)."""
    # Odstranit znaky mimo rozsah běžného textu (prostore + printable ASCII + Unicode)
    return _re.sub(r'[^\x20-\xff]', '', html)


def _strip_html(html):
    """Strhne HTML tags a vrátí čistý text."""
    # Odstranit attributes (např. <p class="..."> → <p>)
    html = _re.sub(r'<(/?[^>]+)\s+([^>]*)>', r'<\1', html)
    # Odstranit zbylé tags
    text = _re.sub(r'<[^>]+>', ' ', html)
    return _clean_text(text)


def extract_title(html_content):
    """Extrahuje title z HTML obsahu."""
    # Zkusit <title> tag
    match = _re.search(r'<title[^>]*>(.*?)</title>', html_content, _re.IGNORECASE | _re.DOTALL)
    if match:
        return _clean_text(match.group(1))

    # Fallback: meta description / og:title
    match = _re.search(r'<meta[^>]+property=["\']og:title["\'][^>]*content=["\']([^"\']+)["\']', html_content, _re.IGNORECASE)
    if match:
        return _clean_text(match.group(1))

    # Fallback: <h1> jako fallback
    match = _re.search(r'<h1[^>]*>(.*?)</h1>', html_content, _re.IGNORECASE | _re.DOTALL)
    if match:
        return _clean_text(match.group(1))

    return ""


def extract_body_text(html_content):
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
    html_content = _re.sub(r'<script[^>]*>.*?</script>', '', html_content, flags=_re.IGNORECASE | _re.DOTALL)
    html_content = _re.sub(r'<style[^>]*>.*?</style>', '', html_content, flags=_re.IGNORECASE | _re.DOTALL)

    # --- Strategie 0: JSON-LD structured data a itemprop (iDNES-style) ---
    # Hledat <div itemprop="articleBody"> nebo <div class="opener" itemprop="description">
    body_match = _re.search(r'<(?:div|section)[^>]*itemprop=["\'](?:articleBody|description)["\'][^>]*(?:[^<>]*){0,10}', html_content)
    if body_match:
        # Najít odpovídající closing tag
        open_tag = body_match.group(0)[:50]
        depth, end_pos = 0, -1
        for i in range(body_match.start(), len(html_content)):
            if html_content[i:i+4] == '</div>':
                depth -= 1
                if depth < 0:
                    end_pos = i + 6; break
            elif html_content[i:i+3] == '<li' and ' itemprop="articleBody"' in html_content[max(0, body_match.start()-5):i]:
                pass

        if end_pos > 0 and (end_pos - body_match.start()) > 100:
            section_text = html_content[body_match.start():end_pos]
            # Extrahovat text z speakable paragraphů
            paras = _re.findall(r'<p[^>]*>(.*?)</p>', section_text, _re.DOTALL)
            if paras:
                article_parts = []
                for sp in paras:
                    clean_p = _strip_html(sp).strip()
                    if len(clean_p) > 30 and not any(kw in clean_p.lower()[:80] for kw in ['reklama', 'souhlas']):
                        article_parts.append(clean_p)
                if article_parts:
                    combined = _strip_html(' '.join(article_parts))
                    combined = _re.sub(r'\s+', ' ', combined).strip()
                    combined = _re.sub(r'&[a-z]+;', ' ', combined)
                    if len(combined) > 100:
                        return combined

    # --- Strategie 0b: JSON-LD structured data (script type="application/ld+json") ---
    ld_match = _re.search(r'<script[^>]*type=["\']application/ld\+json["\'][^>]*(.*?)</script>', html_content, _re.DOTALL)
    if ld_match:
        try:
            import json as _json_mod
            data = _json_mod.loads(ld_match.group(1))
            # Hledat body.content nebo body.htmlContent
            for key in ['body', 'articleBody']:
                content_data = data.get(key, {})
                if isinstance(content_data, dict):
                    text = content_data.get('content', '') or content_data.get('htmlContent', '') or ''
                    if text and len(text) > 100:
                        # Vytvořit čistý text z JSON-LD (bez HTML entity jako &#225;)
                        clean_text = _strip_html(_re.sub(r'\s+', ' ', text)).strip()
                        if any(kw in clean_text.lower() for kw in ['tornádo', 'bouře', 'článok', 'news']):
                            return clean_text[:10000]  # Limit na délku
        except (json.JSONDecodeError, TypeError):
            pass

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
            match = _re.search(
                r'ogm-content__richContent[^"]*"[^>]*>(.*?)</div>',
                html_content[idx:], _re.IGNORECASE | _re.DOTALL
            )
            if match and match.end() > 0:
                section_extracted = html_content[match.start():idx + match.end()]

        # Extrahovat speakable paragraphy z ogm-content__richContent
        if section_extracted:
            speakable_paras = _re.findall(r'class="[^"]*speakable[^<]*>(.*?)</div>', section_extracted[:10000], _re.DOTALL)
        
            # Pokud nebyly nalezeny speakable paragraphy, zkusit všechny <p> v sekci
            if not speakable_paras:
                speakable_paras = _re.findall(r'<p[^>]*>(.*?)</p>', section_extracted, _re.DOTALL)
            
            article_text_parts = []
            for sp in speakable_paras:
                text_p = _strip_html(sp).strip()
                if len(text_p) > 30 and not any(kw in text_p.lower()[:80] for kw in ['reklama', 'souhlas']):
                    article_text_parts.append(text_p)
            
            if article_text_parts:
                combined = _strip_html(' '.join(article_text_parts))
                combined = _re.sub(r'\s+', ' ', combined).strip()
                combined = _re.sub(r'&[a-z]+;', ' ', combined)
                if len(combined) > 100:
                    return combined

    # --- Strategie 2: <article> tag ---
    match = _re.search(r'<article[^>]*>(.*?)</article>', html_content, _re.IGNORECASE | _re.DOTALL)
    if match:
        text = _strip_html(match.group(1))
        if len(text.strip()) > 100:
            return text.strip()

    # --- Strategie 3: <main> tag ---
    match = _re.search(r'<main[^>]*>(.*?)</main>', html_content, _re.IGNORECASE | _re.DOTALL)
    if match:
        text = _strip_html(match.group(1))
        if len(text.strip()) > 100:
            return text.strip()

    # --- Strategie 4: Filtr paragraphů (rozhlas-style) ---
    all_paras = _re.findall(r'<p[^>]*>(.*?)</p>', html_content, _re.DOTALL)
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
            link_word_count = len(_re.findall(r'[A-Z][a-záéíýůÁÉÍÝŮáéíýů]+(?:\s+[A-Z][a-záéíýůÁÉÍÝŮáéíýů]+)+', text_p.lower()))
            if link_word_count > 3 and len(text_p) < 500:
                # Mnoho krátkých slovní spojení = navigace
                continue
            
            # Zbývající <p> jsou article texty (musí mít minimální délku)
            if len(text_p) > 20:
                article_paras.append(text_p)
        
        combined = _strip_html(' '.join(article_paras))
        # Odstranit nadbytečné mezernaty a dekodovat HTML entity
        combined = _re.sub(r'\s+', ' ', combined).strip()
        combined = _decode_html_entities(combined)
        if len(combined) > 100:
            return combined

    # --- Strategie 5: Fallback – body text bez scripts/styles ---
    text = _strip_html(html_content)
    
    # Odfiltruj consent/nav content z fallback textu
    paragraphs = [p.strip() for p in _re.split(r'\s+', text) if len(p) > 20]
    if len(paragraphs) > 10:
        article_text = ' '.join(paragraphs[8:])
        article_text = _strip_html(article_text).strip()
        if len(article_text) > 100:
            return article_text
    
    # Fallback z OG description (pro paywalled stránky – iDNES, lidovky)
    desc_match = _re.search(
        r'property=["\']og:description["\'][^>]*content=["\']([^"\']+)["\']',
        html_content, _re.IGNORECASE
    )
    if desc_match:
        text = _strip_html(desc_match.group(1))
        # Dekodovat HTML entity (&#225; -> á) a odstranit nadbytečné mezernaty
        text = _decode_html_entities(text)
        text_clean = _re.sub(r'\s+', ' ', text).strip()
        if len(text_clean) > 50:
            return text_clean

    return ""


def is_readable_text(text):
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
