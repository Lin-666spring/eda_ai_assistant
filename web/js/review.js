// ═══════════════════════════════════════════
//  Multi-Agent Review —— P1-6 阶段C 自 app.js 拆出（原 2907-3098 行）
//  多智能体审查面板 / 雷达图 / Agent 卡片 / 路线图
//  13 个模块按原文件顺序在 index.html 加载；顺序不可调换：
//  各文件按序拼接（去本头注释）与原 app.js 字节级一致。
// ═══════════════════════════════════════════

// ══════════════════════════════════════════
//  Multi-Agent Review
// ══════════════════════════════════════════

// ── 审查进行中的骨架屏（5 位专家 = 5 张占位卡）──
let _reviewLoadingTimer = null;
let _reviewLoadingTextEl = null;

function _showReviewLoading() {
  const box = document.getElementById('reviewLoading');
  if (!box) return;
  const phrases = ['正在解析设计数据', '5 位专家并行评审中', '正在汇总共识意见', '正在生成改进路线图'];
  box.innerHTML =
    '<div class="review-loading-head">' +
      '<span class="think-dots"><i></i><i></i><i></i></span>' +
      `<span class="review-loading-text">${phrases[0]}</span>` +
    '</div>' +
    Array.from({ length: 5 }, () =>
      '<div class="skeleton-card">' +
        '<div class="skeleton-line h12 w45"></div>' +
        '<div class="skeleton-line w90"></div>' +
        '<div class="skeleton-line w70"></div>' +
      '</div>').join('');
  box.style.display = 'block';
  _reviewLoadingTextEl = box.querySelector('.review-loading-text');
  let i = 0;
  clearInterval(_reviewLoadingTimer);
  _reviewLoadingTimer = setInterval(() => {
    i = (i + 1) % phrases.length;
    if (_reviewLoadingTextEl) _reviewLoadingTextEl.textContent = phrases[i];
  }, 2200);
}

function _hideReviewLoading() {
  clearInterval(_reviewLoadingTimer);
  _reviewLoadingTimer = null;
  _reviewLoadingTextEl = null;
  const box = document.getElementById('reviewLoading');
  if (box) { box.style.display = 'none'; box.innerHTML = ''; }
}

let _reviewRunning = false;

async function runMultiAgentReview() {
  // 按钮在审查开始后就被藏起来了，但 Ctrl+R 快捷键仍可触发 —— 重入会
  // 同时跑两轮审查（双倍 LLM 花费 + 渲染互相覆盖），必须挡住
  if (_reviewRunning) { showToast('审查正在进行中', 'info'); return; }
  _reviewRunning = true;
  const startBtn = document.querySelector('.review-start-btn');
  const resultDiv = document.getElementById('reviewResult');
  const emptyHint = document.getElementById('reviewEmpty');
  if (startBtn) startBtn.disabled = true;
  if (startBtn) startBtn.style.display = 'none';   // 让位给骨架屏，别并存两个「启动」入口
  if (emptyHint) emptyHint.style.display = 'none';
  setStatus('多智能体审查中...');
  _showReviewLoading();

  try {
    const raw = await eel.review_design_multi_agent()();
    const data = JSON.parse(raw);
    if (data.error) {
      _hideReviewLoading(); setStatus('审查失败');
      if (startBtn) { startBtn.disabled = false; startBtn.style.display = ''; }
      if (emptyHint) emptyHint.style.display = '';
      showToast(data.error, 'error'); return;
    }
    renderReviewResult(data);
    _hideReviewLoading();
    if (resultDiv) resultDiv.style.display = 'block';
    if (startBtn) startBtn.style.display = 'none';
    setStatus('审查完成');
  } catch (e) {
    console.error(e);
    _hideReviewLoading(); setStatus('审查失败');
    if (startBtn) { startBtn.disabled = false; startBtn.style.display = ''; }
    if (emptyHint) emptyHint.style.display = '';
  } finally {
    _reviewRunning = false;
  }
}

function renderReviewResult(data) {
  if (data.radar_data) drawRadarChart(data.radar_data);
  const ge = document.getElementById('reviewGrade');
  const se = document.getElementById('reviewScore');
  if (ge) { ge.textContent = data.overall_grade || '?'; ge.style.color = _gradeColor(data.overall_score); }
  if (se) se.textContent = data.overall_score != null ? data.overall_score : '?';
  const ring = document.getElementById('scoreRing');
  if (ring && data.overall_score != null) {
    const c = 2 * Math.PI * 52;
    const s = Math.max(0, Math.min(data.overall_score, 100));
    ring.style.strokeDasharray = c;
    ring.style.strokeDashoffset = c * (1 - s / 100);
    ring.style.stroke = _gradeColor(data.overall_score);
  }
  const ce = document.getElementById('reviewConsensus');
  if (ce) ce.innerHTML = renderMarkdown(data.consensus);
  _renderAgentCards(data.agents);
  _renderRoadmap(data.improvement_roadmap);
}

