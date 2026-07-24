import streamlit as st
import psycopg2
import psycopg2.extras
import pandas as pd
from datetime import datetime
import json
import urllib.parse
import os
import base64
import hashlib
import secrets

# Page Configuration
st.set_page_config(
    page_title="Info Solutions - Service & Quotation Manager",
    page_icon="🛠️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ---------------------------------------------------------
# BRAND COLOR PALETTE (Navy Blue & Professional Red)
# ---------------------------------------------------------
COLOR_BLUE = "#002B49"  # Navy Blue for SOLUTIONS & main elements
COLOR_RED = "#D32F2F"   # Rich Red for INFO & highlights
BG_COLOR = "#F4F6F9"    # Light clean background
TEXT_MAIN = "#1A1A1A"   # Crisp black/dark text for content

# Custom CSS for App Aesthetics
st.markdown(f"""<style>
.main {{ background-color: {BG_COLOR}; }}
.stMetric {{
    background-color: #ffffff;
    padding: 15px;
    border-radius: 10px;
    box-shadow: 0 4px 6px rgba(0,0,0,0.05);
    border-left: 5px solid {COLOR_RED};
}}
.login-box {{
    background: #ffffff;
    padding: 35px 30px;
    border-radius: 15px;
    color: {TEXT_MAIN};
    box-shadow: 0 10px 25px rgba(0,0,0,0.1);
    border-top: 5px solid {COLOR_RED};
    border-bottom: 5px solid {COLOR_BLUE};
    text-align: center;
    margin-top: 20px;
}}
.logo-container {{
    background: #ffffff;
    padding: 10px 16px;
    border-radius: 14px;
    display: inline-block;
    box-shadow: 0 4px 14px rgba(0,43,73,0.12);
    border: 1px solid rgba(0,43,73,0.10);
    margin-bottom: 12px;
}}
.sidebar-brand {{
    background: linear-gradient(145deg, #f7fbff 0%, #e8f1f7 100%);
    border-radius: 14px;
    padding: 14px 12px 12px;
    margin: -4px 0 12px;
    color: {COLOR_BLUE};
    box-shadow: 0 5px 14px rgba(0,43,73,0.20);
}}
.sidebar-brand-title {{ font-size: 1.05rem; font-weight: 800; letter-spacing: .4px; margin-top: 8px; }}
.sidebar-brand-tagline {{ color: #526b7b; font-size: .72rem; line-height: 1.35; margin-top: 3px; }}
.profile-card {{
    border: 1px solid #dce6ee;
    border-left: 4px solid {COLOR_RED};
    border-radius: 10px;
    padding: 9px 10px;
    background: #ffffff;
    font-size: .82rem;
    color: #29465a;
}}
.nav-section {{ color: #557080; font-size: .72rem; font-weight: 800; letter-spacing: .08em; margin: 13px 0 2px; }}
[data-testid="stAppViewContainer"] {{ overflow-y: auto; }}
[data-testid="stMainBlockContainer"] {{ padding-top: 1rem; padding-bottom: 3rem; }}
[data-testid="stSidebarContent"] {{ overflow-y: auto; }}
</style>""", unsafe_allow_html=True)

# ---------------------------------------------------------
# COMPANY DETAILS & BRANDED LOGO HTML
# ---------------------------------------------------------
COMPANY_NAME = "INFO SOLUTIONS"
COMPANY_TAGLINE = "Sales & Services of Laptops, Computers, CCTV & Solar Power Systems"
COMPANY_PHONE = "+91 8921991643 / +91 9744577543"
COMPANY_EMAIL = "infosolutionstvm@gmail.com"
COMPANY_ADDRESS = "TC 52/501(1) | Opposite BSNL | Kaimanam | Trivandrum | Kerala - 695018"

# Check for logo file and convert to Base64
LOGO_PATH = None
LOGO_BASE64 = ""
for fname in ["logo.png", "logo.jpg", "logo.jpeg", "Logo.png", "Logo.jpg"]:
    if os.path.exists(fname):
        LOGO_PATH = fname
        with open(fname, "rb") as image_file:
            LOGO_BASE64 = base64.b64encode(image_file.read()).decode('utf-8')
        break

# Dual-color HTML Title Header
BRAND_HEADER_HTML = f'<span style="color:{COLOR_RED}; font-weight:800;">INFO</span> <span style="color:{COLOR_BLUE}; font-weight:800;">SOLUTIONS</span>'

# ---------------------------------------------------------
# DATABASE CONNECTION & INIT
# ---------------------------------------------------------
def hash_password(password, salt=None):
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 100000).hex()
    return f"{salt}${digest}"

def verify_password(password, stored_hash):
    try:
        salt, saved_digest = stored_hash.split("$", 1)
        return secrets.compare_digest(hash_password(password, salt).split("$", 1)[1], saved_digest)
    except (ValueError, AttributeError):
        return False

def get_db_connection():
    if "postgres" not in st.secrets:
        st.error("⚠️ Supabase Credentials missing! Please check secrets.toml file.")
        st.stop()
        
    try:
        db_config = st.secrets["postgres"]
        conn = psycopg2.connect(
            host=db_config["host"],
            database=db_config["database"],
            user=db_config["user"],
            password=db_config["password"],
            port=db_config["port"],
            client_encoding='utf8',
            cursor_factory=psycopg2.extras.DictCursor
        )
        return conn
    except Exception as e:
        st.error(f"❌ Database Connection Error: {e}")
        st.stop()

@st.cache_resource
def init_db():
    conn = get_db_connection()
    cur = conn.cursor()
    
    cur.execute('''
        CREATE TABLE IF NOT EXISTS service_entries (
            id SERIAL PRIMARY KEY,
            receipt_no TEXT UNIQUE NOT NULL,
            customer_name TEXT NOT NULL,
            phone TEXT NOT NULL,
            item_description TEXT NOT NULL,
            serial_no TEXT,
            issue TEXT,
            status TEXT DEFAULT 'Pending',
            delivery_remarks TEXT DEFAULT '',
            closing_remarks TEXT DEFAULT '',
            closed_date TIMESTAMP,
            estimated_cost NUMERIC DEFAULT 0.0,
            advance_paid NUMERIC DEFAULT 0.0,
            entry_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    ''')
    
    cur.execute('''
        CREATE TABLE IF NOT EXISTS quotations (
            quote_no TEXT PRIMARY KEY,
            customer_name TEXT NOT NULL,
            phone TEXT NOT NULL,
            customer_place TEXT DEFAULT '',
            category TEXT DEFAULT 'WiFi & Networking Solutions',
            status TEXT DEFAULT 'Pending',
            items_json TEXT NOT NULL,
            subtotal NUMERIC DEFAULT 0.0,
            gst_amount NUMERIC DEFAULT 0.0,
            total_amount NUMERIC DEFAULT 0.0,
            quote_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    ''')

    try:
        cur.execute("ALTER TABLE quotations ADD COLUMN IF NOT EXISTS status TEXT DEFAULT 'Pending';")
        cur.execute("ALTER TABLE quotations ADD COLUMN IF NOT EXISTS category TEXT DEFAULT 'WiFi & Networking Solutions';")
        cur.execute("ALTER TABLE quotations ADD COLUMN IF NOT EXISTS customer_place TEXT DEFAULT '';")
        cur.execute("ALTER TABLE quotations ADD COLUMN IF NOT EXISTS subtotal NUMERIC DEFAULT 0.0;")
        cur.execute("ALTER TABLE quotations ADD COLUMN IF NOT EXISTS gst_amount NUMERIC DEFAULT 0.0;")
        conn.commit()
    except Exception:
        conn.rollback()

    cur.execute('''
        CREATE TABLE IF NOT EXISTS products (
            id SERIAL PRIMARY KEY,
            product_name TEXT UNIQUE NOT NULL,
            category TEXT,
            price NUMERIC DEFAULT 0.0,
            stock_qty INT DEFAULT 0
        );
    ''')

    cur.execute('''
        CREATE TABLE IF NOT EXISTS customers (
            id SERIAL PRIMARY KEY,
            customer_name TEXT NOT NULL,
            phone TEXT UNIQUE NOT NULL,
            email TEXT DEFAULT '',
            address TEXT DEFAULT '',
            gstin TEXT DEFAULT '',
            notes TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    ''')
    cur.execute('''
        CREATE TABLE IF NOT EXISTS staff_users (
            id SERIAL PRIMARY KEY,
            username TEXT UNIQUE NOT NULL,
            full_name TEXT NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'Technician',
            is_active BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    ''')
    cur.execute('''
        CREATE TABLE IF NOT EXISTS payments (
            id SERIAL PRIMARY KEY,
            reference_type TEXT NOT NULL,
            reference_no TEXT NOT NULL,
            customer_name TEXT NOT NULL,
            phone TEXT DEFAULT '',
            amount NUMERIC NOT NULL,
            payment_mode TEXT DEFAULT 'Cash',
            payment_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            remarks TEXT DEFAULT '',
            received_by TEXT DEFAULT ''
        );
    ''')
    cur.execute('''
        CREATE TABLE IF NOT EXISTS projects (
            id SERIAL PRIMARY KEY,
            project_no TEXT UNIQUE NOT NULL,
            project_type TEXT NOT NULL,
            customer_name TEXT NOT NULL,
            phone TEXT NOT NULL,
            site_address TEXT DEFAULT '',
            status TEXT DEFAULT 'Site Survey',
            assigned_to TEXT DEFAULT '',
            project_value NUMERIC DEFAULT 0,
            advance_paid NUMERIC DEFAULT 0,
            installation_date DATE,
            warranty_end DATE,
            scope_details TEXT DEFAULT '',
            materials_notes TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    ''')

    cur.execute("ALTER TABLE service_entries ADD COLUMN IF NOT EXISTS assigned_to TEXT DEFAULT '';")
    cur.execute("ALTER TABLE service_entries ADD COLUMN IF NOT EXISTS priority TEXT DEFAULT 'Normal';")
    cur.execute("ALTER TABLE service_entries ADD COLUMN IF NOT EXISTS expected_delivery DATE;")
    cur.execute("ALTER TABLE service_entries ADD COLUMN IF NOT EXISTS labor_charge NUMERIC DEFAULT 0;")
    cur.execute("ALTER TABLE service_entries ADD COLUMN IF NOT EXISTS parts_charge NUMERIC DEFAULT 0;")
    cur.execute("ALTER TABLE quotations ADD COLUMN IF NOT EXISTS paid_amount NUMERIC DEFAULT 0;")

    cur.execute("SELECT id FROM staff_users WHERE username = %s;", ("admin",))
    if not cur.fetchone():
        cur.execute('''INSERT INTO staff_users (username, full_name, password_hash, role)
                       VALUES (%s, %s, %s, %s);''',
                    ("admin", "Administrator", hash_password("password123"), "Admin"))
    
    conn.commit()
    cur.close()
    conn.close()

