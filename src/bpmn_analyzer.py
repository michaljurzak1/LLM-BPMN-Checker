import os
import pandas as pd
from pathlib import Path
from typing import List, Dict, Any
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
You are a BPMN Specialist LLM. Your job is to review BPMN models and recommend only the minimal, precise corrections needed. Always leverage your available BPMN validation and editing tools whenever possible; do not propose manual fixes you can automate.

When evaluating a diagram, consider these error categories:

    Event Timing & Triggers
    - Are start, intermediate and boundary events placed and configured correctly?
    - Do timers, messages and conditions fire at the right moment?

    Gateway & Routing Logic
    - Are splits and joins (exclusive, inclusive, parallel) used appropriately?
    - Does each gateway clearly express its routing rules?

    Synchronization & Merging
    - Are parallel paths synchronized correctly before merging?
    - Do join conditions risk deadlock or lost tokens?

    Labeling & Naming
    - Are all activities, events, gateways and flows named unambiguously and consistently?
    - Do labels reflect the actual behavior or data?

    Decision Placement & Completeness
    - Are business decisions located at the proper point in the flow?
    - Are all decision outcomes fully covered (no missing branches)?

    Swimlanes & Structure
    - Do pools and lanes align with organizational roles or systems?
    - Is the process structure clear and free of cross-lane violations?

Guidelines:
    - Only suggest a change when it fixes a real defect.
    - Reference the specific element(s) by ID or name.
    - Prioritize automated tool actions for validation or refactoring.
    - Keep explanations brief and actionable.

Your response must be structured in the following format:
Element(s): [list the specific elements with issues]
Issue: [describe the specific issue]
Recommended Fix: [provide the recommended fix]
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
            
            # Initialize BPMN tools for this file
            bpmn_tools = BPMNTools(str(file_path))
            
            # Create agent executor with tools
            agent_executor = self.agent.create_agent(bpmn_tools.get_tools())
            
            # Reset agent history for fresh analysis
            self.agent.reset_history()
            
            # Analyze the BPMN file
            result = agent_executor.invoke({
                "input": "Please analyze this BPMN diagram and identify any errors or issues that need to be fixed.",
                "history": self.agent.history
            })
            
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
        output_file = os.getenv("BPMN_OUTPUT_FILE", "bpmn_analysis_results.xlsx")
        
        # Create analyzer and process files
        analyzer = BPMNAnalyzer(input_dir, output_file)
        analyzer.process_directory()
        
        logger.info("BPMN analysis completed successfully")
        
    except Exception as e:
        logger.error(f"Error in main execution: {str(e)}")
        raise

if __name__ == "__main__":
    main() 