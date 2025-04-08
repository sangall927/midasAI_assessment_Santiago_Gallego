import os
import uuid
import json
import requests
import nest_asyncio
from dotenv import load_dotenv
from llama_cloud_services import LlamaParse
from langchain.text_splitter import RecursiveCharacterTextSplitter

# --------------------- Predefined categories ---------------------

CATEGORIES = {
    "Financial Reports": ["annual report", "quarterly report", "earnings"],
    "Investor Presentations": ["presentation", "conference", "slides"],
    "Corporate Governance Documents": ["policy", "charter", "governance"],
    "Press Releases": ["announcement", "merger", "leadership"],
    "Stock Market Information": ["stock price", "dividend", "shareholder"],
    "Corporate Social Responsibility (CSR) Reports": ["sustainability", "ESG", "community"]
}

# --------------------- Classification function --------------------

def classify_document(text):
    """
    Classifies a text chunk into a category based on the presence of predefined keywords.
    Returns the first matching category or 'Unknown' if none match.
    """
    for category, keywords in CATEGORIES.items():
        if any(keyword.lower() in text.lower() for keyword in keywords):
            return category
    return "Unknown"

# --------------------- Fetch documents ---------------------------

def fetch_documents(urls, save_folder='documents'):
    """
    Downloads documents from the given URLs and saves them locally.
    You can add retry logic here if desired.
    Returns a list of local file paths.
    """
    if not os.path.exists(save_folder):
        os.makedirs(save_folder)

    local_paths = []

    for url in urls:
        # If there's a known PPT URL from Microsoft
        if 'microsoft.com' in url and 'SlidesFY25Q2' in url:
            filename = 'SlidesFY25Q2.pptx'
        else:
            # Derive a filename
            filename = url.split('/')[-1].split('?')[0]
            if not filename.endswith('.pdf') and not filename.endswith('.pptx'):
                filename += '.pdf'  # fallback if no clear extension

        response = requests.get(url, stream=True)
        # Check if the request was successful

        if response.status_code == 200:
            filepath = os.path.join(save_folder, filename)
            with open(filepath, 'wb') as f:
                # Write the content to a file in chunks
                # This is useful for large files to avoid memory issues
                # and to show progress
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            print(f"Downloaded: {filename}")
            local_paths.append(filepath)
        else:
            print(f"Failed to download {url} (status: {response.status_code})")

    return local_paths

# --------------------- Parse a single file ------------------------

def parse_file(filepath, parser):
    """
    Uses the Llama-based parser to parse a single file and return
    the resulting doc objects (containing text and metadata).
    """
    # doc_type, etc., could be inferred if needed
    try:
        llama_docs = parser.load_data(filepath)
        return llama_docs  # list of Document objects
    except Exception as e:
        print(f"Failed to parse {filepath}: {e}")
        return []

# --------------------- Chunking logic ----------------------------

def chunk_data(documents, splitter):
    """
    Takes a list of document objects (each containing .text, .metadata)
    and splits each document into chunks. Each chunk is classified and
    returned as a dictionary with the relevant metadata.
    """
    all_chunks = []

    for doc in documents:
        content = doc.text
        # Extract metadata
        # Assuming metadata is a dictionary with keys like 'page', 'source', etc.
        page_num = doc.metadata.get('page', 0)
        source = doc.metadata.get('source', 'unknown')
        doc_type = doc.metadata.get('doc_type', 'pdf')  # or derive programmatically

        # Perform the actual splitting
        chunks = splitter.split_text(content)

        for chunk in chunks:
            chunk_id = str(uuid.uuid4())
            content_type = 'table' if '|' in chunk else 'text'
            category = classify_document(chunk)

            chunk_obj = {
                "chunk_id": chunk_id,
                "content": chunk,
                "metadata": {
                    "source": source,
                    "page_num": page_num,
                    "doc_type": doc_type,
                    "content_type": content_type,
                    "category": category
                }
            }
            all_chunks.append(chunk_obj)

    return all_chunks

# --------------------- The main pipeline -------------------------

def main():
    # 1) Load environment, etc.
    load_dotenv()
    nest_asyncio.apply()
    # Set up Llama Cloud API key, has free tier
    LLAMA_CLOUD_API_KEY = os.getenv("LLAMA_CLOUD_API_KEY")

    # 2) Initialize parser and text splitter
    parser = LlamaParse(result_type="markdown")
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=200
    )

    # 3) Define the URLs to fetch
    urls = [
        "https://cdn-dynmedia-1.microsoft.com/is/content/microsoftcorp/SlidesFY25Q2",
        "https://digitalassets.tesla.com/tesla-contents/image/upload/IR/TSLA-Q4-2024-Update.pdf",
        "https://s2.q4cdn.com/470004039/files/doc_earnings/2025/q1/filing/10Q-Q1-2025-as-filed.pdf",
        "https://www.apple.com/newsroom/pdfs/fy2025-q1/FY25_Q1_Consolidated_Financial_Statements.pdf",
        "https://s2.q4cdn.com/470004039/files/doc_financials/2021/q4/_10-K-2021-(As-Filed).pdf"
    ]

    # 4) Fetch documents and get local file paths
    local_paths = fetch_documents(urls)

    # 5) Parse each file and chunk the results
    output_jsonl = 'output.jsonl'
    with open(output_jsonl, 'w', encoding='utf-8') as jsonl_file:
        for filepath in local_paths:
            # We can add 'doc_type' to metadata, etc.:
            doc_type = 'ppt' if filepath.lower().endswith('.pptx') else 'pdf'

            # Step (a) parse the file into doc objects
            docs = parse_file(filepath, parser)

            # Because the Llama parser might not automatically set source/doc_type, 
            # inject them into doc.metadata:
            for d in docs:
                d.metadata['source'] = os.path.basename(filepath)
                d.metadata['doc_type'] = doc_type

            # Step (b) chunk the doc objects
            chunks = chunk_data(docs, text_splitter)

            # Step (c) write out the chunk data to JSONL
            for c in chunks:
                jsonl_file.write(json.dumps(c, ensure_ascii=False) + '\n')

    print(f"Processing complete. Chunks written to {output_jsonl}")

if __name__ == "__main__":
    main()
# This is a standalone script. You can run it directly.
# Ensure you have the required packages installed: pip install -r requirements.txt
# You can also run this in a Jupyter notebook or similar environment.

