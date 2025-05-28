import streamlit as st
import os
from pathlib import Path
# Assuming bpmn_editor, bpmn_langchain_tools, bpmn_highlighter, bpmn_agent are in the same directory or PYTHONPATH
from src.ai.tools.bpmn_langchain_tools import BPMNTools
from src.core.bpmn_highlighter import BPMNHighlighter
from dotenv import load_dotenv
import tempfile
from src.ai.bpmn_agent import BPMNAgent
import logging
from src.core.bpmn_utils import fix_signavio_process_structure

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Set page config
st.set_page_config(page_title="BPMN Editor & Chat", page_icon="📊", layout="wide")

# Initialize session state
if "messages" not in st.session_state:
    st.session_state.messages = []

if "current_file" not in st.session_state:
    st.session_state.current_file = None

if "current_visualization" not in st.session_state:
    st.session_state.current_visualization = None

if "bpmn_agent" not in st.session_state:
    st.session_state.bpmn_agent = None

if "bpmn_tools" not in st.session_state:
    st.session_state.bpmn_tools = None

if "pending_changes" not in st.session_state:
    st.session_state.pending_changes = False

def create_visualization(bpmn_file_path, changes=None):
    """Create a visualization of the BPMN file using BPMNHighlighter."""
    try:
        if not bpmn_file_path or not Path(bpmn_file_path).exists():
            logger.warning(f"BPMN file path for visualization is invalid or file does not exist: {bpmn_file_path}")
            # Create a dummy empty HTML or return None to avoid errors downstream
            temp_dir = tempfile.gettempdir()
            output_path = os.path.join(temp_dir, "bpmn_visualization_error.html")
            with open(output_path, "w") as f:
                f.write("<html><body>Error: BPMN file not found for visualization.</body></html>")
            return output_path

        # Ensure the file path is absolute
        bpmn_file_path = str(Path(bpmn_file_path).resolve())
        logger.info(f"Creating visualization for BPMN file: {bpmn_file_path}")

        # --- Fix Signavio process structure if needed ---
        try:
            fixed = fix_signavio_process_structure(bpmn_file_path)
            if fixed:
                logger.info(f"Fixed Signavio process structure in: {bpmn_file_path}")
        except Exception as e:
            logger.error(f"Error fixing Signavio process structure: {e}")

        highlighter = BPMNHighlighter()
        temp_dir = tempfile.gettempdir()
        # Ensure unique output file names if multiple visualizations are generated rapidly
        output_filename = f"bpmn_visualization_{Path(bpmn_file_path).stem}_{os.urandom(4).hex()}.html"
        output_path = os.path.join(temp_dir, output_filename)

        try:
            highlighter.highlight_elements(str(bpmn_file_path), output_path=output_path, changes=changes)
            logger.info(f"Successfully created visualization at: {output_path}")
        except Exception as e:
            logger.error(f"Error during BPMN highlighting for {bpmn_file_path}: {e}")
            with open(output_path, "w") as f:
                f.write(f"<html><body>Error generating BPMN visualization: {e}</body></html>")
        return output_path
    except Exception as e:
        logger.error(f"Unexpected error in create_visualization: {e}")
        raise

def initialize_agent_and_tools(file_path: str):
    """Initialize the BPMN agent and tools with proper error handling."""
    try:
        # Create a new BPMNTools instance with the file
        st.session_state.bpmn_tools = BPMNTools(file_path)
        
        # Ensure temp_filepath is initialized and exists
        if not hasattr(st.session_state.bpmn_tools, 'temp_filepath') or \
           not st.session_state.bpmn_tools.temp_filepath or \
           not Path(st.session_state.bpmn_tools.temp_filepath).exists():
            st.session_state.bpmn_tools = BPMNTools(file_path)
            
        # Initialize the agent
        st.session_state.bpmn_agent = BPMNAgent(llm_type="openai")
        return True
    except Exception as e:
        st.error(f"Failed to initialize BPMN tools or agent: {str(e)}")
        return False

# Sidebar for file selection
st.sidebar.title("BPMN File Selection")
current_dir_path = Path(os.getcwd()) # Default to current working directory
user_dir_input = st.sidebar.text_input("Directory Path", value=str(current_dir_path))

if Path(user_dir_input).is_dir():
    current_dir = user_dir_input
else:
    st.sidebar.warning("Invalid directory path. Using current working directory.")
    current_dir = str(current_dir_path)


# Add refresh button
if st.sidebar.button("🔄 Refresh Files"):
    st.rerun()

try:
    files = [f for f in os.listdir(current_dir) if f.endswith(".bpmn")]
    if not files:
        st.sidebar.info("No BPMN files found in the specified directory.")
        selected_file = None
    else:
        selected_file = st.sidebar.selectbox("Select BPMN File", files, index=0 if files else None)

    if selected_file and st.sidebar.button("Load BPMN File"):
        file_path = os.path.join(current_dir, selected_file)
        st.session_state.current_file = file_path
        st.session_state.current_visualization = create_visualization(file_path) # Initial viz, no changes
        st.session_state.messages = []
        st.session_state.pending_changes = False

        if initialize_agent_and_tools(file_path):
            st.session_state.messages.append({
                "role": "assistant",
                "content": f"Ready to analyze **{selected_file}**. What would you like to know or change in the BPMN diagram?"
            })
        else:
            st.session_state.current_file = None # Reset if initialization fails
            st.session_state.current_visualization = None

except Exception as e:
    st.sidebar.error(f"Error accessing directory '{current_dir}': {str(e)}")


