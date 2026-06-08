// ============================================================
// Dilli Report — Frontend
// ============================================================

const API = window.location.origin;
let map, circleLayerGroup, constituenciesData = [];
let selectedConstituency = null;
let uploadedFiles = [];
let currentView = 'map';
let currentPage = 0;
const PAGE_SIZE = 20;
let allCategories = [], allWards = [];
// Upvote dedup: track which issues this browser session has upvoted
let upvotedIssues = new Set(JSON.parse(localStorage.getItem('dcw_upvoted') || '[]'));

// ============================================================
// INIT
// ============================================================
document.addEventListener('DOMContentLoaded', async () => {
    if (typeof L === 'undefined') {
        document.body.innerHTML = '<p style="padding:20px;color:red">Map library failed to load. Check internet.</p>';
        return;
    }
    initMap();
    await Promise.all([loadConstituencies(), loadCategories(), loadWards()]);
    setupEventListeners();
    loadStats();
    setInterval(loadStats, 60000);       // Poll stats every 60s
    setInterval(loadConstituencies, 120000); // Poll constituencies every 2min
    renderPhotoSlots(); // initial slot
});

// ============================================================
// MAP
// ============================================================
function initMap() {
    map = L.map('map', { zoomControl: false, attributionControl: false })
        .setView([28.65, 77.15], 11);
    L.control.zoom({ position: 'bottomright' }).addTo(map);
    L.tileLayer('https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png', {
        attribution: '&copy; OSM &copy; CARTO', maxZoom: 19
    }).addTo(map);
    circleLayerGroup = L.layerGroup().addTo(map);
    map.on('click', (e) => {
        if (e.originalEvent.target === map.getContainer()) deselectConstituency();
    });
}

async function loadConstituencies() {
    try {
        const res = await fetch(`${API}/api/constituencies`);
        constituenciesData = await res.json();
        renderCircles();
    } catch (err) { console.error('Load constituencies:', err); }
}

function renderCircles() {
    circleLayerGroup.clearLayers();
    constituenciesData.forEach(c => {
        if (!c.latitude || !c.longitude) return;
        const active = c.active_count;
        const radius = Math.min(14 + active * 2.5, 50);
        const color = active > 0 ? '#d93025' : '#34a853';
        const fillOpacity = active > 0 ? 0.75 : 0.4;

        const circle = L.circleMarker([c.latitude, c.longitude], {
            radius, fillColor: color, color: '#ffffff', weight: 2, fillOpacity,
        });
        if (active > 0) {
            circle.bindTooltip(`<b>${c.name}</b><br>${active} active issues`, {
                direction: 'top', offset: [0, -radius - 5], permanent: false,
            });
        }
        circle.on('click', (e) => { L.DomEvent.stopPropagation(e); selectConstituency(c); });
        circle.on('mouseover', function () { this.setStyle({ weight: 3, fillOpacity: .9 }); this.bringToFront(); });
        circle.on('mouseout', function () {
            if (selectedConstituency && selectedConstituency.id === c.id) return;
            this.setStyle({ weight: 2, fillOpacity });
        });
        circleLayerGroup.addLayer(circle);
    });
}

// ============================================================
// CONSTITUENCY CARD
// ============================================================
async function selectConstituency(c) {
    selectedConstituency = c;
    document.getElementById('info-card').classList.remove('hidden');
    document.getElementById('card-name').textContent = c.name;
    document.getElementById('card-mla').textContent = c.mla || 'N/A';
    document.getElementById('card-contact').textContent = c.contact_number || 'N/A';
    document.getElementById('card-email').textContent = c.email || 'N/A';
    document.getElementById('card-reported').textContent = c.issue_count;
    document.getElementById('card-resolved').textContent = c.resolved_count;
    document.getElementById('card-active').textContent = c.active_count;

    if (c.avg_resolution_hours) {
        document.getElementById('card-response-time').textContent = `~${formatHours(c.avg_resolution_hours)} avg`;
        document.getElementById('card-response-row').style.display = 'flex';
    } else {
        document.getElementById('card-response-row').style.display = 'none';
    }

    const badge = document.getElementById('card-party');
    badge.textContent = c.party || ''; badge.style.backgroundColor = partyColor(c.party);
    badge.style.display = c.party ? 'inline-block' : 'none';

    document.getElementById('card-report-btn').onclick = () => openReportModal(c);
    document.getElementById('card-email-btn').onclick = () => emailMLA(c);
    document.getElementById('card-watch-btn').onclick = () => openSubscribeModal(c);

    document.getElementById('card-ward-badge').classList.add('hidden'); // updated per-issue

    await loadConstituencyIssues(c.id);

    // Highlight
    circleLayerGroup.eachLayer(layer => {
        const ll = layer.getLatLng();
        if (Math.abs(ll.lat - c.latitude) < 0.001 && Math.abs(ll.lng - c.longitude) < 0.001) {
            layer.setStyle({ weight: 4, color: '#1a73e8', fillOpacity: .95 }); layer.bringToFront();
        }
    });
    document.getElementById('info-card').scrollIntoView({ behavior: 'smooth', block: 'nearest' });
}

