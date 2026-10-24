// ═══════════════════════════════════════════
//  Particles —— 电路粒子场（canvas 2D · 零依赖 · 离线安全）
//  ─────────────────────────────────────────
//  装饰本身讲 EDA 的语言，不做通用「漂浮圆点」：
//    · 节点画成过孔：中心焊盘 + 外圈环（环缓慢呼吸）
//    · 邻近节点之间按 PCB 布线习惯连 45° 折线（斜段 + 直段，一次拐弯），
//      不是粒子网络惯用的斜直线
//    · 信号光点沿走线传播，像板子上跑数据
//  挂两处：#splashParticles（启动界面）、#chatEmptyParticles（对话空态，
//  是 #chatMessages 的第一个子节点 —— tools.js 的清屏白名单要保留它）。
//  工程约束：
//    · 一条 rAF 驱动全部实例；无可视实例时休眠，观察器负责唤醒
//    · prefers-reduced-motion：只画一帧静态走线，不进循环
//    · 颜色每秒重读 CSS 变量（--accent / body[data-theme]），
//      设置里换主题、换强调色后 1 秒内自动跟上
//    · DPR 封顶 2、节点数随面积伸缩 —— 打包版在低端机上也稳
// ═══════════════════════════════════════════
(function () {
  'use strict';

  const REDUCED = window.matchMedia
    ? window.matchMedia('(prefers-reduced-motion: reduce)')
    : { matches: false };

  /* —— 颜色缓存：不每帧读 computed style，每 ~60 帧（≈1s）刷一次 —— */
  const palette = { dark: false, rgb: [37, 101, 254], frame: 0 };
  function refreshPalette() {
    palette.dark = (document.body && document.body.getAttribute('data-theme')) === 'dark';
    const raw = getComputedStyle(document.body).getPropertyValue('--accent').trim();
    const m = /^#([0-9a-f]{6})$/i.exec(raw);
    if (m) {
      palette.rgb = [
        parseInt(m[1].slice(0, 2), 16),
        parseInt(m[1].slice(2, 4), 16),
        parseInt(m[1].slice(4, 6), 16),
      ];
    }
  }
  function tint(alpha) {
    const c = palette.rgb;
    return 'rgba(' + c[0] + ',' + c[1] + ',' + c[2] + ',' + alpha + ')';
  }

  class Field {
    constructor(canvas, opts) {
      this.cv = canvas;
      this.ctx = canvas.getContext('2d');
      this.o = Object.assign(
        { density: 9000, maxNodes: 40, minNodes: 8, link: 130, maxPulses: 5, isVisible: null },
        opts
      );
      this.nodes = [];
      this.pulses = [];
      this.w = 0;
      this.h = 0;
      this.dead = false;
      this.ro = new ResizeObserver(() => this._resize());
      this.ro.observe(canvas);
      this._resize();
    }

    destroy() {
      this.dead = true;
      this.ro.disconnect();
    }

    get visible() {
      if (this.dead || !this.cv.isConnected || this.cv.clientWidth === 0) return false;
      return this.o.isVisible ? this.o.isVisible() : true;
    }

    _resize() {
      const w = this.cv.clientWidth, h = this.cv.clientHeight;
      if (!w || !h) return;
      const dpr = Math.min(2, window.devicePixelRatio || 1);
      this.cv.width = Math.round(w * dpr);
      this.cv.height = Math.round(h * dpr);
      this.ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      // 窗口尺寸变了（如启动小窗 480×340 → 展开 1300×840）：已有节点按
      // 比例平移过来再补齐/裁剪到目标数，避免粒子「全体重掷」的跳变
      const oldW = this.w, oldH = this.h;
      this.w = w; this.h = h;
      if (this.nodes.length && oldW && oldH) {
        const kx = w / oldW, ky = h / oldH;
        for (const p of this.nodes) { p.x *= kx; p.y *= ky; }
        this._fitCount();
      } else {
        this._seed();
      }
      if (REDUCED.matches) this.renderStill();
    }

    _targetCount() {
      const n = Math.round((this.w * this.h) / this.o.density);
      return Math.max(this.o.minNodes, Math.min(this.o.maxNodes, n));
    }

    _spawnNode() {
      const a = Math.random() * Math.PI * 2, sp = 4 + Math.random() * 6; // px/s
      return {
        x: Math.random() * this.w,
        y: Math.random() * this.h,
        vx: Math.cos(a) * sp,
        vy: Math.sin(a) * sp,
        ph: Math.random() * Math.PI * 2,
      };
    }

    _seed() {
      this.nodes = [];
      const n = this._targetCount();
      for (let i = 0; i < n; i++) this.nodes.push(this._spawnNode());
      this.pulses = [];
    }

    _fitCount() {
      const target = this._targetCount();
      while (this.nodes.length < target) this.nodes.push(this._spawnNode());
      if (this.nodes.length > target) this.nodes.length = target;
    }

    /* 45° 折线走线：斜段先吃掉短边差值，剩下的走水平/垂直直段 —— 一次拐弯 */
    static route(a, b) {
      const dx = b.x - a.x, dy = b.y - a.y;
      const d = Math.min(Math.abs(dx), Math.abs(dy));
      const mx = a.x + Math.sign(dx) * d, my = a.y + Math.sign(dy) * d;
      const l1 = d * Math.SQRT2;
      const l2 = (Math.abs(dx) > Math.abs(dy) ? Math.abs(dx) : Math.abs(dy)) - d;
      return { mx, my, l1, len: l1 + l2 };
    }

    step(dt) {
      for (const p of this.nodes) {
        p.x += p.vx * dt;
        p.y += p.vy * dt;
        p.ph += dt * 1.2;
        if (p.x < -24) p.vx = Math.abs(p.vx);
        else if (p.x > this.w + 24) p.vx = -Math.abs(p.vx);
        if (p.y < -24) p.vy = Math.abs(p.vy);
        else if (p.y > this.h + 24) p.vy = -Math.abs(p.vy);
      }
      for (const q of this.pulses) q.t += (q.sp * dt) / q.r.len;
      this.pulses = this.pulses.filter((q) => q.t < 1);
      this._draw(false);
    }

    renderStill() {
      this._draw(true);
    }

    _draw(still) {
      const ctx = this.ctx, D = this.o.link, nodes = this.nodes;
      ctx.clearRect(0, 0, this.w, this.h);
      const traceMax = palette.dark ? 0.20 : 0.11;
      const nodeA = palette.dark ? 0.62 : 0.42;

      // 走线（近则连，透明度随距离衰减）
      const edges = [];
      ctx.lineWidth = 1;
      for (let i = 0; i < nodes.length; i++) {
        for (let j = i + 1; j < nodes.length; j++) {
          const a = nodes[i], b = nodes[j];
          const dx = b.x - a.x, dy = b.y - a.y;
          if (dx * dx + dy * dy > D * D) continue;
          const d = Math.sqrt(dx * dx + dy * dy);
          const r = Field.route(a, b);
          ctx.strokeStyle = tint(traceMax * (1 - d / D));
          ctx.beginPath();
          ctx.moveTo(a.x, a.y);
          ctx.lineTo(r.mx, r.my);
          ctx.lineTo(b.x, b.y);
          ctx.stroke();
          edges.push([a, b]);
        }
      }

      // 过孔节点：中心焊盘 + 呼吸环
      for (const p of nodes) {
        const breathe = 0.75 + 0.25 * Math.sin(p.ph);
        ctx.fillStyle = tint(nodeA);
        ctx.beginPath(); ctx.arc(p.x, p.y, 1.7, 0, 6.2832); ctx.fill();
        ctx.strokeStyle = tint(nodeA * 0.5 * breathe);
        ctx.beginPath(); ctx.arc(p.x, p.y, 3.4, 0, 6.2832); ctx.stroke();
      }

      // 信号脉冲：只在动画模式下生成与绘制
      if (!still) {
        if (edges.length && this.pulses.length < this.o.maxPulses && Math.random() < 0.02) {
          const pair = edges[(Math.random() * edges.length) | 0];
          const r = Field.route(pair[0], pair[1]);
          if (r.len > 30) this.pulses.push({ a: pair[0], b: pair[1], r, t: 0, sp: 90 + Math.random() * 60 });
        }
        for (const q of this.pulses) {
          const s = q.t * q.r.len;
          let x, y;
          if (s <= q.r.l1) {
            const k = q.r.l1 ? s / q.r.l1 : 1;
            x = q.a.x + (q.r.mx - q.a.x) * k;
            y = q.a.y + (q.r.my - q.a.y) * k;
          } else {
            const rest = q.r.len - q.r.l1, k = rest ? (s - q.r.l1) / rest : 1;
            x = q.r.mx + (q.b.x - q.r.mx) * k;
            y = q.r.my + (q.b.y - q.r.my) * k;
          }
          const fade = Math.min(1, q.t / 0.12, (1 - q.t) / 0.12);
          if (fade <= 0) continue;
          ctx.save();
          ctx.shadowColor = tint(0.9);
          ctx.shadowBlur = 8;
          ctx.fillStyle = tint(0.9 * fade);
          ctx.beginPath(); ctx.arc(x, y, 2.1, 0, 6.2832); ctx.fill();
          ctx.restore();
        }
      }
    }
  }

  /* —— 一条循环驱动全部实例；全不可视时休眠，由观察器唤醒 —— */
  const fields = [];
  let raf = 0, last = 0, idle = 0;

  function loop(now) {
    raf = 0;
    const dt = Math.min(0.04, (now - last) / 1000 || 0.016);
    last = now;
    if (++palette.frame >= 60) { palette.frame = 0; refreshPalette(); }
    let any = false;
    for (const f of fields) {
      if (f.dead) continue;
      if (!f.cv.isConnected) { f.destroy(); continue; }
      if (!f.visible) continue;
      any = true;
      f.step(dt);
    }
    if (!any) {
      if (++idle > 90) return; // ≈1.5s 无可视实例 → 停排帧，等 wake()
    } else {
      idle = 0;
      raf = requestAnimationFrame(loop);
    }
  }

  function wake() {
    if (REDUCED.matches) {
      for (const f of fields) if (!f.dead && f.visible) f.renderStill();
      return;
    }
    if (!raf) {
      last = performance.now();
      raf = requestAnimationFrame(loop);
    }
  }

  function mount(canvas, opts) {
    if (!canvas || !canvas.getContext) return;
    fields.push(new Field(canvas, opts));
    wake();
  }

  refreshPalette();
  mount(document.getElementById('splashParticles'), { density: 13000, maxNodes: 24, link: 96, maxPulses: 3 });
  mount(document.getElementById('chatEmptyParticles'), {
    density: 9000,
    maxNodes: 40,
    link: 130,
    // 空态被 _syncChatEmpty 用内联 display 收起时，粒子一并歇业
    isVisible: function () {
      const ce = document.getElementById('chatEmpty');
      return !ce || ce.style.display !== 'none';
    },
  });

  document.addEventListener('visibilitychange', wake);
  const ce = document.getElementById('chatEmpty');
  if (ce) new MutationObserver(wake).observe(ce, { attributes: true, attributeFilter: ['style'] });
  if (REDUCED.addEventListener) REDUCED.addEventListener('change', wake);
})();
