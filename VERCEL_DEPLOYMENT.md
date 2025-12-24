# Vercel 部署指南

本指南將協助你將 AI Street Designer 部署到 Vercel。

## 前置準備

1. **Vercel 帳號**: 前往 [vercel.com](https://vercel.com) 註冊免費帳號
2. **GitHub 連接**: 確保你的專案已推送到 GitHub

## 部署步驟

### 1. 推送程式碼到 GitHub

```bash
cd "/Users/yunching0513/AI Street Designer"
git add .
git commit -m "Add Vercel configuration"
git push origin main
```

### 2. 連接 Vercel

1. 登入 [Vercel Dashboard](https://vercel.com/dashboard)
2. 點擊 **"Add New Project"**
3. 選擇 **"Import Git Repository"**
4. 找到你的 `AI Street Designer` repository 並點擊 **"Import"**

### 3. 配置專案設定

在 Import 頁面:

- **Framework Preset**: 選擇 `Other`
- **Root Directory**: 保持為 `./` (預設)
- **Build Command**: 留空
- **Output Directory**: 留空

點擊 **"Deploy"** 繼續。

### 4. 設定環境變數

部署後,前往專案的 **Settings** → **Environment Variables**,添加以下變數:

#### 必要變數 (擇一設定)

**選項 A: 使用 Vertex AI (推薦,支援完整功能)**
```
GOOGLE_CLOUD_PROJECT=你的專案ID
GOOGLE_CLOUD_LOCATION=us-central1
GOOGLE_APPLICATION_CREDENTIALS=service-account-key.json
```

**選項 B: 使用 Gemini API (較簡單,但功能受限)**
```
GOOGLE_API_KEY=你的API金鑰
```

#### 設定 Service Account (僅 Vertex AI 需要)

如果使用 Vertex AI,你需要將 service account key 的內容設為環境變數:

1. 打開你的 `service-account-key.json` 檔案
2. 複製整個 JSON 內容
3. 在 Vercel 環境變數中:
   - **Name**: `GOOGLE_APPLICATION_CREDENTIALS_JSON`
   - **Value**: 貼上完整的 JSON 內容
4. 在專案中添加一個啟動腳本來處理這個 JSON (或直接在 `app.py` 中處理)

**替代方案**: 使用 Vercel Secrets
```bash
# 安裝 Vercel CLI
npm i -g vercel

# 登入
vercel login

# 設定環境變數
vercel env add GOOGLE_CLOUD_PROJECT
vercel env add GOOGLE_CLOUD_LOCATION
vercel env add GOOGLE_API_KEY
```

### 5. 重新部署

設定環境變數後:
1. 前往 **Deployments** 頁面
2. 點擊最新部署旁的 **"..."** 選單
3. 選擇 **"Redeploy"**

## 驗證部署

部署完成後,Vercel 會提供一個 URL (例如 `https://your-project.vercel.app`)。

測試以下功能:
- ✅ 首頁載入
- ✅ 上傳圖片
- ✅ 生成轉換後的圖片

## 常見問題

### Q: 為什麼圖片上傳後消失了?
A: Vercel 的 serverless 環境使用 `/tmp` 目錄,每次請求後會清空。這是正常行為。圖片會在生成後立即返回給前端。

### Q: 冷啟動時間還是很長怎麼辦?
A: 
- Vercel 免費版的冷啟動通常比 Render 快
- 考慮升級到 Pro 方案以獲得更好的效能
- 或使用 Vercel 的 Edge Functions (需要調整程式碼)

### Q: 如何查看錯誤日誌?
A: 前往 Vercel Dashboard → 你的專案 → **Deployments** → 點擊特定部署 → **Functions** 標籤

### Q: Service Account 認證失敗?
A: 確認:
1. JSON 格式正確 (沒有多餘的空格或換行)
2. Service Account 有正確的權限
3. 專案 ID 和 Location 設定正確

## 自訂網域

如果你想使用自訂網域:
1. 前往 **Settings** → **Domains**
2. 添加你的網域
3. 依照指示設定 DNS 記錄

## 效能優化建議

1. **使用 Gemini API**: 如果不需要 `edit_image` 功能,使用 API Key 會更簡單
2. **減少 Knowledge Base 大小**: 較小的檔案會加快冷啟動速度
3. **啟用 Edge Caching**: 為靜態資源設定快取標頭

## 需要協助?

- [Vercel 文件](https://vercel.com/docs)
- [Vercel 社群](https://github.com/vercel/vercel/discussions)
