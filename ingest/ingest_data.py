import json
import os
from tqdm import tqdm
from dotenv import load_dotenv # Import the dotenv library

from pinecone import Pinecone
from pinecone import ServerlessSpec

load_dotenv()

PINECONE_API_KEY = os.environ.get("PINECONE_API_KEY")

UPSERT_BATCH_SIZE = 50

pc = Pinecone(api_key=PINECONE_API_KEY)

index_name = "cheese-chatbot"


pc = Pinecone(api_key=PINECONE_API_KEY)


if not pc.has_index(index_name):
    pc.create_index(
        name=index_name,
        vector_type="dense",
        dimension=1024,
        metric="dotproduct",
        spec=ServerlessSpec(
            cloud="aws",
            region="us-east-1"
        )
    )

def load_cheese_data(filepath="../scraper/kimelo_cheese_detailed_data_all_pages.json"):
    """Loads cheese data from a JSON file."""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        print(f"Successfully loaded {len(data)} cheese items from {filepath}")
        return data
    except FileNotFoundError:
        print(f"Error: File not found at {filepath}")
        return []
    except json.JSONDecodeError:
        print(f"Error: Could not decode JSON from {filepath}")
        return []

def create_even_more_detailed_semantic_text_chunk(item: dict) -> str:
    name = item.get('product_name_detail', item.get('product_name', ''))
    brand = item.get('brand_supplier_detail', item.get('brand', ''))
    
    categories_list = []
    categories_str_raw = item.get('categories', '')
    if categories_str_raw:
        categories_list = [cat.strip() for cat in categories_str_raw.split('/')]

    quantity_package_info = item.get('quantity_package_info', '')
    weight = item.get('weight', '')
    dimensions = item.get('dimensions', '')

    price = item.get('price', '')
    unit_price = item.get('unit_price', '')
    status = item.get('status', '')

    all_alt_texts = set() 
    main_alt = item.get('detail_page_main_image_alt', '')
    if main_alt:
        all_alt_texts.add(main_alt.strip())
    
    thumbnail_images = item.get('detail_page_thumbnail_images', [])
    if isinstance(thumbnail_images, list):
        for thumb in thumbnail_images:
            if isinstance(thumb, dict) and thumb.get('alt'):
                all_alt_texts.add(thumb.get('alt').strip())
    
    cleaned_alt_texts = set()
    sku_for_cleaning = str(item.get('sku', item.get('product_code_from_url', '')))
    
    for alt in all_alt_texts:
        temp_alt = alt

        if sku_for_cleaning and temp_alt.endswith(f"- {sku_for_cleaning}"):
            temp_alt = temp_alt.replace(f"- {sku_for_cleaning}", "").strip()
        if name and temp_alt.lower() == name.lower():
            continue
        if temp_alt: 
            cleaned_alt_texts.add(temp_alt)
    
    meaningful_alt_text_summary = ""
    if cleaned_alt_texts:
        alt_list_for_summary = list(cleaned_alt_texts)
        if len(alt_list_for_summary) > 3:
            alt_list_for_summary = alt_list_for_summary[:3] 
        meaningful_alt_text_summary = "Visual descriptions and alternative views suggest: " + "; ".join(alt_list_for_summary) + "."

    table_caption = item.get('table_caption', '')
    standard_caption = "Product information or packaging displayed may not be current or complete. *Actual weight may vary based on seasonality and other factors."
    
    prop_65_warning = item.get('proposition_65_warning', '')
    standard_prop_65 = "Warning: This product can expose you to chemicals including arsenic, which is known to the State of California to cause cancer. For more information, go to www.P65Warnings.ca.gov"

    chunk_parts = []

    if name and brand:
        chunk_parts.append(f"This featured product is '{name}', a quality offering from the distinguished brand {brand}.")
    elif name:
        chunk_parts.append(f"Introducing the product: '{name}'.")
    elif brand:
        chunk_parts.append(f"This item is from the brand {brand}.")

    if categories_list:
        category_description = f"It is classified under {categories_str_raw.replace(' / ', ', then ')}."
        chunk_parts.append(category_description)
        
        name_terms = [term.strip().lower() for term in name.replace('(4)','').split(',')] # Remove common package indicators
        type_descriptors = []
        for term in name_terms:
            if term and term != "cheese" and not term.isnumeric() and len(term) > 2:
                is_in_category = any(term in cat.lower() for cat in categories_list)
                if is_in_category or term in ["shredded", "sliced", "mild", "sharp", "fancy", "loaf", "cheddar", "mozzarella", "swiss", "provolone", "parmesan", "jack", "pepperjack"]: # common cheese descriptors and types
                    type_descriptors.append(term)
        
        if "cheese" in categories_list[0].lower() and type_descriptors:
            chunk_parts.append(f"Specifically, this is a {' '.join(type_descriptors)} cheese product.")
        elif "cheese" in categories_list[0].lower():
            chunk_parts.append("This is a cheese product.")

    physical_desc_parts = []
    if quantity_package_info:
        physical_desc_parts.append(f"it comes conveniently packaged as {quantity_package_info}")
    if weight:
        physical_desc_parts.append(f"with a net weight of {weight}")
    if dimensions and dimensions.lower().strip() not in ['l 1" x w 1" x h 1"', 'l 1" x w 1" x h 1"']: # Avoid overly generic/placeholder dimensions
        physical_desc_parts.append(f"and has approximate dimensions of {dimensions}")
    
    if physical_desc_parts:
        chunk_parts.append(f"Regarding its physical attributes, {', '.join(physical_desc_parts)}.")

    if meaningful_alt_text_summary:
        chunk_parts.append(meaningful_alt_text_summary)

    purchase_info_parts = []
    if price:
        purchase_info_parts.append(f"the current retail price is {price}")
    if unit_price:
        purchase_info_parts.append(f"which translates to a unit price of {unit_price}")
    if status:
        purchase_info_parts.append(f"and its current availability status is clearly marked as '{status}'")
    
    if purchase_info_parts:
        chunk_parts.append(f"For prospective buyers, {', '.join(purchase_info_parts)}.")

    if table_caption and table_caption.strip() != standard_caption.strip():
        chunk_parts.append(f"An important note regarding the product or packaging: \"{table_caption.strip()}\"")
    elif table_caption and table_caption.strip() == standard_caption.strip(): # If it's the standard one, just a generic mention
        chunk_parts.append("Please note that product information and packaging may be subject to change, and actual weights can vary.")

    if prop_65_warning and prop_65_warning.strip() != standard_prop_65.strip():
        chunk_parts.append(f"Safety Information: {prop_65_warning.strip()}")
    elif prop_65_warning and prop_65_warning.strip() == standard_prop_65.strip(): # If it's the standard one
        chunk_parts.append("This product is subject to California Proposition 65 chemical exposure warnings.")

    keywords = set()
    if name:
        for term in name.replace('(4)','').replace('-', ' ').split(','):
            cleaned_term = term.strip().lower()
            if cleaned_term and len(cleaned_term) > 2 and not cleaned_term.isnumeric():
                keywords.add(cleaned_term)
    if categories_list:
        for cat_item in categories_list:
            for term in cat_item.split(','):
                cleaned_term = term.strip().lower()
                if cleaned_term and len(cleaned_term) > 2:
                    keywords.add(cleaned_term)
    if brand:
        keywords.add(brand.lower())

    if len(keywords) > 1 and "cheese" in keywords:
        keywords.remove("cheese")
    
    if keywords:
        chunk_parts.append(f"Key characteristics and search terms for this item include: {', '.join(sorted(list(keywords)))}.")

    related_products_count = len(item.get("related_products", []))
    other_like_products_count = len(item.get("other_like_products", []))

    if related_products_count > 0 and other_like_products_count > 0:
        chunk_parts.append(f"This product is frequently viewed alongside {related_products_count} other related items and {other_like_products_count} similar product alternatives.")
    elif related_products_count > 0:
        chunk_parts.append(f"There are {related_products_count} related items that customers often consider with this product.")
    elif other_like_products_count > 0:
        chunk_parts.append(f"Explore {other_like_products_count} other similar product options available in our catalog.")

    final_chunk = " ".join(filter(None, chunk_parts))

    if not final_chunk.strip() or len(final_chunk.strip().split()) < 20: # Increased min word count for "detailed"
        fallback_parts = [name, brand, categories_str_raw, weight, quantity_package_info, status]
        fallback_text = ". ".join(filter(None, fallback_parts)) + "."
        return fallback_text if fallback_text.strip() and fallback_text.strip() != "." else "General cheese product. Further details unavailable."

    return final_chunk