init_db()

# ---------------------------------------------------------
# HELPER FUNCTIONS
# ---------------------------------------------------------
def create_whatsapp_link(phone_number, message):
    clean_phone = "".join(filter(str.isdigit, str(phone_number)))
    if len(clean_phone) == 10:
        clean_phone = "91" + clean_phone
    encoded_msg = urllib.parse.quote(message)
    return f"https://wa.me/{clean_phone}?text={encoded_msg}"

def generate_receipt_no():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM service_entries;")
    count = cur.fetchone()[0]
    cur.close()
    conn.close()
    return f"INF-{1001 + count}"

def generate_quote_no():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM quotations;")
    count = cur.fetchone()[0]
    cur.close()
    conn.close()
    return f"INF-QT-{1001 + count}"

def get_products_list():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT product_name, price FROM products ORDER BY product_name ASC;")
    prods = cur.fetchall()
    cur.close()
    conn.close()
    return prods

def auto_save_product_to_catalog(p_name, p_price):
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute('''
            INSERT INTO products (product_name, category, price, stock_qty)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (product_name) DO UPDATE 
            SET price = EXCLUDED.price;
        ''', (p_name, "General", float(p_price), 1))
        conn.commit()
        cur.close()
        conn.close()
    except Exception:
        pass

def save_customer(customer_name, phone, email="", address="", gstin="", notes=""):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute('''
        INSERT INTO customers (customer_name, phone, email, address, gstin, notes, updated_at)
        VALUES (%s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
        ON CONFLICT (phone) DO UPDATE SET
            customer_name = EXCLUDED.customer_name,
            email = CASE WHEN EXCLUDED.email <> '' THEN EXCLUDED.email ELSE customers.email END,
            address = CASE WHEN EXCLUDED.address <> '' THEN EXCLUDED.address ELSE customers.address END,
            gstin = CASE WHEN EXCLUDED.gstin <> '' THEN EXCLUDED.gstin ELSE customers.gstin END,
            notes = CASE WHEN EXCLUDED.notes <> '' THEN EXCLUDED.notes ELSE customers.notes END,
            updated_at = CURRENT_TIMESTAMP;
    ''', (customer_name, phone, email, address, gstin, notes))
    conn.commit()
    cur.close()
    conn.close()

def get_customer_profiles():
    """Return customer records for CRM-linked forms."""
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""SELECT id, customer_name, phone, COALESCE(email, ''), COALESCE(address, ''),
                         COALESCE(gstin, ''), COALESCE(notes, '')
                  FROM customers ORDER BY customer_name, phone;""")
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return [dict(row) for row in rows]

def update_customer(customer_id, customer_name, phone, email="", address="", gstin="", notes=""):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT phone FROM customers WHERE id = %s;", (customer_id,))
    existing_customer = cur.fetchone()
    previous_phone = existing_customer[0] if existing_customer else phone
    cur.execute('''UPDATE customers
                   SET customer_name = %s, phone = %s, email = %s, address = %s,
                       gstin = %s, notes = %s, updated_at = CURRENT_TIMESTAMP
                   WHERE id = %s;''',
                (customer_name, phone, email, address, gstin, notes, customer_id))
    # Keep historical service, quotation, project and payment records connected
    # when a CRM name or phone number is corrected.
    for table in ("service_entries", "quotations", "projects", "payments"):
        cur.execute(f"UPDATE {table} SET customer_name = %s, phone = %s WHERE phone = %s;",
                    (customer_name, phone, previous_phone))
    conn.commit()
    cur.close()
    conn.close()

def get_active_staff():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT full_name FROM staff_users WHERE is_active = TRUE ORDER BY full_name;")
    rows = [row[0] for row in cur.fetchall()]
    cur.close()
    conn.close()
    return rows

def generate_project_no():
    return f"INF-PRJ-{datetime.now().strftime('%y%m%d%H%M%S')}"

CATEGORY_OPTIONS = [
    "WiFi & Networking Solutions",
    "CCTV Installation & Service",
    "Desktop Integration & Service",
    "Laptop & Computer Services",
    "Solar Power Systems",
    "General Sales & Service"
]

QUOTATION_STATUS_LIST = ["Pending", "Accepted", "Completed", "Cancelled"]

# ---------------------------------------------------------
# LOGIN SYSTEM (FIXED HTML RENDER)
# ---------------------------------------------------------
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

def login_page():
    col1, col2, col3 = st.columns([1, 2.2, 1])
    with col2:
        with st.container(border=True):
            if LOGO_PATH:
                logo_left, logo_center, logo_right = st.columns([1, 2, 1])
                with logo_center:
                    st.image(LOGO_PATH, use_container_width=True)
            st.markdown(f'<h2 style="text-align:center; margin-bottom:0;">{BRAND_HEADER_HTML}</h2>', unsafe_allow_html=True)
            st.markdown(f'<p style="text-align:center; color:#526b7b; font-size:.82rem;">{COMPANY_TAGLINE}</p>', unsafe_allow_html=True)
            st.markdown('<h4 style="text-align:center;">🔐 Staff Login Portal</h4>', unsafe_allow_html=True)
        
        with st.form("login_form"):
            username = st.text_input("Username", key="login_user")
            password = st.text_input("Password", type="password", key="login_pass")
            submit_login = st.form_submit_button("Login to Workspace 🚀", use_container_width=True, type="primary")
            
            if submit_login:
                conn = get_db_connection()
                cur = conn.cursor()
                cur.execute("SELECT full_name, password_hash, role FROM staff_users WHERE username = %s AND is_active = TRUE;", (username.strip(),))
                staff = cur.fetchone()
                cur.close()
                conn.close()
                if staff and verify_password(password, staff[1]):
                    st.session_state.authenticated = True
                    st.session_state.staff_name = staff[0]
                    st.session_state.staff_role = staff[2]
                    st.success("Logged in successfully!")
                    st.rerun()
                else:
                    st.error("Invalid Username or Password!")

if not st.session_state.authenticated:
    login_page()
    st.stop()

# ---------------------------------------------------------
# SIDEBAR NAVIGATION
# ---------------------------------------------------------
if LOGO_PATH:
    with st.sidebar.container(border=True):
        st.image(LOGO_PATH, use_container_width=True)

st.sidebar.markdown(f"""
<div class="sidebar-brand">
    <div class="sidebar-brand-title"><span style="color:#ff7777;">INFO</span> SOLUTIONS</div>
    <div class="sidebar-brand-tagline">{COMPANY_TAGLINE}</div>
