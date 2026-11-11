"""Atribuição conservadora de uma polaridade geral a candidatos citados.

O classificador de sentimento é de frases inteiras. Estas regras não constituem
um modelo treinado para sentimento dirigido a candidatos.
"""

from __future__ import annotations

import re

from analise_sentimentos.domain.targets import normalize


LULA = re.compile(r"(?<!\w)(?:lula|luiz\s+inacio)(?!\w)")
FLAVIO = re.compile(r"(?<!\w)flavio(?!\w)")
LULA_NUMBER = re.compile(r"(?<!\w)13(?!\w)")
FLAVIO_NUMBER = re.compile(r"(?<!\w)22(?!\w)")
BOLSONARO = re.compile(r"(?<!\w)bolsonaro(?!\w)")
JAIR_BOLSONARO = re.compile(r"(?<!\w)jair(?:\s+messias)?\s+bolsonaro(?!\w)")
LABELS = {"NEG": "negativo", "NEU": "neutro", "POS": "positivo"}


def attribute_to_candidates(text: str, probabilities: dict[str, float],
                            minimum_probability: float = 0.60) -> dict[str, str]:
    """Retorna rótulos aproximados para Lula e Flávio, sem inventar alvo.

    Apenas uma menção nominal única permite transportar a polaridade geral
    para o candidato. Números e o sobrenome isolado não identificam alguém
    com segurança. Duas referências também impedem essa atribuição.
    """
    normalized = normalize(text).replace("\ufe0f", "").replace("\u20e3", "")
    jair_present = bool(JAIR_BOLSONARO.search(normalized))
    normalized = JAIR_BOLSONARO.sub(" ", normalized)
    lula_explicit = bool(LULA.search(normalized))
    flavio_explicit = bool(FLAVIO.search(normalized))
    lula_ambiguous = bool(LULA_NUMBER.search(normalized)) and not lula_explicit
    flavio_ambiguous = (bool(FLAVIO_NUMBER.search(normalized)) or
                        bool(BOLSONARO.search(normalized))) and not flavio_explicit
    lula_present = lula_explicit or lula_ambiguous
    flavio_present = flavio_explicit or flavio_ambiguous
    result = {
        "sentimento_lula_automatico": "sem_referencia",
        "sentimento_flavio_automatico": "sem_referencia",
        "regra_atribuicao": "sem_mencao_identificavel",
    }
    if not (lula_present or flavio_present):
        return result
    if jair_present:
        if lula_present:
            result["sentimento_lula_automatico"] = "incerto"
        if flavio_present:
            result["sentimento_flavio_automatico"] = "incerto"
        result["regra_atribuicao"] = "outra_pessoa_mencionada"
        return result
    if lula_present and flavio_present:
        result["sentimento_lula_automatico"] = "incerto"
        result["sentimento_flavio_automatico"] = "incerto"
        result["regra_atribuicao"] = "multiplas_referencias"
        return result
    target = "sentimento_lula_automatico" if lula_present else "sentimento_flavio_automatico"
    if (lula_present and not lula_explicit) or (flavio_present and not flavio_explicit):
        result[target] = "incerto"
        result["regra_atribuicao"] = "referencia_ambigua"
        return result
    best_label = max(probabilities, key=probabilities.get)
    if best_label not in LABELS:
        raise ValueError(f"Classe inesperada do modelo: {best_label}")
    if probabilities[best_label] < minimum_probability:
        result[target] = "incerto"
        result["regra_atribuicao"] = "probabilidade_baixa"
        return result
    result[target] = LABELS[best_label]
    result["regra_atribuicao"] = "mencao_nominal_unica_polaridade_geral"
    return result
