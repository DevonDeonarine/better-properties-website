"""
Better Properties — Complete Working Version
=============================================
Admin Login: manager / admin123
"""

from flask import Flask, render_template, request, jsonify, redirect, url_for, session, flash
from datetime import datetime, timedelta
import os, json, hashlib, secrets, threading, time

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
#  IN-MEMORY STORAGE (No database needed)
# ================================================================
properties = []
property_id_counter = 1

# Users
users = {
    "manager": hash_pw("admin123"),
    "employee1": hash_pw("emp123")
}

# Agents
agents = [
    {"id": 1, "username": "employee1", "name": "John Smith", "phone": "18687654321", "email": "john@betterproperties.com", "bio": "", "photo": ""}
]

# Viewing requests
viewing_requests = []

def hash_pw(p):
    salt = "better_properties_salt_2026"
    return hashlib.sha256((p + salt).encode()).hexdigest()

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
    return agents

def get_areas():
    areas = set()
    for p in properties:
        if p.get("area"):
            areas.add(p["area"])
    return sorted(list(areas))

# ================================================================
#  CONFIG FOR TEMPLATES
# ================================================================
def get_config():
    return {
        "name": BUSINESS_NAME,
        "sub": BUSINESS_SUB,
        "location": BUSINESS_LOCATION,
        "email": BUSINESS_EMAIL,
        "phone": BUSINESS_PHONE,
        "whatsapp": WHATSAPP_NUMBER,
        "expiry_days": SOLD_EXPIRY_DAYS,
        "facebook": FACEBOOK_URL,
        "instagram": INSTAGRAM_URL
    }

# ================================================================
#  PUBLIC ROUTES
# ================================================================
@app.route("/")
def index():
    try:
        return render_template("index.html", 
            props=properties, 
            config=get_config(),
            fmt_price=fmt_price)
    except Exception as e:
        return f"<h1>Template Error</h1><p>Missing 'index.html' template. Error: {str(e)}</p><p>Admin login at <a href='/admin/login'>/admin/login</a> (manager/admin123)</p>"

@app.route("/property/<int:property_id>")
def view_property(property_id):
    try:
        property_data = None
        for p in properties:
            if p.get("id") == property_id:
                property_data = p
                break
        
        if not property_data:
            return "Property not found", 404
        
        return render_template("property_detail.html", 
            property=property_data, 
            config=get_config(),
            fmt_price=fmt_price)
    except Exception as e:
        return f"<h1>Template Error</h1><p>Missing 'property_detail.html' template. Error: {str(e)}</p><a href='/'>Go Home</a>"

@app.route("/api/property/<int:pid>")
def get_public_property_json(pid):
    for p in properties:
        if p.get("id") == pid:
            return jsonify(p)
    return jsonify({"error": "Property not found"}), 404

@app.route("/track/view/<path:title>")
def track_view(title):
    return "", 204

@app.route("/track/inquiry/<path:title>")
def track_inquiry(title):
    return "", 204

@app.route("/viewing", methods=["POST"])
def submit_viewing():
    data = request.get_json()
    viewing_requests.append({
        "id": len(viewing_requests) + 1,
        "property": data.get("property"),
        "name": data.get("name"),
        "email": data.get("email"),
        "phone": data.get("phone"),
        "requested_dt": data.get("datetime"),
        "submitted_at": datetime.now().isoformat()
    })
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
        
        if u in users and users[u] == hash_pw(p):
            session["username"] = u
            session["role"] = "manager" if u == "manager" else "employee"
            session["full_name"] = u
            flash(f"✅ Welcome back, {u}!")
            return redirect(url_for("admin_dashboard"))
        flash("❌ Invalid credentials", "error")
    
    try:
        return render_template("admin_login.html", config={"name": BUSINESS_NAME})
    except Exception as e:
        return f'''
        <h1>Admin Login</h1>
        <form method="POST">
            <input type="hidden" name="_csrf" value="{get_csrf_token()}">
            <input type="text" name="username" placeholder="Username" required><br>
            <input type="password" name="password" placeholder="Password" required><br>
            <button type="submit">Login</button>
        </form>
        <p>Use: manager / admin123</p>
        <p><small>Template 'admin_login.html' not found. Using fallback.</small></p>
        '''

