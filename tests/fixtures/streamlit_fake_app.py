"""Offline Streamlit entry point used only by AppTest."""

from grounded_travel_planner.ui.streamlit_app import main
from tests.test_streamlit_ui import FakeService, FakeVisualService

main(FakeService(), FakeVisualService())
