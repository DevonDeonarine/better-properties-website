"""
Better Properties — Flask Backend with PostgreSQL (Supabase)
=============================================================
Admin Login: manager / admin123

This version uses:
- PostgreSQL via Supabase (permanent data storage)
- CSRF protection
- Property image gallery
- Admin dashboard
"""

from flask import Flask, render_template, request, jsonify, redirect, url_for, session, flash, send_from_directory
from datetime import datetime, timedelta
import os, re, json, hashlib, secrets, threading, time
import psycopg2
import psycopg2.extras

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', secrets.token_hex(32))

# ================================================================
#  CONFIGURATION
# ================================================================
WHATSAPP_NUMBER   = "18681234567"
BUSINESS_EMAIL    = "info@betterproperties.com"
BUSINESS_PHONE    = "+1 (868) 123-4567"
BUSINESS_NAME     = "Better Properties"
BUSINESS_SUB      = "Real Estate Services Ltd"
BUSINESS_LOCATION = "Trinidad & Tobago"
SOLD_EXPIRY_DAYS  = 7
AUTO_CLEANUP_HOURS = 1
MAX_PHOTOS = 21

# Social Media Links
FACEBOOK_URL    = "https://facebook.com/betterproperties"
INSTAGRAM_URL   = "https://instagram.com/betterproperties"

# ================================================================
#  DATABASE CONNECTION (Supabase PostgreSQL)
# ================================================================
DATABASE_URL = os.environ.get('DATABASE_URL')

if not DATABASE_URL:
    print("⚠️ WARNING: DATABASE_URL not set! Using SQLite fallback (data will be lost on redeploy)")
    print("   Please add DATABASE_URL in Leapcell: Settings → Environment Variables")

def get_db():
    """Return a database connection (PostgreSQL if available, otherwise SQLite)"""
    if DATABASE_URL:
        return psycopg2.connect(DATABASE_URL)
    else:
        import sqlite3
        conn = sqlite3.connect('/tmp/better_properties.db')
        conn.row_factory = sqlite3.Row
        return conn

def hash_pw(p):
    salt = "better_properties_salt_2026"
    return hashlib.sha256((p + salt).encode()).hexdigest()

