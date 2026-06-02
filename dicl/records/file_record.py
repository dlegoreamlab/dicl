"""
DICL FileRecord adapter
──────────────────────
DICL 의 출력 레코드는 DFSS 의 표준 FileRecord 를 그대로 사용한다.
"""

from dfss import FileRecord

__all__ = ["FileRecord"]
