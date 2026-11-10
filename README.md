# Kindle e-ink dashboard

A Kindle Paperwhite 11th gen (PW5) as a Wi-Fi dashboard. GitHub Actions renders one PNG per
page every 15 minutes and publishes them on GitHub Pages. The Kindle downloads them, shows them
full screen and redraws the clock itself every minute.

Pages: **Home** (clock, date, Katra weather, 3-day forecast, AQI, sunrise/sunset, headlines, quote),
**News** (India / World / Tech), **Markets** (Nifty 50, Sensex, USD/INR, gold), **Photos**.

Everything is free: Open-Meteo (weather, AQI), RSS feeds (news), Yahoo Finance's unofficial
endpoint (markets; it may break if Yahoo changes it).

## 1. Jailbreak (on the Kindle)

Follow [kindlemodding.org](https://kindlemodding.org/jailbreaking/); its steps take priority over these.

1. **Block updates first.** The PW5 connects over MTP, so filler files are copied rather than made
   by a script: use the MTP filler files from the `Crosunt223/Kindle-Filler-Disk` repo and leave
   only 50–90 MB free (check under Settings → Device options → Device info). Delete any
   `update*.bin` in the Kindle's root folder.
2. Run the [Jailbreak Wizard](https://kindlemodding.org/jailbreak-wizard.html) and choose PW5 /
   5.18.3. It will most likely suggest **Véra**: in the Kindle browser open `kindlemodding.org/vera`,
   download both books, set the Font Calibration book's font/spacing/theme exactly as the guide
   says, then open the Véra book. **Wi-Fi has to be on** for this method.
3. After it restarts: delete the two books, any `update*.bin`, and the filler files.

KUAL is obsolete on modern jailbreaks. This project uses **scriptlets** instead: `.sh` files in
`documents/` that show up as books and run when you open them.

## 2. GitHub (rendering + hosting)

1. Create a **public** repo named `kindle-dashboard` and push this folder to it.
   (Pages is free only for public repos, so all rendered pages and `photos/` are public.)
2. Repo → Settings → Pages → Source: **GitHub Actions**.
3. Actions tab → *Render dashboard* → **Run workflow**. Then
   `https://<username>.github.io/kindle-dashboard/` shows a preview of every page.

Edit `config.toml` to change the location, feeds, market symbols or page order.

## 3. Kindle install (USB)

1. In `kindle/dashboard/settings.sh`, set `BASE_URL` to your Pages address.
2. Copy `kindle/dashboard/` to the Kindle's root and the files in `kindle/documents/` into its
   `documents/` folder.
3. On the Kindle, open **Dashboard - Home** (or News / Markets / Photos / Rotate all pages)
   from the library.

While it runs, tap the screen (positions as you see the page, in either orientation):

| Where | What |
|---|---|
| top-left corner | exit to the normal Kindle (the home screen takes up to a minute) |
| top-right corner | frontlight: off → 3 → 8 → 15 → 25 → off |
| bottom-left corner | switch portrait / landscape |
| left third | previous page |
| anywhere else | next page |

The power button also exits. Orientation and light level are remembered; your normal reading
brightness comes back when you exit. Landscape pages assume the USB port is on the right
(`landscape_rotation` in `config.toml`). Keep it on a charger. If it ever gets stuck, hold the power button about 40 s to
reboot. Nothing starts at boot, so a reboot always brings back the normal Kindle.
`dashboard/dashboard.log` on the Kindle shows what happened.

## Photos

- **Public:** put photos in `photos/` on GitHub (website or mobile app). The next run converts them.
- **Private:** `python tools/convert_photos.py <folder>` writes Kindle-ready PNGs into
  `kindle/dashboard/photos/`. Copy them to the Kindle's `dashboard/photos/` over USB. They never go online.

## Local preview

```
pip install -r requirements.txt
python generator/main.py --out out
```
Then open `out/index.html`.
