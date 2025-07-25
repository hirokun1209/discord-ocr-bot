import os
import discord
from PIL import Image

TOKEN = os.getenv("DISCORD_TOKEN")

intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

# === 修正版座標 (1290x2796専用) ===
base_y = 900         # 少し下げた
row_height = 300     # 行間を広めに
num_box_x = (200, 500)    # 番号ボックスを広めに
time_box_x = (630, 1050)  # 時間ボックスを広めに

def crop_debug_images(img_path):
    img = Image.open(img_path)
    img_w, img_h = img.size
    print(f"画像サイズ: {img_w} x {img_h}")

    cropped_paths = []

    for i in range(3):  # 1枚に3行分だけ処理
        y1 = base_y + i * row_height
        y2 = y1 + 100  # 高さも広めに確保

        num_crop_path = f"/tmp/debug_num_{i+1}.png"
        time_crop_path = f"/tmp/debug_time_{i+1}.png"

        # 駐騎場番号
        img.crop((num_box_x[0], y1, num_box_x[1], y2)).save(num_crop_path)
        # 免戦時間
        img.crop((time_box_x[0], y1, time_box_x[1], y2)).save(time_crop_path)

        cropped_paths.append((num_crop_path, time_crop_path))

    return cropped_paths

@client.event
async def on_message(message):
    if message.author.bot:
        return

    if message.attachments:
        await message.channel.send("✅ 画像を受け取りました！修正版座標で切り出し確認します…")
        
        for attachment in message.attachments:
            file_path = f"/tmp/{attachment.filename}"
            await attachment.save(file_path)

            crops = crop_debug_images(file_path)

            for idx, (num_img, time_img) in enumerate(crops, start=1):
                await message.channel.send(
                    f"行{idx} の切り出し結果（駐騎場番号 / 免戦時間）",
                    files=[
                        discord.File(num_img, filename=f"行{idx}_番号.png"),
                        discord.File(time_img, filename=f"行{idx}_時間.png")
                    ]
                )

client.run(TOKEN)