# app.py
import streamlit as st
import sqlite3
import pandas as pd
import os
import hashlib
import binascii
from datetime import datetime, date

# -------------------------
# CONFIG
# -------------------------
DB_PATH = "database/food_waste.db"

# -------------------------
# STYLES / BACKGROUND
# -------------------------
def set_background(color="#f5f5f5"):
    """Apply flat color background per page."""
    st.markdown(
        f"""
        <style>
        .stApp {{
            background-color: {color};
        }}
        .content-box {{
            background-color: white;
            padding: 1.6rem;
            border-radius: 10px;
            box-shadow: 0px 2px 8px rgba(0,0,0,0.08);
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )

# -------------------------
# HEADER BAR
# -------------------------
def header_bar(user=None):
    """Fixed top header bar with app name and optional profile/logout buttons."""
    st.markdown(
        """
        <style>
        .header-bar {
            position: fixed;
            top: 0;
            left: 0;
            right: 0;
            height: 60px;
            background-color: #2E7D32;
            color: white;
            font-size: 20px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 0 18px;
            z-index: 1000;
        }
        .header-space { margin-top: 70px; }
        .header-title { font-weight: 600; }
        </style>
        """,
        unsafe_allow_html=True,
    )

    # render header content
    st.markdown('<div class="header-bar">', unsafe_allow_html=True)
    st.markdown('<div class="header-title">Smart Food Waste Management Platform</div>', unsafe_allow_html=True)

    # right side buttons - use Streamlit columns inside markdown space to position real buttons
    if user:
        # create tiny columns to place real buttons visually near top-right
        cols = st.columns([1, 1, 12])  # small columns for buttons, rest for spacing
        with cols[0]:
            if st.button("👤 Profile", key="header_profile"):
                st.session_state.page = "Profile"
                st.rerun()
        with cols[1]:
            if st.button("🚪 Logout", key="header_logout"):
                logout()
                st.rerun()
    else:
        # keep spacing for layout consistency when logged out
        st.markdown("<div></div>", unsafe_allow_html=True)

    st.markdown("</div>", unsafe_allow_html=True)
    st.markdown('<div class="header-space"></div>', unsafe_allow_html=True)

# -------------------------
# DB helpers
# -------------------------
def get_conn():
    folder = os.path.dirname(DB_PATH)
    if folder:
        os.makedirs(folder, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

# -------------------------
# Password hashing (PBKDF2)
# -------------------------
def hash_password(password: str, salt: bytes = None):
    if salt is None:
        salt = os.urandom(16)
    pwd = password.encode("utf-8")
    dk = hashlib.pbkdf2_hmac("sha256", pwd, salt, 100_000)
    return binascii.hexlify(dk).decode("utf-8"), binascii.hexlify(salt).decode("utf-8")

def verify_password(stored_hash: str, stored_salt_hex: str, password_attempt: str) -> bool:
    salt = binascii.unhexlify(stored_salt_hex)
    attempt_hash, _ = hash_password(password_attempt, salt)
    return attempt_hash == stored_hash

# -------------------------
# Initialize DB + Migrations
# -------------------------
def init_db():
    conn = get_conn()
    cur = conn.cursor()

    # tables
    cur.execute("""
    CREATE TABLE IF NOT EXISTS Providers (
        Provider_ID INTEGER PRIMARY KEY AUTOINCREMENT,
        Name TEXT NOT NULL,
        Type TEXT,
        Address TEXT,
        City TEXT,
        Contact TEXT
    );""")

    cur.execute("""
    CREATE TABLE IF NOT EXISTS Receivers (
        Receiver_ID INTEGER PRIMARY KEY AUTOINCREMENT,
        Name TEXT NOT NULL,
        Type TEXT,
        City TEXT,
        Contact TEXT
    );""")

    cur.execute("""
    CREATE TABLE IF NOT EXISTS Food_Listings (
        Food_ID INTEGER PRIMARY KEY AUTOINCREMENT,
        Food_Name TEXT NOT NULL,
        Quantity INTEGER,
        Expiry_Date TEXT,
        Provider_ID INTEGER,
        Provider_Type TEXT,
        Location TEXT,
        Food_Type TEXT,
        Meal_Type TEXT,
        Created_At TEXT,
        FOREIGN KEY (Provider_ID) REFERENCES Providers(Provider_ID)
    );""")

    cur.execute("""
    CREATE TABLE IF NOT EXISTS Claims (
        Claim_ID INTEGER PRIMARY KEY AUTOINCREMENT,
        Food_ID INTEGER,
        Receiver_ID INTEGER,
        Status TEXT,
        Timestamp TEXT
    );""")

    cur.execute("""
    CREATE TABLE IF NOT EXISTS Users (
        User_ID INTEGER PRIMARY KEY AUTOINCREMENT,
        Username TEXT UNIQUE NOT NULL,
        Password_Hash TEXT NOT NULL,
        Salt TEXT NOT NULL,
        Role TEXT NOT NULL,
        Profile_ID INTEGER
    );""")

    # migration: Remarks column for Claims
    cur.execute("PRAGMA table_info(Claims)")
    cols = [r[1] for r in cur.fetchall()]
    if "Remarks" not in cols:
        cur.execute("ALTER TABLE Claims ADD COLUMN Remarks TEXT;")

    conn.commit()

    # default admin if none exists
    cur.execute("SELECT COUNT(*) as cnt FROM Users WHERE Role='Admin'")
    row = cur.fetchone()
    if row and row["cnt"] == 0:
        username = "admin"
        password = "admin123"
        pwd_hash, salt = hash_password(password)
        cur.execute("INSERT INTO Users (Username, Password_Hash, Salt, Role) VALUES (?, ?, ?, ?)",
                    (username, pwd_hash, salt, "Admin"))
        conn.commit()

    conn.close()

# -------------------------
# Auth: signup & login
# -------------------------
def signup_user(username, password, role, name, contact, city=None, provider_type=None):
    conn = get_conn()
    cur = conn.cursor()
    pwd_hash, salt = hash_password(password)
    try:
        profile_id = None
        if role == "Provider":
            cur.execute("INSERT INTO Providers (Name, Type, Address, City, Contact) VALUES (?, ?, ?, ?, ?)",
                        (name, provider_type or "", "", city or "", contact))
            profile_id = cur.lastrowid
        elif role == "Receiver":
            cur.execute("INSERT INTO Receivers (Name, Type, City, Contact) VALUES (?, ?, ?, ?)",
                        (name, "Individual", city or "", contact))
            profile_id = cur.lastrowid

        cur.execute("INSERT INTO Users (Username, Password_Hash, Salt, Role, Profile_ID) VALUES (?, ?, ?, ?, ?)",
                    (username, pwd_hash, salt, role, profile_id))
        conn.commit()
        return True, "User registered successfully."
    except sqlite3.IntegrityError:
        return False, "Username already exists."
    finally:
        conn.close()

def login_user(username, password):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM Users WHERE Username = ?", (username,))
    row = cur.fetchone()
    conn.close()
    if row:
        if verify_password(row["Password_Hash"], row["Salt"], password):
            return True, {
                "User_ID": row["User_ID"],
                "Username": row["Username"],
                "Role": row["Role"],
                "Profile_ID": row["Profile_ID"],
            }
        else:
            return False, "Incorrect password."
    else:
        return False, "Username not found."

# -------------------------
# Session helpers
# -------------------------
def init_session():
    if "user" not in st.session_state:
        st.session_state.user = None
    if "page" not in st.session_state:
        st.session_state.page = "Home"

def logout():
    st.session_state.user = None
    st.session_state.page = "Home"
    st.success("Logged out.")

# -------------------------
# PROFILE PAGE
# -------------------------
def profile_page(user):
    set_background("#f3e5f5")  # purple
    header_bar(user)
    st.markdown('<div class="content-box">', unsafe_allow_html=True)
    st.header("👤 My Profile")

    conn = get_conn()
    cur = conn.cursor()

    profile = None
    if user["Role"] == "Provider":
        cur.execute("SELECT * FROM Providers WHERE Provider_ID=?", (user["Profile_ID"],))
        row = cur.fetchone()
        if row:
            profile = dict(row)
    elif user["Role"] == "Receiver":
        cur.execute("SELECT * FROM Receivers WHERE Receiver_ID=?", (user["Profile_ID"],))
        row = cur.fetchone()
        if row:
            profile = dict(row)
    else:  # Admin
        profile = {"Name": "System Admin", "Contact": "-", "City": "-", "Type": "Admin"}

    if profile:
        # Pretty display
        st.write("**Role:**", user["Role"])
        st.write("**Username:**", user["Username"])
        for k, v in profile.items():
            st.write(f"**{k}:** {v}")
    else:
        st.warning("Profile not found.")

    if st.button("⬅ Back"):
        st.session_state.page = "Dashboard"
        st.rerun()

    conn.close()
    st.markdown('</div>', unsafe_allow_html=True)

# -------------------------
# PROVIDER DASHBOARD
# -------------------------
def provider_dashboard(user):
    set_background("#e8f5e9")  # green
    header_bar(user)
    st.markdown('<div class="content-box">', unsafe_allow_html=True)
    st.header("Provider Dashboard")

    conn = get_conn()
    cur = conn.cursor()
    profile_id = user.get("Profile_ID")

    st.subheader("Add Surplus Food")
    with st.form("add_food_form"):
        food_name = st.text_input("Food Name")
        food_type = st.selectbox("Food Type", ["Vegetarian", "Non-Vegetarian", "Vegan", "Other"])
        qty = st.number_input("Quantity", min_value=1, step=1)
        expiry = st.date_input("Expiry Date", value=date.today())
        city = st.text_input("City")
        meal_type = st.selectbox("Meal Type", ["Breakfast", "Lunch", "Dinner", "Snacks", "Other"])
        submit = st.form_submit_button("Add Listing")

        if submit:
            today = date.today()
            if expiry < today:
                st.error("❌ Food is already Expired.")
            else:
                created_at = datetime.utcnow().isoformat()
                cur.execute("""
                    INSERT INTO Food_Listings (Food_Name, Quantity, Expiry_Date, Provider_ID, Provider_Type, Location, Food_Type, Meal_Type, Created_At)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (food_name, qty, expiry.isoformat(), profile_id, "Provider", city, food_type, meal_type, created_at))
                conn.commit()
                st.success("✅ Food added successfully.")

    st.subheader("My Listings")
    df = pd.read_sql_query("SELECT * FROM Food_Listings WHERE Provider_ID = ?", conn, params=(profile_id,))
    st.dataframe(df if not df.empty else pd.DataFrame())

    conn.close()
    st.markdown('</div>', unsafe_allow_html=True)

