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
                reject(new Error('無法轉換這張圖片，請改用 JPEG、PNG 或 WebP。'));
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
        const diagnostic = requestId ? `（診斷碼 ${requestId}）` : '';
        if (response.status >= 500) {
            throw new Error(
                `生成程序在完成前中斷（HTTP ${response.status}）${diagnostic}。`
                + '可能是 Render worker 重啟、記憶體不足或上游服務逾時；'
                + '請等 30 秒再試一次，並先改用 1K 或 2K。'
            );
        }
        throw new Error(
            `伺服器回傳了無法辨識的內容（HTTP ${response.status}）${diagnostic}。`
        );
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
    let maskStrokes = [];
    let activeMaskStroke = null;
    const videoDrafts = new Map();
    let videoReturnFocus = null;

    const videoOptionLabels = {
        speed: {
            gentle: '慢慢散步',
            natural: '自然步行',
            brisk: '輕快前進',
        },
        format: {
            landscape: '橫式',
            portrait: '直式',
        },
    };

    function setComparisonPosition(value) {
        const position = Math.min(100, Math.max(0, Number(value)));
        comparisonViewer.style.setProperty('--comparison-position', `${position}%`);
        comparisonRange.value = String(position);
        comparisonRange.setAttribute(
            'aria-valuetext',
            `改造前 ${position}%，改造後 ${100 - position}%`
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
                reject(new Error('無法建立改造範圍遮罩。'));
            };
            image.src = url;
        });
    }

    async function buildMaskBlob(uploadFile) {
        if (!useEditMask.checked) return null;
        if (!maskStrokes.length) {
            throw new Error('請先在照片上塗出希望 AI 改造的範圍。');
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
                else reject(new Error('無法輸出改造範圍遮罩。'));
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
            alert('Please upload an image file.');
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
        generateBtn.innerHTML = '檢視設計計畫 <span>🔎</span>';
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
        generateBtn.textContent = '正在整理設計依據…';

        try {
            const response = await fetch('/api/design-plan', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    custom_prompt: prompt,
                    preset_id: selectedPresetId,
                    design_preferences: collectDesignPreferences(),
                }),
            });
            const data = await readApiJson(response);
            if (!response.ok || data.status !== 'success') {
                throw new Error(data.error || '無法建立設計計畫。');
            }
            activeDesignPlan = data;
            renderDesignPlan(data);
        } catch (error) {
            console.error('Design plan error:', error);
            alert('設計計畫建立失敗：' + error.message);
        } finally {
            generationBusy = false;
            generateBtn.innerHTML = activeDesignPlan
                ? '重新整理設計計畫 <span>↻</span>'
                : '檢視設計計畫 <span>🔎</span>';
            updateGenerateState();
        }
    });

    function renderDesignPlan(data) {
        const spec = data.design_spec;
        designPlanTitle.textContent = spec.design_label;
        evidenceCount.textContent = `${spec.evidence.length} 項依據`;
        const priorityText = spec.priorities.map(item => item.label).join('、');
        const speedText = spec.target_speed_kmh
            ? `${spec.target_speed_kmh} km/h`
            : '未指定';
        planSummary.textContent = [
            spec.street_context_label,
            spec.intervention_intensity_label,
            `目標速度：${speedText}`,
            `優先：${priorityText}`,
        ].join(' · ');

        evidenceList.innerHTML = '';
        spec.evidence.slice(0, 8).forEach(item => {
            const row = document.createElement('div');
            row.className = 'evidence-item';
            const kind = document.createElement('span');
            kind.className = 'evidence-kind';
            kind.textContent = item.kind === 'rule' ? '設計規則' : '方法參考';
            const copy = document.createElement('div');
            const title = document.createElement('strong');
            title.textContent = item.title;
            copy.appendChild(title);
            copy.appendChild(document.createTextNode(`：${item.statement} `));
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
        designPlanPanel.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
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
        setLoading(true, `${providerName} 正在依確認計畫描繪新街道...`);

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

            const response = await fetch('/api/transform', {
                method: 'POST',
                body: formData,
            });
            const data = await readApiJson(response);
            if (!response.ok) {
                throw new Error(data.error || `HTTP ${response.status}`);
            }
            if (data.status !== 'success' || !data.image_url) {
                throw new Error(data.error || 'Unknown error from server');
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
                addChatMessage('assistant', '嗨，我是小綠 🌱 跟我說你想怎麼調整這條街吧！');
                renderSuggestions(['再多一些樹', '加長椅', '檢查動線']);
            }
            setLoading(false);
            copilotInput.focus();
        } catch (error) {
            console.error('Generation error:', error);
            setLoading(false);
            alert('生成失敗：' + error.message);
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
        auditScore.textContent = safeAudit.score == null
            ? '待人工確認'
            : `${safeAudit.score} / 100`;
        auditSummary.textContent = safeAudit.summary
            || '尚未完成模型視覺稽核，請共同確認。';
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
                ? `${check.label}：${check.note}`
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

    // ===== Walk-through video setup (phase 1: interface + saved draft) =====
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

    videoSetupForm.addEventListener('submit', (event) => {
        event.preventDefault();
        const activeVersion = versions[currentVersion];
        if (!activeVersion) return;
        const formData = new FormData(videoSetupForm);
        videoDrafts.set(activeVersion.version, {
            speed: formData.get('video-speed'),
            duration: formData.get('video-duration'),
            format: formData.get('video-format'),
        });
        updateVideoLauncher();
        closeVideoSetup();
    });

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
        videoLauncher.disabled = generationBusy || !activeVersion;
        if (!activeVersion) {
            videoLauncherTitle.textContent = '滿意這一版？製作街道漫遊影片';
            videoLauncherSummary.textContent = '以第一人稱沿著新街道向前走';
            return;
        }

        const draft = videoDrafts.get(activeVersion.version);
        if (!draft) {
            videoLauncherTitle.textContent = '滿意這一版？製作街道漫遊影片';
            videoLauncherSummary.textContent = `從 v${activeVersion.version} 建立第一人稱漫遊`;
            return;
        }

        videoLauncherTitle.textContent = `v${activeVersion.version} 漫遊影片設定完成`;
        videoLauncherSummary.textContent = [
            videoOptionLabels.speed[draft.speed],
            `${draft.duration} 秒`,
            videoOptionLabels.format[draft.format],
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
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ session_id: sessionId, message }),
            });
            const data = await readApiJson(response);
            removeTypingIndicator();

            if (!response.ok || data.status !== 'success') {
                throw new Error(data.error || 'Chat failed');
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
                `糟糕，我這邊有點卡 🌱 ${error.message || '可以再試一次嗎？'}`
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
        roundBadge.textContent = `共創回合 ${v.version}`;
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
});
