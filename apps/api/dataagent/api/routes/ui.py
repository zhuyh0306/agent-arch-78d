"""Server-rendered pages: the project status board and the metric dictionary.

Why server-rendered HTML and not a Next.js app: the ``apps/web`` workspace is an
empty placeholder, and standing up a build pipeline to display 20 static rows
would cost more than it explains. These pages are generated from the same
contract files the agent reads, so what the page shows cannot drift from what
the service believes -- that consistency is the whole point.

Security: both pages require the same API key as the API, supplied as a query
parameter for a browser-friendly path. The key is short-lived in practice
(bookmark it in a password manager, not a URL in a chat log). This is a
deliberate trade for a dev-facing tool; ``/docs`` uses Basic auth instead
because Swagger needs a navigation-level prompt.
"""

from __future__ import annotations

import html
import re
from pathlib import Path

import yaml
from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import HTMLResponse

from dataagent.agent.ports.repo import MetricRepositoryPort
from dataagent.domain.auth import AuthenticationError

router = APIRouter(prefix="/ui", tags=["ui"])

REPO_ROOT = Path(__file__).resolve().parents[5]
PLAN = REPO_ROOT / "plan.md"

RISK_STYLE = {
    "high": ("#b3261e", "#fce8e6"),
    "medium": ("#8a5a00", "#fef3cd"),
    "low": ("#1e5d2f", "#e6f4ea"),
}

_CSS = """
:root { color-scheme: light; }
* { box-sizing: border-box; }
body { margin: 0; font: 14px/1.55 -apple-system, "PingFang SC", "Microsoft YaHei", sans-serif;
       color: #1b1b1f; background: #f6f7f9; }
header { background: #1b1b1f; color: #fff; padding: 18px 28px; }
header h1 { margin: 0; font-size: 18px; letter-spacing: .2px; }
header p { margin: 4px 0 0; color: #b9bcc4; font-size: 12.5px; }
nav { display: flex; gap: 18px; padding: 10px 28px; background: #26262c; }
nav a { color: #cfd2da; text-decoration: none; font-size: 13px; padding: 3px 0; }
nav a.on, nav a:hover { color: #fff; border-bottom: 2px solid #7aa2ff; }
main { padding: 22px 28px 60px; max-width: 1180px; }
h2 { font-size: 15px; margin: 26px 0 10px; color: #33343a; }
h2:first-child { margin-top: 0; }
.card { background: #fff; border: 1px solid #e3e5ea; border-radius: 8px; padding: 16px 18px; margin-bottom: 18px; }
.stats { display: flex; flex-wrap: wrap; gap: 12px; }
.stat { flex: 1 1 150px; background: #fff; border: 1px solid #e3e5ea; border-radius: 8px; padding: 12px 14px; }
.stat .n { font-size: 22px; font-weight: 600; }
.stat .l { font-size: 12px; color: #6b6f7a; margin-top: 2px; }
.bar { height: 8px; background: #e9ebef; border-radius: 4px; overflow: hidden; margin-top: 8px; }
.bar > i { display: block; height: 100%; background: #2f6fed; }
table { width: 100%; border-collapse: collapse; background: #fff; font-size: 13px; }
th, td { text-align: left; padding: 8px 10px; border-bottom: 1px solid #eef0f3; vertical-align: top; }
th { background: #fafbfc; font-weight: 600; color: #4a4d55; font-size: 12.5px; position: sticky; top: 0; }
tr:hover td { background: #f7f9ff; }
code { font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: 12px; background: #f2f3f5;
       padding: 1px 5px; border-radius: 4px; }
.pill { display: inline-block; padding: 1px 8px; border-radius: 10px; font-size: 11.5px; font-weight: 600; }
.ok { color: #1e5d2f; background: #e6f4ea; }
.part { color: #8a5a00; background: #fef3cd; }
.todo { color: #6b6f7a; background: #eef0f3; }
.muted { color: #6b6f7a; }
.daylist { display: grid; grid-template-columns: repeat(auto-fill, minmax(26px, 1fr)); gap: 4px; }
.daylist span { text-align: center; font-size: 11px; padding: 3px 0; border-radius: 3px; }
ul.pit { margin: 0; padding-left: 18px; }
ul.pit li { margin: 1px 0; }
input[type=search] { padding: 8px 10px; width: 260px; border: 1px solid #d4d7de; border-radius: 6px; font-size: 13px; }
footer { padding: 0 28px 30px; color: #8b8f99; font-size: 12px; }
"""


