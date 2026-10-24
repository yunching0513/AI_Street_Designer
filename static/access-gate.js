// Demo access code gate.
// Wraps fetch for the AI endpoints that cost money. When the server answers
// 401 access_code_required, ask for the code, verify it with /api/access
// (which sets an HttpOnly cookie), then retry the original request once.
(() => {
    const GATED_PATHS = ['/api/transform', '/api/chat', '/api/videos'];
    const originalFetch = window.fetch.bind(window);
    let pendingPrompt = null;

    const isEnglish = () => (document.documentElement.lang || '').toLowerCase().startsWith('en');

    const text = () => isEnglish()
        ? {
            title: 'Enter the demo access code',
            body: 'Browsing is open to everyone. Generating images, chatting with Greenie and making videos uses paid AI services, so an access code is needed.',
            placeholder: 'Access code',
            submit: 'Unlock',
            cancel: 'Cancel',
            invalid: 'That access code is not correct.',
            limited: 'Too many attempts. Please try again in a few minutes.',
            failed: 'Could not check the code. Please try again.',
            request: 'No code? Ask Yun-Ching Wu for one.',
        }
        : {
            title: '請輸入示範通行碼',
            body: '瀏覽網站不需要通行碼。產生圖片、和小綠對話、製作影片會用到付費 AI 服務，所以需要通行碼。',
            placeholder: '通行碼',
            submit: '解鎖',
            cancel: '取消',
            invalid: '通行碼不正確。',
            limited: '嘗試次數太多，請過幾分鐘再試。',
            failed: '暫時無法驗證通行碼，請再試一次。',
            request: '沒有通行碼？請向吳昀慶索取。',
        };

    const isGated = (input, init) => {
        const url = typeof input === 'string' ? input : (input && input.url) || '';
        const method = ((init && init.method) || (input && input.method) || 'GET').toUpperCase();
        if (method !== 'POST') return false;
        try {
            return GATED_PATHS.includes(new URL(url, window.location.href).pathname);
        } catch (e) {
            return false;
        }
    };

    const buildDialog = () => {
        const t = text();
        const dialog = document.createElement('dialog');
        dialog.className = 'access-dialog';
        dialog.innerHTML = `
            <form method="dialog" class="access-form">
                <div class="access-icon" aria-hidden="true">🔑</div>
                <h2 class="access-title"></h2>
                <p class="access-body"></p>
                <input class="access-input" type="password" autocomplete="off" autocapitalize="off" spellcheck="false" required>
                <p class="access-error" role="alert" hidden></p>
                <div class="access-actions">
                    <button type="button" class="access-cancel"></button>
                    <button type="submit" class="access-submit"></button>
                </div>
                <p class="access-request"></p>
            </form>`;
        dialog.querySelector('.access-title').textContent = t.title;
        dialog.querySelector('.access-body').textContent = t.body;
        dialog.querySelector('.access-input').placeholder = t.placeholder;
        dialog.querySelector('.access-input').setAttribute('aria-label', t.placeholder);
        dialog.querySelector('.access-submit').textContent = t.submit;
        dialog.querySelector('.access-cancel').textContent = t.cancel;
        dialog.querySelector('.access-request').textContent = t.request;
        document.body.appendChild(dialog);
        return dialog;
    };

    const askForCode = () => {
        if (pendingPrompt) return pendingPrompt;
        pendingPrompt = new Promise(resolve => {
            const t = text();
            const dialog = buildDialog();
            const form = dialog.querySelector('form');
            const input = dialog.querySelector('.access-input');
            const error = dialog.querySelector('.access-error');
            const submit = dialog.querySelector('.access-submit');

            const finish = granted => {
                dialog.close();
                dialog.remove();
                pendingPrompt = null;
                resolve(granted);
            };

            dialog.querySelector('.access-cancel').addEventListener('click', () => finish(false));
            dialog.addEventListener('cancel', event => {
                event.preventDefault();
                finish(false);
            });

            form.addEventListener('submit', async event => {
                event.preventDefault();
                const code = input.value.trim();
                if (!code) return;
                submit.disabled = true;
                error.hidden = true;
                try {
                    const response = await originalFetch('/api/access', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        credentials: 'same-origin',
                        body: JSON.stringify({ code }),
                    });
                    if (response.ok) {
                        finish(true);
                        return;
                    }
                    error.textContent = response.status === 429 ? t.limited : t.invalid;
                } catch (e) {
                    error.textContent = t.failed;
                }
                error.hidden = false;
                submit.disabled = false;
                input.select();
            });

            dialog.showModal();
            input.focus();
        });
        return pendingPrompt;
    };

    window.fetch = async (input, init) => {
        if (!isGated(input, init)) return originalFetch(input, init);
        const response = await originalFetch(input, init);
        if (response.status !== 401) return response;
        let data = null;
        try {
            data = await response.clone().json();
        } catch (e) {
            return response;
        }
        if (!data || data.code !== 'access_code_required') return response;
        const granted = await askForCode();
        if (!granted) return response;
        return originalFetch(input, init);
    };
})();
