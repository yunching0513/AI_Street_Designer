document.addEventListener('DOMContentLoaded', () => {
    // Elements
    const dropZone = document.getElementById('drop-zone');
    const fileInput = document.getElementById('file-input');
    const uploadContent = document.getElementById('upload-content');
    const previewContainer = document.getElementById('preview-container');
    const imagePreview = document.getElementById('image-preview');
    const removeBtn = document.getElementById('remove-image');
    const optionCards = document.querySelectorAll('.option-card');
    const customPromptInput = document.getElementById('custom-prompt');
    const generateBtn = document.getElementById('generate-btn');
    const resultSection = document.getElementById('result-section');
    const resultImage = document.getElementById('result-image');
    const closeResultBtn = document.getElementById('close-result');
    const loadingOverlay = document.getElementById('loading-overlay');

    let selectedFile = null;
    let selectedPrompt = '';

    // Drag & Drop
    dropZone.addEventListener('dragover', (e) => {
        e.preventDefault();
        dropZone.classList.add('dragover');
    });

    dropZone.addEventListener('dragleave', () => {
        dropZone.classList.remove('dragover');
    });

    dropZone.addEventListener('drop', (e) => {
        e.preventDefault();
        dropZone.classList.remove('dragover');
        if (e.dataTransfer.files.length) {
            handleFile(e.dataTransfer.files[0]);
        }
    });

    dropZone.addEventListener('click', () => {
        if (!selectedFile) fileInput.click();
    });

    fileInput.addEventListener('change', (e) => {
        if (e.target.files.length) {
            handleFile(e.target.files[0]);
        }
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

    function resetFile() {
        selectedFile = null;
        fileInput.value = '';
        imagePreview.src = '';
        uploadContent.classList.remove('hidden');
        previewContainer.classList.add('hidden');
        updateGenerateState();
    }

    // Prompt Selection
    optionCards.forEach(card => {
        card.addEventListener('click', () => {
            // Toggle selection
            if (card.classList.contains('selected')) {
                card.classList.remove('selected');
                selectedPrompt = '';
            } else {
                // Clear others
                optionCards.forEach(c => c.classList.remove('selected'));
                card.classList.add('selected');
                selectedPrompt = card.dataset.prompt;
                // Clear custom input if preset is chosen (optional behavior)
                // customPromptInput.value = ''; 
            }
            updateGenerateState();
        });
    });

    customPromptInput.addEventListener('input', () => {
        // Deselect presets if typing custom? Or keep both?
        // Let's keep both, but update state
        updateGenerateState();
    });

    function updateGenerateState() {
        const hasFile = !!selectedFile;
        // Button enabled if file is there. 
        // Prompt is optional? Or required? Let's say required.
        const hasPrompt = selectedPrompt || customPromptInput.value.trim().length > 0;

        generateBtn.disabled = !(hasFile && hasPrompt);
    }

    // Generate Action
    generateBtn.addEventListener('click', async () => {
        if (!selectedFile) return;

        const effectivePrompt = customPromptInput.value.trim() || selectedPrompt;
        if (!effectivePrompt) return;

        // Show UI
        resultSection.classList.remove('hidden');
        loadingOverlay.classList.remove('hidden');
        resultImage.classList.add('hidden');

        // Prepare Form Data
        const formData = new FormData();
        formData.append('image', selectedFile);
        formData.append('prompt_type', selectedPrompt ? 'preset' : 'custom');
        formData.append('custom_prompt', effectivePrompt);

        try {
            const response = await fetch('/api/transform', {
                method: 'POST',
                body: formData
            });

            const data = await response.json();

            // Handle backend response
            if (data.status === 'success' && data.image_url) {
                console.log('Generation success:', data.image_url);
                // Add timestamp to prevent browser caching
                resultImage.src = data.image_url + '?t=' + new Date().getTime();

                loadingOverlay.classList.add('hidden');
                resultImage.classList.remove('hidden');
            } else {
                throw new Error(data.error || 'Unknown error from server');
            }

        } catch (error) {
            console.error('Error:', error);
            alert('Generation failed: ' + error.message);
            resultSection.classList.add('hidden');
        }
    });

    closeResultBtn.addEventListener('click', () => {
        resultSection.classList.add('hidden');
    });
});
