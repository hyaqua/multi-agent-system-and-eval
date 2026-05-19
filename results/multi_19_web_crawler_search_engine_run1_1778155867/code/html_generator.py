"""Generate a static search.html file for the search interface."""

SEARCH_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Simple Search Engine</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif;
            max-width: 800px;
            margin: 0 auto;
            padding: 20px;
            background: #f5f5f5;
            color: #333;
        }
        h1 {
            text-align: center;
            margin-bottom: 20px;
            color: #1a73e8;
        }
        .search-box {
            display: flex;
            gap: 10px;
            margin-bottom: 30px;
        }
        .search-box input {
            flex: 1;
            padding: 12px 16px;
            font-size: 16px;
            border: 2px solid #ddd;
            border-radius: 8px;
            outline: none;
            transition: border-color 0.2s;
        }
        .search-box input:focus {
            border-color: #1a73e8;
        }
        .search-box button {
            padding: 12px 24px;
            font-size: 16px;
            background: #1a73e8;
            color: white;
            border: none;
            border-radius: 8px;
            cursor: pointer;
            transition: background 0.2s;
        }
        .search-box button:hover {
            background: #1557b0;
        }
        .search-box button:disabled {
            background: #93b8f0;
            cursor: not-allowed;
        }
        .status {
            text-align: center;
            color: #666;
            margin-bottom: 20px;
        }
        .error {
            color: #d93025;
            text-align: center;
            margin-bottom: 20px;
        }
        .result {
            background: white;
            border-radius: 8px;
            padding: 16px 20px;
            margin-bottom: 12px;
            box-shadow: 0 1px 3px rgba(0,0,0,0.1);
        }
        .result-title {
            font-size: 18px;
            margin-bottom: 4px;
        }
        .result-title a {
            color: #1a73e8;
            text-decoration: none;
        }
        .result-title a:hover {
            text-decoration: underline;
        }
        .result-url {
            font-size: 13px;
            color: #006621;
            margin-bottom: 6px;
            word-break: break-all;
        }
        .result-score {
            font-size: 12px;
            color: #999;
            margin-bottom: 6px;
        }
        .result-snippet {
            font-size: 14px;
            color: #555;
            line-height: 1.5;
        }
        .result-snippet b {
            color: #333;
            font-weight: 700;
        }
        .stats {
            font-size: 13px;
            color: #888;
            text-align: center;
            margin-top: 20px;
        }
        .no-results {
            text-align: center;
            color: #888;
            padding: 40px 0;
        }
    </style>
</head>
<body>
    <h1>Simple Search Engine</h1>
    <div class="search-box">
        <input
            type="text"
            id="query-input"
            placeholder="Search the crawled web..."
            autofocus
        />
        <button id="search-btn" onclick="doSearch()">Search</button>
    </div>
    <div id="status" class="status"></div>
    <div id="error" class="error"></div>
    <div id="results"></div>
    <div id="stats" class="stats"></div>

    <script>
        const API_BASE = '';

        async function doSearch() {
            const query = document.getElementById('query-input').value.trim();
            if (!query) return;

            const resultsDiv = document.getElementById('results');
            const statusDiv = document.getElementById('status');
            const errorDiv = document.getElementById('error');
            const btn = document.getElementById('search-btn');

            resultsDiv.innerHTML = '';
            errorDiv.textContent = '';
            statusDiv.textContent = 'Searching...';
            btn.disabled = true;

            try {
                const response = await fetch(
                    `${API_BASE}/search?q=${encodeURIComponent(query)}&limit=20`
                );

                if (!response.ok) {
                    throw new Error(`Server error: ${response.status}`);
                }

                const data = await response.json();

                statusDiv.textContent = data.total_results > 0
                    ? `Found ${data.total_results} result(s) for "${query}"`
                    : `No results found for "${query}"`;

                if (data.results.length === 0) {
                    resultsDiv.innerHTML = '<div class="no-results">No matching pages found.</div>';
                } else {
                    data.results.forEach(result => {
                        const div = document.createElement('div');
                        div.className = 'result';
                        div.innerHTML = `
                            <div class="result-title">
                                <a href="${escapeHtml(result.url)}" target="_blank" rel="noopener">
                                    ${escapeHtml(result.title || result.url)}
                                </a>
                            </div>
                            <div class="result-url">${escapeHtml(result.url)}</div>
                            <div class="result-score">Score: ${result.score.toFixed(4)}</div>
                            <div class="result-snippet">${result.snippet}</div>
                        `;
                        resultsDiv.appendChild(div);
                    });
                }
            } catch (err) {
                errorDiv.textContent = `Search failed: ${err.message}`;
                statusDiv.textContent = '';
            } finally {
                btn.disabled = false;
            }
        }

        function escapeHtml(str) {
            const div = document.createElement('div');
            div.textContent = str;
            return div.innerHTML;
        }

        // Allow pressing Enter to search
        document.getElementById('query-input').addEventListener('keydown', (e) => {
            if (e.key === 'Enter') doSearch();
        });
    </script>
</body>
</html>"""


def generate_search_html(output_path: str = 'search.html'):
    """Write the static search.html file.

    Returns:
        True if the file was written successfully, False on OSError.
    """
    try:
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(SEARCH_HTML)
        print(f'Generated {output_path}')
        return True
    except OSError as e:
        print(f'Warning: Could not write {output_path}: {e}', file=__import__('sys').stderr)
        return False
