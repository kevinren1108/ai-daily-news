# 📰 每日新闻 (Daily News)

每天定时抓取多个 RSS 新闻源，按分类聚合，英文标题自动翻译成中文，生成一个手机友好的网页，托管在 GitHub Pages 上。全程跑在 GitHub Actions 免费额度里，零成本。

- 分类：科技/AI、财经/股市、国际/时事、开发者/极客
- 中英文源混合，英文标题翻成中文（原文保留，点开可见）
- 手机端优化：暗色模式、分类筛选 tab、点书签即看

## 部署到你的 GitHub（kevinren）

只需要做一次，之后全自动。

1. **建仓库**
   在 GitHub 新建一个仓库，比如 `daily-news`。建议设为 **Public**（Public 仓库的 Actions 分钟数无限免费）。

2. **上传这些文件**
   把本文件夹里的所有内容传上去，保持目录结构：
   ```
   daily-news/
   ├── build.py
   ├── feeds.json
   ├── requirements.txt
   ├── README.md
   └── .github/workflows/daily.yml
   ```
   网页方式：仓库页面 → Add file → Upload files，把文件拖进去。
   （`.github/workflows/daily.yml` 这种带文件夹的，直接在上传框输入 `.github/workflows/daily.yml` 当文件名即可。）

   命令行方式：
   ```bash
   git init
   git add .
   git commit -m "init daily news"
   git branch -M main
   git remote add origin https://github.com/kevinren/daily-news.git
   git push -u origin main
   ```

3. **开启 GitHub Pages**
   仓库 → Settings → Pages → Build and deployment → Source 选 **GitHub Actions**。

4. **跑第一次**
   仓库 → Actions → 左侧选 “Daily News” → 右上 “Run workflow” 手动点一次。
   跑完后在 Settings → Pages 顶部会显示网址，形如：
   `https://kevinren.github.io/daily-news/`

5. **手机上看**
   手机浏览器打开上面的网址，加到主屏幕/书签。以后每天早上自动更新，打开就是最新的。

## 定时设置

`.github/workflows/daily.yml` 里：
```
- cron: "0 22 * * *"   # UTC 22:00 = 北京时间 06:00
```
改时间就改这行（用 UTC，北京时间减 8 小时）。想一天多次，可加多行 cron。

注意两个 GitHub 的“脾气”：
- 定时任务在高峰期会延迟几分钟到几十分钟，不保证准点。
- 仓库连续 60 天没有任何 commit，定时任务会被自动暂停。每天有更新一般不会触发，真被暂停了进 Actions 点一下手动跑即可恢复。

## 加 / 删新闻源

改 `feeds.json`，往对应分类的 `feeds` 里加一条：
```json
{ "name": "源名字", "url": "RSS地址", "lang": "zh" }
```
`lang`: `zh` = 中文（不翻译）；`en` = 英文（标题翻成中文）。push 上去下次自动生效。

## 本地试跑

```bash
pip install -r requirements.txt
python build.py
# 打开 dist/index.html
```
> 注：本地能不能抓到源取决于你的网络能不能访问那些站。GitHub 服务器在海外，抓取和翻译都没问题——你只是点链接时可能需要梯子访问个别境外站。

## 关于免费额度

- Public 仓库：Actions 分钟数 **无限免费**，Pages 免费。
- Private 仓库：每月 2000 分钟免费，这个任务一天就 1–3 分钟，完全够。

翻译用的是 `deep-translator` 调 Google 翻译网页端，免费、不需要 API key。
