import sys, pathlib
import streamlit as st
import re

sys.path.append(pathlib.Path(__file__).parents[1].as_posix())

from utils.get_model import (
    get_prompted_model, 
    get_prompted_model_with_params, 
    DEFAULT_PARAMETERS, 
    validate_parameters, 
    get_session_history,
    add_referenced_context_to_history
)
from utils.functions import encode_image
from backend.backend import (
    get_knowledge, 
    form_context_info, 
    get_available_files,
    build_prompt_with_citations,
    extract_citations_from_response
)
from loguru import logger

def create_session():
    st.session_state.current_chat_index += 1
    session_id = f"session_{st.session_state.current_chat_index}"
    chat = {
        "name": f"default chat session {st.session_state.current_chat_index}",
        "messages": [],
        "session_id": session_id,
        "parameters": DEFAULT_PARAMETERS.copy(),
        "selected_file": st.session_state.get('available_files', ['all'])[0] if st.session_state.get('available_files') else 'all'
    }
    st.session_state.chat_sessions[st.session_state.current_chat_index] = chat
    st.session_state.messages = chat["messages"]
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
        with st.container(height=400, border=False):
            for index, chat in st.session_state.chat_sessions.items():
                col1, col2, col3 = st.columns([0.5, 0.25, 0.25])

                with col3:
                    st.button(
                        ":wastebasket:",
                        type="primary",
                        key=f"delete_{index}",
                        on_click=delete_session,
                        args=(index,),
                    )

                with col2:
                    with st.popover(":gear:"):
                        rename_session(index)

                with col1:
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
        
        render_file_selection()
        render_parameter_controls()


def switch_tab(switch_to: int):
    current_index = st.session_state.current_chat_index
    st.session_state.chat_sessions[current_index]["messages"] = st.session_state.messages
    
    st.session_state.chat_sessions[current_index]["parameters"] = st.session_state.current_parameters.copy()
    st.session_state.chat_sessions[current_index]["selected_file"] = st.session_state.current_selected_file

    st.session_state.current_chat_index = switch_to
    st.session_state.messages = st.session_state.chat_sessions[switch_to]["messages"]
    
    target_session = st.session_state.chat_sessions[switch_to]
    if "parameters" not in target_session:
        target_session["parameters"] = DEFAULT_PARAMETERS.copy()
    if "session_id" not in target_session:
        target_session["session_id"] = f"session_{switch_to}"
    
    st.session_state.current_parameters = target_session["parameters"].copy()
    
    if "selected_file" not in target_session:
        target_session["selected_file"] = st.session_state.get('available_files', ['all'])[0] if st.session_state.get('available_files') else 'all'
    
    st.session_state.current_selected_file = target_session.get("selected_file", st.session_state.get('available_files', ['all'])[0] if st.session_state.get('available_files') else 'all')
    
    update_model_with_current_parameters()


def rename_session(renamed_session_index: int):
    st.markdown("Rename this session to ...")
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
        next_session = next(
            filter(
                lambda chat: chat != deleted_session_index,
                st.session_state.chat_sessions.keys(),
            )
        )
        switch_tab(next_session)
        st.session_state.chat_sessions.pop(deleted_session_index)


def render_parameter_controls():
    st.sidebar.markdown("---")
    st.sidebar.subheader("🎛️ Model Parameters")
    
    with st.sidebar.expander("Adjust Parameters", expanded=True):
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
        
        new_top_k = st.slider(
            "Top-k",
            min_value=1,
            max_value=100,
            value=st.session_state.current_parameters["top_k"],
            step=1,
            help="Limits the model to consider only the k most likely next tokens.",
            key="top_k_slider"
        )
        
        parameters_changed = (
            new_temperature != st.session_state.current_parameters["temperature"] or
            new_top_p != st.session_state.current_parameters["top_p"] or
            new_top_k != st.session_state.current_parameters["top_k"]
        )
        
        if parameters_changed:
            is_valid, error_msg = validate_parameters(new_temperature, new_top_p, new_top_k)
            
            if is_valid:
                st.session_state.current_parameters = {
                    "temperature": new_temperature,
                    "top_p": new_top_p,
                    "top_k": new_top_k
                }
                
                current_index = st.session_state.current_chat_index
                st.session_state.chat_sessions[current_index]["parameters"] = st.session_state.current_parameters.copy()
                
                update_model_with_current_parameters()
                
                st.sidebar.success("✅ Parameters updated!")
            else:
                st.sidebar.error(f"❌ {error_msg}")


