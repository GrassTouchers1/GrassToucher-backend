"""
AI Layer Module - Hệ sinh thái Trí tuệ Nhân tạo Giám sát & Ứng phó Thiên tai NorthStar.
Quản lý các AI Provider (Groq Cloud, Local/Ollama, Mock Offline Fallback).
"""

from .base import AIProvider
from .factory import get_ai_provider

__all__ = ["AIProvider", "get_ai_provider"]