</div>
<div class="profile-card"><b>{st.session_state.get('staff_name', 'Staff')}</b><br><span>{st.session_state.get('staff_role', 'Staff')}</span></div>
""", unsafe_allow_html=True)

if st.sidebar.button("Logout 🚪", use_container_width=True):
    st.session_state.authenticated = False
    st.session_state.pop("staff_name", None)
    st.session_state.pop("staff_role", None)
    st.rerun()

st.sidebar.markdown('<div class="nav-section">WORKSPACE</div>', unsafe_allow_html=True)
navigation_groups = {
    "Dashboard": ["📊 Executive Dashboard"],
    "Service Desk": ["📌 New Service Ticket", "📂 Manage Service Tickets"],
    "CRM & Sales": ["👥 Customer CRM", "📝 Quotation Builder", "💳 Payments & Collections"],
    "Operations": ["📍 CCTV & Solar Projects", "👑 Staff Management", "📦 Product Catalog"],
    "Reports & Search": ["📥 Data Reports & Search"],
}
navigation_group = st.sidebar.selectbox("Section", list(navigation_groups), label_visibility="collapsed")
choice = st.sidebar.selectbox("Open page", navigation_groups[navigation_group], label_visibility="collapsed")

st.markdown(f"<div style='font-size:.8rem; color:#657786; margin-bottom:.4rem;'>{COMPANY_NAME} · {COMPANY_TAGLINE}</div>", unsafe_allow_html=True)

# ---------------------------------------------------------
# TAB 1: EXECUTIVE DASHBOARD (FIXED ERROR)
# ---------------------------------------------------------
if choice == "📊 Executive Dashboard":
    st.subheader("📊 Business Overview & Executive Dashboard")
    
    conn = get_db_connection()
    cur = conn.cursor()

    # Service Ticket Counts (Fixed s_status_dict)
    cur.execute("SELECT status, COUNT(*) FROM service_entries GROUP BY status;")
    srv_status_raw = cur.fetchall()
    s_status_dict = {r[0]: r[1] for r in srv_status_raw}

    # Quotation Counts
    cur.execute("SELECT COALESCE(status, 'Pending') as status, COUNT(*), COALESCE(SUM(total_amount), 0) FROM quotations GROUP BY status;")
    q_status_raw = cur.fetchall()
    q_status_dict = {r[0]: {"count": r[1], "value": float(r[2])} for r in q_status_raw}

    cur.close()
    conn.close()

    # --- SECTION A: QUOTATION STATUS BREAKUP ---
    st.markdown("### 📝 Quotations Status Breakup")
    q_col1, q_col2, q_col3, q_col4 = st.columns(4)
    
    q_completed = q_status_dict.get("Completed", {"count": 0, "value": 0.0})
    q_pending = q_status_dict.get("Pending", {"count": 0, "value": 0.0})
    q_accepted = q_status_dict.get("Accepted", {"count": 0, "value": 0.0})
    q_cancelled = q_status_dict.get("Cancelled", {"count": 0, "value": 0.0})

    q_col1.metric("✅ Completed Quotations", f"{q_completed['count']}", f"₹ {q_completed['value']:,.2f}")
    q_col2.metric("⏳ Pending Approval", f"{q_pending['count']}", f"₹ {q_pending['value']:,.2f}")
    q_col3.metric("👍 Accepted (In Progress)", f"{q_accepted['count']}", f"₹ {q_accepted['value']:,.2f}")
    q_col4.metric("❌ Cancelled / Rejected", f"{q_cancelled['count']}", f"₹ {q_cancelled['value']:,.2f}")

    # --- SECTION B: SERVICE TICKETS STATUS BREAKUP ---
    st.markdown("---")
    st.markdown("### 🛠️ Service Tickets Status Breakup")
    s_col1, s_col2, s_col3, s_col4, s_col5 = st.columns(5)

    s_pending = s_status_dict.get("Pending", 0)
    s_in_progress = s_status_dict.get("In Progress", 0)
    s_completed = s_status_dict.get("Completed", 0)
    s_delivered = s_status_dict.get("Delivered", 0)
    s_cancelled = s_status_dict.get("Cancelled", 0)

    s_col1.metric("⏳ Pending Intake", s_pending)
    s_col2.metric("🔧 In Service Progress", s_in_progress)
    s_col3.metric("🎯 Service Completed", s_completed, "Ready for Delivery")
    s_col4.metric("🚚 Delivered to Customer", s_delivered)
    s_col5.metric("🚫 Service Cancelled", s_cancelled)

    # Detailed Summaries
    st.markdown("---")
    col_graph1, col_graph2 = st.columns(2)

    with col_graph1:
        st.markdown("#### Quotation Breakdown Table")
        q_summary_df = pd.DataFrame([
            {"Status": "Completed / Successful", "Count": q_completed['count'], "Total Value (₹)": f"₹ {q_completed['value']:,.2f}"},
            {"Status": "Pending Approval", "Count": q_pending['count'], "Total Value (₹)": f"₹ {q_pending['value']:,.2f}"},
            {"Status": "Accepted", "Count": q_accepted['count'], "Total Value (₹)": f"₹ {q_accepted['value']:,.2f}"},
            {"Status": "Cancelled / Rejected", "Count": q_cancelled['count'], "Total Value (₹)": f"₹ {q_cancelled['value']:,.2f}"}
        ])
        st.table(q_summary_df)

    with col_graph2:
        st.markdown("#### Service Ticket Summary Table")
        s_summary_df = pd.DataFrame([
            {"Service Status": "Pending Intake", "Ticket Count": s_pending},
            {"Service Status": "In Service Progress", "Ticket Count": s_in_progress},
            {"Service Status": "Completed (To be Picked)", "Ticket Count": s_completed},
            {"Service Status": "Delivered", "Ticket Count": s_delivered},
            {"Service Status": "Cancelled", "Ticket Count": s_cancelled}
        ])
        st.table(s_summary_df)

# ---------------------------------------------------------
# TAB 2: NEW SERVICE TICKET
# ---------------------------------------------------------
elif choice == "📌 New Service Ticket":
    st.subheader("📝 Create New Service Receipt / Ticket")
    
    receipt_no = generate_receipt_no()
    st.info(f"Generated Ticket No: **{receipt_no}**")

    service_customers = get_customer_profiles()
    service_customer_options = [None] + service_customers
    selected_service_customer = st.selectbox(
        "Use saved customer details (optional)",
        service_customer_options,
        format_func=lambda c: "-- Enter new customer --" if c is None else f"{c['customer_name']} · {c['phone']}",
        key="service_customer_profile",
    )
    service_customer = selected_service_customer or {}

    with st.form("new_service_form", clear_on_submit=True):
        col1, col2 = st.columns(2)
        
        with col1:
            customer_name = st.text_input("Customer Name*", value=service_customer.get("customer_name", ""))
            phone = st.text_input("Phone Number*", value=service_customer.get("phone", ""))
            item_description = st.text_input("Item Description (Laptop/Desktop/CCTV/Solar)*")
            serial_no = st.text_input("Serial / Model No")
            
        with col2:
            issue = st.text_area("Reported Issue / Fault")
            status = st.selectbox("Status", ["Pending", "Assigned", "In Progress", "Ready for Delivery", "Delivered"])
            assigned_to = st.selectbox("Assign Technician", ["Unassigned"] + get_active_staff())
            priority = st.selectbox("Priority", ["Normal", "High", "Urgent"])
            expected_delivery = st.date_input("Expected Delivery Date", value=None)
            estimated_cost = st.number_input("Estimated Cost (₹)", min_value=0.0, step=50.0)
            advance_paid = st.number_input("Advance Paid (₹)", min_value=0.0, step=50.0)
            
        submit = st.form_submit_button("Create Service Ticket", type="primary")

        if submit:
            if not customer_name or not phone or not item_description:
                st.warning("Please fill mandatory fields marked with *")
            else:
                try:
                    conn = get_db_connection()
                    cur = conn.cursor()
                    cur.execute('''
                        INSERT INTO service_entries 
                        (receipt_no, customer_name, phone, item_description, serial_no, issue, status, estimated_cost, advance_paid, assigned_to, priority, expected_delivery)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s);
                    ''', (receipt_no, customer_name, phone, item_description, serial_no, issue, status, float(estimated_cost), float(advance_paid), "" if assigned_to == "Unassigned" else assigned_to, priority, expected_delivery))
                    conn.commit()
                    cur.close()
                    conn.close()
                    save_customer(customer_name, phone)
                    if advance_paid > 0:
                        conn = get_db_connection()
                        cur = conn.cursor()
                        cur.execute('''INSERT INTO payments (reference_type, reference_no, customer_name, phone, amount, payment_mode, remarks, received_by)
                                       VALUES (%s, %s, %s, %s, %s, %s, %s, %s);''',
                                    ("Service Advance", receipt_no, customer_name, phone, float(advance_paid), "Cash", "Advance received at ticket creation", st.session_state.get("staff_name", "")))
                        conn.commit()
                        cur.close()
                        conn.close()
                    
                    st.success(f"✅ Service Ticket **{receipt_no}** created successfully!")
                    
                    wa_msg = f"Hello {customer_name},\nYour item *{item_description}* has been received at *INFO SOLUTIONS*.\nJob Card No: *{receipt_no}*\nStatus: *{status}*\nEst. Cost: ₹{estimated_cost}\nAdvance: ₹{advance_paid}\nBalance: ₹{estimated_cost - advance_paid}\nThank you!\nContact: {COMPANY_PHONE}"
                    wa_url = create_whatsapp_link(phone, wa_msg)
                    
                    st.markdown(f"""
                        <a href="{wa_url}" target="_blank" style="text-decoration:none;">
                            <button style="background-color:#25D366; color:white; border:none; padding:10px 20px; border-radius:5px; font-weight:bold; cursor:pointer;">
                                📲 Send Service Ticket via WhatsApp
                            </button>
                        </a>
                    """, unsafe_allow_html=True)
                    
                except Exception as e:
                    st.error(f"Error creating ticket: {e}")

# ---------------------------------------------------------
# TAB 3: MANAGE SERVICE TICKETS
# ---------------------------------------------------------
elif choice == "📂 Manage Service Tickets":
    st.subheader("🔍 Manage & Close Service Tickets")
    
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT 
            receipt_no, customer_name, phone, 
            item_description, serial_no, issue, status, 
            COALESCE(delivery_remarks, '') as delivery_remarks, 
            COALESCE(closing_remarks, '') as closing_remarks,
            closed_date, estimated_cost, advance_paid, entry_date,
            COALESCE(assigned_to, ''), COALESCE(priority, 'Normal'), expected_delivery
        FROM service_entries 
        ORDER BY entry_date DESC;
    """)
    rows = cur.fetchall()
    cur.close()
    conn.close()

    if rows:
        df = pd.DataFrame(rows, columns=[
            "Job Card No", "Customer Name", "Phone", 
            "Item", "Serial No", "Issue", "Status", 
            "Delivery Remarks", "Closing Remarks", "Closed Date", "Est Cost", "Advance", "Entry Date", "Assigned To", "Priority", "Expected Delivery"
        ])
        
        st.dataframe(df, use_container_width=True)
        st.markdown("---")
        
        selected_receipt = st.selectbox("Select Service Ticket to Manage / Close", df["Job Card No"].tolist())
        selected_ticket = df[df["Job Card No"] == selected_receipt].iloc[0]

        col_left, col_right = st.columns([2, 1])

        with col_left:
            st.markdown(f"### Update / Close Ticket: `{selected_receipt}`")
            with st.form("update_ticket_form"):
                workflow_statuses = ["Pending", "Assigned", "In Progress", "Ready for Delivery", "Delivered", "Cancelled"]
                current_status = selected_ticket["Status"] if selected_ticket["Status"] in workflow_statuses else "Pending"
                u_status = st.selectbox("Update Status", workflow_statuses, index=workflow_statuses.index(current_status))
                staff_choices = ["Unassigned"] + get_active_staff()
                current_assignee = selected_ticket["Assigned To"] if selected_ticket["Assigned To"] in staff_choices else "Unassigned"
                u_assigned_to = st.selectbox("Assign Technician", staff_choices, index=staff_choices.index(current_assignee))
                u_priority = st.selectbox("Priority", ["Normal", "High", "Urgent"], index=["Normal", "High", "Urgent"].index(selected_ticket["Priority"] if selected_ticket["Priority"] in ["Normal", "High", "Urgent"] else "Normal"))
                u_remarks = st.text_input("Service Progress Remarks", value=selected_ticket["Delivery Remarks"])
                
                st.markdown("#### 🔒 Closing Details")
                u_closing_remarks = st.text_area("Closing Remarks", value=selected_ticket["Closing Remarks"])
                
                u_est_cost = st.number_input("Final / Estimated Cost (₹)", value=float(selected_ticket["Est Cost"]))
                u_advance = st.number_input("Advance Paid (₹)", value=float(selected_ticket["Advance"]))
                
                update_btn = st.form_submit_button("Save & Update Ticket", type="primary")
                
                if update_btn:
                    conn = get_db_connection()
                    cur = conn.cursor()
                    
                    closing_date_val = datetime.now() if u_status in ["Delivered", "Completed"] else selected_ticket["Closed Date"]
                    
                    cur.execute('''
                        UPDATE service_entries 
                        SET status = %s, delivery_remarks = %s, closing_remarks = %s, closed_date = %s, estimated_cost = %s, advance_paid = %s, assigned_to = %s, priority = %s
                        WHERE receipt_no = %s;
                    ''', (u_status, u_remarks, u_closing_remarks, closing_date_val, float(u_est_cost), float(u_advance), "" if u_assigned_to == "Unassigned" else u_assigned_to, u_priority, selected_receipt))
                    conn.commit()
                    cur.close()
                    conn.close()
                    st.success(f"Ticket {selected_receipt} updated successfully!")
                    st.rerun()

            upd_wa_msg = f"Hello {selected_ticket['Customer Name']},\nUpdate regarding Job Card *{selected_receipt}* at *INFO SOLUTIONS*:\nItem: {selected_ticket['Item']}\nStatus: *{selected_ticket['Status']}*\nClosing Remarks: {u_closing_remarks or selected_ticket['Delivery Remarks']}\nTotal Cost: ₹{selected_ticket['Est Cost']}\nAdvance: ₹{selected_ticket['Advance']}\nBalance Due: ₹{selected_ticket['Est Cost'] - selected_ticket['Advance']}\nContact: {COMPANY_PHONE}"
            upd_wa_url = create_whatsapp_link(selected_ticket['Phone'], upd_wa_msg)
            
            st.markdown(f"""
                <a href="{upd_wa_url}" target="_blank" style="text-decoration:none;">
                    <button style="background-color:#25D366; color:white; border:none; padding:10px 20px; border-radius:5px; font-weight:bold; cursor:pointer; margin-top:10px;">
                        📲 Send Return / Service Summary via WhatsApp
                    </button>
                </a>
            """, unsafe_allow_html=True)

        with col_right:
            st.markdown("### Danger Zone")
            if st.button("❌ Delete Ticket"):
                conn = get_db_connection()
                cur = conn.cursor()
                cur.execute("DELETE FROM service_entries WHERE receipt_no = %s;", (selected_receipt,))
                conn.commit()
                cur.close()
                conn.close()
                st.success(f"Ticket {selected_receipt} deleted.")
                st.rerun()

        # PRINT RECEIPT
        st.markdown("---")
        st.markdown("### 🖨️ Printable Service Ticket (A5 Landscape)")
        
        logo_html = f'<img src="data:image/png;base64,{LOGO_BASE64}" style="max-height:48px; float:left; margin-right:10px;">' if LOGO_BASE64 else ''
        formatted_ticket_date = pd.to_datetime(selected_ticket['Entry Date']).strftime('%d-%m-%Y') if selected_ticket['Entry Date'] else datetime.now().strftime('%d-%m-%Y')

        receipt_html = f"""
        <html>
        <head>
            <style>
                @page {{ size: A5 landscape; margin: 4mm; }}
                @media print {{
                    .no-print {{ display: none !important; }}
                    body {{ padding: 0; margin: 0; background: #fff; -webkit-print-color-adjust: exact !important; print-color-adjust: exact !important; }}
                    .receipt-box {{ border: 2px solid {COLOR_BLUE} !important; height: 96vh !important; max-height: 96vh !important; display: flex; flex-direction: column; justify-content: space-between; box-sizing: border-box; }}
                }}
                body {{ font-family: 'Segoe UI', Arial, sans-serif; background-color: #fff; color: {TEXT_MAIN}; padding: 2px; margin: 0; }}
                .receipt-box {{ border: 2px solid {COLOR_BLUE}; padding: 10px 14px; border-radius: 6px; box-sizing: border-box; background: #fff; display: flex; flex-direction: column; justify-content: space-between; height: 430px; }}
                .btn-print {{ background-color: {COLOR_BLUE}; color: #fff; border: none; padding: 8px 18px; font-size: 13px; font-weight: bold; border-radius: 4px; cursor: pointer; margin-bottom: 8px; }}
                .tagline {{ color: #444; font-weight: 600; font-size: 9.5px; margin-top: 1px; font-style: italic; }}
                .contact-header {{ font-size: 9.5px; color: #222; margin-top: 2px; }}
                
                .footer-bar {{
                    background-color: {COLOR_BLUE} !important;
                    color: #ffffff !important;
                    text-align: center;
                    padding: 5px 4px;
                    font-size: 9.5px;
                    border-top: 2px solid {COLOR_RED} !important;
                    -webkit-print-color-adjust: exact !important;
                    print-color-adjust: exact !important;
                    margin-top: 4px;
                }}
                .info-table {{ width: 100%; margin-bottom: 4px; border-collapse: collapse; color: {TEXT_MAIN}; }}
                .info-table td {{ padding: 4px 6px; font-size: 11px; vertical-align: top; }}
                .terms-box {{ font-size: 8.5px; color: #222; border: 1px dashed #bbb; padding: 4px 8px; border-radius: 4px; margin-top: 4px; background: #fafafa; }}
                .terms-box ol {{ margin: 2px 0 0 10px; padding: 0; }}
                .signature-section {{ margin-top: 8px; margin-bottom: 2px; display: flex; justify-content: space-between; align-items: flex-end; font-size: 10px; font-weight: bold; color: {COLOR_BLUE}; }}
                .sig-box {{ width: 38%; text-align: center; }}
                .sig-line {{ border-top: 1px solid {COLOR_BLUE}; margin-bottom: 3px; }}
            </style>
        </head>
        <body>
            <button class="btn-print no-print" onclick="window.print()">🖨️ Print Ticket (A5 Landscape)</button>
            <div class="receipt-box">
                <div>
                    <div style="display: flex; justify-content: space-between; border-bottom: 2px solid {COLOR_BLUE}; padding-bottom: 4px;">
                        <div style="display: flex; align-items: center;">
                            {logo_html}
                            <div>
                                <h2 style="margin: 0; font-size: 17px; letter-spacing: 0.5px;">
                                    <span style="color:{COLOR_RED};">{COMPANY_NAME.split()[0]}</span> 
                                    <span style="color:{COLOR_BLUE};">{COMPANY_NAME.split()[1]}</span>
                                </h2>
                                <div class="tagline">{COMPANY_TAGLINE}</div>
                                <div class="contact-header">📞 {COMPANY_PHONE} &nbsp;|&nbsp; ✉️ {COMPANY_EMAIL}</div>
                            </div>
                        </div>
                        <div style="text-align: right;">
                            <div style="font-size: 11px; color: {COLOR_BLUE}; font-weight: bold;">
                                Job Card No: <span style="background-color: {COLOR_RED}; color: #ffffff; padding: 2px 6px; border-radius: 3px; display: inline-block;">{selected_ticket['Job Card No']}</span>
                            </div>
                            <div style="font-size: 10px; color: #333; margin-top: 4px;"><b>Date:</b> {formatted_ticket_date}</div>
                        </div>
                    </div>
                    
                    <div style="text-align: center; margin: 5px 0; font-weight: bold; color: {COLOR_BLUE}; font-size: 11.5px; letter-spacing: 0.5px;">
                        SERVICE ACKNOWLEDGEMENT RECEIPT
                    </div>
                    
                    <table class="info-table" style="line-height: 1.2;">
                        <tr>
                            <td style="width: 50%;"><b>Customer Name:</b> {selected_ticket['Customer Name']}</td>
                            <td style="width: 50%;"><b>Phone:</b> {selected_ticket['Phone']}</td>
                        </tr>
                        <tr>
                            <td><b>Item:</b> {selected_ticket['Item']}</td>
                            <td><b>Serial / Model No:</b> {selected_ticket['Serial No'] or 'N/A'}</td>
                        </tr>
                        <tr>
                            <td><b>Status:</b> {selected_ticket['Status']}</td>
                            <td><b>Reported Issue:</b> {selected_ticket['Issue']}</td>
                        </tr>
                    </table>
                    
                    <div style="background-color: #f8f9fa; padding: 4px 8px; border-radius: 4px; border: 1px solid #e9ecef; font-size: 10.5px; color: {TEXT_MAIN}; display: flex; justify-content: space-between; align-items: center;">
                        <div><b>Remarks:</b> {selected_ticket['Closing Remarks'] or selected_ticket['Delivery Remarks'] or 'N/A'}</div>
                        <div>
                            <span>Est/Total: <b>₹{selected_ticket['Est Cost']:.2f}</b> | </span>
                            <span>Adv: <b>₹{selected_ticket['Advance']:.2f}</b> | </span>
                            <span style="color: {COLOR_RED}; font-weight: bold;">Bal: ₹{selected_ticket['Est Cost'] - selected_ticket['Advance']:.2f}</span>
                        </div>
                    </div>
                </div>

                <div>
                    <div class="terms-box">
                        <b>Terms & Conditions:</b>
                        <ol>
                            <li>Items must be collected within 15 days of service. INFO SOLUTIONS is not liable after this period.</li>
                            <li>Backup data prior to service. We are not responsible for any data loss.</li>
                            <li>No warranty on physical/liquid damages or power surges after service.</li>
                            <li>Produce this original receipt for device collection.</li>
                        </ol>
                    </div>

                    <div class="signature-section">
                        <div class="sig-box">
                            <div class="sig-line"></div>
                            <span>Customer Signature</span>
                        </div>
                        <div class="sig-box">
                            <div style="height: 20px;"></div>
                            <div class="sig-line"></div>
                            <span>Authorized Signatory (INFO SOLUTIONS)</span>
                        </div>
                    </div>

                    <div class="footer-bar">
                        📍 {COMPANY_ADDRESS}
                    </div>
                </div>
            </div>
        </body>
        </html>
        """
        st.components.v1.html(receipt_html, height=480, scrolling=True)

    else:
        st.info("No service tickets found.")

