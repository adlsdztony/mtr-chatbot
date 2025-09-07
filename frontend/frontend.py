import sys, pathlib
import streamlit as st

sys.path.append(pathlib.Path(__file__).parents[1].as_posix())

from utils.get_model import get_prompted_model, get_prompted_model_with_params, DEFAULT_PARAMETERS, validate_parameters
from utils.functions import encode_image
from backend.backend import get_knowledge, form_context_info, get_available_files
from loguru import logger


class ChatBackend:
    """
    Simple backend class to manage chat history.
    """
    def __init__(self):
        self.history = []
    
    def set_history(self, history: list):
        """
        Set the chat history.
        
        Args:
            history: List of historical chat data
        """
        self.history = history if history is not None else []

def create_session():
    st.session_state.current_chat_index += 1
    chat = {
        "name": f"default chat session {st.session_state.current_chat_index}",
        "messages": [],
        "history": [],
        "parameters": DEFAULT_PARAMETERS.copy(),  # Add default parameters for new session
        "selected_file": st.session_state.get('available_files', ['all'])[0] if st.session_state.get('available_files') else 'all'
    }
    st.session_state.chat_sessions[st.session_state.current_chat_index] = chat
    st.session_state.messages = chat["messages"]
    # Update current parameters to match new session
    st.session_state.current_parameters = chat["parameters"].copy()


def construct_chatting_session():
    st.title(
        f"RAG Chatbot {st.session_state.chat_sessions[st.session_state.current_chat_index]['name']}"
    )

    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])


def update_chat_index(index: int):
    st.session_state.current_chat_index = index


def load_components():
    st.sidebar.title("Chat Sessions")
    with st.sidebar:
        with st.container(height=400, border=False):  # Reduced height to make room for parameters
            for index, chat in st.session_state.chat_sessions.items():
                col1, col2, col3 = st.columns([0.5, 0.25, 0.25])

                with col3:  # delete button
                    st.button(
                        ":wastebasket:",
                        type="primary",
                        key=f"delete_{index}",
                        on_click=delete_session,
                        args=(index,),
                    )

                with col2:  # rename button
                    with st.popover(":gear:"):
                        rename_session(index)

                with col1:  # display name and switch tab
                    st.button(
                        chat["name"],
                        type=(
                            "tertiary"
                            if index != st.session_state.current_chat_index
                            else "secondary"
                        ),
                        use_container_width=True,
                        key=f"chat_{index}",
                        on_click=switch_tab,
                        args=(index,),
                    )
        st.button("create new chat", on_click=create_session, type="primary")
        
        # Add file selection
        render_file_selection()
        
        # Add parameter control panel
        render_parameter_controls()


def switch_tab(switch_to: int):
    # save current chat session parameters
    current_index = st.session_state.current_chat_index
    st.session_state.chat_sessions[current_index][
        "messages"
    ] = st.session_state.messages

    st.session_state.chat_sessions[current_index][
        "history"
    ] = st.session_state.backend.history
    
    # Save current parameters to the session
    st.session_state.chat_sessions[current_index][
        "parameters"
    ] = st.session_state.current_parameters.copy()
    
    # Save current selected file
    st.session_state.chat_sessions[current_index][
        "selected_file"
    ] = st.session_state.get('current_selected_file', 'manual')

    # load selected session
    st.session_state.current_chat_index = switch_to
    st.session_state.messages = st.session_state.chat_sessions[switch_to]["messages"]
    st.session_state.backend.set_history(
        st.session_state.chat_sessions[switch_to]["history"]
    )
    
    # Load parameters from the new session (with backward compatibility)
    target_session = st.session_state.chat_sessions[switch_to]
    if "parameters" not in target_session:
        # Add default parameters for backward compatibility
        target_session["parameters"] = DEFAULT_PARAMETERS.copy()
    
    st.session_state.current_parameters = target_session["parameters"].copy()
    
    # Load selected file from the new session (with backward compatibility)
    if "selected_file" not in target_session:
        target_session["selected_file"] = st.session_state.get('available_files', ['all'])[0] if st.session_state.get('available_files') else 'all'
    
    st.session_state.current_selected_file = target_session["selected_file"]
    
    # Update model with new parameters
    update_model_with_current_parameters()


