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
AIRTABLE_API_KEY = os.getenv("AIRTABLE_API_KEY")
AIRTABLE_BASE_ID = "app5fTUft32PUzoPv"
AIRTABLE_AGENTS_TABLE_ID = "tblEJJWL4bAFQqf0n"
AIRTABLE_BRAND_ELEMENTS_TABLE_ID = "tblQLSn8NDFAxL9eU"

async def stream_response(user_id, messages, session_id, agent_id):
    for message in messages:
        if message["role"] == "assistant":
            message["content"] = message["content"][message["content"].find(":")+1:]
    
    if len(messages) == 0:
        messages = []
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
                    
                    
            if response.status_code >= 400:
                error_text = await response.aread()
                try:
                    error_json = json.loads(error_text)
                    error_msg = error_json.get("detail") or str(error_json)
                except json.JSONDecodeError:
                    error_msg = error_text.decode("utf-8")


                st.session_state.error_message = f"Server Error {response.status_code}: {error_msg}"
                return  # Exit early, don't proceed to streaming
        
            first = True
            buffer = ""  # Buffer to accumulate data
            async for chunk in response.aiter_text():
                buffer += chunk  # Add the chunk to the buffer

                while True:
                    try:
                        # Try to parse a JSON object from the buffer
                        data, idx = json.JSONDecoder().raw_decode(buffer)
                        buffer = buffer[idx:].lstrip()  # Remove the parsed object from the buffer
                        
                        # Now process the data
                        content = data.get("chunk", {}).get("choices", [{}])[0].get("delta", {}).get("content")
                        if content:
                            if first:
                                agent_id = data.get("agent_id")
                                yield f"{agent_id}: "
                                st.session_state.current_agent_id = agent_id
                                first = False
                            yield content
                    except json.JSONDecodeError:
                        # If there's not enough data to decode yet, just wait for more chunks
                        break


def format_messages(messages):
    text = ""
    for m in messages:
        if m["role"] == "user":
            text += f"C: {m['content']}\n"
        else:
            text += f"B: {m['content']}\n"

    return text


def _normalize_brand_element_key(name: str) -> str:
    """Return Brand Element display name as-is for user_info lookup."""
    return name if isinstance(name, str) else ""


def _airtable_get_all(table_id: str):
    """Fetch all records from an Airtable table, handling pagination."""
    if not AIRTABLE_API_KEY:
        raise RuntimeError("AIRTABLE_API_KEY is not set in environment")
    headers = {
        "Authorization": f"Bearer {AIRTABLE_API_KEY}",
    }
    url = f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/{table_id}"
    params = {}
    all_records = []
    while True:
        resp = requests.get(url, headers=headers, params=params, timeout=20)
        resp.raise_for_status()
        data = resp.json()
        all_records.extend(data.get("records", []))
        offset = data.get("offset")
        if not offset:
            break
        params["offset"] = offset
    return all_records


@st.cache_data(ttl=300)
def get_configured_agents():
    try:
        # Fetch Brand Elements and build lookup by record id
        be_records = _airtable_get_all(AIRTABLE_BRAND_ELEMENTS_TABLE_ID)
        brand_element_by_id = {}
        for rec in be_records:
            fields = rec.get("fields", {})
            name = fields.get("Name") or fields.get("name") or ""
            key = _normalize_brand_element_key(name)
            brand_element_by_id[rec.get("id")] = {"id": rec.get("id"), "name": name, "key": key}

        # Fetch Agents
        ag_records = _airtable_get_all(AIRTABLE_AGENTS_TABLE_ID)
        agents = []
        for rec in ag_records:
            fields = rec.get("fields", {})
            agent_name = fields.get("name") or fields.get("Name") or "Unnamed Agent"
            linked_ids = fields.get("Brand Elements") or []
            brand_elements = [brand_element_by_id[x] for x in linked_ids if x in brand_element_by_id]
            agents.append({
                "id": rec.get("id"),
                "name": agent_name,
                "brand_elements": brand_elements,
            })
        return {"agents": agents}
    except Exception:
        return {"agents": []}


def get_user_info():
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {API_TOKEN}"}
    user_info = requests.get(f"{HOST}/user_info", headers=headers, params={"user_id": st.session_state.user_id})
    if user_info.status_code == 200:
        user_info_data = user_info.json()
    else:
        user_info_data = {"error": "Failed to fetch user info"}
    return user_info_data

