"""Gmail SMTP 발송 검증 스크립트.

사용법:
  1. 프로젝트 루트에 .env 파일을 설정합니다 (SMTP_HOST, SMTP_USERNAME, SMTP_PASSWORD, SMTP_FROM).
  2. 프로젝트 루트에서 실행합니다:
     python scripts/send_test_email.py <수신_이메일>

예시:
  python scripts/send_test_email.py test@example.com
"""

import asyncio
import sys
from pathlib import Path

# 프로젝트 루트를 sys.path에 추가합니다.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dotenv import load_dotenv  # type: ignore[import]

load_dotenv()

from app.infrastructure.email.smtp_email_client import SmtpEmailClient  # noqa: E402


async def main(to: str) -> None:
    client = SmtpEmailClient()
    await client.send_verification_email(to=to, code="123456")
    print(f"테스트 메일 발송 완료 → {to}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("사용법: python scripts/send_test_email.py <수신_이메일>")
        sys.exit(1)
    asyncio.run(main(sys.argv[1]))
