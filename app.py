import os
import chromadb
import requests
import time
import streamlit as st
from dotenv import load_dotenv
from openai import OpenAI
from doc_helper import read_file
from tavily import TavilyClient

load_dotenv()

#INITIALIZING TAVILY SEARCH CLIENT
tavily_key = os.getenv("TAVILY_API_KEY")
tavily_client = TavilyClient(api_key=tavily_key) if tavily_key else None


#INITIALIZING ChromaDB CLIENT
db= chromadb.PersistentClient(path="./chromadb")
brain = db.get_or_create_collection("harvey")
memory = db.get_or_create_collection("harvey_chat")

#SYSTEM PROMPT
def anchor_prompt(user_name, personality, length_of_response, context, rerecalled, questions, theweb_info=""):
    return f"""

ROLE AND PURPOSE
You are the "Projectionist," an AI movie companion. 
Your goal is to guide users through their entire movie-watching experience—from selecting the right film 
to answering mid-watch questions and discussing the movie after the credits roll.
If the user tries to talk about anything else that isnt movie related, just say you arent equiped to answer those types of questions. DOnt answer a fitness or cooking or math question.

User's name: {user_name if user_name else "Friend"}
User wants your personality to be like a {personality}

GENERAL BEHAVIOR & STYLE
Response length the user wants: {length_of_response}
Default response length: Use bullet points and bold text for easy reading on screens.

The Standard Rule (STRICT NO-SPOILER POLICY):
   - NEVER reveal plot twists, character deaths, or ending secrets unless the user explicitly confirms they have already finished the movie or specifically asks for a spoiler.
   - If a mid-watch question borders on a future plot reveal, answer ONLY up to the point of the scene they are watching, and explicitly state: *"I can't answer further without spoiling what happens next!"*

OPERATIONAL MODES
When interacting with the user, identify which mode applies or ask the user to clarify if needed.

MODE 1: PRE-WATCH (Selection & Custom Recommendations)
- Tailored Recommendations: Recommend movies based on precise user constraints (e.g., mood, exact duration, high tension vs. low anxiety, era, or specific tropes).
- Trigger & Content Warnings: Provide detailed, non-spoiler assessments of content intensity (e.g., jumpscares, gore, sensitive themes) upon request.
- Marathon Curation: Design thematic double-features or franchise watch orders (e.g., release order vs. chronological order) with brief explanations of why the movies pair well.
- Pre-Watch Primer: Give 2–3 quick, non-spoiler facts before they press play (historical context).

MODE 2: MID-WATCH (Timeline, Character & Context Orientation)
- Franchise & Memory Refresher: Provide quick recaps of previous films, complex family trees, or past plot points to help lost viewers catch up.
- Scene & Character Context: Explain current character relationships, motives, or lore without hinting at future events.
- Strict Guardrail: Always confirm where the user is in the movie/franchise before answering detailed plot queries.

MODE 3: POST-WATCH (Debrief, Analysis & Discussion)
- Ending & Symbolism Breakdown: Explain complex, open-ended, or ambiguous endings, thematic motifs, and hidden easter eggs.
- Discussion Companion: Act as a conversational partner to debate character choices, director decisions, alternate endings, or personal takes.
- Next-Watch Mapping: Suggest what to watch next based specifically on what they loved or hated about the film they just finished.

INPUT/OUTPUT FORMATTING
- Format movie titles in Bold accompanied by the release year in parentheses: e.g., Knives Out (2019).
- For recommendations, provide: Title (Year), Genre, Runtime, a 2-sentence pitch, and a "Why it fits your request" note.

# STARTUP INSTRUCTION
Begin your first interaction by introducing yourself briefly as the Projectionist and asking the user what phase of movie-watching they need help with today (finding something to watch, getting a quick refresher/mid-watch context, or discussing a movie they just finished).
You are not a search engine. You are a movie companion.
If the user asks about a movie, respond as someone sitting beside them discussing cinema.
Correct gently, never abruptly.

CONTEXT FROM DOCUMENTS
{context if context else "nothing"}
EARLIER CONVERSATIONS RECALLED
{rerecalled if rerecalled else "nothing"}
WEB SEARCH RESULTS
{theweb_info if theweb_info else "nothing"}
"""

THRESHOLD=1.7

def shorten(text, limit=500):
    return text if len(text) <= limit else text[:limit] + " ... rest removed to keep it shorter"

#CHUNKS DOWN DOCUMENT
def chunk_by_sentence(text, max_size=700):
    sentences = text.split(", ")
    chunks, current = [], ""
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
        metadatas=[{"source": file.name, "chunk":i} for i in range(len(chunks))],
    )
    return len(text), len(chunks)

