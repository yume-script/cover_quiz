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
    (일반 퀴즈 요청) 성공 {'success': True, 'items': [...], 'total': N,
    'library_name': ..., 'apps_script_url': ...} / 실패
    {'success': False, 'error': '...'}
    (요청 querystring에 list_only=1이 붙은 경우, settings.html 전용)
    {'success': True, 'items': [], 'total': 0,
     'library_options': [...], 'library_debug': [...]}
  두 모드를 분리한 이유: 설정 화면은 라이브러리 드롭다운만 필요한데,
  일반 퀴즈 생성 로직(현재 라이브러리 전체 도서 조회+셔플)까지 매번 함께
  실행되면 설정 화면을 열 때마다 불필요하게 느려지기 때문입니다.
  apps_script_url은 리더보드(최고 점수 기록) 기능을 위한 Google Apps
  Script 웹 앱 URL로, 설정에 값이 있으면 프론트엔드(script.js)가 라운드
  종료 후 이 URL로 직접(브라우저에서) 점수를 저장/조회합니다. 값이
  비어있으면 script.js가 리더보드 UI 자체를 표시하지 않습니다.
- `category_tab`: 코어 좌측/상단 "카테고리" 내비게이션에 별도 메뉴 항목을
  추가합니다 (가이드 문서에는 없지만 stats_dashboard/scan_scheduler 실제
  소스로 확인된 계약: title/icon/order/sessions). index.html/script.js/
  style.css로 완전 커스텀 풀페이지 UI를 렌더링합니다.
  sessions: "all"이 반드시 필요합니다 — 이게 없으면 특정 세션(스코프)
  하나에서만 메뉴가 노출되어, 카테고리별로 독립된 TARGET_LIBRARY_* 설정을
  둔 의미가 없어집니다. "all"이어야 general/adult/audiobook/video 4개
  카테고리 어디서든 이 메뉴가 각각 뜨고, 그때마다 db_type이 해당 스코프로
  넘어와 스코프별 설정이 실제로 분기됩니다.
- `dashboard_widget`은 정의하지 않습니다. 코어의 대시보드 카드 렌더러는
  각 아이템을 정적인 "도서 카드"로만 그리기 때문에 클릭 인터랙션이 필요한
  퀴즈 게임과는 맞지 않습니다 (random_gallery도 같은 이유로 실제로는
  dashboard_widget을 주석 처리해두고 category_tab만 사용합니다).

라이브러리 선택 방식 (카테고리별 독립 설정)
------------------------------------------------
BookOasis는 4개의 고정 DB 스코프(media_ 접두사 + general/adult/audiobook/
video, [[rclone-manager-plugin]](scan_scheduler) 작업에서 확인됨)를 가지고
있고, 각 스코프 "하단"에 여러 개별 라이브러리(예: general 스코프 아래
"텍스트 소설"/"텍스트 일반"/"텍스트 무협")가 존재합니다. `books` 테이블의
`library_id` 컬럼이 이 개별 라이브러리를 구분합니다.

이 플러그인은 카테고리(스코프)마다 완전히 독립된 설정 키를 사용합니다:
TARGET_LIBRARY_GENERAL / TARGET_LIBRARY_ADULT / TARGET_LIBRARY_AUDIOBOOK /
TARGET_LIBRARY_VIDEO (target_library_key() 헬퍼로 생성). get_dashboard_data
가 호출될 때 코어가 넘겨주는 db_type이 "지금 어느 카테고리에서 플러그인이
열렸는지"를 나타내므로, 그 db_type에 해당하는 설정 키 하나만 읽습니다
(_parse_target_selection). 그래서 "일반" 카테고리에서 플러그인을 열면
무조건 TARGET_LIBRARY_GENERAL 값만 적용되고, 다른 스코프의 설정이 섞여
들어올 일이 없습니다.

각 설정값이 비어 있으면 그 스코프의 특정 라이브러리로 좁히지 않고 스코프
전체 도서를 대상으로 합니다. 설정 화면(settings.html)에는 4개 스코프용
드롭다운이 각각 따로 있고, 각 드롭다운은 그 스코프에 속한 라이브러리만
보여줍니다(get_dashboard_data() 응답의 list_only=1 모드가 반환하는
library_options를 스코프별로 필터링해서 채움).

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
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError

