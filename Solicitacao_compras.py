import os
from datetime import datetime
import requests
from flask import (
    Flask, render_template, request, redirect,
    url_for, flash, session
)
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

# Carregar variáveis de ambiente localmente
try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

app = Flask(__name__)

# =========================
# CONFIGURAÇÕES RENDER
# =========================
app.config["SECRET_KEY"] = os.getenv("FLASK_SECRET", "dev_secret_123")
# No Render, prefira usar PostgreSQL. Se usar SQLite, os dados resetam no deploy.
app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv("DATABASE_URL", "sqlite:///app.db")
if app.config["SQLALCHEMY_DATABASE_URI"].startswith("postgres://"):
    app.config["SQLALCHEMY_DATABASE_URI"] = app.config["SQLALCHEMY_DATABASE_URI"].replace("postgres://", "postgresql://", 1)

app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

# =========================
# MODELS
# =========================
class AdminUser(db.Model):
    __tablename__ = "admin_users"
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)

class Product(db.Model):
    __tablename__ = "products"
    id = db.Column(db.Integer, primary_key=True)
    sku = db.Column(db.String(80), nullable=False)
    name = db.Column(db.String(255), nullable=False)
    price_text = db.Column(db.String(80), default="Sob consulta")
    short = db.Column(db.Text)
    description = db.Column(db.Text)
    image_path = db.Column(db.String(400))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class QuoteLog(db.Model):
    __tablename__ = "quote_logs"
    id = db.Column(db.Integer, primary_key=True)
    product_name = db.Column(db.String(255))
    nome = db.Column(db.String(120), nullable=False)
    empresa = db.Column(db.String(160))
    email = db.Column(db.String(160), nullable=False)
    telefone = db.Column(db.String(60))
    mensagem = db.Column(db.Text)
    status = db.Column(db.String(30), default="enviado")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

# =========================
# HELPERS
# =========================
def send_email_quote(subject, body, reply_to):
    api_key = os.getenv("RESEND_API_KEY", "").strip()
    from_addr = os.getenv("RESEND_FROM", "onboarding@resend.dev").strip()
    to_addr = os.getenv("RESEND_TO", "").strip()
    
    if not api_key or not to_addr:
        return False, "Configuração de API Resend ausente."

    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    payload = {
        "from": f"FSantos <{from_addr}>",
        "to": [to_addr],
        "subject": subject,
        "html": f"<div style='font-family:sans-serif;'>{body.replace(chr(10), '<br>')}</div>",
        "reply_to": reply_to
    }
    try:
        resp = requests.post("https://api.resend.com", headers=headers, json=payload, timeout=12)
        return (200 <= resp.status_code < 300), resp.text
    except Exception as e:
        return False, str(e)

def create_admin_if_missing():
    user = os.getenv("ADMIN_USER", "admin").strip()
    pw = os.getenv("ADMIN_PASS", "admin123").strip()
    if not AdminUser.query.filter_by(username=user).first():
        au = AdminUser(username=user, password_hash=generate_password_hash(pw))
        db.session.add(au)
        db.session.commit()

# =========================
# ROTAS VITRINE
# =========================
@app.route("/")
def home():
    q = request.args.get("q", "").strip()
    query = Product.query
    if q:
        query = query.filter(Product.name.ilike(f"%{q}%") | Product.sku.ilike(f"%{q}%"))
    products = query.order_by(Product.created_at.desc()).all()
    return render_template("index.html", products=products, q=q, year=datetime.now().year)

@app.post("/orcamento")
def orcamento():
    nome = request.form.get("nome")
    email = request.form.get("email")
    empresa = request.form.get("empresa")
    telefone = request.form.get("telefone")
    mensagem = request.form.get("mensagem")
    product_id = request.form.get("product_id")
    
    product = Product.query.get(product_id) if product_id else None
    prod_name = product.name if product else "Solicitação Geral"
    
    body = f"Nova solicitação:\nNome: {nome}\nEmpresa: {empresa}\nE-mail: {email}\nTelefone: {telefone}\nProduto: {prod_name}\n\nMensagem: {mensagem}"
    
    sent, err = send_email_quote(f"Orçamento - {prod_name}", body, email)

    log = QuoteLog(nome=nome, email=email, empresa=empresa, telefone=telefone, 
                   mensagem=mensagem, product_name=prod_name, status="enviado" if sent else "erro")
    db.session.add(log)
    db.session.commit()

    if sent:
        flash("Orçamento enviado com sucesso!", "success")
    else:
        flash(f"Erro ao enviar: {err}", "danger")
    return redirect(url_for("home"))

# =========================
# ROTAS ADMIN
# =========================
@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        user = AdminUser.query.filter_by(username=request.form.get("username")).first()
        if user and check_password_hash(user.password_hash, request.form.get("password")):
            session["admin_logged"] = True
            return redirect(url_for("admin_dashboard"))
        flash("Credenciais inválidas", "danger")
    return render_template("login.html")

@app.route("/admin")
def admin_dashboard():
    if not session.get("admin_logged"):
        return redirect(url_for("admin_login"))
    logs = QuoteLog.query.order_by(QuoteLog.created_at.desc()).all()
    products = Product.query.all()
    return render_template("admin.html", logs=logs, products=products)

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("home"))

# =========================
# INICIALIZAÇÃO
# =========================
with app.app_context():
    db.create_all()
    create_admin_if_missing()

if __name__ == "__main__":
    app.run()
