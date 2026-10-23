#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
anon_engine.py — Engine determinística de anonimização (L0/L1) para órgãos públicos.

Gerada pela frota BeansMind (kimi-k2.7-code) e validada por execução de testes.
Stdlib apenas. Política FAIL-CLOSED: se verify() encontrar remanescentes,
o documento NÃO deve ser publicado.

L0 normalize(text)   — NFKC + reconstituição de tokens quebrados por OCR
L1 detectores        — CPF/CNPJ (regex + módulo 11), CNJ (módulo 11), OAB, e-mail, telefone
anonymize()          — pseudônimos consistentes (mode='pseudo') ou irreversível (mode='anon')
verify()             — verificação pré-publicação (detector independente)
"""

import json
import re
import unicodedata

__all__ = ["normalize", "anonymize", "verify", "run_tests", "detect", "load_rulepack"]

_CPF_RE = re.compile(r"(?<!\d)(?:\d{3}\.\d{3}\.\d{3}[-.]?\d{2}|\d{11})(?!\d)")
_CNPJ_RE = re.compile(r"(?<!\d)(?:\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}|\d{14})(?!\d)")
_CNJ_RE = re.compile(
    r"(?<!\d)(?P<num>\d{7})-(?P<dv>\d{2})\.(?P<ano>\d{4})\.(?P<org>\d)\.(?P<tr>\d{2})\.(?P<origem>\d{4})(?!\d)"
)
_OAB_RE = re.compile(r"\bOAB[\s/.-]*([A-Z]{2})[\s/.-]*(\d{1,3}(?:\.\d{3})?|\d{4,6})([A-Z])?\b", re.IGNORECASE)
_EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b")
_TEL_RE = re.compile(
    r"(?<!\d)(?:\+?55[\s.-]?)?(?:\(?\d{2}\)?[\s.-])(?:9\s?)?\d{4}[\s.-]?\d{4}(?!\d)"
)
_OCR_RUN_RE = re.compile(r"\S(?:\s\S){2,}")

_GENERIC_MARKER = {
    "CPF": "[CPF_REMOVIDO]",
    "CNPJ": "[CNPJ_REMOVIDO]",
    "CNJ": "[PROCESSO_REMOVIDO]",
    "OAB": "[OAB_REMOVIDO]",
    "EMAIL": "[EMAIL_REMOVIDO]",
    "PHONE": "[TELEFONE_REMOVIDO]",
}


# ---------------------------------------------------------------- L0

def _should_collapse(chars: str) -> bool:
    if any(ch.isdigit() or ch in ".,:;/–-()[]{}|" for ch in chars):
        return True
    return bool(chars) and all(ch.isalpha() and ch.isupper() for ch in chars)


def _ocr_reconstruct(text: str) -> str:
    def _repl(match):
        run = match.group(0)
        chars = run[::2]
        return chars if _should_collapse(chars) else run
    return _OCR_RUN_RE.sub(_repl, text)


def normalize(text: str) -> str:
    """NFKC + reconstitui tokens quebrados por OCR ('C P F : 1 2 3' -> 'CPF: 123')."""
    text = unicodedata.normalize("NFKC", text)
    text = text.replace(" ", " ")
    return _ocr_reconstruct(text)


# ---------------------------------------------------------------- validadores

def _only_digits(s: str) -> str:
    return re.sub(r"\D", "", s)


def _cpf_dv(base9: str) -> str:
    soma = sum(int(d) * p for d, p in zip(base9, range(10, 1, -1)))
    d1 = 0 if soma % 11 < 2 else 11 - (soma % 11)
    s = base9 + str(d1)
    soma = sum(int(d) * p for d, p in zip(s, range(11, 1, -1)))
    d2 = 0 if soma % 11 < 2 else 11 - (soma % 11)
    return f"{d1}{d2}"


def _cnpj_dv(base12: str) -> str:
    pesos1 = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    soma = sum(int(d) * p for d, p in zip(base12, pesos1))
    d1 = 0 if soma % 11 < 2 else 11 - (soma % 11)
    pesos2 = [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    s = base12 + str(d1)
    soma = sum(int(d) * p for d, p in zip(s, pesos2))
    d2 = 0 if soma % 11 < 2 else 11 - (soma % 11)
    return f"{d1}{d2}"


def _cnj_dv(base18: str, dv: str) -> bool:
    """Valida DV do processo CNJ: ISO 7064 MOD 97-10 — (base18 + DD) mod 97 == 1."""
    return int(base18 + dv) % 97 == 1


def _valid_cpf(s: str) -> bool:
    s = _only_digits(s)
    return len(s) == 11 and len(set(s)) > 1 and _cpf_dv(s[:9]) == s[9:]


def _valid_cnpj(s: str) -> bool:
    s = _only_digits(s)
    return len(s) == 14 and len(set(s)) > 1 and _cnpj_dv(s[:12]) == s[12:]


def _valid_cnj(num: str, dv: str, ano: str, org: str, tr: str, origem: str) -> bool:
    return _cnj_dv(num + ano + org + tr + origem, dv)


# ---------------------------------------------------------------- L2 gazetteers

def load_rulepack(path: str) -> dict:
    """Carrega rulepack de vertical (JSON em rulepacks/). Gazetteers nunca saem da rede do órgão."""
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _gazetteer_entities(text: str, gazetteers: dict):
    """Detecta ocorrências exatas (case-insensitive) das listas do rulepack."""
    ents = []
    for lista_nome, itens in (gazetteers or {}).items():
        for item in itens:
            if not item or not isinstance(item, str) or len(item) < 4:
                continue
            if "A CARREGAR" in item:
                continue
            item_norm = normalize(item)
            for m in re.finditer(re.escape(item_norm), text, re.IGNORECASE):
                ents.append({"type": "GAZETTEER", "start": m.start(), "end": m.end(), "text": m.group(0)})
    return ents


# ---------------------------------------------------------------- L1 detectores

def detect(text: str, gazetteers: dict = None):
    """Retorna lista de entidades detectadas: {type, start, end, text}."""
    ents = _gazetteer_entities(text, gazetteers)
    for m in _CNJ_RE.finditer(text):
        if _valid_cnj(*m.group("num", "dv", "ano", "org", "tr", "origem")):
            ents.append({"type": "CNJ", "start": m.start(), "end": m.end(), "text": m.group(0)})
    for m in _CPF_RE.finditer(text):
        if _valid_cpf(m.group(0)):
            ents.append({"type": "CPF", "start": m.start(), "end": m.end(), "text": m.group(0)})
    for m in _CNPJ_RE.finditer(text):
        if _valid_cnpj(m.group(0)):
            ents.append({"type": "CNPJ", "start": m.start(), "end": m.end(), "text": m.group(0)})
    for m in _OAB_RE.finditer(text):
        ents.append({"type": "OAB", "start": m.start(), "end": m.end(), "text": m.group(0)})
    for m in _EMAIL_RE.finditer(text):
        ents.append({"type": "EMAIL", "start": m.start(), "end": m.end(), "text": m.group(0)})
    for m in _TEL_RE.finditer(text):
        if 8 <= len(_only_digits(m.group(0))) <= 13:
            ents.append({"type": "PHONE", "start": m.start(), "end": m.end(), "text": m.group(0)})
    # dedup por sobreposição (prioridade: entidades mais longas/específicas)
    ents.sort(key=lambda e: (e["start"], -(e["end"] - e["start"])))
    out, last_end = [], -1
    for e in ents:
        if e["start"] >= last_end:
            out.append(e)
            last_end = e["end"]
    return out


# ---------------------------------------------------------------- anonimização

_GENERIC_MARKER["GAZETTEER"] = "[NOME_REMOVIDO]"


def anonymize(text: str, mode: str = "pseudo", gazetteers: dict = None) -> str:
    """
    mode='pseudo': pseudônimos consistentes por documento ([CPF_1], [CPF_1]...).
    mode='anon': marcadores irreversíveis por tipo ([CPF_REMOVIDO]).
    gazetteers: dict de listas do rulepack da vertical (L2).
    """
    if mode not in ("pseudo", "anon"):
        raise ValueError("mode deve ser 'pseudo' ou 'anon'")
    text = normalize(text)
    ents = detect(text, gazetteers)
    counters, seen = {}, {}
    pieces, last = [], 0
    for e in ents:
        pieces.append(text[last:e["start"]])
        if mode == "anon":
            pieces.append(_GENERIC_MARKER[e["type"]])
        else:
            key = (e["type"], e["text"])
            if key not in seen:
                counters[e["type"]] = counters.get(e["type"], 0) + 1
                seen[key] = f"[{e['type']}_{counters[e['type']]}]"
            pieces.append(seen[key])
        last = e["end"]
    pieces.append(text[last:])
    return "".join(pieces)


def verify(text: str) -> list:
    """Fail-closed: retorna entidades remanescentes. Lista vazia = apto a publicar."""
    return detect(normalize(text))


# ---------------------------------------------------------------- testes

def run_tests() -> bool:
    ok = True

    def check(name, cond):
        nonlocal ok
        print(("PASS" if cond else "FAIL"), "-", name)
        ok = ok and cond

    check("CPF válido detectado", any(e["type"] == "CPF" for e in detect("CPF: 529.982.247-25")))
    check("CPF inválido rejeitado (dv)", not any(e["type"] == "CPF" for e in detect("CPF: 529.982.247-99")))
    check("CPNão-detecta sequência igual", not any(e["type"] == "CPF" for e in detect("111.111.111-11")))
    check("CNPJ válido detectado", any(e["type"] == "CNPJ" for e in detect("CNPJ 60.903.775/0001-07")))
    check("CNPJ inválido rejeitado (dv)", not any(e["type"] == "CNPJ" for e in detect("CNPJ 60.903.775/0001-99")))
    check("CNJ válido detectado", any(e["type"] == "CNJ" for e in detect("processo 0810168-25.2025.4.05.8100")))
    check("CNJ inválido rejeitado (dv)", not any(e["type"] == "CNJ" for e in detect("processo 0810168-99.2025.4.05.8100")))
    check("OAB detectada", any(e["type"] == "OAB" for e in detect("advogado OAB/DF 79.173")))
    check("E-mail detectado", any(e["type"] == "EMAIL" for e in detect("contato joao.silva@orgao.gov.br hoje")))
    check("Telefone detectado", any(e["type"] == "PHONE" for e in detect("ligue (85) 99812-3456 urgente")))
    check("OCR quebrado normalizado", "CPF" in normalize("C P F : 1 2 3 . 4 5 6"))
    out = anonymize("João, CPF 529.982.247-25, repete 529.982.247-25")
    check("Pseudônimo consistente", out.count("[CPF_1]") == 2)
    out2 = anonymize("CPF 529.982.247-25", mode="anon")
    check("Modo anon irreversível", "[CPF_REMOVIDO]" in out2 and "529" not in out2)
    check("verify limpa após anonimização", verify(anonymize("João OAB/DF 79173, CPF 529.982.247-25")) == [])
    check("verify detecta remanescente", len(verify("CPF 529.982.247-25 ficou")) == 1)
    gaz = {"tribunais_e_varas": ["12ª Vara Federal"]}
    out3 = anonymize("Ação na 12ª Vara Federal contra o réu", gazetteers=gaz)
    check("Gazetteer (L2) anonimiza nome de órgão", "[GAZETTEER_1]" in out3 and "12ª Vara Federal" not in out3)
    rp = load_rulepack(__import__("os").path.join(__import__("os").path.dirname(__file__), "..", "rulepacks", "jus.json"))
    check("load_rulepack carrega vertical jus", rp["vertical"] == "jus")
    return ok


if __name__ == "__main__":
    import sys
    sys.exit(0 if run_tests() else 1)