def prepare_detailed_metadata(item: dict) -> dict:
    if item.get("price")!='N/A':
        price = float(item.get("price")[1:])
    else:
        price = None
    if item.get("unit_price")!='N/A':
        if(item.get("unit_price")[-1]=='f'):
            unit_price = float(item.get("unit_price")[1:-5])
        else:
            unit_price = float(item.get("unit_price")[1:-3])
    else:
        unit_price = None
    if item.get("weight")!='N/A':
        weight = float(item.get("weight")[:-3])
    else:
        weight = None
    metadata = {
        "product_detail_url": item.get("product_detail_url"),
        "image_url": item.get("image_url"),
        "detail_page_main_image_url": item.get("detail_page_main_image_url"),
        "product_name": item.get("product_name"),
        "product_name_detail": item.get("product_name_detail"),
        "brand": item.get("brand"),
        "brand_supplier_detail": item.get("brand_supplier_detail"),
        "price": price,
        "unit_price": unit_price,
        "status": item.get("status"),
        "categories": item.get("categories"),
        "sku": str(item.get("sku")) if item.get("sku") else None,
        "upc": str(item.get("upc")) if item.get("upc") else None,
        "product_code_from_url": item.get("product_code_from_url"),
        "item_number_from_name": item.get("item_number_from_name"),
        "quantity_package_info": item.get("quantity_package_info"),
        "dimensions": item.get("dimensions"),
        "weight": weight,
        "detail_page_main_image_alt": item.get("detail_page_main_image_alt"),
        "related_products_count": len(item.get("related_products", [])),
        "other_like_products_count": len(item.get("other_like_products", [])),

        "related_products": item.get("related_products", [])[:20],
        "other_like_products": item.get("other_like_products", [])[:20],
        "proposition_65_warning": item.get("proposition_65_warning"),
        "table_caption": item.get("table_caption")
    }

    return {k: v for k, v in metadata.items() if v is not None and v != ""}


