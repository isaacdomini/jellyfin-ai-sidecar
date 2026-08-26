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
        #ai-fab {
            position: fixed;
            bottom: 24px;
            right: 24px;
            z-index: 99999;
            background: linear-gradient(135deg, #00A4DC, #AA5CC3);
            color: #ffffff;
            border: none;
            border-radius: 50px;
            padding: 10px 18px;
            font-size: 14px;
            font-weight: 600;
            cursor: pointer;
            box-shadow: 0 4px 16px rgba(0, 164, 220, 0.4);
            display: flex;
            align-items: center;
            gap: 8px;
            transition: all 0.25s ease;
            backdrop-filter: blur(8px);
            user-select: none;
        }
        #ai-fab:hover {
            transform: translateY(-2px) scale(1.03);
            box-shadow: 0 6px 22px rgba(170, 92, 195, 0.6);
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

    // 2. Inject Floating Action Button
    var fab = document.createElement('button');
    fab.id = 'ai-fab';
    fab.innerHTML = '<span>✨</span><span>Ask AI Scene</span>';
    document.body.appendChild(fab);

    // 3. Inject Modal Structure
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
                <div style="display: flex; gap: 8px; margin-bottom: 14px;">
                    <input type="text" id="ai-query-input" placeholder="Ask about a quote, plot point, or scene..." 
                           style="flex: 1; padding: 10px 14px; border-radius: 6px; border: 1px solid #333; background: #0E1217; color: #fff; outline: none; font-size: 0.95em;">
                    <button id="ai-submit-btn" style="background: #00A4DC; color:#fff; border:none; border-radius:6px; padding: 0 16px; font-weight:600; cursor:pointer;">Ask</button>
                </div>
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
                    name: title,
                    type: item.Type || 'Video',
                    isPlaying: true
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
                    return {
                        id: itemDetails.Id,
                        name: itemDetails.Name,
                        type: itemDetails.Type || 'Item',
                        isPlaying: false
                    };
                }
            } catch (e) {
                console.warn("[AI Sidecar] Failed to fetch item context:", e);
            }
        }

        // Context C: Default global search
        return { id: null, name: "Entire Library", type: "Global", isPlaying: false };
    }

    var currentContext = null;

    // 5. Open Modal & Refresh Context
    fab.onclick = async function () {
        currentContext = await getCurrentMediaContext();
        var badge = document.getElementById('ai-context-badge');
        if (currentContext.id) {
            badge.innerHTML = `🎯 <b>Scoped to:</b> ${currentContext.name} <span style="opacity:0.75; font-size:0.85em;">(${currentContext.type})</span>`;
        } else {
            badge.innerHTML = `🌐 <b>Scope:</b> Entire Media Library`;
        }

        overlay.style.display = 'flex';
        document.getElementById('ai-query-input').focus();
    };

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

        try {
            var response = await ApiClient.fetch({
                url: ApiClient.getUrl('/Plugins/AiSidecar/Rag'),
                type: 'POST',
                data: JSON.stringify({
                    query: query,
                    item_id: currentContext ? currentContext.id : null,
                    top_k: 5
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
