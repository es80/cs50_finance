""" Implements the Flask web app for CS50 Finance. """

from decimal import Decimal
import re
import os
import os.path
from datetime import datetime
from tempfile import mkdtemp
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import exc
from werkzeug.exceptions import default_exceptions
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd, f_time, f_date

# Configure application
app = Flask(__name__)


# Ensure responses aren't cached
@app.after_request
def after_request(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


# Custom filters
app.jinja_env.filters["usd"] = usd
app.jinja_env.filters["f_time"] = f_time
app.jinja_env.filters["f_date"] = f_date

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_FILE_DIR"] = mkdtemp()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure SQLite database using flask_sqlalchemy.SQLAlchemy
db_filename = "finance.db"
db_path = os.path.join(os.getcwd(), db_filename)
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///" + db_path
app.config["SQLALCHEMY_ECHO"] = True
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = True
db = SQLAlchemy(app)


class User(db.Model):
    """The users table in our database."""

    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True, nullable=False)
    username = db.Column(db.Text, nullable=False, unique=True)
    hash = db.Column(db.Text, nullable=False)
    cash = db.Column(db.Text, nullable=False, default="10000")

    transactions = db.relationship("Transaction", back_populates="user",
                                   cascade="all, delete-orphan")
    portfolio = db.relationship("Portfolio", back_populates="user",
                                cascade="all, delete-orphan")

    def __repr__(self):
        return (f"<User(id={self.id}, username={self.username}, "
                f"hash={self.hash}, cash={self.cash})>")


