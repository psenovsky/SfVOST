from __future__ import annotations
import abc

class INER(abc.ABC):
    """
    Abstraktní třída pro modely predikující sentiment příspěvků.
    """

    def __init__(self):
        """
        Inicializace třídy.
        """
        self.nlp = None

    @abc.abstractmethod
    def lazzyLoad(self):
        """
        Inicializace modelu, pokud ještě nebyl načten
        """
        pass

    @abc.abstractmethod
    def ner(self, text: str) -> list[dict]:
        """
        provede predikci pojmenovaných entit pro daný text

        Params:
        -------
            text (str): text, který chceme predikovat

        Returns:
        --------
            dict: predikce sentimentu ve formátu {'label': <predikovaná hodnota>, 'score': <hodnota skóre>, 'sentiment': <slovní hodnocení sentimentu>}
        """
        pass
