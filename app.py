import streamlit as st
import pandas as pd
import sqlite3
import io
from datetime import datetime
import openpyxl
from openpyxl.utils.dataframe import dataframe_to_rows
import os

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
    """สร้างฐานข้อมูล SQLite พร้อม index เพื่อความเร็ว"""
    conn = sqlite3.connect('phone_database.db', timeout=30)
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
    conn = sqlite3.connect('phone_database.db', timeout=30)
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
    conn = sqlite3.connect('phone_database.db', timeout=30)
    cursor = conn.cursor()
    
    cursor.execute("SELECT COUNT(*) FROM old_phones")
    total_count = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM old_phones WHERE LENGTH(last_9_digits) = 9")
    valid_count = cursor.fetchone()[0]
    
    conn.close()
    return total_count, valid_count

def get_phones_count():
    """นับจำนวนเบอร์โทรทั้งหมด"""
    conn = sqlite3.connect('phone_database.db', timeout=30)
    cursor = conn.cursor()
    
    cursor.execute("SELECT COUNT(*) FROM old_phones")
    count = cursor.fetchone()[0]
    
    conn.close()
    return count

def get_phones_batch(limit=1000, offset=0):
    """ดึงข้อมูลเบอร์โทรแบบแบ่งกลุ่ม"""
    conn = sqlite3.connect('phone_database.db', timeout=30)
    
    query = """
    SELECT 
        phone_number,
        last_9_digits,
        source_file,
        created_date
    FROM old_phones
    ORDER BY source_file, phone_number
    LIMIT ? OFFSET ?
    """
    
    df = pd.read_sql_query(query, conn, params=(limit, offset))
    conn.close()
    return df

def save_phones_to_database(phone_numbers, source_file=""):
    """บันทึกเบอร์โทรลงฐานข้อมูล"""
    conn = sqlite3.connect('phone_database.db', timeout=30)
    
    for phone in phone_numbers:
        last_9 = extract_last_9_digits(phone)
        if len(last_9) == 9:
            try:
                conn.execute(
                    "INSERT OR IGNORE INTO old_phones (phone_number, last_9_digits, source_file) VALUES (?, ?, ?)",
                    (str(phone), last_9, source_file)
                )
            except:
                continue
    
    conn.commit()
    conn.close()

def clear_database():
    """ล้างฐานข้อมูล"""
    conn = sqlite3.connect('phone_database.db', timeout=30)
    conn.execute("DELETE FROM old_phones")
    conn.commit()
    conn.close()

def export_all_phones():
    """ส่งออกข้อมูลทั้งหมด"""
    conn = sqlite3.connect('phone_database.db', timeout=30)
    
    query = """
    SELECT 
        phone_number,
        source_file
    FROM old_phones
    ORDER BY source_file, phone_number
    """
    
    df = pd.read_sql_query(query, conn)
    conn.close()
    return df

def export_phones_txt():
    """ส่งออกข้อมูลทั้งหมดเป็นไฟล์ txt - ในรูปแบบ เบอร์โทร-ชื่อไฟล์"""
    conn = sqlite3.connect('phone_database.db', timeout=30)
    cursor = conn.cursor()
    
    # ดึงข้อมูลเรียงตามไฟล์ต้นทางและเบอร์โทร
    cursor.execute("""
        SELECT phone_number, source_file 
        FROM old_phones 
        ORDER BY source_file, phone_number
    """)
    
    # สร้างเนื้อหา txt
    txt_content = "เบอร์โทรทั้งหมดในระบบ\n"
    txt_content += "=" * 50 + "\n"
    txt_content += f"วันที่ส่งออก: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
    txt_content += "รูปแบบ: เบอร์โทร-ชื่อไฟล์\n"
    txt_content += "=" * 50 + "\n\n"
    
    # นับจำนวน
    count = 0
    
    for row in cursor:
        phone, source = row
        # เขียนในรูปแบบ เบอร์โทร-ชื่อไฟล์
        txt_content += f"{phone}-{source}\n"
        count += 1
    
    txt_content += f"\n{'='*50}\n"
    txt_content += f"รวมทั้งหมด: {count} เบอร์\n"
    
    conn.close()
    return txt_content, count

