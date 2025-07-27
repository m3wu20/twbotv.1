from ast import Not
import discord
from discord.ext import commands
from discord import app_commands
import requests
import json
import random
import os


WCA_BASE_URL = "https://www.worldcubeassociation.org/api/v0/persons/"

DATA_FILE = "users.json"
OWNER_ID = 1388145500099973283  # 注意轉成 int
ADMIN_IDS = {1389536857200656385}
WCA_ROLE_ID = 1389535445368438794

GROUP_WITH_ID = "1389535445368438794"
GROUP_NO_ID = "1392134495271911554"

intents = discord.Intents.default()
intents.members = True  # 改暱稱需要 members intent
intents.message_content = True
client = discord.Client(intents=intents)
tree = app_commands.CommandTree(client)

bot = commands.Bot(command_prefix='!', intents=intents)


def load_data():
    if not os.path.exists(DATA_FILE):
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump({}, f)
        return {}
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def get_wca_user(wca_id):
    url = f"https://www.worldcubeassociation.org/api/v0/persons/{wca_id}"
    r = requests.get(url)
    if r.status_code == 200:
        return r.json()
    return None

@tree.command(name="wca", description="查詢WCA選手資料")
@app_commands.describe(wcaid="輸入WCA ID")
async def wca(interaction: discord.Interaction, wcaid: str):
    await interaction.response.defer()

    wca_user = get_wca_user(wcaid)
    if not wca_user:
        await interaction.followup.send("查無此WCA選手", ephemeral=True)
        return

    person = wca_user.get("person", {})
    name = person.get("name", "未知")
    name_native = person.get("name_in_native_script")
    country = person.get("country_iso2", "")
    wca_id = person.get("wca_id", "")
    competition_count = wca_user.get("competition_count", 0)
    country_flag = f":flag_{country.lower()}:" if country else ""
    new_nick = f"{name} ({name_native})" if name_native else name

    # 正確取得 WCA 頭像
    avatar = wca_user.get("user", {}).get("avatar", {})
    avatar_url = avatar.get("url") or "https://www.worldcubeassociation.org/assets/WCA_logo_square-200.png"

    # 嘗試改 Discord 暱稱
    member = interaction.guild.get_member(interaction.user.id)
    try:
        await member.edit(nick=new_nick)
    except Exception as e:
        print(f"改暱稱失敗: {e}")

    # 加入身分組
    role = interaction.guild.get_role(WCA_ROLE_ID)
    if role:
        try:
            await member.add_roles(role)
        except Exception as e:
            print(f"加入 WCA 身分組失敗: {e}")

    # 建立 Embed
    embed = discord.Embed(
        title="✅ WCA 身分綁定成功",
        description=(
            f"已更新暱稱為：{new_nick}\n"
            f"WCA ID：{wca_id}\n"
            f"國籍：{country} {country_flag}\n"
            f"參加比賽次數：{competition_count} 場"
        ),
        color=0x00FF00,
    )
    embed.set_thumbnail(url=avatar_url)
    embed.set_footer(text="由TW魔術方塊交流群 BOT 提供")

    class WCAButton(discord.ui.View):
        def __init__(self):
            super().__init__()
            self.add_item(discord.ui.Button(label="前往 WCA 頁面", url=f"{WCA_BASE_URL}{wca_id}"))

    await interaction.followup.send(embed=embed, view=WCAButton())


@tree.command(name="wca_set", description="管理員設定用戶的WCA ID")
@app_commands.describe(user_id="用戶 Discord ID", wca_id="WCA ID")
async def wca_set(interaction: discord.Interaction, user_id: str, wca_id: str):
    if interaction.user.id != OWNER_ID and interaction.user.id not in ADMIN_IDS:
        await interaction.response.send_message("你沒有權限使用此指令", ephemeral=True)
        return

    users = load_data()
    wca_user = get_wca_user(wca_id)
    if not wca_user:
        await interaction.response.send_message("無效的WCA ID", ephemeral=True)
        return

    if user_id not in users:
        users[user_id] = {}
    users[user_id]["wca_id"] = wca_id
    users[user_id]["nickname"] = wca_user["name"]
    users[user_id]["group"] = GROUP_WITH_ID
    save_data(users)
    await interaction.response.send_message(f"成功設定 {user_id} 的WCA ID為 {wca_id}")


@tree.command(name="設定暱稱", description="設定自己的暱稱 (無WCA ID時用)")
@app_commands.describe(nickname="暱稱")
async def set_nickname(interaction: discord.Interaction, nickname: str):
    users = load_data()
    user_id = str(interaction.user.id)
    users.setdefault(user_id, {})
    users[user_id]["nickname"] = nickname
    users[user_id].pop("wca_id", None)
    users[user_id]["group"] = GROUP_NO_ID
    save_data(users)

    # 更改暱稱
    member = interaction.guild.get_member(interaction.user.id)
    try:
        await member.edit(nick=nickname)
    except Exception as e:
        print(f"改暱稱失敗: {e}")

    # 加入身分組
    role = interaction.guild.get_role(1392134495271911554)
    if role:
        try:
            await member.add_roles(role)
        except Exception as e:
            print(f"加入無WCA ID身分組失敗: {e}")

    await interaction.response.send_message(f"暱稱設定為 {nickname}，且無 WCA ID")

@tree.command(name="抽獎", description="管理員抽獎")
async def lottery(interaction: discord.Interaction):
    if interaction.user.id != OWNER_ID and interaction.user.id not in ADMIN_IDS:
        await interaction.response.send_message("你沒有權限使用此指令", ephemeral=True)
        return

    users = load_data()
    participants = [uid for uid, info in users.items() if "nickname" in info]
    if not participants:
        await interaction.response.send_message("目前沒有可抽獎的成員", ephemeral=True)
        return
    winner = random.choice(participants)
    await interaction.response.send_message(f"抽獎結果！得獎者是：{users[winner]['nickname']} (ID: {winner})")


@bot.event
async def on_ready():
    print(f"機器人已啟動：{bot.user}")

@bot.event
async def on_member_join(member: discord.Member):
    channel = member.guild.get_channel(1389537178807173170)
    if not channel:
        return

    guild_name = member.guild.name

    # 建立嵌入訊息
    embed = discord.Embed(
        title=f"歡迎加入 **{guild_name}**！",
        description=(
            "請選擇下面的按鈕：\n"
            "如果你有 WCA ID 請點「怎麼使用/wca」\n"
            "如果你沒有 WCA ID 請點「怎麼使用/設定暱稱」"
        ),
        color=discord.Color.blue()
    )
    embed.set_footer(text="by TW魔術方塊交流群 [beta]")

    # 建立按鈕元件
    class WelcomeView(discord.ui.View):
        @discord.ui.button(label="怎麼使用/wca", style=discord.ButtonStyle.primary, custom_id="wca_id")
        async def wca_button(self, interaction: discord.Interaction, button: discord.ui.Button):
            await interaction.response.send_message("/wca 輸入你的ID\n"
            "就可以了喔<3", ephemeral=True)

        @discord.ui.button(label="怎麼使用/設定暱稱", style=discord.ButtonStyle.secondary, custom_id="set_nick")
        async def nick_button(self, interaction: discord.Interaction, button: discord.ui.Button):
            await interaction.response.send_message("/設定暱稱 你的暱稱！\n" \
            "就可以了喔<3", ephemeral=True)



    view = WelcomeView()

    await channel.send(content=member.mention, embed=embed, view=view)





bot.run("bottoken")
