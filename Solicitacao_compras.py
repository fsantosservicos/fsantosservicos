import os
import requests
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash

# =========================
# CONFIGURAÇÃO DE AMBIENTE
# =========================
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
TEMPLATE_DIR = os.path.join(BASE_DIR, "templates")
STATIC_DIR = os.path.join(BASE_DIR, "static")

app = Flask(__name__, template_folder=TEMPLATE_DIR, static_folder=STATIC_DIR)
app.config["SECRET_KEY"] = os.getenv("FLASK_SECRET", "dev_secret_fsantos_2026")

# Banco de Dados
INSTANCE_DIR = os.path.join(BASE_DIR, "instance")
os.makedirs(INSTANCE_DIR, exist_ok=True)
DB_URL = os.getenv("DATABASE_URL", "sqlite:///" + os.path.join(INSTANCE_DIR, "app.db"))
if DB_URL.startswith("postgres://"):
    DB_URL = DB_URL.replace("postgres://", "postgresql://", 1)
app.config["SQLALCHEMY_DATABASE_URI"] = DB_URL
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

# =========================
# MODELS
# =========================
class Product(db.Model):
    __tablename__ = "products"
    id = db.Column(db.Integer, primary_key=True)
    sku = db.Column(db.String(80), nullable=False)
    name = db.Column(db.String(255), nullable=False)
    price_text = db.Column(db.String(80), default="Sob consulta")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class QuoteLog(db.Model):
    __tablename__ = "quote_logs"
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(160), nullable=False)
    status = db.Column(db.String(30), default="enviado")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

# =========================
# FUNÇÃO RESEND (E-MAIL)
# =========================
def send_resend_email(subject, body, reply_to):
    api_key = os.getenv("RESEND_API_KEY", "").strip()
    from_email = os.getenv("RESEND_FROM", "onboarding@resend.dev").strip()
    to_email = os.getenv("RESEND_TO", "").strip()

    if not api_key or not to_email:
        return False, "Configuração de API Resend pendente."

    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    payload = {
        "from": f"FSantos <{from_email}>",
        "to": [to_email],
        "subject": subject,
        "html": f"<div>{body}</div>",
        "reply_to": reply_to
    }
    try:
        r = requests.post("https://api.resend.com", headers=headers, json=payload, timeout=12)
        return (200 <= r.status_code < 300), r.text
    except Exception as e:
        return False, str(e)

# ==========================================
# ROTAS CORRIGIDAS (PORTUGUÊS)
# ==========================================

@app.route("/")
def home():
    products = Product.query.order_by(Product.created_at.desc()).all()
    return render_template("index.html", products=products, year=datetime.now().year)

@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        u = os.getenv("ADMIN_USER", "admin")
        p = os.getenv("ADMIN_PASS", "admin123")
        if request.form.get("username") == u and request.form.get("password") == p:
            session["admin_logged"] = True
            return redirect(url_for("admin_dashboard"))
        flash("Usuário ou senha incorretos", "danger")
    return render_template("admin_login.html", year=datetime.now().year)

@app.route("/admin/dashboard")
def admin_dashboard():
    if not session.get("admin_logged"): return redirect(url_for("admin_login"))
    p_count = Product.query.count()
    q_count = QuoteLog.query.count()
    return render_template("admin_dashboard.html", product_count=p_count, quote_count=q_count, year=datetime.now().year)

# ROTA CORRIGIDA PARA /ADMIN/PRODUTOS
@app.route("/admin/produtos")
def admin_products():
    if not session.get("admin_logged"): return redirect(url_for("admin_login"))
    products = Product.query.all()
    return render_template("admin_products.html", products=products, year=datetime.now().year)

@app.route("/admin/orcamentos")
def admin_orcamentos():
    if not session.get("admin_logged"): return redirect(url_for("admin_login"))
    logs = QuoteLog.query.order_by(QuoteLog.created_at.desc()).all()
    return render_template("admin_orcamentos.html", logs=logs, year=datetime.now().year)

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("home"))

@app.post("/orcamento")
def orcamento():
    nome = request.form.get("nome")
    email = request.form.get("email")
    sucesso, erro = send_resend_email(f"Orçamento - {nome}", f"Pedido de {nome}", email)
    log = QuoteLog(nome=nome, email=email, status="sucesso" if sucesso else "erro")
    db.session.add(log)
    db.session.commit()
    flash("Enviado!" if sucesso else f"Erro: {erro}", "success" if sucesso else "danger")
    return redirect(url_for("home"))

# =========================
# INICIALIZAÇÃO
# =========================
with app.app_context():
    db.create_all()

if __name__ == "__main__":
    app.run()