#ADDING EXCHANGES TO MEMORY
def remember_exchange(question, reply):
    #Put this Q and A into long term memory so AI can remember
    memory.add(
        documents=[f"Question: {question}\n and Answer: {shorten(reply)}"],
        ids=[f"turn{time.time()}"]
    )

#INTERFACE SETUP
st.set_page_config(page_title="The Projectionist", page_icon="🎥", layout="wide")

def set_bg_url(url):
  st.markdown(
      f"""
        <style>
        /* 1. Background image with a 60% dark tint overlay */
        [data-testid="stAppViewContainer"] {{
            background-image: linear-gradient(rgba(0, 0, 0, 0.6), rgba(0, 0, 0, 0.6)), url("{url}");
            background-size: cover;
            background-position: center;
            background-repeat: no-repeat;
            background-attachment: fixed;
        }}

        /* 2. Style chat message boxes as crisp, semi-transparent cards */
        [data-testid="stChatMessage"] {{
            background-color: rgba(15, 15, 25, 0.8) !important;
            border: 1px solid rgba(255, 255, 255, 0.15);
            border-radius: 10px;
            padding: 12px 16px;
            margin-bottom: 12px;
            color: #FFFFFF !important;
        }}

        /* 3. Force all text, headers, and paragraphs inside messages to be white */
        [data-testid="stChatMessage"] p, 
        [data-testid="stChatMessage"] span,
        [data-testid="stChatMessage"] div {{
            color: #FFFFFF !important;
        }}
        </style>
        """,
      unsafe_allow_html=True,
  )
set_bg_url("https://i.pinimg.com/1200x/5a/b4/fa/5ab4fa66dee157fea84e4f0a8e4113ba.jpg")

st.title("The Projectionist")
st.subheader("Start by personalizing your AI in the Settings Tab")
st.text("If you don't know where to start just type in 'hey'")

#STARTING SESSION STATE
if "messages" not in st.session_state:
    st.session_state["messages"] = []

