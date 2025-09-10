from flask import Flask, render_template, request
import requests

app = Flask(__name__)
app.secret_key = "your_secret_key_here"  # Needed for sessions later

# Home page: list top anime with search, alphabetical order, pagination
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


# Anime detail page
@app.route("/anime/<int:mal_id>")
def anime_page(mal_id):
    # Fetch anime details from Jikan API
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

    # Extract needed info
    anime_details = {
        'title': anime['title'],
        'image': anime['images']['jpg']['image_url'] if 'images' in anime else None,
        'synopsis': clean_synopsis,
        'episodes': anime['episodes'] or "Unknown",
        'trailer': trailer_url
    }

    return render_template("anime.html", anime=anime_details)


# Extra static pages
@app.route("/about")
def about():
    return render_template("about.html")

@app.route("/contact")
def contact():
    return render_template("contact.html")

@app.route("/credits")
def credits():
    return render_template("credits.html")


if __name__ == "__main__":
    app.run(debug=True)
