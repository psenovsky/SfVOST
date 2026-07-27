"""
Název: models.py
Popis: Pydantic modely pro strukturované zpracování příspěvků ze sociálních sítí.

Tento modul definuje hierarchii tříd pro reprezentaci příspěvků ze sítě BlueSky
a výsledků analytických nástrojů (NER, sentiment, dezinformace).

Autor: Pavel Šenovský
Datum: 2026-07-27
"""

import json
from typing import Any, Optional
from pydantic import BaseModel, ConfigDict, Field


# =============================================================================
# Modely pro BlueSky příspěvky
# =============================================================================

class ViewerState(BaseModel):
    """Stav diváka (viewer state) pro profil uživatele."""
    model_config = ConfigDict(extra='allow')

    blocked_by: bool = False
    blocking: Optional[str] = None
    blocking_by_list: Optional[str] = None
    followed_by: Optional[str] = None
    following: Optional[str] = None
    known_followers: Optional[str] = None
    muted: bool = False
    muted_by_list: Optional[str] = None
    py_type: str = "app.bsky.actor.defs#viewerState"


class ProfileViewer(BaseModel):
    """Stav diváka pro příspěvek."""
    model_config = ConfigDict(extra='allow')

    embedding_disabled: bool = False
    like: Optional[str] = None
    pinned: Optional[str] = None
    reply_disabled: Optional[str] = None
    repost: Optional[str] = None
    thread_muted: bool = False
    py_type: str = "app.bsky.feed.defs#viewerState"


class Label(BaseModel):
    """Štítek (label) připojený k příspěvku nebo profilu."""
    model_config = ConfigDict(extra='allow')

    cts: Optional[str] = None
    src: Optional[str] = None
    uri: Optional[str] = None
    val: Optional[str] = None
    cid: Optional[str] = None
    exp: Optional[str] = None
    neg: Optional[str] = None
    sig: Optional[str] = None
    ver: Optional[str] = None
    py_type: str = "com.atproto.label.defs#label"


class ProfileAssociatedChat(BaseModel):
    """Asociovaný chat profilu."""
    model_config = ConfigDict(extra='allow')

    allow_incoming: str = "following"
    py_type: str = "app.bsky.actor.defs#profileAssociatedChat"


class ProfileAssociated(BaseModel):
    """Asociované prvky profilu."""
    model_config = ConfigDict(extra='allow')

    chat: Optional[ProfileAssociatedChat] = None
    feedgens: Optional[str] = None
    labeler: Optional[str] = None
    lists: Optional[str] = None
    starter_packs: Optional[str] = None
    py_type: str = "app.bsky.actor.defs#profileAssociated"


class Author(BaseModel):
    """Autor příspěvku (profileViewBasic)."""
    model_config = ConfigDict(extra='allow')

    did: str
    handle: str
    associated: Optional[ProfileAssociated] = None
    avatar: Optional[str] = None
    created_at: Optional[str] = None
    display_name: Optional[str] = None
    labels: list[Label] = []
    verification: Optional[str] = None
    viewer: Optional[ViewerState] = None
    py_type: str = "app.bsky.actor.defs#profileViewBasic"


class ReplyRef(BaseModel):
    """Reference na odpověď (reply reference)."""
    model_config = ConfigDict(extra='allow')

    cid: str
    uri: str
    py_type: str = "com.atproto.repo.strongRef"


class Reply(BaseModel):
    """Informace o odpovědi v příspěvku."""
    model_config = ConfigDict(extra='allow')

    parent: Optional[ReplyRef] = None
    root: Optional[ReplyRef] = None
    py_type: str = "app.bsky.feed.post#replyRef"


class BlobRef(BaseModel):
    """Reference na blob (soubor)."""
    model_config = ConfigDict(extra='allow')

    mime_type: str
    size: int
    ref: Optional[Any] = None
    py_type: str = "blob"


class ExternalEmbed(BaseModel):
    """Vložený externí odkaz."""
    model_config = ConfigDict(extra='allow')

    description: Optional[str] = None
    title: Optional[str] = None
    uri: str
    thumb: Optional[Any] = None  # může být BlobRef nebo URL string
    py_type: str = "app.bsky.embed.external#external"


