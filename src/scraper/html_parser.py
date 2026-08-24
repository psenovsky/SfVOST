# -*- coding: utf-8 -*-

"""Parsing HTML – extrakce titulků a textového obsahu z HTML článků."""

import bs4 as _bs4
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
    """Odstraní binární šum z HTML (kontrolní znaky < 0x20, kromě \t\n\r)."""
    return _re.sub(r'[\x00-\x1f]', '', html)




def extract_title(html_content):
    """Extrahuje title z HTML obsahu."""
    # Zkusit <title> tag
    soup = _bs4.BeautifulSoup(html_content, "html.parser")
    title_tag = soup.find("title")
    if title_tag and title_tag.string:
        return _clean_text(title_tag.string)

    # Fallback: meta og:title
    meta = soup.find("meta", attrs={"property": lambda v: v == "og:title"}) or \
           soup.find("meta", property="og:title")
    if meta and meta.get("content"):
        return _clean_text(meta["content"])

    # Fallback: <h1> jako fallback
    h1 = soup.find("h1")
    if h1 and h1.string:
        return _clean_text(h1.string)

    return ""


def extract_body_text(html_content):
    """
    Extrahuje hlavní textový obsah z HTML.

    Postup (v pořadí pokusů – fallback chain):
      1. Odstranit <script> a <style> tagy
      2. Zkusit itemprop (articleBody, description)
      3. Zkusit JSON-LD structured data
      4. Zkusit novinky-style: ogm-content__richContent div
      5. Zkusit <article> tag
      6. Zkusit <main> tag
      7. Filtr paragraphů – pro stránky, kde je text v <p> tagách (rozhlas-style)
      8. Fallback: strhnout HTML tags a vrátit čistý text

    Vrací
    -----
    str
        Čistý text článku, nebo prázdný string pokud nelze extrahovat.
    """
    soup = _bs4.BeautifulSoup(html_content, "html.parser")
    # DEBUG vypsání HTML stránky
    # print(str(soup))
    # exit() #DEBUG

    # iDnes.cz, lidovky.cz
    # meta_tag = soup.find("meta", attrs={"property": "og:site_name", "content": "iDNES.cz"})
    # meta_tag = soup.find("meta", attrs={"property": "og:site_name", "content": "Lidovky.cz"})
    meta_tag = soup.find("meta", property="og:site_name")
    site_name = ""
    if meta_tag:
        site_name = meta_tag.get("content")

    if site_name == "iDNES.cz" or site_name == "Lidovky.cz":
        desc = soup.select_one('div.opener[itemprop="description"]')
        body = soup.select_one('div[itemprop="articleBody"]')
        desc_text = desc.get_text(strip=True)
        body_text = body.get_text(strip=True)
        # print(desc_text, body_text)  # DEBUG
        return f"{desc_text}\n\n{body_text}"

    # český rozhlas (plus.rozhlas.cz)
    # meta_tag = soup.find("meta", attrs={"property": "og:site_name", "content": "Plus"})
    if site_name == "Plus":
        desc = soup.select_one('div.field.field-perex')
        body = soup.select_one('div.field.body')
        desc_text = desc.get_text(strip=True)
        body_text = body.get_text(strip=True)
        # print(desc_text, body_text)  # DEBUG
        return f"{desc_text}\n\n{body_text}"

    # denník.cz
    if site_name == "www.denik.cz":
        desc = soup.select_one('p.text-xl.js-article-perex.scroll-mt-24')
        body = soup.select_one('div.article-body-blocks.js-article-perex')
        desc_text = desc.get_text(strip=True)
        body_text = body.get_text(strip=True)
        # print(desc_text, body_text)  # DEBUG
        return f"{desc_text}\n\n{body_text}"

    # eurozpravy.cz
    if site_name == "EuroZprávy.cz":
        body = soup.select('div.b-article-body__text.u-last-m0')
        body_text = ""
        for b in body:
            body_text += f"{b.get_text(strip=True)}\n"

        return body_text

    # parlamentnílisty.cz
    if site_name == "parlamentnilisty.cz":
        desc = soup.select_one('p.brief')
        body = soup.select_one('div.article-container')
        desc_text = desc.get_text(strip=True)
        body_text = body.get_text(strip=True)
        # print(desc_text, body_text)  # DEBUG
        return f"{desc_text}\n\n{body_text}"

    # Odstranit scripty a style tagy
    for tag in list(soup.find_all(["script", "style"])):
        tag.decompose()

    # TODO po otestování smazat
    # --- Strategie 0: itemprop (iDNES-style) ---
    #for elem in soup.select('[itemprop="articleBody"], [itemprop="description"]'):
    #    text = _clean_text(elem.get_text())
    #    if len(text.strip()) > 100:
    #        return text

    # --- Strategie 0b: JSON-LD structured data (script type="application/ld+json") ---
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            import json as _json_mod
            data = _json_mod.loads(script.string or "")
            for key in ['body', 'articleBody']:
                content_data = data.get(key, {})
                if isinstance(content_data, dict):
                    text = content_data.get('content', '') or content_data.get('htmlContent', '') or ''
                    if text and len(text) > 100:
                        clean_text = _re.sub(r'\s+', ' ', text).strip()
                        return clean_text[:10000]
        except (json.JSONDecodeError, TypeError):
            pass

    # --- Strategie 1: novinky-style – ogm-content__richContent div ---
    rich = soup.select('.g_fp.g_bG') or list(soup.find_all(class_=lambda c: 'ogm' in str(c) if isinstance(c, str) else False))[:1]
    if not rich:
        for el in soup.find_all(attrs={"class": lambda c: "ogm-content__richContent" in str(c)}):
            rich = [el]
            break

    if rich and len(rich[0].get_text()) > 500:
        section = rich[0].get_text()
        speakable_paras = soup.select('.speakable') or list(rich[0].find_all("p"))
        article_text_parts = []
        for sp in speakable_paras:
            text_p = _clean_text(sp.get_text()).strip()
            if len(text_p) > 30 and not any(kw in text_p.lower()[:80] for kw in ['reklama', 'souhlas']):
                article_text_parts.append(text_p)

        if article_text_parts:
            combined = _clean_text(' '.join(article_text_parts))
            combined = _re.sub(r'\s+', ' ', combined).strip()
            combined = _re.sub(r'&[a-z]+;', ' ', combined)
            if len(combined) > 100:
                return combined

    # --- Strategie 2: <article> tag ---
    article_tag = soup.find("article")
    if article_tag and len(article_tag.get_text(strip=True)) > 100:
        text = _clean_text(article_tag.get_text())
        text = _re.sub(r'\s+', ' ', text).strip()
        return text

    # --- Strategie 3: <main> tag ---
    main_tag = soup.find("main")
    if main_tag and len(main_tag.get_text(strip=True)) > 100:
        text = _clean_text(main_tag.get_text())
        text = _re.sub(r'\s+', ' ', text).strip()
        return text

    # --- Strategie 4: Filtr paragraphů (rozhlas-style) ---
    all_paras = soup.find_all("p")
    if len(all_paras) > 5:
        article_paras = []

        for p in all_paras[:12]:
            text_p = _clean_text(p.get_text()).strip()

            if not text_p:
                continue

            first_word = text_p.split()[0].lower() if text_p.split() else ""
            skip_keywords_first = ['menu', 'hlavní menu', 'zavřít menu', 'souhlas', 'cookies']

            # Kontrola prvního slova – pokud odpovídá navigaci/consent, přeskočíme
            if any(kw in first_word for kw in skip_keywords_first):
                continue

            p_lower_full = html_content.lower()

            consent_nav_keywords = ['reklama', 'souhlas', 'cookies', 'banner', 'prihlasit']
            if any(kw in p_lower_full for kw in consent_nav_keywords):
                continue

            # Kontrola: zda obsah <p> vypadá jako navigace (mnoho odkazů)
            link_word_count = len(_re.findall(r'[A-Z][a-záéíýůÁÉÍÝŮáéíýů]+(?:\s+[A-Z][a-záéíýůÁÉÍÝŮáéíýů]+)+', text_p.lower()))
            if link_word_count > 3 and len(text_p) < 500:
                continue

            # Zbývající <p> jsou article texty (musí mít minimální délku)
            if len(text_p) > 20:
                article_paras.append(text_p)

        combined = _clean_text(' '.join(article_paras))
        combined = _re.sub(r'\s+', ' ', combined).strip()
        combined = _decode_html_entities(combined)
        if len(combined) > 100:
            return combined

    # --- Strategie 5: Fallback – body text bez scripts/styles ---
    text = soup.get_text()

    paragraphs = [p.strip() for p in text.split() if len(p) > 20]
    if len(paragraphs) > 10:
        article_text = ' '.join(paragraphs[8:])
        if len(article_text) > 100:
            return _clean_text(article_text)

    # Fallback z OG description (pro paywalled stránky – iDNES, lidovky)
    desc_meta = soup.find("meta", attrs={"property": lambda v: v == "og:description"}) or \
               soup.find("meta", property="og:description")
    if desc_meta and desc_meta.get("content"):
        text = _clean_text(desc_meta["content"])
        text = _decode_html_entities(text)
        text_clean = _re.sub(r'\s+', ' ', text).strip()
        if len(text_clean) > 50:
            return text_clean

    # Poslední fallback: čistý text bez filtru (pro very short articles)
    if soup.get_text(strip=True):
        return _clean_text(soup.get_text())

    return ""
