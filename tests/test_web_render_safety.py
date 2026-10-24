"""P1-12 回归（2026-10-08）：renderMarkdown 必须中和 javascript:/data: 链接。

剥裸 HTML（`replace(/<[^>]*>/g,'')`）挡不住 markdown 链接 —— `[x](javascript:…)`
不含尖括号，marked v15 实测原样产出 href="javascript:…"。本测试用本机 node
加载 vendored marked + 从前端 js 模块抽取真实 renderMarkdown 执行，行为级断言。
（P1-6 阶段C 后 app.js 拆为 web/js/*.js 多模块，这里对模块全集做名字抽取，
不再依赖具体文件，后续模块内搬迁无需改本测试。）
"""

import shutil
import subprocess
from pathlib import Path

import pytest

WEB = Path(__file__).resolve().parent.parent / "web"
JS_DIR = WEB / "js"
FRONTEND_JS = sorted(p for p in JS_DIR.glob("*.js") if p.name != "marked.min.js")

NODE_PROBE = r"""
const fs = require('fs');
const {marked} = require(process.argv[1]);

function extract(name) {
  const src = fs.readFileSync(process.argv[2], 'utf8');  // 模块拼接源（临时文件）
  const re = new RegExp('^function ' + name + '\\([^)]*\\) \\{[\\s\\S]*?^\\}', 'm');
  const m = src.match(re);
  if (!m) { console.error('extract failed: ' + name); process.exit(3); }
  return m[0];
}

// 从前端 js 模块全集里若有现成 escapeHtml 就用真的，否则用等价桩
let escapeHtmlSrc;
try { escapeHtmlSrc = extract('escapeHtml'); } catch (e) {
  escapeHtmlSrc = 'function escapeHtml(s){return String(s).replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;").replace(/"/g,"&quot;")}';
}
const renderMarkdown = new Function(
  'marked', 'escapeHtml',
  extract('renderMarkdown') + '\nreturn renderMarkdown;'
)(marked, new Function('return ' + escapeHtmlSrc)());

const fails = [];
function check(name, cond, detail) { if (!cond) fails.push(name + ': ' + detail); }

const jsOut = renderMarkdown('[a](javascript:alert(1))');
check('js_href_neutralized', !/javascript:/i.test(jsOut), jsOut);

const dataOut = renderMarkdown('[b](data:text/html,<b>x</b>)');
check('data_href_neutralized', !/href=["']?data:/i.test(dataOut), dataOut);

// 2026-10-24（验收 A-2）：实体编码变体。浏览器解析属性值时先解码 HTML
// 实体再解析 URL —— 修复前这些全部绕过字面量正则。
const ent1 = renderMarkdown('[a](javascript&colon;alert(1))');
check('entity_colon_neutralized', !/javascript/i.test(ent1), ent1);
const ent2 = renderMarkdown('[b](javascript&#58;alert(1))');
check('numeric_colon_neutralized', !/javascript/i.test(ent2), ent2);
const ent3 = renderMarkdown('[c](&#106;avascript&#x3A;alert(1))');
check('numeric_scheme_neutralized', !/avascript/i.test(ent3), ent3);
const ent4 = renderMarkdown('[d](java\tscript:alert(1))');
check('tab_split_neutralized', !/javascript/i.test(ent4.replace(/[\s\S]*href/, 'href')), ent4);

// 白名单必须放行正常链接
const mail = renderMarkdown('[m](mailto:a@b.c)');
check('mailto_kept', /href="mailto:a@b\.c"/.test(mail), mail);
const anch = renderMarkdown('[t](#sec)');
check('anchor_kept', /href="#sec"/.test(anch), anch);
const rel = renderMarkdown('[r](docs/readme.md)');
check('relative_kept', /href="docs\/readme\.md"/.test(rel), rel);

// 图片：data:image 放行，javascript 拒绝
const imgOk = renderMarkdown('![i](data:image/png;base64,AAAA)');
check('data_image_src_kept', /src="data:image\/png/.test(imgOk), imgOk);
const imgJs = renderMarkdown('![i](javascript:alert(2))');
check('img_js_neutralized', !/javascript/i.test(imgJs), imgJs);

const normal = renderMarkdown('**bold** [ok](https://x.y)\n\n    code block\n\n| a | b |\n| - | - |\n| 1 | 2 |');
check('bold_kept', normal.includes('<strong>bold</strong>'), normal);
check('https_kept', normal.includes('href="https://x.y"'), normal);
check('codeblock_kept', normal.includes('<code'), normal);
check('table_kept', normal.includes('<table'), normal);

if (fails.length) { console.error(fails.join('\n')); process.exit(1); }
console.log('ALL_OK');
"""


@pytest.mark.skipif(shutil.which("node") is None, reason="需要 node 执行前端渲染逻辑")
def test_rendermarkdown_neutralizes_dangerous_hrefs(tmp_path):
    combined = "\n".join(p.read_text(encoding="utf-8") for p in FRONTEND_JS)
    src_file = tmp_path / "_frontend_combined.js"
    src_file.write_text(combined, encoding="utf-8")
    r = subprocess.run(
        ["node", "-e", NODE_PROBE, str(WEB / "js" / "marked.min.js"), str(src_file)],
        capture_output=True, text=True, timeout=60,
    )
    assert r.returncode == 0, f"stdout={r.stdout}\nstderr={r.stderr}"
    assert "ALL_OK" in r.stdout
