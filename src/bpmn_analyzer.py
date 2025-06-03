import os
import pandas as pd
from pathlib import Path
from typing import Dict, Any
import logging
from dotenv import load_dotenv
from src.ai.bpmn_agent import BPMNAgent
from src.ai.tools.bpmn_langchain_tools import BPMNTools

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
You are a BPMN Specialist LLM. Your job is to review BPMN models and identify the SINGLE most critical issue that needs to be fixed. Focus on the most impactful problem that would cause the most severe consequences if not addressed.

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
    - Identify ONLY the most critical issue that needs immediate attention
    - Reference specific elements by ID or name
    - Provide a single, clear recommended fix
    - Keep the explanation concise and actionable

Your response MUST follow this exact format:
Element(s): [list ONLY the specific elements involved in the most critical issue]
Issue(s): [describe the single most critical issue]
Recommended Fix(es): [provide ONE clear recommended fix]

Do not list multiple issues or fixes. Focus on the single most important problem that needs to be addressed first.
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
            agent_executor = self.agent.create_agent(bpmn_tools.get_tools())
            
            # Reset agent history for fresh analysis
            self.agent.reset_history()
            # Update BPMNTools history reference after reset
            bpmn_tools.agent_history = self.agent.history
            
            # Analyze the BPMN file
            result = agent_executor.invoke({
                "input": "Please analyze this BPMN diagram and identify any errors or issues that need to be fixed.",
                "history": self.agent.history
            })
            
            # Update agent history with the result
            self.agent.update_history("Please analyze this BPMN diagram and identify any errors or issues that need to be fixed.", result)
            # Update BPMNTools history reference after history update
            bpmn_tools.agent_history = self.agent.history
            
            # Get structured response
            structured_response = self.agent.get_structured_response(result)
            
            # Add file information to the response
            structured_response["file_name"] = file_path.name
            structured_response["file_path"] = str(file_path)
            
            return structured_response
            
        except Exception as e:
            logger.error(f"Error analyzing file {file_path}: {str(e)}")
            return {
                "file_name": file_path.name,
                "file_path": str(file_path),
                "elements": "Error during analysis",
                "issue": str(e),
                "recommended_fix": "Analysis failed"
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
            
            # Process each file
            for file_path in bpmn_files:
                result = self.analyze_bpmn_file(file_path)
                self.results.append(result)
                logger.info(f"Completed analysis of {file_path.name}")
            
            # Create DataFrame and save results
            df = pd.DataFrame(self.results)
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