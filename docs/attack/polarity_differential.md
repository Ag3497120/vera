# Polarity differential attack

Scope: the typed Japanese `observe_negation` reader, using its raw-text path
with the tagger unavailable. The reference implementation in the test file is
independent and intentionally narrow: it covers isolated terminal forms with
unambiguous lemmas. No module implementation helpers are used to calculate
reference readings.

## Findings

| ID | Severity | Minimal repro | Expected | Observed |
|---|---|---|---|---|
| PD-01 | wrong-ANSWER | With no tagger, call `observe_negation("彼はしない。", tokens=())` twice. | A sentence-final written negation; verdict `negative`, with an `ending` observation for lemma `する`. | Both calls return verdict `positive` and no observations. |

The test keeps PD-01 visible as a non-strict xfail. The raw fallback stem scan
includes the preceding topic particle and subject when it tries to find the
verb lemma, so the attested `する` form is lost. This reports a polarity
classification error, not an inferred negative claim.

## What held

- The independent reference and implementation agreed on paired positive and
  negative isolated forms for `する`, `いる`, `できる`, and `来る`.
- A sentence-final copula negation produced the dictionary-form observation
  `である`.
- The checks held for lexicalized `ない` adjectives, undecided modality,
  even-parity double negation, embedded negation, noun-plus-`ない` context,
  and trailing sentence-final material.
- The no-tagger fallback did not invent an observation for an unrecognized
  lemma. An inferred negation was rejected by `polarity_key`, while an
  observed negation was accepted.
- The acceptance command completed with **15 passed, 1 xfailed**. The xfail is
  PD-01 and is the deliberately retained reproduction.

## Not covered

- Fugashi tokenization and its dictionary-backed lemma decisions.
- A positive prefix-negation reading with an attesting lattice; only the
  no-lattice abstention path was checked.
- The English antonym detector, polarity placement into `CrossStore`, and the
  contradiction gate.
- Broad Japanese morphology, subject attachment across varied sentence
  structures, or corpus-level precision and recall.
