import asyncio
import json
import os
import sys
import tempfile
import threading

import streamlit as st
from google.adk.runners import Runner
from google.adk.sessions import DatabaseSessionService
from google.genai import types

# ── Google Cloud credentials (Streamlit secrets → env vars) ───────────────────
# Works both locally (.streamlit/secrets.toml) and on Streamlit Community Cloud
if "gcp_service_account" in st.secrets:
    _key = dict(st.secrets["gcp_service_account"])
    _tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False)
    json.dump(_key, _tmp)
    _tmp.flush()
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = _tmp.name

if "GOOGLE_CLOUD_PROJECT" in st.secrets:
    os.environ.setdefault("GOOGLE_CLOUD_PROJECT", st.secrets["GOOGLE_CLOUD_PROJECT"])

# Allow `from Agents.agent import ...` regardless of the working directory
_parent = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _parent not in sys.path:
    sys.path.insert(0, _parent)

from Agents.agent import root_agent  # noqa: E402

# ── constants ──────────────────────────────────────────────────────────────────
APP_NAME = "college_admissions"
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "college_admissions.db")
DB_URL = f"sqlite+aiosqlite:///{DB_PATH}"

# ── persistent event loop ──────────────────────────────────────────────────────
# Streamlit re-executes the entire script on every interaction, so a bare
# `_loop = asyncio.new_event_loop()` at module level creates a NEW loop each
# run. The cached runner/session_service are bound to the ORIGINAL loop, so all
# subsequent runs get "bound to a different event loop". Caching the loop itself
# with @st.cache_resource ensures it is created exactly once per server process.
@st.cache_resource
def _get_loop() -> asyncio.AbstractEventLoop:
    loop = asyncio.new_event_loop()
    threading.Thread(target=loop.run_forever, daemon=True).start()
    return loop


def run_sync(coro):
    """Submit a coroutine to the persistent cached event loop and block until done."""
    return asyncio.run_coroutine_threadsafe(coro, _get_loop()).result()


# ── async helpers ──────────────────────────────────────────────────────────────
async def _get_or_create_session(session_service, user_id: str):
    session_id = f"{APP_NAME}_{user_id}"
    session = await session_service.get_session(
        app_name=APP_NAME, user_id=user_id, session_id=session_id
    )
    if session is None:
        session = await session_service.create_session(
            app_name=APP_NAME, user_id=user_id, session_id=session_id
        )
    return session


async def _send(runner, user_id: str, session_id: str, text: str) -> str:
    message = types.Content(role="user", parts=[types.Part(text=text)])
    parts = []
    async for event in runner.run_async(
        user_id=user_id,
        session_id=session_id,
        new_message=message,
    ):
        if event.is_final_response() and event.content:
            for part in event.content.parts:
                if part.text:
                    parts.append(part.text)
    return "\n".join(parts)


async def _read_state(session_service, user_id: str) -> dict:
    session_id = f"{APP_NAME}_{user_id}"
    session = await session_service.get_session(
        app_name=APP_NAME, user_id=user_id, session_id=session_id
    )
    if session is None:
        return {}
    return dict(session.state)


# ── cached backend (one instance per server process) ──────────────────────────
@st.cache_resource
def init_backend():
    async def _init():
        session_service = DatabaseSessionService(db_url=DB_URL)
        runner = Runner(agent=root_agent, app_name=APP_NAME, session_service=session_service)
        return session_service, runner
    return run_sync(_init())