def init_db():
    """Create all tables if they don't exist"""
    conn = get_db()
    
    if DATABASE_URL:
        # PostgreSQL mode (Supabase)
        c = conn.cursor()
        
        # Create users table
        c.execute("""
            CREATE TABLE IF NOT EXISTS users (
                username TEXT PRIMARY KEY,
                password TEXT NOT NULL,
                role TEXT DEFAULT 'employee',
                full_name TEXT DEFAULT '',
                email TEXT DEFAULT '',
                phone TEXT DEFAULT ''
            )
        """)
        
        # Create properties table
        c.execute("""
            CREATE TABLE IF NOT EXISTS properties (
                id SERIAL PRIMARY KEY,
                title TEXT NOT NULL,
                price INTEGER DEFAULT 0,
                listing_type TEXT DEFAULT 'sale',
                property_type TEXT DEFAULT 'residential',
                status TEXT DEFAULT 'Available',
                description TEXT DEFAULT '',
                map_url TEXT DEFAULT '',
                images TEXT DEFAULT '[]',
                badge TEXT DEFAULT '',
                agent TEXT DEFAULT '',
                agent_id TEXT DEFAULT '',
                views INTEGER DEFAULT 0,
                inquiries INTEGER DEFAULT 0,
                sold_at TIMESTAMP DEFAULT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                area TEXT DEFAULT '',
                bedrooms INTEGER DEFAULT 0,
                bathrooms INTEGER DEFAULT 0,
                living_rooms INTEGER DEFAULT 0,
                kitchens INTEGER DEFAULT 0,
                garages INTEGER DEFAULT 0,
                sqft INTEGER DEFAULT 0,
                offices INTEGER DEFAULT 0,
                conference_rooms INTEGER DEFAULT 0,
                parking_spaces INTEGER DEFAULT 0,
                floor_number INTEGER DEFAULT 0,
                featured INTEGER DEFAULT 0
            )
        """)
        
        # Create viewing_requests table
        c.execute("""
            CREATE TABLE IF NOT EXISTS viewing_requests (
                id SERIAL PRIMARY KEY,
                property TEXT,
                name TEXT,
                email TEXT,
                phone TEXT,
                requested_dt TEXT,
                submitted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Create analytics table
        c.execute("""
            CREATE TABLE IF NOT EXISTS analytics (
                date TEXT PRIMARY KEY,
                views INTEGER DEFAULT 0,
                inquiries INTEGER DEFAULT 0
            )
        """)
        
        # Create agents table
        c.execute("""
            CREATE TABLE IF NOT EXISTS agents (
                id SERIAL PRIMARY KEY,
                username TEXT UNIQUE,
                name TEXT NOT NULL,
                phone TEXT DEFAULT '',
                email TEXT DEFAULT '',
                photo TEXT DEFAULT '',
                bio TEXT DEFAULT ''
            )
        """)
        
        # Insert default admin user if not exists
        c.execute("SELECT username FROM users WHERE username='manager'")
        if not c.fetchone():
            c.execute("""
                INSERT INTO users (username, password, role, full_name, email, phone)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, ("manager", hash_pw("admin123"), "manager", "System Administrator", "admin@betterproperties.com", "18681234567"))
            
            c.execute("""
                INSERT INTO users (username, password, role, full_name, email, phone)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, ("employee1", hash_pw("emp123"), "employee", "John Smith", "john@betterproperties.com", "18687654321"))
            
            c.execute("""
                INSERT INTO agents (username, name, phone, email)
                VALUES (%s, %s, %s, %s)
            """, ("employee1", "John Smith", "18687654321", "john@betterproperties.com"))
        
        conn.commit()
        conn.close()
        print("✅ PostgreSQL database ready! Data will persist permanently.")
        
    else:
        # SQLite fallback (local testing only - data will be lost on redeploy)
        import sqlite3
        conn = sqlite3.connect('/tmp/better_properties.db')
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        
        c.execute("""CREATE TABLE IF NOT EXISTS users (
            username TEXT PRIMARY KEY,
            password TEXT NOT NULL,
            role TEXT DEFAULT 'employee',
            full_name TEXT DEFAULT '',
            email TEXT DEFAULT '',
            phone TEXT DEFAULT ''
        )""")
        
        c.execute("""CREATE TABLE IF NOT EXISTS properties (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            price INTEGER DEFAULT 0,
            listing_type TEXT DEFAULT 'sale',
            property_type TEXT DEFAULT 'residential',
            status TEXT DEFAULT 'Available',
            description TEXT DEFAULT '',
            map_url TEXT DEFAULT '',
            images TEXT DEFAULT '[]',
            badge TEXT DEFAULT '',
            agent TEXT DEFAULT '',
            agent_id TEXT DEFAULT '',
            views INTEGER DEFAULT 0,
            inquiries INTEGER DEFAULT 0,
            sold_at TEXT DEFAULT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            area TEXT DEFAULT '',
            bedrooms INTEGER DEFAULT 0,
            bathrooms INTEGER DEFAULT 0,
            living_rooms INTEGER DEFAULT 0,
            kitchens INTEGER DEFAULT 0,
            garages INTEGER DEFAULT 0,
            sqft INTEGER DEFAULT 0,
            offices INTEGER DEFAULT 0,
            conference_rooms INTEGER DEFAULT 0,
            parking_spaces INTEGER DEFAULT 0,
            floor_number INTEGER DEFAULT 0,
            featured INTEGER DEFAULT 0
        )""")
        
        c.execute("""CREATE TABLE IF NOT EXISTS viewing_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            property TEXT, name TEXT, email TEXT, phone TEXT,
            requested_dt TEXT, submitted_at TEXT DEFAULT CURRENT_TIMESTAMP
        )""")
        
        c.execute("""CREATE TABLE IF NOT EXISTS analytics (
            date TEXT PRIMARY KEY, views INTEGER DEFAULT 0, inquiries INTEGER DEFAULT 0
        )""")
        
        c.execute("""CREATE TABLE IF NOT EXISTS agents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE,
            name TEXT NOT NULL,
            phone TEXT DEFAULT '',
            email TEXT DEFAULT '',
            photo TEXT DEFAULT '',
            bio TEXT DEFAULT ''
        )""")
        
        c.execute("SELECT username FROM users WHERE username='manager'")
        if not c.fetchone():
            c.execute("INSERT INTO users (username, password, role, full_name) VALUES (?,?,?,?)",
                      ("manager", hash_pw("admin123"), "manager", "System Administrator"))
            c.execute("INSERT INTO users (username, password, role, full_name) VALUES (?,?,?,?)",
                      ("employee1", hash_pw("emp123"), "employee", "John Smith"))
            c.execute("INSERT INTO agents (username, name, phone, email) VALUES (?,?,?,?)",
                      ("employee1", "John Smith", "18687654321", "john@betterproperties.com"))
        
        conn.commit()
        conn.close()
        print("⚠️ Using SQLite fallback (data will be lost on redeploy)")

# ================================================================
#  CSRF PROTECTION
# ================================================================
def get_csrf_token():
    if 'csrf_token' not in session:
        session['csrf_token'] = secrets.token_hex(32)
    return session['csrf_token']

@app.context_processor
def inject_csrf():
    return dict(csrf_token=get_csrf_token)

def validate_csrf():
    form_token = request.form.get('_csrf')
    session_token = session.get('csrf_token')
    if not form_token or not session_token or form_token != session_token:
        return False
    return True

# ================================================================
#  HELPER FUNCTIONS
# ================================================================
def fmt_price(p):
    try:
        return "{:,}".format(int(p))
    except:
        return str(p)

def safe_int(v, d=0):
    try:
        return int(float(str(v).strip()))
    except:
        return d

def get_agents():
    conn = get_db()
    if DATABASE_URL:
        c = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        c.execute("SELECT * FROM agents ORDER BY name")
        rows = c.fetchall()
    else:
        c = conn.cursor()
        c.execute("SELECT * FROM agents ORDER BY name")
        rows = c.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def get_areas():
    conn = get_db()
    if DATABASE_URL:
        c = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        c.execute("SELECT DISTINCT area FROM properties WHERE area != '' ORDER BY area")
        rows = c.fetchall()
    else:
        c = conn.cursor()
        c.execute("SELECT DISTINCT area FROM properties WHERE area != '' ORDER BY area")
        rows = c.fetchall()
    conn.close()
    return [row["area"] for row in rows]

# ================================================================
#  PUBLIC ROUTES
# ================================================================
@app.route("/")
def index():
    conn = get_db()
    if DATABASE_URL:
        c = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        c.execute("SELECT * FROM properties ORDER BY id DESC")
        rows = c.fetchall()
    else:
        c = conn.cursor()
        c.execute("SELECT * FROM properties ORDER BY id DESC")
        rows = c.fetchall()
    conn.close()
    
    props = [dict(row) for row in rows]
    for p in props:
        try:
            p["images"] = json.loads(p.get("images", "[]"))
        except:
            p["images"] = []
    
    config_data = {
        "name": BUSINESS_NAME, "sub": BUSINESS_SUB, "location": BUSINESS_LOCATION,
        "email": BUSINESS_EMAIL, "phone": BUSINESS_PHONE, "whatsapp": WHATSAPP_NUMBER,
        "expiry_days": SOLD_EXPIRY_DAYS, "facebook": FACEBOOK_URL, "instagram": INSTAGRAM_URL
    }
    
    return render_template("index.html", 
        props=props, 
        config=config_data,
        fmt_price=fmt_price)

@app.route("/property/<int:property_id>")
def view_property(property_id):
    """View a single property's full details"""
    conn = get_db()
    if DATABASE_URL:
        c = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        c.execute("SELECT * FROM properties WHERE id = %s", (property_id,))
        row = c.fetchone()
    else:
        c = conn.cursor()
        c.execute("SELECT * FROM properties WHERE id = ?", (property_id,))
        row = c.fetchone()
    conn.close()
    
    if not row:
        return "Property not found", 404
    
    property_data = dict(row)
    try:
        property_data["images"] = json.loads(property_data.get("images", "[]"))
    except:
        property_data["images"] = []
    
    config_data = {
        "name": BUSINESS_NAME, "sub": BUSINESS_SUB, "location": BUSINESS_LOCATION,
        "email": BUSINESS_EMAIL, "phone": BUSINESS_PHONE, "whatsapp": WHATSAPP_NUMBER,
        "expiry_days": SOLD_EXPIRY_DAYS, "facebook": FACEBOOK_URL, "instagram": INSTAGRAM_URL
    }
    
    return render_template("property_detail.html", 
        property=property_data, 
        config=config_data,
        fmt_price=fmt_price)

