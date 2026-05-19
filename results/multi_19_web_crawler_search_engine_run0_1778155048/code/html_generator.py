"""Generates a static search.html page with search form and JavaScript."""

import os


def generate_search_html(output_path='search.html', port=8080):
    """Generate a search.html file that queries the REST API."""

    html_content = f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Web Search Engine</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: #f5f5f5;
            color: #333;
            min-height: 100vh;
        }}
        .header {{
            background: linear-gradient(135deg, #1a73e8, #0d47a1);
            color: white;
            padding: 40px 20px;
            text-align: center;
        }}
        .header h1 {{
            font-size: 2.5em;
            margin-bottom: 10px;
        }}
        .header p {{
            opacity: 0.9;
            font-size: 1.1em;
        }}
        .search-container {{
            max-width: 700px;
            margin: -25px auto 0;
            padding: 0 20px;
            position: relative;
            z-index: 10;
        }}
        .search-box {{
            display: flex;
            background: white;
            border-radius: 30px;
            box-shadow: 0 4px 20px rgba(0,0,0,0.15);
            overflow: hidden;
        }}
        .search-box input {{
            flex: 1;
            padding: 16px 24px;
            border: none;
            font-size: 1.1em;
            outline: none;
        }}
        .search-box button {{
            padding: 16px 32px;
            background: #1a73e8;
            color: white;
            border: none;
            font-size: 1.1em;
            cursor: pointer;
            transition: background 0.2s;
        }}
        .search-box button:hover {{
            background: #1557b0;
        }}
        .stats {{
            max-width: 700px;
            margin: 30px auto 0;
            padding: 0 20px;
        }}
        .stats-btn {{
            display: inline-block;
            padding: 8px 20px;
            background: #28a745;
            color: white;
            border: none;
            border-radius: 20px;
            cursor: pointer;
            font-size: 0.9em;
            transition: background 0.2s;
        }}
        .stats-btn:hover {{
            background: #1e7e34;
        }}
        .stats-info {{
            margin-top: 15px;
            padding: 15px 20px;
            background: white;
            border-radius: 10px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.08);
            display: none;
        }}
        .stats-info.visible {{
            display: block;
        }}
        .stats-info table {{
            width: 100%;
            border-collapse: collapse;
        }}
        .stats-info td {{
            padding: 6px 0;
        }}
        .stats-info td:first-child {{
            font-weight: 600;
            width: 200px;
        }}
        .results {{
            max-width: 700px;
            margin: 30px auto;
            padding: 0 20px;
        }}
        .result-item {{
            background: white;
            border-radius: 10px;
            padding: 20px;
            margin-bottom: 15px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.06);
            transition: transform 0.15s, box-shadow 0.15s;
        }}
        .result-item:hover {{
            transform: translateY(-1px);
            box-shadow: 0 4px 16px rgba(0,0,0,0.1);
        }}
        .result-title {{
            font-size: 1.2em;
            margin-bottom: 6px;
        }}
        .result-title a {{
            color: #1a73e8;
            text-decoration: none;
        }}
        .result-title a:hover {{
            text-decoration: underline;
        }}
        .result-url {{
            color: #006621;
            font-size: 0.85em;
            margin-bottom: 6px;
            word-break: break-all;
        }}
        .result-score {{
            color: #888;
            font-size: 0.8em;
            margin-bottom: 8px;
        }}
        .result-snippet {{
            color: #555;
            line-height: 1.5;
            font-size: 0.95em;
        }}
        .result-snippet b {{
            color: #d32f2f;
            font-weight: 700;
        }}
        .no-results {{
            text-align: center;
            color: #888;
            padding: 40px;
            font-size: 1.1em;
        }}
        .loading {{
            text-align: center;
            padding: 30px;
            color: #888;
        }}
        .error {{
            text-align: center;
            padding: 20px;
            color: #d32f2f;
            background: #ffebee;
            border-radius: 8px;
        }}
        .crawl-btn {{
            display: inline-block;
            padding: 8px 20px;
            background: #ff9800;
            color: white;
            border: none;
            border-radius: 20px;
            cursor: pointer;
            font-size: 0.9em;
            transition: background 0.2s;
            margin-left: 10px;
        }}
        .crawl-btn:hover {{
            background: #e68900;
        }}
        .crawl-status {{
            margin-top: 10px;
            padding: 10px;
            background: #fff3e0;
            border-radius: 8px;
            display: none;
        }}
        footer {{
            text-align: center;
            padding: 30px;
            color: #aaa;
            font-size: 0.85em;
        }}
    </style>
