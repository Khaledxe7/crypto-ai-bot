#!/usr/bin/env python3
import os
import time
import requests

TOKEN = "8497098367:AAFNrEefvzzTcQGAmdAIdYaWhQJSrmqh5zs"
CHAT_ID = "900307207"

def send(msg):
    try:
        r = requests.post(f"https://api.telegram.org/bot{TOKEN}/sendMessage", json={"chat_id": CHAT_ID, "text": msg})
        print(r.status_code, r.json())
    except Exception as e:
        print("خطأ:", e)

if __name__ == "__main__":
    send("✅ البوت شغال الآن!")
    # البقاء قيد التشغيل
    while True:
        time.sleep(60)