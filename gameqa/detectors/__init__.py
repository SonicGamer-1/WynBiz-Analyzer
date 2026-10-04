"""gameqa.detectors -- rule-based bug detectors. No ML."""
from .base import DetectContext, Detector, Finding
from .crash import CrashDetector
from .exploit import ExploitDetector
from .map_hole import MapHoleDetector
from .softlock import SoftlockDetector

ALL_DETECTORS = [
    CrashDetector,
    SoftlockDetector,
    MapHoleDetector,
    ExploitDetector,
]


def make_detectors():
    return [cls() for cls in ALL_DETECTORS]


__all__ = [
    "ALL_DETECTORS",
    "DetectContext",
    "Detector",
    "Finding",
    "CrashDetector",
    "ExploitDetector",
    "MapHoleDetector",
    "SoftlockDetector",
    "make_detectors",
]
