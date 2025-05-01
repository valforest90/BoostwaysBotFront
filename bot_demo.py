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
    
    if len(messages) == 0:
        messages = [{"role":"user", "content":"Hello."}]
    payload = {
        "user_id": user_id,
        "messages": messages,
        "stream": True,
        "session_id": session_id,
        "previous_agent_id": agent_id,
    }
    if st.session_state.agent_id:
        payload["agent_id"] = st.session_state.agent_id
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
                            st.session_state.current_agent_id = agent_id
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


def get_user_info():
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {API_TOKEN}"}
    user_info = requests.get(f"{HOST}/user_info", headers=headers, params={"user_id": st.session_state.user_id})
    if user_info.status_code == 200:
        user_info_data = user_info.json()
    else:
        user_info_data = {"error": "Failed to fetch user info"}
    return user_info_data

def process_prompt():
    try:
        # Use Streamlit's placeholder to dynamically update assistant message
        message_placeholder = st.chat_message("assistant").empty()
        streamed_text = ""

        if "current_agent_id" not in st.session_state:
            st.session_state.current_agent_id = "Default"  

        async def run_stream():
            async for chunk in stream_response(
                st.session_state.user_id,
                st.session_state.messages,
                st.session_state.session_id,
                st.session_state.current_agent_id,
            ):
                nonlocal streamed_text
                streamed_text += chunk
                message_placeholder.markdown(streamed_text)

        asyncio.run(run_stream())

        st.session_state.messages.append({"role": "assistant", "content": streamed_text})



        st.rerun()

    except Exception as e:
        raise ValueError(e)

