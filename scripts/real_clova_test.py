"""실제 Naver Clova General OCR 호출 → 원문 추출 + 파서 구조화 확인.

실행: PYTHONPATH=. python scripts/real_clova_test.py [이미지경로]
- .env의 CLOVA_OCR_INVOKE_URL / CLOVA_OCR_SECRET_KEY 사용
- 로컬 이미지를 base64(data)로 전송(클라우드 URL 불필요)
- 응답을 OcrFieldDTO로 매핑 후 OcrParser로 구조화
"""

import base64
import os
import sys
import time
import uuid

import httpx

from app.core.config import settings
from app.infrastructure.ocr.ocr_dto import OcrFieldDTO, OcrResultDTO
from app.infrastructure.ocr.parser import OcrParser

DEFAULT_IMAGE = os.path.expanduser("~/Desktop/일반건강검진.png")


def call_clova(image_path: str) -> dict:
    invoke_url = settings.clova_ocr_invoke_url
    secret_key = settings.clova_ocr_secret_key
    assert invoke_url and secret_key, "Clova 설정 누락(.env)"
    with open(image_path, "rb") as fh:
        b64 = base64.b64encode(fh.read()).decode("ascii")
    ext = image_path.rsplit(".", 1)[-1].lower()
    payload = {
        "version": "V2",
        "requestId": str(uuid.uuid4()),
        "timestamp": int(time.time() * 1000),
        "images": [{"format": ext, "name": "checkup", "data": b64}],
    }
    headers = {"X-OCR-SECRET": secret_key}
    resp = httpx.post(invoke_url, json=payload, headers=headers, timeout=60.0)
    resp.raise_for_status()
    return resp.json()


def to_result(body: dict) -> OcrResultDTO:
    fields = []
    for image in body.get("images") or []:
        for raw in image.get("fields") or []:
            vertices = (raw.get("boundingPoly") or {}).get("vertices")
            if not vertices:
                continue
            fields.append(
                OcrFieldDTO.from_vertices(
                    text=raw.get("inferText", ""),
                    confidence=raw.get("inferConfidence", 0.0),
                    vertices=vertices,
                )
            )
    return OcrResultDTO(fields=fields)


def main():
    image_path = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_IMAGE
    assert settings.clova_ocr_invoke_url and settings.clova_ocr_secret_key, "Clova 설정 누락(.env)"
    print(f"[IMG]  {image_path}")
    print(f"[API]  {settings.clova_ocr_invoke_url[:60]}...")

    body = call_clova(image_path)
    result = to_result(body)
    print(f"\n[RAW]  Clova 인식 토큰 {len(result.fields)}개 (원문):")
    line = " ".join(
        f.text for f in sorted(result.fields, key=lambda f: (round(f.y_center / 18), f.x_min))
    )
    print("  " + line)

    metrics = OcrParser().parse(result)
    print(f"\n[PARSE] 파서 구조화 결과 {len(metrics)}개 metric:")
    print(f"  {'metric_code':18} {'value':10} {'unit':8} {'conf':6}")
    print("  " + "-" * 46)
    for m in sorted(metrics, key=lambda m: m.metric_code):
        print(
            f"  {m.metric_code:18} {m.value:10} {m.unit or '':8} {m.confidence:.2f}  (raw={m.raw_text!r})"
        )

    print("\n[NOTE] 위 metric이 checkup_metric_results에 source=OCR/미검수로 저장되고,")
    print("       사용자가 검수(verify) 후에야 분석(해석) 단계로 진입합니다.")


if __name__ == "__main__":
    main()