def set_user_name(name):
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {API_TOKEN}"}
    user_info = requests.post(f"{HOST}/user_name", headers=headers, json={"user_id": st.session_state.user_id, "name":name})
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

        agent_id = st.session_state.current_agent_id or "Default"
        final_message = f"{agent_id}: {streamed_text}"

        st.session_state.messages.append({"role": "assistant", "content": final_message})



        st.rerun()

    except Exception as e:
        raise ValueError(e)

def main():
    if "agent_id" not in st.session_state:
        st.session_state.agent_id = None

    if "session_id" not in st.session_state:
        st.session_state.session_id = str(uuid.uuid4())

    if "user_id" not in st.session_state:
        st.subheader("Welcome")
        number_input = st.text_input("Enter a user id:", key="number_input")
        if number_input and not number_input.isnumeric():
            st.error("Please enter a valid number.")
        if st.button("Ok"):
            if number_input.isnumeric():
                st.session_state.user_id= int(number_input)
                st.rerun()
            else:
                st.error("Input must be a number.")

        st.write("---")
        st.subheader("Configured Agents")
        agents = get_configured_agents()
        if not agents or not agents.get("agents"):
            st.info("No agents found or failed to fetch agents.")
        else:
            st.write([a["name"] for a in agents["agents"]])
    else:
        user_info_data = get_user_info()

        if user_info_data.get("name") == None:
            name_input = st.text_input("Enter a name:", key="name_input")
            if st.button("Ok"):
                if name_input:
                    st.session_state.user_info_data = set_user_name(name_input)
                    st.rerun()
                else:
                    st.error("Please enter a name.")
        else:
            updated_keys = []
            if "user_info" in st.session_state:
                prev_be = (st.session_state.user_info or {}).get("brand_elements", {})
                curr_be = (user_info_data or {}).get("brand_elements", {})
                for k, v in (curr_be or {}).items():
                    if v is not None and (prev_be.get(k) in (None, "")):
                        updated_keys.append(k)
            st.session_state.user_info = user_info_data

            # Initialize chat history
            if "messages" not in st.session_state:
                st.session_state.messages = []

            if "expander_expanded" not in st.session_state:
                st.session_state.expander_expanded = True

            if "page_title" not in st.session_state:
                st.session_state.page_title = ""

            if "error_message" not in st.session_state:
                st.session_state.error_message = ""
                
            st.markdown("""<style>button[kind="primary"] {
                background-color: #ff7893;
                }
            </style>""", unsafe_allow_html=True)
            
            # Display sidebar
            with st.sidebar:
                st.subheader("Session ID")
                st.code(st.session_state.session_id, language='text')
                
                st.subheader("User Information")
                user_info_placeholder = st.empty()
                user_info_placeholder.json(user_info_data)

                if st.session_state.error_message:
                    st.subheader("Error")
                    st.markdown(st.session_state.error_message)

            if st.session_state.page_title == "":
                agents_cfg = get_configured_agents()
                user_be = (st.session_state.user_info or {}).get("brand_elements", {})

                st.subheader("Brand Elements")
                agents_list = [a for a in agents_cfg.get("agents", []) if a.get("brand_elements")]
                num_cols = 3
                for row_start in range(0, len(agents_list), num_cols):
                    row_agents = agents_list[row_start:row_start+num_cols]
                    cols = st.columns(len(row_agents))
                    for idx, agent in enumerate(row_agents):
                        with cols[idx]:
                            be_list = agent.get("brand_elements", [])
                            # Determine completion
                            completed = all(bool(user_be.get(be.get("key"))) for be in be_list)
                            # Button: primary if incomplete
                            if completed:
                                if st.button(agent["name"], use_container_width=True, key=f"start_{agent['id']}"):
                                    st.session_state.page_title = agent["name"]
                                    st.session_state.agent_id = agent["name"]
                                    st.rerun()
                            else:
                                if st.button(agent["name"], use_container_width=True, type="primary", key=f"start_{agent['id']}"):
                                    st.session_state.page_title = agent["name"]
                                    st.session_state.agent_id = agent["name"]
                                    st.rerun()
                            # Brand Elements status list
                            for be in be_list:
                                name = be.get("name")
                                value = user_be.get(be.get("key"))
                                if value:
                                    st.success(f"✅ {name}")
                                else:
                                    st.warning(f"⏳ {name}")

                st.write("---")
                st.subheader("Main Coaching Bot")
                if st.button("Main Coaching Bot", use_container_width=True, key="start_main"):
                    st.session_state.page_title = "Main Coaching Bot"
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
