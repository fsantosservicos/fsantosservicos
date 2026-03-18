import os
from datetime import datetime
import requests
from flask import (
    Flask, render_template, request, redirect,
    url_for, flash, session
)
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash

# Carregar variáveis de ambiente
try:
    from dotenv import load_dotenv
    load_dotenv()
except:
    pass

# =========================
# CONFIGURAÇÃO DE DIRETÓRIOS
# =========================
BASE_DIR = os.path.abspath(os.path.dirname(__file__))

app = Flask(__name__, 
            template_folder=os.path.join(BASE_DIR, "templates"),
            static_folder=os.path.join(BASE_DIR, "static"))

app.config["SECRET_KEY"] = os.getenv("FLASK_SECRET", "fsantos_secret_key_fixed")

# Banco de Dados (SQLite local ou Postgres no Render)
INSTANCE_DIR = os.path.join(BASE_DIR, "instance")
os.makedirs(INSTANCE_DIR, exist_ok=True)
DB_PATH = os.path.join(INSTANCE_DIR, "app.db")

DB_URL = os.getenv("DATABASE_URL", f"sqlite:///{DB_PATH}")
if DB_URL.startswith("postgres://"):
    DB_URL = DB_URL.replace("postgres://", "postgresql://", 1)
app.config["SQLALCHEMY_DATABASE_URI"] = DB_URL
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

# =========================
# MODELS BÁSICOS
# =========================
class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    sku = db.Column(db.String(80))
    name = db.Column(db.String(255))
    price_text = db.Column(db.String(80))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class QuoteLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(120))
    email = db.Column(db.String(160))
    status = db.Column(db.String(30), default="enviado")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

# ==========================================
# MAPEAMENTO DE TODOS OS HTMLS DA IMAGEM
# ==========================================

# 1. index.html e orcamento_modal.html (Home)
@app.route("/")
def home():
    products = Product.query.order_by(Product.created_at.desc()).all()
    # orcamento_modal.html deve estar incluído via {% include %} dentro do index.html
    return render_template("index.html", products=products, year=datetime.now().year)

# 2. admin_login.html
@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        user = os.getenv("ADMIN_USER", "admin")
        pw = os.getenv("ADMIN_PASS", "admin123")
        if request.form.get("username") == user and request.form.get("password") == pw:
            session["admin_logged"] = True
            return redirect(url_for("admin_dashboard"))
        flash("Acesso negado!", "danger")
    return render_template("admin_login.html")

# 3. admin_dashboard.html
@app.route("/admin/dashboard")
def admin_dashboard():
    if not session.get("admin_logged"): return redirect(url_for("admin_login"))
    return render_template("admin_dashboard.html")

# 4. admin_products.html
@app.route("/admin/products")
def admin_products():
    if not session.get("admin_logged"): return redirect(url_for("admin_login"))
    products = Product.query.all()
    return render_template("admin_products.html", products=products)

# 5. admin_edit_product.html
@app.route("/admin/product/edit/<int:id>")
def admin_edit_product(id):
    if not session.get("admin_logged"): return redirect(url_for("admin_login"))
    product = Product.query.get_or_404(id)
    return render_template("admin_edit_product.html", product=product)

# 6. admin_orcamentos.html
@app.route("/admin/orcamentos")
def admin_orcamentos():
    if not session.get("admin_logged"): return redirect(url_for("admin_login"))
    logs = QuoteLog.query.order_by(QuoteLog.created_at.desc()).all()
    return render_template("admin_orcamentos.html", logs=logs)

# 7. logs.html
@app.route("/admin/logs")
def view_system_logs():
    if not session.get("admin_logged"): return redirect(url_for("admin_login"))
    return render_template("logs.html")

# 8. dashboard.html (Geral/Cliente)
@app.route("/dashboard")
def user_dashboard():
    return render_template("dashboard.html")

# Redirecionamento de segurança para /admin
@app.route("/admin")
def admin_root():
    return redirect(url_for("admin_login"))

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("home"))

# =========================
# INICIALIZAÇÃO
# =========================
with app.app_context():
    db.create_all()

if __name__ == "__main__":
    app.run()
