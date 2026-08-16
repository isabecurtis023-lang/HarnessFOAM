document.addEventListener("DOMContentLoaded", () => {
    const runBtn = document.getElementById("run-btn");
    const promptInput = document.getElementById("prompt");
    const outputDirInput = document.getElementById("output_dir");
    const consoleOutput = document.getElementById("console-output");
    const connectionDot = document.getElementById("connection-dot");
    const connectionStatus = document.getElementById("connection-status");
    const stopBtn = document.getElementById("stop-btn");
    const postprocessBtn = document.getElementById("postprocess-btn");
    const runOpenfoamBtn = document.getElementById("run-openfoam-btn");
    
    let ws = null;

    // 2026-08-15 – Gemini 3.5 Flash: Centralized function to manage button states and colors based on directory & run status
    function updateButtonStates() {
        const hasOutputDir = outputDirInput && outputDirInput.value.trim();
        const isRunning = ws && (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING);
        
        if (!isRunning) {
            if (runBtn) {
                runBtn.disabled = false;
                runBtn.textContent = "Deep driving";
            }
            
            if (runOpenfoamBtn) {
                runOpenfoamBtn.disabled = !hasOutputDir;
                runOpenfoamBtn.style.backgroundColor = hasOutputDir ? "#10b981" : "#4b5563";
                runOpenfoamBtn.style.cursor = hasOutputDir ? "pointer" : "not-allowed";
            }
            
            if (postprocessBtn) {
                postprocessBtn.disabled = !hasOutputDir;
                postprocessBtn.style.backgroundColor = hasOutputDir ? "#a855f7" : "#4b5563";
                postprocessBtn.style.cursor = hasOutputDir ? "pointer" : "not-allowed";
            }
            
            if (stopBtn) {
                stopBtn.disabled = true;
                stopBtn.style.backgroundColor = "#4b5563";
                stopBtn.style.cursor = "not-allowed";
                stopBtn.textContent = "Stop";
            }
        } else {
            if (runBtn) {
                runBtn.disabled = true;
            }
            if (runOpenfoamBtn) {
                runOpenfoamBtn.disabled = true;
                runOpenfoamBtn.style.backgroundColor = "#4b5563";
                runOpenfoamBtn.style.cursor = "not-allowed";
            }
            if (postprocessBtn) {
                postprocessBtn.disabled = true;
                postprocessBtn.style.backgroundColor = "#4b5563";
                postprocessBtn.style.cursor = "not-allowed";
            }
            if (stopBtn) {
                stopBtn.disabled = false;
                stopBtn.style.backgroundColor = "#ef4444";
                stopBtn.style.cursor = "pointer";
            }
        }
    }

    // 2026-08-15 – Gemini 3.5 Flash: Sidebar collapse toggle logic
    const toggleCpBtn = document.getElementById("toggle-cp-btn");
    const controlPanel = document.getElementById("control-panel");
    
    if (toggleCpBtn && controlPanel) {
        toggleCpBtn.addEventListener("click", (e) => {
            e.preventDefault();
            controlPanel.classList.toggle("collapsed");
            if (controlPanel.classList.contains("collapsed")) {
                toggleCpBtn.title = "Expand Panel";
            } else {
                toggleCpBtn.title = "Collapse Panel";
            }
        });
    }

    function appendLog(html) {
        const div = document.createElement("div");
        div.className = "log-entry";
        div.innerHTML = html;
        consoleOutput.appendChild(div);
        consoleOutput.scrollTop = consoleOutput.scrollHeight;
    }
    
    // Check OpenFOAM Status
    const ofDot = document.getElementById("openfoam-dot");
    const ofStatus = document.getElementById("openfoam-status");
    
    function checkOFStatus() {
        fetch('/api/system_status')
            .then(r => r.json())
            .then(data => {
                if (data.openfoam) {
                    ofDot.style.backgroundColor = "#10b981";
                    ofStatus.innerHTML = `OpenFOAM: <span style="color:#10b981">Ready (${data.method})</span>`;
                } else {
                    ofDot.style.backgroundColor = "#ef4444";
                    ofStatus.innerHTML = `OpenFOAM: <span style="color:#ef4444">Not Found</span> <a href="#" id="install-of-btn" style="color:var(--accent);text-decoration:none;margin-left:5px;">(Install)</a>`;
                    
                    setTimeout(() => {
                        const installBtn = document.getElementById("install-of-btn");
                        if (installBtn) {
                            installBtn.addEventListener("click", (e) => {
                                e.preventDefault();
                                installBtn.style.pointerEvents = "none";
                                installBtn.textContent = "(Installing...)";
                                
                                appendLog(`<span class="system">--- OpenFOAM Auto-Installer Triggered ---</span>`);
                                
                                const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
                                const wsUrl = `${protocol}//${window.location.host}/api/stream`;
                                ws = new WebSocket(wsUrl);
                                
                                ws.onopen = () => {
                                    connectionDot.classList.add("connected");
                                    connectionStatus.textContent = "Installer Connected";
                                    ws.send(JSON.stringify({ action: "install" }));
                                };
                                
                                ws.onmessage = (event) => {
                                    const data = JSON.parse(event.data);
                                    if (data.type === "info") {
                                        appendLog(`<span class="info">ℹ️ ${data.message}</span>`);
                                    } else if (data.type === "step") {
                                        appendLog(`<span class="log-agent" style="color:#a855f7">[${data.agent}]</span> <span>${data.message}</span>`);
                                    } else if (data.type === "complete") {
                                        appendLog(`<span class="info" style="color:#10b981">✨ ${data.message}</span>`);
                                        checkOFStatus();
                                    } else if (data.type === "error") {
                                        appendLog(`<span class="error">❌ Error: ${data.message}</span>`);
                                    }
                                };
                                
                                ws.onclose = () => {
                                    connectionDot.classList.remove("connected");
                                    connectionStatus.textContent = "Disconnected";
                                };
                            });
                        }
                    }, 100);
                }
            })
            .catch(() => {
                ofDot.style.backgroundColor = "#ef4444";
                ofStatus.textContent = "OpenFOAM: Status Unknown";
            });
    }
    
    checkOFStatus();
    // 2026-08-15 – Gemini 3.5 Flash: Initial button states update
    updateButtonStates();

    // Auto-set CWD or load from localStorage
    const savedOutputDir = localStorage.getItem("harnessfoam_output_dir");
    if (savedOutputDir) {
        outputDirInput.value = savedOutputDir;
        loadRootTree(savedOutputDir);
        updateButtonStates();
    } else {
        fetch('/api/cwd')
            .then(r => r.json())
            .then(data => {
                if (data.cwd && (!outputDirInput.value || outputDirInput.value === "demo_run_web")) {
                    outputDirInput.value = data.cwd;
                    loadRootTree(data.cwd);
                }
                updateButtonStates();
            });
    }
        
    // Check LLM API Status
    const llmDot = document.getElementById("llm-dot");
    const llmStatus = document.getElementById("llm-status");
    
    function checkLLMStatus() {
        const apiBase = document.getElementById("api_base") ? document.getElementById("api_base").value.trim() : "";
        const apiKey = document.getElementById("api_key") ? document.getElementById("api_key").value.trim() : "";
        
        llmDot.style.backgroundColor = "#fbbf24";
        llmStatus.textContent = "Checking LLM API...";
        
        fetch(`/api/llm_status?api_base=${encodeURIComponent(apiBase)}&api_key=${encodeURIComponent(apiKey)}`)
            .then(r => r.json())
            .then(data => {
                if (data.status === "ok") {
                    llmDot.style.backgroundColor = "#10b981";
                    llmStatus.innerHTML = `LLM API: <span style="color:#10b981">Online</span>`;
                } else {
                    llmDot.style.backgroundColor = "#ef4444";
                    llmStatus.innerHTML = `LLM API: <span style="color:#ef4444">Offline</span>`;
                }
            })
            .catch(() => {
                llmDot.style.backgroundColor = "#ef4444";
                llmStatus.textContent = "LLM API: Error";
            });
    }
    // 2026-08-15 – Gemini 3.5 Flash: Load saved API settings from localStorage
    const savedApiBase = localStorage.getItem("harnessfoam_api_base");
    const savedApiKey = localStorage.getItem("harnessfoam_api_key");
    const savedModelName = localStorage.getItem("harnessfoam_model_name");

    const apiBaseInput = document.getElementById("api_base");
    const apiKeyInput = document.getElementById("api_key");
    const modelNameSelect = document.getElementById("model_name");

    if (apiBaseInput && savedApiBase) apiBaseInput.value = savedApiBase;
    if (apiKeyInput && savedApiKey) apiKeyInput.value = savedApiKey;
    if (modelNameSelect && savedModelName) {
        let optionExists = Array.from(modelNameSelect.options).some(opt => opt.value === savedModelName);
        if (!optionExists) {
            const opt = document.createElement("option");
            opt.value = savedModelName;
            opt.textContent = savedModelName;
            modelNameSelect.appendChild(opt);
        }
        modelNameSelect.value = savedModelName;
    }

    checkLLMStatus();
    
    // Add logic for Browse button
    const browseBtn = document.getElementById("browse-btn");
    if (browseBtn) {
        browseBtn.addEventListener("click", async (e) => {
            e.preventDefault(); // Stop form submission / button default if any
            const originalText = browseBtn.textContent;
            browseBtn.textContent = "...";
            try {
                const response = await fetch('/api/browse_folder');
                if (!response.ok) {
                    throw new Error("HTTP error " + response.status);
                }
                const data = await response.json();
                if (data.path) {
                    outputDirInput.value = data.path;
                    localStorage.setItem("harnessfoam_output_dir", data.path);
                    loadRootTree(data.path);
                    updateButtonStates();
                }
            } catch (err) {
                console.error("Failed to browse folder:", err);
                alert("Failed to open folder browser. Please ensure:\n1. You accessed the page via http://127.0.0.1:8000 (not by opening the HTML file directly).\n2. The HarnessFOAM backend server is running in the terminal.");
            } finally {
                browseBtn.textContent = originalText;
            }
        });
    }

    // File Explorer Logic
    const fileExplorer = document.getElementById("file-explorer");
    const fileTree = document.getElementById("file-tree");
    const refreshFilesBtn = document.getElementById("refresh-files-btn");
    const sidebarResizer = document.getElementById("sidebar-resizer");

    // Output dir change listener
    outputDirInput.addEventListener("change", () => {
        const val = outputDirInput.value.trim();
        if (val) {
            localStorage.setItem("harnessfoam_output_dir", val);
            loadRootTree(val);
        }
        updateButtonStates();
    });

    // Initial load if populated
    if (outputDirInput.value.trim()) {
        loadRootTree(outputDirInput.value.trim());
    }
    
     // 2026-08-15 – Gemini 3.5 Flash: Removed duplicate controlPanel declaration to prevent SyntaxError
    const cpResizer = document.getElementById("cp-resizer");
    
    let isResizingExplorer = false;
    let isResizingCP = false;
    let isResizingSider = false;

    if (sidebarResizer && fileExplorer) {
        sidebarResizer.addEventListener("mousedown", (e) => {
            isResizingExplorer = true;
            sidebarResizer.classList.add("resizing");
            document.body.style.cursor = "ew-resize";
            document.body.style.userSelect = "none";
        });
    }
    
    if (cpResizer && controlPanel) {
        cpResizer.addEventListener("mousedown", (e) => {
            isResizingCP = true;
            cpResizer.classList.add("resizing");
            document.body.style.cursor = "ew-resize";
            document.body.style.userSelect = "none";
        });
    }

    const siderResizer = document.getElementById("sider-resizer");
    const siderPanelEl = document.getElementById("sider-panel");
    const siderToggleBtn = document.getElementById("sider-toggle-btn");
    const closeSiderBtn = document.getElementById("close-sider-btn");
    
    if (siderResizer && siderPanelEl) {
        siderResizer.addEventListener("mousedown", (e) => {
            isResizingSider = true;
            siderPanelEl.classList.add("no-transition"); // Prevent lag during resize
            document.body.style.cursor = "ew-resize";
            document.body.style.userSelect = "none";
        });
    }

    document.addEventListener("mousemove", (e) => {
        if (isResizingExplorer) {
            const cpWidth = controlPanel ? controlPanel.getBoundingClientRect().width : 350;
            // The file explorer sits to the right of the control panel (and a 4px resizer)
            const newWidth = e.clientX - cpWidth - 4; 
            if (newWidth > 150 && newWidth < 800) {
                fileExplorer.style.width = `${newWidth}px`;
            }
        }
        
        if (isResizingCP) {
            const newWidth = e.clientX;
            if (newWidth > 250 && newWidth < 800) {
                controlPanel.style.width = `${newWidth}px`;
            }
        }
        
        if (isResizingSider && siderPanelEl) {
            const newWidth = window.innerWidth - e.clientX;
            if (newWidth > 300 && newWidth < 1200) {
                siderPanelEl.style.width = `${newWidth}px`;
            }
        }
    });

    document.addEventListener("mouseup", () => {
        if (isResizingExplorer) {
            isResizingExplorer = false;
            if (sidebarResizer) sidebarResizer.classList.remove("resizing");
        }
        if (isResizingCP) {
            isResizingCP = false;
            if (cpResizer) cpResizer.classList.remove("resizing");
        }
        if (isResizingSider) {
            isResizingSider = false;
            if (siderPanelEl) siderPanelEl.classList.remove("no-transition");
        }
        if (!isResizingExplorer && !isResizingCP && !isResizingSider) {
            document.body.style.cursor = "";
            document.body.style.userSelect = "";
        }
    });
    
    if (refreshFilesBtn) {
        refreshFilesBtn.addEventListener("click", () => {
            if (outputDirInput.value.trim()) {
                loadRootTree(outputDirInput.value.trim());
            }
        });
    }

    async function loadRootTree(path) {
        if (!fileExplorer || !fileTree) return;
        fileExplorer.style.display = "flex";
        if (sidebarResizer) sidebarResizer.style.display = "block";
        fileTree.innerHTML = '<div style="padding: 1rem 1.5rem; color: #94a3b8; font-size: 0.85rem;">Loading...</div>';
        await fetchAndRenderFolder(path, fileTree);
    }

    const tabConsole = document.getElementById("tab-console");
    const tabFileViewer = document.getElementById("tab-file-viewer");
    const tabAgentContext = document.getElementById("tab-agent-context");
    
    function setTabActive(activeTabId) {
        // Alias for backwards compatibility if needed
        switchToTab(activeTabId.replace('tab-', '').replace('-', '_'));
    }

    function switchToTab(tabName) {
        const consoleOutput = document.getElementById("console-output");
        const fileViewer = document.getElementById("file-viewer");
        const agentContextOutput = document.getElementById("agent-context-output");
        const openfoamLogsOutput = document.getElementById("openfoam-logs-output");
        const tabOpenfoamLogs = document.getElementById("tab-openfoam-logs");

        // Hide all bodies
        if (consoleOutput) consoleOutput.style.display = "none";
        if (agentContextOutput) agentContextOutput.style.display = "none";
        if (openfoamLogsOutput) openfoamLogsOutput.style.display = "none";
        if (fileViewer) fileViewer.style.display = "none";
        
        // Remove active styling
        if (tabConsole) {
            tabConsole.classList.remove("active");
            tabConsole.style.background = "transparent";
            tabConsole.style.color = "var(--text-muted)";
            tabConsole.style.border = "1px solid transparent";
            tabConsole.style.borderBottom = "none";
        }
        if (tabAgentContext) {
            tabAgentContext.classList.remove("active");
            tabAgentContext.style.background = "transparent";
            tabAgentContext.style.color = "var(--text-muted)";
            tabAgentContext.style.border = "1px solid transparent";
            tabAgentContext.style.borderBottom = "none";
        }
        if (tabOpenfoamLogs) {
            tabOpenfoamLogs.classList.remove("active");
            tabOpenfoamLogs.style.background = "transparent";
            tabOpenfoamLogs.style.color = "var(--text-muted)";
            tabOpenfoamLogs.style.border = "1px solid transparent";
            tabOpenfoamLogs.style.borderBottom = "none";
        }
        if (tabFileViewer) {
            tabFileViewer.classList.remove("active");
            tabFileViewer.style.background = "transparent";
            tabFileViewer.style.color = "var(--text-muted)";
            tabFileViewer.style.border = "1px solid transparent";
            tabFileViewer.style.borderBottom = "none";
        }

        // Apply active styling to the selected tab
        if (tabName === "console" || tabName === "console_output") {
            if (consoleOutput) consoleOutput.style.display = "flex";
            if (tabConsole) {
                tabConsole.classList.add("active");
                tabConsole.style.background = "rgba(255,255,255,0.1)";
                tabConsole.style.color = "var(--text-main)";
                tabConsole.style.border = "1px solid rgba(255,255,255,0.05)";
                tabConsole.style.borderBottom = "none";
            }
        } else if (tabName === "agent_context") {
            if (agentContextOutput) agentContextOutput.style.display = "flex";
            if (tabAgentContext) {
                tabAgentContext.classList.add("active");
                tabAgentContext.style.background = "rgba(255,255,255,0.1)";
                tabAgentContext.style.color = "var(--text-main)";
                tabAgentContext.style.border = "1px solid rgba(255,255,255,0.05)";
                tabAgentContext.style.borderBottom = "none";
            }
        } else if (tabName === "openfoam_logs") {
            if (openfoamLogsOutput) openfoamLogsOutput.style.display = "flex";
            if (tabOpenfoamLogs) {
                tabOpenfoamLogs.classList.add("active");
                tabOpenfoamLogs.style.background = "rgba(255,255,255,0.1)";
                tabOpenfoamLogs.style.color = "var(--text-main)";
                tabOpenfoamLogs.style.border = "1px solid rgba(255,255,255,0.05)";
                tabOpenfoamLogs.style.borderBottom = "none";
            }
        } else if (tabName === "file_viewer" || tabName === "file_viewer_content") {
            if (fileViewer) fileViewer.style.display = "flex";
            if (tabFileViewer) {
                tabFileViewer.classList.add("active");
                tabFileViewer.style.background = "rgba(255,255,255,0.1)";
                tabFileViewer.style.color = "var(--text-main)";
                tabFileViewer.style.border = "1px solid rgba(255,255,255,0.05)";
                tabFileViewer.style.borderBottom = "none";
            }
        }
    }

    if (tabConsole) {
        tabConsole.addEventListener("click", () => switchToTab("console"));
    }
    if (tabAgentContext) {
        tabAgentContext.addEventListener("click", () => switchToTab("agent_context"));
    }
    const tabOpenfoamLogs = document.getElementById("tab-openfoam-logs");
    if (tabOpenfoamLogs) {
        tabOpenfoamLogs.addEventListener("click", () => switchToTab("openfoam_logs"));
    }
    if (tabFileViewer) {
        tabFileViewer.addEventListener("click", (e) => {
            if (e.target.id === "close-file-viewer-btn") {
                const currentContent = document.getElementById("file-viewer-content").value;
                if (window.originalFileContent !== undefined && currentContent !== window.originalFileContent) {
                    if (!confirm("You have unsaved changes. Are you sure you want to discard them and close?")) {
                        return; // user cancelled closing
                    }
                }
                tabFileViewer.style.display = "none";
                setTabActive('tab-console');
                return;
            }
            if (e.target.id === "save-file-btn") {
                const content = document.getElementById("file-viewer-content").value;
                const path = window.currentEditingFile;
                
                const btn = e.target;
                const originalText = btn.textContent;
                btn.textContent = "⏳";
                
                fetch('/api/save_file', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ path, content })
                }).then(r => r.json()).then(res => {
                    if(res.error) {
                        alert(res.error);
                        btn.textContent = originalText;
                    } else {
                        btn.textContent = "✅";
                        window.originalFileContent = content; // Update clean state
                        setTimeout(() => { if(btn.textContent === "✅") btn.textContent = originalText; }, 2000);
                    }
                }).catch(err => {
                    alert("Network error");
                    btn.textContent = originalText;
                });
                return;
            }
            setTabActive('tab-file-viewer');
        });
    }

    async function fetchAndRenderFolder(path, parentElement) {
        try {
            const response = await fetch(`/api/files?path=${encodeURIComponent(path)}`);
            const data = await response.json();
            
            parentElement.innerHTML = ""; // clear loading or old content
            
            if (data.error) {
                parentElement.innerHTML = `<div style="padding: 0.5rem 1.5rem; color: #ef4444; font-size: 0.8rem;">${data.error}</div>`;
                return;
            }
            
            if (data.items.length === 0) {
                parentElement.innerHTML = `<div style="padding: 0.5rem 1.5rem; color: #94a3b8; font-size: 0.8rem;">(Empty)</div>`;
                return;
            }
            
            data.items.forEach(item => {
                const li = document.createElement("li");
                
                const itemDiv = document.createElement("div");
                itemDiv.className = "tree-item";
                
                const icon = document.createElement("span");
                icon.className = "tree-icon";
                icon.textContent = item.is_dir ? "📁" : "📄";
                
                const name = document.createElement("span");
                name.textContent = item.name;
                
                itemDiv.appendChild(icon);
                itemDiv.appendChild(name);
                
                // 2026-08-15 – Gemini 3.5 Flash: Create tree actions bar
                const actionsDiv = document.createElement("div");
                actionsDiv.className = "tree-actions";
                
                if (item.is_dir) {
                    // Create File Button
                    const createFileBtn = document.createElement("button");
                    createFileBtn.className = "tree-action-btn";
                    createFileBtn.textContent = "📄+";
                    createFileBtn.title = "Create File";
                    createFileBtn.addEventListener("click", (e) => {
                        e.stopPropagation();
                        const filename = prompt("Enter new file name:");
                        if (!filename) return;
                        createItem(item.path, filename, false);
                    });
                    actionsDiv.appendChild(createFileBtn);
                    
                    // Create Folder Button
                    const createDirBtn = document.createElement("button");
                    createDirBtn.className = "tree-action-btn";
                    createDirBtn.textContent = "📁+";
                    createDirBtn.title = "Create Folder";
                    createDirBtn.addEventListener("click", (e) => {
                        e.stopPropagation();
                        const dirname = prompt("Enter new folder name:");
                        if (!dirname) return;
                        createItem(item.path, dirname, true);
                    });
                    actionsDiv.appendChild(createDirBtn);
                    
                    // Paste Button (only if clipboard is set)
                    if (window.harnessfoamClipboard) {
                        const pasteBtn = document.createElement("button");
                        pasteBtn.className = "tree-action-btn";
                        pasteBtn.textContent = "📋📥";
                        pasteBtn.title = "Paste copied item";
                        pasteBtn.addEventListener("click", (e) => {
                            e.stopPropagation();
                            pasteItem(window.harnessfoamClipboard, item.path);
                        });
                        actionsDiv.appendChild(pasteBtn);
                    }
                }
                
                // Copy Button
                const copyBtn = document.createElement("button");
                copyBtn.className = "tree-action-btn";
                copyBtn.textContent = "📋";
                copyBtn.title = "Copy";
                copyBtn.addEventListener("click", (e) => {
                    e.stopPropagation();
                    window.harnessfoamClipboard = item.path;
                    alert(`Copied path: ${item.name}`);
                    loadRootTree(outputDirInput.value.trim());
                });
                actionsDiv.appendChild(copyBtn);
                
                // Rename Button
                const renameBtn = document.createElement("button");
                renameBtn.className = "tree-action-btn";
                renameBtn.textContent = "✏️";
                renameBtn.title = "Rename";
                renameBtn.addEventListener("click", (e) => {
                    e.stopPropagation();
                    const newName = prompt("Rename to:", item.name);
                    if (!newName || newName === item.name) return;
                    renameItem(item.path, newName);
                });
                actionsDiv.appendChild(renameBtn);
                
                // Delete Button
                const deleteBtn = document.createElement("button");
                deleteBtn.className = "tree-action-btn";
                deleteBtn.textContent = "🗑️";
                deleteBtn.title = "Delete";
                deleteBtn.addEventListener("click", (e) => {
                    e.stopPropagation();
                    if (!confirm(`Are you sure you want to delete ${item.name}?`)) return;
                    deleteItem(item.path);
                });
                actionsDiv.appendChild(deleteBtn);
                
                itemDiv.appendChild(actionsDiv);
                li.appendChild(itemDiv);
                
                if (item.is_dir) {
                    const childrenUl = document.createElement("ul");
                    childrenUl.className = "tree-children";
                    li.appendChild(childrenUl);
                    
                    let isLoaded = false;
                    
                    itemDiv.addEventListener("click", async () => {
                        childrenUl.classList.toggle("open");
                        if (childrenUl.classList.contains("open")) {
                            icon.textContent = "📂";
                            if (!isLoaded) {
                                childrenUl.innerHTML = '<div style="padding: 0.2rem 1.5rem; color: #94a3b8; font-size: 0.8rem;">...</div>';
                                await fetchAndRenderFolder(item.path, childrenUl);
                                isLoaded = true;
                            }
                        } else {
                            icon.textContent = "📁";
                        }
                    });
                } else {
                    itemDiv.addEventListener("click", async () => {
                        const fileViewer = document.getElementById("file-viewer");
                        const consoleOutput = document.getElementById("console-output");
                        const tabFileViewer = document.getElementById("tab-file-viewer");
                        const viewerContent = document.getElementById("file-viewer-content");
                        
                        window.currentEditingFile = item.path;
                        
                        tabFileViewer.style.display = "inline-block";
                        tabFileViewer.innerHTML = `${item.name} <span id="save-file-btn" style="margin-left: 8px; color: #10b981; font-size: 0.9rem; cursor: pointer;" title="Save">💾</span> <span id="close-file-viewer-btn" style="margin-left: 8px; color: #ef4444; font-size: 0.8rem; cursor: pointer;" title="Close">✖</span>`;
                        tabFileViewer.click();
                        
                        viewerContent.value = "Loading...";
                        
                        try {
                            const resp = await fetch(`/api/file_content?path=${encodeURIComponent(item.path)}`);
                            const fileData = await resp.json();
                            
                            if (fileData.error) {
                                viewerContent.style.color = "#ef4444";
                                viewerContent.value = `Error: ${fileData.error}`;
                                window.originalFileContent = undefined;
                            } else {
                                viewerContent.style.color = "var(--text-main)";
                                viewerContent.value = fileData.content;
                                window.originalFileContent = fileData.content;
                            }
                        } catch (err) {
                            viewerContent.style.color = "#ef4444";
                            viewerContent.value = "Network error while loading file.";
                        }
                    });
                }
                
                parentElement.appendChild(li);
            });
        } catch (err) {
            parentElement.innerHTML = `<div style="padding: 0.5rem 1.5rem; color: #ef4444; font-size: 0.8rem;">Network Error</div>`;
        }
    }

    // Modal Logic
    const settingsBtn = document.getElementById("settings-bottom-btn");
    const modal = document.getElementById("settings-modal");
    const closeModalBtn = document.querySelector(".close-modal");
    const saveSettingsBtn = document.getElementById("save-settings-btn");
    
    // Fetch Models Logic
    const fetchModelsBtn = document.getElementById("fetch-models-btn");
    const modelList = document.getElementById("model-list");
    const modelStatus = document.getElementById("model-fetch-status");

    if (fetchModelsBtn) {
        fetchModelsBtn.addEventListener("click", async (e) => {
            e.preventDefault();
            const apiBase = document.getElementById("api_base").value.trim();
            const apiKey = document.getElementById("api_key").value.trim();
            
            if (!apiBase) {
                modelStatus.style.color = "#ef4444";
                modelStatus.textContent = "Please enter an API Base URL first.";
                return;
            }
            
            fetchModelsBtn.disabled = true;
            modelStatus.style.color = "#a78bfa";
            modelStatus.textContent = "Fetching models...";
            
            try {
                const response = await fetch(`/api/models?api_base=${encodeURIComponent(apiBase)}&api_key=${encodeURIComponent(apiKey)}`);
                const data = await response.json();
                
                if (data.error) {
                    modelStatus.style.color = "#ef4444";
                    modelStatus.textContent = `Error: ${data.error}`;
                } else if (data.models && data.models.length > 0) {
                    const modelSelect = document.getElementById("model_name");
                    modelSelect.innerHTML = "";
                    data.models.forEach(modelId => {
                        const option = document.createElement("option");
                        option.value = modelId;
                        option.textContent = modelId;
                        modelSelect.appendChild(option);
                    });
                    // 2026-08-15 – Gemini 3.5 Flash: Re-select the saved model if it's in the fetched list
                    const currentSavedModel = localStorage.getItem("harnessfoam_model_name");
                    if (currentSavedModel && data.models.includes(currentSavedModel)) {
                        modelSelect.value = currentSavedModel;
                    }
                    modelStatus.style.color = "#10b981";
                    modelStatus.textContent = `Successfully loaded ${data.models.length} models! Click to select.`;
                } else {
                    modelStatus.style.color = "#ef4444";
                    modelStatus.textContent = "No models found at this endpoint.";
                }
            } catch (err) {
                modelStatus.style.color = "#ef4444";
                modelStatus.textContent = `Network error: ${err.message}`;
            } finally {
                fetchModelsBtn.disabled = false;
            }
        });
    }

    if (settingsBtn && modal && closeModalBtn) {
        settingsBtn.addEventListener("click", (e) => {
            e.preventDefault();
            modal.classList.add("show");
        });

        closeModalBtn.addEventListener("click", () => {
            modal.classList.remove("show");
        });

        if (saveSettingsBtn) {
            saveSettingsBtn.addEventListener("click", () => {
                // 2026-08-15 – Gemini 3.5 Flash: Save settings to localStorage on save
                const apiBase = document.getElementById("api_base") ? document.getElementById("api_base").value.trim() : "";
                const apiKey = document.getElementById("api_key") ? document.getElementById("api_key").value.trim() : "";
                const modelName = document.getElementById("model_name") ? document.getElementById("model_name").value.trim() : "";
                
                localStorage.setItem("harnessfoam_api_base", apiBase);
                localStorage.setItem("harnessfoam_api_key", apiKey);
                localStorage.setItem("harnessfoam_model_name", modelName);

                modal.classList.remove("show");
                if (typeof checkLLMStatus === "function") {
                    checkLLMStatus();
                }
            });
        }

        // Close when clicking outside of modal content
        window.addEventListener("click", (e) => {
            if (e.target === modal) {
                modal.classList.remove("show");
            }
        });
    }

    runBtn.addEventListener("click", () => {
        const prompt = promptInput.value.trim();
        const postPrompt = document.getElementById("post_prompt") ? document.getElementById("post_prompt").value.trim() : "";
        const outputDir = outputDirInput.value.trim();
        
        if (!prompt) {
            appendLog(`<span class="error">[Error] Simulation requirement cannot be empty.</span>`);
            return;
        }
        
        runBtn.disabled = true;
        runBtn.textContent = "Processing...";
        if (stopBtn) {
            // 2026-08-15 – Gemini 3.5 Flash: Enable Stop button and style it active red when running
            stopBtn.disabled = false;
            stopBtn.style.backgroundColor = "#ef4444";
            stopBtn.style.cursor = "pointer";
        }
        appendLog(`<span class="system">--- New Simulation Requested ---</span>`);
        
        // Use current host for websocket
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${protocol}//${window.location.host}/api/stream`;
        
        ws = new WebSocket(wsUrl);
        
        const apiBase = document.getElementById("api_base").value.trim();
        const modelName = document.getElementById("model_name").value.trim();
        const apiKey = document.getElementById("api_key").value.trim();
        
        ws.onopen = () => {
            connectionDot.classList.add("connected");
            connectionStatus.textContent = "Connected";
            // Send request payload
            ws.send(JSON.stringify({ 
                prompt, 
                post_prompt: postPrompt,
                output_dir: outputDir,
                api_base: apiBase,
                model: modelName,
                api_key: apiKey
            }));
        };
        
        ws.onmessage = (event) => {
            const data = JSON.parse(event.data);
            
            if (data.type === "info") {
                appendLog(`<span class="info">ℹ️ ${data.message}</span>`);
            } else if (data.type === "step") {
                const agentClass = data.agent.startsWith("OpenFOAM") ? "agent-Runner" : `agent-${data.agent.split(" ")[0]}`;
                appendLog(`<span class="log-agent ${agentClass}">[${data.agent}]</span> <span>${data.message}</span>`);
            } else if (data.type === "llm_start") {
                const acContainer = document.getElementById("agent-context-output");
                if (acContainer) {
                    const agentDiv = document.createElement("div");
                    agentDiv.className = "log-entry";
                    agentDiv.style.borderLeft = "3px solid #3b82f6";
                    agentDiv.style.paddingLeft = "10px";
                    agentDiv.style.marginBottom = "1rem";
                    
                    const header = document.createElement("div");
                    header.innerHTML = `<strong style="color: #60a5fa;">[${data.agent}] System Prompt & Context:</strong>`;
                    
                    const prompt = document.createElement("pre");
                    prompt.style.whiteSpace = "pre-wrap";
                    prompt.style.color = "#94a3b8";
                    prompt.style.fontSize = "0.75rem";
                    prompt.style.marginTop = "0.5rem";
                    prompt.textContent = data.prompt;
                    
                    const outputHeader = document.createElement("div");
                    outputHeader.innerHTML = `<strong style="color: #10b981; margin-top: 0.5rem; display:block;">[${data.agent}] Model Output:</strong>`;
                    
                    const tokenContainer = document.createElement("div");
                    tokenContainer.className = "llm-stream-container";
                    tokenContainer.style.color = "#e2e8f0";
                    tokenContainer.style.whiteSpace = "pre-wrap";
                    tokenContainer.style.marginTop = "0.25rem";
                    tokenContainer.id = "current-llm-stream";
                    
                    agentDiv.appendChild(header);
                    agentDiv.appendChild(prompt);
                    agentDiv.appendChild(outputHeader);
                    agentDiv.appendChild(tokenContainer);
                    acContainer.appendChild(agentDiv);
                    acContainer.scrollTop = acContainer.scrollHeight;
                }
            } else if (data.type === "llm_token") {
                const streamContainer = document.getElementById("current-llm-stream");
                if (streamContainer) {
                    streamContainer.textContent += data.token;
                    const acContainer = document.getElementById("agent-context-output");
                    if (acContainer) acContainer.scrollTop = acContainer.scrollHeight;
                }
            } else if (data.type === "llm_end") {
                const streamContainer = document.getElementById("current-llm-stream");
                if (streamContainer) {
                    streamContainer.removeAttribute("id"); // finalize it
                }
            } else if (data.type === "complete") {
                appendLog(`<span class="info" style="color:#10b981">✨ ${data.message}</span>`);
                if (data.directory) {
                    appendLog(`<span class="info">Output saved to: <strong>${data.directory}</strong></span>`);
                }
                
                if (data.files && data.files.length > 0) {
                    const fileList = data.files.map(f => `<div>📄 ${f}</div>`).join("");
                    appendLog(`<div class="file-list">${fileList}</div>`);
                }
                
                if (data.image_base64) {
                    appendLog(`<span class="info">📸 Visualizer Output:</span>`);
                    appendLog(`<img src="data:image/png;base64,${data.image_base64}" style="max-width: 100%; border-radius: 8px; margin-top: 10px; border: 1px solid rgba(255,255,255,0.1);">`);
                }
                
                // Auto-refresh the project files sidebar
                if (outputDirInput.value.trim()) {
                    loadRootTree(outputDirInput.value.trim());
                }
                
                ws.close();
                
                // Show the Run OpenFOAM button
                const runOpenfoamBtn = document.getElementById("run-openfoam-btn");
                if (runOpenfoamBtn && data.message.includes("workflow complete")) {
                    runOpenfoamBtn.style.display = "block";
                }
            } else if (data.type === "error") {
                appendLog(`<span class="error">❌ Error: ${data.message}</span>`);
                ws.close();
            }
        };
        
        ws.onclose = () => {
    connectionDot.classList.remove("connected");
    connectionStatus.textContent = "Disconnected";
    // Reset UI states
    updateButtonStates();
};
        
        ws.onerror = (err) => {
            appendLog(`<span class="error">❌ WebSocket connection error. Ensure FastAPI backend is running.</span>`);
        };
    });

    // Run OpenFOAM Button Logic
    if (runOpenfoamBtn) {
        runOpenfoamBtn.addEventListener("click", () => {
            const outputDir = outputDirInput.value.trim();
            if (!outputDir) return;
            
            runOpenfoamBtn.disabled = true;
            runOpenfoamBtn.textContent = "Running...";
            if (stopBtn) {
                // 2026-08-15 – Gemini 3.5 Flash: Enable Stop button and style it active red when running
                stopBtn.disabled = false;
                stopBtn.style.backgroundColor = "#ef4444";
                stopBtn.style.cursor = "pointer";
            }
            appendLog(`<span class="system">--- Executing Simulation ---</span>`);
            
            const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
            const wsUrl = `${protocol}//${window.location.host}/api/stream`;
            ws = new WebSocket(wsUrl);
            
            ws.onopen = () => {
                connectionDot.classList.add("connected");
                connectionStatus.textContent = "Connected";
                ws.send(JSON.stringify({ 
                    action: "run_openfoam",
                    output_dir: outputDir
                }));
            };
            
            ws.onmessage = (event) => {
                const data = JSON.parse(event.data);
                if (data.type === "info") {
                    appendLog(`<span class="info">ℹ️ ${data.message}</span>`);
                } else if (data.type === "step") {
                    appendLog(`<span class="log-agent agent-Runner">[${data.agent}]</span> <span>${data.message}</span>`);
                } else if (data.type === "openfoam_log") {
                    const openfoamLogsOutput = document.getElementById("openfoam-logs-output");
                    if (openfoamLogsOutput) {
                        const div = document.createElement("div");
                        div.className = "log-entry";
                        div.style.color = data.is_error ? "#ef4444" : "var(--text-main)";
                        div.textContent = data.message;
                        openfoamLogsOutput.appendChild(div);
                        openfoamLogsOutput.scrollTop = openfoamLogsOutput.scrollHeight;
                    }
                    switchToTab("openfoam_logs");
                } else if (data.type === "complete") {
                    appendLog(`<span class="info" style="color:#10b981">✨ ${data.message}</span>`);
                    ws.close();
                } else if (data.type === "error") {
                    appendLog(`<span class="error">❌ Error: ${data.message}</span>`);
                    ws.close();
                }
            };
            
            ws.onclose = () => {
                connectionDot.classList.remove("connected");
                connectionStatus.textContent = "Disconnected";
                runOpenfoamBtn.disabled = false;
                runOpenfoamBtn.textContent = "Run OpenFOAM";
                if (stopBtn) {
                    // 2026-08-15 – Gemini 3.5 Flash: Disable Stop button and restore default styles
                    stopBtn.disabled = true;
                    stopBtn.style.backgroundColor = "#4b5563";
                    stopBtn.style.cursor = "not-allowed";
                    stopBtn.textContent = "Stop Run / Generation";
                }
            };
        });

        // Postprocess Button Logic
        if (postprocessBtn) {
            postprocessBtn.addEventListener("click", () => {
                const outputDir = outputDirInput.value.trim();
                if (!outputDir) return;
                postprocessBtn.disabled = true;
                postprocessBtn.textContent = "Processing...";
                const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
                const wsUrl = `${protocol}//${window.location.host}/api/stream`;
                ws = new WebSocket(wsUrl);
                ws.onopen = () => {
                    connectionDot.classList.add("connected");
                    connectionStatus.textContent = "Connected";
                    ws.send(JSON.stringify({ action: "postprocess", output_dir: outputDir }));
                };
                ws.onmessage = (event) => {
                    const data = JSON.parse(event.data);
                    if (data.type === "info") {
                        appendLog(`<span class="info">ℹ️ ${data.message}</span>`);
                    } else if (data.type === "step") {
                        appendLog(`<span class="log-agent agent-Runner">[${data.agent}]</span> <span>${data.message}</span>`);
                    } else if (data.type === "complete") {
                        appendLog(`<span class="info" style="color:#10b981">✨ ${data.message}</span>`);
                        if (data.image_base64) {
                            appendLog(`<span class="info">📸 Visualizer Output:</span>`);
                            appendLog(`<img src="data:image/png;base64,${data.image_base64}" style="max-width: 100%; border-radius: 8px; margin-top: 10px; border: 1px solid rgba(255,255,255,0.1);">`);
                        }
                        ws.close();
                    } else if (data.type === "error") {
                        appendLog(`<span class="error">❌ Error: ${data.message}</span>`);
                        ws.close();
                    }
                };
                ws.onclose = () => {
                    connectionDot.classList.remove("connected");
                    connectionStatus.textContent = "Disconnected";
                    updateButtonStates();
                };
                ws.onerror = (err) => {
                    appendLog(`<span class="error">❌ WebSocket connection error. Ensure FastAPI backend is running.</span>`);
                };
            });
        }
    }

    // 2026-08-15 – Gemini 3.5 Flash: Stop / Cancel Button Logic
    if (stopBtn) {
        stopBtn.addEventListener("click", () => {
            stopBtn.disabled = true;
            stopBtn.textContent = "Stopping...";
            
            fetch("/api/stop", { method: "POST" })
                .then(resp => resp.json())
                .then(data => {
                    appendLog(`<span class="error">❌ Execution stopped by user.</span>`);
                })
                .catch(err => {
                    console.error("Failed to stop execution:", err);
                    appendLog(`<span class="error">❌ Failed to send stop request.</span>`);
                })
                .finally(() => {
                    if (ws) {
                        ws.close();
                    }
                });
        });
    }

    const terminalContainer = document.querySelector(".terminal-container");

    function getSiderWidth() {
        return siderPanelEl ? siderPanelEl.getBoundingClientRect().width || 400 : 400;
    }

    function openSider() {
        siderPanelEl.classList.add("open");
        siderToggleBtn.classList.add("hidden");
        // Push console left so it auto-resizes instead of being covered
        if (terminalContainer) {
            terminalContainer.style.marginRight = getSiderWidth() + "px";
        }
    }

    function closeSider() {
        siderPanelEl.classList.remove("open");
        siderToggleBtn.classList.remove("hidden");
        if (terminalContainer) {
            terminalContainer.style.marginRight = "0";
        }
    }

    if (siderToggleBtn && siderPanelEl && closeSiderBtn) {
        siderToggleBtn.addEventListener("click", openSider);
        closeSiderBtn.addEventListener("click", closeSider);
    }

    // Also update margin when sider is resized
    if (siderPanelEl) {
        const resizeObserver = new ResizeObserver(() => {
            if (siderPanelEl.classList.contains("open") && terminalContainer) {
                terminalContainer.style.marginRight = siderPanelEl.getBoundingClientRect().width + "px";
            }
        });
        resizeObserver.observe(siderPanelEl);
    }

    // 2026-08-15 – Gemini 3.5 Flash: Removed duplicate modelNameSelect declaration to prevent SyntaxError
    const chatModelSelect = document.getElementById("chat-model-select");

    function syncChatModelOptions() {
        if (!modelNameSelect || !chatModelSelect) return;
        const currentVal = chatModelSelect.value;
        chatModelSelect.innerHTML = '<option value="inherit">Use Global Model</option>';
        Array.from(modelNameSelect.options).forEach(opt => {
            const newOpt = document.createElement("option");
            newOpt.value = opt.value;
            newOpt.textContent = opt.textContent;
            chatModelSelect.appendChild(newOpt);
        });
        if (Array.from(chatModelSelect.options).some(o => o.value === currentVal)) {
            chatModelSelect.value = currentVal;
        } else {
            chatModelSelect.value = "inherit";
        }
    }
    
    if (modelNameSelect && chatModelSelect) {
        syncChatModelOptions();
        const observer = new MutationObserver(() => syncChatModelOptions());
        observer.observe(modelNameSelect, { childList: true });
    }

    // AI Assistant Chat Logic
    const chatInput = document.getElementById("chat-input");
    const chatSendBtn = document.getElementById("chat-send-btn");
    const chatMessages = document.getElementById("chat-messages");
    let chatWs = null;

    function renderMarkdownWithThink(text) {
        if (typeof marked === 'undefined') {
            // fallback if marked fails to load
            let fallback = text.replace(/<think>([\s\S]*?)<\/think>/g, '<details class="think-block"><summary>🧠 Thinking Process</summary><div class="think-content">$1</div></details>');
            if (fallback.includes("<think>") && !fallback.includes("</think>")) {
                fallback = fallback.replace(/<think>([\s\S]*)/g, '<details class="think-block" open><summary>🧠 Thinking Process</summary><div class="think-content">$1</div></details>');
            }
            return fallback.replace(/\n/g, "<br>");
        }
        
        // 1. Extract <think> blocks and replace with placeholders
        const thinkBlocks = [];
        let processedText = text.replace(/<think>([\s\S]*?)(?:<\/think>|$)/g, (match, p1) => {
            const id = `__THINK_${thinkBlocks.length}__`;
            thinkBlocks.push(p1.replace(/\n/g, "<br>"));
            return id;
        });
        
        // 2. Parse the remaining markdown
        let html = marked.parse(processedText);
        
        // 3. Re-insert think blocks as <details>
        thinkBlocks.forEach((content, i) => {
            const isOpen = (i === thinkBlocks.length - 1 && !text.includes("</think>")) ? "open" : "";
            const detailsHtml = `<details class="think-block" ${isOpen}><summary>🧠 Thinking Process</summary><div class="think-content">${content}</div></details>`;
            // Handle cases where marked wrapped the placeholder in <p>
            html = html.replace(`<p>__THINK_${i}__</p>`, detailsHtml);
            html = html.replace(`__THINK_${i}__`, detailsHtml);
        });
        
        return html;
    }

    function addChatMessage(role, text) {
        const div = document.createElement("div");
        div.className = `chat-message-${role}`;
        const bubble = document.createElement("div");
        bubble.className = "chat-bubble";
        
        bubble.innerHTML = renderMarkdownWithThink(text);
        div.appendChild(bubble);
        chatMessages.appendChild(div);
        chatMessages.scrollTop = chatMessages.scrollHeight;
        return bubble;
    }

    function sendChatMessage() {
        const text = chatInput.value.trim();
        if (!text) return;
        
        chatInput.value = "";
        addChatMessage("user", text);
        
        const apiBase = document.getElementById("api_base").value.trim();
        const modelName = document.getElementById("model_name").value.trim();
        const apiKey = document.getElementById("api_key").value.trim();
        const currentPrompt = promptInput.value.trim();
        const currentPostPrompt = document.getElementById("post_prompt") ? document.getElementById("post_prompt").value.trim() : "";
        const currentOutputDir = outputDirInput.value.trim();
        const openfoamStatus = document.getElementById("openfoam-status") ? document.getElementById("openfoam-status").textContent : "Unknown";
        
        const chatModelSelect = document.getElementById("chat-model-select");
        let chatModel = chatModelSelect ? chatModelSelect.value : "inherit";
        if (chatModel === "inherit") chatModel = modelName;

        if (chatWs) {
            chatWs.close();
        }

        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${protocol}//${window.location.host}/api/chat_stream`;
        
        chatWs = new WebSocket(wsUrl);
        
        let currentAssistantBubble = null;
        let assistantBuffer = "";
        
        chatSendBtn.disabled = true;
        chatSendBtn.textContent = "...";
        
        chatWs.onopen = () => {
            chatWs.send(JSON.stringify({ 
                message: text,
                current_prompt: currentPrompt,
                post_prompt: currentPostPrompt,
                output_dir: currentOutputDir,
                openfoam_status: openfoamStatus,
                api_base: apiBase,
                model: chatModel,
                api_key: apiKey
            }));
            currentAssistantBubble = addChatMessage("assistant", "Thinking...");
        };
        
        chatWs.onmessage = (event) => {
            const data = JSON.parse(event.data);
            if (data.type === "chunk") {
                if (assistantBuffer === "") {
                    assistantBuffer = data.text;
                } else {
                    assistantBuffer += data.text;
                }
                
                currentAssistantBubble.innerHTML = renderMarkdownWithThink(assistantBuffer);
                chatMessages.scrollTop = chatMessages.scrollHeight;
                
            } else if (data.type === "usage") {
                const tokenUsageSpan = document.getElementById("chat-token-usage");
                if (tokenUsageSpan) {
                    tokenUsageSpan.textContent = `Tokens: ${data.prompt} + ${data.completion}`;
                }
            } else if (data.type === "done") {
                chatWs.close();
            } else if (data.type === "error") {
                currentAssistantBubble.innerHTML += `<br><span style="color:#ef4444">Error: ${data.text}</span>`;
                chatWs.close();
            }
        };
        
        chatWs.onclose = () => {
            chatSendBtn.disabled = false;
            chatSendBtn.textContent = "Send";
            chatWs = null;
        };
    }

    if (chatSendBtn) {
        chatSendBtn.addEventListener("click", sendChatMessage);
    }
    if (chatInput) {
        chatInput.addEventListener("keydown", (e) => {
            if (e.key === "Enter") {
                sendChatMessage();
            }
        });
    }

    // 2026-08-15 – Gemini 3.5 Flash: File system action helper functions
    async function createItem(parentPath, name, isDir) {
        try {
            const resp = await fetch('/api/create_item', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ parent_path: parentPath, name, is_dir: isDir })
            });
            const data = await resp.json();
            if (data.status === "ok") {
                loadRootTree(outputDirInput.value.trim());
            } else {
                alert(`Error: ${data.message}`);
            }
        } catch (e) {
            alert("Network error creating item");
        }
    }

    async function pasteItem(srcPath, destDir) {
        try {
            const resp = await fetch('/api/copy_paste_file', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ src_path: srcPath, dest_dir: destDir })
            });
            const data = await resp.json();
            if (data.status === "ok") {
                // Clear clipboard after paste
                window.harnessfoamClipboard = null;
                loadRootTree(outputDirInput.value.trim());
            } else {
                alert(`Error: ${data.message}`);
            }
        } catch (e) {
            alert("Network error pasting item");
        }
    }

    async function renameItem(path, newName) {
        try {
            const resp = await fetch('/api/rename_file', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ path, new_name: newName })
            });
            const data = await resp.json();
            if (data.status === "ok") {
                loadRootTree(outputDirInput.value.trim());
            } else {
                alert(`Error: ${data.message}`);
            }
        } catch (e) {
            alert("Network error renaming item");
        }
    }

    async function deleteItem(path) {
        try {
            const resp = await fetch('/api/delete_file', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ path })
            });
            const data = await resp.json();
            if (data.status === "ok") {
                if (window.currentEditingFile === path) {
                    const tabFileViewer = document.getElementById("tab-file-viewer");
                    if (tabFileViewer) {
                        tabFileViewer.style.display = "none";
                        setTabActive('tab-console');
                    }
                }
                loadRootTree(outputDirInput.value.trim());
            } else {
                alert(`Error: ${data.message}`);
            }
        } catch (e) {
            alert("Network error deleting item");
        }
    }

    // Uptime Tracking Logic
    const uptimeElement = document.getElementById("uptime-status");
    if (uptimeElement) {
        const startTime = Date.now();
        setInterval(() => {
            const diff = Math.floor((Date.now() - startTime) / 1000);
            const hrs = String(Math.floor(diff / 3600)).padStart(2, '0');
            const mins = String(Math.floor((diff % 3600) / 60)).padStart(2, '0');
            const secs = String(diff % 60).padStart(2, '0');
            uptimeElement.textContent = `Uptime: ${hrs}:${mins}:${secs}`;
        }, 1000);
    }

});
