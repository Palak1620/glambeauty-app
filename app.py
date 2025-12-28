import streamlit as st
import qrcode
from PIL import Image, ImageDraw
import io
import base64
import json
import os
from datetime import datetime
import csv
import pandas as pd
import sqlite3
import hashlib
import re

def safe_json_loads(s):
    """Safely parse a JSON string. Returns {} if invalid or empty."""
    try:
        if not s or not s.strip():
            return {}
        return json.loads(s)
    except Exception:
        return {}

# --- DATABASE & FILE PATHS ---
DB_PATH = "glambeauty.db"
PRODUCTS_JSON = "products.json"
THEME_JSON = "theme.json"

# --- DATABASE INITIALIZATION ---
def init_db():
    """Initialize SQLite database and create tables"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    c.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            order_id TEXT PRIMARY KEY,
            date TEXT,
            customer_name TEXT,
            email TEXT,
            phone TEXT,
            address TEXT,
            items_json TEXT,
            total INTEGER,
            payment_method TEXT,
            payment_details_json TEXT,
            status TEXT,
            user_id INTEGER
        )
    """)
    
    c.execute("PRAGMA table_info(orders)")
    columns = [column[1] for column in c.fetchall()]
    
    if 'payment_method' not in columns:
        try:
            c.execute("ALTER TABLE orders ADD COLUMN payment_method TEXT DEFAULT 'Cash on Delivery'")
            conn.commit()
        except sqlite3.OperationalError:
            pass
    
    if 'payment_details_json' not in columns:
        try:
            c.execute("ALTER TABLE orders ADD COLUMN payment_details_json TEXT DEFAULT '{}'")
            conn.commit()
        except sqlite3.OperationalError:
            pass
    
    if 'user_id' not in columns:
        try:
            c.execute("ALTER TABLE orders ADD COLUMN user_id INTEGER")
            conn.commit()
        except sqlite3.OperationalError:
            pass
    
    conn.commit()
    conn.close()

def init_users_db():
    """Initialize users table in database"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            full_name TEXT,
            phone TEXT,
            address TEXT,
            created_at TEXT,
            last_login TEXT,
            is_admin INTEGER DEFAULT 0
        )
    """)
    
    conn.commit()
    conn.close()

def hash_password(password):
    """Hash password using SHA-256"""
    return hashlib.sha256(password.encode()).hexdigest()

def validate_email(email):
    """Validate email format"""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None

def validate_phone(phone):
    """Validate phone number format"""
    clean_phone = phone.replace(" ", "").replace("-", "")
    pattern = r'^(\+91)?[6-9]\d{9}$'
    return re.match(pattern, clean_phone) is not None

def validate_name(name):
    """Validate name format"""
    if len(name) < 2:
        return False
    pattern = r'^[a-zA-Z\s]+$'
    return re.match(pattern, name) is not None

def validate_address(address):
    """Validate address format"""
    if len(address) < 10:
        return False
    return True

def validate_password(password):
    """Validate password strength"""
    if len(password) < 8:
        return False, "Password must be at least 8 characters long"
    if not re.search(r'[A-Z]', password):
        return False, "Password must contain at least one uppercase letter"
    if not re.search(r'[a-z]', password):
        return False, "Password must contain at least one lowercase letter"
    if not re.search(r'\d', password):
        return False, "Password must contain at least one digit"
    return True, "Password is strong"

def register_user(username, email, password, full_name, phone, address):
    """Register a new user"""
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        
        password_hash = hash_password(password)
        created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        c.execute("""
            INSERT INTO users (username, email, password_hash, full_name, phone, address, created_at, is_admin)
            VALUES (?, ?, ?, ?, ?, ?, ?, 0)
        """, (username, email, password_hash, full_name, phone, address, created_at))
        
        conn.commit()
        conn.close()
        return True, "Registration successful!"
    except sqlite3.IntegrityError as e:
        if 'username' in str(e):
            return False, "Username already exists"
        elif 'email' in str(e):
            return False, "Email already registered"
        return False, "Registration failed"
    except Exception as e:
        return False, f"Error: {str(e)}"

def login_user(username_or_email, password):
    """Authenticate user login"""
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        
        password_hash = hash_password(password)
        
        c.execute("""
            SELECT user_id, username, email, full_name, phone, address, is_admin
            FROM users 
            WHERE (username = ? OR email = ?) AND password_hash = ?
        """, (username_or_email, username_or_email, password_hash))
        
        user = c.fetchone()
        
        if user:
            c.execute("""
                UPDATE users 
                SET last_login = ? 
                WHERE user_id = ?
            """, (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), user[0]))
            conn.commit()
            
            user_data = {
                'user_id': user[0],
                'username': user[1],
                'email': user[2],
                'full_name': user[3],
                'phone': user[4],
                'address': user[5],
                'is_admin': user[6]
            }
            conn.close()
            return True, "Login successful!", user_data
        else:
            conn.close()
            return False, "Invalid username/email or password", None
    except Exception as e:
        return False, f"Error: {str(e)}", None