def render_file_selection():
    st.sidebar.markdown("---")
    st.sidebar.subheader("📁 Document Selection")
    
    available_files = st.session_state.get('available_files', ['all', 'manual'])
    current_file = st.session_state.get('current_selected_file', available_files[0] if available_files else 'all')
    
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
    
    selected_file = file_display_map[selected_display]
    
    if selected_file != st.session_state.get('current_selected_file'):
        st.session_state.current_selected_file = selected_file
        current_index = st.session_state.current_chat_index
        st.session_state.chat_sessions[current_index]["selected_file"] = selected_file
        
        if selected_file == 'all':
            st.sidebar.success("✅ Switched to: All Documents")
        else:
            st.sidebar.success(f"✅ Switched to: {selected_file}")

def update_model_with_current_parameters():
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
    """Format citations with interactive expandable content - shows chunk metadata"""
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


def style_citations_in_text(text: str, citations_list: list) -> str:
    """
    Replace [1], [2] etc. in text with styled, clickable citations.
    Returns HTML with styled citations.
    """
    # Create a mapping of citation numbers to their data
    citation_map = {c['num']: c for c in citations_list}
    
    def replace_citation(match):
        num = int(match.group(1))
        if num in citation_map:
            citation = citation_map[num]
            # Create a styled span for the citation
            return f'<span style="color: #1f77b4; text-decoration: underline; cursor: pointer; font-weight: 500;" title="Page {citation["page_idx"]}">[{num}]</span>'
        return match.group(0)
    
    # Replace all [1], [2], etc. with styled versions
    styled_text = re.sub(r'\[(\d+)\]', replace_citation, text)
    return styled_text


def display_citations_in_response(citations_list):
    """Display extracted citations that were actually used in the response"""
    if not citations_list:
        return
    
    st.markdown("---")
    st.markdown("**📚 References Used:**")
    
    for citation in citations_list:
        col1, col2 = st.columns([0.1, 0.9])
        
        with col1:
            st.markdown(f'<span style="color: #1f77b4; font-weight: bold; font-size: 1.1em;">[{citation["num"]}]</span>', unsafe_allow_html=True)
        
        with col2:
            filename = citation['filename']
            page = citation['page_idx']
            cite_type = citation['type']
            preview = citation['preview']
            
            # Citation text with page number (ready for PDF viewer integration)
            st.markdown(f"*{filename}* - **Page {page}** ({cite_type})")
            
            # Show preview in expander
            with st.expander("Preview", expanded=False):
                st.text(preview)


# Initialize session state
if "has_init" not in st.session_state:
    st.session_state.current_chat_index = 0
    st.session_state.chat_sessions = {}
    st.session_state.messages = []
    st.session_state.current_parameters = DEFAULT_PARAMETERS.copy()
    
    st.session_state.available_files = get_available_files()
    st.session_state.current_selected_file = st.session_state.available_files[0] if st.session_state.available_files else 'all'
    
    st.session_state.has_init = True
    st.session_state.model = get_prompted_model_with_params(**st.session_state.current_parameters)
    logger.info("Streamlit session initialized with default parameters.")
    logger.info(f"Available files: {st.session_state.available_files}")
    
    if not st.session_state.chat_sessions:
        create_session()
    
load_components()
construct_chatting_session()

