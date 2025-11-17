import streamlit as st
import pandas as pd
import sqlite3
import io
from datetime import datetime
import openpyxl
from openpyxl.utils.dataframe import dataframe_to_rows

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

def save_phones_as_excel(df):
    """บันทึก DataFrame เป็น Excel โดยบังคับให้คอลัมน์ A เป็น text"""
    output = io.BytesIO()
    wb = openpyxl.Workbook()
    ws = wb.active
    
    # เขียนหัวข้อ
    for col_idx, col_name in enumerate(df.columns, 1):
        cell = ws.cell(row=1, column=col_idx, value=col_name)
        if col_idx == 1:  # คอลัมน์ A
            cell.number_format = '@'
    
    # เขียนข้อมูล
    for row_idx, row_data in enumerate(df.values, 2):
        for col_idx, value in enumerate(row_data, 1):
            cell = ws.cell(row=row_idx, column=col_idx)
            
            # คอลัมน์แรก (เบอร์โทร) บังคับให้เป็น text
            if col_idx == 1:
                cell.number_format = '@'  # Text format
                if pd.notna(value) and value != '':
                    # ใช้วิธีบังคับ text โดยเพิ่ม apostrophe
                    phone_str = str(value).strip()
                    # บังคับเป็น text โดยตรง
                    cell.value = phone_str
                    # ตั้งค่าเป็น text แบบ explicit
                    cell.data_type = 's'  # string
                else:
                    cell.value = ''
            else:
                # คอลัมน์อื่นๆ
                if pd.notna(value):
                    cell.value = value
                else:
                    cell.value = ''
    
    # ตั้งค่า column width และ protection
    ws.column_dimensions['A'].width = 20  # ความกว้างคอลัมน์ A
    
    wb.save(output)
    output.seek(0)
    return output

def save_phones_as_excel_alternative(df):
    """วิธีสำรอง: ใช้ CSV ก่อนแล้วแปลงเป็น Excel"""
    import tempfile
    import os
    
    # สร้างไฟล์ CSV ชั่วคราว
    with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False, encoding='utf-8-sig') as f:
        # บันทึกเป็น CSV ด้วย encoding ที่รักษาเลข 0
        df.to_csv(f, index=False)
        temp_csv_path = f.name
    
    # อ่าน CSV กลับมาเป็น Excel
    output = io.BytesIO()
    wb = openpyxl.Workbook()
    ws = wb.active
    
    # อ่านข้อมูลจาก CSV
    with open(temp_csv_path, 'r', encoding='utf-8-sig') as f:
        lines = f.readlines()
    
    # เขียนข้อมูลลง Excel
    for row_idx, line in enumerate(lines, 1):
        values = line.strip().split(',')
        for col_idx, value in enumerate(values, 1):
            cell = ws.cell(row=row_idx, column=col_idx, value=value)
            if col_idx == 1 and row_idx > 1:  # คอลัมน์ A (ยกเว้นหัวข้อ)
                cell.number_format = '@'
    
    # ลบไฟล์ชั่วคราว
    os.unlink(temp_csv_path)
    
    wb.save(output)
    output.seek(0)
    return output

