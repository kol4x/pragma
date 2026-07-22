import streamlit as st
import theme
import engine

theme.inject()
theme.reset_step_counter()
theme.page_title("Risultati", accent_word="Risultati",
                  subtitle="OUTPUT.STREAM — video elaborato e dashboard VBT dell'ultima serie analizzata")

run = st.session_state.get("last_run")

if run is None:
    st.info("Nessuna serie analizzata in questa sessione.")
    if st.button("Vai a Upload & Tracking →", type="primary", use_container_width=True):
        st.switch_page("pages/2_upload_tracking.py")
    theme.footer()
    st.stop()

theme.step_header("Risultato", index="→")
st.video(run["video_bytes"])

st.download_button(
    label="Scarica il video elaborato",
    data=run["video_bytes"],
    file_name="pragma_fit_output.mp4",
    mime="video/mp4",
    use_container_width=True,
)

# ------------------------------------------------------------------
# DASHBOARD VBT (solo in modalita' "VBT Avanzato")
# ------------------------------------------------------------------
if run["vbt_mode"]:
    exercise = run["exercise"]
    peso_kg = run["peso_kg"]
    fps = run["fps"]
    mpp = run["mpp"]
    raw_series = run["raw_series"]

    metrics = engine.compute_vbt_metrics(raw_series, fps, mpp, peso_kg)

    theme.step_header("Dashboard VBT", index="→")

    if metrics is None or metrics["reps_count"] == 0:
        st.warning(
            "Non è stato rilevato un movimento verticale sufficiente per "
            "calcolare le metriche VBT. Verifica che il punto tracciato "
            "segua effettivamente il bilanciere durante la salita."
        )
    else:
        col1, col2 = st.columns(2)
        col1.metric("Velocità media in salita", f"{metrics['mean_concentric_velocity']:.2f} m/s")
        col2.metric("Velocità di picco", f"{metrics['peak_velocity']:.2f} m/s")

        col3, col4 = st.columns(2)
        col3.metric("Potenza di picco", f"{metrics['peak_power']:.0f} W")
        col4.metric("Ripetizioni rilevate", f"{metrics['reps_count']}")

        # --- Stima 1RM di oggi (doppio metodo, vedi costanti VBT in engine.py) ---
        clean_reps = [r for r in metrics["reps"] if not r["is_outlier"]]
        candidate_reps = clean_reps if clean_reps else metrics["reps"]
        fastest_rep = max(candidate_reps, key=lambda r: r["mean_v"])
        n_outliers = len(metrics["reps"]) - len(clean_reps)

        vbt_1rm, pct_used, vbt_affidabile, pct_raw = engine.estimate_1rm_velocity(
            exercise, fastest_rep["mean_v"], peso_kg
        )
        reps_1rm = engine.estimate_1rm_from_reps(peso_kg, metrics["reps_count"])

        serie_adatta_a_vbt = metrics["reps_count"] <= engine.REPS_MAX_FOR_RELIABLE_VBT
        pct_atteso = engine.expected_pct_1rm_for_reps(metrics["reps_count"])
        coerente_con_reps = pct_raw <= pct_atteso + engine.PCT_1RM_CEILING_TOLERANCE
        stima_affidabile = vbt_affidabile and serie_adatta_a_vbt and coerente_con_reps

        theme.micro_header(f"1RM stimato oggi <span>· {exercise}</span>")

        if n_outliers > 0:
            st.caption(
                f"⚙️ {n_outliers} ripetizione/i esclusa/e dal calcolo: velocità "
                f"anomala rispetto al resto della serie (probabile rumore di "
                f"tracciamento, spesso durante la fase eccentrica)."
            )

        col_v, col_r = st.columns(2)
        col_v.metric(
            "Da velocità (VBT)",
            f"{vbt_1rm:.1f} kg",
            help=f"Dalla ripetizione più veloce e attendibile della serie "
                 f"({fastest_rep['mean_v']:.2f} m/s, solo fase concentrica), "
                 f"corrispondente a circa il {pct_used:.0f}% dell'1RM secondo il profilo "
                 f"carico-velocità di {exercise}.",
        )
        col_r.metric(
            "Da ripetizioni (rif.)",
            f"{reps_1rm:.1f} kg",
            help="Stima classica (formula di Epley) da peso e numero di ripetizioni, "
                 "assumendo la serie svolta vicino al cedimento. Utile come riferimento "
                 "incrociato, specialmente su serie lunghe.",
        )

        if stima_affidabile:
            st.caption(
                "Serie breve a velocità elevata e coerente col numero di ripetizioni: "
                "la stima **da velocità** è quella più affidabile in questo caso."
            )
        else:
            if not serie_adatta_a_vbt:
                motivo = (
                    f"la serie ha {metrics['reps_count']} ripetizioni (il modello VBT è "
                    f"pensato per serie di massimo {engine.REPS_MAX_FOR_RELIABLE_VBT})"
                )
            elif not coerente_con_reps:
                motivo = (
                    f"la velocità rilevata sulla ripetizione più veloce è troppo bassa per "
                    f"essere coerente con {metrics['reps_count']} ripetizioni svolte (implica "
                    f"un {pct_raw:.0f}% del massimale, ma con quel numero di rep ci si aspetta "
                    f"circa il {pct_atteso:.0f}%) — probabile inquadratura non perfettamente "
                    f"parallela al bilanciere, o fotogrammi quasi fermi a inizio/fine ripetizione"
                )
            else:
                motivo = "la ripetizione più veloce ha una velocità fuori dal range tipico del modello"
            st.warning(
                f"⚠️ La stima **da velocità** qui sopra non è affidabile: {motivo}. "
                f"In questo caso conviene fare riferimento alla stima **da ripetizioni** "
                f"({reps_1rm:.1f} kg). Per una stima da velocità precisa, esegui una serie "
                f"breve (1-3 ripetizioni) alla massima velocità possibile con un carico "
                f"impegnativo, con il telefono ben perpendicolare al piano di movimento "
                f"del bilanciere."
            )
        st.caption(
            "Entrambe le stime sono indicative: non sostituiscono un test 1RM reale "
            "né un dato clinico validato individualmente."
        )

        # --- Feedback su Velocity Loss ---
        vl_reps = clean_reps if len(clean_reps) >= 2 else metrics["reps"]

        theme.micro_header("Consigli automatici")
        if len(vl_reps) < 2:
            st.info(
                "Rilevata una sola ripetizione: la perdita di velocità si "
                "calcola confrontando la prima e l'ultima ripetizione di "
                "una serie con più ripetizioni."
            )
        else:
            v_first = vl_reps[0]["mean_v"]
            v_last = vl_reps[-1]["mean_v"]
            if v_first > 0:
                vl_pct = max(0.0, (v_first - v_last) / v_first * 100)
                box_type, message = engine.velocity_loss_feedback(vl_pct)
                full_message = f"**Perdita di velocità: {vl_pct:.0f}%.** {message}"
                if box_type == "success":
                    st.success(full_message)
                elif box_type == "warning":
                    st.warning(full_message)
                else:
                    st.info(full_message)
            else:
                st.info("Non è stato possibile calcolare la perdita di velocità per questa serie.")
else:
    st.info("Questa serie è stata analizzata in modalità **Solo Bar Path**: nessuna metrica VBT disponibile.")

theme.footer()
