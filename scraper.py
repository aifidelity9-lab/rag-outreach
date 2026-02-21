"""
Web scraper for finding customs brokers (CHB), import/export companies,
and freight forwarders in Los Angeles — with a focus on Chinese-owned businesses.

Supports multiple search backends:
  1. Google search scraping (may get blocked)
  2. DuckDuckGo HTML scraping (more reliable fallback)
  3. Seed data mode (--seed) for immediate testing
"""

import json
import re
import sys
import time
import random
from urllib.parse import urljoin, urlparse, quote_plus

import requests
from bs4 import BeautifulSoup

SEARCH_QUERIES = [
    "customs broker Los Angeles",
    "customs house broker LA",
    "CHB customs brokerage Los Angeles",
    "import customs entry service Los Angeles",
    "freight forwarder customs broker LA",
    "Chinese customs broker Los Angeles",
    "华人报关行 洛杉矶",
    "报关公司 洛杉矶",
    "Chinese import company Los Angeles",
    "华人进口公司 洛杉矶",
    "customs clearance company Los Angeles",
    "import export company LA Chinatown",
]

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9,zh-CN;q=0.8,zh;q=0.7",
    "Accept-Encoding": "gzip, deflate",
    "DNT": "1",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
}

PHONE_PATTERNS = [
    re.compile(r"\(?\d{3}\)?[\s.\-]?\d{3}[\s.\-]?\d{4}"),
    re.compile(r"\+1[\s.\-]?\(?\d{3}\)?[\s.\-]?\d{3}[\s.\-]?\d{4}"),
]

EMAIL_PATTERN = re.compile(
    r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}"
)

CHINESE_CHAR_PATTERN = re.compile(r"[\u4e00-\u9fff]")

# --- Seed data for testing when search engines block us ---

