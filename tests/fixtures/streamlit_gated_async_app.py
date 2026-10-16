"""Offline Streamlit app with a deliberately delayed planning service."""

from grounded_travel_planner.ui.streamlit_app import main
from tests.test_async_streamlit_ui import GATED_SERVICE, FakeVisualService

main(GATED_SERVICE, FakeVisualService())
