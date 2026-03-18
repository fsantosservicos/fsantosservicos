import os
from datetime import datetime
import requests
from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash
from werkzeug.utils import secure_filename

# Carregar variáveis de ambiente
try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

app = Flask(__name__)

# CONFIGURAÇÕES RENDER (DATABASE E SEGURANÇA)
# No Render, use uma 'Environment Variable' DATABASE_URL se usar Postgres. 
# Caso contrário, ele usará SQLite local (que reseta a cada deploy).
app.config["SECRET_KEY"] = os.getenv("FLASK_SECRET", "chave-secreta-padrao")
app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv("DATABASE_URL", "sqlite:///app.db")
if app.config["SQLALCHEMY_DATABASE_URI"].startswith("postgres://"):
    app.config["SQLALCHEMY_DATABASE_URI"] = app.config["SQLALCHEMY_DATABASE_URI"].replace("postgres://", "postgresql://", 1)

app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db = SQLAlchemy(app)

# MODELS
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
    image_path = db.Column(db.String(400))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class QuoteLog(db.Model):
    __tablename__ = "quote_logs"
    id = db.Column(db.Integer, primary_key=True)
    product_name = db.Column(db.String(255))
    nome = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(160), nullable=False)
    status = db.Column(db.String(30), default="enviado")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

# HELPERS
def send_email_quote(subject, body, reply_to):
    api_key = os.getenv("RESEND_API_KEY", "").strip()
    from_addr = os.getenv("RESEND_FROM", "onboarding@resend.dev").strip()
    to_addr = os.getenv("RESEND_TO", "").strip()
    
    if not api_key or not to_addr:
        return False, "Configuração de e-mail ausente."

    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    payload = {
        "from": f"Sistema <{from_addr}>",
        "to": [to_addr],
        "subject": subject,
        "html": f"<p>{body}</p>",
        "reply_to": reply_to
    }
    try:
        resp = requests.post("https://api.resend.com", headers=headers, json=payload, timeout=10)
        return resp.status_code in [200, 201, 202], resp.text
    except Exception as e:
        return False, str(e)

# ROUTES
@app.route("/")
def home():
    products = Product.query.order_by(Product.created_at.desc()).all()
    return render_template("index.html", products=products)

@app.post("/orcamento")
def orcamento():
    nome = request.form.get("nome")
    email = request.form.get("email")
    product_name = request.form.get("product_name", "Geral")
    
    body = f"Novo orçamento de {nome} ({email}) para o produto: {product_name}"
    sent, err = send_email_quote(f"Orçamento: {product_name}", body, email)

    log = QuoteLog(nome=nome, email=email, product_name=product_name, status="sucesso" if sent else "erro")
    db.session.add(log)
    db.session.commit()

    flash("Solicitação enviada!" if sent else f"Erro: {err}", "success" if sent else "danger")
    return redirect(url_for("home"))

# Inicialização do Banco
with app.app_context():
    db.create_all()

if __name__ == "__main__":
    app.run()
