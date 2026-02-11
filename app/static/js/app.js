const API = '/api';

const form = document.getElementById('jobForm');
const submitBtn = document.getElementById('submitBtn');
const progressSection = document.getElementById('progressSection');
const progressBar = document.getElementById('progressBar');
const progressPct = document.getElementById('progressPct');
const resultsSection = document.getElementById('resultsSection');
const jobList = document.getElementById('jobList');
const failBanner = document.getElementById('failBanner');
const failMsg = document.getElementById('failMsg');

// Ordered pipeline steps
const STEPS = [
    'downloading',
    'enhancing',
    'fetching_stock',
    'generating_thumbnail',
    'compiling',
    'publishing',
    'cleanup',
];

// Toggle thumbnail prompt visibility
document.getElementById('genThumbnail').addEventListener('change', (e) => {
    document.getElementById('thumbPromptGroup').style.display = e.target.checked ? 'block' : 'none';
});

// Check config status on load
async function checkConfig() {
    try {
        const res = await fetch(`${API}/config/status`);
        const cfg = await res.json();

        setDot('pexelsDot', cfg.pexels);
        setDot('falDot', cfg.fal);
        setDot('telegramDot', cfg.telegram);
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

// Reset the step timeline to initial state
function resetTimeline() {
    document.querySelectorAll('.step-row').forEach(row => {
        row.classList.remove('active', 'done', 'failed');
        row.querySelector('.step-status').textContent = '';
    });
    progressBar.style.width = '0%';
    progressBar.classList.remove('failed');
    progressPct.textContent = '0%';
    progressPct.style.color = '';
    failBanner.classList.remove('active');
    failMsg.textContent = '';
}

// Update the timeline based on current step
function updateTimeline(currentStep, progress, status) {
    const currentIdx = STEPS.indexOf(currentStep);

    STEPS.forEach((step, i) => {
        const row = document.querySelector(`.step-row[data-step="${step}"]`);
        if (!row) return;

        row.classList.remove('active', 'done', 'failed');
        const statusEl = row.querySelector('.step-status');

        if (status === 'failed' && i === currentIdx) {
            row.classList.add('failed');
            statusEl.textContent = 'FAILED';
        } else if (i < currentIdx || (currentStep === 'done' && status === 'completed')) {
            row.classList.add('done');
            statusEl.textContent = 'Done';
        } else if (i === currentIdx && status !== 'failed') {
            row.classList.add('active');
            statusEl.textContent = progress + '%';
        } else {
            statusEl.textContent = '';
        }
    });

    // Progress bar
    progressBar.style.width = progress + '%';
    progressPct.textContent = progress + '%';

    if (status === 'failed') {
        progressBar.classList.add('failed');
        progressPct.style.color = 'var(--red)';
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
        stock_clip_count: parseInt(document.getElementById('clipCount').value) || 5,
        generate_thumbnail: document.getElementById('genThumbnail').checked,
        thumbnail_prompt: document.getElementById('thumbnailPrompt').value,
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
    resetTimeline();

    const poll = setInterval(async () => {
        try {
            const res = await fetch(`${API}/jobs/${jobId}`);
            const job = await res.json();

            updateTimeline(job.step, job.progress, job.status);

            if (job.status === 'completed' || job.status === 'failed') {
                clearInterval(poll);
                submitBtn.disabled = false;
                submitBtn.textContent = 'Convert & Publish';

                if (job.status === 'completed') {
                    showResults(job);
                } else {
                    failBanner.classList.add('active');
                    failMsg.textContent = job.error || 'An unknown error occurred.';
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

    if (job.thumbnail_path && !job.thumbnail_path.startsWith('Error')) {
        html += `<div class="result-item thumbnail-result">
            <span class="label">Thumbnail</span>
            <span class="value">
                <a href="/api/thumbnail/${job.id}" target="_blank">View</a>
            </span>
        </div>`;
        html += `<div class="thumbnail-preview">
            <img src="/api/thumbnail/${job.id}" alt="Generated thumbnail">
        </div>`;
    } else if (job.thumbnail_path) {
        html += `<div class="result-item">
            <span class="label">Thumbnail</span>
            <span class="value error">${job.thumbnail_path}</span>
        </div>`;
    }

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

        jobList.innerHTML = data.slice(0, 10).map(j => {
            const statusClass = j.status;
            const label = j.status === 'failed'
                ? `<span class="job-status failed">FAILED</span>`
                : `<span class="job-status ${statusClass}">${j.status}</span>`;
            return `
                <div class="job-item">
                    <span>${j.id}</span>
                    ${label}
                    <span>${j.progress}%</span>
                </div>`;
        }).join('');
    } catch (e) {
        console.error('Load jobs failed:', e);
    }
}

// Init
checkConfig();
loadJobs();
