import os
import shutil
import pandas as pd
from pathlib import Path
import logging
from tqdm import tqdm
from src.ai.bpmn_agent import BPMNAgent
from src.ai.tools.bpmn_langchain_tools import BPMNTools

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler("bpmn_fix_applier.log"), logging.StreamHandler()],
)
logger = logging.getLogger(__name__)

# Paths
EXCEL_PATH = "src/bpmn_analysis_results_v0.xlsx"
BPMN_SOURCE_DIR = "data/raw/archives/Error Models/BPMN_Error_Tasks_and_Fixes/XML"
ACTUAL_ISSUES_DIR = "src/llm_fix/actual_issues"
DETECTED_ISSUES_DIR = "src/llm_fix/detected_issues"

BPMN_ERROR_FIX_PROMPT = """
You are a BPMN Specialist LLM. Your task is to apply a recommended fix to a BPMN model, given the following information:

- The specific elements involved
- A description of the issue
- A recommended fix

Instructions:
    - Carefully review the provided elements, issue, and recommended fix.
    - Use your tools to inspect and modify the BPMN file as needed.
    - Apply the recommended fix precisely and ensure the issue is resolved.
    - Make only the necessary changes to address the described issue.
    - Reference elements by their ID or name as provided.
    - After applying the fix, verify that the BPMN model remains valid and well-structured.
    - If you need more context, use the image attachment tool to inspect the BPMN model.

Make sure to use edit function so the changes are visible and applied directly to the BPMN file.
Your response should confirm the fix has been applied, briefly describe what was changed, and note any additional observations if relevant.
"""

# Ensure output directories exist
os.makedirs(ACTUAL_ISSUES_DIR, exist_ok=True)
os.makedirs(DETECTED_ISSUES_DIR, exist_ok=True)


def construct_prompt(elements, issue, fix):
    return f"""You need to apply the recommended fixes to the issue given these informations:\n\nAffected elements:\n{elements}\n\nIssue:\n{issue}\n\nRecommended fix:\n{fix}\n\nPlease apply the changes to the problematic file (attached), use your tools to interact with the file and reach the end goal of fixing the issue."""


def try_apply_fix(agent, bpmn_file_path, prompt):
    """Attempt to apply a fix using the LLM agent and return result dict. If manual=True, simulate manual application."""
    # Simulate manual application of changes (as in app.py's apply_changes)
    try:
        bpmn_tools = BPMNTools(str(bpmn_file_path), agent_history=agent.history)
        agent_executor = agent.create_agent(bpmn_tools.get_tools(), verbose=True)
        agent.reset_history()
        bpmn_tools.agent_history = agent.history
        result = agent_executor.invoke({"input": prompt, "history": agent.history})
        agent.update_history(prompt, result)
        bpmn_tools.agent_history = agent.history
        bpmn_tools.apply_changes()
        return {"success": True, "message": str(result)}
    except Exception as e:
        logger.error(f"Agent error on file {bpmn_file_path}: {e}")
        return {"success": False, "message": str(e)}


def main():
    # Load the Excel file
    df = pd.read_excel(EXCEL_PATH, sheet_name=None)
    results = []

    # Process each sheet in the Excel file
    for sheet_name, sheet_df in df.items():
        logger.info(f"Processing sheet: {sheet_name}")

        if sheet_name not in ["Errors (multiple)"]:
            continue
        # Skip empty sheets
        if sheet_df.empty:
            logger.warning(f"Sheet {sheet_name} is empty, skipping.")
            continue

        # Iterate over rows in the sheet
        for idx, row in tqdm(
            sheet_df.iterrows(), total=len(sheet_df), desc="Processing issues"
        ):

            try:
                bpmn_files = sorted(Path(BPMN_SOURCE_DIR).glob("*.bpmn"))
                if idx >= len(bpmn_files):
                    logger.warning(f"No matching BPMN file for row {idx}")
                    continue
                src_file = bpmn_files[idx]
                actual_dst = Path(ACTUAL_ISSUES_DIR) / src_file.name
                detected_dst = Path(DETECTED_ISSUES_DIR) / src_file.name
                shutil.copy(src_file, actual_dst)
                shutil.copy(src_file, detected_dst)

                # Construct prompts
                actual_prompt = construct_prompt(
                    row.get("Element(s)", ""),
                    row.get("Issue", ""),
                    row.get("Recommended Fix", ""),
                )
                detected_prompt = construct_prompt(
                    row.get("best detected: element(s)", ""),
                    row.get("best detected: issue", ""),
                    row.get("best detected: recommended fix", ""),
                )

                agent = BPMNAgent(
                    llm_type="openai", custom_system_prompt=BPMN_ERROR_FIX_PROMPT
                )
                # Apply fixes using the agent (auto)
                print("\nActual prompt:", actual_prompt)
                actual_result = try_apply_fix(agent, actual_dst, actual_prompt)

                agent = BPMNAgent(
                    llm_type="openai", custom_system_prompt=BPMN_ERROR_FIX_PROMPT
                )
                print("\nDetected prompt:", detected_prompt)
                detected_result = try_apply_fix(agent, detected_dst, detected_prompt)

                print(actual_result)

                results.append(
                    {
                        "file_path": src_file,
                        "actual_prompt": actual_prompt,
                        "detected_prompt": detected_prompt,
                        "actual_result": actual_result["success"],
                        "actual_message": actual_result["message"],
                        "detected_result": detected_result["success"],
                        "detected_message": detected_result["message"],
                    }
                )
            except Exception as e:
                logger.error(f"Error processing row {idx}: {e}")
                results.append(
                    {
                        "file": None,
                        "actual_prompt": None,
                        "detected_prompt": None,
                        "actual_result": False,
                        "actual_message": str(e),
                        "detected_result": False,
                        "detected_message": str(e),
                    }
                )

    # Save results to Excel
    results_df = pd.DataFrame(results)
    results_df.to_excel("bpmn_fix_results.xlsx", index=False)
    logger.info("Results saved to bpmn_fix_results.xlsx")


if __name__ == "__main__":
    main()
