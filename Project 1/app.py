from flask import Flask, render_template, request, jsonify, redirect, url_for, session, flash
import sqlite3
import yfinance as yf
from datetime import datetime, timedelta
from flask_cors import CORS
from werkzeug.security import generate_password_hash, check_password_hash

# APP CONFIG
app = Flask(__name__)
app.secret_key = "supersecretkey"
CORS(app)

DB_PATH = "transactions.db"
USER_DB = "users.db"

#DB SETUP
def init_transactions_db():
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute("""
            CREATE TABLE IF NOT EXISTS transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                type TEXT NOT NULL,
                amount REAL NOT NULL,
                description TEXT
            )
        """)
        conn.commit()

def init_users_db():
    conn = sqlite3.connect(USER_DB)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL
        )
    ''')
    conn.commit()
    conn.close()

init_transactions_db()
init_users_db()

#HELPERS
def get_all_transactions():
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM transactions")
        rows = cursor.fetchall()
    return rows

def _safe_round(value, ndigits=2, default=0.0):
    try:
        if value is None:
            return default
        return round(float(value), ndigits)
    except Exception:
        return default

# STOCKS CONFIG
INDIAN_STOCKS = {
    'OLA':      {'symbol': 'OLA.NS',       'name': 'Ola Electric Mobility'},
    'VARDHMAN': {'symbol': 'VTL.NS',       'name': 'Vardhman Textiles'},
    'WAAREE':   {'symbol': 'WAAREE.NS',    'name': 'Waaree Energies'},
    'GODFREY':  {'symbol': 'GODFRYPHLP.NS','name': 'Godfrey Phillips India'},
    'BSE':      {'symbol': 'BSE.NS',       'name': 'BSE Limited'},
    'JIOFIN':   {'symbol': 'JIOFIN.NS',    'name': 'Jio Financial Services'},
    'ZOMATO':   {'symbol': 'ZOMATO.NS',    'name': 'Zomato Limited'},
    'MAZAGON':  {'symbol': 'MAZDOCK.NS',   'name': 'Mazagon Dock Shipbuilders'},
    'IRFC':     {'symbol': 'IRFC.NS',      'name': 'Indian Railway Finance Corp'}
}

def get_stock_data(symbol: str):
    try:
        t = yf.Ticker(symbol)

        fi = getattr(t, "fast_info", None)
        info = {}
        try:
            if fi:
                info = {
                    "last_price": getattr(fi, "last_price", None),
                    "previous_close": getattr(fi, "previous_close", None),
                    "day_high": getattr(fi, "day_high", None),
                    "day_low": getattr(fi, "day_low", None),
                    "year_high": getattr(fi, "year_high", None),
                    "year_low": getattr(fi, "year_low", None),
                    "market_cap": getattr(fi, "market_cap", None),
                    "volume": getattr(fi, "volume", None),
                    "ten_day_average_volume": getattr(fi, "ten_day_average_volume", None),
                }
        except Exception:
            info = {}

        if not info.get("last_price"):
            try:
                i = t.info or {}
            except Exception:
                i = {}
            info.setdefault("last_price", i.get("currentPrice") or i.get("regularMarketPrice"))
            info.setdefault("previous_close", i.get("previousClose"))
            info.setdefault("day_high", i.get("dayHigh"))
            info.setdefault("day_low", i.get("dayLow"))
            info.setdefault("year_high", i.get("fiftyTwoWeekHigh"))
            info.setdefault("year_low", i.get("fiftyTwoWeekLow"))
            info.setdefault("market_cap", i.get("marketCap"))
            info.setdefault("volume", i.get("volume"))
            info.setdefault("ten_day_average_volume", i.get("averageVolume10days") or i.get("averageVolume"))

        current_price = info.get("last_price")
        previous_close = info.get("previous_close")

        if current_price is None or previous_close is None:
            try:
                hist = t.history(period="2d")
                if not hist.empty:
                    current_price = current_price or hist["Close"].iloc[-1]
                    if len(hist) >= 2:
                        previous_close = previous_close or hist["Close"].iloc[-2]
                    else:
                        previous_close = previous_close or hist["Close"].iloc[-1]
            except Exception:
                pass

        current_price = _safe_round(current_price, 2, 0.0)
        previous_close = _safe_round(previous_close, 2, 0.0)

        change = current_price - previous_close if previous_close else 0.0
        change_percent = (change / previous_close * 100) if previous_close else 0.0

        volume = info.get("volume") or 0
        avg_volume = info.get("ten_day_average_volume") or 0
        try:
            volume_change = ((volume - avg_volume) / avg_volume * 100) if avg_volume else 0.0
        except Exception:
            volume_change = 0.0

        return {
            'symbol': symbol,
            'current_price': current_price,
            'previous_close': previous_close,
            'change': _safe_round(change, 2, 0.0),
            'change_percent': _safe_round(change_percent, 2, 0.0),
            'volume': int(volume) if volume else 0,
            'avg_volume': int(avg_volume) if avg_volume else 0,
            'volume_change': _safe_round(volume_change, 2, 0.0),
            'market_cap': info.get('market_cap') or 0,
            'day_high': info.get('day_high') or 0,
            'day_low': info.get('day_low') or 0,
            '52_week_high': info.get('year_high') or 0,
            '52_week_low': info.get('year_low') or 0
        }
    except Exception as e:
        print(f"[get_stock_data] Error for {symbol}: {e}")
        return None

def get_historical_data(symbol: str, period: str = '1mo'):
    try:
        t = yf.Ticker(symbol)
        hist = t.history(period=period)
        if hist is None or hist.empty:
            return []
        data = []
        for date, row in hist.iterrows():
            data.append({
                'date': date.strftime('%Y-%m-%d'),
                'open': _safe_round(row.get('Open'), 2, 0.0),
                'high': _safe_round(row.get('High'), 2, 0.0),
                'low': _safe_round(row.get('Low'), 2, 0.0),
                'close': _safe_round(row.get('Close'), 2, 0.0),
                'volume': int(row.get('Volume') or 0)
            })
        return data
    except Exception as e:
        print(f"[get_historical_data] Error for {symbol}: {e}")
        return []
    
    # ------------ CRYPTO DB CONFIG ------------
CRYPTO_DB_PATH = "transactions.db" # Using the same DB file is fine

def init_crypto_db():
    """Initializes the table for blockchain transactions."""
    with sqlite3.connect(CRYPTO_DB_PATH) as conn:
        c = conn.cursor()
        c.execute("""
            CREATE TABLE IF NOT EXISTS blockchain_tx (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                from_address TEXT NOT NULL,
                to_address TEXT NOT NULL,
                amount REAL NOT NULL,
                tx_hash TEXT NOT NULL UNIQUE,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()

        # CRYPTO API ROUTES

@app.route('/api/transaction', methods=['POST'])
def save_blockchain_transaction():
    """Saves a new blockchain transaction from the frontend."""
    data = request.get_json()
    if not all(k in data for k in ['from_address', 'to_address', 'amount', 'tx_hash']):
        return jsonify({'status': 'error', 'message': 'Missing data'}), 400

    try:
        with sqlite3.connect(CRYPTO_DB_PATH) as conn:
            c = conn.cursor()
            c.execute(
                "INSERT INTO blockchain_tx (from_address, to_address, amount, tx_hash) VALUES (?, ?, ?, ?)",
                (data['from_address'], data['to_address'], data['amount'], data['tx_hash'])
            )
            conn.commit()
        return jsonify({'status': 'success', 'message': 'Transaction saved'})
    except sqlite3.IntegrityError:
     
        return jsonify({'status': 'success', 'message': 'Transaction already exists'})
    except Exception as e:
        print(f"Error saving transaction: {e}")
        return jsonify({'status': 'error', 'message': 'Server error'}), 500


@app.route('/api/transactions/<address>', methods=['GET'])
def get_blockchain_transactions(address):
    """Fetches all transactions involving a specific address."""
    try:
        with sqlite3.connect(CRYPTO_DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            c = conn.cursor()
            
            c.execute(
                "SELECT * FROM blockchain_tx WHERE from_address = ? OR to_address = ? ORDER BY timestamp DESC",
                (address.lower(), address.lower())
            )
            rows = c.fetchall()
           
            transactions = [dict(row) for row in rows]
        return jsonify(transactions)
    except Exception as e:
        print(f"Error fetching transactions for {address}: {e}")
        return jsonify({'status': 'error', 'message': 'Could not fetch history'}), 500
    


#AUTH ROUTES
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        conn = sqlite3.connect(USER_DB)
        c = conn.cursor()
        c.execute("SELECT * FROM users WHERE username=?", (username,))
        user = c.fetchone()
        conn.close()

        if user and check_password_hash(user[3], password):
            session["user_id"] = user[0]
            session["username"] = user[1]
            return redirect(url_for("index"))
        else:
            flash("Invalid username or password", "danger")

    return render_template("login.html")

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form["username"]
        email = request.form["email"]
        password = request.form["password"]
        confirm_password = request.form["confirm_password"]

        if password != confirm_password:
            flash("Passwords do not match!", "danger")
            return redirect(url_for("register"))

        hashed_password = generate_password_hash(password)

        try:
            conn = sqlite3.connect(USER_DB)
            c = conn.cursor()
            c.execute("INSERT INTO users (username, email, password) VALUES (?, ?, ?)",
                      (username, email, hashed_password))
            conn.commit()
            conn.close()
            flash("Account created successfully! Please log in.", "success")
            return redirect(url_for("login"))
        except sqlite3.IntegrityError:
            flash("Username or email already exists!", "danger")

    return render_template("register.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

#PP ROUTES
@app.route("/")
def index():
    if "user_id" not in session:
        return redirect(url_for("login"))
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute('SELECT * FROM transactions')
        transactions = c.fetchall()
    return render_template('index.html', transactions=transactions, username=session["username"])

@app.route('/yf')
def YF():
    return render_template('YF.html')

@app.route('/gst')
def gst_calculator():
    return render_template('gst_calculator.html')

@app.route('/emi')
def emi():# FIX DEPLOYMENT BUG
    return render_template('EMI.html')

@app.route('/SIP_ca')
def SIP_ca():
    return render_template('SIP_ca.html')
@app.route('/ai_commander')
def ai_commander():
    return render_template('ai_commander.html')

@app.route('/transaction')
def transaction():
    return render_template('transaction.html')



#TRANSACTIONS CRUD
@app.route('/add', methods=['GET', 'POST'])
def add_transaction():
    if "user_id" not in session:
        return redirect(url_for("login"))
    if request.method == 'POST':
        txn_type = request.form['type']
        amount = float(request.form['amount'])
        description = request.form.get('description', '')

        with sqlite3.connect(DB_PATH) as conn:
            c = conn.cursor()
            c.execute(
                'INSERT INTO transactions (type, amount, description) VALUES (?, ?, ?)',
                (txn_type, amount, description)
            )
            conn.commit()
        return redirect(url_for('index'))
    return render_template('add_transaction.html')

@app.route('/delete/<int:id>')
def delete_transaction(id):
    if "user_id" not in session:
        return redirect(url_for("login"))
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute('DELETE FROM transactions WHERE id = ?', (id,))
        conn.commit()
    return redirect(url_for('index'))

@app.route("/transaction-history")
def transaction_history():
    if "user_id" not in session:
        return redirect(url_for("login"))
    transactions = get_all_transactions()
    return render_template("transaction_history.html", transactions=transactions)

#STOCK APIS 
@app.route('/api/stocks')
def api_get_stocks():
    stocks_data = []
    for key, meta in INDIAN_STOCKS.items():
        data = get_stock_data(meta['symbol'])
        if data:
            data['name'] = meta['name']
            data['key'] = key
            stocks_data.append(data)
    return jsonify({'status': 'success', 'data': stocks_data})

@app.route('/api/stock/<symbol>')
def api_get_single_stock(symbol):
    key = symbol.upper()
    if key in INDIAN_STOCKS:
        meta = INDIAN_STOCKS[key]
        data = get_stock_data(meta['symbol'])
        if data:
            data['name'] = meta['name']
            data['key'] = key
            data['history'] = get_historical_data(meta['symbol'])
            return jsonify({'status': 'success', 'data': data})
    return jsonify({'status': 'error', 'message': 'Stock not found'}), 404

@app.route('/api/volume-shockers')
def api_get_volume_shockers():
    shockers = []
    for key, meta in INDIAN_STOCKS.items():
        data = get_stock_data(meta['symbol'])
        if data and data['volume_change'] > 20:
            shockers.append({
                'name': meta['name'],
                'symbol': key,
                'volume': data['volume'],
                'volume_change': data['volume_change'],
                'current_price': data['current_price'],
                'change_percent': data['change_percent']
            })
    shockers.sort(key=lambda x: x['volume_change'], reverse=True)
    return jsonify({'status': 'success', 'data': shockers[:5]})

@app.route('/api/portfolio')
def api_get_portfolio():
    return jsonify({
        'status': 'success',
        'data': {
            'invested': 24500.90,
            'current': 30080.57,
            'change': 5579.67,
            'change_percent': 22.77,
            'holdings': []
        }
    })

@app.route('/api/search')
def api_search_stocks():
    query = request.args.get('q', '').upper()
    results = []
    if query:
        for key, meta in INDIAN_STOCKS.items():
            if query in key or query in meta['name'].upper():
                results.append({
                    'symbol': key,
                    'name': meta['name'],
                    'exchange': 'NSE'
                })
    return jsonify({'status': 'success', 'data': results})

@app.route('/api/intraday/<symbol>')
def api_get_intraday(symbol):
    key = symbol.upper()
    if key in INDIAN_STOCKS:
        sym = INDIAN_STOCKS[key]['symbol']
        try:
            t = yf.Ticker(sym)
            intraday = t.history(period='1d', interval='1m')
            data = []
            if intraday is not None and not intraday.empty:
                for ts, row in intraday.iterrows():
                    data.append({
                        'time': ts.strftime('%H:%M'),
                        'price': _safe_round(row.get('Close'), 2, 0.0),
                        'volume': int(row.get('Volume') or 0)
                    })
            return jsonify({'status': 'success', 'data': data})
        except Exception as e:
            print(f"[api_get_intraday] Error for {sym}: {e}")
    return jsonify({'status': 'error', 'message': 'Could not fetch intraday data'}), 404

#MAIN
if __name__ == '__main__':
    app.run(debug=True, port=5000)
