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

## When NOT to use

- Rich HTML email composition (use browser)
- OAuth-only providers without app passwords (some Gmail configs)

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

Manual config example:
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

## List & Read

```bash
himalaya envelope list                        # inbox
himalaya envelope list --folder "Sent"        # specific folder
himalaya envelope list --page 1 --page-size 20
himalaya message read 42                      # read by ID
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

# Reply
himalaya message reply 42

# Reply all
himalaya message reply 42 --all

# Forward
himalaya message forward 42
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

## Tips

- Use `--output json` for structured output (pipe to jq)
- Message IDs are relative to current folder
- Store passwords in macOS Keychain: `security add-generic-password -s himalaya -a you@email.com -w`