# ---------------------------------------------------------
# TAB 4: QUOTATION BUILDER (AUTO-FILL FEATURE INCLUDED)
# ---------------------------------------------------------
elif choice == "📝 Quotation Builder":
    st.subheader("📑 Create, Edit, Complete & Print Quotations")
    
    quote_tab1, quote_tab2 = st.tabs(["Create New Quotation", "Manage & Complete Quotations"])

    available_products = get_products_list()
    product_options = ["-- Select from Product Catalog --"] + [f"{p[0]} (₹{p[1]})" for p in available_products]

    # --- TAB 4A: CREATE NEW QUOTATION ---
    with quote_tab1:
        quote_no = generate_quote_no()
        st.info(f"Generated Quotation No: **{quote_no}**")

        quotation_customers = get_customer_profiles()
        selected_quote_customer = st.selectbox(
            "Use saved customer details (optional)",
            [None] + quotation_customers,
            format_func=lambda c: "-- Enter new customer --" if c is None else f"{c['customer_name']} · {c['phone']}",
            key="quotation_customer_profile",
        )
        quote_customer = selected_quote_customer or {}

        col_cust1, col_cust2, col_cust3, col_cust4 = st.columns([2, 2, 2, 2])
        customer_name = col_cust1.text_input("Customer / Company Name", value=quote_customer.get("customer_name", ""))
        customer_place = col_cust2.text_input("Customer Place / City", value=quote_customer.get("address", ""))
        phone = col_cust3.text_input("Phone Number", value=quote_customer.get("phone", ""))
        selected_category = col_cust4.selectbox("Select Service Category", CATEGORY_OPTIONS)

        st.markdown("#### Add Line Items")
        if "quote_items" not in st.session_state:
            st.session_state.quote_items = []

        # AUTO-FILL RATE & DESCRIPTION LOGIC
        selected_prod = st.selectbox("📦 Quick Select Product from Catalog (Auto-Fills Rate & Details)", product_options)
        
        default_item_name = ""
        default_price = 0.0
        if selected_prod != "-- Select from Product Catalog --":
            prod_name_extracted = selected_prod.split(" (₹")[0]
            for p in available_products:
                if p[0] == prod_name_extracted:
                    default_item_name = p[0]
                    default_price = float(p[1])
                    break

        with st.form("add_quote_item_form", clear_on_submit=True):
            col_desc, col_qty, col_rate = st.columns([3, 1, 1])
            item_desc = col_desc.text_input("Item Description / Service", value=default_item_name)
            qty = col_qty.number_input("Qty", min_value=1, value=1)
            rate = col_rate.number_input("Unit Price (₹) [Editable]", min_value=0.0, value=default_price, step=10.0)
            
            if st.form_submit_button("Add Item to List") and item_desc:
                auto_save_product_to_catalog(item_desc, rate)
                
                # 18% GST calculation
                item_subtotal = float(qty * rate)
                item_gst = float(item_subtotal * 0.18)
                item_total = item_subtotal + item_gst
                
                st.session_state.quote_items.append({
                    "description": item_desc,
                    "qty": int(qty),
                    "rate": float(rate),
                    "subtotal": float(item_subtotal),
                    "gst": float(item_gst),
                    "amount": float(item_total)
                })
                st.rerun()

        if st.session_state.quote_items:
            st.markdown("##### Selected Items:")
            items_df = pd.DataFrame(st.session_state.quote_items)
            
            disp_df = items_df[["description", "qty", "rate", "subtotal", "gst", "amount"]].copy()
            disp_df.columns = ["Description", "Qty", "Unit Price (₹)", "Subtotal (₹)", "GST 18% (₹)", "Total (₹)"]
            st.dataframe(disp_df, use_container_width=True)
            
            subtotal_sum = float(items_df["subtotal"].sum())
            gst_sum = float(items_df["gst"].sum())
            grand_total = float(items_df["amount"].sum())

            col_m1, col_m2, col_m3 = st.columns(3)
            col_m1.metric("Subtotal", f"₹ {subtotal_sum:,.2f}")
            col_m2.metric("Total GST (18%)", f"₹ {gst_sum:,.2f}")
            col_m3.metric("Grand Total", f"₹ {grand_total:,.2f}")

            if st.button("Clear Items List"):
                st.session_state.quote_items = []
                st.rerun()

            if st.button("💾 Save & Generate Quotation", type="primary"):
                if not customer_name or not phone:
                    st.warning("Customer Name and Phone are required!")
                else:
                    try:
                        conn = get_db_connection()
                        cur = conn.cursor()
                        
                        cur.execute('''
                            INSERT INTO quotations (quote_no, customer_name, phone, customer_place, category, status, items_json, subtotal, gst_amount, total_amount, quote_date)
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP);
                        ''', (quote_no, customer_name, phone, customer_place, selected_category, 'Pending', json.dumps(st.session_state.quote_items), float(subtotal_sum), float(gst_sum), float(grand_total)))
                        
                        conn.commit()
                        cur.close()
                        conn.close()
                        save_customer(customer_name, phone, address=customer_place)
                        
                        st.success(f"Quotation {quote_no} saved successfully!")
                        
                        items_text = "\n".join([f"- {i['description']} (x{i['qty']}): ₹{i['amount']:,.2f}" for i in st.session_state.quote_items])
                        q_msg = f"Hello {customer_name},\nGreetings from *INFO SOLUTIONS*.\n\n*QUOTATION ({selected_category}) - {quote_no}*\n{items_text}\n\n*Subtotal: ₹{subtotal_sum:,.2f}*\n*GST (18%): ₹{gst_sum:,.2f}*\n*Grand Total: ₹{grand_total:,.2f}*\n\nContact: {COMPANY_PHONE}"
                        q_wa_url = create_whatsapp_link(phone, q_msg)
                        
                        st.markdown(f"""
                            <a href="{q_wa_url}" target="_blank" style="text-decoration:none;">
                                <button style="background-color:#25D366; color:white; border:none; padding:10px 20px; border-radius:5px; font-weight:bold; cursor:pointer;">
                                    📲 Send Quotation Summary via WhatsApp
                                </button>
                            </a>
                        """, unsafe_allow_html=True)
                        
                        st.session_state.quote_items = []
                    except Exception as ex:
                        st.error(f"Error saving quotation: {ex}")

    # --- TAB 4B: MANAGE, COMPLETE & PRINT QUOTATIONS ---
    with quote_tab2:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT quote_no, customer_name, phone, COALESCE(customer_place, '') as customer_place, COALESCE(category, 'General') as category, COALESCE(status, 'Pending') as status, items_json, COALESCE(subtotal,0) as subtotal, COALESCE(gst_amount,0) as gst_amount, total_amount, quote_date FROM quotations ORDER BY quote_date DESC;")
        quotes = cur.fetchall()
        cur.close()
        conn.close()

        if quotes:
            q_df = pd.DataFrame(quotes, columns=["Quote No", "Customer Name", "Phone", "Place", "Category Tag", "Status", "Items JSON", "Subtotal", "GST Amount", "Total Amount", "Date"])
            st.dataframe(q_df[["Quote No", "Customer Name", "Phone", "Place", "Category Tag", "Status", "Subtotal", "GST Amount", "Total Amount", "Date"]], use_container_width=True)
            
            selected_q_no = st.selectbox("Select Quotation to View / Complete / Edit", q_df["Quote No"].tolist())
            q_data = q_df[q_df["Quote No"] == selected_q_no].iloc[0]
            
            st.markdown("---")
            st.markdown(f"### 🎯 Quotation Completion & Status: `{selected_q_no}`")
            
            col_stat1, col_stat2 = st.columns([2, 1])
            with col_stat1:
                current_q_status = q_data["Status"] if q_data["Status"] in QUOTATION_STATUS_LIST else "Pending"
                new_q_status = st.selectbox("Update Quotation Status", QUOTATION_STATUS_LIST, index=QUOTATION_STATUS_LIST.index(current_q_status))
                
                if st.button("🔄 Update Quotation Status", type="primary"):
                    conn = get_db_connection()
                    cur = conn.cursor()
                    cur.execute("UPDATE quotations SET status = %s WHERE quote_no = %s;", (new_q_status, selected_q_no))
                    conn.commit()
                    cur.close()
                    conn.close()
                    st.success(f"Quotation {selected_q_no} marked as **{new_q_status}**!")
                    st.rerun()

            with col_stat2:
                existing_items_wa = json.loads(q_data["Items JSON"])
                items_text_m = "\n".join([f"- {i['description']} (x{i['qty']}): ₹{i.get('amount', 0):,.2f}" for i in existing_items_wa])
                q_wa_msg = f"Hello {q_data['Customer Name']},\nGreetings from *INFO SOLUTIONS*.\n\n*QUOTATION ({q_data['Category Tag']}) - {selected_q_no}*\n*Status: {q_data['Status']}*\n{items_text_m}\n\n*Grand Total: ₹{q_data['Total Amount']:,.2f}*\n\nContact: {COMPANY_PHONE}"
                q_m_wa_url = create_whatsapp_link(q_data['Phone'], q_wa_msg)
                
                st.markdown(f"""
                    <a href="{q_m_wa_url}" target="_blank" style="text-decoration:none;">
                        <button style="background-color:#25D366; color:white; border:none; padding:12px 18px; border-radius:5px; font-weight:bold; cursor:pointer; margin-top:25px;">
                            📲 WhatsApp Quotation Status
                        </button>
                    </a>
                """, unsafe_allow_html=True)

            st.markdown("---")
            st.markdown(f"### ✏️ Edit Items / Details: `{selected_q_no}`")
            existing_items = json.loads(q_data["Items JSON"])

            with st.expander("📝 Click here to Edit Info, Add / Modify Line Items or Delete Quotation"):
                with st.form("edit_quotation_easy_form"):
                    col_e1, col_e2, col_e3, col_e4 = st.columns([2, 2, 2, 2])
                    e_cust_name = col_e1.text_input("Customer Name", value=q_data["Customer Name"])
                    e_place = col_e2.text_input("Customer Place / City", value=q_data["Place"])
                    e_phone = col_e3.text_input("Phone Number", value=q_data["Phone"])
                    
                    cat_index = CATEGORY_OPTIONS.index(q_data["Category Tag"]) if q_data["Category Tag"] in CATEGORY_OPTIONS else 0
                    e_category = col_e4.selectbox("Category Tag", CATEGORY_OPTIONS, index=cat_index)

                    st.markdown("##### Line Items:")
                    updated_items_list = []
                    
                    for idx, item in enumerate(existing_items):
                        st.markdown(f"**Item {idx + 1}**")
                        c_desc, c_qty, c_rate, c_del = st.columns([3, 1, 1, 1])
                        new_desc = c_desc.text_input(f"Description #{idx+1}", value=item.get("description", ""), key=f"edit_desc_{selected_q_no}_{idx}")
                        new_qty = c_qty.number_input(f"Qty #{idx+1}", min_value=1, value=int(item.get("qty", 1)), key=f"edit_qty_{selected_q_no}_{idx}")
                        new_rate = c_rate.number_input(f"Unit Price ₹ #{idx+1}", min_value=0.0, value=float(item.get("rate", 0.0)), key=f"edit_rate_{selected_q_no}_{idx}")
                        
                        delete_item = c_del.checkbox("❌ Delete Item", key=f"delete_item_{selected_q_no}_{idx}")
                        
                        if new_desc and not delete_item:
                            sub_tot = float(new_qty * new_rate)
                            gst_val = float(sub_tot * 0.18)
                            tot_val = sub_tot + gst_val
                            updated_items_list.append({
                                "description": new_desc,
                                "qty": int(new_qty),
                                "rate": float(new_rate),
                                "subtotal": sub_tot,
                                "gst": gst_val,
                                "amount": tot_val
                            })

                    st.markdown("---")
                    st.markdown("##### Add an Additional Item (Optional):")
                    c_add_d, c_add_q, c_add_r = st.columns([3, 1, 1])
                    add_desc = c_add_d.text_input("New Item Description", key=f"add_desc_{selected_q_no}")
                    add_qty = c_add_q.number_input("New Qty", min_value=1, value=1, key=f"add_qty_{selected_q_no}")
                    add_rate = c_add_r.number_input("New Unit Price (₹)", min_value=0.0, value=0.0, key=f"add_rate_{selected_q_no}")

                    if add_desc:
                        sub_tot = float(add_qty * add_rate)
                        gst_val = float(sub_tot * 0.18)
                        tot_val = sub_tot + gst_val
                        updated_items_list.append({
                            "description": add_desc,
                            "qty": int(add_qty),
                            "rate": float(add_rate),
                            "subtotal": sub_tot,
                            "gst": gst_val,
                            "amount": tot_val
                        })

                    save_edits = st.form_submit_button("💾 Save All Changes", type="primary")
                    
                    if save_edits:
                        new_subtotal = sum(i.get("subtotal", i["qty"]*i["rate"]) for i in updated_items_list)
                        new_gst = sum(i.get("gst", i.get("subtotal", i["qty"]*i["rate"])*0.18) for i in updated_items_list)
                        new_grand_total = new_subtotal + new_gst
                        
                        conn = get_db_connection()
                        cur = conn.cursor()
                        cur.execute('''
                            UPDATE quotations
                            SET customer_name = %s, phone = %s, customer_place = %s, category = %s, items_json = %s, subtotal = %s, gst_amount = %s, total_amount = %s
                            WHERE quote_no = %s;
                        ''', (e_cust_name, e_phone, e_place, e_category, json.dumps(updated_items_list), new_subtotal, new_gst, new_grand_total, selected_q_no))
                        conn.commit()
                        cur.close()
                        conn.close()
                        save_customer(e_cust_name, e_phone, address=e_place)
                        st.success(f"Quotation {selected_q_no} updated successfully!")
                        st.rerun()

            if st.button(f"🗑️ Delete Entire Quotation ({selected_q_no})"):
                conn = get_db_connection()
                cur = conn.cursor()
                cur.execute("DELETE FROM quotations WHERE quote_no = %s;", (selected_q_no,))
                conn.commit()
                cur.close()
                conn.close()
                st.success(f"Quotation {selected_q_no} deleted successfully!")
                st.rerun()

            # PRINTABLE QUOTATION
            st.markdown("---")
            st.markdown("### 🖨️ Printable Quotation (Rich Logo Theme)")

            logo_html = f'<img src="data:image/png;base64,{LOGO_BASE64}" style="max-height:55px; float:left; margin-right:12px;">' if LOGO_BASE64 else ''
            
            raw_date = q_data.get("Date")
            parsed_quote_date = pd.to_datetime(raw_date, errors="coerce")
            formatted_quote_date = (
                parsed_quote_date.strftime("%d-%m-%Y")
                if not pd.isna(parsed_quote_date)
                else datetime.now().strftime("%d-%m-%Y")
            )

            items_table_rows = ""
            calc_subtotal = 0.0
            calc_gst = 0.0
            
            for idx, item in enumerate(existing_items, 1):
                i_qty = item.get('qty', 1)
                i_rate = item.get('rate', 0.0)
                i_subtotal = item.get('subtotal', i_qty * i_rate)
                i_gst = item.get('gst', i_subtotal * 0.18)
                i_amount = item.get('amount', i_subtotal + i_gst)
                
                calc_subtotal += i_subtotal
                calc_gst += i_gst
                
                items_table_rows += f"""
                <tr>
                    <td style="text-align: center; border: 1px solid #e2e8f0; padding: 10px;">{idx}</td>
                    <td style="border: 1px solid #e2e8f0; padding: 10px; font-weight: 500; color: #1a1a1a;">{item['description']}</td>
                    <td style="text-align: center; border: 1px solid #e2e8f0; padding: 10px;">{i_qty}</td>
                    <td style="text-align: right; border: 1px solid #e2e8f0; padding: 10px;">₹ {i_rate:,.2f}</td>
                    <td style="text-align: right; border: 1px solid #e2e8f0; padding: 10px;">₹ {i_gst:,.2f}</td>
                    <td style="text-align: right; border: 1px solid #e2e8f0; padding: 10px; font-weight: bold; color: {COLOR_BLUE};">₹ {i_amount:,.2f}</td>
                </tr>
                """

            calc_grand_total = calc_subtotal + calc_gst

            quotation_html = f"""
            <html>
            <head>
                <style>
                    @page {{
                        size: A4 portrait;
                        margin: 10mm;
                    }}
                    @media print {{
                        .no-print {{ display: none !important; }}
                        body {{ padding: 0; margin: 0; background: #fff; -webkit-print-color-adjust: exact !important; print-color-adjust: exact !important; }}
                        .page-container {{ border: none !important; box-shadow: none !important; padding: 0 !important; min-height: 98vh !important; }}
                        .keep-together {{ page-break-inside: avoid; }}
                    }}
                    body {{ font-family: 'Segoe UI', Arial, sans-serif; background-color: #fff; color: #1a1a1a; margin: 0; padding: 10px; }}
                    .page-container {{
                        border: 1px solid #cbd5e1;
                        padding: 30px;
                        max-width: 820px;
                        min-height: 1020px;
                        margin: 0 auto;
                        background: #fff;
                        box-sizing: border-box;
                        display: flex;
                        flex-direction: column;
                        justify-content: space-between;
                        border-top: 6px solid {COLOR_RED};
                        border-radius: 4px;
                    }}
                    .btn-print {{ background-color: {COLOR_BLUE}; color: #ffffff; border: none; padding: 10px 22px; font-size: 14px; font-weight: bold; border-radius: 4px; cursor: pointer; margin-bottom: 15px; }}
                    
                    .header-section {{
                        display: flex;
                        justify-content: space-between;
                        align-items: flex-start;
                        border-bottom: 2px solid #e2e8f0;
                        padding-bottom: 16px;
                        margin-bottom: 20px;
                    }}
                    .company-title {{ font-size: 26px; font-weight: 800; margin: 0; letter-spacing: 0.5px; }}
                    .tagline {{ color: #475569; font-weight: 600; font-size: 11px; margin-top: 3px; font-style: italic; }}
                    .contact-header {{ font-size: 11px; color: #222222; margin-top: 4px; font-weight: 500; }}
                    
                    .right-header-box {{
                        text-align: right;
                    }}
                    .official-badge {{
                        background-color: {COLOR_BLUE} !important;
                        color: #ffffff !important;
                        font-weight: 700;
                        font-size: 12px;
                        padding: 6px 14px;
                        border-radius: 4px;
                        letter-spacing: 1px;
                        display: inline-block;
                        margin-bottom: 6px;
                        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
                        border-bottom: 2px solid {COLOR_RED};
                        -webkit-print-color-adjust: exact !important;
                        print-color-adjust: exact !important;
                    }}
                    .ref-text {{ font-size: 12px; color: {COLOR_BLUE}; font-weight: 700; margin-top: 4px; }}
                    .date-text {{ font-size: 11px; color: #444444; margin-top: 2px; font-weight: 600; }}
                    
                    .info-grid {{
                        display: flex;
                        justify-content: space-between;
                        align-items: flex-start;
                        margin-bottom: 20px;
                        background: #f8fafc;
                        padding: 14px 18px;
                        border-radius: 6px;
                        border-left: 4px solid {COLOR_RED};
                    }}
                    .cust-details {{ font-size: 12px; line-height: 1.5; color: #1a1a1a; }}
                    .cust-name {{ font-size: 15px; font-weight: 700; color: {COLOR_BLUE}; margin-bottom: 3px; }}
                    
                    .category-display {{
                        text-align: right;
                    }}
                    .category-title {{
                        font-size: 10px;
                        text-transform: uppercase;
                        color: #64748b;
                        font-weight: 700;
                        letter-spacing: 0.5px;
                        margin-bottom: 4px;
                    }}
                    .category-value {{
                        font-size: 16px;
                        font-weight: 800;
                        color: {COLOR_BLUE};
                        letter-spacing: 0.3px;
                    }}
                    
                    .items-table {{ width: 100%; border-collapse: collapse; margin-top: 10px; font-size: 12px; color: #1a1a1a; }}
                    .items-table th {{ 
                        background-color: {COLOR_BLUE} !important; 
                        color: #ffffff !important; 
                        border: 1px solid {COLOR_BLUE}; 
                        padding: 10px; 
                        text-align: left; 
                        font-weight: 700;
                        -webkit-print-color-adjust: exact !important; 
                        print-color-adjust: exact !important; 
                    }}
                    
                    .totals-container {{
                        display: flex;
                        justify-content: flex-end;
                        margin-top: 12px;
                    }}
                    .totals-table {{
                        width: 45%;
                        border-collapse: collapse;
                        font-size: 12px;
                        color: #1a1a1a;
                    }}
                    .totals-table td {{ padding: 6px 10px; }}
                    .grand-total-row {{
                        background-color: {COLOR_BLUE} !important;
                        color: #ffffff !important;
                        font-weight: bold;
                        font-size: 14px;
                        -webkit-print-color-adjust: exact !important;
                        print-color-adjust: exact !important;
                    }}
                    
                    .signature-section {{
                        margin-top: 30px;
                        margin-bottom: 10px;
                        display: flex;
                        justify-content: space-between;
                        align-items: flex-end;
                        font-size: 11px;
                        font-weight: bold;
                        color: {COLOR_BLUE};
                        page-break-inside: avoid;
                    }}
                    .sig-box {{ width: 38%; text-align: center; }}
                    .seal-space {{ height: 35px; font-size: 10px; color: #64748b; }}
                    .sig-line {{ border-top: 1px solid {COLOR_BLUE}; margin-bottom: 4px; }}
                    
                    .terms-box {{
                        font-size: 10px;
                        color: #222222;
                        border: 1px dashed #cbd5e1;
                        padding: 10px 14px;
                        border-radius: 4px;
                        margin-top: 15px;
                        background: #f8fafc;
                        page-break-inside: avoid;
                    }}
                    .terms-box ol {{ margin: 3px 0 0 14px; padding: 0; }}
                    
                    .footer-bar {{
                        background-color: {COLOR_BLUE} !important;
                        color: #ffffff !important;
                        text-align: center;
                        padding: 8px;
                        font-size: 10.5px;
                        border-top: 2px solid {COLOR_RED} !important;
                        -webkit-print-color-adjust: exact !important;
                        print-color-adjust: exact !important;
                        margin-top: 15px;
                        page-break-inside: avoid;
                    }}
                </style>
            </head>
            <body>
                <button class="btn-print no-print" onclick="window.print()">🖨️ Print Quotation (A4)</button>
                
                <div class="page-container">
                    <div>
                        <div class="header-section">
                            <div style="display: flex; align-items: center;">
                                {logo_html}
                                <div>
                                    <h1 class="company-title">
                                        <span style="color:{COLOR_RED};">INFO</span> 
                                        <span style="color:{COLOR_BLUE};">SOLUTIONS</span>
                                    </h1>
                                    <div class="tagline">{COMPANY_TAGLINE}</div>
                                    <div class="contact-header">📞 {COMPANY_PHONE} &nbsp;|&nbsp; ✉️ {COMPANY_EMAIL}</div>
                                </div>
                            </div>
                            
                            <div class="right-header-box">
                                <div class="official-badge">OFFICIAL QUOTATION</div>
                                <div class="ref-text">REF: {q_data['Quote No']}</div>
                                <div class="date-text"><b>Date:</b> {formatted_quote_date}</div>
                            </div>
                        </div>

                        <div class="info-grid">
                            <div class="cust-details">
                                <div style="font-size: 10px; text-transform: uppercase; color: #64748b; font-weight: 700; margin-bottom: 2px;">Quotation For</div>
                                <div class="cust-name">{q_data['Customer Name']}</div>
                                <div style="color: #1a1a1a;">📍 {q_data['Place'] if q_data['Place'] else 'N/A'}</div>
                                <div style="color: #1a1a1a;">📞 {q_data['Phone']}</div>
                            </div>
                            
                            <div class="category-display">
                                <div class="category-title">Service Category</div>
                                <div class="category-value">{q_data['Category Tag']}</div>
                            </div>
                        </div>

                        <table class="items-table">
                            <thead>
                                <tr>
                                    <th style="width: 6%; text-align: center;">#</th>
                                    <th>Item Description</th>
                                    <th style="width: 8%; text-align: center;">Qty</th>
                                    <th style="width: 18%; text-align: right;">Unit Price (₹)</th>
                                    <th style="width: 16%; text-align: right;">GST (18%)</th>
                                    <th style="width: 20%; text-align: right;">Total (₹)</th>
                                </tr>
                            </thead>
                            <tbody>
                                {items_table_rows}
                            </tbody>
                        </table>

                        <div class="totals-container">
                            <table class="totals-table">
                                <tr>
                                    <td style="text-align: right; font-weight: 600; color: #333;">Subtotal:</td>
                                    <td style="text-align: right; font-weight: 600; color: #1a1a1a;">₹ {calc_subtotal:,.2f}</td>
                                </tr>
                                <tr>
                                    <td style="text-align: right; font-weight: 600; color: #333;">GST Amount (18%):</td>
                                    <td style="text-align: right; font-weight: 600; color: #1a1a1a;">₹ {calc_gst:,.2f}</td>
                                </tr>
                                <tr class="grand-total-row">
                                    <td style="text-align: right; padding: 8px 10px;">Grand Total:</td>
                                    <td style="text-align: right; padding: 8px 10px;">₹ {calc_grand_total:,.2f}</td>
                                </tr>
                            </table>
                        </div>
                    </div>

                    <div class="keep-together">
                        <div class="terms-box">
                            <b>Terms & Conditions:</b>
                            <ol>
                                <li>Quotation validity is 15 days from the date of issue.</li>
                                <li>Prices are inclusive of 18% GST as specified in the calculation above.</li>
                                <li>Payment terms: 50% advance upon order confirmation, balance upon completion.</li>
                                <li>Warranty coverage is strictly as per manufacturer specifications.</li>
                            </ol>
                        </div>

                        <div class="signature-section">
                            <div class="sig-box">
                                <div class="seal-space"></div>
                                <div class="sig-line"></div>
                                <span>Customer Acceptance</span>
                            </div>
                            <div class="sig-box">
                                <div class="seal-space">( Authorized Seal & Stamp )</div>
                                <div class="sig-line"></div>
                                <span>For INFO SOLUTIONS</span>
                            </div>
                        </div>

                        <div class="footer-bar">
                            📍 {COMPANY_ADDRESS}
                        </div>
                    </div>
                </div>
            </body>
            </html>
            """
            st.components.v1.html(quotation_html, height=1100, scrolling=True)

        else:
            st.info("No quotations found.")

