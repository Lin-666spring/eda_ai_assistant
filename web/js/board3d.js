// ═══════════════════════════════════════════
//  Board3D —— 3D 板卡预览（three.js r128 · vendor 本地 · 离线安全）
//  ─────────────────────────────────────────
//  数据来自后端 get_board_3d_data（ctx.pcb_data 序列化，坐标绝对 mm）：
//    · 板框：outline_rings_mm 真实轮廓（多环：最大环为外形，内部环为挖孔），
//      没有环时退回 bbox 矩形；ExtrudeGeometry 挤出 1.6mm 板厚
//    · 元件：InstancedMesh 单位盒子 + 每实例缩放/旋转/颜色；B 面挂在板底
//    · 走线：按层分组的 LineSegments（Top 层浮在板面上沿、Bottom 层贴下沿、
//      内层画在中平面半透明）；过孔：InstancedMesh 铜色圆柱贯穿板厚
//    · 违规标记：get_drc_violations 坐标化清单（后端把 location 位号解析成
//      绝对 mm 坐标），同点聚合、按最严重级别着色，悬在板面上方 + 细杆落点，
//      点击标记在徽标里看该位置的违规明细
//  尺寸/颜色是「估算」：.epro2 不含元件实体几何，按封装名（立创封装名自带
//  L7.0-W7.0 尺寸、0402/0603 封装码、CD54 电感码等）+ 位号前缀推断，仅作
//  视觉呈现，不进任何规则判定。
//  工程约束（与 particles.js 同一套纪律）：
//    · three.js 懒加载：首次激活 3D 标签才注入 vendor 脚本，不拖慢启动
//    · 一条 rAF；标签未激活/面板折叠/页面隐藏时休眠，观察器唤醒
//    · DPR 封顶 2；alpha 透明背景直接透出面板底色，深浅色主题零适配代码
//    · 不自动旋转（用户驱动的轨道交互，reduced-motion 天然安全）
// ═══════════════════════════════════════════
(function () {
  'use strict';

  var dom = {};            // 缓存用到的节点
  var state = {
    loaded: false,         // 数据已拉取过（首次激活自动拉一次）
    threeReady: false,
    building: false,
    scene: null, renderer: null, camera: null, controls: null,
    compsMesh: null, comps: [],        // comps: 后端元件数组（与实例下标对应）
    traceGroups: [], viaMesh: null,
    showTraces: true, showVias: true,
    // 违规标记层：懒拉取（首次点开「违规」才请求），载荷缓存到 drcPayload，
    // 场景（板框/坐标原点）就绪后落点；刷新按钮会一并丢弃缓存
    showDrc: false, drcLoaded: false, drcBuilding: false, drcPayload: null,
    drcMesh: null, drcStems: null, drcSpots: [], drcFrame: null,
    raf: 0, idle: 0,
    downX: 0, downY: 0,
  };

  // ═══════════ 封装尺寸/颜色估算（纯展示用途）═══════════

  var CHIP_MM = {                          // 英制封装码 → [长, 宽, 高] mm
    '008004': [0.25, 0.125, 0.10], '01005': [0.40, 0.20, 0.12],
    '0201': [0.60, 0.30, 0.23], '0402': [1.00, 0.50, 0.35],
    '0603': [1.60, 0.80, 0.45], '0805': [2.00, 1.25, 0.50],
    '1206': [3.20, 1.60, 0.55], '1210': [3.20, 2.50, 0.55],
    '1812': [4.50, 3.20, 0.55], '2010': [5.00, 2.50, 0.60],
    '2512': [6.30, 3.20, 0.60],
  };
  // 家族正则（封装名匹配）→ [长, 宽, 高]； pins 型家族在函数里按脚数展开
  var FAMILY_MM = [
    [/SOT[- ]?563|SOT[- ]?883/i, [1.0, 0.6, 0.5]],
    [/SOT[- ]?323/i, [2.0, 1.25, 0.9]],
    [/SOT[- ]?23/i, [2.9, 1.3, 1.1]],
    [/SOT[- ]?89/i, [4.5, 2.5, 1.6]],
    [/SOT[- ]?223/i, [6.5, 3.5, 1.6]],
    [/TO[- ]?92/i, [4.6, 4.6, 5.2]],
    [/TO[- ]?252|DPAK/i, [6.5, 5.3, 2.4]],
    [/TO[- ]?263|D2PAK/i, [10.2, 9.0, 4.6]],
    [/TO[- ]?220/i, [10.0, 4.5, 9.0]],
    [/TYPE[- ]?C/i, [8.9, 7.3, 3.2]],
    [/USB/i, [12.0, 12.0, 5.5]],
    [/TF[- ]|MICRO[- ]?SD|SD[- ]?CARD|SIM/i, [12.0, 13.0, 1.5]],
    [/DC005|DC[- ]?JACK|BARREL/i, [9.0, 8.0, 11.0]],
    [/HDMI/i, [11.5, 9.0, 3.2]],
    [/XTAL|CRYSTAL|OSC/i, [5.0, 3.2, 1.2]],
    [/3225/i, [3.2, 2.5, 0.8]],
    [/5032/i, [5.0, 3.2, 1.2]],
    [/WROOM/i, [18.0, 25.5, 3.1]],
    [/QFN/i, [5.0, 5.0, 0.9]],
    [/QFP|LQFP|TQFP/i, [12.0, 12.0, 1.6]],
    [/BGA/i, [8.0, 8.0, 1.0]],
  ];
  // 位号前缀兜底 → [尺寸, 颜色, 类别]；封装名认不出来时用
  var PREFIX_FALLBACK = {
    R: [[1.6, 0.8, 0.5], 0xc8a06c], C: [[1.6, 0.8, 0.6], 0x9c7355],
    L: [[3.0, 3.0, 2.0], 0x8a8f98], U: [[5.0, 5.0, 1.2], 0x30343c],
    Q: [[5.0, 5.0, 1.2], 0x30343c], D: [[1.6, 0.8, 0.5], 0xb03038],
    J: [[8.0, 8.0, 4.0], 0x8d939e], P: [[8.0, 8.0, 4.0], 0x8d939e],
    CN: [[8.0, 8.0, 4.0], 0x8d939e], Y: [[5.0, 3.2, 1.2], 0xb9c1cc],
    X: [[5.0, 3.2, 1.2], 0xb9c1cc], SW: [[6.0, 6.0, 3.5], 0x4a4f57],
    K: [[8.0, 6.5, 8.0], 0x4a5560], F: [[3.2, 1.6, 0.6], 0xc9a86c],
    TP: [[0.9, 0.9, 0.9], 0xc9a86c], MH: [[2.0, 2.0, 0.3], 0xb87333],
    H: [[2.0, 2.0, 0.3], 0xb87333],
  };
  var DEFAULT_PART = [[2.5, 2.0, 1.0], 0x565b64];

  function pinBody(pitch, pins, crossW, h, padMargin) {
    // DIP/SOP 族：体长 = 半边脚距跨度 + 两端余量
    var span = (Math.max(2, Math.round(pins / 2)) - 1) * pitch;
    return [span + padMargin, crossW, h];
  }

  function estimatePart(comp) {
    var fp = String(comp.footprint_name || '');
    var ref = String(comp.ref || '');
    var val = String(comp.value || '');
    var prefix = (/^[A-Za-z]+/.exec(ref) || ['X'])[0].toUpperCase();
    var m;

    // 1) 立创封装名自带的 L7.0-W7.0 显式尺寸（QFP/QFN/BGA/SIP 等大部头）
    m = /L(\d+(?:\.\d+)?)\s*[-_ ]?\s*W(\d+(?:\.\d+)?)\s*[-_ ]?P?/i.exec(fp);
    if (m) {
      var len = parseFloat(m[1]), wid = parseFloat(m[2]);
      if (len > 0.3 && len < 60 && wid > 0.3 && wid < 60) {
        var hIc = /BGA/i.test(fp) ? 1.0 : /QFN|DFN|SON/i.test(fp) ? 0.9 : 1.6;
        return [len, wid, hIc, 0x30343c];
      }
    }
    // 2) 英制贴片码（C0201_2 / R0603 之类，避免匹配进位号数字）
    m = /(?:^|[^0-9])(008004|01005|0201|0402|0603|0805|1206|1210|1812|2010|2512)(?=[^0-9]|$)/.exec(fp);
    if (m && CHIP_MM[m[1]]) {
      var chip = CHIP_MM[m[1]];
      var chipColor = prefix === 'R' ? 0xc8a06c : prefix === 'L' ? 0x8a8f98 : 0x9c7355;
      return [chip[0], chip[1], chip[2], chipColor];
    }
    // 3) 电感/电解电容的 CD 尺寸码：CD54→5.4mm、CD106→10.6mm（位号消歧：
    //    L 开头是功率电感（扁圆），C 开头按铝电解（高圆柱）处理）
    m = /CD(\d{2,3})/.exec(fp);
    if (m) {
      var d = parseInt(m[1], 10) / 10;
      if (d >= 1 && d <= 16) {
        if (prefix === 'L') return [d, d, d * 0.6, 0x8a8f98];
        return [d, d, Math.max(d, 5.0), 0x3d4148];
      }
    }
    // 4) 大容量电容（值里 ≥47uF 大概率电解/钽，个头要立起来）
    m = /(\d+(?:\.\d+)?)\s*[uµ]F/i.exec(val);
    if (m && prefix === 'C' && parseFloat(m[1]) >= 47) {
      return [6.3, 6.3, 5.8, 0x3d4148];
    }
    // 5) 家族正则表
    for (var i = 0; i < FAMILY_MM.length; i++) {
      if (FAMILY_MM[i][0].test(fp)) return FAMILY_MM[i][1].concat([familyColor(fp)]);
    }
    // 6) 脚数展开族：DIP / SOP / SOIC / TSSOP / MSOP / SSOP
    m = /(DIP|SOP|SOIC|SSOP|TSSOP|MSOP)[- ]?(\d+)/i.exec(fp);
    if (m) {
      var pins = parseInt(m[2], 10);
      if (m[1].toUpperCase() === 'DIP') return pinBody(2.54, pins, pins >= 24 ? 10.2 : 6.35, 3.3, 2.2).concat([0x30343c]);
      return pinBody(1.27, pins, 3.9, 1.75, 1.1).concat([0x30343c]);
    }
    // 7) 位号前缀兜底
    var fb = PREFIX_FALLBACK[prefix] || PREFIX_FALLBACK[ref.charAt(0)] || DEFAULT_PART;
    return fb[0].concat([fb[1]]);
  }

  function familyColor(fp) {
    if (/USB|TYPE[- ]?C|HDMI|DC005|DC[- ]?JACK|BARREL|TF[- ]|SD[- ]?CARD|SIM|HDR|HEADER|CONN/i.test(fp)) return 0x8d939e;
    if (/XTAL|CRYSTAL|OSC/i.test(fp)) return 0xb9c1cc;
    if (/WROOM/i.test(fp)) return 0x1f3a5f;
    return 0x30343c;
  }

  // ═══════════ three.js 懒加载 ═══════════

  var threeLoad = null;
  function ensureThree() {
    if (state.threeReady) return Promise.resolve();
    if (threeLoad) return threeLoad;
    threeLoad = new Promise(function (resolve, reject) {
      function inject(src, next) {
        var s = document.createElement('script');
        s.src = src;
        s.onload = next;
        s.onerror = function () { threeLoad = null; reject(new Error('load fail: ' + src)); };
        document.head.appendChild(s);
      }
      // 相对 index.html 解析（与 echarts 的引用同一路径口径），不从本模块
      // src 推导 —— 那样会得到 js/vendor/ 这个不存在的目录
      inject('vendor/three.min.js', function () {
        inject('vendor/OrbitControls.js', function () {
          state.threeReady = true;
          resolve();
        });
      });
    });
    return threeLoad;
  }

  // ═══════════ 场景构建 ═══════════

  var BOARD_T = 1.6;   // 板厚 mm（.epro2 无板厚信息，按四/六层板常规值）

  function clearScene() {
    if (!state.scene) return;
    var group = state.scene.getObjectByName('boardGroup');
    if (group) {
      state.scene.remove(group);
      group.traverse(function (o) {
        if (o.geometry) o.geometry.dispose();
        if (o.material) (Array.isArray(o.material) ? o.material : [o.material]).forEach(function (mt) { mt.dispose(); });
      });
    }
    state.compsMesh = null; state.comps = [];
    state.traceGroups = []; state.viaMesh = null;
    state.drcMesh = null; state.drcStems = null; state.drcSpots = []; state.drcFrame = null;
  }

  function ringToBounds(ring) {
    var x0 = 1e9, y0 = 1e9, x1 = -1e9, y1 = -1e9;
    for (var i = 0; i < ring.length; i++) {
      x0 = Math.min(x0, ring[i][0]); y0 = Math.min(y0, ring[i][1]);
      x1 = Math.max(x1, ring[i][0]); y1 = Math.max(y1, ring[i][1]);
    }
    return [x0, y0, x1, y1];
  }

  function buildBoard(board, fallbackExtent) {
    var bo = board || {};
    var b = bo.rings && bo.rings.length ? bo.rings : null;
    var bbox = bo.min_x_mm != null
      ? [bo.min_x_mm, bo.min_y_mm, bo.max_x_mm, bo.max_y_mm]
      : fallbackExtent;
    if (!bbox) return null;
    var cx = (bbox[0] + bbox[2]) / 2, cy = (bbox[1] + bbox[3]) / 2;
    var THREE = window.THREE;
    var mesh;

    if (b) {
      // 最大环 = 外形；完全落在其包围盒内的小环 = 挖孔
      var outer = b[0], outerBb = ringToBounds(b[0]), outerArea = (outerBb[2] - outerBb[0]) * (outerBb[3] - outerBb[1]);
      for (var i = 1; i < b.length; i++) {
        var bb = ringToBounds(b[i]);
        if ((bb[2] - bb[0]) * (bb[3] - bb[1]) > outerArea) { outer = b[i]; outerBb = bb; outerArea = (bb[2] - bb[0]) * (bb[3] - bb[1]); }
      }
      function toShapePoints(ring) {
        var pts = [];
        for (var k = 0; k < ring.length; k++) {
          var px = ring[k][0] - cx, py = -(ring[k][1] - cy);   // 见 mesh.rotation.x 的坐标映射
          var last = pts[pts.length - 1];
          if (!last || Math.abs(last.x - px) > 1e-4 || Math.abs(last.y - py) > 1e-4) {
            pts.push(new THREE.Vector2(px, py));
          }
        }
        if (pts.length > 2) {
          var f = pts[0], l = pts[pts.length - 1];
          if (Math.abs(f.x - l.x) > 1e-4 || Math.abs(f.y - l.y) > 1e-4) pts.push(f.clone()); // 开放链闭合
        }
        return pts;
      }
      var shape = null, holes = [];
      var outerPts = toShapePoints(outer);
      if (outerPts.length >= 3) {
        shape = new THREE.Shape(outerPts);
        for (var j = 0; j < b.length; j++) {
          if (b[j] === outer) continue;
          var hb = ringToBounds(b[j]);
          var inside = hb[0] >= outerBb[0] - 0.2 && hb[1] >= outerBb[1] - 0.2 &&
                       hb[2] <= outerBb[2] + 0.2 && hb[3] <= outerBb[3] + 0.2;
          var hp = toShapePoints(b[j]);
          if (inside && hp.length >= 3) holes.push(new THREE.Path(hp));
        }
        shape.holes = holes;
      }
      if (shape) {
        var geo = new THREE.ExtrudeGeometry(shape, { depth: BOARD_T, bevelEnabled: false });
        mesh = new THREE.Mesh(geo, [
          new THREE.MeshLambertMaterial({ color: 0x0e5a2e }),  // 阻焊绿
          new THREE.MeshLambertMaterial({ color: 0x0a3f20 }),  // 侧露基材
        ]);
        mesh.rotation.x = -Math.PI / 2;   // XY 形状 → XZ 板面；挤出方向 → +Y
        mesh.position.y = -BOARD_T / 2;
      }
    }
    if (!mesh) {
      var w = Math.max(2, bbox[2] - bbox[0]), h = Math.max(2, bbox[3] - bbox[1]);
      mesh = new THREE.Mesh(
        new THREE.BoxGeometry(w, BOARD_T, h),
        new THREE.MeshLambertMaterial({ color: 0x0e5a2e })
      );
    }
    return { mesh: mesh, cx: cx, cy: cy, w: bbox[2] - bbox[0], h: bbox[3] - bbox[1] };
  }

  function buildComponents(components, frame) {
    if (!components.length || !frame) return null;
    var THREE = window.THREE;
    var list = components.filter(function (c) { return isFinite(c.x) && isFinite(c.y); });
    var geo = new THREE.BoxGeometry(1, 1, 1);
    var mat = new THREE.MeshLambertMaterial({ color: 0xffffff });
    var inst = new THREE.InstancedMesh(geo, mat, list.length);
    var mtx = new THREE.Matrix4(), pos = new THREE.Vector3(),
        quat = new THREE.Quaternion(), sc = new THREE.Vector3(),
        yAxis = new THREE.Vector3(0, 1, 0), col = new THREE.Color();
    for (var i = 0; i < list.length; i++) {
      var c = list[i];
      var est = estimatePart(c);
      var w = est[0], d = est[1], h = est[2];
      var bottom = c.side === 'B';
      pos.set(
        c.x - frame.cx,
        (bottom ? -BOARD_T / 2 - h / 2 : BOARD_T / 2 + h / 2),
        c.y - frame.cy
      );
      var yaw = (bottom ? -1 : 1) * (parseFloat(c.rotation) || 0) * Math.PI / 180;
      quat.setFromAxisAngle(yAxis, yaw);
      sc.set(w, h, d);
      mtx.compose(pos, quat, sc);
      inst.setMatrixAt(i, mtx);
      col.setHex(est[3]);
      inst.setColorAt(i, col);
    }
    inst.instanceMatrix.needsUpdate = true;
    if (inst.instanceColor) inst.instanceColor.needsUpdate = true;
    state.comps = list;
    return inst;
  }

  function buildTraces(traces, frame) {
    var THREE = window.THREE;
    var groups = [];
    if (!traces || !traces.length || !frame) return groups;
    var byLayer = {};
    traces.forEach(function (t) {
      var name = t.layer || '?';
      var y = /top/i.test(name) ? BOARD_T / 2 + 0.012
            : /bottom/i.test(name) ? -BOARD_T / 2 - 0.012 : 0;
      var key = y + '|' + name;
      (byLayer[key] = byLayer[key] || { y: y, name: name, arr: [] }).arr.push(t.segs);
    });
    Object.keys(byLayer).forEach(function (key) {
      var g = byLayer[key];
      var geo = new THREE.BufferGeometry();   // position 由 fillTraceVerts 填充
      var mat = new THREE.LineBasicMaterial({
        color: g.y > 0 ? 0xd98b00 : g.y < 0 ? 0x2a6fd6 : 0x5a6572,
        transparent: true, opacity: g.y === 0 ? 0.28 : 0.85,
      });
      var seg = new THREE.LineSegments(geo, mat);
      seg.userData.layerName = g.name;
      seg.userData.y = g.y;
      seg.userData.rawChunks = g.arr;
      groups.push(seg);
    });
    return groups;
  }

  // 后端 segs 是 [x1,y1,x2,y2,...]，three 需要 [x1,y',z1,x2,y',z2,...]
  function fillTraceVerts(seg, frame) {
    var chunks = seg.userData.rawChunks, y = seg.userData.y;
    var n = 0;
    chunks.forEach(function (a) { n += a.length / 4; });
    var verts = new Float32Array(n * 6);
    var o = 0;
    chunks.forEach(function (a) {
      for (var i = 0; i < a.length; i += 4) {
        verts[o++] = a[i] - frame.cx;     verts[o++] = y; verts[o++] = a[i + 1] - frame.cy;
        verts[o++] = a[i + 2] - frame.cx; verts[o++] = y; verts[o++] = a[i + 3] - frame.cy;
      }
    });
    seg.geometry.setAttribute('position', new THREE.BufferAttribute(verts, 3));
    seg.userData.rawChunks = null;
  }

  function buildVias(vias, frame) {
    if (!vias || !vias.length || !frame) return null;
    var THREE = window.THREE;
    var geo = new THREE.CylinderGeometry(1, 1, BOARD_T + 0.04, 8);
    var mat = new THREE.MeshLambertMaterial({ color: 0xb87333 });
    var inst = new THREE.InstancedMesh(geo, mat, vias.length);
    var mtx = new THREE.Matrix4(), one = new THREE.Quaternion(), sc = new THREE.Vector3();
    for (var i = 0; i < vias.length; i++) {
      var r = Math.max(0.12, (vias[i][2] || 0.5) / 2);
      mtx.compose(
        new THREE.Vector3(vias[i][0] - frame.cx, 0, vias[i][1] - frame.cy),
        one, sc.set(r, 1, r)
      );
      inst.setMatrixAt(i, mtx);
    }
    inst.instanceMatrix.needsUpdate = true;
    return inst;
  }

  // ═══════════ 违规标记层（数据来自 get_drc_violations，坐标绝对 mm）═══════════
  // 每条违规可涉及多个元件 → 多个点；同一点聚合为一个标记（计数 + 最严重
  // 级别着色：error 红 / warning 琥珀 / info 蓝灰），细杆连到板面指示落点。

  var SEV_RANK = { error: 3, warning: 2, info: 1 };
  var SEV_COLOR = { error: 0xd23b3b, warning: 0xd9a100, info: 0x5a6572 };

  function aggregateSpots(items) {
    var byPt = {};
    (items || []).forEach(function (it) {
      (it.coords || []).forEach(function (p) {
        var key = p[0].toFixed(2) + ',' + p[1].toFixed(2);
        var s = byPt[key];
        if (!s) s = byPt[key] = { x: p[0], y: p[1], n: 0, worst: 'info', first: it };
        s.n++;
        if ((SEV_RANK[it.severity] || 1) > (SEV_RANK[s.worst] || 1)) {
          s.worst = it.severity;
          s.first = it;   // 聚合里最严重的一条，点击时优先展示
        }
      });
    });
    return Object.keys(byPt).map(function (k) { return byPt[k]; });
  }

  function buildDrcMarkers(payload, frame, group) {
    var THREE = window.THREE;
    var spots = aggregateSpots(payload.items);
    if (!spots.length || !frame) return;
    var diag = Math.hypot(frame.w, frame.h);
    var r = Math.min(3, Math.max(0.5, diag * 0.012));
    var h = BOARD_T / 2 + Math.max(4, diag * 0.06);   // 悬在板面上方，避开元件主体

    var geo = new THREE.SphereGeometry(1, 12, 10);
    var mat = new THREE.MeshLambertMaterial({ color: 0xffffff });
    var inst = new THREE.InstancedMesh(geo, mat, spots.length);
    var mtx = new THREE.Matrix4(), one = new THREE.Quaternion(),
        sc = new THREE.Vector3(), col = new THREE.Color();
    var stemVerts = new Float32Array(spots.length * 6);
    for (var i = 0; i < spots.length; i++) {
      var s = spots[i];
      mtx.compose(
        new THREE.Vector3(s.x - frame.cx, h, s.y - frame.cy),
        one, sc.set(r, r, r)
      );
      inst.setMatrixAt(i, mtx);
      col.setHex(SEV_COLOR[s.worst] || SEV_COLOR.info);
      inst.setColorAt(i, col);
      var o = i * 6;
      stemVerts[o] = s.x - frame.cx;     stemVerts[o + 1] = BOARD_T / 2 + 0.05; stemVerts[o + 2] = s.y - frame.cy;
      stemVerts[o + 3] = s.x - frame.cx; stemVerts[o + 4] = h - r;              stemVerts[o + 5] = s.y - frame.cy;
    }
    inst.instanceMatrix.needsUpdate = true;
    if (inst.instanceColor) inst.instanceColor.needsUpdate = true;
    inst.visible = state.showDrc;
    group.add(inst);

    var stemGeo = new THREE.BufferGeometry();
    stemGeo.setAttribute('position', new THREE.BufferAttribute(stemVerts, 3));
    var stems = new THREE.LineSegments(stemGeo,
      new THREE.LineBasicMaterial({ color: 0x8a8f98, transparent: true, opacity: 0.4 }));
    stems.visible = state.showDrc;
    group.add(stems);

    state.drcMesh = inst;
    state.drcStems = stems;
    state.drcSpots = spots;
  }

  function drcHintText(payload) {
    var reason = payload && payload.reason;
    if (reason === 'no_data') return '还没有工程数据 — 无法定位违规';
    if (reason === 'no_positions') return '没有元件坐标 — 违规无法定位';
    if (reason === 'unmapped') return '违规未能定位到任何元件位置';
    if (reason === 'no_violations') return 'DRC 未发现违规项 ✓';
    return '';
  }

  function loadDrc() {
    if (state.drcLoaded || state.drcBuilding) return;
    if (typeof eel === 'undefined' || !eel.get_drc_violations) {
      selectedInfo('后端不可用 — 请在应用内查看违规标记');
      return;
    }
    state.drcBuilding = true;
    eel.get_drc_violations()().then(function (raw) {
      state.drcBuilding = false;
      var payload = JSON.parse(raw);
      if (!payload.ok) { selectedInfo('违规数据拉取失败'); return; }
      state.drcLoaded = true;
      state.drcPayload = payload;
      if (!payload.items || !payload.items.length) {
        selectedInfo(drcHintText(payload) || 'DRC 未发现违规项 ✓');
        state.showDrc = false;
        dom.btnDrc.classList.remove('on');
        return;
      }
      applyDrc();
      if (state.drcSpots.length) {
        selectedInfo(payload.violation_count + ' 项违规 · ' +
                     state.drcSpots.length + ' 个位置 — 点击红色标记查看详情');
      } else {
        selectedInfo('已获取 ' + payload.violation_count + ' 项违规 — 3D 场景就绪后显示标记');
      }
    }).catch(function () {
      state.drcBuilding = false;
      selectedInfo('违规数据拉取失败');
    });
  }

  function applyDrc() {
    // 场景（板框/坐标原点）没建好时只存载荷，buildScene 末尾会补画
    if (!state.drcPayload || !state.drcFrame) return;
    var group = state.scene && state.scene.getObjectByName('boardGroup');
    if (group) buildDrcMarkers(state.drcPayload, state.drcFrame, group);
  }

  function extentOf(data) {
    var x0 = 1e9, y0 = 1e9, x1 = -1e9, y1 = -1e9;
    function take(x, y) {
      if (!isFinite(x) || !isFinite(y)) return;
      x0 = Math.min(x0, x); y0 = Math.min(y0, y);
      x1 = Math.max(x1, x); y1 = Math.max(y1, y);
    }
    (data.components || []).forEach(function (c) { take(c.x, c.y); });
    (data.traces || []).forEach(function (t) {
      for (var i = 0; i < t.segs.length; i += 2) take(t.segs[i], t.segs[i + 1]);
    });
    (data.vias || []).forEach(function (v) { take(v[0], v[1]); });
    if (x0 > x1) return null;
    return [x0, y0, x1, y1];
  }

  function buildScene(data) {
    var THREE = window.THREE;
    clearScene();
    var frame = buildBoard(data.board, extentOf(data));
    state.drcFrame = frame;
    var group = new THREE.Group();
    group.name = 'boardGroup';
    if (frame) {
      group.add(frame.mesh);

      var comps = buildComponents(data.components || [], frame);
      if (comps) { state.compsMesh = comps; group.add(comps); }

      state.traceGroups = buildTraces(data.traces || [], frame);
      state.traceGroups.forEach(function (seg) { fillTraceVerts(seg, frame); group.add(seg); });

      state.viaMesh = buildVias(data.vias || [], frame);
      if (state.viaMesh) group.add(state.viaMesh);
    }
    state.scene.add(group);

    // 违规载荷先到、场景后建的情形在这里补画（载荷没到则等 loadDrc 回调）
    applyDrc();

    var diag = frame ? Math.hypot(frame.w, frame.h) : 60;
    state.camera.near = diag / 500;
    state.camera.far = diag * 20;
    state.camera.updateProjectionMatrix();
    setView('tilt', frame);

    var c = data.counts || {};
    dom.badge.textContent =
      (c.components || 0) + ' 元件 · ' + (c.trace_segments || 0) + ' 走线段 · ' +
      (c.vias || 0) + ' 过孔' +
      (frame ? ' · 板 ' + frame.w.toFixed(1) + '×' + frame.h.toFixed(1) + 'mm' : '');
  }

  // ═══════════ 视角 ═══════════

  function setView(kind, frame) {
    if (!state.camera || !state.controls) return;
    var diag = frame ? Math.max(10, Math.hypot(frame.w, frame.h)) : 60;
    var s = diag * 1.15;
    var p;
    if (kind === 'top') p = [0.01, s, 0.01];
    else if (kind === 'side') p = [0, s * 0.06, s];
    else if (kind === 'bottom') p = [s * 0.55, -s * 0.85, s * 0.7];
    else p = [s * 0.55, s * 0.85, s * 0.7];   // tilt 默认
    state.camera.position.set(p[0], p[1], p[2]);
    state.controls.target.set(0, 0, 0);
    state.controls.update();
  }

  // ═══════════ 渲染循环（休眠/唤醒同 particles.js 纪律）═══════════

  function tick() {
    state.raf = 0;
    var active = state.threeReady && state.renderer &&
                 dom.canvas.clientWidth > 0 && !document.hidden;
    if (!active) {
      if (++state.idle > 90) return;       // ≈1.5s 无可视 → 停排帧
    } else {
      state.idle = 0;
      state.controls.update();
      state.renderer.render(state.scene, state.camera);
    }
    state.raf = requestAnimationFrame(tick);
  }

  function wake() {
    if (!state.raf) state.raf = requestAnimationFrame(tick);
  }

  // ═══════════ 数据加载 ═══════════

  function hint(kind) {
    dom.empty.style.display = 'block';
    dom.wrap.style.display = 'none';
    dom.empty.textContent =
      kind === 'no_data' ? '还没有工程数据 — 请先导入 .epro2 工程文件（或 PCB/坐标文件）' :
      kind === 'partial' ? '当前数据只有部分几何（建议导入 .epro2 获得完整 3D 预览）' :
      kind === 'no_backend' ? '后端不可用 — 请在应用内使用 3D 预览' :
      '导入 .epro2 工程文件后可预览 3D 板卡';
  }

  function buildViewer() {
    var THREE = window.THREE;
    if (state.renderer) return;
    var canvas = dom.canvas;
    state.renderer = new THREE.WebGLRenderer({ canvas: canvas, antialias: true, alpha: true });
    state.renderer.setPixelRatio(Math.min(2, window.devicePixelRatio || 1));
    state.scene = new THREE.Scene();
    state.camera = new THREE.PerspectiveCamera(40, 1, 0.1, 2000);
    state.scene.add(new THREE.HemisphereLight(0xffffff, 0x555b66, 0.95));
    var dir = new THREE.DirectionalLight(0xffffff, 0.65);
    dir.position.set(30, 60, 25);
    state.scene.add(dir);
    state.controls = new THREE.OrbitControls(state.camera, canvas);
    state.controls.enableDamping = true;
    state.controls.dampingFactor = 0.12;
    state.controls.maxPolarAngle = Math.PI;   // 允许翻到板底看 B 面
    fitSize();
  }

  function fitSize() {
    if (!state.renderer || !dom.canvas.clientWidth) return;
    var w = dom.canvas.clientWidth, h = dom.canvas.clientHeight;
    state.renderer.setSize(w, h, false);
    state.camera.aspect = w / h;
    state.camera.updateProjectionMatrix();
  }

  function loadData(force) {
    if (state.building) return;
    if (state.loaded && !force) return;
    if (typeof eel === 'undefined' || !eel.get_board_3d_data) { hint('no_backend'); return; }
    state.building = true;
    dom.empty.style.display = 'none';
    dom.wrap.style.display = 'block';
    dom.loading.style.display = 'flex';
    eel.get_board_3d_data()().then(function (raw) {
      var data = JSON.parse(raw);
      state.building = false;
      dom.loading.style.display = 'none';
      if (!data.ok) { hint('no_data'); return; }
      if (data.reason === 'no_data' || (!data.board && !(data.components || []).length)) { hint('no_data'); return; }
      state.loaded = true;
      ensureThree().then(function () {
        buildViewer();
        buildScene(data);
        var hasGeom = data.board || (data.components || []).length;
        if (!hasGeom) hint('no_data');
        else if (data.format && data.format !== 'lceda_epro2' && !(data.board && data.board.rings && data.board.rings.length)) hint('partial');
        wake();
      }).catch(function () { state.building = false; hint('no_backend'); });
    }).catch(function () {
      state.building = false;
      hint('no_data');
    });
  }

  // ═══════════ 交互：工具栏 + 点击查看元件 ═══════════

  function selectedInfo(text) {
    dom.badge.textContent = text;
  }

  function onCanvasDown(e) {
    state.downX = e.clientX; state.downY = e.clientY;
  }

  function onCanvasUp(e) {
    if (Math.hypot(e.clientX - state.downX, e.clientY - state.downY) > 5) return;  // 拖拽转视角，不当点击
    if (!state.scene) return;
    var THREE = window.THREE;
    var rect = dom.canvas.getBoundingClientRect();
    var ndc = new THREE.Vector2(
      ((e.clientX - rect.left) / rect.width) * 2 - 1,
      -((e.clientY - rect.top) / rect.height) * 2 + 1
    );
    var ray = new THREE.Raycaster();
    ray.setFromCamera(ndc, state.camera);
    // 违规标记悬在元件上方且更小，先于元件命中判定
    if (state.drcMesh && state.drcMesh.visible) {
      var drcHits = ray.intersectObject(state.drcMesh);
      if (drcHits.length && drcHits[0].instanceId != null && state.drcSpots[drcHits[0].instanceId]) {
        var s = state.drcSpots[drcHits[0].instanceId];
        selectedInfo(
          s.n + ' 项违规 @ (' + s.x.toFixed(1) + ', ' + s.y.toFixed(1) + ') — [' +
          s.first.rule + '] ' + s.first.description
        );
        return;
      }
    }
    if (!state.compsMesh || !state.comps.length) return;
    var hits = ray.intersectObject(state.compsMesh);
    if (hits.length && hits[0].instanceId != null && state.comps[hits[0].instanceId]) {
      var c = state.comps[hits[0].instanceId];
      selectedInfo(
        c.ref + (c.footprint_name ? ' · ' + c.footprint_name : '') +
        (c.value ? ' · ' + c.value : '') + ' · ' + (c.side === 'B' ? 'B 面' : 'T 面')
      );
    }
  }

  function wireToolbar() {
    dom.viewTop.onclick = function () { setView('top', currentFrame()); };
    dom.viewTilt.onclick = function () { setView('tilt', currentFrame()); };
    dom.viewSide.onclick = function () { setView('side', currentFrame()); };
    dom.viewBottom.onclick = function () { setView('bottom', currentFrame()); };
    dom.btnTraces.onclick = function () {
      state.showTraces = !state.showTraces;
      dom.btnTraces.classList.toggle('on', state.showTraces);
      state.traceGroups.forEach(function (g) { g.visible = state.showTraces; });
    };
    dom.btnVias.onclick = function () {
      state.showVias = !state.showVias;
      dom.btnVias.classList.toggle('on', state.showVias);
      if (state.viaMesh) state.viaMesh.visible = state.showVias;
    };
    dom.btnDrc.onclick = function () {
      state.showDrc = !state.showDrc;
      dom.btnDrc.classList.toggle('on', state.showDrc);
      if (state.showDrc) loadDrc();
      else {
        if (state.drcMesh) state.drcMesh.visible = false;
        if (state.drcStems) state.drcStems.visible = false;
      }
    };
    dom.btnReload.onclick = function () {
      // 刷新 = 换/重导工程后手动同步：违规载荷跟着丢弃（坐标原点会变）
      state.drcLoaded = false; state.drcPayload = null;
      state.showDrc = false; dom.btnDrc.classList.remove('on');
      loadData(true);
    };
    dom.canvas.addEventListener('pointerdown', onCanvasDown);
    dom.canvas.addEventListener('pointerup', onCanvasUp);
    function currentFrame() {
      var g = state.scene && state.scene.getObjectByName('boardGroup');
      if (!g) return null;
      var f = { w: 60, h: 45 };
      var bb = new (window.THREE.Box3)().setFromObject(g);
      if (isFinite(bb.min.x)) { f.w = bb.max.x - bb.min.x; f.h = bb.max.z - bb.min.z; }
      return f;
    }
  }

  // ═══════════ 挂载 ═══════════

  function init() {
    dom.tab = document.getElementById('tab-board3d');
    if (!dom.tab) return;
    // 冒烟测试/调试句柄（先例：两段式启动的 window.boot.state）。
    // UI 冒烟在无头环境里用它确认场景真的建起来、实例数对得上。
    window.board3d = {
      state: state,
      pickAt: function (clientX, clientY) {   // 供测试用的确定性拾取入口
        var rect = dom.canvas.getBoundingClientRect();
        var ndc = new window.THREE.Vector2(
          ((clientX - rect.left) / rect.width) * 2 - 1,
          -((clientY - rect.top) / rect.height) * 2 + 1
        );
        var ray = new window.THREE.Raycaster();
        ray.setFromCamera(ndc, state.camera);
        var hits = state.compsMesh ? ray.intersectObject(state.compsMesh) : [];
        return hits.length ? state.comps[hits[0].instanceId] : null;
      },
      pickDrcAt: function (clientX, clientY) {  // 同上，违规标记层
        var rect = dom.canvas.getBoundingClientRect();
        var ndc = new window.THREE.Vector2(
          ((clientX - rect.left) / rect.width) * 2 - 1,
          -((clientY - rect.top) / rect.height) * 2 + 1
        );
        var ray = new window.THREE.Raycaster();
        ray.setFromCamera(ndc, state.camera);
        var hits = state.drcMesh ? ray.intersectObject(state.drcMesh) : [];
        return hits.length ? state.drcSpots[hits[0].instanceId] : null;
      },
    };
    dom.canvas = document.getElementById('b3dCanvas');
    dom.wrap = document.getElementById('b3dWrap');
    dom.empty = document.getElementById('b3dEmpty');
    dom.loading = document.getElementById('b3dLoading');
    dom.badge = document.getElementById('b3dBadge');
    dom.viewTop = document.getElementById('b3dViewTop');
    dom.viewTilt = document.getElementById('b3dViewTilt');
    dom.viewSide = document.getElementById('b3dViewSide');
    dom.viewBottom = document.getElementById('b3dViewBottom');
    dom.btnTraces = document.getElementById('b3dToggleTraces');
    dom.btnVias = document.getElementById('b3dToggleVias');
    dom.btnDrc = document.getElementById('b3dToggleDrc');
    dom.btnReload = document.getElementById('b3dReload');

    wireToolbar();

    // 标签激活/面板展开都会改变 canvas 尺寸或可见性 → ResizeObserver + class 观察
    new ResizeObserver(function () { fitSize(); wake(); }).observe(dom.wrap);
    new MutationObserver(function () {
      if (dom.tab.classList.contains('active')) { wake(); loadData(false); }
    }).observe(dom.tab, { attributes: true, attributeFilter: ['class'] });
    document.addEventListener('visibilitychange', wake);
  }

  init();
})();