SEED_COMPANIES = [
    # --- Real Chinese-owned customs brokers in LA (from search results) ---
    {
        "name": "Speed C CHB 美国速通清关",
        "url": "https://www.speedcchb.com",
        "snippet": "Chinese-owned customs broker at 5510 W. 104th St., Los Angeles, CA 90045. Licensed CHB handling import entries and customs clearance. 华人报关行 进口清关服务. Phone: (909) 895-7266",
    },
    {
        "name": "C & R Customs Brokers 中美报关",
        "url": "https://www.crcustomsbrokers.com",
        "snippet": "Chinese-owned customs brokerage at 5250 W. Century Blvd., #458, Los Angeles, CA 90045. Import entry filing and clearance services. 中美报关行. Phone: (310) 410-0610",
    },
    {
        "name": "Lee Co. Customs Broker",
        "url": "https://www.yelp.com/biz/lee-company-customs-broker-los-angeles",
        "snippet": "Licensed customs broker at 11099 S. La Cienega Blvd., #152, Los Angeles, CA 90045. Import clearance and customs entry services. Phone: (310) 417-6300",
    },
    {
        "name": "Master Customs Service 万事达报关行",
        "url": "https://www.yelp.com/biz/master-customs-broker-los-angeles",
        "snippet": "Chinese-owned customs broker at 11099 S. La Cienega Blvd., #245, Los Angeles, CA 90045. Import customs clearance, entry filing. 万事达报关行 进口报关. Phone: (310) 670-8898",
    },
    {
        "name": "ORIOX CHB 華捷報關行",
        "url": "https://www.orioxchb.com",
        "snippet": "Chinese-speaking customs broker offering bilingual customs brokerage services. Specializes in serving Chinese importers with customs entry filing and clearance. 華捷報關行 中文报关服务",
    },
    {
        "name": "Great Way Trading & Transportation 大道报关",
        "url": "https://great-way.com",
        "snippet": "First licensed corporate customs brokerage established by a professional from Mainland China. Specializes in clearing goods imported from China. Permits in Los Angeles and San Francisco. 大道报关 中国进口清关",
    },
    {
        "name": "Omega CHB International",
        "url": "https://omegachb.com",
        "snippet": "Over 25 years in customs brokerage in Los Angeles. Full-service import/export customs broker at LA/Long Beach ports. Customs entries, classification, compliance, ISF filing.",
    },
    {
        "name": "Fleischer International",
        "url": "https://www.fleischer-chb.com",
        "snippet": "US customs broker headquartered in Los Angeles. Licensed CHB providing customs brokerage, freight forwarding, and trade compliance services at LA/Long Beach ports.",
    },
    {
        "name": "Alta Logistics Customs Brokers",
        "url": "https://www.yelp.com/biz/alta-logistics-customs-brokers-los-angeles-2",
        "snippet": "Customs broker at 1100 S Grand Ave, Los Angeles, CA 90015. Import customs clearance and logistics services. Phone: (213) 261-4419",
    },
    {
        "name": "Unity Customs Brokers",
        "url": "https://www.yelp.com/biz/unity-customs-brokers-los-angeles",
        "snippet": "Customs broker at 11099 S La Cienega Blvd, Suite 202, Los Angeles, CA 90045. Licensed CHB handling import entries at LA/Long Beach ports.",
    },
    {
        "name": "Packair Customs Broker",
        "url": "https://www.packair.com",
        "snippet": "Customs broker and freight forwarder in Los Angeles for over 47 years. Licensed CHB serving major studios and importers. Customs entries, ISF, ABI filing at LA/Long Beach.",
    },
    {
        "name": "Los Angeles Customs Broker (LACB)",
        "url": "https://losangelescustomsbroker.us",
        "snippet": "Full-service customs brokerage in Southern California. Import entry filing, customs clearance, trade compliance, ISF, and bonded warehouse services at LA/Long Beach ports.",
    },
    {
        "name": "International LinK Logistics",
        "url": "https://www.intllinklogistics.com",
        "snippet": "Top-rated customs broker and freight forwarder in Los Angeles. Licensed CHB handling import entries, ocean/air freight customs clearance at LA/Long Beach.",
    },
    {
        "name": "MBC Brokers",
        "url": "https://www.mbcbrokers.com",
        "snippet": "Licensed customs house broker in Los Angeles area. Import entry filing, customs clearance, compliance consulting for importers at LA/Long Beach ports.",
    },
    {
        "name": "JJM Customs Broker",
        "url": "https://www.jjmcustomsbroker.com",
        "snippet": "Customs brokerage firm serving importers in the Los Angeles and Long Beach port area. Licensed CHB handling entry summaries, HTS classification, and duty management.",
    },
    {
        "name": "Juliana Lim CHB",
        "url": "https://www.yelp.com/search?cflt=customsbrokers&find_loc=Los+Angeles,+CA",
        "snippet": "Licensed customs house broker in Los Angeles. Chinese-owned CHB specializing in import clearance and customs entry services for Asian importers.",
    },
    {
        "name": "EMD Customs Broker & Logistics",
        "url": "https://www.emdcustoms.com",
        "snippet": "Customs broker and logistics company in the Los Angeles area. Licensed CHB providing import entry filing, ISF, FDA/USDA clearance services.",
    },
    {
        "name": "Fleet Broker USA",
        "url": "https://www.fleetbrokerusa.com",
        "snippet": "Customs brokerage and freight services in Los Angeles. Import customs clearance, entry filing, and trade compliance at LA/Long Beach ports.",
    },
    {
        "name": "TKK Custom Brokers",
        "url": "https://www.tkkcustombrokers.com",
        "snippet": "Licensed customs broker near Los Angeles serving importers with customs entry, clearance, and compliance services at LA/Long Beach ports.",
    },
    {
        "name": "NetCHB (Customs Entry Software)",
        "url": "https://www.netchb.com",
        "snippet": "NetCHB is a popular web-based customs entry software used by many small and mid-size customs brokers in LA. Many Chinese-owned CHBs use NetCHB for filing entries with CBP.",
    },
]


def search_duckduckgo(query: str, num_results: int = 10) -> list[dict]:
    """Scrape DuckDuckGo HTML search results (more reliable than Google)."""
    results = []
    url = f"https://html.duckduckgo.com/html/?q={quote_plus(query)}"

    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        for r in soup.select("div.result, div.web-result"):
            link_tag = r.select_one("a.result__a")
            snippet_tag = r.select_one("a.result__snippet, div.result__snippet")

            if link_tag:
                href = link_tag.get("href", "")
                title = link_tag.get_text(strip=True)
                snippet = snippet_tag.get_text(strip=True) if snippet_tag else ""

                if href and title and "duckduckgo.com" not in href:
                    results.append({
                        "name": title,
                        "url": href,
                        "snippet": snippet,
                    })
                    if len(results) >= num_results:
                        break
    except Exception as e:
        print(f"  [!] DuckDuckGo search failed for '{query}': {e}")

    return results


