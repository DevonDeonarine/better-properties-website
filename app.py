"""
Better Properties — Flask Backend
===================================
Run:  python app.py
Open: http://127.0.0.1:5000

Admin: http://127.0.0.1:5000/admin
Login: manager / admin123
"""

from flask import Flask, render_template, request, jsonify, redirect, url_for, session, flash, send_from_directory
from datetime import datetime, timedelta
import sqlite3, hashlib, json, os, shutil, re, threading, time, secrets, tempfile

app = Flask(__name__)

# ================================================================
#  CONFIG — edit before deploying
# ================================================================
# Use environment variable for secret key (works on Leapcell)
app.secret_key = os.environ.get('SECRET_KEY', secrets.token_hex(32))

# ================================================================
#  CSRF PROTECTION - FIXED
# ================================================================
def get_csrf_token():
    """Generate or retrieve CSRF token for form protection"""
    if 'csrf_token' not in session:
        session['csrf_token'] = secrets.token_hex(32)
    return session['csrf_token']

@app.context_processor
def inject_csrf():
    """Make csrf_token available in all templates"""
    return dict(csrf_token=get_csrf_token)

def validate_csrf():
    """Validate CSRF token from POST requests"""
    form_token = request.form.get('_csrf')
    session_token = session.get('csrf_token')
    if not form_token or not session_token or form_token != session_token:
        return False
    return True

WHATSAPP_NUMBER   = "18681234567"
BUSINESS_EMAIL    = "info@betterproperties.com"
BUSINESS_PHONE    = "+1 (868) 123-4567"
BUSINESS_NAME     = "Better Properties"
BUSINESS_SUB      = "Real Estate Services Ltd"
BUSINESS_LOCATION = "Trinidad & Tobago"
SOLD_EXPIRY_DAYS  = 7
AUTO_CLEANUP_HOURS = 1
MAX_PHOTOS = 21

# Database path - MUST use /tmp on Leapcell (only writable directory)
if os.path.exists('/tmp') or os.name == 'posix':
    DB_PATH = '/tmp/better_properties.db'
else:
    DB_PATH = os.path.join(os.path.dirname(__file__), "better_properties.db")

print(f"Database path: {DB_PATH}")

# ================================================================
#  UPLOAD DIRECTORY - FIXED FOR LEAPCELL (using /tmp)
# ================================================================
# Leapcell only allows writing to /tmp directory
UPLOAD_DIR = '/tmp/uploads'
os.makedirs(UPLOAD_DIR, exist_ok=True)
print(f"Upload directory: {UPLOAD_DIR}")

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
MAX_FILE_SIZE = 5 * 1024 * 1024

# Social Media Links
FACEBOOK_URL    = "https://facebook.com/betterproperties"
INSTAGRAM_URL   = "https://instagram.com/betterproperties"

# ================================================================
#  DATABASE
# ================================================================
def get_db():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def hash_pw(p):
    salt = "better_properties_salt_2026"
    return hashlib.sha256((p + salt).encode()).hexdigest()

