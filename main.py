from flask import Flask, render_template, redirect, url_for, request, flash, session
from flask_bootstrap import Bootstrap5
import os
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import Integer, String, Float, text, Text, DateTime, ForeignKey, Boolean
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from flask_login import UserMixin, login_user, LoginManager, current_user, logout_user, login_required
from forms import LoginForm, RegisterForm
from werkzeug.security import generate_password_hash, check_password_hash
import datetime

app = Flask(__name__)
app.config['SECRET_KEY'] = "merlinsbeard-com"
Bootstrap5(app)

login_manager = LoginManager()
login_manager.init_app(app)

@login_manager.user_loader
def user_login(user_id):
    return db.get_or_404(User, user_id)


class Base(DeclarativeBase):
    pass


db = SQLAlchemy(model_class=Base)

# app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:////ecom.db"
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///ecom.db'
# app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///my_database.db'  # Relative path

db.init_app(app)


class Product(db.Model):
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(400), nullable=False)
    price: Mapped[float] = mapped_column(Float, nullable=False)
    description: Mapped[text] = mapped_column(Text)
    image_url: Mapped[str] = mapped_column(String(500))
    featured: Mapped[bool] = mapped_column(Boolean, default=False, nullable=True)
    category_id: Mapped[int] = mapped_column(Integer, ForeignKey('product_category.id'), nullable=False)


    def __repr__(self):
        return f'<Product {self.name}>'

class ProductCategory(db.Model):
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(400), nullable=False)
    description: Mapped[Text] = mapped_column(Text)

class User(db.Model, UserMixin):
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(250), unique=True, nullable=False)
    password: Mapped[str] = mapped_column(String(300), nullable=False)
    name: Mapped[str] = mapped_column(String(350), nullable=False)


class Order(db.Model):
    __tablename__ = "user_order"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey('user.id'), nullable=False)
    total_price: Mapped[float] = mapped_column(Float, nullable=False)
    order_date: Mapped[datetime] = mapped_column(DateTime)
    status: Mapped[str] = mapped_column(String(50), default="pending")


with app.app_context():
    db.create_all()


@app.template_filter()
def length(value):
    return len(value)

@app.route('/')
def home():
    featured = db.session.execute(db.select(Product).where(Product.featured == 1)).scalar_one_or_none()
    return render_template('index.html', featured=featured)

@app.route('/product/<int:id>')
def product(id):
    product = db.session.query(Product).filter_by(id=id).first_or_404()
    return render_template('product.html', product=product)

@app.route('/cart')
def cart():
    pass

@app.route('/add_to_cart/<int:product_id>', methods=['POST'])
def add_to_cart(product_id):
    quantity = request.form.get('quantity', type=int, default=1)

    if 'cart' not in session:
        session['cart'] = {}

    if product_id in session['cart']:
        session['cart'][product_id] += quantity  # increment quantity
    else:
        session['cart'][product_id] = quantity  # add new

    session.modified = True  # mark session as modified to save changes
    return redirect(url_for('home'))


@app.route('/login', methods=['GET', 'POST'])
def login():
    login_form = LoginForm()
    if login_form.validate_on_submit():
        user = db.session.execute(db.select(User).where(User.email == login_form.email.data)).scalar()
        if not user:
            flash("User not found!")
        else:
            if check_password_hash(user.password, login_form.password.data):
                login_user(user)
                return redirect(url_for("home"))
            else:
                flash("Password incorrect!")
    return render_template('login.html', form=login_form)


@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for("home"))


@app.route('/register', methods=['GET', 'POST'])
def register():
    register_form = RegisterForm()
    user_exists = db.session.execute((db.select(User).where(User.email == register_form.email.data)))
    if user_exists:
        flash("User already registered! Please login.")
    if register_form.validate_on_submit():
        new_user = User(name=register_form.name.data,
                        email=register_form.email.data,
                        password=generate_password_hash(register_form.password.data,
                                                        method="pbkdf2:sha256",
                                                        salt_length=8))
        db.session.add(new_user)
        db.session.commit()
        login_user(new_user)
        return redirect(url_for("login"))
    return render_template("register.html", form=register_form)


if __name__ == '__main__':
    app.run(debug=True)