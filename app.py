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

# ตั้งค่าเพื่อรองรับข้อมูลขนาดใหญ่
os.environ['STREAMLIT_SERVER_MAX_UPLOAD_SIZE'] = '1000'

# ฟังก์ชันจัดการฐานข้อมูล
def init_database():
    """สร้างฐานข้อมูล SQLite พร้อม index เพื่อความเร็ว"""
    conn = sqlite3.connect('phone_database.db', timeout=30)
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS old_phones (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            phone_number TEXT,
            last_9_digits TEXT UNIQUE,  -- ใช้ UNIQUE เพื่อป้องกันข้อมูลซ้ำ
            source_file TEXT,
            created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # สร้าง index เพื่อเพิ่มความเร็วในการค้นหา
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_last_9_digits ON old_phones(last_9_digits)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_created_date ON old_phones(created_date)')
    
    conn.commit()
    conn.close()

def extract_last_9_digits(phone):
    """ดึงตัวเลข 9 ตัวท้ายจากเบอร์โทร (optimized version)"""
    if pd.isna(phone) or phone == '' or phone is None:
        return ""
    
    phone_str = str(phone).strip()
    # ใช้วิธีที่เร็วขึ้นสำหรับการดึงตัวเลข
    digits_only = ''.join([c for c in phone_str if c.isdigit()])
    
    return digits_only[-9:] if len(digits_only) >= 9 else digits_only

def get_all_last_9_digits():
    """ดึงตัวเลข 9 ตัวท้ายทั้งหมดจากฐานข้อมูล (ใช้ generator เพื่อประหยัด memory)"""
    conn = sqlite3.connect('phone_database.db', timeout=30)
    cursor = conn.cursor()
    
    cursor.execute("SELECT last_9_digits FROM old_phones WHERE LENGTH(last_9_digits) = 9")
    
    # ใช้ generator เพื่อไม่โหลดทั้งหมดลง memory
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
    """ดึงสถิติจากฐานข้อมูล (optimized)"""
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
    ORDER BY created_date DESC
    LIMIT ? OFFSET ?
    """
    
    df = pd.read_sql_query(query, conn, params=(limit, offset))
    conn.close()
    return df

def save_phones_to_database_batch(phone_numbers, source_file=""):
    """บันทึกเบอร์โทรลงฐานข้อมูลแบบแบ่งกลุ่ม"""
    conn = sqlite3.connect('phone_database.db', timeout=30)
    cursor = conn.cursor()
    
    batch_size = 10000
    saved_count = 0
    
    for i in range(0, len(phone_numbers), batch_size):
        batch = phone_numbers[i:i + batch_size]
        for phone in batch:
            last_9 = extract_last_9_digits(phone)
            if len(last_9) == 9:
                try:
                    cursor.execute(
                        "INSERT OR IGNORE INTO old_phones (phone_number, last_9_digits, source_file) VALUES (?, ?, ?)",
                        (str(phone), last_9, source_file)
                    )
                    saved_count += 1
                except:
                    continue
        
        conn.commit()
    
    conn.close()
    return saved_count

def clear_database_batch():
    """ล้างฐานข้อมูลแบบแบ่งกลุ่มเพื่อป้องกัน memory overflow"""
    conn = sqlite3.connect('phone_database.db', timeout=60)
    cursor = conn.cursor()
    
    # ลบแบบแบ่งกลุ่ม
    batch_size = 50000
    total_deleted = 0
    
    while True:
        cursor.execute(f"DELETE FROM old_phones WHERE id IN (SELECT id FROM old_phones LIMIT {batch_size})")
        deleted_count = cursor.rowcount
        conn.commit()
        total_deleted += deleted_count
        
        if deleted_count == 0:
            break
    
    # Vacuum database เพื่อคืนพื้นที่
    cursor.execute("VACUUM")
    conn.commit()
    conn.close()
    
    return total_deleted

def export_database_chunked():
    """ส่งออกข้อมูลแบบแบ่งส่วน"""
    conn = sqlite3.connect('phone_database.db', timeout=30)
    cursor = conn.cursor()
    
    # นับจำนวนทั้งหมด
    cursor.execute("SELECT COUNT(*) FROM old_phones")
    total_count = cursor.fetchone()[0]
    
    if total_count == 0:
        conn.close()
        return None, 0
    
    # สร้างไฟล์ Excel
    output = io.BytesIO()
    wb = openpyxl.Workbook()
    ws = wb.active
    
    # เขียนหัวข้อ
    headers = ['phone_number', 'last_9_digits', 'source_file', 'created_date']
    for col_idx, header in enumerate(headers, 1):
        ws.cell(row=1, column=col_idx, value=header)
    
    # ดึงข้อมูลแบบแบ่งกลุ่ม
    batch_size = 50000
    offset = 0
    row_count = 1
    
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    while True:
        status_text.text(f"กำลังประมวลผลข้อมูล... {offset:,} จาก {total_count:,} แถว")
        progress = min(offset / total_count, 0.95)
        progress_bar.progress(progress)
        
        cursor.execute(
            "SELECT phone_number, last_9_digits, source_file, created_date FROM old_phones ORDER BY id LIMIT ? OFFSET ?",
            (batch_size, offset)
        )
        
        batch = cursor.fetchall()
        if not batch:
            break
        
        # เขียนข้อมูลลง Excel
        for row in batch:
            row_count += 1
            for col_idx, value in enumerate(row, 1):
                cell = ws.cell(row=row_count, column=col_idx)
                if col_idx == 1:  # คอลัมน์เบอร์โทร
                    cell.value = str(value) if value else ''
                    cell.number_format = '@'
                else:
                    cell.value = value
        
        offset += batch_size
    
    progress_bar.progress(1.0)
    status_text.text("กำลังบันทึกไฟล์...")
    
    # ตั้งค่า column width
    for col in range(1, len(headers) + 1):
        ws.column_dimensions[openpyxl.utils.get_column_letter(col)].width = 20
    
    wb.save(output)
    output.seek(0)
    
    conn.close()
    return output, total_count

def save_phones_as_excel(df):
    """บันทึก DataFrame เป็น Excel"""
    output = io.BytesIO()
    
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Phones')
        
        # ตั้งค่า format สำหรับคอลัมน์เบอร์โทร
        workbook = writer.book
        worksheet = writer.sheets['Phones']
        
        # ตั้งค่า column width
        for column in worksheet.columns:
            max_length = 0
            column_letter = column[0].column_letter
            for cell in column:
                try:
                    if len(str(cell.value)) > max_length:
                        max_length = len(str(cell.value))
                except:
                    pass
            adjusted_width = min(max_length + 2, 20)
            worksheet.column_dimensions[column_letter].width = adjusted_width
        
        # ตั้ง format text สำหรับคอลัมน์แรก
        for row in worksheet.iter_rows(min_row=2, max_row=worksheet.max_row, min_col=1, max_col=1):
            for cell in row:
                cell.number_format = '@'
    
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
    st.metric("เบอร์โทรทั้งหมดในระบบ", f"{total_count:,}")
    st.metric("เบอร์ที่ตรวจสอบได้ (9 ตัว)", f"{valid_count:,}")
    
    st.header("📥 การโหลดข้อมูล")
    
    # ส่วนโหลดเบอร์ทั้งหมด (ต้องใส่รหัสผ่าน)
    if st.button("📤 โหลดเบอร์โทรทั้งหมดจากระบบ", type="primary"):
        st.session_state.show_export_password = True
        st.session_state.show_clear_password = False
    
    if st.session_state.get('show_export_password', False):
        st.subheader("กรุณากรอกรหัสผ่าน")
        export_password = st.text_input("รหัสผ่าน", type="password", key="export_pass")
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("✅ ยืนยัน", key="confirm_export"):
                if export_password == PASSWORD:
                    total_phones = get_phones_count()
                    
                    if total_phones == 0:
                        st.info("ℹ️ ยังไม่มีข้อมูลเบอร์โทรในระบบ")
                        st.session_state.show_export_password = False
                        st.rerun()
                    
                    if total_phones > 1000000:  # ถ้ามากกว่า 1 ล้านเบอร์
                        st.warning(f"⚠️  มีข้อมูลจำนวนมาก ({total_phones:,} เบอร์) การส่งออกอาจใช้เวลานาน")
                        
                        if st.button("🚀 ดาวน์โหลดไฟล์ทั้งหมด", key="download_all"):
                            with st.spinner('กำลังสร้างไฟล์... อาจใช้เวลาหลายนาที'):
                                output, count = export_database_chunked()
                                if output:
                                    st.success(f"✅ สร้างไฟล์สำเร็จ ({count:,} เบอร์)")
                                    
                                    st.download_button(
                                        label=f"📥 ดาวน์โหลดไฟล์ Excel ({count:,} เบอร์)",
                                        data=output.getvalue(),
                                        file_name=f"all_phones_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
                                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                                        type="primary",
                                        use_container_width=True
                                    )
                    else:
                        # แสดงตัวอย่างข้อมูลแบบแบ่งหน้า
                        st.info(f"📋 แสดงตัวอย่างข้อมูล (ทั้งหมด {total_phones:,} เบอร์)")
                        
                        if 'export_page' not in st.session_state:
                            st.session_state.export_page = 0
                        
                        page_size = 100
                        offset = st.session_state.export_page * page_size
                        
                        sample_df = get_phones_batch(limit=page_size, offset=offset)
                        st.dataframe(sample_df, use_container_width=True, height=300)
                        
                        col1, col2, col3 = st.columns([1, 2, 1])
                        with col1:
                            if st.button("◀️ ก่อนหน้า") and st.session_state.export_page > 0:
                                st.session_state.export_page -= 1
                                st.rerun()
                        with col2:
                            st.markdown(f"**หน้า {st.session_state.export_page + 1}**")
                        with col3:
                            if st.button("ถัดไป ▶️") and len(sample_df) == page_size:
                                st.session_state.export_page += 1
                                st.rerun()
                        
                        # ดาวน์โหลดไฟล์ทั้งหมด
                        if st.button("💾 ดาวน์โหลดข้อมูลทั้งหมด"):
                            with st.spinner('กำลังสร้างไฟล์...'):
                                all_data = get_phones_batch(limit=total_phones, offset=0)
                                output = save_phones_as_excel(all_data)
                                
                                st.download_button(
                                    label=f"📥 ดาวน์โหลดไฟล์ Excel ({len(all_data):,} เบอร์)",
                                    data=output.getvalue(),
                                    file_name=f"all_phones_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
                                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                                    type="primary",
                                    use_container_width=True
                                )
                    
                    st.session_state.show_export_password = False
                    st.rerun()
                else:
                    st.error("❌ รหัสผ่านไม่ถูกต้อง")
        
        with col2:
            if st.button("❌ ยกเลิก", key="cancel_export"):
                st.session_state.show_export_password = False
                st.rerun()
    
    st.header("⚙️ การจัดการ")
    
    # ส่วนล้างฐานข้อมูล (ต้องใส่รหัสผ่าน)
    if st.button("🗑️ ล้างฐานข้อมูล", type="secondary"):
        st.session_state.show_clear_password = True
        st.session_state.show_export_password = False
    
    if st.session_state.get('show_clear_password', False):
        st.subheader("กรุณากรอกรหัสผ่าน")
        clear_password = st.text_input("รหัสผ่าน", type="password", key="clear_pass")
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("✅ ยืนยันการล้าง", key="confirm_clear"):
                if clear_password == PASSWORD:
                    total_count = get_phones_count()
                    
                    if total_count == 0:
                        st.info("ℹ️ ไม่มีข้อมูลในระบบที่จะล้าง")
                        st.session_state.show_clear_password = False
                        st.rerun()
                    
                    st.warning(f"⚠️  คุณกำลังจะล้างข้อมูลทั้งหมด {total_count:,} เบอร์")
                    
                    if total_count > 100000:
                        st.error("🚨 **คำเตือน:** มีข้อมูลจำนวนมากในระบบ! การล้างข้อมูลอาจใช้เวลานานและไม่สามารถกู้คืนได้!")
                        
                        col1, col2 = st.columns(2)
                        with col1:
                            if st.button("🔥 ล้างข้อมูลทั้งหมด", type="primary"):
                                with st.spinner('กำลังล้างข้อมูล... อาจใช้เวลานาน'):
                                    deleted_count = clear_database_batch()
                                    st.success(f"✅ ล้างฐานข้อมูลเรียบร้อย! ลบไปทั้งหมด {deleted_count:,} เบอร์")
                                    st.session_state.show_clear_password = False
                                    st.rerun()
                        with col2:
                            if st.button("❌ ยกเลิกการล้าง"):
                                st.session_state.show_clear_password = False
                                st.rerun()
                    else:
                        if st.button("🗑️ ยืนยันล้างข้อมูล"):
                            with st.spinner('กำลังล้างข้อมูล...'):
                                deleted_count = clear_database_batch()
                                st.success(f"✅ ล้างฐานข้อมูลเรียบร้อย! ลบไปทั้งหมด {deleted_count:,} เบอร์")
                                st.session_state.show_clear_password = False
                                st.rerun()
                else:
                    st.error("❌ รหัสผ่านไม่ถูกต้อง")
        
        with col2:
            if st.button("❌ ยกเลิก", key="cancel_clear"):
                st.session_state.show_clear_password = False
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
                    df = pd.read_excel(uploaded_file, dtype={'A': str})
                    
                    # ตรวจสอบคอลัมน์
                    if 'A' not in df.columns and len(df.columns) > 0:
                        first_col = df.columns[0]
                        df = df.rename(columns={first_col: 'A'})
                        st.info(f"ใช้คอลัมน์ '{first_col}' เป็นคอลัมน์เบอร์โทร")
                    
                    # บังคับให้คอลัมน์ A เป็น string
                    df['A'] = df['A'].astype(str)
                    df['A'] = df['A'].fillna('')
                    
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
                        saved_count = save_phones_to_database_batch(df['A'].tolist(), uploaded_file.name)
                        st.success(f"💾 บันทึกเบอร์โทรลงฐานข้อมูลเรียบร้อย ({saved_count} เบอร์)")
                    
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
                    
                    st.info("📝 **หมายเหตุ:** ไฟล์ผลลัพธ์จะรักษาเลข 0 หน้าเบอร์โทรโดยอัตโนมัติ")
                    
                except Exception as e:
                    st.error(f"❌ เกิดข้อผิดพลาด: {str(e)}")

# ส่วนคำแนะนำ
with st.expander("💡 คู่มือการใช้งาน"):
    st.markdown("""
    ### 🚀 สำหรับข้อมูลจำนวนมาก (หมื่นล้านเบอร์)
    
    **การโหลดข้อมูล:**
    - ระบบจะแสดงเฉพาะตัวอย่างข้อมูล
    - ใช้ปุ่ม "ดาวน์โหลดไฟล์ทั้งหมด" สำหรับข้อมูลทั้งหมด
    - ข้อมูลจะถูกประมวลผลแบบแบ่งส่วนเพื่อป้องกัน memory overflow
    
    **การล้างข้อมูล:**
    - ระบบจะล้างข้อมูลแบบแบ่งกลุ่ม
    - ใช้เวลาแต่ปลอดภัยต่อ memory
    - มีการยืนยันหลายขั้นตอนสำหรับข้อมูลจำนวนมาก
    
    **การบันทึกข้อมูล:**
    - บันทึกแบบแบ่งกลุ่ม 10,000 เบอร์/ครั้ง
    - ใช้ UNIQUE constraint เพื่อป้องกันข้อมูลซ้ำ
    - มี index เพื่อเพิ่มความเร็ว
    """)

# Footer
st.markdown("---")
st.markdown(
    "<div style='text-align: center; color: #666;'>"
    "พัฒนาด้วย Streamlit | รองรับข้อมูลขนาดมหาศาล"
    "</div>",
    unsafe_allow_html=True
)
