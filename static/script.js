// Resize and re-encode large images so the request body stays under Vercel's 4.5MB limit.
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
        if (response.status >= 500) {
            throw new Error(
                '伺服器暫時沒回應（可能正在生成中逾時，或服務剛從休眠喚醒）。'
                + '請等 30 秒再試一次；若選了 4K，改用 2K 會更穩定。'
            );
        }
        throw new Error(`伺服器回傳了無法辨識的內容（HTTP ${response.status}）。`);
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

    // Result + co-pilot
    const resultSection = document.getElementById('result-section');
    const resultImage = document.getElementById('result-image');
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

    // State
    let selectedFile = null;
    let selectedPrompt = '';
    let selectedPresetId = '';
    let sessionId = null;
    let versions = []; // [{ version, image_url }]
    let currentVersion = 0;
    let chatBusy = false;
    let generationBusy = false;

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
            updateGenerateState();
        });
    });
    customPromptInput.addEventListener('input', updateGenerateState);
    providerInputs.forEach(input => input.addEventListener('change', updateGenerateState));

    function updateGenerateState() {
        const hasFile = !!selectedFile;
        const hasPrompt = selectedPrompt || customPromptInput.value.trim().length > 0;
        const hasProvider = !!document.querySelector(
            'input[name="image-provider"]:checked:not(:disabled)'
        );
        generateBtn.disabled = generationBusy || !(hasFile && hasPrompt && hasProvider);
    }

    // ===== First-time generation =====
    generateBtn.addEventListener('click', async () => {
        if (!selectedFile || generationBusy) return;
        const effectivePrompt = customPromptInput.value.trim() || selectedPrompt;
        if (!effectivePrompt) return;
        const providerInput = document.querySelector(
            'input[name="image-provider"]:checked:not(:disabled)'
        );
        if (!providerInput) return;

        generationBusy = true;
        updateGenerateState();
        openResultPanel();
        const providerName = providerInput.value === 'openai' ? 'OpenAI' : 'Gemini';
        setLoading(true, `${providerName} 正在描繪你的新街道...`);

        try {
            const uploadFile = await compressImage(selectedFile);
            console.log(`Upload size: ${(selectedFile.size / 1024 / 1024).toFixed(2)}MB → ${(uploadFile.size / 1024 / 1024).toFixed(2)}MB`);

            const formData = new FormData();
            formData.append('image', uploadFile);
            formData.append('prompt_type', selectedPrompt ? 'preset' : 'custom');
            formData.append('custom_prompt', effectivePrompt);
            if (selectedPresetId) formData.append('preset_id', selectedPresetId);
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

            // Reset chat with greeting from 小綠
            copilotMessages.innerHTML = '';
            if (data.copilot && data.copilot.message) {
                addChatMessage('assistant', data.copilot.message);
                renderSuggestions(data.copilot.suggestions || []);
            } else {
                addChatMessage('assistant', '嗨，我是小綠 🌱 跟我說你想怎麼調整這條街吧！');
                renderSuggestions(['再多一些樹', '加長椅', '換成夜景']);
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
            updateGenerateState();
        }
    });

    closeResultBtn.addEventListener('click', () => {
        resultSection.classList.add('hidden');
    });

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
    }

    function openResultPanel() {
        resultSection.classList.remove('hidden');
    }

    function setLoading(on, text) {
        if (on) {
            if (text) loadingText.textContent = text;
            loadingOverlay.classList.remove('hidden');
            resultImage.classList.add('hidden');
        } else {
            loadingOverlay.classList.add('hidden');
            resultImage.classList.remove('hidden');
        }
    }
});
