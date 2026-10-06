# Reserva — Django Booking Engine

A SaaS-ready appointment booking platform (Reserva) built with Django. Full multi-tenant B2B SaaS for service businesses (health, beauty, fitness, education, legal, auto services, IT, etc.). Supports role-based teams, flexible pricing, automated notifications, verified reviews, and a powerful admin dashboard.

## ⭐ Core Features

### 🏢 Multi-Tenant Business Management
- **Business profiles** with custom categories, branding, and descriptions
- **Employee/staff management** with optional user accounts and self-managed schedules
- **Flexible working hours**: per-day business hours + special days off
- **Business teams**: employees can be linked to user accounts for role-based access
- **Hourly capacity management** for businesses without assigned staff

### 📅 Booking & Appointment Management
- **Dual booking modes**: registered users OR guest bookings (no account required)
- **Guest access tokens** for secure appointment management without login
- **Auto-confirmation** or manual approval workflows
- **Availability slots** calculated in real-time based on employee schedules & capacity
- **Booking status tracking**: pending → confirmed → completed (or no-show/cancelled)
- **Guest contact preferences**: email, SMS, or both

### 💰 Payments & Deposits
- **Stripe integration** for secure payments
- **Configurable deposits** (% of booking price) with refund logic
- **Flexible pricing**: price locked at booking time
- **Cancellation fee handling**: configurable % retention on cancellations
- **Refund calculations** based on time-to-appointment or business policy
- **Payment status tracking**: pending, paid, refunded, partially refunded

### 🔔 Automated Notifications
- **SMS notifications** via Twilio for:
  - Booking confirmations (sent to guest/customer)
  - 24-hour reminders before appointments
  - Cancellation notices
  - Booking approvals/rejections (business owner)
  - New booking alerts (business owner)
- **Email notifications** for bookings & reviews
- **Scheduled tasks** for automated reminders & invitations

### ⭐ Review & Rating System
- **Verified reviews**: customers can only review completed bookings
- **5-star ratings** with optional comments
- **Business ratings page** showing average rating & review count
- **Review invitations** sent via SMS/email after appointment completion

### 🔐 Role-Based Access Control
- **Super Admin**: platform management, business approvals, dispute resolution
- **Professional** (Business Owner): full business dashboard, team management, booking handling
- **Employee**: self-managed schedule, availability, optional user account
- **Customer**: book appointments, manage bookings, leave reviews

### 📊 Reporting & Dispute Resolution
- **Business report system** for reporting issues (no-show, offensive behavior, fraud, etc.)
- **Report categorization** and status tracking (new → under review → resolved/dismissed)
- **Admin dashboard** for case management

### 🎨 Public Interfaces
- **Public booking pages** per business (unique URL structure)
- **Embeddable booking widget/iframe** for external websites
- **Responsive mobile-friendly design**
- **Multi-language support** (Greek/English)

## Tech Stack

- **Backend**: Django 4.2+, Python 3.10+
- **Database**: PostgreSQL (production) / SQLite (development)
- **Payments**: Stripe API
- **SMS**: Twilio API
- **Email**: Resend (transactional email)
- **Static files**: WhiteNoise
- **Server**: Gunicorn + Cloudflare (reverse proxy)
- **Async tasks**: Celery + Redis (optional, for background jobs)

## Quick start (development)

1. Clone the repo

```bash
git clone <repo-url> project
cd project
```

2. Create and activate a virtualenv (Windows example)

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

3. Install dependencies

```bash
pip install -r requirements.txt
```

4. Copy `.env` and set environment variables

```bash
copy .env .env.local
# then edit .env.local and add your keys
```

Minimum env vars (see `.env`):
- `SECRET_KEY` — Django secret
- `DEBUG` — True/False
- `ALLOWED_HOSTS` — comma separated
- `STRIPE_PUBLIC_KEY`, `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET`
- `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_PHONE_NUMBER`

5. Migrate and create superuser

```bash
.\.venv\Scripts\python.exe manage.py makemigrations
.\.venv\Scripts\python.exe manage.py migrate
.\.venv\Scripts\python.exe manage.py createsuperuser
```

6. Collect static files

```bash
.\.venv\Scripts\python.exe manage.py collectstatic --noinput
```

7. Run development server

```bash
.\.venv\Scripts\python.exe manage.py runserver 8000
# open http://127.0.0.1:8000/
```

## Stripe setup

- Set `STRIPE_SECRET_KEY` and `STRIPE_PUBLIC_KEY` in your `.env`.
- Configure `STRIPE_WEBHOOK_SECRET` for webhook verification.
- Webhook endpoint: `/payments/webhook/` (configure in Stripe dashboard).

