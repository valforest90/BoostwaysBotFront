import os
import uuid
import httpx
import asyncio
import json
import requests
import streamlit as st
from dotenv import load_dotenv
load_dotenv()

HOST = os.getenv("HOST")
API_TOKEN = os.getenv("API_TOKEN")
USER_ID = 3

async def stream_response(user_id, messages, session_id, agent_id):
    for message in messages:
        if message["role"] == "assistant":
            message["content"] = message["content"][message["content"].find(":")+1:]
    payload = {
        "user_id": user_id,
        "messages": messages,
        "stream": True,
        "session_id": session_id,
        "agent_id": agent_id,
    }
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {API_TOKEN}"}

    async with httpx.AsyncClient(timeout=None) as client:
        async with client.stream("POST", f"{HOST}/coach", headers=headers, json=payload) as response:
            first = True
            async for chunk in response.aiter_text():
                try:
                    data = json.loads(chunk)
                    content = data.get("chunk", {}).get("choices", [{}])[0].get("delta", {}).get("content")
                    if content:
                        if first:
                            agent_id = data.get("agent_id")
                            yield f"{agent_id}: "
                            st.session_state.agent_id = agent_id
                            first = False
                        yield content
                except json.JSONDecodeError:
                    yield "[Stream Error]"



def format_messages(messages):
    text = ""
    for m in messages:
        if m["role"] == "user":
            text += f"C: {m['content']}\n"
        else:
            text += f"B: {m['content']}\n"

    return text

def main():
    st.title("Boostways Bot")

    if "session_id" not in st.session_state:
        st.session_state.session_id = str(uuid.uuid4())

    if "user_id" not in st.session_state:
        st.session_state.user_id = USER_ID

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
        try:
            st.chat_message("user").markdown(prompt)
            st.session_state.messages.append({"role": "user", "content": prompt})

            # Use Streamlit's placeholder to dynamically update assistant message
            message_placeholder = st.chat_message("assistant").empty()
            streamed_text = ""

            if "agent_id" not in st.session_state:
                st.session_state.agent_id = "Default"  

            async def run_stream():
                async for chunk in stream_response(
                    st.session_state.user_id,
                    st.session_state.messages,
                    st.session_state.session_id,
                    st.session_state.agent_id,
                ):
                    nonlocal streamed_text
                    streamed_text += chunk
                    message_placeholder.markdown(streamed_text)

            asyncio.run(run_stream())

            st.session_state.messages.append({"role": "assistant", "content": streamed_text})
            
            # Get user information from /user_info
            headers = {"Content-Type": "application/json", "Authorization": f"Bearer {API_TOKEN}"}
            user_info = requests.get(f"{HOST}/user_info", headers=headers, params={"user_id": st.session_state.user_id})
            if user_info.status_code == 200:
                user_info_data = user_info.json()
            else:
                user_info_data = {"error": "Failed to fetch user info"}

            # Display user info in the sidebar
            with st.sidebar:
                st.header("User Info")
                st.json(user_info_data)

            with st.sidebar:
                st.header("Debug Info")
                st.caption(f"Sesson ID: {st.session_state.session_id}")

                text_contents = f"User {st.session_state.user_id}\n"
                text_contents += format_messages(st.session_state.messages)
                st.download_button("Download Conversation", text_contents)

        except Exception as e:
            raise ValueError(e)

if __name__ == "__main__":
    main()
