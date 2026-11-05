# Image Uploader

A small [Dash](https://dash.plotly.com/) web app for practicing image uploads to [Supabase](https://supabase.com/). Upload an image, browse earlier uploads, and let Google Gemini write a short description that is saved back to the database.

## Features

- Password-protected uploads (SHA-256 hash checked against `PASS_HASH`)
- Validates images: JPEG, PNG or WEBP only, max 5 MB
- Downsizes images to at most 1600 x 1600 px before upload
- Stores files in a public Supabase Storage bucket and records them in a Postgres table
- History dropdown with image preview
- "Describe with AI" button: Gemini generates a 2-sentence description (in Thai) and saves it to the `images` table

## Requirements

- Python 3.12
- [uv](https://docs.astral.sh/uv/)
- A Supabase project
- A Gemini API key from [Google AI Studio](https://aistudio.google.com/)

## Supabase setup

1. **Storage bucket:** create a **public** bucket named `images` (Storage → New bucket).
2. **Table and policies:** run this in the SQL Editor:

   ```sql
   create table public.images (
     id bigint generated always as identity primary key,
     filename text,
     url text not null,
     description text,
     created_at timestamptz not null default now()
   );

   alter table public.images enable row level security;
   create policy "anon read"   on public.images for select to anon using (true);
   create policy "anon insert" on public.images for insert to anon with check (true);
   create policy "anon update" on public.images for update to anon using (true) with check (true);

   create policy "allow uploads to images"
   on storage.objects for insert to anon
   with check (bucket_id = 'images');
   ```

   These policies are for the anon key. If you use the `service_role` key instead, they are not needed, but keep that key server-side only.

## Configuration

Create a `.env` file in this folder (it is git-ignored):

```
SUPABASE_URL=https://<your-project>.supabase.co
SUPABASE_KEY=<your-supabase-key>
PASS_HASH=<sha256-hex-of-your-upload-password>
GEMINI_API_KEY=<your-gemini-api-key>
```

Generate `PASS_HASH` with:

```bash
python3 -c "import hashlib; print(hashlib.sha256(b'your-password').hexdigest())"
```

## Run

```bash
uv run app.py
```

Then open the local address Dash prints (usually http://127.0.0.1:8050).

## Usage

1. Type the password, then drag a file onto the upload area or click it.
2. The new image is selected in the **History** dropdown and previewed.
3. Click **Describe with AI** to generate and save a description. Reselecting the image later shows the saved text.

## Project structure

```
app.py          Dash app: layout, upload, history, Gemini description
pyproject.toml  Dependencies (managed with uv)
.env            Secrets (not committed)
```

## Troubleshooting

| Error | Cause / fix |
|---|---|
| `Bucket not found` | Create the public `images` bucket. |
| `Could not find the table 'public.images'` | Run the SQL above. |
| `violates row-level security policy` | Add the policies above, or use the service_role key. |
| Description shows on screen but is not saved | Missing the `anon update` policy. |
| "AI error - try again later" | Check the terminal for details: wrong `MODEL` name, invalid `GEMINI_API_KEY`, or a rate limit. |

## Notes

Never commit `.env` or expose the Supabase service_role key or Gemini key in client-side code.
