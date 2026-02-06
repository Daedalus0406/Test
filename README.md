# 工作站整合介面設計提案

以下整理你補充的需求，並提供可落地的實作建議（以 Node-RED + PLC + 檔案儲存為核心）。

## 需求摘要

- **更新頻率**：每秒 1 筆。
- **資料欄位**：`Tag name`、`Time (hh:mm:ss)`、`Value`。
- **資料儲存**：每次啟動建立「日期資料夾」，使用者開始紀錄後建立一個檔案，含 `Temperature`、`Pressure`、`Flow rate` 三個 sheet，持續寫入 **最多 24 小時**；停止紀錄時，檔名改為 `開始時間_結束時間`（`hhmmss` 格式）。
- **Config**：JSON 格式，能切換不同設備組合（例如 2 顆或 3 顆幫浦）。

## 1. 檔案儲存設計（CSV / Excel）

### 建議格式
- **首選 Excel（.xlsx）**：符合「三個 sheet」的需求。
- **備選 CSV**：每個類別一個檔案（`Temperature.csv`、`Pressure.csv`、`FlowRate.csv`），但需在 UI 層再聚合。

### 檔案與資料夾命名規則
- **資料夾**：每次執行程式時建立 `YYYY-MM-DD/`。
- **檔案**：使用者開始紀錄時先建立暫存名稱（例如 `recording.xlsx`）；停止時改名為 `HHMMSS_HHMMSS.xlsx`。

### 檔案結構範例
```
/2024-06-01/
  recording.xlsx     (進行中)
  090001_093000.xlsx  (完成)
  100005_120000.xlsx  (完成)
```

### Sheet 欄位定義
每個 sheet 固定欄位：
| Tag name | Time (hh:mm:ss) | Value |
|---|---|---|

### 24 小時上限處理
- 開始紀錄後，記錄「開始時間」；當經過 24 小時即自動停止並進行封存與改名。
- 若未手動停止，也會在 24 小時結束時自動切檔。

### 寫入與鎖定建議
- Node-RED 端 **避免每秒直接寫入 Excel**（可能造成檔案鎖定與性能問題）。
- 建議流程：
  1. Node-RED 每秒收集資料後送到 **本地緩衝（記憶體/Queue）**。
  2. 每 5-10 秒批次寫入 Excel（減少 IO）。
  3. 停止時再 flush buffer。

可用 Node.js 的 `xlsx` 或 `exceljs` 套件，或由 Node-RED 使用 `exec` 觸發自訂寫入腳本。

## 2. Config JSON 設計（設備組合驅動）

### 目的
- 透過 JSON 控制不同的工作站組態（2 泵/3 泵、不同感測器、UI 元件顯示）。

### 範例 JSON
```json
{
  "stationId": "A-01",
  "devices": {
    "pumps": [
      { "id": "P1", "modbusAddress": 1, "tags": ["P1_Start", "P1_Speed"] },
      { "id": "P2", "modbusAddress": 2, "tags": ["P2_Start", "P2_Speed"] }
    ],
    "heaters": [
      { "id": "H1", "modbusAddress": 11, "tags": ["H1_On", "H1_Temp"] }
    ]
  },
  "visualization": {
    "trends": ["Temperature", "Pressure", "Flow rate"],
    "refreshSeconds": 1
  }
}
```

### Node-RED 解析方式
- 啟動時讀取 JSON（File in → JSON node → Flow context）。
- 透過 `function node` 動態生成 UI 控制元件與 Modbus 連線設定。

## 3. 介面功能整合建議

### 控制介面
- Node-RED Dashboard / FlowFuse Dashboard（新版）
- UI 元件依 config 生成：開關、滑桿、狀態燈、警示。

### 即時趨勢
- 即時圖表以 `ui_chart` 顯示（每秒更新）。
- 資料來源為即時緩衝而不是檔案本身。

### 歷史資料可視化
- 停止紀錄後的 Excel 檔可離線開啟。
- 或提供一個「讀取歷史檔案」的 Node-RED flow，將 Excel 轉成 chart data。

## 4. 建議流程總結

1. Node-RED 從 PLC 讀值（Modbus TCP）。
2. 資料每秒送入即時圖表與本地緩衝。
3. 每 5-10 秒批次寫入 Excel 三個 sheet。
4. 使用者按下「停止」，rename 檔案為 `開始_結束`。
5. 24 小時自動切檔。

## 5. 後續可以實作的內容

- Node-RED 寫入 Excel 的範例 flow / script。
- config-driven UI 自動產生節點（或以 subflow 載入）。
- 歷史資料讀取與 UI 顯示。

## 6. 完全取代 Node-RED 與 InfluxDB 的方案

如果希望**完全不使用 Node-RED 與 InfluxDB**，可以改為「自製資料採集服務 + Web 介面」的架構。以下提供兩種常見做法：

### 方案 A：Python（FastAPI）+ 本地檔案（Excel/CSV）

**適合條件**
- 需求以檔案存檔為主，不需要大型時序資料庫。
- 需要快速開發 API 與 Web UI。

**核心組件**
- PLC 通訊：`pymodbus`（Modbus TCP）。
- Web API：`FastAPI`。
- UI：`React` 或簡單 `HTML/JS` + `Plotly`。
- 檔案寫入：`openpyxl` / `pandas`。
- 排程/背景任務：`APScheduler` 或 `asyncio`。

**流程**
1. FastAPI 啟動後讀取 JSON config，初始化設備清單。
2. 後台協程每秒讀取 PLC 資料，送到記憶體 buffer。
3. 每 5–10 秒 flush 到 Excel（`Temperature`/`Pressure`/`Flow rate` sheet）。
4. 提供 `/start` `/stop` API 控制錄製，停止時改名 `HHMMSS_HHMMSS.xlsx`。
5. UI 前端透過 API 顯示即時趨勢、控制按鈕與歷史檔案列表。

**本專案已提供方案 A 的可執行骨架**

1. 安裝依賴：
   ```bash
   pip install -r requirements.txt
   ```
2. 編輯 `config.json`（設定站點、tags、資料來源）。
3. 啟動服務：
   ```bash
   uvicorn app.main:app --reload
   ```
4. 操作 API：
   - `POST /start` 開始錄製
   - `POST /stop` 停止錄製並改名
   - `GET /status` 查詢狀態
   - `GET /history` 取得歷史檔案清單
   - `GET /config` 檢視目前 config

### 方案 B：Node.js（Express）+ 前端 + 檔案

**適合條件**
- 希望延續 Node 生態但不使用 Node-RED。
- 前端與後端都可用 JS 開發。

**核心組件**
- PLC 通訊：`jsmodbus` / `modbus-serial`。
- Web API：`Express` 或 `Fastify`。
- UI：`React` / `Vue` + `ECharts` 或 `Plotly`。
- 檔案寫入：`exceljs` / `xlsx`。

**流程**與方案 A 相同：後端負責 PLC 讀取與檔案存檔，前端顯示控制與趨勢。

### 優點與注意事項

**優點**
- 完全掌控 UI 與流程，方便擴展。
- 不受 Node-RED Dashboard 的限制。

**注意事項**
- 必須自行處理：重連機制、錯誤重試、資料緩衝、檔案鎖定。
- 需要自行設計權限控管與安全性（避免誤操作）。

---

如果你希望我提供 **Node-RED Flow 範例** 或是 **Excel 寫入腳本**，請告訴我你偏好用：
- Node-RED function node + npm 套件（exceljs）
- 由 Node-RED 呼叫外部 Python 腳本（openpyxl）
