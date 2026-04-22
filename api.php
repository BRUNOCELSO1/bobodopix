<?php
session_start();
header('Content-Type: application/json; charset=utf-8');
header('Cache-Control: no-store');

$DATA  = __DIR__ . '/data';
$DB    = $DATA . '/contratos.json';
$USERS = $DATA . '/usuarios.json';

if (!is_dir($DATA)) mkdir($DATA, 0755, true);

/* ── helpers ──────────────────────────────────────────────────────────────── */
function rj($path, $def = []) {
    if (!file_exists($path)) return $def;
    return json_decode(file_get_contents($path), true) ?? $def;
}

function wj($path, $data) {
    $tmp = $path . '.tmp';
    file_put_contents($tmp, json_encode($data, JSON_PRETTY_PRINT | JSON_UNESCAPED_UNICODE));
    rename($tmp, $path);
}

function resp($data, $code = 200) {
    http_response_code($code);
    echo json_encode($data, JSON_UNESCAPED_UNICODE);
    exit;
}

/* compatível com o formato gerado pelo Python: {salt}${sha256(salt+pw)} */
function check_pw($pw, $stored) {
    $parts = explode('$', $stored, 2);
    if (count($parts) !== 2) return false;
    return hash('sha256', $parts[0] . $pw) === $parts[1];
}

function hash_pw($pw) {
    $salt = bin2hex(random_bytes(16));
    return $salt . '$' . hash('sha256', $salt . $pw);
}

/* ── usuário padrão ───────────────────────────────────────────────────────── */
global $USERS;
if (!file_exists($USERS)) {
    wj($USERS, [[
        'id'      => '1',
        'nome'    => 'Administrador',
        'usuario' => 'BOBO777',
        'senha'   => hash_pw('NAODOU@123'),
    ]]);
}

/* ── roteamento ───────────────────────────────────────────────────────────── */
$method = $_SERVER['REQUEST_METHOD'];
$uri    = parse_url($_SERVER['REQUEST_URI'], PHP_URL_PATH);

// extrai o segmento após /api
preg_match('#/api(/[^?]*)?#', $uri, $m);
$path = rtrim($m[1] ?? '/', '/') ?: '/';

/* POST /login */
if ($method === 'POST' && $path === '/login') {
    $body  = json_decode(file_get_contents('php://input'), true) ?? [];
    foreach (rj($USERS) as $u) {
        if ($u['usuario'] === ($body['usuario'] ?? '') &&
            check_pw($body['senha'] ?? '', $u['senha'])) {
            $_SESSION['uid']  = $u['id'];
            $_SESSION['nome'] = $u['nome'];
            resp(['ok' => true, 'nome' => $u['nome']]);
        }
    }
    resp(['ok' => false, 'msg' => 'Usuário ou senha incorretos'], 401);
}

/* POST /logout */
if ($method === 'POST' && $path === '/logout') {
    session_destroy();
    resp(['ok' => true]);
}

/* GET /me */
if ($method === 'GET' && $path === '/me') {
    if (empty($_SESSION['uid'])) resp(['ok' => false], 401);
    resp(['ok' => true, 'nome' => $_SESSION['nome']]);
}

/* ── requer autenticação ──────────────────────────────────────────────────── */
if (empty($_SESSION['uid'])) resp(['ok' => false, 'msg' => 'Não autenticado'], 401);

/* GET /contratos */
if ($method === 'GET' && $path === '/contratos') {
    resp(rj($DB));
}

/* POST /contratos */
if ($method === 'POST' && $path === '/contratos') {
    $body  = json_decode(file_get_contents('php://input'), true) ?? [];
    $items = rj($DB);
    $items[] = $body;
    wj($DB, $items);
    resp(['ok' => true]);
}

/* PUT /contratos/{id} */
if ($method === 'PUT' && preg_match('#^/contratos/(.+)$#', $path, $mx)) {
    $id    = $mx[1];
    $body  = json_decode(file_get_contents('php://input'), true) ?? [];
    $items = array_map(fn($c) => $c['id'] === $id ? $body : $c, rj($DB));
    wj($DB, array_values($items));
    resp(['ok' => true]);
}

/* DELETE /contratos/{id} */
if ($method === 'DELETE' && preg_match('#^/contratos/(.+)$#', $path, $mx)) {
    $id    = $mx[1];
    $items = array_filter(rj($DB), fn($c) => $c['id'] !== $id);
    wj($DB, array_values($items));
    resp(['ok' => true]);
}

resp(['ok' => false, 'msg' => 'Not found'], 404);
