<?php
/**
 * Reflex Divine — contact form endpoint (replaces Elementor Pro Forms).
 *
 * Works on any PHP 7.4+ host (cPanel / LiteSpeed / Apache). Uses PHP mail(),
 * which on most shared hosts is relayed through the local MTA.
 *
 * Configuration (no secrets in this file):
 *   - copy config.sample.php to config.php (same folder) OR set env vars
 *     RD_MAIL_TO, RD_MAIL_FROM. config.php is blocked from web access by .htaccess.
 *
 * Security: POST only, same-origin check, honeypot, length limits, strict
 * validation, header-injection safe, simple per-IP rate limit, JSON responses.
 */
declare(strict_types=1);

header('Content-Type: application/json; charset=utf-8');
header('X-Content-Type-Options: nosniff');
header('Cache-Control: no-store');

function respond(int $code, array $body): void {
    http_response_code($code);
    echo json_encode($body, JSON_UNESCAPED_UNICODE);
    exit;
}

if (($_SERVER['REQUEST_METHOD'] ?? '') !== 'POST') {
    header('Allow: POST');
    respond(405, ['ok' => false, 'error' => 'Method not allowed.']);
}

$config = [
    'to'        => getenv('RD_MAIL_TO') ?: '',
    'from'      => getenv('RD_MAIL_FROM') ?: '',
    'site_host' => 'reflexdivine.com',
    'rate_limit_per_hour' => 5,
];
if (is_file(__DIR__ . '/config.php')) {
    $config = array_merge($config, (array) require __DIR__ . '/config.php');
}
if ($config['to'] === '' || $config['from'] === '') {
    respond(503, ['ok' => false, 'error' => 'Mail is not configured on the server.']);
}

// Same-origin check (blocks cross-site form posts)
$origin = $_SERVER['HTTP_ORIGIN'] ?? ($_SERVER['HTTP_REFERER'] ?? '');
if ($origin !== '') {
    $host = parse_url($origin, PHP_URL_HOST) ?: '';
    $allowed = [$config['site_host'], 'www.' . $config['site_host'], $_SERVER['HTTP_HOST'] ?? ''];
    if (!in_array($host, $allowed, true)) {
        respond(403, ['ok' => false, 'error' => 'Forbidden.']);
    }
}

// Honeypot: bots fill hidden fields. Pretend success.
if (!empty($_POST['company'])) {
    respond(200, ['ok' => true]);
}

function field(string $key, int $max): string {
    $v = isset($_POST[$key]) && is_string($_POST[$key]) ? trim($_POST[$key]) : '';
    $v = str_replace("\0", '', $v);
    return mb_substr($v, 0, $max);
}

$name    = preg_replace('/[\r\n]+/', ' ', field('name', 120));
$email   = field('email', 160);
$phone   = field('phone', 20);
$message = field('message', 5000);

if (!filter_var($email, FILTER_VALIDATE_EMAIL) || preg_match('/[\r\n]/', $email)) {
    respond(422, ['ok' => false, 'field' => 'email', 'error' => 'Please enter a valid email address.']);
}
if (!preg_match('/^[0-9()#&+*=.\s-]{6,20}$/', $phone)) {
    respond(422, ['ok' => false, 'field' => 'phone', 'error' => 'Only numbers and phone characters (#, -, *, etc) are accepted.']);
}

// Simple file-based rate limit per IP (hashed — no raw IPs stored)
$ipHash = hash('sha256', ($_SERVER['REMOTE_ADDR'] ?? '') . __FILE__);
$bucket = sys_get_temp_dir() . '/rd-contact-' . substr($ipHash, 0, 32);
$now = time();
$hits = [];
if (is_file($bucket)) {
    $hits = array_filter((array) json_decode((string) file_get_contents($bucket), true), static fn($t) => is_int($t) && $t > $now - 3600);
}
if (count($hits) >= (int) $config['rate_limit_per_hour']) {
    respond(429, ['ok' => false, 'field' => 'form', 'error' => 'Too many messages. Please try again later or call us.']);
}
$hits[] = $now;
@file_put_contents($bucket, json_encode(array_values($hits)), LOCK_EX);

$subject = 'New website enquiry from ' . ($name !== '' ? $name : $email);
$body = "New message from the Reflex Divine website contact form\n\n"
      . "Name:    {$name}\n"
      . "Email:   {$email}\n"
      . "Phone:   {$phone}\n"
      . "Page:    " . preg_replace('/[\r\n]/', '', (string) ($_SERVER['HTTP_REFERER'] ?? '')) . "\n\n"
      . "Message:\n{$message}\n";

$headers = [
    'From: Reflex Divine Website <' . $config['from'] . '>',
    'Reply-To: ' . $email,
    'MIME-Version: 1.0',
    'Content-Type: text/plain; charset=UTF-8',
    'X-Mailer: ReflexDivine-Static',
];

$encodedSubject = '=?UTF-8?B?' . base64_encode($subject) . '?=';
$sent = @mail($config['to'], $encodedSubject, $body, implode("\r\n", $headers), '-f' . $config['from']);

if (!$sent) {
    respond(502, ['ok' => false, 'error' => 'The message could not be sent.']);
}
respond(200, ['ok' => true]);