def save_as_csv(df):
    """บันทึกเป็น CSV แบบรักษาเลข 0"""
    output = io.BytesIO()
    
    # ใช้ encoding utf-8-sig สำหรับ Excel
    csv_content = df.to_csv(index=False, encoding='utf-8-sig')
    output.write(csv_content.encode('utf-8-sig'))
    output.seek(0)
    
    return output

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
                    # อ่านไฟล์ Excel โดยรักษา format เดิม
                    df = pd.read_excel(uploaded_file, dtype={'A': str})
                    
                    # ตรวจสอบคอลัมน์
                    if 'A' not in df.columns and len(df.columns) > 0:
                        first_col = df.columns[0]
                        df = df.rename(columns={first_col: 'A'})
                        st.info(f"ใช้คอลัมน์ '{first_col}' เป็นคอลัมน์เบอร์โทร")
                    
                    # บังคับให้คอลัมน์ A เป็น string
                    df['A'] = df['A'].astype(str)
                    df['A'] = df['A'].fillna('')
                    
                    # แสดงตัวอย่างข้อมูลต้นฉบับ
                    with st.expander("📋 ดูตัวอย่างข้อมูลที่อัพโหลด"):
                        st.write("**ตัวอย่างเบอร์โทรต้นฉบับ (5 แถวแรก):**")
                        st.dataframe(df[['A']].head(), use_container_width=True)
                        
                        # แสดงรายละเอียดเพิ่มเติม
                        st.write("**รายละเอียดเบอร์โทร:**")
                        sample_phones = df['A'].head(5).tolist()
                        for i, phone in enumerate(sample_phones, 1):
                            st.write(f"{i}. `{phone}` (ความยาว: {len(str(phone))} ตัว)")
                    
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
                        st.success("💾 บันทึกเบอร์โทรลงฐานข้อมูลเรียบร้อย")
                    
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
                    with st.expander("👀 ดูตัวอย่างผลลัพธ์ (เบอร์ที่ไม่ซ้ำ)"):
                        st.dataframe(unique_df.head(10), use_container_width=True)
                        
                        # ตรวจสอบการรักษาเลข 0
                        st.write("**การตรวจสอบเลข 0 หน้าเบอร์โทร:**")
                        if len(unique_df) > 0:
                            sample_result_phones = unique_df['A'].head(3).tolist()
                            for i, phone in enumerate(sample_result_phones, 1):
                                phone_str = str(phone)
                                starts_with_zero = phone_str.startswith('0') if phone_str else False
                                st.write(f"{i}. `{phone}` - ขึ้นต้นด้วย 0: {starts_with_zero}")
                    
                    # ดาวน์โหลดไฟล์ผลลัพธ์
                    st.markdown("---")
                    st.subheader("📥 ดาวน์โหลดไฟล์ผลลัพธ์")
                    
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    
                    # ตัวเลือกการดาวน์โหลด
                    download_option = st.radio(
                        "เลือกรูปแบบไฟล์:",
                        ["Excel (พยายามรักษาเลข 0)", "CSV (รักษาเลข 0 แน่นอน)"],
                        index=1
                    )
                    
                    if download_option == "Excel (พยายามรักษาเลข 0)":
                        # ใช้วิธีแรก
                        try:
                            output = save_phones_as_excel(unique_df)
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
                            st.error(f"ไม่สามารถสร้างไฟล์ Excel: {str(e)}")
                            st.info("กรุณาใช้ตัวเลือก CSV แทน")
                    
                    else:  # CSV
                        output = save_as_csv(unique_df)
                        download_filename = f"filtered_{timestamp}_{uploaded_file.name.replace('.xlsx', '.csv').replace('.xls', '.csv')}"
                        
                        st.download_button(
                            label="💾 ดาวน์โหลดไฟล์ CSV (แนะนำ - รักษาเลข 0 แน่นอน)",
                            data=output.getvalue(),
                            file_name=download_filename,
                            mime="text/csv",
                            type="primary",
                            use_container_width=True
                        )
                    
                    st.info("💡 **คำแนะนำ:** ใช้ไฟล์ CSV เพื่อความมั่นใจว่าเลข 0 หน้าจะไม่หาย")
                    
                except Exception as e:
                    st.error(f"❌ เกิดข้อผิดพลาด: {str(e)}")
                    import traceback
                    st.code(traceback.format_exc())

# ส่วนคำแนะนำ
with st.expander("💡 คู่มือการใช้งาน"):
    st.markdown("""
    ### 🔧 วิธีรักษาเลข 0 หน้าเบอร์โทร
    
    **ปัญหา:** Excel มักจะตัดเลข 0 ออกเพราะคิดว่าเป็นตัวเลข
    
    **วิธีแก้ไข:**
    1. **ใช้ไฟล์ CSV** (แนะนำ) - รักษาเลข 0 ได้แน่นอน
    2. **เปิดไฟล์ Excel แล้วตั้ง format เป็น Text:**
       - เลือกคอลัมน์ A ทั้งหมด
       - คลิกขวา → Format Cells → Text
       - หรือเพิ่ม apostrophe (') หน้าเบอร์โทร
    
    ### 📝 วิธีการใช้โปรแกรม
    
    1. **เตรียมไฟล์ Excel**: ไฟล์ต้องมีคอลัมน์ **A** หรือคอลัมน์แรกเป็นเบอร์โทร
    2. **อัพโหลดไฟล์**: คลิกปุ่ม "Browse files" เพื่อเลือกไฟล์ Excel
    3. **เริ่มตรวจสอบ**: คลิกปุ่ม "เริ่มตรวจสอบเบอร์โทรซ้ำ"
    4. **ดาวน์โหลดผลลัพธ์**: เลือกดาวน์โหลดเป็น **CSV** เพื่อรักษาเลข 0
    """)

# Footer
st.markdown("---")
st.markdown(
    "<div style='text-align: center; color: #666;'>"
    "พัฒนาด้วย Streamlit | โปรแกรมเช็คเบอร์โทรซ้ำ"
    "</div>",
    unsafe_allow_html=True
)
