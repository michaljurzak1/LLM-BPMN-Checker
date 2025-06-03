from typing import Optional, List, Dict, Any
from langchain.tools import tool
from pydantic import BaseModel, Field
from src.core.bpmn_editor import BPMNEditor
import tempfile
import shutil
import os
import base64
from html2image import Html2Image # Configure logging with minimal format and INFO level


class BPMNEditorInput(BaseModel):
    """Input schema for BPMN editing tools."""

    file_path: str = Field(..., description="Path to the BPMN file")
    tasks: Optional[List[Dict[str, Any]]] = Field(
        None,
        description="List of tasks to add, each containing name, optional lane_id, and optional position",
    )
    node_ids: Optional[List[str]] = Field(
        None, description="List of node IDs to remove"
    )
    node_updates: Optional[List[Dict[str, str]]] = Field(
        None, description="List of node updates, each containing node_id and new_name"
    )
    flows: Optional[List[Dict[str, str]]] = Field(
        None,
        description="List of flows to add, each containing source_id and target_id",
    )
    node_id: Optional[str] = Field(
        None, description="ID of a single node to get info about"
    )


class BPMNTools:
    def __init__(self, filepath: str, agent_history: Optional[List] = None):
        self.original_filepath = filepath
        self.temp_dir = tempfile.mkdtemp()
        self.temp_filepath = os.path.join(self.temp_dir, "temp_bpmn.bpmn")
        # Copy original file to temp location
        shutil.copy2(filepath, self.temp_filepath)
        
        try:
            self.editor = BPMNEditor(self.temp_filepath)
        except Exception as e:
            raise
        
        self.agent_history = agent_history
        self.tools = self._create_tools()
        self.changes = {
            "added": [],
            "edited": [],
            "removed": []
        }
        # Initialize ID mapping
        self._init_id_mapping()

    def _init_id_mapping(self):
        """Initialize mapping between internal IDs and simplified IDs."""
        self.id_mapping = {}
        self.reverse_mapping = {}
        self.type_counters = {}
        
        # Get all nodes and create simplified IDs
        nodes = self.editor.get_all_nodes()
        for node in nodes:
            node_type = node['type']
            if node_type not in self.type_counters:
                self.type_counters[node_type] = 0
            self.type_counters[node_type] += 1
            
            # Create simplified ID (e.g., "task_1", "gateway_2", etc.)
            simplified_id = f"{node_type}_{self.type_counters[node_type]}"
            self.id_mapping[node['id']] = simplified_id
            self.reverse_mapping[simplified_id] = node['id']

    def _convert_to_simplified_ids(self, data: Any) -> Any:
        """Convert internal IDs to simplified IDs in the data structure."""
        if isinstance(data, dict):
            return {k: self._convert_to_simplified_ids(v) for k, v in data.items()}
        elif isinstance(data, list):
            return [self._convert_to_simplified_ids(item) for item in data]
        elif isinstance(data, str) and data in self.id_mapping:
            return self.id_mapping[data]
        return data

    def _convert_to_internal_ids(self, data: Any) -> Any:
        """Convert simplified IDs back to internal IDs in the data structure."""
        if isinstance(data, dict):
            return {k: self._convert_to_internal_ids(v) for k, v in data.items()}
        elif isinstance(data, list):
            return [self._convert_to_internal_ids(item) for item in data]
        elif isinstance(data, str) and data in self.reverse_mapping:
            return self.reverse_mapping[data]
        return data

    def _create_tools(self) -> List[Any]:
        """Create LangChain tools for BPMN operations."""
        
        @tool("get_all_nodes")
        def get_all_nodes() -> str:
            """Get information about all nodes in a BPMN diagram."""
            nodes = self.editor.get_all_nodes()
            return str(self._convert_to_simplified_ids(nodes))

        @tool("get_bpmn_as_image")
        def get_bpmn_as_image() -> str:
            """Convert the current BPMN diagram to an image and append it as a human message.
            Returns a confirmation message that the image was added to the conversation.
            """
            try:
                # Create a temporary directory for the image if it doesn't exist
                temp_img_dir = os.path.join(self.temp_dir, "images")
                os.makedirs(temp_img_dir, exist_ok=True)
                
                # Generate image from the current BPMN file
                temp_img_path = os.path.join(temp_img_dir, "current_diagram.png")
                
                # Read the BPMN file content
                with open(self.temp_filepath, 'r', encoding='utf-8') as f:
                    bpmn_content = f.read()
                
                # Create HTML content using the bpmn_viewer template
                html_content = f"""
                <!DOCTYPE html>
                <html>
                <head>
                    <meta charset="UTF-8" />
                    <title>BPMN Viewer</title>
                    <link rel="stylesheet" href="https://unpkg.com/bpmn-js@11.5.0/dist/assets/bpmn-js.css" />
                    <style>
                        html, body, #canvas {{
                            height: 100%;
                            margin: 0;
                            padding: 0;
                            overflow: hidden;
                        }}
                        #canvas {{
                            width: 100%;
                            height: 100%;
                        }}
                        .djs-element.highlight-added .djs-visual > * {{
                            stroke: #90ee90 !important;
                            stroke-width: 4px !important;
                        }}
                        .djs-element.highlight-edited .djs-visual > * {{
                            stroke: #add8e6 !important;
                            stroke-width: 4px !important;
                        }}
                        .djs-element.highlight-removed .djs-visual > * {{
                            stroke: #ffb6c1 !important;
                            stroke-width: 4px !important;
                        }}
                        #error-message {{
                            color: red;
                            padding: 10px;
                            margin: 10px;
                            border: 1px solid red;
                            display: none;
                        }}
                    </style>
                </head>
                <body>
                    <div id="error-message"></div>
                    <div id="canvas"></div>

                    <script src="https://unpkg.com/bpmn-js@11.5.0/dist/bpmn-viewer.development.js"></script>
                    <script>
                        const viewer = new BpmnJS({{
                            container: "#canvas",
                            keyboard: {{
                                bindTo: window,
                            }},
                        }});

                        function showError(message) {{
                            const errorDiv = document.getElementById("error-message");
                            errorDiv.textContent = message;
                            errorDiv.style.display = "block";
                            console.error(message);
                        }}

                        async function loadDiagram(bpmnXML) {{
                            try {{
                                document.getElementById("error-message").style.display = "none";
                                await viewer.importXML(bpmnXML);
                                viewer.get("canvas").zoom("fit-viewport");
                                viewer.on("error", function (event) {{
                                    showError("Error in BPMN viewer: " + event.error.message);
                                }});
                            }} catch (err) {{
                                showError("Error rendering BPMN diagram: " + err.message);
                            }}
                        }}

                        window.addEventListener("error", function (event) {{
                            if (event.target.tagName === "SCRIPT") {{
                                showError("Error loading BPMN-js library: " + event.message);
                            }}
                        }}, true);

                        // Load the BPMN content
                        loadDiagram(`{bpmn_content}`);
                    </script>
                </body>
                </html>
                """
                
                # Save HTML content to a temporary file
                temp_html_path = os.path.join(temp_img_dir, "temp.html")
                with open(temp_html_path, 'w', encoding='utf-8') as f:
                    f.write(html_content)
                
                # Use html2image to convert HTML to image
                hti = Html2Image()
                hti.output_path = temp_img_dir
                
                hti.screenshot(
                    html_file=temp_html_path,
                    save_as="current_diagram.png",
                    size=(800, 600)
                )
                
                # Read the image file and convert to base64
                with open(temp_img_path, "rb") as image_file:
                    image_data = base64.b64encode(image_file.read()).decode("utf-8")
                
                # Create the multimodal message
                multimodal_message = {
                    "type": "image",
                    "source_type": "base64",
                    "mime_type": "image/png",
                    "data": image_data
                }
                
                # Only append to history if it exists
                if self.agent_history is not None:
                    from langchain_core.messages import HumanMessage
                    self.agent_history.append(HumanMessage(content=[{"type": "text", "text": "Here is the current BPMN diagram:"}, multimodal_message]))
                    return "BPMN diagram has been added to the conversation as an image."
                
                return "BPMN diagram has been converted to an image successfully."
                    
            except Exception as e:
                return f"Error converting BPMN diagram to image: {str(e)}"

        @tool("add_tasks")
        def add_tasks(tasks: List[Dict[str, Any]]) -> str:
            """Add multiple tasks to a BPMN diagram.
            
            Args:
                tasks: List of tasks to add, each containing name, optional lane_id, and optional position
            """
            if not tasks:
                raise ValueError("At least one task is required")
            internal_tasks = self._convert_to_internal_ids(tasks)
            task_ids = self.editor.add_tasks(internal_tasks)
            self.editor.save()
            simplified_ids = [self.id_mapping.get(id, id) for id in task_ids]
            self.changes["added"].extend(simplified_ids)
            return f"Added {len(task_ids)} tasks with IDs: {', '.join(simplified_ids)}"

        @tool("remove_nodes")
        def remove_nodes(node_ids: List[str]) -> str:
            """Remove multiple nodes from a BPMN diagram.
            
            Args:
                node_ids: List of node IDs to remove
            """
            if not node_ids:
                raise ValueError("At least one node ID is required")
            internal_ids = self._convert_to_internal_ids(node_ids)
            self.editor.remove_nodes(internal_ids)
            self.editor.save()
            self.changes["removed"].extend(node_ids)
            return f"Removed {len(node_ids)} nodes with IDs: {', '.join(node_ids)}"

        @tool("edit_nodes")
        def edit_nodes(node_updates: List[Dict[str, str]]) -> str:
            """Edit multiple nodes' names in a BPMN diagram.
            
            Args:
                node_updates: List of node updates, each containing node_id and new_name
            """
            if not node_updates:
                raise ValueError("At least one node update is required")
            internal_updates = self._convert_to_internal_ids(node_updates)
            self.editor.edit_nodes(internal_updates)
            self.editor.save()
            edited_ids = [update["node_id"] for update in node_updates]
            self.changes["edited"].extend(edited_ids)
            return f"Updated {len(node_updates)} nodes"

        @tool("add_sequence_flows")
        def add_sequence_flows(flows: List[Dict[str, str]]) -> str:
            """Add multiple sequence flows between nodes in a BPMN diagram.
            
            Args:
                flows: List of flows to add, each containing source_id and target_id
            """
            if not flows:
                raise ValueError("At least one flow is required")
            internal_flows = self._convert_to_internal_ids(flows)
            flow_ids = self.editor.add_sequence_flows(internal_flows)
            self.editor.save()
            self.changes["added"].extend([self.id_mapping.get(id, id) for id in flow_ids])
            return f"Added {len(flow_ids)} sequence flows with IDs: {', '.join(self._convert_to_simplified_ids(flow_ids))}"

        @tool("get_node_info")
        def get_node_info(node_id: str) -> str:
            """Get information about a specific node in a BPMN diagram.
            
            Args:
                node_id: ID of a single node to get info about
            """
            if not node_id:
                raise ValueError("Node ID is required")
            internal_id = self._convert_to_internal_ids(node_id)
            node_info = self.editor.get_node_info(internal_id)
            return str(self._convert_to_simplified_ids(node_info))

        # Create tool instances with access to the editor
        tools_ = [
            get_all_nodes,
            add_tasks,
            remove_nodes,
            edit_nodes,
            add_sequence_flows,
            get_node_info,
            get_bpmn_as_image
        ]

        return tools_

    def get_tools(self) -> List[Any]:
        """Get the list of available tools."""
        return self.tools

    def get_changes(self) -> Dict[str, List[str]]:
        """Get the tracked changes for highlighting."""
        return self.changes

    def apply_changes(self) -> None:
        """Apply the changes to the original file."""
        shutil.copy2(self.temp_filepath, self.original_filepath)

    def discard_changes(self) -> None:
        """Discard changes and clean up temporary files."""
        shutil.rmtree(self.temp_dir)

    def __del__(self):
        """Cleanup temporary files when the object is destroyed."""
        try:
            shutil.rmtree(self.temp_dir)
        except (OSError, FileNotFoundError):
            pass

# def get_bpmn_tools() -> List[Any]:
#     """Get all BPMN editing tools."""
#     return [
#         add_tasks,
#         remove_nodes,
#         edit_nodes,
#         add_sequence_flows,
#         get_node_info,
#         get_all_nodes
#     ]
