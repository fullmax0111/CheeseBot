# --- START OF FILE app.py ---

import streamlit as st
import re # For regex
import os 
import json # For displaying full results and for escaping text for JS
import streamlit.components.v1 as components # For custom HTML components
import requests
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# --- Constants ---
MAX_IMAGES_PER_ROW = 4
IMAGE_WIDTH_PX = 200
IMAGE_HEIGHT_PX = 200
SEARCH_MODULE_PATH = "search.hybrid_search_test" 
ROLE_PROMPT_FILE = "./prompt/role.txt" 

# Add SerpAPI configuration constant with the rest of your constants
SERPAPI_API_KEY = os.getenv('SERPAPI_API_KEY', '')  # Get API key from .env file

# --- Session State Initializations ---
if "chat_log" not in st.session_state:
    st.session_state.chat_log = [] 
if "clients_initialized_successfully" not in st.session_state:
    st.session_state.clients_initialized_successfully = None
if "context_data" not in st.session_state:
    st.session_state.context_data = []

# --- Import Custom Search Logic ---
try:
    from importlib import import_module
    search_module = import_module(SEARCH_MODULE_PATH)
    product_search_bot = search_module.product_search_bot
    initialize_clients = search_module.initialize_clients
except ImportError as e:
    st.error(f"🔴 Failed to import '{SEARCH_MODULE_PATH}' module: {e}. "
             f"Ensure '{SEARCH_MODULE_PATH.replace('.', '/')}.py' exists (e.g., in a subfolder named 'search' "
             f"if path contains a dot) relative to app.py, is in the Python path, and has no syntax errors.")
    st.stop()
except AttributeError as e:
    st.error(f"🔴 Functions not found in '{SEARCH_MODULE_PATH}': {e}. "
             "Ensure 'product_search_bot' and 'initialize_clients' are defined in the module.")
    st.stop()

# --- Streamlit Page Configuration ---
st.set_page_config(layout="wide", page_title="🧀 Cheese Product Assistant")

# --- Helper Functions ---
def clean_image_links_from_text(text: str) -> str:
    """Remove any markdown image links from the text."""
    # Regex to match markdown image links: ![alt text](url)
    image_link_pattern = r'!\[[^\]]*\]\([^)]+\)'
    # Remove all image links
    cleaned_text = re.sub(image_link_pattern, '', text)
    # Remove any resulting double spaces or empty lines
    cleaned_text = re.sub(r'\n\s*\n', '\n\n', cleaned_text)
    cleaned_text = re.sub(r'  +', ' ', cleaned_text)
    return cleaned_text.strip()

def web_search(query: str, num_results: int = 5, engine: str = "google", tb: str = "", tbs: str = "") -> dict:
    """
    Perform a web search using SerpAPI.
    
    Args:
        query: The search query string
        num_results: Number of results to return (default 5)
        engine: The search engine to use (default "google")
        tb: The type of results to return (default "")
        tbs: The time frame for the search (default "")
        
    Returns:
        Dictionary containing search results or error information
    """
    if not SERPAPI_API_KEY:
        return {
            "success": False,
            "error": "SERPAPI_API_KEY not found in .env file. Please add it to use web search functionality."
        }
    
    try:
        url = "https://serpapi.com/search"
        params = {
            "q": query,
            "api_key": SERPAPI_API_KEY,
            "engine": engine,
            "num": num_results,
            "tb": tb,
            "tbs": tbs
        }
        
        response = requests.get(url, params=params)
        response.raise_for_status()  # Raise exception for 4XX/5XX responses
        
        results = response.json()
        
        # Extract organic results
        organic_results = results.get("organic_results", [])
        processed_results = []
        
        for result in organic_results[:num_results]:
            processed_results.append({
                "title": result.get("title", ""),
                "link": result.get("link", ""),
                "snippet": result.get("snippet", "")
            })
            
        return {
            "success": True,
            "results": processed_results,
            "total_results": len(processed_results)
        }
        
    except requests.exceptions.RequestException as e:
        return {
            "success": False,
            "error": f"Error making request to SerpAPI: {str(e)}"
        }
    except ValueError as e:
        return {
            "success": False, 
            "error": f"Error parsing SerpAPI response: {str(e)}"
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"Unexpected error during web search: {str(e)}"
        }

