import sys, pathlib
import streamlit as st

sys.path.append(pathlib.Path(__file__).parents[1].as_posix())

from utils.get_model import get_prompted_model, get_prompted_model_with_params, DEFAULT_PARAMETERS, validate_parameters
from utils.functions import encode_image
from backend.backend import get_knowledge, form_context_info
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
        "parameters": DEFAULT_PARAMETERS.copy()  # Add default parameters for new session
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
    st.session_state.has_init = True
    st.session_state.model = get_prompted_model_with_params(**st.session_state.current_parameters)
    logger.info("Streamlit session initialized with default parameters.")
    
    # Create initial session if no sessions exist
    if not st.session_state.chat_sessions:
        create_session()
    
load_components()

# NOTE - construct chatting session
construct_chatting_session()

# NOTE - load models

if user_input := st.chat_input("Ask something *w*"):
    with st.chat_message("user"):
        st.markdown(user_input)

    st.session_state.messages.append({"role": "user", "content": user_input})
    logger.info(f"User input: {user_input}")

    texts, images = form_context_info(user_input)
    args = {"context_info": texts, "question": user_input}

    logger.debug("Starting model streaming...")
    with st.chat_message("assistant"):
        placeholder = st.empty()
        full_response = ""
        for chunk in st.session_state.model.stream(args):
            full_response += chunk
            placeholder.markdown(full_response + "|")

        for image in images:
            code = encode_image(f'.data/result/manual/{image.get("path", "")}', prefix=True)
            full_response += f"\n![Image]({code})"

        placeholder.markdown(full_response)
        st.session_state.messages.append(
            {
                "role": "assistant",
                "content": full_response,
            }
        )
