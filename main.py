import os
import discord
from discord.ext import commands
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

# ปิด warning SSL
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ค่าคงที่

ADMIN_CHANNEL_ID = 1438091015948075008  # ห้องหลังบ้าน
MAIN_CHANNEL_ID = 1438037309265154119   # ห้องหน้าเติมเงิน

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix='!', intents=intents)

# ระบบฐานข้อมูล
def init_db():
    conn = sqlite3.connect('bot_data.db')
    cursor = conn.cursor()
    
    # ตารางสินค้า
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            price INTEGER NOT NULL,
            stock TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # ตารางเบอร์รับเงิน
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS wallets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            phone_number TEXT NOT NULL UNIQUE,
            is_active BOOLEAN DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # ตารางยอดเงินของผู้ใช้
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_balance (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            balance INTEGER DEFAULT 0,
            total_deposit INTEGER DEFAULT 0,
            total_spent INTEGER DEFAULT 0,
            last_deposit TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(user_id)
        )
    ''')
    
    # ตารางประวัติการเติมเงิน
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS deposit_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            amount INTEGER NOT NULL,
            voucher_hash TEXT,
            status TEXT NOT NULL,
            product_id INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # ตารางประวัติการสั่งซื้อ
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS order_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            product_id INTEGER NOT NULL,
            product_name TEXT NOT NULL,
            price INTEGER NOT NULL,
            payment_method TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    conn.commit()
    conn.close()

def get_wallet_number():
    """ดึงเบอร์รับเงินจากฐานข้อมูล"""
    conn = sqlite3.connect('bot_data.db')
    cursor = conn.cursor()
    cursor.execute('SELECT phone_number FROM wallets WHERE is_active = 1 LIMIT 1')
    result = cursor.fetchone()
    conn.close()
    return result[0] if result else None

def set_wallet_number(phone_number):
    """ตั้งค่าเบอร์รับเงิน"""
    conn = sqlite3.connect('bot_data.db')
    cursor = conn.cursor()
    
    # ปิดใช้งานเบอร์เก่าทั้งหมด
    cursor.execute('UPDATE wallets SET is_active = 0')
    
    # เพิ่มเบอร์ใหม่
    cursor.execute('INSERT OR REPLACE INTO wallets (phone_number, is_active) VALUES (?, 1)', 
                  (phone_number,))
    
    conn.commit()
    conn.close()

def get_products():
    """ดึงรายการสินค้าทั้งหมด"""
    conn = sqlite3.connect('bot_data.db')
    cursor = conn.cursor()
    cursor.execute('SELECT id, name, price, stock FROM products ORDER BY id')
    products = cursor.fetchall()
    conn.close()
    return products

def get_product_by_id(product_id):
    """ดึงสินค้าตาม ID"""
    conn = sqlite3.connect('bot_data.db')
    cursor = conn.cursor()
    cursor.execute('SELECT id, name, price, stock FROM products WHERE id = ?', (product_id,))
    product = cursor.fetchone()
    conn.close()
    return product

def add_product(name, price, stock):
    """เพิ่มสินค้าใหม่"""
    conn = sqlite3.connect('bot_data.db')
    cursor = conn.cursor()
    cursor.execute('INSERT INTO products (name, price, stock) VALUES (?, ?, ?)', 
                  (name, price, stock))
    product_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return product_id

def delete_product(product_id):
    """ลบสินค้า"""
    conn = sqlite3.connect('bot_data.db')
    cursor = conn.cursor()
    cursor.execute('DELETE FROM products WHERE id = ?', (product_id,))
    conn.commit()
    conn.close()

def get_product_stock(product_id):
    """ดึงสต็อกสินค้า"""
    conn = sqlite3.connect('bot_data.db')
    cursor = conn.cursor()
    cursor.execute('SELECT stock FROM products WHERE id = ?', (product_id,))
    result = cursor.fetchone()
    conn.close()
    return result[0] if result else None

def update_product_stock(product_id, new_stock):
    """อัพเดทสต็อกสินค้า"""
    conn = sqlite3.connect('bot_data.db')
    cursor = conn.cursor()
    cursor.execute('UPDATE products SET stock = ? WHERE id = ?', (new_stock, product_id))
    conn.commit()
    conn.close()

def add_product_stock(product_id, additional_stock):
    """เพิ่มสต็อกสินค้า"""
    conn = sqlite3.connect('bot_data.db')
    cursor = conn.cursor()
    
    # ดึงสต็อกปัจจุบัน
    cursor.execute('SELECT stock FROM products WHERE id = ?', (product_id,))
    result = cursor.fetchone()
    current_stock = result[0] if result else ""
    
    # เพิ่มสต็อกใหม่
    if current_stock:
        new_stock = current_stock + "\n" + additional_stock
    else:
        new_stock = additional_stock
    
    # อัพเดทสต็อก
    cursor.execute('UPDATE products SET stock = ? WHERE id = ?', (new_stock, product_id))
    conn.commit()
    conn.close()
    
    return len(additional_stock.splitlines())

def get_user_balance(user_id):
    """ดึงยอดเงินของผู้ใช้"""
    conn = sqlite3.connect('bot_data.db')
    cursor = conn.cursor()
    
    # ตรวจสอบว่ามีคอลัมน์ total_spent หรือไม่
    cursor.execute("PRAGMA table_info(user_balance)")
    columns = [column[1] for column in cursor.fetchall()]
    
    if 'total_spent' in columns:
        cursor.execute('SELECT balance, total_deposit, total_spent FROM user_balance WHERE user_id = ?', (user_id,))
        result = cursor.fetchone()
    else:
        # ถ้ายังไม่มีคอลัมน์ total_spent
        cursor.execute('SELECT balance, total_deposit FROM user_balance WHERE user_id = ?', (user_id,))
        result = cursor.fetchone()
        if result:
            result = (result[0], result[1], 0)  # เพิ่ม total_spent เป็น 0
    
    conn.close()
    
    if result:
        return {'balance': result[0], 'total_deposit': result[1], 'total_spent': result[2] if len(result) > 2 else 0}
    else:
        # สร้าง user ใหม่ถ้ายังไม่มี
        conn = sqlite3.connect('bot_data.db')
        cursor = conn.cursor()
        
        # ตรวจสอบโครงสร้างตารางอีกครั้ง
        cursor.execute("PRAGMA table_info(user_balance)")
        columns = [column[1] for column in cursor.fetchall()]
        
        if 'total_spent' in columns:
            cursor.execute('INSERT INTO user_balance (user_id, balance, total_deposit, total_spent) VALUES (?, 0, 0, 0)', (user_id,))
        else:
            cursor.execute('INSERT INTO user_balance (user_id, balance, total_deposit) VALUES (?, 0, 0)', (user_id,))
        
        conn.commit()
        conn.close()
        return {'balance': 0, 'total_deposit': 0, 'total_spent': 0}

def update_user_balance(user_id, amount):
    """อัพเดทยอดเงินผู้ใช้ (เพิ่มเงิน)"""
    conn = sqlite3.connect('bot_data.db')
    cursor = conn.cursor()
    
    # ตรวจสอบโครงสร้างตาราง
    cursor.execute("PRAGMA table_info(user_balance)")
    columns = [column[1] for column in cursor.fetchall()]
    
    if 'total_spent' in columns:
        # อัพเดทยอดเงินแบบมี total_spent
        cursor.execute('''
            INSERT INTO user_balance (user_id, balance, total_deposit, total_spent) 
            VALUES (?, ?, ?, 0)
            ON CONFLICT(user_id) DO UPDATE SET 
            balance = balance + ?,
            total_deposit = total_deposit + ?,
            last_deposit = CURRENT_TIMESTAMP
        ''', (user_id, amount, amount, amount, amount))
    else:
        # อัพเดทยอดเงินแบบไม่มี total_spent
        cursor.execute('''
            INSERT INTO user_balance (user_id, balance, total_deposit) 
            VALUES (?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET 
            balance = balance + ?,
            total_deposit = total_deposit + ?,
            last_deposit = CURRENT_TIMESTAMP
        ''', (user_id, amount, amount, amount, amount))
    
    conn.commit()
    conn.close()

def deduct_user_balance(user_id, amount):
    """หักยอดเงินผู้ใช้"""
    conn = sqlite3.connect('bot_data.db')
    cursor = conn.cursor()
    
    # ตรวจสอบโครงสร้างตาราง
    cursor.execute("PRAGMA table_info(user_balance)")
    columns = [column[1] for column in cursor.fetchall()]
    
    if 'total_spent' in columns:
        # หักยอดเงินแบบมี total_spent
        cursor.execute('''
            UPDATE user_balance 
            SET balance = balance - ?, 
                total_spent = total_spent + ?
            WHERE user_id = ? AND balance >= ?
        ''', (amount, amount, user_id, amount))
    else:
        # หักยอดเงินแบบไม่มี total_spent
        cursor.execute('''
            UPDATE user_balance 
            SET balance = balance - ?
            WHERE user_id = ? AND balance >= ?
        ''', (amount, user_id, amount))
    
    success = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return success

def add_deposit_history(user_id, amount, voucher_hash, status, product_id=None):
    """เพิ่มประวัติการเติมเงิน"""
    conn = sqlite3.connect('bot_data.db')
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO deposit_history (user_id, amount, voucher_hash, status, product_id)
        VALUES (?, ?, ?, ?, ?)
    ''', (user_id, amount, voucher_hash, status, product_id))
    conn.commit()
    conn.close()

