import re

from bs4 import BeautifulSoup


def parse_file_cards(html: str):
    """
    Parse file cards from the new-style public folder page.
    Returns list of (filename, detail_url).
    """
    soup = BeautifulSoup(html, "html.parser")
    files = []
    for card in soup.find_all("div", class_=lambda c: c and "jsCardItem" in c.split()):
        name_div = card.find("div", class_=lambda c: c and "jsFileName" in c.split())
        if not name_div:
            continue
        filename = name_div.get_text(strip=True)
        link = card.find("a", class_=lambda c: c and "jsGoFile" in c.split())
        if not link or not link.get("href"):
            continue
        href = link["href"]
        if not href.startswith("http"):
            href = "https://www.4shared.com" + href
        files.append((filename, href))
    return files


def parse_subfolder_cards(html: str):
    """
    Parse subfolder cards from the new-style public folder page.
    Returns list of (folder_name, folder_url).
    """
    soup = BeautifulSoup(html, "html.parser")
    folders = []
    for card in soup.find_all("div", class_=lambda c: c and "dir-card" in c.split()):
        link = card.find("a", class_=lambda c: c and "jsFolderLink" in c.split())
        if not link or not link.get("href"):
            continue
        href = link["href"]
        if not href.startswith("http"):
            href = "https://www.4shared.com" + href
        name_div = card.find("div", class_="dir-name")
        folder_name = name_div.get_text(strip=True) if name_div else href
        folders.append((folder_name, href))
    return folders


def parse_next_page(html: str):
    soup = BeautifulSoup(html, "html.parser")
    inp = soup.find("input", class_="jsNextPageLink")
    if inp and inp.get("value"):
        path = inp["value"]
        if path.startswith("http"):
            return path
        return "https://www.4shared.com" + path
    return None


def parse_total_pages(html: str):
    soup = BeautifulSoup(html, "html.parser")
    inp = soup.find("input", class_="jsPagesTotalCount")
    if inp and inp.get("value"):
        try:
            return int(inp["value"])
        except ValueError:
            pass
    return 1


def _parse_media_url_from_html(html: str):
    soup = BeautifulSoup(html, "html.parser")
    img = soup.find("img", class_="jsFilePreviewImage")
    if img and img.get("src"):
        return img["src"]
    vid = soup.find("video")
    if vid:
        if vid.get("src"):
            return vid["src"]
        src_tag = vid.find("source")
        if src_tag and src_tag.get("src"):
            return src_tag["src"]
    m = re.search(r'https://dc\d+\.4shared\.com/(?:download|img)/[^\s"\'&]+', html)
    if m:
        return m.group(0)
    return None
