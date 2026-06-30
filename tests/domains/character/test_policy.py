from app.domains.character import policy


def test_exp_required_for_level_is_non_linear() -> None:
    first = policy.exp_required_for_level(1)
    second = policy.exp_required_for_level(2)
    third = policy.exp_required_for_level(3)

    assert first > 0
    assert second > first
    assert third - second > second - first


def test_animal_catalog_entries_include_exact_mock_values_and_order() -> None:
    entries = policy.animal_catalog_entries()

    assert [entry.animal_code for entry in entries] == [
        "frog",
        "chick",
        "penguin",
        "dog",
        "cat",
        "tiger",
        "panda",
        "monkey",
    ]
    assert {entry.animal_code: entry.required_total_exp for entry in entries} == {
        "frog": 0,
        "chick": 235,
        "penguin": 663,
        "dog": 1443,
        "cat": 3968,
        "tiger": 10181,
        "panda": 25469,
        "monkey": 85268,
    }


def test_unlocked_animals_for_level_is_cumulative() -> None:
    animals = policy.unlocked_animals_for_level(5)
    assert [a.code for a in animals] == ["frog", "chick", "penguin"]


def test_level_for_total_exp_handles_multiple_level_ups() -> None:
    total = policy.exp_required_for_level(1) + policy.exp_required_for_level(2)
    assert policy.level_for_total_exp(total) == 3
    assert policy.current_exp_for_level(total, 3) == 0
