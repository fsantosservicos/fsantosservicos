import os
import smtplib
from email.message import EmailMessage
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

# =========================
# APP + PATHS (Ajustado para Render)
# =========================
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
app = Flask(__name__, 
            template_folder=os.path.join(BASE_DIR, "templates"),
            static_folder=os.path.join(BASE_DIR, "static"))

app.config["SECRET_KEY"] = os.getenv("FLASK_SECRET", "dev_secret_change_me")

# Correção para o Render (Postgres usa postgres:// mas o SQLAlchemy exige postgresql://)
DB_URI = os.getenv("DATABASE_URL", "sqlite:///" + os.path.join(BASE_DIR, "instance", "app.db"))
if DB_URI.startswith("postgres://"):
    DB_URI = DB_URI.replace("postgres://", "postgresql://", 1)
app.config["SQLALCHEMY_DATABASE_URI"] = DB_URI
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

# =========================
# MODELS (Estrutura Original)
# =========================
class AdminUser(db.Model):
    __tablename__ = "admin_users"
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Product(db.Model):
    __tablename__ = "products"
    id = db.Column(db.Integer, primary_key=True)
    sku = db.Column(db.String(80), nullable=False, index=True)
    name = db.Column(db.String(255), nullable=False, index=True)
    price_text = db.Column(db.String(80), default="Sob consulta")
    short = db.Column(db.Text)
    description = db.Column(db.Text)
    image_path = db.Column(db.String(400))
    file_path = db.Column(db.String(400))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class QuoteLog(db.Model):
    __tablename__ = "quote_logs"
    id = db.Column(db.Integer, primary_key=True)
    product_name = db.Column(db.String(255))
    nome = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(160), nullable=False)
    status = db.Column(db.String(30), default="enviado")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

# =========================
# HELPERS (E-mail SMTP Original)
# =========================
def send_email_quote(subject, body, reply_to=None):
    host = os.getenv("SMTP_HOST", "").strip()
    port = int(os.getenv("SMTP_PORT", "587"))
    user = os.getenv("SMTP_USER", "").strip()
    pw = os.getenv("SMTP_PASS", "").strip()
    from_addr = os.getenv("SMTP_FROM", "").strip()
    to_addr = os.getenv("SMTP_TO", "").strip()

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = f"FSantos Serviços <{from_addr}>"
    msg["To"] = to_addr
    if reply_to: msg["Reply-To"] = reply_to
    msg.set_content(body)

    try:
        with smtplib.SMTP(host, port, timeout=20) as s:
            s.starttls()
            s.login(user, pw)
            s.send_message(msg)
        return True, None
    except Exception as e:
        return False, str(e)

# =========================
# ROUTES (Restaurando Chamadas dos HTMLs)
# =========================

@app.route("/")
def home():
    q = request.args.get("q", "").strip()
    query = Product.query
    if q:
        query = query.filter(Product.name.ilike(f"%{q}%"))
    products = query.order_by(Product.created_at.desc()).all()
    return render_template("index.html", products=products, q=q, year=datetime.now().year)

@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        user = AdminUser.query.filter_by(username=request.form.get("username")).first()
        if user and check_password_hash(user.password_hash, request.form.get("password")):
            session["admin_logged"] = True
            return redirect(url_for("admin_dashboard"))
        flash("Credenciais inválidas", "danger")
    return render_template("admin_login.html", year=datetime.now().year)

@app.route("/admin/dashboard")
def admin_dashboard():
    if not session.get("admin_logged"): return redirect(url_for("admin_login"))
    return render_template("admin_dashboard.html", year=datetime.now().year)

@app.route("/admin/products")
def admin_products():
    if not session.get("admin_logged"): return redirect(url_for("admin_login"))
    products = Product.query.all()
    return render_template("admin_products.html", products=products, year=datetime.now().year)

@app.route("/admin/orcamentos")
def admin_orcamentos():
    if not session.get("admin_logged"): return redirect(url_for("admin_login"))
    logs = QuoteLog.query.order_by(QuoteLog.created_at.desc()).all()
    return render_template("admin_orcamentos.html", logs=logs, year=datetime.now().year)

@app.route("/admin/logs")
def view_logs():
    if not session.get("admin_logged"): return redirect(url_for("admin_login"))
    return render_template("logs.html", year=datetime.now().year)

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("home"))

# =========================
# INIT
# =========================
with app.app_context():
    os.makedirs(os.path.join(BASE_DIR, "instance"), exist_ok=True)
    db.create_all()
    # Cria admin se não existir
    if not AdminUser.query.filter_by(username="admin").first():
        hashed = generate_password_hash(os.getenv("ADMIN_PASS", "admin123"))
        db.session.add(AdminUser(username="admin", password_hash=hashed))
        db.session.commit()

if __name__ == "__main__":
    app.run()
