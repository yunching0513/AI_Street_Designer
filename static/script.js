const UI_TEXT = {
    'zh-TW': {
        appTitle: 'AI Street Designer｜一起改造你的街道',
        subtitle: '和小綠一起，把你家門口的街道變得更可愛 💕',
        uploadTitle: '把街景照片丟過來',
        uploadHint: '拖曳上傳，或點一下選圖 ✨',
        maskCanvas: '在照片上畫出希望 AI 改造的範圍',
        styleLabel: '選一個改造風格',
        widenSidewalks: '加寬人行道',
        transitPriority: '公車彎月台',
        bikeLane: '自行車道',
        greenStreet: '綠意盎然',
        reduceTraffic: '減少汽機車',
        providerLabel: '選擇圖像生成器 ✦',
        providerAria: '圖像生成器',
        unavailable: '尚未設定 API Key',
        customWish: '或是自己許個願 💭',
        promptPlaceholder: '例如：步行區、有咖啡店和露天座位...',
        inspectPlan: '檢視設計計畫',
        refreshPlan: '重新整理設計計畫',
        buildingPlan: '正在整理設計依據…',
        coDefine: '和小綠一起定義這條街 🤝',
        streetContext: '街道情境',
        contextAuto: '讓 AI 初步判讀',
        contextMain: '主要街道',
        contextResidential: '住宅生活街道',
        contextSchool: '通學環境',
        contextTransit: '大眾運輸廊道',
        contextUrban: '市中心街道',
        contextNeighbourhood: '鄰里街道',
        targetSpeed: '希望傳達的目標速度',
        unspecified: '不指定',
        intensity: '改造幅度',
        light: '輕量改善',
        balanced: '平衡改造',
        transformative: '大幅重分配',
        priorities: '優先照顧誰／什麼',
        walking: '🚶 步行',
        cycling: '🚲 自行車',
        transit: '🚌 大眾運輸',
        greenery: '🌳 綠化遮蔭',
        accessibility: '♿ 無障礙',
        safety: '🛡️ 道路安全',
        localActivity: '☕ 店家活動',
        preserve: '需要保留',
        existingTrees: '既有好樹',
        parking: '部分停車',
        loadingAccess: '裝卸短停',
        transitOps: '公車營運',
        fixedPreserve: '建築、店面出入口、原始視角及救災通行會固定保留。',
        useMask: '我想在照片上畫出可改造範圍',
        maskHelp: '用手指或滑鼠塗綠希望改造的位置',
        clearMask: '清除重畫',
        maskNote: 'OpenAI 會直接使用透明遮罩；Gemini 會把它當作範圍提示。',
        quality: '畫質 🖼️',
        resolution1K: '標準 1K（最快）',
        resolution2K: '高畫質 2K（建議）',
        resolution4K: '超高 4K（較慢、成本較高）',
        qualityNote: '之後跟小綠共創的調整版本也會用這個畫質',
        planKicker: 'AI × 使用者共同確認',
        planTitle: '這次的設計計畫',
        promptDetails: '查看將送給圖片模型的完整 Prompt',
        confirmGenerate: '確認計畫，開始生成',
        resultTitle: '✨ 你的新街道',
        round: '共創回合 {version}',
        close: '關閉',
        loading: '小綠正在動筆中...',
        resultAlt: '改造後的街道設計',
        beforeAlt: '改造前的原始街道',
        beforeLabel: 'Before · 改造前',
        afterLabel: 'After · 改造後',
        compareAria: '拖曳比較改造前後',
        compareValue: '改造前 {before}%，改造後 {after}%',
        videoTitle: '滿意這一版？製作街道漫遊影片',
        videoSummary: '以第一人稱沿著新街道向前走',
        copilotName: '小綠',
        copilotSubtitle: '你的街道設計小夥伴',
        reviewHeading: '設計依據與畫面檢查',
        pendingAudit: '待檢查',
        auditIntro: '生成後會在這裡檢查設計是否清楚、連續且可信。',
        reviewDetails: '查看依據與檢查項目',
        copilotPlaceholder: '跟小綠聊聊：再多一些樹、人行道更寬...',
        send: '送出',
        videoKicker: '走進你的設計',
        videoSetupTitle: '走進你設計的街道',
        videoSetupDescription: '鏡頭會像行人的視線，沿著人行道自然向前移動。',
        walkingPace: '步行節奏',
        gentle: '慢慢散步',
        gentleSub: '悠閒看街景',
        natural: '自然步行',
        naturalSub: '最適合預覽',
        brisk: '輕快前進',
        briskSub: '更有動態感',
        duration: '影片長度',
        seconds: '{value} 秒',
        format: '畫面比例',
        landscape: '▰ 橫式',
        portrait: '▯ 直式',
        firstPerson: '第一人稱漫遊',
        safetyNote: '畫面不會出現使用者本人，降低人臉造成的生成失敗。',
        later: '稍後再說',
        confirmVideo: '開始生成影片',
        videoStarting: '正在建立街道漫遊',
        videoStartingMessage: '正在把 v{version} 送給 Google Veo…',
        videoQueued: '街道漫遊已排入生成',
        videoQueuedMessage: 'Google Veo 正在處理，通常需要幾分鐘；可以留在這個畫面等候。',
        videoGenerating: '正在走進你的新街道',
        videoGeneratingMessage: 'Veo 正在維持建築與道路配置，同時生成向前步行的鏡頭。',
        videoComplete: '街道漫遊完成',
        videoCompleteMessage: '可以播放、下載，或重新設定另一個步行節奏。',
        videoFailed: '影片生成沒有完成',
        videoFailedMessage: '請稍後重試；若持續失敗，請確認 Google API 的付費額度與 Veo 權限。',
        retryVideo: '重新設定',
        downloadVideo: '下載影片',
        videoProgressAria: '影片生成進度',
        evidenceCount: '{count} 項依據',
        targetSpeedSummary: '目標速度：{value}',
        prioritySummary: '優先：{value}',
        designRule: '設計規則',
        methodReference: '方法參考',
        originalWording: '查看來源原文',
        originalLanguageNote: '以下保留來源語言，正式應用請核對原始文件。',
        manualReview: '待人工確認',
        planError: '設計計畫建立失敗：{message}',
        generationError: '生成失敗：{message}',
        uploadImageError: '請上傳圖片檔。',
        noMask: '請先在照片上塗出希望 AI 改造的範圍。',
        providerDrawing: '{provider} 正在依確認計畫描繪新街道...',
        fallbackGreeting: '嗨，我是小綠 🌱 跟我說你想怎麼調整這條街吧！',
        chatError: '糟糕，我這邊有點卡 🌱 {message}',
        fromVersion: '從 v{version} 建立第一人稱漫遊',
        videoReady: 'v{version} 漫遊影片設定完成',
        evidenceSourceOriginal: '原文',
        removeImage: '移除照片',
        closeVideo: '關閉影片設定',
        imageConversionFailed: '無法轉換這張圖片，請改用 JPEG、PNG 或 WebP。',
        maskCreateError: '無法建立改造範圍遮罩。',
        maskExportError: '無法輸出改造範圍遮罩。',
        planUnavailable: '無法建立設計計畫。',
        unknownServerError: '伺服器回傳未知錯誤。',
        chatFailed: '對話暫時失敗，請再試一次。',
        retryChat: '可以再試一次嗎？',
        auditFallback: '尚未完成模型視覺稽核，請共同確認。',
        generationInterrupted: '生成程序在完成前中斷（HTTP {status}）{diagnostic}。可能是服務重新啟動、記憶體不足或上游服務逾時；請等 30 秒再試一次，並先改用 1K 或 2K。',
        invalidServerResponse: '伺服器回傳了無法辨識的內容（HTTP {status}）{diagnostic}。',
        requestDiagnostic: '（診斷碼 {id}）',
        fallbackSuggestionTrees: '再多一些樹',
        fallbackSuggestionBench: '加長椅',
        fallbackSuggestionMovement: '檢查動線',
    },
    en: {
        appTitle: 'AI Street Designer | Co-design a Better Street',
        subtitle: 'Co-design a safer, greener street with Greenie 🌱',
        uploadTitle: 'Drop in a street photo',
        uploadHint: 'Drag and drop, or click to choose an image ✨',
        maskCanvas: 'Paint the area that AI may transform',
        styleLabel: 'Choose a transformation',
        widenSidewalks: 'Widen sidewalks',
        transitPriority: 'Transit priority',
        bikeLane: 'Protected bike lane',
        greenStreet: 'Greener street',
        reduceTraffic: 'Reduce motor traffic',
        providerLabel: 'Choose an image model ✦',
        providerAria: 'Image model',
        unavailable: 'API key not configured',
        customWish: 'Or describe your own idea 💭',
        promptPlaceholder: 'For example: a walkable street with café seating...',
        inspectPlan: 'Review design plan',
        refreshPlan: 'Refresh design plan',
        buildingPlan: 'Retrieving design guidance…',
        coDefine: 'Define the street together 🤝',
        streetContext: 'Street context',
        contextAuto: 'Let AI make an initial reading',
        contextMain: 'Main street',
        contextResidential: 'Residential living street',
        contextSchool: 'School-zone street',
        contextTransit: 'Transit corridor',
        contextUrban: 'Urban core street',
        contextNeighbourhood: 'Neighbourhood street',
        targetSpeed: 'Target-speed design intent',
        unspecified: 'Not specified',
        intensity: 'Transformation intensity',
        light: 'Light touch',
        balanced: 'Balanced',
        transformative: 'Major reallocation',
        priorities: 'Prioritise',
        walking: '🚶 Walking',
        cycling: '🚲 Cycling',
        transit: '🚌 Public transport',
        greenery: '🌳 Shade and greenery',
        accessibility: '♿ Accessibility',
        safety: '🛡️ Road safety',
        localActivity: '☕ Shops and activity',
        preserve: 'Preserve',
        existingTrees: 'Healthy trees',
        parking: 'Some parking',
        loadingAccess: 'Loading access',
        transitOps: 'Bus operations',
        fixedPreserve: 'Buildings, storefront access, viewpoint, and emergency access are always preserved.',
        useMask: 'Paint the area that may be transformed',
        maskHelp: 'Use a mouse or finger to paint the editable area in green',
        clearMask: 'Clear mask',
        maskNote: 'OpenAI uses the alpha mask directly; Gemini treats it as an edit-area guide.',
        quality: 'Image quality 🖼️',
        resolution1K: 'Standard 1K (fastest)',
        resolution2K: 'High quality 2K (recommended)',
        resolution4K: 'Ultra 4K (slower and more costly)',
        qualityNote: 'Later co-design refinements will use the same quality setting',
        planKicker: 'AI × USER CONFIRMATION',
        planTitle: 'Design plan',
        promptDetails: 'View the exact image-model prompt',
        confirmGenerate: 'Confirm plan and generate',
        resultTitle: '✨ Your redesigned street',
        round: 'Co-design round {version}',
        close: 'Close',
        loading: 'Greenie is sketching...',
        resultAlt: 'Redesigned street',
        beforeAlt: 'Original street',
        beforeLabel: 'Before',
        afterLabel: 'After',
        compareAria: 'Drag to compare before and after',
        compareValue: 'Before {before}%, after {after}%',
        videoTitle: 'Happy with this version? Create a street walk-through',
        videoSummary: 'Move forward along the redesigned street in first person',
        copilotName: 'Greenie',
        copilotSubtitle: 'Your street-design co-pilot',
        reviewHeading: 'Design evidence and visual review',
        pendingAudit: 'Pending',
        auditIntro: 'After generation, this panel checks whether the concept is clear, continuous, and credible.',
        reviewDetails: 'View evidence and review checks',
        copilotPlaceholder: 'Ask Greenie: add more trees, widen the sidewalk...',
        send: 'Send',
        videoKicker: 'WALK THROUGH YOUR DESIGN',
        videoSetupTitle: 'Walk through your redesigned street',
        videoSetupDescription: 'The camera moves naturally forward from a pedestrian viewpoint.',
        walkingPace: 'Walking pace',
        gentle: 'Gentle stroll',
        gentleSub: 'Take in the details',
        natural: 'Natural walk',
        naturalSub: 'Best for previewing',
        brisk: 'Brisk walk',
        briskSub: 'More dynamic',
        duration: 'Duration',
        seconds: '{value} sec',
        format: 'Format',
        landscape: '▰ Landscape',
        portrait: '▯ Portrait',
        firstPerson: 'First-person walk-through',
        safetyNote: 'The user does not appear on screen, reducing face-related generation failures.',
        later: 'Maybe later',
        confirmVideo: 'Generate video',
        videoStarting: 'Starting your street walk-through',
        videoStartingMessage: 'Sending v{version} to Google Veo…',
        videoQueued: 'Street walk-through queued',
        videoQueuedMessage: 'Google Veo is working. This usually takes a few minutes; you can keep this screen open.',
        videoGenerating: 'Walking into your redesigned street',
        videoGeneratingMessage: 'Veo is preserving the street layout while creating a forward pedestrian camera move.',
        videoComplete: 'Street walk-through complete',
        videoCompleteMessage: 'Play or download it, or create another pace.',
        videoFailed: 'Video generation did not finish',
        videoFailedMessage: 'Try again shortly. If it keeps failing, check Google API billing and Veo access.',
        retryVideo: 'Change settings',
        downloadVideo: 'Download video',
        videoProgressAria: 'Video generation progress',
        evidenceCount: '{count} sources',
        targetSpeedSummary: 'Target speed: {value}',
        prioritySummary: 'Priorities: {value}',
        designRule: 'Design rule',
        methodReference: 'Method',
        originalWording: 'View original source wording',
        originalLanguageNote: 'The original-language wording is preserved below. Verify the source document before project use.',
        manualReview: 'Needs review',
        planError: 'Could not create the design plan: {message}',
        generationError: 'Generation failed: {message}',
        uploadImageError: 'Please upload an image file.',
        noMask: 'Paint the area that AI may transform first.',
        providerDrawing: '{provider} is drawing the confirmed street design...',
        fallbackGreeting: 'Hi, I’m Greenie 🌱 Tell me what you would like to adjust next.',
        chatError: 'I got a little stuck 🌱 {message}',
        fromVersion: 'Create a first-person walk-through from v{version}',
        videoReady: 'Walk-through settings ready for v{version}',
        evidenceSourceOriginal: 'Original',
        removeImage: 'Remove photo',
        closeVideo: 'Close video settings',
        imageConversionFailed: 'This image could not be converted. Please use JPEG, PNG, or WebP.',
        maskCreateError: 'The editable-area mask could not be created.',
        maskExportError: 'The editable-area mask could not be exported.',
        planUnavailable: 'The design plan could not be created.',
        unknownServerError: 'The server returned an unknown error.',
        chatFailed: 'Chat is temporarily unavailable. Please try again.',
        retryChat: 'Would you try that again?',
        auditFallback: 'The model-based visual review is not complete. Please review it together.',
        generationInterrupted: 'Generation stopped before completion (HTTP {status}){diagnostic}. The service may have restarted, run out of memory, or timed out; wait 30 seconds, then retry at 1K or 2K.',
        invalidServerResponse: 'The server returned an unreadable response (HTTP {status}){diagnostic}.',
        requestDiagnostic: ' (request ID {id})',
        fallbackSuggestionTrees: 'Add more trees',
        fallbackSuggestionBench: 'Add benches',
        fallbackSuggestionMovement: 'Review movement paths',
    },
};

