"""
Název: sentiment_BERT_multi.py
Popis: Třída pro vyhodnocení sentimentu příspěvků pomocí BERTu. Třída používá https://huggingface.co/nlptown/bert-base-multilingual-uncased-sentiment, který s relativně dobrou přesností umožňuje hodnocení sentimentu v jazycích: angličtina (en), francouzština (fr), němčina (de), italština (it), španělština (es), nizozemština (nl).

Autor: Pavel Šenovský
Datum: 2025-06-27
"""

from transformers.pipelines import pipeline             # NLP
from src.ISentiment import ISentiment

class sentiment_BERT_multi(ISentiment):
    """
    Třída pro vyhodnocení sentimentu příspěvků pomocí BERTu. Třída používá https://huggingface.co/nlptown/bert-base-multilingual-uncased-sentiment, který s relativně dobrou přesností umožňuje hodnocení sentimentu v jazycích: angličtina (en), francouzština (fr), němčina (de), italština (it), španělština (es), nizozemština (nl).
    """

    def prelozit_sentiment(self, skore):
        """
        Převede skóre sentimentu na slovní vyjádření

        Params:
        -------
            skore (str): skóre sentimentu ve formátu X star, kde X je v intervalu [1, 5]

        Returns:
        --------
            str: vyjádření skóre sentimentu
        """
        s = int(skore[0])
        if s in [1, 2]:
            return "negativní"
        elif s == 3:
            return "neutrální"
        else:
            return "pozitivní"

    def lazzyLoad(self):
        """
        Inicializace modelu BERT multilanguage, pokud ještě nebyl načten
        """
        print("Inicializace modelu BERT multilanguage.....")
        self.nlp = pipeline("text-classification", model="nlptown/bert-base-multilingual-uncased-sentiment")
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

        sent = self.nlp(text)[0]   # zpracovávám po příspěvku, zajímá mě pouze 1. odpověď (jelikož je jediná)
        sent['sentiment'] = self.prelozit_sentiment(sent['label'])
        return(sent)
