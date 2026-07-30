import streamlit as st

st.title("Harvey")
st.write("Harvey is a friendly assistant, ready to help you in your daily tasks. Whether your homework is complicated or taxes are hard or something idk.")

#name = st.text_input("Enter your name: ")
#if st.button("SUBMIT"):
    #st.write(f"Hello, {name}! Welcome! Your name has {len(name)} letters!")

st.set_page_config(page_title="Harvey", page_icon="H", layout="wide")

with st.sidebar:
    st.header("Settings")
    with st.form("settings"):
        name = st.text_input("Enter your name: ")
        mood = st.multiselect("Select a few options for his mood:", ["nerdy", "caring", "organized", "straight to the point"])
        creativity = st.slider("Creativity", 0.0, 1.0, 0.5)
        saved = st.form_submit_button("Save")
    if saved:
        st.write(f"Saved mood is {mood} and creativity is {creativity}.")

#left, right = st.columns(2)
#left.write(f"Creativity:  {creativity}")
#right.write(f"Mood: {mood}")

#with st.chat_message("user"):
    #st.write(f"Welcome!")
#with st.chat_message("assistant"):
    #st.write(f"Hello {name}! Welcome! Your name has {len(name)} letters!")
import requests

prompt = st.chat_input("Ask something her...")
#r = requests.get(https://catfact.ninja/fact)
#facts = r.json()["fact"]

if prompt:
    with st.chat_message("user"):
        st.write(f"{prompt}")
    with st.chat_message("assistant"):
        st.write(f"Hello {name}! Welcome! Heres what you wrote: {prompt}")
    #with st.chat_message("user"):
        #st.write(prompt)