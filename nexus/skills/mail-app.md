---
name: mail-app
description: Add and configure email accounts in macOS Mail.app — IMAP/SMTP setup wizard, server settings, troubleshooting
requires: []
---

# Mail.app Account Setup Skill

Add IMAP/SMTP email accounts to macOS Mail.app via GUI. This covers the "Other Mail Account" wizard (for custom/company IMAP), not the auto-configured providers (iCloud, Gmail, Yahoo — those are one-click).

## When to use

- Setting up a company/custom IMAP email account on macOS
- User needs Mail.app configured (not just CLI access via himalaya)
- Account requires manual server entry (auto-detection will fail for most custom domains)

## When NOT to use

- iCloud, Gmail, Outlook, Yahoo — these auto-configure, just select the provider
- User only needs to read/send email — use the `email` skill (himalaya CLI) instead
- Bulk account setup — use `.mobileconfig` profiles (see below)

## The Add Account Wizard

### Screen 1: Choose provider

```
Mail > Add Account
```

A dialog lists providers: iCloud, Microsoft Exchange, Google, Yahoo, AOL.
At the bottom: **"Other Mail Account..."** — click this, then **Continue**.

With Nexus:
```
do("click Mail > Add Account")
see()                                    # find "Other Mail Account"
do("click Other Mail Account")
do("click Continue")
```

### Screen 2: Basic credentials (3 fields)

Dialog title: **"Add a Mail Account"**

| Field | AX Role | What to enter |
|-------|---------|---------------|
| Name | text field | Display name for outgoing mail |
| Email Address | text field | Full email address |
| Password | secure text field | Email password |

Then click **Sign In**.

With Nexus:
```
do("fill Name=Ferran, Email Address=user@company.com, Password=secret")
do("click Sign In")
```

### Screen 3: Auto-detection failure (expected)

For custom/company domains, Mail.app will show:
> **"Unable to verify account name or password"**

This is normal — it means auto-detection failed and manual entry is needed. The dialog now shows additional fields. Do NOT click Cancel.

### Screen 4: Manual server configuration

The dialog expands with these fields:

| Field | AX Role | Example |
|-------|---------|---------|
| Account Type | popup button | **IMAP** (select this, not POP) |
| Incoming Mail Server | text field | `imap.company.com` |
| Outgoing Mail Server | text field | `smtp.company.com` |

The Email Address, User Name, and Password fields from screen 2 remain visible and editable.

With Nexus:
```
do("click Account Type")                 # opens popup
do("click IMAP")                         # select IMAP
do("type imap.company.com in Incoming Mail Server")
do("type smtp.company.com in Outgoing Mail Server")
do("click Sign In")
```

### Screen 5: Select apps to sync

After successful sign-in, a checkbox screen appears:

| Checkbox | Default |
|----------|---------|
| Mail | checked |
| Notes | checked |

Uncheck Notes unless needed, then click **Done**.

With Nexus:
```
do("click Notes")                        # uncheck it
do("click Done")
```

### Screen 6: Privacy prompt (macOS Sequoia+)

May show: **"Protect Mail Activity"** or **"Don't protect Mail activity"**.

```
do("click Protect Mail Activity")
do("click Continue")
```

## Post-Setup: Fix Port/TLS Settings

Mail.app often defaults to auto-managed connection settings. For company IMAP, you usually need to set explicit ports and TLS.

Navigate to server settings:
```
Mail > Settings > Accounts > [account name] > Server Settings
```

With Nexus:
```
do("click Mail > Settings")
do("click Accounts")
do("click the account name")             # or use see(query="account name")
do("click Server Settings")
```

### Incoming Mail Server (IMAP)

| Setting | Where | Value |
|---------|-------|-------|
| Automatically manage connection settings | checkbox — **uncheck** | off |
| Port | text field (appears after uncheck) | 993 |
| Use TLS/SSL | checkbox | on |
| Authentication | popup button | Password |

With Nexus:
```
do("click Automatically manage connection settings")   # uncheck
do("type 993 in Port")
do("click Use TLS/SSL")                                # check
```

### Outgoing Mail Server (SMTP)

Same pattern — uncheck auto-manage, then:

| Setting | Value |
|---------|-------|
| Port | 587 (STARTTLS) or 465 (TLS) |
| Use TLS/SSL | on |
| Authentication | Password |

