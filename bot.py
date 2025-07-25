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

    if message.content.strip() == "!test":
        await message.channel.send("✅ BOT動いてるよ！")
        return

    if message.attachments:
        for attachment in message.attachments:
            img_data = await attachment.read()
            img = Image.open(BytesIO(img_data))
            text = pytesseract.image_to_string(img, lang="jpn")
            print("OCR結果:\n", text)

            server_match = re.search(r's(\d+)', text)
            server_id = server_match.group(1)[-3:] if server_match else "???"

            main_time_match = re.search(r'(\d{1,2}:\d{2}:\d{2})', text)
            if not main_time_match:
                await message.channel.send("右上の時間が見つかりませんでした…")
                return
            base_time = datetime.strptime(main_time_match.group(1), "%H:%M:%S")

            station_numbers = re.findall(r'駐騎場(\d+)', text)
            immune_times = re.findall(r'(\d{1,2}:\d{2}:\d{2})', text)[1:]

            results = []
            for idx, t in enumerate(immune_times):
                station_name = f"越域駐騎場{station_numbers[idx]}" if idx < len(station_numbers) else "駐騎場?"
                delta = timedelta(hours=int(t.split(":")[0]), minutes=int(t.split(":")[1]), seconds=int(t.split(":")[2]))
                new_time = (base_time + delta).time()
                results.append(f"{station_name}({server_id}) {new_time}")

            await message.channel.send("\n".join(results))

client.run(TOKEN)
