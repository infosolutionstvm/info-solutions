import os
import base64
import json
import io
import urllib.parse
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components
from datetime import datetime
import psycopg2
from psycopg2.extras import RealDictCursor

# ----------------- 1. PAGE CONFIGURATION -----------------
st.set_page_config(
    page_title="INFO SOLUTIONS | Service & Quotation Portal",
    page_icon="🖥️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ----------------- 2. LOGIN SYSTEM -----------------
def check_password():
    if "authenticated" not in st.session_state:
        st.session_state["authenticated"] = False

    if not st.session_state["authenticated"]:
        st.markdown("### 🔒 INFO SOLUTIONS - Secure Login")
        pwd = st.text_input("Enter Access Password", type="password", key="login_pwd_input")
        if st.button("Login", key="login_submit_btn", type="primary"):
            # 👈 നിങ്ങളുടെ ആവശ്യമനുസരിച്ച് ഈ പാസ്‌വേഡ് മാറ്റാം
            if pwd == "passwordilla":
                st.session_state["authenticated"] = True
                st.rerun()
            else:
                st.error("തെറ്റായ പാസ്‌വേഡ്! ദയവായി വീണ്ടും ശ്രമിക്കുക.")
        return False
    return True

if not check_password():
    st.stop()  # പാസ്‌വേഡ് ശരിയല്ലെങ്കിൽ ആപ്പിന്റെ ബാക്കി ഭാഗം പ്രവർത്തിക്കില്ല

# ----------------- 3. SUPABASE DATABASE CONNECTION -----------------
def get_db_connection():
    # Streamlit Secrets (.streamlit/secrets.toml) വഴി connection string എടുക്കുന്നു
    try:
        conn_url = st.secrets["postgres"]["url"]
        conn = psycopg2.connect(conn_url)
        return conn
    except Exception as e:
        st.error(f"⚠️ ഡാറ്റാബേസ് കണക്ഷൻ പരാജയപ്പെട്ടു: {e}")
        st.info("Streamlit Secrets-ൽ Supabase Connection URL നൽകിയിട്ടുണ്ടെന്ന് ഉറപ്പാക്കുക.")
        st.stop()

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Services Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS services (
            job_no SERIAL PRIMARY KEY,
            cust_name TEXT, phone TEXT, item_type TEXT, item_desc TEXT,
            complaint TEXT, received_date TEXT, status TEXT, service_charge REAL, delivery_date TEXT
        )
    """)
    
    # Quotations Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS quotations (
            quote_no TEXT PRIMARY KEY, cust_name TEXT, phone TEXT, category TEXT,
            quote_date TEXT, items_json TEXT, subtotal REAL, tax_total REAL, grand_total REAL
        )
    """)

    # Master Products Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS master_products (
            id SERIAL PRIMARY KEY, item_name TEXT UNIQUE,
            unit_price REAL DEFAULT 0.0, tax_pct REAL DEFAULT 18.0
        )
    """)
    
    # Insert default products if empty
    cursor.execute("SELECT COUNT(*) FROM master_products;")
    if cursor.fetchone()[0] == 0:
        default_items = [
            ("5KW Solar Panel System - On Grid", 225000.0, 12.0),
            ("3KW Solar Hybrid Inverter", 45000.0, 12.0),
            ("Hikvision 2MP Outdoor Bullet Camera", 1650.0, 18.0),
            ("Hikvision 8-Channel HD DVR", 4200.0, 18.0),
            ("D-Link Cat6 Networking Cable Roll (305m)", 7800.0, 18.0),
            ("Dell Vostro Laptop Core i5 12th Gen", 54500.0, 18.0),
            ("Logitech Wireless Combo Keyboard & Mouse", 1350.0, 18.0)
        ]
        cursor.executemany(
            "INSERT INTO master_products (item_name, unit_price, tax_pct) VALUES (%s, %s, %s) ON CONFLICT DO NOTHING;", 
            default_items
        )

    conn.commit()
    cursor.close()
    conn.close()

init_db()

# Helper DB Functions
def save_or_update_product(item_name, price, tax):
    if not item_name.strip(): return
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO master_products (item_name, unit_price, tax_pct) VALUES (%s, %s, %s)
        ON CONFLICT(item_name) DO UPDATE SET unit_price = EXCLUDED.unit_price, tax_pct = EXCLUDED.tax_pct;
    """, (item_name.strip(), price, tax))
    conn.commit()
    cursor.close()
    conn.close()

def get_all_master_products():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT item_name, unit_price, tax_pct FROM master_products ORDER BY item_name ASC;")
    rows = cursor.fetchall()
    cursor.close()
    conn.close()
    return rows

# ----------------- 4. LOGO & UTILITIES -----------------
LOGO_PATH = "logo.png"
has_logo = os.path.exists(LOGO_PATH)

