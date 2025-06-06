from typing import List, Dict, Any, Optional, Callable
from langchain_core.messages import HumanMessage, AIMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain.agents.format_scratchpad.openai_tools import format_to_openai_tool_messages
from langchain.agents.output_parsers.openai_tools import OpenAIToolsAgentOutputParser
from langchain.agents import AgentExecutor
from langchain_openai import ChatOpenAI
from langchain_community.chat_models import ChatOllama
from langchain.callbacks.base import BaseCallbackHandler
import os
import logging

logger = logging.getLogger(__name__)

class StreamingCallbackHandler(BaseCallbackHandler):
    """Callback handler for streaming agent steps."""
    
    def __init__(self, callback: Callable[[Dict[str, Any]], None]):
        self.callback = callback
        
    def on_agent_action(self, action, **kwargs):
        """Called when the agent is about to execute an action."""
        self.callback({
            "type": "action",
            "tool": action.tool,
            "tool_input": action.tool_input
        })
        
    def on_tool_start(self, serialized, input_str, **kwargs):
        """Called when a tool starts executing."""
        self.callback({
            "type": "tool_start",
            "tool": serialized.get("name", "unknown"),
            "input": input_str
        })
        
    def on_tool_end(self, output, **kwargs):
        """Called when a tool finishes executing."""
        self.callback({
            "type": "tool_end",
            "output": output
        })
        
    def on_agent_finish(self, finish, **kwargs):
        """Called when the agent finishes."""
        self.callback({
            "type": "finish",
            "output": finish.return_values.get("output", "")
        })

class BPMNAgent:
    def __init__(self, llm_type: str = "openai", custom_system_prompt: str = None):
        self.llm_type = llm_type
        self.llm = self._initialize_llm()
        self.system_prompt = custom_system_prompt if custom_system_prompt else self._get_system_prompt()
        self.history = []

    def _initialize_llm(self):
        if self.llm_type == "local":
            return ChatOllama(
                model=os.getenv("OLLAMA_MODEL", "qwen2:7b"),
                base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
            )
        else:
            return ChatOpenAI(
                model="o4-mini",
                api_key=os.getenv("OPENAI_BPMN_API_KEY")
            )

    def _get_system_prompt(self) -> str:
        return """
You are a BPMN diagram assistant specialized in analyzing and improving business process models. 
Your objective is to help users enhance their BPMN diagrams by proposing and executing well-reasoned, 
standards-compliant modifications using available tools.

You must always follow this structured procedure when addressing user input:

1. **Understand the Diagram**  
   - Retrieve relevant node information and structure as needed.  
   - Get bpmn model as image to understand the diagram better.  
   - Clarify the process flow, logic, and intent.  
   - Identify potential issues such as bottlenecks, redundant tasks, poor sequencing, or vague elements.

2. **Diagnose and Recommend**  
   - Pinpoint specific areas for improvement.  
   - Justify each proposed change clearly, citing process inefficiency, ambiguity, or BPMN best practices.  
   - Ensure recommendations are grounded in business value and BPMN 2.0 compliance.

3. **Modify the Diagram**  
   - Break down each change step-by-step.  
   - Apply concrete modifications using available tools whenever possible.
   - Prioritize using tools that are able to modify the diagram as much as possible.
   - If the tool is not able to modify the diagram, suggest a change to the diagram in natural language.
   - Prioritize clarity and maintainability in the process model.

4. **Validate and Conclude**  
   - Ensure the updated structure is coherent and standards-compliant.  
   - To ensure the updated structure is coherent and standards-compliant, get bpmn model as image and confirm the changes are correct.
   - Summarize the business impact and rationale behind all applied changes.  
   - Suggest any further improvements if necessary.

Additional Guidelines:
- Always act on the diagram using available tools when recommending changes.  
- Communicate in a clear, professional, and domain-appropriate tone.  
- Avoid vague feedback—make each suggestion actionable and technically sound.  
- Avoid hallucinating node names or structures—always inspect the actual diagram when in doubt.

Your primary role is not just to comment on the diagram, but to transform it meaningfully and intelligently using the provided tools.
        """

    def create_agent(self, tools: List[Any], callbacks: Optional[List[BaseCallbackHandler]] = None, verbose: bool = True) -> AgentExecutor:
        prompt = ChatPromptTemplate.from_messages([
            ("system", self.system_prompt),
            ("user", "{input}"),
            MessagesPlaceholder(variable_name="agent_scratchpad"),
            MessagesPlaceholder(variable_name="history")
        ])
        llm_with_tools = self.llm.bind_tools(tools)
        agent = (
            {
                "input": lambda x: x["input"],
                "history": lambda x: x["history"],
                "agent_scratchpad": lambda x: format_to_openai_tool_messages(
                    x["intermediate_steps"]
                ),
            }
            | prompt
            | llm_with_tools
            | OpenAIToolsAgentOutputParser()
        )
        return AgentExecutor(
            agent=agent,
            tools=tools,
            verbose=verbose,
            return_intermediate_steps=True,
            callbacks=callbacks
        )

    def update_history(self, query: str, result: Dict[str, Any]) -> None:
        self.history.append(HumanMessage(content=query))
        self.history.append(AIMessage(content=result["output"]))

    def reset_history(self) -> None:
        """Reset the conversation history."""
        self.history = []

    def get_structured_response(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """Extract structured response from the agent's output."""
        output = result.get("output", "")
        
        # Initialize response structure
        structured_response = {
            "issues": []
        }
        
        try:
            # Check if no issues were found
            if "No Issues Found:" in output:
                return structured_response
            
            # Split the output into sections
            sections = output.split("\n")
            current_issue = None
            current_section = None
            
            for line in sections:
                line = line.strip()
                if not line:
                    continue
                
                # Check for new issue number
                if line[0].isdigit() and "." in line:
                    if current_issue:
                        structured_response["issues"].append(current_issue)
                    
                    # Start new issue
                    current_issue = {
                        "priority": "Unknown",
                        "elements": [],
                        "issue": "",
                        "recommended_fix": ""
                    }
                    
                    # Extract priority if present
                    if "Priority Level:" in line:
                        priority = line.split("Priority Level:")[1].strip()
                        current_issue["priority"] = priority
                    continue
                
                # Process sections within an issue
                if current_issue is not None:
                    if "Element(s):" in line:
                        current_section = "elements"
                        elements = line.replace("Element(s):", "").strip()
                        current_issue["elements"] = [e.strip() for e in elements.split(",")]
                    elif "Issue:" in line:
                        current_section = "issue"
                        current_issue["issue"] = line.replace("Issue:", "").strip()
                    elif "Recommended Fix:" in line:
                        current_section = "recommended_fix"
                        current_issue["recommended_fix"] = line.replace("Recommended Fix:", "").strip()
                    elif current_section and line:
                        # Append to the current section if we're in one
                        if current_section == "elements":
                            current_issue["elements"].extend([e.strip() for e in line.split(",")])
                        else:
                            current_issue[current_section] += " " + line
            
            # Add the last issue if exists
            if current_issue:
                structured_response["issues"].append(current_issue)
            
            return structured_response
            
        except Exception as e:
            logger.error(f"Error parsing structured response: {str(e)}")
            return {
                "issues": [{
                    "priority": "Error",
                    "elements": ["Error during parsing"],
                    "issue": f"Failed to parse response: {str(e)}",
                    "recommended_fix": "Please check the raw output for details"
                }]
            }