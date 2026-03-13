import discord
from discord import app_commands
from discord.ext import commands
import asyncio
import datetime
import os
from flask import Flask
from threading import Thread

# ---------- ตั้งค่าระบบรันบนเว็บไซต์ (Render) ----------
app = Flask('')
@app.route('/')
def home():
    return "Bot is running!"

def run():
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    t = Thread(target=run)
    t.start()

# ---------- เริ่มต้นโค้ดบอทของแทน ----------
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

class MyBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=intents)
        # ตัวแปรสำหรับระบบสแปม
        self.antispam_enabled = False
        self.user_messages = {} # {user_id: [timestamps]}
        self.warn_count = {}   # {user_id: count}

    async def setup_hook(self):
        await self.tree.sync()
        print(f"✅ Sync Slash Commands และเข้าระบบแล้วในชื่อ {self.user}")

bot = MyBot()

# เก็บค่าการตั้งค่าห้องต้อนรับ/ลาออก
welcome_settings = {}

# ---------- ระบบสแปม (เพิ่มเติม) ----------
@bot.tree.command(name="เปิด", description="เปิดระบบป้องกันสแปม")
async def open_antispam(interaction: discord.Interaction):
    bot.antispam_enabled = True
    await interaction.response.send_message("🛡️ **ระบบป้องกันสแปม:** เปิดใช้งานแล้ว! (5 ข้อความรัวๆ / เตือน 3 ครั้ง / Timeout 5 นาที)")

@bot.event
async def on_message(message):
    # ตรวจสอบระบบสแปมก่อน
    if bot.antispam_enabled and not message.author.bot and message.guild:
        user_id = message.author.id
        now = datetime.datetime.now().timestamp()

        if user_id not in bot.user_messages:
            bot.user_messages[user_id] = []
        
        bot.user_messages[user_id].append(now)
        bot.user_messages[user_id] = [t for t in bot.user_messages[user_id] if now - t < 5]

        if len(bot.user_messages[user_id]) >= 5:
            try:
                await message.delete()
            except:
                pass

            count = bot.warn_count.get(user_id, 0) + 1
            bot.warn_count[user_id] = count

            if count >= 3:
                duration = datetime.timedelta(minutes=5)
                try:
                    await message.author.timeout(duration, reason="สแปมข้อความเกินกำหนด")
                    try:
                        await message.author.send(f"⚠️ คุณถูกระงับการพิมพ์ในเซิร์ฟเวอร์ {message.guild.name} เป็นเวลา 5 นาที เนื่องจากสแปม")
                    except:
                        pass
                    bot.warn_count[user_id] = 0
                    bot.user_messages[user_id] = []
                except:
                    pass
            else:
                warning = await message.channel.send(f"⚠️ {message.author.mention} **หยุดสแปม!** เตือนครั้งที่ {count}/3")
                await asyncio.sleep(3)
                await warning.delete()

    # รันคำสั่ง Prefix ปกติของแทน (ถ้ามี)
    await bot.process_commands(message)

# ---------- ระบบโดเนท (เพิ่มเติม) ----------
class DonateModal(discord.ui.Modal, title="ส่งซองของขวัญสนับสนุน"):
    link = discord.ui.TextInput(label="ลิงก์ซองทรูมันนี่ (10บ. ขึ้นไป)", placeholder="https://gift.truemoney.com/...")
    money = discord.ui.TextInput(label="จำนวนเงิน", placeholder="ระบุจำนวนเงิน")

    async def on_submit(self, interaction: discord.Interaction):
        try:
            if int(self.money.value) < 10:
                return await interaction.response.send_message("❌ ขั้นต่ำ 10 บาทครับ", ephemeral=True)
        except: 
            return await interaction.response.send_message("❌ ใส่ตัวเลขเท่านั้น", ephemeral=True)
        
        await interaction.response.defer(ephemeral=True)
        
        emb = discord.Embed(title="💰 มีรายการโดเนทใหม่!", color=discord.Color.gold())
        emb.add_field(name="จากคุณ", value=interaction.user.mention)
        emb.add_field(name="จำนวนเงิน", value=f"{self.money.value} บาท")
        emb.add_field(name="ลิงก์ซองของขวัญ", value=self.link.value)
        emb.set_footer(text="แอดมินท่านใดเห็นก่อนสามารถกดรับได้เลยครับ")

        admin_count = 0
        for member in interaction.guild.members:
            if member.guild_permissions.administrator and not member.bot:
                try:
                    await member.send(embed=emb)
                    admin_count += 1
                except:
                    pass
        
        await interaction.followup.send(f"✅ ส่งลิงก์โดเนทให้ทีมแอดมิน ({admin_count} ท่าน) เรียบร้อยแล้ว!", ephemeral=True)

