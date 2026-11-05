import os, base64, hashlib, uuid
from io import BytesIO
from PIL import Image
from dash import Dash, dcc, html, Input, Output, State, no_update
from dotenv import load_dotenv
from supabase import create_client
import requests
from google import genai
from google.genai import types

load_dotenv()
PASS_HASH = os.getenv("PASS_HASH")
sb = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))
BUCKET = "images"
ALLOWED = {"JPEG", "PNG", "WEBP"}
MAX_BYTES = 5 * 1024 * 1024

# after sb = create_client(...):
ai = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
MODEL = "gemini-3.5-flash-lite"


def password_ok(password):
    h = hashlib.sha256((password or "").encode()).hexdigest()
    return h == PASS_HASH


def history_options():
    rows = (
        sb.table("images")
        .select("id, filename")
        .order("created_at", desc=True)
        .execute()
        .data
    )
    return [{"label": f'{r["id"]}. {r["filename"]}', "value": r["id"]} for r in rows]


def shrink(data, fmt):
    img = Image.open(BytesIO(data))
    img.thumbnail((1600, 1600))
    buf = BytesIO()
    img.save(buf, format=fmt)
    return buf.getvalue()


def check_image(contents):
    data = base64.b64decode(contents.split(",", 1)[1])
    if len(data) > MAX_BYTES:
        raise ValueError("File too large (max 5 MB)")
    try:
        img = Image.open(BytesIO(data))
        img.verify()
    except Exception:
        raise ValueError("This is not a valid image")
    if img.format not in ALLOWED:
        raise ValueError("Only JPEG, PNG, WEBP allowed")
    return data, img.format


def serve_layout():
    return [
        html.H3("Image Uploader"),
        dcc.Input(id="password", type="password", placeholder="Password"),
        dcc.Upload(
            id="upload",
            accept="image/*",
            max_size=MAX_BYTES,
            children=html.Div("Drag or click to upload an image"),
        ),
        html.Div(id="msg"),
        dcc.Dropdown(id="history", options=history_options(), placeholder="History"),
        html.Img(id="preview", style={"maxWidth": "400px"}),
        html.Button("Describe with AI อธิบายด้วยเอไอ", id="btn-ai"),
        dcc.Loading(html.P(id="desc")),
    ]


app = Dash()
server = app.server  # for gunicorn (on Render.com)
app.layout = serve_layout


@app.callback(
    Output("msg", "children"),
    Output("history", "options"),
    Output("history", "value"),
    Input("upload", "contents"),
    State("upload", "filename"),
    State("password", "value"),
    prevent_initial_call=True,
)
def handle_upload(contents, filename, password):
    if not password_ok(password):
        return "Wrong password", no_update, no_update
    try:
        data, fmt = check_image(contents)
    except ValueError as e:
        return str(e), no_update, no_update
    data = shrink(data, fmt)
    name = f"{uuid.uuid4().hex}.{fmt.lower()}"
    sb.storage.from_(BUCKET).upload(
        path=name,
        file=data,
        file_options={"content-type": Image.MIME[fmt]},
    )
    url = sb.storage.from_(BUCKET).get_public_url(name)
    row = (
        sb.table("images").insert({"filename": filename, "url": url}).execute().data[0]
    )
    return "Uploaded!", history_options(), row["id"]


@app.callback(
    Output("preview", "src"),
    Output("desc", "children"),
    Input("history", "value"),
)
def show_image(img_id):
    if not img_id:
        return None, ""
    row = sb.table("images").select("*").eq("id", img_id).execute().data[0]
    return row["url"], row["description"] or "(no description yet)"


@app.callback(
    Output("desc", "children", allow_duplicate=True),
    Input("btn-ai", "n_clicks"),
    State("history", "value"),
    State("password", "value"),
    prevent_initial_call=True,
)
def describe(n_clicks, img_id, password):
    if not password_ok(password):
        return "Wrong password"
    if not img_id:
        return "Please select an image first"
    row = sb.table("images").select("*").eq("id", img_id).execute().data[0]
    try:
        r = requests.get(row["url"])
        part = types.Part.from_bytes(
            data=r.content, mime_type=r.headers["content-type"]
        )
        resp = ai.models.generate_content(
            model=MODEL, contents=[part, "อธิบายภาพนี้เป็นภาษาไทย 2 ประโยค"] #"Describe this picture in 2 sentences."]
        )
        text = resp.text
    except Exception as e:
        print(e)
        return "AI error - try again later (maybe a rate limit)"
    sb.table("images").update({"description": text}).eq("id", img_id).execute()
    return text


if __name__ == "__main__":
    app.run(debug=True)