# ── page config ────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="College Admissions Coach",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
    .school-tag { display: inline-block; padding: 2px 8px; border-radius: 12px;
                  font-size: 0.75rem; font-weight: 600; margin: 2px; }
    .reach  { background: #fee2e2; color: #991b1b; }
    .target { background: #fef9c3; color: #854d0e; }
    .safety { background: #dcfce7; color: #166534; }
    div[data-testid="stChatInput"] textarea { min-height: 52px; }
    </style>
    """,
    unsafe_allow_html=True,
)

session_service, runner = init_backend()


# ── sidebar ────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 🎓 College Admissions Coach")
    st.caption("Your personal AI application advisor")
    st.divider()

    raw_name = st.text_input(
        "Your name",
        placeholder="Enter a name to save your progress",
        help="Each name gets its own persistent profile and school list.",
    )
    user_id = raw_name.lower().strip().replace(" ", "_") if raw_name else None

    if user_id:
        # New user or switched user — reset chat and queue greeting
        if st.session_state.get("last_user_id") != user_id:
            run_sync(_get_or_create_session(session_service, user_id))
            st.session_state["last_user_id"] = user_id
            st.session_state["messages"] = []
            st.session_state["needs_greeting"] = True

        state = run_sync(_read_state(session_service, user_id))
        profile = state.get("student_profile", {})
        schools = state.get("school_list", [])

        if profile:
            st.markdown("**Your Profile**")
            if profile.get("grade_level"):
                st.write(f"**Grade:** {profile['grade_level']}")
            cols = st.columns(2)
            if profile.get("gpa_unweighted"):
                cols[0].metric("GPA", profile["gpa_unweighted"])
            if profile.get("sat_total") and int(profile.get("sat_total", 0)) > 0:
                cols[1].metric("SAT", profile["sat_total"])
            if profile.get("act_composite") and int(profile.get("act_composite", 0)) > 0:
                st.write(f"**ACT:** {profile['act_composite']}")
            if profile.get("intended_major"):
                st.write(f"**Major:** {profile['intended_major']}")
            if profile.get("state_of_residence"):
                st.write(f"**State:** {profile['state_of_residence']}")
            if profile.get("annual_budget_usd") and int(profile.get("annual_budget_usd", 0)) > 0:
                st.write(f"**Budget:** ${int(profile['annual_budget_usd']):,}/yr")
        else:
            st.info("No profile yet — the coach will ask you a few questions to get started.")

        if schools:
            st.divider()
            st.markdown("**Your School List**")
            reaches  = [s["name"] for s in schools if s["classification"] == "reach"]
            targets  = [s["name"] for s in schools if s["classification"] == "target"]
            safeties = [s["name"] for s in schools if s["classification"] == "safety"]

            def badge(names, css_class):
                return " ".join(
                    f'<span class="school-tag {css_class}">{n}</span>' for n in names
                )

            if reaches:
                st.markdown(f"🔴 **Reaches ({len(reaches)})**")
                st.markdown(badge(reaches, "reach"), unsafe_allow_html=True)
            if targets:
                st.markdown(f"🟡 **Targets ({len(targets)})**")
                st.markdown(badge(targets, "target"), unsafe_allow_html=True)
            if safeties:
                st.markdown(f"🟢 **Safeties ({len(safeties)})**")
                st.markdown(badge(safeties, "safety"), unsafe_allow_html=True)

        st.divider()
        if st.button("🗑 Clear chat history", use_container_width=True):
            st.session_state["messages"] = []
            st.session_state["needs_greeting"] = True
            st.rerun()


# ── main chat area ─────────────────────────────────────────────────────────────
if not user_id:
    st.markdown("## Welcome to College Admissions Coach 🎓")
    st.markdown(
        "Your personal AI advisor for building a college list, checking affordability, "
        "understanding your chances, and polishing your essays.\n\n"
        "**Enter your name in the sidebar to get started.**  \n"
        "Your profile and school list are saved so you can pick up where you left off."
    )
    st.stop()

session_id = f"{APP_NAME}_{user_id}"

if "messages" not in st.session_state:
    st.session_state["messages"] = []

# Render existing chat history
for msg in st.session_state["messages"]:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# Auto-greet when user first enters their name (agent speaks first)
if st.session_state.get("needs_greeting"):
    st.session_state["needs_greeting"] = False
    with st.chat_message("assistant"):
        with st.spinner(""):
            opening = run_sync(_send(runner, user_id, session_id, "hi"))
        st.markdown(opening)
    st.session_state["messages"].append({"role": "assistant", "content": opening})
    st.rerun()

# ── suggestion chips (shown once profile exists) ───────────────────────────────
state = run_sync(_read_state(session_service, user_id))
if state.get("student_profile") and st.session_state.get("messages"):
    st.markdown("")
    cols = st.columns(4)
    chips = [
        ("🏫 Add a school", "Can you research and add a school to my list?"),
        ("💰 Check affordability", "Can you check if my school list fits my budget?"),
        ("✍️ Essay feedback", "I'd like feedback on one of my essays."),
        ("📊 My chances", "What are my chances of getting into a school on my list?"),
    ]
    for col, (label, prompt_text) in zip(cols, chips):
        if col.button(label, use_container_width=True, key=f"chip_{label}"):
            st.session_state["pending_prompt"] = prompt_text
            st.rerun()

# ── chat input ─────────────────────────────────────────────────────────────────
typed = st.chat_input("Ask anything about your college applications…")
prompt = st.session_state.pop("pending_prompt", None) or typed

if prompt:
    with st.chat_message("user"):
        st.markdown(prompt)
    st.session_state["messages"].append({"role": "user", "content": prompt})

    with st.chat_message("assistant"):
        with st.spinner(""):
            response = run_sync(_send(runner, user_id, session_id, prompt))
        st.markdown(response)

    st.session_state["messages"].append({"role": "assistant", "content": response})
    st.rerun()