</head>
<body>
    <div class="header">
        <h1>&#x1F50D; Web Search Engine</h1>
        <p>Search across crawled web pages</p>
    </div>

    <div class="search-container">
        <div class="search-box">
            <input type="text" id="queryInput" placeholder="Enter your search query..."
                   autofocus onkeydown="if(event.key==='Enter') doSearch()">
            <button onclick="doSearch()">Search</button>
        </div>
    </div>

    <div class="stats">
        <button class="stats-btn" onclick="showStats()">&#x1F4CA; Index Stats</button>
        <button class="crawl-btn" onclick="triggerCrawl()">&#x1F310; Recrawl</button>
        <div class="crawl-status" id="crawlStatus"></div>
        <div class="stats-info" id="statsInfo"></div>
    </div>

    <div class="results" id="results">
        <div class="no-results">Enter a query to search the index.</div>
    </div>

    <footer>
        Web Crawler &amp; Search Engine &mdash; Built with Python
    </footer>

    <script>
        const API_BASE = 'http://localhost:{port}';

        async function doSearch() {{
            const query = document.getElementById('queryInput').value.trim();
            if (!query) return;

            const resultsDiv = document.getElementById('results');
            resultsDiv.innerHTML = '<div class="loading">Searching...</div>';

            try {{
                const response = await fetch(
                    `${{API_BASE}}/search?q=${{encodeURIComponent(query)}}&limit=10`
                );
                if (!response.ok) throw new Error(`HTTP ${{response.status}}`);
                const data = await response.json();

                if (data.length === 0) {{
                    resultsDiv.innerHTML = '<div class="no-results">No results found for "' +
                        escapeHtml(query) + '".</div>';
                    return;
                }}

                let html = '';
                for (const item of data) {{
                    html += `
                        <div class="result-item">
                            <div class="result-title">
                                <a href="${{escapeHtml(item.url)}}" target="_blank">${{escapeHtml(item.title) || 'Untitled'}}</a>
                            </div>
                            <div class="result-url">${{escapeHtml(item.url)}}</div>
                            <div class="result-score">Score: ${{item.score.toFixed(4)}}</div>
                            <div class="result-snippet">${{item.snippet || ''}}</div>
                        </div>`;
                }}
                resultsDiv.innerHTML = html;
            }} catch (err) {{
                resultsDiv.innerHTML = '<div class="error">Error: ' + escapeHtml(err.message) +
                    '<br><small>Make sure the server is running on port {port}.</small></div>';
            }}
        }}

        async function showStats() {{
            const statsDiv = document.getElementById('statsInfo');
            if (statsDiv.classList.contains('visible')) {{
                statsDiv.classList.remove('visible');
                statsDiv.innerHTML = '';
                return;
            }}

            statsDiv.classList.add('visible');
            statsDiv.innerHTML = '<div class="loading">Loading stats...</div>';

            try {{
                const response = await fetch(`${{API_BASE}}/stats`);
                if (!response.ok) throw new Error(`HTTP ${{response.status}}`);
                const data = await response.json();
                statsDiv.innerHTML = `
                    <table>
                        <tr><td>Pages Crawled:</td><td>${{data.pages_crawled || 0}}</td></tr>
                        <tr><td>Unique Terms:</td><td>${{data.unique_terms || 0}}</td></tr>
                        <tr><td>Index File Size:</td><td>${{formatBytes(data.index_size_bytes || 0)}}</td></tr>
                        <tr><td>Crawl Duration:</td><td>${{(data.crawl_duration_seconds || 0).toFixed(1)}}s</td></tr>
                    </table>`;
            }} catch (err) {{
                statsDiv.innerHTML = '<div class="error">Error loading stats: ' +
                    escapeHtml(err.message) + '</div>';
            }}
        }}

        async function triggerCrawl() {{
            const statusDiv = document.getElementById('crawlStatus');
            statusDiv.style.display = 'block';
            statusDiv.textContent = 'Starting crawl job...';

            try {{
                const response = await fetch(`${{API_BASE}}/crawl`);
                if (!response.ok) throw new Error(`HTTP ${{response.status}}`);
                const data = await response.json();
                const jobId = data.job_id;
                statusDiv.textContent = `Crawl job #${{jobId}} started. Polling status...`;

                // Poll for status
                const pollInterval = setInterval(async () => {{
                    try {{
                        const resp = await fetch(`${{API_BASE}}/crawl/${{jobId}}`);
                        const jobData = await resp.json();
                        statusDiv.textContent = `Job #${{jobId}}: ${{jobData.status}} | ` +
                            `Pages: ${{jobData.pages_crawled || 0}} / ${{jobData.total_queued || 0}}`;

                        if (jobData.status === 'completed') {{
                            clearInterval(pollInterval);
                            statusDiv.textContent = `Job #${{jobId}} completed! ` +
                                `${{jobData.pages_crawled}} pages crawled. Refresh search to use new index.`;
                            setTimeout(() => {{
                                statusDiv.style.display = 'none';
                            }}, 5000);
                        }} else if (jobData.status === 'failed') {{
                            clearInterval(pollInterval);
                            statusDiv.textContent = `Job #${{jobId}} failed.`;
                        }}
                    }} catch (e) {{
                        clearInterval(pollInterval);
                        statusDiv.textContent = 'Error polling job status.';
                    }}
                }}, 2000);
            }} catch (err) {{
                statusDiv.textContent = 'Error starting crawl: ' + escapeHtml(err.message);
            }}
        }}

        function escapeHtml(text) {{
            const div = document.createElement('div');
            div.appendChild(document.createTextNode(text));
            return div.innerHTML;
        }}

        function formatBytes(bytes) {{
            if (bytes < 1024) return bytes + ' B';
            if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
            return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
        }}
    </script>
</body>
</html>'''

    os.makedirs(os.path.dirname(output_path) if os.path.dirname(output_path) else '.', exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html_content)

    print(f"Generated search.html (API base: http://localhost:{port})")
    return output_path


if __name__ == '__main__':
    generate_search_html()