def init_db():
    conn = get_db()
    c = conn.cursor()
    
    # Create users table
    c.execute("""CREATE TABLE IF NOT EXISTS users (
        username TEXT PRIMARY KEY,
        password TEXT NOT NULL,
        role     TEXT NOT NULL DEFAULT 'employee',
        full_name TEXT DEFAULT '',
        email TEXT DEFAULT '',
        phone TEXT DEFAULT ''
    )""")
    
    # Create properties table
    c.execute("""CREATE TABLE IF NOT EXISTS properties (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        title       TEXT NOT NULL,
        price       INTEGER DEFAULT 0,
        listing_type TEXT DEFAULT 'sale',
        property_type TEXT DEFAULT 'residential',
        status      TEXT DEFAULT 'Available',
        description TEXT DEFAULT '',
        map_url     TEXT DEFAULT '',
        images      TEXT DEFAULT '[]',
        badge       TEXT DEFAULT '',
        agent       TEXT DEFAULT '',
        agent_id    TEXT DEFAULT '',
        views       INTEGER DEFAULT 0,
        inquiries   INTEGER DEFAULT 0,
        sold_at     TEXT DEFAULT NULL,
        created_at  TEXT DEFAULT CURRENT_TIMESTAMP,
        area        TEXT DEFAULT '',
        bedrooms    INTEGER DEFAULT 0,
        bathrooms   INTEGER DEFAULT 0,
        living_rooms INTEGER DEFAULT 0,
        kitchens    INTEGER DEFAULT 0,
        garages     INTEGER DEFAULT 0,
        sqft        INTEGER DEFAULT 0,
        offices      INTEGER DEFAULT 0,
        conference_rooms INTEGER DEFAULT 0,
        parking_spaces INTEGER DEFAULT 0,
        floor_number INTEGER DEFAULT 0,
        featured    INTEGER DEFAULT 0
    )""")
    
    # Create viewing_requests table
    c.execute("""CREATE TABLE IF NOT EXISTS viewing_requests (
        id           INTEGER PRIMARY KEY AUTOINCREMENT,
        property     TEXT, name TEXT, email TEXT, phone TEXT,
        requested_dt TEXT,
        submitted_at TEXT DEFAULT CURRENT_TIMESTAMP
    )""")
    
    # Create analytics table
    c.execute("""CREATE TABLE IF NOT EXISTS analytics (
        date TEXT PRIMARY KEY, views INTEGER DEFAULT 0, inquiries INTEGER DEFAULT 0
    )""")
    
    # Create agents table
    c.execute("""CREATE TABLE IF NOT EXISTS agents (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE,
        name TEXT NOT NULL, phone TEXT DEFAULT '',
        email TEXT DEFAULT '', photo TEXT DEFAULT '', bio TEXT DEFAULT ''
    )""")
    
    # Create admin user
    admin_password = hash_pw("admin123")
    c.execute("INSERT OR IGNORE INTO users (username, password, role, full_name, email, phone) VALUES (?,?,?,?,?,?)", 
              ("manager", admin_password, "manager", "System Administrator", "admin@betterproperties.com", "18681234567"))
    
    # Create sample agent
    agent_password = hash_pw("emp123")
    c.execute("INSERT OR IGNORE INTO users (username, password, role, full_name, email, phone) VALUES (?,?,?,?,?,?)", 
              ("employee1", agent_password, "employee", "John Smith", "john@betterproperties.com", "18687654321"))
    c.execute("INSERT OR IGNORE INTO agents (username, name, phone, email) VALUES (?,?,?,?)",
              ("employee1", "John Smith", "18687654321", "john@betterproperties.com"))
    
    # NO SAMPLE PROPERTIES - Database starts empty to avoid column mismatch
    # Properties will be added through admin panel
    print("Database initialized successfully (empty). Add properties via admin panel.")
    
    conn.commit()
    conn.close()

def migrate_db():
    conn = get_db()
    
    user_columns = ["full_name TEXT DEFAULT ''", "email TEXT DEFAULT ''", "phone TEXT DEFAULT ''"]
    for col in user_columns:
        try:
            conn.execute(f"ALTER TABLE users ADD COLUMN {col}")
            conn.commit()
        except:
            pass
    
    prop_columns = [
        "listing_type TEXT DEFAULT 'sale'", "property_type TEXT DEFAULT 'residential'",
        "bedrooms INTEGER DEFAULT 0", "bathrooms INTEGER DEFAULT 0",
        "living_rooms INTEGER DEFAULT 0", "kitchens INTEGER DEFAULT 0",
        "garages INTEGER DEFAULT 0", "offices INTEGER DEFAULT 0",
        "conference_rooms INTEGER DEFAULT 0", "parking_spaces INTEGER DEFAULT 0",
        "floor_number INTEGER DEFAULT 0", "sqft INTEGER DEFAULT 0", "agent_id TEXT DEFAULT ''"
    ]
    for col in prop_columns:
        try:
            conn.execute(f"ALTER TABLE properties ADD COLUMN {col}")
            conn.commit()
        except:
            pass
    
    conn.close()

init_db()
migrate_db()

# ================================================================
#  AUTO-DELETE SOLD PROPERTIES
# ================================================================
def auto_cleanup():
    while True:
        try:
            conn = get_db()
            cutoff = (datetime.now() - timedelta(days=SOLD_EXPIRY_DAYS)).isoformat()
            conn.execute("""UPDATE properties SET sold_at=?
                WHERE status IN ('Sold', 'Rented', 'Leased') AND (sold_at IS NULL OR sold_at='')""",
                (datetime.now().isoformat(),))
            
            rows = conn.execute(
                "SELECT id, title, sold_at FROM properties WHERE status IN ('Sold', 'Rented', 'Leased') AND sold_at<?",
                (cutoff,)
            ).fetchall()
            
            for r in rows:
                conn.execute("DELETE FROM properties WHERE id=?", (r["id"],))
                print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Auto-deleted: {r['title']}")
            
            if rows:
                conn.commit()
                print(f"[Auto-cleanup] Deleted {len(rows)} expired listings")
            conn.close()
        except Exception as e:
            print(f"[Auto-cleanup] Error: {e}")
        time.sleep(AUTO_CLEANUP_HOURS * 3600)

