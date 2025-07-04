# LLM-BPMN-Checker

A tool for analyzing and improving BPMN models using Large Language Models (LLMs). This project provides a web interface for visualizing BPMN models and uses LLMs to detect and correct issues in the models.

<img src="projectUI.png" alt="project UI" width="700"/>

## Features

- BPMN model visualization and analysis
- LLM-powered model improvement suggestions
- Interactive web interface for model editing
- Support for both text and image-based BPMN model input
- Real-time model validation and correction
- Visual highlighting of model changes

## Installation

1. Clone the repository:

```bash
git clone https://github.com/michaljurzak1/LLM-BPMN-Checker.git
cd LLM-BPMN-Checker
```

2. Create and activate a virtual environment with uv or pip:

```bash
uv venv
# On Windows:
.venv/Scripts/activate
# On Unix:
source .venv/bin/activate
```

3. Install dependencies:

```bash
uv pip install -r requirements.txt
```

## Usage

1. Start the web interface:

```bash
streamlit run app.py
```

2. Open your browser and navigate to the provided local URL (typically http://localhost:8501)

3. Upload or input your BPMN model for analysis

4. Use the interface to:
   - View the BPMN model
   - Get LLM-powered analysis
   - Apply suggested improvements
   - Manually edit the model

### Running as a Module

You can also run the BPMN analyzer and fix applier modules directly from the command line for `bpmn_analysis_results.xlsx` results

```bash
# Run the BPMN analyzer
python -m src.bpmn_analyzer
```

```bash
# Run the BPMN fix applier
python -m src.bpmn_fix_applier
```

## Project Structure

```
LLM-BPMN-Checker/
├── src/                    # Source code
│   ├── ai/                # AI/LLM related code
│   ├── core/              # Core BPMN processing
│   ├── notebooks/         # Jupyter notebooks
│   └── utils/             # Utility functions
├── data/                  # Data directory
├── tests/                 # Test files
├── app.py                 # Main Streamlit application
├── bpmn_viewer.html       # BPMN visualization template
└── requirements.txt       # Project dependencies
```

## Dependencies

- pm4py: BPMN model processing
- networkx: Graph operations
- matplotlib: Visualization
- langchain: LLM integration
- streamlit: Web interface
- openai: LLM API that uses OPENAI_BPMN_API_KEY environmental variable
- Additional utilities for image processing and visualization

## Development

The project is actively being developed with the following features in progress:

- Enhanced LLM-based BPMN model extraction from text and images
- Improved accuracy in detecting model issues
- Interactive model correction interface
- Visual highlighting of model changes
- User acceptance workflow for LLM-suggested changes
