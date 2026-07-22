import os
import sqlite3
import base64
import json
import urllib.parse
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components
from datetime import datetime

# ----------------- 1. PAGE CONFIGURATION -----------------
st.set_page_config(
    page_title="INFO SOLUTIONS | Service & Quotation Portal",
    page_icon="🖥️",
    layout="wide",
    initial_sidebar_state="expanded"
)

DB_PATH = "service_center.db"
LOGO_PATH = "logo.png"
has_logo = os.path.exists(LOGO_PATH)

def get_base64_logo(path):
    if os.path.exists(path):
        with open(path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode()
    return ""

logo_base64 = get_base64_logo(LOGO_PATH)

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
    .stDataFrame { border-radius: 8px; overflow: hidden; }
    </style>
""", unsafe_allow_html=True)

# Terms & Conditions HTML Helper
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

# ----------------- 2. DATABASE INITIALIZATION & HELPERS -----------------
def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS services (
                job_no INTEGER PRIMARY KEY AUTOINCREMENT,
                cust_name TEXT, phone TEXT, item_type TEXT, item_desc TEXT,
                complaint TEXT, received_date TEXT, status TEXT, service_charge REAL, delivery_date TEXT,
                closing_remarks TEXT DEFAULT ''
            )
        """)

        try:
            cursor.execute("ALTER TABLE services ADD COLUMN closing_remarks TEXT DEFAULT ''")
        except sqlite3.OperationalError:
            pass
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS quotations (
                quote_no TEXT PRIMARY KEY, cust_name TEXT, phone TEXT, category TEXT,
                quote_date TEXT, items_json TEXT, subtotal REAL, tax_total REAL, grand_total REAL,
                status TEXT DEFAULT 'Open'
            )
        """)

        try:
            cursor.execute("ALTER TABLE quotations ADD COLUMN status TEXT DEFAULT 'Open'")
        except sqlite3.OperationalError:
            pass

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS master_products (
                id INTEGER PRIMARY KEY AUTOINCREMENT, item_name TEXT UNIQUE,
                unit_price REAL DEFAULT 0.0, tax_pct REAL DEFAULT 18.0
            )
        """)
        
        cursor.execute("SELECT COUNT(*) FROM master_products")
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
            cursor.executemany("INSERT OR IGNORE INTO master_products (item_name, unit_price, tax_pct) VALUES (?, ?, ?)", default_items)

init_db()

