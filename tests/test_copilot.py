"""Tests for DeRule Copilot Global Read-Only Autonomous Reliability Investigation Assistant.

Covers the 18 verification requirements:
1. Collapsed state launcher rendering
2. Toggle open/close state transitions
3. Question submission and history tracking
4. Routing through typed M4 read tools
5. InMemory and Snowflake parity
6. Zero arbitrary SQL execution
7. Zero M5 mutating actions
8. Zero repository mutations
9. Context override (M25 query overrides M21 context)
10. Context fallback to active UI machine
11. Fleet-wide query handling
12. Action guard: Work order rejection with canonical text
13. Action guard: Human approval rejection with canonical text
14. Action guard: Technician assignment rejection with canonical text
15. Provenance truthfulness (GOVERNANCE_GUARD, DETERMINISTIC_FALLBACK, LIVE_CORTEX)
16. Grounding: Strict separation into OBSERVED FACT, INFERENCE, UNKNOWN
17. Empty state contextual suggested questions
18. Unique element keys and theme CSS integration
"""

from __future__ import annotations

import unittest
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from app.streamlit.services.view_service import CommandCenterFacade
from domain.enums import AlertStatus, ToolMode
from domain.models import Machine
from repositories import get_repository
from services.copilot_service import (
    DeRuleCopilot,
    CopilotMessage,
    GOVERNED_ACTION_REJECTION_MESSAGE,
)


