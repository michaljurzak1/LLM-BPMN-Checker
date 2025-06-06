import os
import pandas as pd
from pathlib import Path
from typing import Dict, Any
import logging
from dotenv import load_dotenv
from src.ai.bpmn_agent import BPMNAgent
from src.ai.tools.bpmn_langchain_tools import BPMNTools
from tqdm import tqdm

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('bpmn_analysis.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Custom system prompt for BPMN error detection
BPMN_ERROR_DETECTION_PROMPT = """
You are a BPMN Specialist LLM. Your job is to review BPMN models and identify ALL issues that need to be fixed, while maintaining a clear priority order. Focus on finding all potential problems that could impact the process execution.

When evaluating a diagram, consider these error categories in order of priority:

1. Deadlocks & Token Issues
   - Are there any gateway configurations that could cause deadlocks?
   - Are tokens properly synchronized and merged?

2. Event Configuration
   - Are events (start, intermediate, boundary) properly configured?
   - Are event triggers and conditions correctly set up?

3. Gateway Logic
   - Are gateways used appropriately for their intended purpose?
   - Is the routing logic clear and complete?

4. Process Structure
   - Is the process flow logical and complete?
   - Are all paths properly connected?

5. Naming & Documentation
   - Are elements named clearly and consistently?
   - Is the process documentation clear?

Guidelines:
    - List ALL issues found, ordered by priority (most critical first)
    - Reference specific elements by ID or name
    - Provide clear recommended fixes for each issue
    - Keep explanations concise and actionable
    - Use the image attachment tool to get better context of the bpmn model

Your response MUST follow this exact format:
Issues Found:
1. [Priority Level: Critical/High/Medium/Low]
   Element(s): [list the specific elements involved]
   Issue: [describe the issue]
   Recommended Fix: [provide clear recommended fix]

2. [Priority Level: Critical/High/Medium/Low]
   Element(s): [list the specific elements involved]
   Issue: [describe the issue]
   Recommended Fix: [provide clear recommended fix]

[Continue for all issues found...]

If no issues are found, respond with:
No Issues Found: The BPMN diagram appears to be well-structured and follows best practices.
"""

class BPMNAnalyzer:
    def __init__(self, input_dir: str, output_file: str = "bpmn_analysis_results.xlsx"):
        self.input_dir = Path(input_dir)
        self.output_file = output_file
        self.agent = BPMNAgent(llm_type="openai", custom_system_prompt=BPMN_ERROR_DETECTION_PROMPT)
        self.results = []

    def analyze_bpmn_file(self, file_path: Path) -> Dict[str, Any]:
        """Analyze a single BPMN file and return the results."""
        try:
            logger.info(f"Analyzing file: {file_path}")
            
            # Initialize BPMN tools for this file with agent's history
            bpmn_tools = BPMNTools(str(file_path), agent_history=self.agent.history)
            
            # Create agent executor with tools
            agent_executor = self.agent.create_agent(bpmn_tools.get_tools(), verbose=True)
            
            # Reset agent history for fresh analysis
            self.agent.reset_history()
            # Update BPMNTools history reference after reset
            bpmn_tools.agent_history = self.agent.history
            
            # Analyze the BPMN file
            result = agent_executor.invoke({
                "input": "Please analyze this BPMN diagram and identify all errors or issues that need to be fixed.",
                "history": self.agent.history
            })
            
            # Update agent history with the result
            self.agent.update_history("Please analyze this BPMN diagram and identify all errors or issues that need to be fixed.", result)
            # Update BPMNTools history reference after history update
            bpmn_tools.agent_history = self.agent.history
            
            # Get structured response
            structured_response = self.agent.get_structured_response(result)
            
            # Add file information to the response
            structured_response["file_name"] = file_path.name
            structured_response["file_path"] = str(file_path)
            
            # Process multiple issues into a list format
            if "issues" in structured_response:
                issues_list = []
                for issue in structured_response["issues"]:
                    issue_data = {
                        "priority": issue.get("priority", "Unknown"),
                        "elements": issue.get("elements", []),
                        "issue": issue.get("issue", ""),
                        "recommended_fix": issue.get("recommended_fix", ""),
                    }
                    issues_list.append(issue_data)
                structured_response["issues"] = issues_list
            
            return structured_response
            
        except Exception as e:
            logger.error(f"Error analyzing file {file_path}: {str(e)}")
            return {
                "file_name": file_path.name,
                "file_path": str(file_path),
                "issues": [{
                    "priority": "Error",
                    "elements": "Error during analysis",
                    "issue": str(e),
                    "recommended_fix": "Analysis failed",
                }]
            }

    def process_directory(self):
        """Process all BPMN files in the input directory."""
        try:
            # Get all BPMN files in the directory
            bpmn_files = list(self.input_dir.glob("**/*.bpmn"))
            
            if not bpmn_files:
                logger.warning(f"No BPMN files found in {self.input_dir}")
                return
            
            logger.info(f"Found {len(bpmn_files)} BPMN files to analyze")
            
            # Process each file with progress bar
            with tqdm(total=len(bpmn_files), desc="Analyzing BPMN files", unit="file") as pbar:
                for file_path in bpmn_files:
                    pbar.set_description(f"Processing: {file_path.name}")
                    result = self.analyze_bpmn_file(file_path)
                    self.results.append(result)
                    pbar.update(1)
                    logger.info(f"Completed analysis of {file_path.name}")
            
            # Create DataFrame with expanded issues
            expanded_results = []
            with tqdm(total=len(self.results), desc="Preparing results", unit="file") as pbar:
                for result in self.results:
                    file_info = {
                        "file_name": result["file_name"],
                        "file_path": result["file_path"]
                    }
                    
                    if "issues" in result:
                        for issue in result["issues"]:
                            row = {**file_info, **issue}
                            expanded_results.append(row)
                    else:
                        expanded_results.append(file_info)
                    pbar.update(1)
                                
            # Create DataFrame and save results
            df = pd.DataFrame(expanded_results)
            df.to_excel(self.output_file, index=False)
            logger.info(f"Results saved to {self.output_file}")
            
        except Exception as e:
            logger.error(f"Error processing directory: {str(e)}")
            raise

def main():
    try:
        # Get input directory from command line or use default
        input_dir = os.getenv("BPMN_INPUT_DIR", "data/raw/archives/Error Models/BPMN_Error_Tasks_and_Fixes/XML")
        # Change output file to be in the data directory
        output_file = os.getenv("BPMN_OUTPUT_FILE", "src/bpmn_analysis_results.xlsx")
        
        # Ensure the output directory exists
        os.makedirs(os.path.dirname(output_file), exist_ok=True)
        
        # Create analyzer and process files
        analyzer = BPMNAnalyzer(input_dir, output_file)
        analyzer.process_directory()
        
        logger.info("BPMN analysis completed successfully")
        
    except PermissionError:
        logger.error(f"Permission denied when trying to write to {output_file}. Please make sure the file is not open in another program.")
        raise
    except Exception as e:
        logger.error(f"Error in main execution: {str(e)}")
        raise

if __name__ == "__main__":
    main() 