# --- Helper Functions ---
def parse_image_urls_from_bot_response(image_section_text: str) -> list[dict]:
    images = []
    regex_markdown_link = r"\((https?://[^\s)]+)\)"
    for line in image_section_text.strip().split('\n'):
        line = line.strip()
        if not line: continue
        match = re.search(regex_markdown_link, line)
        if match:
            images.append({"url": match.group(1).strip()})
    return images

def get_image_card_html(image_url: str, caption: str, detail_url: str) -> str:
    safe_alt_caption = re.sub(r'[^a-zA-Z0-9 .,!?\'"-]', '', caption) if caption else "Product Image"
    display_caption = caption if caption else "View Details"
    return f"""
    <a href="{detail_url}" target="_blank" style="text-decoration: none; color: inherit; display: block; text-align: center; margin-bottom: 15px;">
        <img src="{image_url}" alt="{safe_alt_caption}" style="width: {IMAGE_WIDTH_PX}px; height: {IMAGE_HEIGHT_PX}px; object-fit: contain; border-radius: 8px; margin-bottom: 8px; box-shadow: 0 4px 8px rgba(0,0,0,0.1); transition: transform 0.2s ease-in-out;" onmouseover="this.style.transform='scale(1.05)';" onmouseout="this.style.transform='scale(1)';">
        <p style="font-size: 14px; width: {IMAGE_WIDTH_PX}px; word-wrap: break-word; margin: 0 auto; line-height: 1.3; height: 3.9em; overflow: hidden; color: #333;">
            {display_caption}
        </p>
    </a>
    """


# --- Sidebar ---
with st.sidebar:
    st.title("🧀 CheeseBot")
    st.markdown("---")
    if st.button("🧹 Clear Chat History"):
        st.session_state.chat_log = []
        st.toast("Chat history cleared!", icon="🧹")
        st.rerun() 
    st.markdown("---")
    st.subheader("Web Search")
    web_search_query = st.text_input("Search the web:", placeholder="Enter search query...")
    
    # Add radio buttons for search options
    search_engine = st.radio(
        "Search Engine:",
        options=["Google", "Bing", "Yahoo"],
        index=0,  # Default to Google
        horizontal=True
    )
    
    result_type = st.radio(
        "Result Type:",
        options=["Web", "Images", "News", "Videos"],
        index=0,  # Default to Web
        horizontal=True
    )
    
    time_frame = st.radio(
        "Time Frame:",
        options=["Any time", "Past day", "Past week", "Past month"],
        index=0,  # Default to Any time
        horizontal=True
    )
    
    search_button = st.button("Search", key="web_search_button")
    
    if search_button and web_search_query:
        with st.spinner(f"Searching {search_engine} for {result_type.lower()}..."):
            # Map the radio button selections to SerpAPI parameters
            engine_param = search_engine.lower()
            
            # Set proper engine parameter
            if engine_param == "google":
                engine = "google"
            elif engine_param == "bing":
                engine = "bing"
            elif engine_param == "yahoo":
                engine = "yahoo"
            else:
                engine = "google"  # Default
            
            # Set proper type parameter based on result_type
            if result_type.lower() == "images":
                tb_param = "isch"  # Google Images
            elif result_type.lower() == "news":
                tb_param = "nws"   # Google News
            elif result_type.lower() == "videos":
                tb_param = "vid"   # Google Videos
            else:
                tb_param = ""      # Regular web search
            
            # Set time parameter based on time_frame
            if time_frame.lower() == "past day":
                tbs_param = "qdr:d"
            elif time_frame.lower() == "past week":
                tbs_param = "qdr:w"
            elif time_frame.lower() == "past month":
                tbs_param = "qdr:m"
            else:
                tbs_param = ""     # Any time
            
            # Update the web_search function call with additional parameters
            search_results = web_search(
                web_search_query, 
                num_results=5,
                engine=engine,
                tb=tb_param,
                tbs=tbs_param
            )
            
        if search_results.get("success"):
            results = search_results.get("results", [])
            if results:
                st.success(f"Found {len(results)} results")
                for result in results:
                    with st.expander(result.get("title", "Result")):
                        st.write(result.get("snippet", "No snippet available"))
                        st.markdown(f"[Visit page]({result.get('link', '#')})")
            else:
                st.info("No results found. Try a different search query.")
        else:
            st.error(search_results.get("error", "An unknown error occurred"))
    st.caption("Happy cheese hunting!")
    st.markdown("---")
    st.subheader("Debug Options")
    show_context = st.radio(
        "Show Context Data:",
        options=["Hide", "Show"],
        index=0,  # Default to Hide
        horizontal=True
    )
    # print(st.session_state.context_data)
    if show_context == "Show" and st.session_state.context_data:
        st.subheader("Context Data")
        with st.expander("Raw Search Results", expanded=True):
            st.json(st.session_state.context_data)