# -------------------------
# RECEIVER DASHBOARD
# -------------------------
def receiver_dashboard(user):
    set_background("#e3f2fd")  # blue
    header_bar(user)
    st.markdown('<div class="content-box">', unsafe_allow_html=True)
    st.header("Receiver Dashboard")

    conn = get_conn()
    cur = conn.cursor()
    profile_id = user.get("Profile_ID")

    # Search section
    st.subheader("🔎 Search Food Listings")
    st.write("Browse available food items posted by providers.")
    city = st.text_input("Filter by City")
    ftype = st.selectbox("Food Type", ["", "Vegetarian", "Non-Vegetarian", "Vegan", "Other"])
    meal = st.selectbox("Meal Type", ["", "Breakfast", "Lunch", "Dinner", "Snacks", "Other"])

    query = """SELECT f.Food_ID, f.Food_Name, f.Quantity, f.Expiry_Date, f.Location, f.Food_Type, f.Meal_Type,
                      p.Name as Provider_Name, p.Contact as Provider_Contact
               FROM Food_Listings f
               LEFT JOIN Providers p ON f.Provider_ID = p.Provider_ID
               WHERE 1=1"""
    params = []
    if city:
        query += " AND f.Location=?"
        params.append(city)
    if ftype:
        query += " AND f.Food_Type=?"
        params.append(ftype)
    if meal:
        query += " AND f.Meal_Type=?"
        params.append(meal)

    df = pd.read_sql_query(query, conn, params=params)
    st.dataframe(df if not df.empty else pd.DataFrame())

    # Claim section
    st.subheader("📥 Claim Food")
    st.write("Request food items and await approval.")
    with st.form("claim_form"):
        food_id = st.number_input("Enter Food ID to Claim", min_value=1, step=1)
        remarks = st.text_area("Remarks (optional)", placeholder="e.g., For community meal on X date")
        submitted = st.form_submit_button("Submit Claim")
        if submitted:
            cur.execute("SELECT * FROM Food_Listings WHERE Food_ID=?", (food_id,))
            food = cur.fetchone()
            if not food:
                st.error("Invalid Food ID. Please check the listings above.")
            else:
                timestamp = datetime.utcnow().isoformat()
                cur.execute("""INSERT INTO Claims (Food_ID, Receiver_ID, Status, Timestamp, Remarks)
                               VALUES (?, ?, ?, ?, ?)""", (food_id, profile_id, "Pending", timestamp, remarks))
                conn.commit()
                st.success("✅ Claim submitted successfully. Status: Pending.")

    # My Claims
    st.subheader("📊 My Claims")
    my_claims = pd.read_sql_query("""
        SELECT c.Claim_ID, f.Food_Name, f.Quantity, f.Location, c.Status, c.Timestamp, c.Remarks
        FROM Claims c
        JOIN Food_Listings f ON c.Food_ID = f.Food_ID
        WHERE c.Receiver_ID=?
        ORDER BY c.Timestamp DESC
    """, conn, params=(profile_id,))
    st.dataframe(my_claims if not my_claims.empty else pd.DataFrame())

    conn.close()
    st.markdown('</div>', unsafe_allow_html=True)

