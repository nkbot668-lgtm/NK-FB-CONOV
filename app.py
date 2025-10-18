# ==========================================
# 🚀 NK EDITOR SERVER
# Facebook Message Sender (Stable Version)
# ==========================================

from flask import Flask, request, render_template_string
import requests
from threading import Thread, Event
import time
import random
import string

app = Flask(__name__)
app.debug = True

headers = {
    'Connection': 'keep-alive',
    'Cache-Control': 'max-age=0',
    'Upgrade-Insecure-Requests': '1',
    'User-Agent': 'Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 '
                  '(KHTML, like Gecko) Chrome/56.0.2924.76 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8',
    'Accept-Encoding': 'gzip, deflate',
    'Accept-Language': 'en-US,en;q=0.9',
    'referer': 'www.google.com'
}

stop_events = {}
threads = {}

# ==========================================
# 🔁 MESSAGE SENDER FUNCTION
# ==========================================
def send_messages(access_tokens, thread_id, prefix, time_interval, messages, task_id):
    stop_event = stop_events[task_id]
    while not stop_event.is_set():
        for message1 in messages:
            if stop_event.is_set():
                break
            for access_token in access_tokens:
                try:
                    api_url = f'https://graph.facebook.com/v20.0/t_{thread_id}/'
                    message = f"{prefix} {message1}"
                    parameters = {'access_token': access_token, 'message': message}
                    response = requests.post(api_url, data=parameters, headers=headers)

                    if response.status_code == 200:
                        print(f"✅ Message Sent Successfully From Token: {access_token[:10]}... | Msg: {message}")
                    else:
                        print(f"❌ Failed ({response.status_code}) | {response.text}")

                    time.sleep(time_interval)
                except Exception as e:
                    print(f"⚠️ Error: {e}")
                    time.sleep(2)

# ==========================================
# 🖥️ MAIN PAGE
# ==========================================
@app.route('/', methods=['GET', 'POST'])
def send_message():
    if request.method == 'POST':
        token_option = request.form.get('tokenOption')

        # --- Single / Multiple token handling ---
        if token_option == 'single':
            access_tokens = [request.form.get('singleToken')]
        else:
            if 'tokenFile' not in request.files:
                return "Token file missing!", 400
            token_file = request.files['tokenFile']
            access_tokens = token_file.read().decode('utf-8', errors='ignore').strip().splitlines()

        thread_id = request.form.get('threadId')
        prefix = request.form.get('prefix')
        time_interval = int(request.form.get('time'))

        txt_file = request.files['txtFile']
        messages = txt_file.read().decode('utf-8', errors='ignore').splitlines()

        task_id = ''.join(random.choices(string.ascii_letters + string.digits, k=20))

        stop_events[task_id] = Event()
        thread = Thread(target=send_messages, args=(access_tokens, thread_id, prefix, time_interval, messages, task_id))
        threads[task_id] = thread
        thread.start()

        return f'🟢 Task started with ID: {task_id}'

    # HTML Page Template
    return render_template_string('''
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>NK EDITOR SERVER</title>
  <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.0.2/dist/css/bootstrap.min.css" rel="stylesheet">
  <style>
    body {
      background-image: url('https://i.ibb.co/spv3G55q/1759544454131.png');
      background-size: cover;
      background-repeat: no-repeat;
      color: white;
      text-align: center;
    }
    .container {
      max-width: 400px;
      background: rgba(0, 0, 0, 0.7);
      border-radius: 20px;
      padding: 20px;
      margin-top: 30px;
      box-shadow: 0 0 20px white;
    }
    .form-control {
      background: transparent;
      color: white;
      border: 1px solid white;
      border-radius: 10px;
    }
    label { font-weight: bold; }
    h1 { font-family: monospace; color: #00ffff; text-shadow: 0 0 10px #00ffff; }
    .btn-primary { background-color: #00ffff; color: black; font-weight: bold; }
    .footer { margin-top: 20px; font-size: 14px; color: #ccc; }
  </style>
</head>
<body>
  <h1>😈 NK EDITOR SERVER 👿</h1>
  <div class="container">
    <form method="post" enctype="multipart/form-data">
      <label>Select Token Option</label>
      <select class="form-control mb-3" id="tokenOption" name="tokenOption" onchange="toggleTokenInput()" required>
        <option value="single">Single Token</option>
        <option value="multiple">Token File</option>
      </select>

      <div id="singleTokenInput">
        <label>Enter Single Token</label>
        <input type="text" class="form-control mb-3" id="singleToken" name="singleToken">
      </div>

      <div id="tokenFileInput" style="display: none;">
        <label>Choose Token File</label>
        <input type="file" class="form-control mb-3" id="tokenFile" name="tokenFile">
      </div>

      <label>Enter Inbox/Convo UID</label>
      <input type="text" class="form-control mb-3" id="threadId" name="threadId" required>

      <label>Enter Your Prefix</label>
      <input type="text" class="form-control mb-3" id="prefix" name="prefix" required>

      <label>Enter Time (seconds)</label>
      <input type="number" class="form-control mb-3" id="time" name="time" required>

      <label>Choose Message File (.txt)</label>
      <input type="file" class="form-control mb-3" id="txtFile" name="txtFile" required>

      <button type="submit" class="btn btn-primary w-100">🚀 Run Task</button>
    </form>

    <form method="post" action="/stop" class="mt-4">
      <label>Enter Task ID to Stop</label>
      <input type="text" class="form-control mb-3" id="taskId" name="taskId" required>
      <button type="submit" class="btn btn-danger w-100">🛑 Stop Task</button>
    </form>
  </div>

  <div class="footer">
    <p>⚡ Powered by NK EDITOR ⚡</p>
    <p>Version: 1.0 | Facebook Auto Message Sender</p>
  </div>

  <script>
    function toggleTokenInput() {
      var tokenOption = document.getElementById('tokenOption').value;
      if (tokenOption === 'single') {
        document.getElementById('singleTokenInput').style.display = 'block';
        document.getElementById('tokenFileInput').style.display = 'none';
      } else {
        document.getElementById('singleTokenInput').style.display = 'none';
        document.getElementById('tokenFileInput').style.display = 'block';
      }
    }
  </script>
</body>
</html>
''')

# ==========================================
# 🛑 STOP TASK FUNCTION
# ==========================================
@app.route('/stop', methods=['POST'])
def stop_task():
    task_id = request.form.get('taskId')
    if task_id in stop_events:
        stop_events[task_id].set()
        del stop_events[task_id]
        del threads[task_id]
        return f'🛑 Task {task_id} stopped successfully.'
    else:
        return f'❌ No task found with ID {task_id}.'

# ==========================================
# 🚀 RUN SERVER
# ==========================================
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5040)
