import requests
from bs4 import BeautifulSoup
import json
from urllib.parse import urljoin, urlparse, parse_qs, unquote
import time
import concurrent.futures
from concurrent.futures import ThreadPoolExecutor
import threading
import os

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options

BASE_APP_URL = "https://shop.kimelo.com/"
MAX_WORKERS = 5
thread_local = threading.local()

def get_actual_image_url(img_tag_src):
    """Helper function to extract the actual image URL from Next.js image sources."""
    if not img_tag_src:
        return None
    if img_tag_src.startswith('/_next/image'):
        parsed_img_src = urlparse(img_tag_src)
        query_params = parse_qs(parsed_img_src.query)
        if 'url' in query_params and query_params['url']:
            image_url_encoded = query_params['url'][0]
            return unquote(image_url_encoded)
    return urljoin(BASE_APP_URL, img_tag_src)

def get_driver():
    if not hasattr(thread_local, "driver"):
        options = Options()
        options.headless = True
        options.add_argument("--window-size=1920,1200")
        options.add_argument("--headless")
        thread_local.driver = webdriver.Chrome(options=options)
    return thread_local.driver

def scrape_product_detail_page(detail_url, headers):
    product_details = {}
    print(f"    Fetching detail page: {detail_url}")

    driver = get_driver()


    driver.get(detail_url)
    wait = WebDriverWait(driver, 10)
    try:

        slick_slider = wait.until(
            EC.presence_of_element_located((By.CLASS_NAME, "slick-slider"))
        )

        wait.until(
            EC.presence_of_element_located((By.CLASS_NAME, "slick-initialized"))
        )
    except Exception as e:
        print(f"    Warning: Could not find slick slider: {e}")
    

    detail_soup = BeautifulSoup(driver.page_source, 'html.parser')
    

    slick_slider = detail_soup.find('div', class_='slick-slider slick-initialized')
    other_like_products=[]
    if slick_slider:
        for a_tag in slick_slider.find_all('a', class_='chakra-card group css-5pmr4x'):
            other_like_products.append(BASE_APP_URL+a_tag.get('href'))

    else:
        print("Slick slider not found in the parsed HTML")
    

    detail_soup = BeautifulSoup(driver.page_source, 'html.parser')

    first_part_container = detail_soup.find('div', class_='css-wpcv6r')


    if first_part_container:
        name_tag_detail = first_part_container.find('h1', class_='css-18j379d')
        if name_tag_detail:
            full_name_detail = name_tag_detail.text.strip()
            name_parts = full_name_detail.split(' - ')
            if len(name_parts) > 1 and name_parts[-1].isdigit():
                product_details['product_name_detail'] = ' - '.join(name_parts[:-1]).strip()
                product_details['item_number_from_name'] = name_parts[-1].strip()
            else:
                product_details['product_name_detail'] = full_name_detail
        
        brand_tag_detail = first_part_container.find('p', class_='css-drbcjm')
        if brand_tag_detail:
            product_details['brand_supplier_detail'] = brand_tag_detail.text.strip()

        breadcrumb_list = first_part_container.find('ol', class_='chakra-breadcrumb__list')
        if breadcrumb_list:
            categories = [
                a.text.strip() for a in breadcrumb_list.find_all('a', class_='chakra-breadcrumb__link')
            ]
            product_details['categories'] = " / ".join(categories) if categories else None

    main_image_panel = detail_soup.find('div', role='tabpanel', class_='chakra-tabs__tab-panel')
    if main_image_panel:
        img_tag_detail = main_image_panel.find('img') 
        if img_tag_detail:
             product_details['detail_page_main_image_url'] = get_actual_image_url(img_tag_detail.get('src'))
             product_details['detail_page_main_image_alt'] = img_tag_detail.get('alt', '').strip()


    thumbnail_list_container = detail_soup.find('div', class_='chakra-tabs__tablist', role='tablist')
    if thumbnail_list_container:
        thumbnail_images = []

        thumbnail_buttons = thumbnail_list_container.find_all('button', class_='chakra-tabs__tab')
        for button in thumbnail_buttons:
            img_tag_thumb = button.find('img')
            if img_tag_thumb and img_tag_thumb.get('src'):
                thumb_url = get_actual_image_url(img_tag_thumb.get('src'))
                if thumb_url:
                    thumbnail_images.append({
                        "url": thumb_url,
                        "alt": img_tag_thumb.get('alt', '').strip()
                    })
        if thumbnail_images:
            product_details['detail_page_thumbnail_images'] = thumbnail_images


    info_block = detail_soup.find('div', class_="css-ahthbn")
    if info_block:
        p_tags_for_sku_upc = info_block.find_all('p', class_='css-0') 
        for p_tag in p_tags_for_sku_upc:
            text_content = p_tag.get_text(separator=" ", strip=True) 
            b_tag_value = p_tag.find('b', class_='css-0') 
            value = b_tag_value.text.strip() if b_tag_value else None

            if value:
                if text_content.startswith("SKU:"):
                    product_details['sku'] = value
                elif text_content.startswith("UPC:"):
                    product_details['upc'] = value
        
        table_container = info_block.find('div', class_='chakra-table__container')
        if table_container:
            table = table_container.find('table', class_='chakra-table')
            if table:
                tbody = table.find('tbody')
                if tbody:
                    rows = tbody.find_all('tr', class_='css-0')
                    if len(rows) >= 1:
                        td_item = rows[0].find('td', class_='css-1eyncsv')
                        if td_item: product_details['quantity_package_info'] = td_item.text.strip()
                    if len(rows) >= 2:
                        td_dims = rows[1].find('td', class_='css-1eyncsv')
                        if td_dims: product_details['dimensions'] = td_dims.text.strip()
                    if len(rows) >= 3:
                        td_weight = rows[2].find('td', class_='css-1eyncsv')
                        if td_weight: product_details['weight'] = td_weight.text.strip()
                
                caption = table.find('caption', class_='css-aqesej')
                if caption:
                    product_details['table_caption'] = caption.text.strip()

        prop65_warning_text = info_block.find('p',class_='css-dw5ttn')

        product_details['proposition_65_warning'] = prop65_warning_text.text.strip()


    if 'sku' not in product_details and product_details.get('item_number_from_name'):
        product_details['sku'] = product_details['item_number_from_name']

    related_products=[]
    for related_product_detail_url in detail_soup.find('div',class_='css-1811skr').find_all('a', class_='chakra-card group css-5pmr4x'):
        related_products.append(BASE_APP_URL+related_product_detail_url.get('href'))
    product_details['related_products'] = related_products

    product_details['other_like_products'] = other_like_products

    return product_details


