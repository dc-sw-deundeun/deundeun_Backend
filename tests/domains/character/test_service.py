from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.domains.character import policy
from app.domains.character.models import CharacterGrowthLog, CharacterOwnedAnimal, CharacterProfile
from app.domains.character.repository import CharacterRepository
from app.domains.character.service import CharacterService
from app.domains.user.models import User


def _create_user(db_session: Session, email: str = "char@example.com") -> User:
    user = User(email=email, password_hash="hash", nickname="캐릭터")
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def _owned_codes(db_session: Session, user_id: int) -> list[str]:
    return [
        animal.animal_code
        for animal in db_session.scalars(
            select(CharacterOwnedAnimal)
            .where(CharacterOwnedAnimal.user_id == user_id)
            .order_by(CharacterOwnedAnimal.id)
        )
    ]


def test_get_my_character_creates_default_profile_and_frog(db_session: Session) -> None:
    user = _create_user(db_session)
    service = CharacterService(CharacterRepository(db_session))

    result = service.get_my_character(user.id)

    assert result.user_id == user.id
    assert result.level == 1
    assert result.total_exp == 0
    assert [a.animal_code for a in result.owned_animals] == ["frog"]
    assert db_session.scalar(select(CharacterProfile).where(CharacterProfile.user_id == user.id))
    assert _owned_codes(db_session, user.id) == ["frog"]


def test_get_my_character_is_idempotent_for_default_frog(db_session: Session) -> None:
    user = _create_user(db_session)
    service = CharacterService(CharacterRepository(db_session))

    service.get_my_character(user.id)
    service.get_my_character(user.id)

    rows = list(
        db_session.scalars(
            select(CharacterOwnedAnimal)
            .where(CharacterOwnedAnimal.user_id == user.id)
            .order_by(CharacterOwnedAnimal.id)
        )
    )
    assert [row.animal_code for row in rows] == ["frog"]


def test_gain_exp_unlocks_cumulative_animals_and_writes_growth_log(db_session: Session) -> None:
    user = _create_user(db_session)
    service = CharacterService(CharacterRepository(db_session))
    amount = policy.cumulative_exp_before_level(5) + 37

    result = service.gain_exp(user.id, amount, reason="TEST", source="unit")

    assert result.exp_gained == amount
    assert result.level_before == 1
    assert result.level_after == 5
    assert result.leveled_up is True
    assert result.profile.current_level_exp == 37
    assert [a.animal_code for a in result.profile.owned_animals] == ["frog", "chick", "penguin"]
    assert _owned_codes(db_session, user.id) == ["frog", "chick", "penguin"]
    owned_rows = list(
        db_session.scalars(
            select(CharacterOwnedAnimal)
            .where(CharacterOwnedAnimal.user_id == user.id)
            .order_by(CharacterOwnedAnimal.id)
        )
    )
    assert [row.unlocked_total_exp for row in owned_rows] == [0, amount, amount]
    logs = list(
        db_session.scalars(select(CharacterGrowthLog).where(CharacterGrowthLog.user_id == user.id))
    )
    assert len(logs) == 1
    assert logs[0].exp_gained == amount
    assert logs[0].source == "unit"


def test_repeated_gain_exp_does_not_duplicate_unlocks(db_session: Session) -> None:
    user = _create_user(db_session)
    service = CharacterService(CharacterRepository(db_session))

    service.gain_exp(user.id, policy.cumulative_exp_before_level(3), reason="TEST", source="unit")
    service.gain_exp(user.id, 1, reason="TEST", source="unit")

    assert _owned_codes(db_session, user.id) == ["frog", "chick"]


