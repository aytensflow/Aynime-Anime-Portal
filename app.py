from flask import Flask, render_template, request, redirect, url_for, session, flash
import requests
from werkzeug.security import generate_password_hash, check_password_hash
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField
from wtforms.validators import InputRequired, Length, Email, EqualTo

app = Flask(__name__)
app.secret_key = "your_secret_key_here"  # Needed for sessions later

# ----------------------------
# In-memory user storage
# ----------------------------
users = {}

# ----------------------------
# Flask-WTF forms
# ----------------------------
class SignupForm(FlaskForm):
    username = StringField('Username', validators=[InputRequired(), Length(min=3, max=20)])
    email = StringField('Email', validators=[InputRequired(), Email()])
    password = PasswordField('Password', validators=[InputRequired(), Length(min=6)])
    confirm_password = PasswordField('Confirm Password', validators=[InputRequired(), EqualTo('password')])
    submit = SubmitField('Sign Up')

class LoginForm(FlaskForm):
    email = StringField('Email', validators=[InputRequired(), Email()])
    password = PasswordField('Password', validators=[InputRequired()])
    submit = SubmitField('Login')

# ----------------------------
# Home page: list top anime with search, alphabetical order, pagination
# ----------------------------
@app.route("/")
def home():
    page = request.args.get('page', 1, type=int)
    query = request.args.get('query', "")

    # Fetch top anime from Jikan API
    url = f"https://api.jikan.moe/v4/top/anime?page={page}"
    response = requests.get(url)
    data = response.json()

    anime_list = []
    for anime in data['data']:
        title = anime['title']
        if query.lower() in title.lower():  # filter by search query
            anime_list.append({
                'title': title,
                'image': anime['images']['jpg']['image_url'] if 'images' in anime else None,
                'mal_id': anime['mal_id']
            })

    # Sort alphabetically
    anime_list.sort(key=lambda x: x['title'])

    # Pagination
    has_next = len(data['data']) > 0
    next_page = page + 1
    prev_page = page - 1 if page > 1 else None

    return render_template(
        "index.html",
        anime_list=anime_list,
        next_page=next_page,
        prev_page=prev_page,
        query=query
    )

# ----------------------------
# Anime detail page
# ----------------------------
@app.route("/anime/<int:mal_id>")
def anime_page(mal_id):
    url = f"https://api.jikan.moe/v4/anime/{mal_id}/full"
    response = requests.get(url)
    data = response.json()
    anime = data['data']

    # Fix trailer URL for embedding
    trailer_url = None
    if anime.get('trailer') and anime['trailer'].get('url'):
        original = anime['trailer']['url']
        if "youtube.com/watch?v=" in original:
            video_id = original.split("watch?v=")[1]
            trailer_url = f"https://www.youtube.com/embed/{video_id}"
        else:
            trailer_url = original

    # Clean synopsis
    raw_synopsis = anime['synopsis'] or "No synopsis available"
    clean_synopsis = raw_synopsis.replace("[Written by MAL Rewrite]", "")

    # Get user's current status for this anime
    status = None
    if "user" in session:
        current_user_email = next((email for email, u in users.items() if u["username"] == session["user"]), None)
        if current_user_email and mal_id in users[current_user_email].get("my_list", {}):
            status = users[current_user_email]["my_list"][mal_id]

    anime_details = {
        'title': anime['title'],
        'image': anime['images']['jpg']['image_url'] if 'images' in anime else None,
        'synopsis': clean_synopsis,
        'episodes': anime['episodes'] or "Unknown",
        'trailer': trailer_url,
        'mal_id': mal_id,
        'status': status
    }

    return render_template("anime.html", anime=anime_details)

# ----------------------------
# Add anime to user's list
# ----------------------------
@app.route("/add_to_list/<int:mal_id>")
def add_to_list(mal_id):
    if "user" not in session:
        flash("You must be logged in to add anime to your list.", "danger")
        return redirect(url_for("login"))

    status = request.args.get("status")
    if status not in ["Watching", "Dropped", "Plan to Watch", "Completed"]:
        flash("Invalid status.", "danger")
        return redirect(request.referrer or url_for("home"))

    current_user_email = next((email for email, u in users.items() if u["username"] == session["user"]), None)
    if current_user_email is None:
        flash("User not found.", "danger")
        return redirect(url_for("home"))

    if "my_list" not in users[current_user_email]:
        users[current_user_email]["my_list"] = {}

    users[current_user_email]["my_list"][mal_id] = status
    flash(f"Anime added to your list as '{status}'.", "success")
    return redirect(request.referrer or url_for("anime_page", mal_id=mal_id))

# ----------------------------
# My List page
# ----------------------------
@app.route("/my_list")
def my_list():
    if "user" not in session:
        flash("You must be logged in to see your list.", "danger")
        return redirect(url_for("login"))

    current_user_email = next((email for email, u in users.items() if u["username"] == session["user"]), None)
    if current_user_email is None:
        flash("User not found.", "danger")
        return redirect(url_for("home"))

    my_list_ids = users[current_user_email].get("my_list", {})
    anime_list = []

    for mal_id, status in my_list_ids.items():
        url = f"https://api.jikan.moe/v4/anime/{mal_id}"
        response = requests.get(url)
        if response.status_code == 200:
            data = response.json()["data"]
            # Convert dicts to objects so Jinja can use dot notation
            class AnimeObj:
                def __init__(self, mal_id, title, image, status):
                    self.mal_id = mal_id
                    self.title = title
                    self.image = image
                    self.status = status

            anime_list.append(AnimeObj(
                mal_id=mal_id,
                title=data["title"],
                image=data["images"]["jpg"]["image_url"] if "images" in data else None,
                status=status
            ))

    return render_template("my_list.html", my_list=anime_list)

# ----------------------------
# About, Contact, Credits pages
# ----------------------------
@app.route("/about")
def about():
    return render_template("about.html", profile_image=url_for("static", filename="images/pfp.png"))

@app.route("/contact")
def contact():
    return render_template("contact.html")

@app.route("/credits")
def credits():
    return render_template("credits.html")

# ----------------------------
# Signup page
# ----------------------------
@app.route("/signup", methods=["GET", "POST"])
def signup():
    form = SignupForm()
    if form.validate_on_submit():
        if form.email.data in users:
            flash("Email already registered!", "danger")
        else:
            hashed_password = generate_password_hash(form.password.data)
            users[form.email.data] = {
                "username": form.username.data,
                "email": form.email.data,
                "password": hashed_password,
                "favorites": [],
                "my_list": {}
            }
            flash("Signup successful! Please login.", "success")
            return redirect(url_for("login"))
    return render_template("signup.html", form=form)

# ----------------------------
# Login page
# ----------------------------
@app.route("/login", methods=["GET", "POST"])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        user = users.get(form.email.data)
        if user and check_password_hash(user["password"], form.password.data):
            session["user"] = user["username"]
            flash(f"Welcome {user['username']}!", "success")
            return redirect(url_for("home"))
        else:
            flash("Invalid email or password.", "danger")
    return render_template("login.html", form=form)

# ----------------------------
# Logout
# ----------------------------
@app.route("/logout")
def logout():
    session.pop("user", None)
    flash("You have been logged out.", "info")
    return redirect(url_for("home"))

# ----------------------------
# Run app
# ----------------------------
if __name__ == "__main__":
    app.run(debug=True)