def rename_session(renamed_session_index: int):
    st.markdown("Rename this sessioin to ...")
    new_name = st.text_input(
        "New name",
        value=st.session_state.chat_sessions[renamed_session_index]["name"],
        key=f"new_chat_{renamed_session_index}",
    )
    st.session_state.chat_sessions[renamed_session_index]["name"] = new_name


def delete_session(deleted_session_index: int):
    if len(st.session_state.chat_sessions) == 1:
        st.session_state.pop(deleted_session_index)
        create_session()
    else:
        # first switch tab
        next_session = next(
            filter(
                lambda chat: chat != deleted_session_index,
                st.session_state.chat_sessions.keys(),
            )
        )
        switch_tab(next_session)
        # then remove
        st.session_state.chat_sessions.pop(deleted_session_index)


def render_parameter_controls():
    """
    Render the parameter control panel in the sidebar.
    """
    st.sidebar.markdown("---")
    st.sidebar.subheader("🎛️ Model Parameters")
    
    # Use expander to save space
    with st.sidebar.expander("Adjust Parameters", expanded=True):
        # Temperature slider
        new_temperature = st.slider(
            "Temperature",
            min_value=0.0,
            max_value=2.0,
            value=st.session_state.current_parameters["temperature"],
            step=0.1,
            format="%.1f",
            help="Controls randomness in responses. Lower values make output more focused and deterministic.",
            key="temperature_slider"
        )
        
        # Top-p slider
        new_top_p = st.slider(
            "Top-p (Nucleus Sampling)",
            min_value=0.0,
            max_value=1.0,
            value=st.session_state.current_parameters["top_p"],
            step=0.05,
            format="%.2f",
            help="Limits the model to consider only the top p probability mass of tokens.",
            key="top_p_slider"
        )
        
        # Top-k slider
        new_top_k = st.slider(
            "Top-k",
            min_value=1,
            max_value=100,
            value=st.session_state.current_parameters["top_k"],
            step=1,
            help="Limits the model to consider only the k most likely next tokens.",
            key="top_k_slider"
        )
        
        # Check if parameters have changed
        parameters_changed = (
            new_temperature != st.session_state.current_parameters["temperature"] or
            new_top_p != st.session_state.current_parameters["top_p"] or
            new_top_k != st.session_state.current_parameters["top_k"]
        )
        
        if parameters_changed:
            # Validate new parameters
            is_valid, error_msg = validate_parameters(new_temperature, new_top_p, new_top_k)
            
            if is_valid:
                # Update parameters
                st.session_state.current_parameters = {
                    "temperature": new_temperature,
                    "top_p": new_top_p,
                    "top_k": new_top_k
                }
                
                # Update current session parameters
                current_index = st.session_state.current_chat_index
                st.session_state.chat_sessions[current_index]["parameters"] = st.session_state.current_parameters.copy()
                
                # Update model with new parameters
                update_model_with_current_parameters()
                
                st.sidebar.success("✅ Parameters updated!")
            else:
                st.sidebar.error(f"❌ {error_msg}")


