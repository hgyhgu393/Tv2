import discord
from discord import app_commands
from discord.ext import commands, tasks
import os
import re
import datetime
import asyncio
import pytchat
from flask import Flask
from threading import Thread

# ---------- ระบบ Web Server สำหรับ Keep Alive ----------
app = Flask('')
@app.route('/')
def home(): return "YouTube Scanner is running."
def run(): app.run(host='0.0.0.0', port=8080)
def keep_alive(): Thread(target=run).start()

# ---------- ระบบจัดเก็บข้อมูล ----------
# monitors: { video_id: { "user_id": int, "prefix": str, "title": str, "status": "green"/"red", "task": pytchat_obj } }
monitors = {}
sent_codes = set()

class YouTubeLiveBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self):
        await self.tree.sync()
        self.check_chat_loop.start() # เริ่มระบบวนลูปอ่านแชท
        print(f"Logged in as {self.user}")

bot = YouTubeLiveBot()

# ---------- ระบบ UI และปุ่มกด ----------
class ControlPanelView(discord.ui.View):
    def __init__(self, log_channel_id):
        super().__init__(timeout=None)
        self.log_channel_id = log_channel_id

    @discord.ui.button(label="เพิ่มลิ้งค์การดู", style=discord.ButtonStyle.success, emoji="➕")
    async def add_link(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(AddLinkModal(self.log_channel_id))

    @discord.ui.button(label="ลบลิ้งค์การดู", style=discord.ButtonStyle.danger, emoji="➖")
    async def remove_link(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not monitors:
            return await interaction.response.send_message("❌ ไม่มีลิ้งค์ที่กำลังดูอยู่", ephemeral=True)
        monitors.clear()
        await interaction.response.send_message("🗑️ ลบรายการเฝ้าดูทั้งหมดเรียบร้อยแล้ว", ephemeral=True)

    @discord.ui.button(label="สถานะการดูของบอท", style=discord.ButtonStyle.secondary, emoji="📊")
    async def check_status(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not monitors:
            return await interaction.response.send_message("⚪ สถานะ: ว่างงาน", ephemeral=True)
        
        embed = discord.Embed(title="📊 สถานะการเฝ้าดูปัจจุบัน", color=discord.Color.blue())
        for vid, data in monitors.items():
            emoji = "🟢" if data['status'] == "green" else "🔴"
            embed.add_field(name=f"{emoji} {data['title']}", value=f"Video ID: `{vid}` | Prefix: `{data['prefix']}`", inline=False)
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

class AddLinkModal(discord.ui.Modal, title="เพิ่มลิ้งค์ YouTube Live"):
    yt_url = discord.ui.TextInput(label="YouTube Live URL", placeholder="วางลิ้งค์ที่นี่...")
    prefix = discord.ui.TextInput(label="คำนำหน้าโค้ด (เช่น RPL)", placeholder="RPL", min_length=2)

    def __init__(self, log_channel_id):
        super().__init__()
        self.log_channel_id = log_channel_id

    async def on_submit(self, interaction: discord.Interaction):
        video_id_match = re.search(r"(?:v=|\/)([0-9A-Za-z_-]{11})", self.yt_url.value)
        if not video_id_match:
            return await interaction.response.send_message("❌ ลิ้งค์ไม่ถูกต้อง", ephemeral=True)
        
        video_id = video_id_match.group(1)
        try:
            # ใช้ pytchat เพื่อดึงชื่อวิดีโอและตรวจสอบว่าไลฟ์อยู่ไหม
            chat = pytchat.create(video_id=video_id)
            if chat.is_alive():
                monitors[video_id] = {
                    "user_id": interaction.user.id,
                    "prefix": self.prefix.value.upper(),
                    "title": "กำลังดึงข้อมูล...",
                    "status": "green",
                    "log_channel": self.log_channel_id,
                    "chat_obj": chat
                }
                await interaction.response.send_message(f"✅ เริ่มเฝ้าดู Video ID: `{video_id}` เรียบร้อย!", ephemeral=True)
            else:
                await interaction.response.send_message("❌ วิดีโอนี้ไม่ใช่ไลฟ์สดที่กำลังฉายอยู่", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"❌ เกิดข้อผิดพลาด: {str(e)}", ephemeral=True)

# ---------- ระบบดึงแชท Real-time (Background Task) ----------
@tasks.loop(seconds=1) # วนลูปอ่านแชททุกวินาที
async def check_chat_loop(self):
    for vid, data in list(monitors.items()):
        try:
            chat = data['chat_obj']
            if chat.is_alive():
                for c in chat.get().sync_items():
                    msg = c.message
                    prefix = data['prefix']
                    
                    # ค้นหาโค้ดที่มี Prefix นำหน้า
                    pattern = rf"{prefix}[A-Z0-9]+"
                    match = re.search(pattern, msg.upper())
                    
                    if match:
                        code = match.group(0)
                        if code not in sent_codes:
                            user = await bot.fetch_user(data['user_id'])
                            await self.send_code_dm(user, code, data['title'])
                            sent_codes.add(code)
                
                monitors[vid]['status'] = "green"
            else:
                # ถ้าไลฟ์จบแล้ว
                monitors[vid]['status'] = "red"
        except Exception as e:
            monitors[vid]['status'] = "red"
            user = await bot.fetch_user(data['user_id'])
            await self.send_error_dm(user, str(e))

async def send_code_dm(self, user, code, title):
    embed = discord.Embed(title="🚀 ตรวจพบโค้ด ROV!", color=0xFFD700, timestamp=datetime.datetime.now())
    embed.add_field(name="📌 รหัส (แตะเพื่อคัดลอก)", value=f"`{code}`", inline=False)
    embed.set_footer(text=f"จากไลฟ์: {title}")
    try: await user.send(embed=embed)
    except: pass

async def send_error_dm(self, error_msg):
    embed = discord.Embed(title="⚠️ แจ้งเตือนข้อผิดพลาด (Error)", description=f"```{error_msg}```", color=discord.Color.red())
    try: await user.send(embed=embed)
    except: pass

# ---------- คำสั่งติดตั้งหลัก ----------
@bot.tree.command(name="setup_monitor", description="สร้างระบบเฝ้าดู YouTube Live แบบ Real-time")
async def setup_monitor(interaction: discord.Interaction, title: str, message: str, image_url: str, channel: discord.TextChannel):
    embed = discord.Embed(title=title, description=message, color=discord.Color.blue())
    if image_url: embed.set_image(url=image_url)
    
    view = ControlPanelView(log_channel_id=channel.id)
    await interaction.response.send_message("✅ ติดตั้ง UI เรียบร้อยแล้ว", ephemeral=True)
    await interaction.channel.send(embed=embed, view=view)

# ---------- รันบอท ----------
if __name__ == "__main__":
    keep_alive()
    bot.run(os.environ.get('DISCORD_TOKEN'))