from plugins.metadata.base import BaseMetadataProvider

logger = logging.getLogger(__name__)

# 표지 상대경로 앞에 붙일 접두사. 실제 서버 라우팅과 다르면 이 값만 수정하세요.
COVER_URL_PREFIX = "/covers/"

# 정답 이미지 등록 도서가 이 개수 미만이면(오답 후보 확보 불가) 퀴즈를 시작할 수 없습니다.
MIN_POOL_SIZE_FLOOR = 2

# 리더보드 기능의 기본 Google Apps Script 웹 앱 URL. 플러그인 설정에서
# 비워두면(또는 아직 설정을 저장한 적이 없으면) 이 값을 사용합니다.
DEFAULT_APPS_SCRIPT_URL = (
    "https://script.google.com/macros/s/"
    "AKfycbzpVeU94Xafkd6fSRd6yP20qj53iltfKMQXH8f2lTBGFSiP8l50FWRRg6qzr_jjXwx1/exec"
)

# BookOasis의 고정 DB 스코프 식별자 4종 (scan_scheduler 플러그인 개발 시 확인됨).
# 이 스코프들 "하단"에 있는 개별 라이브러리 목록은 매번 DB에서 직접 조회합니다
# (서버마다 실제로 어떤 라이브러리가 있는지 다르기 때문에 하드코딩할 수 없음).
KNOWN_LIBRARY_SCOPES = ["general", "adult", "audiobook", "video"]

# 설정 화면에 표시할 스코프별 한글 라벨.
SCOPE_LABELS = {
    "general": "일반 (general)",
    "adult": "성인 (adult)",
    "audiobook": "오디오북 (audiobook)",
    "video": "비디오 (video)",
}

# 스코프 하나(get_db_gateway 연결 + 테이블/컬럼 조회)를 조사하는 데 허용할
# 최대 시간(초). 존재하지 않거나 응답이 없는 스코프 때문에 설정 화면
# 전체가 무한정 멈추는 것을 막기 위한 안전장치입니다. 4개 스코프는
# ThreadPoolExecutor로 병렬 조회하므로, 전체 소요 시간은 대략 이 값과
# 비슷한 수준으로 제한됩니다(직렬로 4배가 되지 않음).
SCOPE_TIMEOUT_SEC = 5


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


def target_library_key(scope):
    """스코프별 라이브러리 선택값을 저장하는 설정 키 이름.
    예: general -> "TARGET_LIBRARY_GENERAL"
    """
    return "TARGET_LIBRARY_%s" % str(scope).upper()


