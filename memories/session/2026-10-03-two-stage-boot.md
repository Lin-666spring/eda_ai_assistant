# 会话小结 — 2026-10-03（两段式启动：小窗先出 → 展开正式界面）

主题：**启动顺序反过来** —— 以前是「先把重活干完，再开窗口」，现在是
「先开 480×340 小窗显示加载态，重活丢后台，就绪后把窗口展开成 1300×840」。

## 起因

`main()` 原来的顺序是：`_ensure_rag_indexed()` → 热键 → 托盘 → `eel.start()`。
也就是说**第一个像素出现之前**要先跑完知识库索引（首次可能十几秒），
用户双击之后只能盯着桌面，不知道程序在干什么。

## 做了什么

### 1. 后端：`src/core/boot.py`（新）—— BootSequencer

只管「现在到哪一步了」，不碰 UI / eel，方便单测：

- `critical` 步骤决定 `ready`（前端据此决定何时展开）；知识库预热**不是** critical；
- **failed 也算结束** —— 热键/托盘/索引都是尽力而为的附属功能，失败绝不能把人永远关在小窗里；
- `step(key)` 上下文管理器：异常不冒泡，记账 + 记日志后继续；
- `status()` 给前端轮询：`{started, ready, warm, percent, step, text, elapsed_ms, steps, errors}`。
  **`started=False` = 不是 `main()` 起的**（UI 冒烟/调试直接 `eel.start`）→ 前端立刻跳过等待。

### 2. `main()`：先开窗，再干重活

```python
boot.start()
threading.Thread(target=_boot_worker, daemon=True).start()   # 热键/托盘/知识库预热
_run_window("chrome")                                        # 开小窗 + 进 Eel 主循环
```

窗口尺寸传两层：Chrome 的 `--window-size=480,340 --window-position=<居中>` **和** eel 的 `size=`。
展开由前端 `window.resizeTo(1300,840)` 做；被浏览器拒绝时 `request_main_window()`
（改 `eel._start_args` 后 `eel.show`）另开一个正式窗口兜底。

### 3. 前端：启动界面重做 + 收尾三件事

- 小窗版式：品牌光晕 + 圆角标记（内联 SVG：走线拼出的 “E”，末端过孔圆点）+ 标题 +
  副标题 + 进度条（按前端真实步骤 0.16/0.42/0.62/0.8 递增 + 流光）+ 状态文案 + 版本号；
- `boot.finish()` = **展开窗口 → 淡出遮罩**，幂等；12s 兜底与出错路径都走它，
  所以「窗口停在小窗」和「遮罩永远盖住界面」两种事故都被堵住；
- 展开后若 `warm` 仍为 false，用 `setStatus` 在顶栏如实报「正在预热知识库…」→「就绪」；
- URL 加 `#boot-hold` 停在启动界面（看设计 / 截图用）。

## 踩到的坑

### 1. eel 的 `size=` 其实是页面里的 `window.resizeTo`

`eel/chrome.py` 的 `run()` **根本不看** `size` / `position` / `geometry` ——
这些值是通过 `/eel.js` 里的 `_start_geometry` 传给页面，由 `eel._position_window()`
在 DOMContentLoaded 里 `window.resizeTo` 落地。**浏览器有权拒绝**（非脚本打开的窗口）。
所以命令行 `--window-size` 才是更可靠的一层，两层都留着。
（顺带确认：本项目的伴生模式 380×540 也是靠同一个 `resizeTo`。）

### 2. `eel.start(block=False)` 之后不要在主线程干重活

探测时踩到：`eel.start(..., block=False)` 只是 `spawn(run_lambda)`，
gevent 的 hub 要等**主线程阻塞在 gevent 原语上**才会跑。主线程直接去跑 CPU 活，
服务端口是通的但**一个请求都不响应**（探测里表现为 `ConnectionRefused`）。
正解：重活放**真线程**（eel/bottle 没打 monkey patch，`threading.Thread` 是真线程），
主线程留在 `eel.start(block=True)`。

### 3. `hidden` 属性挡不住作者样式里的 `display:block`

启动界面那块 64×64 的标记被挤到左边、只剩 23px 宽：`<img hidden>`（还没 src）
配上 `.splash-logo img{display:block}` —— `hidden` 来自 UA 样式表，被作者样式覆盖后
这张空图照样满占 flex 容器（实测 img 41px + svg 23px = 64px，两个都 flex-shrink 了）。
改成默认 `display:none` + `.is-on` 才显示。
**定位手段**：`page.locator('.splash-logo').screenshot()`（device_scale_factor=4）
+ `getBoundingClientRect`，比看整页截图猜像素快得多。

### 4. 受限沙箱跑不了 Playwright（老问题）

`PermissionError: [WinError 5] ... asyncio/windows_utils.py` —— 沙箱边界，不是代码问题。

## 验证

```
tests/ui_smoke.py：85/85 通过（原 74 + P16 新增 6 项 + 其他）
  截图 output/ui_smoke/boot_splash_small.png（浅色）/ _dark.png
pytest：新增 tests/test_boot.py 18 项（critical 语义 / failed 放行 / step() 吞异常 / 并发压测）
```

P16 新增覆盖：小窗启动界面完整渲染（含进度条宽度 > 4px）、480×340 内不溢出（x/y 都是 0）、
`#boot-hold` 停在启动界面、收尾后遮罩移除且 `is-booting` 摘掉、
**`resizeTo` 被拒（无头 Playwright 必然被拒）时 `fallback=true`**。
顺带修了 `scan_warnings` 的误报：`index.html` 里静态写死的 id 不算死代码
（启动遮罩的 id 在首屏之后就不在 DOM 里了）。

## 素材

生图提示词写在 `web/img/README.md`（Logo 标记 / 深色背景 / 浅色变体 + 避坑三条）。
没有图也不影响：`boot_status()` 只在 `web/img/logo-mark.png` 真的存在时才给路径，
所以默认走内联 SVG，不会有 404、不会污染控制台。

**已放入**（2026-10-03）：用户按提示词生成的 1536×1536 JPEG（白色走线 “E” + 过孔环），
经新脚本 `scripts/make_logo_tile.py` 处理成 1024×1024 PNG —— 只做取景与格式、不重绘：
按白色标记包围盒中心裁最大内接正方形再缩放（标记 47% 占高、正居中，184 KB）。
实测该图的标记本来就是居中的（偏移 0,+2px）。重开跑一遍冒烟：85/85 通过，
图片正常加载（无 404、无控制台错误）。

## 改动文件

- `src/core/boot.py`（新）、`tests/test_boot.py`（新）、`web/img/README.md`（新）
- `main.py`（两段式启动 + `boot_status` / `request_main_window` + 窗口参数）
- `src/core/controller.py`（`_ensure_rag_indexed` 双检加锁：启动线程与首次查询可能并发）
- `src/constants.py`（APP_NAME / APP_TAGLINE / APP_VERSION / SPLASH_* / MAIN_*）
- `web/index.html`、`web/css/style.css`、`web/js/app.js`
- `tests/ui_smoke.py`、`CLAUDE.md`