# Chat input handling
if user_input := st.chat_input("Ask something *w*"):
    with st.chat_message("user"):
        st.markdown(user_input)

    st.session_state.messages.append({"role": "user", "content": user_input})
    logger.info(f"User input: {user_input}")

    # Get current selected file
    selected_file = st.session_state.get('current_selected_file', 'all')
    
    # Get context info with detailed chunk metadata
    backend_filename = None if selected_file == 'all' else selected_file
    texts, images, text_chunks, image_chunks = form_context_info(user_input, backend_filename)
    
    # Get current session ID
    current_session = st.session_state.chat_sessions[st.session_state.current_chat_index]
    session_id = current_session.get("session_id", f"session_{st.session_state.current_chat_index}")
    
    # Build prompt with citations
    complete_prompt, citation_context = build_prompt_with_citations(user_input, text_chunks, image_chunks)
    
    # Prepare arguments for the model
    args = {
        "context_info": complete_prompt,
        "question": "" # question already in complete prompt
    }
    
    # Configuration for session history
    config = {"configurable": {"session_id": session_id}}

    logger.debug("Starting model streaming with citations...")
    logger.debug(f"Complete prompt preview: {complete_prompt[:500]}...") 

    with st.chat_message("assistant"):
        # Show all retrieved sources in collapsible expander (existing functionality)
        total_sources = len(text_chunks) + len(image_chunks)
        
        with st.expander(f"📚 All Retrieved Sources ({total_sources} references)", expanded=False):
            format_citations_interactive(text_chunks, image_chunks)
        
        # Show the answer
        st.markdown("## 🤖 Answer\n")

        # Create two placeholders - one for thinking, one for answer
        thinking_placeholder = st.empty()
        answer_placeholder = st.empty()

        full_response = ""
        in_thinking = False
        thinking_content = ""
        answer_content = ""

        # Stream the response with session history
        for chunk in st.session_state.model.stream(args, config=config):
            full_response += chunk
            
            # Check if we're in a thinking block
            if "<think>" in full_response and "</think>" not in full_response:
                in_thinking = True
            elif "</think>" in full_response:
                in_thinking = False
                # Extract answer part after </think>
                import re
                match = re.search(r'</think>\s*(.*)', full_response, re.DOTALL)
                if match:
                    answer_content = match.group(1)
            
            if in_thinking:
                # Show thinking in collapsed expander
                with thinking_placeholder:
                    with st.expander("🧠 Model Thinking Process", expanded=False):
                        thinking_match = re.search(r'<think>(.*?)(?:</think>|$)', full_response, re.DOTALL)
                        if thinking_match:
                            st.text(thinking_match.group(1).strip())
            else:
                # Show answer in main area
                if "</think>" in full_response:
                    answer_placeholder.markdown(answer_content + "|")
                else:
                    # No thinking tags, show everything
                    answer_placeholder.markdown(full_response + "|")

        # Extract the answer part (after thinking) for display and citation extraction
        display_response = full_response

        # If model used extended thinking, extract only the answer part
        if "<think>" in full_response and "</think>" in full_response:
            import re
            # The answer is everything AFTER </think>
            match = re.search(r'</think>\s*(.*)', full_response, re.DOTALL)
            if match:
                display_response = match.group(1).strip()
                logger.debug(f"Extracted answer from thinking: {display_response[:200]}")
            else:
                # Fallback: remove think tags completely
                display_response = re.sub(r'<think>.*?</think>', '', full_response, flags=re.DOTALL).strip()

        # Extract citations from the display response (not the thinking part)
        citations_used = extract_citations_from_response(display_response, text_chunks, image_chunks)

        # If no citations found, log warning
        if not citations_used:
            logger.warning(f"No citations found in response. Response preview: {display_response[:200]}")
            logger.warning(f"Text chunks available: {[c.get('citation_num') for c in text_chunks]}")

        # Add the referenced RAG context to the chat history (Solution A: Full context, no length limit)
        # This allows the model to refer back to previously retrieved content in follow-up questions
        logger.info(f"Adding {len(text_chunks)} text chunks and {len(image_chunks)} image chunks to session history")
        add_referenced_context_to_history(session_id, text_chunks, image_chunks)
        
        # Style the citations in the response text
        styled_response = style_citations_in_text(full_response, citations_used)
        
        # Display final styled response
        answer_placeholder.markdown(styled_response, unsafe_allow_html=True)
        
        # Display citations that were actually used
        display_citations_in_response(citations_used)
        
        # NOW handle images separately (after response text, below citations)
        if images:
            st.markdown("---")
            st.markdown("**🖼️ Referenced Images:**")
            for image in images:
                image_path = image.get("path", "")
                if image_path and image.get("filename"):
                    filename = image.get("filename", selected_file)
                    full_image_path = f'.data/result/{filename}/{image_path}'
                    if not pathlib.Path(full_image_path).exists():
                        full_image_path = f'.data/result/{filename}/auto/{image_path}'
                    
                    if pathlib.Path(full_image_path).exists():
                        try:
                            st.image(full_image_path, caption=f"From {filename}, page {image.get('page_idx', '?')}")
                        except Exception as e:
                            logger.error(f"Failed to display image: {e}")
        
        # Prepare content for message history (without base64 images)
        citations_content_for_history = format_citations_for_history(text_chunks, image_chunks)
        sources_section = f"📚 **All Retrieved Sources ({total_sources} references)**\n\n{citations_content_for_history}\n---\n\n"
        final_content = sources_section + "## 🤖 Answer\n\n" + styled_response
        
        # Save message with both original chunks and extracted citations
        st.session_state.messages.append(
            {
                "role": "assistant", 
                "content": final_content,
                "citations": citations_used,  # Citations actually used in response
                "text_chunks": text_chunks,   # All retrieved text chunks
                "image_chunks": image_chunks, # All retrieved image chunks
                "selected_file": selected_file
            }
        )