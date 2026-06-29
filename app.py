"""
Suvarna — Jewelry Shop Manager
Supports both PostgreSQL (production/Railway) and SQLite (local)
"""

import os
import csv
import io
import random
import string
import webbrowser
import threading
from datetime import datetime
from flask import Flask, request, jsonify, render_template, Response, g

app = Flask(__name__)

# ─── DATABASE SETUP ──────────────────────────────────────────────────────────
# Uses PostgreSQL if DATABASE_URL env var is set (Railway), else SQLite locally

DATABASE_URL = os.environ.get('DATABASE_URL', '')
USE_POSTGRES  = bool(DATABASE_URL)

if USE_POSTGRES:
    import psycopg2
    import psycopg2.extras
    # Railway gives 'postgres://' but psycopg2 needs 'postgresql://'
    if DATABASE_URL.startswith('postgres://'):
        DATABASE_URL = DATABASE_URL.replace('postgres://', 'postgresql://', 1)

    def get_db():
        db = getattr(g, '_database', None)
        if db is None:
            db = g._database = psycopg2.connect(DATABASE_URL)
        return db

    @app.teardown_appcontext
    def close_db(e):
        db = getattr(g, '_database', None)
        if db: db.close()

    def cursor():
        return get_db().cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    def commit():
        get_db().commit()

    PH = '%s'   # postgres placeholder

else:
    import sqlite3
    DB_PATH = os.path.join(os.path.dirname(__file__), 'suvarna.db')

    def get_db():
        db = getattr(g, '_database', None)
        if db is None:
            db = g._database = sqlite3.connect(DB_PATH)
            db.row_factory = sqlite3.Row
            db.execute("PRAGMA journal_mode=WAL")
        return db

    @app.teardown_appcontext
    def close_db(e):
        db = getattr(g, '_database', None)
        if db: db.close()

    def cursor():
        return get_db().cursor()

    def commit():
        get_db().commit()

    PH = '?'    # sqlite placeholder


def fetchall(cur):
    rows = cur.fetchall()
    return [dict(r) for r in rows]

def fetchone(cur):
    r = cur.fetchone()
    return dict(r) if r else None


# ─── INIT DB ─────────────────────────────────────────────────────────────────