class DonateView(discord.ui.View):
    def __init__(self): 
        super().__init__(timeout=None)
    @discord.ui.button(label="💸 โดเนทสนับสนุน", style=discord.ButtonStyle.success, emoji="💰")
    async def donate_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(DonateModal())

@bot.tree.command(name="setup_donate", description="ตั้งค่าระบบโดเนท")
@app_commands.describe(channel="ห้องที่จะส่ง", title="หัวข้อ", description="คำอธิบาย", image_url="ลิงก์รูปภาพ")
async def setup_donate(interaction: discord.Interaction, channel: discord.TextChannel, title: str, description: str, image_url: str):
    emb = discord.Embed(title=title, description=description, color=discord.Color.blue())
    if image_url.startswith("http"): 
        emb.set_image(url=image_url)
    await channel.send(embed=emb, view=DonateView())
    await interaction.response.send_message("✅ ติดตั้งระบบโดเนทเรียบร้อย", ephemeral=True)

# ---------- 1. ระบบรายงานปัญหา (โค้ดเดิมของแทน) ----------
class ReportModal(discord.ui.Modal, title="รายงานปัญหาในเซิร์ฟเวอร์"):
    problem = discord.ui.TextInput(label="พิมพ์ปัญหาของคุณที่นี่", style=discord.TextStyle.long)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        owner = interaction.guild.owner
        try:
            await owner.send(f"📢 **มีรายงานใหม่จาก {interaction.user}**\n```{self.problem.value}```")
            embed = discord.Embed(title="✅ รายงานสำเร็จ!", description="ระบบได้ส่งข้อความไปหาเจ้าของเซิร์ฟแล้ว", color=discord.Color.green())
            await interaction.followup.send(embed=embed, ephemeral=True)
        except:
            embed = discord.Embed(title="❌ ส่งไม่สำเร็จ", description="ไม่สามารถส่ง DM ไปหาเจ้าของเซิร์ฟได้", color=discord.Color.red())
            await interaction.followup.send(embed=embed, ephemeral=True)

