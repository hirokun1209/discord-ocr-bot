import discord
import pytesseract
from PIL import Image
from io import BytesIO
import re
from datetime import datetime, timedelta
import os

TOKEN = os.getenv("DISCORD_TOKEN")

intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

@client.event
async def on_ready():
    print(f"✅ BOTログイン成功: {client.user}")

@client.event
async def on_message(message):
    print(f"DEBUG: {message.author} -> {message.content}")

    if message.author.bot:
        return

    # 動作確認用
    if message.content.strip() == "!test":
        await message.channel.send("✅ BOT動いてるよ！")
        return

    # 画像が送られたらOCR
    if message.attachments:
        for attachment in message.attachments:
            img_data = await attachment.read()
            img = Image.open(BytesIO(img_data))

            # 日本語OCR
            text_jpn = pytesseract.image_to_string(img, lang="jpn")
            # 英数字OCR（時間専用）
            text_eng = pytesseract.image_to_string(img, lang="eng")

            # デバッグ用に両方表示
            await message.channel.send(f"📄 日本語OCR結果:\n```\n{text_jpn}\n```")
            await message.channel.send(f"📄 英数字OCR結果:\n```\n{text_eng}\n```")

            # サーバー番号（日本語OCR結果から抽出）
            server_match = re.search(r's[\sIilL]?\d+', text_jpn)
            if server_match:
                digits = re.sub(r'\D', '', server_match.group())  # 数字だけ
                server_id = digits[-3:] if len(digits) >= 3 else "???"
            else:
                server_id = "???"

            # 時間は英数字OCRから抽出（精度向上）
            time_matches = re.findall(r'([0-2]?\d:[0-5]\d:[0-5]\d)', text_eng)

            if not time_matches:
                await message.channel.send("⚠️ 時間が見つかりませんでした…")
                return

            # 右上の基準時間は最初の時間
            base_time_str = time_matches[0]
            base_time = datetime.strptime(base_time_str, "%H:%M:%S")

            # 駐騎場番号（誤OCR補正）
            station_numbers = re.findall(r'駐[騎機极]|塲|场?(\d+)', text_jpn)

            # 免戦時間は2個目以降
            immune_times = time_matches[1:]

            results = []
            for idx, t in enumerate(immune_times):
                station_name = f"越域駐騎場{station_numbers[idx]}" if idx < len(station_numbers) else "駐騎場?"
                delta = timedelta(
                    hours=int(t.split(":")[0]),
                    minutes=int(t.split(":")[1]),
                    seconds=int(t.split(":")[2])
                )
                new_time = (base_time + delta).time()
                results.append(f"{station_name}({server_id}) {new_time}")

            # 結果が空なら警告
            if results:
                await message.channel.send("\n".join(results))
            else:
                await message.channel.send("⚠️ OCRできたけど、番号や時間が足りませんでした…")

client.run(TOKEN)