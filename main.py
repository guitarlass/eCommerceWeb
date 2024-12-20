import flask_login
from flask import Flask, render_template, redirect, url_for, request, flash, session, jsonify
from flask_bootstrap import Bootstrap5
import os
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import Integer, String, Float, text, Text, DateTime, ForeignKey, Boolean
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from flask_login import UserMixin, login_user, LoginManager, current_user, logout_user, login_required
from forms import LoginForm, RegisterForm
from werkzeug.security import generate_password_hash, check_password_hash
import datetime
import stripe

app = Flask(__name__)
app.config['SECRET_KEY'] = "merlinsbeard-com" # os.getenv('STRIPE_SECRET_KEY')
Bootstrap5(app)

stripe.api_key = os.getenv('STRIPE_SECRET_KEY')  #

app.config['STRIPE_PUBLIC_KEY'] = os.getenv('STRIPE_PUBLIC_KEY')

login_manager = LoginManager()
login_manager.init_app(app)

login_manager.login_view = 'login'


@login_manager.user_loader
def user_login(user_id):
    return db.session.get(User, user_id)
    # return db.get_or_404(User, user_id)


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
    description: Mapped[Text] = mapped_column(Text)  # Text is correct
    image_url: Mapped[str] = mapped_column(String(500))
    featured: Mapped[bool] = mapped_column(Boolean, default=False, nullable=True)
    category_id: Mapped[int] = mapped_column(Integer, ForeignKey('product_category.id'), nullable=False)

    # defined later may not be used in the system
    category = db.relationship('ProductCategory', back_populates="products")

    def __repr__(self):
        return f'<Product {self.name}>'


class ProductCategory(db.Model):
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(400), nullable=False)
    image_url: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[Text] = mapped_column(Text)

    # defined later may not be used in the system
    products = db.relationship("Product", back_populates="category")


class User(db.Model, UserMixin):
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(250), unique=True, nullable=False)
    password: Mapped[str] = mapped_column(String(300), nullable=False)
    name: Mapped[str] = mapped_column(String(350), nullable=False)

    # defined later may not be used in the system
    orders = db.relationship('Order', back_populates='user')


class Order(db.Model):
    __tablename__ = "user_order"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey('user.id'), nullable=False)
    total_price: Mapped[float] = mapped_column(Float, nullable=False)
    order_date: Mapped[datetime] = mapped_column(DateTime)
    status: Mapped[str] = mapped_column(String(50), default="pending")

    # defined later may not be used in the system
    order_items = db.relationship('OrderItem', back_populates='order')
    user = db.relationship('User', back_populates='orders')