cleanup_thread = threading.Thread(target=auto_cleanup, daemon=True)
cleanup_thread.start()
print(f"[System] Auto-cleanup active - will delete after {SOLD_EXPIRY_DAYS} days")

# ================================================================
#  HELPERS
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

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def get_areas():
    conn = get_db()
    rows = conn.execute("SELECT DISTINCT area FROM properties WHERE area!='' ORDER BY area").fetchall()
    conn.close()
    return [r["area"] for r in rows]

def get_agents():
    conn = get_db()
    rows = conn.execute("SELECT * FROM agents ORDER BY name").fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_property_images(images_data):
    if not images_data:
        return ["https://via.placeholder.com/400x300?text=No+Image"]
    if isinstance(images_data, str):
        try:
            images = json.loads(images_data)
        except:
            return ["https://via.placeholder.com/400x300?text=No+Image"]
    elif isinstance(images_data, list):
        images = images_data
    else:
        return ["https://via.placeholder.com/400x300?text=No+Image"]
    
    valid_images = [img for img in images if img and img.strip()]
    if not valid_images:
        return ["https://via.placeholder.com/400x300?text=No+Image"]
    return valid_images

def record_view(title):
    today = datetime.now().strftime("%Y-%m-%d")
    conn = get_db()
    conn.execute("INSERT OR IGNORE INTO analytics(date) VALUES(?)", (today,))
    conn.execute("UPDATE analytics SET views=views+1 WHERE date=?", (today,))
    conn.execute("UPDATE properties SET views=views+1 WHERE title=?", (title,))
    conn.commit()
    conn.close()

def record_inquiry(title):
    today = datetime.now().strftime("%Y-%m-%d")
    conn = get_db()
    conn.execute("INSERT OR IGNORE INTO analytics(date) VALUES(?)", (today,))
    conn.execute("UPDATE analytics SET inquiries=inquiries+1 WHERE date=?", (today,))
    conn.execute("UPDATE properties SET inquiries=inquiries+1 WHERE title=?", (title,))
    conn.commit()
    conn.close()

def save_image(file, title, idx):
    if not file or file.filename == "":
        return ""
    if not allowed_file(file.filename):
        return ""
    file.seek(0, os.SEEK_END)
    file_size = file.tell()
    file.seek(0)
    if file_size > MAX_FILE_SIZE:
        return ""
    safe = re.sub(r'[^a-zA-Z0-9_-]', '_', title)
    ext = os.path.splitext(file.filename)[-1].lower() or ".jpg"
    fname = f"{safe}_{idx}_{datetime.now().strftime('%Y%m%d%H%M%S')}{ext}"
    path = os.path.join(UPLOAD_DIR, fname)
    file.save(path)
    print(f"Image saved to: {path}")
    return f"/uploads/{fname}"

def get_expiry_stats():
    conn = get_db()
    now = datetime.now()
    props = conn.execute("SELECT title, sold_at FROM properties WHERE status IN ('Sold', 'Rented', 'Leased') AND sold_at IS NOT NULL").fetchall()
    conn.close()
    expiring_soon = []
    for p in props:
        try:
            sold = datetime.fromisoformat(p["sold_at"])
            days_left = SOLD_EXPIRY_DAYS - (now - sold).days
            if 0 < days_left <= 3:
                expiring_soon.append({"title": p["title"], "days_left": days_left})
        except:
            pass
    return expiring_soon

def user_can_edit_property(username, role, property_agent_id):
    if role == "manager":
        return True
    return username == property_agent_id

