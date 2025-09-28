# Agentforce MCP Server

This project is a proof-of-concept (PoC) demonstrating how to create a streaming bridge between a FastMCP server and the Salesforce Agentforce API. It's intended for educational purposes to show how to manage OAuth 2.0 authentication and handle Server-Sent Events (SSE) from the Agentforce API.

This streams responses from Agentforce using SSE and turns it into a Streamable HTTP based MCP Server.  
This example also works with elicitations, so agentforce can ask clarifying questions back to the MCP client if necessary.

---

## Getting Started

These instructions will get you a copy of the project up and running on your local machine for development and testing purposes.

### Prerequisites

* Python 3.12 or higher
* `uv` for installing dependencies
* A Salesforce instance with Agentforce enabled and a connected app using client credentials with a client ID and secret.

### Installation

1. **Clone the repository:**

```bash
git clone <your-repository-url>
cd agentforce_mcp_server
```

2. **Install dependencies:**

```bash
uv venv
source .venv/bin/activate
uv sync
```

---

## Configuration

This assumes that you have set up agentforce to be accessible to call via an api (you'll have to setup a connected app and enable client credentials.).  
You will also need to enable CORS for the OAuth endpoints in the Salesforce setup.

1. **Create a `.env` file** in the root of the project.
2. **Add the following environment variables** to the `.env` file, replacing the placeholder values with your actual Salesforce credentials:

    ```bash
    SF_CLIENT_ID=YOUR_SALESFORCE_CLIENT_ID
    SF_CLIENT_SECRET=YOUR_SALESFORCE_CLIENT_SECRET
    AGENTFORCE_AGENT_ID=YOUR_AGENTFORCE_AGENT_ID ( i.e. 0XxHu000000jrBSKAY )
    SF_DOMAIN_URL=https://your-salesforce-instance.my.salesforce.com
    PORT=8000
    ```

---

## Usage

To run the FastMCP server, execute the following command from the root of the project:

```bash
uv run main.py
```

The MCP Server will start on [localhost:8000](http://127.0.0.1:8000/mcp) by default, unless you set a PORT environment variable