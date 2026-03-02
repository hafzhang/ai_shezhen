"""
Extract Chinese text from tongue diagnosis images using RapidOCR
"""
import os
import sys
import json
from pathlib import Path
from rapidocr_onnxruntime import RapidOCR

# Set UTF-8 encoding for Windows console
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# Initialize OCR
ocr = RapidOCR()

# Images directory
images_dir = Path("C:/Users/Administrator/Desktop/shangzhan/ai_shezhen/images")

# Get all images
image_files = list(images_dir.glob("*.jpg")) + list(images_dir.glob("*.png")) + list(images_dir.glob("*.jpeg"))

print(f"Found {len(image_files)} images to process")

# Results storage
all_results = {}

for img_path in sorted(image_files):
    # Sanitize filename for display
    display_name = img_path.name.encode('ascii', 'replace').decode('ascii')
    print(f"\nProcessing: {display_name}")

    # Perform OCR
    result = ocr(str(img_path))

    # Debug: print result structure
    print(f"  Result type: {type(result)}, length: {len(result) if result else 0}")

    if result and len(result) >= 2:
        # RapidOCR returns (result, elapsed_time)
        # result format: [[bbox, text, confidence], ...] or [[bbox, text], ...]
        ocr_result = result[0] if isinstance(result[0], list) else []

        if not ocr_result:
            print(f"  No text detected (empty result)")
            all_results[img_path.name] = {
                "path": str(img_path),
                "full_text": "",
                "structured_lines": [],
                "raw_blocks": []
            }
            continue

        # Extract text from OCR result
        texts = []
        for item in ocr_result:
            if len(item) >= 2:
                texts.append(item[1])

        # Group by lines (similar Y coordinates)
        lines = []
        current_line = []
        last_y = None

        for item in ocr_result:
            if len(item) >= 2:
                bbox = item[0]
                text = item[1]

                # Get Y coordinate of the bounding box
                y = bbox[0][1]

                # If this is the first text or Y is close to last Y, add to current line
                if last_y is None or abs(y - last_y) < 20:
                    current_line.append((bbox[0][0], text))
                else:
                    # Sort by X and join
                    current_line.sort(key=lambda x: x[0])
                    lines.append(" ".join([t for _, t in current_line]))
                    current_line = [(bbox[0][0], text)]

                last_y = y

        # Add remaining line
        if current_line:
            current_line.sort(key=lambda x: x[0])
            lines.append(" ".join([t for _, t in current_line]))

        all_results[img_path.name] = {
            "path": str(img_path),
            "full_text": "\n".join(texts),
            "structured_lines": lines,
            "raw_blocks": [[box, txt] for box, txt, *_ in ocr_result]
        }

        print(f"  Extracted {len(texts)} text blocks, {len(lines)} lines")
        preview = texts[0][:50] if texts else ''
        print(f"  Preview: {preview.encode('ascii', 'replace').decode('ascii')}...")
    else:
        print(f"  No text detected")
        all_results[img_path.name] = {
            "path": str(img_path),
            "full_text": "",
            "structured_lines": [],
            "raw_blocks": []
        }

# Save to JSON
output_path = images_dir / "extracted_text.json"
with open(output_path, "w", encoding="utf-8") as f:
    json.dump(all_results, f, ensure_ascii=False, indent=2)

print(f"\n{'='*60}")
print(f"Extracted text saved to: {output_path}")

# Print summary
print(f"\n{'='*60}")
print("SUMMARY:")
print(f"{'='*60}")
for name, data in all_results.items():
    print(f"\n[{name}]")
    print(data["full_text"][:200] if data["full_text"] else "(No text)")
