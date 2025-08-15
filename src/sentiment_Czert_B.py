"""
Název: sentiment_Czert-B.py
Popis: Třída pro vyhodnocení sentimentu příspěvků pomocí BERT-like modelu. Třída používá https://huggingface.co/UWB-AIR/Czert-B-base-cased, který s relativně dobrou přesností umožňuje hodnocení sentimentu v češtině.

reference:
Sido, Jakub; Pražák, Ondrej; Pribáň, Pavel; Pašek, Jan; Seják, Michal; Konopík, Miloslav (2021): Czert-B: A BERT-like model for Czech sentiment analysis. In: Proceedings of Recent Advances in Natural Language Processing, pp. 1326 - 1338, DOI: 10.26615/978-954-452-072-4_149

Autor: Pavel Šenovský
Datum: 2025-06-27
"""

from transformers.pipelines import pipeline             # NLP
from src.ISentiment import ISentiment

# from transformers import AutoModel

class sentiment_Czert_B(ISentiment):
    """
    Třída pro vyhodnocení sentimentu příspěvků pomocí BERT-like modelu. Třída používá https://huggingface.co/UWB-AIR/Czert-B-base-cased, který s relativně dobrou přesností umožňuje hodnocení sentimentu v češtině.
    """

    def lazzyLoad(self):
        """
        Inicializace modelu Czert-B, pokud ještě nebyl načten
        """
        print("Inicializace modelu Czert-B.....")
        self.nlp = pipeline("fill-mask", model="UWB-AIR/Czert-B-base-cased")
        print("✅ Model úspěšně inicializován")

    def sentiment(self, text):
        """
        provede predikci sentimentu pro daný text

        Params:
        -------
            text (str): text, který chceme predikovat

        Returns:
        --------
            dict: predikce sentimentu ve formátu {'label': <predikovaná hodnota>, 'score': <hodnota skóre>, 'sentiment': <slovní hodnocení sentimentu>}
        """
        if self.nlp is None:
            self.lazzyLoad()

        template = f"Hodnotíme sentiment příspěvku {text}. Příspěvek je [MASK] (negativní, pozitivní, neutrální)."
        sent = self.nlp(template)[0]   # zpracovávám po příspěvku, zajímá mě pouze 1. odpověď (jelikož je jediná)
        sent2 = {
            "label": sent["token_str"],
            "score": sent["score"],
            "sentiment": sent["token_str"].lower()
        }
        return(sent2)
