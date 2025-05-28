import os
import json
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

class BPMNHighlighter:
    def __init__(self, html_template_path="bpmn_viewer.html"):
        """Initialize the BPMN highlighter with the path to the HTML template."""
        # Resolve the template path relative to the current file
        current_dir = Path(__file__).parent.parent.parent
        self.html_template_path = str(current_dir / html_template_path)
        self.colors = {
            "added": "#90EE90",  # Light green
            "edited": "#ADD8E6",  # Light blue
            "removed": "#FFB6C1",  # Light red
        }
        
        # Verify template exists
        if not Path(self.html_template_path).exists():
            raise FileNotFoundError(f"BPMN viewer template not found at: {self.html_template_path}")

    def _read_template(self):
        """Read the HTML template file."""
        try:
            with open(self.html_template_path, "r", encoding="utf-8") as f:
                return f.read()
        except Exception as e:
            logger.error(f"Error reading template file: {e}")
            raise

    def _write_template(self, content):
        """Write the modified HTML content back to the file."""
        try:
            with open(self.html_template_path, "w", encoding="utf-8") as f:
                f.write(content)
        except Exception as e:
            logger.error(f"Error writing template file: {e}")
            raise

    def _create_highlight_script(
        self, added_ids=None, edited_ids=None, removed_ids=None
    ):
        script = f"""
        <script>
        // Automated highlight logic (DOM manipulation, no UI)
        function highlightElement(elementId, color) {{
            const element = document.querySelector(`[data-element-id="${{elementId}}"]`);
            if (element) {{
                element.classList.add("highlighted-element");
                const svgElements = element.querySelectorAll("path, rect, circle, ellipse, polygon, polyline");
                svgElements.forEach((svgElement) => {{
                    svgElement.style.stroke = color;
                    if (
                        svgElement.tagName.toLowerCase() === "rect" ||
                        svgElement.tagName.toLowerCase() === "circle" ||
                        svgElement.tagName.toLowerCase() === "ellipse"
                    ) {{
                        svgElement.style.fill = color + "40"; // Add 40% opacity for fill
                    }}
                }});
            }}
        }}
        function autoHighlightElements() {{
            const highlights = {{
                added: {json.dumps(added_ids or [])},
                edited: {json.dumps(edited_ids or [])},
                removed: {json.dumps(removed_ids or [])}
            }};
            const statusColors = {{
                added: "{self.colors['added']}",
                edited: "{self.colors['edited']}",
                removed: "{self.colors['removed']}"
            }};
            setTimeout(() => {{
                for (const [status, ids] of Object.entries(highlights)) {{
                    if (ids && ids.length > 0) {{
                        ids.forEach(id => {{
                            highlightElement(id, statusColors[status]);
                        }});
                    }}
                }}
            }}, 300);
        }}
        viewer.on('import.done', function() {{
            autoHighlightElements();
        }});
        </script>
        """
        return script

    def highlight_elements(
        self,
        bpmn_file_path,
        added_ids=None,
        edited_ids=None,
        removed_ids=None,
        output_path=None,
        changes=None,
    ):
        """
        Create a modified version of the BPMN viewer with highlighted elements.

        Args:
            bpmn_file_path (str): Path to the BPMN file to load
            added_ids (list): List of element IDs that were added
            edited_ids (list): List of element IDs that were edited
            removed_ids (list): List of element IDs that were removed
            output_path (str): Path where to save the modified HTML file (optional)
            changes (dict): Dictionary containing changes with keys 'added', 'edited', 'removed'
        """
        try:
            # If changes dictionary is provided, use it to set the IDs
            if changes:
                added_ids = list(changes.get('added', []))
                edited_ids = list(changes.get('edited', []))
                removed_ids = list(changes.get('removed', []))

            # Read the template
            html_content = self._read_template()

            # Read the BPMN file content
            bpmn_path = Path(bpmn_file_path)
            if not bpmn_path.exists():
                raise FileNotFoundError(f"BPMN file not found: {bpmn_file_path}")
                
            with open(bpmn_path, "r", encoding="utf-8") as f:
                bpmn_content = f.read()

            # Insert the BPMN XML as a <script type="text/plain" id="bpmn-xml"> block before </body>
            bpmn_xml_block = (
                f'<script type="text/plain" id="bpmn-xml">\n{bpmn_content}\n</script>\n'
            )
            html_content = html_content.replace("</body>", bpmn_xml_block + "</body>")

            # Add a script to force-load the BPMN model on DOMContentLoaded
            force_load_script = """
            <script>
            window.addEventListener('DOMContentLoaded', function() {
                const bpmnXML = document.getElementById('bpmn-xml').textContent;
                loadDiagram(bpmnXML);
            });
            </script>
            """
            html_content = html_content.replace("</body>", force_load_script + "\n</body>")

            # Add the highlight script
            highlight_script = self._create_highlight_script(
                added_ids, edited_ids, removed_ids
            )
            html_content = html_content.replace("</body>", highlight_script + "\n</body>")

            # Add the required CSS for .highlighted-element
            highlight_css = """
            <style>
            .highlighted-element path,
            .highlighted-element rect,
            .highlighted-element circle,
            .highlighted-element ellipse,
            .highlighted-element polygon,
            .highlighted-element polyline {
                stroke-width: 3px !important;
            }
            .highlighted-element .djs-visual > rect,
            .highlighted-element .djs-visual > circle,
            .highlighted-element .djs-visual > ellipse,
            .highlighted-element .djs-visual > polygon,
            .highlighted-element .djs-visual > polyline {
                stroke-width: 3px !important;
            }
            .highlighted-element .djs-visual > path {
                stroke-width: 3px !important;
            }
            .highlighted-element .djs-visual > text {
                font-weight: bold !important;
            }
            </style>
            """
            html_content = html_content.replace("</head>", highlight_css + "\n</head>")

            # Write the modified content
            if output_path:
                output_path = Path(output_path)
                output_path.parent.mkdir(parents=True, exist_ok=True)
                with open(output_path, "w", encoding="utf-8") as f:
                    f.write(html_content)
            else:
                self._write_template(html_content)

            return str(output_path) if output_path else self.html_template_path
            
        except Exception as e:
            logger.error(f"Error in highlight_elements: {e}")
            raise


def main():
    # Example usage
    highlighter = BPMNHighlighter()

    # Example BPMN file path (relative to the HTML file)
    bpmn_file = "1_61cde83dea954a0a80b769e291a7a462 copy nowy.bpmn"

    # Example element IDs to highlight
    added_ids = ["sid-22E11990-8DDF-4F3B-B94F-D4E6A70D3ED8"]
    edited_ids = ["sid-EF8CECA3-8DAB-444B-8D2B-9FEC99FDE97E"]
    removed_ids = ["sid-D98CA1EA-B636-4820-A6B1-0EB30D4EAD58"]

    # Create the highlighted version
    output_file = highlighter.highlight_elements(
        bpmn_file,
        added_ids=added_ids,
        edited_ids=edited_ids,
        removed_ids=removed_ids,
        output_path="bpmn_viewer_highlighted_demo.html",
    )

    print(f"Created highlighted BPMN viewer at: {output_file}")


if __name__ == "__main__":
    main()
