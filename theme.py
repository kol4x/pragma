
import os
import base64
import streamlit as st

ASSETS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")
LOGO_PATH = os.path.join(ASSETS_DIR, "pragma_wordmark.png")
ICON_PATH = os.path.join(ASSETS_DIR, "pragma_logo.png")


def load_logo_b64():
    try:
        with open(LOGO_PATH, "rb") as f:
            return base64.b64encode(f.read()).decode("utf-8")
    except OSError:
        return None


def page_icon():
    try:
        from PIL import Image
        return Image.open(ICON_PATH)
    except Exception:
        return "⚡"


CUSTOM_CSS = """
<style>
    @import url('https://fonts.googleapis.com/css2?family=Orbitron:wght@600;700;900&family=Rajdhani:wght@500;600;700&family=Share+Tech+Mono&display=swap');

    :root {
        --cy-black: #05050a;
        --cy-void: #0a0a14;
        --cy-panel: #0d0d18;
        --cy-line: rgba(0, 255, 240, 0.14);
        --cy-line-strong: rgba(0, 255, 240, 0.35);
        --cy-cyan: #00fff0;
        --cy-magenta: #ff2fd0;
        --cy-yellow: #f4ff2b;
        --cy-white: #eafcff;
        --cy-mist: #7fa6ac;
        --cy-danger: #ff3860;
        --cy-success: #29ffb0;
    }

    html, body, [class*="css"] {
        font-family: 'Rajdhani', sans-serif;
    }

    /* ---------- Sfondo: nero profondo + griglia + scanline ---------- */
    .stApp {
        background:
            repeating-linear-gradient(
                0deg,
                rgba(0,255,240,0.035) 0px,
                rgba(0,255,240,0.035) 1px,
                transparent 1px,
                transparent 3px
            ),
            radial-gradient(ellipse at 20% -10%, rgba(255,47,208,0.09) 0%, transparent 55%),
            radial-gradient(ellipse at 100% 0%, rgba(0,255,240,0.09) 0%, transparent 45%),
            linear-gradient(180deg, var(--cy-black) 0%, var(--cy-void) 100%);
        background-attachment: fixed;
    }

    .block-container {
        padding-top: 1.4rem;
        padding-bottom: 3rem;
        max-width: 860px;
    }

    /* ---------- Sidebar / nav ---------- */
    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, #07070d 0%, #0a0a14 100%);
        border-right: 1px solid var(--cy-line);
    }
    [data-testid="stSidebar"] * {
        font-family: 'Rajdhani', sans-serif;
    }
    [data-testid="stSidebarNav"] a, [data-testid="stSidebarNavLink"] {
        font-family: 'Orbitron', sans-serif !important;
        letter-spacing: 0.05em;
    }

    /* ---------- Hero / lockup ---------- */
    .cy-hero {
        display: flex;
        flex-direction: column;
        align-items: center;
        gap: 0.4rem;
        margin: 0.4rem 0 0.4rem 0;
        text-align: center;
        position: relative;
    }
    .cy-hero img {
        height: 46px;
        width: auto;
        display: block;
        /* Il file del logo ha uno sfondo nero pieno (non trasparente): con
           mix-blend-mode 'screen' il nero del PNG diventa trasparente sopra
           lo sfondo scuro della pagina, eliminando l'effetto "riquadro/alone"
           dietro la scritta. Nessun drop-shadow: niente glow sul logo. */
        mix-blend-mode: screen;
    }
    .cy-hero .cy-tag {
        font-family: 'Orbitron', sans-serif;
        font-weight: 900;
        font-size: 0.82rem;
        letter-spacing: 0.55em;
        color: var(--cy-magenta);
        text-transform: uppercase;
        margin-left: 0.55em;
        text-shadow: 0 0 10px rgba(255,47,208,0.7), 0 0 22px rgba(255,47,208,0.35);
    }
    .cy-subtitle {
        font-family: 'Rajdhani', sans-serif;
        font-weight: 500;
        font-size: 1rem;
        color: var(--cy-mist);
        text-align: center;
        max-width: 40rem;
        margin: 0.5rem auto 1.6rem auto;
        line-height: 1.55;
    }

    /* ---------- Titoli di pagina ---------- */
    .cy-page-title {
        font-family: 'Orbitron', sans-serif;
        font-weight: 800;
        font-size: 1.5rem;
        letter-spacing: 0.06em;
        color: var(--cy-white);
        text-transform: uppercase;
        margin: 0 0 0.15rem 0;
        text-shadow: 0 0 16px rgba(0,255,240,0.35);
    }
    .cy-page-title .accent { color: var(--cy-cyan); }
    .cy-page-sub {
        font-family: 'Share Tech Mono', monospace;
        font-size: 0.78rem;
        color: var(--cy-mist);
        letter-spacing: 0.04em;
        margin-bottom: 1.6rem;
    }

    /* ---------- Eyebrow di sezione (step) ---------- */
    .cy-step {
        display: flex;
        align-items: baseline;
        gap: 0.7rem;
        margin: 2.2rem 0 0.9rem 0;
        padding-bottom: 0.65rem;
        border-bottom: 1px solid var(--cy-line);
        position: relative;
    }
    .cy-step::after {
        content: "";
        position: absolute;
        left: 0; bottom: -1px;
        width: 46px;
        height: 1px;
        background: var(--cy-cyan);
        box-shadow: 0 0 8px var(--cy-cyan);
    }
    .cy-step .idx {
        font-family: 'Share Tech Mono', monospace;
        font-weight: 600;
        font-size: 0.85rem;
        color: var(--cy-cyan);
        text-shadow: 0 0 8px rgba(0,255,240,0.6);
    }
    .cy-step .label {
        font-family: 'Orbitron', sans-serif;
        font-weight: 700;
        font-size: 0.86rem;
        letter-spacing: 0.14em;
        text-transform: uppercase;
        color: var(--cy-white);
    }
    .cy-step .sub {
        font-family: 'Rajdhani', sans-serif;
        font-size: 0.85rem;
        color: var(--cy-mist);
        margin-left: auto;
        text-align: right;
    }

    /* ---------- Micro eyebrow ---------- */
    .cy-micro {
        font-family: 'Orbitron', sans-serif;
        font-weight: 700;
        font-size: 0.72rem;
        letter-spacing: 0.16em;
        text-transform: uppercase;
        color: var(--cy-mist);
        margin: 1.8rem 0 0.8rem 0;
    }
    .cy-micro span { color: var(--cy-magenta); text-shadow: 0 0 8px rgba(255,47,208,0.6); }

    /* ---------- Badge di stato ---------- */
    .status-badge {
        display: inline-flex;
        align-items: center;
        gap: 0.45rem;
        padding: 0.32rem 0.8rem;
        border-radius: 2px;
        font-family: 'Orbitron', sans-serif;
        font-size: 0.7rem;
        font-weight: 700;
        letter-spacing: 0.1em;
        text-transform: uppercase;
        background: rgba(0,255,240,0.08);
        color: var(--cy-cyan);
        border: 1px solid var(--cy-line-strong);
        box-shadow: 0 0 12px rgba(0,255,240,0.15) inset;
    }

    /* ---------- Card per la nav della Home ---------- */
    .cy-card {
        display: block;
        background: linear-gradient(155deg, rgba(0,255,240,0.05), rgba(255,47,208,0.03));
        border: 1px solid var(--cy-line);
        border-radius: 3px;
        padding: 1.1rem 1.2rem;
        margin-bottom: 0.9rem;
        position: relative;
        overflow: hidden;
    }
    .cy-card::before {
        content: "";
        position: absolute; top:0; left:0;
        width: 3px; height: 100%;
        background: var(--cy-cyan);
        box-shadow: 0 0 10px var(--cy-cyan);
    }
    .cy-card .cy-card-title {
        font-family: 'Orbitron', sans-serif;
        font-weight: 700;
        font-size: 0.92rem;
        letter-spacing: 0.06em;
        color: var(--cy-white);
        text-transform: uppercase;
        margin-bottom: 0.35rem;
    }
    .cy-card .cy-card-desc {
        font-family: 'Rajdhani', sans-serif;
        font-size: 0.88rem;
        color: var(--cy-mist);
        line-height: 1.45;
    }

    /* ---------- File uploader ---------- */
    [data-testid="stFileUploaderDropzone"] {
        border: 1px dashed var(--cy-line-strong);
        border-radius: 3px;
        background: var(--cy-panel);
    }
    [data-testid="stFileUploaderDropzone"]:hover {
        border-color: var(--cy-cyan);
        box-shadow: 0 0 18px rgba(0,255,240,0.18) inset;
    }

    /* ---------- Bottoni ---------- */
    .stButton > button {
        border-radius: 2px;
        font-family: 'Orbitron', sans-serif;
        font-weight: 700;
        font-size: 0.8rem;
        letter-spacing: 0.1em;
        text-transform: uppercase;
        padding: 0.8rem 1.2rem;
        transition: all 0.15s ease-in-out;
        border: 1px solid var(--cy-line-strong);
        color: var(--cy-cyan);
        background: rgba(0,255,240,0.04);
    }
    .stButton > button[kind="primary"] {
        background: linear-gradient(90deg, var(--cy-cyan), var(--cy-magenta));
        border: 1px solid transparent;
        color: #05050a;
        box-shadow: 0 0 20px rgba(0,255,240,0.35);
    }
    .stButton > button:hover {
        opacity: 0.9;
        transform: translateY(-1px);
        box-shadow: 0 0 16px rgba(0,255,240,0.35);
    }
    .stDownloadButton > button {
        border-radius: 2px;
        font-family: 'Orbitron', sans-serif;
        font-weight: 700;
        font-size: 0.8rem;
        letter-spacing: 0.1em;
        text-transform: uppercase;
        border: 1px solid var(--cy-line-strong);
        color: var(--cy-magenta);
    }

    /* ---------- Metriche (pannello strumenti) ---------- */
    [data-testid="stMetric"] {
        background: var(--cy-panel);
        border: 1px solid var(--cy-line);
        border-radius: 3px;
        padding: 1rem 1.1rem;
        box-shadow: 0 0 22px rgba(0,255,240,0.05) inset;
    }
    [data-testid="stMetricLabel"] {
        font-family: 'Orbitron', sans-serif !important;
        font-size: 0.66rem !important;
        letter-spacing: 0.1em;
        text-transform: uppercase;
        color: var(--cy-mist) !important;
    }
    [data-testid="stMetricValue"] {
        font-family: 'Share Tech Mono', monospace !important;
        font-weight: 600 !important;
        color: var(--cy-cyan) !important;
        text-shadow: 0 0 10px rgba(0,255,240,0.45);
    }

    /* ---------- Caption e testo secondario ---------- */
    [data-testid="stCaptionContainer"], .stCaption {
        color: var(--cy-mist) !important;
    }

    /* ---------- Numeri stile HUD ---------- */
    .cy-mono {
        font-family: 'Share Tech Mono', monospace;
        color: var(--cy-cyan);
    }

    /* ---------- Tabs ---------- */
    .stTabs [data-baseweb="tab-list"] {
        gap: 0.4rem;
        border-bottom: 1px solid var(--cy-line);
    }
    .stTabs [data-baseweb="tab"] {
        font-family: 'Orbitron', sans-serif;
        font-size: 0.75rem;
        letter-spacing: 0.08em;
        text-transform: uppercase;
        color: var(--cy-mist);
        padding: 0.6rem 1rem;
    }
    .stTabs [aria-selected="true"] {
        color: var(--cy-cyan) !important;
        border-bottom: 2px solid var(--cy-cyan) !important;
        text-shadow: 0 0 8px rgba(0,255,240,0.5);
    }

    /* ---------- Radio / selettori ---------- */
    [data-testid="stRadio"] label {
        font-family: 'Rajdhani', sans-serif;
        font-weight: 600;
    }

    /* ---------- Alert boxes: bordino neon ---------- */
    [data-testid="stAlertContainer"] {
        border-radius: 3px;
        border: 1px solid var(--cy-line-strong);
    }

    /* ---------- Footer ---------- */
    .cy-footer {
        margin-top: 3rem;
        padding-top: 1.2rem;
        border-top: 1px solid var(--cy-line);
        font-family: 'Share Tech Mono', monospace;
        font-size: 0.72rem;
        color: var(--cy-mist);
        text-align: center;
        line-height: 1.7;
        letter-spacing: 0.02em;
    }

    @media (max-width: 600px) {
        .block-container {
            padding-left: 1rem;
            padding-right: 1rem;
        }
        .cy-step .sub {
            display: none;
        }
    }

    /* ---------- Nasconde solo la "chrome" non essenziale di Streamlit ----------
       Menu hamburger e footer "Made with Streamlit": elementi stabili e
       documentati. Non tocchiamo header/toolbar per non rischiare di
       nascondere anche il controllo che apre/chiude la sidebar. */
    #MainMenu { visibility: hidden; }
    footer { visibility: hidden; }
    .stAppDeployButton { display: none; }
</style>
"""


