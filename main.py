"""
Main entry point for the FastMCP Agentforce Streaming Bridge Server.

This script initializes and runs a FastMCP server that provides a tool for
streaming conversations with a Salesforce Agentforce Agent. It handles
configuration, authentication, and the streaming of responses back to the client.
"""

import os
import uuid
import logging
import dotenv
from fastmcp import FastMCP, Context
from pydantic import BaseModel, Field
from auth_manager import AuthManager
from agentforce_client import AgentforceClient

dotenv.load_dotenv()

# --- Logging Setup ---
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    handlers=[
        logging.StreamHandler(),
    ]
)
logger = logging.getLogger(__name__)

# --- 1. Configuration & Constants ---

# Salesforce OAuth Endpoints & Credentials
SF_DOMAIN_URL = os.environ.get("SF_DOMAIN_URL")
SF_CLIENT_ID = os.environ.get("SF_CLIENT_ID","NOT_SET")
SF_CLIENT_SECRET = os.environ.get("SF_CLIENT_SECRET","NOT_SET")
PORT = os.environ.get("PORT",8000)
SF_TOKEN_URL = f"{SF_DOMAIN_URL}/services/oauth2/token"

# --- 2. FastMCP Server and Tool Definition ---

auth_manager = AuthManager(SF_CLIENT_ID, SF_CLIENT_SECRET, SF_TOKEN_URL)
agentforce_client = AgentforceClient(auth_manager)

mcp = FastMCP("AgentforceOAuthStreamingBridge")

class AskAgentforceStreamingInput(BaseModel):
    user_query: str = Field(..., description="The complete question or request for the Agentforce Agent.")

async def ask_agentforce_stream(
    input_data: AskAgentforceStreamingInput, 
    ctx: Context
):
    """
    Engages in a streaming conversation with the Salesforce Agentforce Agent.

    This asynchronous generator function starts a session with the Agentforce API,
    streams the user's query, and yields the response chunks as they are received.
    It also handles errors and session termination.

    Args:
        input_data: The input data containing the user's query.
        ctx: The FastMCP context for logging and interaction.

    Yields:
        Response chunks from the Agentforce Agent.
    """
    user_query = input_data.user_query
    # Use uuid.uuid4() to generate a random externalSessionKey
    user_key = str(uuid.uuid4())
    
    session_id = None

    await ctx.info(f"Starting Agentforce session with external key: {user_key}")
    try:
        # 1. Start Session (OAuth token is checked/refreshed within client)
        session_id = await agentforce_client.start_session(user_key)
        
        await ctx.info(f"Agentforce Session ID received: {session_id}. Streaming query...")
        # 2. Stream Message
        async for chunk in agentforce_client.stream_message(session_id, user_query,ctx):
            # 3. Stream Response to MCP Client by yielding chunks
            yield chunk # <-- MODIFIED to use yield
            
    
        await ctx.info("Agentforce stream completed.")
        
    except Exception as e:
        error_detail = f"An error occurred during Agentforce operation: {e}"
        await ctx.error(error_detail)
        # Send error message as output chunk
        yield f"\n[ERROR: {error_detail}]" 

    finally:
        if session_id:
            # 4. End Session (Uses DELETE on the session resource)
            try:
                await agentforce_client.end_session(session_id)
                await ctx.info(f"Agentforce Session {session_id} ended successfully.")
            except Exception as e:
                await ctx.warning(f"Failed to gracefully end Agentforce session {session_id}: {e}")

    # Note: No final return statement is needed for async generator functions.


@mcp.tool(
    description="Engages in a real-time, streaming conversation with the Salesforce Agentforce Agent. It securely manages authentication and streams the response text back.",
)
async def run_ask_agentforce_stream(
    input_data: AskAgentforceStreamingInput, 
    ctx: Context
):
    """
    FastMCP tool that consumes the ask_agentforce_stream generator.

    This function collects all the streamed chunks from the ask_agentforce_stream
    generator and returns the complete response as a single string.

    Args:
        input_data: The input data containing the user's query.
        ctx: The FastMCP context.

    Returns:
        The full response from the Agentforce Agent.
    """
    full_response = ""
    print("Starting testme execution...")
    # The 'async for' loop is what consumes the asynchronous generator
    async for chunk in ask_agentforce_stream(input_data,ctx):
        full_response += chunk
        # Optional: print chunks as they arrive for debugging
        print(f"Chunk received: {chunk}", end="", flush=True)
        
    return full_response
  
# --- 5. Running the FastMCP Server ---

if __name__ == "__main__":
    # Ensure a valid token is available before starting the server
    try:
        # NOTE: Using synchronous _fetch_new_token for pre-start check.
        # This will still block and may show the ConnectError here, but the rest of the application logic is fixed.
        import asyncio
        asyncio.run(auth_manager._fetch_new_token())
        
    except Exception as e:
        print(f"FATAL: Initial Salesforce authentication failed. Please check credentials.")
        print(e)
        exit(1)
        
    print("FastMCP Agentforce Streaming Bridge Server is starting...")
    
    # Run using the Streamable HTTP transport
    mcp.run(transport='streamable-http', port=PORT)