<?php
// Simple waitlist handler — stores submissions to a CSV file and sends email notification
header('Content-Type: application/json');

if ($_SERVER['REQUEST_METHOD'] !== 'POST') {
    http_response_code(405);
    echo json_encode(['error' => 'Method not allowed']);
    exit;
}

$input = json_decode(file_get_contents('php://input'), true);

if (!$input || empty($input['name']) || empty($input['email']) || empty($input['organization'])) {
    http_response_code(400);
    echo json_encode(['error' => 'Missing required fields']);
    exit;
}

// Validate email
if (!filter_var($input['email'], FILTER_VALIDATE_EMAIL)) {
    http_response_code(400);
    echo json_encode(['error' => 'Invalid email address']);
    exit;
}

// Sanitize
$name = htmlspecialchars(strip_tags($input['name']));
$email = htmlspecialchars(strip_tags($input['email']));
$org = htmlspecialchars(strip_tags($input['organization']));
$programs = htmlspecialchars(strip_tags($input['programs'] ?? ''));
$timestamp = date('Y-m-d H:i:s');

// Store to CSV
$csv_file = __DIR__ . '/../data/waitlist.csv';
$dir = dirname($csv_file);
if (!is_dir($dir)) { mkdir($dir, 0755, true); }

// Check for duplicate email
if (file_exists($csv_file)) {
    $existing = file_get_contents($csv_file);
    if (stripos($existing, $email) !== false) {
        http_response_code(409);
        echo json_encode(['message' => 'This email is already on the waitlist!']);
        exit;
    }
}

// Write header if new file
if (!file_exists($csv_file)) {
    file_put_contents($csv_file, "timestamp,name,email,organization,programs\n");
}

// Append entry
$line = sprintf(
    '"%s","%s","%s","%s","%s"' . "\n",
    $timestamp,
    str_replace('"', '""', $name),
    str_replace('"', '""', $email),
    str_replace('"', '""', $org),
    str_replace('"', '""', $programs)
);
file_put_contents($csv_file, $line, FILE_APPEND | LOCK_EX);

// Send notification email (optional — configure your email)
$to = 'ybema@sustainovate.com';
$subject = "Callio Waitlist: $name ($org)";
$body = "New waitlist signup:\n\nName: $name\nEmail: $email\nOrganisation: $org\nFunding programmes: $programs\nTime: $timestamp";
@mail($to, $subject, $body, "From: noreply@sustainovate.com");

echo json_encode(['success' => true, 'message' => 'Welcome to the waitlist!']);
