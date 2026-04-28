# OpenSky Engineering Portal

CWK2 for module 5COSC021W (Software Development Group Project).
Django + SQLite + Bootstrap + JavaScript.

The database schema in [`db_creator.sql`](db_creator.sql) is mirrored in
`portal/models.py` at column and constraint level. 

---

## Run the app (fresh clone)

1. Clone and enter the repo.
   ```bash
   git clone https://github.com/c0r73x-v01d/opensky-engineering-portal.git
   cd opensky_project
   ```

2. Create a virtual environment and install dependencies.
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate        # Windows: .venv\Scripts\activate
   pip install -r requirements.txt
   ```

3. Build the database.
   ```bash
   python manage.py makemigrations portal
   python manage.py migrate
   ```

4. (Optional) Populate demo data.
   ```bash
   python manage.py seed_demo
   ```
   Seeded accounts all use the password **`sky-demo-2026`**. Sample
   usernames are printed at the end of the command.

5. (Optional) Create an admin login.
   ```bash
   python manage.py createsuperuser
   ```

6. Start the server.
   ```bash
   python manage.py runserver
   ```
   Open <http://localhost:8000/login/>.

Run the test suite any time with:
```bash
python manage.py test portal
```

---

## How to implement your slice

Each menu (Teams, Messages, Organisation, Department, Reports) currently
routes to a placeholder page. To convert your slice into a working one,
follow the same four-file pattern used by Schedule.

### 1. Add a form in `portal/forms.py`

Extend `ModelForm` from the model you own. Add a `clean()` method for any
application-layer invariant (the schema comments in `db_creator.sql` list
them — for example, a team must have at least 5 engineers).

### 2. Write your views in `portal/views.py`

Put them in their own section (see the `=== SCHEDULE ===` banner for an
example). Decorate with `@login_required`. Use `get_object_or_404`,
`select_related`, and the `Q` object for search. When the request succeeds
write an `Action` audit row and, for notifications, create a `Notification`
plus `NotificationRecipient` entries. Wrap multi-step writes in
`transaction.atomic()`.

### 3. Add routes in `portal/urls.py`

Group them under a comment banner for your slice. Follow the same style
as Schedule's sub-routes: list view, detail view, create (GET + POST),
edit (POST), delete/cancel (POST), and any state transitions (RSVP, star,
send).

### 4. Wire the template

- Replace the placeholder view with a `render(request, 'your_slice.html', ctx)`.
- Build `your_slice.html` as `{% extends "base.html" %}`.
- Use the existing design tokens from `portal/static/css/sky-base.css`
  (classes beginning with `sky-`).
- Reach for `portal/static/icons/sky-icons.js` for inline SVGs.
- If you need interactivity add a file under `portal/static/js/`.

### 5. Register for admin

In `portal/admin.py`, each of your models is already registered. Adjust
`list_display`, `list_filter`, `search_fields`, and inlines so
administrators can manage the data without leaving `/admin/`.

### 6. Write tests

Create `portal/tests/test_<slice>.py` mirroring
[`portal/tests/test_schedule.py`](portal/tests/test_schedule.py): model
validation tests, form tests, and view tests (including auth gates).
Run `python manage.py test portal`.

### 7. Commit and push daily

Make small atomic commits. Pull before you push. If you touch a file
outside your slice (e.g. `models.py`), tell the group first.

---

## Layout

```
opensky/                Django project (settings, URL conf)
portal/
  models.py             all 21 tables from db_creator.sql
  forms.py              auth + schedule forms (add yours here)
  admin.py              every model registered
  views.py              auth + schedule (add your section here)
  urls.py               routes (add yours under a banner)
  context_processors.py navbar notification feed
  management/commands/seed_demo.py
  static/
    css/sky-base.css
    icons/sky-icons.js
    js/login.js
    js/schedule.js      (add js/<slice>.js here)
  templates/
    base.html           navbar shell
    base_auth.html      auth pages
    login.html
    schedule.html
    schedule_form.html
    coming_soon.html    placeholder for unimplemented slices
  tests/test_schedule.py
```

---

## Useful URLs

| Route | What |
|---|---|
| `/login/` | Sign in |
| `/register/` | Self-register |
| `/accounts/password_reset/` | Password reset (emails print to terminal) |
| `/schedule/` | Schedule page (fully operational) |
| `/admin/` | Django admin — every model is editable |
