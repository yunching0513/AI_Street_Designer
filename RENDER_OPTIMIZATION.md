# Render 冷啟動優化指南

Render 的免費方案在閒置 15 分鐘後會讓服務進入休眠狀態。當有新的請求進來時,服務需要約 50 秒到幾分鐘的時間重新啟動,導致明顯的延遲。

以下是幾種保持服務喚醒的方法:

## 方法一: 使用 UptimeRobot (推薦)

UptimeRobot 是一個免費的監控服務,可以定期 Ping 你的網站,防止它閒置休眠。

### 設定步驟:
1. 到 [UptimeRobot](https://uptimerobot.com/) 註冊免費帳號
2. 點擊 **"Add New Monitor"**
3. 設定監控:
   - **Monitor Type**: HTTP(s)
   - **Friendly Name**: AI Street Designer
   - **URL (or IP)**: 等於你的 Render 應用網址 (例如 `https://your-app-name.onrender.com`)
   - **Monitoring Interval**: 設為 **5 分鐘** (Render 休眠時間為 15 分鐘,所以小於這個時間即可)
4. 點擊 **"Create Monitor"**

這樣 UptimeRobot 就會每 5 分鐘訪問一次你的網站,確保它保持在執行狀態。

## 方法二: 使用 Cron-Job.org

如果 UptimeRobot 不適用,Cron-Job.org 是另一個好選擇。

1. 註冊 [cron-job.org](https://cron-job.org/en/)
2. 創建 Cron Job
3. URL 填入你的 Render 應用網址
4. 排程設為每 10 分鐘執行一次

## 方法三: 升級 Render 方案

如果上述方法不穩定,或者你需要更好的效能:
- Render 的 "Starter" 方案 ($7 美金/月) 不會有休眠機制,且通常回應速度更快。

## 開發者提示

為了讓監控更有效率,我們可以在程式碼中加入一個輕量級的 `/health` 端點 (剛剛已添加),讓監控服務只檢查服務狀態而不載入整個網頁。

你的 `app.py` 中已經有:
```python
@app.route('/health')
def health():
    return jsonify({'status': 'ok', ...})
```

所以在設定 UptimeRobot 時,URL 可以填入 `https://你的網址/health`,減少資源消耗。

## AI 圖像生成部署設定

`render.yaml` 已固定正式環境的 Gunicorn timeout 與 health check。若目前的
Render 服務不是用 Blueprint 建立，請在 Dashboard 手動同步以下設定：

1. **Start Command**

   ```text
   gunicorn app:app --workers 1 --threads 4 --timeout 300 --keep-alive 75 --max-requests 30 --max-requests-jitter 10
   ```

2. **Health Check Path**：`/health`
3. **Environment Variables**
   - `GOOGLE_API_KEY`：啟用 Gemini 圖像與小綠對話
   - `OPENAI_API_KEY`：啟用 OpenAI GPT Image
   - `DIAG_TOKEN`：保護診斷端點，請使用隨機且不可猜測的值
   - `REDIS_URL`（選用）：保存共創 session，並讓限流與 session 鎖可跨 worker
   - `BLOB_READ_WRITE_TOKEN`（選用）：讓生成圖片在 Render 重啟後仍可存取
   - `GEMINI_IMAGE_MODEL=gemini-3-pro-image`
   - `GEMINI_TEXT_MODELS=gemini-flash-latest`
   - `OPENAI_IMAGE_MODEL=gpt-image-2`
   - `STATE_KEY_PREFIX=ai-street-designer`

API Key 只放在 Render Dashboard，不可提交進 Git。設定後執行一次
**Manual Deploy → Deploy latest commit**，再檢查：

- `/health` 應回傳 HTTP 200。
- 使用診斷 Token 呼叫 `/api/diag`：

  ```bash
  curl -H "X-Diag-Token: $DIAG_TOKEN" https://ai-street-designer.onrender.com/api/diag
  ```

  回傳的 `providers.gemini`／`providers.openai` 應符合已設定的 Key。若要執行
  會實際呼叫 Gemini 的模型連線測試，再加上 `?models=1`。

### OpenAI 圖像選項顯示「尚未設定 API Key」

正式網站的 `/api/diag` 若回傳 `"openai": false`，代表 Render worker 啟動時
沒有讀到 `OPENAI_API_KEY`。請在 Render Web Service 的 **Environment** 頁面
新增或更新 `OPENAI_API_KEY`（不要加引號或前後空白），儲存後重新部署。
部署完成後重新開啟首頁；首頁已禁止快取供應商狀態，OpenAI 選項應立即啟用。

`gpt-image-2` 可能要求 OpenAI API 組織完成驗證。若金鑰已設定但生成時回報
權限或組織驗證錯誤，請到 OpenAI developer console 檢查 Organization
Verification、專案模型權限與用量／額度。不要把 API Key 貼到 GitHub Issue、
瀏覽器前端程式或診斷截圖中。

## 第三階段：持久化與自動檢查

`REDIS_URL` 沒有設定時，程式會維持原本的記憶體模式，不影響本機開發。
正式環境若要讓共創 session 在 worker 重啟後繼續存在，請在 Render 或其他
相容服務建立 Redis，並將其連線字串設為私密環境變數 `REDIS_URL`。請勿把
連線字串寫入 `.env.example` 或提交到 Git。

Redis 保存的是有時效的 session JSON、縮小後的參考圖片、限流計數與短期鎖。
若也希望 `/static/generated/...` 圖片網址在重新部署後仍有效，還要設定
`BLOB_READ_WRITE_TOKEN`；只設定 Redis 並不會讓 Render 的暫存磁碟永久化。

部署後用受保護的診斷端點確認：

- `state_backend` 應為 `redis`；若是 `memory`，請檢查 `REDIS_URL` 與服務連線。
- `durable_images` 應為 `true`；若是 `false`，生成圖片仍使用本機暫存磁碟。
- `sessions` 會回報目前尚未逾時的 Redis session 數。

專案也包含 `.github/workflows/ci.yml`。每次推送到 `main` 或建立 Pull Request
時，GitHub 會自動執行測試、Python 關鍵錯誤檢查、Bandit、依賴漏洞掃描與
前端 JavaScript 語法檢查。這些檢查不需要任何正式環境 API Key。
