/* 2026-08-15 (gemini-2.5-pro) */
document.addEventListener("DOMContentLoaded", () => {
    const runBtn = document.getElementById("run-btn");
    const promptInput = document.getElementById("prompt");
    const outputDirInput = document.getElementById("output_dir");
    const consoleOutput = document.getElementById("console-output");
    const connectionDot = document.getElementById("connection-dot");
    const connectionStatus = document.getElementById("connection-status");
    
    let ws = null;

    function appendLog(html) {
        const div = document.createElement("div");
        div.className = "log-entry";
        div.innerHTML = html;
        consoleOutput.appendChild(div);
        consoleOutput.scrollTop = consoleOutput.scrollHeight;
    }
    
    // Add logic for Browse button
    const browseBtn = document.getElementById("browse-btn");
    if (browseBtn) {
        browseBtn.addEventListener("click", async () => {
            try {
                const response = await fetch('/api/browse_folder');
                const data = await response.json();
                if (data.path) {
                    outputDirInput.value = data.path;
                }
            } catch (err) {
                console.error("Failed to browse folder:", err);
            }
        });
    }

    runBtn.addEventListener("click", () => {
        const prompt = promptInput.value.trim();
        const outputDir = outputDirInput.value.trim();
        
        if (!prompt) {
            appendLog(`<span class="error">[Error] Simulation requirement cannot be empty.</span>`);
            return;
        }
        
        runBtn.disabled = true;
        runBtn.textContent = "Processing...";
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
                const agentClass = `agent-${data.agent.split(" ")[0]}`;
                appendLog(`<span class="log-agent ${agentClass}">[${data.agent}]</span> <span>${data.message}</span>`);
            } else if (data.type === "complete") {
                appendLog(`<span class="info" style="color:#10b981">✨ ${data.message}</span>`);
                appendLog(`<span class="info">Output saved to: <strong>${data.directory}</strong></span>`);
                
                if (data.files && data.files.length > 0) {
                    const fileList = data.files.map(f => `<div>📄 ${f}</div>`).join("");
                    appendLog(`<div class="file-list">${fileList}</div>`);
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
            runBtn.disabled = false;
            runBtn.textContent = "Initialize Simulation";
        };
        
        ws.onerror = (err) => {
            appendLog(`<span class="error">❌ WebSocket connection error. Ensure FastAPI backend is running.</span>`);
        };
    });
});