def _page(title: str, body: str, active: str) -> str:
    def nav(key: str, label: str, href: str) -> str:
        cls = " class='on'" if key == active else ""
        return f"<a{cls} href='{html.escape(href)}'>{label}</a>"

    return f"""<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(title)}</title><style>{_CSS}</style></head>
<body>
<header><h1>DataAgent · {html.escape(title)}</h1>
<p>78 天 Agent 架构学习项目 · Day 15 模块化单体</p></header>
<nav>{nav("status", "工程进度", "/ui")}{nav("metrics", "指标字典", "/ui/metrics")}
<a href="/docs">API 文档 (Basic 认证)</a><a href="/healthz">/healthz</a></nav>
<main>{body}</main>
<footer>页面内容直接读 <code>plan.md</code> 与 <code>packages/contracts/metrics_dictionary.yaml</code>，与代码同源。</footer>
</body></html>"""


def _require_key(request: Request, key: str | None) -> None:
    try:
        request.app.state.container.api_keys.authenticate(key)
    except AuthenticationError:
        raise HTTPException(status_code=401, detail={"failure_code": "GUARDRAIL_BLOCKED", "detail": "add ?key=<API key>"}) from None


# --------------------------------------------------------------- plan parsing


def _parse_plan() -> list[dict]:
    days: list[dict] = []
    current: dict | None = None
    week = ""
    for line in PLAN.read_text(encoding="utf-8").splitlines():
        if line.startswith("## 第") and "周" in line:
            week = line.lstrip("# ").strip()
        match = re.match(r"^### Day (\d+)｜(.+?)（", line)
        if match:
            current = {"day": int(match.group(1)), "title": match.group(2), "week": week, "done": 0, "total": 0}
            days.append(current)
        elif current is not None:
            if line.startswith("- [x]"):
                current["done"] += 1
                current["total"] += 1
            elif line.startswith("- [ ]"):
                current["total"] += 1
    return days


def _status(day: dict) -> str:
    if day["total"] and day["done"] == day["total"]:
        return "done"
    if day["done"]:
        return "partial"
    return "todo"


@router.get("", response_class=HTMLResponse)
@router.get("/", response_class=HTMLResponse)
def status_page(request: Request, key: str | None = Query(default=None)) -> HTMLResponse:
    _require_key(request, key)
    days = _parse_plan()
    done = [d for d in days if _status(d) == "done"]
    partial = [d for d in days if _status(d) == "partial"]
    todo = [d for d in days if _status(d) == "todo"]
    checks_total = sum(d["total"] for d in days)
    checks_done = sum(d["done"] for d in days)
    pct = checks_done / checks_total * 100 if checks_total else 0

    css_for = {"done": "ok", "partial": "part", "todo": "todo"}
    day_cells = "".join(
        f"<span class='{css_for[_status(d)]}' "
        f"title='Day {d['day']} {html.escape(d['title'])} ({d['done']}/{d['total']})'>{d['day']}</span>"
        for d in days
    )
    done_rows = "".join(
        f"<tr><td>Day {d['day']}</td><td>{html.escape(d['title'])}</td><td class='ok pill'>{d['done']}/{d['total']}</td></tr>"
        for d in done
    )
    partial_rows = "".join(
        f"<tr><td>Day {d['day']}</td><td>{html.escape(d['title'])}</td><td class='part pill'>{d['done']}/{d['total']}</td></tr>"
        for d in partial
    )
    next_day = todo[0] if todo else None
    next_html = (
        f"<b>Day {next_day['day']}｜{html.escape(next_day['title'])}</b><div class='muted'>{html.escape(next_day['week'])}</div>"
        if next_day
        else "<b>全部完成</b>"
    )

    body = f"""
<div class="stats">
  <div class="stat"><div class="n">{len(done)}<span class="muted" style="font-size:14px"> / {len(days)}</span></div><div class="l">整日完成</div></div>
  <div class="stat"><div class="n">{len(partial)}</div><div class="l">部分完成</div></div>
  <div class="stat"><div class="n">{len(todo)}</div><div class="l">未开始</div></div>
  <div class="stat"><div class="n">{checks_done}<span class="muted" style="font-size:14px"> / {checks_total}</span></div><div class="l">检查项</div>
    <div class="bar"><i style="width:{pct:.1f}%"></i></div></div>
</div>

<div class="card"><b>下一步：</b>{next_html}</div>

<h2>78 天进度</h2>
<div class="card">
  <div class="daylist">{day_cells}</div>
  <p class="muted" style="margin:12px 0 0;font-size:12px">
    <span class="pill ok">已完成</span> <span class="pill part">部分完成</span> <span class="pill todo">未开始</span>
    · 悬停查看当天标题与检查项进度
  </p>
</div>

<h2>整日完成（{len(done)} 天）</h2>
<table><thead><tr><th style="width:90px">天</th><th>主题</th><th style="width:80px">检查</th></tr></thead>
<tbody>{done_rows}</tbody></table>

<h2>部分完成（{len(partial)} 天）</h2>
<table><thead><tr><th style="width:90px">天</th><th>主题</th><th style="width:80px">检查</th></tr></thead>
<tbody>{partial_rows or "<tr><td colspan=3 class='muted'>无</td></tr>"}</tbody></table>
"""
    return HTMLResponse(_page("工程进度", body, "status"))


