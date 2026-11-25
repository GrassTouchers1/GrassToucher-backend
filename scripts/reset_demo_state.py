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
Khoi phuc trang thai Demo sach se cho NorthStar Fallback DB (su dung truoc khi trinh dien).
Khong dung trong moi truong Production co du lieu nguoi dan that.
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app import auth, fallback_storage  # noqa: E402


TEST_MARKER_NAMES = (
    "Nguyễn Văn Test",
    "Nguyen Van Test",
    "VoiceTest",
    "Zero Origin",
    "An",
    "Bi co lap",
    "Trần Thị Lan",
    "Nguyen Van Bi Mat",
)


def reset_demo_state() -> dict:
    fallback_storage.init_fallback_db()
    auth.init_auth_tables()

    removed_sos = 0
    removed_relief = 0
    with fallback_storage._FALLBACK_WRITE_LOCK:
        with fallback_storage._get_connection() as conn:
            placeholders = ",".join("?" for _ in TEST_MARKER_NAMES)
            cur1 = conn.execute(
                f"DELETE FROM fallback_sos WHERE contact_name IN ({placeholders}) OR phone LIKE '09111111%'",
                TEST_MARKER_NAMES,
            )
            removed_sos = cur1.rowcount
            cur2 = conn.execute(
                "DELETE FROM fallback_relief_requests WHERE id LIKE 'NS-TEST%' OR contact_name IN (" + placeholders + ") OR phone IN ('0988111222','0988333444')",
                TEST_MARKER_NAMES,
            )
            removed_relief = cur2.rowcount
            conn.commit()

    return {
        "db_path": str(fallback_storage.DB_PATH),
        "removed_test_sos": removed_sos,
        "removed_test_relief": removed_relief,
    }


if __name__ == "__main__":
    summary = reset_demo_state()
    print("[NorthStar Demo Reset]", summary)
