# -*- coding: utf-8 -*-
"""cover_quiz 플러그인 패키지 진입점.

코어가 cover_quiz.py를 직접 읽어 클래스를 찾는 방식이라면 이 파일은 비어
있어도 무방하지만, `from plugins.metadata.cover_quiz import ...` 형태의
패키지 임포트에도 대응할 수 있도록 클래스를 재노출해 둡니다.
(random_gallery/__init__.py와 동일한 패턴)
"""

from .cover_quiz import CoverQuizMetadataProvider

__all__ = ["CoverQuizMetadataProvider"]