def render_file_selection():
    """
    Render the file selection dropdown in the sidebar.
    """
    st.sidebar.markdown("---")
    st.sidebar.subheader("📁 Document Selection")
    
    available_files = st.session_state.get('available_files', ['all', 'manual'])
    current_file = st.session_state.get('current_selected_file', available_files[0] if available_files else 'all')
    
    # Create display options with descriptions
    file_options = []
    file_display_map = {}
    
    for file in available_files:
        if file == 'all':
            display_name = "🌐 All Documents"
            file_display_map[display_name] = file
        else:
            display_name = f"📄 {file}"
            file_display_map[display_name] = file
        file_options.append(display_name)
    
    # Find current selection display name
    current_display = None
    for display_name, file_name in file_display_map.items():
        if file_name == current_file:
            current_display = display_name
            break
    
    selected_display = st.sidebar.selectbox(
        "Select document:",
        options=file_options,
        index=file_options.index(current_display) if current_display in file_options else 0,
        help="Choose 'All Documents' to search across all files, or select a specific document",
        key="file_selector"
    )
    
    # Get actual filename from display name
    selected_file = file_display_map[selected_display]
    
    # Update current selected file if changed
    if selected_file != st.session_state.get('current_selected_file'):
        st.session_state.current_selected_file = selected_file
        # Update current session
        current_index = st.session_state.current_chat_index
        st.session_state.chat_sessions[current_index]["selected_file"] = selected_file
        
        if selected_file == 'all':
            st.sidebar.success("✅ Switched to: All Documents")
        else:
            st.sidebar.success(f"✅ Switched to: {selected_file}")

def update_model_with_current_parameters():
    """
    Update the model instance with current parameters.
    """
    try:
        st.session_state.model = get_prompted_model_with_params(
            temperature=st.session_state.current_parameters["temperature"],
            top_p=st.session_state.current_parameters["top_p"],
            top_k=st.session_state.current_parameters["top_k"]
        )
        logger.info(f"Model updated with parameters: {st.session_state.current_parameters}")
    except ValueError as e:
        logger.error(f"Failed to update model parameters: {e}")
        st.sidebar.error(f"Failed to update model: {e}")

# NOTE - set for session change
if "has_init" not in st.session_state:
    st.session_state.current_chat_index = 0
    st.session_state.chat_sessions = {}
    st.session_state.messages = []
    st.session_state.current_parameters = DEFAULT_PARAMETERS.copy()  # Initialize current parameters
    st.session_state.backend = ChatBackend()  # Initialize backend instance
    
    # Load available files
    st.session_state.available_files = get_available_files()
    st.session_state.current_selected_file = st.session_state.available_files[0] if st.session_state.available_files else 'all'
    
    st.session_state.has_init = True
    st.session_state.model = get_prompted_model_with_params(**st.session_state.current_parameters)
    logger.info("Streamlit session initialized with default parameters.")
    logger.info(f"Available files: {st.session_state.available_files}")
    
    # Create initial session if no sessions exist
    if not st.session_state.chat_sessions:
        create_session()
    
load_components()

# NOTE - construct chatting session
construct_chatting_session()

# NOTE - load models

def render_text_chunk_with_expander(chunk, chunk_index):
    """Render a single text chunk with expandable full content"""
    meta = chunk.get('metadata', {})
    filename = meta.get('filename', 'unknown')
    page_idx = meta.get('page_idx', 'unknown')
    chunk_type = meta.get('type', 'unknown')
    full_content = chunk.get('content', '')
    
    # Preview content (first 150 chars)
    content_preview = full_content[:150]
    if len(full_content) > 150:
        content_preview += "..."
    
    st.markdown(f"**[{chunk_index}] {filename} - Page {page_idx} ({chunk_type})**")
    
    # Show preview by default
    st.markdown(f"> {content_preview}")
    
    # Add expander for full content if text is longer than preview
    if len(full_content) > 150:
        with st.expander(f"📖 View full content (Chunk {chunk_index})", expanded=False):
            st.text_area(
                "Full content:",
                value=full_content,
                height=200,
                key=f"chunk_content_{chunk_index}",
                disabled=True
            )
    
    st.markdown("")  # Add spacing

def format_citations_interactive(text_chunks, image_chunks):
    """Format citations with interactive expandable content"""
    if text_chunks:
        st.markdown("### 📄 Text References:")
        for i, chunk in enumerate(text_chunks, 1):
            render_text_chunk_with_expander(chunk, i)
    
    if image_chunks:
        st.markdown("### 🖼️ Image/Table References:")
        for i, chunk in enumerate(image_chunks, len(text_chunks) + 1):
            meta = chunk.get('metadata', {})
            filename = meta.get('filename', 'unknown')
            page_idx = meta.get('page_idx', 'unknown')
            chunk_type = meta.get('type', 'unknown')
            path = meta.get('path', '')
            
            st.markdown(f"**[{i}] {filename} - Page {page_idx} ({chunk_type})**")
            if path:
                st.markdown(f"> Path: {path}")
            st.markdown("")  # Add spacing

