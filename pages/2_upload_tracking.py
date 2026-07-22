import time
import cv2
import streamlit as st
from streamlit_image_coordinates import streamlit_image_coordinates

import theme
import engine

theme.inject()
theme.reset_step_counter()
theme.page_title("Upload // Tracking", accent_word="Tracking",
                  subtitle="CARICA · CALIBRA · ANALIZZA — configura la serie e avvia il tracciamento CSRT")

# ----------------------------------------------------------------------------
# SIDEBAR - solo aspetto grafico (non blocca il flusso su mobile)
# ----------------------------------------------------------------------------
with st.sidebar:
    st.markdown(
        '<div class="cy-step" style="margin-top:0;">'
        '<span class="idx">//</span><span class="label">Aspetto linea</span>'
        '</div>',
        unsafe_allow_html=True,
    )
    line_color_hex = st.color_picker("Colore linea", "#00FFF0")
    line_thickness = st.slider("Spessore linea", min_value=2, max_value=12, value=4)

    st.markdown(
        '<div class="cy-footer" style="text-align:left; margin-top:2rem;">PRAGMA FIT · Streamlit · OpenCV</div>',
        unsafe_allow_html=True,
    )

LINE_COLOR_BGR = engine.hex_to_bgr(line_color_hex)

# ----------------------------------------------------------------------------
# 0) SELEZIONE MODALITÀ
# ----------------------------------------------------------------------------
theme.step_header("Modalità")
mode = st.radio(
    "Modalità",
    ["Solo Bar Path (Analisi visiva)", "VBT Avanzato (Algoritmo di Allenamento)"],
    horizontal=True,
    label_visibility="collapsed",
)
vbt_mode = mode.startswith("VBT")

# ----------------------------------------------------------------------------
# 1) PARAMETRI DELLA SERIE (solo modalità VBT)
# ----------------------------------------------------------------------------
exercise = None
peso_kg = None
diametro_cm = None

if vbt_mode:
    theme.step_header("Parametri della serie")
    st.caption(
        "Servono per calibrare pixel → metri e calcolare velocità, potenza e 1RM stimato. "
        "Per una calibrazione corretta, tieni il telefono ben perpendicolare al piano di "
        "movimento del bilanciere (non inclinato né troppo di lato)."
    )

    exercise = st.radio(
        "Esercizio",
        list(engine.EXERCISE_PROFILES.keys()),
        horizontal=True,
    )

    col_a, col_b = st.columns(2)
    with col_a:
        peso_kg = st.number_input(
            "Peso sul bilanciere (kg)", min_value=1.0, value=20.0, step=1.0,
            help="Il carico totale sul bilanciere per questa serie (bilanciere + dischi).",
        )
    with col_b:
        diametro_cm = st.number_input(
            "Diametro del disco (cm)", min_value=5.0, value=45.0, step=0.5,
            help="45 cm è lo standard olimpico. Usato per convertire i pixel in metri.",
        )

# ----------------------------------------------------------------------------
# 2) UPLOAD VIDEO
# ----------------------------------------------------------------------------
theme.step_header("Carica il video")
uploaded_file = st.file_uploader(
    "Trascina qui il tuo video o caricalo dal rullino",
    type=["mp4", "mov", "avi", "mkv", "m4v"],
    accept_multiple_files=False,
    label_visibility="collapsed",
)

if uploaded_file is None:
    st.info("Carica un video per iniziare.")
    theme.footer()
    st.stop()

st.markdown('<span class="status-badge">● Video caricato</span>', unsafe_allow_html=True)

sig = engine.file_signature(uploaded_file)

if st.session_state.get("video_sig") != sig:
    st.session_state["video_sig"] = sig
    st.session_state["selected_point"] = None

video_bytes = uploaded_file.getvalue()
first_frame, fps, total_frames, width, height = engine.extract_first_frame(video_bytes, sig)

if fps <= 1 or fps > 240:
    fps = 30

if first_frame is None:
    st.error("❌ Impossibile leggere il primo fotogramma del video. Prova con un altro file (mp4 consigliato).")
    theme.footer()
    st.stop()

# ----------------------------------------------------------------------------
# 3) SELEZIONE DEL PUNTO DI PARTENZA SUL PRIMO FOTOGRAMMA
# ----------------------------------------------------------------------------
theme.step_header("Clicca sul bilanciere")
if vbt_mode:
    st.caption(
        "In modalità VBT, l'area selezionata viene usata anche per "
        "calibrare la conversione pixel → metri: falla combaciare con "
        "l'altezza (il diametro) del disco."
    )