# ================================================================
#  PUBLIC ROUTES
# ================================================================
@app.route("/")
def index():
    conn = get_db()
    area = request.args.get("area", "")
    status = request.args.get("status", "")
    search = request.args.get("search", "")
    property_type = request.args.get("property_type", "")
    listing_type = request.args.get("listing_type", "")
    min_p = safe_int(request.args.get("min_price", 0))
    max_p = safe_int(request.args.get("max_price", 0))
    sort = request.args.get("sort", "newest")

    q = "SELECT * FROM properties WHERE 1=1"
    params = []
    if search:
        q += " AND (title LIKE ? OR description LIKE ?)"; params += [f"%{search}%", f"%{search}%"]
    if area:
        q += " AND area=?"; params.append(area)
    if status:
        q += " AND status=?"; params.append(status)
    if property_type:
        q += " AND property_type=?"; params.append(property_type)
    if listing_type:
        q += " AND listing_type=?"; params.append(listing_type)
    if min_p > 0:
        q += " AND price>=?"; params.append(min_p)
    if max_p > 0:
        q += " AND price<=?"; params.append(max_p)
    
    if sort == "price_asc":
        q += " ORDER BY featured DESC, price ASC"
    elif sort == "price_desc":
        q += " ORDER BY featured DESC, price DESC"
    else:
        q += " ORDER BY featured DESC, id DESC"

    rows = conn.execute(q, params).fetchall()
    props = [dict(r) for r in rows]
    
    now = datetime.now()
    for p in props:
        p["images"] = get_property_images(p.get("images"))
        if p.get("status") in ['Sold', 'Rented', 'Leased'] and p.get("sold_at"):
            try:
                sold = datetime.fromisoformat(p["sold_at"])
                p["days_left"] = SOLD_EXPIRY_DAYS - (now - sold).days
                p["expiring_soon"] = p["days_left"] <= 3 and p["days_left"] > 0
            except:
                p["days_left"] = SOLD_EXPIRY_DAYS
                p["expiring_soon"] = False
        else:
            p["days_left"] = None
            p["expiring_soon"] = False

    agents = get_agents()
    areas = get_areas()
    conn.close()

    config_data = {
        "name": BUSINESS_NAME, "sub": BUSINESS_SUB, "location": BUSINESS_LOCATION,
        "email": BUSINESS_EMAIL, "phone": BUSINESS_PHONE, "whatsapp": WHATSAPP_NUMBER,
        "expiry_days": SOLD_EXPIRY_DAYS, "facebook": FACEBOOK_URL, "instagram": INSTAGRAM_URL
    }

    return render_template("index.html",
        props=props, areas=areas, agents=agents,
        search=search, selected_area=area, selected_status=status,
        selected_property_type=property_type, selected_listing_type=listing_type,
        min_price=min_p, max_price=max_p, sort=sort,
        config=config_data, fmt_price=fmt_price)

@app.route("/track/view/<path:title>")
def track_view(title):
    record_view(title)
    return "", 204

@app.route("/track/inquiry/<path:title>")
def track_inquiry(title):
    record_inquiry(title)
    return "", 204

@app.route("/viewing", methods=["POST"])
def submit_viewing():
    data = request.get_json()
    conn = get_db()
    conn.execute("""INSERT INTO viewing_requests(property,name,email,phone,requested_dt)
        VALUES(?,?,?,?,?)""", (data.get("property"), data.get("name"),
        data.get("email"), data.get("phone"), data.get("datetime")))
    conn.commit()
    conn.close()
    record_inquiry(data.get("property", ""))
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
        # Validate CSRF token - FIXED
        if not validate_csrf():
            flash("❌ Invalid security token. Please try again.", "error")
            return redirect(url_for("admin_login"))
        
        u = request.form.get("username", "")
        p = request.form.get("password", "")
        conn = get_db()
        row = conn.execute("SELECT * FROM users WHERE username=?", (u,)).fetchone()
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
    
    if role == "manager":
        props = [dict(r) for r in conn.execute("SELECT * FROM properties ORDER BY id DESC").fetchall()]
    else:
        props = [dict(r) for r in conn.execute("SELECT * FROM properties WHERE agent_id=? ORDER BY id DESC", (username,)).fetchall()]
    
    for p in props:
        p["images"] = json.loads(p["images"]) if isinstance(p.get("images"), str) else []
    
    agents = [dict(r) for r in conn.execute("SELECT * FROM agents").fetchall()]
    users = [dict(r) for r in conn.execute("SELECT username,role,full_name FROM users").fetchall()]
    requests = [dict(r) for r in conn.execute("SELECT * FROM viewing_requests ORDER BY id DESC").fetchall()]
    days = [dict(r) for r in conn.execute("SELECT * FROM analytics ORDER BY date DESC LIMIT 7").fetchall()]
    days = list(reversed(days))
    tv = conn.execute("SELECT SUM(views) FROM properties").fetchone()[0] or 0
    ti = conn.execute("SELECT SUM(inquiries) FROM properties").fetchone()[0] or 0
    
    if role == "manager":
        sc = [dict(r) for r in conn.execute("SELECT status, COUNT(*) as c FROM properties GROUP BY status").fetchall()]
    else:
        sc = [dict(r) for r in conn.execute("SELECT status, COUNT(*) as c FROM properties WHERE agent_id=? GROUP BY status", (username,)).fetchall()]

    now = datetime.now()
    expiring_count = 0
    for p in props:
        if p.get("status") in ['Sold', 'Rented', 'Leased'] and p.get("sold_at"):
            try:
                sold = datetime.fromisoformat(p["sold_at"])
                p["days_left"] = SOLD_EXPIRY_DAYS - (now - sold).days
                if 0 < p["days_left"] <= 3:
                    expiring_count += 1
            except:
                p["days_left"] = SOLD_EXPIRY_DAYS
        else:
            p["days_left"] = None

    expiring_props = get_expiry_stats()
    conn.close()
    
    return render_template("admin.html",
        props=props, agents=agents, users=users,
        requests=requests, analytics_days=days,
        total_views=tv, total_inquiries=ti, status_counts=sc,
        total_props=len(props), total_requests=len(requests),
        areas=get_areas(), agent_names=[a["name"] for a in agents],
        config={"name": BUSINESS_NAME, "sub": BUSINESS_SUB,
                "expiry_days": SOLD_EXPIRY_DAYS, "cleanup_hours": AUTO_CLEANUP_HOURS,
                "facebook": FACEBOOK_URL, "instagram": INSTAGRAM_URL},
        expiring_count=expiring_count, expiring_props=expiring_props,
        fmt_price=fmt_price, session=session, max_photos=MAX_PHOTOS, role=role)

