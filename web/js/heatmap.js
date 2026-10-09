// ═══════════════════════════════════════════
//  DRC Heatmap —— P1-6 阶段C 自 app.js 拆出（原 3099-3242 行）
//  DRC 热力图（ECharts 网格渲染与刷新）
//  13 个模块按原文件顺序在 index.html 加载；顺序不可调换：
//  各文件按序拼接（去本头注释）与原 app.js 字节级一致。
// ═══════════════════════════════════════════

// ═══════════ DRC Heatmap ═══════════

var drcHeatmapChart = null;
var _heatmapResizeHandler = null;

// 热力图空状态文案：后端会说明「为什么画不出来」，别一律甩一句"无数据"
function heatmapEmptyText(payload) {
  switch (payload && payload.reason) {
    case 'no_data':      return '还没有设计数据 — 请先导入 BOM 或工程文件';
    case 'no_positions': return '无元件坐标 — 请导入 PCB 文件或坐标文件(Pick & Place)后重试';
    case 'no_violations':return '规则检查通过，没有违规可统计';
    case 'unmapped':     return '发现的违规没有关联到元件位号（多为网络/板级问题）';
    default:             return '无元件坐标 — 请导入 PCB 文件或坐标文件(Pick & Place)后重试';
  }
}

async function loadDrcHeatmap() {
  var section = document.getElementById('drcHeatmapSection');
  var chartDom = document.getElementById('drcHeatmapChart');
  var emptyHint = document.getElementById('drcHeatmapEmpty');
  var holder = document.getElementById('drcHeatmapLoading');
  var btn = document.querySelector('.heatmap-load-btn');
  var descEl = document.getElementById('drcHeatmapDesc');
  var gridSel = document.getElementById('drcHeatmapGrid');
  var gridMm = gridSel ? (parseFloat(gridSel.value) || 5) : 5;
  if (!section || !chartDom) return;

  section.style.display = 'block';
  emptyHint.style.display = 'none';
  // 统计要遍历全量违规 → 先上占位动效，别让 300px 高度空着
  chartDom.style.display = 'none';
  if (holder) holder.style.display = 'flex';
  _btnLoading(btn, '统计中');
  setStatus('统计违规热力图…');

  try {
    var raw = await eel.get_drc_heatmap(gridMm)();
    var data = JSON.parse(raw);
    if (!data.ok || !data.data || !data.data.length) {
      chartDom.style.display = 'none';
      emptyHint.textContent = heatmapEmptyText(data);
      emptyHint.style.display = 'block';
      if (descEl) descEl.textContent = '网格 ' + gridMm + 'mm · 无可绘制数据';
      return;
    }
    chartDom.style.display = 'block';
    renderDrcHeatmap(chartDom, data.data, data);
    if (descEl) {
      // 数据来源写清楚：PCB 文件自带的坐标 vs 单独导入的坐标文件
      descEl.textContent = '网格 ' + (data.grid_size_mm || gridMm) + 'mm · 位置来源：'
        + (data.source === 'pcb' ? 'PCB 元件坐标' : '坐标文件(Pick & Place)')
        + ' · ' + data.mapped + ' 处计数 / ' + data.violation_count + ' 条违规';
    }
  } catch (e) {
    console.error('Heatmap load failed:', e);
    emptyHint.textContent = '热力图统计失败 — 详见控制台日志';
    emptyHint.style.display = 'block';
    chartDom.style.display = 'none';
  } finally {
    if (holder) holder.style.display = 'none';
    _btnLoaded(btn);
    setStatus('就绪');
  }
}

function renderDrcHeatmap(chartDom, gridData, meta) {
  if (!window.echarts) {
    console.warn('ECharts not loaded');
    return;
  }
  if (drcHeatmapChart) drcHeatmapChart.dispose();

  // 图表主题跟随当前外观（默认浅色），不要写死 dark
  var chartTheme = document.body.getAttribute('data-theme') === 'dark' ? 'dark' : null;
  drcHeatmapChart = echarts.init(chartDom, chartTheme);
  var xs = gridData.map(function(d) { return d[0]; });
  var ys = gridData.map(function(d) { return d[1]; });
  var counts = gridData.map(function(d) { return d[2]; });
  var maxCount = Math.max.apply(null, counts);

  // 网格序号 → 真实 mm：有 meta 就把格子换算回坐标区间，tooltip 才说得清位置
  var gridMm = (meta && meta.grid_size_mm) || 5;
  var hasOrigin = meta && typeof meta.x_min === 'number' && typeof meta.y_min === 'number';

  var option = {
    tooltip: {
      formatter: function(p) {
        var head = '网格 [' + p.value[0] + ', ' + p.value[1] + ']<br/>违规数: <b>' + p.value[2] + '</b>';
        if (!hasOrigin) return head;
        var x0 = meta.x_min + p.value[0] * gridMm;
        var y0 = meta.y_min + p.value[1] * gridMm;
        return head
          + '<br/>X ' + x0.toFixed(1) + '–' + (x0 + gridMm).toFixed(1) + ' mm'
          + '<br/>Y ' + y0.toFixed(1) + '–' + (y0 + gridMm).toFixed(1) + ' mm';
      }
    },
    grid: { left: 60, right: 20, top: 20, bottom: 40 },
    xAxis: {
      type: 'category',
      data: Array.from(new Set(xs)).sort(function(a, b) { return a - b; }),
      name: 'X 网格 (' + gridMm + 'mm)',
      nameLocation: 'center',
      nameGap: 25,
      axisLabel: { fontSize: 9 }
    },
    yAxis: {
      type: 'category',
      data: Array.from(new Set(ys)).sort(function(a, b) { return a - b; }),
      name: 'Y 网格 (' + gridMm + 'mm)',
      nameLocation: 'center',
      nameGap: 45,
      axisLabel: { fontSize: 9 }
    },
    visualMap: {
      min: 0,
      max: maxCount,
      calculable: true,
      orient: 'vertical',
      right: 5,
      top: 'center',
      inRange: { color: ['#1a2a4a', '#4a90d9', '#e6a23c', '#e74c3c'] },
      text: ['高', '低'],
      textStyle: { color: '#aaa' }
    },
    series: [{
      type: 'heatmap',
      data: gridData,
      label: { show: true, fontSize: 9, color: '#ccc' },
      emphasis: {
        itemStyle: {
          shadowBlur: 10,
          shadowColor: 'rgba(255,255,255,0.3)'
        }
      }
    }]
  };

  drcHeatmapChart.setOption(option);
  // 每次重绘先摘掉旧监听再挂新的 —— 否则监听器随重绘次数线性堆积
  if (_heatmapResizeHandler) window.removeEventListener('resize', _heatmapResizeHandler);
  _heatmapResizeHandler = function() { drcHeatmapChart && drcHeatmapChart.resize(); };
  window.addEventListener('resize', _heatmapResizeHandler);
}

