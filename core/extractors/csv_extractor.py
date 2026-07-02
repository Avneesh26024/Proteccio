import pandas as pd
import os

def extract(path: str) -> dict:
    """Extracts a structured summary from a CSV file."""
    if not os.path.exists(path):
        raise FileNotFoundError(f"File not found: {path}")

    # Read the CSV
    df = pd.read_csv(path)
    rows, cols = df.shape
    col_names = df.columns.tolist()

    # 1. Dataset Overview
    overview = (
        "Dataset Overview:\n"
        f"- Rows: {rows}, Columns: {cols}\n"
        f"- Column Names: {', '.join(col_names)}\n"
    )

    # 2. Column Details
    details = ["\nColumn Details:"]
    for col in col_names:
        # Grab up to 5 non-null samples
        samples = df[col].dropna().astype(str).head(5).tolist()
        samples_str = ", ".join(samples) if samples else "None"
        details.append(f"- {col} ({df[col].dtype}): sample values: {samples_str}")

    # 3. Raw Data Sample
    raw_sample = f"\nRaw Data Sample (first 10 rows):\n{df.head(10).to_string()}"

    # Compile the final formatted string
    full_text = overview + "\n".join(details) + "\n" + raw_sample

    return {
        "text": full_text,
        "metadata": {
            "file_name": os.path.basename(path),
            "row_count": rows,
            "column_count": cols,
            "columns": col_names
        }
    }

if __name__ == "__main__":
    # Test script - will create a dummy CSV file to test
    test_file = "test_sample.csv"
    dummy_data = {
        "user_id": [1, 2, 3],
        "email": ["alice@example.com", "bob@example.com", "charlie@example.com"],
        "score": [95.5, None, 88.0]
    }
    pd.DataFrame(dummy_data).to_csv(test_file, index=False)

    print(f"Testing CSV Extractor on '{test_file}'...")
    result = extract(test_file)
    print("Success! Metadata:")
    print(result["metadata"])
    print("\nExtracted String Summary:")
    print(result["text"])
    
    # Cleanup
    os.remove(test_file)