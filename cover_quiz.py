# -*- coding: utf-8 -*-
"""
Book Cover Quiz Plugin (id: cover_quiz)
----------------------------------------

설정에서 지정한 "개별 라이브러리"의 도서 표지 이미지를 보여주고,
객관식(정답 1 + 오답 N)으로 책 제목을 맞히는 BookOasis 게임 플러그인입니다.
(표시명: 책표지 퀴즈)

가이드 문서 "5. 대시보드 위젯 및 플러그인 데스크 계약"의 데이터 계약만
그대로 재사용합니다.

- `get_dashboard_data(self, db_type, limit=10)`:
    성공 {'success': True, 'items': [...], 'total': N, 'library_name': ...,
          'library_options': [...]}
    실패 {'success': False, 'error': '...', 'library_options': [...]}
  library_options는 퀴즈 문제와 무관하게 "설정 화면 드롭다운을 채우기
  위한" 전체 라이브러리 목록입니다. 성공/실패 여부와 관계없이 항상
  포함해서, settings.html의 스크립트가 이 값만 보고 드롭다운을 채울 수
  있게 했습니다.
- `category_tab`: 코어 좌측/상단 "카테고리" 내비게이션에 별도 메뉴 항목을
  추가합니다 (가이드 문서에는 없지만 stats_dashboard 실제 소스로 확인된
  계약: title/icon/order). index.html/script.js/style.css로 완전 커스텀
  풀페이지 UI를 렌더링합니다.
- `dashboard_widget`은 정의하지 않습니다. 코어의 대시보드 카드 렌더러는
  각 아이템을 정적인 "도서 카드"로만 그리기 때문에 클릭 인터랙션이 필요한
  퀴즈 게임과는 맞지 않습니다 (random_gallery도 같은 이유로 실제로는
  dashboard_widget을 주석 처리해두고 category_tab만 사용합니다).

라이브러리 선택 방식 (스코프 + 개별 라이브러리)
------------------------------------------------
BookOasis는 4개의 고정 DB 스코프(media_ 접두사 + general/adult/audiobook/
video, [[rclone-manager-plugin]](scan_scheduler) 작업에서 확인됨)를 가지고
있고, 각 스코프 "하단"에 여러 개별 라이브러리(예: general 스코프 아래
"텍스트 소설"/"텍스트 일반"/"텍스트 무협")가 존재합니다. `books` 테이블의
`library_id` 컬럼이 이 개별 라이브러리를 구분합니다.

그래서 설정값 TARGET_DB_TYPE에는 "스코프:라이브러리ID" 형식의 복합값
(예: "general:12")을 저장합니다. 설정 화면에서는 이 값을 사람이 읽을 수
있는 실제 라이브러리명으로 고른 뒤 저장할 수 있도록, settings.html에
내장된 스크립트가 이 파일의 get_dashboard_data() 응답에 포함된
library_options를 읽어와 스코프별로 그룹핑한 드롭다운을 동적으로
채웁니다 (정적 HTML만으로는 서버마다 다른 실제 라이브러리 목록을 미리
알 수 없기 때문입니다).

값이 비어 있으면 코어가 넘겨준 "현재 카테고리의 라이브러리"(db_type)를
그대로 사용하고, library_id 필터 없이 그 스코프 전체 도서를 대상으로
합니다.

표지 이미지 URL 해석
----------------------
`books.cover_image` 컬럼에는 (unified_book 플러그인의 apply() 저장 로직
기준으로) "{library_id}/{파일명}.webp" 형태의 상대경로가 저장됩니다.
이 플러그인은 이 값을 코어의 표지 정적 제공 경로인 "/covers/" 접두사와
결합해서 사용합니다 (예: "/covers/3/book_abcd1234.webp").

    ⚠️ 만약 실제 서버에서 표지 URL 접두사가 "/covers/"가 아니라면
    (예: "/api/media/covers/" 등), 아래 COVER_URL_PREFIX 상수만 실제
    값으로 바꿔주시면 됩니다. 이미 http(s):// 로 시작하는 절대 URL이
    저장되어 있는 경우(외부 이미지 등)에는 그대로 사용합니다.
"""

import logging
import random

from plugins.metadata.base import BaseMetadataProvider

logger = logging.getLogger(__name__)

# 표지 상대경로 앞에 붙일 접두사. 실제 서버 라우팅과 다르면 이 값만 수정하세요.
COVER_URL_PREFIX = "/covers/"

# 정답 이미지 등록 도서가 이 개수 미만이면(오답 후보 확보 불가) 퀴즈를 시작할 수 없습니다.
MIN_POOL_SIZE_FLOOR = 2