function deselectConstituency() {
    selectedConstituency = null;
    document.getElementById('info-card').classList.add('hidden');
    renderCircles();
}

async function loadConstituencyIssues(constId) {
    const container = document.getElementById('card-issues-list');
    container.innerHTML = '';
    try {
        const res = await fetch(`${API}/api/issues?constituency_id=${constId}&limit=10`);
        const data = await res.json();
        const issues = data.issues || [];
        if (issues.length === 0) {
            container.innerHTML = '<p style="padding:12px 16px;font-size:.76rem;color:var(--gray-600)">No issues yet.</p>';
            return;
        }
        container.innerHTML = issues.map(i => issueItemHTML(i)).join('');
        bindUpvoteButtons(container);
        bindEmailMCDButtons(container);
    } catch (err) { container.innerHTML = ''; }
}

function emailMLA(c) {
    if (!c.email || c.email === 'N/A') { showToast('Email not available'); return; }
    const subject = encodeURIComponent(`Civic Issue: ${c.name}`);
    const body = encodeURIComponent(`Dear ${c.mla},\n\nI would like to report a civic issue in ${c.name} constituency.\n\nDetails:\n\n\nThank you.`);
    window.open(`mailto:${c.email}?subject=${subject}&body=${body}`, '_blank');
}

// ============================================================
// PAGINATED LIST VIEW
// ============================================================
async function loadListView(page = 0) {
    currentPage = page;
    const container = document.getElementById('issues-list');
    container.innerHTML = '<p style="text-align:center;color:var(--gray-600);padding:20px;">Loading...</p>';

    const params = new URLSearchParams();
    params.set('offset', page * PAGE_SIZE);
    params.set('limit', PAGE_SIZE);
    const cat = document.getElementById('filter-category').value;
    const ward = document.getElementById('filter-ward').value;
    const status = document.getElementById('filter-status').value;
    const sort = document.getElementById('filter-sort').value;
    if (cat !== 'All') params.set('category', cat);
    if (ward) params.set('ward', ward);
    if (status !== 'All') params.set('status', status);
    if (sort !== 'newest') params.set('sort', sort);

    try {
        const res = await fetch(`${API}/api/issues?${params}`);
        const data = await res.json();
        const issues = data.issues || [];
        const total = data.total || 0;

        if (issues.length === 0) {
            container.innerHTML = '<p style="text-align:center;color:var(--gray-600);padding:40px;">No issues found.</p>';
        } else {
            container.innerHTML = issues.map(i => {
                const alreadyUpvoted = upvotedIssues.has(i.id);
                return `
                <div class="list-issue">
                    <div class="list-header">
                        <span class="list-constituency">${escapeHtml(i.constituency_id)} ${i.ward ? '· ' + escapeHtml(i.ward) : ''}</span>
                        <span class="list-category${i.resolved ? ' resolved-tag' : ''}">${i.resolved ? '✅ Resolved' : escapeHtml(i.issue_category || 'General')}</span>
                    </div>
                    <div class="list-summary">${escapeHtml(i.issue_summary)}</div>
                    <div class="list-meta">
                        <span>👤 ${escapeHtml(i.complainant_name || 'Anonymous')}</span>
                        <span>🕐 ${new Date(i.created_at).toLocaleDateString()}</span>
                        <span>👍 ${i.upvotes || 0}</span>
                        ${i.upvotes >= 3 ? '<span class="verified-badge">✓ Verified</span>' : ''}
                    </div>
                    ${renderBeforeAfter(i)}
                    ${renderImages(i)}
                    <div class="list-actions">
                        <button class="upvote-btn${alreadyUpvoted ? ' upvoted' : ''}" data-id="${i.id}">👍 ${i.upvotes || 0}</button>
                        <button class="email-mcd-btn" data-id="${i.id}" data-constituency="${i.constituency_id}" data-summary="${escapeHtml(i.issue_summary).replace(/"/g, '&quot;')}" data-images="${escapeHtml(i.images || '[]')}">📧 Email MCD</button>
                        ${!i.resolved ? `<button class="resolve-btn" data-id="${i.id}">✅ Resolve</button>` : ''}
                    </div>
                </div>`}).join('');
            bindUpvoteButtons(container);
            bindResolveButtons(container);
            bindEmailMCDButtons(container);
        }

        renderPagination(total, page);
    } catch (err) {
        container.innerHTML = '<p style="text-align:center;color:var(--red);padding:20px;">Failed to load.</p>';
    }
}

