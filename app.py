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

# รหัสผ่าน
PASSWORD = "23669"

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

def get_all_phones_from_database():
    """ดึงเบอร์โทรทั้งหมดจากฐานข้อมูล"""
    conn = sqlite3.connect('phone_database.db')
    
    query = """
    SELECT 
        phone_number,
        last_9_digits,
        source_file,
        created_date
    FROM old_phones
    ORDER BY created_date DESC
    """
    
    df = pd.read_sql_query(query, conn)
    conn.close()
    return df

def get_phones_count():
    """นับจำนวนเบอร์โทรทั้งหมด"""
    conn = sqlite3.connect('phone_database.db')
    cursor = conn.cursor()
    
    cursor.execute("SELECT COUNT(*) FROM old_phones")
    count = cursor.fetchone()[0]
    
    conn.close()
    return count

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
    
    # เขียนข้อมูลแถวที่ 2 ขึ้นไป
    for row_idx, row_data in enumerate(df.values, 2):
        for col_idx, value in enumerate(row_data, 1):
            cell = ws.cell(row=row_idx, column=col_idx)
            
            # คอลัมน์แรก (เบอร์โทร) บังคับให้เป็น text
            if col_idx == 1:
                if pd.notna(value) and value != '':
                    # ตั้งค่าเป็น text format โดยไม่ใช้ apostrophe
                    cell.value = str(value)
                    cell.number_format = '@'  # Text format
                else:
                    cell.value = ''
            else:
                # คอลัมน์อื่นๆ
                if pd.notna(value):
                    cell.value = value
                else:
                    cell.value = ''
    
    # ตั้งค่า column width
    for col_idx, col_name in enumerate(df.columns, 1):
        ws.column_dimensions[openpyxl.utils.get_column_letter(col_idx)].width = 20
    
    wb.save(output)
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
                    # ตรวจสอบจำนวนข้อมูลก่อน
                    total_phones = get_phones_count()
                    
                    if total_phones == 0:
                        st.info("ℹ️ ยังไม่มีข้อมูลเบอร์โทรในระบบ")
                        st.session_state.show_export_password = False
                        st.rerun()
                    
                    # แสดง progress bar สำหรับข้อมูลจำนวนมาก
                    progress_bar = st.progress(0)
                    status_text = st.empty()
                    
                    status_text.text("📥 กำลังโหลดข้อมูลจากฐานข้อมูล...")
                    progress_bar.progress(30)
                    
                    try:
                        # ดึงข้อมูลทั้งหมดจากฐานข้อมูล
                        all_phones_df = get_all_phones_from_database()
                        progress_bar.progress(70)
                        
                        status_text.text("📊 กำลังประมวลผลข้อมูล...")
                        
                        # บันทึกข้อมูลลง session state เพื่อใช้ใน pagination
                        st.session_state.export_data = all_phones_df
                        st.session_state.current_page = 0
                        st.session_state.rows_per_page = 20
                        
                        progress_bar.progress(100)
                        status_text.text("✅ โหลดข้อมูลเสร็จสิ้น!")
                        
                        # แสดงผลลัพธ์
                        st.success(f"✅ พบเบอร์โทรทั้งหมด {len(all_phones_df):,} เบอร์")
                        
                        # แสดงสถิติเพิ่มเติม
                        st.subheader("📈 สถิติเพิ่มเติม")
                        col1, col2, col3 = st.columns(3)
                        with col1:
                            st.metric("ไฟล์ต้นทางที่แตกต่าง", all_phones_df['source_file'].nunique())
                        with col2:
                            valid_9_digits = len(all_phones_df[all_phones_df['last_9_digits'].str.len() == 9])
                            st.metric("เบอร์ที่มี 9 ตัวท้ายครบ", f"{valid_9_digits:,}")
                        with col3:
                            latest_date = all_phones_df['created_date'].max()
                            st.metric("ข้อมูลล่าสุด", pd.to_datetime(latest_date).strftime('%d/%m/%Y'))
                        
                        # แสดงข้อมูลแบบแบ่งหน้า
                        st.subheader("📋 ข้อมูลเบอร์โทรในระบบ")
                        
                        # ตั้งค่าการแบ่งหน้า
                        total_rows = len(all_phones_df)
                        total_pages = (total_rows + st.session_state.rows_per_page - 1) // st.session_state.rows_per_page
                        
                        # ปุ่มควบคุมหน้า
                        col1, col2, col3, col4, col5 = st.columns([1, 1, 2, 1, 1])
                        
                        with col1:
                            if st.button("⏪ หน้าแรก") and st.session_state.current_page > 0:
                                st.session_state.current_page = 0
                                st.rerun()
                        
                        with col2:
                            if st.button("◀️ ก่อนหน้า") and st.session_state.current_page > 0:
                                st.session_state.current_page -= 1
                                st.rerun()
                        
                        with col3:
                            st.markdown(f"**หน้า {st.session_state.current_page + 1} จาก {total_pages}**")
                            st.markdown(f"แสดง {st.session_state.rows_per_page} แถวต่อหน้า")
                        
                        with col4:
                            if st.button("ถัดไป ▶️") and st.session_state.current_page < total_pages - 1:
                                st.session_state.current_page += 1
                                st.rerun()
                        
                        with col5:
                            if st.button("หน้าสุดท้าย ⏩") and st.session_state.current_page < total_pages - 1:
                                st.session_state.current_page = total_pages - 1
                                st.rerun()
                        
                        # แสดงข้อมูลในหน้าปัจจุบัน
                        start_idx = st.session_state.current_page * st.session_state.rows_per_page
                        end_idx = min(start_idx + st.session_state.rows_per_page, total_rows)
                        
                        current_data = all_phones_df.iloc[start_idx:end_idx]
                        
                        # แสดงตารางข้อมูล
                        st.dataframe(
                            current_data,
                            use_container_width=True,
                            height=400
                        )
                        
                        # แสดงข้อมูลสรุป
                        st.info(f"📄 กำลังแสดงแถวที่ {start_idx + 1} ถึง {end_idx} จากทั้งหมด {total_rows:,} แถว")
                        
                        # ดาวน์โหลดไฟล์
                        st.subheader("💾 ดาวน์โหลดข้อมูลทั้งหมด")
                        st.warning("⚠️  **คำเตือน:** หากมีข้อมูลจำนวนมาก การดาวน์โหลดอาจใช้เวลาสักครู่")
                        
                        # สร้างไฟล์ Excel สำหรับดาวน์โหลด
                        output = save_phones_as_excel(all_phones_df)
                        
                        # ดาวน์โหลดไฟล์
                        st.download_button(
                            label=f"📥 ดาวน์โหลดไฟล์ Excel ({len(all_phones_df):,} เบอร์)",
                            data=output.getvalue(),
                            file_name=f"all_phones_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                            type="primary",
                            use_container_width=True
                        )
                        
                    except Exception as e:
                        st.error(f"❌ เกิดข้อผิดพลาดในการโหลดข้อมูล: {str(e)}")
                        import traceback
                        st.code(traceback.format_exc())
                    
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
                    # แสดงจำนวนข้อมูลที่จะล้าง
                    total_count, _ = get_database_stats()
                    if total_count > 0:
                        st.warning(f"⚠️  คุณกำลังจะล้างข้อมูลทั้งหมด {total_count:,} เบอร์ออกจากระบบ")
                        
                        # ยืนยันอีกครั้งสำหรับข้อมูลจำนวนมาก
                        if total_count > 1000:
                            st.error("🚨 **คำเตือน:** มีข้อมูลจำนวนมากในระบบ การล้างข้อมูลไม่สามารถกู้คืนได้!")
                            confirm_final = st.checkbox("ฉันเข้าใจและต้องการล้างข้อมูลทั้งหมดจริงๆ")
                            if confirm_final:
                                clear_database()
                                st.success("✅ ล้างฐานข้อมูลเรียบร้อย!")
                                st.session_state.show_clear_password = False
                                st.rerun()
                        else:
                            clear_database()
                            st.success("✅ ล้างฐานข้อมูลเรียบร้อย!")
                            st.session_state.show_clear_password = False
                            st.rerun()
                    else:
                        st.info("ℹ️ ไม่มีข้อมูลในระบบที่จะล้าง")
                        st.session_state.show_clear_password = False
                        st.rerun()
                else:
                    st.error("❌ รหัสผ่านไม่ถูกต้อง")
        
        with col2:
            if st.button("❌ ยกเลิก", key="cancel_clear"):
                st.session_state.show_clear_password = False
                st.rerun()

