~~~markdown
# AlphaCraft 智能量化选股平台

基于公开行情/财务数据，做多因子集成评分与滚动样本外回测。

> **⚠️ 免责声明**：本平台仅用于研究与回测，不包含下单、券商连接或实盘交易功能；模型输出不构成投资建议。

---

## 核心架构与数据流

```text
AKShare 公开数据
  → 技术 / 量价 / K线 / 基本面因子构建
  → LightGBM 滚动训练（横截面 rank 归一化，预测未来超额收益）
  → 舆情关键词评分（可审计词典）
  → 五维综合评分（0–100）
  → 滚动样本外回测（成本 / 滑点 / 涨跌停 / 停牌 / 容量 / 行业约束）
~~~

### 技术栈分层

| 层级         | 技术栈                                                     | 说明                                   |
| ------------ | ---------------------------------------------------------- | -------------------------------------- |
| **前端**     | React 18 · TypeScript · Vite 6 · Tailwind CSS 4 · Recharts | 单页应用，包含五个研究视图             |
| **后端**     | FastAPI · Uvicorn · Pydantic                               | REST API + 后台任务 + 托管前端构建产物 |
| **核心模型** | Python 3.10 · LightGBM · scikit-learn · pandas · numpy     | 因子构建、滚动训练、评分、回测         |
| **数据**     | AKShare（东财 / 腾讯 / 交易所接口）                        | 逐股行情、时点元数据、舆情             |

> **部署说明**：前端构建产物 `dist/` 由 FastAPI 直接托管，本地/生产运行只需启动后端一个进程；开发时可分别启动 Vite 与 FastAPI 以获得热更新。

------

## 目录结构

```text
stock-selection-model/
├── server.py                # FastAPI 后端：REST API + 托管 dist/
├── app.py                   # 遗留 Streamlit 界面（可选）
├── run_model.py             # CLI：训练并输出候选股票
├── download_data.py         # CLI：下载行情数据
├── fetch_metadata.py        # CLI：抓取并归档时点元数据
├── stock_model/             # 核心模型与数据管道（Python 包）
│   ├── data.py              #   行情下载 / 面板加载 / 增量更新
│   ├── features.py          #   因子构建（21 个无量纲技术因子 + 可选基本面因子）
│   ├── model.py             #   LightGBM 滚动训练与排名
│   ├── research.py          #   五维评分 + 滚动样本外回测主流程
│   ├── sentiment.py         #   舆情关键词词典评分
│   ├── benchmarks.py        #   外部基准收益（时点对齐）
│   ├── metadata.py          #   时点元数据采集与历史对齐
│   ├── pool.py              #   本地股票池管理
│   ├── quality.py           #   数据质量诊断与修复
│   ├── governance.py        #   验证门禁 + 版本化运行清单（可复现）
│   └── export.py            #   Excel / PDF 报告导出
├── src/                     # 前端源码
│   ├── App.tsx · main.tsx · types.ts
│   ├── api/client.ts        #   FastAPI 客户端
│   ├── components/          #   五个视图 + 导航 / 术语提示 / 错误边界
│   └── utils/               #   评分与回测工具
├── dist/                    # 前端构建产物（由 FastAPI 托管）
├── data/
│   ├── raw/                 # 逐股行情 parquet
│   └── archive/             # 每日元数据 / 评分 / 舆情 / 情绪快照
├── output/                  # 评分 / 回测 / 研究记录产物
├── tests/                   # pytest 测试
├── requirements.txt · package.json · vite.config.ts
└── start_fullstack.bat · start_web.bat
```

------

## 快速开始

### 1. 环境配置

```powershell
conda create -n stock-model python=3.10 -y
conda activate stock-model
pip install -r requirements.txt
```

### 2. 下载研究数据

```powershell
# 少量股票验证流程
python download_data.py --symbols 000001,600000,600519 --start 20180101 --end 20260808

# 按当前成交额下载前 N 只（仅流程验证；严肃回测应提供每个历史日期的股票池，避免幸存者偏差）
python download_data.py --top-n 100 --start 20180101 --end 20260808
```

### 3. 启动 Web 界面

**Fullstack（推荐，单进程）：**

```powershell
npm install
npm run build          # 构建前端到 dist/
python server.py       # 或双击 start_fullstack.bat
```

> 浏览器打开 `http://localhost:8000`，API 文档 `http://localhost:8000/docs`。

**开发模式（前后端分离 + 热更新）：**

```powershell
npm run dev            # 前端 http://localhost:3000
python server.py       # 后端 http://localhost:8000（已配置 CORS）
```

**遗留 Streamlit 界面（可选）：**

```powershell
python -m streamlit run app.py    # 或双击 start_web.bat → http://127.0.0.1:8501
```

> 界面仅监听本机地址，不对公网开放。股票检索支持股票代码、中文名称和拼音首字母，例如 `300476`、`胜宏科技` 或 `SHKJ`。

### 4. CLI 训练 / 评分

```powershell
python run_model.py --top-k 20 --horizon 20
```

------

## Web 研究流程（五个视图）

页面按五个视图组织，侧边栏切换，全局显示本地数据资产与后端连接状态：

