"""Reusable Stateful Pagination Component for DeRule Industrial Dashboard.

Follows DeRule Usability & Performance Architecture:
- Slices datasets in-memory before rendering to prevent massive DOM bloat
- Stateful: maintains current page per view in st.session_state with unique keys
- Standard controls: [ First ] [ Previous ] Page X of Y [ Next ] [ Last ]
- Status indicator: Showing start–end of total records
- Disabled boundary button states
- Zero emojis and clean industrial styling matching DeRule theme variables
"""

from __future__ import annotations

import math
from typing import Any, List, Optional, Tuple, TypeVar
import streamlit as st

T = TypeVar("T")


def get_paginated_slice(
    items: List[T],
    page_size: int,
    state_key: str,
) -> Tuple[List[T], int, int, int, int, int]:
    """Calculate pagination bounds, clamp page state, and slice items.

    Returns:
        (page_items, current_page, total_pages, total_records, start_idx, end_idx)
    """
    total_records = len(items) if items is not None else 0
    safe_page_size = max(1, page_size)
    total_pages = max(1, math.ceil(total_records / safe_page_size)) if total_records > 0 else 1

    current_page = st.session_state.get(state_key, 1)
    if not isinstance(current_page, int) or current_page < 1:
        current_page = 1
    if current_page > total_pages:
        current_page = total_pages

    st.session_state[state_key] = current_page

    start_idx = (current_page - 1) * safe_page_size
    end_idx = min(start_idx + safe_page_size, total_records)
    page_items = items[start_idx:end_idx] if total_records > 0 else []

    return page_items, current_page, total_pages, total_records, start_idx, end_idx


def render_pagination_controls(
    state_key: str,
    current_page: int,
    total_pages: int,
    total_records: int,
    start_idx: int,
    end_idx: int,
    item_label: str = "records",
) -> None:
    """Render compact, accessible pagination toolbar."""
    if total_records == 0:
        st.markdown(
            f"<div style='font-size: 11px; color: var(--text-muted); padding: 4px 0;'>No {item_label} to display.</div>",
            unsafe_allow_html=True,
        )
        return

    if total_pages <= 1:
        st.markdown(
            f"<div style='font-size: 11px; color: var(--text-muted); padding: 4px 0;'>Showing <b>{total_records}</b> of <b>{total_records}</b> {item_label}</div>",
            unsafe_allow_html=True,
        )
        return

    col_info, col_nav = st.columns([2, 3])

    with col_info:
        st.markdown(
            f"<div style='font-size: 11px; color: var(--text-secondary); padding-top: 6px;'>"
            f"Showing <b>{start_idx + 1}–{end_idx}</b> of <b>{total_records}</b> {item_label}"
            f"</div>",
            unsafe_allow_html=True,
        )

    with col_nav:
        c_first, c_prev, c_ind, c_next, c_last = st.columns([1, 1.2, 1.8, 1.2, 1])

        with c_first:
            if st.button("First", key=f"{state_key}_first", disabled=(current_page <= 1), use_container_width=True):
                st.session_state[state_key] = 1
                st.rerun()

        with c_prev:
            if st.button("Prev", key=f"{state_key}_prev", disabled=(current_page <= 1), use_container_width=True):
                st.session_state[state_key] = max(1, current_page - 1)
                st.rerun()

        with c_ind:
            st.markdown(
                f"<div style='text-align: center; font-size: 11px; font-weight: 600; color: var(--text-muted); padding-top: 6px; white-space: nowrap;'>"
                f"Page {current_page} of {total_pages}"
                f"</div>",
                unsafe_allow_html=True,
            )

        with c_next:
            if st.button("Next", key=f"{state_key}_next", disabled=(current_page >= total_pages), use_container_width=True):
                st.session_state[state_key] = min(total_pages, current_page + 1)
                st.rerun()

        with c_last:
            if st.button("Last", key=f"{state_key}_last", disabled=(current_page >= total_pages), use_container_width=True):
                st.session_state[state_key] = total_pages
                st.rerun()


def paginate_items(
    items: List[T],
    page_size: int,
    state_key: str,
    item_label: str = "records",
    render_controls: bool = True,
) -> Tuple[List[T], int, int]:
    """Slice items and optionally render controls at call site.

    Returns:
        (page_items, current_page, total_pages)
    """
    page_items, current_page, total_pages, total_records, start_idx, end_idx = get_paginated_slice(
        items=items,
        page_size=page_size,
        state_key=state_key,
    )

    if render_controls:
        render_pagination_controls(
            state_key=state_key,
            current_page=current_page,
            total_pages=total_pages,
            total_records=total_records,
            start_idx=start_idx,
            end_idx=end_idx,
            item_label=item_label,
        )

    return page_items, current_page, total_pages


def reset_pagination(state_key: str) -> None:
    """Reset specified pagination state to page 1."""
    st.session_state[state_key] = 1