def scrape_listing_page(url, headers):

    products_on_this_page = []
    print(f"Fetching listing page: {url}")
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        print(f"Error fetching listing page {url}: {e}")
        return []

    soup = BeautifulSoup(response.content, 'html.parser')
    product_cards = soup.find_all('a', class_='chakra-card group css-5pmr4x')

    if not product_cards:
        return []

    for card_link_tag in product_cards:
        product_info = {} 

        relative_link = card_link_tag.get('href')
        product_info['product_detail_url'] = urljoin(BASE_APP_URL, relative_link) if relative_link else None

        card_body = card_link_tag.find('div', class_='css-1idwstw')
        if not card_body:
            continue
        
        img_tag_listing = card_body.find('img')
        product_info['image_url'] = get_actual_image_url(img_tag_listing.get('src')) if img_tag_listing else None
        
        name_tag_listing = card_body.find('p', class_='css-pbtft')
        product_info['product_name'] = name_tag_listing.text.strip() if name_tag_listing else "N/A"
        
        if relative_link:
            try:
                code_from_url = relative_link.strip('/').split('/')[-1]
                if code_from_url.isdigit():
                    product_info['product_code_from_url'] = code_from_url
            except: pass 

        brand_tag_listing = card_body.find('p', class_='css-w6ttxb')
        product_info['brand'] = brand_tag_listing.text.strip() if brand_tag_listing else "N/A"

        price_tag_listing = card_body.find('b', class_='css-1vhzs63')
        product_info['price'] = price_tag_listing.text.strip() if price_tag_listing else "N/A"

        unit_price_tag_listing = card_body.find('span', class_='css-ff7g47')
        product_info['unit_price'] = unit_price_tag_listing.text.strip() if unit_price_tag_listing else "N/A"

        if(product_info['price'] == "N/A"):
            product_info['status'] = "BACK IN STOCK SOON"
        else:
            product_info['status'] = "IN STOCK"

        products_on_this_page.append(product_info)

    return products_on_this_page

