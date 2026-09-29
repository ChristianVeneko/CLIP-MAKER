"""Face detection over sampled video frames (OpenCV YuNet, Haar cascade fallback)."""

from __future__ import annotations

from pathlib import Path

ASSETS = Path(__file__).resolve().parents[2] / "assets"
YUNET_MODEL = ASSETS / "face_detection_yunet_2023mar.onnx"
DETECT_WIDTH = 640


class FaceDetector:
    """Returns the horizontal center (in source pixels) of the largest face, or None."""

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

    def center_x(self, frame) -> float | None:
        cv2 = self.cv2
        h, w = frame.shape[:2]
        scale = DETECT_WIDTH / w if w > DETECT_WIDTH else 1.0
        small = cv2.resize(frame, (int(w * scale), int(h * scale))) if scale != 1.0 else frame
        faces: list[tuple[float, float, float, float]] = []
        if self._yunet is not None:
            self._yunet.setInputSize((small.shape[1], small.shape[0]))
            _, det = self._yunet.detect(small)
            if det is not None:
                faces = [(f[0], f[1], f[2], f[3]) for f in det]
        else:
            gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
            found = self._haar.detectMultiScale(gray, 1.1, 5, minSize=(30, 30))
            faces = [tuple(map(float, f)) for f in found]
        if not faces:
            return None
        x, _, fw, fh = max(faces, key=lambda f: f[2] * f[3])
        return (x + fw / 2) / scale


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


def sample_face_centers(
    video: Path, start: float, end: float, sample_fps: float = 3.0
) -> tuple[list[float], list[float | None], str]:
    """Sample frames in [start, end] and detect faces.

    Returns (times relative to ``start``, per-sample face center x or None, backend name).
    """
    import cv2

    detector = FaceDetector()
    cap = cv2.VideoCapture(str(video))
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    step = max(1, int(round(fps / sample_fps)))
    cap.set(cv2.CAP_PROP_POS_MSEC, start * 1000)
    total = int((end - start) * fps)
    times: list[float] = []
    centers: list[float | None] = []
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
            centers.append(detector.center_x(frame))
    finally:
        cap.release()
    return times, centers, detector.backend
