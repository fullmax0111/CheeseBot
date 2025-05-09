# --- START OF FILE hybrid_search.py ---

from dotenv import load_dotenv
import os
from pinecone import Pinecone
import openai
import json

# Load environment variables. This happens once when the module is imported.
load_dotenv()

PINECONE_API_KEY = os.environ.get("PINECONE_API_KEY")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")

# Global variables for clients, to be initialized
pc = None
index = None
_clients_initialized = False

def initialize_clients():
    """Initializes Pinecone and OpenAI clients. Returns True on success, False on failure."""
    global pc, index, openai, _clients_initialized

    if _clients_initialized:
        return True

    if not PINECONE_API_KEY:
        print("ERROR: PINECONE_API_KEY not found in environment variables.")
        return False
    if not OPENAI_API_KEY:
        print("ERROR: OPENAI_API_KEY not found in environment variables.")
        return False

    try:
        openai.api_key = OPENAI_API_KEY
        pc = Pinecone(api_key=PINECONE_API_KEY)
        index_name = "cheese-chatbot"  # Ensure this index exists
        index = pc.Index(index_name)
        _clients_initialized = True
        print("INFO: OpenAI and Pinecone clients initialized successfully.")
        return True
    except Exception as e:
        print(f"ERROR: Failed to initialize clients: {e}")
        _clients_initialized = False
        return False

def _get_prompt_path(filename):
    # Assumes 'prompt' directory is one level up from this script's directory.
    # E.g., if hybrid_search.py is in 'src/', prompts are in 'project_root/prompt/'
    # If hybrid_search.py is in project_root, and prompt/ is a subdir, change to "prompt/" + filename
    base_dir = os.path.dirname(os.path.abspath(__file__))
    prompt_path = os.path.join(base_dir, "..", "prompt", filename)
    if not os.path.exists(prompt_path):
        # Fallback: Try if 'prompt' is a subdirectory of where this script is
        prompt_path_alt = os.path.join(base_dir, "prompt", filename)
        if os.path.exists(prompt_path_alt):
            return prompt_path_alt
        print(f"Warning: Prompt file {filename} not found at {prompt_path} or {prompt_path_alt}")
        raise FileNotFoundError(f"Prompt file {filename} not found.")
    return prompt_path


def generate_search_query(user_input: str):
    """Transform user input into a structured search query using GPT-4o"""
    if not _clients_initialized:
        raise ConnectionError("Clients not initialized. Call initialize_clients() first.")
    
    try:
        with open(_get_prompt_path("system.txt"), 'r') as f:
            search_prompt = f.read()
    except FileNotFoundError as e:
        print(f"ERROR: {e}")
        return None # Or raise

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
    """Execute hybrid search in Pinecone combining vector search with metadata filtering"""
    search_params=json.loads(search_params)
    # Extract search components
    # print(search_params)
    vector_query = search_params.get("vector_query", "")
    metadata_filters = search_params.get("metadata_filters", {})
    top_k = search_params.get("top_k", 5)

    # print(metadata_filters)
    
    # Generate embedding for vector search
    dense_query_embedding = pc.inference.embed(
        model="llama-text-embed-v2",
        inputs=vector_query,
        parameters={"input_type": "query", "truncate": "END"}
    )

    # Convert the query into a sparse vector
    sparse_query_embedding = pc.inference.embed(
        model="pinecone-sparse-english-v0",
        inputs=vector_query,
        parameters={"input_type": "query", "truncate": "END"}
    )

    # Construct metadata filter
    filter_dict = {}
    for key, value in metadata_filters.items():
        if isinstance(value, dict) and ("min" in value or "max" in value):
            # Handle range filters
            range_filter = {}
            if "min" in value:
                range_filter["$gte"] = value["min"]
            if "max" in value:
                range_filter["$lte"] = value["max"]
            filter_dict[key] = range_filter
        else:
            # Handle exact match filters
            filter_dict[key] = value
    print(filter_dict)
    query_response = index.query(
        namespace="hybrid-namespace",
        top_k=top_k,
        vector=dense_query_embedding.data[0]['values'],
        sparse_vector={'indices': sparse_query_embedding.data[0]['sparse_indices'], 'values': sparse_query_embedding.data[0]['sparse_values']},
        include_values=False,
        # filter=filter_dict,
        rerank={
            "model": "bge-reranker-v2-m3",
            "top_n": 5,
            "rank_fields": ["chunk_text"]
        },
        include_metadata=True
    )
    # print(query_response)
    
    return query_response.matches

def generate_response(user_query, search_results, search_params, history):
    """Generate a natural language response to the user's query based on search results"""
    
    # Prepare search results summary for GPT-4o
    results_summary = []
    for i, product in enumerate(search_results[:5]):  # Limit to top 5 for prompt size
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
    
    with open(_get_prompt_path("result.txt"), 'r') as f:
        result_prompt =  f.read()
    
    with open(_get_prompt_path("additional.txt"), 'r') as f:
        additional_data =  f.read()
        
    # Create a prompt for GPT-4o to generate a response
    prompt = f"""
    Additional Data : "{additional_data}"
    
    User query: "{user_query}"
    
    Search parameters used:
    {json.dumps(search_params, indent=2)}
    
    Top search results:
    {json.dumps(results_summary, indent=2)}
    
    Total results found: {len(search_results)}

    Chat history:
    {history}

    You should use the chat history to generate a response.
    You should also use the additional data to generate a response.
    Additional data is very important.

    {result_prompt}
    """

    with open(_get_prompt_path("role.txt"), 'r') as f:
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

def product_search_bot(user_query: str, history: str):
    """Main bot handler. Returns a dictionary with response and results."""
    if not _clients_initialized:
        # Attempt to initialize if not already
        if not initialize_clients():
            return {
                "success": False,
                "response": "Critical Error: Failed to initialize API clients. Please check server logs or .env configuration.",
                "query_interpretation": None, "results": [], "result_count": 0
            }
    
    search_params = generate_search_query(user_query)
    
    # Perform hybrid search
    search_results = perform_hybrid_search(search_params)
    
    # Format results for internal use
    formatted_results = []
    for item in search_results:
        product = item.metadata
        product["score"] = item.score
        formatted_results.append(product)
    
    # Generate natural language response
    response_text = generate_response(user_query, search_results, search_params, history)
    
    return {
        "success": True,
        "response": response_text,
        "query_interpretation": search_params,
        "results": formatted_results,
        "result_count": len(formatted_results)
    }

# Example of how to test this module directly (optional)
if __name__ == "__main__":
    print("Attempting to initialize clients for direct module test...")
    if initialize_clients():
        print("\nClients initialized. Testing product_search_bot...")

        test_query_2 = "who are you?"
        print(f"\n--- Test 2: Query: '{test_query_2}' ---")
        response_2 = product_search_bot(test_query_2)
        print(response_2['response'])
    else:
        print("\nClient initialization failed. Cannot run tests.")

# --- END OF FILE hybrid_search.py ---