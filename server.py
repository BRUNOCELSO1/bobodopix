#!/usr/bin/env python3
"""
Bobo do Pix — Servidor
Execute: python3 server.py
Acesse:  http://localhost:8080
"""
import os, json, hashlib, secrets, time, sys
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs, unquote

BASE   = os.path.dirname(os.path.abspath(__file__))
DATA   = os.path.join(BASE, 'data')
DB     = os.path.join(DATA, 'contratos.json')
USERS  = os.path.join(DATA, 'usuarios.json')
SESS   = os.path.join(DATA, 'sessoes.json')
PORT   = int(os.environ.get('PORT', 8080))

os.makedirs(DATA, exist_ok=True)

# ── helpers de arquivo ────────────────────────────────────────────────────────

def read_json(path, default):
    try:
        with open(path, encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return default

def write_json(path, data):
    tmp = path + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)

# ── usuário padrão ────────────────────────────────────────────────────────────

def hash_pw(pw, salt=None):
    if salt is None:
        salt = secrets.token_hex(16)
    h = hashlib.sha256((salt + pw).encode()).hexdigest()
    return f"{salt}${h}"

def check_pw(pw, stored):
    salt, _ = stored.split('$', 1)
    return hash_pw(pw, salt) == stored

if not os.path.exists(USERS):
    write_json(USERS, [
        {"id": "1", "nome": "Administrador", "usuario": "BOBO777",
         "senha": hash_pw("NAODOU@123")}
    ])

# ── sessões ───────────────────────────────────────────────────────────────────

def sess_get(token):
    if not token:
        return None
    sess = read_json(SESS, {})
    s = sess.get(token)
    if s and s['exp'] > time.time():
        return s
    return None

def sess_create(user_id, nome):
    token = secrets.token_hex(32)
    sess  = read_json(SESS, {})
    sess[token] = {'uid': user_id, 'nome': nome, 'exp': time.time() + 86400 * 7}
    sess = {k: v for k, v in sess.items() if v['exp'] > time.time()}
    write_json(SESS, sess)
    return token

def sess_delete(token):
    sess = read_json(SESS, {})
    sess.pop(token, None)
    write_json(SESS, sess)

# ── handler HTTP ──────────────────────────────────────────────────────────────

class H(BaseHTTPRequestHandler):

    def log_message(self, *a): pass

    def get_cookie(self, name):
        raw = self.headers.get('Cookie', '')
        for part in raw.split(';'):
            k, _, v = part.strip().partition('=')
            if k.strip() == name:
                return v.strip()
        return None

    def set_cookie(self, name, value, days=7, delete=False):
        if delete:
            return f'{name}=; Path=/; HttpOnly; Max-Age=0'
        return f'{name}={value}; Path=/; HttpOnly; Max-Age={days*86400}'

    def json_resp(self, code, data, extra_headers=None):
        body = json.dumps(data, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', len(body))
        if extra_headers:
            for k, v in extra_headers.items():
                self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def html_resp(self, code, body_bytes, extra_headers=None):
        self.send_response(code)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.send_header('Content-Length', len(body_bytes))
        if extra_headers:
            for k, v in extra_headers.items():
                self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body_bytes)

    def redirect(self, location, cookie_header=None):
        self.send_response(302)
        self.send_header('Location', location)
        if cookie_header:
            self.send_header('Set-Cookie', cookie_header)
        self.end_headers()

    def body(self):
        n = int(self.headers.get('Content-Length', 0))
        return json.loads(self.rfile.read(n)) if n else {}

    def current_user(self):
        return sess_get(self.get_cookie('sid'))

    def do_GET(self):
        p = urlparse(self.path).path.rstrip('/')

        if p in ('', '/'):
            self.redirect('/app' if self.current_user() else '/login')
            return

        if p == '/login':
            self.html_resp(200, open(os.path.join(BASE, 'login.html'), 'rb').read())
            return

        if p == '/app':
            if not self.current_user():
                self.redirect('/login')
                return
            self.html_resp(200, open(os.path.join(BASE, 'app.html'), 'rb').read())
            return

        if p == '/api/me':
            u = self.current_user()
            if not u:
                self.json_resp(401, {'ok': False})
                return
            self.json_resp(200, {'ok': True, 'nome': u['nome']})
            return

        if p == '/api/contratos':
            if not self.current_user():
                self.json_resp(401, {'ok': False})
                return
            self.json_resp(200, read_json(DB, []))
            return

        # arquivos estáticos
        static = os.path.join(BASE, unquote(p).lstrip('/'))
        if os.path.isfile(static):
            ext  = os.path.splitext(static)[1].lower()
            mime = {'.png':'image/png','.jpg':'image/jpeg','.svg':'image/svg+xml',
                    '.ico':'image/x-icon'}.get(ext, 'application/octet-stream')
            with open(static, 'rb') as f:
                body = f.read()
            self.send_response(200)
            self.send_header('Content-Type', mime)
            self.send_header('Content-Length', len(body))
            self.end_headers()
            self.wfile.write(body)
            return

        self.json_resp(404, {'ok': False, 'msg': 'not found'})

    def do_POST(self):
        p = urlparse(self.path).path.rstrip('/')

        if p == '/api/login':
            d = self.body()
            users = read_json(USERS, [])
            u = next((x for x in users if x['usuario'] == d.get('usuario', '')), None)
            if u and check_pw(d.get('senha', ''), u['senha']):
                token = sess_create(u['id'], u['nome'])
                self.json_resp(200, {'ok': True, 'nome': u['nome']},
                               {'Set-Cookie': self.set_cookie('sid', token)})
            else:
                self.json_resp(401, {'ok': False, 'msg': 'Usuário ou senha incorretos'})
            return

        if p == '/api/logout':
            token = self.get_cookie('sid')
            if token:
                sess_delete(token)
            self.json_resp(200, {'ok': True},
                           {'Set-Cookie': self.set_cookie('sid', '', delete=True)})
            return

        if p == '/api/contratos':
            if not self.current_user():
                self.json_resp(401, {'ok': False}); return
            data = self.body()
            contratos = read_json(DB, [])
            contratos.append(data)
            write_json(DB, contratos)
            self.json_resp(200, {'ok': True})
            return

        self.json_resp(404, {'ok': False})

    def do_PUT(self):
        p = urlparse(self.path).path
        if p.startswith('/api/contratos/'):
            if not self.current_user():
                self.json_resp(401, {'ok': False}); return
            cid   = p.split('/')[-1]
            data  = self.body()
            items = read_json(DB, [])
            items = [data if c['id'] == cid else c for c in items]
            write_json(DB, items)
            self.json_resp(200, {'ok': True})
            return
        self.json_resp(404, {'ok': False})

    def do_DELETE(self):
        p = urlparse(self.path).path
        if p.startswith('/api/contratos/'):
            if not self.current_user():
                self.json_resp(401, {'ok': False}); return
            cid   = p.split('/')[-1]
            items = read_json(DB, [])
            items = [c for c in items if c['id'] != cid]
            write_json(DB, items)
            self.json_resp(200, {'ok': True})
            return
        self.json_resp(404, {'ok': False})

# ── main ──────────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    print(f'Bobo do Pix | porta {PORT}', flush=True)
    server = HTTPServer(('0.0.0.0', PORT), H)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print('Servidor encerrado.')