#SIDEBAR
with st.sidebar:
    st.header("Settings")
    with st.form("settings"):
        name = st.text_input("Enter your name: ")
        mood = st.selectbox("Personality: ", ["Casual Film Buff", "Academic Film Critic", "No-Nonsense", "Family Friendly"])
        response_length = st.selectbox("Response length: ", ["Bullet Points", "Balanced Overview", "Deep Dive" ])
        knowledge_source = st.radio(
            "Knowledge source",
            [
                "Documents Only",
                "Web Search",
                "All Sources (Docs + Web)"
            ],
            index=2
        )
        creativity = st.slider("Creativity", 0.0, 1.0, 0.0)
        remember_documents = st.slider("How many chunks to remember", 0, 15, 5)
        remember = st.slider("Recent turns to keep", 0,10,3)
        recall = st.slider("Old exchanges to look up", 0,10,3)

        #notes_only = st.checkbox("Only answer using notes")
        #enable_web_search = st.checkbox("Enable Web Search", value=True)
        saved = st.form_submit_button("Save")
    if saved:
        st.write(f"Saved personality is {mood} and creativity is {creativity}.")

    use_docs = knowledge_source in ["Documents Only", "All Sources (Docs + Web)"]
    use_web = knowledge_source in ["Web Search", "All Sources (Docs + Web)"]
    strict_docs_only = (knowledge_source == "Documents Only")

    st.caption(f"In memory: {brain.count()} chunks")
    st.caption(f"Long term memory: {memory.count()} exchanges")
    st.caption(f"On screen: {len(st.session_state.messages)} messages")

    if st.button("Clear chat"):
        st.session_state.messages = []
        st.rerun()
    if st.button ("Forget memory"):
        db.delete_collection("harvey_chat")
        memory = db.get_or_create_collection("harvey_chat")
        st.rerun()
    if st.button ("Forget all documents"):
        db.delete_collection("harvey")
        brain = db.get_or_create_collection("harvey")
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
    prompt_file = user_input.files[0] if user_input.files else None

    #USER MESSAGE DISPLAY
    with st.chat_message("user"):
        if prompt_file:
            clean_len, n_chunks = store_document(prompt_file)
            st.write(f"{prompt_file.name}")
            st.caption(f"{clean_len} characters stored as {n_chunks} chunks.")
        if prompt:
            st.write(f"{prompt}")

        st.session_state.messages.append(
            {"role": "user", "content": prompt if prompt else f"attached: {prompt_file.name}"}
        )

    #ASSISTANT MESSAGE DISPLAY
    with (st.chat_message("assistant")):
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
            docs, dists, good, metas, used_sources = [], [], [], [], []
            if use_docs and brain.count() > 0:
                hits = brain.query(query_texts=[prompt], n_results=remember_documents)
                docs = hits["documents"][0]
                dists = hits["distances"][0]
                metas = hits["metadatas"][0]
                for d, s, m in zip(docs, dists, metas):
                    if s<THRESHOLD:
                        good.append(d)
                        used_sources.append(f"{m['source']} (chunk {m['chunk']})")
                good = [d for d, s in zip(docs, dists) if s <= THRESHOLD]
                notes = "\n\n".join(f"Sources {i +1} {d}" for i, d in enumerate(good))

            recalled = []
            old_docs , old_dists, old_good = [], [], []
            if recall > 0 and memory.count() > remember:
                found = memory.query(query_texts=[prompt], n_results=recall)
                old_docs = found["documents"][0]
                old_dists = found["distances"][0]
                old_good = [d for d, s in zip(old_docs, old_dists) if s <= THRESHOLD]
                recalled = "\n\n".join(old_good)

            #WEB SEARCH
            web_info, web_sources = "", []
            if use_web and tavily_client and prompt:
                try:
                    search_res = tavily_client.search(
                        query=prompt, search_depth="basic", max_results=5,
                    )
                    for r in search_res.get("results", []):
                        web_sources.append(f"{r.get('title')} ({r.get('url')})")
                        web_info += f"Source: {r.get('title')}\nContent: {r.get('content')}\n\n"
                except Exception as e:
                    st.warning(f"Web search error: {e}")

            #NOTES
            #if notes_only:
                #if notes or recalled:
                    #full_prompt= anchor_prompt(name, mood, response_length, notes, recalled, prompt, web_info)
                #else:
                    #full_prompt= prompt

            with st.expander("What I looked up"):
                #SEARCHED INFORMATION
                st.caption("From Web Search")
                if web_sources:
                    for ws in web_sources:
                        st.text(f"🌐 {ws}")
                else:
                    st.text("Nothing")
                #RECALLING FROM NOTES
                st.caption("From your documents")
                if docs:
                    for d, s, m in zip(docs, dists, metas):
                        mark = "kept" if s < THRESHOLD else "dropped"
                        st.text(f"{s:.3f} {mark} {m['source']} {d[:70]}")
                else:
                    st.text("Nothing")
                #RECALLING FROM EARLIER CONVERSATIONS
                st.caption("From earlier conversations")
                if old_docs:
                    for d, s, in zip(old_docs, old_dists):
                        mark = "kept" if s < THRESHOLD else "dropped"
                        st.text(f"{s:.3f} {mark} {d[:70]}")
                else:
                    st.text("Nothing")

                #RECALLING FROM MOST RECENT CONVERSATION
                st.caption("Recent messages I can still see")
                recent = st.session_state.messages[:-1][-(remember*2):]
                if recent:
                    for m in recent:
                        st.text(f"{m['role']}: {shorten(m['content'], 80)}")
                else:
                    st.text("nothing")

            if strict_docs_only and not good:
                answer = "I couldn't find any relevant information in your uploaded documents for that query."
                st.write(answer)
            else:
                api_key = os.getenv("AI_TOKEN") or (st.secrets["AI_TOKEN"] if "AI_TOKEN" in st.secrets else None)

                if not api_key:
                    st.error(
                        "API Key for Groq/OpenAI not found. Please set `AI_TOKEN` in environment variables or secrets.")
                    answer = "Configuration error: Missing API Key."

                else:
                    client = OpenAI(
                        base_url="https://api.groq.com/openai/v1",
                        api_key=os.getenv("AI_TOKEN") or st.secrets["AI_TOKEN"],
                    )

                    system_prompt = anchor_prompt(
                        user_name=name,
                        personality=mood,
                        length_of_response=response_length,
                        context=notes,
                        rerecalled=recalled,
                        questions=prompt,
                        theweb_info=web_info,
                    )

                    messages = [{"role": "system", "content": system_prompt}]
                    past = st.session_state.messages[:-1]
                    if remember>0:
                        for m in past[-(remember*2):]:
                            messages.append({"role": m["role"], "content": shorten(m["content"])})
                    messages.append({"role": "user", "content": prompt})



                    r = client.chat.completions.create(
                        model="llama-3.3-70b-versatile",
                        temperature=creativity,
                        messages=messages
                        )
                    answer = r.choices[0].message.content
                    st.write(answer)

                    if used_sources and strict_docs_only:
                        st.caption("Sources: " + ", ".join(sorted(set(used_sources))))

            #if notes_only and enable_web_search:
                #answer = "If you want me to only search your documents, disable the 'Enable Web Search' button"
                #if used_sources:
                    #for i, src in enumerate(used_sources):
                        #st.caption(f"Sources {i+1}: {src}")
                    #st.caption("Sources: " + ", ".join(sorted(set(used_sources))))

            remember_exchange(prompt, answer)
        st.session_state.messages.append({"role": "assistant", "content": answer})