# ------------------------------------------------------------ metric explorer


def _risk_pill(risk: str) -> str:
    fg, bg = RISK_STYLE.get(risk, ("#6b6f7a", "#eef0f3"))
    return f"<span class='pill' style='color:{fg};background:{bg}'>{html.escape(risk)}</span>"


@router.get("/metrics", response_class=HTMLResponse)
def metrics_page(request: Request, key: str | None = Query(default=None)) -> HTMLResponse:
    _require_key(request, key)
    repo: MetricRepositoryPort = request.app.state.container.metrics
    rows_data = _load_metric_rows(repo)

    high = [m for m in rows_data if m["risk"] == "high"]
    categories: dict[str, int] = {}
    for m in rows_data:
        categories[m["category"]] = categories.get(m["category"], 0) + 1

    table_rows = "".join(
        f"""<tr data-search="{html.escape((m['id'] + ' ' + m['name'] + ' ' + m['category'] + ' ' + m['definition']).lower())}">
<td><code>{html.escape(m['id'])}</code></td>
<td><b>{html.escape(m['name'])}</b></td>
<td>{html.escape(m['category'])}</td>
<td>{html.escape(m['definition'])}</td>
<td><code>{html.escape(m['formula'])}</code></td>
<td>{html.escape(m['unit'])}</td>
<td>{html.escape(m['grain'])}</td>
<td><ul class="pit">{''.join(f'<li>{html.escape(p)}</li>' for p in m['pitfalls'])}</ul></td>
<td>{_risk_pill(m['risk'])}</td>
</tr>"""
        for m in rows_data
    )
    cat_html = "".join(
        f"<span class='pill todo' style='margin-right:6px'>{html.escape(c)} {n}</span>" for c, n in sorted(categories.items())
    )

    body = f"""
<div class="stats">
  <div class="stat"><div class="n">{len(rows_data)}</div><div class="l">指标总数</div></div>
  <div class="stat"><div class="n">{len(categories)}</div><div class="l">分类</div></div>
  <div class="stat"><div class="n">{len(high)}</div><div class="l">高算错风险</div></div>
</div>

<div class="card"><b>高算错风险：</b>{'、'.join(f"<code>{html.escape(m['id'])}</code> {html.escape(m['name'])}" for m in high)}
<div class="muted" style="margin-top:6px;font-size:12.5px">按 Day 13 口径，全表只允许 3 条 high，由 <code>check_metrics.py</code> 强制。</div></div>

<h2>分类分布</h2><div class="card">{cat_html}</div>

<h2>指标字典（{len(rows_data)} 条）</h2>
<div class="card" style="padding:10px 12px"><input type="search" id="q" placeholder="搜索指标名 / 分类 / 定义…"></div>
<table><thead><tr>
<th style="width:120px">id</th><th style="width:110px">名称</th><th style="width:80px">分类</th>
<th style="width:200px">定义</th><th style="width:220px">公式</th><th style="width:56px">单位</th>
<th style="width:90px">粒度</th><th>口径陷阱</th><th style="width:70px">风险</th>
</tr></thead><tbody id="rows">{table_rows}</tbody></table>

<script>
const q = document.getElementById('q');
q.addEventListener('input', () => {{
  const term = q.value.trim().toLowerCase();
  document.querySelectorAll('#rows tr').forEach(tr => {{
    tr.style.display = !term || tr.dataset.search.includes(term) ? '' : 'none';
  }});
}});
</script>
"""
    return HTMLResponse(_page("指标字典", body, "metrics"))


def _load_metric_rows(repo: MetricRepositoryPort) -> list[dict]:
    """Read the full dictionary for display.

    ``MetricDefinition`` is intentionally narrow (the agent does not need
    formula or pitfalls), so the page reads the raw YAML once for display.
    Keeping this in the UI layer means the domain contract stays lean.
    """
    dictionary = getattr(repo, "path", None)
    if dictionary is None:
        # A non-YAML repository: degrade to what the port exposes.
        return [
            {
                "id": mid,
                "name": repo.get(mid).name,
                "category": repo.get(mid).category,
                "definition": repo.get(mid).definition,
                "formula": "—",
                "unit": repo.get(mid).unit,
                "grain": "—",
                "pitfalls": ["(该数据源未提供陷阱字段)"],
                "risk": "low",
            }
            for mid in sorted(repo.list_ids())
        ]
    raw = yaml.safe_load(Path(dictionary).read_text(encoding="utf-8"))
    return [
        {
            "id": m["id"],
            "name": m["name"],
            "category": m["category"],
            "definition": m["definition"],
            "formula": m["formula"],
            "unit": m["unit"],
            "grain": m["grain"],
            "pitfalls": m.get("pitfalls", []),
            "risk": m.get("miscalculation_risk", "low"),
        }
        for m in raw["metrics"]
    ]