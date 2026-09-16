SIGNIN_PAGE = """<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Link your Ring account</title><style>
body{{background:#0b1019;color:#f0f4fa;font-family:"Segoe UI",system-ui,sans-serif;
display:flex;min-height:100vh;align-items:center;justify-content:center;margin:0}}
.card{{border:2px solid #26344a;border-radius:16px;padding:40px;max-width:430px;width:90%}}
h1{{font-size:24px;margin:0 0 8px}} p{{color:#8a9ab0;line-height:1.55;font-size:15px}}
label{{display:block;margin:18px 0 6px;font-size:13px;color:#8a9ab0;
text-transform:uppercase;letter-spacing:.08em}}
input{{width:100%;padding:12px;border-radius:8px;border:1px solid #26344a;
background:#0e1523;color:#f0f4fa;font-size:16px;box-sizing:border-box}}
button{{margin-top:24px;width:100%;background:#40c4a8;color:#0b1019;border:0;
font-weight:700;font-size:16px;padding:14px;border-radius:10px;cursor:pointer}}
.err{{margin-top:16px;color:#e8a850;font-size:14px}}
.note{{margin-top:22px;font-size:13px;color:#5c6a80}}
</style></head><body><div class="card">
<h1>Link your Ring account</h1>
<p>Sign in to Front Desk to finish connecting Ring. Door events will be
classified on hardware you control; images are never sent to a cloud service.</p>
<form method="POST" action="/oauth/authorize">
  <input type="hidden" name="nonce" value="{nonce}">
  <input type="hidden" name="time" value="{time}">
  <label for="u">Username</label>
  <input id="u" name="username" autocomplete="username" autofocus>
  <label for="p">Password</label>
  <input id="p" name="password" type="password" autocomplete="current-password">
  <button type="submit">Sign in and link</button>
</form>
{error}
<div class="note">Front Desk &middot; Banksy AI LLC</div>
</div></body></html>"""

RESULT_PAGE = """<!doctype html><html lang="en"><head><meta charset="utf-8">
<title>{title}</title><style>
body{{background:#0b1019;color:#f0f4fa;font-family:"Segoe UI",system-ui,sans-serif;
display:flex;min-height:100vh;align-items:center;justify-content:center;margin:0}}
.card{{border:2px solid {color};border-radius:16px;padding:44px;max-width:460px}}
h1{{font-size:26px;margin:0 0 12px;color:{color}}} p{{color:#8a9ab0;line-height:1.6}}
</style></head><body><div class="card"><h1>{title}</h1><p>{body}</p></div></body></html>"""
