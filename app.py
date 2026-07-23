
import streamlit as st
import theme

_page_icon = theme.page_icon()

st.set_page_config(
    page_title="PRAGMA FIT",
    page_icon=_page_icon,
    layout="centered",
    initial_sidebar_state="expanded",
)

home = st.Page("pages/1_home.py", title="Home", icon="🏠", default=True)
upload = st.Page("pages/2_upload_tracking.py", title="Upload & Tracking", icon="🎯")
results = st.Page("pages/3_risultati.py", title="Risultati", icon="📊")
history = st.Page("pages/4_storico.py", title="Storico", icon="🗂️")

nav = st.navigation([home, upload, results, history])
nav.run()