# ---------------------------------------------------------
# TAB 5: PRODUCT CATALOG
# ---------------------------------------------------------
elif choice == "📦 Product Catalog":
    st.subheader("📦 Product Catalog Management")
    
    with st.form("add_prod_catalog_form", clear_on_submit=True):
        col_p1, col_p2, col_p3 = st.columns([3, 2, 2])
        p_name = col_p1.text_input("Product / Service Name")
        p_cat = col_p2.selectbox("Category", CATEGORY_OPTIONS)
        p_price = col_p3.number_input("Default Unit Price (₹)", min_value=0.0, step=100.0)
        
        if st.form_submit_button("Add to Catalog", type="primary") and p_name:
            auto_save_product_to_catalog(p_name, p_price)
            st.success(f"Added '{p_name}' to Product Catalog!")
            st.rerun()

    prods = get_products_list()
    if prods:
        st.dataframe(pd.DataFrame(prods, columns=["Product Name", "Unit Price (₹)"]), use_container_width=True)

# ---------------------------------------------------------
# CUSTOMER CRM
# ---------------------------------------------------------
elif choice == "👥 Customer CRM":
    st.subheader("Customer CRM & Service History")
    crm_tab1, crm_tab2 = st.tabs(["Add / Update Customer", "Customer History"])
    with crm_tab1:
        crm_customers = get_customer_profiles()
        selected_crm_customer = st.selectbox(
            "Select an existing customer to edit",
            [None] + crm_customers,
            format_func=lambda c: "-- Add a new customer --" if c is None else f"{c['customer_name']} · {c['phone']}",
            key="crm_customer_editor",
        )
        crm_customer = selected_crm_customer or {}
        with st.form("customer_form", clear_on_submit=True):
            c1, c2 = st.columns(2)
            customer_name = c1.text_input("Customer Name*", value=crm_customer.get("customer_name", ""))
            customer_phone = c1.text_input("Phone Number*", value=crm_customer.get("phone", ""))
            customer_email = c1.text_input("Email", value=crm_customer.get("email", ""))
            customer_address = c2.text_area("Address", value=crm_customer.get("address", ""))
            customer_gstin = c2.text_input("GSTIN", value=crm_customer.get("gstin", ""))
            customer_notes = st.text_area("Customer Notes", value=crm_customer.get("notes", ""))
            action_text = "Update Customer" if selected_crm_customer else "Save Customer"
            if st.form_submit_button(action_text, type="primary"):
                if customer_name and customer_phone:
                    if selected_crm_customer:
                        update_customer(selected_crm_customer["id"], customer_name, customer_phone, customer_email, customer_address, customer_gstin, customer_notes)
                        st.success("Customer profile updated successfully.")
                    else:
                        save_customer(customer_name, customer_phone, customer_email, customer_address, customer_gstin, customer_notes)
                        st.success("Customer profile saved successfully.")
                    st.rerun()
                else:
                    st.warning("Customer name and phone number are required.")
    with crm_tab2:
        search_customer = st.text_input("Search by customer name or phone")
        conn = get_db_connection()
        if search_customer:
            customers_df = pd.read_sql("SELECT * FROM customers WHERE customer_name ILIKE %s OR phone ILIKE %s ORDER BY updated_at DESC;", conn, params=(f"%{search_customer}%", f"%{search_customer}%"))
        else:
            customers_df = pd.read_sql("SELECT * FROM customers ORDER BY updated_at DESC LIMIT 100;", conn)
        if not customers_df.empty:
            st.dataframe(customers_df, use_container_width=True, hide_index=True)
            selected_phone = st.selectbox("View complete history for", customers_df["phone"].tolist())
            service_history = pd.read_sql("SELECT receipt_no, item_description, status, estimated_cost, advance_paid, entry_date FROM service_entries WHERE phone = %s ORDER BY entry_date DESC;", conn, params=(selected_phone,))
            quotation_history = pd.read_sql("SELECT quote_no, category, status, total_amount, quote_date FROM quotations WHERE phone = %s ORDER BY quote_date DESC;", conn, params=(selected_phone,))
            h1, h2 = st.columns(2)
            h1.caption("Service history")
            h1.dataframe(service_history, use_container_width=True, hide_index=True)
            h2.caption("Quotation history")
            h2.dataframe(quotation_history, use_container_width=True, hide_index=True)
        else:
            st.info("No customer profiles found.")
        conn.close()