class CoverQuizMetadataProvider(BaseMetadataProvider):
    id = "cover_quiz"
    name = "책표지 퀴즈"
    is_searchable = False

    # 스코프(카테고리)별로 완전히 독립된 설정 키를 둡니다. "일반" 카테고리에서
    # 플러그인을 열면 TARGET_LIBRARY_GENERAL만, "성인" 카테고리에서 열면
    # TARGET_LIBRARY_ADULT만 사용되므로, 카테고리 간에 서로 다른 스코프의
    # 라이브러리가 섞여 보이는 일이 없습니다.
    config_schema = [
        {
            "key": target_library_key(scope),
            "label": "%s 카테고리에서 사용할 라이브러리 (설정 화면 드롭다운으로 선택)" % SCOPE_LABELS[scope],
            "type": "text",
            "required": False,
            "default": "",
        }
        for scope in KNOWN_LIBRARY_SCOPES
    ] + [
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
        {
            "key": "APPS_SCRIPT_URL",
            "label": "리더보드용 Google Apps Script 웹 앱 URL (비우면 리더보드 기능 비활성화)",
            "type": "text",
            "required": False,
            "default": "https://script.google.com/macros/s/AKfycbzpVeU94Xafkd6fSRd6yP20qj53iltfKMQXH8f2lTBGFSiP8l50FWRRg6qzr_jjXwx1/exec",
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
            "settings.html", "settings.css", "apps_script.gs",
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
        "order": 51,
        "sessions": "all",
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

    def _is_list_only_request(self):
        """설정 화면(settings.html)은 라이브러리 목록만 필요하고 문제 생성은
        필요 없으므로, 요청 querystring에 list_only=1이 있으면 무거운 퀴즈
        생성 로직을 완전히 건너뜁니다. Flask의 요청 컨텍스트에 접근할 수
        없는 환경(다른 프레임워크 등)이면 False로 안전하게 폴백합니다.
        """
        try:
            from flask import request as flask_request
        except Exception:
            return False
        try:
            return flask_request.args.get("list_only") in ("1", "true", "True")
        except Exception:
            return False

    def _parse_target_selection(self, cfg, current_scope):
        """현재 활성 스코프(카테고리)에 해당하는 라이브러리 설정값만 읽습니다.
        예: current_scope="general"이면 TARGET_LIBRARY_GENERAL 키만 봅니다.
        다른 스코프의 설정은 절대 섞이지 않습니다 — "일반" 카테고리에서 열면
        무조건 일반 스코프의 라이브러리(또는 전체)만 대상이 됩니다.
        반환값: (사용할 스코프 = current_scope 그대로, 라이브러리ID 또는 None)
        """
        raw = (cfg.get(target_library_key(current_scope)) or "").strip()
        return current_scope, (raw or None)

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
        existing_tables = set(t.lower() for t in scope_debug["tables"])

        for table in ("libraries", "library", "media_libraries", "book_libraries"):
            # 실제로 존재하지 않는 테이블에 SHOW COLUMNS/PRAGMA를 매번
            # 날리면 (특히 원격 MariaDB에서) 불필요하게 느려지므로, 이미
            # 조회한 테이블 목록에 없는 이름은 컬럼 조회 자체를 생략합니다.
            if existing_tables and table.lower() not in existing_tables:
                continue
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
        4개 고정 스코프 전체에서 수집합니다. 스코프들을 병렬로 조회하고
        스코프 하나당 SCOPE_TIMEOUT_SEC 이상 걸리면 그 스코프는 건너뛰어서,
        일부 스코프가 존재하지 않거나 응답이 없어도 전체 조회가 무한정
        멈추지 않도록 합니다.
        """
        options = []
        debug = []

        def worker(scope):
            scope_debug = []
            libs = self._list_libraries_in_scope(scope, scope_debug)
            return libs, scope_debug

        # 주의: ThreadPoolExecutor를 `with`로 감싸면 __exit__에서
        # shutdown(wait=True)가 호출되어 아직 안 끝난(타임아웃 처리한)
        # 스레드까지 전부 끝날 때까지 블로킹됩니다. 그러면 개별 future에
        # 걸어둔 타임아웃이 무의미해지므로, 여기서는 의도적으로 `with`를
        # 쓰지 않고 shutdown(wait=False)로 응답을 즉시 돌려줍니다(지연
        # 중인 스레드는 백그라운드에서 알아서 끝나거나 소켓 타임아웃으로
        # 종료됩니다).
        executor = ThreadPoolExecutor(max_workers=len(KNOWN_LIBRARY_SCOPES))
        try:
            futures = {executor.submit(worker, scope): scope for scope in KNOWN_LIBRARY_SCOPES}
            for future in futures:
                scope = futures[future]
                try:
                    libs, scope_debug = future.result(timeout=SCOPE_TIMEOUT_SEC)
                except FutureTimeoutError:
                    debug.append(
                        {
                            "scope": scope,
                            "error": "%d초 내에 응답이 없어 건너뜀 (해당 스코프 DB 연결/쿼리 지연)"
                            % SCOPE_TIMEOUT_SEC,
                        }
                    )
                    continue
                except Exception as exc:
                    debug.append({"scope": scope, "error": "조회 실패: %s" % exc})
                    continue
                debug.extend(scope_debug)
                for lib in libs:
                    options.append(
                        {
                            "value": "%s:%s" % (scope, lib["library_id"]),
                            "scope": scope,
                            "library_id": lib["library_id"],
                            "name": lib["name"],
                        }
                    )
        finally:
            executor.shutdown(wait=False)
        return options, debug

    def _get_single_library_name(self, scope, library_id):
        """퀴즈 화면에서 헤더에 표시할 라이브러리명을, 4개 스코프 전체를
        훑는 무거운 _list_all_libraries() 없이 선택된 라이브러리 하나만
        가볍게 조회합니다.
        """
        try:
            gateway = self.get_db_gateway(scope)
        except Exception:
            return None

        tables = self._list_tables(gateway)
        existing_tables = set(t.lower() for t in tables)

        for table in ("libraries", "library", "media_libraries", "book_libraries"):
            if existing_tables and table.lower() not in existing_tables:
                continue
            columns = self._table_columns(gateway, table)
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
                row = gateway.fetch_one(
                    "SELECT %s AS lib_name FROM %s WHERE id = ?" % (name_col, table),
                    (library_id,),
                )
            except Exception:
                row = None
            if row:
                val = get_row_val(row, "lib_name")
                if val:
                    return str(val).strip()
        return None

    # ------------------------------------------------------------------
    # 내부 구현: 퀴즈 라운드 생성
    # ------------------------------------------------------------------
    def _build_quiz(self, db_type, limit=10):
        # settings.html은 라이브러리 목록만 필요하고 문제 생성은 필요 없으므로
        # (list_only=1 요청), 무거운 도서 조회/셔플 로직을 완전히 건너뜁니다.
        # 이걸 나누지 않으면 설정 화면을 열 때마다 현재 라이브러리 전체
        # 도서를 조회하는 무거운 쿼리가 함께 실행돼서 체감상 매우 느려집니다.
        if self._is_list_only_request():
            library_options, library_debug = self._list_all_libraries()
            return {
                "success": True,
                "items": [],
                "total": 0,
                "library_options": library_options,
                "library_debug": library_debug,
            }

        cfg = self._get_config(db_type)
        target_scope, target_library_id = self._parse_target_selection(cfg, db_type)
        question_count = self._get_questions_count(cfg, limit)
        choice_count = self._get_choices_count(cfg)
        apps_script_url = (cfg.get("APPS_SCRIPT_URL") or DEFAULT_APPS_SCRIPT_URL).strip()

        try:
            gateway = self.get_db_gateway(target_scope)
        except Exception as exc:
            logger.exception(
                "[cover_quiz] DB 게이트웨이 연결 실패 (target_scope=%s)", target_scope
            )
            return {
                "success": False,
                "error": "지정된 라이브러리(%s)에 연결할 수 없습니다: %s" % (target_scope, exc),
            }

        # 퀴즈 화면에서는 4개 스코프 전체를 훑는 무거운 _list_all_libraries()
        # 대신, 선택된 라이브러리 하나만 가볍게 조회해서 표시 이름을 얻습니다.
        if target_library_id:
            library_name = self._get_single_library_name(target_scope, target_library_id) or target_scope
        else:
            library_name = target_scope

        # LIMIT을 걸어두는 이유: list_only 감지(Flask request 컨텍스트 의존)가
        # 어떤 이유로든 동작하지 않아 이 무거운 경로를 타게 되더라도, 라이브러리
        # 전체 도서 수와 무관하게 조회 자체가 빠르게 끝나도록 상한을 둡니다.
        # 문제 풀(pool)은 표지/제목 중복 필터링 후 question_count만큼만 쓰이므로
        # 3000권이면 사실상 모든 실사용 시나리오에서 충분합니다.
        # (LIMIT은 반드시 WHERE 절 뒤, 마지막에 와야 하므로 library_id 조건을
        # 먼저 조립한 뒤 맨 마지막에 LIMIT을 붙입니다.)
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
        query += " LIMIT 3000"

        try:
            rows = gateway.fetch_all(query, params) if params else gateway.fetch_all(query)
        except Exception as exc:
            logger.exception(
                "[cover_quiz] 도서 목록 조회 실패 (target_scope=%s, library_id=%s)",
                target_scope, target_library_id,
            )
            return {"success": False, "error": "도서 목록을 가져오지 못했습니다: %s" % exc}

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
            return {
                "success": False,
                "error": (
                    "표지가 등록된 도서가 부족합니다 (현재 %d권, 선택지 %d개를 위해 "
                    "최소 %d권 필요). 라이브러리 설정이나 표지 등록 상태를 확인해주세요."
                )
                % (len(pool), choice_count, min_required),
            }

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

        return {
            "success": True,
            "items": questions,
            "total": len(questions),
            "library_name": library_name,
            "apps_script_url": apps_script_url,
        }