def main():

    cheese_data_list = load_cheese_data()
    if not cheese_data_list:
        print("No data to process. Exiting.")
        return
    try:
        index = pc.Index(index_name)
        print(f"Connected to index '{index_name}'.")
        print(f"Index stats before upsert: {index.describe_index_stats()}")
    except Exception as e:
        print(f"Error connecting to Pinecone index '{index_name}': {e}")
        return
    all_metadata = []
    all_text_chunks = []
    
    for i, item in enumerate(tqdm(cheese_data_list, desc="Preparing Items")):
        vector_id = str(item.get('sku') or item.get('product_code_from_url') or f"item_{i}") # Fallback ID
        if not item.get('sku') and not item.get('product_code_from_url'):
            tqdm.write(f"Warning: Item {item.get('product_name', 'Unknown Name')} (index {i}) is missing a reliable ID. Using generated ID: {vector_id}.")

        text_chunk = create_even_more_detailed_semantic_text_chunk(item)
        metadata = prepare_detailed_metadata(item)
        metadata['_id'] = vector_id

        all_metadata.append(metadata)
        all_text_chunks.append(text_chunk)

    print("Embedding....")
    dense_embeddings = pc.inference.embed(
        model="llama-text-embed-v2",
        inputs=[d for d in all_text_chunks],
        parameters={"input_type": "passage", "truncate": "END"}
    )

    sparse_embeddings = pc.inference.embed(
        model="pinecone-sparse-english-v0",
        inputs=[d for d in all_text_chunks],
        parameters={"input_type": "passage", "truncate": "END"}
    )

    print("End Embedding...")

    index = pc.Index(index_name)

    records = []
    for d, de, se in zip(all_metadata, dense_embeddings, sparse_embeddings):
        records.append({
            "id": d['_id'],
            "values": de['values'],
            "sparse_values": {'indices': se['sparse_indices'], 'values': se['sparse_values']},
            "metadata": d
        })

    print("Upserting...")

    index.upsert(
        vectors=records,
        namespace="hybrid-namespace"
    )
        
    print(f"\n--- Indexing Complete ---")
    print(f"Final index stats: {index.describe_index_stats()}")

if __name__ == "__main__":

    main()