import requests
import urllib3
from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


def send_tg_message(text: str) -> bool:
    if TELEGRAM_BOT_TOKEN == "YOUR_BOT_TOKEN_HERE" or not TELEGRAM_BOT_TOKEN:
        print(f"[TG MOCK] {text}")
        return True

    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        response = requests.post(
            url,
            json={"chat_id": TELEGRAM_CHAT_ID, "text": text, "parse_mode": "HTML"},
            timeout=5,
            verify=False,
        )
        if response.status_code == 200:
            print(f"[TG OK] Сообщение отправлено: {text}")
        else:
            print(f"[TG FAIL] {response.status_code}: {response.text}")
        return True
    except Exception as e:
        print(e)
        return False