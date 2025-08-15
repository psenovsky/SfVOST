"""
Název: ner_BERT_EN.py
Popis: Třída pro vyhodnocení pojmenovaných entit v angličtině.

Autor: Pavel Šenovský
Verze: 0.1
Datum: 2025-06-29
"""
from transformers.pipelines import pipeline             # NLP
from src.INER import INER

class ner_BERT_EN(INER):

    def lazzyLoad(self):
        """
        Inicializace modelu BERT EN, pokud ještě nebyl načten
        """
        print("Inicializace modelu BERT EN.....")
        self.nlp = pipeline("ner", model="dbmdz/bert-large-cased-finetuned-conll03-english", aggregation_strategy="simple")
        print("✅ Model úspěšně inicializován")


    def ner(self, text):
        """
        provede predikci NER pro daný text

        Params:
        -------
            text (str): text, který chceme predikovat

        Returns:
        --------
            dict: predikce pojmenovaných entit ve formátu {slovo: <identifikovaná entita>, skupina: <typ entity>}
        """
        if self.nlp is None:
            self.lazzyLoad()

        entity_vysledky = self.nlp(text.replace("#",""))
        entity_list = []
        for e in entity_vysledky:
            t = {
                "slovo": e['word'],
                "skupina": e['entity_group']
            }
            entity_list.append(t)

        return(entity_list)
