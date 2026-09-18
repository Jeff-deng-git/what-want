import json

from app.services.compaction import PROFILE_FIELDS, compact_profile, serialize_profile


def test_compact_profile_handles_missing_and_malformed_outputs():
    profile = compact_profile([None, "bad", {"likes": ["writing"], "unknown": "ignored"}], current_chapter="ch01")
    assert profile["likes"] == ["writing"]
    assert profile["current_chapter"] == "ch01"
    assert profile["open_questions"] == []
    assert "unknown" not in profile


def test_compact_profile_keeps_only_contract_fields():
    profile = compact_profile([{"values": ["autonomy"], "formula": "make things", "ranked": [1, 2]}])
    assert set(profile) <= set(PROFILE_FIELDS)


def test_compact_profile_maps_top_values_to_cross_chapter_values():
    profile = compact_profile([{"top_values": ["autonomy", "craft"]}], current_chapter="ch04")
    assert profile["values"] == ["autonomy", "craft"]
    assert "top_values" not in profile


def test_compact_profile_keeps_prior_chapter_fields_when_merging():
    profile = compact_profile(
        [
            {"misconceptions_cleared": ["1"], "external_voices": {"1": "family"}},
            {"internal_external_ratio": {"internal": 70, "external": 30}},
        ],
        current_chapter="ch02",
    )
    assert profile["misconceptions_cleared"] == ["1"]
    assert profile["external_voices"] == {"1": "family"}
    assert profile["internal_external_ratio"]["internal"] == 70


def test_serialize_profile_respects_budget():
    serialized = serialize_profile({"open_questions": "x" * 10000}, max_tokens=10)
    assert len(serialized) <= 40
    json.loads(serialized)