# ── Properties (ADD WITH DEBUG) ─────────────────────────────────
@app.route("/admin/property/add", methods=["POST"])
@login_required
def admin_add_property():
    try:
        print("=== ADD PROPERTY DEBUG ===")
        f = request.form
        property_type = f.get("property_type", "residential")
        listing_type = f.get("listing_type", "sale")
        username = session["username"]
        
        print(f"Property Type: {property_type}")
        print(f"Listing Type: {listing_type}")
        print(f"Username: {username}")
        
        imgs = []
        for i in range(1, MAX_PHOTOS + 1):
            file = request.files.get(f"img{i}_file")
            url = f.get(f"img{i}_url", "").strip()
            saved = save_image(file, f.get("title", "prop"), i)
            if saved:
                imgs.append(saved)
                print(f"Photo {i}: saved as {saved}")
            elif url:
                imgs.append(url)
                print(f"Photo {i}: using URL {url}")
        
        sold_at = datetime.now().isoformat() if f.get("status") in ['Sold', 'Rented', 'Leased'] else None
        
        conn = get_db()
        agent_row = conn.execute("SELECT full_name FROM users WHERE username=?", (username,)).fetchone()
        agent_name = agent_row["full_name"] if agent_row and agent_row["full_name"] else username
        
        title = f.get("title", "").strip()
        if not title:
            flash("❌ Title is required", "error")
            return redirect(url_for("admin_dashboard") + "#properties")
        
        print(f"Title: {title}")
        print(f"Price: {f.get('price', 0)}")
        
        if property_type == "residential":
            conn.execute("""INSERT INTO properties
                (title, price, listing_type, property_type, status, description, map_url, images,
                 featured, agent, agent_id, sold_at, area, badge,
                 bedrooms, bathrooms, living_rooms, kitchens, garages, sqft)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""", (
                title,
                safe_int(f.get("price", 0)),
                listing_type,
                property_type,
                f.get("status", "Available"),
                f.get("description", "").strip(),
                f.get("map_url", "").strip(),
                json.dumps(imgs),
                1 if f.get("featured") else 0,
                agent_name,
                username,
                sold_at,
                f.get("area", "").strip(),
                f.get("badge", "").strip(),
                safe_int(f.get("bedrooms", 0)),
                safe_int(f.get("bathrooms", 0)),
                safe_int(f.get("living_rooms", 0)),
                safe_int(f.get("kitchens", 0)),
                safe_int(f.get("garages", 0)),
                safe_int(f.get("sqft", 0))))
        else:
            conn.execute("""INSERT INTO properties
                (title, price, listing_type, property_type, status, description, map_url, images,
                 featured, agent, agent_id, sold_at, area, badge,
                 offices, conference_rooms, bathrooms, kitchens, parking_spaces, sqft, floor_number)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""", (
                title,
                safe_int(f.get("price", 0)),
                listing_type,
                property_type,
                f.get("status", "Available"),
                f.get("description", "").strip(),
                f.get("map_url", "").strip(),
                json.dumps(imgs),
                1 if f.get("featured") else 0,
                agent_name,
                username,
                sold_at,
                f.get("area", "").strip(),
                f.get("badge", "").strip(),
                safe_int(f.get("offices", 0)),
                safe_int(f.get("conference_rooms", 0)),
                safe_int(f.get("bathrooms", 0)),
                safe_int(f.get("kitchens", 0)),
                safe_int(f.get("parking_spaces", 0)),
                safe_int(f.get("sqft", 0)),
                safe_int(f.get("floor_number", 0))))
        
        conn.commit()
        conn.close()
        print(f"✅ Property '{title}' added successfully!")
        flash(f"✅ '{title}' added successfully!")
        return redirect(url_for("admin_dashboard") + "#properties")
    
    except Exception as e:
        import traceback
        print("=" * 50)
        print("ERROR IN ADD PROPERTY:")
        print(traceback.format_exc())
        print("=" * 50)
        flash(f"❌ Error adding property: {str(e)}", "error")
        return redirect(url_for("admin_dashboard") + "#properties")

