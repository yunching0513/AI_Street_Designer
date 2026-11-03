# 🔧 Vercel 部署錯誤排解指南

## 錯誤: FUNCTION_INVOCATION_FAILED

如果你看到這個錯誤,代表 Vercel 的 serverless function 無法正確執行。以下是解決方案:

### ✅ 已修復的問題

1. **api/index.py 路徑問題** - 已更新為正確設定 Python import 路徑
2. **Service Account 認證** - 已支援 `GOOGLE_APPLICATION_CREDENTIALS_JSON` 環境變數

### 🔑 正確設定環境變數

在 Vercel Dashboard → Settings → Environment Variables 中設定:

#### 選項 A: 使用 Gemini API (最簡單,推薦)

```
GOOGLE_API_KEY=你的_API_金鑰
```

#### 選項 B: 使用 Vertex AI (完整功能)

```
GOOGLE_CLOUD_PROJECT=你的專案ID
GOOGLE_CLOUD_LOCATION=us-central1
GOOGLE_APPLICATION_CREDENTIALS_JSON={"type":"service_account","project_id":"...完整的JSON內容..."}
```

**重要**: `GOOGLE_APPLICATION_CREDENTIALS_JSON` 必須是完整的 JSON 字串,不是檔案路徑!

### 📋 如何取得 JSON 內容

1. 打開你的 `service-account-key.json` 檔案
2. 複製**整個檔案內容** (包括所有大括號)
3. 貼到 Vercel 環境變數的值欄位中

範例格式:
```json
{"type":"service_account","project_id":"your-project","private_key_id":"...","private_key":"-----BEGIN PRIVATE KEY-----\\n...","client_email":"...","client_id":"...","auth_uri":"...","token_uri":"...","auth_provider_x509_cert_url":"...","client_x509_cert_url":"..."}
```

### 🔄 重新部署步驟

1. **推送最新程式碼**:
   ```bash
   git add .
   git commit -m "Fix Vercel serverless function handler"
   git push origin main
   ```

2. **在 Vercel 中重新部署**:
   - 前往 Vercel Dashboard
   - 找到你的專案
   - 點擊 "Deployments" 標籤
   - 點擊最新部署旁的 "..." → "Redeploy"

3. **檢查日誌**:
   - 部署完成後,點擊該部署
   - 前往 "Functions" 標籤
   - 查看是否有錯誤訊息

### 🐛 常見錯誤訊息

#### "No module named 'app'"
- **原因**: `api/index.py` 無法找到 `app.py`
- **解決**: 已在最新版本修復,請重新部署

#### "No valid credentials found"
- **原因**: 環境變數未正確設定
- **解決**: 檢查 Vercel 環境變數是否正確設定

#### "Failed to initialize Vertex AI Client"
- **原因**: Service Account JSON 格式錯誤或權限不足
- **解決**: 
  1. 確認 JSON 格式正確 (使用 JSON validator)
  2. 確認 Service Account 有 "Vertex AI User" 權限

### 📊 查看即時日誌

```bash
# 安裝 Vercel CLI
npm i -g vercel

# 查看即時日誌
vercel logs [your-deployment-url]
```

### 💡 測試建議

部署後測試:
1. 訪問首頁 - 應該能正常載入
2. 上傳一張圖片 - 檢查是否有錯誤
3. 查看 Vercel Functions 日誌 - 確認 API client 初始化成功

### 🆘 還是不行?

如果問題持續,請提供:
1. Vercel 部署日誌截圖
2. Functions 錯誤訊息
3. 你使用的是 Gemini API 還是 Vertex AI
