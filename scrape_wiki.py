import os
import sys
import requests

# Get a page via Jina Reader and save it as a markdown file.
def scrape_to_markdown(url: str, output_dir: str, filename: str) -> None:
    reader_url = f"https://r.jina.ai/{url}"
    
    print(f"Fetching from Jina Reader: {reader_url}")
    response = requests.get(reader_url, timeout=30)
    response.raise_for_status()
    
    text = response.text
    # Remove the opt-out footer if it is present in the content.
    cutoff = "Opt-Out Request Honored"
    if cutoff in text:
        text = text.split(cutoff)[0]
    
    os.makedirs(output_dir, exist_ok=True)
    save_path = os.path.join(output_dir, filename)
    
    with open(save_path, "w", encoding="utf-8") as f:
        f.write(text)
        
    print(f"Successfully saved clean Markdown to {save_path}")

if __name__ == "__main__":
    if len(sys.argv) < 4:
        print("Usage: python scrape_wiki.py <url> <output_dir> <filename>")
        sys.exit(1)
        
    try:
        scrape_to_markdown(sys.argv[1], sys.argv[2], sys.argv[3])
    except requests.RequestException as e:
        print(f"Network error while fetching URL: {e}", file=sys.stderr)
        sys.exit(1)
    except IOError as e:
        print(f"File I/O error while saving output: {e}", file=sys.stderr)
        sys.exit(1)