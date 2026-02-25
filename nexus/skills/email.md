---
name: email
description: Manage email from the terminal via IMAP/SMTP using himalaya CLI
requires: [himalaya]
install: brew install himalaya && himalaya account configure
---

# Email Skill

Use `himalaya` CLI instead of navigating Mail.app or Gmail in a browser.
Himalaya connects directly to your IMAP/SMTP server — fast, structured, scriptable.

## When to use

- List, read, search, reply, forward, compose, delete emails
- Check inbox quickly without opening a browser
- Automated email workflows (search + reply)
- Manage multiple accounts from one tool

## When NOT to use

- Rich HTML email composition with inline images (use browser)
- OAuth-only providers without app passwords (some Gmail configs — though himalaya supports OAuth2)

## Safety

Actions that contact other people — ALWAYS draft in chat first, let the user review:

- `himalaya template send` — sends an email. NEVER run without showing the full draft first.
- `himalaya message reply` / `reply --all` — sends a reply. Show the draft first.
- `himalaya message forward` — forwards to someone. Show the draft first.
- `himalaya message delete` — permanent. Confirm with user first.

Safe to run freely (read-only):
- `envelope list`, `message read`, `folder list`, `attachment download`, `account list`

## Setup

```bash
himalaya account configure    # interactive wizard
# Or manual: ~/.config/himalaya/config.toml
```

### Minimal IMAP + SMTP config

```toml
[accounts.personal]
email = "you@example.com"
display-name = "Your Name"
default = true

backend.type = "imap"
backend.host = "imap.example.com"
backend.port = 993
backend.encryption.type = "tls"
backend.login = "you@example.com"
backend.auth.type = "password"
backend.auth.cmd = "security find-generic-password -s himalaya -w"

message.send.backend.type = "smtp"
message.send.backend.host = "smtp.example.com"
message.send.backend.port = 587
message.send.backend.encryption.type = "start-tls"
message.send.backend.login = "you@example.com"
message.send.backend.auth.type = "password"
message.send.backend.auth.cmd = "security find-generic-password -s himalaya-smtp -w"
```

### Password options

```toml
# macOS Keychain (recommended)
backend.auth.type = "password"
backend.auth.cmd = "security find-generic-password -s himalaya -w"

# Raw password (testing only — NOT recommended)
backend.auth.type = "password"
backend.auth.raw = "your-password"

# System keyring
backend.auth.keyring = "imap-example"
```

Store a password in macOS Keychain:
```bash
security add-generic-password -s himalaya -a you@email.com -w "your-password"
security add-generic-password -s himalaya-smtp -a you@email.com -w "your-password"
```

### Gmail

```toml
[accounts.gmail]
email = "you@gmail.com"
display-name = "Your Name"
default = true

backend.type = "imap"
backend.host = "imap.gmail.com"
backend.port = 993
backend.encryption.type = "tls"
backend.login = "you@gmail.com"
backend.auth.type = "password"
backend.auth.cmd = "security find-generic-password -s himalaya-gmail -w"

message.send.backend.type = "smtp"
message.send.backend.host = "smtp.gmail.com"
message.send.backend.port = 587
message.send.backend.encryption.type = "start-tls"
message.send.backend.login = "you@gmail.com"
message.send.backend.auth.type = "password"
message.send.backend.auth.cmd = "security find-generic-password -s himalaya-gmail -w"
```

Gmail requires an App Password if 2FA is enabled.

### iCloud

```toml
[accounts.icloud]
email = "you@icloud.com"
display-name = "Your Name"

backend.type = "imap"
backend.host = "imap.mail.me.com"
backend.port = 993
backend.encryption.type = "tls"
backend.login = "you@icloud.com"
backend.auth.type = "password"
backend.auth.cmd = "security find-generic-password -s himalaya-icloud -w"

message.send.backend.type = "smtp"
message.send.backend.host = "smtp.mail.me.com"
message.send.backend.port = 587
message.send.backend.encryption.type = "start-tls"
message.send.backend.login = "you@icloud.com"
message.send.backend.auth.type = "password"
message.send.backend.auth.cmd = "security find-generic-password -s himalaya-icloud -w"
```

Generate an app-specific password at appleid.apple.com.

### OAuth2 (for providers that support it)

```toml
backend.auth.type = "oauth2"
backend.auth.client-id = "your-client-id"
backend.auth.client-secret.cmd = "security find-generic-password -s himalaya-oauth-secret -w"
backend.auth.access-token.cmd = "security find-generic-password -s himalaya-oauth-access -w"
backend.auth.refresh-token.cmd = "security find-generic-password -s himalaya-oauth-refresh -w"
backend.auth.auth-url = "https://provider.com/oauth/authorize"
backend.auth.token-url = "https://provider.com/oauth/token"
```

### Folder aliases

```toml
[accounts.personal.folder.alias]
inbox = "INBOX"
sent = "Sent"
drafts = "Drafts"
trash = "Trash"
```

## List & Read

```bash
himalaya envelope list                        # inbox
himalaya envelope list --folder "Sent"        # specific folder
himalaya envelope list --page 1 --page-size 20
himalaya message read 42                      # read by ID
himalaya message export 42 --full             # raw MIME
himalaya folder list                          # list all folders
```

## Search

```bash
himalaya envelope list from john@example.com subject meeting
himalaya envelope list --output json | jq     # structured output
```

## Compose & Reply

```bash
# Send directly (no editor)
cat << 'EOF' | himalaya template send
From: you@example.com
To: recipient@example.com
Subject: Quick note

Hello from the terminal!
EOF

# Prefill headers from CLI
himalaya message write \
  -H "To:recipient@example.com" \
  -H "Subject:Quick Message" \
  "Message body here"

# Reply
himalaya message reply 42

# Reply all
himalaya message reply 42 --all

# Forward
himalaya message forward 42
```

### Attachments in composed emails (MML syntax)

```
From: you@example.com
To: recipient@example.com
Subject: With attachment

Here is the document.

<#part filename=/path/to/document.pdf><#/part>
```

Multiple attachments:
```
<#part filename=/path/to/doc1.pdf><#/part>
<#part filename=/path/to/doc2.pdf><#/part>
```

HTML + plain text alternative:
```
<#multipart type=alternative>
Plain text version here.
<#part type=text/html>
<html><body><h1>HTML version</h1></body></html>
<#/multipart>
```

## Organize

```bash
himalaya message move 42 "Archive"
himalaya message copy 42 "Important"
himalaya message delete 42
himalaya flag add 42 --flag seen
himalaya flag remove 42 --flag seen
```

## Attachments

```bash
himalaya attachment download 42
himalaya attachment download 42 --dir ~/Downloads
```

## Multiple Accounts

```bash
himalaya account list
himalaya --account work envelope list
```

## Debugging

```bash
RUST_LOG=debug himalaya envelope list
RUST_LOG=trace RUST_BACKTRACE=1 himalaya envelope list
```

## Common IMAP/SMTP Ports

| Protocol | Port | Encryption |
|----------|------|------------|
| IMAP     | 993  | TLS        |
| IMAP     | 143  | STARTTLS   |
| SMTP     | 587  | STARTTLS   |
| SMTP     | 465  | TLS        |

## Tips

- Use `--output json` for structured output (pipe to jq)
- Message IDs are relative to current folder — re-list after folder changes
- Store passwords in macOS Keychain (see password options above)
- Set `$EDITOR` for interactive compose (`export EDITOR="vim"`)
- MML `<#part>` tags compile to proper MIME when sending
