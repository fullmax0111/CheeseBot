from dotenv import load_dotenv # Import the dotenv library
import os
from pinecone import Pinecone
import openai
import json
load_dotenv()

PINECONE_API_KEY = os.environ.get("PINECONE_API_KEY")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")

openai.api_key = OPENAI_API_KEY

pc = Pinecone(api_key=PINECONE_API_KEY)

index_name = "cheese-chatbot"
index = pc.Index(index_name)


def generate_search_query(user_input: str):
    with open("../prompt/system.txt",'r') as f:
        search_prompt =  f.read()
    prompt = f"""
    Based on this user query: "{user_input}"
    {search_prompt}
    """
    
    response = openai.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": "You are a search query optimization assistant."},
            {"role": "user", "content": prompt}
        ],
        response_format={"type": "json_object"}
    )
    
    return response.choices[0].message.content
def perform_hybrid_search(search_params):
    search_params=json.loads(search_params)

    vector_query = search_params.get("vector_query", "")
    metadata_filters = search_params.get("metadata_filters", {})
    top_k = search_params.get("top_k", 10)

    dense_query_embedding = pc.inference.embed(
        model="llama-text-embed-v2",
        inputs=vector_query,
        parameters={"input_type": "query", "truncate": "END"}
    )

    sparse_query_embedding = pc.inference.embed(
        model="pinecone-sparse-english-v0",
        inputs=vector_query,
        parameters={"input_type": "query", "truncate": "END"}
    )

    filter_dict = {}
    for key, value in metadata_filters.items():
        if isinstance(value, dict) and ("min" in value or "max" in value):
            range_filter = {}
            if "min" in value:
                range_filter["$gte"] = value["min"]
            if "max" in value:
                range_filter["$lte"] = value["max"]
            filter_dict[key] = range_filter
        else:
            filter_dict[key] = value
    query_response = index.query(
        namespace="hybrid-namespace",
        top_k=top_k,
        vector=dense_query_embedding.data[0]['values'],
        sparse_vector={'indices': sparse_query_embedding.data[0]['sparse_indices'], 'values': sparse_query_embedding.data[0]['sparse_values']},
        include_values=False,
        # filter=filter_dict,
        include_metadata=True
    )

    
    return query_response.matches




def generate_response(user_query, search_results, search_params):
    """Generate a natural language response to the user's query based on search results"""
    
    results_summary = []
    for i, product in enumerate(search_results[:5]):
        result = {
            "name": product.metadata.get("product_name", "Unnamed product"),
            "brand": product.metadata.get("brand", "Unknown brand"),
            "price": product.metadata.get("price", "Price not available"),
            "weight": product.metadata.get("weight", "Weight not available"),
            "dimensions": product.metadata.get("dimensions", "Dimensions not available"),
            "categories": product.metadata.get("categories", "Category not available"),
            "image_url": product.metadata.get("image_url", "Image not available"),
            "description": product.metadata.get("description", "Description not available"),
            "link": product.metadata.get("product_detail_url", "Link not available"),
            "brand":product.metadata.get("brand_supplier_detail", "Brand not available"),
            "sku":product.metadata.get("sku", "SKU not available"),
            "upc":product.metadata.get("upc", "UPC not available"),
            "product_code_from_url":product.metadata.get("product_code_from_url", "Product code not available"),
            "item_number_from_name":product.metadata.get("item_number_from_name", "Item number not available"),
            "quantity_package_info":product.metadata.get("quantity_package_info", "Quantity package info not available"),
            "detail_page_main_image_url":product.metadata.get("detail_page_main_image_url", "Detail page main image url not available"),
            "detail_page_main_image_alt":product.metadata.get("detail_page_main_image_alt", "Detail page main image alt not available"),
            "detail_page_thumbnail_images":product.metadata.get("detail_page_thumbnail_images", "Detail page thumbnail images not available"),
            "related_products_count":product.metadata.get("related_products_count", "Related products count not available"),
            "other_like_products_count":product.metadata.get("other_like_products_count", "Other like products count not available"),
            "related_products":product.metadata.get("related_products", "Related products not available"),
            "other_like_products":product.metadata.get("other_like_products", "Other like products not available"),
            "proposition_65_warning":product.metadata.get("proposition_65_warning", "Proposition 65 warning not available"),
            "table_caption":product.metadata.get("table_caption", "Table caption not available"),
            "unit_price":product.metadata.get("unit_price", "Unit price not available"),
            "relevance_score": product.score
        }
        results_summary.append(result)
    
    with open("../prompt/result.txt",'r') as f:
        result_prompt =  f.read()
    
    with open("../prompt/additional.txt",'r') as f:
        additional_data =  f.read()
        
    prompt = f"""
    Additional Data : "{additional_data}"
    
    User query: "{user_query}"
    
    Search parameters used:
    {json.dumps(search_params, indent=2)}
    
    Top search results:
    {json.dumps(results_summary, indent=2)}
    
    Total results found: {len(search_results)}

    {result_prompt}
    """

    with open('../prompt/role.txt','r') as f:
        content=f.read()
    
    response = openai.chat.completions.create(
        model="gpt-4o",
        messages=[
            {
                "role": "system",
                "content": content
             },
            {"role": "user", "content": prompt}
        ],
        temperature=0.7,
        max_tokens=800
    )
    
    return response.choices[0].message.content

def product_search_bot(user_query):
    """Main bot handler that processes user queries and returns product results with a natural language response"""
    
    search_params = generate_search_query(user_query)

    search_results = perform_hybrid_search(search_params)
    
    formatted_results = []
    for item in search_results:
        product = item.metadata
        product["score"] = item.score
        formatted_results.append(product)
    
    response_text = generate_response(user_query, search_results, search_params)
    
    return {
        "success": True,
        "response": response_text,
        "query_interpretation": search_params,
        "results": formatted_results,
        "result_count": len(formatted_results)
    }
        
while True:
    user_message = input("question:  ")

    bot_response = product_search_bot(user_message)

    if bot_response["success"]:
        print(bot_response["response"])
    else:
        print(bot_response["response"])