function renderImages(issue) {
    let html = '<div class="list-images">';
    try {
        const imgs = typeof issue.images === 'string' ? JSON.parse(issue.images) : (issue.images || []);
        imgs.forEach(fn => { html += `<img src="${API}/uploads/${fn}" alt="Issue photo" loading="lazy">`; });
    } catch (e) { /* skip */ }
    if (issue.resolution_photo) {
        html += `<img src="${API}/uploads/${issue.resolution_photo}" alt="Resolution" class="resolution-img" loading="lazy">`;
    }
    html += '</div>';
    return html;
}

function renderBeforeAfter(issue) {
    let html = '';
    try {
        const imgs = typeof issue.images === 'string' ? JSON.parse(issue.images) : (issue.images || []);
        const before = imgs[0];
        const after = issue.resolution_photo;
        if (before && after) {
            html += `<div class="before-after-inline">
                <span class="before-label">Before → After</span>
                <img src="${API}/uploads/${before}" alt="Before">
                <span>→</span>
                <img src="${API}/uploads/${after}" alt="After">
            </div>`;
        }
    } catch (e) { /* skip */ }
    return html;
}

function renderPagination(total, page) {
    const totalPages = Math.ceil(total / PAGE_SIZE);
    const pag = document.getElementById('pagination');
    if (totalPages <= 1) { pag.classList.add('hidden'); return; }
    pag.classList.remove('hidden');
    pag.innerHTML = `
        <button ${page === 0 ? 'disabled' : ''} onclick="loadListView(${page - 1})">← Previous</button>
        <span class="page-info">Page ${page + 1} of ${totalPages} (${total} issues)</span>
        <button ${page >= totalPages - 1 ? 'disabled' : ''} onclick="loadListView(${page + 1})">Next →</button>
    `;
}

function issueItemHTML(i) {
    const alreadyUpvoted = upvotedIssues.has(i.id);
    return `
        <div class="issue-item">
            <span class="cat-tag${i.resolved ? ' resolved-tag' : ''}">${i.resolved ? '✓ Done' : escapeHtml(i.issue_category || 'General')}</span>
            ${i.upvotes >= 3 ? '<span class="verified-tag">✓ Verified</span>' : ''}
            <span style="flex:1;min-width:0;">${escapeHtml(i.issue_summary).substring(0, 90)}${(i.issue_summary||'').length > 90 ? '...' : ''}</span>
            <button class="upvote-btn${alreadyUpvoted ? ' upvoted' : ''}" data-id="${i.id}">👍 ${i.upvotes || 0}</button>
            <button class="email-mcd-btn" data-id="${i.id}" data-constituency="${i.constituency_id}" data-summary="${escapeHtml(i.issue_summary).replace(/"/g, '&quot;')}">📧</button>
        </div>`;
}

// ============================================================
// UPVOTE
// ============================================================
function bindUpvoteButtons(container) {
    container.querySelectorAll('.upvote-btn').forEach(btn => {
        btn.addEventListener('click', async (e) => {
            e.stopPropagation();
            const id = parseInt(btn.dataset.id);
            if (upvotedIssues.has(id)) {
                showToast('You already upvoted this issue');
                return;
            }
            try {
                const res = await fetch(`${API}/api/issues/${id}/upvote`, { method: 'POST' });
                const data = await res.json();
                upvotedIssues.add(id);
                localStorage.setItem('dcw_upvoted', JSON.stringify([...upvotedIssues]));
                btn.textContent = `👍 ${data.upvotes}`;
                btn.classList.add('upvoted');
                if (data.verified) showToast('✓ Issue verified by community!');
                loadStats();
            } catch { showToast('Failed to upvote'); }
        });
    });
}

// ============================================================
// RESOLVE (with before/after photo)
// ============================================================
let resolveTargetId = null;

function bindResolveButtons(container) {
    container.querySelectorAll('.resolve-btn').forEach(btn => {
        btn.addEventListener('click', (e) => {
            e.stopPropagation();
            resolveTargetId = btn.dataset.id;
            openResolveModal();
        });
    });
}

