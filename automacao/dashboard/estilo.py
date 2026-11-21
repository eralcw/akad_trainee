CSS = """
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500&family=IBM+Plex+Sans:wght@400;500;600&display=swap');

:root{
  --ink:#12201D; --muted:#5C6B66; --rule:#CBD6D1; --bg:#EDF1EF;
  --pine:#17453C; --signal:#C8451F; --surface:#E2E9E5;
}
.stApp{background:var(--bg);color:var(--ink);}
.block-container{max-width:1120px;padding-top:2.2rem;padding-bottom:4rem;}
[data-testid="stSidebar"]{background:var(--surface);border-right:1px solid var(--rule);}
[data-testid="stSidebar"] .block-container{padding-top:1.4rem;}
h1,h2,h3,h4{font-family:'IBM Plex Sans','Segoe UI',sans-serif;letter-spacing:-.02em;color:var(--ink);}
p,label,.stMarkdown{font-family:'IBM Plex Sans','Segoe UI',sans-serif;}
code{font-family:'IBM Plex Mono',monospace;font-size:.9em;background:#DDE6E1;padding:1px 4px;}
.masthead{border-bottom:1px solid var(--rule);padding-bottom:16px;margin-bottom:6px;}
.kicker{font-family:'IBM Plex Mono',monospace;font-size:11px;color:var(--muted);margin-bottom:8px;}
.masthead h1{font-size:36px;line-height:1.1;font-weight:600;margin:0 0 8px;}
.standfirst{font-size:15px;line-height:1.55;color:#33443F;max-width:74ch;margin:0;}
.ledger{display:grid;grid-template-columns:repeat(4,1fr);border-top:1px solid var(--rule);border-bottom:1px solid var(--rule);margin:18px 0 8px;}
.ledger div{padding:12px 14px;border-left:1px solid var(--rule);}
.ledger div:first-child{border-left:0;padding-left:0;}
.ledger .lab{display:block;font-size:11px;color:var(--muted);margin-bottom:3px;}
.ledger .val{display:block;font-family:'IBM Plex Mono',monospace;font-size:20px;letter-spacing:-.02em;}
.ledger .nota{display:block;font-size:10px;color:var(--muted);margin-top:3px;}
.small{font-family:'IBM Plex Mono',monospace;font-size:11px;color:var(--muted);}
.stButton > button[kind="primary"]{background:var(--pine);border-color:var(--pine);}
.stButton > button[kind="primary"]:hover{background:#0F332C;border-color:#0F332C;}
.stButton > button:disabled{opacity:.45;}
[data-testid="stDataFrame"]{border:1px solid var(--rule);}
[data-testid="stAlert"]{border-radius:0;}
[data-testid="stTabs"] button[data-baseweb="tab"]{font-family:'IBM Plex Sans',sans-serif;}
@media(max-width:800px){
  .masthead h1{font-size:28px;}
  .ledger{grid-template-columns:1fr 1fr;}
  .ledger div{border-left:0;border-top:1px solid var(--rule);padding-left:0;}
}
"""
