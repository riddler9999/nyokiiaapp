const API = '/api';

const form = document.getElementById('jobForm');
const submitBtn = document.getElementById('submitBtn');
const progressSection = document.getElementById('progressSection');
const progressBar = document.getElementById('progressBar');
const stepLabel = document.getElementById('stepLabel');
const resultsSection = document.getElementById('resultsSection');
const jobList = document.getElementById('jobList');

const STEP_LABELS = {
    downloading: 'Downloading Dhamma audio...',
    enhancing: 'Enhancing audio quality...',
    fetching_stock: 'Fetching Myanmar Buddhist videos from Pexels...',
    compiling: 'Compiling video with FFmpeg...',
    publishing: 'Publishing to platforms...',
    cleanup: 'Cleaning up temporary files...',
    done: 'Complete!',
};

// Check config status on load
async function checkConfig() {
    try {
        const res = await fetch(`${API}/config/status`);
        const cfg = await res.json();

        setDot('pexelsDot', cfg.pexels);
        setDot('telegramDot', cfg.telegram);
        setDot('youtubeDot', cfg.youtube);

        if (cfg.youtube_oauth_needed) {
            document.getElementById('youtubeAuthHint').style.display = 'inline';
        }
    } catch (e) {
        console.error('Config check failed:', e);
    }
}

function setDot(id, active) {
    const dot = document.getElementById(id);
    if (dot) {
        dot.classList.toggle('active', active);
        dot.classList.toggle('warn', !active);
    }
}

// Submit job
form.addEventListener('submit', async (e) => {
    e.preventDefault();
    submitBtn.disabled = true;
    submitBtn.textContent = 'Starting...';

    const data = {
        audio_url: document.getElementById('audioUrl').value,
        title: document.getElementById('title').value,
        description: document.getElementById('description').value,
        publish_telegram: document.getElementById('pubTelegram').checked,
        publish_youtube: document.getElementById('pubYoutube').checked,
        stock_clip_count: parseInt(document.getElementById('clipCount').value) || 5,
    };

    try {
        const res = await fetch(`${API}/jobs`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data),
        });
        const job = await res.json();
        pollJob(job.job_id);
    } catch (err) {
        alert('Failed to start job: ' + err.message);
        submitBtn.disabled = false;
        submitBtn.textContent = 'Convert & Publish';
    }
});

async function pollJob(jobId) {
    progressSection.classList.add('active');
    resultsSection.classList.remove('active');

    const poll = setInterval(async () => {
        try {
            const res = await fetch(`${API}/jobs/${jobId}`);
            const job = await res.json();

            progressBar.style.width = job.progress + '%';
            stepLabel.innerHTML = `<span class="step-name">${STEP_LABELS[job.step] || job.step}</span>`;

            if (job.status === 'completed' || job.status === 'failed') {
                clearInterval(poll);
                submitBtn.disabled = false;
                submitBtn.textContent = 'Convert & Publish';

                if (job.status === 'completed') {
                    showResults(job);
                } else {
                    progressSection.classList.remove('active');
                    alert('Job failed: ' + job.error);
                }
                loadJobs();
            }
        } catch (e) {
            console.error('Poll error:', e);
        }
    }, 2000);
}

function showResults(job) {
    resultsSection.classList.add('active');
    let html = '';

    html += `<div class="result-item">
        <span class="label">Status</span>
        <span class="value success">Completed</span>
    </div>`;

    if (job.output_path) {
        html += `<div class="result-item">
            <span class="label">Video</span>
            <span class="value"><a href="/api/download/${job.id}" target="_blank">Download MP4</a></span>
        </div>`;
    }

    if (job.telegram_result && !job.telegram_result.startsWith('Error')) {
        html += `<div class="result-item">
            <span class="label">Telegram</span>
            <span class="value success">${job.telegram_result}</span>
        </div>`;
    } else if (job.telegram_result) {
        html += `<div class="result-item">
            <span class="label">Telegram</span>
            <span class="value error">${job.telegram_result}</span>
        </div>`;
    }

    if (job.youtube_url && !job.youtube_url.startsWith('Error')) {
        html += `<div class="result-item">
            <span class="label">YouTube</span>
            <span class="value"><a href="${job.youtube_url}" target="_blank">${job.youtube_url}</a></span>
        </div>`;
    } else if (job.youtube_url) {
        html += `<div class="result-item">
            <span class="label">YouTube</span>
            <span class="value error">${job.youtube_url}</span>
        </div>`;
    }

    document.getElementById('resultsList').innerHTML = html;
}

async function loadJobs() {
    try {
        const res = await fetch(`${API}/jobs`);
        const data = await res.json();

        if (!data.length) {
            jobList.innerHTML = '<p style="color:var(--gray);font-size:13px;text-align:center;padding:12px 0;">No jobs yet</p>';
            return;
        }

        jobList.innerHTML = data.slice(0, 10).map(j => `
            <div class="job-item">
                <span>${j.id}</span>
                <span class="job-status ${j.status}">${j.status}</span>
                <span>${j.progress}%</span>
            </div>
        `).join('');
    } catch (e) {
        console.error('Load jobs failed:', e);
    }
}

// YouTube auth
async function authorizeYouTube() {
    try {
        const res = await fetch(`${API}/youtube/auth`);
        const data = await res.json();
        if (data.auth_url) {
            window.open(data.auth_url, '_blank');
        } else {
            alert(data.error || 'YouTube auth not available');
        }
    } catch (e) {
        alert('YouTube auth failed: ' + e.message);
    }
}

// Init
checkConfig();
loadJobs();
