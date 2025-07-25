import discord
import pytesseract
from PIL import Image
from io import BytesIO
import re
from datetime import datetime, timedelta
import os

TOKEN = os.getenv("DISCORD_TOKEN")

BASE_OCR_CONFIG = "--oem 3 --psm 7"    # 1行
SERVER_OCR_CONFIG = "--oem 3 --psm 6"  # 数字＋記号
CENTER_OCR_CONFIG = "--oem 3 --psm 6"  # 複数行

intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

# === 必要な範囲だけ抽出 ===
def crop_top_right(img):
    """右上(基準時間)"""
    w,h = img.size
    return img.crop((w*0.75, h*0.07, w*0.98, h*0.13))

def crop_server_id(img):
    """中央少し上(サーバー番号)"""
    w,h = img.size
    return img.crop((w*0.3, h*0.20, w*0.7, h*0.35))

def crop_center_area(img):
    """中央OCR → サーバー番号も含める縦30〜70%、横10〜50%"""
    w, h = img.size
    return img.crop((w * 0.1, h * 0.30, w * 0.5, h * 0.70))
def clean_text(text):
    return text.replace("駐聴場","駐騎場").replace("駐脱場","駐騎場")

def extract_base_time(text):
    m = re.search(r'([0-2]?\d:[0-5]\d:[0-5]\d)', text)
    return m.group(1) if m else None

def extract_server_id(text):
    m = re.search(r'\[s?(\d{2,4})\]', text, re.IGNORECASE)
    return m.group(1) if m else None

def extract_station_numbers(text):
    return re.findall(r'駐騎場\s*(\d+)', text)

def extract_times(text):
    return re.findall(r'([0-5]?\d:[0-5]\d(?::[0-5]\d)?)', text)

@client.event
async def on_ready():
    print(f"✅ BOTログイン成功: {client.user}")

@client.event
async def on_message(message):
    if message.author.bot: return

    if message.content.strip() == "!test":
        await message.channel.send("✅ BOT動いてるよ！（リセット版）")
        return

    if message.attachments:
        await message.channel.send("📥 画像を受け取りました、抽出リセット版で処理中…")

        for attachment in message.attachments:
            img_data = await attachment.read()
            img = Image.open(BytesIO(img_data))

            # === 基準時間 ===
            base_img = crop_top_right(img)
            base_img.save("/tmp/debug_base.png")
            await message.channel.send(file=discord.File("/tmp/debug_base.png","base_debug.png"))
            base_text = pytesseract.image_to_string(base_img, lang="jpn+eng", config=BASE_OCR_CONFIG)
            base_time = extract_base_time(base_text)

            # === サーバー番号 ===
            server_img = crop_server_id(img)
            server_img.save("/tmp/debug_server.png")
            await message.channel.send(file=discord.File("/tmp/debug_server.png","server_debug.png"))
            server_text = pytesseract.image_to_string(server_img, lang="jpn+eng", config=SERVER_OCR_CONFIG)
            server_id = extract_server_id(server_text)

            # === 中央OCR ===
            center_img = crop_center_area(img)
            center_img.save("/tmp/debug_center.png")
            await message.channel.send(file=discord.File("/tmp/debug_center.png","center_debug.png"))
            center_text = clean_text(pytesseract.image_to_string(center_img, lang="jpn+eng", config=CENTER_OCR_CONFIG))
            station_numbers = extract_station_numbers(center_text)
            immune_times = extract_times(center_text)

            # === デバッグ表示 ===
            await message.channel.send(f"⏫ 基準時間OCR:\n```\n{base_text}\n```")
            await message.channel.send(f"🖥 サーバーOCR:\n```\n{server_text}\n```")
            await message.channel.send(f"📄 中央OCR結果:\n```\n{center_text}\n```")

            if not base_time:
                await message.channel.send("⚠️ 基準時間が読めませんでした")
                return

            if not server_id:
                await message.channel.send("⚠️ サーバー番号が読めませんでした")
                return

            if len(station_numbers) != len(immune_times):
                await message.channel.send(
                    f"⚠️ データ数不一致\n"
                    f"基準時間: {base_time}\n"
                    f"サーバー: {server_id}\n"
                    f"駐騎場: {station_numbers}\n"
                    f"免戦: {immune_times}"
                )
                return

            # 計算
            base_dt = datetime.strptime(base_time,"%H:%M:%S")
            results=[]
            for i,t in enumerate(immune_times):
                hms = list(map(int, t.split(":")))
                while len(hms)<3: hms.append(0)
                end_dt = (base_dt + timedelta(hours=hms[0], minutes=hms[1], seconds=hms[2])).time()
                results.append(f"越域駐騎場{station_numbers[i]}({server_id}) {end_dt.strftime('%H:%M:%S')}")

            await message.channel.send("\n".join(results) if results else "⚠️ 読み取り結果なし")

client.run(TOKEN)