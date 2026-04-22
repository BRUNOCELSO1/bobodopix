<?php
session_start();

$uri  = parse_url($_SERVER['REQUEST_URI'], PHP_URL_PATH);
$page = trim(basename($uri), '/');

/* rota raiz → redireciona */
if ($page === '' || $page === 'index.php') {
    header('Location: ' . (empty($_SESSION['uid']) ? '/login' : '/app'));
    exit;
}

/* rota /login */
if ($page === 'login') {
    if (!empty($_SESSION['uid'])) { header('Location: /app'); exit; }
    readfile(__DIR__ . '/login.html');
    exit;
}

/* rota /app */
if ($page === 'app') {
    if (empty($_SESSION['uid'])) { header('Location: /login'); exit; }
    readfile(__DIR__ . '/app.html');
    exit;
}

http_response_code(404);
echo 'Página não encontrada.';
