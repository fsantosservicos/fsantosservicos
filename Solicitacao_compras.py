import os
from datetime import datetime
import requests
from flask import (
    Flask, render_template, request, redirect,
    url_for, flash, session
)
from flask_sqlalchemy import SQLAlchemy

# Tenta carregar variáveis de ambiente
try:
    from dotenv import load_dotenv
    load_dotenv()
except:
    pass

BASE_DIR = os.path.abspath(os.path.dirname(__file__))

app = Flask(__name__, 
            template_folder=os.path.join(BASE_DIR, "templates"),
            static_folder=os.path.join(BASE_DIR, "static"))

# ATENÇÃO: Isso ajuda a ver o erro real no navegador em vez de "Internal Server Error"
app.config["PROPAGATE_EXCEPTIONS"] = True
app.config["SECRET_KEY"] = os.getenv("FLASK_SECRET", "chave_mestra_123")

# Banco de Dados
DB_PATH = os.path.join(BASE_DIR, "instance", "app.db")
os.makedirs(os.path.join(BASE_DIR, "instance"), exist_ok=True)
app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv("DATABASE_URL", f"sqlite:///{DB_PATH}")
if app.config["SQLALCHEMY_DATABASE_URI"].startswith("postgres://"):
    app.config["SQLALCHEMY_DATABASE_URI"] = app.config["SQLALCHEMY_DATABASE_URI"].replace("postgres://", "postgresql://", 1)

db = SQLAlchemy(app)

# --- MODELS ---
class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    sku = db.Column(db.String(80))
    name = db.Column(db.String(255))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class QuoteLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(120))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

# --- ROTAS CORRIGIDAS ---

@app.route("/")
def home():
    products = Product.query.all()
    # Enviamos 'year' porque muitos templates base usam isso no rodapé
    return render_template("index.html", products=products, year=datetime.now().year)

@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        if request.form.get("username") == "admin" and request.form.get("password") == "admin123":
            session["admin_logged"] = True
            return redirect(url_for("admin_dashboard"))
        flash("Erro no login", "danger")
    return render_template("admin_login.html", year=datetime.now().year)

@app.route("/admin/dashboard")
def admin_dashboard():
    if not session.get("admin_logged"): return redirect(url_for("admin_login"))
    # Passamos variáveis comuns para evitar erro de 'undefined' no HTML
    return render_template("admin_dashboard.html", year=datetime.now().year)

@app.route("/admin/products")
def admin_products():
    if not session.get("admin_logged"): return redirect(url_for("admin_login"))
    products = Product.query.all()
    return render_template("admin_products.html", products=products, year=datetime.now().year)

@app.route("/admin/orcamentos")
def admin_orcamentos():
    if not session.get("admin_logged"): return redirect(url_for("admin_login"))
    logs = QuoteLog.query.all()
    return render_template("admin_orcamentos.html", logs=logs, year=datetime.now().year)

@app.route("/admin/logs")
def view_logs():
    if not session.get("admin_logged"): return redirect(url_for("admin_login"))
    return render_template("logs.html", year=datetime.now().year)

# Inicialização
with app.app_context():
    db.create_all()

if __name__ == "__main__":
    app.run()