function bindEmailMCDButtons(container) {
    container.querySelectorAll('.email-mcd-btn').forEach(btn => {
        btn.addEventListener('click', async (e) => {
            e.stopPropagation();
            const constId = btn.dataset.constituency;
            const summary = btn.dataset.summary || '';
            const images = JSON.parse(btn.dataset.images || '[]');

            try {
                const res = await fetch(`${API}/api/mcd-email?constituency_id=${constId}`);
                const data = await res.json();

                const to = data.mcd_email || '';
                const cc = data.mla_email || '';
                const subject = encodeURIComponent(`Civic Complaint: ${summary.substring(0, 80)}`);
                let body = `To the Municipal Corporation of Delhi,\n\n`;
                body += `I wish to report the following civic issue:\n\n`;
                body += `"${summary}"\n\n`;
                body += `Location: ${data.mcd_zone || 'Delhi'} zone, Constituency: ${constId}\n`;
                if (images.length > 0) {
                    body += `\nPhotos attached:\n`;
                    images.forEach(fn => { body += `${API}/uploads/${fn}\n`; });
                }
                body += `\n\n---\nSent via Delhi Civic Watch`;
                if (cc) body += `\nMLA ${data.mla_name || ''} in CC`;

                window.location.href = `mailto:${to}?cc=${cc}&subject=${subject}&body=${encodeURIComponent(body)}`;
            } catch {
                showToast('Could not load MCD email');
            }
        });
    });
}

function openResolveModal() {
    document.getElementById('resolve-modal').classList.remove('hidden');
    document.body.style.overflow = 'hidden';
    // Reset photo
    const slot = document.getElementById('resolve-photo-slot');
    slot.innerHTML = `
        <label class="photo-slot add-slot">
            <input type="file" id="resolve-photo-input" accept="image/*" capture="environment" hidden>
            <span class="plus">+</span>
            <span class="photo-hint">After Photo</span>
        </label>`;
    document.getElementById('resolve-photo-input').addEventListener('change', handleResolvePhoto);
}

function closeResolveModal() {
    document.getElementById('resolve-modal').classList.add('hidden');
    document.body.style.overflow = '';
    resolveTargetId = null;
}

function handleResolvePhoto(e) {
    const file = e.target.files[0];
    if (!file) return;
    const slot = document.getElementById('resolve-photo-slot');
    const url = URL.createObjectURL(file);
    slot.innerHTML = `<div class="photo-slot"><img src="${url}" alt="After"></div>`;
}

async function handleResolveSubmit(e) {
    e.preventDefault();
    if (!resolveTargetId) return;
    const photoInput = document.getElementById('resolve-photo-input');
    if (!photoInput || !photoInput.files || !photoInput.files[0]) {
        showToast('⚠️ Please upload an "after" photo as proof of resolution');
        return;
    }
    const formData = new FormData();
    formData.append('resolution_photo', photoInput.files[0]);
    try {
        const res = await fetch(`${API}/api/issues/${resolveTargetId}/resolve`, { method: 'POST', body: formData });
        if (!res.ok) throw new Error('Failed');
        closeResolveModal();
        showToast('✅ Marked as resolved!');
        loadListView(currentPage);
        loadConstituencies();
        loadStats();
        if (selectedConstituency) loadConstituencyIssues(selectedConstituency.id);
    } catch { showToast('Failed to mark as resolved'); }
}

// ============================================================
// SUBSCRIBE
// ============================================================
function openSubscribeModal(c) {
    document.getElementById('subscribe-modal').classList.remove('hidden');
    document.body.style.overflow = 'hidden';
    const botLink = document.getElementById('telegram-bot-link');
    botLink.href = 'https://t.me/DelhiCivicWatchBot';

    // Email form — disabled until sender domain is verified
    // document.getElementById('subscribe-email-form').onsubmit = async (e) => {
    //     e.preventDefault();
    //     const email = document.getElementById('subscribe-email').value.trim();
    //     if (!email) return;
    //     try {
    //         const res = await fetch(`${API}/api/subscribe`, {
    //             method: 'POST', headers: { 'Content-Type': 'application/json' },
    //             body: JSON.stringify({ email, constituency_id: c ? c.id : null }),
    //         });
    //         const data = await res.json();
    //         closeSubscribeModal();
    //         showToast('📧 ' + data.message);
    //     } catch { showToast('Subscription failed'); }
    // };
}

function closeSubscribeModal() {
    document.getElementById('subscribe-modal').classList.add('hidden');
    document.body.style.overflow = '';
}

