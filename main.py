import os
import discord
from discord.ext import commands, tasks
import asyncio
import re
import requests
import json
import time
import random
from datetime import datetime
import urllib3
import sqlite3
from myserver import server_on
import aiohttp
import asyncio
import datetime

# --- การตั้งค่า (CONFIG) ---
TOKEN = 'YOUR_DISCORD_BOT_TOKEN'
WEB_API_URL = 'https://your-website.com/api' # URL เว็บของคุณ
WEB_API_KEY = 'YOUR_API_KEY'
ADMIN_CHANNEL_ID = 1448340407942647828  # ห้องหลังบ้าน
MAIN_CHANNEL_ID = 1448339573938720808   # ห้องหน้าเติมเงิน

# ตั้งค่า Intents
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

# --- จำลองฐานข้อมูล (ในงานจริงควรใช้ SQLite หรือ MySQL) ---
# users_db = {user_id: balance}
users_db = {} 
# stock_cache = {product_id: {name, price, stock}}
stock_cache = {}

# --- ส่วนของการเชื่อมต่อ API (ต้องแก้ตามเว็บของคุณ) ---
async def fetch_products_from_web():
    """ดึงข้อมูลสินค้าจากเว็บของคุณ"""
    # ในการใช้งานจริง:
    # async with aiohttp.ClientSession() as session:
    #     async with session.get(f"{WEB_API_URL}/products", headers={"Auth": WEB_API_KEY}) as resp:
    #         return await resp.json()
    
    # จำลองข้อมูลส่งกลับมา
    print("[System] Fetching products...")
    return {
        "p1": {"name": "YouTube Premium", "price": 50, "stock": 10},
        "p2": {"name": "Netflix 4K", "price": 120, "stock": 5}
    }

async def notify_admin(message):
    admin = await bot.fetch_user(ADMIN_ID)
    if admin:
        await admin.send(f"🔔 Admin Alert: {message}")

# --- Background Task: อัปเดตสินค้าอัตโนมัติ ---
@tasks.loop(minutes=5) # ทำงานทุกๆ 5 นาที
async def update_stock_task():
    global stock_cache
    try:
        data = await fetch_products_from_web()
        stock_cache = data
        print(f"[Auto-Update] อัปเดตสินค้าเรียบร้อย: {len(stock_cache)} รายการ")
    except Exception as e:
        print(f"[Error] อัปเดตสินค้าล้มเหลว: {e}")

# --- Event: เมื่อบอทพร้อมทำงาน ---
@bot.event
async def on_ready():
    print(f'Logged in as {bot.user}')
    update_stock_task.start() # เริ่มระบบอัปเดตอัตโนมัติ

# --- Command: เช็คสินค้า ---
@bot.command()
async def stock(ctx):
    embed = discord.Embed(title="🛒 รายการสินค้าพรีเมี่ยม", color=discord.Color.blue())
    
    if not stock_cache:
        await ctx.send("กำลังโหลดข้อมูลสินค้า... กรุณารอสักครู่")
        return

    for pid, info in stock_cache.items():
        status = "✅ พร้อมส่ง" if info['stock'] > 0 else "❌ สินค้าหมด"
        embed.add_field(
            name=f"{info['name']} (ID: {pid})",
            value=f"ราคา: {info['price']} บาท | สถานะ: {status}",
            inline=False
        )
    await ctx.send(embed=embed)

# --- Command: เช็คเงินคงเหลือ ---
@bot.command()
async def balance(ctx):
    bal = users_db.get(ctx.author.id, 0.0)
    await ctx.send(f"💰 ยอดเงินคงเหลือของ {ctx.author.name}: **{bal:.2f} บาท**")

# --- Command: เติมเงิน (ซองอั่งเปา TrueMoney / สลิป) ---
@bot.command()
async def topup(ctx, link_or_ref: str):
    """
    เติมเงินด้วยลิงก์ซองของขวัญ (Truemoney) หรือ เลขอ้างอิง
    """
    user_id = ctx.author.id
    
    await ctx.send("🔄 กำลังตรวจสอบยอดเงิน...")

    # !!! ส่วนสำคัญ: ตรงนี้ต้องเชื่อม API ตรวจสอบสลิป หรือ API แกะซองวอเลท !!!
    # ตัวอย่าง Logic (ต้องใช้ Library ภายนอกช่วย เช่น tmtopup หรือ slipok)
    
    # สมมติว่าตรวจสอบสำเร็จและได้เงินมา 100 บาท
    amount_received = 0
    success = False
    
    # --- จำลองการตรวจสอบ (Mock Logic) ---
    if "truemoney" in link_or_ref: 
        amount_received = 100 # สมมติว่าลิงก์นี้มี 100 บาท
        success = True
    # ----------------------------------

    if success:
        current_bal = users_db.get(user_id, 0.0)
        users_db[user_id] = current_bal + amount_received
        
        await ctx.send(f"✅ เติมเงินสำเร็จ! ได้รับ {amount_received} บาท\nยอดเงินรวม: {users_db[user_id]} บาท")
        await notify_admin(f"User {ctx.author.name} เติมเงิน {amount_received} บาท")
    else:
        await ctx.send("❌ เติมเงินไม่สำเร็จ ลิงก์ผิดหรือถูกใช้ไปแล้ว")

# --- Command: ซื้อสินค้า ---
@bot.command()
async def buy(ctx, product_id: str):
    user_id = ctx.author.id
    current_bal = users_db.get(user_id, 0.0)

    # 1. เช็คว่ามีสินค้าไหม
    if product_id not in stock_cache:
        await ctx.send("❌ ไม่พบสินค้านี้")

Novelty, [12/14/2025 6:08 PM]
return

    product = stock_cache[product_id]
    
    # 2. เช็คสต็อก
    if product['stock'] <= 0:
        await ctx.send("❌ สินค้าหมดชั่วคราว")
        return

    # 3. เช็คเงิน
    if current_bal < product['price']:
        await ctx.send(f"❌ เงินไม่พอ (ขาด {product['price'] - current_bal} บาท)")
        return

    # 4. ทำการซื้อ (หักเงิน และ ส่งของ)
    users_db[user_id] -= product['price']
    
    # --- เชื่อม API เพื่อดึง "โค้ด/ID พรีเมี่ยม" จากเว็บ ---
    # async with session.post(BUY_API_URL, data={'id': product_id}) as resp:
    #     item_data = await resp.json()
    item_sent = "USER:PASS | Premium Account" # สมมติว่าได้ข้อมูลมาแล้ว

    # ลดสต็อกใน cache (เพื่อให้แสดงผลทันที ก่อนรอบอัปเดตถัดไป)
    stock_cache[product_id]['stock'] -= 1

    # ส่งสินค้าทาง DM
    try:
        await ctx.author.send(f"✅ สั่งซื้อสำเร็จ: {product['name']}\n📦 สินค้า: `{item_sent}`\nขอบคุณที่ใช้บริการครับ")
        await ctx.send(f"✅ {ctx.author.mention} ซื้อ {product['name']} เรียบร้อย! เช็ค DM ครับ")
        await notify_admin(f"User {ctx.author.name} ซื้อ {product['name']} ราคา {product['price']} บาท")
    except discord.Forbidden:
        await ctx.send("❌ ไม่สามารถส่งข้อความหาคุณได้ กรุณาเปิด DM")
        # คืนเงินถ้าส่งไม่ได้
        users_db[user_id] += product['price']

# รันบอท
bot.run(TOKEN)
    server_on()


    bot.run(os.getenv('TOKEN'))




