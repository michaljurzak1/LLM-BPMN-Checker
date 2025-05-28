import unittest
import os
import tempfile
import shutil
from bpmn_editor import BPMNEditor

class TestBPMNEditor(unittest.TestCase):
    def setUp(self):
        # Create a temporary directory for testing
        self.temp_dir = tempfile.mkdtemp()
        self.test_file = os.path.join(self.temp_dir, "test.bpmn")
        
        # Copy the real BPMN model to the test directory
        shutil.copy("1_61cde83dea954a0a80b769e291a7a462 copy nowy.bpmn", self.test_file)
        
        self.editor = BPMNEditor(self.test_file)

    def tearDown(self):
        # Clean up temporary files
        shutil.rmtree(self.temp_dir)

    def test_modify_shipping_process(self):
        """Test modifying the shipping process in a business context."""
        # First, find the relevant tasks in the shipping process
        nodes = self.editor.get_all_nodes()
        shipping_tasks = [node for node in nodes if "shipping" in node["name"].lower()]
        
        # Add a new quality check task after shipping
        new_task = {
            "name": "Quality Check Before Dispatch",
            "position": {"x": 800, "y": 1400}  # Position after shipping task
        }
        task_id = self.editor.add_tasks([new_task])[0]
        
        # Connect the new task to the process flow
        # Find the shipping task and its outgoing flow
        shipping_task = next(node for node in nodes if "shipping" in node["name"].lower())
        self.editor.add_sequence_flows([{
            "source_id": shipping_task["id"],
            "target_id": task_id
        }])
        
        # Verify the changes
        nodes_after = self.editor.get_all_nodes()
        self.assertTrue(any(node["name"] == "Quality Check Before Dispatch" for node in nodes_after))

    def test_modify_vendor_selection(self):
        """Test modifying the vendor selection process."""
        # Find the vendor selection task
        nodes = self.editor.get_all_nodes()
        vendor_task = next(node for node in nodes if "Select Vendor" in node["name"])
        
        # Modify the task to include price comparison
        self.editor.edit_nodes([{
            "node_id": vendor_task["id"],
            "new_name": "Select Vendor and Compare Prices"
        }])
        
        # Verify the change
        nodes_after = self.editor.get_all_nodes()
        modified_task = next(node for node in nodes_after if node["id"] == vendor_task["id"])
        self.assertEqual(modified_task["name"], "Select Vendor and Compare Prices")

    def test_handle_parallel_processes(self):
        """Test handling parallel processes in the workflow."""
        # Find the parallel gateway
        nodes = self.editor.get_all_nodes()
        parallel_gateway = next(node for node in nodes if node["type"] == "parallelGateway")
        
        # Add a new parallel task
        new_task = {
            "name": "Additional Quality Check",
            "position": {"x": 1100, "y": 1600}
        }
        task_id = self.editor.add_tasks([new_task])[0]
        
        # Connect it to the parallel gateway
        self.editor.add_sequence_flows([
            {"source_id": parallel_gateway["id"], "target_id": task_id}
        ])
        
        # Verify the changes
        nodes_after = self.editor.get_all_nodes()
        self.assertTrue(any(node["name"] == "Additional Quality Check" for node in nodes_after))

    def test_modify_lane_assignments(self):
        """Test modifying task assignments between lanes."""
        # Find tasks in different lanes
        nodes = self.editor.get_all_nodes()
        
        # First, find the lanes themselves
        lanes = [node for node in nodes if node["type"] == "lane"]
        self.assertTrue(len(lanes) >= 2, "Need at least two lanes for this test")
        
        # Get tasks from the first lane
        source_lane = lanes[0]
        target_lane = lanes[1]
        
        # Find a task in the source lane by looking for tasks that have this lane's ID
        source_tasks = []
        for node in nodes:
            if node["type"] == "task":
                lane_info = self.editor.get_node_info(node["id"])
                if lane_info.get("lane_id") == source_lane["id"]:
                    source_tasks.append(node)
        
        self.assertTrue(len(source_tasks) > 0, f"No tasks found in lane {source_lane['name']}")
        
        task_to_move = source_tasks[0]
        
        # Remove from old lane and add to new lane
        self.editor.remove_nodes([task_to_move["id"]])
        
        # Create new task in the target lane
        new_task = {
            "name": task_to_move["name"],
            "lane_id": target_lane["id"],  # Use the lane's ID
            "position": {"x": 800, "y": 1000}
        }
        task_id = self.editor.add_tasks([new_task])[0]
        
        # Verify the change
        nodes_after = self.editor.get_all_nodes()
        moved_task = next(node for node in nodes_after if node["name"] == task_to_move["name"])
        
        # Get the lane information for the moved task
        lane_info = self.editor.get_node_info(moved_task["id"])
        self.assertEqual(lane_info["lane_id"], target_lane["id"])
        self.assertEqual(lane_info["lane"], target_lane["name"])

    def test_handle_conditional_flows(self):
        """Test modifying conditional flows in the process."""
        # Find the exclusive gateway
        nodes = self.editor.get_all_nodes()
        exclusive_gateway = next(node for node in nodes if node["type"] == "exclusiveGateway")
        
        # Add a new conditional path
        new_task = {
            "name": "Express Shipping Option",
            "position": {"x": 600, "y": 1500}
        }
        task_id = self.editor.add_tasks([new_task])[0]
        
        # Connect it to the gateway
        self.editor.add_sequence_flows([
            {"source_id": exclusive_gateway["id"], "target_id": task_id}
        ])
        
        # Verify the changes
        nodes_after = self.editor.get_all_nodes()
        self.assertTrue(any(node["name"] == "Express Shipping Option" for node in nodes_after))

    def test_save_and_verify_process(self):
        """Test saving and verifying the entire process structure."""
        # Make some business-relevant changes
        nodes = self.editor.get_all_nodes()
        shipping_task = next(node for node in nodes if "shipping" in node["name"].lower())
        
        # Add a new task
        new_task = {
            "name": "Final Inspection",
            "position": {"x": 900, "y": 1400}
        }
        task_id = self.editor.add_tasks([new_task])[0]
        
        # Connect it to the process
        self.editor.add_sequence_flows([
            {"source_id": shipping_task["id"], "target_id": task_id}
        ])
        
        # Save to a new file
        new_file = os.path.join(self.temp_dir, "modified_process.bpmn")
        self.editor.save(new_file)
        
        # Verify the saved file
        new_editor = BPMNEditor(new_file)
        nodes_after = new_editor.get_all_nodes()
        
        # Verify the changes were preserved
        self.assertTrue(any(node["name"] == "Final Inspection" for node in nodes_after))
        self.assertTrue(os.path.getsize(new_file) > 0)

if __name__ == '__main__':
    unittest.main() 