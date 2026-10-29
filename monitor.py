import os, re, subprocess, sys
import requests

MODE = os.environ.get("MODE", "check")  # check | dump | test_detect | test_alert
URL = os.environ.get("BMS_URL", "")
MOVIE = os.environ.get("MOVIE", "ramayana").lower()
FORMAT = os.environ.get("FORMAT", "dolby").lower()
WINDOW = int(os.environ.get("WINDOW", "700"))  # chars after movie name to look for the format

SID = os.environ.get("TWILIO_SID", "")
TOKEN = os.environ.get("TWILIO_TOKEN", "")
MY_NUMBER = os.environ.get("MY_NUMBER", "")            # e.g. +919876543210
CALL_FROM = os.environ.get("TWILIO_CALL_FROM", "")     # your Twilio voice number
WA_FROM = os.environ.get("TWILIO_WA_FROM", "whatsapp:+14155238886")  # Twilio sandbox default


def get_text(screenshot=False):
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        browser = p.chromium.launch()
        ctx = browser.new_context(
            locale="en-IN",
            viewport={"width": 1366, "height": 900},
            user_agent=("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"),
        )
        page = ctx.new_page()
        page.goto(URL, wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(6000)
        if screenshot:
            page.screenshot(path="shot.png", full_page=True)
        text = page.inner_text("body")
        browser.close()
    return re.sub(r"\s+", " ", text.lower())


def found(text):
    for m in re.finditer(re.escape(MOVIE), text):
        if FORMAT in text[m.start(): m.start() + WINDOW]:
            return True
    return False


def alert(test=False):
    prefix = "[TEST] " if test else ""
    msg = f"{prefix}{MOVIE.title()} {FORMAT.title()} tickets look open! Book now: {URL or 'bookmyshow.com'}"
    auth = (SID, TOKEN)
    base = f"https://api.twilio.com/2010-04-01/Accounts/{SID}"
    r1 = requests.post(f"{base}/Messages.json", auth=auth, data={
        "From": WA_FROM, "To": f"whatsapp:{MY_NUMBER}", "Body": msg})
    print("WhatsApp:", r1.status_code, r1.text[:300])
    say = "This is a test call." if test else f"{MOVIE} {FORMAT} tickets are open on Book My Show. Book now."
    twiml = (f"<Response><Pause length='1'/><Say voice='alice'>{say}</Say>"
             f"<Pause length='1'/><Say>{say}</Say></Response>")
    r2 = requests.post(f"{base}/Calls.json", auth=auth, data={
        "From": CALL_FROM, "To": MY_NUMBER, "Twiml": twiml})
    print("Call:", r2.status_code, r2.text[:300])


def disable_self():
    subprocess.run(["gh", "workflow", "disable", "monitor.yml"], check=False)


if __name__ == "__main__":
    if MODE == "test_alert":
        alert(test=True)
    elif MODE == "test_detect":
        yes = "ramayana (hindi) 3d dolby cinema 10:30 pm 7:15 pm"
        no = "ramayana (hindi) 3d 10:30 pm " + "x " * 800 + "other movie dolby cinema"
        print("Should be True :", found(yes))
        print("Should be False:", found(no))
    elif MODE == "dump":
        text = get_text(screenshot=True)
        print(f"Fetched {len(text)} chars. First 1500:\n{text[:1500]}")
        print("Movie word present:", MOVIE in text, "| Format word present:", FORMAT in text)
        print("Detector says:", found(text))
    else:  # check
        text = get_text()
        print(f"Fetched {len(text)} chars")
        if len(text) < 500 or "access denied" in text:
            print("Page looks blocked/empty; will retry next run.")
            sys.exit(0)
        if found(text):
            alert()
            disable_self()
        else:
            print("Not available yet.")