# ---------------------------------------------------------
# PAYMENTS & COLLECTIONS
# ---------------------------------------------------------
elif choice == "💳 Payments & Collections":
    st.subheader("Payments, Collections & Outstanding Balances")
    pay_tab1, pay_tab2 = st.tabs(["Record Payment", "Collection Register"])
    with pay_tab1:
        reference_type = st.selectbox("Payment For", ["Service", "Quotation", "Project", "Other"], key="payment_reference_type")
        conn = get_db_connection()
        cur = conn.cursor()
        if reference_type == "Service":
            cur.execute("SELECT receipt_no, customer_name, phone FROM service_entries ORDER BY entry_date DESC;")
        elif reference_type == "Quotation":
            cur.execute("SELECT quote_no, customer_name, phone FROM quotations ORDER BY quote_date DESC;")
        elif reference_type == "Project":
            cur.execute("SELECT project_no, customer_name, phone FROM projects ORDER BY created_at DESC;")
        else:
            cur.execute("SELECT '' AS reference_no, customer_name, phone FROM customers ORDER BY customer_name;")
        payment_references = [dict(row) for row in cur.fetchall()]
        cur.close()
        conn.close()

        selected_reference = st.selectbox(
            "Link payment to an existing record",
            [None] + payment_references,
            format_func=lambda r: "-- Select record / use manual details --" if r is None else f"{r['reference_no'] or 'Customer'} · {r['customer_name']} · {r['phone']}",
            key="payment_linked_reference",
        )
        payment_reference = selected_reference or {}
        with st.form("payment_form", clear_on_submit=True):
            p1, p2 = st.columns(2)
            reference_no = p1.text_input("Reference No. (Ticket / Quote / Project)", value=payment_reference.get("reference_no", ""))
            payment_customer = p1.text_input("Customer Name*", value=payment_reference.get("customer_name", ""))
            payment_phone = p2.text_input("Customer Phone", value=payment_reference.get("phone", ""))
            payment_amount = p2.number_input("Amount Received (₹)", min_value=0.0, step=50.0)
            payment_mode = p2.selectbox("Payment Mode", ["Cash", "UPI", "Bank Transfer", "Card", "Cheque"])
            payment_remarks = st.text_input("Remarks")
            if st.form_submit_button("Record Payment", type="primary"):
                if payment_customer and payment_amount > 0:
                    conn = get_db_connection()
                    cur = conn.cursor()
                    cur.execute('''INSERT INTO payments (reference_type, reference_no, customer_name, phone, amount, payment_mode, remarks, received_by)
                                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s);''',
                                (reference_type, reference_no, payment_customer, payment_phone, float(payment_amount), payment_mode, payment_remarks, st.session_state.get("staff_name", "")))
                    if reference_type == "Service" and reference_no:
                        cur.execute("UPDATE service_entries SET advance_paid = advance_paid + %s WHERE receipt_no = %s;", (float(payment_amount), reference_no))
                    elif reference_type == "Quotation" and reference_no:
                        cur.execute("UPDATE quotations SET paid_amount = COALESCE(paid_amount, 0) + %s WHERE quote_no = %s;", (float(payment_amount), reference_no))
                    elif reference_type == "Project" and reference_no:
                        cur.execute("UPDATE projects SET advance_paid = advance_paid + %s WHERE project_no = %s;", (float(payment_amount), reference_no))
                    conn.commit()
                    cur.close()
                    conn.close()
                    st.success("Payment recorded successfully.")
                    st.rerun()
                else:
                    st.warning("Customer name and a payment amount are required.")
    with pay_tab2:
        conn = get_db_connection()
        payments_df = pd.read_sql("SELECT reference_type, reference_no, customer_name, phone, amount, payment_mode, payment_date, remarks, received_by FROM payments ORDER BY payment_date DESC;", conn)
        due_df = pd.read_sql("SELECT receipt_no, customer_name, phone, estimated_cost - advance_paid AS balance_due, status FROM service_entries WHERE estimated_cost > advance_paid AND status <> 'Cancelled' ORDER BY entry_date DESC;", conn)
        conn.close()
        c1, c2 = st.columns(2)
        c1.metric("Total Collections", f"₹ {payments_df['amount'].sum():,.2f}" if not payments_df.empty else "₹ 0.00")
        c2.metric("Open Service Balance", f"₹ {due_df['balance_due'].sum():,.2f}" if not due_df.empty else "₹ 0.00")
        st.markdown("#### Recent Collections")
        st.dataframe(payments_df, use_container_width=True, hide_index=True)
        st.markdown("#### Outstanding Service Balances")
        st.dataframe(due_df, use_container_width=True, hide_index=True)

