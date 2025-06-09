import os
from pathlib import Path
from app import create_visualization
import json

# Directories
original_dir = r"D:\University\Modelowanie biznesowe\LLM-BPMN-Checker\data\raw\archives\Error Models\BPMN_Error_Tasks_and_Fixes\XML"
actual_dir = (
    r"D:\University\Modelowanie biznesowe\LLM-BPMN-Checker\src\llm_fix\actual_issues"
)
detected_dir = (
    r"D:\University\Modelowanie biznesowe\LLM-BPMN-Checker\src\llm_fix\detected_issues"
)

# Output HTML
output_html = "bpmn_comparison_dynamic.html"

# Find common files
original_files = set(f for f in os.listdir(original_dir) if f.endswith(".bpmn"))
actual_files = set(f for f in os.listdir(actual_dir) if f.endswith(".bpmn"))
detected_files = set(f for f in os.listdir(detected_dir) if f.endswith(".bpmn"))

common_files = sorted(list(original_files & actual_files & detected_files))

# Pre-generate all visualizations and store their paths
viz_map = {}
for fname in common_files:
    orig_path = os.path.join(original_dir, fname)
    act_path = os.path.join(actual_dir, fname)
    det_path = os.path.join(detected_dir, fname)
    orig_viz = create_visualization(orig_path)
    act_viz = create_visualization(act_path)
    det_viz = create_visualization(det_path)
    viz_map[fname] = {
        "original": orig_viz.replace("\\", "/"),
        "actual": act_viz.replace("\\", "/"),
        "detected": det_viz.replace("\\", "/"),
    }

# JSON for JS
viz_map_json = json.dumps(viz_map)

html = f"""
<html>
<head>
    <title>BPMN Comparison (Dynamic)</title>
    <style>
        body {{ font-family: Arial, sans-serif; }}
        .container {{ display: flex; flex-direction: column; align-items: center; }}
        .dropdown-row {{ margin: 20px 0; }}
        .compare-row {{ display: flex; flex-direction: row; justify-content: center; gap: 20px; }}
        .viz-col {{ display: flex; flex-direction: column; align-items: center; }}
        iframe {{ border: 1px solid #ccc; margin-bottom: 8px; }}
        h4 {{ margin: 0 0 8px 0; }}
        .filename-label {{ margin-top: 10px; font-weight: bold; font-size: 1.1em; }}
    </style>
</head>
<body>
    <div class="container">
        <h2>BPMN Model Comparison (Original vs Actual Issue vs Detected Issue)</h2>
        <div class="dropdown-row">
            <label for="fileSelect">Choose BPMN file: </label>
            <select id="fileSelect">
                {''.join([f'<option value="{fname}">{fname}</option>' for fname in common_files])}
            </select>
        </div>
        <div class="compare-row">
            <div class="viz-col">
                <h4>Original</h4>
                <iframe id="origFrame" src="" width="400" height="600"></iframe>
            </div>
            <div class="viz-col">
                <h4>Actual Issue</h4>
                <iframe id="actFrame" src="" width="400" height="600"></iframe>
            </div>
            <div class="viz-col">
                <h4>Detected Issue</h4>
                <iframe id="detFrame" src="" width="400" height="600"></iframe>
            </div>
        </div>
        <div class="filename-label" id="filenameLabel"></div>
    </div>
    <script>
        const vizMap = {viz_map_json};
        const fileSelect = document.getElementById('fileSelect');
        const origFrame = document.getElementById('origFrame');
        const actFrame = document.getElementById('actFrame');
        const detFrame = document.getElementById('detFrame');
        const filenameLabel = document.getElementById('filenameLabel');

        function updateFrames(fname) {{
            const v = vizMap[fname];
            if (v) {{
                origFrame.src = 'file:///' + v.original;
                actFrame.src = 'file:///' + v.actual;
                detFrame.src = 'file:///' + v.detected;
                filenameLabel.textContent = fname;
            }}
        }}
        fileSelect.addEventListener('change', function() {{
            updateFrames(this.value);
        }});
        // Initialize with first file
        if (fileSelect.value) {{
            updateFrames(fileSelect.value);
        }}
    </script>
</body>
</html>
"""

with open(output_html, "w", encoding="utf-8") as f:
    f.write(html)

print(f"Dynamic comparison HTML generated: {output_html}")