def search_google(query: str, num_results: int = 10) -> list[dict]:
    """Scrape Google search results for a query."""
    results = []
    url = "https://www.google.com/search"
    params = {"q": query, "num": num_results, "hl": "en"}

    try:
        session = requests.Session()
        session.headers.update(HEADERS)
        resp = session.get(url, params=params, timeout=15)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        for g in soup.select("div.g, div[data-hveid]"):
            link_tag = g.select_one("a[href^='http']")
            title_tag = g.select_one("h3")
            snippet_tag = g.select_one("div.VwiC3b, span.aCOpRe, div[data-sncf]")

            if link_tag and title_tag:
                href = link_tag["href"]
                if "google.com" in href:
                    continue
                results.append({
                    "name": title_tag.get_text(strip=True),
                    "url": href,
                    "snippet": snippet_tag.get_text(strip=True) if snippet_tag else "",
                })
    except Exception as e:
        print(f"  [!] Google search failed for '{query}': {e}")

    return results


def search_combined(query: str, num_results: int = 10) -> list[dict]:
    """Try DuckDuckGo first, fall back to Google."""
    results = search_duckduckgo(query, num_results)
    if results:
        return results
    print("  [~] DuckDuckGo returned nothing, trying Google...")
    return search_google(query, num_results)


def extract_phones(text: str) -> list[str]:
    """Extract US phone numbers from text."""
    phones = set()
    for pattern in PHONE_PATTERNS:
        for match in pattern.findall(text):
            cleaned = re.sub(r"[^\d]", "", match)
            if len(cleaned) == 10:
                cleaned = f"({cleaned[:3]}) {cleaned[3:6]}-{cleaned[6:]}"
                phones.add(cleaned)
            elif len(cleaned) == 11 and cleaned.startswith("1"):
                cleaned = f"({cleaned[1:4]}) {cleaned[4:7]}-{cleaned[7:]}"
                phones.add(cleaned)
    return list(phones)


def extract_emails(text: str) -> list[str]:
    """Extract email addresses from text."""
    emails = set()
    for match in EMAIL_PATTERN.findall(text):
        lower = match.lower()
        if not any(lower.endswith(ext) for ext in [".png", ".jpg", ".gif", ".svg", ".css", ".js"]):
            emails.add(lower)
    return list(emails)


def has_chinese_text(text: str) -> bool:
    """Check if text contains Chinese characters."""
    return bool(CHINESE_CHAR_PATTERN.search(text))


def detect_chinese_indicators(soup: BeautifulSoup, text: str) -> dict:
    """Detect indicators that a business may be Chinese-owned."""
    indicators = {
        "has_chinese_text": has_chinese_text(text),
        "bilingual_mentioned": False,
        "chinese_names_found": [],
        "score": 0,
    }

    lower_text = text.lower()

    bilingual_keywords = [
        "bilingual", "chinese", "mandarin", "cantonese",
        "中文", "华人", "双语", "普通话", "粤语",
    ]
    for kw in bilingual_keywords:
        if kw in lower_text:
            indicators["bilingual_mentioned"] = True
            indicators["score"] += 1

    if indicators["has_chinese_text"]:
        indicators["score"] += 2

    chinese_surnames = [
        "wang", "li", "zhang", "liu", "chen", "yang", "huang", "zhao",
        "wu", "zhou", "xu", "sun", "ma", "zhu", "hu", "guo", "lin",
        "he", "luo", "zheng", "liang", "xie", "tang", "han", "cao",
        "feng", "deng", "peng", "zeng", "xiao", "tian", "dong", "pan",
        "yuan", "cai", "jiang", "yu", "du", "ye", "cheng", "wei",
        "su", "lu", "ding", "ren", "shen", "yao", "lu", "chang",
    ]
    name_pattern = re.compile(
        r"(?:CEO|founder|owner|president|director|manager|chief)\s*[:\-]?\s*"
        r"([A-Z][a-z]+\s+[A-Z][a-z]+)",
        re.IGNORECASE,
    )
    for match in name_pattern.findall(text):
        parts = match.strip().split()
        if len(parts) >= 2:
            last_name = parts[-1].lower()
            if last_name in chinese_surnames:
                indicators["chinese_names_found"].append(match.strip())
                indicators["score"] += 2

    return indicators


