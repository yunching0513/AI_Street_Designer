const GALLERY_TEXT = {
    'zh-TW': {
        pageTitle: '街景成果牆｜AI Street Designer',
        homeAria: 'AI Street Designer 首頁',
        primaryNav: '主要導覽',
        createDesign: '＋ 創作我的街道',
        kicker: 'COMMUNITY STREET IDEAS',
        title: '大家想像中的好街道',
        intro: '看看使用者與小綠共同完成的街道改造成果，也用一個喜歡，告訴我們哪些設計最打動你。',
        statsAria: '成果牆統計',
        works: '公開成果',
        likes: '累積喜歡',
        privacyTitle: '由創作者自願分享',
        privacyBody: '這裡只顯示使用者選擇公開的生成成果；原始上傳照片不會出現在成果牆。',
        browse: '瀏覽作品',
        feedTitle: '街道共創成果',
        sortAria: '成果排序',
        latest: '最新分享',
        popular: '最多喜歡',
        feedbackNote: '看到喜歡的成果，就按下「我喜歡這個街景設計！」',
        loading: '正在整理大家的街道作品…',
        emptyTitle: '第一張街道作品，等你來分享',
        emptyBody: '先創作一個街道設計，再從生成結果選擇「分享至成果牆」。',
        emptyAction: '開始創作',
        errorTitle: '成果牆暫時沒有載入',
        errorBody: '請稍後再試一次。',
        retry: '重新載入',
        untitled: '一個更適合人的街道想像',
        coDesignVersion: '共同設計 v{version}',
        like: '我喜歡這個街景設計！',
        liked: '謝謝你的喜歡！',
        likeAria: '喜歡這個街景設計，目前 {count} 人喜歡',
        sharedOn: '{date} 分享',
        imageAlt: '使用者分享的街道改造成果：{title}',
        feedbackError: '回饋暫時沒有送出，請再試一次。',
    },
    en: {
        pageTitle: 'Community Gallery | AI Street Designer',
        homeAria: 'AI Street Designer home',
        primaryNav: 'Primary navigation',
        createDesign: '+ Create my street',
        kicker: 'COMMUNITY STREET IDEAS',
        title: 'Streets imagined by the community',
        intro: 'Explore street transformations co-designed with Greenie, and show us which ideas resonate with you.',
        statsAria: 'Gallery totals',
        works: 'shared designs',
        likes: 'community likes',
        privacyTitle: 'Shared voluntarily by creators',
        privacyBody: 'Only generated results that creators choose to publish appear here. Original uploaded photos are never shown.',
        browse: 'EXPLORE',
        feedTitle: 'Community street designs',
        sortAria: 'Sort gallery',
        latest: 'Newest',
        popular: 'Most liked',
        feedbackNote: 'See an idea you love? Choose “I like this street design!”',
        loading: 'Gathering the community’s street ideas…',
        emptyTitle: 'Share the first street design',
        emptyBody: 'Create a street design, then choose “Share to gallery” from the generated result.',
        emptyAction: 'Start designing',
        errorTitle: 'The gallery could not load',
        errorBody: 'Please try again in a moment.',
        retry: 'Try again',
        untitled: 'A more people-friendly street',
        coDesignVersion: 'Co-design v{version}',
        like: 'I like this street design!',
        liked: 'Thanks for liking this!',
        likeAria: 'Like this street design; {count} likes so far',
        sharedOn: 'Shared {date}',
        imageAlt: 'A community street transformation: {title}',
        feedbackError: 'Your feedback could not be sent. Please try again.',
    },
};

const LANGUAGE_KEY = 'street-designer-language';
const VISITOR_KEY = 'street-designer-gallery-visitor';
const LIKED_KEY = 'street-designer-gallery-liked';
const storedGalleryLanguage = localStorage.getItem(LANGUAGE_KEY);
let galleryLanguage = storedGalleryLanguage
    ? (storedGalleryLanguage === 'en' ? 'en' : 'zh-TW')
    : ((navigator.language || '').startsWith('en') ? 'en' : 'zh-TW');
let activeSort = 'latest';
let galleryStats = { works: 0, likes: 0 };

const galleryGrid = document.getElementById('gallery-grid');
const galleryState = document.getElementById('gallery-state');
const workCount = document.getElementById('gallery-work-count');
const likeCount = document.getElementById('gallery-like-count');
const sortButtons = document.querySelectorAll('[data-sort]');
const languageButtons = document.querySelectorAll(
    '.language-switch button[data-language]'
);