@app.route("/admin/property/edit/<int:pid>", methods=["POST"])
@login_required
def admin_edit_property(pid):
    f = request.form
    conn = get_db()
    old = conn.execute("SELECT * FROM properties WHERE id=?", (pid,)).fetchone()
    if not old:
        conn.close()
        flash("❌ Property not found")
        return redirect(url_for("admin_dashboard"))
    
    if not user_can_edit_property(session["username"], session["role"], old["agent_id"]):
        flash("❌ You don't have permission to edit this property")
        conn.close()
        return redirect(url_for("admin_dashboard"))
    
    property_type = f.get("property_type", old["property_type"])
    listing_type = f.get("listing_type", old["listing_type"])
    old_imgs = json.loads(old["images"]) if isinstance(old["images"], str) else (old["images"] or [])
    
    imgs = []
    for i in range(1, MAX_PHOTOS + 1):
        file = request.files.get(f"img{i}_file")
        url = f.get(f"img{i}_url", "").strip()
        saved = save_image(file, f.get("title", "prop"), i)
        if saved:
            imgs.append(saved)
        elif url:
            imgs.append(url)
        elif len(old_imgs) >= i:
            imgs.append(old_imgs[i-1])
    
    status = f.get("status", "Available")
    sold_at = old["sold_at"] if status in ['Sold', 'Rented', 'Leased'] and old["sold_at"] else (datetime.now().isoformat() if status in ['Sold', 'Rented', 'Leased'] else None)
    
    base_fields = {
        "title": f.get("title", "").strip(), "price": safe_int(f.get("price", 0)),
        "listing_type": listing_type, "property_type": property_type, "status": status,
        "description": f.get("description", "").strip(), "map_url": f.get("map_url", "").strip(),
        "images": json.dumps(imgs), "featured": 1 if f.get("featured") else 0,
        "agent": old["agent"], "agent_id": old["agent_id"], "sold_at": sold_at,
        "area": f.get("area", "").strip(), "badge": f.get("badge", "").strip()
    }
    
    if property_type == "residential":
        base_fields.update({
            "bedrooms": safe_int(f.get("bedrooms", 0)), "bathrooms": safe_int(f.get("bathrooms", 0)),
            "living_rooms": safe_int(f.get("living_rooms", 0)), "kitchens": safe_int(f.get("kitchens", 0)),
            "garages": safe_int(f.get("garages", 0)), "sqft": safe_int(f.get("sqft", 0))
        })
        conn.execute("""UPDATE properties SET
            title=?, price=?, listing_type=?, property_type=?, status=?,
            description=?, map_url=?, images=?, featured=?, agent=?, agent_id=?, sold_at=?,
            area=?, badge=?, bedrooms=?, bathrooms=?, living_rooms=?, kitchens=?,
            garages=?, sqft=? WHERE id=?""", (
            base_fields["title"], base_fields["price"], base_fields["listing_type"],
            base_fields["property_type"], base_fields["status"], base_fields["description"],
            base_fields["map_url"], base_fields["images"], base_fields["featured"],
            base_fields["agent"], base_fields["agent_id"], base_fields["sold_at"],
            base_fields["area"], base_fields["badge"], base_fields["bedrooms"], 
            base_fields["bathrooms"], base_fields["living_rooms"], base_fields["kitchens"], 
            base_fields["garages"], base_fields["sqft"], pid))
    else:
        base_fields.update({
            "offices": safe_int(f.get("offices", 0)), "conference_rooms": safe_int(f.get("conference_rooms", 0)),
            "bathrooms": safe_int(f.get("bathrooms", 0)), "kitchens": safe_int(f.get("kitchens", 0)),
            "parking_spaces": safe_int(f.get("parking_spaces", 0)), "sqft": safe_int(f.get("sqft", 0)),
            "floor_number": safe_int(f.get("floor_number", 0))
        })
        conn.execute("""UPDATE properties SET
            title=?, price=?, listing_type=?, property_type=?, status=?,
            description=?, map_url=?, images=?, featured=?, agent=?, agent_id=?, sold_at=?,
            area=?, badge=?, offices=?, conference_rooms=?, bathrooms=?,
            kitchens=?, parking_spaces=?, sqft=?, floor_number=? WHERE id=?""", (
            base_fields["title"], base_fields["price"], base_fields["listing_type"],
            base_fields["property_type"], base_fields["status"], base_fields["description"],
            base_fields["map_url"], base_fields["images"], base_fields["featured"],
            base_fields["agent"], base_fields["agent_id"], base_fields["sold_at"],
            base_fields["area"], base_fields["badge"], base_fields["offices"], 
            base_fields["conference_rooms"], base_fields["bathrooms"], base_fields["kitchens"], 
            base_fields["parking_spaces"], base_fields["sqft"], base_fields["floor_number"], pid))
    
    conn.commit()
    conn.close()
    flash(f"✅ Property updated!")
    return redirect(url_for("admin_dashboard") + "#properties")

