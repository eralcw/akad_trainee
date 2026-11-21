CSS = """
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500&family=IBM+Plex+Sans:wght@400;500;600&display=swap');

:root{
  --ink:#143057; --muted:#5B6485; --rule:#E4E6F4; --bg:#FFFFFF;
  --akad:#E9256A; --akad-dark:#B3154C; --lilac:#6B72D8; --pink:#F7A3BF;
  --navy:#143057; --surface:#F4F5FD; --charcoal:#3A4A6B;
}
.stApp{background:var(--bg);color:var(--ink);}
.block-container{max-width:1120px;padding-top:2.2rem;padding-bottom:4rem;}
[data-testid="stSidebar"]{background:var(--surface);border-right:1px solid var(--rule);}
[data-testid="stSidebar"] .block-container{padding-top:1.4rem;}
h1,h2,h3,h4{font-family:'IBM Plex Sans','Segoe UI',sans-serif;letter-spacing:-.02em;color:var(--navy);}
p,label,.stMarkdown{font-family:'IBM Plex Sans','Segoe UI',sans-serif;}
a{color:var(--lilac);}
code{font-family:'IBM Plex Mono',monospace;font-size:.9em;background:#F1F2FC;padding:1px 4px;}
hr{border-color:var(--rule);}
.masthead{border-bottom:1px solid var(--rule);padding-bottom:16px;margin-bottom:6px;}
.kicker{font-family:'IBM Plex Mono',monospace;font-size:11px;color:var(--lilac);margin-bottom:8px;}
.masthead h1{font-size:36px;line-height:1.1;font-weight:600;margin:0 0 8px;}
.standfirst{font-size:15px;line-height:1.55;color:var(--charcoal);max-width:74ch;margin:0;}
.ledger{display:grid;grid-template-columns:repeat(4,1fr);border-top:1px solid var(--rule);border-bottom:1px solid var(--rule);margin:18px 0 8px;}
.ledger div{padding:12px 14px;border-left:1px solid var(--rule);}
.ledger div:first-child{border-left:0;padding-left:0;}
.ledger .lab{display:block;font-size:11px;color:var(--muted);margin-bottom:3px;}
.ledger .val{display:block;font-family:'IBM Plex Mono',monospace;font-size:20px;letter-spacing:-.02em;color:var(--navy);}
.ledger .nota{display:block;font-size:10px;color:var(--muted);margin-top:3px;}
.small{font-family:'IBM Plex Mono',monospace;font-size:11px;color:var(--muted);}
.nota{background:#F4F5FD;border-left:3px solid var(--lilac);padding:12px 14px;margin:10px 0;max-width:82ch;}
.nota p{margin:0;font-family:'IBM Plex Sans','Segoe UI',sans-serif;font-size:14px;line-height:1.55;color:var(--charcoal);}
.stButton > button[kind="primary"]{background:var(--akad);border-color:var(--akad);}
.stButton > button[kind="primary"]:hover{background:var(--akad-dark);border-color:var(--akad-dark);}
.stButton > button:disabled{opacity:.45;}
[data-testid="stTabs"] button[data-baseweb="tab"][aria-selected="true"]{color:var(--akad);}
[data-testid="stDataFrame"]{border:1px solid var(--rule);}
[data-testid="stAlert"]{border-radius:0;}
@media(max-width:800px){
  .masthead h1{font-size:28px;}
  .ledger{grid-template-columns:1fr 1fr;}
  .ledger div{border-left:0;border-top:1px solid var(--rule);padding-left:0;}
}
"""
