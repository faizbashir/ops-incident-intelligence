from flask import Flask, request, jsonify, render_template_string
from google import genai
from google.cloud import bigquery
import os, re

app = Flask(__name__)
PROJECT_ID = "ottawa-police-496223"
client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
bq = bigquery.Client(project=PROJECT_ID)

SCHEMA = """
BigQuery project: ottawa-police-496223, dataset: ops_intelligence
Tables/views:
- incidents: incident_id, report_date, incident_type, district, neighbourhood, severity (LOW/MEDIUM/HIGH/CRITICAL), status (OPEN/UNDER_INVESTIGATION/CLOSED), officers_assigned, resolution_hours
- v_incidents_by_district: district, total_incidents, high_severity_count, open_cases, closed_cases, avg_resolution_hours, clearance_rate_pct (last 30 days)
- v_daily_trend: report_date, daily_total, theft_count, assault_count, vandalism_count, critical_count
- v_open_priority_cases: open HIGH/CRITICAL cases with hours_open, district, neighbourhood, incident_type
Districts: Central, East, West, South, North, Rideau-Rockcliffe
Return ONLY valid standard SQL. No markdown. Use: `ottawa-police-496223.ops_intelligence.table_name`
"""

HTML = '''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>OPS Incident Intelligence</title>
<link href="https://fonts.googleapis.com/css2?family=Share+Tech+Mono&family=Rajdhani:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>
  :root {
    --bg: #050a0f;
    --panel: #080e15;
    --border: #0d2137;
    --accent: #0066cc;
    --accent2: #00aaff;
    --alert: #ff3b30;
    --success: #00e676;
    --text: #c8dff0;
    --dim: #4a6a85;
    --mono: "Share Tech Mono", monospace;
    --ui: "Rajdhani", sans-serif;
  }
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body {
    background: var(--bg);
    color: var(--text);
    font-family: var(--ui);
    min-height: 100vh;
    overflow-x: hidden;
  }
  body::before {
    content: "";
    position: fixed;
    inset: 0;
    background: radial-gradient(ellipse at 20% 50%, rgba(0,102,204,0.06) 0%, transparent 60%),
                radial-gradient(ellipse at 80% 20%, rgba(0,170,255,0.04) 0%, transparent 50%);
    pointer-events: none;
    z-index: 0;
  }

  /* HEADER */
  header {
    position: relative;
    z-index: 10;
    display: flex;
    align-items: center;
    gap: 20px;
    padding: 18px 32px;
    border-bottom: 1px solid var(--border);
    background: rgba(8,14,21,0.95);
    backdrop-filter: blur(10px);
  }
  .badge {
    width: 48px; height: 48px;
    background: linear-gradient(135deg, #0055aa, #0088dd);
    clip-path: polygon(50% 0%, 93% 25%, 93% 75%, 50% 100%, 7% 75%, 7% 25%);
    display: flex; align-items: center; justify-content: center;
    font-size: 20px; flex-shrink: 0;
    box-shadow: 0 0 20px rgba(0,136,221,0.4);
    animation: badgePulse 3s ease-in-out infinite;
  }
  @keyframes badgePulse {
    0%, 100% { box-shadow: 0 0 20px rgba(0,136,221,0.4); }
    50% { box-shadow: 0 0 35px rgba(0,170,255,0.7); }
  }
  .header-text h1 {
    font-size: 20px; font-weight: 700; letter-spacing: 2px;
    color: #fff; text-transform: uppercase;
  }
  .header-text p {
    font-size: 12px; color: var(--dim); letter-spacing: 1px;
    font-family: var(--mono);
  }
  .status-bar {
    margin-left: auto;
    display: flex; align-items: center; gap: 24px;
  }
  .status-pill {
    display: flex; align-items: center; gap: 8px;
    font-family: var(--mono); font-size: 11px; color: var(--dim);
  }
  .dot {
    width: 7px; height: 7px; border-radius: 50%;
    background: var(--success);
    box-shadow: 0 0 8px var(--success);
    animation: blink 2s ease-in-out infinite;
  }
  @keyframes blink {
    0%, 100% { opacity: 1; } 50% { opacity: 0.3; }
  }

  /* MAIN LAYOUT */
  .layout {
    position: relative; z-index: 1;
    display: grid;
    grid-template-columns: 280px 1fr;
    height: calc(100vh - 85px);
  }

  /* SIDEBAR */
  .sidebar {
    border-right: 1px solid var(--border);
    background: var(--panel);
    padding: 24px 0;
    overflow-y: auto;
  }
  .sidebar-label {
    font-family: var(--mono); font-size: 10px;
    color: var(--dim); letter-spacing: 2px;
    padding: 0 20px 12px; text-transform: uppercase;
  }
  .quick-btn {
    display: block; width: 100%;
    padding: 12px 20px;
    text-align: left;
    background: none; border: none;
    color: var(--text); font-family: var(--ui);
    font-size: 13px; font-weight: 500;
    cursor: pointer; transition: all 0.2s;
    border-left: 3px solid transparent;
    line-height: 1.4;
  }
  .quick-btn:hover {
    background: rgba(0,102,204,0.08);
    border-left-color: var(--accent2);
    color: #fff;
  }
  .quick-btn .qicon { font-size: 16px; margin-right: 10px; }
  .sidebar-divider {
    height: 1px; background: var(--border);
    margin: 16px 20px;
  }
  .district-grid {
    padding: 0 20px;
    display: grid; grid-template-columns: 1fr 1fr; gap: 8px;
  }
  .district-chip {
    background: rgba(13,33,55,0.6);
    border: 1px solid var(--border);
    border-radius: 4px;
    padding: 8px 10px;
    font-family: var(--mono); font-size: 10px;
    color: var(--dim);
  }
  .district-chip span { display: block; color: var(--accent2); font-size: 16px; font-weight: bold; }

  /* CHAT AREA */
  .chat-area {
    display: flex; flex-direction: column;
    background: var(--bg);
  }
  .messages {
    flex: 1; overflow-y: auto;
    padding: 32px;
    display: flex; flex-direction: column; gap: 24px;
    scroll-behavior: smooth;
  }
  .messages::-webkit-scrollbar { width: 4px; }
  .messages::-webkit-scrollbar-track { background: transparent; }
  .messages::-webkit-scrollbar-thumb { background: var(--border); border-radius: 2px; }

  /* WELCOME */
  .welcome {
    text-align: center; padding: 60px 20px;
    animation: fadeIn 0.6s ease;
  }
  .welcome .w-badge {
    width: 80px; height: 80px; margin: 0 auto 24px;
    background: linear-gradient(135deg, #003d80, #0077cc);
    clip-path: polygon(50% 0%, 93% 25%, 93% 75%, 50% 100%, 7% 75%, 7% 25%);
    display: flex; align-items: center; justify-content: center;
    font-size: 32px;
    box-shadow: 0 0 40px rgba(0,119,204,0.3);
  }
  .welcome h2 { font-size: 28px; color: #fff; font-weight: 700; margin-bottom: 8px; }
  .welcome p { color: var(--dim); font-size: 15px; max-width: 400px; margin: 0 auto; }
  .welcome .hint {
    margin-top: 32px;
    font-family: var(--mono); font-size: 12px;
    color: var(--dim); letter-spacing: 1px;
  }

  /* MESSAGES */
  .msg { display: flex; gap: 14px; animation: slideUp 0.3s ease; }
  @keyframes slideUp {
    from { opacity: 0; transform: translateY(10px); }
    to { opacity: 1; transform: translateY(0); }
  }
  @keyframes fadeIn {
    from { opacity: 0; } to { opacity: 1; }
  }
  .msg-icon {
    width: 36px; height: 36px; border-radius: 50%;
    display: flex; align-items: center; justify-content: center;
    font-size: 16px; flex-shrink: 0; margin-top: 4px;
  }
  .msg.user .msg-icon { background: rgba(0,102,204,0.2); border: 1px solid rgba(0,102,204,0.4); }
  .msg.agent .msg-icon { background: rgba(0,170,255,0.1); border: 1px solid rgba(0,170,255,0.3); }
  .msg-body { flex: 1; }
  .msg-label {
    font-family: var(--mono); font-size: 10px;
    color: var(--dim); letter-spacing: 1px; margin-bottom: 8px;
    text-transform: uppercase;
  }
  .msg.user .msg-label { color: rgba(0,170,255,0.6); }
  .msg-bubble {
    padding: 16px 20px;
    border-radius: 2px 12px 12px 12px;
    font-size: 15px; line-height: 1.6; font-weight: 500;
  }
  .msg.user .msg-bubble {
    background: rgba(0,102,204,0.12);
    border: 1px solid rgba(0,102,204,0.25);
    color: #d0e8ff;
  }
  .msg.agent .msg-bubble {
    background: rgba(8,20,35,0.8);
    border: 1px solid var(--border);
    color: var(--text);
  }
  .sql-block {
    margin-top: 12px; padding: 12px 16px;
    background: rgba(0,0,0,0.4);
    border-left: 3px solid var(--accent);
    border-radius: 0 4px 4px 0;
    font-family: var(--mono); font-size: 11px;
    color: #4a9eff; line-height: 1.7;
    overflow-x: auto; white-space: pre;
  }
  .sql-label {
    font-family: var(--mono); font-size: 10px;
    color: var(--accent); letter-spacing: 2px;
    margin-bottom: 6px; text-transform: uppercase;
  }
  .alert-badge {
    display: inline-flex; align-items: center; gap: 6px;
    background: rgba(255,59,48,0.15);
    border: 1px solid rgba(255,59,48,0.4);
    color: #ff6b6b; border-radius: 4px;
    padding: 4px 10px; font-size: 12px;
    font-family: var(--mono); margin-top: 10px;
  }
  .typing {
    display: flex; align-items: center; gap: 6px;
    padding: 16px 20px;
    background: rgba(8,20,35,0.8);
    border: 1px solid var(--border);
    border-radius: 2px 12px 12px 12px;
    width: fit-content;
  }
  .typing-dot {
    width: 6px; height: 6px; border-radius: 50%;
    background: var(--accent2);
    animation: typingBounce 1.2s ease-in-out infinite;
  }
  .typing-dot:nth-child(2) { animation-delay: 0.2s; }
  .typing-dot:nth-child(3) { animation-delay: 0.4s; }
  @keyframes typingBounce {
    0%, 60%, 100% { transform: translateY(0); opacity: 0.4; }
    30% { transform: translateY(-6px); opacity: 1; }
  }

  /* INPUT */
  .input-area {
    padding: 20px 32px 28px;
    border-top: 1px solid var(--border);
    background: rgba(8,14,21,0.9);
    backdrop-filter: blur(10px);
  }
  .input-row {
    display: flex; gap: 12px; align-items: flex-end;
    max-width: 900px; margin: 0 auto;
  }
  textarea {
    flex: 1; background: rgba(13,33,55,0.5);
    border: 1px solid var(--border);
    border-radius: 8px; padding: 14px 18px;
    color: var(--text); font-family: var(--ui);
    font-size: 15px; font-weight: 500;
    resize: none; outline: none;
    transition: border-color 0.2s;
    min-height: 52px; max-height: 120px;
    line-height: 1.5;
  }
  textarea:focus { border-color: var(--accent); }
  textarea::placeholder { color: var(--dim); }
  .send-btn {
    width: 52px; height: 52px; border-radius: 8px;
    background: linear-gradient(135deg, #0055aa, #0088dd);
    border: none; cursor: pointer;
    display: flex; align-items: center; justify-content: center;
    font-size: 20px; transition: all 0.2s;
    flex-shrink: 0;
    box-shadow: 0 4px 15px rgba(0,102,204,0.3);
  }
  .send-btn:hover { transform: translateY(-2px); box-shadow: 0 6px 20px rgba(0,102,204,0.5); }
  .send-btn:active { transform: translateY(0); }
  .send-btn:disabled { opacity: 0.4; cursor: not-allowed; transform: none; }
  .input-hint {
    text-align: center; margin-top: 10px;
    font-family: var(--mono); font-size: 10px;
    color: var(--dim); letter-spacing: 1px;
  }
</style>
</head>
<body>
<header>
  <div class="badge">🛡️</div>
  <div class="header-text">
    <h1>Ottawa Police Service</h1>
    <p>INCIDENT INTELLIGENCE AGENT &nbsp;·&nbsp; POWERED BY GEMINI + BIGQUERY</p>
  </div>
  <div class="status-bar">
    <div class="status-pill"><div class="dot"></div> SYSTEM ONLINE</div>
    <div class="status-pill" style="color:var(--accent2)">▣ 500 RECORDS LIVE</div>
    <div class="status-pill">◈ northamerica-northeast1</div>
  </div>
</header>

<div class="layout">
  <div class="sidebar">
    <div class="sidebar-label">Quick Queries</div>
    <button class="quick-btn" onclick="sendQuick(this.dataset.q)" data-q="Show me incident counts by district for the last 30 days"><span class="qicon">📊</span>Incidents by District</button>
    <button class="quick-btn" onclick="sendQuick(this.dataset.q)" data-q="Which district has the most open high priority cases right now?"><span class="qicon">🚨</span>Open Priority Cases</button>
    <button class="quick-btn" onclick="sendQuick(this.dataset.q)" data-q="Are there any unusual spikes in incident volume in the last 7 days?"><span class="qicon">⚠️</span>Anomaly Detection</button>
    <button class="quick-btn" onclick="sendQuick(this.dataset.q)" data-q="What are the top 3 incident types across all districts?"><span class="qicon">📋</span>Top Incident Types</button>
    <button class="quick-btn" onclick="sendQuick(this.dataset.q)" data-q="What is the average resolution time by district?"><span class="qicon">⏱️</span>Resolution Times</button>
    <button class="quick-btn" onclick="sendQuick(this.dataset.q)" data-q="Show me clearance rates by district"><span class="qicon">✅</span>Clearance Rates</button>
    <div class="sidebar-divider"></div>
    <div class="sidebar-label">Districts</div>
    <div class="district-grid" id="districtGrid">
      <div class="district-chip">Central<span id="c-central">–</span></div>
      <div class="district-chip">East<span id="c-east">–</span></div>
      <div class="district-chip">West<span id="c-west">–</span></div>
      <div class="district-chip">South<span id="c-south">–</span></div>
      <div class="district-chip">North<span id="c-north">–</span></div>
      <div class="district-chip">Rideau<span id="c-rideau">–</span></div>
    </div>
  </div>

  <div class="chat-area">
    <div class="messages" id="messages">
      <div class="welcome" id="welcome">
        <div class="w-badge">🛡️</div>
        <h2>Incident Intelligence Agent</h2>
        <p>Ask questions about incident trends, district performance, and active cases across Ottawa.</p>
        <div class="hint">▸ SELECT A QUICK QUERY OR TYPE BELOW TO BEGIN</div>
      </div>
    </div>
    <div class="input-area">
      <div class="input-row">
        <textarea id="input" placeholder="Ask about incidents, districts, trends, anomalies..." rows="1"
          onkeydown="if(event.key==='Enter'&&!event.shiftKey){event.preventDefault();sendMsg()}"
          oninput="this.style.height='auto';this.style.height=this.scrollHeight+'px'"></textarea>
        <button class="send-btn" id="sendBtn" onclick="sendMsg()">➤</button>
      </div>
      <div class="input-hint">ENTER TO SEND &nbsp;·&nbsp; SHIFT+ENTER FOR NEW LINE &nbsp;·&nbsp; LIVE DATA FROM BIGQUERY</div>
    </div>
  </div>
</div>

<script>
const messages = document.getElementById("messages");
const input = document.getElementById("input");
const sendBtn = document.getElementById("sendBtn");

function addMsg(role, content, sql="") {
  const welcome = document.getElementById("welcome");
  if (welcome) welcome.remove();
  const div = document.createElement("div");
  div.className = `msg ${role}`;
  const isAlert = content.toLowerCase().includes("spike") || content.toLowerCase().includes("urgent") || content.toLowerCase().includes("critical");
  div.innerHTML = `
    <div class="msg-icon">${role === "user" ? "👤" : "🛡️"}</div>
    <div class="msg-body">
      <div class="msg-label">${role === "user" ? "ANALYST" : "OPS INTELLIGENCE AGENT"}</div>
      <div class="msg-bubble">
        ${sql ? `<div class="sql-label">▸ SQL GENERATED</div><div class="sql-block">${sql}</div><br>` : ""}
        ${content}
        ${isAlert && role === "agent" ? '<br><div class="alert-badge">⚠ OPERATIONAL FLAG RAISED</div>' : ""}
      </div>
    </div>`;
  messages.appendChild(div);
  messages.scrollTop = messages.scrollHeight;
}

function addTyping() {
  const div = document.createElement("div");
  div.className = "msg agent"; div.id = "typing";
  div.innerHTML = `
    <div class="msg-icon">🛡️</div>
    <div class="msg-body">
      <div class="msg-label">OPS INTELLIGENCE AGENT</div>
      <div class="typing"><div class="typing-dot"></div><div class="typing-dot"></div><div class="typing-dot"></div></div>
    </div>`;
  messages.appendChild(div);
  messages.scrollTop = messages.scrollHeight;
}

async function sendMsg() {
  const q = input.value.trim();
  if (!q || sendBtn.disabled) return;
  input.value = ""; input.style.height = "auto";
  sendBtn.disabled = true;
  addMsg("user", q);
  addTyping();
  try {
    const res = await fetch("/query", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({question: q})
    });
    const data = await res.json();
    document.getElementById("typing")?.remove();
    addMsg("agent", data.answer, data.sql || "");
    if (data.districts) updateDistricts(data.districts);
  } catch(e) {
    document.getElementById("typing")?.remove();
    addMsg("agent", "Connection error. Please try again.");
  }
  sendBtn.disabled = false;
  input.focus();
}

function sendQuick(q) { input.value = q; sendMsg(); }

function updateDistricts(d) {
  const map = {"Central":"c-central","East":"c-east","West":"c-west","South":"c-south","North":"c-north","Rideau-Rockcliffe":"c-rideau"};
  d.forEach(r => { const el = document.getElementById(map[r.district]); if(el) el.textContent = r.total_incidents; });
}

// Load district counts on start
fetch("/districts").then(r=>r.json()).then(d=>updateDistricts(d)).catch(()=>{});
</script>
</body>
</html>'''

