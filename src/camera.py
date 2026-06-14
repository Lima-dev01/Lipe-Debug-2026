import threading
import queue
import cv2
import numpy as np
import mediapipe as mp
from mediapipe.tasks import python as mp_python
from mediapipe.tasks.python import vision as mp_vision

from src.config import CONFIG

_cfg_cam     = CONFIG["camera"]
_cfg_gesture = CONFIG["gesture"]

_IDX_LEFT_SHOULDER  = 11
_IDX_RIGHT_SHOULDER = 12
_IDX_LEFT_WRIST     = 15
_IDX_RIGHT_WRIST    = 16

# Conexões relevantes do corpo (subconjunto do BlazePose)
_POSE_CONNECTIONS = [
    (11, 12), (11, 13), (13, 15), (12, 14), (14, 16),  # braços
    (11, 23), (12, 24), (23, 24),                        # tronco
    (23, 25), (25, 27), (24, 26), (26, 28),              # pernas
]


def _draw_landmarks_on_frame(frame_rgb, pose_landmarks, w, h):
    """Desenha landmarks e conexões manualmente com OpenCV."""
    annotated = frame_rgb.copy()

    # Converte coordenadas normalizadas → pixels
    pts = {}
    for idx, lm in enumerate(pose_landmarks):
        px = int(lm.x * w)
        py = int(lm.y * h)
        pts[idx] = (px, py)

    # Conexões
    for a, b in _POSE_CONNECTIONS:
        if a in pts and b in pts:
            cv2.line(annotated, pts[a], pts[b], (255, 255, 255), 2, cv2.LINE_AA)

    # Pontos
    for idx, (px, py) in pts.items():
        cv2.circle(annotated, (px, py), 4, (0, 255, 120), -1, cv2.LINE_AA)
        cv2.circle(annotated, (px, py), 4, (0, 180, 80),   1, cv2.LINE_AA)

    return annotated


class CameraThread:
    """
    Captura webcam + MediaPipe PoseLandmarker (API 0.10+) em thread separada.
    """

    def __init__(self):
        self._cap = cv2.VideoCapture(_cfg_cam["index"])
        self._cap.set(cv2.CAP_PROP_FRAME_WIDTH,  _cfg_cam["width"])
        self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, _cfg_cam["height"])

        self._queue = queue.Queue(maxsize=2)
        self._stop  = threading.Event()

        self._raise_right_count = 0
        self._raise_left_count  = 0

        base_options = mp_python.BaseOptions(
            model_asset_path=self._get_model_path()
        )
        options = mp_vision.PoseLandmarkerOptions(
            base_options=base_options,
            output_segmentation_masks=False,
            running_mode=mp_vision.RunningMode.VIDEO,
            num_poses=1,
            min_pose_detection_confidence=0.5,
            min_pose_presence_confidence=0.5,
            min_tracking_confidence=0.5,
        )
        self._detector = mp_vision.PoseLandmarker.create_from_options(options)
        self._thread   = threading.Thread(target=self._run, daemon=True)

    def _get_model_path(self) -> str:
        import os, urllib.request

        model_dir  = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "assets"
        )
        model_path = os.path.join(model_dir, "pose_landmarker.task")

        if not os.path.exists(model_path):
            print("[CAMERA] Baixando modelo pose_landmarker.task (~7 MB)...")
            url = (
                "https://storage.googleapis.com/mediapipe-models/"
                "pose_landmarker/pose_landmarker_lite/float16/latest/"
                "pose_landmarker_lite.task"
            )
            os.makedirs(model_dir, exist_ok=True)
            urllib.request.urlretrieve(url, model_path)
            print("[CAMERA] Modelo baixado com sucesso.")

        return model_path

    def start(self):
        self._thread.start()

    def stop(self):
        self._stop.set()
        self._cap.release()
        self._detector.close()

    def get_latest(self) -> dict | None:
        try:
            return self._queue.get_nowait()
        except queue.Empty:
            return None

    def _run(self):
        frames_to_confirm = _cfg_gesture["frames_to_confirm"]
        margin            = _cfg_gesture["wrist_above_shoulder_margin"]
        timestamp_ms      = 0

        while not self._stop.is_set():
            ok, frame_bgr = self._cap.read()
            if not ok:
                continue

            frame_bgr = cv2.flip(frame_bgr, 1)
            frame_rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
            h, w      = frame_rgb.shape[:2]

            mp_image = mp.Image(
                image_format=mp.ImageFormat.SRGB,
                data=frame_rgb
            )

            timestamp_ms += 33
            result = self._detector.detect_for_video(mp_image, timestamp_ms)

            landmarks   = None
            raise_right = False
            raise_left  = False

            if result.pose_landmarks:
                lm = result.pose_landmarks[0]
                landmarks = lm

                r_shoulder_y = lm[_IDX_RIGHT_SHOULDER].y
                r_wrist_y    = lm[_IDX_RIGHT_WRIST].y
                l_shoulder_y = lm[_IDX_LEFT_SHOULDER].y
                l_wrist_y    = lm[_IDX_LEFT_WRIST].y

                right_up = r_wrist_y < (r_shoulder_y - margin)
                left_up  = l_wrist_y < (l_shoulder_y - margin)

                self._raise_right_count = (self._raise_right_count + 1) if right_up  else 0
                self._raise_left_count  = (self._raise_left_count  + 1) if left_up   else 0

                raise_right = self._raise_right_count >= frames_to_confirm
                raise_left  = self._raise_left_count  >= frames_to_confirm

                if CONFIG["debug"]:
                    frame_rgb = _draw_landmarks_on_frame(frame_rgb, lm, w, h)

            packet = {
                "frame_rgb":   frame_rgb,
                "landmarks":   landmarks,
                "raise_right": raise_right,
                "raise_left":  raise_left,
            }

            if self._queue.full():
                try:
                    self._queue.get_nowait()
                except queue.Empty:
                    pass
            self._queue.put(packet)