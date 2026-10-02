source /Users/motonisihikoudai/Projects/vera-impl/wt/W1-g-S/artifacts/w1-g/scripts/env.sh
mkdir -p $A/targets $A/b04
(cd $W && vpy $A/b04/readcount.py) > $A/b04/readcount_before.txt 2>&1
for t in \
 "tests/attack/test_semantic_unknown_choice_paraphrase.py::test_query_delimiters_and_line_breaks_stay_inside_the_json_string" \
 "tests/attack/test_memory_revalidate_injection.py::test_matching_file_hash_keeps_only_the_grounded_value" \
 "tests/attack/test_semantic_unknown_differential.py::test_source_word_counts_toward_projection_budget" \
 "tests/attack/test_semantic_unknown_fabrication.py::test_budget_below_clause_and_role_work_floor_refuses" \
 "tests/attack/test_memory_merge_differential.py::test_canonical_order_and_exact_duplicate_removal" \
 "tests/test_memory_merge.py::test_mismatched_supersede_stays_nonoperative_after_serialize_and_reopen" \
 "tests/attack/test_memory_merge_injection.py::test_instruction_payload_cannot_hide_a_dangling_supersession" \
 "tests/attack/test_memory_merge_injection.py::test_instruction_text_does_not_make_a_supersession_cycle_valid" \
 "tests/attack/test_memory_merge_limits.py::test_active_records_reject_dangling_supersession_reference" \
 "tests/attack/test_verifier_agents_fabrication.py::test_run_verifiers_records_references_with_their_verifier_identities" ; do
 echo "## $t"; vtest "$W/$t" 2>&1 | tail -3; done > $A/targets/before.txt