# --- Main Page ---
main_header_cols = st.columns([0.85, 0.15]) 
with main_header_cols[0]:
    st.title("🧀 Cheese Product Assistant 🧀")


st.caption("Ask me about cheese products! I'll do my best to help you find the perfect cheese.")

# --- Initialize Backend Clients ---
if st.session_state.clients_initialized_successfully is None:
    with st.spinner("🛠️ Initializing backend services... This may take a moment."):
        try:
            if initialize_clients():
                st.session_state.clients_initialized_successfully = True
            else:
                st.session_state.clients_initialized_successfully = False
                st.error("🔴 CRITICAL: Failed to initialize backend services. Please check console/server logs.")
        except Exception as e:
            st.session_state.clients_initialized_successfully = False
            st.error(f"🔴 CRITICAL: Exception during backend initialization: {e}")

# --- Display Chat History ---
for entry in st.session_state.chat_log:
    with st.chat_message(entry["role"]):
        if entry["role"] == "user":
            st.markdown(entry["text_response"])
        elif entry["role"] == "assistant":
            st.markdown(entry["text_response"])
            if entry.get("images"):
                st.markdown("---")
                images_to_display_from_history = entry["images"]
                num_images = len(images_to_display_from_history)
                cols_per_row_history = min(num_images, MAX_IMAGES_PER_ROW) if num_images > 0 else 1
                if num_images > 0:
                    image_cols_history = st.columns(cols_per_row_history) 
                    for i, img_data in enumerate(images_to_display_from_history):
                        col_to_use = image_cols_history[i % cols_per_row_history]
                        with col_to_use:
                            st.markdown(
                                get_image_card_html(
                                    img_data.get('url', ''),
                                    img_data.get('caption', 'Product Image'),
                                    img_data.get('detail_url', '#')
                                ),
                                unsafe_allow_html=True
                            )