## Twilio setup

- Set `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_PHONE_NUMBER` in `.env`.
- The project uses `notifications.utils` wrappers to send SMS.

## Scheduling background jobs

Two management commands are available and should be scheduled via cron / Windows Task Scheduler:

- `python manage.py send_reminders` — finds bookings ~24h ahead and sends SMS reminders
- `python manage.py send_review_invites` — sends review invites for bookings completed in last 24h

Example cron (every hour):

```cron
0 * * * * /path/to/venv/bin/python /path/to/project/manage.py send_reminders
0 1 * * * /path/to/venv/bin/python /path/to/project/manage.py send_review_invites
```

## Embeddable widget

Embed the booking widget with an iframe:

```html
<iframe src="https://your-domain.com/widget/<business-slug>/" width="100%" height="700" frameborder="0"></iframe>
```

Or link to the public booking page:

```
https://your-domain.com/b/<business-slug>/
```

## Guest Bookings

Guests can book without creating an account:

1. Guest completes booking (name, phone, email, contact preference)
2. Unique **access token** generated and stored
3. Confirmation HTML email sent with booking link: `/booking/<access_token>/`
4. Guest views booking details via access token (no login required)
5. Contact preference (email/phone/both) controls notification method

Best for: temporary visitors, quick bookings, low-friction UX.

## Legal & Compliance Checklist (Now vs Later)

This checklist separates what must exist on the live site now vs what must be completed before onboarding the first paying customer.

### Now (live-site minimum)

- [x] Privacy Policy page available on-site
- [x] Terms of Service page available on-site
- [x] Cookie banner/consent choice on public pages
- [x] Contact page with real support/privacy emails
- [ ] Production DEBUG handling confirmed in deployment env (`DEBUG=False` in runtime environment)

Note: Application code reads `DEBUG` from environment variables. Keep this controlled via deployment configuration.

### Before first customer (operational/legal readiness)

- [ ] Business setup with tax authority (έναρξη στην εφορία)
- [ ] EFKA registration
- [ ] Accountant engagement and tax process definition
- [ ] Invoicing flow + myDATA integration in production operations
- [ ] Full GDPR compliance pack:
    - [ ] DPA with hosting/cloud providers
    - [ ] DPA/Data terms with subprocessors (payments, email/SMS providers)
    - [ ] Internal process for data-subject requests (access/export/deletion)
    - [ ] Retention and deletion policy execution process
    - [ ] Incident/breach response workflow

Important: Items in this section are legal/operational actions and are not fully solvable through code changes alone.

## Cancellation & Refund Policy (default)

- Cancel > 48 hours before appointment: 100% refund of deposit
- Cancel 24–48 hours before: 50% refund
- Cancel < 24 hours: no refund

Refunds are processed through Stripe when applicable.

## Resetting the Database

### SQLite (development)

1. **Delete the database file** (usually `db.sqlite3` in the project root):

```bash
# Linux / macOS
rm db.sqlite3

# Windows PowerShell
Remove-Item db.sqlite3

# Windows Command Prompt
del db.sqlite3
```

2. **Delete migration files** (keep `__init__.py` in each migrations folder, remove only the numbered files `0001_*.py`, etc.):

```bash
# Linux / macOS
find . -path "*/migrations/0*.py" -delete

# Windows PowerShell
Get-ChildItem -Recurse -Path ".\*\migrations" -Filter "0*.py" | Remove-Item
```

3. **Re-create migrations and apply them**:

```bash
.\.venv\Scripts\python.exe manage.py makemigrations
.\.venv\Scripts\python.exe manage.py migrate
```

4. **Re-create the Super Admin account** (see section below).

---

### PostgreSQL (production)

1. Drop and re-create the database:

```sql
DROP DATABASE reserva_db;
CREATE DATABASE reserva_db OWNER reserva_user;
```

2. Run migrations:

```bash
python manage.py migrate
```

3. Re-create the Super Admin account (see section below).

---

## Creating the Super Admin Account

The Super Admin is a custom account (role `super_admin`) that approves businesses in the `/superadmin/` panel.

Run the following management command to create a superuser and then set its role:

```bash
# Step 1: create the Django superuser
python manage.py createsuperuser
# Enter username, email and password when prompted

# Step 2: open the Django shell and promote the account to super_admin role
python manage.py shell
```

Inside the shell:

```python
from accounts.models import CustomUser
u = CustomUser.objects.get(username='your_admin_username')
u.role = 'super_admin'
u.is_staff = True
u.is_superuser = True
u.save()
print("Done —", u)
exit()
```

