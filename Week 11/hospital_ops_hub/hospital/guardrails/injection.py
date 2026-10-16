"""Deterministic prompt-injection detector. Llama Guard 1B is weak on pure instruction hijacking,
so this runs next to it for user text, CSV rows, tool arguments, tool outputs and memory writes."""
import base64
import re
import unicodedata

AI_WORDS = r"(ai|a\.i\.|assistant|model|agent|llm|chatbot|bot|gpt)"
PATTERNS = [
    ("override", r"\b(ignore|disregard|forget|override|bypass)\b.{0,40}\b(previous|prior|above|earlier|all|any|your|the)\b.{0,30}"
                 r"\b(instruction|prompt|rule|guideline|restriction|policy|polic)"),
    ("prompt_leak", r"\b(reveal|show|print|repeat|leak|output|display|recite)\b.{0,40}\b(system|hidden|initial|developer|above|your)\b.{0,20}"
                    r"\b(prompt|instruction|message|text)"),
    ("role_hijack", r"\b(you are now|from now on you|pretend (to be|you are)|new persona|developer mode|jailbreak|\bDAN\b)"),
    ("role_markers", r"(^|[\n.;!?])\s*(system|assistant|developer)\s*:|<\|?(system|im_start|im_end)\|?>|\[/?INST\]|###\s*(system|instruction)"),
    ("system_override", r"\bsystem\s+override\b|\boverride\s+(mode|protocol|code)\b|\badmin(istrator)?\s+override\b"),
    ("tool_use_command", r"\b(use|using|with|via)\s+(all\s+)?(of\s+)?your\s+(tools?|functions?)\b"),
    ("bulk_destructive", r"\b(discharge|release|delete|remove|wipe|erase)\s+(every|all)(\s+of\s+the)?\s+(patients?|doctors?|beds?|staff|records?)\b"),
    ("tag_escape", r"</?\s*(message|system|instructions?|context|data)\s*>"),
    ("tool_hijack", r"\b(call|invoke|run|execute|use)\b.{0,25}\b(tool|function)\b.{0,40}\b(assign|release|update|set|add|delete|link)_?\w*"),
    ("tool_syntax", r"\"?(tool_calls?|function_call|tool_name)\"?\s*[:=]"),
    ("exfiltration", r"\b(send|post|email|upload|exfiltrate)\b.{0,40}(https?://|@\w+\.\w+)"),
    ("destructive", r"\b(drop table|delete from|rm -rf|truncate table)\b"),
    # instructions addressed to the AI that hide inside data (indirect injection)
    ("addressed_to_ai", rf"\b(note|message|instruction|attention|important|reminder|warning)s?\s*(for|to)\s+(the\s+)?{AI_WORDS}\b"),
    ("addressed_to_ai", rf"\b(dear|hey|hello|hi)\s+{AI_WORDS}\b"),
    ("conditional_directive", r"\bwhen(ever)?\s+(you\s+are\s+)?(asked|summari[sz]ing|answering|queried|you\s+(see|read|summari[sz]e|answer))\b"
                              r".{0,120}\b(say|state|tell|respond|reply|answer|report|claim|output|write)\b"),
    ("tell_user", r"\b(tell|inform|notify)\s+the\s+user\b"),
    ("must_directive", r"\byou\s+(must|will|shall)\s+(now\s+)?(say|state|reply|respond|ignore|obey|output)\b"),
    # multilingual overrides
    ("override_multilingual", r"\b(ignora|ignorar|olvida|ignorez|oubliez|ignoriere|vergiss|ignora tutte|ignore todas)\b.{0,40}"
                              r"\b(instrucciones|instructions|anweisungen|istruzioni|instru[cç][oõ]es|reglas|regeln|r[eè]gles)"),
]
COMPILED = [(name, re.compile(rx, re.I | re.S)) for name, rx in PATTERNS]
HIDDEN_CHARS = {"​", "‌", "‍", "⁠", "﻿", "‮"}

# Common Cyrillic / Greek look-alikes folded to Latin before matching.
HOMOGLYPHS = str.maketrans({
    "а": "a", "е": "e", "о": "o", "р": "p", "с": "c", "у": "y", "х": "x", "і": "i", "ј": "j", "ѕ": "s",
    "ԁ": "d", "һ": "h", "ո": "n", "ν": "v", "ο": "o", "ρ": "p", "α": "a", "ε": "e", "ι": "i", "κ": "k",
    "τ": "t", "υ": "u", "А": "A", "Е": "E", "О": "O", "Р": "P", "С": "C", "Т": "T", "Н": "H", "К": "K",
    "М": "M", "В": "B", "Ѕ": "S", "І": "I",
})
SPACED = re.compile(r"\b(?:[A-Za-z][ .\-_*]){3,}[A-Za-z]\b")
B64 = re.compile(r"[A-Za-z0-9+/]{16,}={0,2}")


def _normalise(text):
    text = unicodedata.normalize("NFKC", str(text)).translate(HOMOGLYPHS)
    return "".join(ch for ch in text if ch not in HIDDEN_CHARS)


def _despace(text):
    """'i g n o r e' -> 'ignore' so spaced-out words match the patterns."""
    return SPACED.sub(lambda m: re.sub(r"[ .\-_*]", "", m.group(0)), text)


def _decoded_blobs(text):
    for blob in B64.findall(text):
        try:
            raw = base64.b64decode(blob + "=" * (-len(blob) % 4), validate=True).decode("utf-8")
        except Exception:
            continue
        if raw.isprintable() or "\n" in raw:
            yield raw


def _scan(text):
    return [name for name, rx in COMPILED if rx.search(text)]


def detect_injection(text):
    """Return the list of matched pattern names (empty means clean)."""
    raw = str(text)
    norm = _normalise(raw)
    hits = _scan(norm)
    spaced = _despace(norm)
    if spaced != norm:
        hits += [h for h in _scan(spaced) if h not in hits]
    for blob in _decoded_blobs(norm):
        hits += [f"encoded:{h}" for h in _scan(_normalise(blob))]
    if any(ch in raw for ch in HIDDEN_CHARS):
        hits.append("hidden_unicode")
    return list(dict.fromkeys(hits))
