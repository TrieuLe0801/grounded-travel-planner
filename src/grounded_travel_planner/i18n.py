"""Small, code-owned presentation translations for the session language."""

from __future__ import annotations

from typing import Literal

Language = Literal["vi", "en"]

_TEXT: dict[str, dict[Language, str]] = {
    "missing_graph_response": {
        "vi": "Chưa nhận được phản hồi hợp lệ cho yêu cầu này.",
        "en": "The request did not return a valid response.",
    },
    "graph_failure": {
        "vi": "Chưa thể hoàn tất yêu cầu; lịch trình cũ đã được giữ nguyên.",
        "en": "The request could not be completed; the previous itinerary was preserved.",
    },
    "background_failure": {
        "vi": "Chưa thể hoàn tất yêu cầu; lịch trình trước đó vẫn được giữ nguyên.",
        "en": "The request could not be completed; the previous itinerary was preserved.",
    },
    "turn_pending": {
        "vi": "Một yêu cầu đang được xử lý.",
        "en": "A request is already being processed.",
    },
}


def localized(key: str, language: Language) -> str:
    return _TEXT[key][language]


def response_language_instruction(language: Language) -> str:
    return "Vietnamese" if language == "vi" else "English"


def localized_issue_message(code: str, message: str, language: Language) -> str:
    """Translate stable codes, while preserving dynamic evidence verbatim."""
    known: dict[str, dict[Language, str]] = {
        "candidate_required": {
            "vi": "Planner chưa tạo được lịch trình đề xuất.",
            "en": "The Planner did not produce a candidate itinerary.",
        },
        "missing_graph_response": _TEXT["missing_graph_response"],
        "bounded_graph_failure": _TEXT["graph_failure"],
        "background_turn_failure": {
            "vi": "Lượt xử lý nền chưa hoàn tất.",
            "en": "The background turn did not complete.",
        },
        "requested_change_not_applied": {
            "vi": "Lịch trình đề xuất chưa áp dụng đúng thay đổi được yêu cầu.",
            "en": "The candidate itinerary did not apply the requested change.",
        },
        "trip_request_required": {
            "vi": "Cần thông tin chuyến đi hợp lệ trước khi lập lịch.",
            "en": "A valid trip request is required before planning.",
        },
        "destination_required": {
            "vi": "Điểm đến hoặc địa điểm không được để trống.",
            "en": "Destination or place must not be blank.",
        },
        "day_count_out_of_range": {
            "vi": "Số ngày phải từ 1 đến 7.",
            "en": "Day count must be between 1 and 7.",
        },
        "candidate_request_mismatch": {
            "vi": "Lịch trình đề xuất không khớp điểm đến, ngày bắt đầu hoặc số ngày đã chọn.",
            "en": "The candidate does not preserve the selected destination, start date, and days.",
        },
        "trip_extension_target_required": {
            "vi": "Cần số ngày mục tiêu hoặc số ngày muốn thêm.",
            "en": "Trip extension needs a target day count or increment.",
        },
        "trip_extension_must_increase": {
            "vi": "Số ngày mới phải lớn hơn lịch trình hiện tại.",
            "en": "Trip extension must increase the current day count.",
        },
        "invalid_search_request": {
            "vi": "Yêu cầu tìm kiếm bị giới hạn không hợp lệ.",
            "en": "The bounded search request was invalid.",
        },
        "search_call_limit": {
            "vi": "Đã đạt giới hạn số lần tìm kiếm cho lượt này.",
            "en": "The search-call limit was reached for this turn.",
        },
        "coordinator_model_failure": {
            "vi": "Chưa thể hiểu yêu cầu này.",
            "en": "The request could not be understood.",
        },
        "planner_model_failure": {
            "vi": "Chưa thể tạo lịch trình đề xuất; lịch trình trước đó được giữ nguyên.",
            "en": "A candidate itinerary could not be created; the previous itinerary was preserved.",
        },
        "search_provider_failure": {
            "vi": "Không thể hoàn tất việc tra cứu nguồn lúc này.",
            "en": "Source research could not be completed at this time.",
        },
        "entry_day_out_of_range": {
            "vi": "Một điểm trong lịch trình nằm ngoài số ngày đã chọn.",
            "en": "An itinerary entry is outside the selected trip days.",
        },
        "invalid_entry_time": {
            "vi": "Một điểm trong lịch trình có thời gian không hợp lệ.",
            "en": "An itinerary entry has an invalid time range.",
        },
        "schedule_overlap": {
            "vi": "Các điểm trong lịch trình bị chồng lấn thời gian.",
            "en": "Itinerary entries overlap in time.",
        },
        "opening_hours_conflict": {
            "vi": "Thời gian lịch trình xung đột với giờ mở cửa đã biết.",
            "en": "The itinerary conflicts with known opening hours.",
        },
        "invalid_opening_hours": {
            "vi": "Giờ mở cửa trong lịch trình không hợp lệ.",
            "en": "An opening-hours value is invalid.",
        },
        "place_source_required": {
            "vi": "Mỗi địa điểm cần có nguồn đã trả về.",
            "en": "Each place needs a returned source.",
        },
        "invalid_source_url": {
            "vi": "Một nguồn không dùng URL HTTP(S) hợp lệ.",
            "en": "A source does not use a valid HTTP(S) URL.",
        },
        "source_not_returned": {
            "vi": "Một nguồn không xuất phát từ kết quả tìm kiếm đã trả về.",
            "en": "A source was not returned by the search provider.",
        },
        "opening_hours_missing": {
            "vi": "Thiếu giờ mở cửa đã xác minh cho địa điểm này.",
            "en": "Verified opening hours are missing for this place.",
        },
        "opening_hours_unsubstantiated": {
            "vi": "Giờ mở cửa đã xác minh không có nguồn hỗ trợ.",
            "en": "Verified opening hours are not supported by a source.",
        },
        "opening_hours_must_be_unverified": {
            "vi": "Giờ mở cửa phải được ghi là chưa xác minh khi không có nguồn hỗ trợ.",
            "en": "Opening hours must be marked unverified when no source supports them.",
        },
    }
    translated = known.get(code)
    return translated[language] if translated else message
