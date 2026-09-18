from pathlib import Path

from playwright.sync_api import sync_playwright


FRONTEND = Path(r"D:\AI_Project\What_Want\platform\frontend\index.html")


def test_step4_browser_shows_book_aligned_pyramid_and_reasoning():
    output = {
        "ranked": [
            {"value": "安稳从容", "locked": False},
            {"value": "自我实现", "locked": False},
        ],
        "support_links": [{
            "from_value": "安稳从容",
            "to_value": "自我实现",
            "reason": "内在安稳减少彷徨，使人更能持续投入成长。",
        }],
        "final_purpose": {
            "value": "自我实现",
            "life_state": "持续成长并活出自己的可能性",
            "reason": "其他主题为持续成长提供基础。",
        },
        "gap_note": "可以继续确认亲密关系是否构成独立主题。",
    }
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(FRONTEND.as_uri())
        page.wait_for_load_state("networkidle")
        page.evaluate(
            """({output}) => {
                const step = {step_id: 'step-4'};
                const run = {status: 'saved', parsed_output: JSON.stringify(output)};
                document.body.innerHTML = ch04Step4Html(step, run);
            }""",
            {"output": output},
        )

        pyramid = page.locator("[data-ch04-pyramid]")
        assert pyramid.count() == 1
        assert pyramid.locator(".ch04-pyramid-axis.top", has_text="最终目的").count() == 1
        assert pyramid.locator(".ch04-pyramid-axis.bottom", has_text="基础").count() == 1
        levels = pyramid.locator("[data-ch04-pyramid-level]")
        assert levels.count() == 2
        assert levels.nth(0).get_attribute("data-value") == "自我实现"
        assert levels.nth(1).get_attribute("data-value") == "安稳从容"
        assert page.get_by_text("持续成长并活出自己的可能性", exact=True).count() == 1
        assert page.locator(".ch04-support-link", has_text="内在安稳减少彷徨，使人更能持续投入成长。").count() == 1
        assert page.locator(".ch04-note", has_text="可以继续确认亲密关系是否构成独立主题。").count() == 1
        assert page.locator(".ch04-ranked-item input").count() == 0
        assert page.locator(".ch04-ranked-item .ch04-icon-btn").count() == 0
        assert page.get_by_role("button", name="返回步骤2调整核心价值观").count() == 1
        browser.close()


def test_step4_browser_marks_reasoning_stale_after_manual_reorder():
    output = {
        "ranked": [
            {"value": "安稳从容", "locked": False},
            {"value": "自我实现", "locked": False},
        ],
        "support_links": [],
        "final_purpose": {},
        "gap_note": "",
        "basis_stale": True,
    }
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(FRONTEND.as_uri())
        page.wait_for_load_state("networkidle")
        page.evaluate(
            """({output}) => {
                const step = {step_id: 'step-4'};
                const run = {status: 'saved', parsed_output: JSON.stringify(output)};
                document.body.innerHTML = ch04Step4Html(step, run);
            }""",
            {"output": output},
        )

        assert page.get_by_text("排序已调整，原依据不再对应当前顺序。请重新运行 LLM 更新依据。", exact=True).count() == 1
        assert page.get_by_role("button", name="提交").is_disabled()
        browser.close()


def test_step4_browser_renders_legacy_saved_result_without_hiding_theme_names():
    output = {
        "ranked": [
            {"theme": "安稳从容", "values": ["简单", "闲适"]},
            {"theme": "自我实现", "values": ["热爱", "成长"]},
        ],
        "support_links": [{
            "from": "安稳从容",
            "to": "自我实现",
            "how_supports": "安稳的生活节奏为持续成长提供空间。",
        }],
        "final_purpose": {
            "description": "持续成长并活出完整的自己。",
            "why_others_serve_it": "其他主题构成实现这一目的的基础。",
        },
        "gap_note": "当前主题已经形成完整链条。",
    }
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(FRONTEND.as_uri())
        page.wait_for_load_state("networkidle")
        page.evaluate(
            """({output}) => {
                const step = {step_id: 'step-4'};
                const run = {status: 'saved', parsed_output: JSON.stringify(output)};
                document.body.innerHTML = ch04Step4Html(step, run);
            }""",
            {"output": output},
        )

        levels = page.locator("[data-ch04-pyramid-level]")
        assert levels.count() == 2
        assert levels.nth(0).get_attribute("data-value") == "自我实现"
        assert levels.nth(1).get_attribute("data-value") == "安稳从容"
        assert page.get_by_text("人生最终目的 · 自我实现", exact=True).count() == 1
        assert page.get_by_text("持续成长并活出完整的自己。", exact=True).count() == 1
        assert page.locator(".ch04-support-link", has_text="安稳的生活节奏为持续成长提供空间。").count() == 1
        browser.close()


def test_step4_browser_gives_each_level_a_distinct_visual_treatment():
    output = {
        "ranked": [
            {"value": "安稳从容", "locked": False},
            {"value": "亲密联结", "locked": False},
            {"value": "仁厚担当", "locked": False},
            {"value": "自我实现", "locked": False},
        ],
        "support_links": [],
        "final_purpose": {"value": "自我实现", "life_state": "活出完整的自己", "reason": "其他主题提供支撑。"},
        "gap_note": "",
    }
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 390, "height": 900})
        page.goto(FRONTEND.as_uri())
        page.wait_for_load_state("networkidle")
        page.evaluate(
            """({output}) => {
                const step = {step_id: 'step-4'};
                const run = {status: 'saved', parsed_output: JSON.stringify(output)};
                document.body.innerHTML = ch04Step4Html(step, run);
            }""",
            {"output": output},
        )

        levels = page.locator("[data-ch04-pyramid-level]")
        assert levels.count() == 4
        assert levels.nth(0).get_attribute("class").find("level-3") >= 0
        assert levels.nth(1).get_attribute("class").find("level-2") >= 0
        assert levels.nth(2).get_attribute("class").find("level-1") >= 0
        assert levels.nth(3).get_attribute("class").find("level-0") >= 0
        assert page.locator(".ch04-level-actions").count() == 4
        assert page.locator(".ch04-level-actions button").count() >= 8
        for index in range(4):
            assert levels.nth(index).locator(".value").evaluate("el => getComputedStyle(el).writingMode") == "horizontal-tb"
        colors = [levels.nth(index).evaluate("el => getComputedStyle(el).backgroundColor") for index in range(4)]
        assert len(set(colors)) == 4
        browser.close()
