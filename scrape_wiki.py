import os
import sys
import requests

def scrape_to_markdown(url: str, output_dir: str, filename: str) -> None:
    reader_url = f"https://r.jina.ai/{url}"
    
    try:
        print(f"Fetching from Jina Reader: {reader_url}")
        response = requests.get(reader_url, timeout=30)
        response.raise_for_status()
        
        text = response.text
        cutoff = "Opt-Out Request Honored"
        if cutoff in text:
            text = text.split(cutoff)[0]
        
        os.makedirs(output_dir, exist_ok=True)
        path = os.path.join(output_dir, filename)
        
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)
            
        print(f"Successfully saved clean Markdown to {path}")
        
    except requests.RequestException as e:
        print(f"Network error while fetching URL: {e}", file=sys.stderr)
        sys.exit(1)
    except IOError as e:
        print(f"File I/O error while saving output: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    if len(sys.argv) < 4:
        print("Usage: python scrape_wiki.py <url> <output_dir> <filename>")
        sys.exit(1)
        
    scrape_to_markdown(sys.argv[1], sys.argv[2], sys.argv[3])