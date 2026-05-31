## PyDantic

jedná se o knihovnu, která slouží pro vynucení (a validaci) textu. 

Použití je poměrně verzatilní, ale jedno z hlavních je použití knihovny ve spolupráci s LLM k zajištění, aby výstupy LLM měly specifický datový formát. 

Pro připomenutí za normálních okolností LLM generuje JSON/JSONL formát, ale bez vynucování datových typů a kontroly validity dat. Je tomu tak proto, že LLM formulují JSON soubory stejným způsobem jako běžný odsatavcový text, na který nejsou žádné požadavky na strukturu.

Pokud PyDantic toto mění. Lze specfikovat vlastní datový formát pomocí Pydantic schématu. To je realizováno formou třídy odvozené z BaseModel.

```python
from pydantic import BaseModel
from openai import OpenAI

class person(BaseModel):
    name: str
    age: int
    # ...

result = client.response_parse(
    model = "gpt-5-mini",
    input = [
        # prompt
    ],
    response_parse = person
)

person: Person = result.output_parsed
print(Person)
```

Uvedený postup může být velmi užitečný v případě, že by bylo nutné implementovat databázový backend pro celý systém.