default_box = max(20, min(width, height) // 12)
box_size = st.slider(
    "Dimensione dell'area da seguire (px)",
    min_value=15,
    max_value=max(40, min(width, height) // 2),
    value=default_box,
    step=1,
    help="Deve coprire un dettaglio ad alto contrasto del bilanciere (bordo, "
         "adesivo, anello). Troppo piccola = facile perdere il tracciamento; "
         "troppo grande = puo' agganciare lo sfondo.",
)

display_width = min(700, width)
scale = width / display_width
display_height = int(height / scale)

preview = first_frame.copy()
selected_point = st.session_state.get("selected_point")
if selected_point is not None:
    px, py = selected_point
    half = box_size // 2
    x, y, w, h = engine.clamp_bbox(px - half, py - half, box_size, box_size, width, height)
    # Colore accento ciano neon in BGR (OpenCV usa l'ordine B,G,R)
    accent_bgr = (240, 255, 0)
    cv2.rectangle(preview, (x, y), (x + w, y + h), accent_bgr, max(2, width // 400))
    cv2.circle(preview, (px, py), max(4, width // 250), accent_bgr, -1)

preview_small = cv2.resize(preview, (display_width, display_height), interpolation=cv2.INTER_AREA)

click_value = streamlit_image_coordinates(preview_small, key=f"point_selector_{sig}")

if click_value is not None:
    disp_w = click_value.get("width") or display_width
    disp_h = click_value.get("height") or display_height
    real_x = int(click_value["x"] * (width / disp_w))
    real_y = int(click_value["y"] * (height / disp_h))
    real_x = max(0, min(real_x, width - 1))
    real_y = max(0, min(real_y, height - 1))
    if st.session_state.get("selected_point") != (real_x, real_y):
        st.session_state["selected_point"] = (real_x, real_y)
        st.rerun()

if selected_point is None:
    st.warning("Clicca su un punto del bilanciere nell'immagine qui sopra prima di procedere.")
else:
    st.caption(f"Punto selezionato — x: {selected_point[0]}px · y: {selected_point[1]}px")

# ----------------------------------------------------------------------------
# 4) ELABORAZIONE
# ----------------------------------------------------------------------------
theme.step_header("Analizza set")
process_clicked = st.button(
    "Analizza set",
    use_container_width=True,
    type="primary",
    disabled=selected_point is None,
)

if process_clicked and selected_point is not None:
    status_text = st.empty()
    progress_bar = st.progress(0, text="Inizializzazione...")

    try:
        result = engine.process_video(
            uploaded_file=uploaded_file,
            video_bytes=video_bytes,
            selected_point=selected_point,
            box_size=box_size,
            width=width,
            height=height,
            fps=fps,
            total_frames=total_frames,
            vbt_mode=vbt_mode,
            diametro_cm=diametro_cm,
            line_color_bgr=LINE_COLOR_BGR,
            line_thickness=line_thickness,
            progress_bar=progress_bar,
            status_text=status_text,
        )
    except RuntimeError as e:
        st.error(f"❌ {e}")
        theme.footer()
        st.stop()

    progress_bar.progress(1.0, text="✅ Elaborazione completata!")

    lost_frames = result["lost_frames"]
    frame_idx = result["frame_idx"]
    if lost_frames == 0:
        status_text.success(
            f"Video elaborato in {result['elapsed_s']:.1f}s — "
            f"{frame_idx} fotogrammi, tracciamento riuscito su tutto il video."
        )
    else:
        loss_pct = 100 * lost_frames / max(frame_idx, 1)
        status_text.warning(
            f"Video elaborato in {result['elapsed_s']:.1f}s. "
            f"Tracciamento perso per {lost_frames} fotogrammi su {frame_idx} "
            f"({loss_pct:.0f}%) — probabilmente il punto scelto è uscito dall'inquadratura "
            f"o è stato oscurato. Prova a scegliere un punto più ad alto contrasto o "
            f"un'area leggermente più grande."
        )

    with open(result["output_path"], "rb") as f:
        video_out_bytes = f.read()

    # Salva tutto il necessario in sessione: la pagina Risultati legge da qui.
    run_record = {
        "timestamp": time.time(),
        "vbt_mode": vbt_mode,
        "exercise": exercise,
        "peso_kg": peso_kg,
        "diametro_cm": diametro_cm,
        "fps": fps,
        "mpp": result["mpp"],
        "raw_series": result["raw_series"],
        "lost_frames": lost_frames,
        "frame_idx": frame_idx,
        "elapsed_s": result["elapsed_s"],
        "video_bytes": video_out_bytes,
        "video_filename": uploaded_file.name,
    }
    st.session_state["last_run"] = run_record
    st.session_state.setdefault("history", [])
    st.session_state["history"].append(run_record)

    st.success("Analisi completata. Apri la sezione **Risultati** per la dashboard.")
    if st.button("Vai a Risultati →", type="primary", use_container_width=True):
        st.switch_page("pages/3_risultati.py")

theme.footer()
