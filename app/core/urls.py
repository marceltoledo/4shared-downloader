import re


def folder_id_from_url(url: str) -> str:
    """
    Extract the stable 4shared folder ID from a URL.
    e.g. https://www.4shared.com/folder/F6YhfbPq/_online.html -> F6YhfbPq
    """
    m = re.search(r"/folder/([A-Za-z0-9_\-]+)/", url)
    if m:
        return m.group(1)
    return re.sub(r"[^\w\-]", "_", url)[-40:]


def normalize_url(raw: str) -> str:
    """
    Accept any 4shared folder URL format and return a clean, single URL.
    Fixes accidentally joined URLs (two https:// on the same line),
    double slashes after domain, and hash/query fragments.
    """
    raw = raw.strip()

    # Fix doubled URLs e.g. "...html https://..." or "...htmlhttps://..."
    # Keep only the first URL if two are joined on one line
    m = re.search(r'(https?://\S+?\.html)\S*https?://', raw)
    if m:
        raw = m.group(1)

    # Remove hash fragments and query strings
    raw = re.sub(r"[?#].*$", "", raw)

    # Fix double slashes after domain
    raw = re.sub(r"(https://www\.4shared\.com)//+", r"\1/", raw)

    # New-style /folder/ URL — return as-is
    if re.search(r"4shared\.(com|io)/folder/[A-Za-z0-9_\-]+/", raw):
        return raw

    # Old _online.html style
    m = re.search(r"folder/([A-Za-z0-9_\-]+)/_online", raw)
    if m:
        folder_id = m.group(1)
        return f"https://www.4shared.com/folder/{folder_id}/_online.html"

    return raw