@app.route("/admin/logout")
def admin_logout():
    session.clear()
    flash("✅ Logged out successfully")
    return redirect(url_for("admin_login"))

@app.route("/admin")
@login_required
def admin_dashboard():
    username = session["username"]
    role = session["role"]
    
    if role == "manager":
        props = properties
    else:
        props = [p for p in properties if p.get("agent_id") == username]
    
    days = []
    for i in range(7):
        date = (datetime.now() - timedelta(days=6-i)).strftime("%Y-%m-%d")
        days.append({"date": date, "views": 0, "inquiries": 0})
    
    try:
        return render_template("admin.html",
            props=props,
            agents=agents,
            users=[{"username": u, "role": "manager" if u == "manager" else "employee", "full_name": u} for u in users.keys()],
            requests=viewing_requests,
            analytics_days=days,
            total_props=len(props),
            total_requests=len(viewing_requests),
            areas=get_areas(),
            agent_names=[a["name"] for a in agents],
            config=get_config(),
            fmt_price=fmt_price,
            session=session,
            max_photos=MAX_PHOTOS,
            role=role)
    except Exception as e:
        return f"<h1>Admin Dashboard</h1><p>You are logged in as {username} (Role: {role})</p><p>Total properties: {len(props)}</p><p><a href='/admin/logout'>Logout</a></p><p><small>Template 'admin.html' not found. Using fallback.</small></p>"

# ── Properties ──────────────────────────────────────────────────
@app.route("/admin/property/add", methods=["POST"])
@login_required
def admin_add_property():
    global property_id_counter
    try:
        f = request.form
        property_type = f.get("property_type", "residential")
        listing_type = f.get("listing_type", "sale")
        username = session["username"]
        
        imgs = []
        for i in range(1, MAX_PHOTOS + 1):
            url = f.get(f"img{i}_url", "").strip()
            if url:
                imgs.append(url)
        
        sold_at = datetime.now().isoformat() if f.get("status") in ['Sold', 'Rented', 'Leased'] else None
        
        title = f.get("title", "").strip()
        if not title:
            flash("❌ Title is required", "error")
            return redirect(url_for("admin_dashboard") + "#properties")
        
        agent_name = username
        for a in agents:
            if a.get("username") == username:
                agent_name = a.get("name", username)
                break
        
        new_property = {
            "id": property_id_counter,
            "title": title,
            "price": safe_int(f.get("price", 0)),
            "listing_type": listing_type,
            "property_type": property_type,
            "status": f.get("status", "Available"),
            "description": f.get("description", "").strip(),
            "map_url": f.get("map_url", "").strip(),
            "images": imgs,
            "featured": 1 if f.get("featured") else 0,
            "agent": agent_name,
            "agent_id": username,
            "sold_at": sold_at,
            "area": f.get("area", "").strip(),
            "badge": f.get("badge", "").strip(),
            "bedrooms": safe_int(f.get("bedrooms", 0)),
            "bathrooms": safe_int(f.get("bathrooms", 0)),
            "living_rooms": safe_int(f.get("living_rooms", 0)),
            "kitchens": safe_int(f.get("kitchens", 0)),
            "garages": safe_int(f.get("garages", 0)),
            "sqft": safe_int(f.get("sqft", 0)),
            "offices": safe_int(f.get("offices", 0)),
            "conference_rooms": safe_int(f.get("conference_rooms", 0)),
            "parking_spaces": safe_int(f.get("parking_spaces", 0)),
            "floor_number": safe_int(f.get("floor_number", 0)),
            "created_at": datetime.now().isoformat(),
            "views": 0,
            "inquiries": 0
        }
        
        properties.append(new_property)
        property_id_counter += 1
        
        flash(f"✅ '{title}' added successfully!")
        return redirect(url_for("admin_dashboard") + "#properties")
    
    except Exception as e:
        flash(f"❌ Error adding property: {str(e)}", "error")
        return redirect(url_for("admin_dashboard") + "#properties")

