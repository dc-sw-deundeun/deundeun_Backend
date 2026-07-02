"""Mock character growth policy.

수치는 제품 확정 전 임시 정책입니다. 실제 밸런싱 값이 정해지면 이 파일만 교체할 수 있게
서비스/라우터와 분리합니다.
"""

from dataclasses import dataclass
from math import floor

BASE_EXP_REQUIREMENT = 100
EXP_GROWTH_RATE = 1.35
MAX_SUPPORTED_LEVEL = 200
INITIAL_LEVEL = 1
INITIAL_TOTAL_EXP = 0


@dataclass(frozen=True)
class AnimalUnlock:
    code: str
    name: str
    unlock_level: int


@dataclass(frozen=True)
class AnimalCatalogEntry:
    animal_code: str
    name: str
    unlock_level: int
    required_total_exp: int


ANIMAL_UNLOCKS: tuple[AnimalUnlock, ...] = (
    AnimalUnlock(code="frog", name="개구리", unlock_level=1),
    AnimalUnlock(code="chick", name="병아리", unlock_level=3),
    AnimalUnlock(code="penguin", name="펭귄", unlock_level=5),
    AnimalUnlock(code="dog", name="강아지", unlock_level=7),
    AnimalUnlock(code="cat", name="고양이", unlock_level=10),
    AnimalUnlock(code="tiger", name="호랑이", unlock_level=13),
    AnimalUnlock(code="panda", name="판다", unlock_level=16),
    AnimalUnlock(code="monkey", name="원숭이", unlock_level=20),
)
INITIAL_ANIMAL_CODE = ANIMAL_UNLOCKS[0].code


def exp_required_for_level(level: int) -> int:
    """현재 level에서 다음 level로 가기 위해 필요한 mock EXP."""
    normalized = max(INITIAL_LEVEL, level)
    return max(1, floor(BASE_EXP_REQUIREMENT * (EXP_GROWTH_RATE ** (normalized - 1))))


def cumulative_exp_before_level(level: int) -> int:
    """해당 level에 도달하기 전까지 필요한 총 누적 EXP."""
    normalized = max(INITIAL_LEVEL, level)
    return sum(exp_required_for_level(lv) for lv in range(INITIAL_LEVEL, normalized))


def level_for_total_exp(total_exp: int) -> int:
    """누적 EXP 기준 level 계산. 여러 level을 한 번에 넘는 경우도 처리합니다."""
    remaining = max(INITIAL_TOTAL_EXP, total_exp)
    level = INITIAL_LEVEL
    while level < MAX_SUPPORTED_LEVEL:
        required = exp_required_for_level(level)
        if remaining < required:
            break
        remaining -= required
        level += 1
    return level


def current_exp_for_level(total_exp: int, level: int) -> int:
    return max(0, total_exp - cumulative_exp_before_level(level))


def progress_ratio(total_exp: int, level: int) -> float:
    required = exp_required_for_level(level)
    return min(1.0, current_exp_for_level(total_exp, level) / required)


def unlocked_animals_for_level(level: int) -> list[AnimalUnlock]:
    normalized = max(INITIAL_LEVEL, level)
    return [animal for animal in ANIMAL_UNLOCKS if animal.unlock_level <= normalized]


def animal_catalog_entries() -> list[AnimalCatalogEntry]:
    return [
        AnimalCatalogEntry(
            animal_code=animal.code,
            name=animal.name,
            unlock_level=animal.unlock_level,
            required_total_exp=cumulative_exp_before_level(animal.unlock_level),
        )
        for animal in ANIMAL_UNLOCKS
    ]


def animal_order_index() -> dict[str, int]:
    return {animal.code: index for index, animal in enumerate(ANIMAL_UNLOCKS)}


def animal_name_by_code() -> dict[str, str]:
    return {animal.code: animal.name for animal in ANIMAL_UNLOCKS}
