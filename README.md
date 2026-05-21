# Flight Monitor — 机票价格监控系统

自动抓取携程机票价格，监控多城市往返乌鲁木齐航线，支持飞书/飞鸽通知。

## 功能概述

- **多机场同时监控** — 支持 7 个出发机场（SHA/PVG/HGH/NKG/WUX/CZX/NTG）同时搜索往返乌鲁木齐（URC）的航班
- **价格分项显示** — 将总价拆为裸票、燃油附加费、机建费，并标注价格渠道（英文 key + 中文名）
- **机场中英文显示** — 机场名同时显示英文代码和中文简称，如 `SHA(上海虹桥)→URC(乌鲁木齐天山)`
- **仅直飞航班** — 自动过滤中转/经停航班，保留直飞
- **免费行李额筛选** — 默认只收录有免费托运行李额的航班
- **历史价格对比** — 记录每次查询，发现价格变动时标注涨跌幅度
- **趋势分析** — 最优组合与上次查询对比，输出涨跌百分比
- **基准对比** — 以 SHA/PVG 上海机场最低价作为基准线，展示各方案溢价
- **多渠道通知** — 支持飞书 Webhook 和飞鸽（Lark CLI）群通知
- **降价告警** — 票价降幅超过阈值时单独推送降价提醒
- **定时调度** — 默认每 6 小时自动查询一次，支持单次运行

## 项目结构

```
flight-monitor/
├── main.py                  # 入口：CLI 参数解析 + 定时调度
├── searcher.py              # 携程页面爬取 + batchSearch API 解析
├── analyzer.py              # 数据分析：最优组合、价格变动、趋势计算
├── database.py              # SQLite 数据库：建表、迁移、读写
├── notifier.py              # 报告格式化 + 飞书/飞鸽通知
├── config_loader.py         # YAML 配置加载与校验
├── anti_detect.py           # 反检测：UA 轮换池 + 随机延迟
├── config.yaml              # 配置文件（航班日期、通知渠道等）
├── requirements.txt         # Python 依赖
├── tests/
│   ├── test_searcher.py     # 搜索 & 解析单元测试
│   ├── test_searcher_integration.py  # 搜索集成测试
│   ├── test_analyzer.py     # 分析逻辑单元测试
│   ├── test_database.py     # 数据库读写测试
│   ├── test_notifier.py     # 报告格式 & 通知测试
│   ├── test_anti_detect.py  # UA/延迟测试
│   └── test_config_loader.py # 配置加载测试
└── data/
    ├── flights.db           # SQLite 数据库文件（自动生成）
    └── debug_api/           # API 响应抓包样本（调试用）
```

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
playwright install chromium
```

### 2. 配置

编辑 `config.yaml`：

```yaml
flight:
  outbound_date: "2026-09-25"       # 去程日期（YYYY-MM-DD）
  return_date: "2026-10-07"         # 回程日期
  departure_airports:               # 出发机场列表
    - code: SHA
      city: "上海"
    - code: PVG
      city: "上海"
    # ... 更多机场
  arrival_airport:                  # 目的地（目前固定为乌鲁木齐）
    code: URC
    city: "乌鲁木齐"
  return_airports:                  # 返程到达机场（通常与出发列表一致）
    - code: SHA
      city: "上海"
    # ... 更多机场

schedule:
  interval_hours: 6                 # 定时查询间隔（小时）

notification:
  feishu_webhook: "https://open.feishu.cn/open-apis/bot/v2/hook/XXXX"
  # lark_chat_id: "oc_xxx"         # 飞鸽群聊 ID（与 feishu 二选一）
  price_drop_threshold: 200         # 降价告警阈值（元）

anti_detect:
  min_delay: 15                     # 每次搜索最小间隔（秒）
  max_delay: 30                     # 最大间隔
  proxy: null                       # 代理设置，如 "http://127.0.0.1:7890"

database:
  path: "data/flights.db"
```

### 3. 运行

```bash
# 单次查询（调试用）
python main.py --once

# 启动定时调度（默认每 6 小时一次）
python main.py

# 立即运行一次，然后启动调度
python main.py --now
```

## 核心设计

### 价格构成

总价 = 裸票价（`adultPrice`）+ 燃油附加费 + 机建费

| 费用项 | 计算方式 |
|--------|----------|
| 裸票 | 从携程 `batchSearch` API 的 `priceList[0].adultPrice` 获取 |
| 燃油附加费 | 飞行距离 ≤800km 收 ¥90，>800km 收 ¥170 |
| 机建费 | 固定 ¥50（民航发展基金） |

飞行距离使用 **Haversine 公式** 按机场经纬度计算。

### 渠道标注

每个航班标注价格渠道，优先匹配 `priceList[0].key`，找不到时回退到 `groupType`：

| Key | 中文名 | GroupType | 中文名 |
|-----|--------|-----------|--------|
| JPFWB | 机票服务包 | Airline | 航司直连 |
| GFFX_HO | 吉祥官方旗舰 | Priority | 优选 |
| CZCW | 畅行舱位 | Service_Packages | 服务包 |
| JJCZL | 经济舱直连 | Favorable | 特惠 |
| ... | ... | | |

完整映射表见 `searcher.py` 中的 `_CHANNEL_CN` 和 `_GROUP_CN`。

### 机场显示

机场名称显示为 `英文代码(中文简称)` 格式，如 `SHA(上海虹桥)`、`URC(乌鲁木齐天山)`。已知机场优先从映射表取简称，未知机场自动从全名中提取（去掉"国际机场""机场"后缀）。

### 报告样例

```
✈️ 机票监控报告 - 2026-05-21 14:00

📊 上海基准: 去程最低 ¥2,630 (SHA) | 回程最低 ¥2,080 (SHA)

🏆 最优组合 Top 5:

1. 去程: SHA(上海虹桥)→URC(乌鲁木齐天山) HO1255 吉祥航空 空客321(中)
        T2 10:05→15:25 (5h20m) ¥3,410
        裸票¥3,190 + 燃油¥170 + 机建¥50 [JPFWB 机票服务包]
        行李: 托运行李额20KG
   回程: URC(乌鲁木齐天山)→SHA(上海虹桥) HO1256 吉祥航空 空客321(中)
        T2 17:00→22:00 (5h0m) ¥3,200
        裸票¥2,980 + 燃油¥170 + 机建¥50 [JPFWB 机票服务包]
        行李: 托运行李额20KG
   总价: ¥6,610  (较上海基准 +¥0)

---
📉 价格趋势: 较上次查询 降3.5%
```

### 数据库

SQLite 存储在 `data/flights.db`，表 `flight_prices` 包含 27 个字段，每次查询追加新记录。使用前向兼容的迁移机制，新增字段通过 `ALTER TABLE` 自动添加。

### 反检测

- **User-Agent 轮换池** — 10 个来自主流浏览器的真实 UA
- **随机延迟** — 每次搜索之间随机休眠 15-30 秒
- **无头浏览器** — 启动参数禁用自动化标识
- **失败自保** — 搜索失败时自动保存截图和 HTML 至 `data/` 目录

## 测试

```bash
# 运行全部 83 个测试
python -m pytest tests/ -v

# 只跑特定模块
python -m pytest tests/test_searcher.py -v
python -m pytest tests/test_analyzer.py -v
```

## 技术栈

| 组件 | 技术 |
|------|------|
| 浏览器自动化 | Playwright (Chromium) |
| 定时调度 | APScheduler |
| 数据存储 | SQLite |
| 配置管理 | PyYAML |
| 通知 | Feishu Webhook / Lark CLI |
| 测试 | pytest + pytest-httpx |

## 许可

MIT