@app.route("/api/property/<int:pid>")
def get_public_property_json(pid):
    """API endpoint for property details (used by AJAX)"""
    try:
        conn = get_db()
        if DATABASE_URL:
            c = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
            c.execute("SELECT * FROM properties WHERE id = %s", (pid,))
            row = c.fetchone()
        else:
            c = conn.cursor()
            c.execute("SELECT * FROM properties WHERE id = ?", (pid,))
            row = c.fetchone()
        conn.close()
        
        if not row:
            return jsonify({"error": "Property not found"}), 404
        
        d = dict(row)
        try:
            d["images"] = json.loads(d.get("images", "[]"))
        except:
            d["images"] = []
        
        return jsonify(d)
    
    except Exception as e:
        print(f"API Error: {e}")
        return jsonify({"error": str(e)}), 500

@app.route("/track/view/<path:title>")
def track_view(title):
    return "", 204

@app.route("/track/inquiry/<path:title>")
def track_inquiry(title):
    return "", 204

@app.route("/viewing", methods=["POST"])
def submit_viewing():
    data = request.get_json()
    conn = get_db()
    if DATABASE_URL:
        c = conn.cursor()
        c.execute("""
            INSERT INTO viewing_requests (property, name, email, phone, requested_dt)
            VALUES (%s, %s, %s, %s, %s)
        """, (data.get("property"), data.get("name"), data.get("email"), data.get("phone"), data.get("datetime")))
    else:
        c = conn.cursor()
        c.execute("""
            INSERT INTO viewing_requests (property, name, email, phone, requested_dt)
            VALUES (?, ?, ?, ?, ?)
        """, (data.get("property"), data.get("name"), data.get("email"), data.get("phone"), data.get("datetime")))
    conn.commit()
    conn.close()
    return jsonify({"ok": True})

# ================================================================
#  ADMIN ROUTES
# ================================================================
def login_required(f):
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("username"):
            return redirect(url_for("admin_login"))
        return f(*args, **kwargs)
    return decorated

def mgr_required(f):
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if session.get("role") != "manager":
            flash("❌ Manager access required")
            return redirect(url_for("admin_dashboard"))
        return f(*args, **kwargs)
    return decorated