Click **Save** when done.

### Advanced IMAP Settings

Click **Advanced** button under incoming server:
- **IMAP Path Prefix**: set to `INBOX` (all caps) if folders don't appear
- **TLS Certificate**: shows certificate chain for verification
- **Allow insecure authentication**: leave OFF

## Alternative: System Settings > Internet Accounts

Another path to the same wizard:

```bash
open "x-apple.systempreferences:com.apple.Internet-Accounts-Settings.extension"
```

Or via GUI:
```
do("open System Settings")
do("click Internet Accounts")            # in sidebar
do("click Add Account")
do("click Other Mail Account")           # same wizard from here
```

## Alternative: .mobileconfig Profile (skip GUI entirely)

For automated/scripted setup, create a `.mobileconfig` XML profile:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>PayloadContent</key>
    <array>
        <dict>
            <key>EmailAccountType</key>
            <string>EmailTypeIMAP</string>
            <key>EmailAddress</key>
            <string>user@company.com</string>
            <key>IncomingMailServerHostName</key>
            <string>imap.company.com</string>
            <key>IncomingMailServerPortNumber</key>
            <integer>993</integer>
            <key>IncomingMailServerUseSSL</key>
            <true/>
            <key>IncomingMailServerUsername</key>
            <string>user@company.com</string>
            <key>OutgoingMailServerHostName</key>
            <string>smtp.company.com</string>
            <key>OutgoingMailServerPortNumber</key>
            <integer>587</integer>
            <key>OutgoingMailServerUseSSL</key>
            <true/>
            <key>OutgoingMailServerUsername</key>
            <string>user@company.com</string>
            <key>OutgoingPasswordSameAsIncomingPassword</key>
            <true/>
            <key>PayloadType</key>
            <string>com.apple.mail.managed</string>
            <key>PayloadIdentifier</key>
            <string>com.company.email</string>
            <key>PayloadUUID</key>
            <string>GENERATE-A-UUID-HERE</string>
            <key>PayloadVersion</key>
            <integer>1</integer>
        </dict>
    </array>
    <key>PayloadDisplayName</key>
    <string>Company Email</string>
    <key>PayloadIdentifier</key>
    <string>com.company.email.profile</string>
    <key>PayloadType</key>
    <string>Configuration</string>
    <key>PayloadUUID</key>
    <string>GENERATE-A-UUID-HERE</string>
    <key>PayloadVersion</key>
    <integer>1</integer>
</dict>
</plist>
```

Install with:
```bash
open /path/to/email-profile.mobileconfig
```

This opens System Settings > Profiles, user clicks **Install** and enters their password. No wizard navigation needed.

## Certificate Trust Dialogs

Company IMAP servers with self-signed or internal CA certs will trigger a trust dialog:
- **"The identity of mail.company.com cannot be verified"**
- Buttons: **Continue** / **Cancel** / **Show Certificate**
- This is a system dialog — Nexus detects it via system dialog detection

```
do("click Continue")                     # trust the certificate
```

## Troubleshooting

| Problem | Fix |
|---------|-----|
| "Unable to verify" on sign-in | Expected for custom domains — fill in server fields manually |
| Folders not showing | Set IMAP Path Prefix to `INBOX` in Advanced settings |
| Sent mail not syncing | Check SMTP settings, ensure port 587 + TLS |
| Connection timeout | Verify port (993/587), check firewall, try without VPN |
| Certificate error | Click Continue to trust, or install CA cert first |
| Authentication failed | Verify username (often full email), check password, check if app password needed |

## Common IMAP/SMTP Ports

| Protocol | Port | Encryption | Notes |
|----------|------|------------|-------|
| IMAP | 993 | TLS/SSL | Standard, preferred |
| IMAP | 143 | STARTTLS | Legacy, some providers |
| SMTP | 587 | STARTTLS | Standard submission |
| SMTP | 465 | TLS/SSL | Alternative |

## AX Tree Tips

- Mail.app is native AppKit/SwiftUI — good accessibility tree
- The Add Account wizard is a modal sheet (AXSheet)
- Fields have clear labels: "Name", "Email Address", "Password"
- "Account Type" is an AXPopUpButton
- Server fields appear dynamically after auto-detection fails
- Settings window: AXWindow with tab-based navigation (Accounts, Composing, etc.)
- Use `see(query="Server Settings")` to find the right tab
