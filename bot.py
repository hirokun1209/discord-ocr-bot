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

    # 画像が送られたら必ず反応する
    if message.attachments:
        await message.channel.send("📥 画像を受け取りました、OCR中です…")

        for attachment in message.attachments:
            # 画像データ読み込み
            img_data = await attachment.read()
            img = Image.open(BytesIO(img_data))

            # OCR実行（日本語：駐騎場検出用）
            text_jpn = pytesseract.image_to_string(img, lang="jpn")
            # OCR実行（英数字：時間検出用）
            text_eng = pytesseract.image_to_string(img, lang="eng")

            # デバッグで必ずOCR結果を返す
            await message.channel.send(f"📄 日本語OCR結果:\n```\n{text_jpn}\n```")
            await message.channel.send(f"📄 英数字OCR結果:\n```\n{text_eng}\n```")

            # サーバー番号（末尾3桁）
            server_match = re.search(r's\d{3,4}', text_jpn)
            server_id = server_match.group()[-3:] if server_match else "???"

            # 駐騎場番号を抽出
            station_numbers = re.findall(r'駐騎場(\d+)', text_jpn)

            # 時間抽出（基準時間＋免戦時間）
            time_matches = re.findall(r'([0-2]?\d:[0-5]\d:[0-5]\d)', text_eng)

            # 時間がまったく無ければ警告して終了
            if not time_matches:
                await message.channel.send("⚠️ OCRできたけど時間が見つかりませんでした…")
                continue  # 他の画像があれば続行

            # 時間が1つだけなら基準時間のみ通知
            if len(time_matches) == 1:
                await message.channel.send(f"⏰ 基準時間のみ検出: {time_matches[0]}")
                continue

            # 最初の時間を基準にする
            base_time_str = time_matches[0]
            base_time = datetime.strptime(base_time_str, "%H:%M:%S")
            immune_times = time_matches[1:]  # 残りの時間が免戦時間

            # 駐騎場番号が取れない場合 → 順番割当
            if not station_numbers:
                station_numbers = [str(i+1) for i in range(len(immune_times))]

            # 結果計算
            results = []
            for idx, t in enumerate(immune_times):
                # 順番に駐騎場番号
                station_name = f"越域駐騎場{station_numbers[idx]}" if idx < len(station_numbers) else f"越域駐騎場{idx+1}"

                # 免戦時間を加算
                h, m, s = map(int, t.split(":"))
                delta = timedelta(hours=h, minutes=m, seconds=s)
                new_time = (base_time + delta).time()

                results.append(f"{station_name}({server_id}) {new_time}")

            # 計算結果を送信
            if results:
                await message.channel.send("\n".join(results))
            else:
                await message.channel.send("⚠️ 時間はOCRできたけど免戦時間の計算結果が空でした…")

client.run(TOKEN)