@app.route("/admin/property/delete/<int:pid>", methods=["POST"])
@login_required
def admin_delete_property(pid):
    conn = get_db()
    row = conn.execute("SELECT title, agent_id FROM properties WHERE id=?", (pid,)).fetchone()
    if not row:
        conn.close()
        flash("❌ Property not found")
        return redirect(url_for("admin_dashboard"))
    
    if not user_can_edit_property(session["username"], session["role"], row["agent_id"]):
        flash("❌ You don't have permission to delete this property")
        conn.close()
        return redirect(url_for("admin_dashboard"))
    
    conn.execute("DELETE FROM properties WHERE id=?", (pid,))
    conn.commit()
    conn.close()
    flash(f"✅ '{row['title']}' removed.")
    return redirect(url_for("admin_dashboard") + "#properties")

# ── Agents (Manager only) ──────────────────────────────────────
@app.route("/admin/agent/add", methods=["POST"])
@mgr_required
def admin_add_agent():
    f = request.form
    file = request.files.get("photo_file")
    photo = save_image(file, f.get("name", "agent"), 0) or f.get("photo_url", "").strip()
    conn = get_db()
    conn.execute("INSERT INTO agents(name,phone,email,bio,photo) VALUES(?,?,?,?,?)",
        (f.get("name", "").strip(), f.get("phone", "").strip(),
         f.get("email", "").strip(), f.get("bio", "").strip(), photo))
    conn.commit()
    conn.close()
    flash(f"✅ Agent '{f.get('name')}' added.")
    return redirect(url_for("admin_dashboard") + "#agents")

@app.route("/admin/agent/delete/<int:aid>", methods=["POST"])
@mgr_required
def admin_delete_agent(aid):
    conn = get_db()
    conn.execute("DELETE FROM agents WHERE id=?", (aid,))
    conn.commit()
    conn.close()
    flash("✅ Agent removed.")
    return redirect(url_for("admin_dashboard") + "#agents")

@app.route("/admin/agent/edit/<int:aid>", methods=["POST"])
@mgr_required
def admin_edit_agent(aid):
    f = request.form
    file = request.files.get("photo_file")
    photo = save_image(file, f.get("name", "agent"), 0) or f.get("photo_url", "").strip()
    
    conn = get_db()
    if not photo:
        current = conn.execute("SELECT photo FROM agents WHERE id=?", (aid,)).fetchone()
        if current and current["photo"]:
            photo = current["photo"]
    
    conn.execute("UPDATE agents SET name=?, phone=?, email=?, bio=?, photo=? WHERE id=?",
        (f.get("name", "").strip(), f.get("phone", "").strip(),
         f.get("email", "").strip(), f.get("bio", "").strip(), photo, aid))
    conn.commit()
    conn.close()
    flash(f"✅ Agent '{f.get('name')}' updated.")
    return redirect(url_for("admin_dashboard") + "#agents")

# ── Users (Manager only) ────────────────────────────────────────
@app.route("/admin/user/add", methods=["POST"])
@mgr_required
def admin_add_user():
    f = request.form
    conn = get_db()
    try:
        conn.execute("INSERT INTO users(username,password,role,full_name,email,phone) VALUES(?,?,?,?,?,?)",
            (f.get("username", "").strip(), hash_pw(f.get("password", "")), 
             f.get("role", "employee"), f.get("full_name", "").strip(),
             f.get("email", "").strip(), f.get("phone", "").strip()))
        if f.get("role") == "employee":
            conn.execute("INSERT OR IGNORE INTO agents(username,name,phone,email) VALUES(?,?,?,?)",
                (f.get("username", "").strip(), f.get("full_name", "").strip(),
                 f.get("phone", "").strip(), f.get("email", "").strip()))
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
    conn.execute("DELETE FROM users WHERE username=?", (username,))
    conn.execute("DELETE FROM agents WHERE username=?", (username,))
    conn.commit()
    conn.close()
    flash(f"✅ User '{username}' removed.")
    return redirect(url_for("admin_dashboard") + "#users")

# ── Change Password Routes - FIXED 404 ERRORS ─────────────────────

