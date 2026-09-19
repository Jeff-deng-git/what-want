"""Question bank API: list, get, answer save/read (via book_notes)."""
import pytest
import pytest_asyncio
from pathlib import Path


@pytest_asyncio.fixture
async def seeded_client(client):
    """Base client + questions seeded into its tmp DB."""
    from seed_questions import QUESTIONS_MD, seed
    if not QUESTIONS_MD.exists():
        pytest.skip("问题清单.md 未提供（书籍原文不随仓库发布）")
    seed()
    return client


@pytest.mark.asyncio
async def test_questions_list_has_categories(seeded_client):
    client = seeded_client
    r = await client.get("/api/questions")
    assert r.status_code == 200
    body = r.json()
    assert len(body) == 90  # 3 × 30 (parser must not drop last per category)
    cats = {q["category"] for q in body}
    assert {"价值观", "才能", "热情"} <= cats
    # q_order sequential, no pollution
    assert body[0]["q_order"] == 1
    assert not any(s.startswith("|") for q in body for s in q["sub_questions"])


def test_parser_keeps_all_90():
    """Unit: parser keeps last question per category, filters 100-example tables."""
    from seed_questions import parse_questions
    # 问题清单.md 由书籍原文提取，不随仓库发布；自备后放在仓库根 chapter_md/ 下。
    data_path = Path(__file__).resolve().parents[3] / "chapter_md" / "问题清单.md"
    if not data_path.exists():
        pytest.skip("问题清单.md 未提供（书籍原文不随仓库发布）")
    text = data_path.read_text(encoding="utf-8")
    qs = parse_questions(text)
    assert len(qs) == 90
    cats = {}
    for q in qs:
        cats[q["category"]] = cats.get(q["category"], 0) + 1
    assert cats == {"价值观": 30, "才能": 30, "热情": 30}
    assert not any(s.startswith("|") for q in qs for s in q["sub_questions"])


@pytest.mark.asyncio
async def test_questions_get_one(seeded_client):
    client = seeded_client
    r = await client.get("/api/questions/1")
    assert r.status_code == 200
    body = r.json()
    assert body["question"]
    assert isinstance(body["sub_questions"], list)


@pytest.mark.asyncio
async def test_questions_answer_roundtrip(seeded_client):
    client = seeded_client
    # No answer yet
    r = await client.get("/api/questions/1/answer")
    assert r.json()["answer"] is None

    r = await client.post("/api/questions/1/answer", json={"answer": "宫本大"})
    assert r.status_code == 200

    r = await client.get("/api/questions/1/answer")
    assert r.json()["answer"] == "宫本大"

    # Overwrite
    r = await client.post("/api/questions/1/answer", json={"answer": "改过的答案"})
    assert r.json()["updated"] is True
    r = await client.get("/api/questions/1/answer")
    assert r.json()["answer"] == "改过的答案"


@pytest.mark.asyncio
async def test_questions_answer_404(seeded_client):
    client = seeded_client
    r = await client.post("/api/questions/9999/answer", json={"answer": "x"})
    assert r.status_code == 404
