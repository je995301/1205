# app.py
import os
import openai
import time
import threading
import schedule

from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage
from datetime import datetime, time



#openai key
openai.api_key = os.getenv("OPENAI_API_KEY")

app = Flask(__name__)

# Line Bot 設定
line_bot_api = LineBotApi(os.getenv("LINE_CHANNEL_ACCESS_TOKEN"))
handler = WebhookHandler(os.getenv("LINE_CHANNEL_SECRET")) 

# 設定BMI的相關變數
user_bmi = {}

# 設定運動菜單的相關變數
user_training_menu = {}

# 設定提醒規劃的相關變數
user_reminder = {}
user_reminders = {}


# 處理Line Bot的Webhook
@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers['X-Line-Signature']
    body = request.get_data(as_text=True)
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    return 'OK' 

# 處理收到的訊息
@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    user_id = event.source.user_id
    message_text = event.message.text

    #計算BMI
    if message_text == '計算BMI':
         line_bot_api.reply_message(
             event.reply_token,
             TextSendMessage(text="請輸入身高(cm)和體重(kg)，格式：身高 體重")
         ) 
    
    
    elif message_text and ' ' in message_text:
        height, weight = map(float, message_text.split(' '))
        bmi = weight / ((height / 100) ** 2)
        
        # 判斷BMI區間
        if bmi < 18.5:
            result = "過輕"
        elif 18.5 <= bmi < 24:
            result = "正常"
        else:
            result = "過重"
        
        user_bmi[user_id] = {'bmi': bmi, 'result': result}
        
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text=f"你的BMI為{bmi:.2f}，屬於{result}範圍")
        )

   	# 當使用者選擇訓練菜單時
    elif message_text == '訓練菜單':
        # 根據使用者的BMI，記錄下來
        if user_id not in user_bmi:
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text="請先計算BMI，再進行訓練菜單的選擇。")
            )
            return
    
        # 詢問使用者的目標
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text="請告訴我你的訓練目標，例如：增肌、減脂等。")
        )
    
        # 設定使用者的狀態為等待目標輸入
        user_bmi[user_id]['status'] = 'waiting_goal'
    
    # 在處理使用者的選擇部分新增以下程式碼
    elif user_id in user_bmi and user_bmi[user_id].get('status') == 'waiting_goal':
        # 紀錄使用者的目標
        user_bmi[user_id]['goal'] = message_text
    
        # 向ChatGPT請求生成訓練菜單
        user_bmi_data = user_bmi.get(user_id, {})
        bmi_value = user_bmi_data.get('bmi', '未知')
        goal_value = user_bmi_data.get('goal', '未設定目標')
        prompt = f"根據BMI {bmi_value}，請為我生成一份訓練菜單，目標是{goal_value}。"
        response = openai.completions.create(
            engine="gpt-3.5-turbo",
            prompt=prompt,
            max_tokens=150
        )
    
        training_menu = response['choices'][0]['text']
    
        # 記錄使用者的訓練菜單
        user_training_menu[user_id] = training_menu
    
        # 回傳訓練菜單給使用者
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text=f"你的訓練菜單如下：\n{training_menu}")
        )


    # 當使用者選擇"影片教學按鈕"時
    elif message_text == '影片教學按鈕':
        # 向ChatGPT請求生成部位訓練相關介紹
        response = openai.completions.create(
            engine="gpt-3.5-turbo",
            prompt="請為我提供一個部位訓練，例如：胸肌訓練。",
            max_tokens=150
        )
        
        training_part = response['choices'][0]['text']

        # 假設你有一個影片教學的連結，這裡用文字訊息顯示
        training_video_link = "https://www.youtube.com/watch?v=6VTZQxOx4Oc"

        # 回傳部位訓練介紹和影片連結給使用者
        reply_message = f"{training_part}\n\n你可以觀看相關影片教學:{training_video_link}"
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text=reply_message)
        )

    # 健康日誌 
    elif message_text == '健康日誌':
        menu_prompt = "請生成一份健康菜單，用於健康日誌。"
        # 向 ChatGPT 請求生成健康菜單
        response = openai.completions.create(
            engine="gpt-3.5-turbo",
            prompt=menu_prompt,
            max_tokens=150
        )
        
        health_menu = response['choices'][0]['text']

        # 格式化健康菜單，以表格方式呈現
        formatted_menu = format_menu(health_menu)

        # 回傳格式化後的健康菜單
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text=formatted_menu)
        )        

    # 提醒規劃
    elif message_text == '提醒規劃':
        # 請使用者選擇提醒的時間
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text="請選擇提醒的時間，格式：HH:MM")
        )

        # 設定使用者的狀態為等待提醒時間
        user_reminders[user_id] = {'status': 'waiting_time'}
    # 聯絡我們
    elif message_text == '聯絡我們':
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text="聯絡我們：xdgame4398@gmail.com")
        )

    # 其他未定義的訊息
    else:
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text="我看不懂你在說甚麼，請重新輸入指令")
        )


def format_menu(health_menu):
    # 菜單格式化
    if health_menu:
        menu_items = health_menu.split('\n')
        formatted_menu = "健康菜單：\n"
        for item in menu_items:
            if item and item.strip():
                formatted_menu += f"- {item.strip()}\n"
        return formatted_menu
    else:
        return "無法生成健康菜單。"
    
# 處理使用者的選擇
@handler.add(MessageEvent)
def handle_reminder_time(event):
    user_id = event.source.user_id
    message_text = event.message.text

    # 檢查使用者的狀態
    if (
        user_id in user_reminders and
        user_reminders[user_id].get('status') == 'waiting_time' and message_text is not None
    ):
        try:
            # 將使用者的提醒時間轉換為 datetime.time 物件
            reminder_time = datetime.strptime(message_text, "%H:%M").time()

            # 將使用者的提醒時間加入排程
            schedule.every().day.at(reminder_time).do(send_reminder, user_id=user_id)

            # 設定使用者的狀態為提醒已設定
            user_reminders[user_id]['status'] = 'reminder_set'

            # 回應使用者提醒已設定
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text=f"提醒已設定在每天 {message_text} 通知你去健身")
            )
        except ValueError:
            # 轉換失敗的例外處理
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text="請輸入正確的時間格式，例如：HH:MM")
            )

# 提醒功能的執行緒
def reminder_thread():
    while True:
        schedule.run_pending()
        time.sleep(1)

# 發送提醒給使用者
def send_reminder(user_id):
    # 在這裡執行 schedule.run_pending()
    schedule.run_pending()

    # 發送提醒給使用者
    line_bot_api.push_message(user_id, TextSendMessage(text="該去健身啦！"))

   
if __name__ == "__main__":
    app.run()