def save_or_update_product(item_name, price, tax):
    if not item_name.strip(): return
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO master_products (item_name, unit_price, tax_pct) VALUES (?, ?, ?)
            ON CONFLICT(item_name) DO UPDATE SET unit_price = excluded.unit_price, tax_pct = excluded.tax_pct
        """, (item_name.strip(), price, tax))

def delete_master_product(product_id):
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM master_products WHERE id = ?", (product_id,))

def get_all_master_products():
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, item_name, unit_price, tax_pct FROM master_products ORDER BY item_name ASC")
        return cursor.fetchall()

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
        f"🔖 *Ref No:* {q_no}\n"
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

# ----------------- 3. AUTHENTICATION & SESSION STATE -----------------
if "logged_in" not in st.session_state:
    st.session_state["logged_in"] = False

# --- STYLISH CENTERED LOGIN SCREEN ---
if not st.session_state["logged_in"]:
    st.markdown("""
        <style>
        [data-testid="stAppViewContainer"] {
            background: linear-gradient(135deg, #0f172a 0%, #1e293b 50%, #0f172a 100%);
        }
        
        [data-testid="stSidebar"] {
            display: none;
        }

        .login-card {
            background: rgba(255, 255, 255, 0.95);
            padding: 35px 30px;
            border-radius: 16px;
            box-shadow: 0 20px 40px rgba(0, 0, 0, 0.3);
            text-align: center;
            border: 1px solid rgba(255, 255, 255, 0.2);
            backdrop-filter: blur(10px);
            margin-top: 40px;
        }

        .login-title {
            color: #0f172a;
            font-size: 24px;
            font-weight: 800;
            letter-spacing: 1px;
            margin-top: 10px;
            margin-bottom: 2px;
        }

        .login-subtitle {
            color: #64748b;
            font-size: 13px;
            font-weight: 600;
            margin-bottom: 20px;
        }

        .stTextInput > div > div > input {
            border-radius: 8px !important;
            padding: 10px 14px !important;
            border: 1px solid #cbd5e1 !important;
        }

        .stButton > button {
            border-radius: 8px !important;
            padding: 10px 20px !important;
            font-weight: 700 !important;
            letter-spacing: 0.5px !important;
            box-shadow: 0 4px 12px rgba(37, 99, 235, 0.3) !important;
            transition: all 0.3s ease !important;
        }
        
        .stButton > button:hover {
            transform: translateY(-2px);
            box-shadow: 0 6px 18px rgba(37, 99, 235, 0.4) !important;
        }
        </style>
    """, unsafe_allow_html=True)

    _, main_col, _ = st.columns([1, 1.2, 1])

    with main_col:
        st.markdown('<div class="login-card">', unsafe_allow_html=True)
        
        if has_logo:
            st.image(LOGO_PATH, width=100)
            
        st.markdown('<div class="login-title">INFO SOLUTIONS</div>', unsafe_allow_html=True)
        st.markdown('<div class="login-subtitle">Service & Quotation Portal</div>', unsafe_allow_html=True)

        with st.form("login_form", clear_on_submit=False):
            username = st.text_input("👤 Username", placeholder="Enter your username")
            password = st.text_input("🔑 Password", type="password", placeholder="Enter your password")
            
            st.write("")
            login_btn = st.form_submit_button("LOG IN 🚀", use_container_width=True, type="primary")

            if login_btn:
                if username == "admin" and password == "admin123":
                    st.session_state["logged_in"] = True
                    st.toast("Welcome Back!", icon="🎉")
                    st.rerun()
                else:
                    st.error("❌ Invalid Username or Password")

        st.markdown('</div>', unsafe_allow_html=True)

    st.stop()

# ----------------- 4. MAIN APPLICATION (POST-LOGIN) -----------------
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

# Fetch Data
with sqlite3.connect(DB_PATH) as conn:
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM services ORDER BY job_no DESC")
    all_rows = cursor.fetchall()

    cursor.execute("SELECT * FROM quotations ORDER BY quote_date DESC")
    all_quotes = cursor.fetchall()

if has_logo: 
    st.sidebar.image(LOGO_PATH, use_container_width=True)

st.sidebar.title("🛠️ Main Menu")
menu = st.sidebar.radio("Go to", ["Dashboard & Operations", "📄 Quotation Manager", "📊 Analytics & Excel Reports"])

st.sidebar.write("---")
if st.sidebar.button("🔒 Logout", use_container_width=True):
    st.session_state["logged_in"] = False
    st.rerun()

# ----------------- 5. PAGE: DASHBOARD & OPERATIONS -----------------
if menu == "Dashboard & Operations":
    total_jobs = len(all_rows)
    pending_jobs = sum(1 for r in all_rows if r[7] == "Pending")
    completed_jobs = sum(1 for r in all_rows if r[7] == "Completed")
    closed_jobs = sum(1 for r in all_rows if r[7] in ["Delivered", "Closed / Delivered"])

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Total Job Cards", total_jobs)
    m2.metric("⏳ Pending", pending_jobs)
    m3.metric("✅ Completed", completed_jobs)
    m4.metric("🔒 Closed / Delivered", closed_jobs)

    st.write("")
    left_col, right_col = st.columns([1, 1.6], gap="large")

    with left_col:
        st.subheader("📝 New Service Entry")
        with st.form("entry_form", clear_on_submit=True):
            cust_name = st.text_input("Customer Name *", placeholder="Enter full name")
            phone = st.text_input("Phone Number *", placeholder="10-digit mobile number")
            
            c1, c2 = st.columns(2)
            with c1: item_type = st.selectbox("Item Category", ["Laptop", "Desktop", "CCTV", "DVR/NVR", "Networking", "Solar System", "Printer", "Other"])
            with c2: status = st.selectbox("Initial Status", ["Pending", "Completed", "Closed / Delivered"])

            item_desc = st.text_input("Model / Serial Number", placeholder="e.g. Dell Inspiron / 5KW Solar Inverter")
            complaint = st.text_area("Reported Issue / Work Description", height=90)
            service_charge = st.number_input("Estimated / Service Charge (₹)", min_value=0.0, step=50.0, value=0.0)
            
            submit_btn = st.form_submit_button("➕ Save Service Entry", use_container_width=True, type="primary")

            if submit_btn:
                if not cust_name.strip() or not phone.strip():
                    st.error("⚠️ Customer Name and Phone Number are required!")
                else:
                    today = datetime.now().strftime("%d-%m-%Y")
                    del_date = today if status == "Closed / Delivered" else "-"
                    with sqlite3.connect(DB_PATH) as conn:
                        cursor = conn.cursor()
                        cursor.execute("""
                            INSERT INTO services (cust_name, phone, item_type, item_desc, complaint, received_date, status, service_charge, delivery_date, closing_remarks)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, '')
                        """, (cust_name, phone, item_type, item_desc, complaint, today, status, service_charge, del_date))
                    st.toast("✅ New job card created!", icon="🎉")
                    st.rerun()

    with right_col:
        st.subheader("🔍 Manage Job Cards")
        sf1, sf2 = st.columns([2, 1])
        with sf1: search_query = st.text_input("Search", placeholder="Type Name, Phone or Job No...", label_visibility="collapsed")
        with sf2: status_filter = st.selectbox("Filter", ["All", "Pending", "Completed", "Closed / Delivered"], label_visibility="collapsed")

        filtered_rows = all_rows
        if status_filter != "All": 
            if status_filter == "Closed / Delivered":
                filtered_rows = [r for r in filtered_rows if r[7] in ["Delivered", "Closed / Delivered"]]
            else:
                filtered_rows = [r for r in filtered_rows if r[7] == status_filter]
        
        if search_query.strip():
            sq = search_query.lower()
            filtered_rows = [r for r in filtered_rows if sq in str(r[0]).lower() or sq in str(r[1]).lower() or sq in str(r[2]).lower()]

        if filtered_rows:
            job_options = {f"Job #00{r[0]} | {r[1]} ({r[3]}) - [{r[7]}]": r for r in filtered_rows}
            selected_label = st.selectbox("Select Record:", list(job_options.keys()))
            selected_data = job_options[selected_label]

            existing_remarks = selected_data[10] if len(selected_data) > 10 and selected_data[10] else ""

            tab_update, tab_receipt = st.tabs(["✏️ Update, Close & Manage", "📄 Print Receipt"])

            with tab_update:
                st.write("")
                u1, u2 = st.columns(2)
                with u1:
                    status_list = ["Pending", "Completed", "Closed / Delivered"]
                    curr_idx = status_list.index(selected_data[7]) if selected_data[7] in status_list else 0
                    new_status = st.selectbox("Update Status", status_list, index=curr_idx)
                    new_charge = st.number_input("Service Charge (₹)", min_value=0.0, step=50.0, value=float(selected_data[8]))
                with u2:
                    new_desc = st.text_input("Model / Serial No", value=selected_data[4])
                    new_complaint = st.text_area("Complaint Note", value=selected_data[5], height=68)

                ub1, ub2 = st.columns(2)
                with ub1:
                    if st.button("💾 Save Changes", use_container_width=True, type="primary"):
                        today = datetime.now().strftime("%d-%m-%Y")
                        del_date = today if new_status == "Closed / Delivered" else selected_data[9]
                        with sqlite3.connect(DB_PATH) as conn:
                            cursor = conn.cursor()
                            cursor.execute("""
                                UPDATE services SET status=?, service_charge=?, delivery_date=?, item_desc=?, complaint=? WHERE job_no=?
                            """, (new_status, new_charge, del_date, new_desc, new_complaint, selected_data[0]))
                        st.toast("Updated successfully!", icon="✅")
                        st.rerun()

                with ub2:
                    wa_phone = format_phone_for_whatsapp(selected_data[2])
                    wa_msg = f"Hello *{selected_data[1]}*,\n\nYour service job (*#00{selected_data[0]}*) status at *INFO SOLUTIONS* is now: *{new_status}*.\nCharge: ₹{new_charge}\n\nPh: +91 89219 91643"
                    st.link_button("💬 WhatsApp Status", f"https://wa.me/{wa_phone}?text={urllib.parse.quote(wa_msg)}", use_container_width=True)

                st.markdown("---")
                st.markdown("#### 🔒 Service Handover / Closing Section")
                
                closing_note = st.text_area(
                    "Closed Remarks / Reason for Closing", 
                    value=existing_remarks,
                    placeholder="e.g. Repaired and handed over / Reopened: Customer brought back device with same issue...",
                    height=80
                )

                if selected_data[7] != "Closed / Delivered":
                    if st.button("🔒 Close Job Ticket (Handed Over)", type="secondary", use_container_width=True):
                        today = datetime.now().strftime("%d-%m-%Y")
                        with sqlite3.connect(DB_PATH) as conn:
                            cursor = conn.cursor()
                            cursor.execute("""
                                UPDATE services SET status='Closed / Delivered', delivery_date=?, closing_remarks=? WHERE job_no=?
                            """, (today, closing_note, selected_data[0]))
                        st.toast("Service Job successfully Closed!", icon="🔒")
                        st.rerun()
                else:
                    st.success(f"🔒 Job Closed / Delivered Date: {selected_data[9]}")
                    
                    act_c1, act_c2 = st.columns(2)
                    with act_c1:
                        if st.button("💾 Update Closing Remarks Only", use_container_width=True):
                            with sqlite3.connect(DB_PATH) as conn:
                                cursor = conn.cursor()
                                cursor.execute("UPDATE services SET closing_remarks=? WHERE job_no=?", (closing_note, selected_data[0]))
                            st.toast("Closing remarks updated!", icon="📝")
                            st.rerun()
                    
                    with act_c2:
                        if st.button("🔄 Reopen Service Ticket", use_container_width=True, type="primary"):
                            reopen_remark = f"{closing_note} | [Reopened on {datetime.now().strftime('%d-%m-%Y')}]".strip(" | ")
                            with sqlite3.connect(DB_PATH) as conn:
                                cursor = conn.cursor()
                                cursor.execute("""
                                    UPDATE services SET status='Pending', delivery_date='-', closing_remarks=? WHERE job_no=?
                                """, (reopen_remark, selected_data[0]))
                            st.toast("Service Ticket Reopened!", icon="🔄")
                            st.rerun()

                st.markdown("---")
                with st.expander("⚠️ Danger Zone (Delete Ticket)"):
                    st.warning("⚠️ ടിക്കറ്റ് ഡിലീറ്റ് ചെയ്താൽ ഡാറ്റാബേസിൽ നിന്ന് ഇത് പൂർണ്ണമായി നീക്കം ചെയ്യപ്പെടും.")
                    if st.button("🗑️ Delete Service Ticket", type="primary", use_container_width=True):
                        with sqlite3.connect(DB_PATH) as conn:
                            cursor = conn.cursor()
                            cursor.execute("DELETE FROM services WHERE job_no=?", (selected_data[0],))
                        st.toast(f"Job Ticket #00{selected_data[0]} deleted successfully!", icon="🗑️")
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
                                    <li>Items must be collected within 15 days.</li>
                                    <li>Warranty as per manufacturer policies. Physical/liquid damages are not covered under warranty.</li>
                                    <li>Not responsible for data loss or physical/liquid damages during service.</li>
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
    
    s_cols = ["Job No", "Customer Name", "Phone", "Category", "Model/Serial", "Issue", "Received Date", "Status", "Charge (₹)", "Delivery Date", "Closing Remarks"]
    if all_rows and len(all_rows[0]) < 11:
        s_cols = s_cols[:len(all_rows[0])]

    df_services = pd.DataFrame(all_rows, columns=s_cols)
    st.dataframe(df_services, use_container_width=True, hide_index=True)

# ----------------- 6. PAGE: QUOTATION MANAGER -----------------
elif menu == "📄 Quotation Manager":
    st.subheader("📄 Sales & Service Quotation Manager")
    
    tab_new, tab_edit, tab_catalog = st.tabs(["➕ Create Quotation", "✏️ Manage / Edit / Close Quotations", "📦 Product Master Catalog"])

    master_prods = get_all_master_products()
    prod_dict = {p[1]: {"rate": p[2], "tax": p[3]} for p in master_prods}
    prod_options = ["-- Type / Select Existing Product --"] + list(prod_dict.keys())

    # --- TAB 1: CREATE NEW QUOTATION ---
    with tab_new:
        if "quote_items" not in st.session_state: 
            st.session_state["quote_items"] = []

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
                            with sqlite3.connect(DB_PATH) as conn:
                                cursor = conn.cursor()
                                cursor.execute("""
                                    INSERT OR REPLACE INTO quotations 
                                    (quote_no, cust_name, phone, category, quote_date, items_json, subtotal, tax_total, grand_total, status)
                                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'Open')
                                """, (generated_no, q_cust_name, q_phone, q_type, today_str, json.dumps(items), subtotal, total_tax, grand_total))
                            st.success(f"Quotation {generated_no} saved successfully!")
                            st.session_state["quote_items"] = []
                            st.rerun()

                with b_col2:
                    if q_phone.strip():
                        wa_q_phone = format_phone_for_whatsapp(q_phone)
                        full_wa_msg = create_whatsapp_text(generated_no, q_cust_name, q_type, items, subtotal, total_tax, grand_total)
                        st.link_button("💬 Send via WhatsApp", f"https://wa.me/{wa_q_phone}?text={urllib.parse.quote(full_wa_msg)}", use_container_width=True)

                html_preview = generate_quotation_html(generated_no, today_str, q_cust_name, q_phone, q_type, items, subtotal, total_tax, grand_total)
                components.html(html_preview, height=750, scrolling=True)
            else:
                st.info("👈 Add items from the left side panel to generate the quotation preview.")

    # --- TAB 2: MANAGE / EDIT / CLOSE QUOTATIONS ---
    with tab_edit:
        st.markdown("#### 📜 Existing Quotations Manager")
        if all_quotes:
            q_dict = {}
            for q in all_quotes:
                status_str = f"[{q[9]}]" if len(q) > 9 and q[9] else "[Open]"
                q_dict[f"{q[0]} | {q[1]} ({q[4]}) - ₹{q[8]:,.2f} - {status_str}"] = q

            sel_q_label = st.selectbox("Select Quotation to View / Edit:", list(q_dict.keys()))
            sel_q = q_dict[sel_q_label]

            if "current_edit_qno" not in st.session_state or st.session_state["current_edit_qno"] != sel_q[0]:
                st.session_state["current_edit_qno"] = sel_q[0]
                st.session_state["edit_quote_items"] = json.loads(sel_q[5])
                st.session_state["edit_cust_name"] = sel_q[1]
                st.session_state["edit_phone"] = sel_q[2]
                st.session_state["edit_category"] = sel_q[3]
                st.session_state["editing_item_idx"] = None

            q_no = sel_q[0]
            q_dt = sel_q[4]
            q_status = sel_q[9] if len(sel_q) > 9 and sel_q[9] else "Open"

            eq_col1, eq_col2 = st.columns([1.2, 1.4], gap="large")

            with eq_col1:
                st.markdown(f"##### ✏️ Edit Quotation Details ({q_no})")
                
                edit_cust_name = st.text_input("Customer / Company Name", value=st.session_state["edit_cust_name"])
                edit_phone = st.text_input("Contact Number", value=st.session_state["edit_phone"])
                
                cat_options = [
                    "Computer & Laptop Sales/Service", "CCTV Surveillance System", 
                    "Networking & Wi-Fi Solutions", "Solar Power System Installation", "General Service Enquiry"
                ]
                curr_cat_idx = cat_options.index(st.session_state["edit_category"]) if st.session_state["edit_category"] in cat_options else 0
                edit_category = st.selectbox("Quotation Category", cat_options, index=curr_cat_idx)

                st.divider()
                
                # --- ITEM EDITING IN-LINE DIALOG / FORM ---
                if st.session_state.get("editing_item_idx") is not None:
                    edit_idx = st.session_state["editing_item_idx"]
                    curr_item = st.session_state["edit_quote_items"][edit_idx]
                    
                    st.markdown(f"##### 🛠️ Edit Item #{edit_idx+1}")
                    with st.form("inline_edit_item_form"):
                        mod_desc = st.text_input("Item Description", value=curr_item["desc"])
                        mq1, mq2, mq3 = st.columns(3)
                        with mq1: mod_qty = st.number_input("Qty", min_value=1, value=int(curr_item["qty"]))
                        with mq2: mod_rate = st.number_input("Unit Price (₹)", min_value=0.0, step=100.0, value=float(curr_item["rate"]))
                        with mq3: mod_tax = st.number_input("GST %", min_value=0.0, max_value=28.0, value=float(curr_item["tax_pct"]))

                        btn_save_item, btn_cancel_item = st.columns(2)
                        with btn_save_item:
                            if st.form_submit_button("✅ Update Item", use_container_width=True, type="primary"):
                                mod_tot = mod_qty * mod_rate
                                mod_tax_amt = mod_tot * (mod_tax / 100.0)
                                st.session_state["edit_quote_items"][edit_idx] = {
                                    "desc": mod_desc, "qty": mod_qty, "rate": mod_rate,
                                    "tax_pct": mod_tax, "tax_amt": mod_tax_amt, "total": mod_tot + mod_tax_amt
                                }
                                st.session_state["editing_item_idx"] = None
                                st.toast("Item updated!", icon="✏️")
                                st.rerun()
                        with btn_cancel_item:
                            if st.form_submit_button("❌ Cancel", use_container_width=True):
                                st.session_state["editing_item_idx"] = None
                                st.rerun()
                else:
                    st.markdown("##### ➕ Add More Items to Quotation")
                    sel_master_edit = st.selectbox("🔍 Search Saved Products List", prod_options, key="edit_master_selector")
                    
                    e_default_name, e_default_rate, e_default_tax = "", 0.0, 18.0
                    if sel_master_edit != "-- Type / Select Existing Product --":
                        e_default_name = sel_master_edit
                        e_default_rate = prod_dict[sel_master_edit]["rate"]
                        e_default_tax = prod_dict[sel_master_edit]["tax"]

                    with st.form("edit_add_item_form", clear_on_submit=False):
                        e_item_name = st.text_input("Item Description / Name *", value=e_default_name)
                        eq_qty, eq_rate, eq_tax = st.columns([1, 1, 1])
                        with eq_qty: e_qty = st.number_input("Qty", min_value=1, value=1, key="eq_qty")
                        with eq_rate: e_price = st.number_input("Unit Price (₹)", min_value=0.0, step=100.0, value=e_default_rate, key="eq_rate")
                        with eq_tax: e_tax = st.number_input("GST %", min_value=0.0, max_value=28.0, step=1.0, value=e_default_tax, key="eq_tax")
                        
                        e_add_btn = st.form_submit_button("➕ Add Item to List", use_container_width=True)

                        if e_add_btn:
                            if not e_item_name.strip():
                                st.error("Please enter item description!")
                            else:
                                save_or_update_product(e_item_name, e_price, e_tax)
                                e_item_total = e_qty * e_price
                                e_tax_amt = e_item_total * (e_tax / 100.0)
                                st.session_state["edit_quote_items"].append({
                                    "desc": e_item_name, "qty": e_qty, "rate": e_price,
                                    "tax_pct": e_tax, "tax_amt": e_tax_amt, "total": e_item_total + e_tax_amt
                                })
                                st.toast("Item added!", icon="✅")
                                st.rerun()

                st.markdown("##### 📋 Current Items List")
                if st.session_state["edit_quote_items"]:
                    for idx, itm in enumerate(st.session_state["edit_quote_items"]):
                        e_ca, e_cb, e_cc = st.columns([3.5, 1, 1])
                        with e_ca: st.text(f"{idx+1}. {itm['desc']} (x{itm['qty']}) - ₹{itm['total']:,.2f}")
                        with e_cb:
                            if st.button("✏️", key=f"edit_btn_{idx}"):
                                st.session_state["editing_item_idx"] = idx
                                st.rerun()
                        with e_cc:
                            if st.button("❌", key=f"del_edit_{idx}"):
                                st.session_state["edit_quote_items"].pop(idx)
                                if st.session_state.get("editing_item_idx") == idx:
                                    st.session_state["editing_item_idx"] = None
                                st.rerun()

                e_subtotal = sum(i["qty"] * i["rate"] for i in st.session_state["edit_quote_items"])
                e_totaltax = sum(i["tax_amt"] for i in st.session_state["edit_quote_items"])
                e_grandtotal = e_subtotal + e_totaltax

                st.markdown("---")
                if st.button("💾 SAVE ALL CHANGES TO QUOTATION", type="primary", use_container_width=True):
                    with sqlite3.connect(DB_PATH) as conn:
                        cursor = conn.cursor()
                        cursor.execute("""
                            UPDATE quotations 
                            SET cust_name=?, phone=?, category=?, items_json=?, subtotal=?, tax_total=?, grand_total=?
                            WHERE quote_no=?
                        """, (edit_cust_name, edit_phone, edit_category, json.dumps(st.session_state["edit_quote_items"]), e_subtotal, e_totaltax, e_grandtotal, q_no))
                    st.success("Quotation updated successfully!")
                    st.rerun()

                act_col1, act_col2 = st.columns(2)
                with act_col1:
                    if q_status != "Closed":
                        if st.button("🔒 Close Quotation", use_container_width=True):
                            with sqlite3.connect(DB_PATH) as conn:
                                cursor = conn.cursor()
                                cursor.execute("UPDATE quotations SET status = 'Closed' WHERE quote_no = ?", (q_no,))
                            st.toast("Quotation Closed!", icon="🔒")
                            st.rerun()
                    else:
                        st.success("🔒 Quotation is Closed")

                with act_col2:
                    if edit_phone:
                        wa_edit_phone = format_phone_for_whatsapp(edit_phone)
                        edit_wa_msg = create_whatsapp_text(q_no, edit_cust_name, edit_category, st.session_state["edit_quote_items"], e_subtotal, e_totaltax, e_grandtotal)
                        st.link_button("💬 Send via WhatsApp", f"https://wa.me/{wa_edit_phone}?text={urllib.parse.quote(edit_wa_msg)}", use_container_width=True)

                if st.button("🗑️ Delete Quotation", type="secondary", use_container_width=True):
                    with sqlite3.connect(DB_PATH) as conn:
                        cursor = conn.cursor()
                        cursor.execute("DELETE FROM quotations WHERE quote_no = ?", (q_no,))
                    st.toast("Quotation deleted successfully!", icon="🗑️")
                    st.rerun()

            with eq_col2:
                reprint_html = generate_quotation_html(q_no, q_dt, edit_cust_name, edit_phone, edit_category, st.session_state["edit_quote_items"], e_subtotal, e_totaltax, e_grandtotal)
                components.html(reprint_html, height=750, scrolling=True)
        else:
            st.info("No saved quotations found.")

    # --- TAB 3: PRODUCT MASTER CATALOG MANAGER ---
    with tab_catalog:
        st.markdown("#### 📦 Master Products Catalog Management")
        p_col1, p_col2 = st.columns([1, 1.5], gap="large")

        with p_col1:
            st.markdown("##### Add / Update Catalog Product")
            with st.form("master_prod_form", clear_on_submit=True):
                mp_name = st.text_input("Product Name / Description *")
                mp_price = st.number_input("Unit Price (₹)", min_value=0.0, step=100.0)
                mp_tax = st.number_input("GST Rate (%)", min_value=0.0, max_value=28.0, value=18.0)
                
                mp_submit = st.form_submit_button("💾 Save Product to Catalog", use_container_width=True, type="primary")

                if mp_submit:
                    if not mp_name.strip():
                        st.error("Product name cannot be empty.")
                    else:
                        save_or_update_product(mp_name, mp_price, mp_tax)
                        st.toast("Product saved to catalog!", icon="✅")
                        st.rerun()

        with p_col2:
            st.markdown("##### Current Products in Catalog")
            prods = get_all_master_products()
            if prods:
                df_prods = pd.DataFrame(prods, columns=["ID", "Product Name", "Unit Price (₹)", "Tax %"])
                st.dataframe(df_prods, use_container_width=True, hide_index=True)

                prod_to_del = st.selectbox("Select Product ID to Delete:", [f"{p[0]} - {p[1]}" for p in prods])
                if st.button("❌ Remove Selected Product", type="secondary"):
                    del_id = int(prod_to_del.split(" - ")[0])
                    delete_master_product(del_id)
                    st.toast("Product removed from catalog!", icon="🗑️")
                    st.rerun()
            else:
                st.info("Catalog is currently empty.")

# ----------------- 7. PAGE: ANALYTICS & EXCEL REPORTS -----------------
elif menu == "📊 Analytics & Excel Reports":
    st.subheader("📊 Analytics & Data Export")

    a_col1, a_col2 = st.columns(2)

    with a_col1:
        st.markdown("### 🛠️ Service Jobs Summary")
        if all_rows:
            cols_s = ["Job No", "Customer", "Phone", "Category", "Model", "Complaint", "Date", "Status", "Charge", "Delivery Date", "Closing Remarks"]
            if len(all_rows[0]) < 11:
                cols_s = cols_s[:len(all_rows[0])]
                
            df_s = pd.DataFrame(all_rows, columns=cols_s)
            st.dataframe(df_s, use_container_width=True, hide_index=True)
            
            csv_s = df_s.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="📥 Download Service Records (CSV)",
                data=csv_s,
                file_name=f"Service_Records_{datetime.now().strftime('%Y%m%d')}.csv",
                mime='text/csv',
                use_container_width=True
            )
        else:
            st.info("No service records found.")

    with a_col2:
        st.markdown("### 📄 Quotations Summary")
        if all_quotes:
            cols_q = ["Quote Ref", "Customer", "Phone", "Category", "Date", "Items JSON", "Subtotal", "Tax Total", "Grand Total", "Status"]
            if len(all_quotes[0]) < 10:
                cols_q = cols_q[:len(all_quotes[0])]
            
            df_q = pd.DataFrame(all_quotes, columns=cols_q)
            st.dataframe(df_q.drop(columns=["Items JSON"] if "Items JSON" in df_q.columns else []), use_container_width=True, hide_index=True)
            
            csv_q = df_q.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="📥 Download Quotation Records (CSV)",
                data=csv_q,
                file_name=f"Quotation_Records_{datetime.now().strftime('%Y%m%d')}.csv",
                mime='text/csv',
                use_container_width=True
            )
        else:
            st.info("No quotation records found.")
