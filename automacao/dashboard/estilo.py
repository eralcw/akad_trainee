CSS = """
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500&family=IBM+Plex+Sans:wght@400;500;600&display=swap');

:root{
  --ink:#143057; --muted:#5B6485; --rule:#E4E6F4; --bg:#FFFFFF;
  --akad:#E9256A; --akad-dark:#B3154C; --lilac:#6B72D8; --pink:#F7A3BF;
  --navy:#143057; --surface:#F4F5FD; --charcoal:#3A4A6B;
}
.stApp{background:var(--bg);color:var(--ink);}
.block-container{max-width:1120px;padding-top:4.2rem;padding-bottom:4rem;}
[data-testid="stSidebar"]{background:var(--surface);border-right:1px solid var(--rule);}
[data-testid="stSidebar"] .block-container{padding-top:1.4rem;}
h1,h2,h3,h4{font-family:'IBM Plex Sans','Segoe UI',sans-serif;letter-spacing:-.02em;color:var(--navy);}
p,label,.stMarkdown{font-family:'IBM Plex Sans','Segoe UI',sans-serif;font-size:15.5px;}
a{color:var(--lilac);}
code{font-family:'IBM Plex Mono',monospace;font-size:.9em;background:#F1F2FC;padding:1px 4px;}
hr{border-color:var(--rule);}
.masthead{border-bottom:1px solid var(--rule);padding-bottom:16px;margin-bottom:6px;}
.kicker{font-family:'IBM Plex Mono',monospace;font-size:11px;color:var(--lilac);margin-bottom:8px;}
.masthead h1{font-size:36px;line-height:1.1;font-weight:600;margin:0 0 8px;}
.standfirst{font-size:16px;line-height:1.55;color:var(--charcoal);max-width:74ch;margin:0;}
.ledger{display:grid;grid-template-columns:repeat(4,1fr);border-top:1px solid var(--rule);border-bottom:1px solid var(--rule);margin:18px 0 8px;}
.ledger div{padding:12px 14px;border-left:1px solid var(--rule);}
.ledger div:first-child{border-left:0;padding-left:0;}
.ledger .lab{display:block;font-size:12px;color:var(--muted);margin-bottom:3px;}
.ledger .val{display:block;font-family:'IBM Plex Mono',monospace;font-size:20px;letter-spacing:-.02em;color:var(--navy);font-variant-numeric:tabular-nums;}
.ledger .nota{display:block;font-size:11px;color:var(--muted);margin-top:3px;background:none;border-left:0;padding:0;max-width:none;}
.small{font-family:'IBM Plex Mono',monospace;font-size:12px;color:var(--muted);}
.fluxo{display:flex;flex-wrap:wrap;gap:6px;align-items:stretch;margin:14px 0 6px;}
.fluxo .passo{flex:1 1 150px;background:#F4F5FD;border:1px solid var(--rule);border-top:3px solid var(--lilac);
  border-radius:6px;padding:10px 12px;min-width:140px;}
.fluxo .passo b{display:block;font-size:13px;color:var(--navy);margin-bottom:2px;}
.fluxo .passo span{display:block;font-size:12px;color:var(--muted);line-height:1.35;}
.fluxo .seta{align-self:center;color:var(--akad);font-size:18px;padding:0 2px;}
.secao{display:flex;align-items:baseline;gap:10px;margin:28px 0 4px;border-top:1px solid var(--rule);padding-top:16px;}
.secao .qtag{font-family:'IBM Plex Mono',monospace;font-size:12px;font-weight:600;color:#FFFFFF;
  background:var(--akad);border-radius:5px;padding:3px 8px;letter-spacing:.03em;white-space:nowrap;}
.secao h4{margin:0;font-size:19px;color:var(--navy);font-family:'IBM Plex Sans','Segoe UI',sans-serif;}
.subsecao{margin:22px 0 6px;}
.heatmap{width:100%;border-collapse:separate;border-spacing:3px;margin:8px 0 4px;font-size:13.5px;}
.heatmap th{font-family:'IBM Plex Sans','Segoe UI',sans-serif;font-weight:500;color:var(--muted);font-size:12px;padding:4px 6px;}
.heatmap th.rowh{text-align:left;color:var(--ink);font-weight:600;font-size:13.5px;white-space:nowrap;}
.heatmap td{text-align:center;font-family:'IBM Plex Mono',monospace;font-size:12.5px;padding:9px 6px;border-radius:4px;}
.linha-titulo{font-size:14px;font-weight:600;color:var(--navy);margin:6px 0 10px;
  font-family:'IBM Plex Sans','Segoe UI',sans-serif;}
[data-testid="stVerticalBlockBorderWrapper"]{background:#FFFFFF;}
.escala{display:flex;flex-wrap:wrap;gap:14px;align-items:center;font-size:11.5px;
  color:var(--muted);margin:2px 0 14px;font-family:'IBM Plex Sans','Segoe UI',sans-serif;}
.escala span{display:inline-flex;align-items:center;gap:5px;}
.escala i{display:inline-block;width:24px;height:11px;border-radius:3px;}
.subsecao h5{margin:0;font-size:15.5px;color:var(--charcoal);font-weight:600;
  font-family:'IBM Plex Sans','Segoe UI',sans-serif;}
.nota{background:#F4F5FD;border-left:3px solid var(--lilac);padding:12px 14px;margin:10px 0;max-width:82ch;}
.nota p{margin:0;font-family:'IBM Plex Sans','Segoe UI',sans-serif;font-size:15px;line-height:1.55;color:var(--charcoal);}
.resp-curta{background:#FFF4F8;border-left:4px solid var(--akad);padding:11px 14px;border-radius:0 8px 8px 0;margin:6px 0 14px;font-size:15.5px;line-height:1.5;color:var(--navy);}
.resp-badge{display:inline-block;background:var(--akad);color:#fff;font-family:'IBM Plex Mono',monospace;font-size:12px;font-weight:600;padding:2px 8px;border-radius:999px;margin-right:8px;vertical-align:middle;}
.stButton > button[kind="primary"]{background:var(--akad);border-color:var(--akad);}
.stButton > button[kind="primary"]:hover{background:var(--akad-dark);border-color:var(--akad-dark);}
.stButton > button:disabled{opacity:.45;}
[data-testid="stTabs"] button[data-baseweb="tab"]{font-size:15.5px !important;padding:10px 12px;}
[data-testid="stTabs"] button[data-baseweb="tab"] p,[data-testid="stTabs"] button[data-baseweb="tab"] div{font-size:15.5px !important;}
[data-testid="stTabs"] button[data-baseweb="tab"][aria-selected="true"]{color:var(--akad);}
[data-testid="stSidebar"] .stMarkdown,[data-testid="stSidebar"] p,[data-testid="stSidebar"] label{font-size:14.5px;}
[data-testid="stCaptionContainer"]{font-size:13px;}
[data-testid="stDataFrame"]{font-size:14px;}
.stButton > button{font-size:15px;}
[data-testid="stDataFrame"]{border:1px solid var(--rule);}
[data-testid="stAlert"]{border-radius:0;}
@media(max-width:800px){
  .masthead h1{font-size:28px;}
  .ledger{grid-template-columns:1fr 1fr;}
  .ledger div{border-left:0;border-top:1px solid var(--rule);padding-left:0;}
}
"""
