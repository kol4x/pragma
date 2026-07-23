
import os
import time
import hashlib
import tempfile

import cv2
import streamlit as st
import imageio

GRAVITY = 9.81

V_THRESHOLD = 0.05
MIN_REP_DISPLACEMENT_M = 0.05
MIN_REP_DURATION_S = 0.15
PEAK_TO_THRESHOLD_MIN_RATIO = 2.0
REP_OUTLIER_MULTIPLIER = 2.2
TRIM_VELOCITY_FRACTION = 0.20
MIN_REP_SAMPLES_AFTER_TRIM = 3
SMOOTH_WINDOW = 7
VELOCITY_SMOOTH_WINDOW = 3

EXERCISE_PROFILES = {
    "Panca Piana": {"a": 121.1, "b": 74.7},
    "Squat": {"a": 116.0, "b": 63.5},
    "Stacco da terra": {"a": 110.0, "b": 72.0},
}

PCT_1RM_FLOOR = 30.0
PCT_1RM_CEILING_TOLERANCE = 10.0
REPS_MAX_FOR_RELIABLE_VBT = 3


def create_tracker():
    creators = []
    if hasattr(cv2, "TrackerCSRT_create"):
        creators.append(cv2.TrackerCSRT_create)
    if hasattr(cv2, "legacy") and hasattr(cv2.legacy, "TrackerCSRT_create"):
        creators.append(cv2.legacy.TrackerCSRT_create)
    last_err = None
    for creator in creators:
        try:
            return creator()
        except Exception as e:
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


def smooth_series(values, window):
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
    if len(raw_series) < 3:
        return None

    frame_idxs = [p[0] for p in raw_series]
    y_positions = [p[2] for p in raw_series]

    y_smooth = smooth_series(y_positions, SMOOTH_WINDOW)

    velocities = [0.0]
    for i in range(1, len(y_smooth)):
        dt = (frame_idxs[i] - frame_idxs[i - 1]) / fps
        if dt <= 0:
            velocities.append(velocities[-1])
            continue
        dy_px = y_smooth[i - 1] - y_smooth[i]
        dy_m = dy_px * mpp
        v = dy_m / dt
        velocities.append(v)

    velocities = smooth_series(velocities, VELOCITY_SMOOTH_WINDOW)

    accelerations = [0.0]
    for i in range(1, len(velocities)):
        dt = (frame_idxs[i] - frame_idxs[i - 1]) / fps
        if dt <= 0:
            accelerations.append(0.0)
            continue
        a = (velocities[i] - velocities[i - 1]) / dt
        accelerations.append(a)

    debounce_frames = max(2, round(fps * 0.10))

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
            if (
                abs(seg_displacement_m) >= MIN_REP_DISPLACEMENT_M
                and len(seg_velocities) >= min_rep_samples
                and max(seg_velocities) >= V_THRESHOLD * PEAK_TO_THRESHOLD_MIN_RATIO
            ):
                peak_v_seg = max(seg_velocities)
                trim_floor = TRIM_VELOCITY_FRACTION * peak_v_seg
                lo, hi = 0, len(seg_velocities) - 1
                while lo < hi and seg_velocities[lo] < trim_floor:
                    lo += 1
                while hi > lo and seg_velocities[hi] < trim_floor:
                    hi -= 1
                trimmed = seg_velocities[lo:hi + 1]
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
    profile = EXERCISE_PROFILES[exercise_name]
    pct_1rm_raw = profile["a"] - profile["b"] * fastest_rep_velocity
    affidabile = pct_1rm_raw >= PCT_1RM_FLOOR
    pct_1rm_clamped = max(PCT_1RM_FLOOR, min(100.0, pct_1rm_raw))
    estimated_1rm = weight_kg / (pct_1rm_clamped / 100.0)
    return estimated_1rm, pct_1rm_clamped, affidabile, pct_1rm_raw


def expected_pct_1rm_for_reps(reps_count):
    reps_count = max(1, reps_count)
    return 100.0 / (1.0 + reps_count / 30.0)


def estimate_1rm_from_reps(weight_kg, reps_count):
    reps_count = max(1, reps_count)
    return weight_kg * (1 + reps_count / 30.0)


def velocity_loss_feedback(vl_pct):
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
    raw_series = []
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
