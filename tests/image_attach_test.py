import base64
from pathlib import Path
from src.ai.bpmn_agent import BPMNAgent
from langchain.tools import tool
from langchain_core.messages import HumanMessage

def test_image_understanding():
    # Initialize the BPMN agent
    agent = BPMNAgent(llm_type="openai")
    
    # Get the path to the test image
    current_dir = Path(__file__).parent
    image_path = current_dir / "Zrzut ekranu 2025-05-28 144749.png"
    
    # Read and encode the image
    with open(image_path, "rb") as image_file:
        image_data = base64.b64encode(image_file.read()).decode("utf-8")
    
    # Create a multimodal input with the image
    multimodal_input = {
        "type": "image",
        "source_type": "base64",
        "mime_type": "image/png",
        "data": image_data
    }
    
    # Create a prompt asking about the image
    prompt = "What do you see in this image? Please describe it in detail."
    
    # Create a tool that will append the image as a user message
    @tool("analyze_image")
    def analyze_image() -> str:
        """Analyze an image and describe what it shows."""
        # Append the image as a user message
        agent.history.append(HumanMessage(content=[{"type": "text", "text": prompt}, multimodal_input]))
        return "Image has been added to the conversation. Please analyze it."
    
    # Create agent with the image analysis tool
    agent_executor = agent.create_agent([analyze_image])
    
    # Get response from the agent
    result = agent_executor.invoke({
        "input": "Please analyze the image I just shared.",
        "history": agent.history
    })
    
    # Print the response
    print("\nLLM Response:")
    print(result["output"])
    
    # Basic assertion to ensure we got a response
    assert result is not None
    assert "output" in result
    assert len(result["output"]) > 0

if __name__ == "__main__":
    test_image_understanding()
