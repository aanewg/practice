import re
import json
import random
from datetime import datetime
from playwright.sync_api import sync_playwright
from playwright_stealth import Stealth
from bs4 import BeautifulSoup

CHROME_PATH = r"C:\Program Files\Google\Chrome\Application\chrome.exe"

results = []

def scrape_target():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
        page = context.new_page()
        print("Scraping Target...")
        page.goto("https://www.target.com/s?searchTerm=dyson+vacuum", timeout=60000, wait_until="domcontentloaded")
        page.wait_for_timeout(5000)
        soup = BeautifulSoup(page.content(), "html.parser")
        browser.close()

        # Get all product links with /p/ in the URL
        seen_urls = set()
        links = soup.find_all("a", href=True)
        product_links = [a for a in links if "/p/" in a.get("href", "") and a.get_text(strip=True)]
        
        for a in product_links:
            name = a.get_text(strip=True)
            href = "https://www.target.com" + a["href"].split("#")[0]  # remove #lnk=sametab
            if href in seen_urls or not name:
                continue
            seen_urls.add(href)
            
            # Try to find price in the surrounding HTML
            parent = a.parent
            price = "See site"
            for _ in range(5):  # walk up 5 levels
                if parent is None:
                    break
                price_match = re.search(r'\$[\d,]+\.?\d*', parent.get_text())
                if price_match:
                    price = price_match.group()
                    break
                parent = parent.parent

            # Skip non-Dyson products, toys, protection plans, and non-vacuum items
            name_lower = name.lower()
            if "dyson" not in name_lower:
                continue
            if any(skip in name_lower for skip in ["toy", "protection plan", "allstate", "stars with", "ratings"]):
                continue

            results.append({
                "site": "Target",
                "name": name[:80],
                "price": price,
                "url": href,
                "timestamp": datetime.now().isoformat()
            })

def scrape_ebay():
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--disable-blink-features=AutomationControlled"]
        )
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 800}
        )
        page = context.new_page()
        page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        print("Scraping eBay...")
        page.goto("https://www.ebay.com/sch/i.html?_nkw=dyson+vacuum", timeout=60000, wait_until="domcontentloaded")
        try:
            page.wait_for_selector(".s-item__link", timeout=15000)
        except:
            pass
        page.wait_for_timeout(3000)
        soup = BeautifulSoup(page.content(), "html.parser")
        browser.close()

        listings = soup.select(".s-card")
        for item in listings:
            name_tag = item.select_one(".s-card__title")
            price_tag = item.select_one(".s-card__price")
            link_tags = item.select("a[href]")
            name = name_tag.get_text(strip=True) if name_tag else None
            price = price_tag.get_text(strip=True) if price_tag else None
            url = next((a.get("href") for a in link_tags if "/itm/" in a.get("href", "")), None)
            if name and price and url and "Shop on eBay" not in name:
                results.append({
                    "site": "eBay",
                    "name": name[:80],
                    "price": price,
                    "url": url,
                    "timestamp": datetime.now().isoformat()
                })

def scrape_bestbuy():
    with sync_playwright() as p:
        browser = p.chromium.launch(
            executable_path=CHROME_PATH,
            headless=False,
            args=["--disable-blink-features=AutomationControlled"]
        )
        context = browser.new_context(
            viewport={"width": 1280, "height": 900},
            locale="en-US",
            timezone_id="America/New_York",
            extra_http_headers={"Accept-Language": "en-US,en;q=0.9"},
            no_viewport=False,
        )
        page = context.new_page()
        Stealth().use_sync(page)
        print("Scraping Best Buy...")

        # Land on homepage first like a real user
        page.goto("https://www.bestbuy.com", timeout=60000, wait_until="domcontentloaded")
        page.wait_for_timeout(random.randint(1500, 2500))

        # Move mouse around naturally before navigating
        page.mouse.move(random.randint(200, 800), random.randint(100, 400))
        page.wait_for_timeout(random.randint(400, 800))

        # Navigate to search results
        page.goto("https://www.bestbuy.com/site/searchpage.jsp?st=dyson+vacuum", timeout=90000, wait_until="domcontentloaded")

        # Wait for real product cards (not skeleton placeholders)
        try:
            page.wait_for_function(
                "document.querySelectorAll(\"a[href*='bestbuy.com/product']\").length >= 10",
                timeout=30000
            )
        except:
            pass

        # Scroll slowly like a human reading results
        for _ in range(10):
            page.mouse.move(random.randint(300, 900), random.randint(200, 700))
            page.evaluate(f"window.scrollBy(0, {random.randint(300, 600)})")
            page.wait_for_timeout(random.randint(500, 1000))

        # Final wait for any late-loading cards
        try:
            page.wait_for_function(
                "document.querySelectorAll(\"a[href*='bestbuy.com/product']\").length >= 20",
                timeout=10000
            )
        except:
            pass
        page.wait_for_timeout(2000)

        soup = BeautifulSoup(page.content(), "html.parser")
        browser.close()

    seen = set()
    cards = soup.select(".product-list-item")
    for card in cards:
        link_tags = card.select("a[href*='bestbuy.com/product']")
        name = next((a.get_text(strip=True) for a in link_tags if a.get_text(strip=True)), None)
        href = link_tags[0].get("href") if link_tags else None
        if not href or href in seen:
            continue
        seen.add(href)
        price_match = re.search(r'\$[\d,]+\.?\d*', card.get_text())
        price = price_match.group() if price_match else "See site"
        if name and href:
            results.append({
                "site": "Best Buy",
                "name": name[:80],
                "price": price,
                "url": href,
                "timestamp": datetime.now().isoformat()
            })

def run_all():
    global results
    results = []
    for func, name in [(scrape_target, "Target"), (scrape_ebay, "eBay"), (scrape_bestbuy, "Best Buy")]:
        try:
            func()
            count = len([r for r in results if r['site'] == name])
            print(f"  OK Found {count} products on {name}")
        except Exception as e:
            print(f"  ERROR on {name}: {e}")

    with open("prices.json", "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nDone! Saved {len(results)} total products to prices.json")

run_all()