function normalizeUiLanguage(value) {
    return String(value || '').toLowerCase().startsWith('en') ? 'en' : 'zh-TW';
}

const storedUiLanguage = localStorage.getItem('street-designer-language');
let currentLanguage = normalizeUiLanguage(
    storedUiLanguage
    || ((navigator.language || '').startsWith('en') ? 'en' : 'zh-TW')
);

function tr(key, replacements = {}) {
    const dictionary = UI_TEXT[currentLanguage] || UI_TEXT['zh-TW'];
    let value = dictionary[key] || UI_TEXT['zh-TW'][key] || key;
    Object.entries(replacements).forEach(([name, replacement]) => {
        value = value.replaceAll(`{${name}}`, String(replacement));
    });
    return value;
}

function languageHeaders(headers = {}) {
    return { ...headers, 'X-UI-Language': currentLanguage };
}

// Resize and re-encode large images to keep Render requests and model inputs small.
async function compressImage(file, maxDimension = 1920, quality = 0.85) {
    const supportedTypes = ['image/jpeg', 'image/png', 'image/webp'];
    if (supportedTypes.includes(file.type) && file.size < 3 * 1024 * 1024) {
        return file;
    }

    const img = await new Promise((resolve, reject) => {
        const reader = new FileReader();
        reader.onload = (e) => {
            const image = new Image();
            image.onload = () => resolve(image);
            image.onerror = reject;
            image.src = e.target.result;
        };
        reader.onerror = reject;
        reader.readAsDataURL(file);
    });

    let { width, height } = img;
    if (Math.max(width, height) > maxDimension) {
        const scale = maxDimension / Math.max(width, height);
        width = Math.round(width * scale);
        height = Math.round(height * scale);
    }

    const canvas = document.createElement('canvas');
    canvas.width = width;
    canvas.height = height;
    canvas.getContext('2d').drawImage(img, 0, 0, width, height);

    return await new Promise((resolve, reject) => {
        canvas.toBlob((blob) => {
            if (!blob) {
                reject(new Error(tr('imageConversionFailed')));
                return;
            }
            const baseName = file.name.replace(/\.[^.]+$/, '');
            resolve(new File([blob], `${baseName}.jpg`, { type: 'image/jpeg' }));
        }, 'image/jpeg', quality);
    });
}

