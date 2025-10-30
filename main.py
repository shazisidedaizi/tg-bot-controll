import os
import requests
from flask import Flask, request

app = Flask(__name__)

TG_BOT_TOKEN = os.getenv("TG_BOT_TOKEN")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))
WEBHOOK_URL = os.getenv("WEBHOOK_URL")

REPO_CONFIG = {
    k.strip(): v.strip()
    for k, v in [
        x.split(":", 1) for x in os.getenv("REPO_CONFIG", "").split(",") if ":" in x
    ]
}

API_URL = f"https://api.telegram.org/bot{TG_BOT_TOKEN}"

def send_message(chat_id, text, reply_markup=None):
    data = {"chat_id": chat_id, "text": text, "parse_mode": "HTML"}
    if reply_markup:
        data["reply_markup"] = reply_markup
    requests.post(f"{API_URL}/sendMessage", json=data)

def trigger_workflow(chat_id, repo, workflow):
    url = f"https://api.github.com/repos/{repo}/actions/workflows/{workflow}/dispatches"
    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json",
    }
    data = {"ref": "main"}
    r = requests.post(url, headers=headers, json=data)
    if r.status_code == 204:
        send_message(chat_id, f"✅ 成功触发：<b>{repo}/{workflow}</b>")
    else:
        send_message(chat_id, f"⚠️ 触发失败 ({r.status_code})\n<code>{r.text}</code>")

@app.route(f"/{TG_BOT_TOKEN}", methods=["POST"])
def webhook():
    data = request.get_json()
    if not data:
        return "ok"

    if "callback_query" in data:
        q = data["callback_query"]
        chat_id = q["message"]["chat"]["id"]
        from_id = q["from"]["id"]
        payload = q["data"]

        if from_id != ADMIN_ID:
            send_message(chat_id, "⛔ 你没有权限。")
            return "ok"

        if payload.startswith("repo:"):
            repo_key = payload.split(":", 1)[1]
            repo = REPO_CONFIG.get(repo_key)
            workflows = get_workflows(repo)
            keyboard = [
                [{"text": f"🟢 {wf}", "callback_data": f"wf:{repo}|{wf}"}]
                for wf in workflows
            ]
            send_message(chat_id, f"📦 选择要触发的 workflow：\n<code>{repo}</code>",
                         reply_markup={"inline_keyboard": keyboard})
        elif payload.startswith("wf:"):
            repo, wf = payload.split(":", 1)[1].split("|")
            trigger_workflow(chat_id, repo, wf)
        return "ok"

    if "message" in data:
        msg = data["message"]
        chat_id = msg["chat"]["id"]
        from_id = msg["from"]["id"]
        text = msg.get("text", "")

        if from_id != ADMIN_ID:
            send_message(chat_id, "⛔ 未授权用户。")
            return "ok"

        if text == "/run":
            keyboard = [
                [{"text": f"📁 {alias}", "callback_data": f"repo:{alias}"}]
                for alias in REPO_CONFIG
            ]
            send_message(chat_id, "请选择要触发的仓库：",
                         reply_markup={"inline_keyboard": keyboard})
    return "ok"

def get_workflows(repo):
    url = f"https://api.github.com/repos/{repo}/actions/workflows"
    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json",
    }
    r = requests.get(url, headers=headers)
    if r.status_code == 200:
        data = r.json()
        return [wf["path"].split("/")[-1] for wf in data.get("workflows", [])]
    return []

if __name__ == "__main__":
    if WEBHOOK_URL:
        webhook_url = f"{WEBHOOK_URL}/{TG_BOT_TOKEN}"
        r = requests.get(f"{API_URL}/setWebhook", params={"url": webhook_url})
        print("Webhook 设置结果:", r.text)
    app.run(host="0.0.0.0", port=8000)