function galleryTr(key, replacements = {}) {
    let value = (GALLERY_TEXT[galleryLanguage] || GALLERY_TEXT['zh-TW'])[key] || key;
    Object.entries(replacements).forEach(([name, replacement]) => {
        value = value.replaceAll(`{${name}}`, String(replacement));
    });
    return value;
}

function applyGalleryLanguage() {
    document.documentElement.lang = galleryLanguage === 'en' ? 'en' : 'zh-Hant';
    document.title = galleryTr('pageTitle');
    document.querySelectorAll('[data-i18n]').forEach(element => {
        element.textContent = galleryTr(element.dataset.i18n);
    });
    document.querySelectorAll('[data-i18n-aria-label]').forEach(element => {
        element.setAttribute(
            'aria-label',
            galleryTr(element.dataset.i18nAriaLabel)
        );
    });
    languageButtons.forEach(button => {
        button.setAttribute(
            'aria-pressed',
            String(button.dataset.language === galleryLanguage)
        );
    });
}

function makeElement(tag, className, text) {
    const element = document.createElement(tag);
    if (className) element.className = className;
    if (text !== undefined) element.textContent = text;
    return element;
}

function visitorToken() {
    let token = localStorage.getItem(VISITOR_KEY);
    if (token && /^[A-Za-z0-9_-]{16,80}$/.test(token)) return token;
    if (window.crypto?.randomUUID) {
        token = window.crypto.randomUUID().replaceAll('-', '');
    } else {
        token = `${Date.now()}${Math.random().toString(36).slice(2)}gallery`;
    }
    localStorage.setItem(VISITOR_KEY, token);
    return token;
}

function likedPostIds() {
    try {
        const value = JSON.parse(localStorage.getItem(LIKED_KEY) || '[]');
        return new Set(Array.isArray(value) ? value : []);
    } catch (_error) {
        return new Set();
    }
}

function rememberLike(postId) {
    const ids = likedPostIds();
    ids.add(postId);
    localStorage.setItem(LIKED_KEY, JSON.stringify([...ids].slice(-500)));
}

function formattedDate(timestamp) {
    return new Intl.DateTimeFormat(
        galleryLanguage === 'en' ? 'en' : 'zh-TW',
        { year: 'numeric', month: 'short', day: 'numeric' }
    ).format(new Date(Number(timestamp) * 1000));
}

function renderStats() {
    const formatter = new Intl.NumberFormat(
        galleryLanguage === 'en' ? 'en' : 'zh-TW'
    );
    workCount.textContent = formatter.format(galleryStats.works);
    likeCount.textContent = formatter.format(galleryStats.likes);
}

function renderGalleryCard(post) {
    const article = makeElement('article', 'gallery-card');
    const imageFrame = makeElement('div', 'gallery-card-image');
    const image = makeElement('img');
    const titleText = post.caption || post.design_label || galleryTr('untitled');
    image.src = post.image_url;
    image.alt = galleryTr('imageAlt', { title: titleText });
    image.loading = 'lazy';
    image.decoding = 'async';
    imageFrame.appendChild(image);

    const version = makeElement(
        'span',
        'gallery-version-badge',
        galleryTr('coDesignVersion', { version: post.version })
    );
    imageFrame.appendChild(version);
    article.appendChild(imageFrame);

    const body = makeElement('div', 'gallery-card-body');
    const title = makeElement('h3', '', titleText);
    body.appendChild(title);

    const details = makeElement('div', 'gallery-card-details');
    if (post.caption && post.design_label) {
        details.appendChild(makeElement('span', '', post.design_label));
    }
    if (post.street_context) {
        details.appendChild(makeElement('span', '', post.street_context));
    }
    details.appendChild(makeElement(
        'time',
        '',
        galleryTr('sharedOn', { date: formattedDate(post.created_at) })
    ));
    body.appendChild(details);

    const action = makeElement('div', 'gallery-card-action');
    const likeButton = makeElement('button', 'gallery-like-button');
    likeButton.type = 'button';
    const heart = makeElement('span', 'gallery-like-heart', '♥');
    heart.setAttribute('aria-hidden', 'true');
    const label = makeElement('span', 'gallery-like-label', galleryTr('like'));
    const count = makeElement('strong', 'gallery-like-count', String(post.likes));
    likeButton.append(heart, label, count);
    const alreadyLiked = likedPostIds().has(post.id);
    if (alreadyLiked) {
        likeButton.classList.add('is-liked');
        likeButton.disabled = true;
        label.textContent = galleryTr('liked');
    }
    likeButton.setAttribute(
        'aria-label',
        galleryTr('likeAria', { count: post.likes })
    );

    likeButton.addEventListener('click', async () => {
        if (likeButton.disabled) return;
        likeButton.disabled = true;
        likeButton.classList.add('is-sending');
        try {
            const response = await fetch(`/api/gallery/${post.id}/like`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-UI-Language': galleryLanguage,
                },
                body: JSON.stringify({
                    visitor_token: visitorToken(),
                    language: galleryLanguage,
                }),
            });
            const data = await response.json();
            if (!response.ok) {
                throw new Error(data.error || `HTTP ${response.status}`);
            }
            const previousLikes = Number(post.likes) || 0;
            post.likes = Number(data.likes) || previousLikes;
            count.textContent = String(post.likes);
            label.textContent = galleryTr('liked');
            likeButton.classList.remove('is-sending');
            likeButton.classList.add('is-liked');
            likeButton.setAttribute(
                'aria-label',
                galleryTr('likeAria', { count: post.likes })
            );
            rememberLike(post.id);
            if (data.new_like) {
                galleryStats.likes += Math.max(0, post.likes - previousLikes);
                renderStats();
            }
        } catch (error) {
            console.error('Gallery feedback error:', error);
            likeButton.disabled = false;
            likeButton.classList.remove('is-sending');
            window.alert(galleryTr('feedbackError'));
        }
    });
    action.appendChild(likeButton);
    body.appendChild(action);
    article.appendChild(body);
    return article;
}

