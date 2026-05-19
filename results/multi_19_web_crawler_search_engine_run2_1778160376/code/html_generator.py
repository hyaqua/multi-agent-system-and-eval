"""
Generates a static search.html file for the search interface.
"""


def generate_search_html(port: int) -> None:
    """Write search.html to the current directory."""
    html = f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Web Search Engine</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    background: #f5f5f5;
    color: #333;
    min-height: 100vh;
  }}
  .container {{
    max-width: 800px;
    margin: 0 auto;
    padding: 40px 20px;
  }}
  h1 {{
    text-align: center;
    margin-bottom: 30px;
    color: #1a73e8;
    font-size: 2.2em;
  }}
  .search-form {{
    display: flex;
    gap: 10px;
    margin-bottom: 30px;
  }}
  .search-form input {{
    flex: 1;
    padding: 14px 18px;
    font-size: 16px;
    border: 2px solid #ddd;
    border-radius: 24px;
    outline: none;
    transition: border-color 0.2s;
  }}
  .search-form input:focus {{
    border-color: #1a73e8;
  }}
  .search-form button {{
    padding: 14px 28px;
    font-size: 16px;
    background: #1a73e8;
    color: white;
    border: none;
    border-radius: 24px;
    cursor: pointer;
    transition: background 0.2s;
  }}
  .search-form button:hover {{
    background: #1557b0;
  }}
  .stats {{
    text-align: center;
    color: #666;
    margin-bottom: 20px;
    font-size: 14px;
  }}
  .result {{
    background: white;
    border-radius: 8px;
    padding: 20px;
    margin-bottom: 15px;
    box-shadow: 0 1px 3px rgba(0,0,0,0.1);
  }}
  .result-title {{
    font-size: 18px;
    margin-bottom: 4px;
  }}
  .result-title a {{
    color: #1a0dab;
    text-decoration: none;
  }}
  .result-title a:hover {{
    text-decoration: underline;
  }}
  .result-url {{
    color: #006621;
    font-size: 13px;
    margin-bottom: 6px;
    word-break: break-all;
  }}
  .result-score {{
    color: #999;
    font-size: 12px;
    margin-bottom: 8px;
  }}
  .result-snippet {{
    font-size: 14px;
    line-height: 1.5;
    color: #545454;
  }}
  .result-snippet b {{
    color: #333;
    font-weight: 700;
  }}
  .no-results {{
    text-align: center;
    color: #999;
    padding: 40px;
    font-size: 16px;
  }}
  .error {{
    background: #fde7e7;
    color: #c00;
    padding: 15px;
    border-radius: 8px;
    text-align: center;
    margin-bottom: 20px;
  }}
  .loading {{
    text-align: center;
    color: #999;
    padding: 20px;
  }}
</style>
</head>
<body>
<div class="container">
  <h1>&#x1f50d; Web Search Engine</h1>
  <form class="search-form" id="searchForm">
    <input type="text" id="queryInput" placeholder="Enter your search query..." autofocus>
    <button type="submit">Search</button>
  </form>
  <div class="stats" id="stats"></div>
  <div id="results"></div>
</div>

<script>
  const API_BASE = "http://localhost:{port}";

  document.getElementById("searchForm").addEventListener("submit", async (e) => {{
    e.preventDefault();
    const query = document.getElementById("queryInput").value.trim();
    if (!query) return;

    const resultsDiv = document.getElementById("results");
    const statsDiv = document.getElementById("stats");
    resultsDiv.innerHTML = '<div class="loading">Searching...</div>';
    statsDiv.textContent = "";

    try {{
      const resp = await fetch(`${{API_BASE}}/search?q=${{encodeURIComponent(query)}}&limit=20`);
      const data = await resp.json();

      if (data.error) {{
        resultsDiv.innerHTML = `<div class="error">${{data.error}}</div>`;
        return;
      }}

      statsDiv.textContent = `Found ${{data.total}} result(s) for "${{data.query}}"`;

      if (!data.results || data.results.length === 0) {{
        resultsDiv.innerHTML = '<div class="no-results">No results found. Try a different query.</div>';
        return;
      }}

      let html = "";
      for (const r of data.results) {{
        const title = r.title || "Untitled";
        const url = r.url || "#";
        const displayUrl = url.length > 80 ? url.substring(0, 77) + "..." : url;
        html += `
          <div class="result">
            <div class="result-title"><a href="${{url}}" target="_blank">${{escapeHtml(title)}}</a></div>
            <div class="result-url">${{escapeHtml(displayUrl)}}</div>
            <div class="result-score">Score: ${{r.score.toFixed(4)}}</div>
            <div class="result-snippet">${{r.snippet}}</div>
          </div>`;
      }}
      resultsDiv.innerHTML = html;
    }} catch (err) {{
      resultsDiv.innerHTML = `<div class="error">Failed to connect to search server: ${{err.message}}</div>`;
    }}
  }});

  function escapeHtml(text) {{
    const div = document.createElement("div");
    div.textContent = text;
    return div.innerHTML;
  }}
</script>
</body>
</html>'''
    with open("search.html", "w", encoding="utf-8") as f:
        f.write(html)
    print(f"Generated search.html (API port: {port})")
