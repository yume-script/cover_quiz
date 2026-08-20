(function () {
  "use strict";

  // random_gallery와 동일하게, 코어가 category_tab/dashboard_widget에
  // 공통으로 노출하는 데이터 엔드포인트를 그대로 사용합니다.
  var DATA_ENDPOINT = "/api/media/dashboard/widgets/cover_quiz/data";

  var state = {
    questions: [],
    currentIndex: 0,
    correctCount: 0,
    answered: false,
  };

  var els = {};

  function qs(id) {
    return document.getElementById(id);
  }

  function cacheEls() {
    els.subtitle = qs("bq-subtitle");
    els.status = qs("bq-status");
    els.quizArea = qs("bq-quiz-area");
    els.result = qs("bq-result");
    els.coverImg = qs("bq-cover-img");
    els.choices = qs("bq-choices");
    els.feedback = qs("bq-feedback");
    els.nextBtn = qs("bq-next-btn");
    els.restartBtn = qs("bq-restart-btn");
    els.score = qs("bq-score");
    els.progressFill = qs("bq-progress-fill");
    els.progressText = qs("bq-progress-text");
    els.resultScore = qs("bq-result-score");
  }

  function showStatus(message) {
    els.status.textContent = message;
    els.status.style.display = "block";
    els.quizArea.style.display = "none";
    els.result.style.display = "none";
  }

  function updateScoreboard(answeredCount) {
    var answered = typeof answeredCount === "number" ? answeredCount : state.currentIndex;
    els.score.textContent = state.correctCount + " / " + answered;
  }

  function updateProgress() {
    var total = state.questions.length;
    var current = Math.min(state.currentIndex + 1, total);
    var pct = total ? Math.round((state.currentIndex / total) * 100) : 0;
    els.progressFill.style.width = pct + "%";
    els.progressText.textContent = "문제 " + current + " / " + total;
  }

  function loadQuiz() {
    showStatus("문제를 불러오는 중...");

    fetch(DATA_ENDPOINT, { credentials: "same-origin" })
      .then(function (res) {
        return res.json();
      })
      .then(function (data) {
        if (!data || data.success !== true || !Array.isArray(data.items) || data.items.length === 0) {
          var msg = (data && data.error) ? data.error : "문제를 불러오지 못했습니다.";
          showStatus(msg);
          return;
        }
        state.questions = data.items;
        state.currentIndex = 0;
        state.correctCount = 0;
        if (data.library_name) {
          els.subtitle.textContent = "[" + data.library_name + "] 표지 이미지를 보고 책 제목을 맞혀보세요.";
        }
        els.status.style.display = "none";
        els.result.style.display = "none";
        els.quizArea.style.display = "block";
        renderQuestion();
      })
      .catch(function (err) {
        showStatus("문제를 불러오는 중 오류가 발생했습니다: " + err);
      });
  }

  function renderQuestion() {
    state.answered = false;
    var q = state.questions[state.currentIndex];

    updateProgress();
    updateScoreboard();

    els.coverImg.src = q.cover;
    els.coverImg.alt = "표지 이미지";

    els.feedback.style.display = "none";
    els.feedback.className = "bq-feedback";
    els.nextBtn.style.display = "none";

    els.choices.innerHTML = "";
    (q.choices || []).forEach(function (choice, idx) {
      var btn = document.createElement("button");
      btn.className = "bq-choice-btn";
      btn.type = "button";
      btn.textContent = choice.text;
      btn.dataset.correct = choice.correct ? "1" : "0";
      btn.addEventListener("click", function () {
        onChoiceClick(btn, choice);
      });
      els.choices.appendChild(btn);
    });
  }

  function onChoiceClick(btn, choice) {
    if (state.answered) {
      return;
    }
    state.answered = true;

    var buttons = els.choices.querySelectorAll(".bq-choice-btn");
    buttons.forEach(function (b) {
      b.disabled = true;
      if (b.dataset.correct === "1") {
        b.classList.add("bq-choice-correct");
      }
    });

    if (choice.correct) {
      state.correctCount += 1;
      btn.classList.add("bq-choice-correct");
      els.feedback.textContent = "정답입니다!";
      els.feedback.className = "bq-feedback bq-feedback-correct";
    } else {
      btn.classList.add("bq-choice-wrong");
      els.feedback.textContent = "오답입니다.";
      els.feedback.className = "bq-feedback bq-feedback-wrong";
    }
    els.feedback.style.display = "block";

    updateScoreboard(state.currentIndex + 1);

    if (state.currentIndex + 1 >= state.questions.length) {
      els.nextBtn.textContent = "결과 보기";
      var icon = document.createElement("i");
      icon.className = "fa-solid fa-flag-checkered";
      els.nextBtn.innerHTML = "";
      els.nextBtn.appendChild(document.createTextNode("결과 보기 "));
      els.nextBtn.appendChild(icon);
    } else {
      els.nextBtn.innerHTML = "";
      els.nextBtn.appendChild(document.createTextNode("다음 문제 "));
      var arrowIcon = document.createElement("i");
      arrowIcon.className = "fa-solid fa-arrow-right";
      els.nextBtn.appendChild(arrowIcon);
    }
    els.nextBtn.style.display = "inline-flex";
  }

  function onNextClick() {
    state.currentIndex += 1;
    if (state.currentIndex >= state.questions.length) {
      showResult();
    } else {
      renderQuestion();
    }
  }

  function showResult() {
    els.quizArea.style.display = "none";
    els.result.style.display = "flex";
    els.resultScore.textContent = state.correctCount + " / " + state.questions.length;
  }

  function init() {
    cacheEls();
    els.nextBtn.addEventListener("click", onNextClick);
    els.restartBtn.addEventListener("click", loadQuiz);
    loadQuiz();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
