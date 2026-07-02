import pandas as pd
import fitz

# 1. Create a sample TXT
with open("sample.txt", "w") as f:
    f.write("Contact: test@proteccio.com. Phone: 9876543210. PAN: ABCDE1234F.")

# 2. Create a sample CSV
pd.DataFrame({
    "Name": ["Alice", "Bob"],
    "Email": ["alice@example.com", "bob@example.com"],
    "Employee_ID": ["EMP-001", "EMP-002"]
}).to_csv("sample.csv", index=False)

# 3. Create a sample PDF
doc = fitz.open()
page = doc.new_page()
page.insert_text((50, 50), "Confidential Document.\nBank account no: 123456789012, IFSC: SBIN0001234")
doc.save("sample.pdf")
doc.close()

print("Successfully created sample.txt, sample.csv, and sample.pdf!")