// ============================================================
// REPORT MODAL
// ============================================================
function openReportModal(preselected) {
    document.getElementById('report-modal').classList.remove('hidden');
    document.body.style.overflow = 'hidden';

    const sel = document.getElementById('form-constituency');
    sel.innerHTML = '<option value="">Select your area...</option>' +
        constituenciesData.map(c => `<option value="${c.id}" ${preselected && c.id === preselected.id ? 'selected' : ''}>${c.name}</option>`).join('');

    // Reset form-ward and load wards for preselected constituency (or clear)
    const formWard = document.getElementById('form-ward');
    formWard.innerHTML = '<option value="">Select constituency first</option>';

    // Reload wards when constituency changes
    sel.onchange = function () {
        if (this.value) {
            loadWardsForConstituency(this.value);
        } else {
            formWard.innerHTML = '<option value="">Select constituency first</option>';
        }
    };

    // Load wards if preselected
    if (preselected) {
        loadWardsForConstituency(preselected.id);
    }

    document.getElementById('form-category').innerHTML = allCategories.map(cat => `<option value="${cat}">${cat}</option>`).join('');
    document.getElementById('form-description').value = '';
    document.getElementById('form-name').value = '';
    document.getElementById('form-contact').value = '';
    document.getElementById('form-lat').value = '';
    document.getElementById('form-lng').value = '';
    document.getElementById('location-status').textContent = '';
    uploadedFiles = [];
    renderPhotoSlots();
}

function closeReportModal() {
    document.getElementById('report-modal').classList.add('hidden');
    document.body.style.overflow = '';
}

async function handleFormSubmit(e) {
    e.preventDefault();

    // Quick storage check before submitting
    const reportBtn = document.getElementById('form-submit');
    try {
        const hr = await fetch(`${API}/api/health`);
        const health = await hr.json();
        if (!health.accepting_reports) {
            showStorageBanner(health.storage);
            reportBtn.disabled = false;
            showToast('⚠️ Reports temporarily paused — storage is full. Admin has been notified.');
            return;
        }
    } catch { /* proceed anyway — server check will catch it */ }

    const constituencyId = document.getElementById('form-constituency').value;
    const ward = document.getElementById('form-ward').value;
    const category = document.getElementById('form-category').value;
    const description = document.getElementById('form-description').value.trim();
    const name = document.getElementById('form-name').value.trim();
    const contact = document.getElementById('form-contact').value.trim();
    const lat = document.getElementById('form-lat').value;
    const lng = document.getElementById('form-lng').value;

    if (!constituencyId || !description) { showToast('Select area and describe the issue.'); return; }
    if (description.length < 5) { showToast('Please provide more detail.'); return; }

    const btn = document.getElementById('form-submit');
    btn.disabled = true; btn.textContent = 'Submitting...';

    const constData = constituenciesData.find(c => c.id === constituencyId);
    try {
        const formData = new FormData();
        formData.append('constituency_id', constituencyId);
        formData.append('issue_summary', description);
        formData.append('issue_category', category);
        if (ward) formData.append('ward', ward);
        formData.append('mla_name', constData ? constData.mla : '');
        if (name) formData.append('complainant_name', name);
        if (contact) formData.append('contact_number', contact);
        if (lat) formData.append('latitude', lat);
        if (lng) formData.append('longitude', lng);
        uploadedFiles.forEach(f => formData.append('images', f));

        const res = await fetch(`${API}/api/issues`, { method: 'POST', body: formData });
        if (!res.ok) throw new Error('Failed');
        closeReportModal();
        showToast('✅ Reported! Thank you.');
        await loadConstituencies(); loadStats();
        if (selectedConstituency) loadConstituencyIssues(selectedConstituency.id);
    } catch { showToast('❌ Failed. Try again.'); }
    finally { btn.disabled = false; btn.textContent = '🚀 Submit Report'; }
}

// ============================================================
// PHOTO UPLOAD
// ============================================================
function handlePhotoInput(e) {
    const files = Array.from(e.target.files);
    files.forEach(f => {
        if (uploadedFiles.length >= 3) { showToast('Max 3 photos'); return; }
        if (!f.type.startsWith('image/')) return;
        uploadedFiles.push(f);
    });
    renderPhotoSlots();
    e.target.value = '';
}

function removePhoto(index) { uploadedFiles.splice(index, 1); renderPhotoSlots(); }