async function readApiJson(response) {
    const rawText = await response.text();
    try {
        return JSON.parse(rawText);
    } catch (parseError) {
        const requestId = response.headers.get('X-Request-ID');
        const diagnostic = requestId
            ? tr('requestDiagnostic', { id: requestId })
            : '';
        if (response.status >= 500) {
            throw new Error(
                tr('generationInterrupted', {
                    status: response.status,
                    diagnostic,
                })
            );
        }
        throw new Error(tr('invalidServerResponse', {
            status: response.status,
            diagnostic,
        }));
    }
}

document.addEventListener('DOMContentLoaded', () => {
    // Upload + controls
    const dropZone = document.getElementById('drop-zone');
    const fileInput = document.getElementById('file-input');
    const uploadContent = document.getElementById('upload-content');
    const previewContainer = document.getElementById('preview-container');
    const imagePreview = document.getElementById('image-preview');
    const removeBtn = document.getElementById('remove-image');
    const optionCards = document.querySelectorAll('.option-card');
    const customPromptInput = document.getElementById('custom-prompt');
    const generateBtn = document.getElementById('generate-btn');
    const languageButtons = document.querySelectorAll(
        '.language-switch button[data-language]'
    );
    const providerInputs = document.querySelectorAll('input[name="image-provider"]');
    const streetContext = document.getElementById('street-context');
    const targetSpeed = document.getElementById('target-speed');
    const intensityInputs = document.querySelectorAll(
        'input[name="intervention-intensity"]'
    );
    const priorityInputs = document.querySelectorAll(
        '#priority-options input[type="checkbox"]'
    );
    const preserveInputs = document.querySelectorAll(
        '#preserve-options input[type="checkbox"]'
    );
    const useEditMask = document.getElementById('use-edit-mask');
    const editMaskCanvas = document.getElementById('edit-mask-canvas');
    const maskTools = document.getElementById('mask-tools');
    const clearMaskBtn = document.getElementById('clear-mask');
    const designPlanPanel = document.getElementById('design-plan-panel');
    const designPlanTitle = document.getElementById('design-plan-title');
    const evidenceCount = document.getElementById('evidence-count');
    const planSummary = document.getElementById('plan-summary');
    const evidenceList = document.getElementById('evidence-list');
    const assumptionList = document.getElementById('assumption-list');
    const promptPreview = document.getElementById('generation-prompt-preview');
    const confirmGenerateBtn = document.getElementById('confirm-generate-btn');

    // Result + co-pilot
    const resultSection = document.getElementById('result-section');
    const comparisonViewer = document.getElementById('comparison-viewer');
    const comparisonRange = document.getElementById('comparison-range');
    const beforeImage = document.getElementById('before-image');
    const resultImage = document.getElementById('result-image');
    const beforeLabel = comparisonViewer.querySelector('.comparison-label-before');
    const afterLabel = comparisonViewer.querySelector('.comparison-label-after');
    const closeResultBtn = document.getElementById('close-result');
    const loadingOverlay = document.getElementById('loading-overlay');
    const loadingText = document.getElementById('loading-text');
    const roundBadge = document.getElementById('round-badge');
    const versionStrip = document.getElementById('version-strip');
    const copilotMessages = document.getElementById('copilot-messages');
    const copilotSuggestions = document.getElementById('copilot-suggestions');
    const copilotInputForm = document.getElementById('copilot-input-form');
    const copilotInput = document.getElementById('copilot-input');
    const copilotSend = document.getElementById('copilot-send');
    const videoLauncher = document.getElementById('video-launcher');
    const videoLauncherTitle = document.getElementById('video-launcher-title');
    const videoLauncherSummary = document.getElementById('video-launcher-summary');
    const videoModal = document.getElementById('video-modal');
    const videoSetupForm = document.getElementById('video-setup-form');
    const videoModalClose = document.getElementById('video-modal-close');
    const videoCancel = document.getElementById('video-cancel');
    const videoStatusCard = document.getElementById('video-status-card');
    const videoStatusIcon = document.getElementById('video-status-icon');
    const videoStatusTitle = document.getElementById('video-status-title');
    const videoStatusMessage = document.getElementById('video-status-message');
    const videoProgress = document.getElementById('video-progress');
    const videoPlayer = document.getElementById('video-player');
    const videoStatusActions = document.getElementById('video-status-actions');
    const videoDownload = document.getElementById('video-download');
    const videoRetry = document.getElementById('video-retry');
    const auditScore = document.getElementById('audit-score');
    const auditSummary = document.getElementById('audit-summary');
    const resultAuditChecks = document.getElementById('result-audit-checks');
    const resultEvidence = document.getElementById('result-evidence');
    const auditDisclaimer = document.getElementById('audit-disclaimer');

    // State
    let selectedFile = null;
    let selectedPrompt = '';
    let selectedPresetId = '';
    let sessionId = null;
    let versions = []; // [{ version, image_url }]
    let currentVersion = 0;
    let chatBusy = false;
    let generationBusy = false;
    let originalImageUrl = null;
    let activeDesignPlan = null;
    let currentDesignSpec = null;
    let currentAudit = null;
    let maskStrokes = [];
    let activeMaskStroke = null;
    const videoDrafts = new Map();
    let videoReturnFocus = null;
    let activeVideoJob = null;
    let videoPollTimer = null;
    let videoBusy = false;
    let videoPollFailures = 0;

    function applyLanguage() {
        document.documentElement.lang = currentLanguage === 'en'
            ? 'en'
            : 'zh-Hant';
        document.title = tr('appTitle');

        document.querySelectorAll('[data-i18n]').forEach(element => {
            const replacements = element.dataset.i18nValue
                ? { value: element.dataset.i18nValue }
                : {};
            element.textContent = tr(element.dataset.i18n, replacements);
        });
        [
            ['data-i18n-placeholder', 'placeholder'],
            ['data-i18n-aria-label', 'aria-label'],
            ['data-i18n-alt', 'alt'],
        ].forEach(([dataAttribute, targetAttribute]) => {
            document.querySelectorAll(`[${dataAttribute}]`).forEach(element => {
                element.setAttribute(
                    targetAttribute,
                    tr(element.getAttribute(dataAttribute))
                );
            });
        });

        languageButtons.forEach(button => {
            button.setAttribute(
                'aria-pressed',
                String(button.dataset.language === currentLanguage)
            );
        });
        document.querySelectorAll('.provider-option').forEach(option => {
            const model = option.dataset.model || '';
            const unavailable = option.dataset.available === 'false'
                ? ` · ${tr('unavailable')}`
                : '';
            const detail = option.querySelector('small');
            if (detail) detail.textContent = `${model}${unavailable}`;
        });

        generateBtn.innerHTML = activeDesignPlan
            ? `${tr('refreshPlan')} <span>↻</span>`
            : `${tr('inspectPlan')} <span>🔎</span>`;
        if (versions[currentVersion]) {
            roundBadge.textContent = tr('round', {
                version: versions[currentVersion].version,
            });
        }
        setComparisonPosition(comparisonRange.value);
        updateVideoLauncher();
        if (activeVideoJob) renderVideoStatus(activeVideoJob);
        if (activeDesignPlan) renderDesignPlan(activeDesignPlan, false);
        if (currentDesignSpec || currentAudit) {
            renderResultReview(currentDesignSpec, currentAudit);
        }
    }

    languageButtons.forEach(button => {
        button.addEventListener('click', () => {
            const nextLanguage = normalizeUiLanguage(button.dataset.language);
            if (nextLanguage === currentLanguage) return;
            currentLanguage = nextLanguage;
            localStorage.setItem('street-designer-language', currentLanguage);
            invalidateDesignPlan();
            applyLanguage();
        });
    });

    function setComparisonPosition(value) {
        const position = Math.min(100, Math.max(0, Number(value)));
        comparisonViewer.style.setProperty('--comparison-position', `${position}%`);
        comparisonRange.value = String(position);
        comparisonRange.setAttribute(
            'aria-valuetext',
            tr('compareValue', {
                before: position,
                after: 100 - position,
            })
        );
        beforeLabel.style.opacity = position < 12 ? '0' : '1';
        afterLabel.style.opacity = position > 88 ? '0' : '1';
    }

    function setBeforeImage(file) {
        if (originalImageUrl) URL.revokeObjectURL(originalImageUrl);
        originalImageUrl = URL.createObjectURL(file);
        beforeImage.src = originalImageUrl;
        setComparisonPosition(50);
    }

    comparisonRange.addEventListener('input', (event) => {
        setComparisonPosition(event.target.value);
    });
    setComparisonPosition(50);

    function maskContentRect() {
        const width = editMaskCanvas.width;
        const height = editMaskCanvas.height;
        const naturalWidth = imagePreview.naturalWidth || width || 1;
        const naturalHeight = imagePreview.naturalHeight || height || 1;
        const scale = Math.min(width / naturalWidth, height / naturalHeight);
        const contentWidth = naturalWidth * scale;
        const contentHeight = naturalHeight * scale;
        return {
            x: (width - contentWidth) / 2,
            y: (height - contentHeight) / 2,
            width: contentWidth,
            height: contentHeight,
        };
    }

    function resizeMaskCanvas() {
        const rect = previewContainer.getBoundingClientRect();
        editMaskCanvas.width = Math.max(1, Math.round(rect.width));
        editMaskCanvas.height = Math.max(1, Math.round(rect.height));
        renderMaskOverlay();
    }

    function renderStroke(context, stroke, width, height) {
        if (!stroke.length) return;
        context.lineWidth = Math.max(12, Math.min(width, height) * 0.09);
        context.lineCap = 'round';
        context.lineJoin = 'round';
        context.beginPath();
        const first = stroke[0];
        context.moveTo(first.x * width, first.y * height);
        stroke.slice(1).forEach(point => {
            context.lineTo(point.x * width, point.y * height);
        });
        if (stroke.length === 1) {
            context.lineTo(
                first.x * width + 0.001,
                first.y * height + 0.001
            );
        }
        context.stroke();
    }

    function renderMaskOverlay() {
        const context = editMaskCanvas.getContext('2d');
        context.clearRect(0, 0, editMaskCanvas.width, editMaskCanvas.height);
        if (!useEditMask.checked) return;
        const content = maskContentRect();
        context.save();
        context.translate(content.x, content.y);
        context.strokeStyle = 'rgba(68, 181, 106, 0.58)';
        maskStrokes.forEach(stroke => {
            renderStroke(context, stroke, content.width, content.height);
        });
        context.restore();
    }

    function normalizedMaskPoint(event) {
        const canvasRect = editMaskCanvas.getBoundingClientRect();
        const scaleX = editMaskCanvas.width / canvasRect.width;
        const scaleY = editMaskCanvas.height / canvasRect.height;
        const x = (event.clientX - canvasRect.left) * scaleX;
        const y = (event.clientY - canvasRect.top) * scaleY;
        const content = maskContentRect();
        if (
            x < content.x
            || x > content.x + content.width
            || y < content.y
            || y > content.y + content.height
        ) {
            return null;
        }
        return {
            x: (x - content.x) / content.width,
            y: (y - content.y) / content.height,
        };
    }

    editMaskCanvas.addEventListener('pointerdown', event => {
        if (!useEditMask.checked) return;
        const point = normalizedMaskPoint(event);
        if (!point) return;
        event.preventDefault();
        editMaskCanvas.setPointerCapture(event.pointerId);
        activeMaskStroke = [point];
        maskStrokes.push(activeMaskStroke);
        renderMaskOverlay();
        invalidateDesignPlan();
    });

    editMaskCanvas.addEventListener('pointermove', event => {
        if (!activeMaskStroke) return;
        const point = normalizedMaskPoint(event);
        if (!point) return;
        const previous = activeMaskStroke[activeMaskStroke.length - 1];
        if (
            Math.abs(point.x - previous.x) + Math.abs(point.y - previous.y)
            < 0.004
        ) {
            return;
        }
        activeMaskStroke.push(point);
        renderMaskOverlay();
    });

    function finishMaskStroke() {
        activeMaskStroke = null;
    }
    editMaskCanvas.addEventListener('pointerup', finishMaskStroke);
    editMaskCanvas.addEventListener('pointercancel', finishMaskStroke);

    useEditMask.addEventListener('change', () => {
        editMaskCanvas.classList.toggle('hidden', !useEditMask.checked);
        maskTools.classList.toggle('hidden', !useEditMask.checked);
        resizeMaskCanvas();
        invalidateDesignPlan();
    });

    clearMaskBtn.addEventListener('click', event => {
        event.stopPropagation();
        maskStrokes = [];
        renderMaskOverlay();
        invalidateDesignPlan();
    });

    function imageDimensions(file) {
        return new Promise((resolve, reject) => {
            const url = URL.createObjectURL(file);
            const image = new Image();
            image.onload = () => {
                URL.revokeObjectURL(url);
                resolve({ width: image.naturalWidth, height: image.naturalHeight });
            };
            image.onerror = () => {
                URL.revokeObjectURL(url);
                reject(new Error(tr('maskCreateError')));
            };
            image.src = url;
        });
    }

    async function buildMaskBlob(uploadFile) {
        if (!useEditMask.checked) return null;
        if (!maskStrokes.length) {
            throw new Error(tr('noMask'));
        }
        const dimensions = await imageDimensions(uploadFile);
        const canvas = document.createElement('canvas');
        canvas.width = dimensions.width;
        canvas.height = dimensions.height;
        const context = canvas.getContext('2d');
        context.fillStyle = '#ffffff';
        context.fillRect(0, 0, canvas.width, canvas.height);
        context.globalCompositeOperation = 'destination-out';
        context.strokeStyle = '#000000';
        maskStrokes.forEach(stroke => {
            renderStroke(context, stroke, canvas.width, canvas.height);
        });
        return new Promise((resolve, reject) => {
            canvas.toBlob(blob => {
                if (blob) resolve(blob);
                else reject(new Error(tr('maskExportError')));
            }, 'image/png');
        });
    }

    imagePreview.addEventListener('load', resizeMaskCanvas);
    window.addEventListener('resize', resizeMaskCanvas);

    // ===== Upload handling =====
    dropZone.addEventListener('dragover', (e) => {
        e.preventDefault();
        dropZone.classList.add('dragover');
    });
    dropZone.addEventListener('dragleave', () => dropZone.classList.remove('dragover'));
    dropZone.addEventListener('drop', (e) => {
        e.preventDefault();
        dropZone.classList.remove('dragover');
        if (e.dataTransfer.files.length) handleFile(e.dataTransfer.files[0]);
    });
    dropZone.addEventListener('click', () => {
        if (!selectedFile) fileInput.click();
    });
    fileInput.addEventListener('change', (e) => {
        if (e.target.files.length) handleFile(e.target.files[0]);
    });
    removeBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        resetFile();
    });

    function handleFile(file) {
        if (!file.type.startsWith('image/')) {
            alert(tr('uploadImageError'));
            return;
        }
        selectedFile = file;
        maskStrokes = [];
        invalidateDesignPlan();
        setBeforeImage(file);
        const reader = new FileReader();
        reader.onload = (e) => {
            imagePreview.src = e.target.result;
            uploadContent.classList.add('hidden');
            previewContainer.classList.remove('hidden');
            updateGenerateState();
        };
        reader.readAsDataURL(file);
    }

    // Auto-load a street view handed over from the schoolzone map's
    // makeover album (…/?img=<street view static url>&road=…). The image
    // is fetched through our backend proxy (/api/fetch_street) to dodge
    // CORS and the Maps key's referrer restriction.
    (() => {
        const params = new URLSearchParams(location.search);
        const img = params.get('img');
        if (!img || !img.startsWith('https://maps.googleapis.com/maps/api/streetview')) return;
        fetch('/api/fetch_street?url=' + encodeURIComponent(img))
            .then(r => { if (!r.ok) throw new Error('fetch failed'); return r.blob(); })
            .then(b => {
                const road = params.get('road') || '';
                const name = (road ? road : 'streetview') + '.jpg';
                handleFile(new File([b], name, { type: b.type || 'image/jpeg' }));
            })
            .catch(() => {});   // fall back to manual upload silently
    })();

    function resetFile() {
        selectedFile = null;
        maskStrokes = [];
        useEditMask.checked = false;
        editMaskCanvas.classList.add('hidden');
        maskTools.classList.add('hidden');
        invalidateDesignPlan();
        if (originalImageUrl) URL.revokeObjectURL(originalImageUrl);
        originalImageUrl = null;
        beforeImage.src = '';
        fileInput.value = '';
        imagePreview.src = '';
        uploadContent.classList.remove('hidden');
        previewContainer.classList.add('hidden');
        updateGenerateState();
    }

    // ===== Preset selection =====
    optionCards.forEach(card => {
        card.addEventListener('click', () => {
            if (card.classList.contains('selected')) {
                card.classList.remove('selected');
                selectedPrompt = '';
                selectedPresetId = '';
            } else {
                optionCards.forEach(c => c.classList.remove('selected'));
                card.classList.add('selected');
                selectedPrompt = card.dataset.prompt;
                selectedPresetId = card.dataset.presetId || '';
            }
            invalidateDesignPlan();
            updateGenerateState();
        });
    });
    customPromptInput.addEventListener('input', () => {
        invalidateDesignPlan();
        updateGenerateState();
    });
    providerInputs.forEach(input => input.addEventListener('change', updateGenerateState));
    [
        streetContext,
        targetSpeed,
        ...intensityInputs,
        ...priorityInputs,
        ...preserveInputs,
    ].forEach(input => {
        input.addEventListener('change', () => {
            invalidateDesignPlan();
            updateGenerateState();
        });
    });

    function effectivePrompt() {
        return customPromptInput.value.trim() || selectedPrompt;
    }

    function collectDesignPreferences() {
        const selectedIntensity = document.querySelector(
            'input[name="intervention-intensity"]:checked'
        );
        return {
            street_context: streetContext.value,
            target_speed_kmh: targetSpeed.value || null,
            intervention_intensity: selectedIntensity
                ? selectedIntensity.value
                : 'balanced',
            priorities: Array.from(priorityInputs)
                .filter(input => input.checked)
                .map(input => input.value),
            preserve: Array.from(preserveInputs)
                .filter(input => input.checked)
                .map(input => input.value),
        };
    }

    function invalidateDesignPlan() {
        activeDesignPlan = null;
        designPlanPanel.classList.add('hidden');
        generateBtn.innerHTML = `${tr('inspectPlan')} <span>🔎</span>`;
    }

    function updateGenerateState() {
        const hasFile = !!selectedFile;
        const hasPrompt = effectivePrompt().length > 0;
        const hasProvider = !!document.querySelector(
            'input[name="image-provider"]:checked:not(:disabled)'
        );
        generateBtn.disabled = generationBusy || !(hasFile && hasPrompt && hasProvider);
    }

    // ===== Participatory plan preview =====
    generateBtn.addEventListener('click', async () => {
        if (!selectedFile || generationBusy) return;
        const prompt = effectivePrompt();
        if (!prompt) return;

        generationBusy = true;
        updateGenerateState();
        generateBtn.textContent = tr('buildingPlan');

        try {
            const response = await fetch('/api/design-plan', {
                method: 'POST',
                headers: languageHeaders({
                    'Content-Type': 'application/json',
                }),
                body: JSON.stringify({
                    custom_prompt: prompt,
                    preset_id: selectedPresetId,
                    design_preferences: collectDesignPreferences(),
                    language: currentLanguage,
                }),
            });
            const data = await readApiJson(response);
            if (!response.ok || data.status !== 'success') {
                throw new Error(data.error || tr('planUnavailable'));
            }
            activeDesignPlan = data;
            renderDesignPlan(data);
        } catch (error) {
            console.error('Design plan error:', error);
            alert(tr('planError', { message: error.message }));
        } finally {
            generationBusy = false;
            generateBtn.innerHTML = activeDesignPlan
                ? `${tr('refreshPlan')} <span>↻</span>`
                : `${tr('inspectPlan')} <span>🔎</span>`;
            updateGenerateState();
        }
    });

    function renderDesignPlan(data, scrollIntoView = true) {
        const spec = data.design_spec;
        designPlanTitle.textContent = spec.design_label;
        evidenceCount.textContent = tr('evidenceCount', {
            count: spec.evidence.length,
        });
        const priorityText = spec.priorities
            .map(item => item.label)
            .join(currentLanguage === 'en' ? ', ' : '、');
        const speedText = spec.target_speed_kmh
            ? `${spec.target_speed_kmh} km/h`
            : tr('unspecified');
        planSummary.textContent = [
            spec.street_context_label,
            spec.intervention_intensity_label,
            tr('targetSpeedSummary', { value: speedText }),
            tr('prioritySummary', { value: priorityText }),
        ].join(' · ');

        evidenceList.innerHTML = '';
        spec.evidence.slice(0, 8).forEach(item => {
            const row = document.createElement('div');
            row.className = 'evidence-item';
            const kind = document.createElement('span');
            kind.className = 'evidence-kind';
            kind.textContent = item.kind === 'rule'
                ? tr('designRule')
                : tr('methodReference');
            const copy = document.createElement('div');
            const title = document.createElement('strong');
            title.textContent = item.title;
            copy.appendChild(title);
            copy.appendChild(document.createTextNode(
                `${currentLanguage === 'en' ? ': ' : '：'}${item.statement} `
            ));
            const sourceText = [
                item.manual_title,
                item.section ? `§${item.section}` : '',
                item.page ? `p.${item.page}` : '',
                item.authority_label,
            ].filter(Boolean).join(' · ');
            if (item.source_url) {
                const link = document.createElement('a');
                link.href = item.source_url;
                link.target = '_blank';
                link.rel = 'noopener noreferrer';
                link.textContent = sourceText;
                copy.appendChild(link);
            } else {
                copy.appendChild(document.createTextNode(sourceText));
            }
            if (
                currentLanguage === 'en'
                && item.original_statement
                && item.original_statement !== item.statement
            ) {
                const original = document.createElement('details');
                original.className = 'evidence-original';
                const summary = document.createElement('summary');
                summary.textContent = tr('originalWording');
                const note = document.createElement('small');
                note.textContent = tr('originalLanguageNote');
                const originalCopy = document.createElement('p');
                const originalTitle = document.createElement('strong');
                originalTitle.textContent = item.original_title || item.title;
                originalCopy.appendChild(originalTitle);
                originalCopy.appendChild(document.createTextNode(
                    `：${item.original_statement}`
                ));
                original.append(summary, note, originalCopy);
                copy.appendChild(original);
            }
            row.append(kind, copy);
            evidenceList.appendChild(row);
        });

        assumptionList.innerHTML = '';
        spec.assumptions.forEach(text => {
            const item = document.createElement('div');
            item.textContent = `• ${text}`;
            assumptionList.appendChild(item);
        });
        promptPreview.textContent = data.generation_prompt;
        designPlanPanel.classList.remove('hidden');
        if (scrollIntoView) {
            designPlanPanel.scrollIntoView({
                behavior: 'smooth',
                block: 'nearest',
            });
        }
    }

    // ===== First-time generation after plan confirmation =====
    confirmGenerateBtn.addEventListener('click', async () => {
        if (!activeDesignPlan || !selectedFile || generationBusy) return;
        const prompt = effectivePrompt();
        const providerInput = document.querySelector(
            'input[name="image-provider"]:checked:not(:disabled)'
        );
        if (!prompt || !providerInput) return;

        generationBusy = true;
        updateGenerateState();
        confirmGenerateBtn.disabled = true;
        openResultPanel();
        setComparisonPosition(50);
        const providerName = providerInput.value === 'openai' ? 'OpenAI' : 'Gemini';
        setLoading(true, tr('providerDrawing', { provider: providerName }));

        try {
            const uploadFile = await compressImage(selectedFile);
            const maskBlob = await buildMaskBlob(uploadFile);
            console.log(`Upload size: ${(selectedFile.size / 1024 / 1024).toFixed(2)}MB → ${(uploadFile.size / 1024 / 1024).toFixed(2)}MB`);

            const formData = new FormData();
            formData.append('image', uploadFile);
            formData.append('prompt_type', selectedPrompt ? 'preset' : 'custom');
            formData.append('custom_prompt', prompt);
            formData.append(
                'design_preferences',
                JSON.stringify(collectDesignPreferences())
            );
            if (selectedPresetId) formData.append('preset_id', selectedPresetId);
            if (maskBlob) formData.append('mask', maskBlob, 'edit-mask.png');
            const resSel = document.getElementById('resolution-select');
            formData.append('resolution', resSel ? resSel.value : '2K');
            formData.append('provider', providerInput.value);
            formData.append('ui_language', currentLanguage);

            const response = await fetch('/api/transform', {
                method: 'POST',
                headers: languageHeaders(),
                body: formData,
            });
            const data = await readApiJson(response);
            if (!response.ok) {
                throw new Error(data.error || `HTTP ${response.status}`);
            }
            if (data.status !== 'success' || !data.image_url) {
                throw new Error(data.error || tr('unknownServerError'));
            }

            sessionId = data.session_id;
            versions = [];
            addVersion(data.version || 1, data.image_url);
            showVersion(versions.length - 1);
            renderResultReview(data.design_spec, data.audit);

            copilotMessages.innerHTML = '';
            if (data.copilot && data.copilot.message) {
                addChatMessage('assistant', data.copilot.message);
                renderSuggestions(data.copilot.suggestions || []);
            } else {
                addChatMessage('assistant', tr('fallbackGreeting'));
                renderSuggestions([
                    tr('fallbackSuggestionTrees'),
                    tr('fallbackSuggestionBench'),
                    tr('fallbackSuggestionMovement'),
                ]);
            }
            setLoading(false);
            copilotInput.focus();
        } catch (error) {
            console.error('Generation error:', error);
            setLoading(false);
            alert(tr('generationError', { message: error.message }));
            resultSection.classList.add('hidden');
        } finally {
            generationBusy = false;
            confirmGenerateBtn.disabled = false;
            updateGenerateState();
            updateVideoLauncher();
        }
    });

    function renderResultReview(spec, audit) {
        const safeSpec = spec || { evidence: [] };
        const safeAudit = audit || { checks: [] };
        currentDesignSpec = safeSpec;
        currentAudit = safeAudit;
        auditScore.textContent = safeAudit.score == null
            ? tr('manualReview')
            : `${safeAudit.score} / 100`;
        auditSummary.textContent = safeAudit.summary
            || tr('auditFallback');
        auditDisclaimer.textContent = safeAudit.disclaimer || '';

        resultAuditChecks.innerHTML = '';
        (safeAudit.checks || []).forEach(check => {
            const row = document.createElement('div');
            row.className = 'audit-check';
            const status = document.createElement('span');
            status.className = `audit-status ${check.status || 'warning'}`;
            status.textContent = check.status === 'pass'
                ? '✓'
                : check.status === 'fail' ? '!' : '?';
            const copy = document.createElement('div');
            copy.textContent = check.note
                ? `${check.label}${currentLanguage === 'en' ? ': ' : '：'}${check.note}`
                : check.label;
            row.append(status, copy);
            resultAuditChecks.appendChild(row);
        });

        resultEvidence.innerHTML = '';
        (safeSpec.evidence || []).slice(0, 6).forEach(item => {
            const row = document.createElement('div');
            row.className = 'result-evidence-item';
            const marker = document.createElement('span');
            marker.textContent = item.kind === 'rule' ? '📏' : '🧭';
            const copy = document.createElement('div');
            copy.appendChild(document.createTextNode(`${item.title} · `));
            if (item.source_url) {
                const link = document.createElement('a');
                link.href = item.source_url;
                link.target = '_blank';
                link.rel = 'noopener noreferrer';
                link.textContent = item.manual_title;
                copy.appendChild(link);
            } else {
                copy.appendChild(document.createTextNode(item.manual_title));
            }
            row.append(marker, copy);
            resultEvidence.appendChild(row);
        });
    }

    closeResultBtn.addEventListener('click', () => {
        closeVideoSetup();
        resultSection.classList.add('hidden');
    });

    // ===== Google Veo walk-through video =====
    videoLauncher.addEventListener('click', () => {
        if (videoLauncher.disabled || !versions[currentVersion]) return;
        const version = versions[currentVersion].version;
        const draft = videoDrafts.get(version);
        if (draft) {
            setCheckedVideoOption('video-speed', draft.speed);
            setCheckedVideoOption('video-duration', draft.duration);
            setCheckedVideoOption('video-format', draft.format);
        }
        videoReturnFocus = document.activeElement;
        videoModal.classList.remove('hidden');
        document.body.style.overflow = 'hidden';
        videoModalClose.focus();
    });

    videoModalClose.addEventListener('click', closeVideoSetup);
    videoCancel.addEventListener('click', closeVideoSetup);
    videoModal.addEventListener('click', (event) => {
        if (event.target === videoModal) closeVideoSetup();
    });
    document.addEventListener('keydown', (event) => {
        if (event.key === 'Escape' && !videoModal.classList.contains('hidden')) {
            closeVideoSetup();
        }
    });

    videoSetupForm.addEventListener('submit', async (event) => {
        event.preventDefault();
        const activeVersion = versions[currentVersion];
        if (!activeVersion || !sessionId || videoBusy) return;
        const formData = new FormData(videoSetupForm);
        const draft = {
            speed: formData.get('video-speed'),
            duration: formData.get('video-duration'),
            format: formData.get('video-format'),
        };
        videoDrafts.set(activeVersion.version, draft);
        videoBusy = true;
        videoPollFailures = 0;
        activeVideoJob = {
            status: 'starting',
            version: activeVersion.version,
            ...draft,
        };
        clearTimeout(videoPollTimer);
        renderVideoStatus(activeVideoJob);
        updateVideoLauncher();
        closeVideoSetup();

        try {
            const response = await fetch('/api/videos', {
                method: 'POST',
                headers: languageHeaders({
                    'Content-Type': 'application/json',
                }),
                body: JSON.stringify({
                    session_id: sessionId,
                    version: activeVersion.version,
                    language: currentLanguage,
                    ...draft,
                }),
            });
            const data = await readApiJson(response);
            if (!response.ok || !data.job_id) {
                throw new Error(data.error || tr('videoFailedMessage'));
            }
            activeVideoJob = data;
            renderVideoStatus(activeVideoJob);
            scheduleVideoPoll(8000);
        } catch (error) {
            console.error('Video creation error:', error);
            activeVideoJob = {
                ...activeVideoJob,
                status: 'failed',
                error: error.message,
            };
            videoBusy = false;
            renderVideoStatus(activeVideoJob);
            updateVideoLauncher();
        }
    });

    videoRetry.addEventListener('click', () => {
        if (!versions[currentVersion]) return;
        videoLauncher.click();
    });

    function scheduleVideoPoll(delay = 12000) {
        clearTimeout(videoPollTimer);
        videoPollTimer = setTimeout(pollVideoStatus, delay);
    }

    async function pollVideoStatus() {
        if (!activeVideoJob?.job_id || !sessionId) return;
        try {
            const params = new URLSearchParams({
                session_id: sessionId,
                language: currentLanguage,
            });
            const response = await fetch(
                `/api/videos/${activeVideoJob.job_id}?${params}`,
                { headers: languageHeaders() }
            );
            const data = await readApiJson(response);
            if (!response.ok) {
                if ([409, 502, 503].includes(response.status)) {
                    videoPollFailures += 1;
                    if (videoPollFailures <= 5) {
                        scheduleVideoPoll(
                            Number(response.headers.get('Retry-After') || 10)
                            * 1000
                        );
                        return;
                    }
                }
                throw new Error(data.error || tr('videoFailedMessage'));
            }
            videoPollFailures = 0;
            activeVideoJob = data;
            renderVideoStatus(activeVideoJob);
            if (['queued', 'in_progress'].includes(data.status)) {
                scheduleVideoPoll();
                return;
            }
            videoBusy = false;
            updateVideoLauncher();
        } catch (error) {
            console.error('Video status error:', error);
            activeVideoJob = {
                ...activeVideoJob,
                status: 'failed',
                error: error.message,
            };
            videoBusy = false;
            renderVideoStatus(activeVideoJob);
            updateVideoLauncher();
        }
    }

    function renderVideoStatus(job) {
        if (!job) {
            videoStatusCard.classList.add('hidden');
            resultSection.classList.remove('has-video-status');
            return;
        }
        resultSection.classList.add('has-video-status');
        const status = job.status || 'starting';
        const content = {
            starting: ['⏳', 'videoStarting', 'videoStartingMessage'],
            queued: ['🎞️', 'videoQueued', 'videoQueuedMessage'],
            in_progress: ['✨', 'videoGenerating', 'videoGeneratingMessage'],
            completed: ['✓', 'videoComplete', 'videoCompleteMessage'],
            failed: ['!', 'videoFailed', 'videoFailedMessage'],
        }[status] || ['🎞️', 'videoQueued', 'videoQueuedMessage'];

        videoStatusCard.classList.remove('hidden', 'is-complete', 'is-failed');
        videoStatusCard.classList.toggle('is-complete', status === 'completed');
        videoStatusCard.classList.toggle('is-failed', status === 'failed');
        videoStatusIcon.textContent = content[0];
        videoStatusTitle.textContent = tr(content[1]);
        videoStatusMessage.textContent = job.error || tr(content[2], {
            version: job.version,
        });
        videoProgress.setAttribute('aria-label', tr('videoProgressAria'));
        videoProgress.classList.toggle(
            'hidden',
            ['completed', 'failed'].includes(status)
        );
        videoPlayer.classList.toggle('hidden', status !== 'completed');
        videoStatusActions.classList.toggle(
            'hidden',
            !['completed', 'failed'].includes(status)
        );
        videoDownload.classList.toggle('hidden', status !== 'completed');
        if (status === 'completed' && job.video_url) {
            if (videoPlayer.src !== new URL(job.video_url, location.href).href) {
                videoPlayer.src = job.video_url;
            }
            videoDownload.href = job.video_url;
            videoDownload.download = `street-walkthrough-v${job.version}.mp4`;
        }
    }

    function setCheckedVideoOption(name, value) {
        const input = videoSetupForm.querySelector(
            `input[name="${name}"][value="${value}"]`
        );
        if (input) input.checked = true;
    }

    function closeVideoSetup() {
        if (videoModal.classList.contains('hidden')) return;
        videoModal.classList.add('hidden');
        document.body.style.overflow = '';
        if (videoReturnFocus && document.contains(videoReturnFocus)) {
            videoReturnFocus.focus();
        }
        videoReturnFocus = null;
    }

    function updateVideoLauncher() {
        const activeVersion = versions[currentVersion];
        videoLauncher.disabled = generationBusy || videoBusy || !activeVersion;
        if (!activeVersion) {
            videoLauncherTitle.textContent = tr('videoTitle');
            videoLauncherSummary.textContent = tr('videoSummary');
            return;
        }

        const draft = videoDrafts.get(activeVersion.version);
        if (!draft) {
            videoLauncherTitle.textContent = tr('videoTitle');
            videoLauncherSummary.textContent = tr('fromVersion', {
                version: activeVersion.version,
            });
            return;
        }

        videoLauncherTitle.textContent = tr('videoReady', {
            version: activeVersion.version,
        });
        videoLauncherSummary.textContent = [
            tr(draft.speed),
            tr('seconds', { value: draft.duration }),
            tr(draft.format),
        ].join(' · ');
    }

    // ===== Co-pilot chat =====
    copilotInputForm.addEventListener('submit', (e) => {
        e.preventDefault();
        const msg = copilotInput.value.trim();
        if (!msg) return;
        sendChat(msg);
        copilotInput.value = '';
    });

    async function sendChat(message) {
        if (!sessionId || chatBusy) return;
        chatBusy = true;
        addChatMessage('user', message);
        clearSuggestions();
        addTypingIndicator();
        copilotSend.disabled = true;

        try {
            const response = await fetch('/api/chat', {
                method: 'POST',
                headers: languageHeaders({
                    'Content-Type': 'application/json',
                }),
                body: JSON.stringify({
                    session_id: sessionId,
                    message,
                    language: currentLanguage,
                }),
            });
            const data = await readApiJson(response);
            removeTypingIndicator();

            if (!response.ok || data.status !== 'success') {
                throw new Error(data.error || tr('chatFailed'));
            }

            if (data.intent === 'refine' && data.image_url) {
                addVersion(data.version, data.image_url);
                showVersion(versions.length - 1);
            }
            if (data.design_spec || data.audit) {
                renderResultReview(data.design_spec, data.audit);
            }
            addChatMessage('assistant', data.message);
            renderSuggestions(data.suggestions || []);
        } catch (error) {
            removeTypingIndicator();
            console.error('Chat error:', error);
            addChatMessage(
                'assistant',
                tr('chatError', {
                    message: error.message || tr('retryChat'),
                })
            );
        } finally {
            chatBusy = false;
            copilotSend.disabled = false;
            copilotInput.focus();
        }
    }

    function addChatMessage(role, text) {
        const bubble = document.createElement('div');
        bubble.className = `chat-bubble chat-${role}`;
        bubble.textContent = text;
        copilotMessages.appendChild(bubble);
        copilotMessages.scrollTop = copilotMessages.scrollHeight;
    }

    function addTypingIndicator() {
        if (document.getElementById('typing-indicator')) return;
        const el = document.createElement('div');
        el.className = 'chat-bubble chat-assistant typing-indicator';
        el.id = 'typing-indicator';
        el.innerHTML = '<span></span><span></span><span></span>';
        copilotMessages.appendChild(el);
        copilotMessages.scrollTop = copilotMessages.scrollHeight;
    }

    function removeTypingIndicator() {
        const el = document.getElementById('typing-indicator');
        if (el) el.remove();
    }

    function renderSuggestions(items) {
        copilotSuggestions.innerHTML = '';
        items.forEach(text => {
            const chip = document.createElement('button');
            chip.type = 'button';
            chip.className = 'suggestion-chip';
            chip.textContent = text;
            chip.addEventListener('click', () => sendChat(text));
            copilotSuggestions.appendChild(chip);
        });
    }
    function clearSuggestions() {
        copilotSuggestions.innerHTML = '';
    }

    // ===== Versions =====
    function addVersion(versionNum, imageUrl) {
        const url = imageUrl + (imageUrl.includes('?') ? '&' : '?') + 't=' + Date.now();
        versions.push({ version: versionNum, image_url: url });
        renderVersionStrip();
    }

    function renderVersionStrip() {
        versionStrip.innerHTML = '';
        versions.forEach((v, idx) => {
            const thumb = document.createElement('button');
            thumb.type = 'button';
            thumb.className = 'version-thumb' + (idx === currentVersion ? ' active' : '');
            thumb.innerHTML = `
                <img src="${v.image_url}" alt="v${v.version}">
                <span class="version-label">v${v.version}</span>
            `;
            thumb.addEventListener('click', () => showVersion(idx));
            versionStrip.appendChild(thumb);
        });
    }

    function showVersion(idx) {
        if (idx < 0 || idx >= versions.length) return;
        currentVersion = idx;
        const v = versions[idx];
        resultImage.src = v.image_url;
        roundBadge.textContent = tr('round', { version: v.version });
        renderVersionStrip();
        updateVideoLauncher();
    }

    function openResultPanel() {
        resultSection.classList.remove('hidden');
    }

    function setLoading(on, text) {
        if (on) {
            if (text) loadingText.textContent = text;
            loadingOverlay.classList.remove('hidden');
            resultImage.classList.add('hidden');
            videoLauncher.disabled = true;
        } else {
            loadingOverlay.classList.add('hidden');
            resultImage.classList.remove('hidden');
            updateVideoLauncher();
        }
    }

    window.addEventListener('beforeunload', () => {
        if (originalImageUrl) URL.revokeObjectURL(originalImageUrl);
    });

    applyLanguage();
});