@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        if not validate_csrf():
            flash("❌ Invalid security token", "error")
            return redirect(url_for("admin_login"))
        
        u = request.form.get("username", "")
        p = request.form.get("password", "")
        
        conn = get_db()
        if DATABASE_URL:
            c = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
            c.execute("SELECT * FROM users WHERE username = %s", (u,))
            row = c.fetchone()
        else:
            c = conn.cursor()
            c.execute("SELECT * FROM users WHERE username = ?", (u,))
            row = c.fetchone()
        conn.close()
        
        if row and row["password"] == hash_pw(p):
            session["username"] = u
            session["role"] = row["role"]
            try:
                full_name = row["full_name"] if row["full_name"] else u
            except:
                full_name = u
            session["full_name"] = full_name
            flash(f"✅ Welcome back, {session['full_name']}!")
            return redirect(url_for("admin_dashboard"))
        flash("❌ Invalid credentials", "error")
    return render_template("admin_login.html", config={"name": BUSINESS_NAME})

@app.route("/admin/logout")
def admin_logout():
    session.clear()
    flash("✅ Logged out successfully")
    return redirect(url_for("admin_login"))

@app.route("/admin")
@login_required
def admin_dashboard():
    conn = get_db()
    username = session["username"]
    role = session["role"]
    
    if DATABASE_URL:
        c = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        if role == "manager":
            c.execute("SELECT * FROM properties ORDER BY id DESC")
        else:
            c.execute("SELECT * FROM properties WHERE agent_id = %s ORDER BY id DESC", (username,))
        rows = c.fetchall()
    else:
        c = conn.cursor()
        if role == "manager":
            c.execute("SELECT * FROM properties ORDER BY id DESC")
        else:
            c.execute("SELECT * FROM properties WHERE agent_id = ? ORDER BY id DESC", (username,))
        rows = c.fetchall()
    
    props = [dict(row) for row in rows]
    for p in props:
        try:
            p["images"] = json.loads(p.get("images", "[]"))
        except:
            p["images"] = []
    
    # Get agents and users
    agents = get_agents()
    
    if DATABASE_URL:
        c = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        c.execute("SELECT username, role, full_name FROM users")
        users = [dict(row) for row in c.fetchall()]
        c.execute("SELECT * FROM viewing_requests ORDER BY id DESC")
        requests = [dict(row) for row in c.fetchall()]
        c.execute("SELECT * FROM analytics ORDER BY date DESC LIMIT 7")
        days = [dict(row) for row in c.fetchall()]
    else:
        c = conn.cursor()
        c.execute("SELECT username, role, full_name FROM users")
        users = [dict(row) for row in c.fetchall()]
        c.execute("SELECT * FROM viewing_requests ORDER BY id DESC")
        requests = [dict(row) for row in c.fetchall()]
        c.execute("SELECT * FROM analytics ORDER BY date DESC LIMIT 7")
        days = [dict(row) for row in c.fetchall()]
    
    days = list(reversed(days))
    
    conn.close()
    
    return render_template("admin.html",
        props=props,
        agents=agents,
        users=users,
        requests=requests,
        analytics_days=days,
        total_props=len(props),
        total_requests=len(requests),
        areas=get_areas(),
        agent_names=[a["name"] for a in agents],
        config={"name": BUSINESS_NAME, "sub": BUSINESS_SUB,
                "expiry_days": SOLD_EXPIRY_DAYS, "cleanup_hours": AUTO_CLEANUP_HOURS,
                "facebook": FACEBOOK_URL, "instagram": INSTAGRAM_URL},
        fmt_price=fmt_price,
        session=session,
        max_photos=MAX_PHOTOS,
        role=role)

