import os 
import requests
from flask import Flask, request

app = Flask(__name__)

# ===========================================
# 🔧 强制加载环境变量 + 错误检查
# ===========================================
TG_BOT_TOKEN = os.getenv("TG_BOT_TOKEN")
if not TG_BOT_TOKEN:
    raise ValueError("❌ TG_BOT_TOKEN 未设置！请在 Zeabur 环境变量中配置")

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
if not GITHUB_TOKEN:
    raise ValueError("❌ GITHUB_TOKEN 未设置！")

ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))
WEBHOOK_URL = os.getenv("WEBHOOK_URL")
if not WEBHOOK_URL:
    raise ValueError("❌ WEBHOOK_URL 未设置！格式：https://your-domain.zeabur.app")

# 解析仓库配置：myrepo:owner/repo1,blog:owner/repo2
REPO_CONFIG = {
    k.strip(): v.strip()
    for k, v in [
        x.split(":", 1) for x in os.getenv("REPO_CONFIG", "").split(",")
        if ":" in x and x.strip()
    ]
}

API_URL = f"https://api.telegram.org/bot{TG_BOT_TOKEN}"

# ===========================================
# 🖨️ 启动时打印调试信息
# ===========================================
print("🚀 === Bot 启动调试信息 ===")
print(f"✅ TG_BOT_TOKEN: {TG_BOT_TOKEN[:20]}... (长度: {len(TG_BOT_TOKEN)})")
print(f"✅ WEBHOOK_URL: {WEBHOOK_URL}")
print(f"✅ ADMIN_ID: {ADMIN_ID}")
print(f"✅ 仓库配置: {list(REPO_CONFIG.keys())}")
print(f"✅ Webhook 路由: /{TG_BOT_TOKEN}")
print("🚀 =====================")

# ===========================================
# 📤 发送消息函数
# ===========================================
def send_message(chat_id, text, reply_markup=None):
    try:
        data = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "HTML"
        }
        if reply_markup:
            data["reply_markup"] = reply_markup
        response = requests.post(f"{API_URL}/sendMessage", json=data, timeout=10)
        print(f"📤 发送消息状态: {response.status_code}")
    except Exception as e:
        print(f"❌ 发送消息失败: {e}")

# ===========================================
# 🔍 获取仓库默认分支
# ===========================================
def get_default_branch(repo):
    try:
        url = f"https://api.github.com/repos/{repo}"
        headers = {
            "Authorization": f"token {GITHUB_TOKEN}",
            "Accept": "application/vnd.github+json",
            "User-Agent": "tg-bot-controller"
        }
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            return response.json().get("default_branch", "main")
        print(f"⚠️ 获取默认分支失败: {response.status_code}")
        return "main"
    except Exception as e:
        print(f"⚠️ 获取默认分支异常: {e}")
        return "main"

# ===========================================
# 🎯 获取 Workflow 列表
# ===========================================
def get_workflows(repo):
    try:
        url = f"https://api.github.com/repos/{repo}/actions/workflows"
        headers = {
            "Authorization": f"token {GITHUB_TOKEN}",
            "Accept": "application/vnd.github+json",
            "User-Agent": "tg-bot-controller"
        }
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            data = response.json()
            workflows = []
            for wf in data.get("workflows", []):
                filename = wf["path"].split("/")[-1]
                wf_id = wf.get("id")
                wf_name = wf.get("name", filename)
                if filename:
                    workflows.append({
                        "filename": filename,
                        "id": wf_id,
                        "name": wf_name
                    })
            return workflows
        else:
            print(f"❌ 获取 workflows 失败: {response.status_code} {response.text}")
            return []
    except Exception as e:
        print(f"❌ 获取 workflows 失败: {e}")
        return []

# ===========================================
# ⚡ 触发 GitHub Workflow
# ===========================================
def trigger_workflow(chat_id, repo, workflow_filename):
    try:
        if not (workflow_filename.endswith(".yml") or workflow_filename.endswith(".yaml")):
            workflow_filename += ".yml"

        url = f"https://api.github.com/repos/{repo}/actions/workflows/{workflow_filename}/dispatches"
        headers = {
            "Authorization": f"token {GITHUB_TOKEN}",
            "Accept": "application/vnd.github+json",
            "User-Agent": "tg-bot-controller"
        }

        ref = get_default_branch(repo)
        data = {"ref": ref}

        response = requests.post(url, headers=headers, json=data, timeout=10)
        if response.status_code == 204:
            send_message(chat_id, f"✅ <b>触发成功！</b>\n📦 <code>{repo}/{workflow_filename}</code>\n🌿 分支: <code>{ref}</code>")
        else:
            error_text = response.text[:300] if response.text else "无错误信息"
            send_message(chat_id,
                         f"⚠️ <b>触发失败</b>\n📦 <code>{repo}/{workflow_filename}</code>\n🌿 分支: <code>{ref}</code>\n❌ 状态码: <code>{response.status_code}</code>\n📝 错误: <code>{error_text}</code>")
            print(f"触发失败详情: {response.status_code} {response.text}")
    except Exception as e:
        send_message(chat_id, f"💥 <b>触发异常</b>\n<code>{str(e)[:200]}</code>")
        print(f"触发异常: {e}")