def update_user_profile(user_id, full_name, phone, address):
    """Update user profile information"""
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        
        c.execute("""
            UPDATE users 
            SET full_name = ?, phone = ?, address = ?
            WHERE user_id = ?
        """, (full_name, phone, address, user_id))
        
        conn.commit()
        conn.close()
        return True, "Profile updated successfully!"
    except Exception as e:
        return False, f"Error: {str(e)}"

def change_password(user_id, old_password, new_password):
    """Change user password"""
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        
        old_hash = hash_password(old_password)
        
        c.execute("SELECT password_hash FROM users WHERE user_id = ?", (user_id,))
        result = c.fetchone()
        
        if not result or result[0] != old_hash:
            conn.close()
            return False, "Current password is incorrect"
        
        new_hash = hash_password(new_password)
        c.execute("UPDATE users SET password_hash = ? WHERE user_id = ?", (new_hash, user_id))
        
        conn.commit()
        conn.close()
        return True, "Password changed successfully!"
    except Exception as e:
        return False, f"Error: {str(e)}"

def save_order_to_db(order):
    """Save order to database"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    items_json = json.dumps(order['items'])
    payment_details_json = json.dumps(order.get('payment_details', {}))
    
    c.execute("""
        INSERT INTO orders (
            order_id, date, customer_name, email, 
            phone, address, items_json, total, payment_method, payment_details_json, status, user_id
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        order['order_id'],
        order['order_date'],
        order['customer_name'],
        order['customer_email'],
        order['customer_phone'],
        order['customer_address'],
        items_json,
        order['total_amount'],
        order['payment_method'],
        payment_details_json,
        order['status'],
        order.get('user_id')
    ))
    
    conn.commit()
    conn.close()

def fetch_orders_from_db():
    """Fetch all orders from database"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT * FROM orders ORDER BY date DESC")
    rows = c.fetchall()
    conn.close()
    return rows

@st.cache_data
def load_products():
    """Load products from JSON file"""
    if os.path.exists(PRODUCTS_JSON):
        with open(PRODUCTS_JSON, 'r') as f:
            return json.load(f)
    else:
        default_products = [
            {
                "id": 1,
                "name": "Ruby Red Lipstick",
                "price": 899,
                "category": "Lips",
                "description": "Long-lasting matte finish lipstick with rich pigmentation. Perfect for all-day wear.",
                "image": "https://images.pexels.com/photos/14839822/pexels-photo-14839822.jpeg"
            },
            {
                "id": 2,
                "name": "Rose Petal Blush",
                "price": 749,
                "category": "Face",
                "description": "Silky smooth blush that gives you a natural rosy glow. Buildable formula.",
                "image": "https://images.pexels.com/photos/17354882/pexels-photo-17354882.jpeg"
            },
            {
                "id": 3,
                "name": "Midnight Black Eyeliner",
                "price": 599,
                "category": "Eyes",
                "description": "Waterproof gel eyeliner with precision applicator. Smudge-proof formula.",
                "image": "https://images.pexels.com/photos/2697787/pexels-photo-2697787.jpeg"
            },
            {
                "id": 4,
                "name": "Hydrating Face Cream",
                "price": 1299,
                "category": "Skincare",
                "description": "24-hour moisturizing cream with hyaluronic acid. Suitable for all skin types.",
                "image": "https://images.pexels.com/photos/10221859/pexels-photo-10221859.jpeg"
            },
            {
                "id": 5,
                "name": "Nude Matte Lipstick",
                "price": 899,
                "category": "Lips",
                "description": "Everyday nude shade with comfortable matte finish. Non-drying formula.",
                "image": "https://images.pexels.com/photos/28968376/pexels-photo-28968376.jpeg"
            }
        ]
        with open(PRODUCTS_JSON, "w") as f:
            json.dump(default_products, f, indent=2)
        return default_products

def save_products(products):
    """Save products to JSON file"""
    with open(PRODUCTS_JSON, "w") as f:
        json.dump(products, f, indent=2)
    load_products.clear()

@st.cache_data
def load_theme():
    """Load theme configuration"""
    if os.path.exists(THEME_JSON):
        with open(THEME_JSON, "r") as f:
            return json.load(f)
    return {
        "primary_color": "#8b4789",
        "background": "#ffffff",
        "card_shadow": "0 4px 6px rgba(0,0,0,0.1)"
    }

def get_app_url():
    """Get the current Streamlit app URL"""
    import os
    app_url = os.getenv('STREAMLIT_APP_URL')
    if app_url:
        return app_url
    if 'app_url' in st.session_state and st.session_state.app_url:
        return st.session_state.app_url
    return "http://localhost:8501"

def generate_qr_code(data, product_name):
    """Generate QR code without center overlay"""
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_H,
        box_size=10,
        border=4,
    )
    qr.add_data(data)
    qr.make(fit=True)
    img = qr.make_image(fill_color="#8b4789", back_color="white")
    img = img.convert('RGB')
    return img

def add_to_cart(product):
    """Add product to cart"""
    product_id = product['id']
    st.session_state.cart.append(product)
    if product_id in st.session_state.cart_count:
        st.session_state.cart_count[product_id] += 1
    else:
        st.session_state.cart_count[product_id] = 1
    st.session_state.cart_update_trigger += 1
    st.success(f"✅ {product['name']} added to cart!")
    st.rerun()

def remove_from_cart(index):
    """Remove product from cart"""
    product = st.session_state.cart[index]
    product_id = product['id']
    if product_id in st.session_state.cart_count:
        st.session_state.cart_count[product_id] -= 1
        if st.session_state.cart_count[product_id] <= 0:
            del st.session_state.cart_count[product_id]
    st.session_state.cart.pop(index)
    st.session_state.cart_update_trigger += 1
    st.rerun()

def save_order(customer_info, cart_items, total_amount, payment_method, payment_details=None, user_id=None):
    """Save order to database"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM orders")
    order_count = c.fetchone()[0]
    conn.close()
    
    order = {
        'order_id': f"ORD{order_count + 1:04d}",
        'order_date': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        'customer_name': customer_info['name'],
        'customer_email': customer_info['email'],
        'customer_phone': customer_info['phone'],
        'customer_address': customer_info['address'],
        'items': cart_items.copy(),
        'total_amount': total_amount,
        'payment_method': payment_method,
        'payment_details': payment_details if payment_details else {},
        'status': 'Confirmed',
        'user_id': user_id
    }
    save_order_to_db(order)
    return order['order_id']

