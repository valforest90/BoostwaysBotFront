import os
import uuid

import requests
import streamlit as st

#https://boostwaysbotfront-ijb2ot67q68andeqbm3gyf.streamlit.app/
HOST = "https://pregnant-tessie-boostways-bv-f469777c.koyeb.app"
API_TOKEN = os.getenv("API_TOKEN")
def get_response(user_id, messages, session_id):
    payload = {
        "user_id": "1",
        "messages": messages,
        "stream": False,
        "session_id": "session_streamlit",
        "audience":"external"
    }
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {API_TOKEN}"}

    headers = {
        "Authorization":f"Bearer {os.getenv("API_KEY")}",
        "Content-Type": "application/json"}
    response = requests.post(f"{HOST}/coach", headers=headers, json=payload)

    return response.json()


def format_messages(messages):
    text = ""
    for m in messages:
        if m["role"] == "user":
            text += f"C: {m['content']}\n"
        else:
            text += f"B: {m['content']}\n"

    return text


# Not sure if necessary for the internal chatbot
def upsert_user_details(user_id, user_details):
    text = ""
    for key, value in user_details.items():
        if value:
            text += f"{key}: {value}\n"

    json_data = {"user_id": user_id, "content": text}
    requests.post(f"{HOST}/v1/user/upsert", json=json_data)


def main():
    st.title("Boostways Internal Bot")

    if "session_id" not in st.session_state:
        st.session_state.session_id = str(uuid.uuid4())

    if "user_id" not in st.session_state:
        st.session_state.user_id = str(uuid.uuid4())

    # Initialize chat history
    if "messages" not in st.session_state:
        st.session_state.messages = []

    if "expander_expanded" not in st.session_state:
        st.session_state.expander_expanded = True

    # Display chat messages from history on app rerun
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    # React to user input
    if prompt := st.chat_input("Hallo, hoe kan ik je vandaag helpen?"):
        # Display user message in chat message container
        st.chat_message("user").markdown(prompt)
        # Add user message to chat history
        st.session_state.messages.append({"role": "user", "content": prompt})
        response = get_response(st.session_state.user_id, st.session_state.messages, st.session_state.session_id)
        try:
            assistant_message = response["choices"][0]["message"]["content"]
        
            assistant_message = response["agent_id"] + ": " + assistant_message
            # Display assistant response in chat message container
            with st.chat_message("assistant"):
                st.markdown(assistant_message)

            # Add assistant response to chat history
            st.session_state.messages.append({"role": "assistant", "content": assistant_message})

            with st.sidebar:
                st.header("Debug Info")
                st.caption(f"Sesson ID: {st.session_state.session_id}")

                # with st.expander("Retrieved Boostways Resources"):
                #     relevant_resources = debug_info["relevant_resources"]
                #     st.write(relevant_resources)



                text_contents = f"User {st.session_state.user_id}\n"
                text_contents += format_messages(st.session_state.messages)
                # Not sure if wanted for the internal chatbot
                st.download_button("Download Conversation", text_contents)
        except Exception as e:
            raise ValueError(response)


if __name__ == "__main__":
    main()