def format_citations_for_history(text_chunks, image_chunks):
    """Format citations for chat history (simple text format)"""
    citations_content = ""
    
    if text_chunks:
        citations_content += "### 📄 Text References:\n"
        for i, chunk in enumerate(text_chunks, 1):
            meta = chunk.get('metadata', {})
            filename = meta.get('filename', 'unknown')
            page_idx = meta.get('page_idx', 'unknown')
            chunk_type = meta.get('type', 'unknown')
            
            # Preview of chunk content (first 150 chars)
            content_preview = chunk.get('content', '')[:150]
            if len(chunk.get('content', '')) > 150:
                content_preview += "..."
            
            citations_content += f"**[{i}] {filename} - Page {page_idx} ({chunk_type})**\n"
            citations_content += f"> {content_preview}\n\n"
    
    if image_chunks:
        citations_content += "### 🖼️ Image/Table References:\n"
        for i, chunk in enumerate(image_chunks, len(text_chunks) + 1):
            meta = chunk.get('metadata', {})
            filename = meta.get('filename', 'unknown')
            page_idx = meta.get('page_idx', 'unknown')
            chunk_type = meta.get('type', 'unknown')
            path = meta.get('path', '')
            
            citations_content += f"**[{i}] {filename} - Page {page_idx} ({chunk_type})**\n"
            if path:
                citations_content += f"> Path: {path}\n"
            citations_content += "\n"
    
    return citations_content

if user_input := st.chat_input("Ask something *w*"):
    with st.chat_message("user"):
        st.markdown(user_input)

    st.session_state.messages.append({"role": "user", "content": user_input})
    logger.info(f"User input: {user_input}")

    # Get current selected file
    selected_file = st.session_state.get('current_selected_file', 'all')
    
    # Get context info with detailed chunk metadata
    # Pass None to backend if "all" is selected to use all documents
    backend_filename = None if selected_file == 'all' else selected_file
    texts, images, text_chunks, image_chunks = form_context_info(user_input, backend_filename)
    args = {"context_info": texts, "question": user_input}

    logger.debug("Starting model streaming...")
    with st.chat_message("assistant"):
        # Show citations in a collapsible expander with interactive content
        total_sources = len(text_chunks) + len(image_chunks)
        
        with st.expander(f"📚 Sources ({total_sources} references)", expanded=False):
            format_citations_interactive(text_chunks, image_chunks)
        
        # Show the answer
        st.markdown("## 🤖 Answer\n")
        placeholder = st.empty()
        full_response = ""
        for chunk in st.session_state.model.stream(args):
            full_response += chunk
            placeholder.markdown(full_response + "|")

        # Handle images with proper path resolution
        for image in images:
            image_path = image.get("path", "")
            if image_path:
                # Try to determine the correct document path
                filename = image.get("filename", selected_file)
                code = encode_image(f'.data/result/{filename}/{image_path}', prefix=True)
                full_response += f"\n![Image]({code})"

        # Final content for message history (uses simple format for history)
        citations_content_for_history = format_citations_for_history(text_chunks, image_chunks)
        sources_section = f"📚 **Sources ({total_sources} references)** - Click to expand\n\n" + citations_content_for_history + "\n---\n\n"
        final_content = sources_section + "## 🤖 Answer\n\n" + full_response
        placeholder.markdown(full_response)
        
        st.session_state.messages.append(
            {
                "role": "assistant", 
                "content": final_content,
                "citations": {
                    "text_chunks": text_chunks,
                    "image_chunks": image_chunks,
                    "selected_file": selected_file
                }
            }
        )