# BookOasis의 고정 DB 스코프 식별자 4종 (scan_scheduler 플러그인 개발 시 확인됨).
# 이 스코프들 "하단"에 있는 개별 라이브러리 목록은 매번 DB에서 직접 조회합니다
# (서버마다 실제로 어떤 라이브러리가 있는지 다르기 때문에 하드코딩할 수 없음).
KNOWN_LIBRARY_SCOPES = ["general", "adult", "audiobook", "video"]


def get_row_val(row, key, default=None):
    """DB 게이트웨이가 반환하는 Row 객체가 dict-like이든 sqlite3.Row/튜플성
    객체이든 안전하게 값을 꺼내기 위한 헬퍼 (unified_book의 get_row_val과
    동일한 목적의 방어적 헬퍼를 이 플러그인 안에 자체 내장했습니다).
    """
    try:
        return row[key]
    except Exception:
        pass
    try:
        return row.get(key, default)
    except Exception:
        return default


class CoverQuizMetadataProvider(BaseMetadataProvider):
    id = "cover_quiz"
    name = "책표지 퀴즈"
    is_searchable = False

    config_schema = [
        {
            "key": "TARGET_DB_TYPE",
            "label": "퀴즈에 사용할 라이브러리 (설정 화면에서 드롭다운으로 선택)",
            "type": "text",
            "required": False,
            "default": "",
        },
        {
            "key": "QUESTIONS_PER_ROUND",
            "label": "한 라운드 문제 수",
            "type": "number",
            "required": False,
            "default": 10,
        },
        {
            "key": "CHOICES_COUNT",
            "label": "선택지 개수 (정답 1개 포함)",
            "type": "number",
            "required": False,
            "default": 4,
        },
    ]

    # 자동 업데이트를 사용하려면 raw_base_url을 실제 리포지토리 경로로 수정하고
    # enabled를 True로 바꾸세요.
    update_manifest = {
        "enabled": False,
        "provider": "github-raw",
        "raw_base_url": "https://raw.githubusercontent.com/yume-script/cover_quiz/refs/heads/main/",
        "files": [
            "README.md", "VERSION", "__init__.py", "cover_quiz.py",
            "index.html", "script.js", "style.css",
            "settings.html", "settings.css",
        ],
        "version_file": "VERSION",
        "version_key": "plugin version",
        "show_sample_update_button": False,
    }

    # 코어 좌측/상단 "카테고리" 내비게이션에 별도 메뉴로 노출 + index.html/
    # script.js/style.css로 완전 커스텀 풀페이지 렌더링. dashboard_widget과
    # 달리 @property가 아닌 고정 dict여야 코어가 목록에서 플러그인을
    # 정상적으로 인식합니다 (random_gallery에서 실제로 겪은 회귀 버그).
    category_tab = {
        "title": "책표지 퀴즈",
        "icon": "fa-solid fa-image-portrait",
        "order": 92,
    }

    # ------------------------------------------------------------------
    # 필수 계약 (이 플러그인은 검색/적용 대상이 아니므로 빈 구현만 제공)
    # ------------------------------------------------------------------
    def search(self, db_type, query):
        return {"success": True, "items": []}

    def apply(self, db_type, book_id, item_data):
        return False, "이 플러그인은 카테고리 전용(표지 퀴즈 게임)입니다."

    # ------------------------------------------------------------------
    # 대시보드 공통 계약 (category_tab의 script.js / settings.html의
    # 드롭다운 채우기 스크립트가 공통으로 이 엔드포인트를 호출)
    # ------------------------------------------------------------------
    def get_dashboard_data(self, db_type, limit=10):
        return self._build_quiz(db_type, limit=limit)

    # ------------------------------------------------------------------
    # 설정값 헬퍼
    # ------------------------------------------------------------------
    def _get_config(self, db_type):
        return self.get_plugin_config(db_type, default={}) or {}

    def _parse_target_selection(self, cfg, fallback_db_type):
        """설정값 TARGET_DB_TYPE("스코프:라이브러리ID" 또는 빈 값)을 파싱합니다.
        반환값: (사용할 스코프, 라이브러리ID 또는 None)
        """
        raw = (cfg.get("TARGET_DB_TYPE") or "").strip()
        if not raw:
            return fallback_db_type, None
        if ":" in raw:
            scope, _, lib_id = raw.partition(":")
            scope = scope.strip()
            lib_id = lib_id.strip()
            return (scope or fallback_db_type), (lib_id or None)
        # 콜론 없이 스코프 식별자만 저장된 경우(과거 버전 호환)에 대한 폴백
        return raw, None

    def _get_questions_count(self, cfg, limit):
        try:
            n = int(cfg.get("QUESTIONS_PER_ROUND") or limit or 10)
        except (ValueError, TypeError):
            n = 10
        return max(1, min(n, 50))

    def _get_choices_count(self, cfg):
        try:
            n = int(cfg.get("CHOICES_COUNT") or 4)
        except (ValueError, TypeError):
            n = 4
        return max(2, min(n, 6))

    def _resolve_cover_url(self, cover_image):
        if not cover_image:
            return None
        cover_image = str(cover_image).strip()
        if not cover_image:
            return None
        if cover_image.startswith("http://") or cover_image.startswith("https://"):
            return cover_image
        return COVER_URL_PREFIX + cover_image.lstrip("/")

    # ------------------------------------------------------------------
    # 라이브러리 목록/이름 조회 (MariaDB/SQLite 방어적 컬럼 탐색)
    # ------------------------------------------------------------------
    def _table_columns(self, gateway, table):
        """unified_book.py의 컬럼 존재 여부 동적 체크와 동일한 방식으로,
        SHOW COLUMNS(MariaDB) 시도 후 실패하면 PRAGMA table_info(SQLite)로
        재시도합니다. 두 시도 모두 실패하면 빈 리스트를 반환합니다(테이블이
        아예 없는 경우 포함).
        """
        try:
            info = gateway.fetch_all("SHOW COLUMNS FROM %s" % table)
            if info:
                return [str(get_row_val(col, "Field") or "").lower() for col in info]
        except Exception:
            pass
        try:
            info = gateway.fetch_all("PRAGMA table_info(%s)" % table)
            if info:
                return [str(get_row_val(col, "name") or "").lower() for col in info]
        except Exception:
            pass
        return []

    def _list_tables(self, gateway):
        """진단용: 이 DB 스코프에 실제로 어떤 테이블이 있는지 조회합니다.
        MariaDB(SHOW TABLES)와 SQLite(sqlite_master) 양쪽을 방어적으로
        시도합니다. 정확한 라이브러리 테이블명을 모를 때 이 목록으로
        후보를 좁힙니다.
        """
        try:
            rows = gateway.fetch_all("SHOW TABLES")
            if rows:
                names = []
                for row in rows:
                    try:
                        # SHOW TABLES 결과는 컬럼명이 DB명에 따라 달라지므로
                        # dict/tuple 양쪽 다 방어적으로 처리
                        if hasattr(row, "values"):
                            names.append(str(list(row.values())[0]))
                        else:
                            names.append(str(row[0]))
                    except Exception:
                        continue
                if names:
                    return names
        except Exception:
            pass
        try:
            rows = gateway.fetch_all(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
            if rows:
                return [str(get_row_val(row, "name")) for row in rows if get_row_val(row, "name")]
        except Exception:
            pass
        return []

    def _list_libraries_in_scope(self, scope, debug):
        """지정된 스코프의 DB에 연결해서 그 안에 있는 개별 라이브러리
        (id, 실제 이름) 목록을 조회합니다. 정확한 스키마(테이블/컬럼명)를
        알 수 없으므로 흔히 쓰이는 테이블/컬럼 조합을 순서대로 방어적으로
        시도합니다. 실패하면 빈 리스트를 반환하고, debug 리스트에 이
        스코프에서 실제로 발견된 테이블 목록/시도한 테이블별 컬럼을
        기록해서 원인 파악에 사용합니다.
        """
        try:
            gateway = self.get_db_gateway(scope)
        except Exception as exc:
            debug.append({"scope": scope, "error": "게이트웨이 연결 실패: %s" % exc})
            return []

        scope_debug = {"scope": scope, "tables": self._list_tables(gateway), "tried": []}
        debug.append(scope_debug)

        for table in ("libraries", "library", "media_libraries", "book_libraries"):
            columns = self._table_columns(gateway, table)
            scope_debug["tried"].append({"table": table, "columns": columns})
            if not columns or "id" not in columns:
                continue
            name_col = None
            for candidate in ("name", "display_name", "library_name", "title"):
                if candidate in columns:
                    name_col = candidate
                    break
            if not name_col:
                continue
            try:
                rows = gateway.fetch_all(
                    "SELECT id, %s AS lib_name FROM %s "
                    "WHERE %s IS NOT NULL AND %s != '' ORDER BY %s"
                    % (name_col, table, name_col, name_col, name_col)
                )
            except Exception:
                rows = None
            if not rows:
                continue
            result = []
            for row in rows:
                lib_id = get_row_val(row, "id")
                lib_name = get_row_val(row, "lib_name")
                if lib_id is None or not lib_name:
                    continue
                result.append({"library_id": lib_id, "name": str(lib_name).strip()})
            if result:
                return result
        return []

    def _list_all_libraries(self):
        """설정 화면 드롭다운에 사용할 전체 (스코프, 라이브러리) 목록을
        4개 고정 스코프 전체에서 수집합니다. 스코프 하나가 실패해도
        나머지는 계속 진행합니다. 두 번째 반환값은 진단 정보입니다
        (settings.html에서 실패 원인을 바로 확인할 수 있도록 응답에
        그대로 포함시킵니다).
        """
        options = []
        debug = []
        for scope in KNOWN_LIBRARY_SCOPES:
            for lib in self._list_libraries_in_scope(scope, debug):
                options.append(
                    {
                        "value": "%s:%s" % (scope, lib["library_id"]),
                        "scope": scope,
                        "library_id": lib["library_id"],
                        "name": lib["name"],
                    }
                )
        return options, debug

    def _resolve_library_name(self, scope, library_id, library_options):
        if library_id:
            for opt in library_options:
                if opt["scope"] == scope and str(opt["library_id"]) == str(library_id):
                    return opt["name"]
        # 개별 라이브러리를 특정하지 못한 경우, 스코프 전체를 쓰는 것이므로
        # 식별자 자체를 표시명으로 폴백합니다.
        return scope

    # ------------------------------------------------------------------
    # 내부 구현: 퀴즈 라운드 생성
    # ------------------------------------------------------------------
    def _build_quiz(self, db_type, limit=10):
        # settings.html의 드롭다운 채우기 스크립트도 이 응답을 사용하므로,
        # 아래 어떤 경로로 리턴하든 항상 library_options/library_debug를 포함시킵니다.
        library_options, library_debug = self._list_all_libraries()

        def finish(result):
            result["library_options"] = library_options
            result["library_debug"] = library_debug
            return result

        cfg = self._get_config(db_type)
        target_scope, target_library_id = self._parse_target_selection(cfg, db_type)
        question_count = self._get_questions_count(cfg, limit)
        choice_count = self._get_choices_count(cfg)

        try:
            gateway = self.get_db_gateway(target_scope)
        except Exception as exc:
            logger.exception(
                "[cover_quiz] DB 게이트웨이 연결 실패 (target_scope=%s)", target_scope
            )
            return finish(
                {
                    "success": False,
                    "error": "지정된 라이브러리(%s)에 연결할 수 없습니다: %s" % (target_scope, exc),
                }
            )

        library_name = self._resolve_library_name(target_scope, target_library_id, library_options)

        query = (
            "SELECT id, title, cover_image FROM books "
            "WHERE COALESCE(is_deleted, 0) = 0 "
            "AND cover_image IS NOT NULL AND cover_image != '' "
            "AND title IS NOT NULL AND title != ''"
        )
        params = ()
        if target_library_id:
            query += " AND library_id = ?"
            params = (target_library_id,)

        try:
            rows = gateway.fetch_all(query, params) if params else gateway.fetch_all(query)
        except Exception as exc:
            logger.exception(
                "[cover_quiz] 도서 목록 조회 실패 (target_scope=%s, library_id=%s)",
                target_scope, target_library_id,
            )
            return finish({"success": False, "error": "도서 목록을 가져오지 못했습니다: %s" % exc})

        # 표지/제목이 유효하고, 제목이 중복되지 않는 도서만 문제 후보 풀에 포함.
        # (같은 제목의 책이 여러 권 있으면 오답 선택지끼리 겹쳐서 문제가
        # 성립하지 않으므로 정규화된 제목 기준으로 1권씩만 남깁니다.)
        pool = []
        seen_titles = set()
        for row in rows:
            title = (get_row_val(row, "title") or "").strip()
            cover_image = get_row_val(row, "cover_image")
            book_id = get_row_val(row, "id")
            if not title or not cover_image or book_id is None:
                continue
            norm_title = title.lower()
            if norm_title in seen_titles:
                continue
            cover_url = self._resolve_cover_url(cover_image)
            if not cover_url:
                continue
            seen_titles.add(norm_title)
            pool.append({"id": book_id, "title": title, "cover": cover_url})

        min_required = max(choice_count, MIN_POOL_SIZE_FLOOR)
        if len(pool) < min_required:
            return finish(
                {
                    "success": False,
                    "error": (
                        "표지가 등록된 도서가 부족합니다 (현재 %d권, 선택지 %d개를 위해 "
                        "최소 %d권 필요). 라이브러리 설정이나 표지 등록 상태를 확인해주세요."
                    )
                    % (len(pool), choice_count, min_required),
                }
            )

        random.shuffle(pool)
        question_source = pool[: min(question_count, len(pool))]

        questions = []
        for idx, answer in enumerate(question_source):
            wrong_pool = [b for b in pool if b["id"] != answer["id"]]
            random.shuffle(wrong_pool)
            wrong_choices = wrong_pool[: choice_count - 1]

            choice_books = wrong_choices + [answer]
            random.shuffle(choice_books)

            questions.append(
                {
                    "id": "q-%d" % idx,
                    "cover": answer["cover"],
                    "choices": [
                        {"text": c["title"], "correct": c["id"] == answer["id"]}
                        for c in choice_books
                    ],
                }
            )

        return finish(
            {
                "success": True,
                "items": questions,
                "total": len(questions),
                "library_name": library_name,
            }
        )