After this the account can log in at `/superadmin/` and approve professionals, view reports, and manage the platform.

> **Tip:** keep the admin credentials in a secure secrets manager (e.g. AWS Secrets Manager, Vault, or a `.env` file that is **not** committed to version control).



## Tests

There are no automated tests included yet. Recommended next steps:

- Add unit tests for availability logic (`bookings.utils`) and booking/cancellation flows
- Add integration tests for the public booking AJAX endpoints

## 🚀 Production Deployment & Hosting (€~10/month)

### Current Setup
- **Domain**: Custom domain with Cloudflare reverse proxy (excellent choice!)
- **Current limit**: 10 businesses at launch
- **Expected daily users**: Multiple businesses with staff + daily customer bookings
- **Database**: PostgreSQL recommended (replace SQLite in production)

### Recommended Hosting Stack for Greece (Budget: ~€10/month)

#### **Option 1: Hetzner Cloud (RECOMMENDED) — €5–9/month**
Best for: European hosting from Greece, good performance, reliable

- **VM**: 2 CPU, 4GB RAM VPS (€4.99/month)
- **Managed Database**: PostgreSQL (€4.99/month) — *OR use self-managed on VM*
- **Total**: ~€5–10/month for both

**Setup:**
```bash
# 1. SSH into your Hetzner VM (Ubuntu 22.04 LTS)
ssh root@your-ip

# 2. Install dependencies
apt update && apt upgrade -y
apt install python3-pip python3-venv postgresql nginx gunicorn -y

# 3. Clone your project
git clone your-repo-url /var/www/reserva
cd /var/www/reserva

# 4. Virtual environment
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 5. Configure .env
# Copy your .env with Stripe, Twilio, Django secrets
nano .env

# 6. Migrate
python manage.py migrate
python manage.py collectstatic --noinput

# 7. Create systemd service
sudo nano /etc/systemd/system/reserva.service
```

**Systemd service file** (`/etc/systemd/system/reserva.service`):
```ini
[Unit]
Description=Reserva Django App
After=network.target

[Service]
Type=notify
User=www-data
WorkingDirectory=/var/www/reserva
ExecStart=/var/www/reserva/venv/bin/gunicorn erantevou.wsgi:application --bind 0.0.0.0:8000 --workers 4
Restart=always

[Install]
WantedBy=multi-user.target
```

**Nginx reverse proxy** (`/etc/nginx/sites-available/reserva`):
```nginx
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location /static/ {
        alias /var/www/reserva/staticfiles/;
    }
}
```

**Enable & start:**
```bash
sudo systemctl enable reserva
sudo systemctl start reserva
sudo systemctl enable nginx
sudo systemctl restart nginx
```

---

#### **Option 2: Contabo — €4–8/month**
- European hosting (Germany), very cheap VPS
- Same setup as Hetzner above

---

#### **Option 3: Render.com or Railway.app — €7–15/month**
- Simpler deployment (Heroku-style, no SSH needed)
- PostgreSQL included
- Good for beginners
- **Render.com setup**: Push to GitHub → auto-deploys

---

### Scaling for 10+ Businesses (Current Launch)

**Your current load:**
- ~10 businesses
- ~50–500 daily bookings (varies)
- SMS/email notifications
- Stripe payments

**This VPS setup handles:**
- ✅ 50–100 concurrent users
- ✅ 10,000+ daily requests
- ✅ Automated SMS reminders via scheduled tasks

**When to upgrade (beyond 10 businesses):**
- 100+ businesses → Add Redis cache + Celery workers
- 1000+ daily bookings → Upgrade to higher-tier VM (€15–25/month)
- High SMS volume → Consider Twilio message queuing

---

### Environment Variables for Production

Create `.env` file on your server:

```env
SECRET_KEY=your-very-long-random-secret-here
DEBUG=False
ALLOWED_HOSTS=your-domain.com,www.your-domain.com

# Database (PostgreSQL)
DATABASE_URL=postgresql://user:password@localhost:5432/reserva

# Stripe
STRIPE_PUBLIC_KEY=pk_live_...
STRIPE_SECRET_KEY=sk_live_...
STRIPE_WEBHOOK_SECRET=whsec_...

# Twilio
TWILIO_ACCOUNT_SID=ACxxxxx
TWILIO_AUTH_TOKEN=your_token
TWILIO_PHONE_NUMBER=+30XXXXXXXXX

# Django security
SECURE_SSL_REDIRECT=True
SESSION_COOKIE_SECURE=True
CSRF_COOKIE_SECURE=True
```