class OrderItem(db.Model):
    __tablename__ = "user_order_item"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    product_id: Mapped[int] = mapped_column(Integer, ForeignKey('product.id'), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    price: Mapped[float] = mapped_column(Float, nullable=False)
    order_id: Mapped[int] = mapped_column(Integer, ForeignKey('user_order.id'), nullable=False)

    order = db.relationship('Order', back_populates='order_items')
    product = db.relationship('Product')


with app.app_context():
    db.create_all()


# @app.template_filter()
# def length(value):
#     return len(value)

@app.route('/')
def home():
    featured = db.session.execute(db.select(Product).where(Product.featured == 1)).scalar_one_or_none()
    recents = db.session.query(Product).limit(4).all()
    categories = db.session.query(ProductCategory).all()
    return render_template('index.html', featured=featured, recents=recents, categories=categories)


@app.route('/product/<int:id>')
def product(id):
    product = db.session.query(Product).filter_by(id=id).first_or_404()
    return render_template('product.html', product=product)


@app.route('/cart')
def cart():
    cart_items = session.get('cart', {})
    products = []

    for product_id, quantity in cart_items.items():
        product = db.session.query(Product).filter_by(id=product_id).first()
        if product:  # Ensure the product exists
            products.append({"product": product, "quantity": quantity})

    tot_amount = 0.0
    for item in products:
        # Ensure price is treated as float to prevent TypeError
        price = float(item['product'].price) if item['product'] else 0.0
        quantity = item['quantity']
        tot_amount += round(price * quantity, 2)


    # print(tot_amount)  # For debugging
    return render_template('cart.html', products=products, tot_amount=tot_amount)  # Pass total amount to template


@app.route('/add_to_cart/<int:product_id>', methods=['POST'])
def add_to_cart(product_id):
    quantity = request.form.get('quantity', type=int) or 1

    if 'cart' not in session:
        session['cart'] = {}

    if str(product_id) in session['cart']:
        session['cart'][str(product_id)] += int(quantity)
    else:
        session['cart'][str(product_id)] = int(quantity)

    # mark the session as modified to ensure it gets saved
    session.modified = True
    flash(f"Added {quantity} of this product to the cart.")
    return redirect(url_for('product', id=product_id))


@app.route('/remove_from_cart/<int:product_id>')
def remove_from_cart(product_id):
    if 'cart' in session:
        if str(product_id) in session['cart']:
            del session['cart'][str(product_id)]  # remove item from the session
            session.modified = True
            flash(f"Removed the item from the cart")
        else:
            flash(f"Item not added to cart.")
    else:
        flash(f"Cart is empty.")

    return redirect(url_for('cart'))


# @flask_login.login_required # <- THIS DOESNT WORK
@app.route('/checkout', methods=['GET', 'POST'])
@flask_login.login_required
def checkout():
    amount = 0.0
    client_secret = None
    if request.method == 'POST':
        if request.form.get('process') == 'no':
            try:
                # # Get product details (could also be passed from the frontend)
                amount = float(request.form.get('amount'))  # $50.00 in cents
                amount_in_cents = int(amount * 100)
                # Create a PaymentIntent on the server
                intent = stripe.PaymentIntent.create(
                    amount=amount_in_cents,
                    currency='usd',
                    payment_method_types=['card'],
                    receipt_email=current_user.email,
                )

                client_secret = intent['client_secret']

            except Exception as e:
                return jsonify(error=str(e)), 403

    return render_template('checkout.html', public_key=app.config['STRIPE_PUBLIC_KEY'], amount=amount,
                           client_secret=client_secret)


@app.route('/place_order', methods=['POST'])
@flask_login.login_required
def place_order():
    new_order_id = None
    total_amount = float(request.form.get("amount", 0.0))
    status = request.form.get("status", "pending")

    try:
        order_date = datetime.datetime.now().replace(second=0, microsecond=0)

        new_order = Order(total_price=total_amount, user_id=current_user.id, order_date=order_date,
                          status=status)
        db.session.add(new_order)
        db.session.commit()

        new_order_id = new_order.id
        cart_items = session.get('cart', {})

        cart_items = session.get('cart', {})

        for product_id, quantity in cart_items.items():
            product_price = db.session.scalar(db.select(Product.price).where(Product.id==product_id))

            if product_price is None:
                raise ValueError(f"Product with id {product_id} not found or price is empty.")

            if quantity <= 0:
                raise ValueError(f"Quantity for product {product_id} must be positive.")

            new_order_item = OrderItem(
                product_id=product_id,
                price=product_price,
                quantity=quantity,
                order_id=new_order_id
            )
            db.session.add(new_order_item)

        db.session.commit()
        flash("successfully placed the order")

        session.pop('cart', None)  # Removes the 'cart' key from the session

        flash("Your cart has been emptied.")

        return jsonify(order_id=new_order_id)

    except Exception as e:
        db.session.rollback()  # Rollback the session in case of error
        print(f"Error: {str(e)}")
        flash("An error occurred while placing your order. Please try again.")
        return jsonify(error=str(e)), 403


@app.route('/order_confirmation/<int:order_id>')
def order_confirmation(order_id):
    order = db.session.query(Order).filter_by(id=order_id).first()
    payment_method = "Card"
    # send any emails
    return render_template('order.html', order=order,
                           payment_method=payment_method)


@app.route('/category/<int:id>')
def category(id):
    products = db.session.query(Product).filter_by(category_id=id).all()
    category = db.session.query(ProductCategory.name).filter_by(id=id).first()
    category_name = db.session.scalar(db.select(ProductCategory.name).where(ProductCategory.id == id))
    # category_name = category[0] if category else None
    return render_template('category.html', products=products, category_name=category_name)


@app.route('/shop')
def shop():
    products = db.session.query(Product).all()
    return render_template('shop.html', products=products)


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

    if register_form.validate_on_submit():
        existing_user = db.session.scalar(db.select(User).where(User.email == register_form.email.data))
        if existing_user:
            flash("User already registered! Please login.")
            return redirect(url_for("login"))

        new_user = User(
            name=register_form.name.data,
            email=register_form.email.data,
            password=generate_password_hash(register_form.password.data,
                                            method="pbkdf2:sha256", salt_length=8)
        )

        db.session.add(new_user)
        db.session.commit()
        login_user(new_user)

        return redirect(url_for("home"))  # Redirect to the home or dashboard instead of login

    return render_template("register.html", form=register_form)


@app.route('/contact')
def contact():
    pass

if __name__ == '__main__':
    app.run(debug=True)
