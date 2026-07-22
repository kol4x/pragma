"""
PRAGMA FIT — Motore di calcolo (bar path tracking + VBT).

Questo modulo contiene ESATTAMENTE la stessa logica di calcolo della
versione originale monolitica di app.py: nessuna formula, soglia o
algoritmo e' stato cambiato. E' stato solo spostato qui per poter
costruire sopra una vera web app multipagina, mantenendo il motore
completamente separato dalla presentazione/tema.

Vedi i commenti originali per il razionale di ogni costante: sono stati
preservati parola per parola.
"""

import os
import time
import hashlib
import tempfile

import cv2
import streamlit as st
import imageio

# ----------------------------------------------------------------------------
# COSTANTI VBT
# ----------------------------------------------------------------------------
GRAVITY = 9.81  # m/s^2

# Soglie per la classificazione di fase (su/giu'/fermo) usate per il conteggio
# ripetizioni e per isolare i campioni "concentrici" (fase di salita).
V_THRESHOLD = 0.05          # m/s: sotto questa soglia il movimento e' considerato rumore
                             # (alzata da 0.03: la fase eccentrica controllata e' lenta, quindi
                             # con una soglia troppo bassa il rumore di tracciamento durante la
                             # discesa puo' superarla e passare per un breve tratto "in salita")
MIN_REP_DISPLACEMENT_M = 0.05  # una "salita" deve spostare almeno 5 cm per contare come rep
MIN_REP_DURATION_S = 0.15   # durata minima di una "salita" per contare come rep (non un numero
                             # fisso di fotogrammi: cosi' funziona correttamente sia a 24 che a
                             # 60 fps)
PEAK_TO_THRESHOLD_MIN_RATIO = 2.0  # il picco di velocita' del tratto deve superare chiaramente
                                    # la soglia di rumore (non bastare per un pelo) per essere
                                    # considerato un vero movimento esplosivo
REP_OUTLIER_MULTIPLIER = 2.2       # una "rep" con velocita' media oltre 2.2x la mediana delle
                                    # altre rep della stessa serie e' quasi certamente un
                                    # artefatto di tracciamento, non un colpo davvero piu' veloce
                                    # (era la causa piu' probabile del bug "500kg da 100kg")
TRIM_VELOCITY_FRACTION = 0.20      # rifila dalla media (non dal segmento) i fotogrammi di testa/coda
                                    # sotto il 20% del picco della rep: sono lo stacco iniziale e il
                                    # lockout finale, quasi fermi, che il debounce include nel
                                    # segmento ma che farebbero crollare la media senza motivo
MIN_REP_SAMPLES_AFTER_TRIM = 3     # se il trim lascia meno campioni di cosi', si tiene il segmento
                                    # originale non tagliato (evita medie su 1-2 valori isolati)
SMOOTH_WINDOW = 7           # finestra di media mobile sulla posizione, solo per i calcoli fisici
VELOCITY_SMOOTH_WINDOW = 3  # ulteriore, leggero smoothing sulla serie di velocita' stessa

# Profili carico-velocita' per la stima dell'1RM: %1RM = a - b * v_media_rep_piu_veloce
# ATTENZIONE: solo il profilo "Panca Piana" corrisponde a un modello diffuso in
# letteratura VBT. I profili di Squat e Stacco da terra qui sotto sono valori
# INDICATIVI/APPROSSIMATI (non una citazione scientifica specifica): usali solo
# come riferimento di massima, non come dato clinico validato.
EXERCISE_PROFILES = {
    "Panca Piana": {"a": 121.1, "b": 74.7},
    "Squat": {"a": 116.0, "b": 63.5},          # indicativo
    "Stacco da terra": {"a": 110.0, "b": 72.0},  # indicativo
}

