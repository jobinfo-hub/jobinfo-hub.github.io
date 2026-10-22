
"""CareerPick sitemap generator - preserve existing URLs."""
from pathlib import Path
from datetime import date
from urllib.parse import urlparse
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parent.parent
SITEMAP = ROOT / "sitemap.xml"
JOBS = ROOT / "jobs"
BASE = "https://jobinfo-hub.github.io"
NS = "http://www.sitemaps.org/schemas/sitemap/0.9"

ET.register_namespace("", NS)
TAG = lambda name: f"{{{NS}}}{name}"


def main():
    if not SITEMAP.exists():
        raise SystemExit("기존 sitemap.xml이 없습니다.")

    tree = ET.parse(SITEMAP)
    root = tree.getroot()
    if root.tag != TAG("urlset"):
        raise SystemExit("올바른 사이트맵 형식이 아닙니다.")

    existing = set()
    for entry in root.findall(TAG("url")):
        loc = entry.findtext(TAG("loc"), default="").strip()
        if loc:
            existing.add(loc)

    pages = sorted(JOBS.glob("a[0-9]*.html"))
    if not pages:
        raise SystemExit("생성된 채용공고 페이지가 없습니다.")

    current_jobs = {
        f"{BASE}/jobs/{page.name}"
        for page in pages
        if page.stem[1:].isdigit()
    }

    # 이전에 등록된 채용공고 주소 중 더 이상
    # 생성되지 않는 페이지는 사이트맵에서 제외
    for entry in list(root.findall(TAG("url"))):
        loc = entry.findtext(TAG("loc"), default="").strip()
        parsed = urlparse(loc)
        if (
            parsed.scheme == "https"
            and parsed.netloc == "jobinfo-hub.github.io"
            and parsed.path.startswith("/jobs/")
            and loc not in current_jobs
        ):
            root.remove(entry)
            existing.discard(loc)

    # 자체 제작 가이드는 존재하는 HTML 파일만 사이트맵에 등록합니다.
    guide_files = [ROOT / "guides" / "index.html", ROOT / "guides" / "application-checklist.html"]
    guide_urls = {
        f"{BASE}/guides/" if page.name == "index.html"
        else f"{BASE}/guides/{page.name}"
        for page in guide_files if page.is_file()
    }

    added = 0
    today = date.today().isoformat()

    for loc in sorted(current_jobs):
        if loc in existing:
            continue
        entry = ET.SubElement(root, TAG("url"))
        ET.SubElement(entry, TAG("loc")).text = loc
        ET.SubElement(entry, TAG("lastmod")).text = today
        added += 1

    for loc in sorted(guide_urls):
        if loc in existing:
            continue
        entry = ET.SubElement(root, TAG("url"))
        ET.SubElement(entry, TAG("loc")).text = loc
        ET.SubElement(entry, TAG("lastmod")).text = today
        existing.add(loc)
        added += 1

    ET.indent(tree, space="  ")
    tree.write(SITEMAP, encoding="utf-8", xml_declaration=True)

    print("현재 채용 상세페이지:", len(current_jobs))
    print("새로 추가한 주소:", added)
    print("사이트맵 전체 주소:", len(root.findall(TAG("url"))))


if __name__ == "__main__":
    main()
