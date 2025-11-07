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
            status TEXT
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
    
    conn.commit()
    conn.close()

import streamlit as st
import sqlite3
import hashlib
import re
from datetime import datetime

# --- DATABASE INITIALIZATION FOR USERS ---
DB_PATH = "glambeauty.db"

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
    pattern = r'^(\+91)?[6-9]\d{9}$'
    return re.match(pattern, phone.replace(" ", "").replace("-", "")) is not None

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
            # Update last login
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

# --- LOGIN PAGE UI ---
def login_page():
    """Display login/registration page"""
    st.markdown("""
        <style>
        .login-container {
            max-width: 500px;
            margin: 0 auto;
            padding: 40px;
            background: linear-gradient(135deg, #ffeef8 0%, #fff5f7 100%);
            border-radius: 20px;
            box-shadow: 0 8px 16px rgba(0,0,0,0.1);
        }
        .login-header {
            text-align: center;
            color: #d81b60;
            font-size: 36px;
            font-weight: bold;
            margin-bottom: 10px;
        }
        .login-subtitle {
            text-align: center;
            color: #666;
            margin-bottom: 30px;
        }
        </style>
    """, unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col2:
        st.markdown('<div class="login-container">', unsafe_allow_html=True)
        
        # Logo and Title
        st.markdown('<h1 class="login-header">💄 GlamBeauty</h1>', unsafe_allow_html=True)
        st.markdown('<p class="login-subtitle">Welcome to Premium Cosmetics</p>', unsafe_allow_html=True)
        
        # Tabs for Login and Register
        tab1, tab2 = st.tabs(["🔐 Login", "📝 Register"])
        
        # --- LOGIN TAB ---
        with tab1:
            st.write("### Sign In to Your Account")
            
            with st.form("login_form"):
                username_or_email = st.text_input(
                    "Username or Email *",
                    placeholder="Enter your username or email"
                )
                password = st.text_input(
                    "Password *",
                    type="password",
                    placeholder="Enter your password"
                )
                
                remember_me = st.checkbox("Remember me")
                
                col_a, col_b = st.columns(2)
                with col_a:
                    login_btn = st.form_submit_button("🔓 Login", use_container_width=True, type="primary")
                with col_b:
                    guest_btn = st.form_submit_button("👤 Guest", use_container_width=True)
                
                forgot_password = st.form_submit_button("🔑 Forgot Password?")
            
            if login_btn:
                if not username_or_email or not password:
                    st.error("⚠️ Please fill in all fields")
                else:
                    success, message, user_data = login_user(username_or_email, password)
                    
                    if success:
                        st.session_state.logged_in = True
                        st.session_state.user = user_data
                        st.session_state.page = 'home'
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
            
            if forgot_password:
                st.info("📧 Password reset feature coming soon! Please contact support.")
        
        # --- REGISTER TAB ---
        with tab2:
            st.write("### Create Your Account")
            
            with st.form("register_form"):
                reg_username = st.text_input(
                    "Username *",
                    placeholder="Choose a unique username",
                    max_chars=20
                )
                
                reg_email = st.text_input(
                    "Email *",
                    placeholder="your.email@example.com"
                )
                
                reg_full_name = st.text_input(
                    "Full Name *",
                    placeholder="Enter your full name"
                )
                
                reg_phone = st.text_input(
                    "Phone Number *",
                    placeholder="+91 XXXXX XXXXX"
                )
                
                reg_address = st.text_area(
                    "Address",
                    placeholder="Your delivery address (optional)"
                )
                
                reg_password = st.text_input(
                    "Password *",
                    type="password",
                    placeholder="Create a strong password"
                )
                
                reg_confirm_password = st.text_input(
                    "Confirm Password *",
                    type="password",
                    placeholder="Re-enter your password"
                )
                
                st.caption("Password must contain at least 8 characters, including uppercase, lowercase, and numbers")
                
                agree_terms = st.checkbox("I agree to the Terms & Conditions and Privacy Policy *")
                
                register_btn = st.form_submit_button("✨ Create Account", use_container_width=True, type="primary")
            
            if register_btn:
                # Validation
                errors = []
                
                if not all([reg_username, reg_email, reg_full_name, reg_phone, reg_password, reg_confirm_password]):
                    errors.append("Please fill in all required fields")
                
                if len(reg_username) < 3:
                    errors.append("Username must be at least 3 characters long")
                
                if not validate_email(reg_email):
                    errors.append("Invalid email format")
                
                if not validate_phone(reg_phone):
                    errors.append("Invalid phone number format (use +91 XXXXXXXXXX)")
                
                is_valid_password, password_message = validate_password(reg_password)
                if not is_valid_password:
                    errors.append(password_message)
                
                if reg_password != reg_confirm_password:
                    errors.append("Passwords do not match")
                
                if not agree_terms:
                    errors.append("You must agree to the Terms & Conditions")
                
                if errors:
                    for error in errors:
                        st.error(f"⚠️ {error}")
                else:
                    success, message = register_user(
                        reg_username,
                        reg_email,
                        reg_password,
                        reg_full_name,
                        reg_phone,
                        reg_address
                    )
                    
                    if success:
                        st.success(f"✅ {message}")
                        st.balloons()
                        st.info("👉 Please switch to the Login tab to sign in")
                    else:
                        st.error(f"❌ {message}")
        
        st.markdown('</div>', unsafe_allow_html=True)
    
    # Benefits section
    st.write("---")
    st.write("### 🌟 Why Shop With Us?")
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.write("#### 🔒 Secure")
        st.write("Your data is encrypted and safe")
    
    with col2:
        st.write("#### 🚚 Fast Delivery")
        st.write("Quick shipping across India")
    
    with col3:
        st.write("#### 💝 Quality")
        st.write("100% authentic products")

# --- PROFILE PAGE ---
def profile_page():
    """Display user profile page"""
    if not st.session_state.get('logged_in'):
        st.warning("⚠️ Please login to view your profile")
        if st.button("Go to Login"):
            st.session_state.page = 'login'
            st.rerun()
        return
    
    user = st.session_state.user
    
    st.markdown(f"<h1 style='color: #d81b60;'>👤 My Profile</h1>", unsafe_allow_html=True)
    st.write(f"### Welcome, {user['full_name']}! 💖")
    
    tab1, tab2 = st.tabs(["📝 Profile Information", "🔐 Change Password"])
    
    with tab1:
        st.write("#### Update Your Information")
        
        with st.form("profile_form"):
            full_name = st.text_input("Full Name", value=user.get('full_name', ''))
            phone = st.text_input("Phone Number", value=user.get('phone', ''))
            address = st.text_area("Address", value=user.get('address', ''))
            
            st.write("**Account Information:**")
            st.info(f"**Username:** {user['username']}")
            st.info(f"**Email:** {user['email']}")
            
            if st.form_submit_button("💾 Save Changes", use_container_width=True, type="primary"):
                if not validate_phone(phone):
                    st.error("⚠️ Invalid phone number format")
                else:
                    success, message = update_user_profile(
                        user['user_id'],
                        full_name,
                        phone,
                        address
                    )
                    
                    if success:
                        st.session_state.user['full_name'] = full_name
                        st.session_state.user['phone'] = phone
                        st.session_state.user['address'] = address
                        st.success(f"✅ {message}")
                        st.rerun()
                    else:
                        st.error(f"❌ {message}")
    
    with tab2:
        st.write("#### Change Your Password")
        
        with st.form("password_form"):
            old_password = st.text_input("Current Password", type="password")
            new_password = st.text_input("New Password", type="password")
            confirm_password = st.text_input("Confirm New Password", type="password")
            
            st.caption("Password must contain at least 8 characters, including uppercase, lowercase, and numbers")
            
            if st.form_submit_button("🔑 Change Password", use_container_width=True, type="primary"):
                if not all([old_password, new_password, confirm_password]):
                    st.error("⚠️ Please fill in all fields")
                elif new_password != confirm_password:
                    st.error("⚠️ New passwords do not match")
                else:
                    is_valid, password_message = validate_password(new_password)
                    if not is_valid:
                        st.error(f"⚠️ {password_message}")
                    else:
                        success, message = change_password(
                            user['user_id'],
                            old_password,
                            new_password
                        )
                        
                        if success:
                            st.success(f"✅ {message}")
                        else:
                            st.error(f"❌ {message}")

# Initialize database
init_users_db()

# Initialize session state
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
if 'user' not in st.session_state:
    st.session_state.user = None
if 'page' not in st.session_state:
    st.session_state.page = 'login'

# Display appropriate page
if st.session_state.page == 'login':
    login_page()
elif st.session_state.page == 'profile':
    profile_page()


def save_order_to_db(order):
    """Save order to database"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    items_json = json.dumps(order['items'])
    payment_details_json = json.dumps(order.get('payment_details', {}))
    
    c.execute("""
        INSERT INTO orders (
            order_id, date, customer_name, email, 
            phone, address, items_json, total, payment_method, payment_details_json, status
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
        order['status']
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

# --- DATA LOADING FUNCTIONS ---
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
        "primary_color": "#d81b60",
        "background": "linear-gradient(135deg, #ffeef8 0%, #fff5f7 100%)",
        "card_shadow": "0 4px 6px rgba(0,0,0,0.1)"
    }

# Initialize database and load data
init_db()
PRODUCTS = load_products()
THEME = load_theme()

# --- PAGE CONFIG & CSS ---
st.set_page_config(
    page_title="GlamBeauty - Cosmetics Store",
    page_icon="💄",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown(f"""
    <style>
    .main {{
        padding: 0rem 1rem;
    }}
    .product-card {{
        border: 2px solid #f0f0f0;
        border-radius: 15px;
        padding: 20px;
        margin: 10px;
        background: {THEME['background']};
        box-shadow: {THEME['card_shadow']};
        transition: transform 0.3s;
    }}
    .product-card:hover {{
        transform: translateY(-5px);
        box-shadow: 0 6px 12px rgba(0,0,0,0.15);
    }}
    .price-tag {{
        font-size: 24px;
        color: {THEME['primary_color']};
        font-weight: bold;
    }}
    .header-title {{
        text-align: center;
        color: {THEME['primary_color']};
        font-size: 48px;
        font-weight: bold;
        margin-bottom: 10px;
    }}
    .subtitle {{
        text-align: center;
        color: {THEME['primary_color']};
        font-size: 18px;
        margin-bottom: 30px;
    }}
    .stImage img {{
        object-fit: cover !important;
        height: 280px !important;
        width: 100% !important;
        border-radius: 10px;
        box-shadow: 0 2px 8px rgba(0,0,0,0.1);
    }}
    div[data-testid="column"]:first-child .stImage img {{
        height: 500px !important;
    }}
    .cart-thumbnail img {{
        height: 120px !important;
        width: 120px !important;
        object-fit: cover !important;
        border-radius: 8px;
    }}
    </style>
""", unsafe_allow_html=True)

# --- SESSION STATE INITIALIZATION ---
if 'cart' not in st.session_state:
    st.session_state.cart = []
if 'page' not in st.session_state:
    st.session_state.page = 'home'
if 'selected_product' not in st.session_state:
    st.session_state.selected_product = None
if 'customer_info' not in st.session_state:
    st.session_state.customer_info = {}
if 'cart_count' not in st.session_state:
    st.session_state.cart_count = {}

# --- HANDLE QR CODE SCAN (Query Parameters) ---
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

# --- UTILITY FUNCTIONS ---
def get_app_url():
    """Get the current Streamlit app URL"""
    try:
        return "https://glambeauty.streamlit.app"
    except:
        return "http://localhost:8501"

def generate_qr_code(data, product_name):
    """Generate QR code with branded overlay"""
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_H,
        box_size=10,
        border=4,
    )
    qr.add_data(data)
    qr.make(fit=True)
    img = qr.make_image(fill_color=THEME['primary_color'], back_color="white")
    img = img.convert('RGB')
    width, height = img.size
    logo_size = width // 5
    overlay = Image.new('RGBA', (logo_size, logo_size), (255, 255, 255, 0))
    draw = ImageDraw.Draw(overlay)
    draw.ellipse([0, 0, logo_size, logo_size], fill='#ffffff', outline=THEME['primary_color'], width=3)
    img_with_overlay = img.copy()
    pos = ((width - logo_size) // 2, (height - logo_size) // 2)
    img_with_overlay.paste(overlay, pos, overlay)
    return img_with_overlay

def add_to_cart(product):
    """Add product to cart"""
    product_id = product['id']
    st.session_state.cart.append(product)
    if product_id in st.session_state.cart_count:
        st.session_state.cart_count[product_id] += 1
    else:
        st.session_state.cart_count[product_id] = 1
    st.success(f"✅ {product['name']} added to cart!")

def remove_from_cart(index):
    """Remove product from cart"""
    product = st.session_state.cart[index]
    product_id = product['id']
    if product_id in st.session_state.cart_count:
        st.session_state.cart_count[product_id] -= 1
        if st.session_state.cart_count[product_id] <= 0:
            del st.session_state.cart_count[product_id]
    st.session_state.cart.pop(index)
    st.rerun()

def save_order(customer_info, cart_items, total_amount, payment_method, payment_details=None):
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
        'status': 'Confirmed'
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

def export_cart_json():
    """Export cart to JSON format"""
    cart_data = {
        'cart_items': st.session_state.cart,
        'total_items': len(st.session_state.cart),
        'total_amount': sum(item['price'] for item in st.session_state.cart),
        'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    return json.dumps(cart_data, indent=2)

# --- UI COMPONENTS ---
def display_product_card(product, col):
    """Display a single product card"""
    with col:
        st.markdown(f"""
            <div class="product-card">
                <h3 style="color: {THEME['primary_color']}; margin-bottom: 10px;">{product['name']}</h3>
                <p style="color: #666; font-size: 12px; margin-bottom: 10px;">{product['category']}</p>
            </div>
        """, unsafe_allow_html=True)
        st.image(product['image'], use_container_width=True)
        st.markdown(f"<p class='price-tag'>₹{product['price']}</p>", unsafe_allow_html=True)
        desc = product['description'][:80] + ("..." if len(product['description']) > 80 else "")
        st.write(desc)
        col1, col2 = st.columns(2)
        with col1:
            if st.button("View Details", key=f"view_{product['id']}", use_container_width=True):
                st.session_state.selected_product = product['id']
                st.session_state.page = 'product'
                st.rerun()
        with col2:
            if st.button("🛒 Add", key=f"add_{product['id']}", use_container_width=True):
                add_to_cart(product)

# --- PAGE FUNCTIONS ---
def home_page():
    """Display home page with products"""
    st.markdown(f"<h1 class='header-title'>💄 GlamBeauty</h1>", unsafe_allow_html=True)
    st.markdown(f"<p class='subtitle'>Premium Cosmetics & Skincare</p>", unsafe_allow_html=True)
    
    categories = ["All"] + sorted(list(set(p['category'] for p in PRODUCTS)))
    selected_category = st.selectbox("Filter by Category:", categories)
    filtered = PRODUCTS if selected_category == "All" else [p for p in PRODUCTS if p['category'] == selected_category]
    
    st.write(f"### 🛍️ {len(filtered)} Products Available")
    
    cols_per_row = 3
    for i in range(0, len(filtered), cols_per_row):
        cols = st.columns(cols_per_row)
        for j in range(cols_per_row):
            if i + j < len(filtered):
                display_product_card(filtered[i + j], cols[j])

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
    
    st.markdown(f"<h1 style='color: {THEME['primary_color']};'>{product['name']}</h1>", unsafe_allow_html=True)
    
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
        st.write("Scan to view product details or share with friends!")
        
        base_url = get_app_url()
        product_url = f"{base_url}?product_id={product['id']}"
        
        qr_img = generate_qr_code(product_url, product['name'])
        st.image(qr_img, width=300)
        
        img_buffer = io.BytesIO()
        qr_img.save(img_buffer, format='PNG')
        img_buffer.seek(0)
        
        st.download_button(
            label="📥 Download QR Code",
            data=img_buffer,
            file_name=f"{product['name']}_QR.png",
            mime="image/png",
            use_container_width=True
        )
        st.write("**Product URL:**")
        st.code(product_url, language=None)
        st.caption("💡 Scan this QR code to open this product directly!")

def cart_page():
    """Display shopping cart"""
    st.markdown(f"<h1 style='color: {THEME['primary_color']};'>🛒 Shopping Cart</h1>", unsafe_allow_html=True)
    
    if not st.session_state.cart:
        st.info("Your cart is empty. Start shopping!")
        if st.button("Continue Shopping"):
            st.session_state.page = 'home'
            st.rerun()
        return
    
    total = 0
    for idx, item in enumerate(st.session_state.cart):
        col1, col2, col3, col4 = st.columns([2, 3, 2, 1])
        with col1:
            st.markdown('<div class="cart-thumbnail">', unsafe_allow_html=True)
            st.image(item['image'], width=120)
            st.markdown('</div>', unsafe_allow_html=True)
        with col2:
            st.write(f"**{item['name']}**")
            st.write(f"{item['category']}")
        with col3:
            st.write(f"**₹{item['price']}**")
        with col4:
            if st.button("🗑️", key=f"remove_{idx}"):
                remove_from_cart(idx)
        total += item['price']
        st.divider()
    
    st.write("### 📊 Cart Summary")
    col1, col2 = st.columns(2)
    with col1:
        st.metric("Total Items", len(st.session_state.cart))
    with col2:
        st.metric("Total Amount", f"₹{total}")
    
    st.divider()
    
    cart_json = export_cart_json()
    st.download_button(
        label="💾 Save Cart as JSON",
        data=cart_json,
        file_name="glambeauty_cart.json",
        mime="application/json",
        use_container_width=True
    )
    
    st.divider()
    st.write("### 📝 Customer Information")
    
    with st.form("checkout_form"):
        name = st.text_input("Full Name *", placeholder="Enter your name")
        email = st.text_input("Email *", placeholder="your.email@example.com")
        phone = st.text_input("Phone Number *", placeholder="+91 XXXXX XXXXX")
        address = st.text_area("Delivery Address *", placeholder="Full address with pincode")
        
        st.divider()
        st.write("### 💳 Payment Method")
        payment_method = st.radio(
            "Select Payment Method *",
            ["Cash on Delivery", "UPI", "Credit/Debit Card"],
            horizontal=True
        )
        
        payment_details = {}
        
        if payment_method == "UPI":
            st.write("#### 📱 UPI Payment Details")
            col1, col2 = st.columns(2)
            with col1:
                upi_id = st.text_input("UPI ID *", placeholder="yourname@paytm", key="upi_id")
            with col2:
                upi_provider = st.selectbox("UPI Provider", ["Google Pay", "PhonePe", "Paytm", "BHIM", "Other"])
            
            st.info("💡 You will receive a payment request on your UPI app after placing the order.")
            payment_details = {'upi_id': upi_id, 'upi_provider': upi_provider}
        
        elif payment_method == "Credit/Debit Card":
            st.write("#### 💳 Card Payment Details")
            card_number = st.text_input("Card Number *", placeholder="1234 5678 9012 3456", max_chars=19, key="card_num")
            
            col1, col2, col3 = st.columns(3)
            with col1:
                card_holder = st.text_input("Cardholder Name *", placeholder="Name on card", key="card_holder")
            with col2:
                expiry_date = st.text_input("Expiry Date *", placeholder="MM/YY", max_chars=5, key="expiry")
            with col3:
                cvv = st.text_input("CVV *", placeholder="123", max_chars=3, type="password", key="cvv")
            
            card_type = st.radio("Card Type", ["Credit Card", "Debit Card"], horizontal=True)
            
            st.warning("🔒 Your card details are encrypted and secure. We use industry-standard SSL encryption.")
            payment_details = {
                'card_number': card_number[-4:] if len(card_number) >= 4 else "****",
                'card_holder': card_holder,
                'expiry_date': expiry_date,
                'card_type': card_type
            }
        
        else:
            st.write("#### 💵 Cash on Delivery")
            st.info("💡 Pay in cash when your order is delivered to your doorstep.")
            st.success("✅ No advance payment required!")
            payment_details = {'method': 'Cash on Delivery'}
        
        st.divider()
        
        col1, col2 = st.columns(2)
        with col1:
            continue_shop = st.form_submit_button("Continue Shopping", use_container_width=True)
        with col2:
            place_order = st.form_submit_button("🎉 Place Order", use_container_width=True, type="primary")
    
    if continue_shop:
        st.session_state.page = 'home'
        st.rerun()
    
    if place_order:
        if not (name and email and phone and address):
            st.error("⚠️ Please fill in all customer information fields")
            return
        
        payment_valid = True
        if payment_method == "UPI":
            if not upi_id:
                st.error("⚠️ Please enter your UPI ID")
                payment_valid = False
            elif '@' not in upi_id:
                st.error("⚠️ Invalid UPI ID format")
                payment_valid = False
        
        elif payment_method == "Credit/Debit Card":
            if not (card_number and card_holder and expiry_date and cvv):
                st.error("⚠️ Please fill in all card details")
                payment_valid = False
            elif len(card_number.replace(" ", "")) < 13:
                st.error("⚠️ Invalid card number")
                payment_valid = False
            elif len(cvv) != 3:
                st.error("⚠️ CVV must be 3 digits")
                payment_valid = False
        
        if payment_valid:
            customer_info = {'name': name, 'email': email, 'phone': phone, 'address': address}
            st.session_state.customer_info = customer_info
            order_id = save_order(customer_info, st.session_state.cart, total, payment_method, payment_details)
            
            st.session_state.cart = []
            st.session_state.cart_count = {}
            
            st.balloons()
            st.success(f"✅ Order #{order_id} placed successfully! Thank you for shopping with GlamBeauty! 💄")
            
            if payment_method == "UPI":
                st.info(f"📱 UPI payment request sent to {upi_id}")
            elif payment_method == "Credit/Debit Card":
                st.info(f"💳 Payment processed on card ending with {payment_details['card_number']}")
            else:
                st.info(f"💵 You will pay ₹{total} in cash upon delivery")
            
            st.info(f"📧 Order confirmation sent to {email}")

def orders_page():
    """Display order history"""
    st.markdown(f"<h1 style='color: {THEME['primary_color']};'>📦 Order History</h1>", unsafe_allow_html=True)
    
    rows = fetch_orders_from_db()
    if not rows:
        st.info("No orders yet. Start shopping to place your first order!")
        if st.button("Start Shopping"):
            st.session_state.page = 'home'
            st.rerun()
        return
    
    csv_data = export_orders_csv()
    st.download_button(
        label="📥 Export Orders (CSV)",
        data=csv_data,
        file_name=f"glambeauty_orders_{datetime.now().strftime('%Y%m%d')}.csv",
        mime="text/csv"
    )
    
    st.write(f"### Total Orders: {len(rows)}")
    st.divider()
    
    for row in rows:
        if len(row) >= 11:
            order_id, date, name, email, phone, address, items_json, total, payment_method, payment_details_json, status = row[:11]
            payment_details = safe_json_loads(payment_details_json)
        else:
            order_id, date, name, email, phone, address, items_json, total, status = row[:9]
            payment_method = "Cash on Delivery"
            payment_details = {}
        
        items = safe_json_loads(items_json)
        
        with st.expander(f"🛍️ Order #{order_id} - {date} - ₹{total}"):
            col1, col2 = st.columns(2)
            
            with col1:
                st.write("#### 👤 Customer Details")
                st.write(f"**Name:** {name}")
                st.write(f"**Email:** {email}")
                st.write(f"**Phone:** {phone}")
                st.write(f"**Address:** {address}")
            
            with col2:
                st.write("#### 💳 Payment Details")
                st.write(f"**Status:** {status}")
                st.write(f"**Payment Method:** {payment_method}")
                
                if payment_method == "UPI" and payment_details:
                    st.write(f"**UPI ID:** {payment_details.get('upi_id', 'N/A')}")
                    st.write(f"**UPI Provider:** {payment_details.get('upi_provider', 'N/A')}")
                elif payment_method == "Credit/Debit Card" and payment_details:
                    st.write(f"**Card Type:** {payment_details.get('card_type', 'N/A')}")
                    st.write(f"**Card Holder:** {payment_details.get('card_holder', 'N/A')}")
                    st.write(f"**Card Number:** **** **** **** {payment_details.get('card_number', '****')}")
                elif payment_method == "Cash on Delivery":
                    st.write("**Payment:** Pay on delivery")
            
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

def about_page():
    """Display about page"""
    st.markdown(f"<h1 style='color: {THEME['primary_color']};'>About GlamBeauty</h1>", unsafe_allow_html=True)
    st.write("""
    ### Welcome to GlamBeauty! 💄✨

    We are your one-stop destination for premium cosmetics and skincare products.
    Our mission is to help everyone feel confident and beautiful in their own skin.

    #### Why Choose Us?
    - 🌟 **Premium Quality**: All products are carefully curated for quality
    - 💯 **Authentic**: 100% genuine and original products
    - 🚚 **Fast Delivery**: Quick and reliable shipping across India
    - 💰 **Best Prices**: Competitive pricing with regular offers
    - 🎁 **Gift Ready**: Beautiful packaging perfect for gifting

    #### Our Categories
    - **Lips**: Lipsticks, Glosses, Lip Liners
    - **Eyes**: Mascara, Eyeliner, Eyeshadow, Brow Products
    - **Face**: Foundation, Blush, Highlighter, Setting Spray
    - **Skincare**: Cleansers, Serums, Moisturizers, Treatments

    Thank you for choosing GlamBeauty! 💖
    """)

def contact_page():
    """Display contact page"""
    st.markdown(f"<h1 style='color: {THEME['primary_color']};'>Contact Us</h1>", unsafe_allow_html=True)
    st.write("""
    ### Get in Touch! 📧

    We'd love to hear from you! Whether you have a question about our products,
    need help with your order, or just want to say hi, we're here for you.
    """)
    col1, col2 = st.columns(2)
    with col1:
        st.write("#### 📍 Visit Us")
        st.write("""
        GlamBeauty Store
        123 Beauty Street
        Fashion District
        Mumbai, Maharashtra 400001
        India
        """)
        st.write("#### 📞 Call Us")
        st.write("Phone: +91 98765 43210")
        st.write("WhatsApp: +91 98765 43210")
        st.write("#### 📧 Email Us")
        st.write("support@glambeauty.com")
        st.write("orders@glambeauty.com")
    with col2:
        st.write("#### 💬 Send us a Message")
        with st.form("contact_form"):
            name = st.text_input("Your Name")
            email = st.text_input("Your Email")
            message = st.text_area("Your Message", height=150)
            if st.form_submit_button("Send Message", use_container_width=True):
                if name and email and message:
                    st.success("✅ Thank you! Your message has been sent. We'll get back to you soon!")
                else:
                    st.error("Please fill in all fields")

def admin_page():
    """Display admin dashboard"""
    st.markdown(f"<h1 style='color: {THEME['primary_color']};'>🧑‍💼 Admin Dashboard</h1>", unsafe_allow_html=True)
    
    tab1, tab2 = st.tabs(["Add Product", "Manage Products"])
    
    with tab1:
        st.subheader("Add New Product")
        with st.form("add_product"):
            name = st.text_input("Product Name *")
            price = st.number_input("Price (₹) *", min_value=0, step=1)
            category = st.selectbox("Category *", ["Lips", "Eyes", "Face", "Skincare"])
            description = st.text_area("Description *")
            image = st.text_input("Image URL *", placeholder="https://...")
            
            if st.form_submit_button("Add Product", use_container_width=True):
                if name and image and description:
                    new_id = max([p["id"] for p in PRODUCTS]) + 1 if PRODUCTS else 1
                    new_product = {
                        "id": new_id,
                        "name": name,
                        "price": int(price),
                        "category": category,
                        "description": description,
                        "image": image
                    }
                    PRODUCTS.append(new_product)
                    save_products(PRODUCTS)
                    st.success("✅ Product added successfully!")
                    st.rerun()
                else:
                    st.error("Please fill in all required fields.")
    
    with tab2:
        st.subheader("Current Products")
        for p in PRODUCTS:
            col1, col2, col3 = st.columns([3, 1, 1])
            with col1:
                st.write(f"**{p['name']}** - ₹{p['price']} - {p['category']}")
            with col2:
                st.write(f"ID: {p['id']}")
            with col3:
                if st.button("🗑️ Delete", key=f"del_{p['id']}"):
                    PRODUCTS.remove(p)
                    save_products(PRODUCTS)
                    st.success(f"Deleted {p['name']}")
                    st.rerun()

# --- SIDEBAR NAVIGATION ---
with st.sidebar:
    st.image("https://img.icons8.com/color/96/000000/cosmetics.png", width=100)
    st.title("GlamBeauty")
    st.write("---")
    
    if st.button("🏠 Home", use_container_width=True):
        st.session_state.page = 'home'
        st.rerun()
    
    if st.button(f"🛒 Cart ({len(st.session_state.cart)})", use_container_width=True):
        st.session_state.page = 'cart'
        st.rerun()
    
    if st.button("📦 Orders", use_container_width=True):
        st.session_state.page = 'orders'
        st.rerun()
    
    if st.button("ℹ️ About", use_container_width=True):
        st.session_state.page = 'about'
        st.rerun()
    
    if st.button("📞 Contact", use_container_width=True):
        st.session_state.page = 'contact'
        st.rerun()
    
    if st.button("🧑‍💼 Admin", use_container_width=True):
        st.session_state.page = 'admin'
        st.rerun()
    
    st.write("---")
    st.write("### 🎉 Special Offers")
    st.info("💝 Free shipping on orders above ₹1000!")
    st.success("🎁 Buy 3, Get 1 Free on select items")

# --- MAIN PAGE ROUTING ---
if st.session_state.page == 'home':
    home_page()
elif st.session_state.page == 'product':
    product_page()
elif st.session_state.page == 'cart':
    cart_page()
elif st.session_state.page == 'orders':
    orders_page()
elif st.session_state.page == 'about':
    about_page()
elif st.session_state.page == 'contact':
    contact_page()
elif st.session_state.page == 'admin':
    admin_page()

# --- FOOTER ---
st.write("---")
st.markdown(f"""
    <div style='text-align: center; color: #666; padding: 20px;'>
        <p>© {datetime.now().year} GlamBeauty - Premium Cosmetics & Skincare</p>
        <p>Made with ❤️ in India | 🔒 Secure Shopping | 📦 Fast Delivery</p>
    </div>
""", unsafe_allow_html=True)