# --- Affidabilita' della stima 1RM da velocita' -----------------------------
# Il modello carico-velocita' (%1RM = a - b*v) e' calibrato per SERIE BREVI
# (1-3 ripetizioni) eseguite alla massima velocita' intenzionale con un carico
# davvero impegnativo. Fuori da queste condizioni la stima puo' diventare
# assurda in DUE direzioni opposte:
# - troppo ALTA: un colpo "veloce" dentro una serie lunga o sub-massimale (es.
#   100kg per 8 ripetizioni) puo' avere una velocita' che il modello legge
#   come "carico leggerissimo" (es. 500kg da un colpo a 100kg).
# - troppo BASSA: fotogrammi quasi fermi a inizio/fine rep (vedi TRIM_VELOCITY_
#   FRACTION sopra) o un'inquadratura non perfettamente parallela al bilanciere
#   possono far leggere una velocita' piu' bassa del vero, che il modello
#   scambia per "sei al 100% del massimale" anche se hai fatto piu' rep — cosa
#   fisicamente impossibile (se hai fatto 3 rep, sulla prima non eri al 100%).
#
# Soluzione applicata (protezione simmetrica):
# 1. Il pavimento del clamp su %1RM e' al 30% (PCT_1RM_FLOOR): sotto questa
#    soglia il modello e' considerato fuori dal proprio range valido (troppo
#    ALTA velocita' per essere credibile).
# 2. Il %1RM grezzo non puo' superare di piu' di PCT_1RM_CEILING_TOLERANCE
#    punti percentuali quello atteso dal numero di ripetizioni realmente
#    svolte (troppo BASSA velocita' per essere credibile, vedi
#    expected_pct_1rm_for_reps).
# 3. Quando la serie ha piu' di REPS_MAX_FOR_RELIABLE_VBT ripetizioni, oppure
#    quando uno dei due controlli sopra fallisce, la stima da velocita' viene
#    affiancata (non sostituita silenziosamente) da una stima classica basata
#    sul numero di ripetizioni (formula di Epley), con un avviso esplicito su
#    quale numero fidarsi di piu' e perche'.
PCT_1RM_FLOOR = 30.0
PCT_1RM_CEILING_TOLERANCE = 10.0
REPS_MAX_FOR_RELIABLE_VBT = 3


# ----------------------------------------------------------------------------
# UTILS DI TRACCIAMENTO (invariati rispetto alla versione Bar Path)
# ----------------------------------------------------------------------------
def create_tracker():
    """Crea un tracker CSRT, gestendo le diverse posizioni dell'API in OpenCV."""
    creators = []
    if hasattr(cv2, "TrackerCSRT_create"):
        creators.append(cv2.TrackerCSRT_create)
    if hasattr(cv2, "legacy") and hasattr(cv2.legacy, "TrackerCSRT_create"):
        creators.append(cv2.legacy.TrackerCSRT_create)
    last_err = None
    for creator in creators:
        try:
            return creator()
        except Exception as e:  # pragma: no cover
            last_err = e
    raise RuntimeError(
        "Impossibile creare il tracker CSRT. Verifica di avere installato "
        f"'opencv-contrib-python-headless' (errore: {last_err})."
    )


def clamp_bbox(x, y, w, h, frame_w, frame_h):
    x = max(0, min(x, frame_w - 1))
    y = max(0, min(y, frame_h - 1))
    w = max(4, min(w, frame_w - x))
    h = max(4, min(h, frame_h - y))
    return int(x), int(y), int(w), int(h)


def file_signature(uploaded_file) -> str:
    return hashlib.md5(
        f"{uploaded_file.name}-{uploaded_file.size}".encode("utf-8")
    ).hexdigest()


@st.cache_data(show_spinner=False)
def extract_first_frame(video_bytes: bytes, _sig: str):
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".mp4")
    tmp.write(video_bytes)
    tmp.flush()
    tmp.close()
    cap = cv2.VideoCapture(tmp.name)
    ok, frame = cap.read()
    fps = cap.get(cv2.CAP_PROP_FPS) or 30
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) or 0
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    cap.release()
    os.remove(tmp.name)
    if not ok:
        return None, fps, total_frames, width, height
    rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    return rgb_frame, fps, total_frames, width, height


# ----------------------------------------------------------------------------
# MOTORE DI CALCOLO VBT (velocità, potenza, ripetizioni, 1RM, feedback)
# ----------------------------------------------------------------------------
def smooth_series(values, window):
    """Media mobile centrata semplice, usata solo per i calcoli fisici."""
    n = len(values)
    if n == 0:
        return []
    half = window // 2
    smoothed = []
    for i in range(n):
        lo = max(0, i - half)
        hi = min(n, i + half + 1)
        chunk = values[lo:hi]
        smoothed.append(sum(chunk) / len(chunk))
    return smoothed