@app.route("/admin/property/edit/<int:pid>", methods=["POST"])
@login_required
def admin_edit_property(pid):
    try:
        old_property = None
        old_index = None
        for i, p in enumerate(properties):
            if p.get("id") == pid:
                old_property = p
                old_index = i
                break
        
        if not old_property:
            flash("❌ Property not found", "error")
            return redirect(url_for("admin_dashboard") + "#properties")
        
        f = request.form
        property_type = f.get("property_type", old_property.get("property_type", "residential"))
        listing_type = f.get("listing_type", old_property.get("listing_type", "sale"))
        
        old_imgs = old_property.get("images", [])
        imgs = []
        for i in range(1, MAX_PHOTOS + 1):
            url = f.get(f"img{i}_url", "").strip()
            if url:
                imgs.append(url)
            elif len(old_imgs) >= i:
                imgs.append(old_imgs[i-1])
        
        status = f.get("status", "Available")
        sold_at = old_property.get("sold_at") if status in ['Sold', 'Rented', 'Leased'] and old_property.get("sold_at") else (datetime.now().isoformat() if status in ['Sold', 'Rented', 'Leased'] else None)
        
        updated_property = {
            "id": pid,
            "title": f.get("title", "").strip(),
            "price": safe_int(f.get("price", 0)),
            "listing_type": listing_type,
            "property_type": property_type,
            "status": status,
            "description": f.get("description", "").strip(),
            "map_url": f.get("map_url", "").strip(),
            "images": imgs,
            "featured": 1 if f.get("featured") else 0,
            "agent": old_property.get("agent", ""),
            "agent_id": old_property.get("agent_id", ""),
            "sold_at": sold_at,
            "area": f.get("area", "").strip(),
            "badge": f.get("badge", "").strip(),
            "bedrooms": safe_int(f.get("bedrooms", 0)),
            "bathrooms": safe_int(f.get("bathrooms", 0)),
            "living_rooms": safe_int(f.get("living_rooms", 0)),
            "kitchens": safe_int(f.get("kitchens", 0)),
            "garages": safe_int(f.get("garages", 0)),
            "sqft": safe_int(f.get("sqft", 0)),
            "offices": safe_int(f.get("offices", 0)),
            "conference_rooms": safe_int(f.get("conference_rooms", 0)),
            "parking_spaces": safe_int(f.get("parking_spaces", 0)),
            "floor_number": safe_int(f.get("floor_number", 0)),
            "created_at": old_property.get("created_at", datetime.now().isoformat()),
            "views": old_property.get("views", 0),
            "inquiries": old_property.get("inquiries", 0)
        }
        
        properties[old_index] = updated_property
        flash(f"✅ Property updated!")
        return redirect(url_for("admin_dashboard") + "#properties")
    
    except Exception as e:
        flash(f"❌ Error updating property: {str(e)}", "error")
        return redirect(url_for("admin_dashboard") + "#properties")

@app.route("/admin/property/delete/<int:pid>", methods=["POST"])
@login_required
def admin_delete_property(pid):
    global properties
    properties = [p for p in properties if p.get("id") != pid]
    flash(f"✅ Property removed.")
    return redirect(url_for("admin_dashboard") + "#properties")

@app.route("/admin/property/<int:pid>/json")
@login_required
def get_property_json(pid):
    for p in properties:
        if p.get("id") == pid:
            return jsonify(p)
    return jsonify({}), 404

# ── Agents ──────────────────────────────────────────────────────
@app.route("/admin/agent/add", methods=["POST"])
@mgr_required
def admin_add_agent():
    f = request.form
    new_id = len(agents) + 1
    agents.append({
        "id": new_id,
        "username": f.get("username", f"agent_{new_id}"),
        "name": f.get("name", "").strip(),
        "phone": f.get("phone", "").strip(),
        "email": f.get("email", "").strip(),
        "bio": f.get("bio", "").strip(),
        "photo": ""
    })
    flash(f"✅ Agent '{f.get('name')}' added.")
    return redirect(url_for("admin_dashboard") + "#agents")