def export_phones_simple_txt():
    """ส่งออกเฉพาะเบอร์โทรเป็นไฟล์ txt (แบบง่าย)"""
    conn = sqlite3.connect('phone_database.db', timeout=30)
    cursor = conn.cursor()
    
    # ดึงเฉพาะเบอร์โทร เรียงตามไฟล์ต้นทาง
    cursor.execute("SELECT phone_number FROM old_phones ORDER BY source_file, phone_number")
    
    # สร้างเนื้อหา txt แบบง่าย (เบอร์โทรอย่างเดียว)
    txt_content = f"# เบอร์โทรทั้งหมดในระบบ\n"
    txt_content += f"# วันที่ส่งออก: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
    txt_content += f"# รวมทั้งหมด: \n\n"
    
    count = 0
    for row in cursor:
        phone = row[0]
        if phone and str(phone).strip():  # ตรวจสอบว่าไม่ว่าง
            txt_content += f"{phone}\n"
            count += 1
    
    # อัพเดตจำนวน
    txt_content = txt_content.replace("# รวมทั้งหมด: ", f"# รวมทั้งหมด: {count} เบอร์")
    
    conn.close()
    return txt_content, count

def save_phones_as_excel(df):
    """บันทึก DataFrame เป็น Excel - แก้ไขปัญหาเลข 0 หาย"""
    output = io.BytesIO()
    
    # ตรวจสอบว่า DataFrame ว่างหรือไม่
    if df.empty or len(df) == 0:
        # สร้าง DataFrame ว่างที่มีหัวข้อคอลัมน์
        empty_df = pd.DataFrame(columns=df.columns)
        empty_df.loc[0] = ['ไม่มีข้อมูล'] + [''] * (len(df.columns) - 1)
        df = empty_df
    
    # ใช้ openpyxl โดยตรงเพื่อควบคุม format มากขึ้น
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "เบอร์โทร"
    
    # เขียนหัวข้อ
    for col_idx, col_name in enumerate(df.columns, 1):
        cell = ws.cell(row=1, column=col_idx, value=str(col_name))
        cell.font = openpyxl.styles.Font(bold=True)
        cell.fill = openpyxl.styles.PatternFill(start_color="DDDDDD", end_color="DDDDDD", fill_type="solid")
    
    # เขียนข้อมูล - แก้ไขปัญหาเลข 0 หาย
    for row_idx, (_, row_data) in enumerate(df.iterrows(), 2):
        for col_idx, value in enumerate(row_data, 1):
            cell = ws.cell(row=row_idx, column=col_idx)
            
            # คอลัมน์แรก (เบอร์โทร) บังคับให้เป็น text และรักษาเลข 0
            if col_idx == 1 and pd.notna(value) and value != '':
                # แปลงเป็น string และรักษาเลข 0 นำหน้า
                phone_str = str(value).strip()
                # ตรวจสอบว่าเป็นตัวเลขและมี 0 นำหน้าหรือไม่
                if phone_str and phone_str != 'ไม่มีข้อมูล':
                    # บังคับให้เป็น text format
                    cell.value = phone_str
                    cell.number_format = '@'  # Text format
                else:
                    cell.value = phone_str
            else:
                # คอลัมน์อื่นๆ
                if pd.notna(value):
                    cell.value = value
                else:
                    cell.value = ''
    
    # ตั้งค่า column width
    column_widths = [20, 15, 20, 15]
    for col_idx, width in enumerate(column_widths[:len(df.columns)], 1):
        col_letter = openpyxl.utils.get_column_letter(col_idx)
        ws.column_dimensions[col_letter].width = width
    
    wb.save(output)
    output.seek(0)
    return output

