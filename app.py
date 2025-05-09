# --- START OF FILE app.py ---

import streamlit as st
import re # For regex
import os 
import json # For displaying full results and for escaping text for JS
import streamlit.components.v1 as components # For custom HTML components

# --- Constants ---
MAX_IMAGES_PER_ROW = 4
IMAGE_WIDTH_PX = 200
IMAGE_HEIGHT_PX = 200
SEARCH_MODULE_PATH = "search.hybrid_searh_test" 
ROLE_PROMPT_FILE = "./prompt/role.txt" 

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

# --- Session State Initializations ---
if "chat_log" not in st.session_state:
    st.session_state.chat_log = [] 
if "clients_initialized_successfully" not in st.session_state:
    st.session_state.clients_initialized_successfully = None
if "show_prompt_modal" not in st.session_state:
    st.session_state.show_prompt_modal = False

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

def load_prompt_from_file(filepath: str) -> str:
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        st.error(f"🔴 Prompt file '{filepath}' not found. Please create it in the same directory as app.py.")
        return f"Error: Prompt file '{filepath}' not found."
    except Exception as e:
        st.error(f"🔴 Error reading prompt file '{filepath}': {e}")
        return f"Error reading prompt file '{filepath}': {e}"

# --- Modal Display Logic (using st.dialog) ---
@st.dialog("📝 System Prompts")
def show_prompts_dialog():
    prompt_content = load_prompt_from_file(ROLE_PROMPT_FILE)
    st.markdown(prompt_content) # Display the prompt content

    st.markdown("---") # Separator before buttons

    # Safely escape prompt content for JavaScript
    escaped_prompt_content = json.dumps(prompt_content)

    copy_button_html = f"""
    <script>
    function copyPromptTextToClipboard() {{
        const textToCopy = {escaped_prompt_content};
        navigator.clipboard.writeText(textToCopy).then(() => {{
            const btn = document.getElementById('streamlitCopyPromptBtn');
            if (btn) {{
                const originalText = btn.innerHTML;
                btn.innerHTML = '✅ Copied!';
                btn.disabled = true;
                // Re-enable the button and restore original text after 2 seconds
                setTimeout(() => {{
                    btn.innerHTML = originalText;
                    btn.disabled = false;
                }}, 2000);
            }}
        }}).catch(err => {{
            console.error('Failed to copy text: ', err);
            alert('Failed to copy text. Check console for details. Your browser might not support this feature or requires HTTPS.');
        }});
    }}
    </script>
    <button id="streamlitCopyPromptBtn" onclick="copyPromptTextToClipboard()"
        style="
            padding: 0.6em 1em; /* Use em for responsive padding */
            font-size: 1rem;
            font-weight: 500;
            color: white;
            margin-top: -15%;
            background-color: #007bff; /* Primary blue */
            border: none;
            border-color: red;
            border-radius: 0.3rem;
            cursor: pointer;
            transition: background-color 0.2s ease-in-out, transform 0.1s ease;
            display: inline-flex; /* Align icon and text */
            align-items: center;
            justify-content: center;
            width: 100%; /* Make button take full width of its column */
            box-sizing: border-box; /* Include padding and border in element's total width and height */
        "
        onmouseover="this.style.backgroundColor='#0056b3'"
        onmouseout="this.style.backgroundColor='#007bff'"
        onmousedown="this.style.transform='scale(0.98)'"
        onmouseup="this.style.transform='scale(1)'"
    >
        <span style="margin-right: 0.5em;"></span> Copy
    </button>
    """

    # Layout for buttons at the bottom of the dialog
    # You might need to adjust column widths for optimal appearance
    col1, col2 = st.columns([0.6, 0.6]) # Give more space to copy button if needed

    with col1:
        components.html(copy_button_html, height=55) # Adjust height if button text wraps or padding changes
    
    with col2:
        if st.button("Close", key="close_prompt_dialog_button_modal", use_container_width=True):
            st.session_state.show_prompt_modal = False
            st.rerun()

if st.session_state.get("show_prompt_modal", False):
    show_prompts_dialog()

# --- Sidebar ---
with st.sidebar:
    st.title("🧀 CheeseBot")
    st.markdown("---")
    st.subheader("About This Bot")
    st.info(
        """
        This is your friendly **Cheese Product Assistant!** 🧀

        Ask me about cheese products, and I'll try my best to find what you're looking for.
        For example:
        - "Show me some sharp cheddar cheeses."
        - "Any recommendations for soft French cheese?"
        - "Find cheese under $10."

        I use a special search method to understand your needs and fetch relevant cheese details, including images.
        """
    )
    st.markdown("---")
    if st.button("🧹 Clear Chat History"):
        st.session_state.chat_log = []
        st.toast("Chat history cleared!", icon="🧹")
        st.rerun() 
    st.markdown("---")
    st.caption("Happy cheese hunting!")

# --- Main Page ---
main_header_cols = st.columns([0.85, 0.15]) 
with main_header_cols[0]:
    st.title("🧀 Cheese Product Assistant 🧀")
with main_header_cols[1]:
    if st.button("📜 Prompt", key="show_prompts_main_page_button", help="View the system prompts for this bot."):
        st.session_state.show_prompt_modal = True
        st.rerun()

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
                    parts = full_response_text.split("******", 1)
                    conversational_text = parts[0].strip()
                    if len(parts) > 1:
                        image_list_text_from_bot = parts[1].strip()
                        parsed_image_urls_from_bot = parse_image_urls_from_bot_response(image_list_text_from_bot)
                elif bot_data: 
                    conversational_text = bot_data.get("response", "An error occurred, or no specific information was found.")

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

# --- END OF FILE app.py ---