from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
import requests
import json
import asyncio
import uvicorn

app = FastAPI(title="Alert Agent Frontend")
DISCORD_WEBHOOK_URL = "https://discord.com/api/webhooks/1547479599074779216/gEpmw1XRxwJGlQ3mu9F5cAnBQc-e_MWL2TfDGlGXUSOcGnrCTMS_dDYduCmQLzEKVbvo"

# Store recent alerts in memory
recent_alerts = []

html_template = """
<!DOCTYPE html>
<html>
<head>
    <title>🚨 Alert Agent Monitor</title>
    <style>
        body { font-family: 'Inter', sans-serif; background-color: #0f172a; color: #f8fafc; padding: 2rem; margin: 0; }
        h1 { text-align: center; color: #38bdf8; font-weight: 600; margin-bottom: 2rem; }
        .alert-box { background: #1e293b; border-left: 4px solid #ef4444; padding: 1.5rem; margin-bottom: 1rem; border-radius: 6px; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1); }
        .timestamp { color: #94a3b8; font-size: 0.85rem; margin-bottom: 0.5rem; }
        pre { background: #0f172a; padding: 1rem; border-radius: 4px; overflow-x: auto; color: #a5b4fc; }
        .empty { text-align: center; color: #64748b; font-style: italic; margin-top: 3rem; }
    </style>
    <script>
        // Auto-refresh the page every 3 seconds to show new alerts
        setInterval(() => window.location.reload(), 3000);
    </script>
</head>
<body>
    <h1>🚨 Alert Agent Live Monitor</h1>
    <div id="alerts">
        {content}
    </div>
</body>
</html>
"""

@app.get("/", response_class=HTMLResponse)
async def dashboard():
    if not recent_alerts:
        content = '<div class="empty">Waiting for alerts to arrive...</div>'
    else:
        content = ""
        for alert in reversed(recent_alerts):
            content += f'''
            <div class="alert-box">
                <div class="timestamp">Received just now</div>
                <pre>{json.dumps(alert, indent=2)}</pre>
            </div>
            '''
    return html_template.replace("{content}", content)

@app.post("/process_alert")
async def process_alert(request: Request):
    try:
        data = await request.form()
        data = dict(data)
    except:
        data = await request.json()

    print("\n" + "="*50)
    print(">>> ALERT AGENT RECEIVED NEW DATA <<<")
    print(json.dumps(data, indent=2))
    print("="*50 + "\n")

    # Add to memory for the frontend
    recent_alerts.append(data)
    if len(recent_alerts) > 10:
        recent_alerts.pop(0)

    # Send to Discord
    discord_payload = {
        "content": f"🚨 **New Alert Received!** 🚨\n```json\n{json.dumps(data, indent=2)}\n```"
    }
    try:
        requests.post(DISCORD_WEBHOOK_URL, json=discord_payload)
    except Exception as e:
        print(f"❌ Failed to send to Discord: {e}")

    return {"status": "success", "message": "Alert processed and sent to Discord!"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8001)
