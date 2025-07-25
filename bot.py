import os
import discord
from PIL import Image

TOKEN = os.getenv("DISCORD_TOKEN")

intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

# === 1290x2796専用・微調整版 ===

# サーバー番号は10px下げる
server_box = (420, 970, 870, 1040)

# 駐騎場3行は20px上げる
base_y = 1140
row_height = 310  # 行間はそのまま
num_box_x = (180, 520)
time_box_x = (600, 1100)

def crop_debug_images(img_path):
    img = Image.open(img_path)
    img_w, img_h = img.size
    print(f"画像サイズ: {img_w} x {img_h}")

    cropped_paths = []

    # ✅ サーバー番号を切り出す（10px下）
    server_crop_path = "/tmp/debug_server.png"
    img.crop(server_box).save(server_crop_path)

    # ✅ 駐騎場3行分を切り出す（20px上）
    for i in range(3):
        y1 = base_y + i * row_height
        y2 = y1 + 110

        num_crop_path = f"/tmp/debug_num_{i+1}.png"
        time_crop_path = f"/tmp/debug_time_{i+1}.png"

        img.crop((num_box_x[0], y1, num_box_x[1], y2)).save(num_crop_path)
        img.crop((time_box_x[0], y1, time_box_x[1], y2)).save(time_crop_path)

        cropped_paths.append((num_crop_path, time_crop_path))

    return server_crop_path, cropped_paths

@client.event
async def on_message(message):
    if message.author.bot:
        return

    if message.attachments:
        await message.channel.send("✅ 画像を受け取りました！サーバー番号10px下・駐騎場20px上で切り出します…")
        
        for attachment in message.attachments:
            file_path = f"/tmp/{attachment.filename}"
            await attachment.save(file_path)

            server_img, crops = crop_debug_images(file_path)

            # サーバー番号画像を送る
            await message.channel.send("サーバー番号の切り出し結果", file=discord.File(server_img))

            # 駐騎場3行分を送る
            for idx, (num_img, time_img) in enumerate(crops, start=1):
                await message.channel.send(
                    f"行{idx} の切り出し結果（駐騎場番号 / 免戦時間）",
                    files=[
                        discord.File(num_img, filename=f"行{idx}_番号.png"),
                        discord.File(time_img, filename=f"行{idx}_時間.png")
                    ]
                )

client.run(TOKEN)