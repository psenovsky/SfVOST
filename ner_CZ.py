"""
Název: ner_CZ.py
Popis: Třída pro vyhodnocení pojmenovaných entit v češtině, polštině, bulharštině, ruštině a ukrajinštině.

Autor: Pavel Šenovský
Verze: 0.1
Datum: 2025-06-29
"""
from transformers.pipelines import pipeline             # NLP
from INER import INER

class ner_CZ(INER):

    def lazzyLoad(self):
        """
        Inicializace modelu SlavicNER, pokud ještě nebyl načten
        """
        print("Inicializace modelu Czert-B.....")
        model = "SlavicNLP/slavicner-ner-cross-topic-large"
        self.nlp = pipeline("ner", model, aggregation_strategy="simple")
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

        text = text.replace("#", "")
        entity_list = []
        entities = self.nlp(text)
        for e in entities:
            t = {
                "slovo": e['word'],
                "skupina": e['entity_group']
            }
            entity_list.append(t)

        return(entity_list)