def read_excel_preserve_format(uploaded_file):
    """อ่านไฟล์ Excel โดยรักษา format เดิมและเลข 0 นำหน้า"""
    try:
        # อ่านไฟล์โดยใช้ openpyxl เพื่อรักษา format
        wb = openpyxl.load_workbook(uploaded_file, data_only=False)
        ws = wb.active
        
        # แปลงเป็น DataFrame
        data = []
        for row in ws.iter_rows(values_only=True):
            data.append(row)
        
        df = pd.DataFrame(data)
        
        # ตั้งชื่อคอลัมน์แรกเป็น 'A'
        if len(df.columns) > 0:
            df = df.rename(columns={0: 'A'})
            
            # แปลงคอลัมน์ A เป็น string และรักษา format
            df['A'] = df['A'].astype(str)
            df['A'] = df['A'].fillna('')
            
            # ฟังก์ชันช่วยรักษาเลข 0 นำหน้า
            def preserve_leading_zeros(cell_value):
                if pd.isna(cell_value) or cell_value == '':
                    return ''
                # ถ้าเป็นตัวเลขและมี 0 นำหน้าใน Excel
                try:
                    # ตรวจสอบว่าเป็นตัวเลขและมี 0 นำหน้า
                    cell_str = str(cell_value)
                    if cell_str.isdigit() and len(cell_str) > 1 and cell_str[0] == '0':
                        return cell_str
                    else:
                        return cell_str
                except:
                    return str(cell_value)
            
            # ปรับคอลัมน์ A เพื่อรักษาเลข 0
            df['A'] = df['A'].apply(preserve_leading_zeros)
        
        return df
        
    except Exception as e:
        # ถ้าใช้ openpyxl ไม่ได้ ให้ใช้ pandas แบบเดิม
        st.warning("⚠️  ใช้การอ่านไฟล์แบบรักษา format ไม่สำเร็จ ใช้วิธีปกติแทน")
        df = pd.read_excel(uploaded_file, dtype=str)
        
        # ตรวจสอบคอลัมน์
        if 'A' not in df.columns and len(df.columns) > 0:
            first_col = df.columns[0]
            df = df.rename(columns={first_col: 'A'})
        
        # บังคับให้คอลัมน์ A เป็น string
        df['A'] = df['A'].astype(str)
        df['A'] = df['A'].fillna('')
        
        return df

# เริ่มต้นฐานข้อมูล
init_database()

# เริ่มต้น session state
if 'show_export_password' not in st.session_state:
    st.session_state.show_export_password = False
if 'show_clear_password' not in st.session_state:
    st.session_state.show_clear_password = False
if 'export_page' not in st.session_state:
    st.session_state.export_page = 0

# UI
st.title("📱 โปรแกรมเช็คเบอร์โทรซ้ำ")
st.markdown("อัพโหลดไฟล์ Excel เพื่อตรวจสอบเบอร์โทรซ้ำโดยใช้**ตัวเลข 9 ตัวท้าย**")

