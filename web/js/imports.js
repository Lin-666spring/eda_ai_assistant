// ═══════════════════════════════════════════
//  Imports & Panels —— P1-6 阶段C 自 app.js 拆出（原 2015-2138 行）
//  图片预览 / BOM·PCB·坐标文件导入 / renderBOMTable / 右侧面板 Tab
//  13 个模块按原文件顺序在 index.html 加载；顺序不可调换：
//  各文件按序拼接（去本头注释）与原 app.js 字节级一致。
// ═══════════════════════════════════════════

// ═══════════ Image Handling ═══════════

function showImagePreview(dataUrl) {
  document.getElementById('imagePreviewThumb').src = dataUrl;
  document.getElementById('imagePreviewBar').style.display = 'flex';
}
function hideImagePreview() {
  document.getElementById('imagePreviewBar').style.display = 'none';
}
function removeImage() {
  currentImage = null; hideImagePreview();
  document.getElementById('imageFileInput').value = '';
}
function onImageFileSelected(input) {
  const file = input.files[0];
  if (!file) return;
  const reader = new FileReader();
  reader.onload = e => { currentImage = e.target.result; showImagePreview(currentImage); };
  reader.readAsDataURL(file);
  input.value = '';
}

// ═══════════ File Imports ═══════════

function onFileSelected(type, input) {
  const file = input.files[0];
  if (!file) return;
  const reader = new FileReader();
  reader.onload = async function(e) {
    const bytes = new Uint8Array(e.target.result);
    // 分块转二进制串：.epro2 工程动辄几 MB，逐字节 `binary +=` 是 O(n²)，
    // 导入时会把整个界面卡住
    let binary = '';
    const CHUNK = 0x8000;
    for (let i = 0; i < bytes.length; i += CHUNK) {
      binary += String.fromCharCode.apply(null, bytes.subarray(i, i + CHUNK));
    }
    const b64 = btoa(binary);
    setStatus('加载中...');
    try {
      if (type === 'bom') {
        const resp = await eel.import_bom_file(file.name, b64)();
        if (resp.ok) { appendSystem(resp.msg); renderBOMTable(resp.items); setStatus(`已加载 BOM (${resp.count} 条)`); showDesignSuggestions(); }
        else { appendTip(resp.msg, 'error'); setStatus('加载失败'); }
      } else if (type === 'pcb') {
        // .epro2 是立创 V3 工程，一次导入同时拿到 BOM + PCB
        const isProject = /\.epro2$/i.test(file.name) && typeof eel.import_project_file === 'function';
        const resp = isProject
          ? await eel.import_project_file(file.name, b64)()
          : await eel.import_pcb_file(file.name, b64)();
        if (resp.ok) {
          appendSystem(resp.msg);
          if (resp.items && resp.items.length) renderBOMTable(resp.items);
          setStatus(isProject ? `已加载工程 (${resp.count} 行 BOM)` : `已加载 PCB`);
        }
        else { appendTip(resp.msg, 'error'); setStatus('加载失败'); }
      } else if (type === 'pos') {
        const resp = await eel.import_pos_file(file.name, b64)();
        if (resp.ok) { appendSystem(resp.msg); setStatus('已加载坐标'); }
        else { appendTip(resp.msg, 'error'); setStatus('加载失败'); }
      }
    } catch(err) { appendTip('导入失败: ' + err, 'error'); setStatus('导入失败'); }
    // 数据到位 → 工具箱里「需先导入 BOM」的徽标要立刻变成可用
    await refreshToolCatalog();
    input.value = '';
  };
  reader.readAsArrayBuffer(file);
}

function renderBOMTable(items) {
  const tbody = document.querySelector('#bomTable tbody');
  tbody.innerHTML = items.map((item, i) => `
    <tr>
      <td style="color:var(--text-muted);text-align:right;padding-right:8px;width:28px">${i + 1}</td>
      <td>${escapeHtml(item.reference)}</td>
      <td>${escapeHtml(item.value)}</td>
      <td>${escapeHtml(item.package)}</td>
      <td>${escapeHtml(item.part_number)}</td>
      <td style="text-align:right">${item.quantity}</td>
    </tr>
  `).join('');
  document.getElementById('bomEmpty').style.display = items.length ? 'none' : 'flex';
}

// ═══════════ Panel Tabs ═══════════

function switchTab(name) {
  document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
  document.querySelectorAll('.tab-panel').forEach(p => p.classList.remove('active'));
  const btn = document.querySelector(`[data-tab="${name}"]`);
  if (btn) btn.classList.add('active');
  const panel = document.getElementById(`tab-${name}`);
  if (panel) panel.classList.add('active');
  // Show heatmap section when review tab is active
  var hs = document.getElementById('drcHeatmapSection');
  if (hs) hs.style.display = (name === 'review') ? 'block' : 'none';
}

function toggleRightPanel() {
  const panel = document.getElementById('rightPanel');
  if (!panel) return;
  const collapsed = panel.classList.toggle('collapsed');
  _syncPanelToggle(collapsed);
}

/** 确保右面板展开（工具/快捷入口跳转时用） */
function openRightPanel() {
  const panel = document.getElementById('rightPanel');
  if (!panel || !panel.classList.contains('collapsed')) return;
  panel.classList.remove('collapsed');
  _syncPanelToggle(false);
}

function _syncPanelToggle(collapsed) {
  // 折叠按钮只剩顶栏一个（旧的悬浮圆钮会压住入口卡片，已移除）
  const btn = document.getElementById('panelToggleTop');
  if (btn) {
    btn.classList.toggle('active', !collapsed);
    btn.title = collapsed ? '展开任务面板' : '折叠任务面板';
  }
  const panel = document.getElementById('rightPanel');
  if (panel) panel.setAttribute('aria-expanded', String(!collapsed));
}

