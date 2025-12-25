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