# ส่วนหลัก (ส่วนที่เหลือของโค้ดเดิม)
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
                    
                    st.info("📝 **หมายเหตุ:** ไฟล์ผลลัพธ์จะรักษาเลข 0 หน้าเบอร์โทรโดยอัตโนมัติ")
                    
                except Exception as e:
                    st.error(f"❌ เกิดข้อผิดพลาด: {str(e)}")
                    import traceback
                    st.code(traceback.format_exc())

# ส่วนคำแนะนำ
with st.expander("💡 คู่มือการใช้งาน"):
    st.markdown("""
    ### 📝 วิธีการใช้โปรแกรม
    
    1. **เตรียมไฟล์ Excel**: ไฟล์ต้องมีคอลัมน์ **A** หรือคอลัมน์แรกเป็นเบอร์โทร
    2. **อัพโหลดไฟล์**: คลิกปุ่ม "Browse files" เพื่อเลือกไฟล์ Excel
    3. **เริ่มตรวจสอบ**: คลิกปุ่ม "เริ่มตรวจสอบเบอร์โทรซ้ำ"
    4. **ดาวน์โหลดผลลัพธ์**: ดาวน์โหลดไฟล์ที่มีเฉพาะเบอร์ที่ไม่ซ้ำ
    
    ### 🔐 การรักษาความปลอดภัย
    
    - **โหลดข้อมูลทั้งหมด**: ต้องใช้รหัสผ่าน **23669**
    - **ล้างฐานข้อมูล**: ต้องใช้รหัสผ่าน **23669**
    
    ### 🔍 หลักการทำงาน
    
    - ตรวจสอบซ้ำโดยใช้ **ตัวเลข 9 ตัวท้าย** ของเบอร์โทร
    - ตัวอย่าง: เบอร์ `081-234-5678` จะใช้ `123456789` ในการตรวจสอบ
    - เบอร์ที่ซ้ำจะถูกกรองออกจากผลลัพธ์
    - **รักษาเลข 0 หน้าเบอร์โทร** โดยอัตโนมัติ
    
    ### 💾 การจัดการข้อมูล
    
    - **บันทึกข้อมูล**: เมื่อเลือก "บันทึกเบอร์จากไฟล์นี้ลงฐานข้อมูล"
    - **โหลดข้อมูล**: ใช้ปุ่ม "โหลดเบอร์โทรทั้งหมดจากระบบ" ใน sidebar (ต้องใช้รหัสผ่าน)
    - **ล้างข้อมูล**: ใช้ปุ่ม "ล้างฐานข้อมูล" ใน sidebar (ต้องใช้รหัสผ่าน)
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
