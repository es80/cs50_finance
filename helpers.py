"""Helper functions to implement application.py."""

import csv
import json
import urllib.request
from functools import wraps
from flask import redirect, render_template, session


def apology(message, code=400):
    """Renders message as an apology to user."""
    def escape(s):
        """
        Escape special characters.

        https://github.com/jacebrowning/memegen#special-characters
        """
        for old, new in [("-", "--"), (" ", "-"), ("_", "__"), ("?", "~q"),
                         ("%", "~p"), ("#", "~h"), ("/", "~s"), ("\"", "''")]:
            s = s.replace(old, new)
        return s
    return render_template("apology.html", top=escape(message),
                           bottom="that'd be great"), code


def login_required(f):
    """
    Decorate routes to require login.

    http://flask.pocoo.org/docs/0.12/patterns/viewdecorators/
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get("user_id") is None:
            return redirect("/login")
        return f(*args, **kwargs)
    return decorated_function


def lookup(symbol):
    """Look up quote for symbol."""

    # Reject symbol if it starts with caret.
    if symbol.startswith("^"):
        return None

    # Reject symbol if it contains comma.
    if "," in symbol:
        return None

    # Query IEX API for quote.
    try:
        # Get JSON data.
        url = f"https://api.iextrading.com/1.0/stock/{symbol}/quote"
        response = urllib.request.urlopen(url)
        data = json.loads(response.read().decode("utf-8"))

        # Ensure price exists.
        try:
            price = float(data["latestPrice"])
        except:
            return None

        # Return stock's name (as a str), price (as a float), and (uppercased)
        # symbol (as a str).
        return {
            "name": data["companyName"],
            "price": price,
            "symbol": data["symbol"].upper()
        }

    except:
        pass

    # Query Yahoo for quote.
    # http://stackoverflow.com/a/21351911
    try:

        # GET CSV.
        url = ("http://download.finance.yahoo.com/d/quotes.csv?f=snl1&"
               f"s={symbol}")
        webpage = urllib.request.urlopen(url)

        # Read CSV.
        datareader = csv.reader(webpage.read().decode("utf-8").splitlines())

        # Parse first row.
        row = next(datareader)

        # Ensure stock exists.
        try:
            price = float(row[2])
        except:
            return None

        # Return stock's name (as a str), price (as a float), and (uppercased)
        # symbol (as a str).
        return {
            "name": row[1],
            "price": price,
            "symbol": row[0].upper()
        }

    except:
        pass

    # Query Alpha Vantage for quote instead.
    # https://www.alphavantage.co/documentation/
    try:

        # GET CSV.
        url = ("https://www.alphavantage.co/query?"
               "apikey=NAJXWIA8D6VN6A3K&datatype=csv"
               "&function=TIME_SERIES_INTRADAY"
               f"&interval=1min&symbol={symbol}")

        webpage = urllib.request.urlopen(url)

        # Parse CSV.
        datareader = csv.reader(webpage.read().decode("utf-8").splitlines())

        # Ignore first row.
        next(datareader)

        # Parse second row.
        row = next(datareader)

        # Ensure stock exists.
        try:
            price = float(row[4])
        except:
            return None

        # Return stock's name (as a str), price (as a float), and (uppercased)
        # symbol (as a str).
        return {
            "name": symbol.upper(),  # for backward compatibility with Yahoo
            "price": price,
            "symbol": symbol.upper()
        }

    except:
        return None


def usd(value):
    """Formats value as USD."""

    # Any string passed should be converted to float first.
    if isinstance(value, str):
        value = float(value)

    return f"${value:,.2f}"


def f_time(time):
    """Formats a datetime object as a time."""
    return time.strftime("%H:%M:%S")


def f_date(date):
    """Formats a datetime object as a date."""
    return date.strftime("%d %b %y")
