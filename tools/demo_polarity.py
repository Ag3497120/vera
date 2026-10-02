"""Small constructed demo for semantic polarity wiring; no corpus is read."""
from verantyx import polarity
from verantyx.polarity import InferredNegation, ObservedNegation
from verantyx.semantic_polarity import (
    ANSWER,
    POLARITY_UNDECIDED,
    UNKNOWN_NO_EVIDENCE,
    PolarityAnswer,
    answer_antonym,
    answer_negation,
)


checks = 0


def check(condition):
    global checks
    assert condition
    checks += 1


def main():
    observed_docs = {"observed-note": "水が流れない。"}
    observed = answer_negation(observed_docs, "流れる")
    check(isinstance(observed, PolarityAnswer))
    check(observed.status == ANSWER)
    check(observed.value is True)
    check(len(observed.evidence) == 1)
    witness = observed.evidence[0].observation
    check(witness is not None)
    check(isinstance(witness.observation, ObservedNegation))
    check(observed_docs[witness.span.source][witness.span.start:witness.span.end]
          == witness.observation.surface)

    absent = answer_negation({"other-note": "空が青い。"}, "流れる")
    check(absent.status == UNKNOWN_NO_EVIDENCE)
    check(absent.value is None)
    check(isinstance(absent.inferred, InferredNegation))
    check(absent.inferred.reason == "absence_is_not_negation")

    lexical = polarity.observe_negation("この映画はつまらない。")
    check(lexical.verdict == polarity.POLARITY_POSITIVE)
    check(lexical.observed == ())

    undecided = answer_negation(
        {"modal-note": "彼が来ないとは言えない。"}, "来る")
    check(undecided.status == POLARITY_UNDECIDED)
    check(undecided.value is None)
    check(undecided.refusal is not None)
    check(undecided.refusal.code == POLARITY_UNDECIDED)

    antonym = answer_antonym(
        {"road-note": "道は安全です。"}, "道", "危険")
    check(antonym.status == ANSWER)
    check(antonym.value is False)
    check(antonym.evidence[0].aspect == "安全")
    check(antonym.evidence[0].clause_span.text == "道は安全です。")

    print("DEMO OK")


if __name__ == "__main__":
    main()