@app.route("/")
def index():
    return render_template_string(HTML)

@app.route("/districts")
def districts():
    try:
        rows = list(bq.query("SELECT district, total_incidents FROM `ottawa-police-496223.ops_intelligence.v_incidents_by_district` ORDER BY total_incidents DESC").result())
        return jsonify([dict(r) for r in rows])
    except:
        return jsonify([])

@app.route("/query", methods=["POST"])
def query():
    question = request.json.get("question","")
    try:
        sql_raw = client.models.generate_content(
            model="gemini-2.5-flash-lite",
            contents=f"{SCHEMA}\nWrite SQL to answer: {question}"
        ).text.strip()
        sql = re.sub(r"```sql|```","", sql_raw).strip()
        rows = list(bq.query(sql).result())
        rows_text = "\n".join([str(dict(r)) for r in rows[:15]])
        answer = client.models.generate_content(
            model="gemini-2.5-flash-lite",
            contents=f"You are an AI analyst for Ottawa Police Service. Question: {question}\nData: {rows_text}\nBrief operational briefing, plain English, under 80 words. Flag anything urgent with specific numbers."
        ).text.strip()
        districts = []
        if "district" in question.lower() or "all" in question.lower():
            try:
                drows = list(bq.query("SELECT district, total_incidents FROM `ottawa-police-496223.ops_intelligence.v_incidents_by_district`").result())
                districts = [dict(r) for r in drows]
            except: pass
        return jsonify({"answer": answer, "sql": sql, "districts": districts})
    except Exception as e:
        return jsonify({"answer": f"Query error: {str(e)}", "sql": "", "districts": []})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080, debug=False)
