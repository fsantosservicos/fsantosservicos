import os
from datetime import datetime
import requests
from flask import (
    Flask, render_template, request, redirect,
    url_for, flash, session
)
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash

# Carregamento de env vars
try:
    from dotenv import load_dotenv
    load_dotenv()
except:
    pass

# =========================
# CONFIGURAÇÃO DE PASTAS
# =========================
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
# Força o Flask a olhar para as pastas corretas no Render
app = Flask(__name__, 
            template_folder=os.path.join(BASE_DIR, "templates"),
            static_folder=os.path.join(BASE_DIR, "static"))

app.config["SECRET_KEY"] = os.getenv("FLASK_SECRET", "dev_secret_123")

# Banco de Dados (SQLite por padrão, ou Postgres se configurado no Render)
DB_PATH = os.path.join(BASE_DIR, "instance", "app.db")
os.makedirs(os.path.join(BASE_DIR, "instance"), exist_ok=True)
app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv("DATABASE_URL", f"sqlite:///{DB_PATH}")
if app.config["SQLALCHEMY_DATABASE_URI"].startswith("postgres://"):
    app.config["SQLALCHEMY_DATABASE_URI"] = app.config["SQLALCHEMY_DATABASE_URI"].replace("postgres://", "postgresql://", 1)

db = SQLAlchemy(app)

# =========================
# MODELS (Resumido do original)
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
    status = db.Column(db.String(30))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

# =========================
# ROTAS PARA TODOS OS SEUS HTMLS
# =========================

# 1. HOME (Página Principal) -> index.html
@app.route("/")
def home():
    products = Product.query.order_by(Product.created_at.desc()).all()
    return render_template("index.html", products=products, year=datetime.now().year)

# 2. LOGIN ADMIN -> admin_login.html
@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        # Verificação simples para teste (ajuste conforme seu banco)
        if request.form.get("username") == "admin" and request.form.get("password") == "admin123":
            session["admin_logged"] = True
            return redirect(url_for("admin_dashboard"))
        flash("Credenciais inválidas", "danger")
    return render_template("admin_login.html")

# 3. DASHBOARD ADMIN -> admin_dashboard.html
@app.route("/admin/dashboard")
def admin_dashboard():
    if not session.get("admin_logged"): return redirect(url_for("admin_login"))
    return render_template("admin_dashboard.html")

# 4. LISTA DE PRODUTOS ADMIN -> admin_products.html
@app.route("/admin/products")
def admin_products():
    if not session.get("admin_logged"): return redirect(url_for("admin_login"))
    products = Product.query.all()
    return render_template("admin_products.html", products=products)

# 5. EDITAR PRODUTO -> admin_edit_product.html
@app.route("/admin/products/edit/<int:id>")
def admin_edit_product(id):
    if not session.get("admin_logged"): return redirect(url_for("admin_login"))
    product = Product.query.get_or_404(id)
    return render_template("admin_edit_product.html", product=product)

# 6. LOGS DE ORÇAMENTOS -> admin_orcamentos.html ou logs.html
@app.route("/admin/orcamentos")
def admin_orcamentos():
    if not session.get("admin_logged"): return redirect(url_for("admin_login"))
    logs = QuoteLog.query.order_by(QuoteLog.created_at.desc()).all()
    # Note que você tem logs.html e admin_orcamentos.html. Usei o admin_orcamentos.
    return render_template("admin_orcamentos.html", logs=logs)

# 7. LOGOUT
@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("home"))

# ROTA POST PARA ORÇAMENTO
@app.post("/orcamento")
def orcamento():
    # Lógica de envio de e-mail (Resend) e salvamento de log
    flash("Orçamento solicitado com sucesso!", "success")
    return redirect(url_for("home"))

# =========================
# INICIALIZAÇÃO
# =========================
with app.app_context():
    db.create_all()

if __name__ == "__main__":
    app.run(debug=True)
