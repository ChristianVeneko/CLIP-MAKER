"""Face detection over sampled video frames (OpenCV YuNet, Haar cascade fallback)."""

from __future__ import annotations

from pathlib import Path

import numpy as np

from .speaker import FaceObs, filter_faces

ASSETS = Path(__file__).resolve().parents[2] / "assets"
YUNET_MODEL = ASSETS / "face_detection_yunet_2023mar.onnx"
DETECT_WIDTH = 960


PATCH_SIZE = (24, 20)  # (width, height) of the normalised mouth patch


def mouth_roi(mouth_right: tuple[float, float], mouth_left: tuple[float, float]) -> tuple[float, float, float, float]:
    """Region (x0, y0, x1, y1) around the mouth, sized from the distance between the corners."""
    mx = (mouth_right[0] + mouth_left[0]) / 2
    my = (mouth_right[1] + mouth_left[1]) / 2
    mw = max(abs(mouth_left[0] - mouth_right[0]), 4.0)
    return mx - 0.9 * mw, my - 0.6 * mw, mx + 0.9 * mw, my + 0.9 * mw


class FaceDetector:
    """Detects all faces (with mouth patches for speaker estimation) in a frame."""

    def __init__(self) -> None:
        import cv2

        self.cv2 = cv2
        self.backend = "haar"
        self._yunet = None
        if YUNET_MODEL.exists():
            try:
                self._yunet = cv2.FaceDetectorYN.create(str(YUNET_MODEL), "", (320, 320), 0.6, 0.3, 5000)
                self.backend = "opencv-yunet"
            except Exception:
                self._yunet = None
        if self._yunet is None:
            self._haar = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")

    def _patch(self, gray, roi) -> np.ndarray | None:
        h, w = gray.shape[:2]
        x0, y0, x1, y1 = (int(round(v)) for v in roi)
        x0, y0, x1, y1 = max(0, x0), max(0, y0), min(w, x1), min(h, y1)
        if x1 - x0 < 4 or y1 - y0 < 4:
            return None
        patch = self.cv2.resize(gray[y0:y1, x0:x1], PATCH_SIZE, interpolation=self.cv2.INTER_AREA)
        return self.cv2.GaussianBlur(patch, (3, 3), 0).astype(np.float32)

    def detect(self, frame) -> list[FaceObs]:
        cv2 = self.cv2
        h, w = frame.shape[:2]
        scale = DETECT_WIDTH / w if w > DETECT_WIDTH else 1.0
        small = cv2.resize(frame, (int(w * scale), int(h * scale))) if scale != 1.0 else frame
        found: list[tuple[float, float, float, float, tuple | None, float]] = []
        if self._yunet is not None:
            self._yunet.setInputSize((small.shape[1], small.shape[0]))
            _, det = self._yunet.detect(small)
            for f in det if det is not None else []:
                lm = f[4:14] / scale
                found.append((f[0] / scale, f[1] / scale, f[2] / scale, f[3] / scale, ((lm[6], lm[7]), (lm[8], lm[9])), float(f[14])))
        else:
            gray_small = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
            for x, y, fw, fh in self._haar.detectMultiScale(gray_small, 1.1, 5, minSize=(30, 30)):
                found.append((x / scale, y / scale, fw / scale, fh / scale, None, 1.0))
        if not found:
            return []
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        faces = []
        for x, y, fw, fh, marks, score in found:
            if marks is None:  # Haar: assume the mouth sits in the lower third of the face box
                marks = ((x + fw * 0.28, y + fh * 0.78), (x + fw * 0.72, y + fh * 0.78))
            faces.append(FaceObs(x + fw / 2, y + fh / 2, fw, fh, self._patch(gray, mouth_roi(*marks)), score))
        return filter_faces(faces, min_score=0.7)

    def center_x(self, frame) -> float | None:
        faces = self.detect(frame)
        return max(faces, key=lambda f: f.area).cx if faces else None


def probe_video(path: Path) -> tuple[int, int, float, float]:
    """Return (width, height, fps, duration_seconds) using OpenCV."""
    import cv2

    cap = cv2.VideoCapture(str(path))
    try:
        w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
        frames = cap.get(cv2.CAP_PROP_FRAME_COUNT)
        return w, h, fps, (frames / fps if frames else 0.0)
    finally:
        cap.release()


def sample_faces(
    video: Path, start: float, end: float, sample_fps: float = 6.0
) -> tuple[list[float], list[list[FaceObs]], str]:
    """Sample frames in [start, end] and detect every face.

    Returns (times relative to ``start``, faces per sample, backend name).
    """
    import cv2

    detector = FaceDetector()
    cap = cv2.VideoCapture(str(video))
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    step = max(1, int(round(fps / sample_fps)))
    cap.set(cv2.CAP_PROP_POS_MSEC, start * 1000)
    total = int((end - start) * fps)
    times: list[float] = []
    samples: list[list[FaceObs]] = []
    try:
        for i in range(total):
            if not cap.grab():
                break
            if i % step:
                continue
            ok, frame = cap.retrieve()
            if not ok:
                continue
            times.append(i / fps)
            samples.append(detector.detect(frame))
    finally:
        cap.release()
    return times, samples, detector.backend