class ExternalEmbedView(BaseModel):
    """Pohled na vložený externí odkaz."""
    model_config = ConfigDict(extra='allow')

    external: ExternalEmbed
    py_type: str = "app.bsky.embed.external"


class Image(BaseModel):
    """Obrázek v příspěvku."""
    model_config = ConfigDict(extra='allow')

    alt: str = ""
    image: Optional[BlobRef] = None
    py_type: str = "app.bsky.embed.images#image"


class ImagesEmbed(BaseModel):
    """Vložené obrázky."""
    model_config = ConfigDict(extra='allow')

    images: list[Image] = []
    py_type: str = "app.bsky.embed.images"


class ImagesEmbedView(BaseModel):
    """Pohled na vložené obrázky."""
    model_config = ConfigDict(extra='allow')

    images: list[Image] = []
    py_type: str = "app.bsky.embed.images#view"


class RecordEmbedView(BaseModel):
    """Pohled na vložený záznam."""
    model_config = ConfigDict(extra='allow')

    cid: str
    uri: str
    py_type: str = "com.atproto.repo.strongRef"


class RecordWithMediaView(BaseModel):
    """Pohled na záznam s médií."""
    model_config = ConfigDict(extra='allow')

    external: Optional[ExternalEmbedView] = None
    images: Optional[ImagesEmbedView] = None
    py_type: str = "app.bsky.embed.recordWithMedia#view"


class RecordView(BaseModel):
    """Pohled na vložený záznam (příspěvek)."""
    model_config = ConfigDict(extra='allow')

    record: Optional[str] = None
    py_type: str = "app.bsky.embed.record#viewRecord"


class EmbedView(BaseModel):
    """Pohled na vložený obsah."""
    model_config = ConfigDict(extra='allow')

    record: Optional[RecordView] = None
    record_with_media: Optional[RecordWithMediaView] = None
    external: Optional[ExternalEmbedView] = None
    images: Optional[ImagesEmbedView] = None
    py_type: str = "app.bsky.embed.record#view"


class FacetFeature(BaseModel):
    """Funkce facetu (tag nebo odkaz)."""
    model_config = ConfigDict(extra='allow')

    tag: Optional[str] = None
    uri: Optional[str] = None
    py_type: str = "app.bsky.richtext.facet#tag"


class FacetIndex(BaseModel):
    """Index facetu v textu."""
    model_config = ConfigDict(extra='allow')

    byte_end: int
    byte_start: int
    py_type: str = "app.bsky.richtext.facet#byteSlice"


class Facet(BaseModel):
    """Facet (formátování textu, tag, odkaz)."""
    model_config = ConfigDict(extra='allow')

    features: list[FacetFeature] = []
    index: Optional[FacetIndex] = None
    py_type: str = "app.bsky.richtext.facet"


class Record(BaseModel):
    """Záznam příspěvku (record)."""
    model_config = ConfigDict(extra='allow')

    created_at: str
    text: str
    embed: Optional[dict] = None
    entities: Optional[list] = None
    facets: Optional[list[Facet]] = None
    labels: Optional[list[Label]] = None
    langs: list[str] = []
    reply: Optional[Reply] = None
    tags: Optional[list[str]] = None
    py_type: str = "app.bsky.feed.post"


class Threadgate(BaseModel):
    """Brána vlákna (threadgate)."""
    model_config = ConfigDict(extra='allow')

    py_type: str = "app.bsky.feed.threadgate"


class Post(BaseModel):
    """
    Kompletní příspěvek ze sítě BlueSky (postView).

    Tento model umožňuje přidávat další pole (extra='allow') pro výsledky
    analytických nástrojů (NER, sentiment, dezinformace, překlad).
    """
    model_config = ConfigDict(extra='allow')

    author: Author
    cid: str
    indexed_at: str
    record: Record
    uri: str
    embed: Optional[dict] = None
    labels: list[Label] = []
    like_count: int = 0
    quote_count: int = 0
    reply_count: int = 0
    repost_count: int = 0
    threadgate: Optional[Threadgate] = None
    viewer: Optional[ProfileViewer] = None
    py_type: str = "app.bsky.feed.defs#postView"


# =============================================================================
# Modely pro výsledky analytických nástrojů
# =============================================================================