def main():
    if "agent_id" not in st.session_state:
        st.session_state.agent_id = None

    if "session_id" not in st.session_state:
        st.session_state.session_id = str(uuid.uuid4())

    if "user_id" not in st.session_state:
        st.session_state.user_id = USER_ID
    user_info_data = get_user_info()

    updated_keys = []
    if "user_info" in st.session_state:
        for key in ["vision", "manifesto", "positioning", "brand_story", "ideal_customer"]:
            if user_info_data.get(key) != None and st.session_state.user_info.get(key) == None:
                updated_keys.append(key)
    st.session_state.user_info = user_info_data


    st.session_state.disabled = user_info_data.get("vision")==None or user_info_data.get("manifesto")==None or user_info_data.get("positioning")==None or user_info_data.get("brand_story")==None or user_info_data.get("ideal_customer")==None

    # Initialize chat history
    if "messages" not in st.session_state:
        st.session_state.messages = []

    if "expander_expanded" not in st.session_state:
        st.session_state.expander_expanded = True

    if "page_title" not in st.session_state:
        st.session_state.page_title = ""
        
    st.markdown("""<style>button[kind="primary"] {
        background-color: #ff7893;
        }
    </style>""", unsafe_allow_html=True)
    
    # Display sidebar
    with st.sidebar:
        st.subheader("Brand Basics")

        if st.session_state.user_info.get("ideal_customer"):
            if st.button("Ideale Klantenkenner", use_container_width=True):
                st.session_state.page_title = "Ideale Klantenkenner"
                st.session_state.agent_id = "Ideale Klantenkenner"
                st.session_state.messages = []
        else:
            if st.button("Ideale Klantenkenner", use_container_width=True, type="primary"):
                st.session_state.page_title = "Ideale Klantenkenner"
                st.session_state.agent_id = "Ideale Klantenkenner"
                st.session_state.messages = []

        if st.session_state.user_info.get("vision"):
            if st.button("Missie&Visie architect", use_container_width=True):
                st.session_state.page_title = "Missie&Visie architect"
                st.session_state.agent_id = "Missie&Visie architect"
                st.session_state.messages = []
        else:
            if st.button("Missie&Visie architect", use_container_width=True, type="primary"):
                st.session_state.page_title = "Missie&Visie architect"
                st.session_state.agent_id = "Missie&Visie architect"
                st.session_state.messages = []

        if st.session_state.user_info.get("positioning"):
            if st.button("Positioneringsexpert", use_container_width=True):
                st.session_state.page_title = "Positioneringsexpert"
                st.session_state.agent_id = "Positioneringsexpert"
                st.session_state.messages = []
        else:
            if st.button("Positioneringsexpert", use_container_width=True, type="primary"):
                st.session_state.page_title = "Positioneringsexpert"
                st.session_state.agent_id = "Positioneringsexpert"
                st.session_state.messages = []

        if st.session_state.user_info.get("manifesto") and st.session_state.user_info.get("brand_story"):
            if st.button("De Pitchmaker", use_container_width=True):
                st.session_state.page_title = "De Pitchmaker"
                st.session_state.agent_id = "De Pitchmaker"
                st.session_state.messages = []
        else:
            if st.button("De Pitchmaker", use_container_width=True, type="primary"):
                st.session_state.page_title = "De Pitchmaker"
                st.session_state.agent_id = "De Pitchmaker"
                st.session_state.messages = []

        st.subheader("Main Bot")

        if st.button("Boostways Bot", use_container_width=True, disabled=st.session_state.get('disabled')):
            st.session_state.page_title = "Boostways Bot"
            st.session_state.agent_id = None
            st.session_state.messages = []

        st.subheader("User Information")
        user_info_placeholder = st.empty()
        user_info_placeholder.json(user_info_data)

    if st.session_state.page_title == "":
        st.subheader("Brand Basics")

        if st.session_state.user_info.get("ideal_customer"):
            if st.button("Ideale Klantenkenner", use_container_width=True, key="b1"):
                st.session_state.page_title = "Ideale Klantenkenner"
                st.session_state.agent_id = "Ideale Klantenkenner"
                st.rerun()
        else:
            if st.button("Ideale Klantenkenner", use_container_width=True, type="primary", key="b2"):
                st.session_state.page_title = "Ideale Klantenkenner"
                st.session_state.agent_id = "Ideale Klantenkenner"
                st.rerun()

        if st.session_state.user_info.get("vision"):
            if st.button("Missie&Visie architect", use_container_width=True, key="b3"):
                st.session_state.page_title = "Missie&Visie architect"
                st.session_state.agent_id = "Missie&Visie architect"
                st.rerun()
        else:
            if st.button("Missie&Visie architect", use_container_width=True, type="primary", key="b4"):
                st.session_state.page_title = "Missie&Visie architect"
                st.session_state.agent_id = "Missie&Visie architect"
                st.rerun()

        if st.session_state.user_info.get("positioning"):
            if st.button("Positioneringsexpert", use_container_width=True, key="b5"):
                st.session_state.page_title = "Positioneringsexpert"
                st.session_state.agent_id = "Positioneringsexpert"
                st.rerun()
        else:
            if st.button("Positioneringsexpert", use_container_width=True, type="primary", key="b6"):
                st.session_state.page_title = "Positioneringsexpert"
                st.session_state.agent_id = "Positioneringsexpert"
                st.rerun()

        if st.session_state.user_info.get("manifesto") and st.session_state.user_info.get("brand_story"):
            if st.button("De Pitchmaker", use_container_width=True, key="b7"):
                st.session_state.page_title = "De Pitchmaker"
                st.session_state.agent_id = "De Pitchmaker"
                st.rerun()
        else:
            if st.button("De Pitchmaker", use_container_width=True, type="primary", key="b8"):
                st.session_state.page_title = "De Pitchmaker"
                st.session_state.agent_id = "De Pitchmaker"
                st.rerun()

        st.subheader("Main Bot")
        if st.session_state.get('disabled'):
            st.text("Gelieve alle merkbasics te voltooien om verder te gaan.")
        if st.button("Boostways Bot", use_container_width=True, disabled=st.session_state.get('disabled'), key="b9"):
            st.session_state.page_title = "Boostways Bot"
            st.session_state.agent_id = None
            st.rerun()

    if st.session_state.page_title != "":
        st.title(st.session_state.page_title)

        # Display chat messages from history on app rerun
        for message in st.session_state.messages:
            with st.chat_message(message["role"]):
                st.markdown(message["content"])

        # ✅ Notifications below messages
        for key in updated_keys:
            st.success(f'New value saved: {key}', icon="✅")

        # React to user input
        if prompt := st.chat_input("Hallo, hoe kan ik je vandaag helpen?"):
            st.chat_message("user").markdown(prompt)
            st.session_state.messages.append({"role": "user", "content": prompt})
            process_prompt()

        # First message
        if len(st.session_state.messages) == 0:
            process_prompt()

    
    with st.sidebar:
        text_contents = f"User {st.session_state.user_id}\n"
        text_contents += format_messages(st.session_state.messages)
        st.download_button("Download Conversation", text_contents)


if __name__ == "__main__":
    main()
