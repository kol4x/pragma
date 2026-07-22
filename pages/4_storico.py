import datetime
import streamlit as st
import theme
import engine

theme.inject()
theme.reset_step_counter()
theme.page_title("Storico", accent_word="Storico",
                  subtitle="LOG.SESSIONE — le serie elaborate finora in questa sessione")

history = st.session_state.get("history", [])

if not history:
    st.info("Nessuna serie ancora elaborata in questa sessione.")
    if st.button("Vai a Upload & Tracking →", type="primary", use_container_width=True):
        st.switch_page("pages/2_upload_tracking.py")
    theme.footer()
    st.stop()

st.markdown(
    f'<span class="status-badge">● {len(history)} serie registrate</span>',
    unsafe_allow_html=True,
)

theme.step_header("Serie elaborate", index="//")

for i, run in enumerate(reversed(history)):
    idx = len(history) - i
    ts = datetime.datetime.fromtimestamp(run["timestamp"]).strftime("%H:%M:%S")
    mode_label = "VBT Avanzato" if run["vbt_mode"] else "Solo Bar Path"
    exercise_label = f" · {run['exercise']}" if run["vbt_mode"] and run["exercise"] else ""

    with st.expander(f"#{idx:02d} — {ts} — {mode_label}{exercise_label}", expanded=(i == 0)):
        col1, col2, col3 = st.columns(3)
        col1.metric("Fotogrammi", run["frame_idx"])
        col2.metric("Persi", run["lost_frames"])
        col3.metric("Tempo elaborazione", f"{run['elapsed_s']:.1f}s")

        if run["vbt_mode"]:
            metrics = engine.compute_vbt_metrics(
                run["raw_series"], run["fps"], run["mpp"], run["peso_kg"]
            )
            if metrics and metrics["reps_count"] > 0:
                col_v1, col_v2, col_v3 = st.columns(3)
                col_v1.metric("Vel. media", f"{metrics['mean_concentric_velocity']:.2f} m/s")
                col_v2.metric("Vel. picco", f"{metrics['peak_velocity']:.2f} m/s")
                col_v3.metric("Ripetizioni", metrics["reps_count"])
            else:
                st.caption("Nessuna metrica VBT valida rilevata per questa serie.")

        st.video(run["video_bytes"])
        st.download_button(
            label="Scarica questo video",
            data=run["video_bytes"],
            file_name=f"pragma_fit_output_{idx:02d}.mp4",
            mime="video/mp4",
            use_container_width=True,
            key=f"dl_{idx}",
        )

        if st.button("Mostra in Risultati →", key=f"show_{idx}", use_container_width=True):
            st.session_state["last_run"] = run
            st.switch_page("pages/3_risultati.py")

st.write("")
if st.button("🗑️ Svuota storico", use_container_width=True):
    st.session_state["history"] = []
    st.rerun()

theme.footer()