def inject():
    st.markdown(CUSTOM_CSS, unsafe_allow_html=True)


def hero(tag="FIT"):
    logo = load_logo_b64()
    if logo:
        st.markdown(
            f'<div class="cy-hero">'
            f'<img src="data:image/png;base64,{logo}" alt="PRAGMA" />'
            f'<span class="cy-tag">{tag}</span>'
            f'</div>',
            unsafe_allow_html=True,
        )
    else:
        st.markdown(f'<div class="cy-hero"><span class="cy-tag">PRAGMA {tag}</span></div>', unsafe_allow_html=True)


def page_title(title, subtitle=None, accent_word=None):
    display = title
    if accent_word and accent_word in title:
        display = title.replace(accent_word, f'<span class="accent">{accent_word}</span>')
    st.markdown(f'<div class="cy-page-title">{display}</div>', unsafe_allow_html=True)
    if subtitle:
        st.markdown(f'<div class="cy-page-sub">{subtitle}</div>', unsafe_allow_html=True)


_STEP_COUNTER = {"n": 0}


def reset_step_counter():
    _STEP_COUNTER["n"] = 0


def step_header(label: str, sub: str = "", index: str = None):
    if index is None:
        idx_str = f"{_STEP_COUNTER['n']:02d}"
        _STEP_COUNTER["n"] += 1
    else:
        idx_str = index
    sub_html = f'<span class="sub">{sub}</span>' if sub else ""
    st.markdown(
        f'<div class="cy-step">'
        f'<span class="idx">{idx_str}</span>'
        f'<span class="label">{label}</span>'
        f'{sub_html}'
        f'</div>',
        unsafe_allow_html=True,
    )


def micro_header(label: str):
    st.markdown(f'<div class="cy-micro">{label}</div>', unsafe_allow_html=True)


def footer():
    st.markdown(
        '<div class="cy-footer">PRAGMA FIT · SYS.CORE — la traiettoria è calcolata tramite '
        'object tracking (CSRT) sul punto scelto dall\'utente.<br>Le metriche VBT sono stime basate '
        'su video 2D non calibrato: usale come riferimento di tendenza, non come dato clinico.</div>',
        unsafe_allow_html=True,
    )
