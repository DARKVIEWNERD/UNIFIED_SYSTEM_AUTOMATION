# detector/platform.py
import os
from scraper_helpers.util import filename_tokens_lower

def detect_platform_from_filename(path_or_label: str) -> str:
    base = os.path.basename(path_or_label or "").lower()
    # Built-ins
    if "sensortower" in base or "sensor_tower" in base or "sensor-tower" in base:
        return "sensortower"
    if "similarweb" in base or "similar_web" in base or "similar-web" in base:
        return "similarweb"
    if "appfollow" in base or "app_follow" in base or "app-follow" in base:
        return "appfollow"
    # Customs
    else:
        return base.split("_")[2]
    