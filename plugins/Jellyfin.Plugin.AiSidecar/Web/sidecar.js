/**
 * Jellyfin AI Sidecar - Context-Aware Client-Side Floating Search Widget
 *
 * Provides a floating action button (FAB) and modal search interface for all
 * Jellyfin users (admin and non-admin).
 *
 * Context Awareness:
 * 1. Active Video Playback: Automatically scopes queries to the currently playing movie or episode,
 *    and seeks directly inside the active video player when a citation is clicked.
 * 2. Details Page (#/details?id=...): Scopes queries to the specific Movie, Series, or Episode.
 * 3. Library / Home: Defaults to searching across the entire indexed media library.
 */
(function () {
    if (window._jellyfinAiSidecarLoaded) return;
    window._jellyfinAiSidecarLoaded = true;

    // 1. Inject Styles
    var style = document.createElement('style');
    style.id = 'ai-sidecar-styles';
    style.innerHTML = `
        .btnAiSidecar {
            background: transparent;
            border: none;
            color: inherit;
            cursor: pointer;
            display: inline-flex;
            align-items: center;
            justify-content: center;
            padding: 0.3em;
            margin: 0 4px;
            vertical-align: middle;
            border-radius: 50%;
            transition: background-color 0.2s, color 0.2s, transform 0.15s;
            outline: none;
            width: 40px;
            height: 40px;
            box-sizing: border-box;
        }
        .btnAiSidecar:hover {
            background-color: rgba(255, 255, 255, 0.15);
            color: #00A4DC;
            transform: scale(1.08);
        }
        .btnAiSidecar svg {
            width: 22px;
            height: 22px;
            fill: currentColor;
            pointer-events: none;
            display: block;
        }
        #ai-modal-overlay {
            display: none;
            position: fixed;
            inset: 0;
            background: rgba(0, 0, 0, 0.75);
            z-index: 100000;
            backdrop-filter: blur(6px);
            align-items: center;
            justify-content: center;
        }
        #ai-modal-box {
            background: #14181F;
            border: 1px solid rgba(255, 255, 255, 0.12);
            border-radius: 12px;
            width: 90%;
            max-width: 600px;
            max-height: 85vh;
            display: flex;
            flex-direction: column;
            box-shadow: 0 12px 40px rgba(0, 0, 0, 0.8);
            color: #ffffff;
            overflow: hidden;
            font-family: inherit;
            animation: aiFadeIn 0.2s ease-out;
        }
        @keyframes aiFadeIn {
            from { opacity: 0; transform: scale(0.96); }
            to { opacity: 1; transform: scale(1); }
        }
        .ai-modal-header {
            padding: 14px 18px;
            background: #1B212B;
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-bottom: 1px solid rgba(255, 255, 255, 0.08);
        }
        .ai-modal-body {
            padding: 16px;
            overflow-y: auto;
            flex: 1;
        }
        .ai-context-badge {
            background: rgba(0, 164, 220, 0.15);
            color: #00A4DC;
            padding: 4px 10px;
            border-radius: 6px;
            font-size: 0.85em;
            margin-bottom: 12px;
            display: inline-block;
            border: 1px solid rgba(0, 164, 220, 0.3);
        }
        .ai-citation-card {
            background: #1D232F;
            border: 1px solid rgba(255, 255, 255, 0.06);
            border-radius: 8px;
            padding: 10px 14px;
            margin-top: 10px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            gap: 12px;
        }
        .ai-play-btn {
            background: #E50914;
            color: #ffffff;
            border: none;
            border-radius: 6px;
            padding: 6px 12px;
            font-size: 0.85em;
            cursor: pointer;
            white-space: nowrap;
            transition: background 0.2s;
        }
        .ai-play-btn:hover {
            background: #b80710;
        }
    `;
    document.head.appendChild(style);

    // 2. Inject Modal Structure
    var overlay = document.createElement('div');
    overlay.id = 'ai-modal-overlay';
    overlay.innerHTML = `
        <div id="ai-modal-box">
            <div class="ai-modal-header">
                <div style="font-weight: bold; font-size: 1.1em; display: flex; align-items: center; gap: 6px;">
                    <span>🎬</span> AI Scene & Dialogue Search
                </div>
                <button id="ai-modal-close" style="background:none; border:none; color:#aaa; font-size:1.4em; cursor:pointer; padding:0 4px;">&times;</button>
            </div>
            <div class="ai-modal-body">
                <div id="ai-context-badge" class="ai-context-badge">🎯 Scope: Entire Media Library</div>
                <div style="display: flex; gap: 8px; margin-bottom: 12px;">
                    <input type="text" id="ai-query-input" placeholder="Ask about a quote, plot point, or scene..." 
                           style="flex: 1; padding: 10px 14px; border-radius: 6px; border: 1px solid #333; background: #0E1217; color: #fff; outline: none; font-size: 0.95em;">
                    <button id="ai-submit-btn" style="background: #00A4DC; color:#fff; border:none; border-radius:6px; padding: 0 16px; font-weight:600; cursor:pointer;">Ask</button>
                </div>
                <details id="ai-advanced-details" style="margin-bottom: 14px; font-size: 0.85em; color: #aaa;">
                    <summary style="cursor: pointer; user-select: none; color: #00A4DC; font-weight: 500; outline: none;">⚙️ Advanced Options</summary>
                    <div style="display: flex; align-items: center; justify-content: space-between; margin-top: 10px; padding: 10px 12px; background: #0E1217; border-radius: 6px; border: 1px solid #222;">
                        <div>
                            <label for="ai-topk-input" style="color: #ddd; font-weight: 600;">Scenes Retrieved (top_k):</label>
                            <div style="color: #888; font-size: 0.85em; margin-top: 2px;">Number of 30s dialogue chunks to feed to the AI</div>
                        </div>
                        <div style="display: flex; align-items: center; gap: 8px;">
                            <input type="number" id="ai-topk-input" min="1" max="50" value="20"
                                   style="width: 60px; padding: 6px 8px; border-radius: 4px; border: 1px solid #444; background: #1a1f26; color: #fff; text-align: center; outline: none; font-weight: bold;">
                        </div>
                    </div>
                </details>
                <div id="ai-loading" style="display:none; color:#00A4DC; text-align:center; padding:12px; font-size:0.9em;">
                    🔍 Searching subtitles and generating response...
                </div>
                <div id="ai-answer" style="background:#0E1217; padding:12px; border-radius:8px; border:1px solid #222; display:none; line-height:1.5; font-size:0.95em;"></div>
                <div id="ai-citations" style="margin-top:14px;"></div>
            </div>
        </div>
    `;
    document.body.appendChild(overlay);

    // 4. Resolve Active Context
    async function getCurrentMediaContext() {
        // Context A: Media currently playing in Jellyfin video player
        if (window.playbackManager) {
            var item = typeof window.playbackManager.currentItem === 'function'
                ? window.playbackManager.currentItem()
                : window.playbackManager.currentItem;

            if (item && item.Id) {
                var title = item.Name || "Current Video";
                if (item.SeriesName) {
                    title = item.SeriesName + " - " + title;
                }
                return {
                    id: item.Id,
                    ids: [item.Id],
                    name: title,
                    type: item.Type || 'Video',
                    isPlaying: true,
                    scoped: true
                };
            }
        }

        // Context B: Details page in view (e.g. #/details?id=...)
        var hash = window.location.hash || "";
        var match = hash.match(/[?&]id=([a-f0-9-]+)/i);
        if (match && match[1] && window.ApiClient) {
            try {
                var userId = ApiClient.getCurrentUserId();
                var itemDetails = await ApiClient.getItem(userId, match[1]);
                if (itemDetails) {
                    var ids = [itemDetails.Id];

                    // If viewing a Series or Season, resolve all child episodes for comprehensive scoping
                    if (itemDetails.Type === 'Series' || itemDetails.Type === 'Season') {
                        try {
                            var epRes = null;
                            if (typeof ApiClient.getEpisodes === 'function' && itemDetails.Type === 'Series') {
                                epRes = await ApiClient.getEpisodes(itemDetails.Id, { userId: userId, fields: 'Id' });
                            }
                            if (!epRes || !epRes.Items || epRes.Items.length === 0) {
                                epRes = await ApiClient.getItems(userId, {
                                    parentId: itemDetails.Id,
                                    seriesId: itemDetails.Id,
                                    includeItemTypes: 'Episode',
                                    recursive: true,
                                    fields: 'Id'
                                });
                            }
                            if (epRes && epRes.Items && epRes.Items.length > 0) {
                                var epIds = epRes.Items.map(function(e) { return e.Id; });
                                ids = [itemDetails.Id].concat(epIds);
                            }
                        } catch (epErr) {
                            console.warn("[AI Sidecar] Failed to fetch episodes for series/season:", epErr);
                        }
                    }

                    return {
                        id: itemDetails.Id,
                        ids: ids,
                        name: itemDetails.Name,
                        type: itemDetails.Type || 'Item',
                        isPlaying: false,
                        scoped: true
                    };
                }
            } catch (e) {
                console.warn("[AI Sidecar] Failed to fetch item context:", e);
            }
        }

        // Context C: Default global search
        return { id: null, ids: [], name: "Entire Library", type: "Global", isPlaying: false, scoped: false };
    }

    var currentContext = null;

    function renderContextBadge() {
        var badge = document.getElementById('ai-context-badge');
        if (currentContext && currentContext.scoped && currentContext.id) {
            badge.innerHTML = `
                <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:6px;">
                    <div>🎯 <b>Scoped to:</b> ${currentContext.name} <span style="opacity:0.75; font-size:0.85em;">(${currentContext.type})</span></div>
                    <div style="display:flex; gap:10px; font-size:0.85em;">
                        <a href="#" id="ai-reindex-btn" style="color:#FFC107; text-decoration:underline;">⚡ Sync/Re-Index</a>
                        <a href="#" id="ai-toggle-scope" style="color:#00A4DC; text-decoration:underline;">Switch to Global</a>
                    </div>
                </div>
            `;

            var toggle = document.getElementById('ai-toggle-scope');
            if (toggle) {
                toggle.onclick = function(e) {
                    e.preventDefault();
                    currentContext.scoped = false;
                    renderContextBadge();
                };
            }

            var reindex = document.getElementById('ai-reindex-btn');
            if (reindex) {
                reindex.onclick = async function(e) {
                    e.preventDefault();
                    reindex.textContent = "⏳ Syncing...";
                    try {
                        var targetId = (currentContext.ids && currentContext.ids.length > 0) ? currentContext.ids[0] : currentContext.id;
                        var res = await ApiClient.fetch({
                            url: ApiClient.getUrl('/Plugins/AiSidecar/IndexItem/' + targetId),
                            type: 'POST'
                        });
                        if (res.ok) {
                            reindex.textContent = "✅ Queued!";
                            setTimeout(function() { renderContextBadge(); }, 3000);
                        } else {
                            reindex.textContent = "⚠️ Error";
                        }
                    } catch (err) {
                        console.error("[AI Sidecar] Manual sync error:", err);
                        reindex.textContent = "⚠️ Failed";
                    }
                };
            }
        } else {
            badge.innerHTML = `🌐 <b>Scope:</b> Entire Media Library` + (currentContext && currentContext.id ? ` <a href="#" id="ai-toggle-scope" style="color:#00A4DC; margin-left:8px; text-decoration:underline; font-size:0.85em;">(Re-scope to ${currentContext.name})</a>` : '');
            var toggle = document.getElementById('ai-toggle-scope');
            if (toggle) {
                toggle.onclick = function(e) {
                    e.preventDefault();
                    currentContext.scoped = true;
                    renderContextBadge();
                };
            }
        }
    }

    // 5. Open Modal & Refresh Context
    async function openAiModal() {
        currentContext = await getCurrentMediaContext();
        renderContextBadge();

        var savedTopK = localStorage.getItem('ai_sidecar_top_k');
        var topKInput = document.getElementById('ai-topk-input');
        if (topKInput && savedTopK) {
            topKInput.value = savedTopK;
        }

        overlay.style.display = 'flex';
        var input = document.getElementById('ai-query-input');
        if (input) input.focus();
    }

    function createAiButton() {
        var btn = document.createElement('button');
        btn.type = 'button';
        btn.className = 'paper-icon-button-light headerButton headerButtonRight btnAiSidecar';
        btn.setAttribute('title', 'AI Scene & Dialogue Search');
        btn.setAttribute('aria-label', 'AI Scene & Dialogue Search');
        btn.innerHTML = `
            <svg viewBox="0 0 24 24">
                <path d="M19 9l1.25-2.75L23 5l-2.75-1.25L19 1l-1.25 2.75L15 5l2.75 1.25L19 9zm-7.5.5L9 4 6.5 9.5 1 12l5.5 2.5L9 20l2.5-5.5L17 12l-5.5-2.5zM19 15l-1.25 2.75L15 19l2.75 1.25L19 23l1.25-2.75L23 19l-2.75-1.25L19 15z"/>
            </svg>
        `;
        btn.onclick = function (e) {
            if (e) {
                e.preventDefault();
                e.stopPropagation();
            }
            openAiModal();
        };
        return btn;
    }

    function attachAiButtons() {
        // 1. Target Group Play / Cast buttons in Video Player OSD and main headers
        var controlButtons = document.querySelectorAll(
            '.btnGroupPlay, .headerGroupPlayButton, .btnCast, .headerCastButton, .videoOsd-btnGroupPlay, .videoOsd-btnCast, [data-action="groupplay"], [data-action="cast"]'
        );

        controlButtons.forEach(function (btn) {
            var parent = btn.parentElement;
            if (parent && !parent.querySelector('.btnAiSidecar')) {
                var aiBtn = createAiButton();
                if (btn.nextSibling) {
                    parent.insertBefore(aiBtn, btn.nextSibling);
                } else {
                    parent.appendChild(aiBtn);
                }
            }
        });

        // 2. Target header button containers (e.g. videoOsdHeader, skinHeader-right)
        var containers = document.querySelectorAll(
            '.videoOsdHeader .headerRight, .osdHeader .headerRight, .headerRight, .skinHeader-right, .mainHeader .headerRight, .videoOsdBottom-buttons'
        );

        containers.forEach(function (container) {
            if (!container.querySelector('.btnAiSidecar')) {
                var aiBtn = createAiButton();
                if (container.firstChild) {
                    container.insertBefore(aiBtn, container.firstChild);
                } else {
                    container.appendChild(aiBtn);
                }
            }
        });
    }

    // Attach buttons and watch for DOM updates / OSD appearances
    attachAiButtons();
    var domObserver = new MutationObserver(function () {
        attachAiButtons();
    });
    domObserver.observe(document.body, { childList: true, subtree: true });
    setInterval(attachAiButtons, 1000);

    var topKInputEl = document.getElementById('ai-topk-input');
    if (topKInputEl) {
        topKInputEl.onchange = function () {
            var val = parseInt(topKInputEl.value, 10);
            if (val > 0) {
                localStorage.setItem('ai_sidecar_top_k', val);
            }
        };
    }

    // Close Modal
    function closeModal() {
        overlay.style.display = 'none';
    }
    document.getElementById('ai-modal-close').onclick = closeModal;
    overlay.onclick = function (e) {
        if (e.target === overlay) closeModal();
    };
    document.addEventListener('keydown', function (e) {
        if (e.key === 'Escape' && overlay.style.display === 'flex') {
            closeModal();
        }
    });

    // 6. Search Execution
    document.getElementById('ai-submit-btn').onclick = executeSearch;
    document.getElementById('ai-query-input').onkeydown = function (e) {
        if (e.key === 'Enter') executeSearch();
    };

    async function executeSearch() {
        var query = document.getElementById('ai-query-input').value.trim();
        if (!query) return;

        var loading = document.getElementById('ai-loading');
        var answerBox = document.getElementById('ai-answer');
        var citBox = document.getElementById('ai-citations');

        loading.style.display = 'block';
        answerBox.style.display = 'none';
        citBox.innerHTML = '';

        var filterId = null;
        if (currentContext && currentContext.scoped) {
            if (currentContext.ids && currentContext.ids.length > 0) {
                filterId = currentContext.ids.join(',');
            } else if (currentContext.id) {
                filterId = currentContext.id;
            }
        }

        var topKVal = 20;
        var topKInput = document.getElementById('ai-topk-input');
        if (topKInput) {
            var parsed = parseInt(topKInput.value, 10);
            if (parsed > 0) {
                topKVal = parsed;
                localStorage.setItem('ai_sidecar_top_k', topKVal);
            }
        }

        try {
            var response = await ApiClient.fetch({
                url: ApiClient.getUrl('/Plugins/AiSidecar/Rag'),
                type: 'POST',
                data: JSON.stringify({
                    query: query,
                    item_id: filterId,
                    itemId: filterId,
                    top_k: topKVal,
                    topK: topKVal
                }),
                contentType: 'application/json'
            });

            var data = await response.json();
            loading.style.display = 'none';

            if (data.answer) {
                answerBox.innerHTML = `<b>AI Response:</b><br><div style="margin-top:6px;">${data.answer.replace(/\n/g, '<br>')}</div>`;
                answerBox.style.display = 'block';
            }

            if (data.citations && data.citations.length > 0) {
                var header = document.createElement('div');
                header.style.fontSize = '0.9em';
                header.style.color = '#aaa';
                header.style.marginBottom = '6px';
                header.textContent = 'Cited Scenes:';
                citBox.appendChild(header);

                data.citations.forEach(function (cit) {
                    var card = document.createElement('div');
                    card.className = 'ai-citation-card';
                    card.innerHTML = `
                        <div style="font-size: 0.9em; flex: 1;">
                            <div style="font-weight:600; color:#FFC107;">🎬 ${cit.item_name || 'Scene'} <span style="color:#ddd; font-weight:normal;">(${cit.timestamp_formatted || '00:00:00'})</span></div>
                            <div style="color:#bbb; font-style:italic; margin-top:4px; line-height:1.3;">"${cit.text}"</div>
                        </div>
                        <button class="ai-play-btn">▶ Play Scene</button>
                    `;

                    // Handle Play / Seek
                    card.querySelector('.ai-play-btn').onclick = function () {
                        closeModal();

                        // If video is currently playing the same media item, seek immediately
                        if (currentContext && currentContext.isPlaying && window.playbackManager && typeof window.playbackManager.seek === 'function') {
                            window.playbackManager.seek(cit.start_ticks || 0);
                        } else if (window.playbackManager && typeof window.playbackManager.play === 'function') {
                            window.playbackManager.play({
                                ids: [cit.item_id],
                                startPositionTicks: cit.start_ticks || 0
                            });
                        } else if (window.appRouter && typeof window.appRouter.showItem === 'function') {
                            window.appRouter.showItem(cit.item_id);
                        }
                    };

                    citBox.appendChild(card);
                });
            } else if (!data.answer) {
                citBox.innerHTML = '<div style="color:#aaa; font-style:italic; padding:8px 0;">No matching dialogue or scenes found.</div>';
            }
        } catch (err) {
            loading.style.display = 'none';
            alert("Error querying AI Sidecar: " + (err.message || 'Check server connection.'));
        }
    }
})();