# ===========================================
# 🩺 健康检查路由
# ===========================================
@app.route("/", methods=["GET"])
def health_check():
    return (
        f"🤖 <b>Bot 运行正常！</b>\n\n"
        f"✅ Webhook 路由: <code>/{TG_BOT_TOKEN}</code>\n"
        f"✅ 管理员 ID: <code>{ADMIN_ID}</code>\n"
        f"✅ 仓库数量: <code>{len(REPO_CONFIG)}</code>\n"
        f"📱 发送 <code>/run</code> 开始使用",
        200, {'Content-Type': 'text/html; charset=utf-8'}
    )

# ===========================================
# 🌐 Telegram Webhook
# ===========================================
@app.route(f"/{TG_BOT_TOKEN}", methods=["POST"])
def webhook():
    try:
        data = request.get_json(force=False, silent=True)
        if not data:
            print("⚠️ 空请求体")
            return "ok", 200, {'Content-Type': 'text/plain'}

        print(f"📨 收到更新: {data.get('update_id', 'unknown')}")

        # 处理回调按钮
        if "callback_query" in data:
            query = data["callback_query"]
            chat_id = query["message"]["chat"]["id"]
            user_id = query["from"]["id"]
            payload = query["data"]

            if user_id != ADMIN_ID:
                send_message(chat_id, "⛔ <b>无权限</b>")
                return "ok", 200, {'Content-Type': 'text/plain'}

            if payload.startswith("repo:"):
                repo_key = payload.split(":", 1)[1]
                repo_full = REPO_CONFIG.get(repo_key)
                if not repo_full:
                    send_message(chat_id, "❌ 仓库配置错误")
                    return "ok", 200, {'Content-Type': 'text/plain'}

                workflows = get_workflows(repo_full)
                if not workflows:
                    send_message(chat_id, f"❌ 仓库 <code>{repo_full}</code> 无 workflows")
                    return "ok", 200, {'Content-Type': 'text/plain'}

                keyboard = [[{"text": f"🚀 {wf['name']}",
                              "callback_data": f"wf:{repo_key}|{wf['filename']}"}]
                            for wf in workflows[:10]]

                send_message(chat_id,
                             f"📦 <b>选择 Workflow</b>\n\n<code>{repo_full}</code>",
                             {"inline_keyboard": keyboard})

            elif payload.startswith("wf:"):
                _, repo_key_wf = payload.split(":", 1)
                repo_key, workflow_filename = repo_key_wf.split("|", 1)
                repo_full = REPO_CONFIG.get(repo_key)
                if repo_full:
                    trigger_workflow(chat_id, repo_full, workflow_filename)

            return "ok", 200, {'Content-Type': 'text/plain'}

        # 处理文本消息
        if "message" in data and "text" in data["message"]:
            message = data["message"]
            chat_id = message["chat"]["id"]
            user_id = message["from"]["id"]
            text = message["text"].strip()

            if user_id != ADMIN_ID:
                send_message(chat_id, "⛔ <b>仅管理员可用</b>")
                return "ok", 200, {'Content-Type': 'text/plain'}

            if text in ("/run", "/start"):
                if not REPO_CONFIG:
                    send_message(chat_id,
                                 "❌ <b>未配置仓库</b>\n\n请在 Zeabur 环境变量设置 <code>REPO_CONFIG</code>\n格式: <code>myrepo:owner/repo,blog:owner/blog</code>")
                else:
                    keyboard = [[{"text": f"📁 {alias}", "callback_data": f"repo:{alias}"}]
                                for alias in REPO_CONFIG.keys()]
                    send_message(chat_id,
                                 "🤖 <b>GitHub Actions 触发器</b>\n\n👇 请选择仓库",
                                 {"inline_keyboard": keyboard})

            elif text == "/status":
                send_message(chat_id,
                             f"✅ <b>Bot 状态</b>\n\n🔗 Webhook: <code>✅ 已连接</code>\n📦 仓库: <code>{len(REPO_CONFIG)}</code>\n👤 管理员: <code>{ADMIN_ID}</code>")

        return "ok", 200, {'Content-Type': 'text/plain'}

    except Exception as e:
        print(f"💥 Webhook 异常: {e}")
        print(f"原始数据: {request.data[:200]}...")
        return "error", 200, {'Content-Type': 'text/plain'}

# ===========================================
# 🚀 应用启动
# ===========================================
if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))

    print(f"🌐 启动 Webhook: {WEBHOOK_URL}/{TG_BOT_TOKEN}")

    # 设置 Telegram Webhook
    try:
        webhook_url = f"{WEBHOOK_URL}/{TG_BOT_TOKEN}"
        response = requests.get(f"{API_URL}/setWebhook", params={"url": webhook_url}, timeout=10)
        result = response.json()
        print(f"🔗 Webhook 设置: {result}")
    except Exception as e:
        print(f"⚠️ Webhook 设置失败: {e}")

    print(f"🎯 Flask 启动: 0.0.0.0:{port}")
    app.run(host="0.0.0.0", port=port, debug=False)
