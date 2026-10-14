"""Start the Maths Shorts Studio website and open it in the browser."""
import threading
import webbrowser

import uvicorn

PORT = 8000

if __name__ == "__main__":
    url = f"http://localhost:{PORT}"
    print(f"\n  Maths Shorts Studio is running at {url}\n  Keep this window open while you use it. Close it to stop.\n")
    threading.Timer(2.0, lambda: webbrowser.open(url)).start()
    uvicorn.run("server.main:app", host="127.0.0.1", port=PORT, log_level="warning")