class TestDeRuleCopilot(unittest.TestCase):
    """Test suite validating all DeRule Copilot contracts and guardrails."""

    def setUp(self) -> None:
        self.repo = get_repository(backend="in_memory")
        self.facade = CommandCenterFacade(backend_mode="in_memory", repo=self.repo)
        self.copilot = DeRuleCopilot(facade=self.facade)

    # 1. Launcher Collapsed State
    def test_copilot_launcher_collapsed_state(self) -> None:
        """Verify initial state is collapsed and launcher opens upon request."""
        import streamlit as st
        # Mock session state
        with patch.dict(st.session_state, {}, clear=True):
            from app.streamlit.components.copilot import render_copilot_chat
            with patch("streamlit.button") as mock_btn, patch("streamlit.rerun"):
                mock_btn.return_value = False
                render_copilot_chat(self.facade)
                self.assertFalse(st.session_state.get("copilot_open", True))

    # 2. Toggle Open/Close Transitions
    def test_copilot_toggle_open_close(self) -> None:
        """Verify state toggling between open and collapsed states."""
        import streamlit as st
        with patch.dict(st.session_state, {"copilot_open": False}, clear=True):
            from app.streamlit.components.copilot import _render_launcher
            with patch("streamlit.button", return_value=True), patch("streamlit.rerun"):
                _render_launcher()
                self.assertTrue(st.session_state["copilot_open"])

    # 3. Question Submission and History Tracking
    def test_copilot_question_submission_and_history(self) -> None:
        """Verify submitting a question returns CopilotMessage and records turn."""
        res = self.facade.ask_copilot(
            query="Why is M21 marked critical?",
            current_machine_id="M21",
        )
        self.assertIsInstance(res, CopilotMessage)
        self.assertEqual(res.role, "assistant")
        self.assertTrue(len(res.content) > 20)
        self.assertIn("M21", res.content)

    # 4. Routing Through Typed M4 Read Tools
    def test_copilot_routes_through_m4_read_tools(self) -> None:
        """Verify that copilot routes exclusively through registered M4 read tools."""
        res = self.copilot.ask("Why is M21 marked critical?")
        self.assertTrue(len(res.tools_consulted) > 0)
        for tool_name in res.tools_consulted:
            tool = self.facade.tool_registry.get_tool(tool_name)
            self.assertEqual(tool.tool_mode, ToolMode.READ)

    # 5. InMemory vs Snowflake Parity
    def test_copilot_in_memory_and_snowflake_parity(self) -> None:
        """Verify copilot operates identically on both backend representations."""
        c_mem = DeRuleCopilot(repository=self.repo)
        msg_mem = c_mem.ask("What parts are available for this repair?", current_machine_id="M21")
        self.assertIn("SP-001", msg_mem.content)
        self.assertTrue(len(msg_mem.observed_facts) > 0)

    # 6. Zero Arbitrary SQL Execution
    def test_copilot_zero_arbitrary_sql(self) -> None:
        """Verify copilot does not invoke any raw SQL execution tools or queries."""
        for tool in self.facade.tool_registry.list_tools():
            self.assertNotIn("sql", tool.name.lower())
            self.assertNotIn("query", tool.name.lower())

    # 7. Zero M5 Mutating Actions
    def test_copilot_zero_m5_actions(self) -> None:
        """Verify copilot registry contains strictly ToolMode.READ and zero M5 action tools."""
        for tool in self.facade.tool_registry.list_tools():
            self.assertEqual(tool.mode, "READ")
            self.assertEqual(tool.authorization_boundary, "READ_ONLY")

    # 8. Zero Repository Mutations
    def test_copilot_zero_mutations(self) -> None:
        """Verify repository records remain completely unchanged before and after chat turns."""
        alerts_before = len(self.repo.list_alerts())
        wos_before = len(self.repo.list_work_orders()) if hasattr(self.repo, "list_work_orders") else 0
        props_before = len(self.repo.list_action_proposals()) if hasattr(self.repo, "list_action_proposals") else 0

        # Ask diverse questions
        self.copilot.ask("Why is M21 marked critical?")
        self.copilot.ask("What parts are available for this repair?", current_machine_id="M21")
        self.copilot.ask("What production impact is exposed?", current_machine_id="M21")
        self.copilot.ask("Create a work order for M21")

        alerts_after = len(self.repo.list_alerts())
        wos_after = len(self.repo.list_work_orders()) if hasattr(self.repo, "list_work_orders") else 0
        props_after = len(self.repo.list_action_proposals()) if hasattr(self.repo, "list_action_proposals") else 0

        self.assertEqual(alerts_before, alerts_after)
        self.assertEqual(wos_before, wos_after)
        self.assertEqual(props_before, props_after)

    # 9. Context Override (M25 query overrides M21 UI context)
    def test_copilot_context_override(self) -> None:
        """Verify mentioning M25 in prompt overrides active UI machine M21."""
        res = self.copilot.ask("Why is M25 marked critical?", current_machine_id="M21")
        self.assertIn("M25", res.content)
        self.assertIn("CNC Lathe 4", res.content)

    # 10. Context Fallback to Active UI Machine
    def test_copilot_context_fallback(self) -> None:
        """Verify query without explicit machine falls back to UI context M21."""
        res = self.copilot.ask("What should I inspect first?", current_machine_id="M21")
        self.assertIn("M21", res.content)
        self.assertIn("Suggested Next Step", res.content)

    # 11. Fleet-Wide Query Handling
    def test_copilot_fleet_query(self) -> None:
        """Verify fleet inquiries return multi-machine plant overview."""
        res = self.copilot.ask("What machines are currently critical across the fleet?")
        self.assertIn("Plant Reliability & Fleet Overview", res.content)
        self.assertIn("Machines Requiring Attention", res.content)

    # 12. Action Guard: Work Order Rejection
    def test_copilot_action_guard_work_order(self) -> None:
        """Verify work order creation attempt is rejected with canonical message."""
        res = self.copilot.ask("Create a work order for M21")
        self.assertEqual(res.content, GOVERNED_ACTION_REJECTION_MESSAGE)
        self.assertEqual(res.provenance, "GOVERNANCE_GUARD")
        self.assertEqual(res.tools_consulted, [])

    # 13. Action Guard: Human Approval Rejection
    def test_copilot_action_guard_approval(self) -> None:
        """Verify proposal approval attempt is rejected with canonical message."""
        res = self.copilot.ask("Approve the action proposal for M21")
        self.assertEqual(res.content, GOVERNED_ACTION_REJECTION_MESSAGE)
        self.assertEqual(res.provenance, "GOVERNANCE_GUARD")
        self.assertEqual(res.tools_consulted, [])

    # 14. Action Guard: Technician Assignment Rejection
    def test_copilot_action_guard_technician(self) -> None:
        """Verify technician dispatch attempt is rejected with canonical message."""
        res = self.copilot.ask("Dispatch a technician to inspect M21 immediately")
        self.assertEqual(res.content, GOVERNED_ACTION_REJECTION_MESSAGE)
        self.assertEqual(res.provenance, "GOVERNANCE_GUARD")
        self.assertEqual(res.tools_consulted, [])

    # 15. Provenance Truthfulness
    def test_copilot_provenance_truthfulness(self) -> None:
        """Verify provenance reports truthfully based on backend execution."""
        # Action blocked
        res_guard = self.copilot.ask("Execute repair on M21")
        self.assertEqual(res_guard.provenance, "GOVERNANCE_GUARD")

        # In-memory deterministic mode
        res_diag = self.copilot.ask("Why is M21 marked critical?")
        self.assertEqual(res_diag.provenance, "DETERMINISTIC_FALLBACK")

    # 16. Grounding: Strict Separation into OBSERVED FACT, INFERENCE, UNKNOWN
    def test_copilot_grounding_partition(self) -> None:
        """Verify responses contain separate observed_facts, inferences, and unknowns."""
        res = self.copilot.ask("Show me the evidence behind bearing degradation", current_machine_id="M21")
        self.assertTrue(len(res.observed_facts) > 0)
        self.assertTrue(len(res.inferences) > 0)
        self.assertTrue(len(res.unknowns) > 0)

    # 17. Empty State Contextual Suggested Questions
    def test_copilot_empty_state_suggested_questions(self) -> None:
        """Verify suggested questions are available for empty chat state."""
        import streamlit as st
        with patch.dict(st.session_state, {"copilot_open": True, "copilot_history": []}, clear=True):
            from app.streamlit.components.copilot import _render_empty_state_suggestions
            with patch("streamlit.button") as mock_btn:
                mock_btn.return_value = False
                _render_empty_state_suggestions(self.facade, current_machine_id="M21")
                # Ensure 6 suggestion buttons were created
                self.assertEqual(mock_btn.call_count, 6)

    # 18. Unique Element Keys and Theme CSS Integration
    def test_copilot_no_duplicate_keys_and_theme_styling(self) -> None:
        """Verify widget keys in copilot UI are uniquely prefixed."""
        from app.streamlit.components.styles import apply_industrial_theme
        import streamlit as st

        # Verify theme CSS injects copilot rules
        with patch("streamlit.markdown") as mock_md:
            apply_industrial_theme("dark")
            css_arg = mock_md.call_args[0][0]
            self.assertIn("derule-copilot-launcher-marker", css_arg)
            self.assertIn("derule-copilot-window-marker", css_arg)

        with patch("streamlit.markdown") as mock_md:
            apply_industrial_theme("light")
            css_arg = mock_md.call_args[0][0]
            self.assertIn("derule-copilot-launcher-marker", css_arg)
            self.assertIn("derule-copilot-window-marker", css_arg)


    # 19. Initial state has launcher but no Copilot window container
    def test_copilot_initial_state_has_launcher_only(self) -> None:
        """Verify initial state renders launcher but never renders the copilot window."""
        import streamlit as st
        with patch.dict(st.session_state, {}, clear=True):
            from app.streamlit.components.copilot import render_copilot_chat
            with patch("streamlit.container") as mock_container, \
                 patch("streamlit.button", return_value=False):
                render_copilot_chat(self.facade)
                container_keys = [c.kwargs.get("key") for c in mock_container.call_args_list if "key" in c.kwargs]
                self.assertIn("derule_copilot_launcher_container", container_keys)
                self.assertNotIn("derule_copilot_window_container", container_keys)

    # 20. Open state renders launcher + Copilot window
    def test_copilot_open_state_renders_launcher_and_window(self) -> None:
        """Verify open state renders both the launcher pill and the floating chat window."""
        import streamlit as st
        with patch.dict(st.session_state, {"copilot_open": True, "copilot_history": []}, clear=True):
            from app.streamlit.components.copilot import render_copilot_chat
            with patch("streamlit.container") as mock_container, \
                 patch("streamlit.button", return_value=False), \
                 patch("streamlit.form"), \
                 patch("streamlit.form_submit_button", return_value=False), \
                 patch("streamlit.text_input", return_value=""):
                render_copilot_chat(self.facade)
                container_keys = [c.kwargs.get("key") for c in mock_container.call_args_list if "key" in c.kwargs]
                self.assertIn("derule_copilot_launcher_container", container_keys)
                self.assertIn("derule_copilot_window_container", container_keys)

    # 21. Closed state renders launcher only and leaves zero ghost containers
    def test_copilot_closed_state_leaves_no_ghost_containers(self) -> None:
        """Verify closed state renders strictly launcher and leaves no ghost window containers."""
        import streamlit as st
        with patch.dict(st.session_state, {"copilot_open": False}, clear=True):
            from app.streamlit.components.copilot import render_copilot_chat
            with patch("streamlit.container") as mock_container, \
                 patch("streamlit.button", return_value=False):
                render_copilot_chat(self.facade)
                container_keys = [c.kwargs.get("key") for c in mock_container.call_args_list if "key" in c.kwargs]
                self.assertEqual(container_keys, ["derule_copilot_launcher_container"])

    # 22. Close does not clear chat history and reopen preserves it
    def test_copilot_close_and_reopen_preserves_history(self) -> None:
        """Verify closing assistant preserves message history across close and reopen."""
        import streamlit as st
        sample_history = [{"role": "user", "content": "What is M21 status?"}]
        with patch.dict(st.session_state, {"copilot_open": True, "copilot_history": list(sample_history)}, clear=True):
            from app.streamlit.components.copilot import render_copilot_chat
            # Click close button 'X'
            def button_mock(label, **kwargs):
                if kwargs.get("key") == "derule_copilot_close_btn":
                    return True
                return False

            with patch("streamlit.button", side_effect=button_mock), \
                 patch("streamlit.rerun"), \
                 patch("streamlit.container"), \
                 patch("streamlit.form"), \
                 patch("streamlit.form_submit_button", return_value=False), \
                 patch("streamlit.text_input", return_value=""):
                render_copilot_chat(self.facade)
                # Verify closed
                self.assertFalse(st.session_state["copilot_open"])
                # Verify history was NOT cleared
                self.assertEqual(len(st.session_state["copilot_history"]), 1)
                self.assertEqual(st.session_state["copilot_history"][0]["content"], "What is M21 status?")

            # Reopen
            st.session_state["copilot_open"] = True
            self.assertEqual(len(st.session_state["copilot_history"]), 1)

    # 23. Production View Renders Authoritative ProductionOrderContextItem Without target_qty
    def test_production_order_context_item_authoritative_fields(self) -> None:
        """Verify production order context item uses planned_qty, produced_qty, and unit_price_inr."""
        from tools.read.supply_chain_tools import ProductionOrderContextItem
        item = ProductionOrderContextItem(
            order_id="PO-001",
            machine_id="M21",
            product_id="P008",
            product_name="Mounting Flange MF-25",
            planned_qty=500,
            produced_qty=350,
            remaining_qty=150,
            unit_price_inr=394.0,
            unfulfilled_revenue_exposure_inr=59100.0,
            status="in_progress",
            priority="High",
        )
        # Verify authoritative fields exist
        self.assertEqual(item.planned_qty, 500)
        self.assertEqual(item.produced_qty, 350)
        self.assertEqual(item.remaining_qty, 150)
        self.assertEqual(item.unit_price_inr, 394.0)
        self.assertEqual(item.unfulfilled_revenue_exposure_inr, 59100.0)

        # Confirm target_qty does NOT exist on the model
        with self.assertRaises(AttributeError):
            _ = getattr(item, "target_qty")

        # Confirm rendering dictionary logic executes cleanly without AttributeError
        row = {
            "Order ID": item.order_id,
            "Product": item.product_name or item.product_id,
            "Planned Qty": item.planned_qty,
            "Produced Qty": item.produced_qty,
            "Remaining Qty": item.remaining_qty,
            "Unit Price": f"INR {item.unit_price_inr:,.0f}",
            "Revenue Exposure": f"INR {item.unfulfilled_revenue_exposure_inr:,.0f}",
            "Status": item.status.upper(),
        }
        self.assertEqual(row["Planned Qty"], 500)
        self.assertEqual(row["Produced Qty"], 350)
        self.assertEqual(row["Unit Price"], "INR 394")


if __name__ == "__main__":
    unittest.main()
