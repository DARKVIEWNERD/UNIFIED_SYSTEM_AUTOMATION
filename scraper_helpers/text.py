# helpers/text.py
import re

CURRENCY_RE = re.compile(r"(?:[\$\€\£\¥₱]|USD|EUR|GBP|JPY|CNY|RMB|HKD|TWD|KRW|INR|PHP)", re.IGNORECASE)
PRICE_WORDS_RE = re.compile(r"\b(?:free|price|deal|discount|offer|sale)\b", re.IGNORECASE)
RATING_RE = re.compile(r"(?:★|☆|⭐|/5|/10|ratings?|reviews?)", re.IGNORECASE)
ONLY_DIGITS_RE = re.compile(r"^\s*[\d.,]+\s*$")
ZERO_DOLLARS_RE = re.compile(r"^\s*0+\s*(?:dollars|usd|php)?\s*$", re.IGNORECASE)

def looks_like_bad_publisher(s: str) -> bool:
    if not s:
        return True
    t = s.strip()
    if len(t) <= 2:
        return True
    if ONLY_DIGITS_RE.search(t):
        return True
    if ZERO_DOLLARS_RE.search(t.replace(" ", "")) or ZERO_DOLLARS_RE.search(t):
        return True
    if CURRENCY_RE.search(t) or PRICE_WORDS_RE.search(t):
        return True
    if RATING_RE.search(t):
        return True
    letters = sum(ch.isalpha() for ch in t)
    total = len(t)
    if total > 0 and letters / total < 0.35:
        return True
    return False

def clean_publisher_text(s: str) -> str:
    t = (s or "").strip()
    if t.lower().startswith("by "):
        t = t[3:].strip()
    t = re.sub(r"[\s\|\-·]+$", "", t).strip()
    return t

def score_publisher_candidate(app_name: str, cand: str) -> int:
    s = cand.strip()
    score = 0
    if not s:
        return -999
    if app_name and s.lower() == app_name.lower():
        score -= 10
    if len(s) > 60:
        score -= 3
    if 3 <= len(s) <= 40:
        score += 2
    if any(ch.isupper() for ch in s) and any(ch.islower() for ch in s):
        score += 2
    elif any(ch.isupper() for ch in s):
        score += 1
    score += min(sum(ch.isalpha() for ch in s) // 3, 5)
    if looks_like_bad_publisher(s):
        score -= 20
    return score