function renderPhotoSlots() {
    const container = document.getElementById('photo-slots');
    let html = '';
    uploadedFiles.forEach((f, i) => {
        const url = URL.createObjectURL(f);
        html += `<div class="photo-slot"><img src="${url}" alt="Photo ${i+1}"><button type="button" class="remove-photo" onclick="removePhoto(${i})">&times;</button></div>`;
    });
    if (uploadedFiles.length < 3) {
        html += `<label class="photo-slot add-slot"><input type="file" id="photo-input" accept="image/*" capture="environment" multiple hidden><span class="plus">+</span><span class="photo-hint">Add Photo</span></label>`;
    }
    container.innerHTML = html;
    const input = document.getElementById('photo-input');
    if (input) input.addEventListener('change', handlePhotoInput);
}

// ============================================================
// LOCATION (with map picker fallback for iOS)
// ============================================================
let pickerMap = null;
let pickerMarker = null;

function detectLocation() {
    const statusEl = document.getElementById('location-status');
    if (!navigator.geolocation) {
        statusEl.textContent = 'Geolocation not supported. Use Pick on Map below.';
        statusEl.style.color = 'var(--orange)';
        return;
    }
    statusEl.textContent = 'Detecting...';
    statusEl.style.color = 'var(--gray-600)';

    navigator.geolocation.getCurrentPosition(
        pos => {
            setLocation(pos.coords.latitude, pos.coords.longitude);
        },
        err => {
            let msg = 'Could not detect';
            if (err.code === 1) msg = 'Location permission denied. Tap "Pick on Map" below.';
            else if (err.code === 2) msg = 'Location unavailable. Try "Pick on Map".';
            else if (err.code === 3) msg = 'Location timed out. Try again or use Pick on Map.';
            statusEl.textContent = msg;
            statusEl.style.color = 'var(--orange)';
            // Auto-show map picker on permission denial (common on iOS non-HTTPS)
            if (err.code === 1) toggleMapPicker();
        },
        { enableHighAccuracy: true, timeout: 8000, maximumAge: 300000 }
    );
}

function setLocation(lat, lng) {
    document.getElementById('form-lat').value = lat;
    document.getElementById('form-lng').value = lng;
    const statusEl = document.getElementById('location-status');
    statusEl.textContent = `📍 ${lat.toFixed(4)}, ${lng.toFixed(4)}`;
    statusEl.style.color = 'var(--green)';
}

function toggleMapPicker() {
    const pickerDiv = document.getElementById('location-picker-map');
    const isHidden = pickerDiv.classList.contains('hidden');

    if (isHidden) {
        pickerDiv.classList.remove('hidden');
        // Initialize mini Leaflet map for picking
        if (!pickerMap) {
            pickerMap = L.map('location-picker-map', {
                zoomControl: false, attributionControl: false
            }).setView([28.65, 77.15], 11);
            L.tileLayer('https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png', {
                maxZoom: 19
            }).addTo(pickerMap);

            pickerMarker = L.marker([28.65, 77.15], { draggable: true }).addTo(pickerMap);
            pickerMarker.bindPopup('Drag me or tap the map').openPopup();

            pickerMap.on('click', function (e) {
                pickerMarker.setLatLng(e.latlng);
                setLocation(e.latlng.lat, e.latlng.lng);
            });

            pickerMarker.on('dragend', function () {
                const pos = pickerMarker.getLatLng();
                setLocation(pos.lat, pos.lng);
            });
        }
        setTimeout(() => pickerMap.invalidateSize(), 200);
        // If we already have coords, center there
        const lat = parseFloat(document.getElementById('form-lat').value);
        const lng = parseFloat(document.getElementById('form-lng').value);
        if (lat && lng) {
            pickerMap.setView([lat, lng], 15);
            pickerMarker.setLatLng([lat, lng]);
        }
        document.getElementById('pick-on-map-btn').textContent = '🔼 Hide Map';
    } else {
        pickerDiv.classList.add('hidden');
        document.getElementById('pick-on-map-btn').textContent = '🗺️ Pick on Map';
    }
}

// ============================================================
// STATS
// ============================================================
async function loadStats() {
    try {
        const res = await fetch(`${API}/api/stats`);
        const s = await res.json();
        document.getElementById('stat-active').textContent = s.total_active;
        document.getElementById('stat-total').textContent = s.total_reports;
        document.getElementById('stat-resolved').textContent = s.total_resolved;
        document.getElementById('stat-upvotes').textContent = s.total_upvotes;
    } catch { /* silent */ }
}