class ReportButton(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
    @discord.ui.button(label="📩 รายงานปัญหา", style=discord.ButtonStyle.danger)
    async def report(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(ReportModal())

@bot.tree.command(name="report", description="ตั้ง UI รายงานปัญหาในห้องที่เลือก")
async def report_command(interaction: discord.Interaction, channel: discord.TextChannel):
    await channel.send("📣 หากพบปัญหาในเซิร์ฟเวอร์ กดปุ่มด้านล่างเพื่อรายงาน", view=ReportButton())
    await interaction.response.send_message("✅ ตั้ง UI รายงานปัญหาเรียบร้อย!", ephemeral=True)

# ---------- 2. ระบบยืนยันตัวตน (โค้ดเดิมของแทน) ----------
class VerifyModal(discord.ui.Modal, title="ยืนยันตัวตน"):
    name = discord.ui.TextInput(label="กรอกชื่อของคุณ", style=discord.TextStyle.short)
    def __init__(self, verify_channel, success_channel, role):
        super().__init__()
        self.verify_channel = verify_channel
        self.success_channel = success_channel
        self.role = role

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        user = interaction.user
        try:
            await self.success_channel.send(f"✅ {user.mention} ยืนยันตัวตนสำเร็จ! (ชื่อ: {self.name.value})")
            if self.role:
                await user.add_roles(self.role)
            embed = discord.Embed(title="🎉 ยืนยันตัวตนเรียบร้อย!", description=f"ขอบคุณ {user.mention}", color=discord.Color.green())
            await interaction.followup.send(embed=embed, ephemeral=True)
        except discord.Forbidden:
            await interaction.followup.send("❌ บอทไม่มีสิทธิ์ให้ยศ กรุณาตรวจสอบสิทธิ์ใน Server Settings → Roles", ephemeral=True)

class VerifyButton(discord.ui.View):
    def __init__(self, verify_channel, success_channel, role):
        super().__init__(timeout=None)
        self.verify_channel = verify_channel
        self.success_channel = success_channel
        self.role = role
    @discord.ui.button(label="✅ ยืนยันตัวตน", style=discord.ButtonStyle.success)
    async def verify(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(VerifyModal(self.verify_channel, self.success_channel, self.role))

@bot.tree.command(name="verify", description="ตั้งระบบยืนยันตัวตน")
async def verify_command(interaction: discord.Interaction, verify_channel: discord.TextChannel, success_channel: discord.TextChannel, role: discord.Role):
    await verify_channel.send("👤 กดยืนยันตัวตนด้านล่างเพื่อเริ่ม", view=VerifyButton(verify_channel, success_channel, role))
    await interaction.response.send_message("✅ ตั้งระบบยืนยันตัวตนเรียบร้อย!", ephemeral=True)

# ---------- 3. ส่งข้อความไปยังห้อง (โค้ดเดิมของแทน) ----------
@bot.tree.command(name="send_message", description="ส่งข้อความไปยังห้องที่เลือก")
async def send_message(interaction: discord.Interaction, channel: discord.TextChannel, message: str):
    await channel.send(message)
    await interaction.response.send_message("✅ ส่งข้อความเรียบร้อย!", ephemeral=True)

# ---------- 4. ส่ง DM ทุกคน (โค้ดเดิมของแทน) ----------
@bot.tree.command(name="dm_all", description="ส่ง DM ไปหาทุกคนในเซิร์ฟเวอร์")
async def dm_all(interaction: discord.Interaction, message: str):
    await interaction.response.send_message("📨 กำลังส่ง DM ...", ephemeral=True)
    count = 0
    async for member in interaction.guild.fetch_members(limit=None):
        if not member.bot:
            try:
                await member.send(message)
                count += 1
            except:
                pass
    await interaction.followup.send(f"✅ ส่งข้อความถึง {count} คนแล้ว!", ephemeral=True)

# ---------- 5. ส่ง DM หนึ่งคน (โค้ดเดิมของแทน) ----------
@bot.tree.command(name="dm_one", description="ส่ง DM ไปหาสมาชิกที่เลือก")
async def dm_one(interaction: discord.Interaction, member: discord.Member, message: str):
    try:
        await member.send(message)
        await interaction.response.send_message(f"✅ ส่งข้อความถึง {member} แล้ว!", ephemeral=True)
    except:
        await interaction.response.send_message("❌ ไม่สามารถส่งข้อความได้ (ปิด DM)", ephemeral=True)

# ---------- 6. ตั้งค่าห้องแจ้งคนเข้า/ออก (โค้ดเดิมของแทน) ----------
@bot.tree.command(name="setup_welcome", description="ตั้งค่าห้องแจ้งคนเข้าออก")
async def setup_welcome(interaction: discord.Interaction, join_channel: discord.TextChannel, leave_channel: discord.TextChannel):
    welcome_settings[interaction.guild.id] = {"join": join_channel.id, "leave": leave_channel.id}
    await interaction.response.send_message("✅ ตั้งค่าห้องแจ้งคนเข้าออกเรียบร้อย!", ephemeral=True)

@bot.event
async def on_member_join(member):
    data = welcome_settings.get(member.guild.id)
    if data:
        ch = member.guild.get_channel(data["join"])
        if ch: await ch.send(f"👋 ยินดีต้อนรับ {member.mention} เข้าสู่เซิร์ฟเวอร์!")

@bot.event
async def on_member_remove(member):
    data = welcome_settings.get(member.guild.id)
    if data:
        ch = member.guild.get_channel(data["leave"])
        if ch: await ch.send(f"😢 {member} ได้ออกจากเซิร์ฟเวอร์แล้ว")

# ---------- เริ่มรันระบบ ----------
if __name__ == "__main__":
    keep_alive()
    token = os.environ.get('TOKEN')
    if token:
        bot.run(token)
    else:
        print("❌ ไม่พบ TOKEN ใน Environment Variables!")