class Portfolio(db.Model):
    """The portfolios table in our database"""

    __tablename__ = "portfolios"
    id = db.Column(db.Integer, primary_key=True, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    stock_id = db.Column(db.Integer, db.ForeignKey('stocks.id'),
                         nullable=False)
    quantity = db.Column(db.Integer, nullable=False)

    user = db.relationship("User", back_populates="portfolio")
    stock = db.relationship("Stock", back_populates="portfolios")

    def __repr__(self):
        return (f"<Portfolio(id={self.id}, user_id={self.user_id}, "
                f"stock_id={self.stock_id}, quantity={self.quantity})>")


class Stock(db.Model):
    """The stocks table in our database."""

    __tablename__ = "stocks"
    id = db.Column(db.Integer, primary_key=True, nullable=False)
    symbol = db.Column(db.Text, unique=True)
    name = db.Column(db.Text, unique=True)

    transactions = db.relationship("Transaction", back_populates="stock")
    portfolios = db.relationship("Portfolio", back_populates="stock")

    def __repr__(self):
        return f"<Stock(id={self.id}, symbol={self.symbol})>"


class TransactionType(db.Model):
    """The table for the three types of transactions in our database"""

    __tablename__ = "transaction_types"
    id = db.Column(db.Integer, primary_key=True, nullable=False)
    name = db.Column(db.Text, unique=True)

    transactions = db.relationship("Transaction", back_populates="ttype")

    def __repr__(self):
        return f"<TransactionType(id={self.id}, name={self.name}>"


class Transaction(db.Model):
    """The Transactions table in our database."""

    __tablename__ = "transactions"
    id = db.Column(db.Integer, primary_key=True, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    stock_id = db.Column(db.Integer, db.ForeignKey('stocks.id'),
                         nullable=False)
    type_id = db.Column(db.Integer, db.ForeignKey('transaction_types.id'),
                        nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    price = db.Column(db.Text, nullable=False)
    datetime = db.Column(db.DateTime, nullable=False)

    user = db.relationship("User", back_populates="transactions")
    stock = db.relationship("Stock", back_populates="transactions")
    ttype = db.relationship("TransactionType", back_populates="transactions")

    def __repr__(self):
        return (f"<Transaction(id={self.id}, user_id={self.user_id}, "
                f"stock_id={self.stock_id}, "
                f"type_id={self.type_id}, "
                f"quantity={self.quantity}, price={self.price}, "
                f"datetime={self.datetime})>")


# Create database tables if not already existing.
db.create_all()

"""
# For testing and initialization
db.drop_all()
db.create_all()
# Create some example rows.
a = User(username="a", hash=generate_password_hash("a"))
b = User(username="b", hash=generate_password_hash("b"))
c = User(username="c", hash=generate_password_hash("c"))
d = User(username="d", hash=generate_password_hash("d"))
db.session.add_all([a,b,c,d])
"""

# Add, if not already existing, the three transaction types the database allows
if not TransactionType.query.filter_by(name="BUY").first():
    db.session.add(TransactionType(name="BUY"))

if not TransactionType.query.filter_by(name="SELL").first():
    db.session.add(TransactionType(name="SELL"))

if not TransactionType.query.filter_by(name="CASH").first():
    db.session.add(TransactionType(name="CASH"))

# Commit changes
try:
    db.session.commit()
except exc.SQLAlchemyError:
    db.session.rollback()



@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""

    # Query for user
    user = User.query.filter_by(id=session["user_id"]).first()

    # Form a table listing each entry in user's portfolio and include the
    # current market price and total value
    table = []

    for item in user.portfolio:

        # Lookup the current price
        quoted = lookup(item.stock.symbol)

        if quoted:
            price = quoted["price"]

        else:
            # If lookup failed use price from most recent transaction for any
            # user
            price = db.session.query(Transaction.price).\
                    filter(Transaction.stock.symbol == item.stock.symbol).\
                    order_by(Transaction.datetime.desc()).first()

        # Calculate subtotal for row
        subtotal = Decimal(price) * Decimal(item.quantity)

        # Add data to table
        table.append({"symbol": item.stock.symbol, "name": item.stock.name,
                      "quantity": item.quantity, "price": price,
                      "subtotal": subtotal})

    # Include current cash and total assets for template
    cash = Decimal(user.cash)
    total = cash + sum(row["subtotal"] for row in table)

    return render_template("index.html", table=table, cash=cash, total=total)


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""

    # User reached route via GET (as by clicking a link or via redirect)
    if request.method == "GET":
        return render_template("buy.html")

    # User reached route via POST (as by submitting a form via POST)
    symbol = request.form.get("symbol")
    shares = request.form.get("shares")
    error = None

    # Check a symbol was submitted
    if not symbol:
        error = "yeah, if you could provide a symbol"

    # Check shares is a positive integer
    elif not re.fullmatch(r"[1-9]+[0-9]*", shares):
        error = ("yeah, if you could provide a positive whole number of "
                 "shares")

    else:
        # Lookup a quote for symbol
        quoted = lookup(symbol)

        # Failed lookup
        if quoted is None:
            error = f"yeah, if we could find a quote for {symbol}"

    # Handle all errors thus far
    if error:
        flash("403 Forbidden")
        return apology(error, 403)

    # Compute cost of purchase as decimal
    price = str(quoted["price"])
    quantity = int(shares)
    cost = Decimal(quantity) * Decimal(price)

    # Check user can afford purchase
    user = User.query.filter_by(id=session["user_id"]).first()

    if Decimal(user.cash) < cost:
        flash("403 Forbidden")
        return apology("yeah, if you could try to not go overdrawn", 403)

    # Find the stock in the stocks table
    stock = Stock.query.filter_by(symbol=symbol.upper()).first()

    # Or else add the stock to the stocks table
    if not stock:
        stock = Stock(symbol=symbol.upper(), name=quoted["name"])
        try:
            db.session.add(stock)
            db.session.commit()
        except exc.SQLAlchemyError:
            db.session.rollback()
            flash("500 Internal Server Error")
            return apology("yeah, if the server could work properly", 500)

    # Create the row for the transactions table
    buy_type = TransactionType.query.filter_by(name="BUY").first()
    db.session.add(Transaction(user_id=user.id, stock_id=stock.id,
                               type_id=buy_type.id, quantity=quantity,
                               price=price, datetime=datetime.now()))

    # Look for any row for this user and symbol in portfolios table
    portfolio_row = Portfolio.query.filter_by(user_id=user.id,
                                              stock_id=stock.id).first()

    # If the entry does not exist, create it
    if not portfolio_row:
        db.session.add(Portfolio(user_id=user.id, stock_id=stock.id,
                                 quantity=quantity))
    # Otherwise update the existing entry
    else:
        portfolio_row.quantity += quantity

    # Finally update the users cash, subtract from existing cash and convert
    # back to string for storage
    user.cash = str(Decimal(user.cash) - cost)

    # Try to commit changes
    try:
        db.session.commit()
    except exc.SQLAlchemyError:
        db.session.rollback()
        flash("500 Internal Server Error")
        return apology("yeah, if the server could work properly", 500)

    # Redirect user to home page
    flash("Purchase complete")
    return redirect("/")


@app.route("/history")
@login_required
def history():
    """Show history of transactions"""

    # Query for user
    user = User.query.filter_by(id=session["user_id"]).first()

    # Form a table listing each entry in user's transaction history and include
    # the subtotals for each transaction
    table = []

    print(type(user.transactions))

    for item in user.transactions:

        # Replacing any missing symbols or names by empty strings
        symbol = item.stock.symbol
        name = item.stock.name
        if not symbol:
            symbol = ""
        if not name:
            name = ""

        # Compute subtotals to include with transaction history
        quantity = item.quantity
        price = item.price
        subtotal = Decimal(quantity) * Decimal(price)

        # Make some adjustments for the cash transaction rows
        if not quantity:
            quantity = ""
            subtotal = price
            price = ""

        # Add data to table
        table.append({"symbol": symbol, "name": name,
                      "type": item.ttype.name, "quantity": quantity,
                      "price": price, "subtotal": subtotal,
                      "datetime": item.datetime})

    # Render history of user's transactions, most recent first
    return render_template("history.html", table=reversed(table))


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via GET (as by clicking a link or via redirect)
    if request.method == "GET":
        return render_template("login.html")

    # User reached route via POST (as by submitting a form via POST)
    username = request.form.get("username")
    password = request.form.get("password")
    error = None

    # Ensure username was submitted
    if not username:
        error = "yeah, if you could provide a username"

    # Ensure password was submitted
    elif not password:
        error = "yeah, if you could provide a password"

    else:
        # Query database for username
        row = User.query.filter_by(username=username).first()

        # Ensure username exists and password is correct
        if not (row and check_password_hash(row.hash, password)):
            error = "yeah, if you could provide a valid username and password"

    if error:
        flash("403 Forbidden")
        return apology(error, 403)

    # Remember which user has logged in
    session["user_id"] = row.id

    # Redirect user to home page
    flash('You were successfully logged in')
    return redirect("/")


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    flash('You were successfully logged out')
    return render_template("exited.html")


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    """Get stock quote."""

    # User reached route via GET (as by clicking a link or via redirect)
    if request.method == "GET":
        return render_template("quote.html")

    # User reached route via POST (as by submitting a form via POST)
    symbol = request.form.get("symbol")
    error = None

    # Check a symbol was submitted
    if not symbol:
        error = "yeah, if you could provide a symbol"

    else:
        # Lookup a quote for symbol
        quoted = lookup(symbol)

        # Check we got a quote back
        if quoted is None:
            error = f"yeah, if we could find a quote for {symbol}"

    if error:
        flash("403 Forbidden")
        return apology(error, 403)

    return render_template("quoted.html", quote=quoted)


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""

    # Forget any user_id
    session.clear()

    # User reached route via GET (as by clicking a link or via redirect)
    if request.method == "GET":
        return render_template("register.html")

    # User reached route via POST (as by submitting a form via POST)
    username = request.form.get("username")
    password = request.form.get("password")
    error = None

    # Ensure username was submitted
    if not username:
        error = "yeah, if you could provide a username"

    # Ensure username is unique
    elif User.query.filter_by(username=username).first():
        error = ("yeah, that username exists, if you could provide a "
                 "different username")

    # Ensure a password was submitted
    elif not password:
        error = "yeah, if you could provide a password"

    # Ensure password and confirmation match
    elif password != request.form.get("confirmation"):
        error = "yeah, if you could provide a matching password confirmation"

    # Ensure password meets length requirements
    elif len(password) < 8 or len(password) > 20:
        error = "yeah, if your password could be 8-20 characters long"

    # Ensure password meets complexity requirements
    elif not (re.search(r"[a-z]", password) and re.search(r"[A-Z]", password)
              and re.search(r"[0-9]", password)):
        error = ("yeah, if your password could contain upper-case, "
                 "lower-case and a number")

    if error:
        flash("403 Forbidden")
        return apology(error, 403)

    # Success
    new_user = User(username=username, hash=generate_password_hash(password))
    try:
        db.session.add(new_user)
        db.session.commit()
    except exc.SQLAlchemyError:
        db.session.rollback()
        flash("500 Internal Server Error")
        return apology("yeah, if the server could work properly", 500)

    # Remember which user has logged in
    session["user_id"] = new_user.id

    # Inform user of success
    flash("You are now registered!")

    # Redirect user to home page
    return redirect("/")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""

    # Query for the user
    user = User.query.filter_by(id=session["user_id"]).first()

    # User reached route via GET (as by clicking a link or via redirect)
    if request.method == "GET":

        # Use relationship attributes to get all user's share symbols
        symbols = [p.stock.symbol for p in user.portfolio]

        return render_template("sell.html", symbols=symbols)

    # User reached route via POST (as by submitting a form via POST)
    symbol = request.form.get("symbol")
    shares = request.form.get("shares")
    error = None

    # Check a symbol was submitted
    if not symbol:
        error = "yeah, if you could provide a symbol"

    # Check shares is a positive integer
    elif not re.fullmatch(r"[1-9]+[0-9]*", shares):
        error = ("yeah, if you could provide a positive whole number of "
                 "shares")

    else:
        # Lookup current number of shares owned for that symbol
        owned = 0
        for item in user.portfolio:
            if item.stock.symbol == symbol:
                portfolio = item  # saved for use below
                owned = portfolio.quantity
                break

        # Check user owns enough shares to sell
        if not owned:
            error = f"yeah, if you owned any {symbol} shares"

        elif owned < int(shares):
            error = f"yeah, if you owned enough {symbol} shares"

        else:
            # Lookup a quote for symbol
            quoted = lookup(symbol)

            # Failed lookup
            if quoted is None:
                error = f"yeah, if we could find a quote for {symbol}"

    # Handle all errors thus far
    if error:
        flash("403 Forbidden")
        return apology(error, 403)

    # Compute profit of sale as decimal
    price = str(quoted["price"])
    quantity_sold = int(shares)
    profit = Decimal(quantity_sold) * Decimal(price)

    # Update the user's cash
    user.cash = str(Decimal(user.cash) + profit)

    # Create the row for the transactions table
    sell_type = TransactionType.query.filter_by(name="SELL").first()
    db.session.add(Transaction(user_id=user.id, stock_id=portfolio.stock.id,
                               type_id=sell_type.id, quantity=quantity_sold,
                               price=price, datetime=datetime.now()))

    # Update number of shares owned
    portfolio.quantity -= quantity_sold

    # Delete portfolio row if quantity now zero
    if not portfolio.quantity:

        # Delete the portfolio row
        db.session.delete(portfolio)

    # Try to commit changes
    try:
        db.session.commit()
    except exc.SQLAlchemyError:
        db.session.rollback()
        flash("500 Internal Server Error")
        return apology("yeah, if the server could work properly", 500)

    # Redirect user to home page
    flash("Sale complete")
    return redirect("/")


@app.route("/deposit", methods=["GET", "POST"])
@login_required
def deposit():
    """Allow user to deposit more cash"""

    return cash_transaction(True)


@app.route("/withdraw", methods=["GET", "POST"])
@login_required
def withdraw():
    """Allow user to withdraw cash"""

    return cash_transaction(False)


def cash_transaction(is_deposit):
    """Implement both the deposit and withdrawal routes"""

    # Query for the user
    user = User.query.filter_by(id=session["user_id"]).first()

    # User reached route via GET (as by clicking a link or via redirect)
    if request.method == "GET":
        if is_deposit:
            return render_template("deposit.html", cash=user.cash)
        return render_template("withdraw.html", cash=user.cash)

    # User reached route via POST (as by submitting a form via POST)
    amount = request.form.get("amount")
    password = request.form.get("password")
    error = None

    # Ensure a password was submitted
    if not password:
        error = "yeah, if you could provide a password"

    # Ensure password matches
    elif not check_password_hash(user.hash, password):
        error = "yeah, if you could provide the correct password"

    else:
        # Check amount has correct format
        match_object = re.match(r"^\s*\$?(\d*)(\.?\d{,2})\s*$", amount)

        if not match_object:
            error = "yeah, if you could enter a valid amount of money"
        else:
            # Get the dollars and the cents strings from the match_object
            dollars = match_object.group(1)
            cents = match_object.group(2)

            # Some defaults if the match was empty string
            if not dollars:
                dollars = "0"
            if not cents:
                cents = ".00"

            # Sum the amount as decimal
            amount = Decimal(dollars + cents)

            # Check the whole string wasn't equal to 0
            if not amount:
                error = "yeah, if you could enter a non-zero amount of money"

            # Check the user has sufficent cash to withdraw
            elif not is_deposit and Decimal(user.cash) < amount:
                error = "yeah, if you had that much money to withdraw"

    # Handle errors
    if error:
        flash("403 Forbidden")
        return apology(error, 403)

    # Success, find the 'stock' in the stocks table
    if is_deposit:
        name = "Deposit"
    else:
        name = "Withdrawal"

    stock = Stock.query.filter_by(name=name).first()

    # Or else add it to the stocks table
    if not stock:
        stock = Stock(name=name)
        try:
            db.session.add(stock)
            db.session.commit()
        except exc.SQLAlchemyError:
            db.session.rollback()
            flash("500 Internal Server Error")
            return apology("yeah, if the server could work properly", 500)

    # Add amount to user's cash
    if is_deposit:
        user.cash = str(Decimal(user.cash) + amount)
    else:
        user.cash = str(Decimal(user.cash) - amount)

    # Create the row for the transactions table
    cash_type = TransactionType.query.filter_by(name="CASH").first()
    db.session.add(Transaction(user_id=user.id, stock_id=stock.id,
                               type_id=cash_type.id, quantity=0,
                               price=str(amount), datetime=datetime.now()))

    # Try to commit changes
    try:
        db.session.commit()
    except exc.SQLAlchemyError:
        db.session.rollback()
        flash("500 Internal Server Error")
        return apology("yeah, if the server could work properly", 500)

    # Redirect user to home page
    if is_deposit:
        flash("Deposit complete")
    else:
        flash("Withdrawal complete")
    return redirect("/")


@app.route("/account")
@login_required
def account():
    """Allow user to make account changes"""

    return render_template("account.html")


@app.route("/change_password", methods=["POST"])
@login_required
def change_password():
    """Change the user's password"""

    # Query for the user
    user = User.query.filter_by(id=session["user_id"]).first()

    old_password = request.form.get("old_password")
    new_password = request.form.get("new_password")
    error = None

    # Ensure an old password was submitted
    if not old_password:
        error = "yeah, if you could provide your old password"

    # Check old password is correct
    elif not check_password_hash(user.hash, old_password):
        error = "yeah, if you could provide a valid password"

    # Ensure a new password was submitted
    elif not new_password:
        error = "yeah, if you could provide a new password"

    # Ensure password and confirmation match
    elif new_password != request.form.get("new_confirmation"):
        error = "yeah, if you could provide a matching password confirmation"

    # Ensure password meets length requirements
    elif len(new_password) < 8 or len(new_password) > 20:
        error = "yeah, if your new password could be 8-20 characters long"

    # Ensure password meets complexity requirements
    elif not (re.search(r"[a-z]", new_password)
              and re.search(r"[A-Z]", new_password)
              and re.search(r"[0-9]", new_password)):
        error = ("yeah, if your new password could contain upper-case, "
                 "lower-case and a number")

    # Handle errors so far
    if error:
        flash("403 Forbidden")
        return apology(error, 403)

    # Success, assign new hash
    user.hash = generate_password_hash(new_password)

    # Commit change
    try:
        db.session.commit()
    except exc.SQLAlchemyError:
        db.session.rollback()
        flash("500 Internal Server Error")
        return apology("yeah, if the server could work properly", 500)

    flash("Password changed")
    return redirect("/")


@app.route("/delete_user", methods=["POST"])
@login_required
def delete_user():
    """Delete the user's account"""

    # Query for the user
    user = User.query.filter_by(id=session["user_id"]).first()

    # Get the form data
    password = request.form.get("password")
    confirm = request.form.get("confirmation")
    error = None

    # Validate data
    if not confirm == "confirmed":
        error = "yeah, if you could tick the checkbox to confirm deletion"

    # Ensure password was submitted
    elif not password:
        error = "yeah, if you could provide your password"

    # Check old password is correct
    elif not check_password_hash(user.hash, password):
        error = "yeah, if you could provide a valid password"

    # Handle errors so far
    if error:
        flash("403 Forbidden")
        return apology(error, 403)

    # Delete user from users table, deletion cascades to portfolio and
    # transactions
    db.session.delete(user)

    # Delete any stocks which are no longer referenced in any user's
    # transactions
    for stock in Stock.query.all():
        if not stock.transactions:
            db.session.delete(stock)

    # Commit change
    try:
        db.session.commit()
    except exc.SQLAlchemyError:
        db.session.rollback()
        flash("500 Internal Server Error")
        return apology("yeah, if the server could work properly", 500)

    # Forget any user_id
    session.clear()

    # Redirect user to register page
    flash('Account deleted')
    return render_template("exited.html")


def errorhandler(e):
    """Handle error"""
    flash(e.code)
    return apology(f"yeah, if we could not have {e.name} errors", e.code)


# listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)
