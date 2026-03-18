
import os
from datetime import datetime
import requests
from flask import (
    Flask, render_template, request, redirect,
    url_for, flash, session
)
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash

# Carregar variáveis de ambiente (Local: .env | Render: Painel de Controle)
try:
    from dotenv import load_dotenv
    load_dotenv()
except:
    pass

# =========================
# CONFIGURAÇÃO DE AMBIENTE
# =========================
BASE_DIR = os.path.abspath(os.path.dirname(__file__))

app = Flask(__name__, 
            template_folder=os.path.join(BASE_DIR, "templates"),
            static_folder=os.path.join(BASE_DIR, "static"))

app.config["SECRET_KEY"] = os.getenv("FLASK_SECRET", "fsantos_secret_key_99")

# Configuração do Banco de Dados
INSTANCE_DIR = os.path.join(BASE_DIR, "instance")
os.makedirs(INSTANCE_DIR, exist_ok=True)
DB_PATH = os.path.join(INSTANCE_DIR, "app.db")

# No Render, prioriza DATABASE_URL (Postgres). Se não houver, usa SQLite.
DB_URL = os.getenv("DATABASE_URL", f"sqlite:///{DB_PATH}")
if DB_URL.startswith("postgres://"):
    DB_URL = DB_URL.replace("postgres://", "postgresql://", 1)
app.config["SQLALCHEMY_DATABASE_URI"] = DB_URL
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

# =========================
# MODELS
# =========================
class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    sku = db.Column(db.String(80), nullable=False)
    name = db.Column(db.String(255), nullable=False)
    price_text = db.Column(db.String(80), default="Sob consulta")
    short = db.Column(db.Text)
    description = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class QuoteLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(120))
    empresa = db.Column(db.String(160))
    email = db.Column(db.String(160))
    mensagem = db.Column(db.Text)
    status = db.Column(db.String(30), default="enviado")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

# =========================
# ROTAS PARA TODOS OS HTMLS
# =========================

# 1. Vitrine Principal (index.html)
@app.route("/")
def home():
    products = Product.query.order_by(Product.created_at.desc()).all()
    # orcamento_modal.html é incluído via {% include %} dentro do index.html
    return render_template("index.html", products=products, year=datetime.now().year)

# 2. Login Administrativo (admin_login.html)
@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        user = os.getenv("ADMIN_USER", "admin")
        pw = os.getenv("ADMIN_PASS", "admin123")
        if request.form.get("username") == user and request.form.get("password") == pw:
            session["admin_logged"] = True
            return redirect(url_for("admin_dashboard"))
        flash("Usuário ou senha incorretos.", "danger")
    return render_template("admin_login.html")

# 3. Painel de Controle Admin (admin_dashboard.html)
@app.route("/admin/dashboard")
def admin_dashboard():
    if not session.get("admin_logged"): return redirect(url_for("admin_login"))
    return render_template("admin_dashboard.html")

# 4. Gerenciamento de Produtos (admin_products.html)
@app.route("/admin/products")
def admin_products():
    if not session.get("admin_logged"): return redirect(url_for("admin_login"))
    products = Product.query.all()
    return render_template("admin_products.html", products=products)

# 5. Edição de Produto Específico (admin_edit_product.html)
@app.route("/admin/product/edit/<int:id>")
def admin_edit_product(id):
    if not session.get("admin_logged"): return redirect(url_for("admin_login"))
    product = Product.query.get_or_404(id)
    return render_template("admin_edit_product.html", product=product)

# 6. Visualização de Orçamentos (admin_orcamentos.html)
@app.route("/admin/orcamentos")
def admin_orcamentos():
    if not session.get("admin_logged"): return redirect(url_for("admin_login"))
    logs = QuoteLog.query.order_by(QuoteLog.created_at.desc()).all()
    return render_template("admin_orcamentos.html", logs=logs)

# 7. Logs do Sistema (logs.html)
@app.route("/admin/system-logs")
def system_logs():
    if not session.get("admin_logged"): return redirect(url_for("admin_login"))
    logs = QuoteLog.query.all() # Ou log de erros se você preferir
    return render_template("logs.html", logs=logs)

# 8. Dashboard Genérico (dashboard.html - se houver outro nível de acesso)
@app.route("/dashboard")
def general_dashboard():
    return render_template("dashboard.html")

# 9. Logout
@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("home"))

# =========================
# LÓGICA DE ORÇAMENTO (POST)
# =========================
@app.post("/orcamento")
def orcamento():
    nome = request.form.get("nome")
    email = request.form.get("email")
    # Lógica do Resend aqui...
    log = QuoteLog(nome=nome, email=email, status="enviado")
    db.session.add(log)
    db.session.commit()
    flash("Sua solicitação foi enviada!", "success")
    return redirect(url_for("home"))

# =========================
# INICIALIZAÇÃO
# =========================
with app.app_context():
    db.create_all()

if __name__ == "__main__":
    app.run()
