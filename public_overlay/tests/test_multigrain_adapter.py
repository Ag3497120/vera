"""Focused, self-authored fixtures for the multi-resolution source adapter.

These fixtures test candidate reach and routing/source preservation only. They
are not semantic accuracy or generalization evaluations.
"""
from __future__ import annotations

import unittest

from verantyx.base import Base
from verantyx import conduct_tree
from verantyx.cross_store import CrossStore
from verantyx.full_sovereign import FullConstellation
from verantyx.hierarchy import Node
from verantyx.multigrain_adapter import retrieve_multigrain_candidates


_SETTINGS = (
    ("whole", {"rungs": (("whole", 0),), "grammar": "raw", "depth": 1}),
    ("char3", {"rungs": (("g3", 3),), "grammar": "raw", "depth": 1}),
    ("char2", {"rungs": (("g2", 2),), "grammar": "raw", "depth": 1}),
    ("char1", {"rungs": (("g1", 1),), "grammar": "raw", "depth": 1}),
)


def _same_content_at_each_grain() -> FullConstellation:
    """One source leaf shared by whole/3/2/1-character resolution views."""
    source = CrossStore()
    source.add("東町避難所", ["東町の防災資料", "地域の避難拠点"])
    source.source_labels.add("防災案内資料")
    leaves = {"防災": {"source-leaf-a": source}}
    return FullConstellation().build(
        source,
        leaves,
        settings=_SETTINGS,
        with_tree=True,
    )


class MultiGrainAdapterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.constellation = _same_content_at_each_grain()

    def test_finer_existing_grains_reach_a_source_leaf_candidate(self) -> None:
        result = retrieve_multigrain_candidates(
            "東町避難支援所", self.constellation)

        self.assertEqual(result["resolution_item"], "東町避難所")
        self.assertEqual(result["resolution_verdict"], "ANSWER_BY_COARSENING")
        self.assertEqual(result["selected_candidate"], "東町避難所")
        trace = {row["member"]: row for row in result["grain_trace"]}
        self.assertIsNone(trace["whole"]["member_reading"])
        self.assertEqual(trace["char3"]["member_reading"], "東町避難所")
        self.assertEqual(trace["char2"]["member_reading"], "東町避難所")
        self.assertEqual(trace["char1"]["member_reading"], "東町避難所")
        self.assertTrue(trace["char3"]["used_by_existing_candidate_selection"])
        self.assertFalse(any(row["independent_source_vote"]
                             for row in result["grain_trace"]))

        candidate = next(row for row in result["candidates"]
                         if row["item"] == "東町避難所")
        self.assertEqual(candidate["resolution_views"], ["char1", "char2", "char3"])
        self.assertEqual(candidate["source_leaf_match_count"], 1)
        self.assertEqual(len(candidate["sources"]), 1)
        self.assertEqual(candidate["sources"][0]["leaf"], "source-leaf-a")
        self.assertEqual(candidate["sources"][0]["domain_path"], ["主権", "防災"])
        self.assertEqual(candidate["sources"][0]["identity_status"],
                         "identity_unverified")
        self.assertIsNone(candidate["independent_source_count"])
        self.assertEqual(result["source_identity_status"], "identity_unverified")
        self.assertIn("FullConstellation.ask(raw_question)",
                      result["trace"]["candidate_selection"])

    def test_shared_grain_views_do_not_multiply_source_references(self) -> None:
        result = retrieve_multigrain_candidates(
            "東町避難支援所", self.constellation)
        candidate = next(row for row in result["candidates"]
                         if row["item"] == "東町避難所")

        self.assertEqual(len(candidate["resolution_views"]), 3)
        self.assertEqual(len(candidate["sources"]), 1)
        self.assertIsNone(candidate["independent_source_count"])
        self.assertEqual(candidate["source_identity_status"], "identity_unverified")

    def test_same_display_label_on_separate_leaves_is_not_claimed_independent(self) -> None:
        tree = next(member.tree for member in self.constellation.members
                    if member.tree is not None)
        domain = tree.children["防災"]
        original_children = dict(domain.children)
        duplicate = CrossStore()
        duplicate.add("東町避難所", ["同じ候補を記載した別の小fixture"])
        duplicate.source_labels.add("防災案内資料")
        domain.children["source-leaf-b"] = Node(name="source-leaf-b", store=duplicate)
        try:
            result = retrieve_multigrain_candidates(
                "東町避難支援所", self.constellation)
        finally:
            domain.children = original_children

        candidate = next(row for row in result["candidates"]
                         if row["item"] == "東町避難所")
        self.assertEqual(candidate["source_leaf_match_count"], 2)
        self.assertEqual(len(candidate["sources"]), 2)
        self.assertEqual({row["source_label"] for row in candidate["sources"]},
                         {"防災案内資料"})
        self.assertEqual({row["identity_status"] for row in candidate["sources"]},
                         {"identity_unverified"})
        self.assertIsNone(candidate["independent_source_count"])

    def test_surface_route_tie_and_unknown_are_preserved(self) -> None:
        source_stores = {}
        for name, core in (
            ("left-leaf", "東京避難所"),
            ("right-leaf", "東京避難所"),
            ("unique-leaf", "北町避難所"),
        ):
            store = CrossStore()
            store.add(core, ["案内資料"])
            store.source_labels.add(name)
            source_stores[name] = store
        root = Node(name="主権", children={
            "北": Node(name="left-leaf", store=source_stores["left-leaf"]),
            "南": Node(name="right-leaf", store=source_stores["right-leaf"]),
            "固有": Node(name="unique-leaf", store=source_stores["unique-leaf"]),
        })
        router = Base()
        router.root = root
        router.routing_root = conduct_tree.build(
            {name: store.crosses for name, store in source_stores.items()},
            hierarchy=root,
        )

        routed = retrieve_multigrain_candidates(
            "北町避難所", self.constellation, source_router=router)
        self.assertEqual(routed["surface_route"]["verdict"], "ROUTED")
        self.assertEqual(routed["surface_route"]["selected_leaf"], "unique-leaf")
        self.assertTrue(routed["surface_route"]["trail"])
        self.assertEqual(routed["surface_route"]["via_api"],
                         ["Base.lower", "conduct_tree.descend", "surface.route"])

        tied = retrieve_multigrain_candidates(
            "東京避難所", self.constellation, source_router=router)
        self.assertEqual(tied["surface_route"]["route_kind"], "surface_conduction")
        self.assertEqual(tied["surface_route"]["verdict"], "UNKNOWN_NO_ROUTE")
        self.assertIn("two arms tied", tied["surface_route"].get("note", ""))
        self.assertIsNone(tied["surface_route"]["selected_leaf"])
        self.assertFalse(tied["surface_route"]["used_for_candidate_selection"])

        unknown = retrieve_multigrain_candidates(
            "龘龘未知語", self.constellation, source_router=router)
        self.assertEqual(unknown["resolution_verdict"], "UNKNOWN_NOT_PRESENT")
        self.assertEqual(unknown["surface_route"]["verdict"], "UNKNOWN_NO_ROUTE")
        self.assertIsNone(unknown["selected_candidate"])


if __name__ == "__main__":
    unittest.main()
