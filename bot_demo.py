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

async def stream_response(user_id, messages, session_id):
    for message in messages:
        if message["role"] == "assistant":
            message["content"] = message["content"][message["content"].find(":")+1:]
    print(messages)
    user_id = "3"
    payload = {
        "user_id": user_id,
        "messages": messages,
        "stream": True,
        "session_id": session_id,
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


# Not sure if necessary for the chatbot
def upsert_user_details(user_id, user_details):
    text = ""
    for key, value in user_details.items():
        if value:
            text += f"{key}: {value}\n"

    json_data = {"user_id": user_id, "content": text}
    requests.post(f"{HOST}/v1/user/upsert", json=json_data)


def main():
    st.title("Boostways Bot")

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
        try:
            st.chat_message("user").markdown(prompt)
            st.session_state.messages.append({"role": "user", "content": prompt})

            # Use Streamlit's placeholder to dynamically update assistant message
            message_placeholder = st.chat_message("assistant").empty()
            streamed_text = ""

            async def run_stream():
                async for chunk in stream_response(
                    st.session_state.user_id,
                    st.session_state.messages,
                    st.session_state.session_id,
                ):
                    nonlocal streamed_text
                    streamed_text += chunk
                    message_placeholder.markdown(streamed_text)

            asyncio.run(run_stream())

            st.session_state.messages.append({"role": "assistant", "content": streamed_text})


            with st.sidebar:
                st.header("Debug Info")
                st.caption(f"Sesson ID: {st.session_state.session_id}")

                # with st.expander("Retrieved Boostways Resources"):
                #     relevant_resources = debug_info["relevant_resources"]
                #     st.write(relevant_resources)



                text_contents = f"User {st.session_state.user_id}\n"
                text_contents += format_messages(st.session_state.messages)
                # Not sure if wanted for the chatbot
                st.download_button("Download Conversation", text_contents)
        except Exception as e:
            raise ValueError(e)



if __name__ == "__main__":
    main()