def test_ensure_owned_animals_handles_duplicate_integrity_error(
    db_session: Session, monkeypatch
) -> None:
    user = _create_user(db_session)
    repo = CharacterRepository(db_session)
    profile = repo.get_or_create_by_user_id(user.id)
    repo.ensure_owned_animals(
        profile, [policy.animal_catalog_entries()[0]], unlocked_total_exp=profile.total_exp
    )
    original_list_owned_animals = repo.list_owned_animals
    calls = {"count": 0}

    def stale_then_fresh(user_id: int):
        calls["count"] += 1
        if calls["count"] == 1:
            return []
        return original_list_owned_animals(user_id)

    monkeypatch.setattr(repo, "list_owned_animals", stale_then_fresh)

    try:
        repo.ensure_owned_animals(
            profile, [policy.animal_catalog_entries()[0]], unlocked_total_exp=profile.total_exp
        )
    except IntegrityError:  # pragma: no cover - explicit regression guard
        raise AssertionError("duplicate owned animal sync should re-query instead of leaking")

    assert calls["count"] >= 2
    assert _owned_codes(db_session, user.id) == ["frog"]


def test_list_animals_returns_full_catalog_with_locked_state(db_session: Session) -> None:
    user = _create_user(db_session)
    service = CharacterService(CharacterRepository(db_session))

    animals = service.list_animals(user.id)

    assert [animal.animal_code for animal in animals] == [
        "frog",
        "chick",
        "penguin",
        "dog",
        "cat",
        "tiger",
        "panda",
        "monkey",
    ]
    assert animals[0].is_unlocked is True
    assert animals[0].required_total_exp == 0
    assert animals[1].is_unlocked is False
    assert animals[1].required_total_exp == 235
    assert animals[1].unlocked_at is None


def test_revoke_exp_decreases_total_exp_and_writes_negative_growth_log(
    db_session: Session,
) -> None:
    user = _create_user(db_session)
    service = CharacterService(CharacterRepository(db_session))
    service.gain_exp(user.id, 50, reason="TEST", source="unit")

    result = service.revoke_exp(user.id, 20, reason="TEST_CANCEL", source="unit")

    assert result.exp_gained == -20
    assert result.level_before == 1
    assert result.level_after == 1
    assert result.leveled_up is False
    assert result.profile.total_exp == 30
    logs = list(
        db_session.scalars(
            select(CharacterGrowthLog)
            .where(CharacterGrowthLog.user_id == user.id)
            .order_by(CharacterGrowthLog.id)
        )
    )
    assert len(logs) == 2
    assert logs[1].exp_gained == -20
    assert logs[1].before_total_exp == 50
    assert logs[1].after_total_exp == 30


def test_revoke_exp_does_not_go_below_zero(db_session: Session) -> None:
    user = _create_user(db_session)
    service = CharacterService(CharacterRepository(db_session))
    service.gain_exp(user.id, 10, reason="TEST", source="unit")

    result = service.revoke_exp(user.id, 999, reason="TEST_CANCEL", source="unit")

    assert result.profile.total_exp == 0
    assert result.exp_gained == -10


def test_revoke_exp_can_decrease_level(db_session: Session) -> None:
    user = _create_user(db_session)
    service = CharacterService(CharacterRepository(db_session))
    amount = policy.cumulative_exp_before_level(5) + 37
    service.gain_exp(user.id, amount, reason="TEST", source="unit")

    result = service.revoke_exp(user.id, amount, reason="TEST_CANCEL", source="unit")

    assert result.level_before == 5
    assert result.level_after == 1
    assert result.profile.total_exp == 0


def test_gain_mock_mission_exp_uses_mission_reward_and_unlocks(db_session: Session) -> None:
    user = _create_user(db_session)
    service = CharacterService(CharacterRepository(db_session))

    result = service.gain_mock_mission_exp(user.id, mission_type="exercise", mission_id=7)

    assert result.exp_gained == 20
    assert [animal.animal_code for animal in result.profile.owned_animals] == ["frog"]
    log = db_session.scalar(select(CharacterGrowthLog).where(CharacterGrowthLog.user_id == user.id))
    assert log is not None
    assert log.reason == "MISSION_COMPLETED"
    assert log.source == "mock_mission"
    assert log.source_id == "7"
