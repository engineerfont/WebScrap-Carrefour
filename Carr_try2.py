from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import pandas as pd
import time
import re
import random

# =============================
# CONFIG
# Llista de URLs d'on s'extraura info
# =============================

URLS = [
    "https://www.carrefour.es/supermercado/frescos/cat20002/c",
    "https://www.carrefour.es/supermercado/la-despensa/cat20001/c",
    "https://www.carrefour.es/supermercado/bebidas/cat20003/c",
    "https://www.carrefour.es/supermercado/limpieza-del-hogar/cat20005/c",
    "https://www.carrefour.es/supermercado/perfumeria-e-higiene/cat20004/c",
    "https://www.carrefour.es/supermercado/congelados/cat21449123/c",
    "https://www.carrefour.es/supermercado/bebe/cat20006/c",
    "https://www.carrefour.es/supermercado/parafarmacia/cat20008/c"
]

PAGE_SIZE = 24  # Nombre de productes per pàgina
MAX_PAGES = 50  #Límit de pàgines a recórrer per evitar loops infinits.
RETRIES = 3     # Nombre de reintents quan una pàgina no carrega

# =============================
# UTILS
# =============================

def slugify(url):
    """Generar noms de CSV"""
    name = url.split("/supermercado/")[-1].replace("/", "_")
    return re.sub(r"[^a-zA-Z0-9_]", "", name)


def wait_human(min_s=1, max_s=2.5):
    """Evitar sobrecarregar servidor → Pausa aleatoria."""
    time.sleep(random.uniform(min_s, max_s))


# =============================
# DRIVER
# =============================

def init_driver():
    """
    Crea i configura el navegador controlat per Selenium
    """
    options = Options()
    options.add_argument(
        "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    )

    return webdriver.Chrome(options=options)


# =============================
# POP-UPS
# =============================

def close_popups(driver):
    """Tancar cookies i altres pop-ups comuns."""
    wait_human()
    try:
        driver.find_element(By.ID, "onetrust-accept-btn-handler").click()
        print("✅ Cookies tancades")
    except:
        pass

    selectors = [
        ".wizard__body .icon-cross-thin",
        ".icon-cross-thin",
        ".c-modal__close",
        ".c-button--close",
        ".icon-close",
        ".modal-close"
    ]

    for s in selectors:
        try:
            btn = driver.find_element(By.CSS_SELECTOR, s)
            driver.execute_script("arguments[0].click();", btn)
            print(f"✅ Popup cerrado ({s})")
            break
        except:
            continue


# =============================
# SCROLL
# =============================

def scroll_until_done(driver, delay=0.4):
    """
    Desplaçament per carregar més productes (lazy loading).
    Si no hi han nous productes → parar.
    """
    last_count = 0
    while True:
        driver.execute_script("window.scrollBy(0, 2000);")
        wait_human()
        new_count = len(driver.find_elements(By.CSS_SELECTOR, "div.product-card__parent"))
        if new_count == last_count:
            break
        last_count = new_count


# =============================
# PRODUCT EXTRACTION
# =============================

def extract_product(card, url):
    """Extreu dades d'un producte individual.
       Si el producte forma part de la seccio ofertes  → ignorar.
    """

    # Ignorar productes dins de seccions ‘product-offers’
    try:
        card.find_element(By.XPATH, ".ancestor::div[contains(@class, 'product-offers')]")
        return None   # ⬅ producte NO vàlid
    except:
        pass    # no està dins → continua

    def safe(selector):
        """Lectura segura de text sense trencar camp."""
        try:
            return card.find_element(By.CSS_SELECTOR, selector).text.strip()
        except:
            return ""

    name = safe(".product-card__title")
    price = safe(".product-card__price")
    price_unit = safe(".product-card__price-per-unit")

    offers = ", ".join([
        o.text.strip()
        for o in card.find_elements(
            By.CSS_SELECTOR,
            ".product-card__badges-container-promotions .badge__name"
        )
    ])

    return {
        "category_url": url,
        "name": name,
        "price": price,
        "price_unit": price_unit,
        "offer": offers
    }


# =============================
# CATEGORY SCRAPING
# =============================

def scrap_category(driver, url):
    """Executa el procés complet sobre una categoria."""
    offset = 0
    page_num = 0
    items = []

    while page_num < MAX_PAGES:

        page_url = f"{url}?offset={offset}"
        print(f"\n➡ Accedeix: {page_url}")

        # Reintents si falla
        for attempt in range(RETRIES):
            try:
                driver.get(page_url)
                break
            except Exception as e:
                print(f"⚠ Error cargant web → reintent {attempt+1}/{RETRIES}")
                wait_human()
        else:
            print("❌ No s'ha pogut carregar la web → cancelada")
            return items

        wait_human()

        # Pop-ups nomes primer cop
        if page_num == 0:
            close_popups(driver)

        # Espera a que carreguin productes
        try:
            WebDriverWait(driver, 15).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "div.product-card__parent"))
            )
        except:
            print("⚠ No hi han productes → fi")
            break

        # Scroll per carregar tot
        scroll_until_done(driver)

        products = driver.find_elements(By.CSS_SELECTOR, "div.product-card__parent")
        print(f"📦 Productes detectads en la web {page_num+1}: {len(products)}")

        # Extreure cada producte
        for card in products:
            items.append(extract_product(card, url))

        # Detectar última pàgina
        try:
            next_btn = driver.find_element(By.CSS_SELECTOR, "span.pagination__next")
            if "pagination__next--disabled" in next_btn.get_attribute("class"):
                print("✅ Última pàgina assolida")
                break
        except:
            print("⚠ No s'ha detectat boto → fi")
            break

        # Salt a la següent pàgina
        offset += PAGE_SIZE
        page_num += 1
        wait_human()

    return items


# =============================
# MAIN
# =============================

def scrap_all():
    """Bucle principal: revisar todes les URLs."""
    driver = init_driver()

    for url in URLS:
        print(f"\n===== INICIANT SCRAP: {url} =====")
        items = scrap_category(driver, url)

        if items:
            df = pd.DataFrame(items)
            filename = f"carrefour_{slugify(url)}.csv"
            df.to_csv(filename, index=False, encoding="utf-8-sig")
            print(f"✅ CSV generat: {filename} (Total: {len(df)})")
        else:
            print("⚠ No s'ha generat CSV → sense productes")

    driver.quit()
    print("\n✅ SCRAP COMPLETAT")


if __name__ == "__main__":
    scrap_all()