def compute_vbt_metrics(raw_series, fps, mpp, weight_kg):
    """
    Calcola velocita', potenza, fasi (su/giu') e ripetizioni a partire dalla
    serie di centri tracciati.

    raw_series: lista di tuple (frame_idx, x_px, y_px) SOLO per i fotogrammi
                in cui il tracciamento e' riuscito (i fotogrammi persi vengono
                semplicemente saltati nel calcolo del delta tempo/spazio).
    fps: fotogrammi al secondo del video.
    mpp: metri per pixel (fattore di calibrazione).
    weight_kg: peso sul bilanciere (kg), usato per calcolare Forza e Potenza.

    Ritorna un dizionario con le metriche aggregate e la lista delle
    ripetizioni rilevate (ognuna con velocita' media/di picco).
    """
    if len(raw_series) < 3:
        return None

    frame_idxs = [p[0] for p in raw_series]
    y_positions = [p[2] for p in raw_series]

    # Smoothing SOLO per i calcoli fisici (non per la linea disegnata sul video)
    y_smooth = smooth_series(y_positions, SMOOTH_WINDOW)

    # --- Velocita' istantanea (asse verticale) ---
    # Convenzione: positiva = verso l'alto (fase concentrica per gli esercizi
    # supportati), perche' in pixel-immagine y decresce salendo.
    velocities = [0.0]  # nessuna velocita' definita per il primissimo campione
    for i in range(1, len(y_smooth)):
        dt = (frame_idxs[i] - frame_idxs[i - 1]) / fps
        if dt <= 0:
            velocities.append(velocities[-1])
            continue
        dy_px = y_smooth[i - 1] - y_smooth[i]  # positivo se sale
        dy_m = dy_px * mpp
        v = dy_m / dt
        velocities.append(v)

    # Smoothing leggero anche sulla velocita' stessa: lo smoothing sulla sola
    # posizione non basta a eliminare gli "spike" della derivata quando il
    # tracciamento oscilla di 1-2 pixel tra due fotogrammi consecutivi. Senza
    # questo passaggio, un singolo colpo rumoroso puo' risultare con una
    # velocita' istantanea assurda e falsare la stima dell'1RM (era la causa
    # principale del bug "500kg da un colpo a 100kg").
    velocities = smooth_series(velocities, VELOCITY_SMOOTH_WINDOW)

    # --- Accelerazione e potenza istantanea ---
    # Forza = m * (g + a); Potenza = Forza * velocita'
    accelerations = [0.0]
    for i in range(1, len(velocities)):
        dt = (frame_idxs[i] - frame_idxs[i - 1]) / fps
        if dt <= 0:
            accelerations.append(0.0)
            continue
        a = (velocities[i] - velocities[i - 1]) / dt
        accelerations.append(a)

    # --- Classificazione fase (su / giu' / fermo) con debounce anti-rumore ---
    debounce_frames = max(2, round(fps * 0.10))  # ~100ms di persistenza minima

    direction_raw = []
    for v in velocities:
        if v > V_THRESHOLD:
            direction_raw.append("up")
        elif v < -V_THRESHOLD:
            direction_raw.append("down")
        else:
            direction_raw.append("still")

    confirmed_phase = []
    if direction_raw:
        run_dir = direction_raw[0]
        run_len = 0
        current_phase = run_dir
        for d in direction_raw:
            if d == run_dir:
                run_len += 1
            else:
                run_dir = d
                run_len = 1
            if run_len >= debounce_frames:
                current_phase = run_dir
            confirmed_phase.append(current_phase)

    # --- Segmentazione delle ripetizioni (ogni tratto continuo "up") ---
    min_rep_samples = max(4, round(fps * MIN_REP_DURATION_S))
    reps = []
    i = 0
    n = len(confirmed_phase)
    while i < n:
        if confirmed_phase[i] == "up":
            start = i
            while i < n and confirmed_phase[i] == "up":
                i += 1
            end = i - 1
            seg_velocities = velocities[start:end + 1]
            seg_displacement_m = sum(
                (y_smooth[k] - y_smooth[k + 1]) * mpp
                for k in range(start, end)
                if k + 1 <= end
            )
            # Filtra micro-oscillazioni classificate come "salita" per errore:
            # spostamento minimo, durata minima (proporzionata agli fps: 4
            # fotogrammi a 30fps sono ~130ms, a 60fps sarebbero troppo pochi),
            # e un picco di velocita' chiaramente sopra la soglia di rumore
            # (non solo "appena sopra" per un fotogramma isolato).
            if (
                abs(seg_displacement_m) >= MIN_REP_DISPLACEMENT_M
                and len(seg_velocities) >= min_rep_samples
                and max(seg_velocities) >= V_THRESHOLD * PEAK_TO_THRESHOLD_MIN_RATIO
            ):
                peak_v_seg = max(seg_velocities)
                # Il meccanismo di debounce (necessario per non spezzare una
                # rep per un fotogramma rumoroso) ha un effetto collaterale:
                # include nel segmento anche qualche fotogramma di "coda"
                # quasi fermo, subito prima dello stacco e subito dopo il
                # lockout, prima che il cambio di fase venga confermato.
                # Includerli nella MEDIA la fa crollare artificialmente,
                # anche se a meta' salita la spinta e' stata forte (lo si
                # vede dal picco).
                trim_floor = TRIM_VELOCITY_FRACTION * peak_v_seg
                lo, hi = 0, len(seg_velocities) - 1
                while lo < hi and seg_velocities[lo] < trim_floor:
                    lo += 1
                while hi > lo and seg_velocities[hi] < trim_floor:
                    hi -= 1
                trimmed = seg_velocities[lo:hi + 1]
                # Se il trim lascia troppo pochi campioni (rep molto corta),
                # meglio tenere il segmento originale piuttosto che rischiare
                # una media calcolata su 1-2 valori isolati.
                if len(trimmed) < MIN_REP_SAMPLES_AFTER_TRIM:
                    trimmed = seg_velocities

                reps.append({
                    "start_idx": start,
                    "end_idx": end,
                    "mean_v": sum(trimmed) / len(trimmed),
                    "peak_v": peak_v_seg,
                })
        else:
            i += 1

    # --- Rilevamento outlier tra le ripetizioni (protezione per la stima 1RM) ---
    # Anche dopo i filtri sopra, un singolo tratto puo' restare "falsamente
    # veloce" per rumore di tracciamento residuo — tipicamente durante la fase
    # eccentrica (discesa), che essendo lenta e controllata ha un rapporto
    # segnale/rumore peggiore della concentrica esplosiva. Se scelto come
    # "ripetizione piu' veloce", questo tipo di artefatto e' la causa piu'
    # probabile di stime 1RM assurde. Qui marchiamo come outlier ogni rep la
    # cui velocita' media supera abbondantemente la mediana della serie:
    # una vera serie di ripetizioni pesanti ha velocita' simili tra loro,
    # non un colpo isolato molto piu' "esplosivo" degli altri.
    if len(reps) >= 2:
        sorted_means = sorted(r["mean_v"] for r in reps)
        mid = len(sorted_means) // 2
        median_v = (
            sorted_means[mid] if len(sorted_means) % 2 == 1
            else (sorted_means[mid - 1] + sorted_means[mid]) / 2
        )
        for r in reps:
            r["is_outlier"] = median_v > 0 and r["mean_v"] > REP_OUTLIER_MULTIPLIER * median_v
    else:
        for r in reps:
            r["is_outlier"] = False

    # --- Metriche aggregate ---
    # Costruite SOLO dai campioni appartenenti a ripetizioni valide e non
    # outlier (la stessa lista 'reps' usata per l'1RM), non da ogni singolo
    # fotogramma grezzo classificato "su": cosi' un tratto rumoroso troppo
    # corto per essere una vera rep (o marcato outlier) non gonfia neppure
    # "Velocità di picco" o "Potenza di picco" nella dashboard.
    clean_reps = [r for r in reps if not r["is_outlier"]]
    reps_for_aggregate = clean_reps if clean_reps else reps

    concentric_indices = [
        idx
        for r in reps_for_aggregate
        for idx in range(r["start_idx"], r["end_idx"] + 1)
    ]
    concentric_velocities = [velocities[idx] for idx in concentric_indices]
    concentric_power = [
        weight_kg * (GRAVITY + accelerations[idx]) * velocities[idx]
        for idx in concentric_indices
    ] if concentric_indices else []

    mean_concentric_velocity = (
        sum(concentric_velocities) / len(concentric_velocities) if concentric_velocities else 0.0
    )
    peak_velocity = max(concentric_velocities) if concentric_velocities else 0.0
    peak_power = max(concentric_power) if concentric_power else 0.0

    return {
        "reps": reps,
        "mean_concentric_velocity": mean_concentric_velocity,
        "peak_velocity": peak_velocity,
        "peak_power": peak_power,
        "reps_count": len(reps),
    }