def detect_chinese_indicators_from_text(text: str) -> dict:
    """Detect Chinese indicators from plain text (no BeautifulSoup needed)."""
    indicators = {
        "has_chinese_text": has_chinese_text(text),
        "bilingual_mentioned": False,
        "chinese_names_found": [],
        "score": 0,
    }

    lower_text = text.lower()

    bilingual_keywords = [
        "bilingual", "chinese", "mandarin", "cantonese",
        "中文", "华人", "双语", "普通话", "粤语",
    ]
    for kw in bilingual_keywords:
        if kw in lower_text:
            indicators["bilingual_mentioned"] = True
            indicators["score"] += 1

    if indicators["has_chinese_text"]:
        indicators["score"] += 2

    chinese_surnames = [
        "wang", "li", "zhang", "liu", "chen", "yang", "huang", "zhao",
        "wu", "zhou", "xu", "sun", "ma", "zhu", "hu", "guo", "lin",
        "he", "luo", "zheng", "liang", "xie", "tang", "han", "cao",
        "feng", "deng", "peng", "zeng", "xiao", "tian", "dong", "pan",
        "yuan", "cai", "jiang", "yu", "du", "ye", "cheng", "wei",
        "su", "lu", "ding", "ren", "shen", "yao", "lu", "chang",
    ]
    name_pattern = re.compile(
        r"(?:CEO|founder|owner|president|director|manager|chief)\s*[:\-]?\s*"
        r"([A-Z][a-z]+\s+[A-Z][a-z]+)",
        re.IGNORECASE,
    )
    for match in name_pattern.findall(text):
        parts = match.strip().split()
        if len(parts) >= 2:
            last_name = parts[-1].lower()
            if last_name in chinese_surnames:
                indicators["chinese_names_found"].append(match.strip())
                indicators["score"] += 2

    return indicators


def scrape_company_website(url: str) -> dict:
    """Visit a company website and extract contact info and details."""
    info = {
        "phones": [],
        "emails": [],
        "description": "",
        "services": "",
        "chinese_indicators": {},
    }

    try:
        resp = requests.get(url, headers=HEADERS, timeout=15, allow_redirects=True)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        text = soup.get_text(separator=" ", strip=True)

        info["phones"] = extract_phones(text)
        info["emails"] = extract_emails(text)

        meta_desc = soup.find("meta", attrs={"name": "description"})
        if meta_desc and meta_desc.get("content"):
            info["description"] = meta_desc["content"].strip()

        services_keywords = ["services", "solutions", "what we do", "our services"]
        for tag in soup.find_all(["h1", "h2", "h3", "p", "div"]):
            tag_text = tag.get_text(strip=True).lower()
            if any(kw in tag_text for kw in services_keywords):
                parent = tag.find_parent()
                if parent:
                    service_text = parent.get_text(separator=" ", strip=True)[:500]
                    info["services"] = service_text
                    break

        if not info["services"]:
            paragraphs = soup.find_all("p")
            combined = " ".join(p.get_text(strip=True) for p in paragraphs[:5])
            info["services"] = combined[:500]

        info["chinese_indicators"] = detect_chinese_indicators(soup, text)

        for subpath in ["/about", "/contact", "/about-us", "/contact-us"]:
            try:
                sub_url = urljoin(url, subpath)
                sub_resp = requests.get(sub_url, headers=HEADERS, timeout=10, allow_redirects=True)
                if sub_resp.status_code == 200:
                    sub_soup = BeautifulSoup(sub_resp.text, "html.parser")
                    sub_text = sub_soup.get_text(separator=" ", strip=True)
                    info["phones"].extend(extract_phones(sub_text))
                    info["emails"].extend(extract_emails(sub_text))

                    sub_indicators = detect_chinese_indicators(sub_soup, sub_text)
                    info["chinese_indicators"]["score"] = max(
                        info["chinese_indicators"].get("score", 0),
                        sub_indicators["score"],
                    )
                    if sub_indicators["chinese_names_found"]:
                        info["chinese_indicators"]["chinese_names_found"].extend(
                            sub_indicators["chinese_names_found"]
                        )
                    if sub_indicators["has_chinese_text"]:
                        info["chinese_indicators"]["has_chinese_text"] = True
                    if sub_indicators["bilingual_mentioned"]:
                        info["chinese_indicators"]["bilingual_mentioned"] = True

                time.sleep(random.uniform(0.5, 1.5))
            except Exception:
                pass

        info["phones"] = list(set(info["phones"]))
        info["emails"] = list(set(info["emails"]))

    except Exception as e:
        print(f"  [!] Failed to scrape {url}: {e}")

    return info


