# 南京邮电大学材料考研信息采集与分析系统

## 1. 项目简介

本项目是一个面向南京邮电大学材料科学与工程相关考研公开信息的采集与展示系统。系统通过本地 Python 爬虫采集公开网页信息，生成 `JSON` 和 `CSV` 数据文件，再由纯静态网页读取数据并展示统计结果。

当前版本为第一版静态项目，不使用 Flask、Django、FastAPI 等后端框架，不使用数据库，适合后续部署到 GitHub Pages。

## 2. 功能模块

- 首页仪表盘：展示项目简介、总信息数量、分类数量和最近采集时间。
- 数据列表页：展示学校、学院、专业、类别、标题、摘要、发布时间、来源、原文链接、采集时间。
- 数据筛选：支持按类别筛选、按来源筛选、按关键词搜索。
- 分析图表页：使用 ECharts 展示类别数量、来源数量和年份数量统计图。
- 本地爬虫：使用 `requests` + `BeautifulSoup` 采集公开页面，并输出 `data/kaoyan_materials.json` 与 `data/kaoyan_materials.csv`。

## 3. 数据字段说明

每条数据包含以下字段：

| 字段 | 含义 |
| --- | --- |
| `school` | 学校名称，固定为南京邮电大学 |
| `college` | 学院名称，固定为材料科学与工程学院 |
| `major` | 专业名称，固定为材料科学与工程 |
| `category` | 信息类别，如招生简章、专业目录、考试大纲、复试细则、拟录取名单、调剂信息、经验贴、其他 |
| `title` | 信息标题 |
| `content` | 正文摘要 |
| `publish_time` | 原网页发布时间 |
| `url` | 原文链接 |
| `source` | 来源网站 |
| `crawl_time` | 本地采集时间 |

## 4. 技术栈

- 前端：HTML、CSS、JavaScript
- 图表：ECharts CDN
- 数据格式：JSON、CSV
- 爬虫：Python、requests、BeautifulSoup、pandas、lxml
- 部署：GitHub Pages

## 5. 项目目录结构

```text
njupt-material-kaoyan/
├── README.md
├── requirements.txt
├── .gitignore
├── crawler/
│   └── run_kaoyan.py
├── data/
│   ├── kaoyan_materials.json
│   └── kaoyan_materials.csv
└── docs/
    ├── index.html
    ├── data.html
    ├── analysis.html
    ├── css/
    │   └── style.css
    └── js/
        └── main.js
```

## 6. 本地运行方式

安装依赖：

```bash
pip install -r requirements.txt
```

运行本地爬虫：

```bash
python crawler/run_kaoyan.py
```

启动静态网页服务：

```bash
python -m http.server 8000
```

浏览器访问：

```text
http://localhost:8000/docs/index.html
```

说明：由于浏览器安全限制，直接双击打开 HTML 文件时，`fetch` 读取本地 JSON 可能失败。建议使用 `python -m http.server` 启动本地静态服务。

## 7. GitHub Pages 部署方式

推荐方式：

1. 将项目提交并推送到 GitHub 仓库。
2. 进入仓库 `Settings`。
3. 打开 `Pages`。
4. `Build and deployment` 选择 `Deploy from a branch`。
5. 分支选择 `main`，目录选择 `/root`。
6. 部署后访问：

```text
https://你的用户名.github.io/仓库名/njupt-material-kaoyan/docs/index.html
```

本项目的网页默认从 `../data/kaoyan_materials.json` 读取数据。使用 `/root` 发布时，`docs/` 与 `data/` 的相对路径可以保持正常。

## 8. 数据采集流程

1. 程序启动后读取已有 `data/kaoyan_materials.json`。
2. 以南京邮电大学材料科学与工程学院官网、南京邮电大学研究生招生信息网等公开页面为入口。
3. 从公开列表页解析候选链接。
4. 按南京邮电大学、材料、硕士研究生、考研、复试、调剂、拟录取、专业目录、考试大纲等关键词过滤。
5. 按标题规则自动分类。
6. 根据 `url` 去重；如果 `url` 为空，则根据 `title + content` 去重。
7. 每新增 20 条执行一次保存。
8. 程序结束后生成 JSON 和 CSV 文件。

分类规则：

- 标题包含“招生简章”：`招生简章`
- 标题包含“专业目录”：`专业目录`
- 标题包含“大纲”：`考试大纲`
- 标题包含“复试”：`复试细则`
- 标题包含“拟录取”或“综合成绩”：`拟录取名单`
- 标题包含“调剂”：`调剂信息`
- 标题包含“经验”或“经验贴”：`经验贴`
- 其他：`其他`

参考书目等未单独列入枚举的内容，在当前版本中归入 `其他`。

## 9. 后续优化方向

- 补充更多官方公开列表页入口。
- 增加 PDF、DOC、XLS 附件的元信息解析。
- 增加数据更新时间趋势图。
- 增加关键词高亮和分页。
- 增加数据质量检查脚本。
- 将采集任务接入 GitHub Actions，并保持低频、合规运行。
- 为不同年份建立可切换的数据视图。

## 10. 免责声明

本项目仅用于学习与研究，采集公开页面信息，不用于商业用途；不采集隐私信息，不绕过登录、验证码、付费墙或反爬机制。所有信息以原发布网站内容为准，项目作者不对信息的完整性、实时性和准确性作承诺。使用者应遵守目标网站的 `robots.txt`、网站服务条款以及相关法律法规。
