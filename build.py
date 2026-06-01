#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
每日新闻聚合 -> 生成手机友好的 index.html
- 抓取 feeds.json 里的 RSS 源
- 去重、按分类聚合
- 英文标题翻译成中文（原文保留，可点开）
- 输出 dist/index.html （GitHub Pages 直接托管）
"""
import os
import json
import html
import time
import hashlib
import datetime as dt
from concurrent.futures import ThreadPoolExecutor, as_completed

import feedparser

# 翻译是可选依赖，挂了也不影响出页面
try:
    from deep_translator import GoogleTranslator
    _HAS_TRANSLATOR = True
except Exception:
    _HAS_TRANSLATOR = False

HERE = os.path.dirname(os.path.abspath(__file__))
DIST = os.path.join(HERE, "dist")


def load_config():
    with open(os.path.join(HERE, "feeds.json"), "r", encoding="utf-8") as f:
        return json.load(f)


def clean(text):
    if not text:
        return ""
    text = html.unescape(text)
    # 去掉残留 html 标签
    out, depth = [], 0
    for ch in text:
        if ch == "<":
            depth += 1
        elif ch == ">":
            depth = max(0, depth - 1)
        elif depth == 0:
            out.append(ch)
    return "".join(out).strip()


def fetch_feed(feed):
    """抓单个源，返回 entry 列表。失败返回空列表，不抛异常。"""
    items = []
    try:
        parsed = feedparser.parse(feed["url"], request_headers={
            "User-Agent": "Mozilla/5.0 (compatible; DailyNewsBot/1.0)"
        })
        for e in parsed.entries:
            title = clean(getattr(e, "title", ""))
            link = getattr(e, "link", "")
            if not title or not link:
                continue
            ts = None
            for key in ("published_parsed", "updated_parsed"):
                v = getattr(e, key, None)
                if v:
                    try:
                        ts = time.mktime(v)
                    except Exception:
                        ts = None
                    break
            items.append({
                "title": title,
                "link": link,
                "source": feed["name"],
                "lang": feed.get("lang", "en"),
                "ts": ts or 0,
            })
    except Exception as ex:
        print(f"  [warn] {feed['name']} 抓取失败: {ex}")
    return items


def translate_titles(titles):
    """批量把英文标题翻成中文。返回 {原文: 译文}。"""
    result = {}
    if not (_HAS_TRANSLATOR and titles):
        return result
    uniq = list({t for t in titles})
    try:
        translator = GoogleTranslator(source="auto", target="zh-CN")
        # deep-translator 支持 batch
        for i in range(0, len(uniq), 20):
            chunk = uniq[i:i + 20]
            try:
                out = translator.translate_batch(chunk)
                for src, zh in zip(chunk, out):
                    if zh and zh.strip():
                        result[src] = zh.strip()
            except Exception as ex:
                print(f"  [warn] 翻译批次失败: {ex}")
    except Exception as ex:
        print(f"  [warn] 翻译初始化失败: {ex}")
    return result


def build():
    cfg = load_config()
    settings = cfg.get("settings", {})
    max_feed = settings.get("max_per_feed", 8)
    max_cat = settings.get("max_per_category", 20)
    do_translate = settings.get("translate_en_titles", True)

    categories_out = []
    all_en_titles = []

    for cat in cfg["categories"]:
        print(f"[分类] {cat['name']}")
        collected = []
        with ThreadPoolExecutor(max_workers=6) as ex:
            futs = {ex.submit(fetch_feed, f): f for f in cat["feeds"]}
            per_feed = {}
            for fut in as_completed(futs):
                f = futs[fut]
                items = fut.result()
                # 每个源按时间排序后取前 N
                items.sort(key=lambda x: x["ts"], reverse=True)
                per_feed[f["name"]] = items[:max_feed]
                print(f"  {f['name']}: {len(items)} 条 -> 取 {len(per_feed[f['name']])} 条")
            for items in per_feed.values():
                collected.extend(items)

        # 去重（按 link）
        seen, deduped = set(), []
        for it in collected:
            key = it["link"]
            if key in seen:
                continue
            seen.add(key)
            deduped.append(it)

        deduped.sort(key=lambda x: x["ts"], reverse=True)
        deduped = deduped[:max_cat]
        for it in deduped:
            if it["lang"] == "en":
                all_en_titles.append(it["title"])
        categories_out.append({"meta": cat, "items": deduped})

    # 翻译
    trans_map = translate_titles(all_en_titles) if do_translate else {}
    print(f"[翻译] 完成 {len(trans_map)} 条英文标题")

    for cat in categories_out:
        for it in cat["items"]:
            if it["lang"] == "en":
                it["zh"] = trans_map.get(it["title"], "")
            else:
                it["zh"] = ""

    render(categories_out, settings)


def fmt_time(ts):
    if not ts:
        return ""
    try:
        return dt.datetime.fromtimestamp(ts).strftime("%m-%d %H:%M")
    except Exception:
        return ""


def render(categories, settings):
    tz = settings.get("timezone", "Asia/Shanghai")
    os.environ["TZ"] = tz
    try:
        time.tzset()
    except Exception:
        pass
    now = dt.datetime.now().strftime("%Y-%m-%d %H:%M")

    cards = []
    for cat in categories:
        meta = cat["meta"]
        rows = []
        for it in cat["items"]:
            t = fmt_time(it["ts"])
            if it["lang"] == "en" and it.get("zh"):
                main = html.escape(it["zh"])
                sub = f'<div class="orig">{html.escape(it["title"])}</div>'
            else:
                main = html.escape(it["title"])
                sub = ""
            rows.append(f'''<li>
        <a href="{html.escape(it['link'])}" target="_blank" rel="noopener">{main}</a>
        {sub}
        <div class="meta"><span class="src">{html.escape(it['source'])}</span>{(' · ' + t) if t else ''}</div>
      </li>''')
        items_html = "\n".join(rows) if rows else '<li class="empty">暂无内容</li>'
        emoji = meta.get('emoji', '')
        heading = f"{emoji} {html.escape(meta['name'])}".strip()
        cards.append(f'''<section class="card" data-cat="{meta.get('id', '')}">
      <h2>{heading} <span class="count">{len(cat['items'])}</span></h2>
      <ul>
{items_html}
      </ul>
    </section>''')

    cards_html = "\n".join(cards)
    page = HTML_TEMPLATE.replace("{{UPDATED}}", now).replace("{{CARDS}}", cards_html)

    os.makedirs(DIST, exist_ok=True)
    with open(os.path.join(DIST, "index.html"), "w", encoding="utf-8") as f:
        f.write(page)
    print(f"[输出] {os.path.join(DIST, 'index.html')}")


HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<meta name="theme-color" content="#0d1117">
<title>每日新闻</title>
<style>
:root{
  --bg:#0d1117; --card:#161b22; --border:#21262d; --text:#e6edf3;
  --muted:#8b949e; --link:#58a6ff; --accent:#238636; --orig:#6e7681;
}
*{box-sizing:border-box;-webkit-tap-highlight-color:transparent}
body{margin:0;background:var(--bg);color:var(--text);
  font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC","Microsoft YaHei",sans-serif;
  line-height:1.5;padding:env(safe-area-inset-top) 0 env(safe-area-inset-bottom)}
header{position:sticky;top:0;z-index:10;background:rgba(13,17,23,.85);
  backdrop-filter:saturate(180%) blur(12px);border-bottom:1px solid var(--border);
  padding:14px 16px}
header h1{margin:0;font-size:18px;display:flex;align-items:center;gap:8px}
header .upd{color:var(--muted);font-size:12px;margin-top:2px}
.tabs{display:flex;gap:6px;overflow-x:auto;padding:10px 16px 0;scrollbar-width:none}
.tabs::-webkit-scrollbar{display:none}
.tab{flex:0 0 auto;padding:6px 12px;border:1px solid var(--border);border-radius:999px;
  color:var(--muted);font-size:13px;background:var(--card);cursor:pointer;white-space:nowrap}
.tab.active{color:#fff;border-color:var(--accent);background:var(--accent)}
main{padding:12px 16px 40px;max-width:720px;margin:0 auto}
.card{background:var(--card);border:1px solid var(--border);border-radius:14px;
  padding:6px 14px 8px;margin-bottom:14px}
.card h2{font-size:15px;margin:10px 2px;display:flex;align-items:center;gap:6px}
.card .count{color:var(--muted);font-size:12px;font-weight:normal;
  background:var(--bg);border:1px solid var(--border);border-radius:999px;padding:0 8px;margin-left:auto}
.card ul{list-style:none;margin:0;padding:0}
.card li{padding:11px 2px;border-top:1px solid var(--border)}
.card li:first-child{border-top:none}
.card li a{color:var(--text);text-decoration:none;font-size:15px;display:block}
.card li a:active{color:var(--link)}
.orig{color:var(--orig);font-size:12.5px;margin-top:3px}
.meta{color:var(--muted);font-size:12px;margin-top:5px}
.src{color:var(--link)}
.empty{color:var(--muted)}
footer{text-align:center;color:var(--muted);font-size:12px;padding:20px}
@media(prefers-color-scheme:light){
  :root{--bg:#f6f8fa;--card:#fff;--border:#d0d7de;--text:#1f2328;--muted:#656d76;--orig:#8c959f}
  header{background:rgba(246,248,250,.85)}
}
</style>
</head>
<body>
<header>
  <h1>📰 每日新闻</h1>
  <div class="upd">更新于 {{UPDATED}}</div>
</header>
<div class="tabs" id="tabs"><span class="tab active" data-target="all">全部</span></div>
<main id="main">
{{CARDS}}
</main>
<footer>自动更新 · GitHub Actions + Pages<br>「投资前瞻」仅为媒体观点与新闻聚合，不构成投资建议，入市有风险。</footer>
<script>
// 生成分类筛选 tab
const tabs=document.getElementById('tabs');
document.querySelectorAll('.card').forEach(c=>{
  const h=c.querySelector('h2').textContent.replace(/\s*\d+\s*$/,'').trim();
  const t=document.createElement('span');
  t.className='tab';t.dataset.target=c.dataset.cat;t.textContent=h;
  tabs.appendChild(t);
});
tabs.addEventListener('click',e=>{
  const tab=e.target.closest('.tab');if(!tab)return;
  tabs.querySelectorAll('.tab').forEach(x=>x.classList.remove('active'));
  tab.classList.add('active');
  const tgt=tab.dataset.target;
  document.querySelectorAll('.card').forEach(c=>{
    c.style.display=(tgt==='all'||c.dataset.cat===tgt)?'':'none';
  });
  window.scrollTo({top:0,behavior:'smooth'});
});
</script>
</body>
</html>"""


if __name__ == "__main__":
    build()
