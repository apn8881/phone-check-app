import streamlit as st
import pandas as pd
import sqlite3
import io
from datetime import datetime
import openpyxl
import os
import json
import base64
import requests

# ตั้งค่าหน้า
st.set_page_config(
    page_title="โปรแกรมเช็คเบอร์โทรซ้ำ",
    page_icon="📱",
    layout="wide"
)

# รหัสผ่าน
PASSWORD = "23669"

# ฟังก์ชันจัดการฐานข้อมูล
def init_database():
    """สร้างฐานข้อมูล SQLite"""
    conn = sqlite3.connect("phone_database.db", timeout=30)
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS old_phones (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            phone_number TEXT,
            last_9_digits TEXT UNIQUE,
            source_file TEXT,
            created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_last_9_digits ON old_phones(last_9_digits)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_created_date ON old_phones(created_date)')
    
    conn.commit()
    conn.close()

def extract_last_9_digits(phone):
    """ดึงตัวเลข 9 ตัวท้ายจากเบอร์โทร"""
    if pd.isna(phone) or phone == '' or phone is None:
        return ""
    
    phone_str = str(phone).strip()
    digits_only = ''.join([c for c in phone_str if c.isdigit()])
    
    return digits_only[-9:] if len(digits_only) >= 9 else digits_only

def get_all_last_9_digits():
    """ดึงตัวเลข 9 ตัวท้ายทั้งหมดจากฐานข้อมูล"""
    conn = sqlite3.connect("phone_database.db", timeout=30)
    cursor = conn.cursor()
    
    cursor.execute("SELECT last_9_digits FROM old_phones WHERE LENGTH(last_9_digits) = 9")
    
    results = set()
    batch_size = 100000
    while True:
        batch = cursor.fetchmany(batch_size)
        if not batch:
            break
        results.update(result[0] for result in batch)
    
    conn.close()
    return results

def get_database_stats():
    """ดึงสถิติจากฐานข้อมูล"""
    conn = sqlite3.connect("phone_database.db", timeout=30)
    cursor = conn.cursor()
    
    cursor.execute("SELECT COUNT(*) FROM old_phones")
    total_count = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM old_phones WHERE LENGTH(last_9_digits) = 9")
    valid_count = cursor.fetchone()[0]
    
    conn.close()
    return total_count, valid_count

def save_phones_to_database(phone_numbers, source_file=""):
    """บันทึกเบอร์โทรลงฐานข้อมูล"""
    conn = sqlite3.connect("phone_database.db", timeout=30)
    
    new_records_count = 0
    for phone in phone_numbers:
        last_9 = extract_last_9_digits(phone)
        if len(last_9) == 9:
            try:
                cursor = conn.execute(
                    "INSERT OR IGNORE INTO old_phones (phone_number, last_9_digits, source_file) VALUES (?, ?, ?)",
                    (str(phone), last_9, source_file)
                )
                if cursor.rowcount > 0:
                    new_records_count += 1
            except:
                continue
    
    conn.commit()
    conn.close()
    return new_records_count

def save_phones_as_excel(df):
    """บันทึก DataFrame เป็น Excel"""
    output = io.BytesIO()
    
    if df.empty or len(df) == 0:
        empty_df = pd.DataFrame(columns=df.columns)
        empty_df.loc[0] = ['ไม่มีข้อมูล'] + [''] * (len(df.columns) - 1)
        df = empty_df
    
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "เบอร์โทร"
    
    # เขียนหัวข้อ
    for col_idx, col_name in enumerate(df.columns, 1):
        cell = ws.cell(row=1, column=col_idx, value=str(col_name))
        cell.font = openpyxl.styles.Font(bold=True)
        cell.fill = openpyxl.styles.PatternFill(start_color="DDDDDD", end_color="DDDDDD", fill_type="solid")
    
    # เขียนข้อมูล
    for row_idx, (_, row_data) in enumerate(df.iterrows(), 2):
        for col_idx, value in enumerate(row_data, 1):
            cell = ws.cell(row=row_idx, column=col_idx)
            
            if col_idx == 1 and pd.notna(value) and value != '':
                phone_str = str(value).strip()
                if phone_str and phone_str != 'ไม่มีข้อมูล':
                    cell.value = phone_str
                    cell.number_format = '@'
                else:
                    cell.value = phone_str
            else:
                if pd.notna(value):
                    cell.value = value
                else:
                    cell.value = ''
    
    column_widths = [20, 15, 20, 15]
    for col_idx, width in enumerate(column_widths[:len(df.columns)], 1):
        col_letter = openpyxl.utils.get_column_letter(col_idx)
        ws.column_dimensions[col_letter].width = width
    
    wb.save(output)
    output.seek(0)
    return output

def export_database():
    """ส่งออกฐานข้อมูลเป็นไฟล์"""
    if os.path.exists("phone_database.db"):
        with open("phone_database.db", "rb") as f:
            return f.read()
    return None

def import_database(uploaded_file):
    """นำเข้าฐานข้อมูลจากไฟล์"""
    try:
        with open("phone_database.db", "wb") as f:
            f.write(uploaded_file.getvalue())
        return True, "✅ นำเข้าข้อมูลสำเร็จ"
    except Exception as e:
        return False, f"❌ นำเข้าข้อมูลล้มเหลว: {str(e)}"

# เริ่มต้นฐานข้อมูล
if not os.path.exists("phone_database.db"):
    init_database()

# UI
st.title("📱 โปรแกรมเช็คเบอร์โทรซ้ำ")
st.markdown("อัพโหลดไฟล์ Excel เพื่อตรวจสอบเบอร์โทรซ้ำโดยใช้**ตัวเลข 9 ตัวท้าย**")

# Sidebar - การจัดการข้อมูล
with st.sidebar:
    st.header("💾 การจัดการข้อมูล")
    
    # ส่งออกข้อมูล
    if st.button("📤 ส่งออกฐานข้อมูล"):
        db_data = export_database()
        if db_data:
            st.download_button(
                label="📥 ดาวน์โหลดไฟล์ฐานข้อมูล",
                data=db_data,
                file_name=f"phone_database_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db",
                mime="application/octet-stream"
            )
        else:
            st.error("❌ ไม่มีข้อมูลที่จะส่งออก")
    
    # นำเข้าข้อมูล
    st.markdown("---")
    st.subheader("นำเข้าข้อมูล")
    uploaded_db = st.file_uploader("เลือกไฟล์ฐานข้อมูล (.db)", type=['db'], key="db_uploader")
    if uploaded_db and st.button("📥 นำเข้าฐานข้อมูล"):
        success, message = import_database(uploaded_db)
        if success:
            st.success(message)
            st.rerun()
        else:
            st.error(message)
    
    # สถิติ
    st.markdown("---")
    st.subheader("📊 สถิติ")
    total_count, valid_count = get_database_stats()
    st.metric("เบอร์โทรทั้งหมด", f"{total_count:,}")
    st.metric("เบอร์ที่ตรวจสอบได้", f"{valid_count:,}")
    
    if os.path.exists("phone_database.db"):
        file_size = os.path.getsize("phone_database.db")
        file_time = datetime.fromtimestamp(os.path.getmtime("phone_database.db"))
        st.caption(f"ขนาดไฟล์: {file_size:,} bytes")
        st.caption(f"อัพเดท: {file_time.strftime('%Y-%m-%d %H:%M')}")

# ส่วนหลัก
st.markdown("---")

# อัพโหลดไฟล์ Excel
uploaded_file = st.file_uploader(
    "**เลือกไฟล์ Excel**", 
    type=['xlsx', 'xls'],
    help="ไฟล์ Excel ต้องมีคอลัมน์แรกเป็นเบอร์โทร"
)

if uploaded_file is not None:
    col1, col2 = st.columns(2)
    
    with col1:
        save_to_db = st.checkbox(
            "💾 บันทึกเบอร์จากไฟล์นี้ลงฐานข้อมูล", 
            value=True,
            help="บันทึกเบอร์โทรจากไฟล์นี้เพื่อใช้ตรวจสอบซ้ำในครั้งต่อไป"
        )
    
    with col2:
        if st.button("🚀 เริ่มตรวจสอบเบอร์โทรซ้ำ", type="primary", use_container_width=True):
            with st.spinner('กำลังตรวจสอบเบอร์โทรซ้ำ...'):
                try:
                    # อ่านไฟล์ Excel
                    df = pd.read_excel(uploaded_file, dtype=str)
                    df = df.rename(columns={df.columns[0]: 'A'})
                    df['A'] = df['A'].astype(str).fillna('')
                    
                    st.info(f"ใช้คอลัมน์แรกเป็นคอลัมน์เบอร์โทร (พบ {len(df)} แถว)")
                    
                    # ดึงตัวเลข 9 ตัวท้าย
                    df['last_9_digits'] = df['A'].apply(extract_last_9_digits)
                    
                    # ดึงข้อมูลเบอร์เก่าจากฐานข้อมูล
                    existing_last_9_digits = get_all_last_9_digits()
                    
                    # ตรวจสอบซ้ำ
                    df['is_duplicate'] = df['last_9_digits'].isin(existing_last_9_digits)
                    
                    # กรองข้อมูลที่ไม่ซ้ำ
                    unique_df = df[~df['is_duplicate']].copy()
                    unique_df = unique_df.drop(columns=['last_9_digits', 'is_duplicate'])
                    
                    # บันทึกลงฐานข้อมูล
                    if save_to_db:
                        new_records = save_phones_to_database(df['A'].tolist(), uploaded_file.name)
                        st.success(f"💾 บันทึกเบอร์โทรลงฐานข้อมูลเรียบร้อย (เพิ่ม {new_records} เบอร์ใหม่)")
                    
                    # แสดงผลลัพธ์
                    st.success("✅ ตรวจสอบเสร็จสิ้น!")
                    
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric("เบอร์โทรทั้งหมด", len(df))
                    with col2:
                        st.metric("เบอร์ที่ไม่ซ้ำ", len(unique_df))
                    with col3:
                        st.metric("เบอร์ที่ซ้ำ", len(df) - len(unique_df))
                    
                    # ดาวน์โหลดไฟล์ผลลัพธ์
                    output = save_phones_as_excel(unique_df)
                    
                    original_name = uploaded_file.name
                    name_without_ext = original_name.rsplit('.', 1)[0]
                    download_filename = f"{name_without_ext}-Cut.xlsx"
                    
                    st.download_button(
                        label="💾 ดาวน์โหลดไฟล์ผลลัพธ์",
                        data=output.getvalue(),
                        file_name=download_filename,
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        type="primary",
                        use_container_width=True
                    )
                    
                    # แสดงตัวอย่าง
                    with st.expander("📋 ดูตัวอย่างข้อมูลผลลัพธ์"):
                        st.dataframe(unique_df.head(10), use_container_width=True)
                        
                except Exception as e:
                    st.error(f"❌ เกิดข้อผิดพลาด: {str(e)}")

# คำแนะนำ
with st.expander("💡 คู่มือการใช้งาน"):
    st.markdown("""
    ### 🔒 วิธีป้องกันข้อมูลหายเมื่อรีสตาร์ตแอป:
    
    1. **สำรองข้อมูลเป็นระยะ**:
       - ใช้ปุ่ม "📤 ส่งออกฐานข้อมูล" ใน sidebar
       - ดาวน์โหลดไฟล์ .db เก็บไว้ในเครื่องหรือ Google Drive
       
    2. **กู้คืนข้อมูลเมื่อรีสตาร์ต**:
       - อัพโหลดไฟล์ .db ที่สำรองไว้
       - กด "📥 นำเข้าฐานข้อมูล"
       
    3. **เก็บไฟล์ .db ไว้ใน Google Drive**:
       - อัพโหลดไฟล์ .db ไปยัง Google Drive ด้วยตนเอง
       - ดาวน์โหลดกลับมาเมื่อต้องการใช้
       
    4. **ข้อมูลจะปลอดภัย** เพราะคุณเป็นคนจัดการไฟล์ backup เอง
    """)

st.markdown("---")
st.markdown("พัฒนาด้วย Streamlit | ระบบสำรองข้อมูลแบบ manual")
