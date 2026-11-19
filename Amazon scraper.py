import random
import re
import time

import pandas as pd
from selenium import webdriver
from selenium.common.exceptions import NoSuchElementException, TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.edge.options import Options
from selenium.webdriver.edge.service import Service
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from webdriver_manager.microsoft import EdgeChromiumDriverManager

SEARCH_URL = "https://www.amazon.eg/s?k=mechanical+keyboard&page={page}"
TARGET = 100
MAX_PAGES = 12
KEYWORDS = ("keyboard", "كيبورد", "لوحة مفاتيح")
RESULT_SELECTOR = 'div[data-component-type="s-search-result"]'


def build_driver():
    options = Options()
    options.add_argument("--start-maximized")
    options.add_argument("--lang=en-US")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)
    options.add_argument(r"--user-data-dir=C:\selenium_edge_profile")

    driver = webdriver.Edge(
        service=Service(EdgeChromiumDriverManager().install()), options=options
    )
    driver.execute_cdp_cmd(
        "Page.addScriptToEvaluateOnNewDocument",
        {
            "source": "Object.defineProperty(navigator, 'webdriver', {get: () => undefined});"
        },
    )
    return driver


def is_blocked(driver):
    html = driver.page_source.lower()
    return (
        "validatecaptcha" in html
        or "enter the characters you see" in html
        or "robot check" in driver.title.lower()
        or "api-services-support@amazon" in html
    )


def handle_block(driver):
    print("\n[!] Amazon is showing a CAPTCHA / block page.")
    input("Solve the CAPTCHA manually in the browser, then press Enter to continue... ")
    time.sleep(random.uniform(2, 4))
    return not is_blocked(driver)


def human_scroll(driver):
    height = driver.execute_script("return document.body.scrollHeight")
    pos = 0
    while pos < height:
        pos += random.randint(350, 700)
        driver.execute_script(f"window.scrollTo(0, {pos});")
        time.sleep(random.uniform(0.4, 1.1))
        height = driver.execute_script("return document.body.scrollHeight")


def text_of(el):
    return (el.get_attribute("textContent") or "").strip()


def parse_card(card):
    asin = card.get_attribute("data-asin")
    if not asin:
        return None

    try:
        name = text_of(card.find_element(By.CSS_SELECTOR, "h2 span"))
    except NoSuchElementException:
        return None
    if not name or not any(k in name.lower() for k in KEYWORDS):
        return None

    price = None
    try:
        raw = text_of(card.find_element(By.CSS_SELECTOR, "span.a-price span.a-offscreen"))
        cleaned = re.sub(r"[^\d.]", "", raw.replace(",", ""))
        price = float(cleaned) if cleaned else None
    except (NoSuchElementException, ValueError):
        pass

    rating = None
    try:
        raw = text_of(card.find_element(By.CSS_SELECTOR, "span.a-icon-alt"))
        m = re.search(r"\d+(\.\d+)?", raw)
        rating = float(m.group()) if m else None
    except NoSuchElementException:
        pass

    return {
        "ASIN": asin,
        "Product Name": name,
        "Price (EGP)": price,
        "Rating": rating,
        "Product Link": f"https://www.amazon.eg/dp/{asin}",
    }


def scrape_amazon():
    driver = build_driver()
    products = {}

    try:
        for page in range(1, MAX_PAGES + 1):
            if len(products) >= TARGET:
                break

            driver.get(SEARCH_URL.format(page=page))
            time.sleep(random.uniform(3, 6))

            if is_blocked(driver) and not handle_block(driver):
                print("Still blocked. Stopping and saving what was collected.")
                break

            try:
                WebDriverWait(driver, 15).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, RESULT_SELECTOR))
                )
            except TimeoutException:
                print(f"Page {page}: no results found (or selectors changed). Stopping.")
                break

            human_scroll(driver)

            before = len(products)
            for card in driver.find_elements(By.CSS_SELECTOR, RESULT_SELECTOR):
                item = parse_card(card)
                if item and item["ASIN"] not in products:
                    products[item["ASIN"]] = item
                if len(products) >= TARGET:
                    break

            print(f"Page {page}: +{len(products) - before} | total = {len(products)}")
            time.sleep(random.uniform(4, 9))

    except Exception as e:
        print(f"Error: {e}")
    finally:
        driver.quit()

    return list(products.values())[:TARGET]


if __name__ == "__main__":
    results = scrape_amazon()

    if results:
        df = pd.DataFrame(results)

        for path, writer in (
            ("amazon_keyboards.xlsx", lambda p: df.to_excel(p, index=False, engine="openpyxl")),
            ("amazon_keyboards.csv", lambda p: df.to_csv(p, index=False, encoding="utf-8-sig")),
        ):
            try:
                writer(path)
            except PermissionError:
                fallback = path.replace("amazon_keyboards", f"amazon_keyboards_{int(time.time())}")
                writer(fallback)
                print(f"{path} is open. Saved to {fallback} instead.")

        print(f"Saved {len(df)} items.")
        print(df.head())
    else:
        print("No data extracted.")