# ── Properties ──────────────────────────────────────────────────
@app.route("/admin/property/add", methods=["POST"])
@login_required
def admin_add_property():
    try:
        f = request.form
        property_type = f.get("property_type", "residential")
        listing_type = f.get("listing_type", "sale")
        username = session["username"]
        
        # Collect images from form
        imgs = []
        for i in range(1, MAX_PHOTOS + 1):
            url = f.get(f"img{i}_url", "").strip()
            if url:
                imgs.append(url)
        
        sold_at = datetime.now().isoformat() if f.get("status") in ['Sold', 'Rented', 'Leased'] else None
        
        conn = get_db()
        
        # Get agent name
        if DATABASE_URL:
            c = conn.cursor()
            c.execute("SELECT full_name FROM users WHERE username = %s", (username,))
            row = c.fetchone()
        else:
            c = conn.cursor()
            c.execute("SELECT full_name FROM users WHERE username = ?", (username,))
            row = c.fetchone()
        agent_name = row[0] if row and row[0] else username
        
        title = f.get("title", "").strip()
        if not title:
            flash("❌ Title is required", "error")
            return redirect(url_for("admin_dashboard") + "#properties")
        
        if property_type == "residential":
            if DATABASE_URL:
                c.execute("""
                    INSERT INTO properties
                    (title, price, listing_type, property_type, status, description, map_url, images,
                     featured, agent, agent_id, sold_at, area, badge,
                     bedrooms, bathrooms, living_rooms, kitchens, garages, sqft)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    title, safe_int(f.get("price", 0)), listing_type, property_type,
                    f.get("status", "Available"), f.get("description", "").strip(),
                    f.get("map_url", "").strip(), json.dumps(imgs),
                    1 if f.get("featured") else 0, agent_name, username, sold_at,
                    f.get("area", "").strip(), f.get("badge", "").strip(),
                    safe_int(f.get("bedrooms", 0)), safe_int(f.get("bathrooms", 0)),
                    safe_int(f.get("living_rooms", 0)), safe_int(f.get("kitchens", 0)),
                    safe_int(f.get("garages", 0)), safe_int(f.get("sqft", 0))
                ))
            else:
                c.execute("""
                    INSERT INTO properties
                    (title, price, listing_type, property_type, status, description, map_url, images,
                     featured, agent, agent_id, sold_at, area, badge,
                     bedrooms, bathrooms, living_rooms, kitchens, garages, sqft)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    title, safe_int(f.get("price", 0)), listing_type, property_type,
                    f.get("status", "Available"), f.get("description", "").strip(),
                    f.get("map_url", "").strip(), json.dumps(imgs),
                    1 if f.get("featured") else 0, agent_name, username, sold_at,
                    f.get("area", "").strip(), f.get("badge", "").strip(),
                    safe_int(f.get("bedrooms", 0)), safe_int(f.get("bathrooms", 0)),
                    safe_int(f.get("living_rooms", 0)), safe_int(f.get("kitchens", 0)),
                    safe_int(f.get("garages", 0)), safe_int(f.get("sqft", 0))
                ))
        else:
            # Commercial property
            if DATABASE_URL:
                c.execute("""
                    INSERT INTO properties
                    (title, price, listing_type, property_type, status, description, map_url, images,
                     featured, agent, agent_id, sold_at, area, badge,
                     offices, conference_rooms, bathrooms, kitchens, parking_spaces, sqft, floor_number)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    title, safe_int(f.get("price", 0)), listing_type, property_type,
                    f.get("status", "Available"), f.get("description", "").strip(),
                    f.get("map_url", "").strip(), json.dumps(imgs),
                    1 if f.get("featured") else 0, agent_name, username, sold_at,
                    f.get("area", "").strip(), f.get("badge", "").strip(),
                    safe_int(f.get("offices", 0)), safe_int(f.get("conference_rooms", 0)),
                    safe_int(f.get("bathrooms", 0)), safe_int(f.get("kitchens", 0)),
                    safe_int(f.get("parking_spaces", 0)), safe_int(f.get("sqft", 0)),
                    safe_int(f.get("floor_number", 0))
                ))
            else:
                c.execute("""
                    INSERT INTO properties
                    (title, price, listing_type, property_type, status, description, map_url, images,
                     featured, agent, agent_id, sold_at, area, badge,
                     offices, conference_rooms, bathrooms, kitchens, parking_spaces, sqft, floor_number)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    title, safe_int(f.get("price", 0)), listing_type, property_type,
                    f.get("status", "Available"), f.get("description", "").strip(),
                    f.get("map_url", "").strip(), json.dumps(imgs),
                    1 if f.get("featured") else 0, agent_name, username, sold_at,
                    f.get("area", "").strip(), f.get("badge", "").strip(),
                    safe_int(f.get("offices", 0)), safe_int(f.get("conference_rooms", 0)),
                    safe_int(f.get("bathrooms", 0)), safe_int(f.get("kitchens", 0)),
                    safe_int(f.get("parking_spaces", 0)), safe_int(f.get("sqft", 0)),
                    safe_int(f.get("floor_number", 0))
                ))
        
        conn.commit()
        conn.close()
        flash(f"✅ '{title}' added successfully!")
        return redirect(url_for("admin_dashboard") + "#properties")
    
    except Exception as e:
        import traceback
        print(traceback.format_exc())
        flash(f"❌ Error adding property: {str(e)}", "error")
        return redirect(url_for("admin_dashboard") + "#properties")

