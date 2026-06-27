<a name="start-building"></a>
<p align="center">
<img src="img/banner-build-26.png" alt="Microsoft Build 2026" width="1200"/>
</p>

# [Microsoft Build 2026](https://build.microsoft.com)

## 🔥 BRK231: Deploy, Observe, Learn — Reinforcement Learning for Production Agents

### Session Description

Improve a multi-tool AI agent using SFT distillation and reinforcement fine-tuning (RFT). Starting with a 6-tool retail customer service agent that struggles with complex business rules, this session shows how fine-tuned models dramatically outperform base models — with Qwen3-32B RFT achieving 86.9% quality, beating even the GPT-5.4 teacher model (64.5%).

### 🏫 Getting started in a guided session

To get started in a guided lab session:
- Open this repo in a Codespace (click the green **Code** button → **Create a Codespace**)
- Run `pip install -r requirements.txt` to install dependencies
- Follow along with the notebooks in `src/notebooks/` as the instructor demonstrates each phase

### 🏠 Getting started in your own environment

If you're following these steps at your own pace:
- Clone this repository
- Install Python 3.12+ and run `pip install -r requirements.txt`
- Install Azure CLI (`az`) and Azure Developer CLI (`azd`) >= 1.25.x
- Copy `.env.example` to `.env` and fill in your Azure AI Foundry project details
- Follow the [deployment guide](#-deployment) to provision infrastructure and deploy agents

### 🧠 Learning Outcomes

By the end of this session, you will be able to:

- Deploy and evaluate multi-tool AI agents on Azure AI Foundry
- Apply SFT distillation to teach smaller models from production agent traces
- Apply reinforcement fine-tuning (RFT) using custom Python graders as reward functions
- Use low-level RFT APIs for open-weight models (Qwen3-32B) with full training control
- Compare base, SFT, and RFT model performance using structured evaluations

### 💬 Keep Learning with Copilot

Try these prompts with GitHub Copilot to explore the topics from this session. Open Copilot Chat in Visual Studio Code (`Ctrl+Alt+I` on Windows/Linux, `Cmd+Shift+I` on Mac), paste a prompt, and see what you learn. Try connecting the [Microsoft Learn MCP Server](#-microsoft-learn-mcp-server) for the latest official documentation.

Use these as a starting point — or write your own!

- "Explain the difference between SFT distillation and reinforcement fine-tuning for AI agents"
- "How do I write a custom Python grader for reinforcement fine-tuning on Azure AI Foundry?"
- "What is the Azure AI Agents SDK and how do I deploy an agent with tools?"
- "Show me how to submit an RFT job using the Azure AI Foundry SDK with a custom reward function"
- "How do I use azd to deploy multiple agent variants with different model configurations?"

### 💻 Technologies Used

1. [Azure AI Foundry](https://ai.azure.com) — Agent deployment, evaluation, and fine-tuning
1. [Azure AI Agents SDK](https://learn.microsoft.com/azure/ai-services/agents/) — Multi-tool agent orchestration
1. [Azure Developer CLI (azd)](https://learn.microsoft.com/azure/developer/azure-developer-cli/) — Infrastructure provisioning and deployment
1. [Azure Functions](https://learn.microsoft.com/azure/azure-functions/) — Tool server hosting
1. [OpenTelemetry](https://opentelemetry.io/) — Agent tracing and observability

### 📚 Resources and Next Steps

| Resource | Description |
|:---------|:------------|
| [Azure AI Foundry Documentation](https://learn.microsoft.com/azure/ai-studio/) | Platform for building, evaluating, and deploying AI agents |
| [Fine-tuning on Azure AI Foundry](https://learn.microsoft.com/azure/ai-studio/concepts/fine-tuning-overview) | SFT and RFT fine-tuning documentation |
| [Azure AI Agents SDK](https://learn.microsoft.com/azure/ai-services/agents/) | Build multi-tool agents with Azure |
| [LAB521: Improving agent behavior using reinforcement learning from traces](https://github.com/microsoft/Build26-LAB521-improving-agent-behavior-using-reinforcement-learning-from-traces) | Related Build 2026 lab repository |
| [https://aka.ms/build26-next-steps](https://aka.ms/build26-next-steps) | Explore lab and session repos to further your learning from Microsoft Build |
| [Watch the session recording](https://aka.ms/build26/BRK231/youtube) | Watch the recorded Microsoft Build session. |


### 📁 Repo Structure

```
├── src/
│   ├── agents/retail/          # Source agent (6-tool orchestration)
│   ├── scripts/                # Deploy, eval, and grader scripts
│   ├── notebooks/              # Jupyter notebooks (demo flow)
│   ├── tools/retail-tools/     # Tool server (Azure Functions)
│   └── data/                   # Datasets, dashboards, eval results
├── deploy/                     # Azure Developer CLI (azd) deployment
│   ├── azure.yaml              # Service definitions (13 agent variants)
│   ├── infra/                  # Bicep templates
│   └── src/                    # Per-model agent deployments
├── docs/                       # Phase guides (session walkthrough)
├── .env.example                # Environment variable template
└── requirements.txt            # Python dependencies
```

### 🚀 Deployment

All agents deploy via Azure Developer CLI (`azd`):

```bash
cd deploy
azd ai agent init -m ../src/agents/retail/agent.manifest.yaml
azd env set enableHostedAgentVNext true
azd provision
azd deploy
```

See the [Quick Start](#-getting-started-in-your-own-environment) section above for full setup instructions.

### 📊 Key Results

| Model | retail_quality | Approach |
|-------|:---:|---|
| qwen3-32b-finetuned | 86.9% | RFT fine-tuned |
| o4-mini-finetuned | 82.3% | RFT fine-tuned |
| gpt-4-1-mini-finetuned | 71.0% | SFT fine-tuned |
| o4-mini (base) | 71.0% | Base model |
| gpt-5-4 (teacher) | 64.5% | Teacher model |
| gpt-4-1 (base) | 58.1% | Base model |


### 🌟 Microsoft Learn MCP Server

The Microsoft Learn MCP Server gives your AI agent direct access to Microsoft's official documentation — grounded, up-to-date answers about the products and services covered in this session.

**VS Code** — One click installation: 

[![Install in VS Code](https://img.shields.io/badge/VS_Code-Install_Microsoft_Learn_MCP-0098FF?style=flat-square&logo=visualstudiocode&logoColor=white)](https://vscode.dev/redirect/mcp/install?name=microsoft-learn&config=%7B%22type%22%3A%22http%22%2C%22url%22%3A%22https%3A%2F%2Flearn.microsoft.com%2Fapi%2Fmcp%22%7D)


**GitHub Copilot CLI** — Run this to install the Learn MCP Server as a plugin:
```
/plugin install microsoftdocs/mcp
```

For more info, other clients, and to post questions, visit the [Learn MCP Server repo](https://aka.ms/learnmcp).

## Content Owners

<table>
<tr>
    <td align="center"><a href="https://github.com/omkarmore83">
        <img src="https://github.com/omkarmore83.png" width="100px;" alt="Omkar More"/><br />
        <sub><b>Omkar More</b></sub></a><br />
            <a href="https://github.com/omkarmore83" title="talk">📢</a>
    </td>
    <td align="center"><a href="https://github.com/aliciaframe">
        <img src="https://github.com/aliciaframe.png" width="100px;" alt="Alicia Frame"/><br />
        <sub><b>Alicia Frame</b></sub></a><br />
            <a href="https://github.com/aliciaframe" title="talk">📢</a>
    </td>
</tr></table>

## Contributing

This project welcomes contributions and suggestions.  Most contributions require you to agree to a
Contributor License Agreement (CLA) declaring that you have the right to, and actually do, grant us
the rights to use your contribution. For details, visit [Contributor License Agreements](https://cla.opensource.microsoft.com).

When you submit a pull request, a CLA bot will automatically determine whether you need to provide
a CLA and decorate the PR appropriately (e.g., status check, comment). Simply follow the instructions
provided by the bot. You will only need to do this once across all repos using our CLA.

This project has adopted the [Microsoft Open Source Code of Conduct](https://opensource.microsoft.com/codeofconduct/).
For more information see the [Code of Conduct FAQ](https://opensource.microsoft.com/codeofconduct/faq/) or
contact [opencode@microsoft.com](mailto:opencode@microsoft.com) with any additional questions or comments.

## Trademarks

This project may contain trademarks or logos for projects, products, or services. Authorized use of Microsoft
trademarks or logos is subject to and must follow
[Microsoft's Trademark & Brand Guidelines](https://www.microsoft.com/legal/intellectualproperty/trademarks/usage/general).
Use of Microsoft trademarks or logos in modified versions of this project must not cause confusion or imply Microsoft sponsorship.
Any use of third-party trademarks or logos are subject to those third-party's policies.
