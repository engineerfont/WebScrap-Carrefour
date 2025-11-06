from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import pandas as pd
import time
import re
import random
from datetime import datetime

# =============================
# CONFIG
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

PAGE_SIZE = 24
MAX_PAGES = 50
RETRIES = 3


# =============================
# UTILS
# =============================

def slugify(url):
    """Genera el nombre de la categoría a partir de la URL (p.ej. 'bebe' o 'frescos')."""
    try:
        part = url.split("/supermercado/")[1].split("/")[0]
        part = re.sub(r"[^a-zA-Z0-9_-]", "", part)
        return part.strip().lower()
    except:
        return "categoria"

def wait_human(min_s=1, max_s=2.5):
    """Evita sobrecargar el servidor → pausa aleatoria."""
    time.sleep(random.uniform(min_s, max_s))


# =============================
# DRIVER
# =============================

def init_driver():
    """Crea y configura el navegador controlado por Selenium."""
    options = Options()
    options.add_argument(
        "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    )
    driver = webdriver.Chrome(options=options)
    driver.maximize_window()
    return driver


# =============================
# POP-UPS
# =============================

def close_popups(driver):
    """Cierra cookies y pop-ups comunes."""
    wait_human()
    try:
        driver.find_element(By.ID, "onetrust-accept-btn-handler").click()
        print("✅ Cookies aceptadas")
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
    """Desplazamiento para cargar más productos (lazy loading)."""
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

def read_products_from_page(driver):
    """Lee todos los productos visibles en la página actual."""
    try:
        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "div.product-card-list ul.product-card-list__list"))
        )
    except:
        print("⚠️ No se encontró la lista principal de productos.")
        return []

    wait_human(0.8, 1.2)
    lists = driver.find_elements(By.CSS_SELECTOR, "div.product-card-list")
    items = []

    for lst in lists:
        try:
            if "display: none" in (lst.get_attribute("style") or ""):
                continue

            cards = lst.find_elements(By.CSS_SELECTOR, "div.product-card__parent")
            for c in cards:
                try:
                    name = c.find_element(By.CSS_SELECTOR, ".product-card__title").text.strip()
                except:
                    name = ""
                try:
                    price = c.find_element(By.CSS_SELECTOR, ".product-card__price").text.strip()
                except:
                    price = ""
                try:
                    price_unit = c.find_element(By.CSS_SELECTOR, ".product-card__price-per-unit").text.strip()
                except:
                    price_unit = ""
                try:
                    offer = ", ".join([o.text.strip() for o in c.find_elements(By.CSS_SELECTOR, ".badge__name")])
                except:
                    offer = ""
                if name or price:
                    items.append({
                        "product_name": name,
                        "price": price,
                        "price_unit": price_unit,
                        "offer": offer
                    })
        except:
            continue

    print(f"✅ {len(items)} productos encontrados en la página actual")
    return items


# =============================
# CATEGORY SCRAPING
# =============================

def scrap_category(driver, url):
    """Ejecuta el scraping completo sobre una categoría."""
    offset = 0
    page_num = 0
    items = []

    while page_num < MAX_PAGES:
        page_url = f"{url}?offset={offset}"
        print(f"\n➡ Accediendo a: {page_url}")

        for attempt in range(RETRIES):
            try:
                driver.get(page_url)
                break
            except Exception as e:
                print(f"⚠️ Error cargando página → reintento {attempt+1}/{RETRIES}")
                wait_human()
        else:
            print("❌ No se pudo cargar la página → cancelado")
            return items

        wait_human()

        if page_num == 0:
            close_popups(driver)

        try:
            WebDriverWait(driver, 15).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "div.product-card__parent"))
            )
        except:
            print("⚠️ No hay productos → fin de la categoría")
            break

        scroll_until_done(driver)

        page_items = read_products_from_page(driver)
        for p in page_items:
            p["category_url"] = url
        items.extend(page_items)

        print(f"📦 Total acumulado: {len(items)} productos")

        try:
            next_btn = driver.find_element(By.CSS_SELECTOR, "span.pagination__next")
            if "pagination__next--disabled" in next_btn.get_attribute("class"):
                print("✅ Última página alcanzada")
                break
        except:
            print("⚠️ No se detectó botón de siguiente → fin")
            break

        offset += PAGE_SIZE
        page_num += 1
        wait_human()

    return items


# =============================
# MAIN
# =============================

def scrap_all():
    """Bucle principal: recorre todas las URLs y guarda un CSV por categoría."""
    driver = init_driver()

    for url in URLS:
        print(f"\n===== INICIANDO SCRAP: {url} =====")
        items = scrap_category(driver, url)

        if items:
            df = pd.DataFrame(items)
            category_name = slugify(url)
            date_str = datetime.now().strftime("%Y%m%d")
            filename = f"carrefour_{category_name}_{date_str}.csv"
            df.to_csv(filename, index=False, encoding="utf-8-sig")
            print(f"💾 CSV generado: {filename} (Total: {len(df)})")
        else:
            print("⚠️ No se ha generado CSV → sin productos")

    driver.quit()
    print("\n✅ SCRAP COMPLETADO")


if __name__ == "__main__":
    scrap_all()
