import os
import chromadb
import streamlit as st
import requests
from dotenv import load_dotenv
from openai import OpenAI
from doc_helper import read_file
load_dotenv()

#INITIALIZING ChromaDB CLIENT
db= chromadb.PersistentClient(path="./chromadb")
brain = db.get_or_create_collection("harvey")
memory = db.get_or_create_collection("harvey_chat")
SYSTEM_PROMPT = ("You are Kortex, you are here to optimize learning"
                 "You do not do the students work, you do not write essays or give the answer to an equation"
                 "NOTE REORGANIZATION: when provided with notes, clean up typos and formatting, restructure them clearly, create a cross reference section linking the notes with past notes"
                 "STUDY PLANNING: when asked to plan study sessions break large assignments down into smaller tasks with dates, allocate heavy tasks to prime focus time"
                 "RECALL: when asked to study or test knowledge, challenge the user with conceptual questions, use real world analogies"
                 "Be direct, encouraging, efficient, dont use filler words"
                 "Maximize information density"
                 "if the users notes are missing critical context to be useful")


def shorten(text, limit=500):
    return text if len(text) <= limit else text[:limit] + " ... rest removed to keep it shorter"

#CHUNKS DOWN DOCUMENT
def chunk_by_sentence(text, max_size=400):
    sentences = text.split(", ")
    chunks = []
    current = ""
    for sentence in sentences:
        if len(current) + len(sentence) < max_size:
            current += sentence + ". "
        else:
            if current.strip():
                chunks.append(current.strip())
            current = sentence + ". "
    if current.strip():
        chunks.append(current.strip())
    return chunks

#STORES DOCUMENTS
def store_document(file):
    text = read_file(file)
    chunks = chunk_by_sentence(text)
    prefix = file.name.replace(" ", "_")
    brain.add(
        documents=chunks,
        ids=[f"{prefix}_chunks{i}" for i in range(len(chunks))],
    )
    return len(text), len(chunks)

#ADDING EXCHANGES TO MEMORY
def remember_exchange(question, answer):
    #Put this Q and A into long term memory so AI can remember
    memory.add(
        documents=[f"Question: {question}\n and Answer: {shorten(answer)}"],
        ids=[f"turn{memory.count()}"]
    )

#INTERFACE SETUP
st.set_page_config(page_title="Kortex", page_icon="K", layout="wide")
st.title("Kortex")
st.subheader("Set up your AI in the Settings Tab")

#STARTING SESSION STATE
if "messages" not in st.session_state:
    st.session_state["messages"] = []

#SIDEBAR
with st.sidebar:
    st.header("Settings")
    with st.form("settings"):
        name = st.text_input("Enter your name: ")
        mood = st.text_input("Enter a prompt for how you want Harvey to act: ")
        creativity = st.slider("Creativity", 0.0, 1.0, 0.0)
        remember = st.slider("Recent turns to keep", 0,10,3)
        recall = st.slider("Old exchanges to look up", 0,10,3)
        saved = st.form_submit_button("Save")
    if saved:
        st.write(f"Saved mood is {mood} and creativity is {creativity}.")
    st.caption(f"In memory: {brain.count()} chunks")
    st.caption(f"Long term memory: {memory.count()} exchanges")
    st.caption(f"On screen: {len(st.session_state.messages)} messages")

    if st.button("Clear chat"):
        st.session_state.messages = []
        st.rerun()
    if st.button ("Forget memory"):
        db.delete_collection("harvey_chat")
        st.rerun()
    if st.button ("Forget all documents"):
        db.delete_collection("harvey")
        st.rerun()

#OLD CONVERSATIONS APPEAR
for old in st.session_state.messages:
    with st.chat_message(old["role"]):
        st.write(old["content"])

#INPUT
user_input = st.chat_input("Ask something here...",
                       accept_file=True,
                       file_type = ["pdf", "txt"],)

if user_input:
    prompt = user_input.text
    prompt_file = None
    if user_input.files:
        prompt_file = user_input.files[0]

    #USER MESSAGE DISPLAY
    with st.chat_message("user"):

        if prompt_file:
            #text = read_file(prompt_file)
            #chunks = chunk_by_sentence(text)
            clean_len, n_chunks = store_document(prompt_file)
            st.write(f"{prompt_file.name}")
            st.caption(
                f"{clean_len} characters. "
                f"stored as {n_chunks} chunks."
            )
        if prompt:
            st.write(f"{prompt}")

        st.session_state.messages.append(
            {"role": "user", "content": prompt if prompt else f"attached: {prompt_file.name}"}
        )

    #ASSISTANT MESSAGE DISPLAY
    with st.chat_message("assistant"):
        if prompt == "Cat Fact":
            r = requests.get("https://catfact.ninja/fact")
            fact = r.json()["fact"]
            answer = fact
            st.write(f"{fact}")
        elif not prompt:
            answer = "Saved. Ask something here..."
            st.write(answer)

        #AI GENERATION
        else:
            notes = []
            docs, dists = [], []
            if brain.count() > 0:
                hits = brain.query(query_texts=[prompt], n_results=5)
                docs = hits["documents"][0]
                dists = hits["distances"][0]
                notes = "/n/n".join(hits["documents"][0])

            recalled = []
            if recall > 0 and memory.count() > remember:
                found = memory.query(query_texts=[prompt], n_results=recall)
                recalled = "\n\n".join(found["documents"][0])

            if notes or recalled:
                full_prompt= (f"Answer using the notes if useful"
                              f"If the notes dont contain the answer, say so"
                              f"The notes could contain some irrelevant information"
                              f"You can answer using your knowledge/information"
                              f"This is the user's name: {name}"
                              f"This is how the user wants you to act: {mood}"
                              f"{notes}"
                              f"Things we talked about earlier {recalled}"
                              f"User question: {prompt}")
            else:
                full_prompt= prompt

            with st.expander("What I looked up"):
                st.caption("From your documents")
                st.text(shorten(notes, 800) or "nothing")
                st.caption("From earlier conversations")
                st.text(shorten(recalled, 800) or "nothing")

            client = OpenAI(
                #base_url="https://models.github.ai/inference",
                base_url="https://api.groq.com/openai/v1",
                api_key=os.getenv("AI_TOKEN") or st.secrets["AI_TOKEN"],
            )

            messages = [{"role": "system", "content": SYSTEM_PROMPT}]
            past = st.session_state.messages[:-1]
            if remember>0:
                for m in past[-(remember*2):]:
                    messages.append({"role": m["role"], "content": shorten(m["content"])})
            messages.append({"role": "user", "content": full_prompt})

            r = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                temperature=creativity,
                messages=messages
            )

            answer = r.choices[0].message.content
            st.write(answer)

            remember_exchange(prompt, answer)
        st.session_state.messages.append({"role": "assistant", "content": answer})