function showStorageBanner(storage) {
    const banner = document.getElementById('storage-banner');
    const fab = document.getElementById('report-fab');

    if (storage.status === 'critical') {
        banner.className = 'storage-banner critical';
        banner.innerHTML = `⚠️ ${storage.message || 'Reports paused — storage full. Admin is working on it.'} <small>(${storage.disk.pct_used}% used · ${storage.disk.free_gb}GB free)</small>`;
        banner.classList.remove('hidden');
        fab.disabled = true;
        fab.textContent = '⏸️ Paused';
        fab.style.opacity = '0.6';
    } else if (storage.status === 'warning') {
        banner.className = 'storage-banner warning';
        banner.innerHTML = `⚡ ${storage.message || 'Storage running low.'} <small>(${storage.disk.pct_used}% used · ${storage.disk.free_gb}GB free)</small>`;
        banner.classList.remove('hidden');
        fab.disabled = false;
        fab.textContent = '✏️ Report';
        fab.style.opacity = '1';
    }
}

async function loadCategories() {
    try {
        const res = await fetch(`${API}/api/categories`);
        allCategories = await res.json();
        document.getElementById('form-category').innerHTML = allCategories.map(c => `<option value="${c}">${c}</option>`).join('');
        document.getElementById('filter-category').innerHTML = '<option value="All">All Categories</option>' + allCategories.map(c => `<option value="${c}">${c}</option>`).join('');
    } catch { /* silent */ }
}

async function loadWards() {
    // Load all 250 wards on init for the filter bar
    try {
        const res = await fetch(`${API}/api/wards`);
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        allWards = await res.json();
        const filterWard = document.getElementById('filter-ward');
        if (filterWard) filterWard.innerHTML = '<option value="">All Wards</option>' + allWards.map(w => `<option value="${w}">${w}</option>`).join('');
    } catch (err) {
        console.warn('Wards failed:', err);
        setTimeout(loadWards, 2000);
    }
}

async function loadWardsForConstituency(constituencyId) {
    // Reload ward dropdown for a specific constituency in the report form
    const formWard = document.getElementById('form-ward');
    if (!formWard) return;
    formWard.innerHTML = '<option value="">Loading wards...</option>';
    try {
        const res = await fetch(`${API}/api/wards?constituency_id=${constituencyId}`);
        if (!res.ok) throw new Error('Failed');
        const wards = await res.json();
        formWard.innerHTML = '<option value="">Select ward (optional)</option>' +
            wards.map(w => `<option value="${w}">${w}</option>`).join('');
    } catch {
        formWard.innerHTML = '<option value="">Select ward (optional)</option>';
    }
}

// ============================================================
// LEADERBOARD
// ============================================================
async function loadLeaderboard() {
    const container = document.getElementById('leaderboard-table');
    container.innerHTML = '<p style="text-align:center;color:var(--gray-600);padding:20px;">Loading...</p>';
    try {
        const res = await fetch(`${API}/api/constituencies/leaderboard`);
        const data = await res.json();
        if (data.length === 0) {
            container.innerHTML = '<p style="text-align:center;padding:20px;">No data yet.</p>';
            return;
        }
        const rows = data.map(lb => {
            let rankIcon = lb.rank;
            if (lb.rank === 1) rankIcon = '🥇';
            else if (lb.rank === 2) rankIcon = '🥈';
            else if (lb.rank === 3) rankIcon = '🥉';
            let scoreClass = 'score-good';
            if (lb.resolution_rate < 30) scoreClass = 'score-bad';
            else if (lb.resolution_rate < 60) scoreClass = 'score-ok';
            return `<tr>
                <td class="rank">${rankIcon}</td>
                <td class="mla-cell">${escapeHtml(lb.name)}</td>
                <td>${escapeHtml(lb.mla)} <span style="font-size:.65rem;color:${partyColor(lb.party)}">${lb.party}</span></td>
                <td>${lb.active} active</td>
                <td class="${scoreClass}">${lb.resolution_rate}%</td>
                <td>${lb.avg_resolution_hours ? formatHours(lb.avg_resolution_hours) : '—'}</td>
            </tr>`;
        }).join('');
        container.innerHTML = `<table class="lb-table">
            <thead><tr><th>#</th><th>Constituency</th><th>MLA</th><th>Active</th><th>Resolved</th><th>Avg Time</th></tr></thead>
            <tbody>${rows}</tbody></table>`;
    } catch { container.innerHTML = '<p style="text-align:center;color:var(--red);padding:20px;">Failed to load.</p>'; }
}

