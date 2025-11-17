import streamlit as st
import pandas as pd
import sqlite3

st.set_page_config(page_title="โปรแกรมเช็คเบอร์โทรซ้ำ", page_icon="📱")

st.title("📱 โปรแกรมเช็คเบอร์โทรซ้ำ")
st.write("แอปพร้อมทำงาน!")

# ทดสอบการ import
try:
    st.success("✅ Streamlit ทำงานได้")
    st.success("✅ Pandas ทำงานได้") 
    st.success("✅ SQLite ทำงานได้")
except Exception as e:
    st.error(f"❌ Import error: {e}")
