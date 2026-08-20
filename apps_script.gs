/**
 * 책표지 퀴즈(cover_quiz) 리더보드용 Google Apps Script 웹 앱.
 *
 * 사용 방법
 * ----------
 * 1. 새 Google 스프레드시트를 만듭니다 (시트 이름은 무엇이든 상관없습니다.
 *    이 스크립트가 "leaderboard"라는 이름의 시트를 자동으로 만들어 씁니다).
 * 2. 상단 메뉴에서 확장 프로그램 > Apps Script 를 엽니다.
 * 3. 기본 생성된 코드를 모두 지우고 이 파일의 내용 전체를 붙여넣습니다.
 * 4. 우측 상단 "배포" > "새 배포"를 클릭합니다.
 *    - 유형: 웹 앱
 *    - 실행 계정: 나
 *    - 액세스 권한이 있는 사용자: 전체(익명 사용자도 가능)
 * 5. 배포 후 나오는 웹 앱 URL(".../exec"로 끝남)을 복사합니다.
 * 6. BookOasis "책표지 퀴즈" 플러그인 설정의 APPS_SCRIPT_URL 값에
 *    이 URL을 붙여넣고 저장합니다.
 *
 * 스프레드시트 "leaderboard" 시트 컬럼: timestamp, name, library, score, total
 */

function doGet(e) {
  try {
    var params = (e && e.parameter) || {};
    var action = params.action || "leaderboard";

    if (action === "leaderboard") {
      return jsonOutput_(getLeaderboard_(params));
    }

    return jsonOutput_({ success: false, error: "알 수 없는 action: " + action });
  } catch (err) {
    return jsonOutput_({ success: false, error: String(err) });
  }
}

function doPost(e) {
  try {
    var payload = {};
    if (e && e.postData && e.postData.contents) {
      payload = JSON.parse(e.postData.contents);
    }
    return jsonOutput_(saveScore_(payload));
  } catch (err) {
    return jsonOutput_({ success: false, error: String(err) });
  }
}

function getLeaderboard_(params) {
  var sheet = getSheet_();
  var library = params.library || "";
  var limit = parseInt(params.limit || "10", 10);
  if (isNaN(limit) || limit <= 0) {
    limit = 10;
  }

  var lastRow = sheet.getLastRow();
  if (lastRow < 2) {
    return { success: true, items: [] };
  }

  var values = sheet.getRange(2, 1, lastRow - 1, 5).getValues();
  var rows = values.map(function (r) {
    return {
      timestamp: r[0] ? new Date(r[0]).toISOString() : "",
      name: String(r[1] || "익명"),
      library: String(r[2] || ""),
      score: Number(r[3]) || 0,
      total: Number(r[4]) || 0,
    };
  });

  if (library) {
    rows = rows.filter(function (r) {
      return r.library === library;
    });
  }

  rows.sort(function (a, b) {
    // 점수 내림차순, 동점이면 total이 작은(=효율 좋은) 쪽이 우선
    if (b.score !== a.score) {
      return b.score - a.score;
    }
    return a.total - b.total;
  });

  return { success: true, items: rows.slice(0, limit) };
}

function saveScore_(payload) {
  var name = String(payload.name || "익명").trim().slice(0, 30) || "익명";
  var library = String(payload.library || "").trim();
  var score = parseInt(payload.score, 10);
  var total = parseInt(payload.total, 10);

  if (isNaN(score) || isNaN(total) || total <= 0 || score < 0 || score > total) {
    return { success: false, error: "잘못된 점수 데이터입니다." };
  }

  var sheet = getSheet_();
  sheet.appendRow([new Date(), name, library, score, total]);
  return { success: true };
}

function getSheet_() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var sheet = ss.getSheetByName("leaderboard");
  if (!sheet) {
    sheet = ss.insertSheet("leaderboard");
    sheet.appendRow(["timestamp", "name", "library", "score", "total"]);
  }
  return sheet;
}

function jsonOutput_(obj) {
  return ContentService.createTextOutput(JSON.stringify(obj)).setMimeType(
    ContentService.MimeType.JSON
  );
}
