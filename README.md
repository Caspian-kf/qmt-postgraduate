# 空白爬虫模板

这是一个可复用的 Python 爬虫项目模板，默认不采集任何真实网站数据。你可以在此基础上添加目标站点、请求参数、解析规则和保存逻辑。

## 目录结构

```text
crawler-template/
├── README.md
├── requirements.txt
├── .gitignore
├── config/
│   └── config.example.json
├── crawler/
│   └── run.py
├── data/
│   └── .gitkeep
└── logs/
    └── .gitkeep
```

## 快速开始

安装依赖：

```bash
pip install -r requirements.txt
```

复制配置文件：

```bash
copy config\config.example.json config\config.json
```

运行模板：

```bash
python crawler\run.py
```

## 合规提醒

- 只采集公开页面信息。
- 不采集需要登录、验证码、付费墙后的内容。
- 不绕过反爬机制。
- 不采集个人隐私信息。
- 遵守 robots.txt、网站用户协议和相关法律法规。