def run_scraper_live(output_path: str = "companies.json") -> list[dict]:
    """Run the full scraping pipeline using search engines."""
    print("[*] Starting live scraper...")
    seen_urls = set()
    companies = []

    for query in SEARCH_QUERIES:
        print(f"\n[*] Searching: {query}")
        results = search_combined(query)
        print(f"    Found {len(results)} results")

        for result in results:
            url = result["url"]
            domain = urlparse(url).netloc

            if domain in seen_urls:
                continue
            seen_urls.add(domain)

            print(f"  [>] Scraping: {result['name']} ({url})")
            site_info = scrape_company_website(url)

            chinese_score = site_info["chinese_indicators"].get("score", 0)

            company = {
                "name": result["name"],
                "website": url,
                "snippet": result["snippet"],
                "phones": site_info["phones"],
                "emails": site_info["emails"],
                "description": site_info["description"] or result["snippet"],
                "services": site_info["services"],
                "location": "Los Angeles, CA",
                "likely_chinese_owned": chinese_score >= 2,
                "chinese_indicators": site_info["chinese_indicators"],
            }
            companies.append(company)

            time.sleep(random.uniform(1.0, 3.0))

    return companies


def run_scraper_seed(output_path: str = "companies.json") -> list[dict]:
    """Use seed data + attempt to scrape actual websites for contact info."""
    print("[*] Starting scraper with seed data...")
    print(f"    {len(SEED_COMPANIES)} seed companies loaded")
    companies = []

    for i, seed in enumerate(SEED_COMPANIES):
        print(f"\n  [{i+1}/{len(SEED_COMPANIES)}] {seed['name']}")
        combined_text = f"{seed['name']} {seed['snippet']}"
        indicators = detect_chinese_indicators_from_text(combined_text)

        # Try to scrape the actual website for real contact info
        site_info = {"phones": [], "emails": [], "description": "", "services": ""}
        print(f"    Scraping {seed['url']}...")
        try:
            resp = requests.get(seed["url"], headers=HEADERS, timeout=10, allow_redirects=True)
            if resp.status_code == 200:
                soup = BeautifulSoup(resp.text, "html.parser")
                text = soup.get_text(separator=" ", strip=True)
                site_info["phones"] = extract_phones(text)
                site_info["emails"] = extract_emails(text)

                meta_desc = soup.find("meta", attrs={"name": "description"})
                if meta_desc and meta_desc.get("content"):
                    site_info["description"] = meta_desc["content"].strip()

                paragraphs = soup.find_all("p")
                combined = " ".join(p.get_text(strip=True) for p in paragraphs[:5])
                site_info["services"] = combined[:500]

                web_indicators = detect_chinese_indicators(soup, text)
                indicators["score"] = max(indicators["score"], web_indicators["score"])
                if web_indicators["chinese_names_found"]:
                    indicators["chinese_names_found"].extend(web_indicators["chinese_names_found"])
                if web_indicators["has_chinese_text"]:
                    indicators["has_chinese_text"] = True
                if web_indicators["bilingual_mentioned"]:
                    indicators["bilingual_mentioned"] = True

                print(f"    Found {len(site_info['phones'])} phones, {len(site_info['emails'])} emails")
            else:
                print(f"    HTTP {resp.status_code} — using seed data only")
        except Exception as e:
            print(f"    Could not reach website: {e}")
            print(f"    Using seed data only")

        company = {
            "name": seed["name"],
            "website": seed["url"],
            "snippet": seed["snippet"],
            "phones": site_info["phones"],
            "emails": site_info["emails"],
            "description": site_info["description"] or seed["snippet"],
            "services": site_info["services"] or seed["snippet"],
            "location": "Los Angeles, CA",
            "likely_chinese_owned": indicators["score"] >= 2,
            "chinese_indicators": indicators,
        }
        companies.append(company)

        time.sleep(random.uniform(0.5, 1.5))

    return companies


def run_scraper(output_path: str = "companies.json", use_seed: bool = False) -> list[dict]:
    """Run the scraping pipeline.

    Args:
        output_path: Where to save the JSON output.
        use_seed: If True, use built-in seed data instead of live search.
    """
    if use_seed:
        companies = run_scraper_seed(output_path)
    else:
        # Try live search first
        companies = run_scraper_live(output_path)

        # If live search found nothing, fall back to seed data
        if not companies:
            print("\n[!] Live search returned no results (search engines may be blocking).")
            print("[*] Falling back to seed data...")
            companies = run_scraper_seed(output_path)

    print(f"\n[*] Scraped {len(companies)} unique companies")
    print(f"    Chinese-owned (likely): {sum(1 for c in companies if c['likely_chinese_owned'])}")

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(companies, f, indent=2, ensure_ascii=False)
    print(f"[*] Saved to {output_path}")

    return companies


if __name__ == "__main__":
    use_seed = "--seed" in sys.argv
    run_scraper(use_seed=use_seed)
