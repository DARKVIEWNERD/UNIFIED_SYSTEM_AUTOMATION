

from scraper_helpers.io import load_config
from yyyy import scrape_app_name_publisher_link

config = load_config()
selectors = config.get("appmagic", {}).get("custom_scraper_selectors", [])

apps = scrape_app_name_publisher_link(
    r"C:\Users\sp8866\Downloads\dist\dist\AUTOMATION FILE\AUTOMATION_2026-03-23\0310_BR_AppMagic_apple_Social_20260323.mhtml",
    selectors,
    max_rows=10,
    main_container_index=0
)

for app in apps:
    print(app["app_name"], app["publisher"], app["app_link"])