# -------------------------
# ADMIN DASHBOARD
# -------------------------
def admin_dashboard(user):
    set_background("#fff3e0")  # orange
    header_bar(user)
    st.markdown('<div class="content-box">', unsafe_allow_html=True)
    st.header("⚙️ Admin Dashboard")

    conn = get_conn()
    cur = conn.cursor()

    # CRUD operations
    st.subheader("📂 Manage CRUD Operations")
    crud_action = st.selectbox("Choose Operation", ["Read", "Create", "Update", "Delete"])

    if crud_action == "Read":
        df = pd.read_sql_query("SELECT * FROM Food_Listings", conn)
        st.dataframe(df if not df.empty else pd.DataFrame())

    elif crud_action == "Create":
        with st.form("create_listing"):
            food_name = st.text_input("Food Name")
            qty = st.number_input("Quantity", min_value=1, step=1)
            expiry = st.date_input("Expiry Date", value=date.today())
            location = st.text_input("City/Location")
            food_type = st.selectbox("Food Type", ["Vegetarian", "Non-Vegetarian", "Vegan", "Other"])
            meal_type = st.selectbox("Meal Type", ["Breakfast", "Lunch", "Dinner", "Snacks", "Other"])
            submit = st.form_submit_button("Add Listing")
            if submit:
                today = date.today()
                if expiry < today:
                    st.error("❌ Expiry date cannot be in the past. Please select today or a future date.")
                else:
                    cur.execute("""
                        INSERT INTO Food_Listings (Food_Name, Quantity, Expiry_Date, Provider_ID, Provider_Type, Location, Food_Type, Meal_Type, Created_At)
                        VALUES (?, ?, ?, NULL, 'Admin', ?, ?, ?, ?)
                    """, (food_name, qty, expiry.isoformat(), location, food_type, meal_type, datetime.utcnow().isoformat()))
                    conn.commit()
                    st.success("✅ Food listing added by Admin.")

    elif crud_action == "Update":
        listing_id = st.number_input("Enter Food_ID to Update", min_value=1, step=1)
        new_qty = st.number_input("New Quantity", min_value=1, step=1)
        new_expiry = st.date_input("New Expiry Date")
        if st.button("Update Listing"):
            today = date.today()
            if new_expiry < today:
                st.error("❌ Expiry date cannot be in the past.")
            else:
                cur.execute("UPDATE Food_Listings SET Quantity=?, Expiry_Date=? WHERE Food_ID=?",
                            (new_qty, new_expiry.isoformat(), listing_id))
                conn.commit()
                st.success(f"✅ Listing {listing_id} updated.")

    elif crud_action == "Delete":
        del_id = st.number_input("Enter Food_ID to Delete", min_value=1, step=1)
        if st.button("Delete Listing"):
            cur.execute("DELETE FROM Food_Listings WHERE Food_ID=?", (del_id,))
            conn.commit()
            st.success(f"🗑️ Listing {del_id} deleted.")

    st.markdown("---")

    # Reports & Analytics (clean)
    st.subheader("📊 View Reports & Analytics")
    col1, col2 = st.columns(2)
    with col1:
        df_type = pd.read_sql_query("SELECT Food_Type, COUNT(*) as Count FROM Food_Listings GROUP BY Food_Type", conn)
        if not df_type.empty:
            st.bar_chart(df_type.set_index("Food_Type"))
    with col2:
        df_meal = pd.read_sql_query("SELECT Meal_Type, COUNT(*) as Count FROM Food_Listings GROUP BY Meal_Type", conn)
        if not df_meal.empty:
            st.bar_chart(df_meal.set_index("Meal_Type"))
    df_claims = pd.read_sql_query("SELECT Status, COUNT(*) as Count FROM Claims GROUP BY Status", conn)
    if not df_claims.empty:
        st.bar_chart(df_claims.set_index("Status"))

    st.markdown("---")

    # Approve Claims
    st.subheader("✅ Approve Claims")
    pending = pd.read_sql_query("""
        SELECT c.Claim_ID, f.Food_Name, r.Name as Receiver_Name, p.Name as Provider_Name, c.Status, c.Remarks
        FROM Claims c
        JOIN Food_Listings f ON c.Food_ID = f.Food_ID
        JOIN Receivers r ON c.Receiver_ID = r.Receiver_ID
        LEFT JOIN Providers p ON f.Provider_ID = p.Provider_ID
        WHERE c.Status='Pending'
    """, conn)
    st.dataframe(pending if not pending.empty else pd.DataFrame())

    claim_id = st.number_input("Enter Claim ID to update", min_value=1, step=1)
    action = st.selectbox("Action", ["Approve", "Reject", "Complete"])
    remarks = st.text_input("Admin Remarks")
    if st.button("Update Claim"):
        cur.execute("UPDATE Claims SET Status=?, Remarks=? WHERE Claim_ID=?", (action, remarks, claim_id))
        conn.commit()
        st.success(f"✅ Claim {claim_id} marked {action}.")

    conn.close()
    st.markdown('</div>', unsafe_allow_html=True)

