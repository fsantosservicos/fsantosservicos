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

# Tenta carregar .env apenas localmente
try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

# =========================
# CONFIGURAÇÕES DE CAMINHOS
# =========================
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
# Garantindo que o Flask encontre as pastas templates e static
app = Flask(__name__, 
            template_folder=os.path.join(BASE_DIR, "templates"),
            static_folder=os.path.join(BASE_DIR, "static"))

app.config["SECRET_KEY"] = os.getenv("FLASK_SECRET", "dev_secret_change_me")

# Banco de Dados: Prioriza DATABASE_URL (Postgres) do Render, senão usa SQLite
DB_URL = os.getenv("DATABASE_URL", "sqlite:///" + os.path.join(BASE_DIR, "instance", "app.db"))
if DB_URL.startswith("postgres://"):
    DB_URL = DB_URL.replace("postgres://", "postgresql://", 1)
app.config["SQLALCHEMY_DATABASE_URI"] = DB_URL
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

# Pastas de Upload (Cria se não existirem)
UPLOADS_DIR = os.path.join(app.static_folder, "uploads")
COVERS_DIR = os.path.join(UPLOADS_DIR, "covers")
PDFS_DIR = os.path.join(UPLOADS_DIR, "pdfs")
os.makedirs(COVERS_DIR, exist_ok=True)
os.makedirs(PDFS_DIR, exist_ok=True)

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
    empresa = db.Column(db.String(160))
    email = db.Column(db.String(160), nullable=False)
    telefone = db.Column(db.String(60))
    mensagem = db.Column(db.Text)
    status = db.Column(db.String(30), default="enviado")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

# =========================
# HELPERS
# =========================
def send_email_quote(subject, body, reply_to=None):
    api_key = os.getenv("RESEND_API_KEY", "").strip()
    from_addr = os.getenv("RESEND_FROM", "onboarding@resend.dev").strip()
    to_addr = os.getenv("RESEND_TO", "").strip()
    
    if not api_key or not to_addr:
        return False, "Configuração de e-mail pendente no Render."

    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    payload = {
        "from": f"FSantos <{from_addr}>",
        "to": [to_addr],
        "subject": subject,
        "html": f"<pre style='font-family:sans-serif'>{body}</pre>",
    }
    if reply_to: payload["reply_to"] = reply_to

    try:
        resp = requests.post("https://api.resend.com", headers=headers, json=payload, timeout=12)
        return (200 <= resp.status_code < 300), resp.text
    except Exception as e:
        return False, str(e)

# =========================
# ROTAS PÚBLICAS
# =========================
@app.route("/")
def home():
    q = request.args.get("q", "").strip()
    query = Product.query
    if q:
        like = f"%{q}%"
        query = query.filter(db.or_(Product.name.ilike(like), Product.sku.ilike(like)))
    products = query.order_by(Product.created_at.desc()).all()
    return render_template("index.html", products=products, q=q, year=datetime.now().year)

@app.post("/orcamento")
def orcamento():
    data = request.form
    nome, email = data.get("nome"), data.get("email")
    
    if not nome or not email:
        flash("Nome e E-mail são obrigatórios.", "danger")
        return redirect(url_for("home"))

    body = f"Cliente: {nome}\nEmpresa: {data.get('empresa')}\nE-mail: {email}\nTelefone: {data.get('telefone')}\nMsg: {data.get('mensagem')}"
    sent, err = send_email_quote(f"Novo Orçamento - {nome}", body, reply_to=email)

    log = QuoteLog(nome=nome, email=email, empresa=data.get("empresa"), mensagem=data.get("mensagem"), status="sucesso" if sent else "erro")
    db.session.add(log)
    db.session.commit()

    flash("Pedido enviado com sucesso!" if sent else f"Erro ao enviar: {err}", "success" if sent else "danger")
    return redirect(url_for("home"))

# =========================
# ROTAS ADMIN (CHAMADAS HTML)
# =========================
@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        user = AdminUser.query.filter_by(username=request.form.get("username")).first()
        if user and check_password_hash(user.password_hash, request.form.get("password")):
            session["admin_logged"] = True
            return redirect(url_for("admin_dashboard"))
        flash("Usuário ou senha inválidos.", "danger")
    return render_template("admin_login.html")

@app.route("/admin/dashboard")
def admin_dashboard():
    if not session.get("admin_logged"): return redirect(url_for("admin_login"))
    return render_template("admin_dashboard.html")

@app.route("/admin/products")
def admin_products():
    if not session.get("admin_logged"): return redirect(url_for("admin_login"))
    products = Product.query.all()
    return render_template("admin_products.html", products=products)

@app.route("/admin/orcamentos")
def admin_orcamentos():
    if not session.get("admin_logged"): return redirect(url_for("admin_login"))
    logs = QuoteLog.query.order_by(QuoteLog.created_at.desc()).all()
    return render_template("admin_orcamentos.html", logs=logs)

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("home"))

# =========================
# INICIALIZAÇÃO
# =========================
with app.app_context():
    db.create_all()
    # Criar admin padrão se não existir
    if not AdminUser.query.filter_by(username="admin").first():
        hashed_pw = generate_password_hash(os.getenv("ADMIN_PASS", "admin123"))
        db.session.add(AdminUser(username="admin", password_hash=hashed_pw))
        db.session.commit()

if __name__ == "__main__":
    app.run()