@app.route("/admin/property/edit/<int:pid>", methods=["POST"])
@login_required
def admin_edit_property(pid):
    f = request.form
    conn = get_db()
    
    # Get old property data
    if DATABASE_URL:
        c = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        c.execute("SELECT * FROM properties WHERE id = %s", (pid,))
        old = c.fetchone()
    else:
        c = conn.cursor()
        c.execute("SELECT * FROM properties WHERE id = ?", (pid,))
        old = c.fetchone()
    
    if not old:
        conn.close()
        flash("❌ Property not found")
        return redirect(url_for("admin_dashboard"))
    
    property_type = f.get("property_type", old["property_type"])
    listing_type = f.get("listing_type", old["listing_type"])
    
    # Collect images
    old_imgs = json.loads(old["images"]) if isinstance(old["images"], str) else (old["images"] or [])
    imgs = []
    for i in range(1, MAX_PHOTOS + 1):
        url = f.get(f"img{i}_url", "").strip()
        if url:
            imgs.append(url)
        elif len(old_imgs) >= i:
            imgs.append(old_imgs[i-1])
    
    status = f.get("status", "Available")
    sold_at = old["sold_at"] if status in ['Sold', 'Rented', 'Leased'] and old["sold_at"] else (datetime.now().isoformat() if status in ['Sold', 'Rented', 'Leased'] else None)
    
    if DATABASE_URL:
        if property_type == "residential":
            c.execute("""
                UPDATE properties SET
                    title=%s, price=%s, listing_type=%s, property_type=%s, status=%s,
                    description=%s, map_url=%s, images=%s, featured=%s, sold_at=%s,
                    area=%s, badge=%s, bedrooms=%s, bathrooms=%s, living_rooms=%s,
                    kitchens=%s, garages=%s, sqft=%s
                WHERE id=%s
            """, (
                f.get("title", "").strip(), safe_int(f.get("price", 0)), listing_type, property_type, status,
                f.get("description", "").strip(), f.get("map_url", "").strip(), json.dumps(imgs),
                1 if f.get("featured") else 0, sold_at, f.get("area", "").strip(), f.get("badge", "").strip(),
                safe_int(f.get("bedrooms", 0)), safe_int(f.get("bathrooms", 0)),
                safe_int(f.get("living_rooms", 0)), safe_int(f.get("kitchens", 0)),
                safe_int(f.get("garages", 0)), safe_int(f.get("sqft", 0)), pid
            ))
        else:
            c.execute("""
                UPDATE properties SET
                    title=%s, price=%s, listing_type=%s, property_type=%s, status=%s,
                    description=%s, map_url=%s, images=%s, featured=%s, sold_at=%s,
                    area=%s, badge=%s, offices=%s, conference_rooms=%s, bathrooms=%s,
                    kitchens=%s, parking_spaces=%s, sqft=%s, floor_number=%s
                WHERE id=%s
            """, (
                f.get("title", "").strip(), safe_int(f.get("price", 0)), listing_type, property_type, status,
                f.get("description", "").strip(), f.get("map_url", "").strip(), json.dumps(imgs),
                1 if f.get("featured") else 0, sold_at, f.get("area", "").strip(), f.get("badge", "").strip(),
                safe_int(f.get("offices", 0)), safe_int(f.get("conference_rooms", 0)),
                safe_int(f.get("bathrooms", 0)), safe_int(f.get("kitchens", 0)),
                safe_int(f.get("parking_spaces", 0)), safe_int(f.get("sqft", 0)),
                safe_int(f.get("floor_number", 0)), pid
            ))
    else:
        if property_type == "residential":
            c.execute("""
                UPDATE properties SET
                    title=?, price=?, listing_type=?, property_type=?, status=?,
                    description=?, map_url=?, images=?, featured=?, sold_at=?,
                    area=?, badge=?, bedrooms=?, bathrooms=?, living_rooms=?,
                    kitchens=?, garages=?, sqft=?
                WHERE id=?
            """, (
                f.get("title", "").strip(), safe_int(f.get("price", 0)), listing_type, property_type, status,
                f.get("description", "").strip(), f.get("map_url", "").strip(), json.dumps(imgs),
                1 if f.get("featured") else 0, sold_at, f.get("area", "").strip(), f.get("badge", "").strip(),
                safe_int(f.get("bedrooms", 0)), safe_int(f.get("bathrooms", 0)),
                safe_int(f.get("living_rooms", 0)), safe_int(f.get("kitchens", 0)),
                safe_int(f.get("garages", 0)), safe_int(f.get("sqft", 0)), pid
            ))
        else:
            c.execute("""
                UPDATE properties SET
                    title=?, price=?, listing_type=?, property_type=?, status=?,
                    description=?, map_url=?, images=?, featured=?, sold_at=?,
                    area=?, badge=?, offices=?, conference_rooms=?, bathrooms=?,
                    kitchens=?, parking_spaces=?, sqft=?, floor_number=?
                WHERE id=?
            """, (
                f.get("title", "").strip(), safe_int(f.get("price", 0)), listing_type, property_type, status,
                f.get("description", "").strip(), f.get("map_url", "").strip(), json.dumps(imgs),
                1 if f.get("featured") else 0, sold_at, f.get("area", "").strip(), f.get("badge", "").strip(),
                safe_int(f.get("offices", 0)), safe_int(f.get("conference_rooms", 0)),
                safe_int(f.get("bathrooms", 0)), safe_int(f.get("kitchens", 0)),
                safe_int(f.get("parking_spaces", 0)), safe_int(f.get("sqft", 0)),
                safe_int(f.get("floor_number", 0)), pid
            ))
    
    conn.commit()
    conn.close()
    flash(f"✅ Property updated!")
    return redirect(url_for("admin_dashboard") + "#properties")

@app.route("/admin/property/delete/<int:pid>", methods=["POST"])
@login_required
def admin_delete_property(pid):
    conn = get_db()
    if DATABASE_URL:
        c = conn.cursor()
        c.execute("DELETE FROM properties WHERE id = %s", (pid,))
    else:
        c = conn.cursor()
        c.execute("DELETE FROM properties WHERE id = ?", (pid,))
    conn.commit()
    conn.close()
    flash(f"✅ Property removed.")
    return redirect(url_for("admin_dashboard") + "#properties")

@app.route("/admin/property/<int:pid>/json")
@login_required
def get_property_json(pid):
    conn = get_db()
    if DATABASE_URL:
        c = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        c.execute("SELECT * FROM properties WHERE id = %s", (pid,))
        row = c.fetchone()
    else:
        c = conn.cursor()
        c.execute("SELECT * FROM properties WHERE id = ?", (pid,))
        row = c.fetchone()
    conn.close()
    
    if not row:
        return jsonify({}), 404
    d = dict(row)
    try:
        d["images"] = json.loads(d.get("images", "[]"))
    except:
        d["images"] = []
    return jsonify(d)

