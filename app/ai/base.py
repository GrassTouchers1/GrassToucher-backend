# Copyright 2026 GrassTouchers Team
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# SPDX-License-Identifier: Apache-2.0

"""
Interface Trừu tượng AIProvider cho Hệ sinh thái NorthStar.
Đảm bảo tính pluggable: Dễ dàng hoán đổi giữa Groq, Mock, LocalAI/Ollama
hoặc bất kỳ nhà cung cấp AI nào mà không sửa đổi logic nghiệp vụ của tầng API.
"""

from abc import ABC, abstractmethod
from typing import Any, Optional

from .schemas import (
    ReportAnalysisResult,
    DisasterSummaryResult,
    EmergencyClassificationResult,
    AIChatResult,
    ProviderStatusResult,
)


class AIProvider(ABC):
    """Lớp cơ sở trừu tượng cho tất cả các nhà cung cấp AI."""

    @abstractmethod
    async def analyze_report(
        self,
        content: str,
        source: Optional[str] = "community",
        reporter: Optional[str] = None
    ) -> ReportAnalysisResult:
        """
        1. Disaster Report Analysis:
        Phân tích nội dung báo cáo thiên tai, trích xuất loại thiên tai, địa điểm,
        thời gian xảy ra, thông tin còn thiếu và phân loại mức độ khẩn cấp sơ bộ.
        """
        pass

    @abstractmethod
    async def summarize_disaster(
        self,
        region: Optional[str] = None,
        reports: Optional[list[dict[str, Any]]] = None,
        time_window_hours: int = 24
    ) -> DisasterSummaryResult:
        """
        2. Disaster Information Summarization:
        Tổng hợp báo cáo từ nhiều nguồn, tóm tắt diễn biến thiên tai,
        nhóm báo cáo tương tự và đánh dấu mâu thuẫn/chưa xác minh.
        """
        pass

    @abstractmethod
    async def classify_emergency(
        self,
        message: str,
        contact_phone: Optional[str] = None,
        location_text: Optional[str] = None
    ) -> EmergencyClassificationResult:
        """
        3. Rescue Information Classification:
        Phân loại yêu cầu cứu trợ (sơ tán, thực phẩm, nước sạch, y tế, cứu hộ),
        nhận diện nhóm dễ bị tổn thương và trích xuất số người bị ảnh hưởng.
        """
        pass

    @abstractmethod
    async def chat(
        self,
        query: str,
        conversation_history: Optional[list[dict[str, str]]] = None,
        context: Optional[dict[str, Any]] = None,
        lat: Optional[float] = None,
        lng: Optional[float] = None
    ) -> AIChatResult:
        """
        4. Emergency Assistant Chat:
        Hỗ trợ hỏi đáp về tình hình thiên tai, trả lời dựa trên dữ liệu thực tế backend cung cấp.
        Không tự tạo ra số liệu giả mạo.
        """
        pass

    @abstractmethod
    async def get_status(self) -> ProviderStatusResult:
        """Kiểm tra và trả về trạng thái hoạt động của AI Provider."""
        pass
