from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import pandas as pd
import time
import re

# Lista de URLs de categorías
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

PAGE_SIZE = 24
MAX_PAGES = 50  # Seguridad: no pasar de 50 páginas por categoría

def slugify(url):
    """Crear un nombre de archivo seguro a partir de la URL"""
    name = url.split("/supermercado/")[-1].replace("/", "_")
    return re.sub(r"[^a-zA-Z0-9_]", "", name)

def close_popups(driver):
    time.sleep(2)
    try:
        driver.find_element(By.ID, "onetrust-accept-btn-handler").click()
        print("✅ Cookies cerradas")
        time.sleep(1)
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
            time.sleep(1)
            break
        except:
            continue

def scroll_until_done(driver, delay=0.4):
    last_count = 0
    while True:
        driver.execute_script("window.scrollBy(0, 2000);")
        time.sleep(delay)
        new_count = len(driver.find_elements(By.CSS_SELECTOR, "div.product-card__parent"))
        if new_count == last_count:
            break
        last_count = new_count

def scrap_category(driver, url):
    offset = 0
    page_num = 0
    category_items = []

    while page_num < MAX_PAGES:
        page_url = f"{url}?offset={offset}"
        print(f"\n➡ Accediendo: {page_url}")
        driver.get(page_url)
        time.sleep(2)

        if page_num == 0:
            close_popups(driver)

        try:
            WebDriverWait(driver, 15).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "div.product-card__parent"))
            )
        except:
            print("⚠ No se detectan productos → Fin de categoría")
            break

        scroll_until_done(driver)

        products = driver.find_elements(By.CSS_SELECTOR, "div.product-card__parent")
        print(f"📦 Productos detectados en página {page_num+1}: {len(products)}")

        for card in products:
            def safe(selector):
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

            category_items.append({
                "category_url": url,
                "name": name,
                "price": price,
                "price_unit": price_unit,
                "offer": offers
            })

        # Comprobar botón siguiente
        try:
            next_btn = driver.find_element(By.CSS_SELECTOR, "span.pagination__next")
            if "pagination__next--disabled" in next_btn.get_attribute("class"):
                print("✅ Última página alcanzada en esta categoría")
                break
        except:
            print("⚠ No se detecta botón siguiente → Fin de categoría")
            break

        offset += PAGE_SIZE
        page_num += 1
        time.sleep(1)

    return category_items

def scrap_all():
    options = Options()
    # options.add_argument("--headless")
    driver = webdriver.Chrome(options=options)

    for url in URLS:
        print(f"\n===== INICIANDO SCRAP DE CATEGORÍA: {url} =====")
        items = scrap_category(driver, url)
        if items:
            df = pd.DataFrame(items)
            filename = f"carrefour_{slugify(url)}.csv"
            df.to_csv(filename, index=False, encoding="utf-8-sig")
            print(f"✅ CSV generado: {filename} (Total productos: {len(df)})")
        else:
            print("⚠ No se generó CSV → sin productos")

    driver.quit()
    print("\n✅ SCRAP COMPLETADO")

if __name__ == "__main__":
    scrap_all()
