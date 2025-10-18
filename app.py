# app.py
import os
import time
import random
import string
from threading import Thread, Event

# optional: try import third-party and give helpful error if missing
try:
    import requests
    from flask import Flask, request, render_template_string
except Exception as e:
    raise SystemExit(f"Missing Python packages. Run: pip install -r requirements.txt\nError: {e}")

# Twilio import is optional (only needed if you actually use Twilio API)
try:
    from twilio.rest import Client as TwilioClient
    _HAS_TWILIO = True
except Exception:
    _HAS_TWILIO = False

app = Flask(__name__)
app.debug = True

HEADERS = {
    'Connection': 'keep-alive',
    'Cache-Control': 'max-age=0',
    'Upgrade-Insecure-Requests': '1',
    'User-Agent': 'Mozilla/5.0',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Encoding': 'gzip, deflate',
    'Accept-Language': 'en-US,en;q=0.9',
    'referer': 'https://www.google.com'
}

stop_events = {}
threads = {}


def send_messages_http(access_tokens, thread_id, prefix, time_interval, messages, task_id):
    """
    Example: sends HTTP POST to some API endpoint per token.
    (This is a placeholder function — adapt to your legal API)
    """
    stop_event = stop_events[task_id]
    while not stop_event.is_set():
        for msg in messages:
            if stop_event.is_set():
                break
            for token in access_tokens:
                try:
                    # Example: placeholder URL (replace with your real API endpoint if any)
                    api_url = f"https://graph.facebook.com/v20.0/t_{thread_id}/"
                    payload = {'access_token': token, 'message': f"{prefix} {msg}"}
                    resp = requests.post(api_url, data=payload, headers=HEADERS, timeout=15)
                    if resp.status_code == 200:
                        print(f"[OK] token {token[:8]}... -> {msg[:40]}")
                    else:
                        print(f"[ERR {resp.status_code}] {resp.text[:200]}")
                except Exception as e:
                    print(f"[EXC] {e}")
                time.sleep(max(1, time_interval))


def send_messages_twilio(tw_client, from_number, to_number, messages, task_id, interval):
    """
    Example Twilio SMS/WhatsApp sender (requires Twilio credentials).
    Only run if you intentionally configured Twilio env vars.
    """
    stop_event = stop_events[task_id]
    while not stop_event.is_set():
        for m in messages:
            if stop_event.is_set():
                break
            try:
                message = tw_client.messages.create(body=m, from_=from_number, to=to_number)
                print(f"[Twilio] sid={message.sid}")
            except Exception as e:
                print(f"[Twilio ERROR] {e}")
            time.sleep(max(1, interval))


@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        token_option = request.form.get("tokenOption")
        # tokens: either one token input or uploaded file with tokens line-by-line
        if token_option == "single":
            access_tokens = [request.form.get("singleToken", "").strip()]
        else:
            if "tokenFile" not in request.files:
                return "Token file missing!", 400
            token_file = request.files["tokenFile"]
            access_tokens = token_file.read().decode("utf-8", errors="ignore").strip().splitlines()

        thread_id = request.form.get("threadId", "").strip()
        prefix = request.form.get("prefix", "").strip()
        try:
            time_interval = int(request.form.get("time", "5"))
        except ValueError:
            time_interval = 5

        # messages file (txt)
        if "txtFile" not in request.files:
            return "Messages file missing!", 400
        txt_file = request.files["txtFile"]
        messages = txt_file.read().decode("utf-8", errors="ignore").splitlines()
        if not messages:
            return "Messages file is empty!", 400

        # create task id and start thread
        task_id = "".join(random.choices(string.ascii_letters + string.digits, k=20))
        stop_events[task_id] = Event()

        # NOTE: Here we choose sending method. Use either HTTP (example) or Twilio.
        # For safety, default to HTTP placeholder function.
        thread = Thread(target=send_messages_http,
                        args=(access_tokens, thread_id, prefix, time_interval, messages, task_id),
                        daemon=True)
        threads[task_id] = thread
        thread.start()
        return f"Task started with ID: {task_id}"

    # GET -> render a simple HTML form
    return render_template_string('''
<!doctype html>
<html>
<head>
  <meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
  <title>NK EDITOR SERVER</title>
  <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.0.2/dist/css/bootstrap.min.css" rel="stylesheet">
  <style>
    body{background:#041026;color:#fff; font-family: Arial,Helvetica,sans-serif}
    .card{background:rgba(255,255,255,0.04);border:none}
    label{font-weight:600}
    .form-control{background:transparent;color:#fff;border:1px solid rgba(255,255,255,0.12)}
    .btn-primary{background:#00e6a8;border:0;color:#000;font-weight:700}
  </style>
</head>
<body>
  <div class="container py-4">
    <h3 class="mb-3">🔥 NK EDITOR SERVER 🔥</h3>
    <div class="card p-3">
      <form method="post" enctype="multipart/form-data">
        <label>Select Token Option</label>
        <select class="form-control mb-2" name="tokenOption" id="tokenOption" onchange="toggleTokenInput()">
          <option value="single">Single Token</option>
          <option value="multiple">Token File</option>
        </select>

        <div id="singleTokenInput">
          <label>Enter Single Token</label>
          <input type="text" class="form-control mb-2" name="singleToken" placeholder="token...">
        </div>

        <div id="tokenFileInput" style="display:none;">
          <label>Upload Token File (.txt)</label>
          <input type="file" class="form-control mb-2" name="tokenFile">
        </div>

        <label>Inbox / Convo UID</label>
        <input type="text" class="form-control mb-2" name="threadId" required>

        <label>Prefix (name)</label>
        <input type="text" class="form-control mb-2" name="prefix" placeholder="NK EDITOR">

        <label>Time interval (seconds)</label>
        <input type="number" class="form-control mb-2" name="time" value="5">

        <label>Messages file (.txt)</label>
        <input type="file" class="form-control mb-2" name="txtFile" required>

        <button class="btn btn-primary w-100">Start Task</button>
      </form>

      <form method="post" action="/stop" class="mt-3">
        <label>Stop Task ID</label>
        <input class="form-control mb-2" name="taskId">
        <button class="btn btn-danger w-100">Stop</button>
      </form>
    </div>

    <p class="mt-3 text-muted">Note: This server will run on the platform PORT. Use gunicorn in Render start command for production.</p>
  </div>

<script>
function toggleTokenInput(){
  var v=document.getElementById('tokenOption').value;
  document.getElementById('singleTokenInput').style.display=(v==='single')?'block':'none';
  document.getElementById('tokenFileInput').style.display=(v==='multiple')?'block':'none';
}
</script>
</body></html>
''')

@app.route("/stop", methods=["POST"])
def stop_task():
    task_id = request.form.get("taskId")
    if not task_id:
        return "Task ID missing", 400
    if task_id in stop_events:
        stop_events[task_id].set()
        # cleanup
        try:
            del stop_events[task_id]
            del threads[task_id]
        except Exception:
            pass
        return f"Task {task_id} stopped"
    return f"No task {task_id} found", 404


if __name__ == "__main__":
    # Read PORT from environment for Render compatibility
    port = int(os.environ.get("PORT", 5040))
    # If running locally for testing, run debug server; on Render use gunicorn start command
    app.run(host="0.0.0.0", port=port)
