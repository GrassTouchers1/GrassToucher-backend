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
AI Provider Factory cho Hệ sinh thái NorthStar.
Khởi tạo và cung cấp AI Provider dựa trên cấu hình môi trường (.env).
"""

from functools import lru_cache
from typing import Optional

from .. import config
from .base import AIProvider
from .groq_provider import GroqProvider
from .mock_provider import MockAIProvider
from .schemas import ProviderStatusResult


class DisabledAIProvider(AIProvider):
    """Provider đại diện khi quản trị viên tắt hoàn toàn tính năng AI (AI_ENABLED=false)."""

    def __init__(self):
        self.fallback = MockAIProvider(model_name="disabled")

    async def analyze_report(self, content: str, source: Optional[str] = "community", reporter: Optional[str] = None):
        return await self.fallback.analyze_report(content, source, reporter)

    async def summarize_disaster(self, region: Optional[str] = None, reports: Optional[list] = None, time_window_hours: int = 24):
        return await self.fallback.summarize_disaster(region, reports, time_window_hours)

    async def classify_emergency(self, message: str, contact_phone: Optional[str] = None, location_text: Optional[str] = None):
        return await self.fallback.classify_emergency(message, contact_phone, location_text)

    async def chat(self, query: str, conversation_history: Optional[list] = None, context: Optional[dict] = None, lat: Optional[float] = None, lng: Optional[float] = None):
        return await self.fallback.chat(query, conversation_history, context, lat, lng)

    async def get_status(self) -> ProviderStatusResult:
        return ProviderStatusResult(
            enabled=False,
            configured_provider=config.AI_PROVIDER,
            active_provider="disabled",
            model="none",
            status="disabled",
            is_fallback_active=False,
            capabilities=[],
            message="Toàn bộ hệ thống AI đang ở trạng thái TẮT (AI_ENABLED=false)."
        )


@lru_cache(maxsize=1)
def get_ai_provider() -> AIProvider:
    """Trả về Singleton instance của AI Provider dựa trên cấu hình."""
    if not config.AI_ENABLED:
        return DisabledAIProvider()

    provider_name = config.AI_PROVIDER.lower().strip()

    if provider_name == "groq":
        return GroqProvider(
            api_key=config.GROQ_API_KEY,
            model=config.GROQ_MODEL,
            timeout_sec=config.AI_TIMEOUT_SEC
        )
    elif provider_name == "mock":
        return MockAIProvider()
    else:
        # Trường hợp cấu hình provider chưa được hỗ trợ (ví dụ 'ollama' tương lai) -> fallback về Mock
        return MockAIProvider(model_name=f"{provider_name}-unsupported-fallback")
