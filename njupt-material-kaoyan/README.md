# 南京邮电大学材料考研信息采集与分析系统

## 1. 项目简介

本项目是一个“纯静态网页 + 本地 Python 爬虫”的南京邮电大学材料考研信息采集与分析系统。当前版本已升级为真实公开数据采集版，重点整理南京邮电大学材料科学与工程学院、南京邮电大学研究生招生信息网公开发布的硕士研究生招生、复试、调剂、拟录取、复试分数线和报考录取情况信息。

项目不使用 Flask、Django、FastAPI，不使用数据库。爬虫在本地运行后生成 JSON/CSV 文件，网页通过 GitHub Pages 静态展示。

## 2. 功能模块

- 首页仪表盘：展示信息总数、采集年份数、分数线记录数、录取统计记录数、考试信息记录数和最近采集时间。
- 信息列表：展示原始公开信息摘要，支持类别、来源、年份和关键词筛选。
- 历年分数线：展示历年复试分数线，支持年份筛选、专业筛选和按分数排序。
- 录取统计：展示计划招生、复试人数、录取人数、调剂人数和分数聚合统计；不保存考生个人明细。
- 分析图表：使用 ECharts 展示复试线趋势、专业分数线对比、录取人数、信息类别和来源分布。
- 本地爬虫：使用 `requests`、`BeautifulSoup`、`pandas.read_html`、`openpyxl`、可选 `pdfplumber` 采集和解析公开网页及公开附件。

## 3. 数据文件

| 文件 | 说明 |
| --- | --- |
| `data/kaoyan_materials.json` / `.csv` | 原始公开信息列表 |
| `data/score_lines.json` / `.csv` | 历年复试分数线 |
| `data/admission_stats.json` / `.csv` | 录取情况聚合统计 |
| `data/exam_info.json` / `.csv` | 考试科目、考试大纲、参考书目信息 |

所有 JSON 使用 `ensure_ascii=False` 保存，所有 CSV 使用 `utf-8-sig` 编码。

## 4. 技术栈

- 前端：HTML、CSS、JavaScript
- 图表：ECharts CDN
- 数据格式：JSON、CSV
- 爬虫：Python、requests、BeautifulSoup、pandas、lxml、openpyxl、pdfplumber
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
│   ├── kaoyan_materials.csv
│   ├── score_lines.json
│   ├── score_lines.csv
│   ├── admission_stats.json
│   ├── admission_stats.csv
│   ├── exam_info.json
│   └── exam_info.csv
└── docs/
    ├── index.html
    ├── data.html
    ├── score.html
    ├── admission.html
    ├── analysis.html
    ├── css/
    │   └── style.css
    └── js/
        └── main.js
```

根目录 `docs/` 是 GitHub Pages 发布目录，内容由 `njupt-material-kaoyan/docs/` 和 `njupt-material-kaoyan/data/` 同步而来。

## 6. 本地运行方式

安装依赖：

```bash
pip install -r requirements.txt
```

运行本地爬虫：

```bash
cd njupt-material-kaoyan
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

## 7. GitHub Pages 部署方式

当前仓库推荐方式：

1. 将项目提交并推送到 GitHub 仓库。
2. 进入仓库 `Settings`。
3. 打开 `Pages`。
4. `Build and deployment` 选择 `Deploy from a branch`。
5. 分支选择 `main`，目录选择 `/docs`。
6. 部署后访问：

```text
https://你的用户名.github.io/仓库名/
```

## 8. 数据采集流程

1. 读取已有 JSON 文件，支持断点续爬。
2. 优先扫描材料学院“硕士生招生”栏目和研究生招生信息网公开栏目。
3. 按“复试分数线、招生简章、专业目录、考试大纲、复试、拟录取、综合成绩、调剂、参考书”等关键词筛选。
4. 对详情页提取标题、发布时间、正文摘要、附件链接。
5. 对复试分数线页面优先使用 `pandas.read_html` 解析网页表格；无法标准解析时保留来源链接。
6. 对拟录取、复试成绩、综合成绩页面只做聚合统计，不保存姓名、准考证号、身份证号、手机号等个人信息。
7. 附件下载仅用于本地解析，`data/raw/` 被 Git 忽略，不提交到 GitHub。
8. 每次运行结束生成四类 JSON 和 CSV。

## 9. 后续优化方向

- 继续补充分数线和招生目录的字段映射规则。
- 增加更多附件格式解析能力。
- 增加数据质量检查和人工核验标记。
- 增加分页、关键词高亮和多专业对比。
- 将低频合规采集接入 GitHub Actions。

## 10. 免责声明

本项目仅用于学习与研究，采集公开页面信息，不用于商业用途；不采集隐私信息，不绕过登录、验证码、付费墙或反爬机制。页面数据由公开网页采集整理，可能存在滞后或解析误差，最终信息以南京邮电大学官方发布为准。使用者应遵守目标网站的 `robots.txt`、网站服务条款以及相关法律法规。
