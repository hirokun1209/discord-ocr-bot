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
    if message.author.bot:
        return

    if message.content.strip() == "!test":
        await message.channel.send("✅ BOT動いてるよ！")
        return

    if message.attachments:
        for attachment in message.attachments:
            img_data = await attachment.read()
            img = Image.open(BytesIO(img_data))

            # 日本語OCR → サーバー番号・駐騎場番号用
            text_jpn = pytesseract.image_to_string(img, lang="jpn")
            # 英数字OCR → 時間抽出用
            text_eng = pytesseract.image_to_string(img, lang="eng")

            # デバッグ表示
            await message.channel.send(f"📄 日本語OCR結果:\n```\n{text_jpn}\n```")
            await message.channel.send(f"📄 英数字OCR結果:\n```\n{text_eng}\n```")

            # サーバー番号（末尾3桁）
            server_match = re.search(r's\d{3,4}', text_jpn)
            server_id = server_match.group()[-3:] if server_match else "???"

            # 駐騎場番号を抽出
            station_numbers = re.findall(r'駐騎場(\d+)', text_jpn)

            # 時間抽出（基準時間 + 免戦時間）
            time_matches = re.findall(r'([0-2]?\d:[0-5]\d:[0-5]\d)', text_eng)
            if not time_matches or len(time_matches) < 2:
                await message.channel.send("⚠️ 時間が足りません（基準時間＋免戦時間が必要）")
                return

            # 最初の時間 → 基準時間
            base_time_str = time_matches[0]
            base_time = datetime.strptime(base_time_str, "%H:%M:%S")
            immune_times = time_matches[1:]

            results = []
            for idx, t in enumerate(immune_times):
                # 駐騎場番号が取れない場合は順番割当
                station_name = f"越域駐騎場{station_numbers[idx]}" if idx < len(station_numbers) else f"越域駐騎場{idx+1}"

                # 免戦時間を足す
                h, m, s = map(int, t.split(":"))
                delta = timedelta(hours=h, minutes=m, seconds=s)
                new_time = (base_time + delta).time()

                results.append(f"{station_name}({server_id}) {new_time}")

            await message.channel.send("\n".join(results))