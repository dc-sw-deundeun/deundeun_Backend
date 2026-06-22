from enum import Enum


class OcrStatus(str, Enum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class VerificationStatus(str, Enum):
    UNVERIFIED = "UNVERIFIED"
    VERIFIED = "VERIFIED"


class MetricSource(str, Enum):
    OCR = "OCR"
    MANUAL = "MANUAL"