function drawRadarChart(data) {
  var c = document.getElementById('radarChart');
  if (!c || !data || data.length < 3) return;
  var ctx = c.getContext('2d'), w = c.width, h = c.height, cx = w / 2, cy = h / 2;
  var n = data.length, maxR = Math.min(cx, cy) - 20;
  var rs = getComputedStyle(document.body);
  var accent = (rs.getPropertyValue('--accent') || '#2565fe').trim();
  var muted = (rs.getPropertyValue('--text-muted') || '#8b919c').trim();
  var grid = (rs.getPropertyValue('--border') || '#e4e7ec').trim();
  ctx.clearRect(0, 0, w, h);
  ctx.strokeStyle = grid; ctx.lineWidth = 0.5;
  // grid
  for (var lv = 1; lv <= 4; lv++) {
    var r = (maxR / 4) * lv; ctx.beginPath();
    for (var i = 0; i < n; i++) {
      var a = (Math.PI * 2 / n) * i - Math.PI / 2;
      var x = cx + r * Math.cos(a), y = cy + r * Math.sin(a);
      i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
    }
    ctx.closePath(); ctx.stroke();
  }
  // axes
  for (var i = 0; i < n; i++) {
    var a = (Math.PI * 2 / n) * i - Math.PI / 2;
    ctx.beginPath(); ctx.moveTo(cx, cy);
    ctx.lineTo(cx + maxR * Math.cos(a), cy + maxR * Math.sin(a));
    ctx.stroke();
  }
  // polygon
  ctx.beginPath();
  for (var i = 0; i < n; i++) {
    var d = data[i], r = (d.score / 100) * maxR;
    var a = (Math.PI * 2 / n) * i - Math.PI / 2;
    var x = cx + r * Math.cos(a), y = cy + r * Math.sin(a);
    i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
  }
  ctx.closePath(); ctx.fillStyle = 'rgba(91,141,239,0.12)'; ctx.fill();
  ctx.strokeStyle = accent; ctx.lineWidth = 1.5; ctx.stroke();
  // dots + labels
  ctx.font = '9px sans-serif'; ctx.textAlign = 'center'; ctx.fillStyle = muted;
  for (var i = 0; i < n; i++) {
    var d = data[i], r = (d.score / 100) * maxR;
    var a = (Math.PI * 2 / n) * i - Math.PI / 2;
    ctx.beginPath(); ctx.arc(cx + r * Math.cos(a), cy + r * Math.sin(a), 3, 0, Math.PI * 2);
    ctx.fillStyle = accent; ctx.fill();
    ctx.fillText(d.label, cx + (maxR + 14) * Math.cos(a), cy + (maxR + 14) * Math.sin(a) + 3);
  }
}

function _renderAgentCards(agents) {
  var ct = document.getElementById('reviewAgentCards');
  if (!ct || !agents) return; ct.innerHTML = '';
  var order = ['power', 'signal', 'thermal', 'emc', 'dfm'];
  for (var o = 0; o < order.length; o++) {
    var a = agents[order[o]]; if (!a) continue;
    var hasCrit = a.findings && a.findings.some(function(f) { return f.severity === 'critical'; });
    var cls = hasCrit ? 'critical' : (a.score >= 90 ? 'clean' : 'major');
    var fhtml = '';
    if (a.findings && a.findings.length) {
      fhtml = a.findings.map(function(f) {
        // findings 来自 LLM 输出（review_with_llm），与聊天气泡同一口径：先转义再进 DOM
        var sev = String(f.severity || 'info').replace(/[^a-z-]/gi, '');
        return '<div class="review-finding sev-' + sev + '">' + escapeHtml(f.title)
          + (f.suggestion ? ' — ' + escapeHtml(f.suggestion) : '') + '</div>';
      }).join('');
    }
    ct.innerHTML += '<div class="review-agent-card ' + cls + '">' +
      '<div class="review-agent-header"><span>' + escapeHtml(a.emoji || '') + '</span> ' +
      '<span class="review-agent-name">' + escapeHtml(a.name) + '</span>' +
      '<span class="review-agent-score">' + (a.score != null ? a.score.toFixed(1) : '?') + ' 分</span></div>' +
      '<div class="review-agent-summary">' + escapeHtml(a.summary || '') + '</div>' +
      (fhtml ? '<div class="review-agent-findings">' + fhtml + '</div>' : '') + '</div>';
  }
}

function _renderRoadmap(items) {
  var ct = document.getElementById('reviewRoadmap');
  if (!ct || !items || !items.length) return;
  ct.innerHTML = '<h3> 改进路线图</h3>' + items.map(function(i) {
    return '<div class="review-roadmap-item">' + escapeHtml(i) + '</div>';
  }).join('');
}

function _gradeColor(score) {
  if (score == null) return '#888';
  if (score >= 88) return '#2ecc71';
  if (score >= 70) return '#2565fe';
  if (score >= 55) return '#e67e22';
  return '#e74c3c';
}

