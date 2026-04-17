/**
 * HAR viewer — renders step network requests from a HAR file.
 * Included in test_detail.html and view_executions.html.
 */

// Lazy-load screenshots when a .screenshots-details element is opened.
document.addEventListener('toggle', function (e) {
    const details = e.target;
    if (!details.classList.contains('screenshots-details') || !details.open) return;
    if (details.dataset.loaded) return;
    details.dataset.loaded = 'true';

    const gallery = details.querySelector('.screenshots-gallery');
    gallery.innerHTML = '<p class="gallery-loading">Loading\u2026</p>';

    fetch(`/api/artefacts/${details.dataset.artefactDir}/screenshots`)
        .then(r => r.json())
        .then(urls => {
            if (!urls.length) {
                gallery.innerHTML = '<p class="gallery-empty">No screenshots available.</p>';
                return;
            }
            gallery.innerHTML = urls.map((url, i) =>
                `<div class="screenshot-frame">
                    <span class="screenshot-label">${i + 1}</span>
                    <img src="${url}" loading="lazy" class="screenshot-img">
                </div>`
            ).join('');
        })
        .catch(() => {
            gallery.innerHTML = '<p class="gallery-empty">Failed to load screenshots.</p>';
        });
}, true);

// Fetch and render HAR when a .har-details element is opened.
// Uses event delegation so it works for dynamically-injected content too.
document.addEventListener('toggle', function (e) {
    const details = e.target;
    if (!details.classList.contains('har-details') || !details.open) return;
    if (details.dataset.loaded) return;
    details.dataset.loaded = 'true';

    const container = details.querySelector('.har-container');
    container.innerHTML = '<p class="har-loading">Loading\u2026</p>';

    fetch(details.dataset.harUrl)
        .then(r => { if (!r.ok) throw new Error('not found'); return r.json(); })
        .then(data => { container.innerHTML = renderHar(data); })
        .catch(() => { container.innerHTML = '<p class="har-empty">No HAR data available for this step.</p>'; });
}, true);

function renderHar(har) {
    const entries = (har.log && har.log.entries) || [];
    if (!entries.length) {
        return '<p class="har-empty">No network requests captured for this step.</p>';
    }

    const maxTime = Math.max(...entries.map(e => e.time || 0), 1);

    const rows = entries.map(e => {
        const url = (e.request && e.request.url) || '';
        const displayUrl = url.length > 70 ? '\u2026' + url.slice(-67) : url;
        const bodySize = (e.response && e.response.bodySize) || 0;
        const size = formatBytes(bodySize);
        const time = Math.round(e.time || 0);
        const t = e.timings || {};
        const dns     = Math.max(0, t.dns     || 0);
        const connect = Math.max(0, t.connect || 0);
        const wait    = Math.max(0, t.wait    || 0);
        const receive = Math.max(0, t.receive || 0);

        const pct = v => Math.min(100, Math.round((v / maxTime) * 100));

        return `<tr>
            <td class="har-url" title="${escHtml(url)}">${escHtml(displayUrl)}</td>
            <td class="har-size">${size}</td>
            <td class="har-time">${time}&nbsp;ms</td>
            <td class="har-timing">
                <div class="timing-bar">
                    <div class="t-dns"     style="width:${pct(dns)}%"     title="DNS ${Math.round(dns)} ms"></div>
                    <div class="t-connect" style="width:${pct(connect)}%" title="Connect ${Math.round(connect)} ms"></div>
                    <div class="t-wait"    style="width:${pct(wait)}%"    title="Wait (TTFB) ${Math.round(wait)} ms"></div>
                    <div class="t-receive" style="width:${pct(receive)}%" title="Receive ${Math.round(receive)} ms"></div>
                </div>
            </td>
        </tr>`;
    }).join('');

    return `
        <div class="har-legend">
            <span class="l-dns">DNS</span>
            <span class="l-connect">Connect</span>
            <span class="l-wait">Wait</span>
            <span class="l-receive">Receive</span>
        </div>
        <div class="har-table-wrap">
            <table class="har-table">
                <thead><tr>
                    <th>URL</th>
                    <th>Size</th>
                    <th>Time</th>
                    <th>Timing</th>
                </tr></thead>
                <tbody>${rows}</tbody>
            </table>
        </div>`;
}

function formatBytes(b) {
    if (b <= 0) return '\u2014';
    if (b < 1024) return b + ' B';
    if (b < 1048576) return (b / 1024).toFixed(1) + ' KB';
    return (b / 1048576).toFixed(1) + ' MB';
}

function escHtml(str) {
    const d = document.createElement('div');
    d.textContent = str;
    return d.innerHTML;
}

/**
 * Build the HTML for a list of step results.
 * artefactDir may be empty (older executions won't have HAR files).
 */
function renderStepResults(steps, artefactDir) {
    if (!steps || !steps.length) {
        return '<p class="no-steps">No step results available.</p>';
    }
    return steps.map(s => {
        const stepNum = String(s.step).padStart(3, '0');
        const harUrl  = artefactDir
            ? `/artefacts/${artefactDir}/hars/step_${stepNum}.har`
            : '';

        return `<div class="step-result step-result-${s.status}">
            <div class="step-result-header">
                <span class="step-number">Step ${s.step}</span>
                <span class="step-action">${s.action.toUpperCase()}</span>
                <span class="status-badge status-${s.status}">${s.status}</span>
            </div>
            <div class="step-result-message">${escHtml(s.message || '')}</div>
            ${harUrl ? `<details class="har-details" data-har-url="${harUrl}">
                <summary>Network requests</summary>
                <div class="har-container"></div>
            </details>` : ''}
        </div>`;
    }).join('');
}