def estimate_1rm_velocity(exercise_name, fastest_rep_velocity, weight_kg):
    """
    Stima l'1RM dal profilo carico-velocita' dell'esercizio, usando la
    velocita' media della SINGOLA ripetizione piu' veloce della serie (mai
    una media su tutte le ripetizioni: mediare i colpi di una serie lunga
    con quelli di una serie esplosiva breve produrrebbe una velocita' non
    rappresentativa di nessuno dei due scenari).

    Ritorna (1RM stimato, %1RM usato/clampato, affidabile:bool, %1RM grezzo
    non-clampato). 'affidabile' e' False quando il %1RM grezzo cade sotto
    PCT_1RM_FLOOR: significa che la velocita' misurata e' fuori dal range su
    cui il modello lineare ha senso (tipicamente perche' il colpo piu' veloce
    viene da una serie lunga o sub-massimale, non da un vero tentativo a
    carico impegnativo). Il %1RM grezzo viene restituito anche quando supera
    il 100%, cosi' chi chiama puo' verificare la coerenza con il numero di
    ripetizioni svolte (vedi expected_pct_1rm_for_reps).
    """
    profile = EXERCISE_PROFILES[exercise_name]
    pct_1rm_raw = profile["a"] - profile["b"] * fastest_rep_velocity
    affidabile = pct_1rm_raw >= PCT_1RM_FLOOR
    pct_1rm_clamped = max(PCT_1RM_FLOOR, min(100.0, pct_1rm_raw))
    estimated_1rm = weight_kg / (pct_1rm_clamped / 100.0)
    return estimated_1rm, pct_1rm_clamped, affidabile, pct_1rm_raw


