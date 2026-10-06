# 启动界面 / 图标素材（web/img/）

启动界面**不依赖任何图片**：没放文件时用的是 `index.html` 里那枚内联 SVG 标记
（电路走线拼出的 “E”，不会去抓 404）。想要自己的品牌标记，就按下面的提示词生成、
按文件名丢进本目录，**重启即生效，不用改代码**。

| 文件 | 用在哪 | 必需 | 规格 |
|---|---|---|---|
| `logo-mark.png` | 启动界面中央的 64×64 方块（CSS 会裁圆角） | **已放入** | 1024×1024，**正方形满幅、四角不要自己画圆角/描边/投影** |
| `splash-bg.png` | 启动界面背景（可选，建议只在深色主题启用） | 可选 | 1536×1024 或更大，低对比、留白多 |

> 载入逻辑：后端 `boot_status()` 只在 `web/img/logo-mark.png` **确实存在**时
> 才把路径发给前端（见 `main.py`），所以没生成图也不会有 404、不会报控制台错误。

## 现用素材（2026-10-03 放入）

`logo-mark.png` = 生图产出（1536×1536 JPEG，白色走线 “E” + 三个过孔环 + 品牌蓝渐变），
经 `scripts/make_logo_tile.py` 处理：**不重绘、只取景**——

- 标记包围盒 (477,412)-(1060,1128)，中心相对画面中心偏移 (0, +2)px（本来就是正的）；
- 按标记中心裁最大内接正方形 (2,4)-(1534,1536) → LANCZOS 缩到 1024×1024 → 存 PNG；
- 成品里标记 391×479px，占高 47%，正居中；184 KB。

重新生成或换图时跑同一条命令即可（圆角交给 CSS，别在图里画）：

```bash
python scripts/make_logo_tile.py "C:/Users/lin/Downloads/新图.jpeg"
```

---

## 一、App Logo 标记（推荐先做这个）

品牌蓝渐变 `#2565FE → #5B8DEF`，标记为纯白。核心意象：**用 PCB 走线拼出的字母 E**
（一根竖向干线 + 三根横向走线，每根末端一个小圆形过孔焊盘）——
和「EDA / 电路板 / AI 辅助设计」直接相关，又足够几何、好识别。

**英文提示词（复制给 GPT 生图）**

```
Flat vector app icon for an AI-assisted PCB design desktop tool.
A single centered geometric mark: the capital letter "E" constructed from printed-circuit
traces — one vertical trace as the spine, three horizontal traces as the arms, each arm
ending in a small circular via pad.
Uniform stroke weight with rounded caps, precise right angles, generous and even negative space.
Monochrome pure white mark on a smooth diagonal gradient background from #2565FE (top-left)
to #5B8DEF (bottom-right).
Perfectly square image, full-bleed background with SQUARE corners — no rounded corners,
no border, no frame, no drop shadow, no reflection.
Crisp flat vector edges, minimal, modern, product-grade. No texture, no noise, no gradient
mesh, no 3D bevel, no photorealism, no text, no letters other than the mark, no watermark,
no background pattern.
1024x1024, mark centered, ~22% padding on all sides.
```

**中文提示词（同样可用）**

```
面向 PCB/EDA 设计工具的扁平化 App 图标。
画面正中一个几何标记：用印刷电路板走线拼出的大写字母「E」——
一根竖向走线作主干，三根横向走线作横臂，每根横臂末端是一个小圆形过孔焊盘。
线条粗细统一、端头圆角、直角精确、留白均匀。
纯白色标记，背景为从 #2565FE（左上）到 #5B8DEF（右下）的平滑对角渐变。
正方形满幅，四角必须是直角——不要画圆角、不要描边、不要外框、不要投影、不要反光。
干净的扁平矢量质感，极简、现代、成品级。不要纹理、不要噪点、不要 3D 立体、
不要照片写实、不要任何文字或字母、不要水印、不要背景图案。
1024×1024，标记居中，四边各留约 22% 空白。
```

**避坑（这几条不写清楚，生成结果基本不能用）**

1. **不要让它画圆角/描边/投影** —— 圆角由 CSS 的 `border-radius` 负责。
   图里再画一层圆角，两个圆角对不齐，边缘会露出底色。
2. **不要出现文字**（包括 “EDA” 字样）—— 生图模型的文字容易写错，
   而且启动界面里品牌名是 HTML 文本，重复反而廉价。
3. **线条别太细** —— 这张图会被缩到 64×64 显示，细过 1/40 边长的线会糊掉。
4. 生成 4 张挑一张；挑的时候把图缩到 64px 看一眼，能认出 “E” 就合格。

---

## 二、启动界面背景（可选，深色主题更出效果）

启动窗只有 480×340，能露出来的只有 Logo 周围那圈 —— 所以背景要**极低对比、
大面积留白**，否则会和文字打架。放进来之后由 `web/css/style.css` 的
`.splash-glow` 位置改用这张图（或直接告诉我要启用，我来接）。

**提示词**

```
Abstract minimal technical backdrop for a desktop app splash panel.
Very dark navy-black base (#0E1015). A faint isometric printed-circuit-board trace network
in the bottom-right third only, drawn in thin lines at about 8% opacity in #5B8DEF,
slightly out of focus. A soft, wide, diffuse radial glow in #2565FE just above the center.
Enormous negative space in the middle. Cinematic, quiet, high-end developer-tool aesthetic.
No text, no logo, no icons, no grid lines in the center, no bright hotspots, no noise,
no photographic elements.
```

---

## 三、可选的换色版本

启动界面跟随浅色/深色主题（`body[data-theme]`）。上面那版渐变底在两种主题下都能用；
若想要**浅色主题专用**的一版：把提示词里的背景换成 `flat solid #F7F8FA`、
标记颜色换成 `#2565FE`，其余不变，另存为 `logo-mark-light.png`（要启用告诉我，
需要给 CSS 加一条深色/浅色分支）。

## 四、顺带能升级的地方（暂未接线）

- **exe 图标**：`build.bat` 目前没传 `--icon`；同一张标记可以先转成 `.ico`
  （≥256px 含多尺寸），再 `pyinstaller --icon assets/app.ico`。
- **托盘图标**：`src/core/system_bridge.py` 现在用 PIL 现画；可以改成读这张图。
- **favicon**：`index.html` 里现在是内联 SVG 的 “EDA” 方块，可换成同一张图。
