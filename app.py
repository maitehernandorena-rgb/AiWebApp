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
brain = db.get_or_create_collection("zeus")

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

#INTERFACE SETUP
st.set_page_config(page_title="Harvey", page_icon="H", layout="wide")
st.title("Harvey")
st.subheader("Set up your AI in the Settings Tab")
st.write("Harvey is a friendly AI here to help you with your homework or any concepts you are struggling to understand. """)

#SIDEBAR
with st.sidebar:
    st.header("Settings")
    with st.form("settings"):
        name = st.text_input("Enter your name: ")
        mood = st.multiselect("Select a few options for his mood:", ["nerdy", "caring", "organized", "straight to the point"])
        creativity = st.slider("Creativity", 0.0, 1.0, 0.0)
        saved = st.form_submit_button("Save")
    if saved:
        st.write(f"Saved mood is {mood} and creativity is {creativity}.")
    st.caption(f"In memory: {brain.count()} chunks")

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
            text = read_file(prompt_file)
            #chunks = chunk_by_sentence(text)
            clean_len, n_chunks = store_document(prompt_file)
            if prompt:
                st.write(f"{prompt}")
            st.write(f"{prompt_file.name}")
            st.caption(
                f"{clean_len} characters. "
                f"stored as {n_chunks} chunks."
            )

    #ASSISTANT MESSAGE DISPLAY
    with st.chat_message("assistant"):
        if prompt == "Cat Fact":
            r = requests.get("https://catfact.ninja/fact")
            fact = r.json()["fact"]
            st.write(f"{fact}")
        if not prompt:
            st.write(f"Saved. Ask something here...")

        #AI GENERATION
        else:
            notes = 0
            if brain.count() > 0:
                hits = brain.query(query_texts=[prompt], n_results=5)
                notes = "/n/n".join(hits["documents"][0])
            if notes:
                full_prompt= (f"Answer using the notes if useful"
                              f"If the notes dont contain the answer, say so"
                              f"The notes could contain some irrelevant information"
                              f"{notes}"
                              f"User question: {prompt}")
            else:
                full_prompt= prompt
            #system_prompt = f"""You are a {mood} assistant with {creativity} creativity from a scale from 0 to 1. You help students with homework or concepts hard to understand.
            #Dont pretend you are anything but an AI here to help with homework or concepts hard to grasp. You do not intervene in the users personal life.
            #Current prompt: {prompt}
            #and here is {prompt_file} to help you answer the question"""
            client = OpenAI(
                #base_url="https://models.github.ai/inference",
                base_url="https://api.groq.com/openai/v1",
                api_key=os.getenv("AI_TOKEN") or st.secrets["AI_TOKEN"],
            )
            r = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                temperature=creativity,
                messages=([{"role": "system", "content": full_prompt},
                          {"role": "user", "content": prompt}])
            )

            response = r.choices[0].message.content

            st.write(response)