# Route 1: Manager changes ANY user's password (used by password modal)
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
    conn.execute("UPDATE users SET password=? WHERE username=?", (hash_pw(new_password), username))
    conn.commit()
    conn.close()
    
    flash(f"✅ Password updated for '{username}'!", "success")
    return redirect(url_for("admin_dashboard") + "#users")

# Route 2: User changes THEIR OWN password (used by My Password tab)
@app.route("/admin/user/change_my_password", methods=["POST"])
@login_required
def change_my_password():
    username = session["username"]
    current = request.form.get("current_password", "")
    new_password = request.form.get("new_password", "")
    confirm = request.form.get("confirm_password", "")
    
    # Validate CSRF
    if not validate_csrf():
        flash("❌ Invalid security token. Please try again.", "error")
        return redirect(url_for("admin_dashboard") + "#settings")
    
    # Check passwords match
    if new_password != confirm:
        flash("❌ New passwords do not match", "error")
        return redirect(url_for("admin_dashboard") + "#settings")
    
    # Check minimum length
    if len(new_password) < 8:
        flash("❌ Password must be at least 8 characters", "error")
        return redirect(url_for("admin_dashboard") + "#settings")
    
    conn = get_db()
    row = conn.execute("SELECT * FROM users WHERE username=?", (username,)).fetchone()
    
    if not row or row["password"] != hash_pw(current):
        flash("❌ Current password is incorrect", "error")
    else:
        conn.execute("UPDATE users SET password=? WHERE username=?", (hash_pw(new_password), username))
        conn.commit()
        flash(f"✅ Your password has been updated successfully!", "success")
    
    conn.close()
    return redirect(url_for("admin_dashboard") + "#settings")

# ── Serve uploaded files from /tmp/uploads ────────────────────────
@app.route('/uploads/<path:filename>')
def uploaded_file(filename):
    """Serve uploaded files from /tmp/uploads directory"""
    try:
        return send_from_directory('/tmp/uploads', filename)
    except Exception as e:
        print(f"Error serving file {filename}: {e}")
        return "File not found", 404

# ── API for property data ────────────────────────────────────────
@app.route("/admin/property/<int:pid>/json")
@login_required
def get_property_json(pid):
    conn = get_db()
    row = conn.execute("SELECT * FROM properties WHERE id=?", (pid,)).fetchone()
    conn.close()
    if not row:
        return jsonify({}), 404
    d = dict(row)
    d["images"] = json.loads(d["images"]) if isinstance(d.get("images"), str) else []
    return jsonify(d)

@app.route("/api/property/<int:pid>")
def get_public_property_json(pid):
    conn = get_db()
    row = conn.execute("SELECT * FROM properties WHERE id=?", (pid,)).fetchone()
    conn.close()
    if not row:
        return jsonify({"error": "Property not found"}), 404
    d = dict(row)
    d["images"] = json.loads(d["images"]) if isinstance(d.get("images"), str) else []
    return jsonify(d)

if __name__ == "__main__":
    # Verify upload directory exists
    if not os.path.exists('/tmp/uploads'):
        os.makedirs('/tmp/uploads', exist_ok=True)
        print("Created /tmp/uploads directory")
    
    # List existing files for debugging
    try:
        files = os.listdir('/tmp/uploads')
        print(f"Existing files in uploads: {files}")
    except:
        print("Could not list uploads directory")
    
    print(f"""
    ╔══════════════════════════════════════════════════════════╗
    ║     Better Properties - Real Estate Management System    ║
    ╠══════════════════════════════════════════════════════════╣
    ║  Website:    http://127.0.0.1:5000                       ║
    ║  Admin:      http://127.0.0.1:5000/admin                 ║
    ║  Login:      manager / admin123                          ║
    ╠══════════════════════════════════════════════════════════╣
    ║  Features Enabled:                                       ║
    ║  • Auto-delete after {SOLD_EXPIRY_DAYS} days                    ║
    ║  • Dynamic photo upload (up to {MAX_PHOTOS} photos)             ║
    ║  • Residential & Commercial property types              ║
    ║  • Role-based access (Manager/Agent)                    ║
    ║  • File upload validation (max 5MB)                     ║
    ║  • Social Media Links (Facebook & Instagram)            ║
    ║  • Public API for property details                      ║
    ║  • CSRF Protection Enabled                              ║
    ║  • Password Change Routes Fixed (No more 404!)          ║
    ║  • Upload directory: /tmp/uploads (Leapcell compatible) ║
    ║  • Images will be served correctly from /uploads/       ║
    ╚══════════════════════════════════════════════════════════╝
    """)
    app.run(debug=True, port=5000)