function renderState(type) {
    galleryState.replaceChildren();
    galleryState.className = `gallery-state gallery-state-${type}`;
    if (type === 'hidden') {
        galleryState.classList.add('hidden');
        return;
    }
    galleryState.classList.remove('hidden');
    const icon = makeElement(
        'span',
        'gallery-state-icon',
        type === 'error' ? '🌧️' : type === 'empty' ? '🌱' : '🌿'
    );
    icon.setAttribute('aria-hidden', 'true');
    const titleKey = type === 'error'
        ? 'errorTitle'
        : type === 'empty' ? 'emptyTitle' : 'loading';
    galleryState.append(icon, makeElement('strong', '', galleryTr(titleKey)));
    if (type === 'error' || type === 'empty') {
        galleryState.appendChild(makeElement(
            'p',
            '',
            galleryTr(type === 'error' ? 'errorBody' : 'emptyBody')
        ));
        const action = makeElement(
            type === 'error' ? 'button' : 'a',
            'gallery-state-action',
            galleryTr(type === 'error' ? 'retry' : 'emptyAction')
        );
        if (type === 'error') {
            action.type = 'button';
            action.addEventListener('click', () => loadGallery());
        } else {
            action.href = '/';
        }
        galleryState.appendChild(action);
    }
}

async function loadGallery() {
    renderState('loading');
    galleryGrid.replaceChildren();
    sortButtons.forEach(button => {
        const selected = button.dataset.sort === activeSort;
        button.setAttribute('aria-pressed', String(selected));
        button.disabled = true;
    });
    try {
        const response = await fetch(
            `/api/gallery?sort=${encodeURIComponent(activeSort)}&limit=48`,
            { headers: { 'X-UI-Language': galleryLanguage } }
        );
        const data = await response.json();
        if (!response.ok) {
            throw new Error(data.error || `HTTP ${response.status}`);
        }
        galleryStats = data.stats || { works: 0, likes: 0 };
        renderStats();
        const items = Array.isArray(data.items) ? data.items : [];
        items.forEach(post => galleryGrid.appendChild(renderGalleryCard(post)));
        renderState(items.length ? 'hidden' : 'empty');
    } catch (error) {
        console.error('Gallery loading error:', error);
        renderState('error');
    } finally {
        sortButtons.forEach(button => {
            button.disabled = false;
        });
    }
}

sortButtons.forEach(button => {
    button.addEventListener('click', () => {
        if (button.dataset.sort === activeSort) return;
        activeSort = button.dataset.sort;
        loadGallery();
    });
});

languageButtons.forEach(button => {
    button.addEventListener('click', () => {
        const nextLanguage = button.dataset.language === 'en' ? 'en' : 'zh-TW';
        if (nextLanguage === galleryLanguage) return;
        galleryLanguage = nextLanguage;
        localStorage.setItem(LANGUAGE_KEY, galleryLanguage);
        applyGalleryLanguage();
        loadGallery();
    });
});

applyGalleryLanguage();
loadGallery();
