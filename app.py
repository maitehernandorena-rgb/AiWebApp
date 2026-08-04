import streamlit as st
import requests
import os
from dotenv import load_dotenv
from openai import OpenAI
from doc_helper import read_file
import chromadb

db= chromadb.PersistentClient(path="./chromadb")
brain = db.get_or_create_collection("zeus")

#digests the document
def chunk_by_sentence(text, max_size=400):
    sentences = text.split(", ")
    chunks = []
    current = ""
    for sentence in sentences:
        if len(current) + len(sentence) < max_size:
            current += sentence + ". "
        else:
            chunks.append(current)
            current = sentence + ". "
    if current.strip():
        chunks.append(current.strip())
    return chunks

#stores document
def store_document(file):
    text = read_file(file)
    chunks = chunk_by_sentence(text)

    prefix = file.name.replace(" ", "_")
    brain.add(
        documents=chunks,
        ids=[f"{prefix}_chunks{i}" for i in range(len(chunks))],
    )
    return len(text), len(chunks)


st.set_page_config(page_title="Harvey", page_icon="H", layout="wide")

st.title("Harvey")
st.subheader("Set up your AI in the Settings Tab")
st.write("Harvey is an friendly AI here to help you with your homework or any concepts you are struggling to understand. """)


with st.sidebar:
    st.header("Settings")
    with st.form("settings"):
        name = st.text_input("Enter your name: ")
        mood = st.multiselect("Select a few options for his mood:", ["nerdy", "caring", "organized", "straight to the point"])
        creativity = st.slider("Creativity", 0.0, 1.0, 0.0)
        uploaded = st.file_uploader("Add your notes here: ", type=["pdf", "txt"])
        saved = st.form_submit_button("Save")
    if saved:
        st.write(f"Saved mood is {mood} and creativity is {creativity}.")

import requests

user_input = st.chat_input("Ask something here...",
                       accept_file=True,
                       file_type = ["pdf", "txt"],)


if user_input:
    prompt = user_input.text
    prompt_file = None
    if user_input.files:
        prompt_file = user_input.files[0]
    with st.chat_message("user"):
        if prompt_file:
            text = read_file(prompt_file)
            #chunks = chunk_by_sentence(text)
            clean_len, n_chunks = store_document(prompt_file)
            st.write(f"{prompt_file.name}")
            st.caption(
                f"{clean_len} characters."
                f"stored as {n_chunks} chunks."
            )
        else:
            st.write(f"{prompt}")
    with st.chat_message("assistant"):
        if prompt == "Cat Fact":
            r = requests.get("https://catfact.ninja/fact")
            fact = r.json()["fact"]
            st.write(f"{fact}")
        else:
            system_prompt = f"""You are a {mood} assistant with {creativity} creativity from a scale from 0 to 1. You help students with homework or concepts hard to understand.
            Dont pretend you are anything but an AI here to help with homework or concepts hard to grasp. You do not intervene in the users personal life.
            Current prompt: {prompt}"""
            load_dotenv()
            client = OpenAI(
                #base_url="https://models.github.ai/inference",
                base_url="https://api.groq.com/openai/v1",
                api_key=os.getenv("AI_TOKEN") or st.secrets["AI_TOKEN"],
            )
            r = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=([{"role": "system", "content": system_prompt},
                          {"role": "user", "content": prompt}])
            )

            response = r.choices[0].message.content

            st.write(response)