# Main content area
col1, col2 = st.columns([2, 1])

with col1:
    st.subheader("BPMN Viewer") # Changed to subheader for better hierarchy
    if st.session_state.current_file and st.session_state.current_visualization:
        try:
            # Logic to update visualization if pending changes exist (this runs on every rerun)
            if st.session_state.bpmn_tools and st.session_state.pending_changes:
                changes = st.session_state.bpmn_tools.get_changes()
                if any(changes.values()): # Ensure changes still exist
                    # Use temp_filepath if it's where modifications are staged
                    viz_file_path = getattr(st.session_state.bpmn_tools, 'temp_filepath', st.session_state.current_file)
                    if not Path(viz_file_path).exists() and Path(st.session_state.current_file).exists():
                        viz_file_path = st.session_state.current_file # Fallback if temp_filepath is gone
                    
                    st.session_state.current_visualization = create_visualization(
                        viz_file_path,
                        changes=changes
                    )
                else: # Pending changes flag was true, but get_changes is now empty (e.g. after discard)
                    st.session_state.pending_changes = False # Correct the flag
                    # Re-render based on the original file
                    st.session_state.current_visualization = create_visualization(st.session_state.current_file)


            with open(st.session_state.current_visualization, "r", encoding="utf-8") as f:
                html_content = f.read()
            st.components.v1.html(html_content, height=800, scrolling=True)

            if st.session_state.pending_changes:
                btn_cols = st.columns(2)
                with btn_cols[0]:
                    if st.button("✅ Apply Changes", key="apply_changes_btn"):
                        if st.session_state.bpmn_tools:
                            st.session_state.bpmn_tools.apply_changes()
                            st.session_state.pending_changes = False
                            # Regenerate visualization from the main file (now updated)
                            st.session_state.current_visualization = create_visualization(st.session_state.current_file)
                            st.success("Changes applied successfully!")
                            st.rerun()
                        else:
                            st.error("BPMN tools not available to apply changes.")
                with btn_cols[1]:
                    if st.button("❌ Discard Changes", key="discard_changes_btn"):
                        if st.session_state.bpmn_tools:
                            st.session_state.bpmn_tools.discard_changes()
                            st.session_state.pending_changes = False
                            # Regenerate visualization from the main file (reverted or unchanged)
                            st.session_state.current_visualization = create_visualization(st.session_state.current_file)
                            st.info("Changes discarded.")
                            st.rerun()
                        else:
                            st.error("BPMN tools not available to discard changes.")

        except Exception as e:
            st.error(f"Error displaying BPMN visualization: {str(e)}")
    elif st.session_state.current_file and not st.session_state.current_visualization:
        st.warning("Visualization could not be generated. Please check logs.")
    else:
        st.info("Please select and load a BPMN file from the sidebar to view it here.")

with col2:
    st.subheader("Chat Assistant") # Changed to subheader

    # Display chat messages
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    user_input = st.chat_input("Ask about the BPMN diagram or request changes...")

    if user_input:
        if not st.session_state.current_file:
            st.error("Please select and load a BPMN file first!")
        elif not st.session_state.bpmn_agent or not st.session_state.bpmn_tools:
            st.error("BPMN Agent or Tools are not initialized. Please load a BPMN file.")
        else:
            # Ensure tools are properly initialized before processing
            if not Path(st.session_state.bpmn_tools.temp_filepath).exists():
                initialize_agent_and_tools(st.session_state.current_file)
            
            st.session_state.messages.append({"role": "user", "content": user_input})
            with st.chat_message("user"):
                st.markdown(user_input)

            with st.chat_message("assistant"):
                message_placeholder = st.empty()
                full_response = ""
                needs_rerun_for_viz_update = False

                with st.spinner("Thinking..."):
                    try:
                        agent_executor = st.session_state.bpmn_agent.create_agent(
                            st.session_state.bpmn_tools.get_tools()
                        )
                        agent_result = agent_executor.invoke({
                            "input": user_input,
                            "history": st.session_state.bpmn_agent.history
                        })

                        # Update history with the result
                        st.session_state.bpmn_agent.update_history(user_input, agent_result)
                        
                        # Get the output from the result
                        output = agent_result.get("output", str(agent_result)) if isinstance(agent_result, dict) else str(agent_result)
                        full_response = output

                        # Display and store the message
                        message_placeholder.markdown(full_response)
                        st.session_state.messages.append({"role": "assistant", "content": full_response})

                        # Check for changes made by tools and update visualization if needed
                        if st.session_state.bpmn_tools:
                            changes = st.session_state.bpmn_tools.get_changes()
                            if any(changes.values()):
                                st.session_state.pending_changes = True
                                # Use temp_filepath if it's where modifications are staged
                                viz_file_path = getattr(st.session_state.bpmn_tools, 'temp_filepath', st.session_state.current_file)
                                if not Path(viz_file_path).exists():
                                    initialize_agent_and_tools(st.session_state.current_file)
                                    viz_file_path = st.session_state.bpmn_tools.temp_filepath

                                st.session_state.current_visualization = create_visualization(
                                    viz_file_path,
                                    changes=changes
                                )
                                needs_rerun_for_viz_update = True

                    except Exception as e:
                        full_response = f"Sorry, an error occurred while processing your request: {str(e)}"
                        message_placeholder.error(full_response)
                        st.session_state.messages.append({"role": "assistant", "content": full_response})

                # Rerun IF AND ONLY IF the visualization needs to be updated
                if needs_rerun_for_viz_update:
                    st.rerun()