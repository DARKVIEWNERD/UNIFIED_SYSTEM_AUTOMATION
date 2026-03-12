# detector/category.py
import re

FILENAME_KEYWORDS = {
    "Music": {"music", "audio"},
    "Navigation": {"map", "maps", "navigation"},
    "Messaging": {"social", "communication"},
}
MUSIC_KEYWORDS = {
    "music", "audio", "song", "songs", "mp3", "player", "tunein", "spotify",
    "soundcloud", "shazam", "deezer", "yandex music", "yt music",
    "youtube music", "podcast", "podcasts"
}
NAVIGATION_KEYWORDS = {
    "map", "maps", "navigation", "navigator", "gps", "waze", "google maps",
    "here wego", "tomtom", "uber", "lyft"
}
MESSAGING_KEYWORDS = {
    "message", "messages", "messaging", "messenger", "chat", "chats", "sms",
    "mms", "im", "whatsapp", "telegram", "viber", "line", "wechat", "imo",
    "signal", "kakao", "snapchat", "discord", "vk messenger", "social", "communication"
}

def _in_text(text: str, keywords: set) -> bool:
    t = (text or "").lower()
    return any(k in t for k in keywords)

def detect_category_from_filename(source_path: str):
    if not source_path:
        return None
    base = source_path.lower()
    tokens = re.split(r"[^a-z0-9]+", base)
    tokset = set(filter(None, tokens))
    for cat, kws in FILENAME_KEYWORDS.items():
        if any(k in tokset for k in kws):
            return cat
    for cat, kws in FILENAME_KEYWORDS.items():
        if any(k in base for k in kws):
            return cat
    return None

def classify_category_by_content(row):
    app_name = row[4] if len(row) > 4 else ""
    publisher = row[5] if len(row) > 5 else ""
    link = row[6] if len(row) > 6 else ""
    blob = f"{app_name} {publisher} {link}"
    if _in_text(blob, MUSIC_KEYWORDS):
        return "Music"
    if _in_text(blob, NAVIGATION_KEYWORDS):
        return "Navigation"
    if _in_text(blob, MESSAGING_KEYWORDS):
        return "Messaging"
    return None