def init_db():
    with app.app_context():
        cur = cursor()
        if USE_POSTGRES:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS sales (
                    id           TEXT PRIMARY KEY,
                    date         TEXT NOT NULL,
                    item         TEXT NOT NULL,
                    category     TEXT,
                    metal        TEXT,
                    weight       NUMERIC DEFAULT 0,
                    purity       TEXT,
                    wastage_pct  NUMERIC DEFAULT 0,
                    wastage_g    NUMERIC DEFAULT 0,
                    adj_price    NUMERIC DEFAULT 0,
                    price        NUMERIC DEFAULT 0,
                    making       NUMERIC DEFAULT 0,
                    cost         NUMERIC DEFAULT 0,
                    gross_profit NUMERIC DEFAULT 0,
                    payment      TEXT,
                    customer     TEXT,
                    notes        TEXT,
                    created_at   TEXT DEFAULT current_timestamp
                );
                CREATE TABLE IF NOT EXISTS expenses (
                    id          TEXT PRIMARY KEY,
                    date        TEXT NOT NULL,
                    type        TEXT NOT NULL,
                    amount      NUMERIC DEFAULT 0,
                    description TEXT,
                    staff       TEXT,
                    created_at  TEXT DEFAULT current_timestamp
                );
                CREATE TABLE IF NOT EXISTS inventory (
                    id         TEXT PRIMARY KEY,
                    name       TEXT NOT NULL,
                    category   TEXT,
                    metal      TEXT,
                    purity     TEXT,
                    qty        INTEGER DEFAULT 0,
                    weight     NUMERIC DEFAULT 0,
                    cost       NUMERIC DEFAULT 0,
                    notes      TEXT,
                    created_at TEXT DEFAULT current_timestamp
                );
                CREATE TABLE IF NOT EXISTS prices (
                    date       TEXT PRIMARY KEY,
                    gold       NUMERIC DEFAULT 0,
                    silver     NUMERIC DEFAULT 0,
                    updated_at TEXT DEFAULT current_timestamp
                );
            """)
        else:
            get_db().executescript("""
                CREATE TABLE IF NOT EXISTS sales (
                    id TEXT PRIMARY KEY, date TEXT NOT NULL, item TEXT NOT NULL,
                    category TEXT, metal TEXT, weight REAL DEFAULT 0, purity TEXT,
                    wastage_pct REAL DEFAULT 0, wastage_g REAL DEFAULT 0,
                    adj_price REAL DEFAULT 0, price REAL DEFAULT 0,
                    making REAL DEFAULT 0, cost REAL DEFAULT 0,
                    gross_profit REAL DEFAULT 0, payment TEXT,
                    customer TEXT, notes TEXT,
                    created_at TEXT DEFAULT (datetime('now'))
                );
                CREATE TABLE IF NOT EXISTS expenses (
                    id TEXT PRIMARY KEY, date TEXT NOT NULL, type TEXT NOT NULL,
                    amount REAL DEFAULT 0, description TEXT, staff TEXT,
                    created_at TEXT DEFAULT (datetime('now'))
                );
                CREATE TABLE IF NOT EXISTS inventory (
                    id TEXT PRIMARY KEY, name TEXT NOT NULL, category TEXT,
                    metal TEXT, purity TEXT, qty INTEGER DEFAULT 0,
                    weight REAL DEFAULT 0, cost REAL DEFAULT 0, notes TEXT,
                    created_at TEXT DEFAULT (datetime('now'))
                );
                CREATE TABLE IF NOT EXISTS prices (
                    date TEXT PRIMARY KEY, gold REAL DEFAULT 0, silver REAL DEFAULT 0,
                    updated_at TEXT DEFAULT (datetime('now'))
                );
            """)
        commit()


def gen_id():
    ts  = datetime.now().strftime('%Y%m%d%H%M%S')
    rnd = ''.join(random.choices(string.ascii_lowercase + string.digits, k=4))
    return ts + rnd


# ─── ROUTES ──────────────────────────────────────────────────────────────────

@app.route('/')
def index():
    return render_template('index.html')


# SALES
@app.route('/api/sales', methods=['GET'])
def get_sales():
    date_from = request.args.get('from', '')
    date_to   = request.args.get('to', '')
    metal     = request.args.get('metal', '')
    q = "SELECT * FROM sales WHERE 1=1"
    params = []
    if date_from: q += f" AND date >= {PH}"; params.append(date_from)
    if date_to:   q += f" AND date <= {PH}"; params.append(date_to)
    if metal:     q += f" AND metal = {PH}";  params.append(metal)
    q += " ORDER BY date DESC, created_at DESC"
    cur = cursor(); cur.execute(q, params)
    return jsonify(fetchall(cur))

@app.route('/api/sales', methods=['POST'])
def add_sale():
    d   = request.json
    sid = gen_id()
    cur = cursor()
    cur.execute(f"""
        INSERT INTO sales (id,date,item,category,metal,weight,purity,wastage_pct,
                           wastage_g,adj_price,price,making,cost,gross_profit,payment,customer,notes)
        VALUES ({PH},{PH},{PH},{PH},{PH},{PH},{PH},{PH},{PH},{PH},{PH},{PH},{PH},{PH},{PH},{PH},{PH})
    """, (sid, d.get('date'), d.get('item'), d.get('category'), d.get('metal'),
          d.get('weight',0), d.get('purity',''), d.get('wastage_pct',0), d.get('wastage_g',0),
          d.get('adj_price',0), d.get('price',0), d.get('making',0), d.get('cost',0),
          d.get('gross_profit',0), d.get('payment'), d.get('customer',''), d.get('notes','')))
    commit()
    return jsonify({'id': sid, 'ok': True})

@app.route('/api/sales/<sid>', methods=['DELETE'])
def delete_sale(sid):
    cur = cursor()
    cur.execute(f"DELETE FROM sales WHERE id={PH}", (sid,))
    commit()
    return jsonify({'ok': True})


# EXPENSES
@app.route('/api/expenses', methods=['GET'])
def get_expenses():
    date_from = request.args.get('from', '')
    date_to   = request.args.get('to', '')
    etype     = request.args.get('type', '')
    q = "SELECT * FROM expenses WHERE 1=1"
    params = []
    if date_from: q += f" AND date >= {PH}"; params.append(date_from)
    if date_to:   q += f" AND date <= {PH}"; params.append(date_to)
    if etype:     q += f" AND type = {PH}";   params.append(etype)
    q += " ORDER BY date DESC, created_at DESC"
    cur = cursor(); cur.execute(q, params)
    return jsonify(fetchall(cur))

@app.route('/api/expenses', methods=['POST'])
def add_expense():
    d   = request.json
    eid = gen_id()
    cur = cursor()
    cur.execute(f"""
        INSERT INTO expenses (id,date,type,amount,description,staff)
        VALUES ({PH},{PH},{PH},{PH},{PH},{PH})
    """, (eid, d.get('date'), d.get('type'), d.get('amount',0),
          d.get('description',''), d.get('staff','')))
    commit()
    return jsonify({'id': eid, 'ok': True})

@app.route('/api/expenses/<eid>', methods=['DELETE'])
def delete_expense(eid):
    cur = cursor()
    cur.execute(f"DELETE FROM expenses WHERE id={PH}", (eid,))
    commit()
    return jsonify({'ok': True})


# INVENTORY
@app.route('/api/inventory', methods=['GET'])
def get_inventory():
    cur = cursor()
    cur.execute("SELECT * FROM inventory ORDER BY created_at DESC")
    return jsonify(fetchall(cur))

@app.route('/api/inventory', methods=['POST'])
def add_inventory():
    d   = request.json
    iid = gen_id()
    cur = cursor()
    cur.execute(f"""
        INSERT INTO inventory (id,name,category,metal,purity,qty,weight,cost,notes)
        VALUES ({PH},{PH},{PH},{PH},{PH},{PH},{PH},{PH},{PH})
    """, (iid, d.get('name'), d.get('category'), d.get('metal'),
          d.get('purity',''), d.get('qty',0), d.get('weight',0),
          d.get('cost',0), d.get('notes','')))
    commit()
    return jsonify({'id': iid, 'ok': True})

@app.route('/api/inventory/<iid>', methods=['DELETE'])
def delete_inventory_item(iid):
    cur = cursor()
    cur.execute(f"DELETE FROM inventory WHERE id={PH}", (iid,))
    commit()
    return jsonify({'ok': True})


# PRICES
@app.route('/api/prices', methods=['GET'])
def get_prices():
    cur = cursor()
    cur.execute("SELECT * FROM prices ORDER BY date DESC")
    return jsonify(fetchall(cur))

@app.route('/api/prices', methods=['POST'])
def save_price():
    d   = request.json
    cur = cursor()
    if USE_POSTGRES:
        cur.execute("""
            INSERT INTO prices (date,gold,silver,updated_at)
            VALUES (%s,%s,%s,current_timestamp)
            ON CONFLICT(date) DO UPDATE SET gold=EXCLUDED.gold, silver=EXCLUDED.silver, updated_at=current_timestamp
        """, (d.get('date'), d.get('gold',0), d.get('silver',0)))
    else:
        cur.execute("""
            INSERT INTO prices (date,gold,silver,updated_at)
            VALUES (?,?,?,datetime('now'))
            ON CONFLICT(date) DO UPDATE SET gold=excluded.gold, silver=excluded.silver, updated_at=excluded.updated_at
        """, (d.get('date'), d.get('gold',0), d.get('silver',0)))
    commit()
    return jsonify({'ok': True})

@app.route('/api/prices/<date>', methods=['DELETE'])
def delete_price(date):
    cur = cursor()
    cur.execute(f"DELETE FROM prices WHERE date={PH}", (date,))
    commit()
    return jsonify({'ok': True})


# SUMMARY
@app.route('/api/summary', methods=['GET'])
def summary():
    date_from = request.args.get('from', '')
    date_to   = request.args.get('to', '')
    ws = "WHERE 1=1"; we = "WHERE 1=1"
    ps = []; pe = []
    if date_from:
        ws += f" AND date >= {PH}"; ps.append(date_from)
        we += f" AND date >= {PH}"; pe.append(date_from)
    if date_to:
        ws += f" AND date <= {PH}"; ps.append(date_to)
        we += f" AND date <= {PH}"; pe.append(date_to)

    cur = cursor()
    cur.execute(f"SELECT * FROM sales {ws}", ps)
    sales = fetchall(cur)
    cur.execute(f"SELECT * FROM expenses {we}", pe)
    expenses = fetchall(cur)

    total_rev    = sum(float(r.get('price',0))        for r in sales)
    total_cogs   = sum(float(r.get('cost',0))         for r in sales)
    total_making = sum(float(r.get('making',0))       for r in sales)
    gross_profit = sum(float(r.get('gross_profit',0)) for r in sales)

    by_type = {}
    for e in expenses:
        by_type[e['type']] = by_type.get(e['type'], 0) + float(e.get('amount',0))

    wages    = by_type.get('Wages', 0)
    wastage  = by_type.get('Wastage', 0)
    rent     = by_type.get('Rent', 0)
    elec     = by_type.get('Electricity', 0)
    purchase = by_type.get('Purchase', 0)
    repair   = by_type.get('Repair', 0)
    other    = sum(v for k,v in by_type.items()
                   if k not in ('Wages','Wastage','Rent','Electricity','Purchase','Repair'))
    total_exp  = wages + wastage + rent + elec + repair + other
    net_profit = gross_profit - total_exp

    return jsonify({
        'total_revenue': total_rev, 'total_cogs': total_cogs,
        'total_making': total_making, 'gross_profit': gross_profit,
        'wages': wages, 'wastage': wastage, 'rent': rent,
        'electricity': elec, 'purchase': purchase, 'repair': repair,
        'other': other, 'total_expenses': total_exp,
        'net_profit': net_profit, 'sales_count': len(sales),
    })


# CSV EXPORTS
@app.route('/api/export/sales')
def export_sales():
    cur = cursor()
    cur.execute("SELECT * FROM sales ORDER BY date DESC")
    rows = fetchall(cur)
    out = io.StringIO()
    w = csv.writer(out)
    w.writerow(['Date','Item','Category','Metal','Weight(g)','Purity','Wastage%',
                'Wastage(g)','Adj.Price','Sale Price','Making','Cost','Gross Profit',
                'Payment','Customer','Notes'])
    for r in rows:
        w.writerow([r.get('date'),r.get('item'),r.get('category'),r.get('metal'),
                    r.get('weight'),r.get('purity'),r.get('wastage_pct'),r.get('wastage_g'),
                    r.get('adj_price'),r.get('price'),r.get('making'),r.get('cost'),
                    r.get('gross_profit'),r.get('payment'),r.get('customer'),r.get('notes')])
    return Response(out.getvalue(), mimetype='text/csv',
                    headers={'Content-Disposition':'attachment;filename=suvarna_sales.csv'})

@app.route('/api/export/expenses')
def export_expenses():
    cur = cursor()
    cur.execute("SELECT * FROM expenses ORDER BY date DESC")
    rows = fetchall(cur)
    out = io.StringIO()
    w = csv.writer(out)
    w.writerow(['Date','Type','Amount','Description','Staff'])
    for r in rows:
        w.writerow([r.get('date'),r.get('type'),r.get('amount'),r.get('description'),r.get('staff')])
    return Response(out.getvalue(), mimetype='text/csv',
                    headers={'Content-Disposition':'attachment;filename=suvarna_expenses.csv'})


# ─── RUN ─────────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    init_db()
    port = int(os.environ.get('PORT', 5000))
    if not USE_POSTGRES:
        print("\n" + "="*50)
        print("  SUVARNA — Jewelry Shop Manager")
        print(f"  http://localhost:{port}")
        print("  Database: suvarna.db (SQLite, local)")
        print("  Press Ctrl+C to stop")
        print("="*50 + "\n")
        def open_browser():
            import time; time.sleep(1)
            webbrowser.open(f'http://localhost:{port}')
        threading.Thread(target=open_browser, daemon=True).start()
    app.run(host='0.0.0.0', port=port, debug=False)