# ---------------------------------------------------------
# CCTV & SOLAR PROJECTS
# ---------------------------------------------------------
elif choice == "📍 CCTV & Solar Projects":
    st.subheader("CCTV & Solar Installation Project Manager")
    project_tab1, project_tab2 = st.tabs(["Create Project", "Manage Projects"])
    with project_tab1:
        project_no = generate_project_no()
        st.info(f"New Project No: {project_no}")
        selected_project_customer = st.selectbox(
            "Use saved customer details (optional)",
            [None] + get_customer_profiles(),
            format_func=lambda c: "-- Enter new customer --" if c is None else f"{c['customer_name']} · {c['phone']}",
            key="project_customer_profile",
        )
        project_customer_profile = selected_project_customer or {}
        with st.form("project_form", clear_on_submit=True):
            p1, p2 = st.columns(2)
            project_type = p1.selectbox("Project Type", ["CCTV Installation", "Solar Installation", "Computer / Network Project"])
            project_customer = p1.text_input("Customer Name*", value=project_customer_profile.get("customer_name", ""))
            project_phone = p1.text_input("Phone Number*", value=project_customer_profile.get("phone", ""))
            project_assigned = p2.selectbox("Project Lead", ["Unassigned"] + get_active_staff())
            project_status = p2.selectbox("Project Status", ["Site Survey", "Quotation Sent", "Approved", "Material Ready", "Installation Scheduled", "Installation In Progress", "Completed", "AMC / Warranty"])
            project_value = p2.number_input("Project Value (₹)", min_value=0.0, step=1000.0)
            project_advance = p2.number_input("Advance Received (₹)", min_value=0.0, step=500.0)
            project_address = st.text_area("Site Address", value=project_customer_profile.get("address", ""))
            installation_date = st.date_input("Planned Installation Date", value=None)
            warranty_end = st.date_input("Warranty / AMC End Date", value=None)
            scope_details = st.text_area("Scope / Equipment Details (camera count, panel capacity, inverter, etc.)")
            materials_notes = st.text_area("Material Checklist / Installation Notes")
            if st.form_submit_button("Create Project", type="primary"):
                if project_customer and project_phone:
                    conn = get_db_connection()
                    cur = conn.cursor()
                    cur.execute('''INSERT INTO projects (project_no, project_type, customer_name, phone, site_address, status, assigned_to, project_value, advance_paid, installation_date, warranty_end, scope_details, materials_notes)
                                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s);''',
                                (project_no, project_type, project_customer, project_phone, project_address, project_status, "" if project_assigned == "Unassigned" else project_assigned, float(project_value), float(project_advance), installation_date, warranty_end, scope_details, materials_notes))
                    conn.commit()
                    cur.close()
                    conn.close()
                    save_customer(project_customer, project_phone, address=project_address)
                    st.success("Project created successfully.")
                    st.rerun()
                else:
                    st.warning("Customer name and phone number are required.")
    with project_tab2:
        conn = get_db_connection()
        projects_df = pd.read_sql("SELECT project_no, project_type, customer_name, phone, status, assigned_to, project_value, advance_paid, project_value - advance_paid AS balance_due, installation_date, warranty_end, created_at FROM projects ORDER BY created_at DESC;", conn)
        conn.close()
        st.dataframe(projects_df, use_container_width=True, hide_index=True)

