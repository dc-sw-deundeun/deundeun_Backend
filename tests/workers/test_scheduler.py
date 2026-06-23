import contextlib

import pytest

from app.workers import scheduler


@pytest.mark.asyncio
async def test_ocr_batch_tick_runs_recovery(db_session, monkeypatch):
    # session_scope가 테스트 세션을 쓰도록 패치
    @contextlib.contextmanager
    def _scope():
        yield db_session

    monkeypatch.setattr(scheduler, "session_scope", _scope)
    processed = await scheduler._ocr_batch_tick()
    assert processed == 0  # PENDING 없음 → 0


@pytest.mark.asyncio
async def test_start_scheduler_registers_job():
    # AsyncIOScheduler.start() requires a running event loop;
    # making this an async test ensures one is active.
    try:
        scheduler.start_scheduler()
        assert scheduler._scheduler is not None
        assert len(scheduler._scheduler.get_jobs()) >= 1
    finally:
        scheduler.stop_scheduler()
