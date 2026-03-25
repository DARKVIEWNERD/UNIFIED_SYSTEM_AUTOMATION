import email
from bs4 import BeautifulSoup


def scrape_app_name_publisher_link(
    mhtml_file,
    selectors,
    max_rows=10,
    main_container_index=None 
):
    """
    Returns a list of dicts:
    [
        {
            "app_name": "...",
            "publisher": "...",
            "app_link": "..."
        }
    ]

    selectors example:
    [  
        {"role": "Main Container", "tag": "table", "type": "class", "value": "apps-table"},
        {"role": "Row Container", "tag": "tr", "type": "class", "value": "app-row"},
        {"role": "App Name", "tag": "a", "type": "class", "value": "app-name"},
        {"role": "Publisher", "tag": "span", "type": "class", "value": "publisher"},
        {"role": "App Link", "tag": "a", "type": "class", "value": "app-name"},
    ]
    """

    # --- Load HTML from MHTML ---
    with open(mhtml_file, "r", encoding="utf-8") as f:
        msg = email.message_from_file(f)

    html = None
    for part in msg.walk():
        if part.get_content_type() == "text/html":
            html = part.get_payload(decode=True).decode(
                part.get_content_charset("utf-8")
            )
            break

    if not html:
        raise ValueError("No HTML found in MHTML file")

    soup = BeautifulSoup(html, "html.parser")

    # --- Optional main container selection ---
    main_sel = next((s for s in selectors if s["role"] == "Main Container"), None)

    if main_sel and main_container_index is not None:
        kwargs = {main_sel["type"]: main_sel["value"]}
        containers = soup.find_all(main_sel["tag"], **kwargs)

        if not containers:
            raise ValueError("Main container not found")

        if main_container_index >= len(containers):
            raise IndexError("Main container index out of range")

        soup = containers[main_container_index]

    # --- Row container ---
    row_sel = next((s for s in selectors if s["role"] == "Row Container"), None)
    if not row_sel:
        raise ValueError("Row Container selector is required")

    row_kwargs = {row_sel["type"]: row_sel["value"]}
    row_elements = soup.find_all(row_sel["tag"], **row_kwargs)[:max_rows]

    results = []

    for row in row_elements:
        # App Name
        app_name = ""
        app_sel = next((s for s in selectors if s["role"] == "App Name"), None)
        if app_sel:
            tag = row.find(app_sel["tag"], **{app_sel["type"]: app_sel["value"]})
            if tag:
                app_name = tag.get_text(strip=True)

        # Publisher
        publisher = ""
        pub_sel = next((s for s in selectors if s["role"] == "Publisher"), None)
        if pub_sel:
            tag = row.find(pub_sel["tag"], **{pub_sel["type"]: pub_sel["value"]})
            if tag:
                publisher = tag.get_text(strip=True)

        # App Link
        app_link = ""
        link_sel = next((s for s in selectors if s["role"] == "App Link"), None)
        if link_sel:
            tag = row.find(link_sel["tag"], **{link_sel["type"]: link_sel["value"]})
            if tag and tag.has_attr("href"):
                app_link = tag["href"]

        results.append({
            "app_name": app_name,
            "publisher": publisher,
            "app_link": app_link
        })

    return results