# -------------------------
# PAGES: Home / Login / Register / About
# -------------------------
def home_page():
    set_background("#f5f5f5")
    header_bar()
    st.markdown('<div class="content-box" style="text-align:center;">', unsafe_allow_html=True)
    st.title(" Smart Food Waste Management Platform")
    st.write("Connecting food providers with receivers to reduce food waste.")
    if st.button("Login"):
        st.session_state.page = "Login"
        st.rerun()
    if st.button("About Us"):
        st.session_state.page = "About"
        st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)

def login_page():
    set_background("#f5f5f5")
    header_bar()
    st.markdown('<div class="content-box">', unsafe_allow_html=True)
    st.header("Login")
    uname = st.text_input("Username")
    pwd = st.text_input("Password", type="password")
    if st.button("Login"):
        ok, res = login_user(uname, pwd)
        if ok:
            st.session_state.user = res
            st.session_state.page = "Dashboard"
            st.rerun()
        else:
            st.error(res)
    st.markdown("---")
    st.write("Don't have an account?")
    if st.button("Register here"):
        st.session_state.page = "Register"
        st.rerun()
    if st.button("⬅ Back to Home"):
        st.session_state.page = "Home"
        st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)

def register_page():
    set_background("#f5f5f5")
    header_bar()
    st.markdown('<div class="content-box">', unsafe_allow_html=True)
    st.header("Register")
    role = st.selectbox("Role", ["Provider", "Receiver"])
    username = st.text_input("Username")
    password = st.text_input("Password", type="password")
    name = st.text_input("Name")
    contact = st.text_input("Contact")
    city = st.text_input("City")
    provider_type = st.text_input("Provider Type") if role == "Provider" else None
    if st.button("Register"):
        ok, msg = signup_user(username, password, role, name, contact, city, provider_type)
        if ok:
            st.success("Registered! Please login.")
            st.session_state.page = "Login"
            st.rerun()
        else:
            st.error(msg)
    if st.button("⬅ Back to Home"):
        st.session_state.page = "Home"
        st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)