# ---------------------------------------------------------
# STAFF MANAGEMENT
# ---------------------------------------------------------
elif choice == "👑 Staff Management":
    st.subheader("Staff Accounts & Roles")
    if st.session_state.get("staff_role") != "Admin":
        st.error("Only an Admin can manage staff accounts.")
    else:
        with st.form("staff_form", clear_on_submit=True):
            s1, s2 = st.columns(2)
            new_username = s1.text_input("Username")
            new_full_name = s1.text_input("Full Name")
            new_password = s1.text_input("Temporary Password", type="password")
            new_role = s2.selectbox("Role", ["Admin", "Sales", "Technician", "Accounts", "Manager"])
            if st.form_submit_button("Create Staff Account", type="primary"):
                if new_username and new_full_name and new_password:
                    try:
                        conn = get_db_connection()
                        cur = conn.cursor()
                        cur.execute("INSERT INTO staff_users (username, full_name, password_hash, role) VALUES (%s, %s, %s, %s);", (new_username.strip(), new_full_name, hash_password(new_password), new_role))
                        conn.commit()
                        cur.close()
                        conn.close()
                        st.success("Staff account created.")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Could not create staff account: {e}")
                else:
                    st.warning("Fill all fields to create an account.")
        conn = get_db_connection()
        staff_df = pd.read_sql("SELECT username, full_name, role, is_active, created_at FROM staff_users ORDER BY full_name;", conn)
        conn.close()
        st.dataframe(staff_df, use_container_width=True, hide_index=True)
        st.warning("Security: change the default admin password before using this application with staff.")
        if not staff_df.empty:
            with st.form("reset_staff_password"):
                reset_username = st.selectbox("Reset password for", staff_df["username"].tolist())
                reset_password = st.text_input("New Password", type="password")
                if st.form_submit_button("Reset Password"):
                    if reset_password:
                        conn = get_db_connection()
                        cur = conn.cursor()
                        cur.execute("UPDATE staff_users SET password_hash = %s WHERE username = %s;", (hash_password(reset_password), reset_username))
                        conn.commit()
                        cur.close()
                        conn.close()
                        st.success("Password updated successfully.")
                    else:
                        st.warning("Enter a new password.")

# ---------------------------------------------------------
# TAB 6: COMPLETE DATA REPORTS & SEARCH (ADDED GLOBAL SEARCH)
# ---------------------------------------------------------
elif choice == "📥 Data Reports & Search":
    st.subheader("📥 Service Tickets & Quotations Report with Search")

    search_query = st.text_input("🔍 Search Tickets / Quotations (Name, Phone Number, Receipt No, Quote No)", "")

    tab_rep1, tab_rep2 = st.tabs(["🛠️ Service Tickets Report", "📝 Quotations Report"])

    conn = get_db_connection()

    with tab_rep1:
        st.markdown("### Service Tickets Search & Report")
        query_srv = "SELECT * FROM service_entries"
        if search_query:
            query_srv += " WHERE customer_name ILIKE %s OR phone ILIKE %s OR receipt_no ILIKE %s OR item_description ILIKE %s"
            search_params_srv = tuple([f"%{search_query}%"] * 4)
        else:
            search_params_srv = None
        query_srv += " ORDER BY entry_date DESC;"
        
        df_srv = pd.read_sql(query_srv, conn, params=search_params_srv)
        st.dataframe(df_srv, use_container_width=True)

        excel_path = "Service_Report.xlsx"
        df_srv.to_excel(excel_path, index=False)
        with open(excel_path, "rb") as f:
            st.download_button("📥 Download Service Report Excel", f, file_name="Service_Report.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

    with tab_rep2:
        st.markdown("### Quotations Search & Report")
        query_q = "SELECT * FROM quotations"
        if search_query:
            query_q += " WHERE customer_name ILIKE %s OR phone ILIKE %s OR quote_no ILIKE %s OR category ILIKE %s"
            search_params_q = tuple([f"%{search_query}%"] * 4)
        else:
            search_params_q = None
        query_q += " ORDER BY quote_date DESC;"
        
        df_q = pd.read_sql(query_q, conn, params=search_params_q)
        st.dataframe(df_q, use_container_width=True)

        excel_path_q = "Quotations_Report.xlsx"
        df_q.to_excel(excel_path_q, index=False)
        with open(excel_path_q, "rb") as f:
            st.download_button("📥 Download Quotations Excel", f, file_name="Quotations_Report.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

    conn.close()