@app.route("/admin/agent/delete/<int:aid>", methods=["POST"])
@mgr_required
def admin_delete_agent(aid):
    global agents
    agents = [a for a in agents if a.get("id") != aid]
    flash("✅ Agent removed.")
    return redirect(url_for("admin_dashboard") + "#agents")

@app.route("/admin/agent/edit/<int:aid>", methods=["POST"])
@mgr_required
def admin_edit_agent(aid):
    f = request.form
    for i, a in enumerate(agents):
        if a.get("id") == aid:
            agents[i]["name"] = f.get("name", "").strip()
            agents[i]["phone"] = f.get("phone", "").strip()
            agents[i]["email"] = f.get("email", "").strip()
            agents[i]["bio"] = f.get("bio", "").strip()
            break
    flash(f"✅ Agent '{f.get('name')}' updated.")
    return redirect(url_for("admin_dashboard") + "#agents")

# ── Users ────────────────────────────────────────────────────────
@app.route("/admin/user/add", methods=["POST"])
@mgr_required
def admin_add_user():
    f = request.form
    username = f.get("username", "").strip()
    password = f.get("password", "")
    
    if not username or not password:
        flash("❌ Username and password required", "error")
        return redirect(url_for("admin_dashboard") + "#users")
    
    if username in users:
        flash("❌ Username already exists", "error")
        return redirect(url_for("admin_dashboard") + "#users")
    
    users[username] = hash_pw(password)
    flash(f"✅ User '{username}' created.")
    return redirect(url_for("admin_dashboard") + "#users")

@app.route("/admin/user/delete/<username>", methods=["POST"])
@mgr_required
def admin_delete_user(username):
    if username == "manager":
        flash("❌ Cannot delete main manager.")
        return redirect(url_for("admin_dashboard") + "#users")
    
    if username in users:
        del users[username]
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
    
    if username in users:
        users[username] = hash_pw(new_password)
        flash(f"✅ Password updated for '{username}'!", "success")
    else:
        flash(f"❌ User '{username}' not found", "error")
    
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
    
    if username in users and users[username] == hash_pw(current):
        users[username] = hash_pw(new_password)
        flash(f"✅ Your password has been updated!", "success")
    else:
        flash("❌ Current password is incorrect", "error")
    
    return redirect(url_for("admin_dashboard") + "#settings")

# ================================================================
#  AUTO-CLEANUP THREAD
# ================================================================
def auto_cleanup():
    global properties
    while True:
        try:
            now = datetime.now()
            cutoff = now - timedelta(days=SOLD_EXPIRY_DAYS)
            expired = []
            
            for p in properties:
                if p.get("status") in ['Sold', 'Rented', 'Leased'] and p.get("sold_at"):
                    try:
                        sold_at = datetime.fromisoformat(p["sold_at"])
                        if sold_at < cutoff:
                            expired.append(p)
                    except:
                        pass
            
            if expired:
                properties = [p for p in properties if p not in expired]
                print(f"[Auto-cleanup] Deleted {len(expired)} expired listings")
        
        except Exception as e:
            print(f"[Auto-cleanup] Error: {e}")
        time.sleep(AUTO_CLEANUP_HOURS * 3600)

cleanup_thread = threading.Thread(target=auto_cleanup, daemon=True)
cleanup_thread.start()

# ================================================================
#  STARTUP
# ================================================================
if __name__ == "__main__":
    print(f"""
    ╔══════════════════════════════════════════════════════════╗
    ║     Better Properties - Real Estate Management System    ║
    ╠══════════════════════════════════════════════════════════╣
    ║  Website:    http://127.0.0.1:5000                       ║
    ║  Admin:      http://127.0.0.1:5000/admin/login           ║
    ║  Login:      manager / admin123                          ║
    ╠══════════════════════════════════════════════════════════╣
    ║  Storage:    In-Memory (for testing)                     ║
    ║  Status:     RUNNING                                      ║
    ╚══════════════════════════════════════════════════════════╝
    """)
    app.run(debug=True, port=5000)