def save_to_json(data, filename, is_first=False):
    """Save data to JSON file, either creating new or appending to existing"""
    try:
        if is_first:
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump([data], f, ensure_ascii=False, indent=4)
        else:
            try:
                with open(filename, 'r', encoding='utf-8') as f:
                    existing_data = json.load(f)
            except (FileNotFoundError, json.JSONDecodeError):
                existing_data = []
            
            existing_data.append(data)
            
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(existing_data, f, ensure_ascii=False, indent=4)
                
    except Exception as e:
        print(f"Error saving to JSON: {e}")

def process_product_batch(product_batch, output_filename, is_first_batch=False):
    """Process a batch of products in parallel and save results incrementally"""
    results = []
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        future_to_product = {
            executor.submit(scrape_product_detail_page, product['product_detail_url'], common_headers): product 
            for product in product_batch
        }
        
        for i, future in enumerate(concurrent.futures.as_completed(future_to_product)):
            product = future_to_product[future]
            try:
                detailed_info = future.result()
                combined_info = {**product, **detailed_info}
                results.append(combined_info)
                
                is_first = is_first_batch and i == 0
                save_to_json(combined_info, output_filename, is_first)
                
                print(f"Completed and saved details for: {product.get('product_name', 'N/A')}")
            except Exception as e:
                print(f"Error processing product {product.get('product_name', 'N/A')}: {e}")

                is_first = is_first_batch and i == 0
                save_to_json(product, output_filename, is_first)
                results.append(product)
    
    return results

if __name__ == '__main__':
    base_department_url = "https://shop.kimelo.com/department/cheese/3365"
    output_filename = "kimelo_cheese_detailed_data_all_pages.json"
    
    page_number = 1
    
    common_headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }

    print("Starting scraper...")
    print(f"Using {MAX_WORKERS} parallel workers for detail page scraping")
    print(f"Results will be saved incrementally to {output_filename}")

    all_product_summaries = []
    while True:
        if page_number == 1:
            current_listing_url = base_department_url
        else:
            current_listing_url = f"{base_department_url}?page={page_number}"
            
        summaries_on_page = scrape_listing_page(current_listing_url, common_headers)
        
        if summaries_on_page:
            print(f"Found {len(summaries_on_page)} product summaries on listing page {page_number}.")
            all_product_summaries.extend(summaries_on_page)
            page_number += 1
            print(f"--- Delaying {1.5}s before next listing page ---")
            time.sleep(1.5)
        else:
            if page_number > 1:
                print(f"No more products found on page {page_number}. Moving to detail scraping.")
            else:
                print("No products found on the first page. Please check the URL.")
            break

    BATCH_SIZE = 10
    total_products = len(all_product_summaries)
    
    for i in range(0, total_products, BATCH_SIZE):
        batch = all_product_summaries[i:i + BATCH_SIZE]
        print(f"\nProcessing batch {i//BATCH_SIZE + 1} of {(total_products + BATCH_SIZE - 1)//BATCH_SIZE}")
        is_first_batch = (i == 0)
        process_product_batch(batch, output_filename, is_first_batch)

        if i + BATCH_SIZE < total_products:
            print("--- Delaying between batches ---")
            time.sleep(2)

    try:
        if hasattr(thread_local, "driver"):
            thread_local.driver.quit()
    except:
        pass

    try:
        with open(output_filename, 'r', encoding='utf-8') as f:
            final_data = json.load(f)
            print(f"\nTotal {len(final_data)} products scraped and saved to '{output_filename}'")
    except Exception as e:
        print(f"Error reading final count: {e}")