/**
 * script.js — ReadNext Podcast Generator Frontend Logic
 *
 * Handles:
 * - Tab switching (URL / Text input)
 * - API call to generate podcast
 * - Progress step animation
 * - Custom audio player controls
 * - Waveform seek bar
 * - Transcript rendering with live highlight sync
 */

// =====================================================================
// DOM References
// =====================================================================

const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => document.querySelectorAll(sel);

// Sections
const inputSection    = $('#input-section');
const progressSection = $('#progress-section');
const resultsSection  = $('#results-section');

// Inputs
const urlInput  = $('#url-input');
const textInput = $('#text-input');
const generateBtn = $('#generate-btn');

// Progress
const progressTitle = $('#progress-title');
const steps = {
    scrape: $('#step-scrape'),
    script: $('#step-script'),
    audio:  $('#step-audio'),
    stitch: $('#step-stitch'),
};

// Player
const audioPlayer     = $('#audio-player');
const episodeTitle    = $('#episode-title');
const waveformBar     = $('#waveform-bar');
const waveformProgress = $('#waveform-progress');
const waveformHandle  = $('#waveform-handle');
const timeCurrent     = $('#time-current');
const timeTotal       = $('#time-total');
const btnPlay         = $('#btn-play');
const btnRewind       = $('#btn-rewind');
const btnForward      = $('#btn-forward');
const btnDownload     = $('#btn-download');
const iconPlay        = btnPlay.querySelector('.icon-play');
const iconPause       = btnPlay.querySelector('.icon-pause');

// Transcript
const transcriptBody = $('#transcript-body');

// Other
const btnNew      = $('#btn-new');
const errorToast  = $('#error-toast');
const errorMsg    = $('#error-message');
const errorClose  = $('#error-close');

// =====================================================================
// State
// =====================================================================

let currentTiming = [];   // Array of { index, speaker, text, start_s, end_s }
let currentAudioUrl = '';
let activeTab = 'url';    // 'url' or 'text'


// =====================================================================
// Tab Switching
// =====================================================================

$$('.tab-btn').forEach(btn => {
    btn.addEventListener('click', () => {
        const tab = btn.dataset.tab;
        activeTab = tab;

        $$('.tab-btn').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');

        $$('.tab-content').forEach(c => c.classList.remove('active'));
        $(`#content-${tab}`).classList.add('active');
    });
});


// =====================================================================
// Generate Podcast
// =====================================================================

generateBtn.addEventListener('click', handleGenerate);

async function handleGenerate() {
    const source = activeTab === 'url'
        ? urlInput.value.trim()
        : textInput.value.trim();

    if (!source) {
        showError(activeTab === 'url'
            ? 'Please enter a URL.'
            : 'Please paste some text.');
        return;
    }

    // Switch to progress view
    inputSection.classList.add('hidden');
    resultsSection.classList.add('hidden');
    progressSection.classList.remove('hidden');
    generateBtn.disabled = true;

    // Reset progress steps
    Object.values(steps).forEach(s => {
        s.classList.remove('active', 'done');
    });

    try {
        // Animate progress steps with simulated timing
        activateStep('scrape');
        progressTitle.textContent = 'Fetching article content...';

        // Make the actual API call
        const requestBody = {
            source: source,
            input_type: activeTab,
        };

        // Start the request
        const fetchPromise = fetch('/api/generate-podcast', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(requestBody),
        });

        // Simulate progress while waiting
        await sleep(800);
        completeStep('scrape');
        activateStep('script');
        progressTitle.textContent = 'Writing podcast script with AI...';

        await sleep(1200);
        completeStep('script');
        activateStep('audio');
        progressTitle.textContent = 'Generating speech with AI voices...';

        // Wait for the actual response
        const response = await fetchPromise;

        if (!response.ok) {
            const err = await response.json().catch(() => ({}));
            throw new Error(err.detail || `Server error (${response.status})`);
        }

        completeStep('audio');
        activateStep('stitch');
        progressTitle.textContent = 'Stitching final audio...';
        await sleep(500);
        completeStep('stitch');

        const data = await response.json();

        // Show results
        progressTitle.textContent = 'Done!';
        await sleep(400);
        showResults(data);

    } catch (err) {
        console.error('Generation failed:', err);
        showError(err.message || 'Something went wrong. Please try again.');
        // Go back to input
        progressSection.classList.add('hidden');
        inputSection.classList.remove('hidden');
    } finally {
        generateBtn.disabled = false;
    }
}


// =====================================================================
// Progress Helpers
// =====================================================================

function activateStep(key) {
    if (steps[key]) steps[key].classList.add('active');
}

function completeStep(key) {
    if (steps[key]) {
        steps[key].classList.remove('active');
        steps[key].classList.add('done');
    }
}

function sleep(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
}


// =====================================================================
// Show Results
// =====================================================================

