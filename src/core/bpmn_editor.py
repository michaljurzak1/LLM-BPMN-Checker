from lxml import etree
from typing import Dict, List, Optional, Any
import uuid


class BPMNEditor:
    def __init__(self, file_path: str):
        """Initialize BPMN editor with a file path."""
        self.file_path = file_path
        self.tree = etree.parse(file_path)
        self.root = self.tree.getroot()
        self.namespaces = {
            "bpmn": "http://www.omg.org/spec/BPMN/20100524/MODEL",
            "bpmndi": "http://www.omg.org/spec/BPMN/20100524/DI",
            "dc": "http://www.omg.org/spec/DD/20100524/DC",
            "di": "http://www.omg.org/spec/DD/20100524/DI",
        }
        # Track changes for highlighting
        self.changes = {"added": set(), "modified": set(), "removed": set()}

    def save(self, file_path: Optional[str] = None) -> None:
        """Save the BPMN file."""
        save_path = file_path or self.file_path
        self.tree.write(save_path, encoding="UTF-8", xml_declaration=True)

    def add_tasks(self, tasks: List[Dict[str, Any]]) -> List[str]:
        """Add multiple tasks to the BPMN diagram.

        Args:
            tasks: List of task dictionaries, each containing:
                - name: Task name
                - lane_id: Optional lane ID
                - position: Optional dict with x, y coordinates

        Returns:
            List of created task IDs
        """
        task_ids = []
        process = self.root.find(".//bpmn:process", self.namespaces)
        if process is None:
            raise ValueError("No process element found in BPMN file")

        for task_info in tasks:
            task_id = f"Task_{str(uuid.uuid4())[:8]}"
            task_ids.append(task_id)

            task = etree.SubElement(process, f"{{{self.namespaces['bpmn']}}}task")
            task.set("id", task_id)
            task.set("name", task_info["name"])
            # Add tag for highlighting
            task.set("data-element-status", "added")
            self.changes["added"].add(task_id)

            if "lane_id" in task_info and task_info["lane_id"]:
                lane = self.root.find(
                    f'.//bpmn:lane[@id="{task_info["lane_id"]}"]', self.namespaces
                )
                if lane is not None:
                    flow_node_ref = etree.SubElement(
                        lane, f"{{{self.namespaces['bpmn']}}}flowNodeRef"
                    )
                    flow_node_ref.text = task_id

            if "position" in task_info and task_info["position"]:
                bpmn_shape = self.root.find(".//bpmndi:BPMNPlane", self.namespaces)
                if bpmn_shape is not None:
                    shape = etree.SubElement(
                        bpmn_shape, f"{{{self.namespaces['bpmndi']}}}BPMNShape"
                    )
                    shape.set("id", f"{task_id}_di")
                    shape.set("bpmnElement", task_id)
                    # Add tag for highlighting
                    shape.set("data-element-status", "added")

                    bounds = etree.SubElement(
                        shape, f"{{{self.namespaces['dc']}}}Bounds"
                    )
                    bounds.set("x", str(task_info["position"].get("x", 0)))
                    bounds.set("y", str(task_info["position"].get("y", 0)))
                    bounds.set("width", "100")
                    bounds.set("height", "80")

        return task_ids

    # def add_task(
    #     self,
    #     name: str,
    #     lane_id: Optional[str] = None,
    #     position: Optional[Dict[str, float]] = None,
    # ) -> str:
    #     """Add a single task to the BPMN diagram."""
    #     task_info = {"name": name, "lane_id": lane_id, "position": position}
    #     return self.add_tasks([task_info])[0]

    def remove_nodes(self, node_ids: List[str]) -> None:
        """Remove multiple nodes from the BPMN diagram.
        
        This function handles removal of nodes and their nested elements properly.
        It will:
        1. Remove the node from its parent element
        2. Remove any references to the node in lanes
        3. Remove associated shapes and edges
        4. Handle nested elements like event definitions
        """
        process = self.root.find(".//bpmn:process", self.namespaces)
        if process is None:
            raise ValueError("No process element found in BPMN file")

        for node_id in node_ids:
            # Add to removed changes before removing
            self.changes["removed"].add(node_id)

            # Find the node anywhere in the document
            node = self.root.find(f'.//*[@id="{node_id}"]')
            if node is not None:
                # Add tag for highlighting before removing
                node.set("data-element-status", "removed")
                
                # Get the parent element
                parent = node.getparent()
                if parent is not None:
                    # Remove the node from its parent
                    parent.remove(node)
                    
                    # If this was an event, also remove any event definitions
                    if node.tag.endswith('Event'):
                        # Find and remove any event definitions
                        for event_def in self.root.findall(f'.//*[@id="{node_id}"]//*', self.namespaces):
                            if event_def.getparent() is not None:
                                event_def.getparent().remove(event_def)

            # Remove from lanes
            for lane in self.root.findall(".//bpmn:lane", self.namespaces):
                for flow_node_ref in lane.findall(".//bpmn:flowNodeRef", self.namespaces):
                    if flow_node_ref.text == node_id:
                        lane.remove(flow_node_ref)

            # Remove shape and any associated edges
            shape = self.root.find(f'.//bpmndi:BPMNShape[@bpmnElement="{node_id}"]', self.namespaces)
            if shape is not None:
                shape.set("data-element-status", "removed")
                shape.getparent().remove(shape)

            # Remove any edges connected to this node
            for edge in self.root.findall(".//bpmndi:BPMNEdge", self.namespaces):
                if edge.get("bpmnElement") is not None:
                    flow = self.root.find(f'.//*[@id="{edge.get("bpmnElement")}"]')
                    if flow is not None and (flow.get("sourceRef") == node_id or flow.get("targetRef") == node_id):
                        # Remove the edge
                        edge.getparent().remove(edge)
                        # Remove the flow
                        flow.getparent().remove(flow)

    # def remove_node(self, node_id: str) -> None:
    #     """Remove a single node from the BPMN diagram."""
    #     self.remove_nodes([node_id])

    def edit_nodes(self, node_updates: List[Dict[str, str]]) -> None:
        """Edit multiple nodes in the BPMN diagram.

        Args:
            node_updates: List of dictionaries containing:
                - node_id: ID of the node to edit
                - new_name: New name for the node
        """
        for update in node_updates:
            node = self.root.find(f'.//*[@id="{update["node_id"]}"]')
            if node is not None:
                node.set("name", update["new_name"])
                # Add tag for highlighting
                node.set("data-element-status", "modified")
                self.changes["modified"].add(update["node_id"])

    # def edit_node(self, node_id: str, new_name: str) -> None:
    #     """Edit a single node's name in the BPMN diagram."""
    #     self.edit_nodes([{"node_id": node_id, "new_name": new_name}])

    def add_sequence_flows(self, flows: List[Dict[str, str]]) -> List[str]:
        """Add multiple sequence flows between nodes.

        Args:
            flows: List of flow dictionaries, each containing:
                - source_id: Source node ID
                - target_id: Target node ID

        Returns:
            List of created flow IDs
        """
        flow_ids = []
        process = self.root.find(".//bpmn:process", self.namespaces)
        if process is None:
            raise ValueError("No process element found in BPMN file")

        bpmn_plane = self.root.find(".//bpmndi:BPMNPlane", self.namespaces)

        for flow_info in flows:
            flow_id = f"Flow_{str(uuid.uuid4())[:8]}"
            flow_ids.append(flow_id)

            flow = etree.SubElement(
                process, f"{{{self.namespaces['bpmn']}}}sequenceFlow"
            )
            flow.set("id", flow_id)
            flow.set("sourceRef", flow_info["source_id"])
            flow.set("targetRef", flow_info["target_id"])
            # Add tag for highlighting
            flow.set("data-element-status", "added")
            self.changes["added"].add(flow_id)

            if bpmn_plane is not None:
                edge = etree.SubElement(
                    bpmn_plane, f"{{{self.namespaces['bpmndi']}}}BPMNEdge"
                )
                edge.set("id", f"{flow_id}_di")
                edge.set("bpmnElement", flow_id)
                # Add tag for highlighting
                edge.set("data-element-status", "added")

        return flow_ids

    # def add_sequence_flow(self, source_id: str, target_id: str) -> str:
    #     """Add a single sequence flow between two nodes."""
    #     flow_info = {"source_id": source_id, "target_id": target_id}
    #     return self.add_sequence_flows([flow_info])[0]

    def get_node_info(self, node_id: str) -> Dict[str, Any]:
        """Get information about a specific node."""
        node = self.root.find(f'.//*[@id="{node_id}"]')
        if node is None:
            raise ValueError(f"Node with ID {node_id} not found")

        info = {
            "id": node_id,
            "type": node.tag.split("}")[-1],
            "name": node.get("name", ""),
            "status": node.get("data-element-status", ""),
        }

        # Get lane information
        lane = self.root.find(
            f'.//bpmn:lane[bpmn:flowNodeRef="{node_id}"]', self.namespaces
        )
        if lane is not None:
            info["lane"] = lane.get("name", "")
            info["lane_id"] = lane.get("id", "")

        return info

    def get_all_nodes(self) -> List[Dict[str, Any]]:
        """Get information about all nodes in the diagram."""
        nodes = []
        process = self.root.find(".//bpmn:process", self.namespaces)
        if process is None:
            raise ValueError("No process element found in BPMN file")

        for node in process.findall(".//*[@id]"):
            node_id = node.get("id")
            if node_id:
                try:
                    nodes.append(self.get_node_info(node_id))
                except ValueError:
                    continue

        return nodes

    def get_changes(self) -> Dict[str, set]:
        """Get the current changes tracked in the diagram."""
        return self.changes