---

### Cloudflare Configuration (Already Used ✓)

1. **DNS**: Point your domain to Hetzner/Contabo IP
2. **SSL**: Cloudflare "Flexible SSL" (or "Full") for free HTTPS
3. **Caching**: Cache static files (CSS, JS, images)
4. **Security**: Enable DDoS protection, rate limiting

---

### Scheduled Tasks (SMS Reminders, Reviews)

Use **crontab** to run management commands hourly:

```bash
# Edit crontab
crontab -e

# Add:
0 * * * * cd /var/www/reserva && /var/www/reserva/venv/bin/python manage.py send_reminders
0 1 * * * cd /var/www/reserva && /var/www/reserva/venv/bin/python manage.py send_review_invites
```

---

### Monitoring & Logging

Monitor your app with free tools:
- **Logs**: Use `journalctl -u reserva -f` to tail logs
- **Uptime**: UptimeRobot.com (free monitoring)
- **Performance**: Check Hetzner/Contabo dashboard

---

### Backup Strategy

PostgreSQL backups (daily):
```bash
# Create backup script
sudo nano /usr/local/bin/backup-db.sh
```

```bash
#!/bin/bash
BACKUP_DIR="/var/backups/reserva"
DATE=$(date +%Y%m%d_%H%M%S)
pg_dump -U reserva_user reserva_db > $BACKUP_DIR/reserva_$DATE.sql
# Upload to cloud (S3, Google Cloud, etc.) for safety
```

Add to crontab: `0 2 * * * /usr/local/bin/backup-db.sh`

## 📁 Project Structure

```
reserva/
├── accounts/          # User authentication, roles (super_admin, professional, customer, employee)
├── businesses/        # Business profiles, employees, services, working hours
├── bookings/          # Appointments, availability slots, guest bookings
├── payments/          # Stripe integration, refunds, payment tracking
├── notifications/     # SMS/email notifications, scheduled tasks
├── reviews/           # Verified reviews, ratings
├── reports/           # Dispute resolution, issue reports
├── erantevou/         # Django settings, URLs, middleware
├── templates/         # HTML templates (business pages, admin, customer portal)
├── static/            # CSS, JS, images
├── manage.py          # Django management
├── requirements.txt   # Python dependencies
└── README.md          # This file
```

## 🔧 Management Commands

```bash
# Send 24h SMS reminders for upcoming bookings
python manage.py send_reminders

# Send review invitations for completed bookings
python manage.py send_review_invites
```

## 📋 Key Models

| Model | Purpose |
|-------|---------|
| `CustomUser` | Extended Django User (roles, phone) |
| `Business` | Business profile owned by Professional |
| `Employee` | Staff member, can have user account |
| `Service` | Appointment service (price, duration) |
| `Booking` | Appointment record |
| `Payment` | Stripe payment linked to booking |
| `SMSNotification` | SMS log (confirmations, reminders, etc.) |
| `Review` | Verified 5-star rating + comment |
| `BusinessReport` | Issue report for dispute resolution |

---

## 🚨 Important Notes

- **Guest bookings do NOT require registration** — perfect for high-conversion public sites
- **Prices are locked at booking time** — changes to service prices don't affect past bookings
- **Availability slots calculated dynamically** — considers employee schedules, business hours, existing bookings
- **Stripe deposits** — fully refundable based on cancellation policy
- **SMS notifications in Greek** — all messages are in Greek (customizable)
- **Multi-language UI** — templates support Greek/English switching
- **Employee accounts optional** — businesses without staff use hourly capacity instead

---

## 🏥 Support / Issues

For bugs and feature requests, contact the development team or open an issue.

---

## 📜 License

[Specify your license here — MIT, GPL, Proprietary, etc.]
- `bookings/` — booking models, availability, public views
- `payments/` — Stripe integration
- `reviews/` — review model + views
- `notifications/` — Twilio SMS + management commands
- `templates/`, `static/` — frontend

## Useful commands

```bash
# Run dev server
.\.venv\Scripts\python.exe manage.py runserver

# Make migrations
.\.venv\Scripts\python.exe manage.py makemigrations
.\.venv\Scripts\python.exe manage.py migrate

# Create superuser
.\.venv\Scripts\python.exe manage.py createsuperuser

# Collect static
.\.venv\Scripts\python.exe manage.py collectstatic --noinput
```

## Contact

Project owner: [`aloualou56`](https://github.com/aloualou56). Please open an issue for questions or bug reports.

## License

Released under the MIT License — see [LICENSE](LICENSE).