# Sidebar สำหรับสถิติและการจัดการ
with st.sidebar:
    st.header("📊 สถิติ")
    total_count, valid_count = get_database_stats()
    st.metric("เบอร์โทรทั้งหมดในระบบ", f"{total_count:,}")
    st.metric("เบอร์ที่ตรวจสอบได้ (9 ตัว)", f"{valid_count:,}")
    
    st.header("📥 การโหลดข้อมูล")
    
    # ส่วนโหลดเบอร์ทั้งหมด
    if st.button("📤 โหลดเบอร์โทรทั้งหมดจากระบบ", type="primary"):
        st.session_state.show_export_password = True
        st.session_state.show_clear_password = False
        st.rerun()
    
    if st.session_state.show_export_password:
        st.subheader("กรุณากรอกรหัสผ่าน")
        export_password = st.text_input("รหัสผ่าน:", type="password", key="export_pass")
        
        if st.button("✅ ยืนยัน", key="confirm_export"):
            if export_password == PASSWORD:
                st.session_state.export_authenticated = True
                st.session_state.show_export_password = False
                st.rerun()
            else:
                st.error("❌ รหัสผ่านไม่ถูกต้อง")
        
        if st.button("❌ ยกเลิก", key="cancel_export"):
            st.session_state.show_export_password = False
            st.rerun()
    
    if st.session_state.get('export_authenticated', False):
        st.success("✅ รหัสผ่านถูกต้อง")
        
        total_phones = get_phones_count()
        
        if total_phones == 0:
            st.info("ℹ️ ยังไม่มีข้อมูลเบอร์โทรในระบบ")
            st.session_state.export_authenticated = False
            st.rerun()
        
        # แสดงตัวอย่างข้อมูลแบบแบ่งหน้า
        st.info(f"📋 แสดงตัวอย่างข้อมูล (ทั้งหมด {total_phones:,} เบอร์)")
        
        page_size = 100
        offset = st.session_state.export_page * page_size
        
        sample_df = get_phones_batch(limit=page_size, offset=offset)
        st.dataframe(sample_df, use_container_width=True, height=300)
        
        col1, col2, col3 = st.columns([1, 2, 1])
        with col1:
            if st.button("◀️ ก่อนหน้า", key="prev_page") and st.session_state.export_page > 0:
                st.session_state.export_page -= 1
                st.rerun()
        with col2:
            st.markdown(f"**หน้า {st.session_state.export_page + 1}**")
        with col3:
            if st.button("ถัดไป ▶️", key="next_page") and len(sample_df) == page_size:
                st.session_state.export_page += 1
                st.rerun()
        
        # ดาวน์โหลดไฟล์ทั้งหมด
        st.markdown("---")
        st.subheader("💾 ดาวน์โหลดข้อมูลทั้งหมด")
        
        # ตัวเลือกการดาวน์โหลด
        download_option = st.radio(
            "รูปแบบไฟล์:",
            ["📄 TXT - เบอร์โทรอย่างเดียว", "📋 TXT - เบอร์โทร-ชื่อไฟล์"],
            index=1
        )
        
        if st.button("🚀 สร้างไฟล์ดาวน์โหลด", key="generate_download"):
            with st.spinner('กำลังสร้างไฟล์...'):
                try:
                    if download_option == "📄 TXT - เบอร์โทรอย่างเดียว":
                        txt_content, count = export_phones_simple_txt()
                        file_type = "text/plain"
                        file_name = f"phones_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
                        st.success(f"✅ สร้างไฟล์ TXT สำเร็จ ({count} เบอร์)")
                        
                    else:  # TXT - เบอร์โทร-ชื่อไฟล์
                        txt_content, count = export_phones_txt()
                        file_type = "text/plain"
                        file_name = f"phones_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
                        st.success(f"✅ สร้างไฟล์ TXT สำเร็จ ({count} เบอร์)")
                    
                    # ปุ่มดาวน์โหลด
                    st.download_button(
                        label=f"📥 ดาวน์โหลดไฟล์ ({count} เบอร์)",
                        data=txt_content,
                        file_name=file_name,
                        mime=file_type,
                        type="primary",
                        use_container_width=True
                    )
                    
                except Exception as e:
                    st.error(f"❌ เกิดข้อผิดพลาด: {str(e)}")
        
        if st.button("🔒 ออกจากระบบ", key="logout_export"):
            st.session_state.export_authenticated = False
            st.session_state.export_page = 0
            st.rerun()
    
    st.header("⚙️ การจัดการ")
    
    # ส่วนล้างฐานข้อมูล
    if st.button("🗑️ ล้างฐานข้อมูล", type="secondary"):
        st.session_state.show_clear_password = True
        st.session_state.show_export_password = False
        st.rerun()
    
    if st.session_state.show_clear_password:
        st.subheader("กรุณากรอกรหัสผ่าน")
        clear_password = st.text_input("รหัสผ่าน:", type="password", key="clear_pass")
        
        if st.button("✅ ยืนยันการล้าง", key="confirm_clear"):
            if clear_password == PASSWORD:
                st.session_state.clear_authenticated = True
                st.session_state.show_clear_password = False
                st.rerun()
            else:
                st.error("❌ รหัสผ่านไม่ถูกต้อง")
        
        if st.button("❌ ยกเลิก", key="cancel_clear"):
            st.session_state.show_clear_password = False
            st.rerun()
    
    if st.session_state.get('clear_authenticated', False):
        st.success("✅ รหัสผ่านถูกต้อง")
        
        total_count = get_phones_count()
        
        if total_count == 0:
            st.info("ℹ️ ไม่มีข้อมูลในระบบที่จะล้าง")
            st.session_state.clear_authenticated = False
            st.rerun()
        
        st.warning(f"⚠️  คุณกำลังจะล้างข้อมูลทั้งหมด {total_count:,} เบอร์")
        st.error("🚨 **คำเตือน:** การล้างข้อมูลไม่สามารถกู้คืนได้!")
        
        if st.button("🔥 ยืนยันล้างข้อมูลทั้งหมด", type="primary", key="final_clear"):
            with st.spinner('กำลังล้างข้อมูล...'):
                try:
                    clear_database()
                    st.success(f"✅ ล้างฐานข้อมูลเรียบร้อย!")
                    st.session_state.clear_authenticated = False
                    st.rerun()
                except Exception as e:
                    st.error(f"❌ เกิดข้อผิดพลาด: {str(e)}")
        
        if st.button("🔒 ออกจากระบบ", key="logout_clear"):
            st.session_state.clear_authenticated = False
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
                    # ใช้ฟังก์ชันอ่านไฟล์แบบรักษา format
                    df = read_excel_preserve_format(uploaded_file)
                    
                    st.info(f"ใช้คอลัมน์ 'A' เป็นคอลัมน์เบอร์โทร (พบ {len(df)} แถว)")
                    
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
                        st.metric("เบอร์ที่ไม่ซ้ำ", len(unique_df))
                    with col3:
                        st.metric("เบอร์ที่ซ้ำ", len(df) - len(unique_df))
                    
                    # ดาวน์โหลดไฟล์ผลลัพธ์
                    st.markdown("---")
                    st.subheader("📥 ดาวน์โหลดไฟล์ผลลัพธ์")
                    
                    # สร้างชื่อไฟล์ตามต้นฉบับ-Cut
                    original_name = uploaded_file.name
                    if '.' in original_name:
                        name_without_ext = original_name.rsplit('.', 1)[0]
                        extension = original_name.rsplit('.', 1)[1]
                        download_filename = f"{name_without_ext}-Cut.{extension}"
                    else:
                        download_filename = f"{original_name}-Cut.xlsx"
                    
                    # บันทึกเป็น Excel
                    output = save_phones_as_excel(unique_df)
                    
                    st.download_button(
                        label="💾 ดาวน์โหลดไฟล์ผลลัพธ์",
                        data=output.getvalue(),
                        file_name=download_filename,
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        type="primary",
                        use_container_width=True
                    )
                    
                    st.success("✅ **ไฟล์ผลลัพธ์จะรักษาเลข 0 หน้าเบอร์โทรโดยอัตโนมัติ**")
                    
                    # แสดงตัวอย่างข้อมูล
                    with st.expander("📋 ดูตัวอย่างข้อมูลผลลัพธ์"):
                        st.dataframe(unique_df.head(10), use_container_width=True)
                    
                except Exception as e:
                    st.error(f"❌ เกิดข้อผิดพลาด: {str(e)}")

# ส่วนคำแนะนำ
with st.expander("💡 คู่มือการใช้งาน"):
    st.markdown("""
   """)

# Footer
st.markdown("---")
st.markdown(
    "<div style='text-align: center; color: #666;'>"
    "พัฒนาด้วย Streamlit | โปรแกรมเช็คเบอร์โทรซ้ำ - รูปแบบ เบอร์โทร-ชื่อไฟล์"
    "</div>",
    unsafe_allow_html=True
)
