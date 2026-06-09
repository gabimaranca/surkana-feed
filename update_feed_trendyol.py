import pandas as pd
import xml.etree.ElementTree as ET
import re
import sys

sys.stdout.reconfigure(encoding='utf-8')

TRENDYOL_EXCEL = r"C:\Users\gabri\Downloads\Products_03.06.2026-11.42.xlsx"
FEED_IN        = r"C:\Users\gabri\ClaudeWorkspace\Skroutz\skroutz_feed_trendyol.xml"
FEED_OUT       = r"C:\Users\gabri\ClaudeWorkspace\Skroutz\skroutz_feed_trendyol.xml"
MERCHANT_ID    = "1161950"

# --- 1. Citeste exportul Trendyol ---
df = pd.read_excel(TRENDYOL_EXCEL, sheet_name=0, dtype={"Cod de bare": str})
df["Cod de bare"] = df["Cod de bare"].str.strip()

def clean_trendyol_url(raw_url):
    """Extrage product ID si construieste URL curat cu merchantId."""
    if pd.isna(raw_url):
        return None
    m = re.search(r'-p-(\d+)', str(raw_url))
    if m:
        pid = m.group(1)
        return f"https://www.trendyol.com/ro/surkana/x-p-{pid}?merchantId={MERCHANT_ID}"
    return str(raw_url)

# Construieste dict EAN -> date Trendyol
trendyol = {}
for _, row in df.iterrows():
    ean = row["Cod de bare"]
    images = [str(row[f"Imagine {i}"]).strip()
              for i in range(1, 9)
              if pd.notna(row.get(f"Imagine {i}"))]
    trendyol[ean] = {
        "link":   clean_trendyol_url(row.get("Link trendyol.com")),
        "images": images,
        "stock":  int(row["Stoc"]) if pd.notna(row.get("Stoc")) else 0,
    }

# --- 2. Actualizeaza XML ---
ET.register_namespace("", "")
tree = ET.parse(FEED_IN)
root = tree.getroot()

updated = 0
no_match = 0

for product in root.findall(".//product"):
    ean_el = product.find("ean")
    if ean_el is None:
        continue
    ean = ean_el.text.strip() if ean_el.text else ""

    # Availability - valoare acceptata de Skroutz
    avail_el = product.find("availability")
    if avail_el is not None:
        avail_el.text = "In Stock"

    data = trendyol.get(ean)
    if not data:
        no_match += 1
        continue

    # Link
    link_el = product.find("link")
    if link_el is not None and data["link"]:
        link_el.text = data["link"]

    # Imagine principala
    images = data["images"]
    if images:
        img_el = product.find("image")
        if img_el is not None:
            img_el.text = images[0]

        # Imagini aditionale
        add_el = product.find("additional_imageurl")
        if add_el is not None:
            product.remove(add_el)
        if len(images) > 1:
            add_el = ET.SubElement(product, "additional_imageurl")
            for img_url in images[1:]:
                ai = ET.SubElement(add_el, "additional_image")
                ai.text = img_url

    # Stock Y/N
    instock_el = product.find("instock")
    if instock_el is not None:
        instock_el.text = "Y" if data["stock"] > 0 else "N"

    # Quantity - camp numeric cerut de Skroutz
    qty_el = product.find("quantity")
    if qty_el is None:
        qty_el = ET.SubElement(product, "quantity")
    qty_el.text = str(data["stock"])

    updated += 1

print(f"Actualizate: {updated} produse")
print(f"Fara match:  {no_match} produse")

# --- 3. Salveaza XML cu CDATA pentru campurile text ---
raw_xml = ET.tostring(root, encoding="unicode", xml_declaration=False)

# Rewrap text fields in CDATA
cdata_tags = ["name", "link", "image", "additional_image", "category",
              "description", "manufacturer"]
def unescape(text):
    return (text.replace("&amp;", "&")
                .replace("&lt;", "<")
                .replace("&gt;", ">")
                .replace("&quot;", '"')
                .replace("&apos;", "'"))

for tag in cdata_tags:
    raw_xml = re.sub(
        rf'<{tag}>([^<]+)</{tag}>',
        lambda m, t=tag: f'<{t}><![CDATA[{unescape(m.group(1))}]]></{t}>',
        raw_xml
    )

with open(FEED_OUT, "w", encoding="utf-8") as f:
    f.write('<?xml version="1.0" encoding="UTF-8"?>\n')
    f.write(raw_xml)

print(f"\nFeed salvat: {FEED_OUT}")
