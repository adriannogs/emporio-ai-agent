"""Retriever lexical leve para o manual de políticas; não exige serviço externo."""
import re
from pathlib import Path
from .config import POLICY_PATH

def _tokens(text):
    stop = {"a","o","as","os","de","da","do","das","dos","e","em","no","na","nos","nas","um","uma","me","minha","meu","posso","qual","quais","é","ser","que","para","por","com"}
    return {t for t in re.findall(r"[a-z0-9À-ÿ]+", text.lower()) if t not in stop and len(t) > 1}

def retrieve_policy(question, top_k=3):
    if not POLICY_PATH.exists():
        return []
    text = POLICY_PATH.read_text(encoding="utf-8")
    chunks = [c.strip() for c in re.split(r"(?=^## )", text, flags=re.M) if c.strip()]
    q = _tokens(question)
    scored=[]
    for chunk in chunks:
        tokens=_tokens(chunk)
        score=len(q & tokens) / max(len(q), 1)
        if score > 0:
            scored.append((score, chunk))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [chunk for score, chunk in scored[:top_k]]
