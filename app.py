import os

from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.security import check_password_hash, generate_password_hash
import datetime

from helpers import apology, login_required, lookup, usd

# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True

# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")

# Make sure API key is set
if not os.environ.get("API_KEY"):
    raise RuntimeError("API_KEY not set")


@app.after_request
def after_request(response):
    """Ensure responses aren't cached"""
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


@app.route("/")
@login_required
def index():
    user_id = session["user_id"]
    transactions = db.execute(
        "SELECT symbol, SUM(shares) AS shares, price, total, name FROM transactions WHERE user_id = ? GROUP BY id", user_id)
    cash_db = db.execute("SELECT cash FROM users WHERE id = ?", user_id)
    cash = cash_db[0]["cash"]

    return render_template("index.html", transactions=transactions, cash=cash)


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""
    shares = request.form.get("shares")
    if request.method == "POST":
        if not request.form.get("symbol"):
            return apology("must provide symbol", 400)
        elif not request.form.get("shares"):
            return apology("must provide number of shares", 400)
        elif lookup(request.form.get("symbol")) == None:
            return apology("must provide valid symbol", 400)
        elif int(request.form.get("shares")) <= 0 or shares - int(shares) != 0:
            return apology("must provide valid number of shares", 400)
        elif shares.isdigit() == True:
            return apology("must provide valid number of shares", 400)

        symbol = request.form.get("symbol")
        quote = lookup(request.form.get("symbol"))
        price = quote["price"]
        name = quote["name"]
        total = float(price) * float(shares)
        user_id = session["user_id"]
        user_cash_db = db.execute("SELECT cash FROM users WHERE id = ?", user_id)
        user_cash = user_cash_db[0]["cash"]

        if user_cash < total:
            return apology("not enough cash", 403)

        updated_cash = user_cash - total
        db.execute("UPDATE users SET cash = ? WHERE id = ?", updated_cash, user_id)
        date = datetime.datetime.now()
        db.execute("INSERT INTO transactions (user_id, symbol, shares, price, date, total, name) VALUES(?, ?, ?, ?, ?, ?, ?)",
                   user_id, symbol, shares, price, date, total, name)
        db.execute("INSERT INTO history (user_id, symbol, shares, price, date) VALUES(?, ?, ?, ?, ?)",
                   user_id, symbol, shares, price, date)

        flash("Bought!")

        return redirect("/")

    else:
        return render_template("buy.html")


@app.route("/history")
@login_required
def history():
    user_id = session["user_id"]
    history = db.execute("SELECT * FROM history WHERE user_id = ? GROUP BY id", user_id)

    return render_template("history.html", history=history)


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = ?", request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return apology("invalid username and/or password", 403)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    if request.method == "POST":
        if not request.form.get("symbol"):
            return apology("must provide symbol", 400)
        else:
            quote = lookup(request.form.get("symbol"))
            if quote == None:
                return apology("invalid symbol", 400)
            else:
                name = quote["name"]
                price = quote["price"]
                symbol = quote["symbol"]
                return render_template("quoted.html", name=name, price=price, symbol=symbol)
    else:
        return render_template("quote.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        if not request.form.get("username"):
            return apology("must provide username", 400)
        elif not request.form.get("password"):
            return apology("must provide password", 400)
        elif not request.form.get("confirmation"):
            return apology("confirm password", 400)
        elif not request.form.get("password") == request.form.get("confirmation"):
            return apology("passwords don't match", 400)

        row = db.execute("SELECT * FROM users WHERE username = ?", request.form.get("username"))
        if len(row) == 1:
            return apology("username already in use", 400)
        else:
            username = request.form.get("username")
            password = generate_password_hash(request.form.get("password"))
            db.execute("INSERT INTO users (username, hash) VALUES(?, ?)", username, password)

        return redirect("/login")

    else:
        return render_template("register.html")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""
    user_id = session["user_id"]
    if request.method == "POST":
        symbol = request.form.get("symbol")
        shares = request.form.get("shares")
        stock = lookup(symbol)
        price = stock["price"]

        if not symbol:
            return apology("must enter symbol", 403)
        if not shares:
            return apology("must enter shares", 403)
        if int(shares) < 0:
            return apology("must enter valid number of shares", 403)

        transaction_value = float(price) * float(shares)
        user_cash_db = db.execute("SELECT cash FROM users WHERE id = ?", user_id)
        user_cash = user_cash_db[0]["cash"]
        user_shares = db.execute("SELECT shares FROM transactions WHERE user_id = ? AND symbol = ?", user_id, symbol)
        user_share = user_shares[0]["shares"]

        if int(shares) > user_share:
            return apology("you don't own enough shares", 403)
        else:
            new_share = user_share - int(shares)
            if new_share == 0:
                db.execute("DELETE FROM transactions WHERE symbol = ?", symbol)
            else:
                db.execute("UPDATE transactions SET shares = ?, total = ? WHERE symbol = ?", new_share, new_share*price, symbol)

        date = datetime.datetime.now()
        db.execute("INSERT INTO history (user_id, symbol, shares, price, date) VALUES(?, ?, ?, ?, ?)",
                   user_id, symbol, f"-{shares}", price, date)
        updt_cash = user_cash + transaction_value

        db.execute("UPDATE users SET cash = ? WHERE id = ?", round(updt_cash, 2), user_id)

        flash("Sold!")

        return redirect("/")

    else:
        symbols = db.execute("SELECT symbol FROM transactions WHERE user_id = ?", user_id)
        return render_template("sell.html", symbols=[row["symbol"] for row in symbols])
