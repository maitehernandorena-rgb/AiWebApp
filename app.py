import streamlit as st
import requests
import os
from dotenv import load_dotenv
from openai import OpenAI

st.set_page_config(page_title="Harvey", page_icon="H", layout="wide")

st.title("Harvey")
st.write("Harvey is a friendly assistant, ready to help you in your daily tasks. Whether your homework is complicated or taxes are hard or something idk. Please start by setting up your AI in the left Tab.")


with st.sidebar:
    st.header("Settings")
    with st.form("settings"):
        name = st.text_input("Enter your name: ")
        mood = st.multiselect("Select a few options for his mood:", ["nerdy", "caring", "organized", "straight to the point"])
        creativity = st.slider("Creativity", 0.0, 1.0, 0.5)
        saved = st.form_submit_button("Save")
    if saved:
        st.write(f"Saved mood is {mood} and creativity is {creativity}.")

import requests

prompt = st.chat_input("Ask something here...")

if prompt:
    with st.chat_message("user"):
        st.write(f"{prompt}")
    with st.chat_message("assistant"):
        if prompt == "Cat Fact":
            r = requests.get("https://catfact.ninja/fact")
            fact = r.json()["fact"]
            st.write(f"{fact}")
        else:
            promptforai = f"""You are a {mood} assistant with {creativity} creativity from a scale from 0 to 1.
            Current Prompt: {prompt}"""
            load_dotenv()
            client = OpenAI(
                #base_url="https://models.github.ai/inference",
                base_url="https://api.groq.com/openai/v1",
                api_key=os.getenv("AI_TOKEN") or st.secrets["AI_TOKEN"],
            )
            r = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[{"role": "user", "content": promptforai}]
            )

            response = r.choices[0].message.content

            st.write(response)