# --- Handle User Input and Bot Interaction ---
if user_query := st.chat_input("What kind of cheese are you looking for?"):
    if st.session_state.clients_initialized_successfully is False:
        st.error("🔴 Backend services not initialized. Cannot process query.")
    elif st.session_state.clients_initialized_successfully is None:
        st.warning("⏳ Backend initialization is still pending. Please wait a moment and try again.")
    else:
        st.session_state.chat_log.append({
            "role": "user", 
            "text_response": user_query, 
            "images": [], 
            "full_results": []
        })
        with st.chat_message("user"):
            st.markdown(user_query)

        with st.chat_message("assistant"):
            message_placeholder = st.empty()
            image_container_placeholder = st.container() 

            with st.spinner("🧀 Searching for cheeses..."):
                try:
                    history_context = ""
                    # The current user_query is st.session_state.chat_log[-1]
                    # If len > 1, st.session_state.chat_log[-2] is the message before the current user query.
                    if len(st.session_state.chat_log) > 1: 
                        history_context = st.session_state.chat_log[-2]["text_response"]
                    
                    bot_data = product_search_bot(user_query, history_context)
                    st.session_state.context_data = bot_data.get("results", "")
                    # print(st.session_state.context_data)
                except Exception as e:
                    st.error(f"⚠️ Error during product search: {e}")
                    bot_data = {"success": False, "response": "Sorry, an unexpected error occurred while searching."}

                conversational_text = "Sorry, I couldn't process that request."
                parsed_image_urls_from_bot = [] 
                all_search_results_from_bot = []
                images_for_log_and_history = [] 

                if bot_data and bot_data.get("success"):
                    full_response_text = bot_data.get("response", "")
                    all_search_results_from_bot = bot_data.get("results", [])
                    
                    # Split the response by delimiter
                    parts = full_response_text.split("******", 1)
                    
                    # Get conversational text and clean it of any remaining image links
                    conversational_text = clean_image_links_from_text(parts[0].strip())
                    
                    # Extract images from the delimiter section if it exists
                    if len(parts) > 1:
                        image_list_text_from_bot = parts[1].strip()
                        parsed_image_urls_from_bot = parse_image_urls_from_bot_response(image_list_text_from_bot)
                    else:
                        # If no delimiter but there might be images in the text, extract them
                        image_link_pattern = r'!\[[^\]]*\]\((https?://[^\s)]+)\)'
                        image_matches = re.findall(image_link_pattern, parts[0])
                        for url in image_matches:
                            parsed_image_urls_from_bot.append({"url": url.strip()})
                elif bot_data: 
                    # Clean any image links from error message too
                    conversational_text = clean_image_links_from_text(
                        bot_data.get("response", "An error occurred, or no specific information was found.")
                    )

                message_placeholder.markdown(conversational_text)

                if parsed_image_urls_from_bot and all_search_results_from_bot:
                    with image_container_placeholder:
                        st.markdown("---") 
                        num_parsed_urls = len(parsed_image_urls_from_bot)
                        cols_for_new_images = min(num_parsed_urls, MAX_IMAGES_PER_ROW)
                        if cols_for_new_images > 0:
                            image_display_cols = st.columns(cols_for_new_images)
                            for i, parsed_img_info in enumerate(parsed_image_urls_from_bot):
                                target_url_from_parser = parsed_img_info['url']
                                match_found_for_this_url = False
                                for product_data in all_search_results_from_bot:
                                    product_image_url = product_data.get('image_url')
                                    product_main_image_url = product_data.get('detail_page_main_image_url')
                                    if target_url_from_parser == product_image_url or \
                                       target_url_from_parser == product_main_image_url:
                                        caption = product_data.get('product_name', "Product")
                                        detail_url = product_data.get('product_detail_url', '#')
                                        images_for_log_and_history.append({
                                            'url': target_url_from_parser,
                                            'caption': caption,
                                            'detail_url': detail_url
                                        })
                                        col_to_use = image_display_cols[i % cols_for_new_images]
                                        with col_to_use:
                                            st.markdown(
                                                get_image_card_html(target_url_from_parser, caption, detail_url),
                                                unsafe_allow_html=True
                                            )
                                        match_found_for_this_url = True
                                        break 
                st.session_state.chat_log.append({
                    "role": "assistant",
                    "text_response": conversational_text,
                    "images": images_for_log_and_history, 
                    "full_results": all_search_results_from_bot
                })



# --- Add this function after clean_image_links_from_text


# --- END OF FILE app.py ---