# ── Agents ──────────────────────────────────────────────────────
@app.route("/admin/agent/add", methods=["POST"])
@mgr_required
def admin_add_agent():
    f = request.form
    conn = get_db()
    if DATABASE_URL:
        c = conn.cursor()
        c.execute("""
            INSERT INTO agents (name, phone, email, bio)
            VALUES (%s, %s, %s, %s)
        """, (f.get("name", "").strip(), f.get("phone", "").strip(),
              f.get("email", "").strip(), f.get("bio", "").strip()))
    else:
        c = conn.cursor()
        c.execute("""
            INSERT INTO agents (name, phone, email, bio)
            VALUES (?, ?, ?, ?)
        """, (f.get("name", "").strip(), f.get("phone", "").strip(),
              f.get("email", "").strip(), f.get("bio", "").strip()))
    conn.commit()
    conn.close()
    flash(f"✅ Agent '{f.get('name')}' added.")
    return redirect(url_for("admin_dashboard") + "#agents")

@app.route("/admin/agent/delete/<int:aid>", methods=["POST"])
@mgr_required
def admin_delete_agent(aid):
    conn = get_db()
    if DATABASE_URL:
        c = conn.cursor()
        c.execute("DELETE FROM agents WHERE id = %s", (aid,))
    else:
        c = conn.cursor()
        c.execute("DELETE FROM agents WHERE id = ?", (aid,))
    conn.commit()
    conn.close()
    flash("✅ Agent removed.")
    return redirect(url_for("admin_dashboard") + "#agents")

@app.route("/admin/agent/edit/<int:aid>", methods=["POST"])
@mgr_required
def admin_edit_agent(aid):
    f = request.form
    conn = get_db()
    if DATABASE_URL:
        c = conn.cursor()
        c.execute("""
            UPDATE agents SET name=%s, phone=%s, email=%s, bio=%s
            WHERE id=%s
        """, (f.get("name", "").strip(), f.get("phone", "").strip(),
              f.get("email", "").strip(), f.get("bio", "").strip(), aid))
    else:
        c = conn.cursor()
        c.execute("""
            UPDATE agents SET name=?, phone=?, email=?, bio=?
            WHERE id=?
        """, (f.get("name", "").strip(), f.get("phone", "").strip(),
              f.get("email", "").strip(), f.get("bio", "").strip(), aid))
    conn.commit()
    conn.close()
    flash(f"✅ Agent '{f.get('name')}' updated.")
    return redirect(url_for("admin_dashboard") + "#agents")

# ── Users ────────────────────────────────────────────────────────
@app.route("/admin/user/add", methods=["POST"])
@mgr_required
def admin_add_user():
    f = request.form
    conn = get_db()
    try:
        if DATABASE_URL:
            c = conn.cursor()
            c.execute("""
                INSERT INTO users (username, password, role, full_name, email, phone)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (f.get("username", "").strip(), hash_pw(f.get("password", "")),
                  f.get("role", "employee"), f.get("full_name", "").strip(),
                  f.get("email", "").strip(), f.get("phone", "").strip()))
        else:
            c = conn.cursor()
            c.execute("""
                INSERT INTO users (username, password, role, full_name, email, phone)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (f.get("username", "").strip(), hash_pw(f.get("password", "")),
                  f.get("role", "employee"), f.get("full_name", "").strip(),
                  f.get("email", "").strip(), f.get("phone", "").strip()))
        conn.commit()
        flash(f"✅ User '{f.get('username')}' created.")
    except Exception as e:
        flash(f"❌ Username already exists.")
    conn.close()
    return redirect(url_for("admin_dashboard") + "#users")

@app.route("/admin/user/delete/<username>", methods=["POST"])
@mgr_required
def admin_delete_user(username):
    if username == "manager":
        flash("❌ Cannot delete main manager.")
        return redirect(url_for("admin_dashboard") + "#users")
    conn = get_db()
    if DATABASE_URL:
        c = conn.cursor()
        c.execute("DELETE FROM users WHERE username = %s", (username,))
        c.execute("DELETE FROM agents WHERE username = %s", (username,))
    else:
        c = conn.cursor()
        c.execute("DELETE FROM users WHERE username = ?", (username,))
        c.execute("DELETE FROM agents WHERE username = ?", (username,))
    conn.commit()
    conn.close()
    flash(f"✅ User '{username}' removed.")
    return redirect(url_for("admin_dashboard") + "#users")

@app.route("/admin/user/password", methods=["POST"])
@mgr_required
def admin_change_password():
    f = request.form
    username = f.get("username", "")
    new_password = f.get("new_password", "")
    
    if not username or not new_password:
        flash("❌ Username and password are required", "error")
        return redirect(url_for("admin_dashboard") + "#users")
    
    if len(new_password) < 4:
        flash("❌ Password must be at least 4 characters", "error")
        return redirect(url_for("admin_dashboard") + "#users")
    
    conn = get_db()
    if DATABASE_URL:
        c = conn.cursor()
        c.execute("UPDATE users SET password = %s WHERE username = %s", (hash_pw(new_password), username))
    else:
        c = conn.cursor()
        c.execute("UPDATE users SET password = ? WHERE username = ?", (hash_pw(new_password), username))
    conn.commit()
    conn.close()
    
    flash(f"✅ Password updated for '{username}'!", "success")
    return redirect(url_for("admin_dashboard") + "#users")

