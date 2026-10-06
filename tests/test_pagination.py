"""Tests for Reusable Pagination Component and UI View Pagination Behavior.

Verifies the 12 critical pagination and layout requirements:
1. First page renders only configured page size.
2. Next page button advances to page 2 and renders expected items.
3. Previous page button returns to previous page.
4. First page button returns to page 1.
5. Last page button advances to final page.
6. Boundary disabling: Prev/First disabled on page 1; Next/Last disabled on last page.
7. Total page count calculation: ceil(N / page_size), handles empty list (1 page, 0 items).
8. Filter changes reset current page to 1.
9. Machine switch resets sub-entity paginations to page 1.
10. Separate views maintain separate pagination states (no cross-contamination).
11. Large dataset slices before rendering (verify slice length <= page_size, never renders all N items).
12. Single-page datasets (N <= page_size) render cleanly without unnecessary pagination controls.
"""

from __future__ import annotations

import math
import unittest
from unittest.mock import MagicMock, call, patch

import streamlit as st

from app.streamlit.components.pagination import (
    get_paginated_slice,
    paginate_items,
    render_pagination_controls,
    reset_pagination,
)


class TestPagination(unittest.TestCase):
    """Test suite validating pagination mechanics and layout controls."""

    def setUp(self) -> None:
        self.mock_session_state: dict[str, int | str] = {}

    # 1. First page renders only configured page size
    def test_first_page_renders_only_configured_page_size(self) -> None:
        """Requirement 1: Verify first page slice contains exactly page_size items."""
        items = list(range(100))
        page_size = 10
        state_key = "test_page_1"

        with patch.dict(st.session_state, self.mock_session_state, clear=True):
            page_items, current_page, total_pages, total_records, start_idx, end_idx = get_paginated_slice(
                items=items,
                page_size=page_size,
                state_key=state_key,
            )

            self.assertEqual(len(page_items), page_size)
            self.assertEqual(page_items, list(range(0, 10)))
            self.assertEqual(current_page, 1)
            self.assertEqual(total_pages, 10)
            self.assertEqual(total_records, 100)
            self.assertEqual(start_idx, 0)
            self.assertEqual(end_idx, 10)

    # 2. Next page advances correctly
    def test_next_page_advances_and_renders_expected_items(self) -> None:
        """Requirement 2: Next page renders items from the second page."""
        items = [f"item_{i}" for i in range(25)]
        page_size = 5
        state_key = "test_page_2"

        with patch.dict(st.session_state, {state_key: 2}, clear=True):
            page_items, current_page, total_pages, _, start_idx, end_idx = get_paginated_slice(
                items=items,
                page_size=page_size,
                state_key=state_key,
            )

            self.assertEqual(current_page, 2)
            self.assertEqual(len(page_items), 5)
            self.assertEqual(page_items, ["item_5", "item_6", "item_7", "item_8", "item_9"])
            self.assertEqual(start_idx, 5)
            self.assertEqual(end_idx, 10)
            self.assertEqual(total_pages, 5)

    # 3. Previous page returns to previous page
    def test_previous_page_returns_to_previous_page(self) -> None:
        """Requirement 3: Decrementing page renders previous page slice."""
        items = list(range(30))
        page_size = 10
        state_key = "test_page_3"

        with patch.dict(st.session_state, {state_key: 3}, clear=True):
            # Page 3
            items_p3, cur_p3, _, _, _, _ = get_paginated_slice(items, page_size, state_key)
            self.assertEqual(cur_p3, 3)
            self.assertEqual(items_p3, list(range(20, 30)))

            # Go to Page 2
            st.session_state[state_key] = 2
            items_p2, cur_p2, _, _, _, _ = get_paginated_slice(items, page_size, state_key)
            self.assertEqual(cur_p2, 2)
            self.assertEqual(items_p2, list(range(10, 20)))

    # 4. First page returns to page 1
    def test_first_page_returns_to_page_1(self) -> None:
        """Requirement 4: Setting page to 1 returns to first slice."""
        items = list(range(50))
        page_size = 10
        state_key = "test_page_4"

        with patch.dict(st.session_state, {state_key: 4}, clear=True):
            reset_pagination(state_key)
            page_items, cur_page, _, _, _, _ = get_paginated_slice(items, page_size, state_key)
            self.assertEqual(cur_page, 1)
            self.assertEqual(page_items, list(range(0, 10)))

    # 5. Last page advances to final page
    def test_last_page_advances_to_final_page(self) -> None:
        """Requirement 5: Navigating to last page yields remaining items."""
        items = list(range(23))  # 23 items with page_size=10 -> pages: 1..3 (last has 3 items)
        page_size = 10
        state_key = "test_page_5"

        with patch.dict(st.session_state, {state_key: 3}, clear=True):
            page_items, cur_page, total_pages, total_recs, start_idx, end_idx = get_paginated_slice(
                items, page_size, state_key
            )
            self.assertEqual(cur_page, 3)
            self.assertEqual(total_pages, 3)
            self.assertEqual(total_recs, 23)
            self.assertEqual(len(page_items), 3)
            self.assertEqual(page_items, [20, 21, 22])
            self.assertEqual(start_idx, 20)
            self.assertEqual(end_idx, 23)

    # 6. Boundary disabling: Prev/First disabled on page 1; Next/Last disabled on last page
    def test_boundary_button_disabling(self) -> None:
        """Requirement 6: Verify boundary button disabled flags."""
        with patch("streamlit.button") as mock_button, \
             patch("streamlit.columns") as mock_cols, \
             patch("streamlit.markdown"):
            
            mock_cols.side_effect = lambda spec: [MagicMock() for _ in range(len(spec) if isinstance(spec, (list, tuple)) else spec)]

            # Case A: On page 1 of 5
            render_pagination_controls(
                state_key="test_boundary",
                current_page=1,
                total_pages=5,
                total_records=50,
                start_idx=0,
                end_idx=10,
            )

            # Check calls for First, Prev, Next, Last
            btn_calls = {call[0][0]: call[1].get("disabled") for call in mock_button.call_args_list}
            self.assertTrue(btn_calls.get("First"), "First button must be disabled on page 1")
            self.assertTrue(btn_calls.get("Prev"), "Prev button must be disabled on page 1")
            self.assertFalse(btn_calls.get("Next"), "Next button must be enabled on page 1")
            self.assertFalse(btn_calls.get("Last"), "Last button must be enabled on page 1")

            mock_button.reset_mock()

            # Case B: On page 5 of 5
            render_pagination_controls(
                state_key="test_boundary",
                current_page=5,
                total_pages=5,
                total_records=50,
                start_idx=40,
                end_idx=50,
            )

            btn_calls_last = {call[0][0]: call[1].get("disabled") for call in mock_button.call_args_list}
            self.assertFalse(btn_calls_last.get("First"), "First button must be enabled on last page")
            self.assertFalse(btn_calls_last.get("Prev"), "Prev button must be enabled on last page")
            self.assertTrue(btn_calls_last.get("Next"), "Next button must be disabled on last page")
            self.assertTrue(btn_calls_last.get("Last"), "Last button must be disabled on last page")

    # 7. Total page count calculation handles empty lists and exact multiples
    def test_total_page_count_calculation(self) -> None:
        """Requirement 7: ceil(N / page_size), handles empty list (1 page, 0 items)."""
        state_key = "test_calc"

        with patch.dict(st.session_state, {}, clear=True):
            # Empty list
            items_empty, cur_p, tot_p, tot_r, _, _ = get_paginated_slice([], 10, state_key)
            self.assertEqual(items_empty, [])
            self.assertEqual(cur_p, 1)
            self.assertEqual(tot_p, 1)
            self.assertEqual(tot_r, 0)

            # Exact multiple: 50 items with page size 10 -> 5 pages
            _, _, tot_p50, _, _, _ = get_paginated_slice(list(range(50)), 10, state_key)
            self.assertEqual(tot_p50, 5)

            # Not exact multiple: 51 items with page size 10 -> 6 pages
            _, _, tot_p51, _, _, _ = get_paginated_slice(list(range(51)), 10, state_key)
            self.assertEqual(tot_p51, 6)

    # 8. Filter changes reset current page to 1
    def test_filter_changes_reset_pagination(self) -> None:
        """Requirement 8: Calling reset_pagination resets state to page 1."""
        state_key = "test_filter_key"
        with patch.dict(st.session_state, {state_key: 5}, clear=True):
            self.assertEqual(st.session_state[state_key], 5)
            reset_pagination(state_key)
            self.assertEqual(st.session_state[state_key], 1)

            # Verify subsequent slice starts at index 0
            items = list(range(100))
            page_items, cur_page, _, _, start_idx, _ = get_paginated_slice(items, 10, state_key)
            self.assertEqual(cur_page, 1)
            self.assertEqual(start_idx, 0)
            self.assertEqual(page_items, list(range(0, 10)))

    # 9. Machine switch resets sub-entity paginations
    def test_machine_switch_resets_sub_entity_pagination(self) -> None:
        """Requirement 9: Machine switch resets machine-scoped pagination keys."""
        # Key formatted with machine ID
        mach_a = "M21"
        mach_b = "M25"
        key_a = f"pagination_assets_prod_{mach_a}"
        key_b = f"pagination_assets_prod_{mach_b}"

        with patch.dict(st.session_state, {key_a: 3}, clear=True):
            # When switching to mach_b, key_b is not set yet, so defaults to 1
            items = list(range(20))
            page_items_b, cur_p_b, _, _, _, _ = get_paginated_slice(items, 5, key_b)
            self.assertEqual(cur_p_b, 1)
            self.assertEqual(page_items_b, [0, 1, 2, 3, 4])

            # Machine A's state was preserved independently or can be reset
            self.assertEqual(st.session_state.get(key_a), 3)
            reset_pagination(key_a)
            self.assertEqual(st.session_state.get(key_a), 1)

    # 10. Separate views maintain separate pagination states
    def test_separate_views_maintain_separate_states(self) -> None:
        """Requirement 10: State keys for different views do not cross-contaminate."""
        cc_fleet_key = "pagination_command_center_fleet_page"
        wo_key = "pagination_work_orders_page"
        maint_key = "pagination_maintenance_page"

        with patch.dict(st.session_state, {}, clear=True):
            items_cc = list(range(50))
            items_wo = list(range(30))
            items_maint = list(range(40))

            # Set cc to page 2
            st.session_state[cc_fleet_key] = 2
            # Set wo to page 3
            st.session_state[wo_key] = 3

            _, cur_cc, _, _, _, _ = get_paginated_slice(items_cc, 10, cc_fleet_key)
            _, cur_wo, _, _, _, _ = get_paginated_slice(items_wo, 10, wo_key)
            _, cur_maint, _, _, _, _ = get_paginated_slice(items_maint, 10, maint_key)

            self.assertEqual(cur_cc, 2)
            self.assertEqual(cur_wo, 3)
            self.assertEqual(cur_maint, 1)  # Default page 1, unaffected

    # 11. Large dataset slices before rendering
    def test_large_dataset_slices_before_rendering(self) -> None:
        """Requirement 11: 10,000 items slices into <= page_size items before rendering."""
        large_dataset = [f"sensor_record_{i}" for i in range(10_000)]
        page_size = 10
        state_key = "test_large_data"

        with patch.dict(st.session_state, {}, clear=True):
            page_items, cur_page, total_pages = paginate_items(
                items=large_dataset,
                page_size=page_size,
                state_key=state_key,
                render_controls=False,  # Don't mock streamlit controls for pure slice test
            )

            # Ensure we strictly sliced to 10 items, preventing DOM bloat
            self.assertEqual(len(page_items), 10)
            self.assertEqual(total_pages, 1000)
            self.assertEqual(cur_page, 1)
            self.assertEqual(page_items[0], "sensor_record_0")
            self.assertEqual(page_items[-1], "sensor_record_9")

    # 12. Single-page datasets render cleanly without unnecessary pagination controls
    def test_single_page_datasets_render_cleanly(self) -> None:
        """Requirement 12: Single page datasets (N <= page_size) render summary without nav buttons."""
        items = ["alert_1", "alert_2", "alert_3"]
        page_size = 10
        state_key = "test_single_page"

        with patch("streamlit.button") as mock_button, \
             patch("streamlit.markdown") as mock_markdown, \
             patch.dict(st.session_state, {}, clear=True):

            page_items, cur_page, total_pages = paginate_items(
                items=items,
                page_size=page_size,
                state_key=state_key,
                render_controls=True,
            )

            self.assertEqual(len(page_items), 3)
            self.assertEqual(total_pages, 1)
            self.assertEqual(cur_page, 1)

            # Buttons (First, Prev, Next, Last) should NOT be called for single-page datasets
            mock_button.assert_not_called()

            # Markdown was called to display showing count summary
            markdown_texts = [call[0][0] for call in mock_markdown.call_args_list]
            found_summary = any("Showing <b>3</b> of <b>3</b>" in txt for txt in markdown_texts)
            self.assertTrue(found_summary, "Summary showing 3 of 3 records should be rendered")


if __name__ == "__main__":
    unittest.main()
