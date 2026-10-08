source /Users/motonisihikoudai/Projects/vera-impl/wt/W1-g-S/artifacts/w1-g/scripts/env.sh
mkdir -p $A/accept
cd $W
vtest -rf \
  "$W/tests/attack/test_semantic_unknown_choice_paraphrase.py::test_query_delimiters_and_line_breaks_stay_inside_the_json_string" \
  "$W/tests/attack/test_memory_revalidate_injection.py::test_matching_file_hash_keeps_only_the_grounded_value" \
  "$W/tests/attack/test_semantic_unknown_differential.py::test_source_word_counts_toward_projection_budget" \
  "$W/tests/attack/test_semantic_unknown_fabrication.py::test_budget_below_clause_and_role_work_floor_refuses" > $A/accept/H1.txt 2>&1
vtest -rf -v $W/tests/test_w1g_b03_choice_prompt.py $W/tests/test_w1g_b04_single_read.py $W/tests/test_w1g_b05_budget_words.py > $A/accept/H2.txt 2>&1
vtest -rf $W/tests/test_w1g_decision_a_unverified.py $W/tests/test_w1g_decision_bc_supersede.py > $A/accept/H3_new_tests.txt 2>&1
vtest -rf "$W/tests/attack/test_memory_merge_differential.py::test_canonical_order_and_exact_duplicate_removal" "$W/tests/test_memory_merge.py::test_mismatched_supersede_stays_nonoperative_after_serialize_and_reopen" > $A/accept/H3_C.txt 2>&1
vtest -rf \
  "$W/tests/attack/test_memory_merge_injection.py::test_instruction_payload_cannot_hide_a_dangling_supersession" \
  "$W/tests/attack/test_memory_merge_injection.py::test_instruction_text_does_not_make_a_supersession_cycle_valid" \
  "$W/tests/attack/test_memory_merge_limits.py::test_active_records_reject_dangling_supersession_reference" \
  "$W/tests/attack/test_verifier_agents_fabrication.py::test_run_verifiers_records_references_with_their_verifier_identities" > $A/accept/H3_B_A_not_met.txt 2>&1
vpy -c "from verantyx.memory_merge import merge_report, MergeReport, SupersedeStatus; from verantyx.memory_frame import Memory; print(hasattr(Memory, 'supersede_accounting'))" > $A/accept/api.txt 2>&1
vpy -c "import verantyx.memory_merge as m; print(sorted(m.__all__))" >> $A/accept/api.txt 2>&1
vpy -c "import sys, verantyx.memory_frame, verantyx.memory_merge, verantyx.conductor, verantyx.semantic_unknown, verantyx.semantic_unknown_choice, verantyx.memory_revalidate; bad=[k for k,m in sys.modules.items() if k.startswith('verantyx') and getattr(m,'__file__',None) and not m.__file__.startswith('$W/')]; print('outside', bad)" > $A/provenance_after.txt
for f in H1 H2 H3_new_tests H3_C H3_B_A_not_met; do echo "$f: $(tail -1 $A/accept/$f.txt)"; done
cat $A/accept/api.txt $A/provenance_after.txt
