import discord
import pytesseract
from PIL import Image, ImageEnhance, ImageFilter
from io import BytesIO
import re
from datetime import datetime, timedelta
import os

TOKEN = os.getenv("DISCORD_TOKEN")

# OCR設定（精度重視）
OCR_CONFIG = "--oem 1 --psm 6"

intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

def preprocess_image(img: Image.Image) -> Image.Image:
    """OCR前に画像を補正（グレースケール + コントラストUP + 二値化）"""
    # グレースケール化
    img = img.convert("L")
    # コントラスト強調
    enhancer = ImageEnhance.Contrast(img)
    img = enhancer.enhance(2.0)  # 数字をクッキリ
    # シャープ化
    img = img.filter(ImageFilter.SHARPEN)
    # 二値化（しきい値128）
    img = img.point(lambda x: 0 if x < 128 else 255, '1')
    return img

@client.event
async def on_ready():
    print(f"✅ BOTログイン成功: {client.user}")

@client.event
async def on_message(message):
    if message.author.bot:
        return

    if message.content.strip() == "!test":
        await message.channel.send("✅ BOT動いてるよ！")
        return

    if message.attachments:
        await message.channel.send("📥 画像を受け取りました、OCR補正中です…")

        for attachment in message.attachments:
            img_data = await attachment.read()
            img = Image.open(BytesIO(img_data))

            # OCR前に補正
            img_processed = preprocess_image(img)

            # OCR（日本語）
            text_jpn = pytesseract.image_to_string(img_processed, lang="jpn", config=OCR_CONFIG)
            # OCR（英数字）
            text_eng = pytesseract.image_to_string(img_processed, lang="eng", config=OCR_CONFIG)

            # デバッグ結果
            await message.channel.send(f"📄 日本語OCR結果:\n```\n{text_jpn}\n```")
            await message.channel.send(f"📄 英数字OCR結果:\n```\n{text_eng}\n```")

            # サーバー番号
            server_match = re.search(r's\d{3,4}', text_jpn)
            server_id = server_match.group()[-3:] if server_match else "???"

            # 駐騎場番号
            station_numbers = re.findall(r'駐騎場(\d+)', text_jpn)

            # 時間抽出
            time_matches = re.findall(r'([0-2]?\d:[0-5]\d:[0-5]\d)', text_eng)

            if not time_matches:
                await message.channel.send("⚠️ OCR補正後でも時間が見つかりませんでした…")
                continue

            if len(time_matches) == 1:
                await message.channel.send(f"⏰ 基準時間のみ検出: {time_matches[0]}")
                continue

            # 基準時間は最初
            base_time_str = time_matches[0]
            base_time = datetime.strptime(base_time_str, "%H:%M:%S")
            immune_times = time_matches[1:]

            # 駐騎場番号がなければ順番割当
            if not station_numbers:
                station_numbers = [str(i+1) for i in range(len(immune_times))]

            results = []
            for idx, t in enumerate(immune_times):
                station_name = f"越域駐騎場{station_numbers[idx]}" if idx < len(station_numbers) else f"越域駐騎場{idx+1}"
                h, m, s = map(int, t.split(":"))
                delta = timedelta(hours=h, minutes=m, seconds=s)
                new_time = (base_time + delta).time()
                results.append(f"{station_name}({server_id}) {new_time}")

            if results:
                await message.channel.send("\n".join(results))
            else:
                await message.channel.send("⚠️ OCRできたけど免戦時間の計算はできませんでした…")

client.run(TOKEN)