def add_order_history(user_id, product_id, product_name, price, payment_method):
    """เพิ่มประวัติการสั่งซื้อ"""
    conn = sqlite3.connect('bot_data.db')
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO order_history (user_id, product_id, product_name, price, payment_method)
        VALUES (?, ?, ?, ?, ?)
    ''', (user_id, product_id, product_name, price, payment_method))
    conn.commit()
    conn.close()

# ตัวแปรเก็บ message ID สำหรับอัพเดทแบบ real-time
shop_message_id = None
admin_message_id = None

async def update_shop_display():
    """อัพเดทการแสดงผลร้านค้าแบบ real-time"""
    global shop_message_id
    
    channel = bot.get_channel(MAIN_CHANNEL_ID)
    if not channel:
        return
    
    products = get_products()
    
    embed = discord.Embed(
        title="🛒 ขายสินค้าต่างๆ",
        description="**เลือกสินค้าที่ต้องการจากเมนูด้านล่างนี้**\n\nหลังจากเลือกสินค้าแล้ว ให้ทำการเติมเงินตามจำนวนที่กำหนด",
        color=0x00ff00
    )
    
    # เพิ่มข้อมูลสินค้าลงใน embed
    if products:
        for product in products:
            product_id, name, price, stock = product
            stock_count = len(stock.splitlines())
            embed.add_field(
                name=f"🎯 {name} - {price} บาท",
                value=f"📦 สต็อก: {stock_count} รายการ",
                inline=False
            )
    else:
        embed.add_field(
            name="📦 กำลังเตรียมสินค้า",
            value="กรุณารอสักครู่ หรือติดต่อแอดมิน",
            inline=False
        )
    
    view = ProductView(products)
    
    try:
        if shop_message_id:
            # อัพเดทข้อความเดิม
            message = await channel.fetch_message(shop_message_id)
            await message.edit(embed=embed, view=view)
        else:
            # ส่งข้อความใหม่
            message = await channel.send(embed=embed, view=view)
            shop_message_id = message.id
    except:
        # ส่งข้อความใหม่ถ้าไม่พบข้อความเดิม
        message = await channel.send(embed=embed, view=view)
        shop_message_id = message.id

async def update_admin_display():
    """อัพเดทการแสดงผลหลังบ้านแบบ real-time"""
    global admin_message_id
    
    channel = bot.get_channel(ADMIN_CHANNEL_ID)
    if not channel:
        return
    
    embed = discord.Embed(
        title="🛠️ ระบบหลังบ้าน - การตั้งค่า",
        description=(
            "**ใช้งานปุ่มด้านล่างสำหรับการตั้งค่าระบบ:**\n\n"
            "📱 **ตั้งค่าเบอร์รับเงิน** - กำหนดเบอร์สำหรับรับเงิน\n"
            "📦 **เพิ่มสินค้า** - เพิ่มสินค้าใหม่เข้าสู่ระบบ\n"
            "🗑️ **ลบสินค้า** - ลบสินค้าออกจากระบบ\n"
            "📦 **จัดการสต็อก** - เพิ่มสต็อกให้สินค้า\n"
            "📊 **ดูสินค้าทั้งหมด** - ตรวจสอบรายการสินค้าและสต็อก\n"
            "🔄 **อัพเดทร้านค้า** - รีเฟรชหน้าจอหลัก"
        ),
        color=0x3498db
    )
    
    view = AdminView()
    
    try:
        if admin_message_id:
            # อัพเดทข้อความเดิม
            message = await channel.fetch_message(admin_message_id)
            await message.edit(embed=embed, view=view)
        else:
            # ส่งข้อความใหม่
            message = await channel.send(embed=embed, view=view)
            admin_message_id = message.id
    except:
        # ส่งข้อความใหม่ถ้าไม่พบข้อความเดิม
        message = await channel.send(embed=embed, view=view)
        admin_message_id = message.id

# Modal สำหรับตั้งค่าเบอร์รับเงิน
class WalletModal(discord.ui.Modal):
    def __init__(self):
        super().__init__(title="📱 ตั้งค่าเบอร์รับเงิน", timeout=300)
        self.phone_number = discord.ui.TextInput(
            label="เบอร์รับเงิน TrueMoney",
            placeholder="0637166416 (ใส่เฉพาะตัวเลข)",
            style=discord.TextStyle.short,
            required=True,
            max_length=10,
            min_length=10
        )
        self.add_item(self.phone_number)

    async def on_submit(self, interaction: discord.Interaction):
        phone = self.phone_number.value.strip()
        
        # ตรวจสอบว่าเป็นตัวเลขทั้งหมด
        if not phone.isdigit() or len(phone) != 10:
            await interaction.response.send_message("❌ กรุณากรอกเบอร์โทรศัพท์ 10 หลัก (ตัวเลขเท่านั้น)", ephemeral=True)
            return
        
        # บันทึกเบอร์รับเงิน
        set_wallet_number(phone)
        
        await interaction.response.send_message(f"✅ ตั้งค่าเบอร์รับเงินเป็น: {phone}", ephemeral=True)
        await update_admin_display()

# Modal สำหรับเพิ่มสินค้า
class AddProductModal(discord.ui.Modal):
    def __init__(self):
        super().__init__(title="📦 เพิ่มสินค้าใหม่", timeout=300)
        
        self.product_name = discord.ui.TextInput(
            label="ชื่อสินค้า",
            placeholder="ตัวอย่าง: 100 Point",
            style=discord.TextStyle.short,
            required=True,
            max_length=100
        )
        
        self.product_price = discord.ui.TextInput(
            label="ราคาสินค้า (บาท)",
            placeholder="ตัวอย่าง: 50",
            style=discord.TextStyle.short,
            required=True,
            max_length=10
        )
        
        self.product_stock = discord.ui.TextInput(
            label="สต็อกสินค้า (1 บรรทัด = 1 สต็อก)",
            placeholder="ตัวอย่าง:\nusername1|password1\nusername2|password2",
            style=discord.TextStyle.paragraph,
            required=True
        )
        
        self.add_item(self.product_name)
        self.add_item(self.product_price)
        self.add_item(self.product_stock)

    async def on_submit(self, interaction: discord.Interaction):
        name = self.product_name.value.strip()
        price_str = self.product_price.value.strip()
        stock = self.product_stock.value.strip()
        
        # ตรวจสอบราคา
        if not price_str.isdigit():
            await interaction.response.send_message("❌ กรุณากรอกราคาเป็นตัวเลขเท่านั้น", ephemeral=True)
            return
        
        price = int(price_str)
        
        # เพิ่มสินค้า
        product_id = add_product(name, price, stock)
        
        await interaction.response.send_message(f"✅ เพิ่มสินค้า {name} ราคา {price} บาท สำเร็จ", ephemeral=True)
        await update_shop_display()
        await update_admin_display()

# Modal สำหรับเพิ่มสต็อก
class AddStockModal(discord.ui.Modal):
    def __init__(self, product_id, product_name):
        super().__init__(title=f"📦 เพิ่มสต็อก {product_name}", timeout=300)
        self.product_id = product_id
        self.product_name = product_name
        
        self.additional_stock = discord.ui.TextInput(
            label="สต็อกเพิ่มเติม (1 บรรทัด = 1 สต็อก)",
            placeholder="ตัวอย่าง:\nusername3|password3\nusername4|password4",
            style=discord.TextStyle.paragraph,
            required=True
        )
        
        self.add_item(self.additional_stock)

    async def on_submit(self, interaction: discord.Interaction):
        additional_stock = self.additional_stock.value.strip()
        
        if not additional_stock:
            await interaction.response.send_message("❌ กรุณากรอกสต็อกเพิ่มเติม", ephemeral=True)
            return
        
        # เพิ่มสต็อก
        added_count = add_product_stock(self.product_id, additional_stock)
        
        await interaction.response.send_message(f"✅ เพิ่มสต็อก {added_count} รายการให้ {self.product_name} สำเร็จ", ephemeral=True)
        await update_shop_display()

# Select สำหรับเลือกสินค้า
class ProductSelect(discord.ui.Select):
    def __init__(self, products):
        options = []
        for product in products:
            product_id, name, price, stock = product
            stock_count = len(stock.splitlines())
            options.append(
                discord.SelectOption(
                    label=f"{name} - {price} บาท",
                    value=str(product_id),
                    description=f"สต็อก: {stock_count} รายการ"
                )
            )
        
        super().__init__(
            placeholder="🎯 เลือกสินค้าที่ต้องการเติมเงิน",
            min_values=1,
            max_values=1,
            options=options
        )
    
    async def callback(self, interaction: discord.Interaction):
        product_id = int(self.values[0])
        product = get_product_by_id(product_id)
        
        if not product:
            await interaction.response.send_message("❌ ไม่พบสินค้านี้", ephemeral=True)
            return
        
        product_id, name, price, stock = product
        wallet_number = get_wallet_number()
        
        if not wallet_number:
            await interaction.response.send_message("❌ ระบบยังไม่พร้อม กรุณาตั้งค่าเบอร์รับเงินก่อน", ephemeral=True)
            return
        
        # ตรวจสอบสต็อก
        if not stock or not stock.strip():
            await interaction.response.send_message("❌ สินค้านี้หมดสต็อกแล้ว", ephemeral=True)
            return
        
        # แสดงข้อมูลการเติมเงิน
        user_balance = get_user_balance(str(interaction.user.id))
        
        embed = discord.Embed(
            title="💰 การเติมเงิน",
            description=(
                f"**สินค้า:** {name}\n"
                f"**ราคา:** {price} บาท\n"
                f"**เบอร์รับเงิน:** {wallet_number}\n"
                f"**ยอดเงินในบัญชี:** {user_balance['balance']} บาท\n\n"
                f"⚠️ **กรุณาเติมเงินให้ครบ {price} บาท**\n"
                f"ระบบจะหักเงิน {price} บาทอัตโนมัติเมื่อเติมเงินสำเร็จ"
            ),
            color=0xffff00
        )
        
        view = PaymentMethodView(product_id, price, name)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

# View สำหรับเลือกสินค้า
class ProductView(discord.ui.View):
    def __init__(self, products):
        super().__init__(timeout=None)
        if products:
            self.add_item(ProductSelect(products))
            
            # เพิ่มปุ่มตรวจสอบยอดเงิน
            self.add_item(discord.ui.Button(
                label="💳 ตรวจสอบยอดเงิน",
                style=discord.ButtonStyle.blurple,
                custom_id="check_balance",
                emoji="💰"
            ))
        else:
            # ถ้ายังไม่มีสินค้า ให้แสดงปุ่มแจ้งเตือน
            self.add_item(discord.ui.Button(
                label="📦 ยังไม่มีสินค้าในระบบ",
                style=discord.ButtonStyle.secondary,
                disabled=True
            ))

# View สำหรับเลือกวิธีการชำระเงิน
class PaymentMethodView(discord.ui.View):
    def __init__(self, product_id, price, product_name):
        super().__init__(timeout=300)
        self.product_id = product_id
        self.price = price
        self.product_name = product_name
    
    @discord.ui.button(
        label="💰 เติมเงินด้วยอั่งเปา",
        style=discord.ButtonStyle.success,
        emoji="🎁"
    )
    async def voucher_payment(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = VoucherModal(self.product_id, self.price, self.product_name)
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(
        label="💳 ใช้ยอดเงินในบัญชี",
        style=discord.ButtonStyle.primary,
        emoji="💎"
    )
    async def balance_payment(self, interaction: discord.Interaction, button: discord.ui.Button):
        user_balance = get_user_balance(str(interaction.user.id))
        
        if user_balance['balance'] < self.price:
            await interaction.response.send_message(
                f"❌ ยอดเงินไม่เพียงพอ\nยอดเงินในบัญชี: {user_balance['balance']} บาท\nต้องการ: {self.price} บาท", 
                ephemeral=True
            )
            return
        
        # ใช้ยอดเงินในบัญชี
        await process_balance_payment(interaction, self.product_id, self.price, self.product_name)

# Modal สำหรับเติมเงินด้วยลิงก์อั่งเปา
class VoucherModal(discord.ui.Modal):
    def __init__(self, product_id, price, product_name):
        super().__init__(title="💰 กรอกลิงก์อั่งเปา", timeout=300)
        self.product_id = product_id
        self.price = price
        self.product_name = product_name
        
        self.voucher_link = discord.ui.TextInput(
            label="ลิงก์ซองอั่งเปา TrueMoney",
            placeholder="https://gift.truemoney.com/campaign/?v=XXXXXXXXXX",
            style=discord.TextStyle.paragraph,
            required=True,
            max_length=500
        )
        self.add_item(self.voucher_link)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        
        link = self.voucher_link.value.strip()
        wallet_number = get_wallet_number()
        
        if not wallet_number:
            await interaction.followup.send("❌ ระบบยังไม่พร้อม กรุณาตั้งค่าเบอร์รับเงินก่อน", ephemeral=True)
            return
        
        voucher_hash = extract_voucher_hash(link)
        if not voucher_hash:
            await interaction.followup.send("❌ ลิงก์ไม่ถูกต้อง กรุณาตรวจสอบลิงก์อั่งเปาให้ถูกต้อง", ephemeral=True)
            return
        
        # ตรวจสอบสต็อกก่อน
        stock = get_product_stock(self.product_id)
        if not stock or not stock.strip():
            await interaction.followup.send("❌ สินค้านี้หมดสต็อกแล้ว", ephemeral=True)
            return
        
        # เรียกใช้ฟังก์ชันสำหรับใช้ voucher
        result = redeem_truemoney_voucher(wallet_number, voucher_hash)
        
        if not result['success']:
            # บันทึกประวัติการเติมเงินที่ไม่สำเร็จ
            add_deposit_history(
                str(interaction.user.id), 
                self.price, 
                voucher_hash, 
                'FAILED', 
                self.product_id
            )
            
            await interaction.followup.send(f"❌ การเติมเงินล้มเหลว: {result['message']}", ephemeral=True)
            return
        
        api_data = result['data']
        code = api_data.get('status', {}).get('code', 'UNKNOWN')
        
        if code == 'SUCCESS':
            # คำนวณจำนวนเงิน
            voucher_data = api_data['data']['voucher']
            amount_str = voucher_data.get('redeemed_amount_baht', '0')
            amount = int(str(amount_str).replace(',', '').replace(' ', '').replace('.00', ''))
            
            if amount < self.price:
                # บันทึกประวัติการเติมเงินที่ไม่ครบ
                add_deposit_history(
                    str(interaction.user.id), 
                    amount, 
                    voucher_hash, 
                    'INSUFFICIENT', 
                    self.product_id
                )
                
                await interaction.followup.send(
                    f"❌ จำนวนเงินไม่ครบ\nเติมเงินมา: {amount} บาท\nต้องการ: {self.price} บาท\nขาดอยู่: {self.price - amount} บาท", 
                    ephemeral=True
                )
                return
            
            # นำสต็อกอันแรกมาใช้
            stock_lines = stock.strip().split('\n')
            first_stock = stock_lines[0]
            remaining_stock = '\n'.join(stock_lines[1:])
            
            # อัพเดทสต็อก
            update_product_stock(self.product_id, remaining_stock)
            
            # อัพเดทยอดเงินผู้ใช้ (เพิ่มเงินที่เติมเข้ามา)
            update_user_balance(str(interaction.user.id), amount)
            
            # 🔥 หักเงินตามราคาสินค้าที่เลือก 🔥
            deduct_user_balance(str(interaction.user.id), self.price)
            
            # บันทึกประวัติการเติมเงินที่สำเร็จ
            add_deposit_history(
                str(interaction.user.id), 
                amount, 
                voucher_hash, 
                'SUCCESS', 
                self.product_id
            )
            
            # บันทึกประวัติการสั่งซื้อ
            add_order_history(
                str(interaction.user.id),
                self.product_id,
                self.product_name,
                self.price,
                'VOUCHER'
            )
            
            user_balance = get_user_balance(str(interaction.user.id))
            
            embed = discord.Embed(
                title="✅ การเติมเงินสำเร็จ",
                description=(
                    f"**จำนวนเงินที่เติม:** {amount} บาท\n"
                    f"**ราคาสินค้า:** {self.price} บาท\n"
                    f"**หักเงิน:** {self.price} บาท\n"
                    f"**ได้รับสินค้า:**\n```{first_stock}```\n"
                    f"**ยอดเงินคงเหลือ:** {user_balance['balance']} บาท\n"
                    f"**ยอดเงินที่ใช้ไป:** {user_balance['total_spent']} บาท"
                ),
                color=0x00ff00
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            
            # อัพเดทการแสดงผลร้านค้า
            await update_shop_display()
        else:
            # บันทึกประวัติการเติมเงินที่ไม่สำเร็จ
            add_deposit_history(
                str(interaction.user.id), 
                self.price, 
                voucher_hash, 
                'FAILED', 
                self.product_id
            )
            
            await interaction.followup.send("❌ ไม่สามารถใช้งานอั่งเปาได้", ephemeral=True)

async def process_balance_payment(interaction, product_id, price, product_name):
    """ประมวลผลการชำระเงินด้วยยอดเงินในบัญชี"""
    await interaction.response.defer(ephemeral=True)
    
    # ตรวจสอบสต็อก
    stock = get_product_stock(product_id)
    if not stock or not stock.strip():
        await interaction.followup.send("❌ สินค้านี้หมดสต็อกแล้ว", ephemeral=True)
        return
    
    # หักยอดเงิน
    success = deduct_user_balance(str(interaction.user.id), price)
    
    if not success:
        await interaction.followup.send("❌ ไม่สามารถหักยอดเงินได้ กรุณาตรวจสอบยอดเงินอีกครั้ง", ephemeral=True)
        return
    
    # นำสต็อกอันแรกมาใช้
    stock_lines = stock.strip().split('\n')
    first_stock = stock_lines[0]
    remaining_stock = '\n'.join(stock_lines[1:])
    
    # อัพเดทสต็อก
    update_product_stock(product_id, remaining_stock)
    
    # บันทึกประวัติการสั่งซื้อ
    add_order_history(
        str(interaction.user.id),
        product_id,
        product_name,
        price,
        'BALANCE'
    )
    
    user_balance = get_user_balance(str(interaction.user.id))
    
    embed = discord.Embed(
        title="✅ การชำระเงินสำเร็จ",
        description=(
            f"**ใช้ยอดเงิน:** {price} บาท\n"
            f"**ได้รับสินค้า:**\n```{first_stock}```\n"
            f"**ยอดเงินคงเหลือ:** {user_balance['balance']} บาท\n"
            f"**ยอดเงินที่ใช้ไป:** {user_balance['total_spent']} บาท"
        ),
        color=0x00ff00
    )
    await interaction.followup.send(embed=embed, ephemeral=True)
    
    # อัพเดทการแสดงผลร้านค้า
    await update_shop_display()

# Select สำหรับลบสินค้า
class DeleteProductSelect(discord.ui.Select):
    def __init__(self, products):
        options = []
        for product in products:
            product_id, name, price, stock = product
            stock_count = len(stock.splitlines())
            options.append(
                discord.SelectOption(
                    label=f"{name} - {price} บาท",
                    value=str(product_id),
                    description=f"สต็อก: {stock_count} รายการ"
                )
            )
        
        super().__init__(
            placeholder="🗑️ เลือกสินค้าที่ต้องการลบ",
            min_values=1,
            max_values=1,
            options=options
        )
    
    async def callback(self, interaction: discord.Interaction):
        product_id = int(self.values[0])
        product = get_product_by_id(product_id)
        
        if not product:
            await interaction.response.send_message("❌ ไม่พบสินค้านี้", ephemeral=True)
            return
        
        # ลบสินค้า
        delete_product(product_id)
        
        await interaction.response.send_message(f"✅ ลบสินค้า #{product_id} เรียบร้อยแล้ว", ephemeral=True)
        await update_shop_display()
        await update_admin_display()

# Select สำหรับจัดการสินค้า (เพิ่มสต็อก)
class ManageProductSelect(discord.ui.Select):
    def __init__(self, products):
        options = []
        for product in products:
            product_id, name, price, stock = product
            stock_count = len(stock.splitlines())
            options.append(
                discord.SelectOption(
                    label=f"{name} - {price} บาท",
                    value=str(product_id),
                    description=f"สต็อก: {stock_count} รายการ"
                )
            )
        
        super().__init__(
            placeholder="📦 เลือกสินค้าที่ต้องการจัดการ",
            min_values=1,
            max_values=1,
            options=options
        )
    
    async def callback(self, interaction: discord.Interaction):
        product_id = int(self.values[0])
        product = get_product_by_id(product_id)
        
        if not product:
            await interaction.response.send_message("❌ ไม่พบสินค้านี้", ephemeral=True)
            return
        
        product_id, name, price, stock = product
        
        # ส่ง Modal สำหรับเพิ่มสต็อก
        modal = AddStockModal(product_id, name)
        await interaction.response.send_modal(modal)

# View สำหรับลบสินค้า
class DeleteProductView(discord.ui.View):
    def __init__(self, products):
        super().__init__(timeout=300)
        if products:
            self.add_item(DeleteProductSelect(products))
        else:
            self.add_item(discord.ui.Button(
                label="📦 ไม่มีสินค้าให้ลบ",
                style=discord.ButtonStyle.secondary,
                disabled=True
            ))

# View สำหรับจัดการสินค้า (เพิ่มสต็อก)
class ManageProductView(discord.ui.View):
    def __init__(self, products):
        super().__init__(timeout=300)
        if products:
            self.add_item(ManageProductSelect(products))
        else:
            self.add_item(discord.ui.Button(
                label="📦 ไม่มีสินค้าให้จัดการ",
                style=discord.ButtonStyle.secondary,
                disabled=True
            ))

# ฟังก์ชันสำหรับใช้งาน TrueMoney Voucher
def extract_voucher_hash(link):
    """ดึง voucher_hash จากลิงก์"""
    patterns = [
        r'[?&]v=([a-zA-Z0-9]+)',
        r'truemoney\.com/campaign/\?v=([a-zA-Z0-9]+)',
        r'voucher/([a-zA-Z0-9]+)'
    ]
    
    for pattern in patterns:
        match = re.search(pattern, link)
        if match:
            return match.group(1)
    
    return None

def redeem_truemoney_voucher(mobile, voucher_hash):
    """ฟังก์ชันสำหรับใช้ voucher ที่หลีกเลี่ยง 403"""
    endpoints = [
        f"https://gift.truemoney.com/campaign/vouchers/{voucher_hash}/redeem",
        f"https://tmn-gift-staging.aws.truemoney.com/campaign/vouchers/{voucher_hash}/redeem"
    ]
    
    user_agents = [
        'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1',
        'Mozilla/5.0 (Linux; Android 13; SM-G998B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0'
    ]
    
    for url in endpoints:
        ua = random.choice(user_agents)
        
        # สร้าง session ใหม่สำหรับแต่ละการเรียก
        session_id = 'PHPSESSID=' + ''.join(random.choices('0123456789abcdef', k=32))
        csrf_token = ''.join(random.choices('0123456789abcdef', k=64))
        
        headers = {
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'th-TH,th;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'Cache-Control': 'no-cache',
            'Connection': 'keep-alive',
            'Content-Type': 'application/json;charset=UTF-8',
            'Origin': 'https://gift.truemoney.com',
            'Pragma': 'no-cache',
            'Referer': f'https://gift.truemoney.com/campaign/?v={voucher_hash}',
            'sec-ch-ua': '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
            'sec-ch-ua-mobile': '?1',
            'sec-ch-ua-platform': '"Android"',
            'sec-fetch-dest': 'empty',
            'sec-fetch-mode': 'cors',
            'sec-fetch-site': 'same-origin',
            'User-Agent': ua,
            'X-Requested-With': 'XMLHttpRequest',
            'Cookie': session_id,
            'X-CSRF-TOKEN': csrf_token
        }
        
        post_data = json.dumps({
            'mobile': mobile,
            'voucher_hash': voucher_hash,
            '_token': csrf_token
        })
        
        try:
            response = requests.post(
                url,
                data=post_data,
                headers=headers,
                timeout=30,
                verify=False
            )
            
            if response.status_code != 403:
                result = response.json()
                if result and 'status' in result:
                    return {'success': True, 'data': result, 'http_code': response.status_code}
                    
        except Exception as e:
            print(f"Error with endpoint {url}: {e}")
        
        time.sleep(0.5)
    
    # Fallback to scraping
    return scrape_truemoney_voucher(mobile, voucher_hash)

def scrape_truemoney_voucher(mobile, voucher_hash):
    """วิธีการ scraping เป็น fallback"""
    voucher_url = f"https://gift.truemoney.com/campaign/?v={voucher_hash}"
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Linux; Android 13; SM-G998B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'th-TH,th;q=0.9,en;q=0.8',
        'Accept-Encoding': 'gzip, deflate, br',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
        'Sec-Fetch-Dest': 'document',
        'Sec-Fetch-Mode': 'navigate',
        'Sec-Fetch-Site': 'none'
    }
    
    try:
        response = requests.get(voucher_url, headers=headers, timeout=30, verify=False)
        
        if response.status_code == 200 and response.text:
            html = response.text
            
            if 'หมดอายุแล้ว' in html or 'expired' in html:
                return {'success': False, 'message': 'อั๋งเปานี้หมดอายุแล้ว'}
            
            if 'ถูกใช้แล้ว' in html or 'used' in html:
                return {'success': False, 'message': 'อั๋งเปานี้ถูกใช้งานไปแล้ว'}
            
            if 'แจกเงิน' in html or 'gift' in html:
                amount_match = re.search(r'(\d+(?:,\d{3})*(?:\.\d{2})?)\s*บาท', html)
                amount = amount_match.group(1).replace(',', '') if amount_match else '50'
                
                return {
                    'success': True,
                    'data': {
                        'status': {'code': 'SUCCESS'},
                        'data': {
                            'voucher': {
                                'redeemed_amount_baht': amount,
                                'voucher_hash': voucher_hash
                            }
                        }
                    }
                }
                
    except Exception as e:
        print(f"Scraping error: {e}")
    
    return {'success': False, 'message': 'ไม่สามารถประมวลผล voucher ได้'}

# View สำหรับหลังบ้าน
class AdminView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
    
    @discord.ui.button(
        label="📱 ตั้งค่าเบอร์รับเงิน",
        style=discord.ButtonStyle.primary,
        custom_id="set_wallet",
        emoji="💰"
    )
    async def set_wallet_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = WalletModal()
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(
        label="📦 เพิ่มสินค้า",
        style=discord.ButtonStyle.success,
        custom_id="add_product",
        emoji="🛒"
    )
    async def add_product_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = AddProductModal()
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(
        label="🗑️ ลบสินค้า",
        style=discord.ButtonStyle.danger,
        custom_id="delete_product",
        emoji="❌"
    )
    async def delete_product_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        products = get_products()
        
        if not products:
            await interaction.response.send_message("❌ ยังไม่มีสินค้าในระบบ", ephemeral=True)
            return
        
        view = DeleteProductView(products)
        await interaction.response.send_message("🗑️ เลือกสินค้าที่ต้องการลบจากเมนูด้านล่าง", view=view, ephemeral=True)
    
    @discord.ui.button(
        label="📦 จัดการสต็อก",
        style=discord.ButtonStyle.blurple,
        custom_id="manage_stock",
        emoji="📥"
    )
    async def manage_stock_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        products = get_products()
        
        if not products:
            await interaction.response.send_message("❌ ยังไม่มีสินค้าในระบบ", ephemeral=True)
            return
        
        view = ManageProductView(products)
        await interaction.response.send_message("📦 เลือกสินค้าที่ต้องการเพิ่มสต็อกจากเมนูด้านล่าง\n(1 บรรทัด = 1 สต็อก)", view=view, ephemeral=True)
    
    @discord.ui.button(
        label="📊 ดูสินค้าทั้งหมด",
        style=discord.ButtonStyle.secondary,
        custom_id="view_products",
        emoji="📋"
    )
    async def view_products_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        products = get_products()
        
        if not products:
            await interaction.response.send_message("❌ ยังไม่มีสินค้าในระบบ", ephemeral=True)
            return
        
        embed = discord.Embed(title="📦 รายการสินค้าทั้งหมด", color=0x00ff00)
        
        for product in products:
            product_id, name, price, stock = product
            stock_count = len(stock.splitlines())
            embed.add_field(
                name=f"#{product_id} - {name}",
                value=f"💰 ราคา: {price} บาท\n📦 สต็อก: {stock_count} รายการ",
                inline=False
            )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @discord.ui.button(
        label="🔄 อัพเดทร้านค้า",
        style=discord.ButtonStyle.blurple,
        custom_id="refresh_shop",
        emoji="🔄"
    )
    async def refresh_shop_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await update_shop_display()
        await interaction.response.send_message("✅ อัพเดทร้านค้าเรียบร้อยแล้ว!", ephemeral=True)

@bot.event
async def on_ready():
    print(f'✅ บอท {bot.user} พร้อมทำงานแล้ว!')
    
    # เริ่มต้นฐานข้อมูล
    init_db()
    
    # อัพเดทการแสดงผลทั้งสองห้อง
    await update_shop_display()
    await update_admin_display()

@bot.event
async def on_interaction(interaction: discord.Interaction):
    """จัดการการโต้ตอบทั้งหมด"""
    if interaction.type == discord.InteractionType.component:
        # ตรวจสอบปุ่มตรวจสอบยอดเงิน
        if interaction.data.get('custom_id') == 'check_balance':
            user_balance = get_user_balance(str(interaction.user.id))
            
            embed = discord.Embed(
                title="💳 ยอดเงินในบัญชี",
                description=(
                    f"**ยอดเงินคงเหลือ:** {user_balance['balance']} บาท\n"
                    f"**ยอดเงินที่เติมทั้งหมด:** {user_balance['total_deposit']} บาท\n"
                    f"**ยอดเงินที่ใช้ไป:** {user_balance['total_spent']} บาท\n"
                    f"**ผู้ใช้:** {interaction.user.mention}"
                ),
                color=0x3498db
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

@bot.command()
async def setup(ctx):
    """คำสั่งสำหรับตั้งค่าระบบ"""
    if ctx.author.guild_permissions.administrator:
        await update_shop_display()
        await update_admin_display()
        await ctx.message.delete()
    else:
        await ctx.message.delete()

@bot.command()
async def balance(ctx):
    """ตรวจสอบยอดเงิน"""
    user_balance = get_user_balance(str(ctx.author.id))
    
    embed = discord.Embed(
        title="💳 ยอดเงินในบัญชี",
        description=(
            f"**ยอดเงินคงเหลือ:** {user_balance['balance']} บาท\n"
            f"**ยอดเงินที่เติมทั้งหมด:** {user_balance['total_deposit']} บาท\n"
            f"**ยอดเงินที่ใช้ไป:** {user_balance['total_spent']} บาท\n"
            f"**ผู้ใช้:** {ctx.author.mention}"
        ),
        color=0x3498db
    )
    await ctx.send(embed=embed, delete_after=10)

if __name__ == "__main__":
    # เริ่มต้นระบบ
    print("กำลังเริ่มต้นระบบเติมเงินอัตโนมัติ...")

    server_on()


    bot.run(os.getenv('TOKEN'))
