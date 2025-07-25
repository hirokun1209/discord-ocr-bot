import os
import discord
from PIL import Image
import pytesseract

# ✅ トークンは環境変数から取得
TOKEN = os.getenv("DISCORD_TOKEN")

intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

# === 座標設定 ===
base_y = 480
row_height = 160
num_box_x = (120, 250)    # 駐騎場番号
time_box_x = (360, 540)   # 免戦時間

def extract_slots(img_path):
    img = Image.open(img_path)
    results = []

    for i in range(3):  # 1枚に最大3行
        y1 = base_y + i * row_height
        y2 = y1 + 50  # 高さ50px
        
        num_crop  = img.crop((num_box_x[0], y1, num_box_x[1], y2))
        time_crop = img.crop((time_box_x[0], y1, time_box_x[1], y2))
        
        parking_num = pytesseract.image_to_string(
            num_crop, config="--psm 7 -c tessedit_char_whitelist=0123456789"
        ).strip()
        
        timer_text = pytesseract.image_to_string(
            time_crop, config="--psm 7 -c tessedit_char_whitelist=0123456789:"
        ).strip()
        
        if not parking_num:
            continue  # 空行ならスキップ
        
        if timer_text:
            results.append(f"行{i+1} → 駐騎場番号: {parking_num}, 免戦時間: {timer_text}")
        else:
            results.append(f"行{i+1} → 駐騎場番号: {parking_num}, 開戦済")
    
    return "\n".join(results)

@client.event
async def on_message(message):
    if message.author.bot:
        return

    if message.attachments:
        # 受け取ったときの即レス
        await message.channel.send("✅ 画像を受け取りました！解析中です…")
        
        for attachment in message.attachments:
            file_path = f"/tmp/{attachment.filename}"
            await attachment.save(file_path)
            
            debug_result = extract_slots(file_path)
            await message.channel.send(f"[DEBUG 結果]\n{debug_result}")

client.run(TOKEN)