class NerVysledky(BaseModel):
    """Výsledky analýzy pojmenovaných entit (NER)."""
    per: list[str] = Field(default=[], description="Seznam osob (Person)")
    org: list[str] = Field(default=[], description="Seznam organizací (Organization)")
    loc: list[str] = Field(default=[], description="Seznam lokalit (Location)")
    gpe: list[str] = Field(default=[], description="Seznam geopolitických entit (GPE)")
    date: list[str] = Field(default=[], description="Seznam dat")
    fac: list[str] = Field(default=[], description="Seznam zařízení/staveb (Facility)")


class SentimentVysledky(BaseModel):
    """Výsledky analýzy sentimentu."""
    kategorie: str = Field(description="Kategorie sentimentu: pozitivní, neutrální, negativní")
    skore: Optional[float] = Field(default=None, description="Skore sentimentu (0-1)")


class DezinformaceVysledky(BaseModel):
    """Výsledky analýzy dezinformací."""
    label: str = Field(description="Označení: fake news, reliable news")
    skore: Optional[float] = Field(default=None, description="Skore spolehlivosti (0-1)")


# =============================================================================
# Pomocné funkce pro práci s JSONL
# =============================================================================

def nacti_prispevky_z_jsonl(cesta: str) -> list[Post]:
    """
    Načte příspěvky ze souboru JSONL.

    Parametry:
    ----------
    cesta : str
        Cesta k souboru JSONL s příspěvky.

    Vrací:
    ------
    list[Post]
        Seznam načtených příspěvků.
    """
    prispevky = []
    with open(cesta, "r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            try:
                data = json.loads(line)
                prispevky.append(Post(**data))
            except Exception as e:
                print(f"❌ Chyba při načítání příspěvku: {e}")
                continue
    return prispevky


def uloz_prispevky_do_jsonl(prispevky: list[Post], cesta: str) -> None:
    """
    Uloží příspěvky do souboru JSONL.

    Parametry:
    ----------
    prispevky : list[Post]
        Seznam příspěvků k uložení.
    cesta : str
        Cesta k výstupnímu souboru JSONL.
    """
    with open(cesta, "w", encoding="utf-8") as f:
        for post in prispevky:
            f.write(post.model_dump_json())
            f.write("\n")
    print(f"✅ ... uloženo {len(prispevky)} příspěvků do souboru {cesta}")


# =============================================================================
# Pomocné funkce pro práci s Apache Arrow / Parquet
# =============================================================================

def prispevky_na_flat_row(post: Post) -> dict:
    """
    Převede instanci Post na plochý slovník vhodný pro řádek Parquet tabulky.

    Komplexní zanořené struktury (NER, facets, embed) jsou serializovány jako JSON string.
    Analytické výsledky (sentiment, dezinformace) jsou rozloženy do samostatných sloupců.

    Parametry:
    ----------
    post : Post
        Instance příspěvku ze sítě BlueSky.

    Vrací:
    ------
    dict
        Plochý slovník s daty příspěvku.
    """
    sentiment = getattr(post, 'sentiment', None)
    dezinformace = getattr(post, 'dezinformace', None)
    ner = getattr(post, 'ner', None)

    row = {
        "uri": post.uri,
        "cid": post.cid,
        "indexed_at": post.indexed_at,
        "record_created_at": post.record.created_at,
        "record_text": post.record.text,
        "record_lang": post.record.langs[0] if post.record.langs else None,
        "author_handle": post.author.handle,
        "author_did": post.author.did,
        "author_display_name": post.author.display_name,
        "like_count": post.like_count,
        "quote_count": post.quote_count,
        "reply_count": post.reply_count,
        "repost_count": post.repost_count,
        "sentiment_kategorie": sentiment.get("sentiment") if isinstance(sentiment, dict) else None,
        "sentiment_skore": sentiment.get("score") if isinstance(sentiment, dict) else None,
        "dezinformace_label": dezinformace.get("label") if isinstance(dezinformace, dict) else None,
        "dezinformace_skore": dezinformace.get("score") if isinstance(dezinformace, dict) else None,
        "ner": json.dumps(ner, ensure_ascii=False) if ner else None,
        "record_facets": json.dumps([f.model_dump() for f in post.record.facets], ensure_ascii=False) if post.record.facets else None,
        "record_tags": json.dumps(post.record.tags, ensure_ascii=False) if post.record.tags else None,
        "record_labels": json.dumps([l.model_dump() for l in post.record.labels], ensure_ascii=False) if post.record.labels else None,
        "embed": json.dumps(post.embed, ensure_ascii=False, default=str) if post.embed else None,
        "record_reply_parent_uri": post.record.reply.parent.uri if post.record.reply and post.record.reply.parent else None,
        "record_reply_root_uri": post.record.reply.root.uri if post.record.reply and post.record.reply.root else None,
    }
    return row


def uloz_prispevky_do_parquet(prispevky: list[Post], cesta: str) -> None:
    """
    Uloží příspěvky do Parquet souboru.

    Příspěvky jsou nejprve převedeny na ploché řádky a poté zapsány jako Parquet tabulka.

    Parametry:
    ----------
    prispevky : list[Post]
        Seznam příspěvků k uložení.
    cesta : str
        Cesta k výstupnímu souboru Parquet.
    """
    import pyarrow as pa
    import pyarrow.parquet as pq

    radky = [prispevky_na_flat_row(p) for p in prispevky]
    table = pa.Table.from_pylist(radky)
    pq.write_table(table, cesta)
    print(f"✅ ... uloženo {len(prispevky)} příspěvků do souboru {cesta}")


def nacti_prispevky_z_parquet(cesta: str) -> list[Post]:
    """
    Načte příspěvky z Parquet souboru.

    Parametry:
    ----------
    cesta : str
        Cesta k souboru Parquet s příspěvky.

    Vrací:
    ------
    list[Post]
        Seznam načtených příspěvků.
    """
    import pyarrow.parquet as pq

    table = pq.read_table(cesta)
    prispevky = []
    for radok in table.to_pylist():
        prispevky.append(_flat_row_na_post(radok))
    print(f"✅ ... načteno {len(prispevky)} příspěvků z souboru {cesta}")
    return prispevky


def _flat_row_na_post(radok: dict) -> Post:
    """
    Převede plochý slovník (řádek Parquet tabulky) zpět na instanci Post.

    Parametry:
    ----------
    radok : dict
        Plochý slovník s daty příspěvku.

    Vrací:
    ------
    Post
        Instance příspěvku.
    """
    author = Author(
        did=radok["author_did"],
        handle=radok["author_handle"],
        display_name=radok.get("author_display_name"),
    )

    reply = None
    if radok.get("record_reply_parent_uri") or radok.get("record_reply_root_uri"):
        reply = Reply(
            parent=ReplyRef(cid="", uri=radok["record_reply_parent_uri"]) if radok.get("record_reply_parent_uri") else None,
            root=ReplyRef(cid="", uri=radok["record_reply_root_uri"]) if radok.get("record_reply_root_uri") else None,
        )

    facets = None
    if radok.get("record_facets"):
        try:
            facets = json.loads(radok["record_facets"])
        except (json.JSONDecodeError, TypeError):
            facets = None

    tags = None
    if radok.get("record_tags"):
        try:
            tags = json.loads(radok["record_tags"])
        except (json.JSONDecodeError, TypeError):
            tags = None

    record = Record(
        created_at=radok["record_created_at"],
        text=radok["record_text"],
        langs=[radok["record_lang"]] if radok.get("record_lang") else [],
        facets=facets,
        tags=tags,
        reply=reply,
    )

    post = Post(
        author=author,
        cid=radok["cid"],
        indexed_at=radok["indexed_at"],
        record=record,
        uri=radok["uri"],
        like_count=radok.get("like_count", 0),
        quote_count=radok.get("quote_count", 0),
        reply_count=radok.get("reply_count", 0),
        repost_count=radok.get("repost_count", 0),
    )

    if radok.get("ner"):
        try:
            post.ner = json.loads(radok["ner"])
        except (json.JSONDecodeError, TypeError):
            pass

    if radok.get("sentiment_kategorie"):
        post.sentiment = {
            "sentiment": radok["sentiment_kategorie"],
            "score": radok.get("sentiment_skore"),
            "label": radok["sentiment_kategorie"],
        }

    if radok.get("dezinformace_label"):
        post.dezinformace = {
            "label": radok["dezinformace_label"],
            "score": radok.get("dezinformace_skore"),
        }

    return post