function showResults(data) {
    progressSection.classList.add('hidden');
    resultsSection.classList.remove('hidden');

    // Set title
    episodeTitle.textContent = data.title || 'Untitled Episode';

    // Set audio source
    currentAudioUrl = data.audio_url;
    audioPlayer.src = data.audio_url;
    audioPlayer.load();

    // Store timing data
    currentTiming = data.timing || [];

    // Render transcript
    renderTranscript(data.dialogue, data.timing);

    // Reset player UI
    timeCurrent.textContent = '0:00';
    timeTotal.textContent = '0:00';
    waveformProgress.style.width = '0%';
    waveformHandle.style.left = '0%';
    showPlayIcon();
}


// =====================================================================
// Transcript Rendering
// =====================================================================

function renderTranscript(dialogue, timing) {
    transcriptBody.innerHTML = '';

    dialogue.forEach((line, i) => {
        const el = document.createElement('div');
        const speakerClass = line.speaker.toLowerCase() === 'host' ? 'host' : 'guest';
        el.className = `dialogue-line ${speakerClass}`;
        el.dataset.index = i;

        el.innerHTML = `
            <span class="speaker-tag ${speakerClass}">${line.speaker}</span>
            <span class="dialogue-text">${escapeHtml(line.text)}</span>
        `;

        // Click to seek
        el.addEventListener('click', () => {
            const t = timing[i];
            if (t && audioPlayer.duration) {
                audioPlayer.currentTime = t.start_s;
                if (audioPlayer.paused) {
                    audioPlayer.play();
                    showPauseIcon();
                }
            }
        });

        transcriptBody.appendChild(el);
    });
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}


// =====================================================================
// Audio Player Controls
// =====================================================================

// Play / Pause
btnPlay.addEventListener('click', () => {
    if (audioPlayer.paused) {
        audioPlayer.play();
        showPauseIcon();
    } else {
        audioPlayer.pause();
        showPlayIcon();
    }
});

// Rewind 10s
btnRewind.addEventListener('click', () => {
    audioPlayer.currentTime = Math.max(0, audioPlayer.currentTime - 10);
});

// Forward 10s
btnForward.addEventListener('click', () => {
    audioPlayer.currentTime = Math.min(audioPlayer.duration || 0, audioPlayer.currentTime + 10);
});

// Download
btnDownload.addEventListener('click', () => {
    if (currentAudioUrl) {
        const a = document.createElement('a');
        a.href = currentAudioUrl;
        a.download = 'readnext-podcast.mp3';
        a.click();
    }
});

function showPlayIcon() {
    iconPlay.classList.remove('hidden');
    iconPause.classList.add('hidden');
}

function showPauseIcon() {
    iconPlay.classList.add('hidden');
    iconPause.classList.remove('hidden');
}


// =====================================================================
// Waveform / Seek Bar
// =====================================================================

// Update progress bar as audio plays
audioPlayer.addEventListener('timeupdate', () => {
    if (!audioPlayer.duration) return;
    const pct = (audioPlayer.currentTime / audioPlayer.duration) * 100;
    waveformProgress.style.width = pct + '%';
    waveformHandle.style.left = pct + '%';
    timeCurrent.textContent = formatTime(audioPlayer.currentTime);

    // Sync transcript highlight
    updateActiveTranscriptLine(audioPlayer.currentTime);
});

audioPlayer.addEventListener('loadedmetadata', () => {
    timeTotal.textContent = formatTime(audioPlayer.duration);
});

audioPlayer.addEventListener('ended', () => {
    showPlayIcon();
    // Clear active transcript line
    $$('.dialogue-line.active').forEach(el => el.classList.remove('active'));
});

// Click to seek on waveform bar
waveformBar.addEventListener('click', (e) => {
    if (!audioPlayer.duration) return;
    const rect = waveformBar.getBoundingClientRect();
    const pct = (e.clientX - rect.left) / rect.width;
    audioPlayer.currentTime = pct * audioPlayer.duration;
});


// =====================================================================
// Transcript Sync
// =====================================================================

function updateActiveTranscriptLine(currentTime) {
    const lines = $$('.dialogue-line');

    lines.forEach((el, i) => {
        const t = currentTiming[i];
        if (!t) return;

        if (currentTime >= t.start_s && currentTime < t.end_s) {
            if (!el.classList.contains('active')) {
                // Remove active from all others
                lines.forEach(l => l.classList.remove('active'));
                el.classList.add('active');

                // Scroll into view smoothly
                el.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
            }
        }
    });
}


// =====================================================================
// Generate Another
// =====================================================================

btnNew.addEventListener('click', () => {
    resultsSection.classList.add('hidden');
    inputSection.classList.remove('hidden');
    audioPlayer.pause();
    audioPlayer.src = '';
    showPlayIcon();
});


// =====================================================================
// Error Toast
// =====================================================================

function showError(message) {
    errorMsg.textContent = message;
    errorToast.classList.remove('hidden');
    setTimeout(() => {
        errorToast.classList.add('hidden');
    }, 6000);
}

errorClose.addEventListener('click', () => {
    errorToast.classList.add('hidden');
});


// =====================================================================
// Utility
// =====================================================================

function formatTime(seconds) {
    if (!seconds || isNaN(seconds)) return '0:00';
    const m = Math.floor(seconds / 60);
    const s = Math.floor(seconds % 60);
    return `${m}:${s.toString().padStart(2, '0')}`;
}