def about_page():
    set_background("#f5f5f5")
    header_bar()
    st.markdown('<div class="content-box">', unsafe_allow_html=True)
    st.header("About Us")
    st.write("""
    The **Smart Food Waste Management Platform** reduces food waste by connecting providers
    (restaurants, hotels, grocery stores) with receivers (NGOs, individuals).

    - Providers can list surplus food.
    - Receivers can search & claim food.
    - Admin manages the system, verifies claims, and generates reports.

     Save food, fight hunger, and build a sustainable ecosystem. 🌱
    """)
    if st.button("⬅ Back to Home"):
        st.session_state.page = "Home"
        st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)

# -------------------------
# MAIN
# -------------------------
def main():
    st.set_page_config(page_title="Smart Food Waste Management Platform", layout="wide")
    init_db()
    init_session()

    if st.session_state.user is None:
        # not logged in
        if st.session_state.page == "Home":
            home_page()
        elif st.session_state.page == "Login":
            login_page()
        elif st.session_state.page == "Register":
            register_page()
        elif st.session_state.page == "About":
            about_page()
        else:
            home_page()
    else:
        # logged in
        user = st.session_state.user

        # show profile/logout header inside each dashboard via header_bar()
        if st.session_state.page == "Profile":
            profile_page(user)
        else:
            if user["Role"] == "Provider":
                provider_dashboard(user)
            elif user["Role"] == "Receiver":
                receiver_dashboard(user)
            elif user["Role"] == "Admin":
                admin_dashboard(user)
            else:
                st.info("Unknown role. Please contact administrator.")
                if st.button("Logout"):
                    logout()
                    st.rerun()

if __name__ == "__main__":
    main()
