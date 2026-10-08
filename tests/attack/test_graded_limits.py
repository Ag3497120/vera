from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace

from verantyx.graded import GradedJudge, band_annotation


WHOLE = (("whole", {"rungs": (("whole", 0),), "grammar": "raw", "depth": 1}),)
MENTIONS = (("mentions", {"rungs": (("whole", 0),), "grammar": "raw"}),)


def store(crosses, labels=()):
    return SimpleNamespace(crosses=crosses, source_labels=set(labels))


def judge_for(terms, settings=WHOLE, data=None):
    return GradedJudge(settings, read=lambda _query: list(terms)).build(
        data if data is not None else store({})
    )


def test_unique_whole_core_is_typed_as_answer():
    judge = judge_for(["alpha"], data=store({"alpha": [], "beta": []}))

    result = judge.ask("alpha")

    assert result["verdict"] == "ANSWER"
    assert result["item"] == "alpha"
    assert result["readings"] == {"whole": "alpha"}


def test_empty_settings_refuse_without_division_or_crash():
    judge = judge_for(["alpha"], settings=())

    result = judge.ask("alpha")

    assert result["verdict"] == "UNKNOWN_NOT_PRESENT"
    assert result["agreeing"] == 0
    assert result["of"] == 0
    assert result["coverage"] == 0.0


def test_empty_and_content_free_queries_have_distinct_typed_refusals():
    judge = judge_for([], data=store({"alpha": []}))

    blank = judge.ask(" \t ")
    greeting = judge.ask("こんにちは")

    assert blank["verdict"] == "UNKNOWN_UNPARSED"
    assert greeting["verdict"] == "UNKNOWN_NO_SUBJECT"
    assert blank["terms"] == greeting["terms"] == []


def test_time_dependent_query_is_refused_before_any_setting_can_answer():
    judge = judge_for(["weather"], data=store({"weather": []}))

    result = judge.ask("current weather")

    assert result["verdict"] == "UNKNOWN_TIME_DEPENDENT"
    assert result["item"] is None
    assert result["deictic"] == "current"


def test_equal_ladder_scores_abstain():
    judge = judge_for(
        ["shared"],
        settings=MENTIONS,
        data=store({"alpha": ["shared"], "beta": ["shared"]}),
    )

    result = judge.ask("shared")

    assert result["verdict"] == "UNKNOWN_NOT_PRESENT"
    assert result["item"] is None
    assert result["agreeing"] == 0


def test_core_insertion_order_does_not_change_reading():
    forward = store({"alpha": ["facet-a"], "beta": ["facet-b"]})
    reverse = store({"beta": ["facet-b"], "alpha": ["facet-a"]})
    first = judge_for(["alpha"], data=forward).ask("alpha")
    second = judge_for(["alpha"], data=reverse).ask("alpha")

    assert first == second
    assert first["verdict"] == "ANSWER"
    assert first["item"] == "alpha"


def test_repeated_asks_and_rebuilds_are_idempotent():
    data = store({"alpha": ["facet"], "beta": []})
    judge = judge_for(["alpha"], data=data)
    expected = judge.ask("alpha")

    for _ in range(40):
        assert judge.ask("alpha") == expected
        assert judge.build(data).ask("alpha") == expected


def test_two_readers_can_ask_concurrently_without_cross_talk():
    data = store({"alpha": [], "beta": []})
    alpha = judge_for(["alpha"], data=data)
    beta = judge_for(["beta"], data=data)

    def repeat(judge, query, item):
        for _ in range(30):
            result = judge.ask(query)
            assert result["verdict"] == "ANSWER"
            assert result["item"] == item
        return True

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(
            lambda args: repeat(*args),
            ((alpha, "alpha", "alpha"), (beta, "beta", "beta")),
        ))

    assert outcomes == [True, True]


def test_thousands_of_unheld_terms_return_a_typed_refusal():
    terms = ["absent-%d" % i for i in range(4000)]
    judge = judge_for(terms, data=store({"held": []}))

    result = judge.ask("large input")

    assert result["verdict"] == "UNKNOWN_NOT_PRESENT"
    assert result["item"] is None
    assert len(result["missing"]) == len(terms)
    assert result["coverage"] == 0.0


def test_large_synthetic_store_builds_and_keeps_exact_core_answerable():
    crosses = {"subject-%d" % i: [] for i in range(1500)}
    judge = judge_for(["subject-1499"], data=store(crosses))

    result = judge.ask("selected subject")

    assert result["verdict"] == "ANSWER"
    assert result["item"] == "subject-1499"


def test_band_annotation_is_beside_the_reading_and_empty_for_no_subject():
    judge = judge_for(["alpha"], data=store({"alpha": []}))

    assert band_annotation(judge, "alpha") == {
        "agree": 1, "of": 1, "item": "alpha", "concord": 1.0,
    }
    assert band_annotation(judge_for([], data=store({"alpha": []})), "hi") is None


def test_repeated_distinct_queries_do_not_grow_judge_state():
    judge = judge_for(["alpha"], data=store({"alpha": [], "beta": []}))
    initial = (len(judge.ladders), len(judge.held), len(judge.cores))

    for i in range(200):
        judge.ask("query-%d" % i)

    assert (len(judge.ladders), len(judge.held), len(judge.cores)) == initial
