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

    # 確認用コマンド
    if message.content.strip() == "!test":
        await message.channel.send("✅ BOT動いてるよ！")
        return

    # 画像が送られたとき
    if message.attachments:
        for attachment in message.attachments:
            img_data = await attachment.read()
            img = Image.open(BytesIO(img_data))

            # OCR実行
            text = pytesseract.image_to_string(img, lang="jpn")
            print("OCR結果:\n", text)

            # ✅ OCR結果をそのままDiscordに送る（デバッグ用）
            if text.strip():
                await message.channel.send(f"📄 OCR結果:\n```\n{text}\n```")
            else:
                await message.channel.send("⚠️ OCRで文字が読み取れませんでした…")
                return

            # サーバー番号 s1281 → 末尾3桁だけ
            server_match = re.search(r's(\d+)', text)
            server_id = server_match.group(1)[-3:] if server_match else "???"

            # 右上の基準時間
            main_time_match = re.search(r'(\d{1,2}:\d{2}:\d{2})', text)
            if not main_time_match:
                await message.channel.send("⚠️ 右上の時間が見つかりませんでした…")
                return

            base_time = datetime.strptime(main_time_match.group(1), "%H:%M:%S")

            # 駐騎場番号
            station_numbers = re.findall(r'駐騎場(\d+)', text)

            # 免戦時間（右上の時間除外）
            immune_times = re.findall(r'(\d{1,2}:\d{2}:\d{2})', text)[1:]

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

            # ✅ 結果が空なら警告
            if results:
                await message.channel.send("\n".join(results))
            else:
                await message.channel.send("⚠️ OCRできたけど、番号や時間が見つかりませんでした…")

client.run(TOKEN)