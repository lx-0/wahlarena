"""Build docs/blog.html from BLOG.md."""
import re
from pathlib import Path

ROOT = Path(__file__).parent.parent

def inline(text):
    text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', text)
    text = re.sub(r'\*(.+?)\*', r'<em>\1</em>', text)
    text = re.sub(r'`(.+?)`', r'<code>\1</code>', text)
    text = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'<a href="\2">\1</a>', text)
    return text

def md_to_html(text):
    lines = text.split('\n')
    out = []
    in_code = False
    in_ul = False
    for line in lines:
        if line.startswith('```'):
            if not in_code:
                if in_ul:
                    out.append('</ul>')
                    in_ul = False
                out.append('<pre><code>')
                in_code = True
            else:
                out.append('</code></pre>')
                in_code = False
            continue
        if in_code:
            out.append(line.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;'))
            continue
        if line.startswith('# '):
            if in_ul:
                out.append('</ul>')
                in_ul = False
            out.append(f'<h1>{inline(line[2:])}</h1>')
        elif line.startswith('## '):
            if in_ul:
                out.append('</ul>')
                in_ul = False
            out.append(f'<h2>{inline(line[3:])}</h2>')
        elif line.startswith('### '):
            if in_ul:
                out.append('</ul>')
                in_ul = False
            out.append(f'<h3>{inline(line[4:])}</h3>')
        elif line.startswith('- '):
            if not in_ul:
                out.append('<ul>')
                in_ul = True
            out.append(f'<li>{inline(line[2:])}</li>')
        elif line.startswith('> '):
            if in_ul:
                out.append('</ul>')
                in_ul = False
            out.append(f'<blockquote>{inline(line[2:])}</blockquote>')
        elif line.strip() == '---':
            if in_ul:
                out.append('</ul>')
                in_ul = False
            out.append('<hr>')
        elif line.strip() == '':
            if in_ul:
                out.append('</ul>')
                in_ul = False
            out.append('')
        else:
            if in_ul:
                out.append('</ul>')
                in_ul = False
            out.append(f'<p>{inline(line)}</p>')
    if in_ul:
        out.append('</ul>')
    return '\n'.join(out)

md = (ROOT / 'BLOG.md').read_text()
body = md_to_html(md)

html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>We Ran 12 Frontier LLMs Through Germany's Wahl-O-Mat</title>
<style>
:root {{
  --bg: #0f1117; --surface: #1a1d27; --border: #2a2d3e;
  --text: #e2e8f0; --muted: #8892a4; --accent: #6366f1;
}}
* {{ box-sizing: border-box; margin: 0; padding: 0; }}
body {{ background: var(--bg); color: var(--text); font-family: Georgia, serif; font-size: 16px; line-height: 1.8; }}
header {{ border-bottom: 1px solid var(--border); padding: 16px 32px; display: flex; gap: 16px; align-items: center; font-family: system-ui, sans-serif; }}
header a {{ color: var(--accent); text-decoration: none; font-size: 0.85rem; }}
article {{ max-width: 720px; margin: 40px auto; padding: 0 24px 80px; }}
h1 {{ font-size: 1.8rem; line-height: 1.3; margin-bottom: 12px; }}
h2 {{ font-size: 1.15rem; font-weight: 700; margin: 36px 0 10px; color: var(--text); }}
h3 {{ font-size: 1rem; font-weight: 700; margin: 24px 0 8px; }}
p {{ color: #cbd5e1; margin-bottom: 14px; }}
em {{ color: var(--muted); font-style: italic; }}
strong {{ color: var(--text); font-weight: 700; }}
a {{ color: var(--accent); text-decoration: none; }}
a:hover {{ text-decoration: underline; }}
ul {{ color: #cbd5e1; padding-left: 22px; margin-bottom: 14px; }}
li {{ margin-bottom: 4px; }}
blockquote {{ border-left: 3px solid var(--accent); padding: 8px 16px; margin: 16px 0; color: var(--muted); font-style: italic; background: var(--surface); border-radius: 0 6px 6px 0; }}
pre {{ background: var(--surface); border: 1px solid var(--border); border-radius: 8px; padding: 16px; margin: 16px 0; overflow-x: auto; }}
code {{ font-family: 'Fira Code', monospace; font-size: 0.85rem; background: var(--surface); padding: 1px 5px; border-radius: 3px; }}
pre code {{ background: none; padding: 0; }}
hr {{ border: none; border-top: 1px solid var(--border); margin: 32px 0; }}
</style>
</head>
<body>
<header>
  <span style="font-weight:700;font-family:system-ui">Wahl-O-Mat LLM Evaluation</span>
  <a href="index.html">← Dashboard</a>
  <a href="../REPORT.en.md">Full Report</a>
  <a href="https://github.com/lx-0/wahlarena">GitHub</a>
</header>
<article>
{body}
</article>
</body>
</html>"""

out = ROOT / 'docs' / 'blog.html'
out.write_text(html)
print(f"Written {out} ({len(html):,} chars)")
