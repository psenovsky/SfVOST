"""
Název: ner_spacy.py
Popis: Třída pro vyhodnocení pojmenovaných entit (NER) pomocí frameworku spaCy.

Podporované jazyky a výchozí modely:
- en: en_core_web_lg
- cs: cs_core_news_lg
- bg: bg_core_news_lg
- pl: pl_core_news_lg
- ru: ru_core_news_lg
- uk: uk_core_news_lg

Autor: Pavel Šenovský
Datum: 2026-07-28
"""
import spacy
from src.INER import INER


class ner_spacy(INER):
    """
    Implementace NER pomocí frameworku spaCy.

    Třída implementuje rozhraní INER a poskytuje NER funkčnost
    s využitím předtrénovaných spaCy modelů pro různé jazyky.
    """

    def __init__(self):
        """
        Inicializace třídy.
        """
        super().__init__()
        self.models = {}

    def lazzyLoad(self, lang: str, model_name: str):
        """
        Inicializace spaCy modelu pro daný jazyk, pokud ještě nebyl načten.

        Parametry:
        ----------
        lang : str
            Kód jazyka (např. 'en', 'cs', 'bg')
        model_name : str
            Název spaCy modelu (např. 'en_core_web_lg')
        """
        if lang not in self.models:
            print(f"Inicializace spaCy modelu {model_name} pro jazyk {lang}.....")
            try:
                self.models[lang] = spacy.load(model_name)
                print(f"✅ Model {model_name} úspěšně inicializován")
            except OSError as e:
                raise Exception(
                    f"❌ Nelze načíst spaCy model '{model_name}'. "
                    f"Nainstalujte ho příkazem: python -m spacy download {model_name}"
                ) from e

    def ner(self, text: str, lang: str = "en", model_name: str = "en_core_web_lg") -> list[dict]:
        """
        Provede predikci NER pro daný text.

        Parametry:
        ----------
        text : str
            Text, který chceme analyzovat
        lang : str
            Kód jazyka (výchozí: 'en')
        model_name : str
            Název spaCy modelu (výchozí: 'en_core_web_lg')

        Vrací:
        ------
        list[dict]
            Seznam detekovaných entit ve formátu [{'slovo': '<entita>', 'skupina': '<typ>'}]
        """
        if lang not in self.models:
            self.lazzyLoad(lang, model_name)

        nlp = self.models[lang]
        doc = nlp(text)

        entity_list = []
        for ent in doc.ents:
            entity_list.append({
                "slovo": ent.text,
                "skupina": self._map_entity_type(ent.label_)
            })

        return entity_list

    def _map_entity_type(self, spacy_label: str) -> str:
        """
        Přemapuje typ entity spaCy na formát používaný projektem.

        Parametry:
        ----------
        spacy_label : str
            Typ entity dle spaCy (např. 'PERSON', 'ORG', 'GPE')

        Vrací:
        ------
        str
            Přemapovaný typ entity (např. 'PER', 'ORG', 'LOC')
        """
        mapping = {
            "PERSON": "PER",
            "ORG": "ORG",
            "GPE": "GPE",
            "LOC": "LOC",
            "DATE": "DATE",
            "EVENT": "EVT",
            "PRODUCT": "PRO",
            "FAC": "FAC",
            "NORP": "MISC",
            "LANGUAGE": "MISC",
            "LAW": "MISC",
            "MONEY": "MISC",
            "PERCENT": "MISC",
            "QUANTITY": "MISC",
            "TIME": "DATE",
            "WORK_OF_ART": "MISC",
        }
        return mapping.get(spacy_label, "MISC")
