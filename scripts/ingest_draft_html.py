from bs4 import BeautifulSoup
from pathlib import Path
import json

HTML_DIR = Path("/data/draft_html")
OUTPUT = Path("/data/documents.jsonl")

def extract_text(html):
    soup = BeautifulSoup(html, "html.parser")

    # Remove junk
    for tag in soup(["script", "style", "nav", "header", "footer"]):
        tag.decompose()

    text = soup.get_text(separator=" ")
    return " ".join(text.split())

def extract_title(soup):
    if soup.title:
        return soup.title.text.strip()
    return "Untitled"

def extract_meta(soup, name):
    tag = soup.find("meta", attrs={"name": name}) or soup.find("meta", attrs={"property": name})
    return tag["content"].strip() if tag and tag.get("content") else ""

def process_file(path):
    html = path.read_text(errors="ignore")
    soup = BeautifulSoup(html, "html.parser")

    title = extract_title(soup)
    description = extract_meta(soup, "description")
    image = extract_meta(soup, "og:image")
    url = extract_meta(soup, "og:url") or str(path)

    text = extract_text(html)

    return {
        "title": title,
        "url": url,
        "text": text,
        "excerpt": description,
        "image": image,
        "visibility": "private",
        "source_type": "draft_html"
    }

def main():
    files = list(HTML_DIR.glob("*.html"))
    print(f"Processing {len(files)} HTML files...")

    with OUTPUT.open("a", encoding="utf-8") as f:
        for file in files:
            doc = process_file(file)
            f.write(json.dumps(doc) + "\n")

    print("Done.")

if __name__ == "__main__":
    main()
