# Job Search Agent - FCC Project

A local, private job search agent that scrapes LinkedIn for relevant positions using Ollama LLMs for intelligent filtering.

## Features
- **Local-first**: All processing happens on your machine
- **Session persistence**: Secure LinkedIn login session storage
- **Intelligent filtering**: Uses local LLMs to evaluate job relevance
- **Time-bucket analysis**: Categorizes jobs by posting time (<30m, <1h, etc.)
- **Duplicate prevention**: SQLite database prevents re-processing same jobs
- **Real-time UI**: Gradio interface with live results
- **CSV export**: Automatically exports findings to timestamped CSV files
- **Stealth scraping**: Built-in throttling to avoid detection

## Architecture
```mermaid
graph TD
    A[Gradio UI] --> B[Agent Logic]
    B --> C[Browser Automation<br/>Playwright]
    B --> D[LLM Engine<br/>Ollama]
    B --> E[Database<br/>SQLite]
    C --> F[LinkedIn<br/>Job Search]
    D --> G[Local Model<br/>Inference]
    E --> H[Job Storage<br/>& Deduplication]
    F --> I[Job Cards<br/>& Descriptions]
    I --> B
    style A fill:#e3f2fd,stroke:#1565c0
    style B fill:#fff3e0,stroke:#ef6c00
    style C fill:#e8f5e8,stroke:#2e7d32
    style D fill:#f3e5f5,stroke:#6a1b9a
    style E fill:#ffebee,stroke:#c62828
    style F fill:#fff8e1,stroke:#ff6f00
    style G fill:#e3f2fd,stroke:#1565c0
    style H fill:#e8f5e8,stroke:#2e7d32
    style I fill:#fff8e1,stroke:#ff6f00
```

## Setup Instructions