def get_base64_logo(path):
    if os.path.exists(path):
        with open(path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode()
    return ""

logo_base64 = get_base64_logo(LOGO_PATH)

def format_phone_for_whatsapp(phone_num):
    clean_num = ''.join(filter(str.isdigit, str(phone_num)))
    return f"91{clean_num}" if len(clean_num) == 10 else clean_num

def create_whatsapp_text(q_no, q_cust_name, q_type, items, subtotal, total_tax, grand_total):
    items_text = ""
    for idx, item in enumerate(items, 1):
        items_text += f"\n{idx}. *{item['desc']}*\n    Qty: {item['qty']} | Rate: ₹{item['rate']:,.2f} | Total: ₹{item['total']:,.2f}"

    message = (
        f"📄 *QUOTATION FROM INFO SOLUTIONS*\n"
        f"----------------------------------------\n"
        f"📋 *Ref No:* {q_no}\n"
        f"👤 *Customer:* {q_cust_name if q_cust_name else 'Valued Customer'}\n"
        f"📁 *Category:* {q_type}\n"
        f"----------------------------------------\n"
        f"*ITEMS DETAILED:* {items_text}\n"
        f"----------------------------------------\n"
        f"💰 *Subtotal:* ₹{subtotal:,.2f}\n"
        f"🧾 *GST Tax:* ₹{total_tax:,.2f}\n"
        f"💵 *Grand Total: ₹{grand_total:,.2f}*\n"
        f"----------------------------------------\n"
        f"📞 *Contact Us:* +91 89219 91643, +91 97445 77543\n"
        f"📍 *Location:* Kaimanam, Thiruvananthapuram\n\n"
        f"Thank you for choosing INFO SOLUTIONS!"
    )
    return message

def get_terms_html(category):
    cat_str = str(category).upper()
    if any(keyword in cat_str for keyword in ["CCTV", "COMPUTER", "LAPTOP"]):
        validity_text = "Quotation valid for <strong>5 days</strong> from issue date (market price fluctuations)."
    else:
        validity_text = "Quotation valid for <strong>15 days</strong> from the date of issue."
    
    return f"""
    <div class="terms">
        <strong>TERMS & CONDITIONS:</strong>
        <ul>
            <li>{validity_text}</li>
            <li>50% advance payment required upon work order confirmation for Solar & CCTV projects.</li>
            <li>Warranty as per manufacturer policies. Physical & liquid damages are not covered.</li>
            <li>Goods once sold will not be taken back or exchanged without prior written approval.</li>
        </ul>
    </div>
    """

# Custom CSS Styling
st.markdown("""
    <style>
    .stApp { background-color: #f8fafc; }
    .header-card {
        background: linear-gradient(135deg, #0f172a 0%, #1e293b 50%, #2563eb 100%);
        padding: 20px 30px;
        border-radius: 12px;
        color: white;
        box-shadow: 0 4px 15px rgba(0,0,0,0.1);
        margin-bottom: 25px;
    }
    .header-title { font-size: 26px; font-weight: 800; margin: 0; color: #ffffff; }
    .header-sub { font-size: 13px; color: #cbd5e1; margin-top: 4px; }
    [data-testid="stMetricValue"] { font-size: 24px; font-weight: bold; color: #1e293b; }
    .stButton>button { border-radius: 6px; font-weight: 600; }
    </style>
""", unsafe_allow_html=True)

# ----------------- 5. HEADER VIEW -----------------
with st.container():
    st.markdown("""
        <div class="header-card">
            <div style="display: flex; align-items: center; gap: 20px;">
    """, unsafe_allow_html=True)
    col_img, col_txt = st.columns([1, 5]) if has_logo else (st.empty(), st.container())
    if has_logo:
        with col_img: st.image(LOGO_PATH, width=90)
    with col_txt:
        st.markdown("""
            <div>
                <h1 class="header-title">INFO SOLUTIONS</h1>
                <p class="header-sub">Computer, CCTV, Networking & Solar Solutions</p>
            </div>
        """, unsafe_allow_html=True)
    st.markdown("</div></div>", unsafe_allow_html=True)

# ----------------- 6. FETCH INITIAL DATA -----------------
conn = get_db_connection()
cursor = conn.cursor()
cursor.execute("SELECT job_no, cust_name, phone, item_type, item_desc, complaint, received_date, status, service_charge, delivery_date FROM services ORDER BY job_no DESC;")
all_rows = cursor.fetchall()

cursor.execute("SELECT quote_no, cust_name, phone, category, quote_date, items_json, subtotal, tax_total, grand_total FROM quotations ORDER BY quote_date DESC;")
all_quotes = cursor.fetchall()
cursor.close()
conn.close()

# ----------------- 7. SIDEBAR MENU & LOGOUT -----------------
if has_logo: st.sidebar.image(LOGO_PATH, use_container_width=True)
st.sidebar.title("🛠️ Main Menu")
menu = st.sidebar.radio(
    "Go to", 
    ["Dashboard & Operations", "📄 Quotation Manager", "📊 Analytics & Excel Reports"],
    key="main_menu_radio"
)

st.sidebar.divider()
if st.sidebar.button("🚪 Logout", key="logout_btn", use_container_width=True, type="secondary"):
    st.session_state["authenticated"] = False
    st.rerun()

# Printable Quotation HTML Template
def generate_quotation_html(q_no, q_date, cust_name, phone, category, items, subtotal, total_tax, grand_total):
    table_rows_html = ""
    for idx, item in enumerate(items, 1):
        table_rows_html += f"""
        <tr>
            <td style="text-align:center;">{idx}</td>
            <td>{item['desc']}</td>
            <td style="text-align:center;">{item['qty']}</td>
            <td style="text-align:right;">₹{item['rate']:,.2f}</td>
            <td style="text-align:center;">{item['tax_pct']}%</td>
            <td style="text-align:right;">₹{item['total']:,.2f}</td>
        </tr>
        """

    logo_tag = f'<img src="data:image/png;base64,{logo_base64}" style="max-height: 55px;">' if logo_base64 else ''
    terms_block_html = get_terms_html(category)

    return f"""
    <html>
    <head>
        <style>
            @page {{ size: A4 portrait; margin: 8mm 12mm 15mm 12mm; }}
            * {{ box-sizing: border-box !important; -webkit-print-color-adjust: exact !important; print-color-adjust: exact !important; }}
            html, body {{ margin: 0; padding: 0; font-family: 'Segoe UI', Arial, sans-serif; background: #fff; color: #0f172a; width: 100%; height: 100%; }}
            .page-container {{ position: relative; width: 100%; min-height: 268mm; padding: 5mm 5mm 18mm 5mm; display: flex; flex-direction: column; justify-content: space-between; box-sizing: border-box; }}
            .header {{ display: flex; justify-content: space-between; align-items: center; border-bottom: 2.5px solid #0f172a; padding-bottom: 12px; margin-bottom: 18px; }}
            .badge {{ background-color: #0f172a !important; color: #ffffff !important; padding: 5px 12px; font-weight: bold; border-radius: 4px; text-transform: uppercase; font-size: 12px; display: inline-block; }}
            .info-grid {{ display: flex; justify-content: space-between; margin-bottom: 20px; font-size: 13px; line-height: 1.5; width: 100%; }}
            table {{ width: 100%; border-collapse: collapse; margin-top: 10px; font-size: 12px; table-layout: fixed; }}
            th {{ background-color: #0f172a !important; color: white !important; padding: 10px 8px; border: 1px solid #0f172a; font-weight: bold; font-size: 12.5px; }}
            td {{ padding: 10px 8px; border: 1px solid #cbd5e1; word-wrap: break-word; }}
            .totals-table {{ width: 45%; margin-left: auto; margin-top: 15px; font-size: 13px; }}
            .totals-table td {{ padding: 6px 8px; border: none; }}
            .terms {{ background-color: #f8fafc !important; border: 1px solid #cbd5e1; padding: 12px 15px; border-radius: 6px; font-size: 11px; line-height: 1.6; margin-top: 25px; width: 100%; }}
            .terms ul {{ margin: 4px 0 0 0; padding-left: 18px; }}
            .sign-container {{ display: flex; justify-content: space-between; align-items: flex-end; margin-top: 30px; font-size: 12px; font-weight: bold; width: 100%; }}
            .seal-box {{ width: 180px; height: 85px; border: 1px dashed #64748b; border-radius: 6px; margin-top: 8px; display: flex; align-items: center; justify-content: center; color: #94a3b8; font-size: 10px; font-weight: normal; }}
            .footer-bar {{ position: absolute; bottom: 0; left: 0; right: 0; width: 100%; background: linear-gradient(135deg, #0f2027, #203a43, #2c5364); color: #ffffff; text-align: center; padding: 8px 0; font-size: 9.5pt; letter-spacing: 0.3px; border-top: 2.5px solid #ffb703; box-sizing: border-box; }}
            .footer-bar .divider {{ color: #ffb703; margin: 0 6px; font-weight: bold; }}
            .btn {{ background: #2563eb; color: white; border: none; padding: 10px; width: 100%; border-radius: 6px; font-weight: bold; cursor: pointer; font-size: 13px; margin-top: 15px; }}
            @media print {{ .btn {{ display: none !important; }} .page-container {{ min-height: 98vh; padding-bottom: 15mm; }} }}
        </style>
    </head>
    <body>
        <div class="page-container">
            <div>
                <div class="header">
                    <div>
                        {logo_tag}
                        <h2 style="margin: 0; color: #0f172a; font-size: 20px;">INFO SOLUTIONS</h2>
                        <div style="font-size: 11px; font-weight: 600; margin-top: 2px;">Computer, CCTV, Networking & Solar System Installation</div>
                        <div style="font-size: 11px; font-weight: bold; color: #2563eb; margin-top: 2px;">Ph: +91 89219 91643, +91 97445 77543</div>
                    </div>
                    <div style="text-align: right;">
                        <div class="badge">OFFICIAL QUOTATION</div>
                        <div style="margin-top: 6px; font-size: 12px; font-weight: bold;">Ref: {q_no}</div>
                        <div style="font-size: 12px; margin-top: 2px;">Date: {q_date}</div>
                    </div>
                </div>

                <div class="info-grid">
                    <div>
                        <span style="color: #64748b;">QUOTATION FOR:</span><br>
                        <strong style="font-size: 14px; color: #0f172a;">{cust_name if cust_name else 'Valued Customer'}</strong><br>
                        <span>Ph: {phone if phone else 'N/A'}</span>
                    </div>
                    <div style="text-align: right;">
                        <span style="color: #64748b;">CATEGORY:</span><br>
                        <strong style="font-size: 13px; color: #2563eb;">{category}</strong>
                    </div>
                </div>

                <table>
                    <thead>
                        <tr>
                            <th style="width: 6%;">#</th>
                            <th style="width: 44%;">Item Description</th>
                            <th style="width: 8%;">Qty</th>
                            <th style="width: 14%;">Unit Price</th>
                            <th style="width: 10%;">GST</th>
                            <th style="width: 18%;">Total (₹)</th>
                        </tr>
                    </thead>
                    <tbody>{table_rows_html}</tbody>
                </table>

                <table class="totals-table">
                    <tr><td>Subtotal:</td><td style="text-align: right;">₹{subtotal:,.2f}</td></tr>
                    <tr><td>Tax Total:</td><td style="text-align: right;">₹{total_tax:,.2f}</td></tr>
                    <tr style="border-top: 2px solid #0f172a; font-size: 14px;">
                        <td><strong>Grand Total:</strong></td>
                        <td style="text-align: right; color: #2563eb;"><strong>₹{grand_total:,.2f}</strong></td>
                    </tr>
                </table>

                {terms_block_html}

                <div class="sign-container">
                    <div><br><br><br> Customer Signature</div>
                    <div style="text-align: right;">
                        Authorized Signatory<br>
                        <strong>INFO SOLUTIONS</strong>
                        <div class="seal-box">[ Stamp / Seal & Sign ]</div>
                    </div>
                </div>
            </div>

            <button class="btn" onclick="window.print()">🖨️ PRINT / SAVE AS PDF</button>

            <div class="footer-bar">
                <span>INFO SOLUTIONS</span>
                <span class="divider">|</span>
                <span>TC 52/501(1)</span>
                <span class="divider">|</span>
                <span>Opposite BSNL Kaimanam</span>
                <span class="divider">|</span>
                <span>Thiruvananthapuram 695018</span>
            </div>
        </div>
    </body>
    </html>
    """

# ----------------- 8. DASHBOARD & OPERATIONS PAGE -----------------
if menu == "Dashboard & Operations":
    total_jobs = len(all_rows)
    pending_jobs = sum(1 for r in all_rows if r[7] == "Pending")
    completed_jobs = sum(1 for r in all_rows if r[7] == "Completed")
    delivered_jobs = sum(1 for r in all_rows if r[7] == "Delivered")

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Total Job Cards", total_jobs)
    m2.metric("⏳ Pending", pending_jobs)
    m3.metric("✅ Completed", completed_jobs)
    m4.metric("🚚 Delivered", delivered_jobs)

    st.write("")
    left_col, right_col = st.columns([1, 1.6], gap="large")

    with left_col:
        st.subheader("📝 New Service Entry")
        with st.form("entry_form", clear_on_submit=True):
            cust_name = st.text_input("Customer Name *", placeholder="Enter full name")
            phone = st.text_input("Phone Number *", placeholder="10-digit mobile number")
            
            c1, c2 = st.columns(2)
            with c1: item_type = st.selectbox("Item Category", ["Laptop", "Desktop", "CCTV", "DVR/NVR", "Networking", "Solar System", "Printer", "Other"])
            with c2: status = st.selectbox("Initial Status", ["Pending", "Completed", "Delivered"])

            item_desc = st.text_input("Model / Serial Number", placeholder="e.g. Dell Inspiron / 5KW Solar Inverter")
            complaint = st.text_area("Reported Issue / Work Description", height=90)
            service_charge = st.number_input("Estimated / Service Charge (₹)", min_value=0.0, step=50.0, value=0.0)
            
            submit_btn = st.form_submit_button("➕ Save Service Entry", use_container_width=True, type="primary")

            if submit_btn:
                if not cust_name.strip() or not phone.strip():
                    st.error("⚠️ Customer Name and Phone Number are required!")
                else:
                    today = datetime.now().strftime("%d-%m-%Y")
                    del_date = today if status == "Delivered" else "-"
                    conn = get_db_connection()
                    cursor = conn.cursor()
                    cursor.execute("""
                        INSERT INTO services (cust_name, phone, item_type, item_desc, complaint, received_date, status, service_charge, delivery_date)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s);
                    """, (cust_name, phone, item_type, item_desc, complaint, today, status, service_charge, del_date))
                    conn.commit()
                    cursor.close()
                    conn.close()
                    st.toast("✅ New job card created in Supabase!", icon="🎉")
                    st.rerun()

    with right_col:
        st.subheader("🔍 Manage Job Cards")
        sf1, sf2 = st.columns([2, 1])
        with sf1: search_query = st.text_input("Search", placeholder="Type Name, Phone or Job No...", label_visibility="collapsed")
        with sf2: status_filter = st.selectbox("Filter", ["All", "Pending", "Completed", "Delivered"], label_visibility="collapsed")

        filtered_rows = all_rows
        if status_filter != "All": filtered_rows = [r for r in filtered_rows if r[7] == status_filter]
        if search_query.strip():
            sq = search_query.lower()
            filtered_rows = [r for r in filtered_rows if sq in str(r[0]).lower() or sq in str(r[1]).lower() or sq in str(r[2]).lower()]

        if filtered_rows:
            job_options = {f"Job #00{r[0]} | {r[1]} ({r[3]}) - [{r[7]}]": r for r in filtered_rows}
            selected_label = st.selectbox("Select Record:", list(job_options.keys()))
            selected_data = job_options[selected_label]

            tab_update, tab_receipt = st.tabs(["✏️ Edit / Update Status", "📄 Print Receipt"])

            with tab_update:
                st.write("")
                e_col1, e_col2 = st.columns(2)
                with e_col1:
                    edit_cust_name = st.text_input("Customer Name", value=selected_data[1])
                    edit_phone = st.text_input("Phone Number", value=selected_data[2])
                    edit_item_type = st.selectbox("Item Category", ["Laptop", "Desktop", "CCTV", "DVR/NVR", "Networking", "Solar System", "Printer", "Other"], 
                                                  index=["Laptop", "Desktop", "CCTV", "DVR/NVR", "Networking", "Solar System", "Printer", "Other"].index(selected_data[3]) if selected_data[3] in ["Laptop", "Desktop", "CCTV", "DVR/NVR", "Networking", "Solar System", "Printer", "Other"] else 0)
                with e_col2:
                    new_status = st.selectbox("Status", ["Pending", "Completed", "Delivered"], index=["Pending", "Completed", "Delivered"].index(selected_data[7]))
                    new_charge = st.number_input("Service Charge (₹)", min_value=0.0, step=50.0, value=float(selected_data[8]))
                    new_desc = st.text_input("Model / Serial No", value=selected_data[4])
                
                new_complaint = st.text_area("Complaint Note / Issue", value=selected_data[5], height=68)

                st.divider()

                ub1, ub2, ub3 = st.columns([1.2, 1.2, 1])
                
                with ub1:
                    if st.button("💾 Save Changes", use_container_width=True, type="primary"):
                        today = datetime.now().strftime("%d-%m-%Y")
                        del_date = today if new_status == "Delivered" else "-"
                        conn = get_db_connection()
                        cursor = conn.cursor()
                        cursor.execute("""
                            UPDATE services 
                            SET cust_name=%s, phone=%s, item_type=%s, item_desc=%s, complaint=%s, status=%s, service_charge=%s, delivery_date=%s 
                            WHERE job_no=%s;
                        """, (edit_cust_name, edit_phone, edit_item_type, new_desc, new_complaint, new_status, new_charge, del_date, selected_data[0]))
                        conn.commit()
                        cursor.close()
                        conn.close()
                        st.toast("Service record updated successfully!", icon="✅")
                        st.rerun()

                with ub2:
                    wa_phone = format_phone_for_whatsapp(edit_phone)
                    wa_msg = f"Hello *{edit_cust_name}*,\n\nYour service job (*#00{selected_data[0]}*) status at *INFO SOLUTIONS* is now: *{new_status}*.\nCharge: ₹{new_charge}\n\nPh: +91 89219 91643"
                    st.link_button("💬 WhatsApp Status", f"https://wa.me/{wa_phone}?text={urllib.parse.quote(wa_msg)}", use_container_width=True)

                with ub3:
                    if st.button("🗑️ Delete Job", type="secondary", use_container_width=True):
                        conn = get_db_connection()
                        cursor = conn.cursor()
                        cursor.execute("DELETE FROM services WHERE job_no = %s;", (selected_data[0],))
                        conn.commit()
                        cursor.close()
                        conn.close()
                        st.toast(f"Job #00{selected_data[0]} deleted!", icon="🗑️")
                        st.rerun()

            with tab_receipt:
                logo_tag = f'<img src="data:image/png;base64,{logo_base64}" style="max-height: 50px;">' if logo_base64 else ''
                html_receipt = f"""
                <html>
                <head>
                    <style>
                        @page {{ size: A5 landscape; margin: 4mm; }}
                        * {{ box-sizing: border-box; -webkit-print-color-adjust: exact !important; print-color-adjust: exact !important; }}
                        body {{ font-family: 'Segoe UI', sans-serif; margin: 0; background: #fff; }}
                        .box {{ border: 2px solid #0f172a; padding: 15px; border-radius: 6px; min-height: 95vh; display: flex; flex-direction: column; justify-content: space-between; }}
                        .header {{ display: flex; align-items: center; justify-content: center; gap: 15px; border-bottom: 2px solid #0f172a; padding-bottom: 8px; text-align: center; }}
                        .badge {{ background: #0f172a !important; color: #fff !important; padding: 4px 12px; font-weight: bold; border-radius: 4px; text-transform: uppercase; font-size: 11px; display: inline-block; margin: 10px 0; border: 1px solid #000; }}
                        .grid {{ display: flex; gap: 20px; }}
                        .col {{ flex: 1; }}
                        .row {{ display: flex; justify-content: space-between; margin: 6px 0; font-size: 12px; }}
                        .terms {{ background: #f8fafc !important; border: 1px solid #cbd5e1; padding: 8px; font-size: 9px; margin-top: 10px; border-radius: 4px; }}
                        .sign {{ display: flex; justify-content: space-between; margin-top: 15px; font-size: 11px; font-weight: bold; }}
                        .btn {{ background: #2563eb; color: #fff; border: none; padding: 10px; width: 100%; border-radius: 6px; font-weight: bold; cursor: pointer; margin-top: 10px; }}
                        @media print {{ .btn {{ display: none !important; }} .box {{ border: 2px solid #000; height: 98vh !important; }} }}
                    </style>
                </head>
                <body>
                    <div class="box">
                        <div>
                            <div class="header">
                                {logo_tag}
                                <div>
                                    <h2 style="margin:0; color:#0f172a;">INFO SOLUTIONS</h2>
                                    <div style="font-size:10px; font-weight:bold;">Computer, CCTV, Networking & Solar Services</div>
                                    <div style="font-size:10px; color:#2563eb; font-weight:bold;">Ph: +91 89219 91643, +91 97445 77543</div>
                                </div>
                            </div>
                            <div style="text-align:center;"><span class="badge">Service Acknowledgment Receipt</span></div>
                            <div class="grid">
                                <div class="col" style="border-right: 1px dashed #cbd5e1; padding-right: 15px;">
                                    <div class="row"><b>Job Card No:</b> <span>#00{selected_data[0]}</span></div>
                                    <div class="row"><b>Date:</b> <span>{selected_data[6]}</span></div>
                                    <div class="row"><b>Customer Name:</b> <span>{selected_data[1]}</span></div>
                                    <div class="row"><b>Phone:</b> <span>{selected_data[2]}</span></div>
                                </div>
                                <div class="col">
                                    <div class="row"><b>Category:</b> <span>{selected_data[3]}</span></div>
                                    <div class="row"><b>Model / Sl No:</b> <span>{selected_data[4]}</span></div>
                                    <div class="row"><b>Issue:</b> <span>{selected_data[5]}</span></div>
                                    <div class="row"><b>Status:</b> <span>{selected_data[7]}</span></div>
                                    <div class="row"><b>Service Charge:</b> <span>₹{selected_data[8]}</span></div>
                                </div>
                            </div>
                        </div>
                        <div>
                            <div class="terms">
                                <b>TERMS & CONDITIONS:</b>
                                <ul style="margin: 2px 0; padding-left: 15px;">
                                    <li>Items must be collected within 15 days of servive. INFOSOLUTIONS is not liable after this period.</li>
                                    <li>Backup data prior to service.We are not responsible for any data loss.</li>
                                    <li>No warranty on physical/liquid damages or power surges.</li>
                                    <li>Produce this original receipt for device collection.</li>
                                </ul>
                            </div>
                            <div class="sign"><span>Customer Signature</span><span>Authorized Signatory</span></div>
                        </div>
                        <button class="btn" onclick="window.print()">🖨️ PRINT RECEIPT</button>
                    </div>
                </body>
                </html>
                """
                components.html(html_receipt, height=500)
        else:
            st.info("No records found.")

    st.divider()
    st.subheader("📋 Master Service Database")
    st.dataframe(all_rows, use_container_width=True, hide_index=True)


# ----------------- 9. QUOTATION MANAGER PAGE -----------------
elif menu == "📄 Quotation Manager":
    st.subheader("📄 Sales & Service Quotation Manager")
    
    tab_new, tab_edit, tab_catalog = st.tabs(["➕ Create Quotation", "✏️ Edit / Delete / Reprint Quotations", "📦 Product Master Catalog"])

    master_prods = get_all_master_products()
    prod_dict = {p[0]: {"rate": p[1], "tax": p[2]} for p in master_prods}
    prod_options = ["-- Type / Select Existing Product --"] + list(prod_dict.keys())

    # --- TAB 1: CREATE NEW QUOTATION ---
    with tab_new:
        if "quote_items" not in st.session_state: st.session_state["quote_items"] = []

        q_col1, q_col2 = st.columns([1.1, 1.4], gap="large")

        with q_col1:
            st.markdown("#### 👤 Customer Details")
            q_cust_name = st.text_input("Customer / Company Name", placeholder="e.g. ABC Pvt Ltd / Rahul", key="nc_name")
            q_phone = st.text_input("Contact Number", placeholder="10-digit Mobile Number", key="nc_phone")
            
            q_type = st.selectbox("Quotation Category", [
                "Computer & Laptop Sales/Service", "CCTV Surveillance System", 
                "Networking & Wi-Fi Solutions", "Solar Power System Installation", "General Service Enquiry"
            ], key="nc_type")
            
            st.divider()
            st.markdown("#### 📦 Add Line Items (Auto-Suggest)")
            
            selected_master = st.selectbox("🔍 Search Saved Products List", prod_options, key="master_selector")
            
            default_name, default_rate, default_tax = "", 0.0, 18.0
            if selected_master != "-- Type / Select Existing Product --":
                default_name = selected_master
                default_rate = prod_dict[selected_master]["rate"]
                default_tax = prod_dict[selected_master]["tax"]

            with st.form("add_item_form", clear_on_submit=False):
                item_name = st.text_input("Item Description / Name *", value=default_name, placeholder="Type item name")
                c_qty, c_rate, c_tax = st.columns([1, 1, 1])
                with c_qty: qty = st.number_input("Qty", min_value=1, value=1)
                with c_rate: unit_price = st.number_input("Unit Price (₹)", min_value=0.0, step=100.0, value=default_rate)
                with c_tax: tax_pct = st.number_input("GST %", min_value=0.0, max_value=28.0, step=1.0, value=default_tax)
                    
                add_item_btn = st.form_submit_button("➕ Add Item & Save to Master", use_container_width=True)

                if add_item_btn:
                    if not item_name.strip():
                        st.error("Please enter item description!")
                    else:
                        save_or_update_product(item_name, unit_price, tax_pct)
                        item_total = qty * unit_price
                        tax_amt = item_total * (tax_pct / 100.0)
                        st.session_state["quote_items"].append({
                            "desc": item_name, "qty": qty, "rate": unit_price,
                            "tax_pct": tax_pct, "tax_amt": tax_amt, "total": item_total + tax_amt
                        })
                        st.toast("Item added and saved to Master Catalog!", icon="✅")
                        st.rerun()

            if st.session_state["quote_items"]:
                st.write("**Added Items:**")
                for idx, itm in enumerate(st.session_state["quote_items"]):
                    ic_a, ic_b = st.columns([4, 1])
                    with ic_a: st.text(f"{idx+1}. {itm['desc']} - Qty: {itm['qty']} - ₹{itm['total']:,.2f}")
                    with ic_b:
                        if st.button("❌", key=f"del_new_{idx}"):
                            st.session_state["quote_items"].pop(idx)
                            st.rerun()

                if st.button("🗑️ Clear All Items", type="secondary"):
                    st.session_state["quote_items"] = []
                    st.rerun()

        with q_col2:
            items = st.session_state["quote_items"]
            subtotal = sum(i["qty"] * i["rate"] for i in items)
            total_tax = sum(i["tax_amt"] for i in items)
            grand_total = subtotal + total_tax
            
            today_str = datetime.now().strftime("%d-%m-%Y")
            generated_no = f"INF-QT-{datetime.now().strftime('%d%m%H%M')}"

            if items:
                b_col1, b_col2 = st.columns(2)
                with b_col1:
                    if st.button("💾 SAVE QUOTATION TO DATABASE", type="primary", use_container_width=True):
                        if not q_cust_name.strip():
                            st.error("Please enter Customer Name before saving!")
                        else:
                            conn = get_db_connection()
                            cursor = conn.cursor()
                            cursor.execute("""
                                INSERT INTO quotations 
                                (quote_no, cust_name, phone, category, quote_date, items_json, subtotal, tax_total, grand_total)
                                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                                ON CONFLICT(quote_no) DO UPDATE SET
                                cust_name=EXCLUDED.cust_name, phone=EXCLUDED.phone, category=EXCLUDED.category,
                                quote_date=EXCLUDED.quote_date, items_json=EXCLUDED.items_json,
                                subtotal=EXCLUDED.subtotal, tax_total=EXCLUDED.tax_total, grand_total=EXCLUDED.grand_total;
                            """, (generated_no, q_cust_name, q_phone, q_type, today_str, json.dumps(items), subtotal, total_tax, grand_total))
                            conn.commit()
                            cursor.close()
                            conn.close()
                            st.success(f"Quotation {generated_no} saved to Supabase successfully!")
                            st.session_state["quote_items"] = []
                            st.rerun()

                with b_col2:
                    if q_phone.strip():
                        wa_q_phone = format_phone_for_whatsapp(q_phone)
                        full_wa_msg = create_whatsapp_text(generated_no, q_cust_name, q_type, items, subtotal, total_tax, grand_total)
                        st.link_button("💬 Share via WhatsApp", f"https://wa.me/{wa_q_phone}?text={urllib.parse.quote(full_wa_msg)}", use_container_width=True)

                st.write("### Live Print Preview")
                html_preview = generate_quotation_html(
                    generated_no, today_str, q_cust_name, q_phone, q_type, items, subtotal, total_tax, grand_total
                )
                components.html(html_preview, height=750, scrolling=True)
            else:
                st.info("Add line items on the left to generate the quotation preview.")

    # --- TAB 2: EDIT / DELETE / REPRINT QUOTATIONS ---
    with tab_edit:
        if not all_quotes:
            st.info("No saved quotations found in the database.")
        else:
            quote_dict = {f"{q[0]} | {q[1]} ({q[4]}) - ₹{q[8]:,.2f}": q for q in all_quotes}
            selected_quote_key = st.selectbox("Select Quotation to View / Edit:", list(quote_dict.keys()))
            selected_q = quote_dict[selected_quote_key]

            q_no, q_cust, q_ph, q_cat, q_dt, q_json, q_sub, q_tax, q_grand = selected_q
            q_items = json.loads(q_json)

            e_tab1, e_tab2 = st.tabs(["📄 View & Print / WhatsApp", "✏️ Edit Items & Details"])

            with e_tab1:
                col_actions1, col_actions2 = st.columns([1, 1])
                with col_actions1:
                    wa_phone = format_phone_for_whatsapp(q_ph)
                    wa_msg = create_whatsapp_text(q_no, q_cust, q_cat, q_items, q_sub, q_tax, q_grand)
                    st.link_button("💬 Resend via WhatsApp", f"https://wa.me/{wa_phone}?text={urllib.parse.quote(wa_msg)}", use_container_width=True)

                with col_actions2:
                    if st.button("🗑️ Delete Quotation", type="secondary", use_container_width=True):
                        conn = get_db_connection()
                        cursor = conn.cursor()
                        cursor.execute("DELETE FROM quotations WHERE quote_no = %s;", (q_no,))
                        conn.commit()
                        cursor.close()
                        conn.close()
                        st.toast("Quotation deleted successfully!")
                        st.rerun()

                q_html = generate_quotation_html(q_no, q_dt, q_cust, q_ph, q_cat, q_items, q_sub, q_tax, q_grand)
                components.html(q_html, height=750, scrolling=True)

            with e_tab2:
                st.markdown("#### Edit Quotation Details")
                with st.form(f"edit_q_form_{q_no}"):
                    eq_cust = st.text_input("Customer Name", value=q_cust)
                    eq_ph = st.text_input("Phone Number", value=q_ph)
                    eq_cat = st.selectbox("Category", [
                        "Computer & Laptop Sales/Service", "CCTV Surveillance System", 
                        "Networking & Wi-Fi Solutions", "Solar Power System Installation", "General Service Enquiry"
                    ], index=0 if q_cat not in ["CCTV Surveillance System", "Networking & Wi-Fi Solutions", "Solar Power System Installation", "General Service Enquiry"] else ["Computer & Laptop Sales/Service", "CCTV Surveillance System", "Networking & Wi-Fi Solutions", "Solar Power System Installation", "General Service Enquiry"].index(q_cat))

                    st.markdown("##### Line Items Editor")
                    df_items = pd.DataFrame(q_items)
                    edited_df = st.data_editor(
                        df_items,
                        num_rows="dynamic",
                        column_config={
                            "desc": st.column_config.TextColumn("Description", required=True),
                            "qty": st.column_config.NumberColumn("Qty", min_value=1, default=1),
                            "rate": st.column_config.NumberColumn("Rate (₹)", min_value=0.0, step=50.0),
                            "tax_pct": st.column_config.NumberColumn("GST %", min_value=0.0, max_value=28.0)
                        },
                        use_container_width=True
                    )

                    save_edits = st.form_submit_button("💾 Save Updated Quotation", type="primary", use_container_width=True)

                    if save_edits:
                        updated_items = []
                        new_subtotal = 0.0
                        new_tax_total = 0.0

                        for _, row in edited_df.iterrows():
                            desc = str(row["desc"]).strip()
                            if not desc: continue
                            qty = int(row["qty"])
                            rate = float(row["rate"])
                            tax_p = float(row["tax_pct"])

                            tot = qty * rate
                            t_amt = tot * (tax_p / 100.0)

                            new_subtotal += tot
                            new_tax_total += t_amt

                            updated_items.append({
                                "desc": desc, "qty": qty, "rate": rate,
                                "tax_pct": tax_p, "tax_amt": t_amt, "total": tot + t_amt
                            })

                        new_grand = new_subtotal + new_tax_total

                        conn = get_db_connection()
                        cursor = conn.cursor()
                        cursor.execute("""
                            UPDATE quotations 
                            SET cust_name=%s, phone=%s, category=%s, items_json=%s, subtotal=%s, tax_total=%s, grand_total=%s
                            WHERE quote_no=%s;
                        """, (eq_cust, eq_ph, eq_cat, json.dumps(updated_items), new_subtotal, new_tax_total, new_grand, q_no))
                        conn.commit()
                        cursor.close()
                        conn.close()

                        st.toast("Quotation updated successfully in Supabase!", icon="✅")
                        st.rerun()

    # --- TAB 3: PRODUCT MASTER CATALOG ---
    with tab_catalog:
        st.markdown("#### 📦 Master Product List & Pricing")
        st.caption("Items saved here will automatically appear in auto-suggest lists when creating quotations.")

        with st.form("master_catalog_form", clear_on_submit=True):
            mc1, mc2, mc3 = st.columns([2, 1, 1])
            with mc1: new_pname = st.text_input("Product Description / Name")
            with mc2: new_prate = st.number_input("Default Price (₹)", min_value=0.0, step=100.0)
            with mc3: new_ptax = st.number_input("Default GST %", min_value=0.0, max_value=28.0, value=18.0)

            add_master_btn = st.form_submit_button("➕ Save / Update Item in Catalog", type="primary")
            if add_master_btn:
                if new_pname.strip():
                    save_or_update_product(new_pname, new_prate, new_ptax)
                    st.toast("Product catalog updated!", icon="✅")
                    st.rerun()

        st.divider()
        master_rows = get_all_master_products()
        if master_rows:
            m_df = pd.DataFrame(master_rows, columns=["Product / Item Description", "Unit Price (₹)", "GST %"])
            st.dataframe(m_df, use_container_width=True, hide_index=True)


# ----------------- 10. ANALYTICS & REPORTS PAGE -----------------
elif menu == "📊 Analytics & Excel Reports":
    st.subheader("📊 Reports & Business Analytics")

    st.markdown("#### 📈 Service Operations Summary")
    r_col1, r_col2 = st.columns(2)

    with r_col1:
        if all_rows:
            df_services = pd.DataFrame(all_rows, columns=[
                "Job No", "Customer", "Phone", "Category", "Model", 
                "Issue", "Date Received", "Status", "Charge (₹)", "Date Delivered"
            ])
            st.markdown("##### Job Status Distribution")
            status_counts = df_services["Status"].value_counts()
            st.bar_chart(status_counts)

            output_services = io.BytesIO()
            with pd.ExcelWriter(output_services, engine='openpyxl') as writer:
                df_services.to_excel(writer, index=False, sheet_name='Service Jobs')
            
            st.download_button(
                label="📥 Export Service Jobs to Excel",
                data=output_services.getvalue(),
                file_name=f"Service_Jobs_Report_{datetime.now().strftime('%d_%m_%Y')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True
            )

    with r_col2:
        if all_quotes:
            df_quotes = pd.DataFrame([
                (q[0], q[1], q[2], q[3], q[4], q[6], q[7], q[8]) for q in all_quotes
            ], columns=["Quote Ref", "Customer", "Phone", "Category", "Date", "Subtotal", "GST Total", "Grand Total"])

            st.markdown("##### Quotation Revenue Summary")
            total_quoted_val = df_quotes["Grand Total"].sum()
            st.metric("Total Quoted Volume", f"₹{total_quoted_val:,.2f}")

            output_quotes = io.BytesIO()
            with pd.ExcelWriter(output_quotes, engine='openpyxl') as writer:
                df_quotes.to_excel(writer, index=False, sheet_name='Quotations')

            st.download_button(
                label="📥 Export Quotations to Excel",
                data=output_quotes.getvalue(),
                file_name=f"Quotations_Report_{datetime.now().strftime('%d_%m_%Y')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True
            )
