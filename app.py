import streamlit as st
import pandas as pd
import sqlite3
import io
from datetime import datetime
import openpyxl

# ตั้งค่าหน้า
st.set_page_config(
    page_title="โปรแกรมเช็คเบอร์โทรซ้ำ",
    page_icon="📱",
    layout="wide"
)

# ฟังก์ชันจัดการฐานข้อมูล
def init_database():
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
    if pd.isna(phone) or phone == '' or phone is None:
        return ""
    phone_str = str(phone).strip()
    digits_only = ''.join(filter(str.isdigit, phone_str))
    return digits_only[-9:] if len(digits_only) >= 9 else digits_only

def get_all_last_9_digits():
    conn = sqlite3.connect('phone_database.db')
    cursor = conn.cursor()
    cursor.execute("SELECT last_9_digits FROM old_phones WHERE LENGTH(last_9_digits) = 9")
    results = cursor.fetchall()
    conn.close()
    return set([result[0] for result in results])

def get_database_stats():
    conn = sqlite3.connect('phone_database.db')
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM old_phones")
    total_count = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM old_phones WHERE LENGTH(last_9_digits) = 9")
    valid_count = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(DISTINCT source_file) FROM old_phones")
    file_count = cursor.fetchone()[0]
    conn.close()
    return total_count, valid_count, file_count

def save_phones_to_database(phone_numbers, source_file=""):
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
    conn = sqlite3.connect('phone_database.db')
    conn.execute("DELETE FROM old_phones")
    conn.commit()
    conn.close()

def save_phones_as_excel(df):
    output = io.BytesIO()
    wb = openpyxl.Workbook()
    ws = wb.active
    
    # เขียนหัวข้อ
    for col_idx, col_name in enumerate(df.columns, 1):
        cell = ws.cell(row=1, column=col_idx, value=col_name)
    
    # เขียนข้อมูล
    for row_idx, row_data in enumerate(df.values, 2):
        for col_idx, value in enumerate(row_data, 1):
            cell = ws.cell(row=row_idx, column=col_idx)
            if col_idx == 1:  # คอลัมน์เบอร์โทร
                if pd.notna(value) and value != '':
                    cell.value = str(value)
                    cell.number_format = '@'
                else:
                    cell.value = ''
            else:
                if pd.notna(value):
                    cell.value = value
                else:
                    cell.value = ''
    
    ws.column_dimensions['A'].width = 20
    wb.save(output)
    output.seek(0)
    return output

# เริ่มต้นฐานข้อมูล
init_database()

# UI
st.title("📱 โปรแกรมเช็คเบอร์โทรซ้ำ")

# แท็บหลัก
tab1, tab2, tab3 = st.tabs(["🔍 ตรวจสอบเบอร์โทร", "📊 ดูข้อมูลในระบบ", "⚙️ การจัดการ"])

with tab1:
    st.header("ตรวจสอบเบอร์โทรซ้ำ")
    st.markdown("อัพโหลดไฟล์ Excel เพื่อตรวจสอบเบอร์โทรซ้ำโดยใช้**ตัวเลข 9 ตัวท้าย**")
    
    uploaded_file = st.file_uploader("เลือกไฟล์ Excel", type=['xlsx', 'xls'])
    
    if uploaded_file is not None:
        col1, col2 = st.columns(2)
        with col1:
            save_to_db = st.checkbox("💾 บันทึกเบอร์จากไฟล์นี้ลงฐานข้อมูล", value=True)
        with col2:
            if st.button("🚀 เริ่มตรวจสอบเบอร์โทรซ้ำ", type="primary", use_container_width=True):
                with st.spinner('กำลังตรวจสอบเบอร์โทรซ้ำ...'):
                    try:
                        df = pd.read_excel(uploaded_file, dtype={'A': str})
                        
                        if 'A' not in df.columns and len(df.columns) > 0:
                            first_col = df.columns[0]
                            df = df.rename(columns={first_col: 'A'})
                            st.info(f"ใช้คอลัมน์ '{first_col}' เป็นคอลัมน์เบอร์โทร")
                        
                        df['A'] = df['A'].astype(str).fillna('')
                        df['last_9_digits'] = df['A'].apply(extract_last_9_digits)
                        existing_last_9_digits = get_all_last_9_digits()
                        df['is_duplicate'] = df['last_9_digits'].isin(existing_last_9_digits)
                        unique_df = df[~df['is_duplicate']].copy()
                        
                        for col in ['last_9_digits', 'is_duplicate']:
                            if col in unique_df.columns:
                                unique_df = unique_df.drop(columns=[col])
                        
                        if save_to_db:
                            save_phones_to_database(df['A'].tolist(), uploaded_file.name)
                            st.success("💾 บันทึกเบอร์โทรลงฐานข้อมูลเรียบร้อย")
                        
                        st.success("✅ ตรวจสอบเสร็จสิ้น!")
                        
                        col1, col2, col3 = st.columns(3)
                        with col1:
                            st.metric("เบอร์โทรทั้งหมด", len(df))
                        with col2:
                            st.metric("เบอร์ที่ไม่ซ้ำ", len(unique_df))
                        with col3:
                            st.metric("เบอร์ที่ซ้ำ", len(df) - len(unique_df))
                        
                        original_name = uploaded_file.name
                        if '.' in original_name:
                            name_without_ext = original_name.rsplit('.', 1)[0]
                            extension = original_name.rsplit('.', 1)[1]
                            download_filename = f"{name_without_ext}-Cut.{extension}"
                        else:
                            download_filename = f"{original_name}-Cut.xlsx"
                        
                        output = save_phones_as_excel(unique_df)
                        
                        st.download_button(
                            label="💾 ดาวน์โหลดไฟล์ผลลัพธ์",
                            data=output.getvalue(),
                            file_name=download_filename,
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                            type="primary",
                            use_container_width=True
                        )
                        
                    except Exception as e:
                        st.error(f"❌ เกิดข้อผิดพลาด: {str(e)}")