def export_orders_csv():
    """Export orders to CSV format"""
    rows = fetch_orders_from_db()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['Order ID', 'Date', 'Customer Name', 'Email', 'Phone', 'Address', 'Items', 'Total', 'Payment Method', 'Status'])
    
    for row in rows:
        if len(row) >= 11:
            order_id, date, name, email, phone, address, items_json, total, payment_method, payment_details_json, status = row[:11]
        else:
            order_id, date, name, email, phone, address, items_json, total, status = row[:9]
            payment_method = "Cash on Delivery"
        
        items = safe_json_loads(items_json)
        items_str = "; ".join([f"{item.get('name')} (₹{item.get('price')})" for item in items])
        writer.writerow([order_id, date, name, email, phone, address, items_str, f"₹{total}", payment_method, status])
    
    return output.getvalue()

# Initialize database and load data
init_db()
init_users_db()
PRODUCTS = load_products()
THEME = load_theme()

# --- PAGE CONFIG & ENHANCED CSS ---
st.set_page_config(
    page_title="GlamBeauty - Cosmetics Store",
    page_icon="💄",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
    <style>
    .main {
        background: linear-gradient(135deg, #fef9f3 0%, #fef3f8 25%, #f3f9fe 50%, #fef6f0 75%, #f8f3fe 100%);
        padding: 1rem 2rem;
    }
    
    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, #e8f4f8 0%, #f0e8f8 50%, #f8f0e8 100%);
        border-right: 4px solid #b8a8d8;
    }
    
    .product-card {
        background: #ffffff !important;
        border: 3px solid #d4a8c8 !important;
        border-radius: 25px !important;
        padding: 30px !important;
        margin: 20px 10px !important;
        box-shadow: 0 10px 30px rgba(139, 71, 137, 0.15) !important;
        transition: all 0.4s ease !important;
    }
    
    .product-card:hover {
        transform: translateY(-8px) !important;
        box-shadow: 0 15px 40px rgba(139, 71, 137, 0.25) !important;
        border-color: #b89cc8 !important;
    }
    
    .price-tag {
        font-size: 28px;
        color: #ffffff;
        font-weight: 900;
        background: linear-gradient(135deg, #9b5d9d 0%, #7a4a7c 100%);
        padding: 10px 24px;
        border-radius: 15px;
        display: inline-block;
        border: 3px solid #b89cc8;
        box-shadow: 0 6px 15px rgba(139, 71, 137, 0.3);
    }
    
    .header-title {
        text-align: center;
        background: linear-gradient(135deg, #8b4789 0%, #6b3669 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        font-size: 52px;
        font-weight: bold;
        margin-bottom: 10px;
    }
    
    .subtitle {
        text-align: center;
        color: #7a4a7c;
        font-size: 20px;
        margin-bottom: 30px;
        font-weight: 600;
    }
    
    .stButton > button {
        background: linear-gradient(135deg, #8b4789 0%, #9b5d9d 100%) !important;
        color: white !important;
        border: 2px solid #b89cc8 !important;
        border-radius: 12px !important;
        padding: 12px 24px !important;
        font-weight: 700 !important;
        box-shadow: 0 4px 12px rgba(139, 71, 137, 0.3) !important;
        transition: all 0.3s ease !important;
    }
    
    .stButton > button:hover {
        background: linear-gradient(135deg, #9b5d9d 0%, #8b4789 100%) !important;
        transform: translateY(-2px) !important;
        box-shadow: 0 6px 16px rgba(139, 71, 137, 0.4) !important;
    }
    
    .stAlert {
        border-radius: 15px !important;
        border-left: 5px solid #8b4789 !important;
        background: #ffffff !important;
        box-shadow: 0 4px 12px rgba(0,0,0,0.08) !important;
    }
    
    .stTabs [data-baseweb="tab-list"] {
        background: #ffffff;
        border-radius: 15px;
        padding: 10px;
        border: 2px solid #d4a8c8;
    }
    
    .stTabs [data-baseweb="tab"] {
        background: #fef5f9;
        border-radius: 10px;
        color: #8b4789;
        font-weight: 600;
    }
    
    .stTabs [aria-selected="true"] {
        background: linear-gradient(135deg, #8b4789 0%, #9b5d9d 100%);
        color: white !important;
    }
    
    .stTextInput > div > div > input,
    .stTextArea > div > div > textarea,
    .stSelectbox > div > div > select {
        background: #ffffff !important;
        border: 2px solid #d4a8c8 !important;
        border-radius: 12px !important;
        padding: 12px !important;
        color: #333 !important;
    }
    
    .stTextInput > div > div > input:focus,
    .stTextArea > div > div > textarea:focus {
        border-color: #8b4789 !important;
        box-shadow: 0 0 0 2px rgba(139, 71, 137, 0.2) !important;
    }
    
    .streamlit-expanderHeader {
        background: #ffffff !important;
        border: 2px solid #d4a8c8 !important;
        border-radius: 12px !important;
        color: #8b4789 !important;
        font-weight: 600 !important;
    }
    
    hr {
        border-color: #d4a8c8 !important;
        margin: 30px 0 !important;
    }
    
    .cart-item-box {
        background: #ffffff;
        border: 2px solid #d4a8c8;
        border-radius: 15px;
        padding: 20px;
        margin: 15px 0;
        box-shadow: 0 4px 12px rgba(139, 71, 137, 0.1);
    }
    </style>
""", unsafe_allow_html=True)

# --- SESSION STATE ---
if 'cart' not in st.session_state:
    st.session_state.cart = []
if 'page' not in st.session_state:
    st.session_state.page = 'login'
if 'selected_product' not in st.session_state:
    st.session_state.selected_product = None
if 'customer_info' not in st.session_state:
    st.session_state.customer_info = {}
if 'cart_count' not in st.session_state:
    st.session_state.cart_count = {}
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
if 'user' not in st.session_state:
    st.session_state.user = None
if 'cart_update_trigger' not in st.session_state:
    st.session_state.cart_update_trigger = 0
if 'checkout_as_guest' not in st.session_state:
    st.session_state.checkout_as_guest = False
if 'app_url' not in st.session_state:
    st.session_state.app_url = None

# --- HANDLE QR CODE ---
query_params = st.query_params
if 'product_id' in query_params:
    try:
        product_id = int(query_params['product_id'])
        if any(p['id'] == product_id for p in PRODUCTS):
            st.session_state.selected_product = product_id
            st.session_state.page = 'product'
        st.query_params.clear()
    except (ValueError, TypeError):
        pass

# --- UI COMPONENTS ---
def display_product_card(product, col):
    """Display a product card"""
    with col:
        st.markdown(f"""
            <div class="product-card">
                <div style='text-align: center; margin-bottom: 15px;'>
                    <h3 style="color: #8b4789; margin-bottom: 8px;">{product['name']}</h3>
                    <span style="background: #e8d5f2; padding: 5px 15px; border-radius: 20px; color: #8b4789; font-size: 12px; font-weight: 600;">
                        {product['category']}
                    </span>
                </div>
            </div>
        """, unsafe_allow_html=True)
        
        st.markdown(f"""
            <div style='padding: 0 10px;'>
                <img src='{product['image']}' style='width: 100%; height: 280px; object-fit: contain; border-radius: 15px; border: 2px solid #d4a8c8; background: #fefefe;'>
            </div>
        """, unsafe_allow_html=True)
        
        st.markdown(f"<div style='text-align: center; margin: 15px 0;'><span class='price-tag'>₹{product['price']}</span></div>", unsafe_allow_html=True)
        
        desc = product['description'][:80] + ("..." if len(product['description']) > 80 else "")
        st.markdown(f"<p style='text-align: center; color: #666; font-size: 14px; padding: 0 10px;'>{desc}</p>", unsafe_allow_html=True)
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("👁️ View", key=f"view_{product['id']}", use_container_width=True):
                st.session_state.selected_product = product['id']
                st.session_state.page = 'product'
                st.rerun()
        with col2:
            if st.button("🛒 Add", key=f"add_{product['id']}", use_container_width=True):
                add_to_cart(product)

def display_user_orders(user_id, limit=None):
    """Display orders for specific user"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    if limit:
        c.execute("SELECT * FROM orders WHERE user_id = ? ORDER BY date DESC LIMIT ?", (user_id, limit))
    else:
        c.execute("SELECT * FROM orders WHERE user_id = ? ORDER BY date DESC", (user_id,))
    
    rows = c.fetchall()
    conn.close()
    
    if not rows:
        st.info("You haven't placed any orders yet. Start shopping!")
        if st.button("Start Shopping", key="start_shop_orders"):
            st.session_state.page = 'home'
            st.rerun()
        return
    
    st.write(f"### Total Orders: {len(rows)}")
    
    for row in rows:
        if len(row) >= 11:
            order_id, date, name, email, phone, address, items_json, total, payment_method, payment_details_json, status = row[:11]
            payment_details = safe_json_loads(payment_details_json)
        else:
            order_id, date, name, email, phone, address, items_json, total, status = row[:9]
            payment_method = "Cash on Delivery"
            payment_details = {}
        
        items = safe_json_loads(items_json)
        
        with st.expander(f"🛍️ Order #{order_id} - {date} - ₹{total} - {status}"):
            col1, col2 = st.columns(2)
            
            with col1:
                st.write("#### 📍 Delivery Details")
                st.write(f"**Address:** {address}")
                st.write(f"**Phone:** {phone}")
            
            with col2:
                st.write("#### 💳 Payment Details")
                st.write(f"**Status:** {status}")
                st.write(f"**Payment Method:** {payment_method}")
            
            st.divider()
            st.write("#### 🛍️ Order Items:")
            for item in items:
                c1, c2, c3 = st.columns([2, 4, 2])
                with c1:
                    st.image(item['image'], width=80)
                with c2:
                    st.write(f"**{item['name']}**")
                    st.write(f"{item['category']}")
                with c3:
                    st.write(f"₹{item['price']}")

# --- PAGE FUNCTIONS ---
def login_page():
    """Display login/registration page"""
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col2:
        st.markdown("""
            <div style='padding: 40px; background: #ffffff; border-radius: 20px; box-shadow: 0 8px 24px rgba(0,0,0,0.08); border: 3px solid #d4a8c8;'>
                <h1 style='text-align: center; color: #8b4789; font-size: 36px; margin-bottom: 10px;'>💄 GlamBeauty</h1>
                <p style='text-align: center; color: #666; margin-bottom: 30px;'>Welcome to Premium Cosmetics</p>
            </div>
        """, unsafe_allow_html=True)
        
        st.write("")
        tab1, tab2 = st.tabs(["🔐 Login", "📝 Register"])
        
        with tab1:
            st.write("### Sign In to Your Account")
            
            with st.form("login_form"):
                username_or_email = st.text_input("Username or Email *", placeholder="Enter your username or email")
                password = st.text_input("Password *", type="password", placeholder="Enter your password")
                
                col_a, col_b = st.columns(2)
                with col_a:
                    login_btn = st.form_submit_button("🔐 Login", use_container_width=True, type="primary")
                with col_b:
                    guest_btn = st.form_submit_button("👤 Guest", use_container_width=True)
            
            if login_btn:
                if not username_or_email or not password:
                    st.error("⚠️ Please fill in all fields")
                else:
                    success, message, user_data = login_user(username_or_email, password)
                    if success:
                        st.session_state.logged_in = True
                        st.session_state.user = user_data
                        if user_data['is_admin']:
                            st.session_state.page = 'admin_dashboard'
                        else:
                            st.session_state.page = 'customer_dashboard'
                        st.success(f"✅ {message}")
                        st.balloons()
                        st.rerun()
                    else:
                        st.error(f"❌ {message}")
            
            if guest_btn:
                st.session_state.logged_in = False
                st.session_state.user = None
                st.session_state.page = 'home'
                st.info("👤 Continuing as guest")
                st.rerun()
        
        with tab2:
            st.write("### Create Your Account")
            
            with st.form("register_form"):
                reg_username = st.text_input("Username *", placeholder="Choose a unique username", max_chars=20)
                reg_email = st.text_input("Email *", placeholder="your.email@example.com")
                reg_full_name = st.text_input("Full Name *", placeholder="Enter your full name")
                reg_phone = st.text_input("Phone Number *", placeholder="+91 XXXXX XXXXX")
                reg_address = st.text_area("Address", placeholder="Your delivery address (optional)")
                reg_password = st.text_input("Password *", type="password", placeholder="Create a strong password")
                reg_confirm_password = st.text_input("Confirm Password *", type="password", placeholder="Re-enter your password")
                agree_terms = st.checkbox("I agree to the Terms & Conditions *")
                register_btn = st.form_submit_button("✨ Create Account", use_container_width=True, type="primary")
            
            if register_btn:
                errors = []
                if not all([reg_username, reg_email, reg_full_name, reg_phone, reg_password, reg_confirm_password]):
                    errors.append("Please fill in all required fields")
                if len(reg_username) < 3:
                    errors.append("Username must be at least 3 characters")
                if not validate_email(reg_email):
                    errors.append("Invalid email format")
                if not validate_phone(reg_phone):
                    errors.append("Invalid phone number")
                is_valid_password, password_message = validate_password(reg_password)
                if not is_valid_password:
                    errors.append(password_message)
                if reg_password != reg_confirm_password:
                    errors.append("Passwords do not match")
                if not agree_terms:
                    errors.append("You must agree to Terms & Conditions")
                
                if errors:
                    for error in errors:
                        st.error(f"⚠️ {error}")
                else:
                    success, message = register_user(reg_username, reg_email, reg_password, reg_full_name, reg_phone, reg_address)
                    if success:
                        st.success(f"✅ {message}")
                        st.balloons()
                        st.info("👉 Please switch to Login tab")
                    else:
                        st.error(f"❌ {message}")

def home_page():
    """Display home page"""
    st.markdown(f"<h1 class='header-title'>💄 GlamBeauty</h1>", unsafe_allow_html=True)
    st.markdown(f"<p class='subtitle'>✨ Premium Cosmetics & Skincare Collection ✨</p>", unsafe_allow_html=True)
    
    if st.session_state.get('logged_in') and st.session_state.get('user'):
        st.markdown(f"""
            <div style='background: linear-gradient(135deg, #b8e6d5 0%, #95d5b2 100%); padding: 20px; border-radius: 15px; margin-bottom: 20px; text-align: center; border: 3px solid #74c69d;'>
                <h3 style='color: #1b4332; margin: 0;'>👋 Welcome back, {st.session_state.user['full_name']}!</h3>
            </div>
        """, unsafe_allow_html=True)
        
        col1, col2, col3 = st.columns([2, 2, 1])
        with col3:
            if st.session_state.user.get('is_admin'):
                if st.button("🧑‍💼 Dashboard", use_container_width=True):
                    st.session_state.page = 'admin_dashboard'
                    st.rerun()
            else:
                if st.button("👤 Dashboard", use_container_width=True):
                    st.session_state.page = 'customer_dashboard'
                    st.rerun()
    
    categories = ["All"] + sorted(list(set(p['category'] for p in PRODUCTS)))
    selected_category = st.selectbox("🎨 Select Category", categories)
    filtered = PRODUCTS if selected_category == "All" else [p for p in PRODUCTS if p['category'] == selected_category]
    
    st.markdown(f"<h2 style='color: #8b4789; text-align: center; margin: 30px 0;'>🛍️ {len(filtered)} Products Available</h2>", unsafe_allow_html=True)
    
    cols_per_row = 3
    for i in range(0, len(filtered), cols_per_row):
        cols = st.columns(cols_per_row)
        for j in range(cols_per_row):
            if i + j < len(filtered):
                display_product_card(filtered[i + j], cols[j])

def cart_page():
    """Display shopping cart"""
    st.markdown(f"<h1 style='color: #8b4789; text-align: center;'>🛒 Shopping Cart</h1>", unsafe_allow_html=True)
    
    if not st.session_state.cart:
        st.markdown("""
            <div style='background: #ffffff; padding: 40px; border-radius: 20px; text-align: center; border: 3px solid #d4a8c8; margin: 40px 0;'>
                <h2 style='color: #8b4789;'>Your cart is empty! 🛍️</h2>
                <p style='color: #666; font-size: 18px;'>Start adding products</p>
            </div>
        """, unsafe_allow_html=True)
        if st.button("🌟 Start Shopping", use_container_width=True):
            st.session_state.page = 'home'
            st.rerun()
        return
    
    total = 0
    for idx, item in enumerate(st.session_state.cart):
        st.markdown('<div class="cart-item-box">', unsafe_allow_html=True)
        
        col1, col2, col3, col4 = st.columns([2, 3, 2, 1])
        with col1:
            st.image(item['image'], width=120)
        with col2:
            st.markdown(f"<h3 style='color: #8b4789;'>{item['name']}</h3>", unsafe_allow_html=True)
            st.markdown(f"<p style='color: #666;'>{item['category']}</p>", unsafe_allow_html=True)
        with col3:
            st.markdown(f"<div class='price-tag'>₹{item['price']}</div>", unsafe_allow_html=True)
        with col4:
            if st.button("🗑️", key=f"remove_{idx}"):
                remove_from_cart(idx)
        
        st.markdown('</div>', unsafe_allow_html=True)
        total += item['price']
    
    col1, col2 = st.columns(2)
    with col1:
        st.markdown(f"""
            <div style='background: #fff; padding: 25px; border-radius: 15px; text-align: center; border: 3px solid #d4a8c8;'>
                <h4 style='color: #8b4789;'>Total Items</h4>
                <h1 style='color: #8b4789;'>{len(st.session_state.cart)}</h1>
            </div>
        """, unsafe_allow_html=True)
    
    with col2:
        st.markdown(f"""
            <div style='background: #fff; padding: 25px; border-radius: 15px; text-align: center; border: 3px solid #b8e6d5;'>
                <h4 style='color: #2d6a4f;'>Total Amount</h4>
                <h1 style='color: #8b4789;'>₹{total}</h1>
            </div>
        """, unsafe_allow_html=True)
    
    st.divider()
    
    if not st.session_state.get('logged_in'):
        st.warning("⚠️ Please login to place an order")
        col1, col2 = st.columns(2)
        with col1:
            if st.button("🔐 Login", use_container_width=True, type="primary"):
                st.session_state.page = 'login'
                st.rerun()
        with col2:
            if st.button("Continue as Guest", use_container_width=True):
                st.session_state.checkout_as_guest = True
    else:
        st.session_state.checkout_as_guest = False
    
    if st.session_state.get('logged_in') or st.session_state.get('checkout_as_guest'):
        st.write("### 📝 Customer Information")
        
        default_name = ""
        default_email = ""
        default_phone = ""
        default_address = ""
        
        if st.session_state.get('logged_in') and st.session_state.get('user'):
            user = st.session_state.user
            default_name = user.get('full_name', '')
            default_email = user.get('email', '')
            default_phone = user.get('phone', '')
            default_address = user.get('address', '')
        
        with st.form("checkout_form"):
            name = st.text_input("Full Name *", value=default_name)
            email = st.text_input("Email *", value=default_email)
            phone = st.text_input("Phone *", value=default_phone)
            address = st.text_area("Address *", value=default_address)
            
            st.divider()
            payment_method = st.radio("💳 Payment Method", ["Cash on Delivery", "UPI", "Credit/Debit Card"], horizontal=True)
            
            payment_details = {}
            
            if payment_method == "UPI":
                upi_id = st.text_input("UPI ID *", placeholder="yourname@paytm")
                payment_details = {'upi_id': upi_id}
            elif payment_method == "Credit/Debit Card":
                card_number = st.text_input("Card Number *", placeholder="1234 5678 9012 3456")
                col1, col2 = st.columns(2)
                with col1:
                    expiry = st.text_input("Expiry *", placeholder="MM/YY")
                with col2:
                    cvv = st.text_input("CVV *", placeholder="123", type="password")
                payment_details = {'card_last4': card_number[-4:] if len(card_number) >= 4 else "****"}
            
            col1, col2 = st.columns(2)
            with col1:
                continue_shop = st.form_submit_button("Continue Shopping", use_container_width=True)
            with col2:
                place_order = st.form_submit_button("🎉 Place Order", use_container_width=True, type="primary")
        
        if continue_shop:
            st.session_state.page = 'home'
            st.rerun()
        
        if place_order:
            if not all([name, email, phone, address]):
                st.error("⚠️ Please fill all fields")
            else:
                customer_info = {'name': name, 'email': email, 'phone': phone, 'address': address}
                user_id = st.session_state.user['user_id'] if st.session_state.get('logged_in') else None
                order_id = save_order(customer_info, st.session_state.cart, total, payment_method, payment_details, user_id)
                st.session_state.cart = []
                st.session_state.cart_count = {}
                st.balloons()
                st.success(f"✅ Order #{order_id} placed successfully!")
                st.info(f"📧 Confirmation sent to {email}")

def product_page():
    """Display product detail page"""
    product = next((p for p in PRODUCTS if p['id'] == st.session_state.selected_product), None)
    if not product:
        st.error("Product not found!")
        if st.button("← Back to Home"):
            st.session_state.page = 'home'
            st.rerun()
        return
    
    if st.button("← Back to Home"):
        st.session_state.page = 'home'
        st.rerun()
    
    st.markdown(f"<h1 style='color: #8b4789;'>{product['name']}</h1>", unsafe_allow_html=True)
    
    col1, col2 = st.columns([1, 1])
    with col1:
        st.image(product['image'], use_container_width=True)
        st.markdown(f"<h2 class='price-tag'>₹{product['price']}</h2>", unsafe_allow_html=True)
        st.write(f"**Category:** {product['category']}")
        st.write(f"**Description:** {product['description']}")
        if st.button("🛒 Add to Cart", use_container_width=True):
            add_to_cart(product)
    
    with col2:
        st.write("### 📱 Product QR Code")
        base_url = get_app_url()
        product_url = f"{base_url}?product_id={product['id']}"
        qr_img = generate_qr_code(product_url, product['name'])
        st.image(qr_img, width=300)

def customer_dashboard():
    """Display customer dashboard"""
    if not st.session_state.get('logged_in'):
        st.warning("⚠️ Please login")
        if st.button("Go to Login"):
            st.session_state.page = 'login'
            st.rerun()
        return
    
    user = st.session_state.user
    st.markdown(f"<h1 style='color: #8b4789;'>👤 Customer Dashboard</h1>", unsafe_allow_html=True)
    st.write(f"### Welcome, {user['full_name']}! 💖")
    
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT COUNT(*), SUM(total) FROM orders WHERE user_id = ?", (user['user_id'],))
    stats = c.fetchone()
    total_orders = stats[0] if stats[0] else 0
    total_spent = stats[1] if stats[1] else 0
    conn.close()
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.markdown(f"<div style='background: #fff; padding: 20px; border-radius: 15px; border: 3px solid #d4a8c8; text-align: center;'><h4 style='color: #8b4789;'>Total Orders</h4><h2>{total_orders}</h2></div>", unsafe_allow_html=True)
    with col2:
        st.markdown(f"<div style='background: #fff; padding: 20px; border-radius: 15px; border: 3px solid #b8e6d5; text-align: center;'><h4 style='color: #2d6a4f;'>Total Spent</h4><h2>₹{total_spent}</h2></div>", unsafe_allow_html=True)
    with col3:
        st.markdown(f"<div style='background: #fff; padding: 20px; border-radius: 15px; border: 3px solid #cce3ff; text-align: center;'><h4 style='color: #1e6091;'>Cart Items</h4><h2>{len(st.session_state.cart)}</h2></div>", unsafe_allow_html=True)
    with col4:
        st.markdown(f"<div style='background: #fff; padding: 20px; border-radius: 15px; border: 3px solid #f0e6f6; text-align: center;'><h4 style='color: #8b4789;'>Member</h4><p>{user['username']}</p></div>", unsafe_allow_html=True)
    
    st.divider()
    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button("🛍️ Shop Now", use_container_width=True):
            st.session_state.page = 'home'
            st.rerun()
    with col2:
        if st.button("🛒 View Cart", use_container_width=True):
            st.session_state.page = 'cart'
            st.rerun()
    with col3:
        if st.button("📦 My Orders", use_container_width=True):
            st.session_state.page = 'profile'
            st.rerun()
    
    st.divider()
    st.write("### 📦 Recent Orders")
    display_user_orders(user['user_id'], limit=5)

def admin_dashboard():
    """Display admin dashboard"""
    if not st.session_state.get('logged_in') or not st.session_state.user.get('is_admin'):
        st.error("🚫 Access Denied")
        if st.button("← Back"):
            st.session_state.page = 'home'
            st.rerun()
        return
    
    st.markdown("<h1 style='color: #8b4789;'>🧑‍💼 Admin Dashboard</h1>", unsafe_allow_html=True)
    st.success(f"Welcome, Admin {st.session_state.user['full_name']}!")

def profile_page():
    """Display user profile"""
    if not st.session_state.get('logged_in'):
        st.warning("⚠️ Please login")
        if st.button("Go to Login"):
            st.session_state.page = 'login'
            st.rerun()
        return
    
    user = st.session_state.user
    st.markdown("<h1 style='color: #8b4789;'>👤 My Profile</h1>", unsafe_allow_html=True)
    
    tab1, tab2, tab3 = st.tabs(["📝 Profile", "🔐 Password", "📦 Orders"])
    
    with tab1:
        with st.form("profile_form"):
            full_name = st.text_input("Full Name", value=user.get('full_name', ''))
            phone = st.text_input("Phone", value=user.get('phone', ''))
            address = st.text_area("Address", value=user.get('address', ''))
            if st.form_submit_button("💾 Save", type="primary"):
                success, msg = update_user_profile(user['user_id'], full_name, phone, address)
                if success:
                    st.session_state.user['full_name'] = full_name
                    st.session_state.user['phone'] = phone
                    st.session_state.user['address'] = address
                    st.success(msg)
                    st.rerun()
                else:
                    st.error(msg)
    
    with tab2:
        with st.form("password_form"):
            old_pwd = st.text_input("Current Password", type="password")
            new_pwd = st.text_input("New Password", type="password")
            confirm_pwd = st.text_input("Confirm Password", type="password")
            if st.form_submit_button("🔒 Change Password", type="primary"):
                if new_pwd != confirm_pwd:
                    st.error("Passwords don't match")
                else:
                    success, msg = change_password(user['user_id'], old_pwd, new_pwd)
                    if success:
                        st.success(msg)
                    else:
                        st.error(msg)
    
    with tab3:
        display_user_orders(user['user_id'])

# --- NAVIGATION ---
with st.sidebar:
    st.markdown("<h2 style='color: #8b4789;'>💄 GlamBeauty</h2>", unsafe_allow_html=True)
    
    cart_count = len(st.session_state.cart)
    
    if st.button(f"🏠 Home", use_container_width=True):
        st.session_state.page = 'home'
        st.rerun()
    
    if st.button(f"🛒 Cart ({cart_count})", use_container_width=True):
        st.session_state.page = 'cart'
        st.rerun()
    
    if st.session_state.get('logged_in'):
        if st.button("👤 Profile", use_container_width=True):
            st.session_state.page = 'profile'
            st.rerun()
        
        if st.button("🚪 Logout", use_container_width=True):
            st.session_state.logged_in = False
            st.session_state.user = None
            st.session_state.page = 'login'
            st.rerun()
    else:
        if st.button("🔐 Login", use_container_width=True):
            st.session_state.page = 'login'
            st.rerun()

# --- MAIN ROUTING ---
page = st.session_state.page

if page == 'login':
    login_page()
elif page == 'home':
    home_page()
elif page == 'cart':
    cart_page()
elif page == 'product':
    product_page()
elif page == 'customer_dashboard':
    customer_dashboard()
elif page == 'admin_dashboard':
    admin_dashboard()
elif page == 'profile':
    profile_page()
else:
    login_page()
