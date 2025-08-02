import streamlit as st


def create_session():
    st.session_state.current_chat_index += 1
    chat = {
        "name": f"default chat session {st.session_state.current_chat_index}",
        "messages": [],
        "history": [],
    }
    st.session_state.chat_sessions[st.session_state.current_chat_index] = chat
    st.session_state.messages = chat["messages"]


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
        with st.container(height=520, border=False):
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


def switch_tab(switch_to: int):
    # save current chat session
    current_index = st.session_state.current_chat_index
    st.session_state.chat_sessions[current_index][
        "messages"
    ] = st.session_state.messages

    st.session_state.chat_sessions[current_index][
        "history"
    ] = st.session_state.backend.history

    # load selected session
    st.session_state.current_chat_index = switch_to
    st.session_state.messages = st.session_state.chat_sessions[switch_to]["messages"]
    st.session_state.backend.set_history(
        st.session_state.chat_sessions[switch_to]["history"]
    )


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