def expected_pct_1rm_for_reps(reps_count):
    """
    %1RM atteso per un certo numero di ripetizioni, dalla stessa relazione
    che sta dietro alla formula di Epley (100% per 1 rep, via via piu' basso
    all'aumentare delle rep). Usato come ancora di coerenza: se il %1RM
    calcolato dalla velocita' risulta molto piu' ALTO di quanto il numero di
    ripetizioni realmente svolte renda plausibile, la lettura di velocita'
    e' quasi certamente troppo bassa per un motivo esterno al modello
    (fotogrammi quasi fermi a inizio/fine rep, inquadratura non perfettamente
    parallela al bilanciere, ecc.) — fisicamente, se hai fatto 3 ripetizioni
    non puoi essere stato al 100% del tuo massimale sulla prima.
    """
    reps_count = max(1, reps_count)
    return 100.0 / (1.0 + reps_count / 30.0)


def estimate_1rm_from_reps(weight_kg, reps_count):
    """
    Stima di riserva basata sul numero di ripetizioni (formula di Epley),
    utile come riferimento incrociato quando la serie non e' adatta alla
    stima da velocita' (troppo lunga per essere stata un tentativo massimale
    a velocita' intenzionale). Presuppone la serie svolta vicino al cedimento:
    e' anch'essa una stima, non un dato certo.
    """
    reps_count = max(1, reps_count)
    return weight_kg * (1 + reps_count / 30.0)


def velocity_loss_feedback(vl_pct):
    """Restituisce (tipo_box, messaggio) in base alla perdita di velocita'."""
    if vl_pct < 10:
        return "success", (
            "Fatica minima. Ottimo per stimolare la forza esplosiva o se hai "
            "altre serie da fare. Puoi aumentare leggermente il carico."
        )
    elif vl_pct <= 20:
        return "info", (
            "Zona ideale per l'ipertrofia e la forza neurale. Ottimo stimolo "
            "allenante, mantieni questo peso."
        )
    elif vl_pct <= 30:
        return "warning", (
            "Fatica moderata-alta. Sei in una zona di transizione: valuta se "
            "ridurre leggermente il carico nelle prossime serie."
        )
    else:
        return "warning", (
            "Fatica eccessiva rilevata! Stai sporcando il movimento o sei "
            "vicino al cedimento totale. Riduci il carico del 5-10% nella "
            "prossima serie o fermati qui."
        )


def hex_to_bgr(hex_color: str):
    hex_color = hex_color.lstrip("#")
    r, g, b = tuple(int(hex_color[i:i + 2], 16) for i in (0, 2, 4))
    return (b, g, r)