// ============================================================
// DIGEST
// ============================================================
async function loadDigest() {
    const container = document.getElementById('digest-table');
    container.innerHTML = '<p style="text-align:center;color:var(--gray-600);padding:20px;">Loading...</p>';
    try {
        const res = await fetch(`${API}/api/digest`);
        const d = await res.json();
        document.getElementById('digest-dates').textContent = `${d.week_start} → ${d.week_end}`;
        if (d.total_new === 0) {
            container.innerHTML = '<p style="text-align:center;padding:20px;">No activity this week.</p>';
            return;
        }
        const rows = d.constituencies.slice(0, 30).map(c => `
            <tr>
                <td>${escapeHtml(c.constituency_name)}</td>
                <td style="color:var(--red);font-weight:600;">+${c.new_issues}</td>
                <td style="color:var(--green);font-weight:600;">${c.resolved_issues > 0 ? '−'+c.resolved_issues : '0'}</td>
                <td>${escapeHtml(c.top_category)}</td>
            </tr>`).join('');
        container.innerHTML = `<table class="lb-table">
            <thead><tr><th>Area</th><th>New</th><th>Resolved</th><th>Top Issue</th></tr></thead>
            <tbody>${rows}</tbody></table>`;
    } catch { container.innerHTML = '<p style="text-align:center;color:var(--red);padding:20px;">Failed to load.</p>'; }
}

// ============================================================
// VIEW SWITCHING
// ============================================================
function switchView(view) {
    currentView = view;
    ['map','list','leaderboard','digest'].forEach(v => {
        document.getElementById(`view-${v}`).classList.toggle('hidden', v !== view);
    });
    document.querySelectorAll('.nav-btn').forEach(b => b.classList.toggle('active', b.dataset.view === view));
    document.getElementById('filter-bar').style.display = (view === 'list' || view === 'map') ? 'flex' : 'none';

    if (view === 'map') { map.invalidateSize(); }
    if (view === 'list') { loadListView(0); }
    if (view === 'leaderboard') { loadLeaderboard(); }
    if (view === 'digest') { loadDigest(); }
}

// ============================================================
// EVENT LISTENERS
// ============================================================
function setupEventListeners() {
    // Nav buttons
    document.querySelectorAll('.nav-btn').forEach(btn => {
        btn.addEventListener('click', () => switchView(btn.dataset.view));
    });

    // Report FAB + card buttons
    document.getElementById('report-fab').addEventListener('click', () => openReportModal(null));
    document.getElementById('card-close').addEventListener('click', deselectConstituency);

    // Modals
    document.getElementById('modal-close').addEventListener('click', closeReportModal);
    document.getElementById('report-modal').addEventListener('click', e => { if (e.target.id === 'report-modal') closeReportModal(); });
    document.getElementById('report-form').addEventListener('submit', handleFormSubmit);
    document.getElementById('detect-location-btn').addEventListener('click', detectLocation);
    document.getElementById('pick-on-map-btn').addEventListener('click', toggleMapPicker);

    document.getElementById('resolve-modal-close').addEventListener('click', closeResolveModal);
    document.getElementById('resolve-modal').addEventListener('click', e => { if (e.target.id === 'resolve-modal') closeResolveModal(); });
    document.getElementById('resolve-form').addEventListener('submit', handleResolveSubmit);

    document.getElementById('subscribe-modal-close').addEventListener('click', closeSubscribeModal);
    document.getElementById('subscribe-modal').addEventListener('click', e => { if (e.target.id === 'subscribe-modal') closeSubscribeModal(); });

    // Filters
    ['filter-category', 'filter-ward', 'filter-status', 'filter-sort'].forEach(id => {
        document.getElementById(id).addEventListener('change', () => {
            if (currentView === 'list') loadListView(0);
        });
    });
}

// ============================================================
// UTILS
// ============================================================
function showToast(msg) {
    const toast = document.getElementById('toast');
    document.getElementById('toast-msg').textContent = msg;
    toast.classList.remove('hidden');
    clearTimeout(toast._timeout);
    toast._timeout = setTimeout(() => toast.classList.add('hidden'), 3000);
}

function partyColor(party) {
    const m = { 'AAP': '#4ECDC4', 'BJP': '#FF6B6B', 'INC': '#1a73e8', 'BSP': '#6C5CE7', 'IND': '#95a5a6' };
    return m[party] || '#95a5a6';
}

function escapeHtml(str) {
    const div = document.createElement('div');
    div.textContent = str || ''; return div.innerHTML;
}

function formatHours(h) {
    if (h < 1) return '<1h';
    if (h < 24) return `${Math.round(h)}h`;
    return `${Math.round(h / 24)}d`;
}
