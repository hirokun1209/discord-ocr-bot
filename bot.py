import os
import discord
from PIL import Image

TOKEN = os.getenv("DISCORD_TOKEN")

intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

# === サーバー番号は完璧なので現状維持 ===
server_box = (420, 970, 870, 1040)

# === 駐騎場番号＋免戦時間 ===
base_y = 1095             # 1枚目OKの位置
row_height = 310          # 行間はそのまま
full_box_x = (270, 630)   # 横幅は270～630のまま

def crop_debug_images(img_path):
    img = Image.open(img_path)
    img_w, img_h = img.size
    print(f"画像サイズ: {img_w} x {img_h}")

    cropped_paths = []

    # ✅ サーバー番号はそのまま
    server_crop_path = "/tmp/debug_server.png"
    img.crop(server_box).save(server_crop_path)

    # ✅ 駐騎場番号＋免戦時間（2枚目だけ上に50補正）
    for i in range(3):
        y1 = base_y + i * row_height

        # 行2だけ上に50pxずらす
        if i == 1:
            y1 -= 50

        y2 = y1 + 110

        full_crop_path = f"/tmp/debug_full_{i+1}.png"
        img.crop((full_box_x[0], y1, full_box_x[1], y2)).save(full_crop_path)
        cropped_paths.append(full_crop_path)

    return server_crop_path, cropped_paths

@client.event
async def on_message(message):
    if message.author.bot:
        return

    if message.attachments:
        await message.channel.send(
            "✅ 画像を受け取りました！1枚目そのまま・2枚目だけ50px上げて切り出します…"
        )
        
        for attachment in message.attachments:
            file_path = f"/tmp/{attachment.filename}"
            await attachment.save(file_path)

            server_img, crops = crop_debug_images(file_path)

            # サーバー番号画像（そのまま）
            await message.channel.send("サーバー番号の切り出し結果", file=discord.File(server_img))

            # 駐騎場番号＋免戦時間（2枚目だけ上50補正）
            for idx, full_img in enumerate(crops, start=1):
                await message.channel.send(
                    f"行{idx} の切り出し結果（番号＋免戦時間）",
                    file=discord.File(full_img, filename=f"行{idx}_番号_免戦時間.png")
                )

client.run(TOKEN)