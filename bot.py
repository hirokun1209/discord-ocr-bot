import os
import discord
from PIL import Image

# ✅ 環境変数からトークンを取得
TOKEN = os.getenv("DISCORD_TOKEN")

intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

# === 1290x2796専用の改良座標 ===
# サーバー番号切り出し範囲（画面中央上あたり）
server_box = (420, 730, 870, 800)

# 駐騎場3行分の座標
base_y = 930         # さらに下に補正
row_height = 310     # 行間を広めに
num_box_x = (180, 520)    # 駐騎場番号ボックス（広め）
time_box_x = (600, 1100)  # 免戦時間ボックス（広め）

def crop_debug_images(img_path):
    img = Image.open(img_path)
    img_w, img_h = img.size
    print(f"画像サイズ: {img_w} x {img_h}")

    cropped_paths = []

    # ✅ サーバー番号を切り出す
    server_crop_path = "/tmp/debug_server.png"
    img.crop(server_box).save(server_crop_path)

    # ✅ 駐騎場3行分を切り出す
    for i in range(3):
        y1 = base_y + i * row_height
        y2 = y1 + 110  # 高さも広めに確保

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
        await message.channel.send("✅ 画像を受け取りました！サーバー番号＋駐騎場3行分を切り出します…")
        
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