1. **研究看板（默认页）**：三步研究引导（准备数据 → 综合评分 → 历史回测）带完成状态；速览最新候选与回测净值曲线。
2. **股票池与数据**：按代码、名称或拼音首字母检索并加入股票池；下载为逐只真实进度并报告成功/失败清单，失败可单独重试；支持表格排序、CSV/Excel 导入导出；内置数据质量诊断。
3. **综合评分**：参数与结果同页——运行后展示候选列表、个股正反证据、五维贡献、验证指标与因子重要性；支持导出 CSV / Excel / PDF。候选不会反向改变研究股票池。
4. **历史回测**：滚动训练回测，按总览、有效性、收益风险、执行、暴露、明细组织结果；支持外部基准、买卖成本、滑点、容量、涨跌停、停牌与行业约束。历史舆情不足时会排除舆情维度，不伪装成已验证。
5. **研究记录**：按运行编号追溯数据、参数、验证状态与候选变化；每次运行在 `output/runs/<run_id>/` 保存完整结果文件。

------

## 评分模型

五维综合评分，每维先做横截面 rank 归一化到 0–100，再加权合成：

| 维度                    | 默认权重 | 构成                                                         |
| ----------------------- | -------- | ------------------------------------------------------------ |
| **model (模型分)**      | 0.35     | LightGBM 滚动训练预测值（rank 归一化）                       |
| **technical (技术面)**  | 0.25     | `ret_20` · `ret_60` · `sma_20_ratio` · `vol_20`（低波动占优） |
| **volume_price (量价)** | 0.20     | `volume_ratio_20` · `obv_slope_20` · `money_flow_20` · `vwap_dev` |
| **candle (K线形态)**    | 0.10     | `close_position` · `body_pct` · `lower_shadow_pct` · `upper_shadow_pct` |
| **sentiment (舆情)**    | 0.10     | 关键词词典评分（见下），默认中性 50                          |

> *权重可在界面调整，运行前自动归一化到和为 1。*

### 辅助评分机制

- **舆情维度**：默认尝试读取公开新闻接口，用可审计关键词词典给出 0–100 分；接口不可用、没有新闻或没有历史舆情文件时明确按中性 50 分处理，不伪造覆盖率。词典为分级强度（强 2 / 中 1 / 弱 0.5），支持否定词反转（如「澄清减持传闻」不记负面）、近因时间衰减（3 天内 1.0、7 天内 0.5、30 天内 0.2）与同事件标题去重。
- **市场情绪面**：综合评分页可叠加市场情绪面（上涨家数占比、量能、涨停占比合成，仅判断环境强弱，不改变当日排序）。每次评分的个股快照与市场情绪自动存档到 `data/archive/`，用于日后回测验证舆情与情绪权重。
- **信号可信度**：另按策略一致性（0.30）、条件有效性（0.30）、稳定性（0.20）、维度一致性（0.15）、新闻覆盖率（0.05）合成 `credibility_grade`（高 / 中 / 低），用于对候选信号做门禁审计。

------

## API 端点（节选）

| 方法与路径                                                   | 说明                             |
| ------------------------------------------------------------ | -------------------------------- |
| `GET /api/status`                                            | 系统状态、数据资产、后端在线情况 |
| `GET/POST /api/pool` · `POST /api/pool/batch` · `DELETE /api/pool/{symbol}` | 股票池增删查                     |
| `GET /api/universe/search` · `GET /api/universe/{symbol}/industry` | 全市场检索 / 行业                |
| `POST /api/data/download` · `GET /api/data/download-progress` | 数据下载与进度                   |
| `POST /api/data/sync-metadata` · `POST /api/data/repair-quality` | 元数据同步 / 数据质量修复        |
| `GET /api/stock/{symbol}/history`                            | 单股历史行情                     |
| `GET /api/scores/latest` · `POST /api/scores/run` · `GET /api/scores/run-progress` | 最新评分 / 触发评分 / 进度       |
| `GET /api/backtest/latest` · `POST /api/backtest/run` · `GET /api/backtest/run-progress` | 回测结果 / 触发 / 进度           |
| `GET /api/export/excel` · `/pdf` · `/backtest-csv`           | 报告导出                         |
| `GET /api/governance/status`                                 | 研究门禁审计状态                 |
| `GET /api/runs` · `GET /api/runs/{run_id}`                   | 研究记录列表 / 详情              |

> *完整交互式文档见运行后的 `http://localhost:8000/docs`。*

------

## 测试与输出

### 运行测试

```powershell
pytest tests/
```

> 覆盖数据、因子、元数据、质量/股票池、治理、研究与 API 模块。

### 输出文件说明

结果默认保存在 `output/` 目录下：

- `latest_picks.csv`：最新候选股票及综合评分、五维分项评分、可信度等级
- `latest_scores.csv`：最新交易日全部本地股票评分（行情看板）
- `feature_importance.csv`：模型因子重要性
- `validation_metrics.json`：样本外验证指标（含 IC、分组单调性等）
- `backtest_periods.csv`：每个滚动调仓期的组合、基准与持仓
- `backtest_metrics.json`：累计收益、年化收益、最大回撤、夏普、胜率等
- `runs/<run_id>/`：单次运行的完整结果与清单

------

## 研究注意事项

1. **避免未来函数**：财务数据必须按公告日对齐，不能使用未来信息。
2. **交易摩擦成本**：回测必须加入佣金、印花税、滑点与涨跌停限制（已实现）。当前回测已模拟买卖成本、滑点、涨跌停、停牌、流动性容量与行业集中约束；复权口径、历史成分范围与历史元数据仍需持续核验。
3. **数据源风险**：AKShare 是开源数据接口，接口与上游数据可能变化；重要数据应与交易所或上市公司公告抽样校验。历史行情下载默认尝试东方财富接口，失败时自动回退腾讯历史行情接口，并在结果中标记实际来源。
4. **因子无量纲化**：所有因子统一无量纲化（收益率 / 比率 / 位置量），避免绝对价格尺度在横截面间不可比导致过拟合。
5. **合规提示**：模型输出只是研究结果，不是投资建议。

