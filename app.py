import streamlit as st
import pandas as pd
import sqlite3
import io
from datetime import datetime
import tempfile
import os

# ตั้งค่าหน้า
st.set_page_config(
    page_title="โปรแกรมเช็คเบอร์โทรซ้ำ",
    page_icon="📱",
    layout="wide"
)

# ฟังก์ชันจัดการฐานข้อมูล
def init_database():
    """สร้างฐานข้อมูล SQLite"""
    conn = sqlite3.connect('phone_database.db')
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS old_phones (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            phone_number TEXT,
            last_9_digits TEXT,
            source_file TEXT,
            created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    conn.commit()
    conn.close()

def extract_last_9_digits(phone):
    """ดึงตัวเลข 9 ตัวท้ายจากเบอร์โทร"""
    if pd.isna(phone) or phone == '' or phone is None:
        return ""
    
    phone_str = str(phone).strip()
    digits_only = ''.join(filter(str.isdigit, phone_str))
    
    if len(digits_only) >= 9:
        return digits_only[-9:]
    else:
        return digits_only

def get_all_last_9_digits():
    """ดึงตัวเลข 9 ตัวท้ายทั้งหมดจากฐานข้อมูล"""
    conn = sqlite3.connect('phone_database.db')
    cursor = conn.cursor()
    
    cursor.execute("SELECT last_9_digits FROM old_phones WHERE LENGTH(last_9_digits) = 9")
    results = cursor.fetchall()
    
    conn.close()
    return set([result[0] for result in results])

def get_database_stats():
    """ดึงสถิติจากฐานข้อมูล"""
    conn = sqlite3.connect('phone_database.db')
    cursor = conn.cursor()
    
    cursor.execute("SELECT COUNT(*) FROM old_phones")
    total_count = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM old_phones WHERE LENGTH(last_9_digits) = 9")
    valid_count = cursor.fetchone()[0]
    
    conn.close()
    return total_count, valid_count

def save_phones_to_database(phone_numbers, source_file=""):
    """บันทึกเบอร์โทรลงฐานข้อมูล"""
    conn = sqlite3.connect('phone_database.db')
    
    for phone in phone_numbers:
        last_9 = extract_last_9_digits(phone)
        if len(last_9) == 9:
            conn.execute(
                "INSERT OR IGNORE INTO old_phones (phone_number, last_9_digits, source_file) VALUES (?, ?, ?)",
                (str(phone), last_9, source_file)
            )
    
    conn.commit()
    conn.close()

def clear_database():
    """ล้างฐานข้อมูล"""
    conn = sqlite3.connect('phone_database.db')
    conn.execute("DELETE FROM old_phones")
    conn.commit()
    conn.close()

# เริ่มต้นฐานข้อมูล
init_database()

# UI
st.title("📱 โปรแกรมเช็คเบอร์โทรซ้ำ")
st.markdown("อัพโหลดไฟล์ Excel เพื่อตรวจสอบเบอร์โทรซ้ำโดยใช้**ตัวเลข 9 ตัวท้าย**")

# Sidebar สำหรับสถิติและการจัดการ
with st.sidebar:
    st.header("📊 สถิติ")
    total_count, valid_count = get_database_stats()
    st.metric("เบอร์โทรทั้งหมดในระบบ", total_count)
    st.metric("เบอร์ที่ตรวจสอบได้ (9 ตัว)", valid_count)
    
    st.header("⚙️ การจัดการ")
    if st.button("🗑️ ล้างฐานข้อมูล", type="secondary"):
        if st.session_state.get('confirm_clear', False):
            clear_database()
            st.success("ล้างฐานข้อมูลเรียบร้อย!")
            st.session_state.confirm_clear = False
            st.rerun()
        else:
            st.session_state.confirm_clear = True
            st.warning("คลิกอีกครั้งเพื่อยืนยันการล้างฐานข้อมูล")
    
    if st.session_state.get('confirm_clear', False):
        if st.button("✅ ยืนยันการล้าง"):
            clear_database()
            st.success("ล้างฐานข้อมูลเรียบร้อย!")
            st.session_state.confirm_clear = False
            st.rerun()
        if st.button("❌ ยกเลิก"):
            st.session_state.confirm_clear = False
            st.rerun()

# ส่วนหลัก
st.markdown("---")

# อัพโหลดไฟล์
uploaded_file = st.file_uploader(
    "**เลือกไฟล์ Excel**", 
    type=['xlsx', 'xls'],
    help="ไฟล์ Excel ต้องมีคอลัมน์ A หรือคอลัมน์แรกเป็นเบอร์โทร"
)

if uploaded_file is not None:
    # ตั้งค่า options
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
                    df = pd.read_excel(uploaded_file)
                    
                    # ตรวจสอบคอลัมน์
                    if 'A' not in df.columns and len(df.columns) > 0:
                        first_col = df.columns[0]
                        df = df.rename(columns={first_col: 'A'})
                        st.info(f"ใช้คอลัมน์ '{first_col}' เป็นคอลัมน์เบอร์โทร")
                    
                    df['A'] = df['A'].fillna('')
                    
                    # แสดงตัวอย่างข้อมูล
                    with st.expander("📋 ดูตัวอย่างข้อมูลที่อัพโหลด"):
                        st.dataframe(df.head(10), use_container_width=True)
                    
                    # ดึงตัวเลข 9 ตัวท้าย
                    df['last_9_digits'] = df['A'].apply(extract_last_9_digits)
                    
                    # ดึงข้อมูลเบอร์เก่าจากฐานข้อมูล
                    existing_last_9_digits = get_all_last_9_digits()
                    
                    # ตรวจสอบซ้ำ
                    df['is_duplicate'] = df['last_9_digits'].isin(existing_last_9_digits)
                    
                    # กรองข้อมูลที่ไม่ซ้ำ
                    unique_df = df[~df['is_duplicate']].copy()
                    
                    # ลบคอลัมน์ชั่วคราว
                    columns_to_drop = ['last_9_digits', 'is_duplicate']
                    for col in columns_to_drop:
                        if col in unique_df.columns:
                            unique_df = unique_df.drop(columns=[col])
                    
                    # บันทึกลงฐานข้อมูลถ้าต้องการ
                    if save_to_db:
                        save_phones_to_database(df['A'].tolist(), uploaded_file.name)
                    
                    # แสดงผลลัพธ์
                    st.success("✅ ตรวจสอบเสร็จสิ้น!")
                    
                    # สรุปผล
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric("เบอร์โทรทั้งหมด", len(df))
                    with col2:
                        st.metric("เบอร์ที่ไม่ซ้ำ", len(unique_df), delta=f"+{len(unique_df)}")
                    with col3:
                        st.metric("เบอร์ที่ซ้ำ", len(df) - len(unique_df), delta=f"-{len(df) - len(unique_df)}")
                    
                    # แสดงตัวอย่างผลลัพธ์
                    with st.expander("👀 ดูตัวอย่างผลลัพธ์"):
                        st.dataframe(unique_df.head(10), use_container_width=True)
                    
                    # ดาวน์โหลดไฟล์ผลลัพธ์
                    st.markdown("---")
                    st.subheader("📥 ดาวน์โหลดไฟล์ผลลัพธ์")
                    
                    # สร้างไฟล์ใน memory
                    output = io.BytesIO()
                    with pd.ExcelWriter(output, engine='openpyxl') as writer:
                        unique_df.to_excel(writer, index=False, sheet_name='เบอร์ไม่ซ้ำ')
                    output.seek(0)
                    
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    download_filename = f"filtered_{timestamp}_{uploaded_file.name}"
                    
                    st.download_button(
                        label="💾 ดาวน์โหลดไฟล์ Excel",
                        data=output.getvalue(),
                        file_name=download_filename,
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        type="primary",
                        use_container_width=True
                    )
                    
                except Exception as e:
                    st.error(f"❌ เกิดข้อผิดพลาด: {str(e)}")
                    st.info("⚠️ **ข้อแนะนำ:** กรุณาตรวจสอบว่าไฟล์ Excel มีรูปแบบที่ถูกต้องและไม่เสียหาย")

# ส่วนคำแนะนำ
with st.expander("💡 คู่มือการใช้งาน"):
    st.markdown("""
    ### 📝 วิธีการใช้โปรแกรม
    
    1. **เตรียมไฟล์ Excel**: ไฟล์ต้องมีคอลัมน์ **A** หรือคอลัมน์แรกเป็นเบอร์โทร
    2. **อัพโหลดไฟล์**: คลิกปุ่ม "Browse files" เพื่อเลือกไฟล์ Excel
    3. **ตั้งค่าการบันทึก**: เลือกว่าต้องการบันทึกเบอร์จากไฟล์นี้ลงฐานข้อมูลหรือไม่
    4. **เริ่มตรวจสอบ**: คลิกปุ่ม "เริ่มตรวจสอบเบอร์โทรซ้ำ"
    5. **ดาวน์โหลดผลลัพธ์**: ดาวน์โหลดไฟล์ที่มีเฉพาะเบอร์ที่ไม่ซ้ำ
    
    ### 🔍 หลักการทำงาน
    
    - ตรวจสอบซ้ำโดยใช้ **ตัวเลข 9 ตัวท้าย** ของเบอร์โทร
    - ตัวอย่าง: เบอร์ `081-234-5678` จะใช้ `123456789` ในการตรวจสอบ
    - เบอร์ที่ซ้ำจะถูกกรองออกจากผลลัพธ์
    
    ### 💾 การจัดการข้อมูล
    
    - **บันทึกข้อมูล**: เมื่อเลือก "บันทึกเบอร์จากไฟล์นี้ลงฐานข้อมูล"
    - **ล้างข้อมูล**: ใช้ปุ่ม "ล้างฐานข้อมูล" ใน sidebar
    - **ข้อมูลจะถูกเก็บในฐานข้อมูล SQLite** ในเซิร์ฟเวอร์
    """)

# Footer
st.markdown("---")
st.markdown(
    "<div style='text-align: center; color: #666;'>"
    "พัฒนาด้วย Streamlit | โปรแกรมเช็คเบอร์โทรซ้ำ"
    "</div>",
    unsafe_allow_html=True
)
