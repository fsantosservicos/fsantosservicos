import os
import requests
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy

# Configurações de Pastas (Render)
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
app = Flask(__name__, 
            template_folder=os.path.join(BASE_DIR, "templates"),
            static_folder=os.path.join(BASE_DIR, "static"))

app.config["SECRET_KEY"] = os.getenv("FLASK_SECRET", "chave_mestra_99")

# Banco de Dados (Postgres no Render ou SQLite local)
DB_URL = os.getenv("DATABASE_URL", "sqlite:///" + os.path.join(BASE_DIR, "instance", "app.db"))
if DB_URL.startswith("postgres://"):
    DB_URL = DB_URL.replace("postgres://", "postgresql://", 1)
app.config["SQLALCHEMY_DATABASE_URI"] = DB_URL
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

# --- MODELS ---
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

# --- FUNÇÃO RESEND ---
def send_resend_email(subject, body, reply_to):
    api_key = os.getenv("RESEND_API_KEY")
    from_email = os.getenv("RESEND_FROM", "onboarding@resend.dev")
    to_email = os.getenv("RESEND_TO")

    if not api_key or not to_email:
        return False, "Configuração de API pendente no Render."

    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    payload = {
        "from": f"FSantos <{from_email}>",
        "to": [to_email],
        "subject": subject,
        "html": f"<div style='font-family:sans-serif'>{body}</div>",
        "reply_to": reply_to
    }
    try:
        r = requests.post("https://api.resend.com", headers=headers, json=payload, timeout=10)
        return r.status_code in [200, 201, 202, 204], r.text
    except Exception as e:
        return False, str(e)

# --- ROTAS (URLs EM PORTUGUÊS PARA BATER COM O NAVEGADOR) ---

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
    return render_template("admin_dashboard.html", year=datetime.now().year)

# ROTA DA SUA IMAGEM: /admin/produtos
@app.route("/admin/produtos")
def admin_products():
    if not session.get("admin_logged"): return redirect(url_for("admin_login"))
    products = Product.query.all()
    return render_template("admin_products.html", products=products, year=datetime.now().year)

# ROTA DE LOGS: /admin/orcamentos
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

@app.post("/orcamento")
def orcamento():
    nome, email = request.form.get("nome"), request.form.get("email")
    corpo = f"Solicitação de orçamento de {nome} ({email})"
    sucesso, erro = send_resend_email(f"Orçamento - {nome}", corpo, email)
    
    log = QuoteLog(nome=nome, email=email, status="sucesso" if sucesso else "erro")
    db.session.add(log)
    db.session.commit()
    
    flash("Enviado com sucesso!" if sucesso else f"Erro: {erro}", "success" if sucesso else "danger")
    return redirect(url_for("home"))

# Inicialização
with app.app_context():
    os.makedirs(os.path.join(BASE_DIR, "instance"), exist_ok=True)
    db.create_all()

if __name__ == "__main__":
    app.run()