### 1. Prerequisites
- Ubuntu Linux (or any OS with Docker/Podman support)
- [Ollama](https://ollama.ai/) installed and running
- At least one LLM model pulled (e.g., `ollama pull llama3`)
- Python 3.8+

### 2. Installation
```bash
# Clone or create the directory
mkdir job_search-fcc && cd job_search-fcc

# Install Python dependencies
pip install -r requirements.txt

# Install Playwright browsers
playwright install
```

### 3. Initial Setup (One-time)
```bash
# Run the interactive login script to set up your LinkedIn session
python interactive_login.py

# Follow the prompts to log in to LinkedIn manually
# Close the browser when you're on your LinkedIn feed
```

### 4. Usage
```bash
# Start the agent
python agent.py

# The Gradio interface will open at http://127.0.0.1:7860
```

### 5. Using the Interface
1. **Select your Ollama model** from the dropdown (click refresh to update)
2. **Enter your target role** (e.g., "Edge AI Engineer")
3. **Specify location preference** (e.g., "Remote", "New York")
4. **Adjust throttle** if needed (higher = safer but slower)
5. **Click "Initialize Agent"** to start scraping
6. **Watch results** appear in the dataframe in real-time
7. **Click URLs** to open jobs directly in your browser
8. **Check the exports folder** for CSV files of your results

## How It Works
```mermaid
flowchart TD
    A[Start: User Configures Agent] --> B[Load LinkedIn Session]
    B --> C{Session Valid?}
    C -- Yes --> D[Headless Browser]
    C -- No --> E[Run interactive_login.py]
    E --> F[Manual LinkedIn Login]
    F --> G[Save Session Cookies]
    G --> D
    D --> H[Navigate to LinkedIn Jobs Search]
    H --> I[Extract Job Cards]
    I --> J{New Job?}
    J -- No --> K[Skip to Next Card]
    J -- Yes --> L[Click Job Description]
    L --> M[Parse Posting Time]
    M --> N[Bucket Time: <30m, <1h, etc.]
    N --> O[Extract Raw Description]
    O --> P[Send to Ollama LLM]
    P --> Q{Relevant Fit?}
    Q -- Score ≥ 7 --> R[Save to SQLite DB]
    Q -- Score < 7 --> S[Discard Job]
    R --> T[Add to Results Dataframe]
    S --> T
    T --> U{More Jobs?}
    U -- Yes --> V[Continue Processing]
    U -- No --> W[Export to CSV]
    W --> X[Display Results in Gradio]
    X --> Y[End: User Can Apply/Export]
    
    subgraph Deep Scoping
        direction TB
        Z[24hr Search Only Duplicates?] --> AA[Expand to Past Week]
        AA --> AB[Still Only Duplicates?]
        AB --> AC[Expand to Past Month]
        AC --> AD[Stop on Consecutive Known IDs]
    end
    
    style A fill:#e3f2fd,stroke:#1565c0
    style B fill:#fff3e0,stroke:#ef6c00
    style C fill:#e8f5e8,stroke:#2e7d32
    style D fill:#f3e5f5,stroke:#6a1b9a
    style E fill:#ffebee,stroke:#c62828
    style F fill:#fff8e1,stroke:#ff6f00
    style G fill:#e3f2fd,stroke:#1565c0
    style H fill:#f3e5f5,stroke:#6a1b9a
    style I fill:#e8f5e8,stroke:#2e7d32
    style J fill:#fff3e0,stroke:#ef6c00
    style K fill:#ffebee,stroke:#c62828
    style L fill:#f3e5f5,stroke:#6a1b9a
    style M fill:#e8f5e8,stroke:#2e7d32
    style N fill:#fff8e1,stroke:#ff6f00
    style O fill:#e3f2fd,stroke:#1565c0
    style P fill:#fff3e0,stroke:#ef6c00
    style Q fill:#e8f5e8,stroke:#2e7d32
    style R fill:#ffebee,stroke:#c62828
    style S fill:#fff8e1,stroke:#ff6f00
    style T fill:#e3f2fd,stroke:#1565c0
    style U fill:#fff3e0,stroke:#ef6c00
    style V fill:#e8f5e8,stroke:#2e7d32
    style W fill:#ffebee,stroke:#c62828
    style X fill:#fff8e1,stroke:#ff6f00
    style Y fill:#e3f2fd,stroke:#1565c0
    style Z fill:#f3e5f5,stroke:#6a1b9a
    style AA fill:#e8f5e8,stroke:#2e7d32
    style AB fill:#fff8e1,stroke:#ff6f00
    style AC fill:#e3f2fd,stroke:#1565c0
    style AD fill:#fff3e0,stroke:#ef6c00
```

## LLM Evaluation Schema
The agent instructs the LLM to output JSON matching this schema:
```json
{
  "is_relevant_fit": boolean,
  "requires_edge_hardware": boolean,
  "hardware_mentioned": ["list"],
  "requires_robotics_stack": boolean,
  "protocols_mentioned": ["list"],
  "years_experience_required": integer,
  "remote_policy": "string",
  "match_score_1_to_10": integer (1-10),
  "red_flags": ["list"]
}
```

## Customization
- Adjust the relevance threshold (currently 7/10) in `agent.py`
- Modify time buckets in the `time_bucket()` function
- Change LinkedIn search parameters in the `scrape_linkedin_jobs()` function
- Add new evaluation criteria to the LLM prompt and database schema

## Privacy & Security
- **Zero data leaves your machine** unless you explicitly share CSV exports
- LinkedIn session stored only locally in Chrome user data format
- No external APIs called except Ollama (running locally)
- Playwright operates in headless mode after initial setup
- Respects robots.txt via reasonable throttling

## Troubleshooting
- **"Model not found"**: Make sure Ollama is running (`ollama serve`) and you've pulled a model
- **Login issues**: Re-run `interactive_login.py` to refresh your session
- **Slow performance**: Increase throttle value in the UI
- **No jobs found**: Check your LinkedIn credentials and search terms
- **CAPTCHA blocks**: Increase throttle or solve manually during interactive login

## License
MIT License - Feel free to modify and extend for your job search needs.

---
**Built with ❤️ for private, efficient job hunting**