with tab2:
    st.header("ข้อมูลเบอร์โทรในระบบ")
    
    total_count, valid_count, file_count = get_database_stats()
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("เบอร์โทรทั้งหมด", total_count)
    with col2:
        st.metric("เบอร์ 9 ตัวสมบูรณ์", valid_count)
    with col3:
        st.metric("ไฟล์ต้นทาง", file_count)
    with col4:
        completeness = (valid_count/total_count*100) if total_count > 0 else 0
        st.metric("อัตราสมบูรณ์", f"{completeness:.1f}%")
    
    if st.button("🔄 โหลดข้อมูลล่าสุด"):
        try:
            conn = sqlite3.connect('phone_database.db')
            df_all_phones = pd.read_sql_query("""
                SELECT 
                    phone_number as 'เบอร์โทร',
                    last_9_digits as '9 ตัวท้าย',
                    source_file as 'ไฟล์ต้นทาง',
                    created_date as 'วันที่บันทึก'
                FROM old_phones 
                ORDER BY created_date DESC
            """, conn)
            conn.close()
            
            if len(df_all_phones) > 0:
                st.success(f"พบเบอร์โทรทั้งหมด {len(df_all_phones)} เบอร์")
                st.dataframe(df_all_phones, use_container_width=True)
                
                # สถิติเพิ่มเติม
                st.subheader("📈 สถิติเพิ่มเติม")
                col1, col2 = st.columns(2)
                with col1:
                    st.write("**ไฟล์ต้นทางล่าสุด:**")
                    recent_files = df_all_phones['ไฟล์ต้นทาง'].value_counts().head(5)
                    for file, count in recent_files.items():
                        st.write(f"- {file}: {count} เบอร์")
                with col2:
                    st.write("**การกระจายตัว:**")
                    # แก้ไขบรรทัดนี้ - ใช้วิธีที่ถูกต้อง
                    starts_with_0 = len(df_all_phones[df_all_phones['เบอร์โทร'].str.startswith('0', na=False)])
                    starts_with_6 = len(df_all_phones[df_all_phones['เบอร์โทร'].str.startswith('6', na=False)])
                    starts_with_8 = len(df_all_phones[df_all_phones['เบอร์โทร'].str.startswith('8', na=False)])
                    
                    st.write(f"- เบอร์ที่ขึ้นต้นด้วย 0: {starts_with_0}")
                    st.write(f"- เบอร์ที่ขึ้นต้นด้วย 6: {starts_with_6}")
                    st.write(f"- เบอร์ที่ขึ้นต้นด้วย 8: {starts_with_8}")
                
                # ดาวน์โหลด
                output_all = io.BytesIO()
                df_all_phones.to_excel(output_all, index=False)
                output_all.seek(0)
                
                st.download_button(
                    label="📥 ดาวน์โหลดข้อมูลทั้งหมด",
                    data=output_all.getvalue(),
                    file_name=f"all_phones_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
            else:
                st.info("⚠️ ยังไม่มีเบอร์โทรในระบบ")
                
        except Exception as e:
            st.error(f"เกิดข้อผิดพลาด: {str(e)}")

with tab3:
    st.header("การจัดการระบบ")
    
    st.subheader("🗑️ ล้างฐานข้อมูล")
    st.warning("การล้างฐานข้อมูลจะทำให้ข้อมูลเบอร์โทรทั้งหมดหายไป!")
    
    if st.button("ล้างฐานข้อมูลทั้งหมด", type="secondary"):
        if st.session_state.get('confirm_clear', False):
            clear_database()
            st.success("ล้างฐานข้อมูลเรียบร้อย!")
            st.session_state.confirm_clear = False
            st.rerun()
        else:
            st.session_state.confirm_clear = True
            st.error("⚠️ คลิกอีกครั้งเพื่อยืนยันการล้างฐานข้อมูล!")
    
    if st.session_state.get('confirm_clear', False):
        col1, col2 = st.columns(2)
        with col1:
            if st.button("✅ ยืนยันการล้าง", type="primary"):
                clear_database()
                st.success("ล้างฐานข้อมูลเรียบร้อย!")
                st.session_state.confirm_clear = False
                st.rerun()
        with col2:
            if st.button("❌ ยกเลิก"):
                st.session_state.confirm_clear = False
                st.rerun()
    
    st.subheader("💾 สำรองข้อมูล")
    try:
        with open('phone_database.db', 'rb') as f:
            st.download_button(
                label="📥 ดาวน์โหลดไฟล์ฐานข้อมูล",
                data=f,
                file_name=f"phone_database_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db",
                mime="application/octet-stream"
            )
    except Exception as e:
        st.error(f"ไม่สามารถดาวน์โหลดฐานข้อมูล: {str(e)}")

# Footer
st.markdown("---")
st.markdown(
    "<div style='text-align: center; color: #666;'>"
    "พัฒนาด้วย Streamlit | โปรแกรมเช็คเบอร์โทรซ้ำ"
    "</div>",
    unsafe_allow_html=True
)