def process_video(uploaded_file, video_bytes, selected_point, box_size, width, height,
                   fps, total_frames, vbt_mode, diametro_cm, line_color_bgr, line_thickness,
                   progress_bar, status_text):
    """
    Esegue il tracciamento CSRT sull'intero video e scrive il video di output
    con la traiettoria disegnata. Identico all'elaborazione originale
    (nessuna modifica alla logica di tracciamento/disegno).

    Ritorna un dizionario con: output_path, raw_series, lost_frames,
    frame_idx, elapsed_s, mpp.
    """
    input_suffix = os.path.splitext(uploaded_file.name)[1] or ".mp4"
    input_tmp = tempfile.NamedTemporaryFile(delete=False, suffix=input_suffix)
    input_tmp.write(video_bytes)
    input_tmp.flush()
    input_path = input_tmp.name
    input_tmp.close()

    output_path = tempfile.NamedTemporaryFile(delete=False, suffix=".mp4").name

    cap = cv2.VideoCapture(input_path)
    if not cap.isOpened():
        raise RuntimeError("Impossibile leggere il video. Prova con un altro file o formato (mp4 consigliato).")

    ret, frame = cap.read()
    if not ret:
        cap.release()
        raise RuntimeError("Impossibile leggere il primo fotogramma per inizializzare il tracciamento.")

    px, py = selected_point
    half = box_size // 2
    init_bbox = clamp_bbox(px - half, py - half, box_size, box_size, width, height)

    # Fattore di calibrazione pixel -> metri (solo modalita' VBT):
    # usiamo l'altezza della bounding box iniziale come riferimento del
    # diametro del disco. metri_per_pixel = (diametro_cm/100) / altezza_px
    mpp = None
    if vbt_mode:
        bbox_height_px = init_bbox[3]
        mpp = (diametro_cm / 100.0) / bbox_height_px

    tracker = create_tracker()
    tracker.init(frame, init_bbox)

    writer = imageio.get_writer(
        output_path,
        fps=fps,
        codec="libx264",
        quality=8,
        pixelformat="yuv420p",
        macro_block_size=1,
    )

    trajectory_points = []
    raw_series = []  # (frame_idx, x_px, y_px) per i soli frame trovati (usato solo in VBT)
    lost_frames = 0
    frame_idx = 0
    start_time = time.time()
    last_center = (int(px), int(py))

    while True:
        if frame_idx > 0:
            ret, frame = cap.read()
            if not ret:
                break
        frame_idx += 1

        if frame_idx == 1:
            x, y, w, h = init_bbox
            success = True
        else:
            success, bbox = tracker.update(frame)
            if success:
                x, y, w, h = bbox

        if success:
            center = (int(x + w / 2), int(y + h / 2))
            last_center = center
            trajectory_points.append(center)
            if vbt_mode:
                raw_series.append((frame_idx, center[0], center[1]))
        else:
            lost_frames += 1
            # Nessun punto fittizio: il percorso disegnato resta quello reale
            # fin dove il tracciamento e' riuscito.

        if len(trajectory_points) > 1:
            for i in range(1, len(trajectory_points)):
                cv2.line(
                    frame,
                    trajectory_points[i - 1],
                    trajectory_points[i],
                    line_color_bgr,
                    line_thickness,
                    lineType=cv2.LINE_AA,
                )

        marker_color = line_color_bgr if success else (128, 128, 128)
        cv2.circle(frame, last_center, line_thickness + 2, marker_color, -1, lineType=cv2.LINE_AA)
        cv2.circle(frame, last_center, line_thickness + 4, (255, 255, 255), 2, lineType=cv2.LINE_AA)

        frame_rgb_out = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        writer.append_data(frame_rgb_out)

        progress = min(frame_idx / max(total_frames, 1), 1.0)
        elapsed = time.time() - start_time
        if progress_bar is not None:
            progress_bar.progress(
                progress,
                text=f"Elaborazione fotogramma {frame_idx}/{total_frames or '?'} "
                     f"({progress*100:.0f}%) · {elapsed:.0f}s",
            )

    cap.release()
    writer.close()

    try:
        os.remove(input_path)
    except OSError:
        pass

    return {
        "output_path": output_path,
        "raw_series": raw_series,
        "lost_frames": lost_frames,
        "frame_idx": frame_idx,
        "elapsed_s": time.time() - start_time,
        "mpp": mpp,
    }
