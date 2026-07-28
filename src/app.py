from flask import Flask, request, render_template, url_for, redirect, flash, get_flashed_messages
import psycopg2, hashlib, os
from werkzeug.middleware.proxy_fix import ProxyFix

app = Flask(__name__)
app.secret_key = "some-secret-key"

app.wsgi_app = ProxyFix(
    app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1
)

def generate_token(url):
    h = hashlib.sha256(url.encode()).hexdigest().upper()
    return h[:6]

def connect():
    try:
        conn = psycopg2.connect(
            dbname=os.environ.get("POSTGRES_DB"),
            user=os.environ.get("POSTGRES_USER"),
            password=os.environ.get("POSTGRES_PASSWORD"),
            host="sql_server"
        )
        return conn
    except psycopg2.Error:
        return None

def init_db():
    sql_query = """ CREATE TABLE IF NOT EXISTS url (
    id SERIAL PRIMARY KEY,
    token text NOT NULL UNIQUE,
    redirect text NOT NULL
    );"""

    conn = None
    cursor = None
    try:
        conn = connect()
        cursor = conn.cursor()
        cursor.execute(sql_query)
        conn.commit()
    except Exception as e:
        print(e)
        return "An error has occured", 500
    finally:
        if cursor is not None:
            cursor.close()
        if conn is not None:
            conn.close()

@app.route('/', methods=['GET','POST'])
def generate_url():
    if request.method == 'POST':
        conn = None
        cursor = None
        try:
            conn = connect()
            url = request.form['url']
            if not url.startswith(('http://', 'https://')):
                url = 'https://' + url
            token = generate_token(url)
            sql_query = """INSERT INTO url (token, redirect)
                        VALUES (%s, %s) ON CONFLICT DO NOTHING;"""
            cursor = conn.cursor()
            cursor.execute(sql_query, (token, url))
            conn.commit()
            short_url = url_for('redirect_to_url', code=token, _external=True)
            return render_template('index.html', short_url=short_url)
        except Exception as e:
            print(e)
            return "An error has occured", 500
        finally:
            if cursor is not None:
                cursor.close()
            if conn is not None:
                conn.close()
    messages = get_flashed_messages()
    error_msg = messages[0] if messages else None
    return render_template('index.html', error=error_msg)


@app.route('/<code>')
def redirect_to_url(code):
    conn = None
    cursor = None
    try:
        conn = connect()
        sql_query = """SELECT redirect FROM url WHERE token = %s;"""
        cursor = conn.cursor()
        cursor.execute(sql_query, (code,))
        row = cursor.fetchone()

        if row is None:
            flash("Redirect not found!")
            return redirect(url_for('generate_url'))
        return redirect(row[0])
    except Exception as e:
        
        return e, 500
    finally:
        if cursor is not None:
            cursor.close()
        if conn is not None:
            conn.close()

if __name__ == '__main__':
    init_db()
    app.run(host="0.0.0.0", port=4242, debug=True)