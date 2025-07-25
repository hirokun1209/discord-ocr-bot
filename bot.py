import discord
import pytesseract
from PIL import Image, ImageEnhance, ImageFilter
from io import BytesIO
import re
from datetime import datetime, timedelta
import os

TOKEN = os.getenv("DISCORD_TOKEN")

BASE_OCR_CONFIG = "--oem 3 --psm 7"
CENTER_OCR_CONFIG = "--oem 3 --psm 6"

intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

# === OCR前処理(精密版) ===
def preprocess_image(img: Image.Image) -> Image.Image:
    # 4倍拡大
    img = img.resize((img.width * 4, img.height * 4))
    # グレースケール
    img = img.convert("L")
    # ノイズ軽減ぼかし
    img = img.filter(ImageFilter.GaussianBlur(radius=1))
    # コントラスト強化
    img = ImageEnhance.Contrast(img).enhance(4.5)
    # 白黒化(細い線も残す)
    img = img.point(lambda p: 255 if p > 165 else 0)
    # エッジ強調
    img = img.filter(ImageFilter.EDGE_ENHANCE_MORE)
    # 仕上げシャープ化
    img = img.filter(ImageFilter.SHARPEN)
    return img

# === 基準時間の切り出し範囲を広げる ===
def crop_top_right(img):
    """右上の基準時間 → 縦5〜15%、横70〜99%に拡大"""
    w,h = img.size
    return img.crop((w*0.70, h*0.05, w*0.99, h*0.15))

def crop_center_area(img):
    """中央OCR → 元の範囲: 縦35〜70%、横10〜50%"""
    w,h = img.size
    return img.crop((w*0.1, h*0.35, w*0.5, h*0.70))

def clean_text(text):
    return (text.replace("駐聴場","駐騎場")
                .replace("駐脱場","駐騎場")
                .replace("越域駐豚場","越域駐騎場"))

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
        await message.channel.send("✅ BOT動いてるよ！（精密前処理版）")
        return

    if message.attachments:
        await message.channel.send("📥 画像を受け取りました、精密前処理で解析中…")

        for attachment in message.attachments:
            img_data = await attachment.read()
            img = Image.open(BytesIO(img_data))

            # === 基準時間OCR ===
            base_img = preprocess_image(crop_top_right(img))
            base_img.save("/tmp/debug_base.png")
            await message.channel.send(file=discord.File("/tmp/debug_base.png","base_debug.png"))
            base_text = pytesseract.image_to_string(base_img, lang="jpn+eng", config=BASE_OCR_CONFIG)
            base_time = extract_base_time(base_text)

            # === 中央OCR ===
            center_img = preprocess_image(crop_center_area(img))
            center_img.save("/tmp/debug_center.png")
            await message.channel.send(file=discord.File("/tmp/debug_center.png","center_debug.png"))
            center_text_raw = pytesseract.image_to_string(center_img, lang="jpn+eng", config=CENTER_OCR_CONFIG)
            center_text = clean_text(center_text_raw)

            # === 駐騎場行 + 2行下までペア解析 ===
            lines = center_text.splitlines()
            paired_lines = []
            for i, line in enumerate(lines):
                if "駐騎場" in line:
                    block = " ".join(lines[i:i+3])  # その行＋2行下まで連結
                    paired_lines.append(block)
            filtered_text = "\n".join(paired_lines)

            # デバッグ結果
            await message.channel.send(f"⏫ 基準時間OCR:\n```\n{base_text}\n```")
            await message.channel.send(f"📄 中央OCR結果(全体):\n```\n{center_text_raw}\n```")
            await message.channel.send(f"📄 駐騎場＋次行ペア抽出:\n```\n{filtered_text}\n```")

            # サーバー番号 / 駐騎場番号 / 免戦時間抽出
            server_id = extract_server_id(filtered_text)
            station_numbers = extract_station_numbers(filtered_text)
            immune_times = extract_times(filtered_text)

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

            # === 計算 ===
            base_dt = datetime.strptime(base_time,"%H:%M:%S")
            results=[]
            for i,t in enumerate(immune_times):
                hms = list(map(int, t.split(":")))
                while len(hms)<3: hms.append(0)
                end_dt = (base_dt + timedelta(hours=hms[0], minutes=hms[1], seconds=hms[2])).time()
                results.append(f"越域駐騎場{station_numbers[i]}({server_id}) {end_dt.strftime('%H:%M:%S')}")

            await message.channel.send("\n".join(results) if results else "⚠️ 読み取り結果なし")

client.run(TOKEN)