@app.route("/admin/user/change_my_password", methods=["POST"])
@login_required
def change_my_password():
    username = session["username"]
    current = request.form.get("current_password", "")
    new_password = request.form.get("new_password", "")
    confirm = request.form.get("confirm_password", "")
    
    if not validate_csrf():
        flash("❌ Invalid security token", "error")
        return redirect(url_for("admin_dashboard") + "#settings")
    
    if new_password != confirm:
        flash("❌ New passwords do not match", "error")
        return redirect(url_for("admin_dashboard") + "#settings")
    
    if len(new_password) < 8:
        flash("❌ Password must be at least 8 characters", "error")
        return redirect(url_for("admin_dashboard") + "#settings")
    
    conn = get_db()
    if DATABASE_URL:
        c = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        c.execute("SELECT * FROM users WHERE username = %s", (username,))
        row = c.fetchone()
    else:
        c = conn.cursor()
        c.execute("SELECT * FROM users WHERE username = ?", (username,))
        row = c.fetchone()
    
    if not row or row["password"] != hash_pw(current):
        flash("❌ Current password is incorrect", "error")
    else:
        if DATABASE_URL:
            c = conn.cursor()
            c.execute("UPDATE users SET password = %s WHERE username = %s", (hash_pw(new_password), username))
        else:
            c = conn.cursor()
            c.execute("UPDATE users SET password = ? WHERE username = ?", (hash_pw(new_password), username))
        conn.commit()
        flash(f"✅ Your password has been updated!", "success")
    
    conn.close()
    return redirect(url_for("admin_dashboard") + "#settings")

# ================================================================
#  AUTO-CLEANUP THREAD (for sold/rented properties)
# ================================================================
def auto_cleanup():
    while True:
        try:
            conn = get_db()
            cutoff = (datetime.now() - timedelta(days=SOLD_EXPIRY_DAYS)).isoformat()
            
            if DATABASE_URL:
                c = conn.cursor()
                c.execute("""
                    UPDATE properties SET sold_at = %s
                    WHERE status IN ('Sold', 'Rented', 'Leased') AND (sold_at IS NULL OR sold_at = '')
                """, (datetime.now().isoformat(),))
                
                c.execute("""
                    SELECT id, title, sold_at FROM properties
                    WHERE status IN ('Sold', 'Rented', 'Leased') AND sold_at < %s
                """, (cutoff,))
                rows = c.fetchall()
                
                for r in rows:
                    c.execute("DELETE FROM properties WHERE id = %s", (r[0],))
                    print(f"Auto-deleted: {r[1]}")
                
                if rows:
                    conn.commit()
                    print(f"[Auto-cleanup] Deleted {len(rows)} expired listings")
            else:
                c = conn.cursor()
                c.execute("""
                    UPDATE properties SET sold_at = ?
                    WHERE status IN ('Sold', 'Rented', 'Leased') AND (sold_at IS NULL OR sold_at = '')
                """, (datetime.now().isoformat(),))
                
                c.execute("""
                    SELECT id, title, sold_at FROM properties
                    WHERE status IN ('Sold', 'Rented', 'Leased') AND sold_at < ?
                """, (cutoff,))
                rows = c.fetchall()
                
                for r in rows:
                    c.execute("DELETE FROM properties WHERE id = ?", (r[0],))
                    print(f"Auto-deleted: {r[1]}")
                
                if rows:
                    conn.commit()
                    print(f"[Auto-cleanup] Deleted {len(rows)} expired listings")
            
            conn.close()
        except Exception as e:
            print(f"[Auto-cleanup] Error: {e}")
        time.sleep(AUTO_CLEANUP_HOURS * 3600)

# Start cleanup thread
cleanup_thread = threading.Thread(target=auto_cleanup, daemon=True)
cleanup_thread.start()
print(f"[System] Auto-cleanup active - will delete after {SOLD_EXPIRY_DAYS} days")

# ================================================================
#  STARTUP
# ================================================================
if __name__ == "__main__":
    init_db()
    print(f"""
    ╔══════════════════════════════════════════════════════════╗
    ║     Better Properties - Real Estate Management System    ║
    ╠══════════════════════════════════════════════════════════╣
    ║  Website:    http://127.0.0.1:5000                       ║
    ║  Admin:      http://127.0.0.1:5000/admin                 ║
    ║  Login:      manager / admin123                          ║
    ╠══════════════════════════════════════════════════════════╣
    ║  Database:   {'PostgreSQL (Supabase) - PERSISTENT' if DATABASE_URL else 'SQLite (temporary)'}
    ║  Data will survive redeploys: {'YES ✅' if DATABASE_URL else 'NO ⚠️'}
    ╚══════════════════════════════════════════════════════════╝
    """)
    app.run(debug=True, port=5000)